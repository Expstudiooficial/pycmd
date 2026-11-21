"""The Go evaluator.

Walks the tuples :mod:`go_parser` produces. It is a dynamic interpreter: types
are parsed, remembered where they matter (zero values, conversions, struct
layouts, `%T`) and otherwise not enforced, because a phone is a place to run a
program, not to reimplement a type checker.

What that costs is honest to state: a program the real compiler would reject
may run here. What it buys is that everything the compiler would accept -
goroutines, channels, closures, methods, interfaces, defer, panic and recover
- actually runs, on a device that is not allowed to compile anything.
"""

from __future__ import annotations

import sys
import threading

from .clike_lexer import LangSyntaxError
from . import go_parser, go_stdlib
from .go_values import (
    Array, Bound, Builtin, Chan, ErrorValue, Func, GoError, GoExit, GoPanic,
    NIL, Nil, Package, Pointer, Rune, Slice, Struct, TypedMap, copy_value, go_string,
    type_name,
)

INT_MASK = (1 << 64) - 1
INT_SIGN = 1 << 63


class Env:
    __slots__ = ("values", "parent")

    def __init__(self, parent=None) -> None:
        self.values = {}
        self.parent = parent

    def define(self, name, value) -> None:
        self.values[name] = value

    def lookup(self, name):
        scope = self
        while scope is not None:
            if name in scope.values:
                return scope.values[name]
            scope = scope.parent
        raise GoError(f"undefined: {name}")

    def has(self, name) -> bool:
        scope = self
        while scope is not None:
            if name in scope.values:
                return True
            scope = scope.parent
        return False

    def assign(self, name, value) -> None:
        scope = self
        while scope is not None:
            if name in scope.values:
                scope.values[name] = value
                return
            scope = scope.parent
        raise GoError(f"undefined: {name}")

    def cell(self, name):
        scope = self
        while scope is not None:
            if name in scope.values:
                return scope
            scope = scope.parent
        raise GoError(f"undefined: {name}")


class MultiValue(list):
    """What a function with several results hands back."""


class _Return(Exception):
    def __init__(self, values) -> None:
        self.values = values


class _Break(Exception):
    def __init__(self, label=None) -> None:
        self.label = label


class _Continue(Exception):
    def __init__(self, label=None) -> None:
        self.label = label


class _Fallthrough(Exception):
    pass


class Frame:
    """One function call: what it deferred, and whether it is panicking."""

    __slots__ = ("defers", "panic", "recovered")

    def __init__(self) -> None:
        self.defers = []
        self.panic = None
        self.recovered = False


class Interpreter:

    def __init__(self, stdout=None, stdin=None, argv=None) -> None:
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stdin = stdin if stdin is not None else sys.stdin
        self.argv = argv or ["main"]
        self.globals = Env()
        self.types = {}
        self.methods = {}
        self.functions = {}
        self.packages = {}
        self.frames = threading.local()
        self.threads = []
        self.exit_code = 0

    # ------------------------------------------------------------ the frame

    @property
    def frame(self):
        stack = getattr(self.frames, "stack", None)
        if not stack:
            stack = [Frame()]
            self.frames.stack = stack
        return stack[-1]

    def push_frame(self):
        stack = getattr(self.frames, "stack", None)
        if stack is None:
            stack = []
            self.frames.stack = stack
        frame = Frame()
        stack.append(frame)
        return frame

    def pop_frame(self) -> None:
        self.frames.stack.pop()

    # ---------------------------------------------------------------- setup

    def load(self, unit) -> None:
        self.types = dict(unit["types"])
        self.methods = {k: dict(v) for k, v in unit["methods"].items()}
        self.functions = dict(unit["functions"])

        for alias, path in unit["imports"]:
            package = go_stdlib.package(path, self)
            name = alias or path.rsplit("/", 1)[-1]
            if package is not None:
                self.packages[name] = package
                self.globals.define(name, package)

        for name, node in self.functions.items():
            self.globals.define(
                name, Func(name, node[2], node[3], node[4], node[5], self.globals)
            )

        for names, declared, values, line, index in unit["consts"]:
            self.declare(self.globals, names, declared, values, line, iota=index)
        for names, declared, values, line in unit["globals"]:
            self.declare(self.globals, names, declared, values, line)

    def run(self) -> int:
        main = self.functions.get("main")
        if main is None:
            raise GoError("no main function")
        self.call(self.globals.lookup("main"), [], 0)
        return self.exit_code

    # ----------------------------------------------------------- statements

    def execute_block(self, statements, env) -> None:
        for statement in statements:
            self.execute(statement, env)

    def execute(self, node, env) -> None:
        kind = node[0]

        if kind == "expr":
            self.evaluate(node[1], env)
        elif kind == "define":
            self.execute_define(node, env)
        elif kind == "assign":
            self.execute_assign(node, env)
        elif kind == "varblock":
            for declaration in node[1]:
                if len(declaration) == 5:
                    names, declared, values, line, index = declaration
                    self.declare(env, names, declared, values, line, iota=index)
                else:
                    names, declared, values, line = declaration
                    self.declare(env, names, declared, values, line)
        elif kind == "localtype":
            self.types.update(node[1])
        elif kind == "block":
            self.execute_block(node[1], Env(env))
        elif kind == "if":
            self.execute_if(node, env)
        elif kind == "for":
            self.execute_for(node, env, None)
        elif kind == "range":
            self.execute_range(node, env, None)
        elif kind == "switch":
            self.execute_switch(node, env, None)
        elif kind == "typeswitch":
            self.execute_typeswitch(node, env, None)
        elif kind == "select":
            self.execute_select(node, env)
        elif kind == "label":
            self.execute_labelled(node, env)
        elif kind == "return":
            values = [self.evaluate(item, env) for item in node[1]]
            if len(values) == 1 and isinstance(values[0], MultiValue):
                values = list(values[0])
            raise _Return(values)
        elif kind == "break":
            raise _Break(node[1])
        elif kind == "continue":
            raise _Continue(node[1])
        elif kind == "fallthrough":
            raise _Fallthrough()
        elif kind == "incdec":
            target = node[1]
            current = self.evaluate(target, env)
            step = 1 if node[2] == "++" else -1
            self.assign_to(target, self.wrap_int(current + step), env)
        elif kind == "send":
            channel = self.evaluate(node[1], env)
            value = self.evaluate(node[2], env)
            self.expect_chan(channel, node[3]).send(value)
        elif kind == "defer":
            self.frame.defers.append(self.prepare_call(node[1], env))
        elif kind == "go":
            self.spawn(node[1], env)
        elif kind == "empty":
            pass
        else:
            raise GoError(f"cannot execute {kind}", node[-1])

    def declare(self, env, names, declared, values, line, iota=None) -> None:
        if values:
            evaluated = self.spread_values(values, env, len(names), line, iota=iota)
        else:
            evaluated = [self.zero_value(declared) for _ in names]
        for name, value in zip(names, evaluated):
            if name != "_":
                env.define(name, copy_value(value))

    def spread_values(self, values, env, wanted, line, iota=None):
        if iota is not None:
            env = Env(env)
            env.define("iota", iota)
        if len(values) == 1 and wanted > 1:
            single = self.evaluate(values[0], env, want=wanted)
            if isinstance(single, MultiValue):
                if len(single) != wanted:
                    raise GoError(
                        f"assignment mismatch: {wanted} variables but {len(single)} values", line
                    )
                return list(single)
            raise GoError(f"assignment mismatch: {wanted} variables but 1 value", line)
        evaluated = []
        for item in values:
            value = self.evaluate(item, env)
            if isinstance(value, MultiValue):
                evaluated.extend(value)
            else:
                evaluated.append(value)
        if wanted and len(evaluated) != wanted:
            raise GoError(
                f"assignment mismatch: {wanted} variables but {len(evaluated)} values", line
            )
        return evaluated

    def execute_define(self, node, env) -> None:
        targets, values, line = node[1], node[2], node[3]
        names = []
        for target in targets:
            if target[0] != "name":
                raise GoError("cannot declare this", line)
            names.append(target[1])
        evaluated = self.spread_values(values, env, len(names), line)
        for name, value in zip(names, evaluated):
            if name == "_":
                continue
            # `:=` redeclares only in this scope; an outer name is shadowed.
            env.define(name, copy_value(value))

    def execute_assign(self, node, env) -> None:
        targets, operator, values, line = node[1], node[2], node[3], node[4]
        if operator == "=":
            evaluated = self.spread_values(values, env, len(targets), line)
            for target, value in zip(targets, evaluated):
                self.assign_to(target, copy_value(value), env)
            return
        current = self.evaluate(targets[0], env)
        addend = self.evaluate(values[0], env)
        result = self.binary(operator[:-1], current, addend, line)
        self.assign_to(targets[0], result, env)

    def assign_to(self, target, value, env) -> None:
        kind = target[0]
        if kind == "name":
            if target[1] == "_":
                return
            env.assign(target[1], value)
        elif kind == "index":
            container = self.evaluate(target[1], env)
            index = self.evaluate(target[2], env)
            if isinstance(container, dict):
                container[self.map_key(index)] = value
            elif isinstance(container, (Slice, Array)):
                container.set(int(index), value)
            elif isinstance(container, Pointer):
                inner = container.get()
                inner.set(int(index), value)
            else:
                raise GoError("cannot index this value", target[3])
        elif kind == "field":
            owner = self.evaluate(target[1], env)
            self.set_field(owner, target[2], value, target[3])
        elif kind == "unary" and target[1] == "*":
            pointer = self.evaluate(target[2], env)
            if not isinstance(pointer, Pointer):
                raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
            pointer.set(value)
        else:
            raise GoError("cannot assign to this", target[-1])

    def set_field(self, owner, name, value, line) -> None:
        if isinstance(owner, Pointer):
            owner = owner.get()
        if isinstance(owner, Nil):
            raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
        if isinstance(owner, Struct):
            owner.fields[name] = value
            return
        if isinstance(owner, go_stdlib.Native):
            owner.set(name, value)
            return
        raise GoError(f"cannot set field {name}", line)

    def execute_if(self, node, env) -> None:
        _, init, condition, then, otherwise, line = node
        scope = Env(env)
        if init is not None:
            self.execute(init, scope)
        if self.condition(self.evaluate(condition, scope), line):
            self.execute_block(then, Env(scope))
        elif otherwise is not None:
            self.execute_block(otherwise, Env(scope))

    def condition(self, value, line) -> bool:
        if isinstance(value, bool):
            return value
        raise GoError("expected a boolean condition", line)

    def execute_for(self, node, env, label) -> None:
        _, init, condition, post, body, line = node
        scope = Env(env)
        if init is not None:
            self.execute(init, scope)
        while True:
            if condition is not None and not self.condition(self.evaluate(condition, scope), line):
                return
            try:
                self.execute_block(body, Env(scope))
            except _Break as stop:
                if stop.label in (None, label):
                    return
                raise
            except _Continue as skip:
                if skip.label not in (None, label):
                    raise
            if post is not None:
                self.execute(post, scope)

    def execute_range(self, node, env, label) -> None:
        _, key_node, value_node, subject_node, body, declares, line = node
        subject = self.evaluate(subject_node, env)
        scope = Env(env)

        key_name = key_node[1] if key_node is not None and key_node[0] == "name" else None
        value_name = value_node[1] if value_node is not None and value_node[0] == "name" else None

        for key, value in self.range_pairs(subject, line):
            inner = Env(scope)
            if declares:
                if key_name and key_name != "_":
                    inner.define(key_name, key)
                if value_name and value_name != "_":
                    inner.define(value_name, copy_value(value))
            else:
                if key_node is not None and key_name != "_":
                    self.assign_to(key_node, key, scope)
                if value_node is not None and value_name != "_":
                    self.assign_to(value_node, copy_value(value), scope)
            try:
                self.execute_block(body, inner)
            except _Break as stop:
                if stop.label in (None, label):
                    return
                raise
            except _Continue as skip:
                if skip.label not in (None, label):
                    raise

    def range_pairs(self, subject, line):
        if isinstance(subject, (Slice, Array)):
            for index in range(len(subject)):
                yield index, subject.get(index)
            return
        if isinstance(subject, str):
            # Go ranges a string by rune, and the index is the byte offset.
            offset = 0
            for character in subject:
                yield offset, Rune(ord(character))
                offset += len(character.encode("utf-8"))
            return
        if isinstance(subject, dict):
            for key in list(subject.keys()):
                yield key, subject[key]
            return
        if isinstance(subject, Chan):
            while True:
                value, ok = subject.receive()
                if not ok:
                    return
                yield value, None
            return
        if isinstance(subject, int) and not isinstance(subject, bool):
            # Go 1.22: `for i := range n`.
            for index in range(int(subject)):
                yield index, None
            return
        if isinstance(subject, Nil):
            return
        raise GoError(f"cannot range over {type_name(subject)}", line)

    def execute_switch(self, node, env, label) -> None:
        _, init, tag, cases, default, line = node
        scope = Env(env)
        if init is not None:
            self.execute(init, scope)
        subject = self.evaluate(tag, scope) if tag is not None else True

        chosen = None
        for index, (matches, body) in enumerate(cases):
            for match in matches:
                if self.equal(subject, self.evaluate(match, scope)):
                    chosen = index
                    break
            if chosen is not None:
                break

        bodies = [body for _, body in cases]
        if chosen is None:
            if default is None:
                return
            bodies = [default]
            chosen = 0

        while chosen < len(bodies):
            try:
                self.execute_block(bodies[chosen], Env(scope))
            except _Break as stop:
                if stop.label in (None, label):
                    return
                raise
            except _Fallthrough:
                chosen += 1
                continue
            return

    def execute_typeswitch(self, node, env, label) -> None:
        _, init, binding, subject_node, cases, default, line = node
        scope = Env(env)
        if init is not None:
            self.execute(init, scope)
        subject = self.evaluate(subject_node, scope)

        for matches, body in cases:
            for match in matches:
                if self.matches_type(subject, match):
                    inner = Env(scope)
                    if binding:
                        inner.define(binding, subject)
                    try:
                        self.execute_block(body, inner)
                    except _Break as stop:
                        if stop.label not in (None, label):
                            raise
                    return
        if default is not None:
            inner = Env(scope)
            if binding:
                inner.define(binding, subject)
            try:
                self.execute_block(default, inner)
            except _Break as stop:
                if stop.label not in (None, label):
                    raise

    def execute_select(self, node, env) -> None:
        import time

        _, cases, default, line = node
        deadline = time.monotonic() + 30
        while True:
            for comm, body in cases:
                ready, bindings = self.select_ready(comm, env)
                if ready:
                    scope = Env(env)
                    for name, value in bindings.items():
                        scope.define(name, value)
                    try:
                        self.execute_block(body, scope)
                    except _Break as stop:
                        if stop.label is not None:
                            raise
                    return
            if default is not None:
                try:
                    self.execute_block(default, Env(env))
                except _Break as stop:
                    if stop.label is not None:
                        raise
                return
            if time.monotonic() > deadline:
                raise GoPanic("all goroutines are asleep - deadlock!")
            time.sleep(0.005)

    def select_ready(self, comm, env):
        """Is this select case able to proceed right now?"""
        if comm[0] == "send":
            channel = self.expect_chan(self.evaluate(comm[1], env), comm[3])
            if channel.capacity and len(channel) >= channel.capacity:
                return False, {}
            channel.send(self.evaluate(comm[2], env))
            return True, {}

        node = comm[1] if comm[0] == "expr" else None
        if comm[0] in ("define", "assign"):
            node = comm[2][0] if comm[0] == "define" else comm[3][0]
        if node is None or node[0] != "recv":
            return False, {}

        channel = self.expect_chan(self.evaluate(node[1], env), node[2])
        if not channel.ready():
            return False, {}
        value, ok = channel.receive()
        bindings = {}
        if comm[0] == "define":
            targets = comm[1]
            if targets and targets[0][1] != "_":
                bindings[targets[0][1]] = value
            if len(targets) > 1 and targets[1][1] != "_":
                bindings[targets[1][1]] = ok
        elif comm[0] == "assign":
            for target, item in zip(comm[1], [value, ok]):
                self.assign_to(target, item, env)
        return True, bindings

    def execute_labelled(self, node, env) -> None:
        _, label, statement, line = node
        kind = statement[0]
        try:
            if kind == "for":
                self.execute_for(statement, env, label)
            elif kind == "range":
                self.execute_range(statement, env, label)
            elif kind == "switch":
                self.execute_switch(statement, env, label)
            elif kind == "typeswitch":
                self.execute_typeswitch(statement, env, label)
            else:
                self.execute(statement, env)
        except _Break as stop:
            if stop.label != label:
                raise

    def spawn(self, call_node, env) -> None:
        prepared = self.prepare_call(call_node, env)

        def body():
            try:
                prepared()
            except GoPanic as panic:
                self.write_error(f"panic: {go_string(panic.value, interp=self)}\n")
            except (GoExit, _Return):
                pass
            except GoError as error:
                self.write_error(f"goroutine error: {error}\n")

        thread = threading.Thread(target=body, daemon=True)
        self.threads.append(thread)
        thread.start()

    def prepare_call(self, node, env):
        """Freezes a call's arguments now, and runs it later.

        This is what `defer` and `go` promise: the arguments are evaluated at
        the point the statement is reached, not when the call finally happens.
        """
        if node[0] != "call":
            raise GoError("expression in go/defer must be a function call", node[-1])
        _, target, arguments, spread, line = node
        function = self.evaluate(target, env)
        values = self.evaluate_arguments(arguments, spread, env)
        return lambda: self.call(function, values, line)

    # ---------------------------------------------------------- expressions

    def evaluate(self, node, env, want=1):
        kind = node[0]

        if kind == "int":
            return node[1]
        if kind == "float":
            return node[1]
        if kind == "str":
            return node[1]
        if kind == "name":
            return self.lookup_name(node[1], env, node[2])
        if kind == "bin":
            return self.evaluate_binary(node, env)
        if kind == "unary":
            return self.evaluate_unary(node, env)
        if kind == "call":
            return self.evaluate_call(node, env, want)
        if kind == "field":
            return self.evaluate_field(node, env)
        if kind == "index":
            return self.evaluate_index(node, env, want)
        if kind == "slice":
            return self.evaluate_slice(node, env)
        if kind == "complit":
            return self.composite(node[1], node[2], env, node[3])
        if kind == "closure":
            return Func("", node[1], node[2], node[3], node[4], env)
        if kind == "typeassert":
            return self.evaluate_assert(node, env, want)
        if kind == "recv":
            channel = self.expect_chan(self.evaluate(node[1], env), node[2])
            value, ok = channel.receive()
            if want > 1:
                return MultiValue([value, ok])
            return value
        if kind == "type":
            return node[1]
        if kind == "range":
            raise GoError("range is only allowed in a for statement", node[2])
        raise GoError(f"cannot evaluate {kind}", node[-1])

    def lookup_name(self, name, env, line):
        if name == "nil":
            return NIL
        if name == "true":
            return True
        if name == "false":
            return False
        if env.has(name):
            return env.lookup(name)
        if name in self.types:
            return ("named", name)
        builtin = go_stdlib.BUILTINS.get(name)
        if builtin is not None:
            return builtin
        raise GoError(f"undefined: {name}", line)

    def evaluate_binary(self, node, env):
        _, operator, left_node, right_node, line = node
        if operator == "&&":
            left = self.evaluate(left_node, env)
            if not self.condition(left, line):
                return False
            return self.condition(self.evaluate(right_node, env), line)
        if operator == "||":
            left = self.evaluate(left_node, env)
            if self.condition(left, line):
                return True
            return self.condition(self.evaluate(right_node, env), line)
        return self.binary(operator, self.evaluate(left_node, env),
                           self.evaluate(right_node, env), line)

    def binary(self, operator, left, right, line):
        if operator == "==":
            return self.equal(left, right)
        if operator == "!=":
            return not self.equal(left, right)

        if operator in ("<", "<=", ">", ">="):
            if isinstance(left, str) != isinstance(right, str):
                raise GoError("cannot compare a string with a number", line)
            if operator == "<":
                return left < right
            if operator == "<=":
                return left <= right
            if operator == ">":
                return left > right
            return left >= right

        if operator == "+":
            if isinstance(left, str) or isinstance(right, str):
                if not (isinstance(left, str) and isinstance(right, str)):
                    raise GoError("cannot add a string to a number", line)
                return left + right
            return self.arith(left + right, left, right)
        if operator == "-":
            return self.arith(left - right, left, right)
        if operator == "*":
            return self.arith(left * right, left, right)
        if operator == "/":
            if isinstance(left, float) or isinstance(right, float):
                if right == 0:
                    raise GoPanic("runtime error: division by zero")
                return left / right
            if right == 0:
                raise GoPanic("runtime error: integer divide by zero")
            # Go truncates towards zero; Python floors.
            result = abs(left) // abs(right)
            if (left < 0) != (right < 0):
                result = -result
            return self.wrap_int(result)
        if operator == "%":
            if right == 0:
                raise GoPanic("runtime error: integer divide by zero")
            if isinstance(left, float) or isinstance(right, float):
                raise GoError("% is not defined for floats", line)
            # The sign of a Go remainder follows the dividend.
            result = abs(left) % abs(right)
            return self.wrap_int(-result if left < 0 else result)
        if operator == "&":
            return self.wrap_int(int(left) & int(right))
        if operator == "|":
            return self.wrap_int(int(left) | int(right))
        if operator == "^":
            return self.wrap_int(int(left) ^ int(right))
        if operator == "&^":
            return self.wrap_int(int(left) & ~int(right))
        if operator == "<<":
            return self.wrap_int(int(left) << int(right))
        if operator == ">>":
            return self.wrap_int(int(left) >> int(right))
        raise GoError(f"unknown operator {operator}", line)

    def arith(self, result, left, right):
        if isinstance(left, float) or isinstance(right, float):
            return result
        return self.wrap_int(result)

    def wrap_int(self, value):
        if isinstance(value, float):
            return value
        value &= INT_MASK
        return value - (1 << 64) if value & INT_SIGN else value

    def equal(self, left, right) -> bool:
        if isinstance(left, Nil) or isinstance(right, Nil):
            other = right if isinstance(left, Nil) else left
            if isinstance(other, Nil):
                return True
            if isinstance(other, (Slice, dict, Chan)):
                return len(other) == 0 and isinstance(other, Slice) and other.backing is None
            return False
        if isinstance(left, bool) != isinstance(right, bool):
            return False
        if isinstance(left, Struct) and isinstance(right, Struct):
            return left.type_name == right.type_name and all(
                self.equal(left.fields[k], right.fields.get(k)) for k in left.fields
            )
        if isinstance(left, (Array, Slice)) and isinstance(right, (Array, Slice)):
            if len(left) != len(right):
                return False
            return all(self.equal(a, b) for a, b in zip(left, right))
        try:
            return bool(left == right)
        except Exception:  # noqa: BLE001
            return left is right

    def evaluate_unary(self, node, env):
        _, operator, operand, line = node
        if operator == "&":
            return self.address_of(operand, env, line)
        value = self.evaluate(operand, env)
        if operator == "-":
            return self.arith(-value, value, value)
        if operator == "+":
            return value
        if operator == "!":
            return not self.condition(value, line)
        if operator == "^":
            return self.wrap_int(~int(value))
        if operator == "*":
            if isinstance(value, Pointer):
                return value.get()
            if isinstance(value, Nil):
                raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
            raise GoError("cannot dereference this value", line)
        raise GoError(f"unknown unary {operator}", line)

    def address_of(self, operand, env, line):
        kind = operand[0]
        if kind == "name":
            scope = env.cell(operand[1])
            name = operand[1]
            value = scope.values[name]
            if isinstance(value, (Struct, Array)):
                # Pointing at the object itself keeps `p.X = 1` visible
                # through every other pointer to the same struct.
                return Pointer.to(value)
            return Pointer(lambda: scope.values[name],
                           lambda new: scope.values.__setitem__(name, new), label=name)
        if kind == "complit":
            return Pointer.to(self.evaluate(operand, env))
        if kind == "index":
            container = self.evaluate(operand[1], env)
            index = self.evaluate(operand[2], env)
            if isinstance(container, (Slice, Array)):
                item = container.get(int(index))
                if isinstance(item, (Struct, Array)):
                    return Pointer.to(item)
                return Pointer(lambda: container.get(int(index)),
                               lambda new: container.set(int(index), new))
            if isinstance(container, dict):
                raise GoError("cannot take the address of a map element", line)
        if kind == "field":
            owner = self.evaluate(operand[1], env)
            if isinstance(owner, Pointer):
                owner = owner.get()
            if isinstance(owner, Struct):
                item = owner.fields.get(operand[2])
                if isinstance(item, (Struct, Array)):
                    return Pointer.to(item)
                return Pointer(lambda: owner.fields[operand[2]],
                               lambda new: owner.fields.__setitem__(operand[2], new))
        value = self.evaluate(operand, env)
        return Pointer.to(value)

    def evaluate_field(self, node, env):
        _, owner_node, name, line = node

        if owner_node[0] == "name" and not env.has(owner_node[1]):
            package = self.packages.get(owner_node[1])
            if package is not None:
                if name not in package.members:
                    raise GoError(f"undefined: {owner_node[1]}.{name}", line)
                return package.members[name]

        owner = self.evaluate(owner_node, env)
        return self.member(owner, name, line)

    def member(self, owner, name, line):
        if isinstance(owner, Package):
            if name not in owner.members:
                raise GoError(f"undefined: {owner.name}.{name}", line)
            return owner.members[name]

        target = owner
        if isinstance(target, Pointer):
            target = target.get()
        if isinstance(target, Nil):
            raise GoPanic("runtime error: invalid memory address or nil pointer dereference")

        if isinstance(target, Struct):
            if name in target.fields:
                return target.fields[name]
            method = self.method_for(target.type_name, name)
            if method is not None:
                return Bound(method, owner)
            # An embedded struct's fields and methods are promoted.
            for field in target.fields.values():
                inner = field.get() if isinstance(field, Pointer) else field
                if isinstance(inner, Struct):
                    if name in inner.fields:
                        return inner.fields[name]
                    promoted = self.method_for(inner.type_name, name)
                    if promoted is not None:
                        return Bound(promoted, field)
            raise GoError(f"{target.type_name} has no field or method {name}", line)

        if isinstance(target, ErrorValue):
            if name == "Error":
                return Builtin("Error", lambda args: target.message)
            if name == "Unwrap":
                return Builtin("Unwrap", lambda args: target.wrapped or NIL)

        if isinstance(target, go_stdlib.Native):
            return target.member(name, line)

        method = self.method_for(type_name(target), name)
        if method is not None:
            return Bound(method, owner)

        raise GoError(f"{type_name(target)} has no field or method {name}", line)

    def method_for(self, type_name_value, name):
        table = self.methods.get(type_name_value)
        if table is None:
            return None
        node = table.get(name)
        if node is None:
            return None
        return Func(name, node[2], node[3], node[4], node[5], self.globals, node[6])

    def stringer(self, value):
        """Renders through Error() or String() when the type has one."""
        target = value.get() if isinstance(value, Pointer) else value
        if not isinstance(target, Struct):
            return None
        for name in ("Error", "String"):
            method = self.method_for(target.type_name, name)
            if method is not None:
                try:
                    return self.call(Bound(method, value), [], 0)
                except Exception:  # noqa: BLE001
                    return None
        return None

    def evaluate_index(self, node, env, want=1):
        _, owner_node, index_node, line = node
        owner = self.evaluate(owner_node, env)
        index = self.evaluate(index_node, env)

        if isinstance(owner, Pointer):
            owner = owner.get()
        if isinstance(owner, dict):
            key = self.map_key(index)
            if key in owner:
                value = owner[key]
                ok = True
            else:
                value = self.zero_for_map(owner)
                ok = False
            if want > 1:
                return MultiValue([value, ok])
            return value
        if isinstance(owner, (Slice, Array)):
            return owner.get(int(index))
        if isinstance(owner, str):
            position = int(index)
            data = owner.encode("utf-8")
            if position < 0 or position >= len(data):
                raise GoPanic(
                    f"runtime error: index out of range [{position}] with length {len(data)}"
                )
            return data[position]
        if isinstance(owner, Nil):
            raise GoPanic("runtime error: index of a nil value")
        raise GoError(f"cannot index {type_name(owner)}", line)

    def map_key(self, value):
        if isinstance(value, Struct):
            return (value.type_name, tuple(sorted(
                (k, self.map_key(v)) for k, v in value.fields.items()
            )))
        if isinstance(value, (Slice, Array)):
            return tuple(self.map_key(item) for item in value)
        return value

    def zero_for_map(self, mapping):
        marker = getattr(mapping, "value_type", None)
        if marker is not None:
            return self.zero_value(marker)
        for value in mapping.values():
            return self.zero_like(value)
        return 0

    def zero_like(self, value):
        if isinstance(value, bool):
            return False
        if isinstance(value, float):
            return 0.0
        if isinstance(value, int):
            return 0
        if isinstance(value, str):
            return ""
        return NIL

    def evaluate_slice(self, node, env):
        _, owner_node, low_node, high_node, line = node
        owner = self.evaluate(owner_node, env)
        low = int(self.evaluate(low_node, env)) if low_node is not None else None
        high = int(self.evaluate(high_node, env)) if high_node is not None else None

        if isinstance(owner, Pointer):
            owner = owner.get()
        if isinstance(owner, str):
            data = owner.encode("utf-8")
            return data[low or 0:len(data) if high is None else high].decode("utf-8", "replace")
        if isinstance(owner, (Slice, Array)):
            return owner.cut(low, high)
        raise GoError(f"cannot slice {type_name(owner)}", line)

    def evaluate_assert(self, node, env, want=1):
        _, subject_node, wanted, line = node
        subject = self.evaluate(subject_node, env)
        if wanted is None:
            return subject
        ok = self.matches_type(subject, wanted)
        if want > 1:
            return MultiValue([subject if ok else self.zero_value(wanted), ok])
        if not ok:
            raise GoPanic(
                f"interface conversion: interface {{}} is {type_name(subject)}, "
                f"not {self.type_label(wanted)}"
            )
        return subject

    def type_label(self, declared) -> str:
        kind = declared[0]
        if kind == "named":
            return declared[1]
        if kind == "ptr":
            return "*" + self.type_label(declared[1])
        if kind == "slice":
            return "[]" + self.type_label(declared[1])
        if kind == "map":
            return f"map[{self.type_label(declared[1])}]{self.type_label(declared[2])}"
        return kind

    def matches_type(self, value, declared) -> bool:
        kind = declared[0]
        if kind == "named":
            name = declared[1]
            if name in ("any", "interface{}"):
                return True
            if name == "error":
                return isinstance(value, ErrorValue) or (
                    isinstance(value, Struct) and self.method_for(value.type_name, "Error")
                ) is not None and not isinstance(value, Nil)
            if name == "nil":
                return isinstance(value, Nil)
            if name in ("int", "int8", "int16", "int32", "int64", "uint", "uint8",
                        "uint16", "uint32", "uint64", "byte", "rune"):
                return isinstance(value, int) and not isinstance(value, bool)
            if name in ("float64", "float32"):
                return isinstance(value, float)
            if name == "string":
                return isinstance(value, str)
            if name == "bool":
                return isinstance(value, bool)
            if name in self.types and self.types[name][0] != "struct" \
                    and self.types[name][0] != "iface":
                return self.matches_type(value, self.types[name])
            declared_type = self.types.get(name)
            if declared_type is not None and declared_type[0] == "iface":
                return all(
                    self.member_exists(value, method) for method in declared_type[1]
                )
            target = value.get() if isinstance(value, Pointer) else value
            return isinstance(target, Struct) and target.type_name == name \
                and not isinstance(value, Pointer)
        if kind == "ptr":
            if not isinstance(value, Pointer):
                return False
            return self.matches_type(value.get(), declared[1])
        if kind == "slice":
            return isinstance(value, Slice)
        if kind == "map":
            return isinstance(value, dict)
        if kind == "iface":
            return all(self.member_exists(value, method) for method in declared[1])
        if kind == "chan":
            return isinstance(value, Chan)
        if kind == "functype":
            return isinstance(value, (Func, Bound, Builtin))
        return False

    def member_exists(self, value, name) -> bool:
        try:
            self.member(value, name, 0)
            return True
        except Exception:  # noqa: BLE001
            return False

    # --------------------------------------------------------------- calls

    def evaluate_call(self, node, env, want=1):
        _, target, arguments, spread, line = node

        if target[0] == "name":
            name = target[1]
            if not env.has(name):
                if name in self.types:
                    return self.convert(self.types[name], name,
                                        self.evaluate(arguments[0], env), line)
                if name in go_stdlib.CONVERSIONS:
                    return go_stdlib.CONVERSIONS[name](
                        self, [self.evaluate(item, env) for item in arguments], line
                    )
                if name in go_stdlib.SPECIAL_FORMS:
                    return go_stdlib.SPECIAL_FORMS[name](self, arguments, env, line, want)

        if target[0] == "type":
            return self.convert(target[1], self.type_label(target[1]),
                                self.evaluate(arguments[0], env), line)

        function = self.evaluate(target, env)
        if isinstance(function, tuple):
            # A declared type used as a conversion: MyInt(3).
            return self.convert(self.types.get(function[1], function), function[1],
                                self.evaluate(arguments[0], env), line)

        values = self.evaluate_arguments(arguments, spread, env)
        return self.call(function, values, line, want)

    def evaluate_arguments(self, arguments, spread, env):
        values = []
        # `f(g())` spreads every result of g, but `f(<-ch)` and `f(m[k])` pass
        # one value: the second result of those is only offered to an
        # assignment that asked for it.
        spreadable = len(arguments) == 1 and arguments[0][0] == "call"
        for item in arguments:
            value = self.evaluate(item, env, want=2 if spreadable else 1)
            if isinstance(value, MultiValue):
                if spreadable:
                    values.extend(value)
                else:
                    values.append(value[0])
            else:
                values.append(value)
        if spread and values and isinstance(values[-1], (Slice, Array)):
            last = values.pop()
            values.extend(last)
        return values

    def call(self, function, values, line, want=1):
        if isinstance(function, Builtin):
            result = function.call(self, values) if function.wants_interp \
                else function.call(values)
            # A library function with two results hands back a plain list.
            if type(result) is list:
                return MultiValue(result)
            return result

        if isinstance(function, Bound):
            return self.invoke(function.func, values, line, function.receiver, want)

        if isinstance(function, Func):
            return self.invoke(function, values, line, None, want)

        if isinstance(function, Nil):
            raise GoPanic("runtime error: invalid memory address or nil pointer dereference")

        raise GoError(f"cannot call {type_name(function)}", line)

    def invoke(self, function, values, line, receiver=None, want=1):
        env = Env(function.env)

        if function.receiver is not None and receiver is not None:
            name, _type, pointer = function.receiver
            if name != "_":
                if pointer:
                    env.define(name, receiver if isinstance(receiver, Pointer)
                               else Pointer.to(receiver))
                else:
                    target = receiver.get() if isinstance(receiver, Pointer) else receiver
                    env.define(name, copy_value(target))

        params = function.params
        if function.variadic:
            fixed = params[:-1]
            for name, value in zip(fixed, values):
                if name != "_":
                    env.define(name, copy_value(value))
            rest = values[len(fixed):]
            if len(rest) == 1 and isinstance(rest[0], Slice):
                env.define(params[-1], rest[0])
            else:
                env.define(params[-1], Slice.of([copy_value(item) for item in rest]))
        else:
            if len(values) != len(params):
                raise GoError(
                    f"wrong number of arguments: wanted {len(params)}, got {len(values)}", line
                )
            for name, value in zip(params, values):
                if name != "_":
                    env.define(name, copy_value(value))

        count, declared_results = function.results if isinstance(function.results, tuple) \
            else (function.results, [])
        named = [(name, kind) for name, kind in declared_results if name and name != "_"]
        for name, kind in named:
            env.define(name, self.zero_value(kind))

        frame = self.push_frame()
        results = []
        try:
            try:
                self.execute_block(function.body, env)
            except _Return as returned:
                results = returned.values
            results = self.settle_results(frame, env, named, results)
        except GoPanic as panic:
            frame.panic = panic
            self.run_defers(frame)
            if not frame.recovered:
                raise
            # A recovered panic still returns: whatever the deferred function
            # put in the named results is what the caller gets.
            results = [env.lookup(name) for name, _ in named]
        finally:
            self.pop_frame()

        if not results:
            return None if count == 0 else NIL
        if len(results) == 1:
            return results[0]
        return MultiValue(results)

    def settle_results(self, frame, env, named, results):
        """Runs the deferred calls, then decides what the function returns.

        Order matters: `return x` writes x into the named result, the deferred
        functions run, and only then is the value read back - which is what
        lets a deferred `recover()` change the answer.
        """
        if not named:
            self.run_defers(frame)
            return results
        if results:
            for (name, _), value in zip(named, results):
                env.assign(name, value)
        self.run_defers(frame)
        return [env.lookup(name) for name, _ in named]

    def run_defers(self, frame) -> None:
        while frame.defers:
            deferred = frame.defers.pop()
            try:
                deferred()
            except GoPanic as panic:
                frame.panic = panic

    # --------------------------------------------------------- construction

    def resolve(self, declared):
        """Follows named types down to what they are made of."""
        seen = 0
        while declared is not None and declared[0] == "named" and seen < 16:
            target = self.types.get(declared[1])
            if target is None:
                return declared
            declared = target
            seen += 1
        return declared

    def zero_value(self, declared):
        if declared is None:
            return NIL
        kind = declared[0]

        if kind == "named":
            name = declared[1]
            if name in ("int", "int8", "int16", "int32", "int64", "uint", "uint8",
                        "uint16", "uint32", "uint64", "byte", "rune", "uintptr"):
                return 0
            if name in ("float64", "float32"):
                return 0.0
            if name == "string":
                return ""
            if name == "bool":
                return False
            if name in ("error", "any"):
                return NIL
            native = go_stdlib.zero_native(name, self)
            if native is not None:
                return native
            target = self.types.get(name)
            if target is not None:
                value = self.zero_value(target)
                if isinstance(value, Struct):
                    value.type_name = name
                return value
            return NIL
        if kind == "struct":
            fields = {}
            for field_name, field_type in declared[1]:
                fields[field_name] = self.zero_value(field_type)
            return Struct("", fields)
        if kind == "array":
            size = declared[1]
            count = size[1] if isinstance(size, tuple) and size[0] == "int" else 0
            return Array([self.zero_value(declared[2]) for _ in range(int(count))])
        if kind == "slice":
            empty = Slice([], 0, 0, 0, self.type_label(declared[1]))
            empty.backing = None
            empty.backing = []
            return empty
        if kind == "map":
            return TypedMap(value_type=declared[2] if len(declared) > 2 else None)
        return NIL

    def struct_type_name(self, declared) -> str:
        return declared[1] if declared is not None and declared[0] == "named" else ""

    def composite(self, declared, items, env, line):
        resolved = self.resolve(declared)
        if resolved is None:
            raise GoError("cannot tell what this literal builds", line)
        kind = resolved[0]

        if kind == "struct":
            fields = {}
            for field_name, field_type in resolved[1]:
                fields[field_name] = self.zero_value(field_type)
            names = [name for name, _ in resolved[1]]
            types = dict(resolved[1])
            for index, (key, value_node) in enumerate(items):
                if key is None:
                    if index >= len(names):
                        raise GoError("too many values in the struct literal", line)
                    field_name = names[index]
                else:
                    field_name = key[1]
                value = self.literal_value(value_node, types.get(field_name), env)
                fields[field_name] = copy_value(value)
            return Struct(self.struct_type_name(declared), fields)

        if kind in ("slice", "array"):
            element = resolved[1] if kind == "slice" else resolved[2]
            values = []
            for key, value_node in items:
                value = self.literal_value(value_node, element, env)
                if key is None:
                    values.append(copy_value(value))
                else:
                    position = int(self.evaluate(key, env))
                    while len(values) <= position:
                        values.append(self.zero_value(element))
                    values[position] = copy_value(value)
            if kind == "array":
                size = resolved[1]
                count = int(self.evaluate(size, env)) if size is not None else len(values)
                while len(values) < count:
                    values.append(self.zero_value(element))
                return Array(values, 0, len(values), len(values), self.type_label(element))
            return Slice(values, 0, len(values), len(values), self.type_label(element))

        if kind == "map":
            mapping = TypedMap(value_type=resolved[2])
            for key, value_node in items:
                if key is None:
                    raise GoError("a map literal needs keys", line)
                mapping[self.map_key(self.literal_value(key, resolved[1], env))] = copy_value(
                    self.literal_value(value_node, resolved[2], env)
                )
            return mapping

        raise GoError(f"cannot build a literal of {self.type_label(declared)}", line)

    def literal_value(self, node, element, env):
        """Inner literals inherit their type: `[]Point{{1, 2}}` needs no repeat."""
        if isinstance(node, tuple) and node[0] == "complit" and node[1] is None:
            target = element
            if target is not None and self.resolve(target)[0] == "ptr":
                inner = self.resolve(target)[1]
                return Pointer.to(self.composite(inner, node[2], env, node[3]))
            return self.composite(target, node[2], env, node[3])
        return self.evaluate(node, env)

    def convert(self, declared, name, value, line):
        resolved = self.resolve(declared) if isinstance(declared, tuple) else declared
        if name in go_stdlib.CONVERSIONS:
            return go_stdlib.CONVERSIONS[name](self, [value], line)
        if resolved is not None and isinstance(resolved, tuple):
            if resolved[0] == "slice":
                element = self.type_label(resolved[1])
                if isinstance(value, str):
                    if element in ("byte", "uint8"):
                        return Slice.of(list(value.encode("utf-8")), element)
                    return Slice.of([Rune(ord(c)) for c in value], element)
                if isinstance(value, (Slice, Array)):
                    return value
            if resolved[0] == "struct" and isinstance(value, Struct):
                return Struct(name, dict(value.fields))
            if resolved[0] == "named":
                return go_stdlib.CONVERSIONS.get(
                    resolved[1], lambda interp, args, ln: args[0]
                )(self, [value], line)
        return value

    # -------------------------------------------------------------- helpers

    def expect_chan(self, value, line):
        if isinstance(value, Chan):
            return value
        if isinstance(value, Nil):
            raise GoPanic("all goroutines are asleep - deadlock!")
        raise GoError(f"expected a channel, found {type_name(value)}", line)

    def write(self, text) -> None:
        self.stdout.write(text)

    def write_error(self, text) -> None:
        try:
            sys.stderr.write(text)
        except Exception:  # noqa: BLE001
            self.stdout.write(text)

    def read_line(self):
        line = self.stdin.readline()
        if not line:
            return None
        return line.rstrip("\n")


def run_source(source: str, stdout=None, stdin=None, argv=None) -> int:
    """Parses and runs a Go program, returning its exit status."""
    unit = go_parser.parse(source)
    interpreter = Interpreter(stdout=stdout, stdin=stdin, argv=argv)
    interpreter.load(unit)

    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous, 6000))
    try:
        return interpreter.run()
    except GoExit as exit_request:
        return exit_request.code
    except GoPanic as panic:
        message = go_string(panic.value, interp=interpreter)
        raise GoError(f"panic: {message}") from None
    except RecursionError:
        raise GoError("stack overflow: the call stack got too deep") from None
    finally:
        sys.setrecursionlimit(previous)
