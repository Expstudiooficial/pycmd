"""Rust's macros, its built-in methods, and the paths that make values.

Everything here is dispatched on the Python type standing in for a Rust one:
`str` is String and &str, `list` is Vec, `dict` is HashMap, `set` is HashSet.
That keeps the method tables small enough to read, and means an iterator chain
costs no more than the Python it turns into.
"""

from __future__ import annotations

import math
import random
import sys
import time as pytime

from .rust_values import (
    Bound, Char, Enum, Formatter, Func, Iter, NONE, Native, Range, Ref, Struct,
    UNIT, Unit, RustError, RustPanic, clone_value, debug, display, err,
    format_float, is_none, is_some, ok, some, type_label, unref,
)

INT_TYPES = {"i8", "i16", "i32", "i64", "i128", "isize",
             "u8", "u16", "u32", "u64", "u128", "usize"}
FLOAT_TYPES = {"f32", "f64"}


# ------------------------------------------------------------------ format


class SortedMap(dict):
    """A BTreeMap: a dictionary that walks its keys in order.

    Until 2.8.0 BTreeMap was an ordinary dict, so it walked keys in the order
    they were inserted - which is HashMap's behaviour, near enough, and the
    one thing a BTreeMap is chosen for is the other one. Only iteration is
    sorted; lookups are the dict's own.
    """

    def __iter__(self):
        return iter(sorted(dict.keys(self)))

    def keys(self):
        return sorted(dict.keys(self))

    def values(self):
        return [dict.__getitem__(self, key) for key in sorted(dict.keys(self))]

    def items(self):
        return [(key, dict.__getitem__(self, key)) for key in sorted(dict.keys(self))]


class SortedSet(set):
    """A BTreeSet: a set that walks its members in order."""

    def __iter__(self):
        return iter(sorted(set.__iter__(self)))

def format_args(interp, template, args, env=None) -> str:
    """The formatting language `println!` and `format!` share."""
    out = []
    position = 0
    next_index = 0
    length = len(template)

    while position < length:
        char = template[position]
        if char == "{" and position + 1 < length and template[position + 1] == "{":
            out.append("{")
            position += 2
            continue
        if char == "}" and position + 1 < length and template[position + 1] == "}":
            out.append("}")
            position += 2
            continue
        if char != "{":
            out.append(char)
            position += 1
            continue

        end = template.find("}", position)
        if end < 0:
            raise RustError("unclosed { in a format string")
        body = template[position + 1:end]
        position = end + 1

        name, _, spec = body.partition(":")
        if name == "":
            if next_index >= len(args):
                raise RustError(
                    f"format string wants at least {next_index + 1} arguments, "
                    f"{len(args)} given"
                )
            value = args[next_index]
            next_index += 1
        elif name.isdigit():
            index = int(name)
            if index >= len(args):
                raise RustError(f"format string refers to argument {index}, which is not there")
            value = args[index]
        else:
            # Rust 2021 captures a plain identifier from the surrounding scope.
            if env is None or not env.has(name):
                raise RustError(f"there is no variable called {name} to format")
            value = env.lookup(name)

        out.append(apply_spec(interp, value, spec))

    return "".join(out)


def apply_spec(interp, value, spec: str) -> str:
    value = unref(value)
    fill = " "
    align = ""
    sign = ""
    alternate = False
    zero = False
    width = ""
    precision = ""
    kind = ""

    index = 0
    if len(spec) >= 2 and spec[1] in "<>^":
        fill = spec[0]
        align = spec[1]
        index = 2
    elif spec[:1] in ("<", ">", "^"):
        align = spec[0]
        index = 1

    if index < len(spec) and spec[index] in "+-":
        sign = spec[index]
        index += 1
    if spec[index:index + 1] == "#":
        alternate = True
        index += 1
    if spec[index:index + 1] == "0":
        zero = True
        index += 1
    while index < len(spec) and spec[index].isdigit():
        width += spec[index]
        index += 1
    if spec[index:index + 1] == ".":
        index += 1
        while index < len(spec) and spec[index].isdigit():
            precision += spec[index]
            index += 1
    kind = spec[index:]

    if kind == "?":
        text = debug(value, interp, pretty=alternate)
    elif kind in ("x", "X", "b", "o"):
        number = int(value)
        base = {"x": 16, "X": 16, "b": 2, "o": 8}[kind]
        text = _to_base(abs(number), base)
        if kind == "X":
            text = text.upper()
        if alternate:
            text = {"x": "0x", "X": "0x", "b": "0b", "o": "0o"}[kind] + text
        if number < 0:
            text = "-" + text
    elif kind in ("e", "E"):
        text = f"{float(value):e}"
        if kind == "E":
            text = text.upper()
    else:
        if precision and isinstance(value, float):
            text = f"{value:.{int(precision)}f}"
        elif precision and isinstance(value, int) and not isinstance(value, bool):
            text = f"{float(value):.{int(precision)}f}"
        elif precision and isinstance(value, str):
            text = value[:int(precision)]
        else:
            text = display(value, interp)

    if sign == "+" and isinstance(value, (int, float)) and not isinstance(value, bool) \
            and not text.startswith("-"):
        text = "+" + text

    if width:
        size = int(width)
        if zero and not align:
            negative = text.startswith("-") or text.startswith("+")
            head = text[0] if negative else ""
            body = text[1:] if negative else text
            text = head + body.rjust(size - len(head), "0")
        elif align == "<":
            text = text.ljust(size, fill)
        elif align == "^":
            # Rust puts the odd space on the right; Python's center does not.
            padding = max(0, size - len(text))
            left = padding // 2
            text = fill * left + text + fill * (padding - left)
        elif align == ">":
            text = text.rjust(size, fill)
        else:
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            text = text.rjust(size, fill) if numeric else text.ljust(size, fill)
    return text


def _to_base(number: int, base: int) -> str:
    if number == 0:
        return "0"
    digits = "0123456789abcdef"
    out = ""
    while number:
        out = digits[number % base] + out
        number //= base
    return out


# ------------------------------------------------------------------ macros

def run_macro(interp, name, arguments, repeat, env, line):
    """The macros a Rust program cannot do without."""
    if name in ("println", "print", "eprintln", "eprint"):
        if not arguments:
            text = "\n" if name.endswith("ln") else ""
        else:
            template = interp.evaluate(arguments[0], env)
            values = [interp.evaluate(item, env) for item in arguments[1:]]
            if not isinstance(template, str):
                raise RustError(f"{name}! wants a format string first", line)
            text = format_args(interp, template, values, env)
            if name.endswith("ln"):
                text += "\n"
        if name.startswith("e"):
            interp.write_error(text)
        else:
            interp.write(text)
        return UNIT

    if name == "format":
        template = interp.evaluate(arguments[0], env)
        values = [interp.evaluate(item, env) for item in arguments[1:]]
        return format_args(interp, template, values, env)

    if name == "vec":
        if repeat is not None:
            value = interp.evaluate(arguments[0], env)
            count = int(interp.evaluate(repeat, env))
            return [clone_value(value) for _ in range(count)]
        return [interp.evaluate(item, env) for item in arguments]

    if name == "panic":
        if not arguments:
            raise RustPanic("explicit panic")
        template = interp.evaluate(arguments[0], env)
        values = [interp.evaluate(item, env) for item in arguments[1:]]
        raise RustPanic(format_args(interp, template, values, env))

    if name in ("write", "writeln"):
        target = interp.evaluate(arguments[0], env)
        template = interp.evaluate(arguments[1], env) if len(arguments) > 1 else ""
        values = [interp.evaluate(item, env) for item in arguments[2:]]
        text = format_args(interp, template, values, env)
        if name == "writeln":
            text += "\n"
        target = unref(target)
        if isinstance(target, Formatter):
            target.write(text)
        elif isinstance(arguments[0], tuple) and arguments[0][0] == "ref":
            interp.assign_to(arguments[0][1], interp.evaluate(arguments[0][1], env) + text, env)
        else:
            interp.write(text)
        return ok()

    if name == "assert":
        condition = interp.evaluate(arguments[0], env)
        if not condition:
            detail = ""
            if len(arguments) > 1:
                template = interp.evaluate(arguments[1], env)
                values = [interp.evaluate(item, env) for item in arguments[2:]]
                detail = ": " + format_args(interp, template, values, env)
            raise RustPanic(f"assertion failed{detail}")
        return UNIT

    if name in ("assert_eq", "assert_ne"):
        left = interp.evaluate(arguments[0], env)
        right = interp.evaluate(arguments[1], env)
        same = interp.equal(left, right)
        if (name == "assert_eq") != same:
            word = "==" if name == "assert_eq" else "!="
            raise RustPanic(
                f"assertion `left {word} right` failed\n"
                f"  left: {debug(left, interp)}\n right: {debug(right, interp)}"
            )
        return UNIT

    if name in ("todo", "unimplemented"):
        raise RustPanic("not yet implemented")
    if name == "unreachable":
        raise RustPanic("internal error: entered unreachable code")
    if name == "dbg":
        value = interp.evaluate(arguments[0], env) if arguments else UNIT
        interp.write_error(f"[{line}] = {debug(value, interp)}\n")
        return value

    raise RustError(f"unknown macro {name}!", line)


# ------------------------------------------------------------------- paths

def path_value(interp, parts, line):
    """`String::new`, `Vec::new`, `i32::MAX` and friends."""
    joined = "::".join(parts)
    head = parts[0]
    tail = parts[-1]

    if joined in SIMPLE_PATHS:
        return SIMPLE_PATHS[joined]
    if tail in ("MAX", "MIN") and head in INT_TYPES | FLOAT_TYPES:
        return _limit(head, tail)

    if head in ("String", "str"):
        if tail == "new":
            return Native("String::new", lambda args: "")
        if tail == "from":
            return Native("String::from", lambda args: _as_text(args[0]))
        if tail == "with_capacity":
            return Native("String::with_capacity", lambda args: "")
    if head == "Vec":
        if tail in ("new", "with_capacity"):
            return Native("Vec::new", lambda args: [])
        if tail == "from":
            return Native("Vec::from", lambda args: list(_iterate(args[0])))
    if head == "BTreeMap":
        if tail in ("new", "with_capacity"):
            return Native("BTreeMap::new", lambda args: SortedMap())
        if tail == "from":
            return Native("BTreeMap::from", lambda args: SortedMap(
                (tuple(item)[0], tuple(item)[1]) for item in _iterate(args[0])
            ))
    if head == "HashMap":
        if tail in ("new", "with_capacity"):
            return Native("HashMap::new", lambda args: {})
        if tail == "from":
            return Native("HashMap::from", lambda args: {
                tuple(item)[0]: tuple(item)[1] for item in _iterate(args[0])
            })
    if head == "BTreeSet":
        if tail in ("new", "with_capacity"):
            return Native("BTreeSet::new", lambda args: SortedSet())
        if tail == "from":
            return Native("BTreeSet::from", lambda args: SortedSet(_iterate(args[0])))
    if head == "HashSet":
        if tail in ("new", "with_capacity"):
            return Native("HashSet::new", lambda args: set())
        if tail == "from":
            return Native("HashSet::from", lambda args: set(_iterate(args[0])))
    if head == "VecDeque" and tail in ("new", "with_capacity"):
        import collections

        return Native("VecDeque::new", lambda args: collections.deque())
    if head in ("Box", "Rc", "Arc", "RefCell", "Cell", "Cow") and tail == "new":
        # These wrappers only matter to the borrow checker, which is not here.
        return Native(f"{head}::new", lambda args: args[0])

    if head in INT_TYPES and tail == "from":
        return Native("from", lambda args: int(unref(args[0])))
    if head in FLOAT_TYPES and tail == "from":
        return Native("from", lambda args: float(unref(args[0])))
    if head == "char" and tail == "from_u32":
        return Native("char::from_u32", lambda args: some(Char(chr(int(args[0])))))
    if head == "char" and tail == "from_digit":
        return Native("char::from_digit", lambda args: some(Char(
            "0123456789abcdefghijklmnopqrstuvwxyz"[int(args[0])])))

    return None


def _limit(kind, which):
    if kind in FLOAT_TYPES:
        return sys.float_info.max if which == "MAX" else -sys.float_info.max
    bits = int("".join(c for c in kind if c.isdigit()) or 64)
    if kind.startswith("u"):
        return (1 << bits) - 1 if which == "MAX" else 0
    return (1 << (bits - 1)) - 1 if which == "MAX" else -(1 << (bits - 1))


def _as_text(value):
    value = unref(value)
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value)


def _iterate(value):
    value = unref(value)
    if isinstance(value, (Iter, Range)):
        return iter(value)
    if isinstance(value, dict):
        return iter(tuple(item) for item in value.items())
    if isinstance(value, str):
        return iter(Char(c) for c in value)
    if isinstance(value, Enum) and value.enum == "Option":
        return iter(value.values if value.variant == "Some" else [])
    if value is None:
        return iter(())
    return iter(value)


def _exit(args):
    from .rust_values import RustError

    raise SystemExit(int(unref(args[0])) if args else 0)


def _stdin(interp):
    native = Struct("Stdin", {}, "unit")
    return native


SIMPLE_PATHS = {}


def build_paths(interp) -> None:
    """Paths that need the interpreter itself to work."""
    SIMPLE_PATHS.clear()
    SIMPLE_PATHS.update({
        "std::process::exit": Native("exit", _exit),
        "process::exit": Native("exit", _exit),
        "std::io::stdin": Native("stdin", lambda args: Struct("Stdin", {}, "unit")),
        "io::stdin": Native("stdin", lambda args: Struct("Stdin", {}, "unit")),
        "stdin": Native("stdin", lambda args: Struct("Stdin", {}, "unit")),
        "std::io::stdout": Native("stdout", lambda args: Struct("Stdout", {}, "unit")),
        "io::stdout": Native("stdout", lambda args: Struct("Stdout", {}, "unit")),
        "std::mem::swap": Native("swap", lambda args: _swap(args)),
        "mem::swap": Native("swap", lambda args: _swap(args)),
        "std::mem::replace": Native("replace", lambda args: _replace(args)),
        "mem::replace": Native("replace", lambda args: _replace(args)),
        "std::f64::consts::PI": math.pi,
        "f64::consts::PI": math.pi,
        "consts::PI": math.pi,
        "std::f64::consts::E": math.e,
        "f64::consts::E": math.e,
        "std::thread::sleep": Native("sleep", lambda args: _sleep(args)),
        "thread::sleep": Native("sleep", lambda args: _sleep(args)),
        "std::time::Duration::from_millis": Native(
            "from_millis", lambda args: float(unref(args[0])) / 1000.0),
        "Duration::from_millis": Native(
            "from_millis", lambda args: float(unref(args[0])) / 1000.0),
        "Duration::from_secs": Native("from_secs", lambda args: float(unref(args[0]))),
        "Instant::now": Native("now", lambda args: pytime.monotonic()),
        "std::time::Instant::now": Native("now", lambda args: pytime.monotonic()),
    })


def _swap(args):
    left, right = args[0], args[1]
    if isinstance(left, Ref) and isinstance(right, Ref):
        first, second = left.get(), right.get()
        left.set(second)
        right.set(first)
    return UNIT


def _replace(args):
    target, value = args[0], args[1]
    if isinstance(target, Ref):
        previous = target.get()
        target.set(value)
        return previous
    return target


def _sleep(args):
    pytime.sleep(min(5.0, float(unref(args[0]))))
    return UNIT


# --------------------------------------------------------- method dispatch

def call_method(interp, receiver, name, args, hint, line):
    """Methods on the built-in types. Returns (handled, result)."""
    raw = receiver
    receiver = unref(receiver)

    # Methods every type answers to.
    if name == "clone":
        return True, clone_value(receiver)
    if name == "to_string":
        return True, display(receiver, interp)
    if name in ("to_owned", "as_str", "as_ref", "as_mut", "borrow", "borrow_mut",
                "as_slice", "as_mut_slice", "into", "as_bytes_mut", "by_ref", "deref"):
        if name == "into" and hint in INT_TYPES:
            return True, int(receiver)
        if name == "into" and hint in FLOAT_TYPES:
            return True, float(receiver)
        if name == "into" and hint == "String":
            return True, display(receiver, interp)
        return True, receiver
    if name == "eq":
        return True, interp.equal(receiver, unref(args[0]))
    if name == "ne":
        return True, not interp.equal(receiver, unref(args[0]))
    if name == "cmp" or name == "partial_cmp":
        other = unref(args[0])
        order = Enum("Ordering", "Less" if receiver < other else
                     ("Greater" if receiver > other else "Equal"), [], "unit")
        return True, some(order) if name == "partial_cmp" else order

    if isinstance(receiver, Struct) and receiver.name in ("Stdin", "Stdout"):
        return True, _io_method(interp, receiver, name, args, raw, line)

    if isinstance(receiver, Enum):
        handled, result = _enum_method(interp, receiver, name, args, hint, line)
        if handled:
            return True, result

    if isinstance(receiver, str) and not isinstance(receiver, Char):
        handled, result = _string_method(interp, receiver, name, args, hint, raw, line)
        if handled:
            return True, result

    if isinstance(receiver, Char):
        handled, result = _char_method(interp, receiver, name, args, line)
        if handled:
            return True, result

    if isinstance(receiver, bool):
        if name == "then":
            return True, some(interp.call(args[0], [], line)) if receiver else NONE
        if name == "then_some":
            return True, some(args[0]) if receiver else NONE

    if isinstance(receiver, (int, float)) and not isinstance(receiver, bool):
        handled, result = _number_method(interp, receiver, name, args, hint, line)
        if handled:
            return True, result

    if isinstance(receiver, list):
        handled, result = _vec_method(interp, receiver, name, args, hint, raw, line)
        if handled:
            return True, result

    if isinstance(receiver, dict):
        handled, result = _map_method(interp, receiver, name, args, hint, line)
        if handled:
            return True, result

    if isinstance(receiver, set):
        handled, result = _set_method(interp, receiver, name, args, line)
        if handled:
            return True, result

    if isinstance(receiver, (Iter, Range, tuple)):
        handled, result = _iterator_method(interp, receiver, name, args, hint, line)
        if handled:
            return True, result

    # Anything that can be iterated answers the iterator methods.
    if name in ITERATOR_METHODS and isinstance(receiver, (list, dict, set, str)):
        return _iterator_method(interp, Iter(_iterate(receiver)), name, args, hint, line)

    return False, None


def _io_method(interp, receiver, name, args, raw, line):
    if name == "read_line":
        target = args[0]
        text = interp.read_line()
        if text is None:
            return ok(0)
        if isinstance(target, Ref):
            target.set(unref(target) + text + "\n")
        return ok(len(text) + 1)
    if name == "lines":
        return Iter(_stdin_lines(interp))
    if name in ("flush", "lock"):
        return ok() if name == "flush" else receiver
    if name == "write_all" or name == "write":
        interp.write(_as_text(args[0]))
        return ok()
    raise RustError(f"Stdin has no method {name}", line)


def _stdin_lines(interp):
    while True:
        text = interp.read_line()
        if text is None:
            return
        yield ok(text)


def _enum_method(interp, receiver, name, args, hint, line):
    kind = receiver.enum
    variant = receiver.variant
    inner = receiver.values[0] if receiver.values else UNIT

    if kind == "Option":
        if name == "is_some":
            return True, variant == "Some"
        if name == "is_none":
            return True, variant == "None"
        if name == "unwrap":
            if variant == "None":
                raise RustPanic("called `Option::unwrap()` on a `None` value")
            return True, inner
        if name == "expect":
            if variant == "None":
                raise RustPanic(display(args[0], interp))
            return True, inner
        if name == "unwrap_or":
            return True, inner if variant == "Some" else args[0]
        if name == "unwrap_or_else":
            return True, inner if variant == "Some" else interp.call(args[0], [], line)
        if name == "unwrap_or_default":
            return True, inner if variant == "Some" else 0
        if name == "map":
            return True, some(interp.call(args[0], [inner], line)) if variant == "Some" else NONE
        if name == "and_then":
            return True, interp.call(args[0], [inner], line) if variant == "Some" else NONE
        if name == "filter":
            keep = variant == "Some" and interp.call(args[0], [inner], line)
            return True, receiver if keep else NONE
        if name == "or":
            return True, receiver if variant == "Some" else args[0]
        if name == "ok_or":
            return True, ok(inner) if variant == "Some" else err(args[0])
        if name in ("cloned", "copied", "as_deref"):
            return True, receiver
        if name == "take":
            return True, receiver
        if name == "iter" or name == "into_iter":
            return True, Iter(list(receiver.values) if variant == "Some" else [])

    if kind == "Result":
        if name == "is_ok":
            return True, variant == "Ok"
        if name == "is_err":
            return True, variant == "Err"
        if name == "unwrap":
            if variant == "Err":
                raise RustPanic(
                    f"called `Result::unwrap()` on an `Err` value: {debug(inner, interp)}"
                )
            return True, inner
        if name == "expect":
            if variant == "Err":
                raise RustPanic(
                    f"{display(args[0], interp)}: {debug(inner, interp)}"
                )
            return True, inner
        if name == "unwrap_or":
            return True, inner if variant == "Ok" else args[0]
        if name == "unwrap_or_else":
            return True, inner if variant == "Ok" else interp.call(args[0], [inner], line)
        if name == "ok":
            return True, some(inner) if variant == "Ok" else NONE
        if name == "err":
            return True, some(inner) if variant == "Err" else NONE
        if name == "map":
            return True, ok(interp.call(args[0], [inner], line)) if variant == "Ok" else receiver
        if name == "map_err":
            return True, receiver if variant == "Ok" else err(interp.call(args[0], [inner], line))
        if name == "and_then":
            return True, interp.call(args[0], [inner], line) if variant == "Ok" else receiver
        if name == "unwrap_err":
            if variant == "Ok":
                raise RustPanic("called `Result::unwrap_err()` on an `Ok` value")
            return True, inner

    return False, None


def _string_method(interp, text, name, args, hint, raw, line):
    def first():
        return unref(args[0])

    if name == "len":
        return True, len(text.encode("utf-8"))
    if name == "is_empty":
        return True, len(text) == 0
    if name == "chars":
        return True, Iter([Char(c) for c in text])
    if name == "bytes":
        return True, Iter(list(text.encode("utf-8")))
    if name == "as_bytes":
        return True, list(text.encode("utf-8"))
    if name == "char_indices":
        return True, Iter([(index, Char(c)) for index, c in enumerate(text)])
    if name == "lines":
        return True, Iter(text.splitlines())
    if name == "split_whitespace" or name == "split_ascii_whitespace":
        return True, Iter(text.split())
    if name == "split":
        separator = first()
        if isinstance(separator, (Func, Bound, Native)):
            return True, Iter(_split_by(interp, text, separator, line))
        return True, Iter(text.split(str(separator)))
    if name == "splitn":
        return True, Iter(text.split(str(unref(args[1])), int(first()) - 1))
    if name == "rsplit":
        return True, Iter(text.split(str(first()))[::-1])
    if name == "split_once":
        head, found, tail = text.partition(str(first()))
        return True, some((head, tail)) if found else NONE
    if name == "trim":
        return True, text.strip()
    if name == "trim_start":
        return True, text.lstrip()
    if name == "trim_end":
        return True, text.rstrip()
    if name == "trim_matches":
        return True, text.strip(str(first()))
    if name == "to_uppercase" or name == "to_ascii_uppercase":
        return True, text.upper()
    if name == "to_lowercase" or name == "to_ascii_lowercase":
        return True, text.lower()
    if name == "contains":
        needle = first()
        return True, str(needle) in text
    if name == "starts_with":
        return True, text.startswith(str(first()))
    if name == "ends_with":
        return True, text.endswith(str(first()))
    if name == "find":
        index = text.find(str(first()))
        return True, some(index) if index >= 0 else NONE
    if name == "rfind":
        index = text.rfind(str(first()))
        return True, some(index) if index >= 0 else NONE
    if name == "replace" or name == "replacen":
        if name == "replacen":
            return True, text.replace(str(first()), str(unref(args[1])), int(unref(args[2])))
        return True, text.replace(str(first()), str(unref(args[1])))
    if name == "repeat":
        return True, text * int(first())
    if name == "parse":
        return True, _parse_text(text, hint)
    if name == "push_str" or name == "push":
        addition = str(first())
        if isinstance(raw, Ref):
            raw.set(text + addition)
            return True, UNIT
        raise RustError("push on a String needs a mutable binding", line)
    if name == "insert_str":
        position = int(first())
        addition = str(unref(args[1]))
        if isinstance(raw, Ref):
            raw.set(text[:position] + addition + text[position:])
        return True, UNIT
    if name == "clear":
        if isinstance(raw, Ref):
            raw.set("")
        return True, UNIT
    if name == "pop":
        if not text:
            return True, NONE
        if isinstance(raw, Ref):
            raw.set(text[:-1])
        return True, some(Char(text[-1]))
    if name == "get":
        return True, some(text) if text else NONE
    if name == "count":
        return True, len(text)
    if name == "nth":
        index = int(first())
        return True, some(Char(text[index])) if index < len(text) else NONE
    if name == "join":
        return True, text
    if name == "capacity":
        return True, len(text)
    if name == "matches":
        needle = str(first())
        return True, Iter([needle] * text.count(needle))
    return False, None


def _split_by(interp, text, predicate, line):
    pieces = []
    current = []
    for character in text:
        if interp.call(predicate, [Char(character)], line):
            pieces.append("".join(current))
            current = []
        else:
            current.append(character)
    pieces.append("".join(current))
    return pieces


def _parse_text(text, hint):
    body = text.strip()
    try:
        if hint in FLOAT_TYPES:
            return ok(float(body))
        if hint == "char":
            if len(body) != 1:
                raise ValueError
            return ok(Char(body))
        if hint == "bool":
            if body not in ("true", "false"):
                raise ValueError
            return ok(body == "true")
        return ok(int(body))
    except ValueError:
        kind = "float" if hint in FLOAT_TYPES else "digit"
        return err(Struct("ParseIntError", {
            "message": f"invalid {kind} found in string",
        }, "named"))


def _char_method(interp, character, name, args, line):
    if name == "is_alphabetic" or name == "is_alphanumeric":
        return True, character.isalpha() if name == "is_alphabetic" else character.isalnum()
    if name == "is_numeric" or name == "is_ascii_digit" or name == "is_digit":
        return True, character.isdigit()
    if name == "is_whitespace":
        return True, character.isspace()
    if name == "is_uppercase" or name == "is_ascii_uppercase":
        return True, character.isupper()
    if name == "is_lowercase" or name == "is_ascii_lowercase":
        return True, character.islower()
    if name == "is_ascii_punctuation":
        return True, not character.isalnum() and not character.isspace()
    if name == "to_uppercase" or name == "to_ascii_uppercase":
        return True, Char(character.upper())
    if name == "to_lowercase" or name == "to_ascii_lowercase":
        return True, Char(character.lower())
    if name == "to_digit":
        base = int(unref(args[0])) if args else 10
        try:
            return True, some(int(character, base))
        except ValueError:
            return True, NONE
    if name == "len_utf8":
        return True, len(character.encode("utf-8"))
    return False, None


def _number_method(interp, number, name, args, hint, line):
    def first():
        return unref(args[0])

    if name == "abs":
        return True, abs(number)
    if name == "pow" or name == "powi":
        return True, number ** int(first())
    if name == "powf":
        return True, float(number) ** float(first())
    if name == "sqrt":
        return True, math.sqrt(float(number))
    if name == "floor":
        return True, float(math.floor(number))
    if name == "ceil":
        return True, float(math.ceil(number))
    if name == "round":
        return True, float(math.floor(number + 0.5) if number >= 0 else math.ceil(number - 0.5))
    if name == "trunc":
        return True, float(int(number))
    if name == "min":
        return True, min(number, first())
    if name == "max":
        return True, max(number, first())
    if name == "clamp":
        return True, max(first(), min(unref(args[1]), number))
    if name == "signum":
        return True, (0 if number == 0 else (1 if number > 0 else -1))
    if name in ("ln", "log", "log10", "log2", "exp", "sin", "cos", "tan", "atan", "asin", "acos"):
        table = {"ln": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
                 "sin": math.sin, "cos": math.cos, "tan": math.tan, "atan": math.atan,
                 "asin": math.asin, "acos": math.acos}
        if name == "log":
            return True, math.log(float(number), float(first()))
        return True, table[name](float(number))
    if name == "hypot":
        return True, math.hypot(float(number), float(first()))
    if name == "atan2":
        return True, math.atan2(float(number), float(first()))
    if name == "is_nan":
        return True, number != number
    if name in ("checked_add", "checked_sub", "checked_mul"):
        other = first()
        table = {"checked_add": number + other, "checked_sub": number - other,
                 "checked_mul": number * other}
        return True, some(table[name])
    if name == "checked_div":
        other = first()
        return True, NONE if other == 0 else some(number // other)
    if name in ("saturating_sub", "saturating_add"):
        other = first()
        value = number - other if name == "saturating_sub" else number + other
        return True, max(0, value)
    if name in ("wrapping_add", "wrapping_sub", "wrapping_mul"):
        other = first()
        table = {"wrapping_add": number + other, "wrapping_sub": number - other,
                 "wrapping_mul": number * other}
        return True, table[name]
    if name == "count_ones":
        return True, bin(int(number) & ((1 << 64) - 1)).count("1")
    if name == "to_le_bytes" or name == "to_be_bytes":
        return True, list(int(number).to_bytes(8, "little" if name.endswith("le_bytes")
                                               else "big", signed=True))
    if name == "rem_euclid":
        return True, number % first()
    if name == "div_euclid":
        return True, number // first()
    return False, None


def _vec_method(interp, items, name, args, hint, raw, line):
    def first():
        return unref(args[0]) if args else None

    if name == "push":
        items.append(args[0])
        return True, UNIT
    if name == "pop":
        return True, some(items.pop()) if items else NONE
    if name == "len":
        return True, len(items)
    if name == "is_empty":
        return True, not items
    if name == "clear":
        items.clear()
        return True, UNIT
    if name == "insert":
        items.insert(int(first()), args[1])
        return True, UNIT
    if name == "remove":
        index = int(first())
        if index >= len(items):
            raise RustPanic(f"removal index (is {index}) should be < len (is {len(items)})")
        return True, items.pop(index)
    if name == "swap_remove":
        index = int(first())
        items[index], items[-1] = items[-1], items[index]
        return True, items.pop()
    if name == "swap":
        i, j = int(first()), int(unref(args[1]))
        items[i], items[j] = items[j], items[i]
        return True, UNIT
    if name == "get":
        index = first()
        if isinstance(index, Range):
            return True, some(items[index.start:index.end])
        index = int(index)
        return True, some(items[index]) if 0 <= index < len(items) else NONE
    if name == "first":
        return True, some(items[0]) if items else NONE
    if name == "last":
        return True, some(items[-1]) if items else NONE
    if name == "contains":
        wanted = first()
        return True, any(interp.equal(item, wanted) for item in items)
    if name == "sort":
        items.sort(key=_sort_key)
        return True, UNIT
    if name == "sort_unstable":
        items.sort(key=_sort_key)
        return True, UNIT
    if name in ("sort_by", "sort_unstable_by"):
        import functools

        items.sort(key=functools.cmp_to_key(
            lambda a, b: _ordering_to_int(interp.call(args[0], [a, b], line))
        ))
        return True, UNIT
    if name in ("sort_by_key", "sort_unstable_by_key"):
        items.sort(key=lambda item: _sort_key(interp.call(args[0], [item], line)))
        return True, UNIT
    if name == "reverse":
        items.reverse()
        return True, UNIT
    if name == "dedup":
        seen = []
        for item in items:
            if not seen or not interp.equal(seen[-1], item):
                seen.append(item)
        items[:] = seen
        return True, UNIT
    if name == "retain":
        items[:] = [item for item in items if interp.call(args[0], [item], line)]
        return True, UNIT
    if name == "extend" or name == "extend_from_slice" or name == "append":
        addition = list(_iterate(args[0]))
        items.extend(addition)
        if name == "append" and isinstance(unref(args[0]), list):
            unref(args[0]).clear()
        return True, UNIT
    if name == "truncate":
        del items[int(first()):]
        return True, UNIT
    if name == "split_off":
        index = int(first())
        tail = items[index:]
        del items[index:]
        return True, tail
    if name == "join":
        separator = str(first())
        return True, separator.join(display(item, interp) for item in items)
    if name == "concat":
        return True, "".join(display(item, interp) for item in items)
    if name == "binary_search":
        import bisect

        wanted = first()
        keys = [_sort_key(item) for item in items]
        index = bisect.bisect_left(keys, _sort_key(wanted))
        if index < len(items) and interp.equal(items[index], wanted):
            return True, ok(index)
        return True, err(index)
    if name == "windows":
        size = int(first())
        return True, Iter([items[i:i + size] for i in range(len(items) - size + 1)])
    if name == "chunks":
        size = int(first())
        return True, Iter([items[i:i + size] for i in range(0, len(items), size)])
    if name == "capacity":
        return True, len(items)
    if name == "resize":
        size = int(first())
        while len(items) < size:
            items.append(clone_value(args[1]))
        del items[size:]
        return True, UNIT
    if name == "iter_mut":
        # Without real references this hands back the items themselves, which
        # is enough for the objects people actually mutate through it.
        return True, Iter(list(items))
    if name == "drain":
        taken = list(items)
        items.clear()
        return True, Iter(taken)
    if name == "to_vec":
        return True, list(items)
    if name == "fill":
        items[:] = [clone_value(args[0]) for _ in items]
        return True, UNIT
    return _iterator_method(interp, Iter(items), name, args, hint, line)


def _ordering_to_int(value) -> int:
    if isinstance(value, Enum):
        return {"Less": -1, "Equal": 0, "Greater": 1}.get(value.variant, 0)
    return int(value)


def _sort_key(value):
    value = unref(value)
    if isinstance(value, bool):
        return (0, int(value), "")
    if isinstance(value, (int, float)):
        return (0, value, "")
    if isinstance(value, str):
        return (1, 0, value)
    if isinstance(value, tuple):
        return (2, 0, tuple(_sort_key(item) for item in value))
    return (3, 0, display(value))


def _map_method(interp, mapping, name, args, hint, line):
    def first():
        return unref(args[0]) if args else None

    if name == "insert":
        key = _key(first())
        previous = mapping.get(key)
        mapping[key] = args[1]
        return True, some(previous) if previous is not None else NONE
    if name == "get":
        value = mapping.get(_key(first()))
        return True, some(value) if value is not None else NONE
    if name == "get_mut":
        value = mapping.get(_key(first()))
        return True, some(value) if value is not None else NONE
    if name == "contains_key":
        return True, _key(first()) in mapping
    if name == "remove":
        key = _key(first())
        if key in mapping:
            return True, some(mapping.pop(key))
        return True, NONE
    if name == "len":
        return True, len(mapping)
    if name == "is_empty":
        return True, not mapping
    if name == "clear":
        mapping.clear()
        return True, UNIT
    if name == "keys":
        return True, Iter(list(mapping.keys()))
    if name == "values":
        return True, Iter(list(mapping.values()))
    if name == "values_mut":
        return True, Iter(list(mapping.values()))
    if name == "entry":
        return True, _Entry(mapping, _key(first()))
    if name == "iter" or name == "into_iter" or name == "iter_mut":
        return True, Iter([tuple(pair) for pair in mapping.items()])
    if name == "get_or_insert_with":
        key = _key(first())
        if key not in mapping:
            mapping[key] = interp.call(args[1], [], line)
        return True, mapping[key]
    if name == "extend":
        for pair in _iterate(args[0]):
            pair = tuple(pair)
            mapping[_key(pair[0])] = pair[1]
        return True, UNIT
    return _iterator_method(interp, Iter([tuple(p) for p in mapping.items()]),
                            name, args, hint, line)


def _key(value):
    value = unref(value)
    if isinstance(value, list):
        return tuple(value)
    return value


class _Entry:
    """What `map.entry(k)` returns: the one API that makes counters readable."""

    __slots__ = ("mapping", "key")

    def __init__(self, mapping, key) -> None:
        self.mapping = mapping
        self.key = key


def entry_method(interp, entry, name, args, line):
    if name == "or_insert":
        if entry.key not in entry.mapping:
            entry.mapping[entry.key] = args[0]
        return True, Ref(lambda: entry.mapping[entry.key],
                         lambda value: entry.mapping.__setitem__(entry.key, value))
    if name == "or_insert_with":
        if entry.key not in entry.mapping:
            entry.mapping[entry.key] = interp.call(args[0], [], line)
        return True, Ref(lambda: entry.mapping[entry.key],
                         lambda value: entry.mapping.__setitem__(entry.key, value))
    if name == "or_default":
        if entry.key not in entry.mapping:
            entry.mapping[entry.key] = 0
        return True, Ref(lambda: entry.mapping[entry.key],
                         lambda value: entry.mapping.__setitem__(entry.key, value))
    if name == "and_modify":
        if entry.key in entry.mapping:
            reference = Ref(lambda: entry.mapping[entry.key],
                            lambda value: entry.mapping.__setitem__(entry.key, value))
            interp.call(args[0], [reference], line)
        return True, entry
    raise RustError(f"Entry has no method {name}", line)


def _set_method(interp, members, name, args, line):
    def first():
        return _key(unref(args[0])) if args else None

    if name == "insert":
        added = first() not in members
        members.add(first())
        return True, added
    if name == "contains":
        return True, first() in members
    if name == "remove":
        found = first() in members
        members.discard(first())
        return True, found
    if name == "len":
        return True, len(members)
    if name == "is_empty":
        return True, not members
    if name == "clear":
        members.clear()
        return True, UNIT
    if name in ("iter", "into_iter"):
        return True, Iter(list(members))
    if name == "union":
        return True, Iter(sorted(members | unref(args[0]), key=_sort_key))
    if name == "intersection":
        return True, Iter(sorted(members & unref(args[0]), key=_sort_key))
    if name == "difference":
        return True, Iter(sorted(members - unref(args[0]), key=_sort_key))
    return False, None


ITERATOR_METHODS = {
    "iter", "into_iter", "map", "filter", "filter_map", "flat_map", "flatten",
    "enumerate", "zip", "rev", "take", "take_while", "skip", "skip_while",
    "chain", "step_by", "collect", "sum", "product", "count", "fold", "any",
    "all", "find", "position", "max", "min", "max_by_key", "min_by_key",
    "max_by", "min_by", "last", "nth", "for_each", "peekable", "cloned",
    "copied", "inspect", "unzip", "partition", "cycle", "scan", "reduce",
}


def _iterator_method(interp, receiver, name, args, hint, line):
    if isinstance(receiver, tuple):
        # A tuple is not an iterator, but `.0`-style access goes through fields
        # and only a few methods make sense here.
        if name in ("len",):
            return True, len(receiver)
        return False, None

    def items():
        return list(_iterate(receiver))

    if name in ("iter", "into_iter", "cloned", "copied", "by_ref"):
        return True, Iter(items())
    if name == "map":
        return True, Iter([interp.call(args[0], [item], line) for item in items()])
    if name == "filter":
        return True, Iter([item for item in items() if interp.call(args[0], [item], line)])
    if name == "filter_map":
        out = []
        for item in items():
            result = interp.call(args[0], [item], line)
            if is_some(result):
                out.append(result.values[0])
        return True, Iter(out)
    if name == "flat_map":
        out = []
        for item in items():
            out.extend(_iterate(interp.call(args[0], [item], line)))
        return True, Iter(out)
    if name == "flatten":
        out = []
        for item in items():
            out.extend(_iterate(item))
        return True, Iter(out)
    if name == "enumerate":
        return True, Iter([(index, item) for index, item in enumerate(items())])
    if name == "zip":
        return True, Iter([tuple(pair) for pair in zip(items(), _iterate(args[0]))])
    if name == "rev":
        return True, Iter(list(reversed(items())))
    if name == "take":
        return True, Iter(items()[:int(unref(args[0]))])
    if name == "skip":
        return True, Iter(items()[int(unref(args[0])):])
    if name == "step_by":
        return True, Iter(items()[::int(unref(args[0]))])
    if name == "take_while":
        out = []
        for item in items():
            if not interp.call(args[0], [item], line):
                break
            out.append(item)
        return True, Iter(out)
    if name == "skip_while":
        out = []
        skipping = True
        for item in items():
            if skipping and interp.call(args[0], [item], line):
                continue
            skipping = False
            out.append(item)
        return True, Iter(out)
    if name == "chain":
        return True, Iter(items() + list(_iterate(args[0])))
    if name == "cycle":
        return True, Iter(items() * 32)
    if name == "peekable":
        return True, Iter(items())
    if name == "inspect":
        for item in items():
            interp.call(args[0], [item], line)
        return True, Iter(items())
    if name == "collect":
        return True, _collect(interp, items(), hint)
    if name == "sum":
        values = items()
        if hint in FLOAT_TYPES or any(isinstance(v, float) for v in values):
            return True, float(sum(unref(v) for v in values))
        return True, sum(unref(v) for v in values)
    if name == "product":
        total = 1
        for item in items():
            total *= unref(item)
        return True, total
    if name == "count":
        return True, len(items())
    if name == "fold":
        total = args[0]
        for item in items():
            total = interp.call(args[1], [total, item], line)
        return True, total
    if name == "reduce":
        values = items()
        if not values:
            return True, NONE
        total = values[0]
        for item in values[1:]:
            total = interp.call(args[0], [total, item], line)
        return True, some(total)
    if name == "scan":
        state = args[0]
        out = []
        for item in items():
            result = interp.call(args[1], [state, item], line)
            if is_none(result):
                break
            out.append(result.values[0] if is_some(result) else result)
        return True, Iter(out)
    if name == "any":
        return True, any(interp.call(args[0], [item], line) for item in items())
    if name == "all":
        return True, all(interp.call(args[0], [item], line) for item in items())
    if name == "find":
        for item in items():
            if interp.call(args[0], [item], line):
                return True, some(item)
        return True, NONE
    if name == "find_map":
        for item in items():
            result = interp.call(args[0], [item], line)
            if is_some(result):
                return True, result
        return True, NONE
    if name == "position":
        for index, item in enumerate(items()):
            if interp.call(args[0], [item], line):
                return True, some(index)
        return True, NONE
    if name == "for_each":
        for item in items():
            interp.call(args[0], [item], line)
        return True, UNIT
    if name in ("max", "min"):
        values = items()
        if not values:
            return True, NONE
        chosen = (max if name == "max" else min)(values, key=_sort_key)
        return True, some(chosen)
    if name in ("max_by_key", "min_by_key"):
        values = items()
        if not values:
            return True, NONE
        chosen = (max if name == "max_by_key" else min)(
            values, key=lambda item: _sort_key(interp.call(args[0], [item], line))
        )
        return True, some(chosen)
    if name in ("max_by", "min_by"):
        import functools

        values = items()
        if not values:
            return True, NONE
        ordered = sorted(values, key=functools.cmp_to_key(
            lambda a, b: _ordering_to_int(interp.call(args[0], [a, b], line))
        ))
        return True, some(ordered[-1] if name == "max_by" else ordered[0])
    if name == "last":
        values = items()
        return True, some(values[-1]) if values else NONE
    if name == "nth":
        values = items()
        index = int(unref(args[0]))
        return True, some(values[index]) if index < len(values) else NONE
    if name == "len":
        return True, len(items())
    if name == "sum_by":
        return True, sum(interp.call(args[0], [item], line) for item in items())
    if name == "unzip":
        values = items()
        return True, ([tuple(v)[0] for v in values], [tuple(v)[1] for v in values])
    if name == "partition":
        yes, no = [], []
        for item in items():
            (yes if interp.call(args[0], [item], line) else no).append(item)
        return True, (yes, no)
    if name == "contains":
        wanted = unref(args[0])
        if isinstance(receiver, Range):
            return True, receiver.contains(wanted)
        return True, any(interp.equal(item, wanted) for item in items())
    if name == "next":
        values = items()
        return True, some(values[0]) if values else NONE
    return False, None


def _collect(interp, values, hint):
    if hint in ("String", "str"):
        return "".join(display(item, interp) for item in values)
    if hint in ("HashMap", "BTreeMap"):
        return {_key(tuple(item)[0]): tuple(item)[1] for item in values}
    if hint in ("HashSet", "BTreeSet"):
        return {_key(item) for item in values}
    if hint == "Result":
        # collect::<Result<Vec<_>, _>>() stops at the first Err.
        out = []
        for item in values:
            if isinstance(item, Enum) and item.enum == "Result":
                if item.variant == "Err":
                    return item
                out.append(item.values[0])
            else:
                out.append(item)
        return ok(out)
    if hint == "Option":
        out = []
        for item in values:
            if is_none(item):
                return NONE
            out.append(item.values[0] if is_some(item) else item)
        return some(out)
    if values and all(isinstance(unref(item), Char) for item in values):
        return "".join(str(unref(item)) for item in values)
    return list(values)
