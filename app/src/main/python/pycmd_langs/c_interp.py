"""A C interpreter that runs on the phone.

Why an interpreter and not a compiler: since Android 10 an app may not make
memory executable, nor load a shared library it wrote itself (W^X, enforced by
SELinux). A compiler could emit perfectly good machine code and then be unable
to execute one instruction of it. An interpreter never generates code - it
walks the parsed program - so the restriction does not apply, which is the same
reason CPython itself runs here.

The memory model is what makes real C work rather than a toy:

* Every object lives in a *storage*, which is a plain Python list. A scalar has
  a storage of length one, an array a storage of length n.
* An lvalue is the pair `(storage, index)`, so `&x`, `&a[i]` and `&s.field` are
  all the same operation.
* A `Pointer` is that same pair, which makes `p + 1`, `*p`, `p[i]` and pointer
  comparison fall out naturally, and makes `malloc` just another storage.

That is enough for the pointer idioms C programs are actually written with:
walking a string, passing an array to a function, out-parameters, linked
structures built from malloc.
"""

from __future__ import annotations

import math
import random
import sys

from .c_lexer import CSyntaxError
from .c_parser import CType, parse

MAX_DEPTH = 220
INT_MIN = -(2 ** 31)
INT_MAX = 2 ** 31 - 1


class CRuntimeError(Exception):
    def __init__(self, message: str, line: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Exit(Exception):
    def __init__(self, code):
        self.code = code


class _Window:
    """A writable view of part of a storage list.

    `initialise` fills an array by assigning into the list it is handed, so
    handing it `storage[a:b]` hands it a *copy* and every write lands in
    something that is thrown away a moment later. That is why a row of a
    two-dimensional array initialised to zeroes. A window forwards the writes
    to the real list instead.
    """

    __slots__ = ("_storage", "_start", "_length")

    def __init__(self, storage, start: int, length: int) -> None:
        self._storage = storage
        self._start = start
        self._length = max(0, min(length, len(storage) - start))

    def __len__(self) -> int:
        return self._length

    def __getitem__(self, index):
        if isinstance(index, slice):
            start, stop, _ = index.indices(self._length)
            return _Window(self._storage, self._start + start, stop - start)
        if not (0 <= index < self._length):
            raise IndexError(index)
        return self._storage[self._start + index]

    def __setitem__(self, index, value) -> None:
        if not (0 <= index < self._length):
            raise IndexError(index)
        self._storage[self._start + index] = value

    def extend(self, values) -> None:
        # Only `char buf[] = "text"` reaches this, and a window is always a
        # row of something already sized, so there is nothing to grow into.
        raise CRuntimeError("cannot size an array from inside another one")


class Pointer:
    """A location inside a storage list. `NULL` is a pointer to nothing.

    `shape` is what is left of a multi-dimensional array after the dimensions
    already indexed. A C array is one flat run of memory and `grid[r][c]` is
    arithmetic on it - `r * columns + c` - so `grid` decaying to a pointer has
    to remember how wide a row is or the second `[` has nothing to work with.
    That is what shape is: the dimensions still to come. An ordinary pointer
    has none, and behaves exactly as it always did.
    """

    __slots__ = ("storage", "index", "base", "shape")

    def __init__(self, storage, index: int = 0, base: str = "int",
                 shape=None) -> None:
        self.storage = storage
        self.index = index
        self.base = base
        self.shape = list(shape or [])

    @property
    def stride(self) -> int:
        """How many cells one step of this pointer covers."""
        step = 1
        for size in self.shape:
            step *= max(int(size), 0)
        return step

    @property
    def is_null(self) -> bool:
        return self.storage is None

    def offset(self, delta: int) -> "Pointer":
        return Pointer(self.storage, self.index + delta * (self.stride or 1),
                       self.base, self.shape)

    def read(self):
        if self.storage is None:
            raise CRuntimeError("dereferenced a NULL pointer")
        if not (0 <= self.index < len(self.storage)):
            raise CRuntimeError(
                f"pointer out of bounds (index {self.index}, size {len(self.storage)})"
            )
        return self.storage[self.index]

    def write(self, value) -> None:
        if self.storage is None:
            raise CRuntimeError("wrote through a NULL pointer")
        if not (0 <= self.index < len(self.storage)):
            raise CRuntimeError(
                f"pointer out of bounds (index {self.index}, size {len(self.storage)})"
            )
        self.storage[self.index] = value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "NULL" if self.is_null else f"<pointer +{self.index}>"


NULL = Pointer(None, 0)

# Constants the headers define, which programs use without declaring. NULL has
# to be the null pointer rather than plain 0 so that `p = NULL` stores a
# pointer and `p != NULL` compares like one.
BUILTIN_CONSTANTS = {
    "NULL": NULL,
    "EXIT_SUCCESS": 0,
    "EXIT_FAILURE": 1,
    "RAND_MAX": 32767,
    "INT_MAX": INT_MAX,
    "INT_MIN": INT_MIN,
    "CHAR_BIT": 8,
    "true": 1,
    "false": 0,
    "M_PI": math.pi,
    "M_E": math.e,
    "EOF": -1,
}


class CStruct:
    """A struct instance: one storage per field, so `&s.field` is expressible."""

    __slots__ = ("name", "fields")

    def __init__(self, name: str, fields: dict) -> None:
        self.name = name
        self.fields = fields

    def copy(self) -> "CStruct":
        return CStruct(self.name, {k: _copy_storage(v) for k, v in self.fields.items()})


def _copy_storage(storage):
    return [item.copy() if isinstance(item, CStruct) else item for item in storage]


class Interpreter:
    def __init__(self, program: dict, stdout=None, stdin=None, argv=None) -> None:
        self.functions = program["functions"]
        self.structs = program["structs"]
        self.enums = program["enums"]
        self.global_decls = program["globals"]
        self.globals: dict = {}
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stdin = stdin if stdin is not None else sys.stdin
        self.argv = argv or ["program"]
        self.depth = 0
        self._stdin_buffer = ""
        self._random = random.Random()

    # ------------------------------------------------------------------ output

    def write(self, text: str) -> None:
        self.stdout.write(text)

    def read_line(self) -> str:
        if self._stdin_buffer:
            buffered, self._stdin_buffer = self._stdin_buffer, ""
            return buffered
        return self.stdin.readline()

    def next_char(self) -> str:
        """One character of stdin, for getchar()."""
        if not self._stdin_buffer:
            self._stdin_buffer = self.stdin.readline()
            if not self._stdin_buffer:
                return ""
        character, self._stdin_buffer = self._stdin_buffer[0], self._stdin_buffer[1:]
        return character

    def next_token(self, single_char: bool = False):
        """One whitespace-delimited token, for scanf.

        scanf skips leading whitespace and reads across line boundaries, so a
        program that asks for three numbers works whether they were typed on
        one line or three.
        """
        while True:
            if not self._stdin_buffer:
                self._stdin_buffer = self.stdin.readline()
                if not self._stdin_buffer:
                    return None
            if single_char:
                character, self._stdin_buffer = self._stdin_buffer[0], self._stdin_buffer[1:]
                return character
            stripped = self._stdin_buffer.lstrip()
            if not stripped:
                self._stdin_buffer = ""
                continue
            self._stdin_buffer = stripped
            end = 0
            while end < len(self._stdin_buffer) and not self._stdin_buffer[end].isspace():
                end += 1
            token = self._stdin_buffer[:end]
            self._stdin_buffer = self._stdin_buffer[end:]
            return token

    # ------------------------------------------------------------------- types

    def zero_value(self, ctype: CType):
        if ctype.is_pointer:
            return NULL
        if ctype.base == "struct":
            return self.new_struct(ctype.struct_name)
        if ctype.base in ("float", "double"):
            return 0.0
        return 0

    def new_struct(self, name: str) -> CStruct:
        fields_spec = self.structs.get(name)
        if fields_spec is None:
            raise CRuntimeError(f"unknown struct '{name}'")
        fields = {}
        for field_name, field_type in fields_spec:
            fields[field_name] = self.allocate(field_type)
        return CStruct(name, fields)

    def allocate(self, ctype: CType, scope=None) -> list:
        """Creates the storage for a declaration and returns the list."""
        if ctype.is_array:
            sizes = []
            for dimension in ctype.array:
                if dimension is None:
                    sizes.append(0)
                else:
                    sizes.append(int(self.evaluate(dimension, scope if scope is not None else {})))
            total = 1
            for size in sizes:
                total *= max(size, 0)
            element = CType(ctype.base, ctype.pointer, [], ctype.struct_name)
            return [self.zero_value(element) for _ in range(total)]
        return [self.zero_value(ctype)]

    # ------------------------------------------------------------------- entry

    def run(self, entry: str = "main") -> int:
        # Each C frame costs several Python frames, so the interpreter needs
        # headroom to reach its own MAX_DEPTH and report a useful message
        # rather than dying of RecursionError first.
        if sys.getrecursionlimit() < 6000:
            sys.setrecursionlimit(6000)
        for name, ctype, init, line in self.global_decls:
            storage = self.allocate(ctype, {})
            self.globals[name] = (storage, ctype)
            if init is not None:
                self.initialise(storage, ctype, init, {}, line)

        function = self.functions.get(entry)
        if function is None:
            raise CRuntimeError(f"no {entry}() function to run")

        args = []
        if function["params"]:
            # main(int argc, char **argv)
            argv_storage = [self.make_string(a) for a in self.argv]
            args = [len(self.argv), Pointer(argv_storage, 0, "char")][: len(function["params"])]

        try:
            result = self.call_function(function, args, 0)
        except _Exit as exit_signal:
            return int(exit_signal.code)
        return int(result) if isinstance(result, (int, float)) else 0

    def make_string(self, text: str) -> Pointer:
        storage = [ord(c) & 0xFF for c in text] + [0]
        return Pointer(storage, 0, "char")

    def read_string(self, pointer) -> str:
        if not isinstance(pointer, Pointer):
            raise CRuntimeError("expected a string pointer")
        if pointer.is_null:
            return "(null)"
        out = []
        index = pointer.index
        storage = pointer.storage
        while index < len(storage):
            value = storage[index]
            if not isinstance(value, int) or value == 0:
                break
            out.append(chr(value & 0xFF))
            index += 1
        return "".join(out)

    # --------------------------------------------------------------- functions

    def call_function(self, function: dict, args: list, line: int):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth -= 1
            raise CRuntimeError(
                f"call stack too deep (over {MAX_DEPTH} frames) - infinite recursion?", line
            )
        scope = {}
        params = function["params"]
        for index, (param_name, param_type) in enumerate(params):
            value = args[index] if index < len(args) else self.zero_value(param_type)
            if isinstance(value, CStruct):
                value = value.copy()
            storage = [value]
            scope[param_name] = (storage, param_type)
        if function.get("variadic"):
            scope["__varargs__"] = (list(args[len(params):]), None)

        try:
            self.execute(function["body"], scope)
            return 0
        except _Return as returned:
            return returned.value
        except RecursionError:
            raise CRuntimeError(
                "call stack too deep - infinite recursion?", line
            ) from None
        finally:
            self.depth -= 1

    # -------------------------------------------------------------- statements

    def execute(self, node, scope) -> None:
        kind = node[0]

        if kind == "block":
            inner = dict(scope)
            for statement in node[1]:
                self.execute(statement, inner)
            # Names declared in the block do not escape it, but assignments to
            # outer names must: copy back anything that already existed.
            for name in scope:
                if name in inner:
                    scope[name] = inner[name]
            return

        if kind == "expr":
            self.evaluate(node[1], scope)
            return

        if kind == "empty":
            return

        if kind == "declare":
            for name, ctype, init in node[1]:
                storage = self.allocate(ctype, scope)
                scope[name] = (storage, ctype)
                if init is not None:
                    self.initialise(storage, ctype, init, scope, node[2])
            return

        if kind == "if":
            if truthy(self.evaluate(node[1], scope)):
                self.execute(node[2], scope)
            elif node[3] is not None:
                self.execute(node[3], scope)
            return

        if kind == "while":
            while truthy(self.evaluate(node[1], scope)):
                try:
                    self.execute(node[2], scope)
                except _Break:
                    break
                except _Continue:
                    continue
            return

        if kind == "dowhile":
            while True:
                try:
                    self.execute(node[2], scope)
                except _Break:
                    break
                except _Continue:
                    pass
                if not truthy(self.evaluate(node[1], scope)):
                    break
            return

        if kind == "for":
            inner = dict(scope)
            if node[1] is not None:
                self.execute(node[1], inner)
            while True:
                if node[2] is not None and not truthy(self.evaluate(node[2], inner)):
                    break
                try:
                    self.execute(node[4], inner)
                except _Break:
                    break
                except _Continue:
                    pass
                if node[3] is not None:
                    self.evaluate(node[3], inner)
            for name in scope:
                if name in inner:
                    scope[name] = inner[name]
            return

        if kind == "switch":
            subject = self.evaluate(node[1], scope)
            cases = node[2]
            start = None
            for position, (value, _) in enumerate(cases):
                if value is not None and self.evaluate(value, scope) == subject:
                    start = position
                    break
            if start is None:
                for position, (value, _) in enumerate(cases):
                    if value is None:
                        start = position
                        break
            if start is None:
                return
            try:
                # Fall-through is the point of switch: run every case from here.
                for _, statements in cases[start:]:
                    for statement in statements:
                        self.execute(statement, scope)
            except _Break:
                pass
            return

        if kind == "return":
            raise _Return(self.evaluate(node[1], scope) if node[1] is not None else 0)

        if kind == "break":
            raise _Break()

        if kind == "continue":
            raise _Continue()

        raise CRuntimeError(f"cannot execute {kind}", node[-1] if isinstance(node[-1], int) else 0)

    def _dimensions(self, ctype: CType, scope) -> list:
        """A type's array sizes as numbers, for working out a row's width."""
        sizes = []
        for dimension in ctype.array:
            if dimension is None:
                sizes.append(0)
            else:
                try:
                    sizes.append(int(self.evaluate(dimension, scope or {})))
                except Exception:  # noqa: BLE001 - a size that will not count
                    sizes.append(0)
        return sizes

    def initialise(self, storage, ctype: CType, init, scope, line: int) -> None:
        if init[0] == "initlist":
            items = init[1]
            if ctype.base == "struct" and not ctype.is_array:
                target = storage[0]
                spec = self.structs.get(ctype.struct_name, [])
                for index, item in enumerate(items):
                    if index >= len(spec):
                        break
                    field_name, field_type = spec[index]
                    self.initialise(target.fields[field_name], field_type, item, scope, line)
                return
            # `int grid[2][3] = {{1,2,3},{4,5,6}}` - each inner list fills one
            # row, and a row is three cells along in one flat run of storage.
            # Stepping one cell per initialiser, as this used to, put the
            # second row on top of the first and then ran out of room.
            sizes = self._dimensions(ctype, scope)
            row = 1
            for size in sizes[1:]:
                row *= max(int(size), 0)
            row = max(row, 1)

            # `int scores[] = {3, 1, 4}` leaves the first dimension out and
            # lets the list decide it. The type says nothing, so storage was
            # allocated empty and the first initialiser had nowhere to go.
            if sizes and sizes[0] == 0 and len(storage) == 0:
                element = CType(ctype.base, ctype.pointer, [], ctype.struct_name)
                storage.extend(self.zero_value(element)
                               for _ in range(len(items) * row))

            for index, item in enumerate(items):
                # Anything at all, once there is more than one dimension,
                # fills a whole row: `{1,2,3}` fills it cell by cell and
                # `"ab"` - which is how `char names[2][6] = {"ab", "cd"}` is
                # written - copies its characters in. Both are the row's
                # business, so both recurse into the row.
                if len(sizes) > 1:
                    start = index * row
                    if start >= len(storage):
                        raise CRuntimeError("too many initialisers for this array", line)
                    inner = CType(ctype.base, ctype.pointer, list(ctype.array[1:]),
                                  ctype.struct_name)
                    self.initialise(_Window(storage, start, row), inner, item, scope, line)
                    continue
                if index >= len(storage):
                    raise CRuntimeError("too many initialisers for this array", line)
                if item[0] == "initlist":
                    element = CType(ctype.base, ctype.pointer, [], ctype.struct_name)
                    self.initialise(_Window(storage, index, 1), element, item, scope, line)
                else:
                    storage[index] = self.coerce(self.evaluate(item, scope), ctype)
            return

        value = self.evaluate(init, scope)

        # char buf[] = "text" copies the characters into the array.
        if ctype.is_array and isinstance(value, Pointer) and ctype.base == "char":
            text = self.read_string(value)
            if len(storage) == 0:
                storage.extend([0] * (len(text) + 1))
            for index in range(len(storage)):
                storage[index] = ord(text[index]) if index < len(text) else 0
            return

        if isinstance(value, CStruct):
            value = value.copy()
        storage[0] = self.coerce(value, ctype)

    def coerce(self, value, ctype: CType):
        if ctype.is_pointer or ctype.is_array:
            # `int *p = 0;` - a literal zero is a null pointer constant in C,
            # so it has to become a pointer, not stay an integer.
            if value == 0 and isinstance(value, int) and not isinstance(value, bool):
                return NULL
            # `struct Node *n = malloc(sizeof(struct Node));` hands back raw
            # storage full of zeroes. The declared type is what says those
            # slots are structs, so materialise them here - with or without an
            # explicit cast, since C converts void* implicitly.
            if (
                isinstance(value, Pointer)
                and ctype.base == "struct"
                and ctype.pointer == 1
                and not value.is_null
            ):
                self.materialise_structs(value, ctype.struct_name)
            return value
        if ctype.base in ("float", "double"):
            return float(value) if isinstance(value, (int, float)) else value
        if ctype.base == "char" and isinstance(value, (int, float)):
            return int(value) & 0xFF
        if ctype.base == "int" and isinstance(value, float):
            return int(value)
        return value

    # ------------------------------------------------------------- expressions

    def lookup(self, name: str, scope, line: int):
        if name in scope:
            return scope[name]
        if name in self.globals:
            return self.globals[name]
        raise CRuntimeError(f"'{name}' is not declared", line)

    def lvalue(self, node, scope):
        """Resolves an expression to the (storage, index) it names."""
        kind = node[0]

        if kind == "name":
            storage, ctype = self.lookup(node[1], scope, node[2])
            return storage, 0, ctype

        if kind == "index":
            base = self.evaluate(node[1], scope)
            offset = int(self.evaluate(node[2], scope))
            if isinstance(base, Pointer):
                if base.is_null:
                    raise CRuntimeError("indexed a NULL pointer", node[3])
                return (base.storage, base.index + offset * (base.stride or 1),
                        CType(base.base))
            raise CRuntimeError("indexed something that is not an array or pointer", node[3])

        if kind == "deref":
            pointer = self.evaluate(node[1], scope)
            if not isinstance(pointer, Pointer):
                raise CRuntimeError("dereferenced something that is not a pointer", node[2])
            if pointer.is_null:
                raise CRuntimeError("dereferenced a NULL pointer", node[2])
            return pointer.storage, pointer.index, CType(pointer.base)

        if kind == "member":
            _, target, field, through_pointer = node
            if through_pointer:
                pointer = self.evaluate(target, scope)
                if not isinstance(pointer, Pointer):
                    raise CRuntimeError(f"'->{field}' used on something that is not a pointer")
                struct = pointer.read()
            else:
                storage, index, _ = self.lvalue(target, scope)
                struct = storage[index]
            if not isinstance(struct, CStruct):
                raise CRuntimeError(f"'.{field}' used on something that is not a struct")
            if field not in struct.fields:
                raise CRuntimeError(f"struct {struct.name} has no field '{field}'")
            return struct.fields[field], 0, CType("int")

        raise CRuntimeError("this expression cannot be assigned to")

    def evaluate(self, node, scope):
        kind = node[0]

        if kind == "const":
            return node[1]

        if kind == "string":
            return self.make_string(node[1])

        if kind == "name":
            name = node[1]
            if name in self.enums:
                return self.enums[name]
            if name not in scope and name not in self.globals:
                if name in self.functions:
                    return ("__function__", name)
                if name in BUILTIN_CONSTANTS:
                    return BUILTIN_CONSTANTS[name]
                raise CRuntimeError(f"'{name}' is not declared", node[2])
            storage, ctype = self.lookup(name, scope, node[2])
            if ctype is not None and ctype.is_array:
                return Pointer(storage, 0, ctype.base,
                               self._dimensions(ctype, scope)[1:])
            return storage[0]

        if kind == "assign":
            return self.do_assign(node, scope)

        if kind == "binary":
            return self.do_binary(node, scope)

        if kind == "unary":
            operand = self.evaluate(node[2], scope)
            op = node[1]
            if op == "-":
                return -operand
            if op == "+":
                return +operand
            if op == "!":
                return 0 if truthy(operand) else 1
            if op == "~":
                return ~int(operand)

        if kind == "deref":
            storage, index, _ = self.lvalue(node, scope)
            if not (0 <= index < len(storage)):
                raise CRuntimeError(
                    f"pointer out of bounds (index {index}, size {len(storage)})", node[2]
                )
            return storage[index]

        if kind == "addressof":
            target = node[1]
            if target[0] == "name":
                storage, ctype = self.lookup(target[1], scope, target[2])
                if ctype is not None and ctype.is_array:
                    return Pointer(storage, 0, ctype.base)
                return Pointer(storage, 0, ctype.base if ctype else "int")
            storage, index, ctype = self.lvalue(target, scope)
            return Pointer(storage, index, ctype.base if ctype else "int")

        if kind == "index":
            base = self.evaluate(node[1], scope)
            if isinstance(base, Pointer) and base.shape:
                # `grid[1]` where grid is int[2][3] is the second row: still a
                # place, not a value, and the next `[` indexes into it.
                if base.is_null:
                    raise CRuntimeError("indexed a NULL pointer", node[3])
                offset = int(self.evaluate(node[2], scope))
                return Pointer(base.storage, base.index + offset * base.stride,
                               base.base, base.shape[1:])
            storage, index, _ = self.lvalue(node, scope)
            if not (0 <= index < len(storage)):
                raise CRuntimeError(
                    f"index {index} is outside the array (size {len(storage)})", node[3]
                )
            return storage[index]

        if kind == "member":
            storage, index, _ = self.lvalue(node, scope)
            return storage[index]

        if kind == "call":
            return self.do_call(node, scope)

        if kind == "ternary":
            return self.evaluate(node[2] if truthy(self.evaluate(node[1], scope)) else node[3], scope)

        if kind == "comma":
            self.evaluate(node[1], scope)
            return self.evaluate(node[2], scope)

        if kind == "preincr":
            storage, index, ctype = self.lvalue(node[2], scope)
            storage[index] = self.step(storage[index], 1 if node[1] == "++" else -1)
            return storage[index]

        if kind == "postincr":
            storage, index, ctype = self.lvalue(node[2], scope)
            previous = storage[index]
            storage[index] = self.step(previous, 1 if node[1] == "++" else -1)
            return previous

        if kind == "cast":
            value = self.evaluate(node[2], scope)
            return self.coerce(value, node[1])

        if kind == "sizeof_type":
            return self.sizeof(node[1])

        if kind == "sizeof_expr":
            value = self.evaluate(node[1], scope)
            if isinstance(value, Pointer):
                return 8
            if isinstance(value, CStruct):
                return sum(
                    self.sizeof(field_type) for _, field_type in self.structs.get(value.name, [])
                ) or 1
            return 8 if isinstance(value, float) else 4

        raise CRuntimeError(f"cannot evaluate {kind}")

    def materialise_structs(self, pointer: "Pointer", struct_name: str) -> None:
        """Turns freshly allocated zeroes into struct instances.

        Only untouched slots are replaced, so casting a pointer that already
        addresses structs leaves the data alone.
        """
        storage = pointer.storage
        if storage is None or struct_name not in self.structs:
            return
        if any(isinstance(slot, CStruct) for slot in storage):
            return
        if not all(isinstance(slot, int) and slot == 0 for slot in storage):
            return
        unit = self.sizeof(CType("struct", 0, struct_name=struct_name)) or 1
        count = max(1, len(storage) // unit)
        storage[:] = [self.new_struct(struct_name) for _ in range(count)]

    def sizeof(self, ctype: CType) -> int:
        if ctype.is_pointer:
            return 8
        if ctype.base == "struct":
            total = sum(
                self.sizeof(field_type) for _, field_type in self.structs.get(ctype.struct_name, [])
            )
            return total or 1
        return {"char": 1, "int": 4, "float": 4, "double": 8, "void": 1}.get(ctype.base, 4)

    def step(self, value, delta: int):
        if isinstance(value, Pointer):
            return value.offset(delta)
        return value + delta

    def do_assign(self, node, scope):
        _, op, target, source = node
        value = self.evaluate(source, scope)
        storage, index, ctype = self.lvalue(target, scope)

        if op != "=":
            current = storage[index]
            arithmetic = op[:-1]
            value = self.apply_binary(arithmetic, current, value)
        elif ctype is not None and (ctype.is_pointer or ctype.base in ("float", "double", "char")):
            value = self.coerce(value, ctype)

        if isinstance(value, CStruct):
            value = value.copy()
        elif isinstance(storage[index], int) and isinstance(value, float) and not isinstance(storage[index], bool):
            # Assigning a double into an int variable truncates, as C does.
            if not isinstance(storage[index], Pointer):
                value = int(value)
        elif isinstance(storage[index], float) and isinstance(value, int):
            value = float(value)

        storage[index] = value
        return value

    def do_binary(self, node, scope):
        _, op, left_node, right_node = node
        if op == "&&":
            return 1 if truthy(self.evaluate(left_node, scope)) and truthy(self.evaluate(right_node, scope)) else 0
        if op == "||":
            return 1 if truthy(self.evaluate(left_node, scope)) or truthy(self.evaluate(right_node, scope)) else 0
        return self.apply_binary(op, self.evaluate(left_node, scope), self.evaluate(right_node, scope))

    def apply_binary(self, op, left, right):
        # Pointer arithmetic and comparison
        if isinstance(left, Pointer) or isinstance(right, Pointer):
            if op == "+":
                if isinstance(left, Pointer):
                    return left.offset(int(right))
                return right.offset(int(left))
            if op == "-":
                if isinstance(left, Pointer) and isinstance(right, Pointer):
                    if left.storage is not right.storage:
                        raise CRuntimeError("subtracted pointers into different objects")
                    return left.index - right.index
                return left.offset(-int(right))
            if op in ("==", "!="):
                same = (
                    isinstance(left, Pointer) and isinstance(right, Pointer)
                    and left.storage is right.storage and left.index == right.index
                )
                if not isinstance(left, Pointer) or not isinstance(right, Pointer):
                    # Comparing against the literal 0, i.e. NULL.
                    pointer = left if isinstance(left, Pointer) else right
                    other = right if isinstance(left, Pointer) else left
                    same = pointer.is_null and other == 0
                return (1 if same else 0) if op == "==" else (0 if same else 1)
            if op in ("<", ">", "<=", ">="):
                if isinstance(left, Pointer) and isinstance(right, Pointer):
                    a, b = left.index, right.index
                    return 1 if {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op] else 0
            raise CRuntimeError(f"cannot apply '{op}' to a pointer")

        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise CRuntimeError("division by zero")
            if isinstance(left, float) or isinstance(right, float):
                return left / right
            # C truncates toward zero; Python floors, which differs for negatives.
            return int(left / right)
        if op == "%":
            if right == 0:
                raise CRuntimeError("modulo by zero")
            if isinstance(left, float) or isinstance(right, float):
                return math.fmod(left, right)
            return int(left - right * int(left / right))
        if op == "<":
            return 1 if left < right else 0
        if op == ">":
            return 1 if left > right else 0
        if op == "<=":
            return 1 if left <= right else 0
        if op == ">=":
            return 1 if left >= right else 0
        if op == "==":
            return 1 if left == right else 0
        if op == "!=":
            return 1 if left != right else 0
        if op == "&":
            return int(left) & int(right)
        if op == "|":
            return int(left) | int(right)
        if op == "^":
            return int(left) ^ int(right)
        if op == "<<":
            return int(left) << int(right)
        if op == ">>":
            return int(left) >> int(right)
        raise CRuntimeError(f"unknown operator '{op}'")

    def do_call(self, node, scope):
        _, target, arg_nodes, line = node

        name = target[1] if target[0] == "name" else None
        args = [self.evaluate(a, scope) for a in arg_nodes]

        if name in self.functions:
            return self.call_function(self.functions[name], args, line)

        from .c_stdlib import call_builtin

        handled, result = call_builtin(self, name, args, arg_nodes, scope, line)
        if handled:
            return result

        raise CRuntimeError(f"'{name}' is not defined and is not a library function", line)


def truthy(value) -> bool:
    if isinstance(value, Pointer):
        return not value.is_null
    return bool(value)


def run_source(source: str, stdout=None, stdin=None, argv=None) -> int:
    """Parses and runs a C program. Returns main()'s exit status."""
    program = parse(source)
    return Interpreter(program, stdout=stdout, stdin=stdin, argv=argv).run()
