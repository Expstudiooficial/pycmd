"""Go's builtins and the parts of its standard library worth carrying.

Chosen by what people write rather than by what the library contains: fmt,
strings, strconv, math, sort, errors, time, os, bufio, unicode, sync and
math/rand cover essentially every program that fits on a phone screen. What is
missing is missing loudly - an unknown package is an error at the import, not a
mystery at the call.
"""

from __future__ import annotations

import math as pymath
import random
import sys
import threading
import time as pytime

from .go_values import (
    Array, Bound, Builtin, Chan, ErrorValue, Func, GoError, GoExit, GoPanic,
    NIL, Nil, Package, Pointer, Rune, Slice, Struct, copy_value, format_float,
    go_string, type_name,
)


class Native:
    """A standard-library object with methods, like a Builder or a WaitGroup."""

    def __init__(self, label, members=None) -> None:
        self.label = label
        self.members = members or {}

    def member(self, name, line=0):
        if name not in self.members:
            raise GoError(f"{self.label} has no field or method {name}", line)
        return self.members[name]

    def set(self, name, value) -> None:
        self.members[name] = value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.label}>"


def method(name, function):
    return Builtin(name, function)


# --------------------------------------------------------------- formatting

def format_verbs(interp, spec: str, args) -> str:
    """Printf, with the verbs and flags that actually get typed."""
    out = []
    index = 0
    position = 0
    length = len(spec)

    while position < length:
        char = spec[position]
        if char != "%":
            out.append(char)
            position += 1
            continue

        position += 1
        if position < length and spec[position] == "%":
            out.append("%")
            position += 1
            continue

        flags = ""
        while position < length and spec[position] in "-+ #0":
            flags += spec[position]
            position += 1

        width = ""
        if position < length and spec[position] == "*":
            width = str(int(args[index]))
            index += 1
            position += 1
        else:
            while position < length and spec[position].isdigit():
                width += spec[position]
                position += 1

        precision = ""
        if position < length and spec[position] == ".":
            position += 1
            precision = "."
            if position < length and spec[position] == "*":
                precision += str(int(args[index]))
                index += 1
                position += 1
            else:
                while position < length and spec[position].isdigit():
                    precision += spec[position]
                    position += 1

        if position >= length:
            out.append("%!(NOVERB)")
            break

        verb = spec[position]
        position += 1

        if index >= len(args):
            out.append(f"%!{verb}(MISSING)")
            continue
        value = args[index]
        index += 1
        out.append(render(interp, verb, flags, width, precision, value))

    if index < len(args):
        extra = ", ".join(f"{type_name(v)}={go_string(v, interp=interp)}" for v in args[index:])
        out.append(f"%!(EXTRA {extra})")
    return "".join(out)


def render(interp, verb, flags, width, precision, value) -> str:
    plus = "+" in flags
    if verb == "v":
        text = go_string(value, plus=plus, interp=interp)
    elif verb == "T":
        text = type_name(value)
    elif verb in "dbo":
        number = int(value)
        base = {"d": 10, "b": 2, "o": 8}[verb]
        text = _in_base(number, base)
        if plus and number >= 0:
            text = "+" + text
    elif verb in "xX":
        if isinstance(value, str):
            text = value.encode("utf-8").hex()
        elif isinstance(value, (Slice, Array)):
            text = "".join(f"{int(item):02x}" for item in value)
        else:
            text = _in_base(int(value), 16)
        if verb == "X":
            text = text.upper()
    elif verb in "eEfFgG":
        number = float(value)
        digits = int(precision[1:]) if len(precision) > 1 else (6 if verb in "eEfF" else None)
        if verb in "fF":
            text = f"{number:.{digits}f}"
        elif verb in "eE":
            text = f"{number:.{digits}e}"
            text = text.replace("e-0", "e-0").replace("e+0", "e+0")
            if verb == "E":
                text = text.upper()
        else:
            text = format_float(number) if digits is None else f"{number:.{digits}g}"
        if plus and number >= 0:
            text = "+" + text
    elif verb == "s":
        text = go_string(value, plus=plus, interp=interp)
        if len(precision) > 1:
            text = text[:int(precision[1:])]
    elif verb == "q":
        text = _quote(value if isinstance(value, str) else go_string(value, interp=interp))
    elif verb == "c":
        text = chr(int(value))
    elif verb == "t":
        text = "true" if value else "false"
    elif verb == "p":
        text = f"0x{id(value):x}"
    elif verb == "U":
        text = f"U+{int(value):04X}"
    else:
        return f"%!{verb}({type_name(value)}={go_string(value, interp=interp)})"

    if width:
        size = int(width)
        if "-" in flags:
            text = text.ljust(size)
        elif "0" in flags and verb not in "sqvT":
            negative = text.startswith("-")
            body = text[1:] if negative else text
            body = body.rjust(size - 1 if negative else size, "0")
            text = ("-" + body) if negative else body
        else:
            text = text.rjust(size)
    return text


def _in_base(number: int, base: int) -> str:
    if base == 10:
        return str(number)
    digits = "0123456789abcdef"
    negative = number < 0
    number = abs(number)
    if number == 0:
        return "0"
    out = ""
    while number:
        out = digits[number % base] + out
        number //= base
    return ("-" + out) if negative else out


def _quote(text: str) -> str:
    body = text.replace("\\", "\\\\").replace('"', '\\"')
    body = body.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return f'"{body}"'


def spaced(interp, args) -> str:
    """`fmt.Print` inserts a space only between two non-strings."""
    pieces = []
    for position, value in enumerate(args):
        if position:
            previous = args[position - 1]
            if not isinstance(previous, str) and not isinstance(value, str):
                pieces.append(" ")
        pieces.append(go_string(value, interp=interp))
    return "".join(pieces)


# ---------------------------------------------------------------- builtins

def _len(args):
    value = args[0]
    if isinstance(value, Nil):
        return 0
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (Slice, Array, dict, Chan)):
        return len(value)
    raise GoError(f"len is not defined for {type_name(value)}")


def _cap(args):
    value = args[0]
    if isinstance(value, (Slice, Array)):
        return value.capacity
    if isinstance(value, Chan):
        return value.capacity
    if isinstance(value, Nil):
        return 0
    raise GoError(f"cap is not defined for {type_name(value)}")


def _append(args):
    target = args[0]
    additions = args[1:]
    if isinstance(target, Nil):
        target = Slice([], 0, 0, 0)
    if not isinstance(target, Slice):
        raise GoError(f"append needs a slice, found {type_name(target)}")

    end = target.offset + target.length
    room = target.capacity - target.length
    if room >= len(additions) and end == len(target.backing) - max(0, room):
        pass
    if len(additions) <= room:
        # There is spare capacity, so append writes into the backing array -
        # which is exactly why two slices over one array can surprise you.
        for position, value in enumerate(additions):
            slot = end + position
            while len(target.backing) <= slot:
                target.backing.append(NIL)
            target.backing[slot] = copy_value(value)
        return Slice(target.backing, target.offset, target.length + len(additions),
                     target.capacity, target.element)

    grown = target.items() + [copy_value(value) for value in additions]
    capacity = max(len(grown), target.capacity * 2, 4)
    backing = grown + [NIL] * (capacity - len(grown))
    return Slice(backing, 0, len(grown), capacity, target.element)


def _copy(args):
    destination, source = args[0], args[1]
    if isinstance(source, str):
        source = Slice.of(list(source.encode("utf-8")))
    count = min(len(destination), len(source))
    values = [source.get(index) for index in range(count)]
    for index in range(count):
        destination.set(index, values[index])
    return count


def _delete(args):
    mapping, key = args[0], args[1]
    if isinstance(mapping, dict):
        mapping.pop(key, None)
    return None


def _panic(args):
    raise GoPanic(args[0] if args else NIL)


def _recover(interp, args):
    stack = getattr(interp.frames, "stack", None)
    # The frame that deferred this call is the one below the deferred function.
    for frame in reversed(stack or []):
        if frame.panic is not None and not frame.recovered:
            frame.recovered = True
            value = frame.panic.value
            frame.panic = None
            return value
    return NIL


def _print(interp, args):
    interp.write_error(spaced(interp, args))
    return None


def _println(interp, args):
    interp.write_error(" ".join(go_string(v, interp=interp) for v in args) + "\n")
    return None


def _close(args):
    channel = args[0]
    if isinstance(channel, Chan):
        channel.close()
    return None


def _min(args):
    return min(args)


def _max(args):
    return max(args)


BUILTINS = {
    "len": Builtin("len", _len),
    "cap": Builtin("cap", _cap),
    "append": Builtin("append", _append),
    "copy": Builtin("copy", _copy),
    "delete": Builtin("delete", _delete),
    "panic": Builtin("panic", _panic),
    "recover": Builtin("recover", _recover, wants_interp=True),
    "print": Builtin("print", _print, wants_interp=True),
    "println": Builtin("println", _println, wants_interp=True),
    "close": Builtin("close", _close),
    "min": Builtin("min", _min),
    "max": Builtin("max", _max),
}


# ------------------------------------------------------------- conversions

def _to_int(interp, args, line):
    value = args[0]
    if isinstance(value, bool):
        raise GoError("cannot convert a bool to an int", line)
    if isinstance(value, str):
        raise GoError("cannot convert a string to an int; use strconv.Atoi", line)
    return interp.wrap_int(int(value))


def _to_float(interp, args, line):
    return float(args[0])


def _to_string(interp, args, line):
    value = args[0]
    if isinstance(value, str):
        return value
    if isinstance(value, (Slice, Array)):
        items = list(value)
        if items and all(isinstance(item, Rune) for item in items):
            return "".join(chr(int(item)) for item in items)
        try:
            return bytes(int(item) & 0xFF for item in items).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return "".join(chr(int(item)) for item in items)
    if isinstance(value, int) and not isinstance(value, bool):
        return chr(int(value))
    return go_string(value, interp=interp)


def _to_rune(interp, args, line):
    return Rune(int(args[0]))


def _to_byte(interp, args, line):
    return int(args[0]) & 0xFF


def _to_bool(interp, args, line):
    return bool(args[0])


CONVERSIONS = {
    "int": _to_int, "int8": _to_int, "int16": _to_int, "int32": _to_rune,
    "int64": _to_int, "uint": _to_int, "uint16": _to_int, "uint32": _to_int,
    "uint64": _to_int, "uintptr": _to_int,
    "float64": _to_float, "float32": _to_float,
    "string": _to_string, "rune": _to_rune, "byte": _to_byte, "uint8": _to_byte,
    "bool": _to_bool,
}


# ----------------------------------------------------------- special forms

def _make(interp, arguments, env, line, want=1):
    declared = arguments[0][1] if arguments[0][0] == "type" else interp.types.get(
        arguments[0][1], arguments[0]
    )
    resolved = interp.resolve(declared)
    sizes = [int(interp.evaluate(item, env)) for item in arguments[1:]]

    if resolved[0] == "slice":
        length = sizes[0] if sizes else 0
        capacity = sizes[1] if len(sizes) > 1 else length
        element = resolved[1]
        backing = [interp.zero_value(element) for _ in range(capacity)]
        return Slice(backing, 0, length, capacity, interp.type_label(element))
    if resolved[0] == "map":
        from .go_values import TypedMap

        return TypedMap(value_type=resolved[2])
    if resolved[0] == "chan":
        return Chan(sizes[0] if sizes else 0, interp.type_label(resolved[1]))
    raise GoError(f"cannot make a {interp.type_label(resolved)}", line)


def _new(interp, arguments, env, line, want=1):
    declared = arguments[0][1] if arguments[0][0] == "type" else arguments[0]
    if declared[0] == "name":
        declared = ("named", declared[1])
    value = interp.zero_value(declared)
    return Pointer.to(value)


SPECIAL_FORMS = {
    "make": _make,
    "new": _new,
}


# ------------------------------------------------------------- the packages

def _fmt(interp):
    def println(args):
        interp.write(" ".join(go_string(v, interp=interp) for v in args) + "\n")
        return None

    def printf(args):
        interp.write(format_verbs(interp, args[0], args[1:]))
        return None

    def scan(args, split_line=False):
        """Reads whitespace-separated values into the pointers it was given."""
        filled = 0
        pending = list(args)
        while pending:
            line = interp.read_line()
            if line is None:
                break
            fields = line.split()
            if not fields and not split_line:
                continue
            for field in fields:
                if not pending:
                    break
                target = pending.pop(0)
                _store_scanned(target, field)
                filled += 1
            if split_line:
                break
        return filled if len(args) < 2 else [filled, NIL]

    def fprint(args, newline=False, formatted=False):
        writer = args[0]
        rest = args[1:]
        if formatted:
            text = format_verbs(interp, rest[0], rest[1:])
        elif newline:
            text = " ".join(go_string(v, interp=interp) for v in rest) + "\n"
        else:
            text = spaced(interp, rest)
        if isinstance(writer, Native) and writer.label == "os.Stderr":
            interp.write_error(text)
        else:
            interp.write(text)
        return None

    return Package("fmt", {
        "Println": Builtin("Println", println),
        "Print": Builtin("Print", lambda args: interp.write(spaced(interp, args))),
        "Printf": Builtin("Printf", printf),
        "Sprintf": Builtin("Sprintf", lambda args: format_verbs(interp, args[0], args[1:])),
        "Sprint": Builtin("Sprint", lambda args: spaced(interp, args)),
        "Sprintln": Builtin(
            "Sprintln",
            lambda args: " ".join(go_string(v, interp=interp) for v in args) + "\n",
        ),
        "Errorf": Builtin("Errorf", lambda args: _errorf(interp, args)),
        "Scan": Builtin("Scan", lambda args: scan(args)),
        "Scanln": Builtin("Scanln", lambda args: scan(args, split_line=True)),
        "Fprintln": Builtin("Fprintln", lambda args: fprint(args, newline=True)),
        "Fprint": Builtin("Fprint", lambda args: fprint(args)),
        "Fprintf": Builtin("Fprintf", lambda args: fprint(args, formatted=True)),
    })


def _errorf(interp, args):
    text = format_verbs(interp, args[0], args[1:])
    wrapped = None
    for value in args[1:]:
        if isinstance(value, ErrorValue):
            wrapped = value
    return ErrorValue(text, wrapped)


def _store_scanned(target, field) -> None:
    if not isinstance(target, Pointer):
        raise GoError("Scan needs pointers, like &name")
    current = target.get()
    if isinstance(current, bool):
        target.set(field == "true")
    elif isinstance(current, float):
        target.set(float(field))
    elif isinstance(current, int):
        target.set(int(field))
    else:
        target.set(field)


def _strings(interp):
    def split(args):
        text, separator = args[0], args[1]
        parts = list(text) if separator == "" else text.split(separator)
        return Slice.of(parts, "string")

    def builder(args=None):
        pieces = []
        native = Native("strings.Builder", {})
        native.members.update({
            "WriteString": Builtin("WriteString", lambda a: (pieces.append(a[0]), NIL)[1]),
            "WriteRune": Builtin("WriteRune", lambda a: (pieces.append(chr(int(a[0]))), NIL)[1]),
            "WriteByte": Builtin("WriteByte", lambda a: (pieces.append(chr(int(a[0]))), NIL)[1]),
            "String": Builtin("String", lambda a: "".join(pieces)),
            "Len": Builtin("Len", lambda a: len("".join(pieces))),
            "Reset": Builtin("Reset", lambda a: (pieces.clear(), None)[1]),
        })
        return native

    _strings.builder = builder

    return Package("strings", {
        "Contains": Builtin("Contains", lambda a: a[1] in a[0]),
        "ContainsRune": Builtin("ContainsRune", lambda a: chr(int(a[1])) in a[0]),
        "ContainsAny": Builtin("ContainsAny", lambda a: any(c in a[0] for c in a[1])),
        "HasPrefix": Builtin("HasPrefix", lambda a: a[0].startswith(a[1])),
        "HasSuffix": Builtin("HasSuffix", lambda a: a[0].endswith(a[1])),
        "Index": Builtin("Index", lambda a: a[0].find(a[1])),
        "IndexByte": Builtin("IndexByte", lambda a: a[0].find(chr(int(a[1])))),
        "LastIndex": Builtin("LastIndex", lambda a: a[0].rfind(a[1])),
        "Split": Builtin("Split", split),
        "SplitN": Builtin("SplitN", lambda a: Slice.of(
            a[0].split(a[1]) if int(a[2]) < 0 else a[0].split(a[1], int(a[2]) - 1), "string")),
        "Fields": Builtin("Fields", lambda a: Slice.of(a[0].split(), "string")),
        "Join": Builtin("Join", lambda a: a[1].join(go_string(v, interp=interp) for v in a[0])),
        "Replace": Builtin("Replace", lambda a: a[0].replace(
            a[1], a[2], int(a[3]) if int(a[3]) >= 0 else -1)),
        "ReplaceAll": Builtin("ReplaceAll", lambda a: a[0].replace(a[1], a[2])),
        "ToUpper": Builtin("ToUpper", lambda a: a[0].upper()),
        "ToLower": Builtin("ToLower", lambda a: a[0].lower()),
        "ToTitle": Builtin("ToTitle", lambda a: a[0].upper()),
        "Title": Builtin("Title", lambda a: a[0].title()),
        "TrimSpace": Builtin("TrimSpace", lambda a: a[0].strip()),
        "Trim": Builtin("Trim", lambda a: a[0].strip(a[1])),
        "TrimLeft": Builtin("TrimLeft", lambda a: a[0].lstrip(a[1])),
        "TrimRight": Builtin("TrimRight", lambda a: a[0].rstrip(a[1])),
        "TrimPrefix": Builtin("TrimPrefix", lambda a: a[0][len(a[1]):]
                              if a[0].startswith(a[1]) else a[0]),
        "TrimSuffix": Builtin("TrimSuffix", lambda a: a[0][:-len(a[1])]
                              if a[1] and a[0].endswith(a[1]) else a[0]),
        "Repeat": Builtin("Repeat", lambda a: a[0] * int(a[1])),
        "Count": Builtin("Count", lambda a: (len(a[0]) + 1) if a[1] == "" else a[0].count(a[1])),
        "EqualFold": Builtin("EqualFold", lambda a: a[0].lower() == a[1].lower()),
        "Builder": Builtin("Builder", lambda a: builder()),
        "NewReader": Builtin("NewReader", lambda a: _string_reader(a[0])),
    })


def _string_reader(text):
    state = {"position": 0}
    native = Native("strings.Reader", {})
    native.members["ReadString"] = Builtin("ReadString", lambda a: _read_until(state, text, a[0]))
    return native


def _read_until(state, text, delimiter):
    position = state["position"]
    if position >= len(text):
        return [", ".join([]), ErrorValue("EOF")]
    end = text.find(chr(int(delimiter)), position)
    if end < 0:
        end = len(text)
    state["position"] = end + 1
    return [text[position:end + 1], NIL]


def _strconv(interp):
    def atoi(args):
        try:
            return [int(args[0].strip()), NIL]
        except ValueError:
            return [0, ErrorValue(
                f'strconv.Atoi: parsing "{args[0]}": invalid syntax'
            )]

    def parse_float(args):
        try:
            return [float(args[0].strip()), NIL]
        except ValueError:
            return [0.0, ErrorValue(
                f'strconv.ParseFloat: parsing "{args[0]}": invalid syntax'
            )]

    def parse_int(args):
        try:
            return [int(args[0].strip(), int(args[1]) or 10), NIL]
        except ValueError:
            return [0, ErrorValue(
                f'strconv.ParseInt: parsing "{args[0]}": invalid syntax'
            )]

    def parse_bool(args):
        text = args[0].strip().lower()
        if text in ("1", "t", "true"):
            return [True, NIL]
        if text in ("0", "f", "false"):
            return [False, NIL]
        return [False, ErrorValue(f'strconv.ParseBool: parsing "{args[0]}": invalid syntax')]

    return Package("strconv", {
        "Itoa": Builtin("Itoa", lambda a: str(int(a[0]))),
        "Atoi": Builtin("Atoi", atoi),
        "ParseFloat": Builtin("ParseFloat", parse_float),
        "ParseInt": Builtin("ParseInt", parse_int),
        "ParseBool": Builtin("ParseBool", parse_bool),
        "FormatInt": Builtin("FormatInt", lambda a: _in_base(int(a[0]), int(a[1]))),
        "FormatFloat": Builtin("FormatFloat", lambda a: format_float(float(a[0]))),
        "FormatBool": Builtin("FormatBool", lambda a: "true" if a[0] else "false"),
        "Quote": Builtin("Quote", lambda a: _quote(a[0])),
    })


def _math(interp):
    return Package("math", {
        "Sqrt": Builtin("Sqrt", lambda a: pymath.sqrt(float(a[0]))),
        "Pow": Builtin("Pow", lambda a: float(a[0]) ** float(a[1])),
        "Abs": Builtin("Abs", lambda a: abs(float(a[0]))),
        "Floor": Builtin("Floor", lambda a: float(pymath.floor(float(a[0])))),
        "Ceil": Builtin("Ceil", lambda a: float(pymath.ceil(float(a[0])))),
        "Round": Builtin("Round", lambda a: float(pymath.floor(float(a[0]) + 0.5))
                         if a[0] >= 0 else float(pymath.ceil(float(a[0]) - 0.5))),
        "Trunc": Builtin("Trunc", lambda a: float(int(float(a[0])))),
        "Mod": Builtin("Mod", lambda a: pymath.fmod(float(a[0]), float(a[1]))),
        "Max": Builtin("Max", lambda a: max(float(a[0]), float(a[1]))),
        "Min": Builtin("Min", lambda a: min(float(a[0]), float(a[1]))),
        "Log": Builtin("Log", lambda a: pymath.log(float(a[0]))),
        "Log2": Builtin("Log2", lambda a: pymath.log2(float(a[0]))),
        "Log10": Builtin("Log10", lambda a: pymath.log10(float(a[0]))),
        "Exp": Builtin("Exp", lambda a: pymath.exp(float(a[0]))),
        "Sin": Builtin("Sin", lambda a: pymath.sin(float(a[0]))),
        "Cos": Builtin("Cos", lambda a: pymath.cos(float(a[0]))),
        "Tan": Builtin("Tan", lambda a: pymath.tan(float(a[0]))),
        "Atan2": Builtin("Atan2", lambda a: pymath.atan2(float(a[0]), float(a[1]))),
        "Hypot": Builtin("Hypot", lambda a: pymath.hypot(float(a[0]), float(a[1]))),
        "Inf": Builtin("Inf", lambda a: pymath.inf if int(a[0]) >= 0 else -pymath.inf),
        "NaN": Builtin("NaN", lambda a: pymath.nan),
        "IsNaN": Builtin("IsNaN", lambda a: a[0] != a[0]),
        "IsInf": Builtin("IsInf", lambda a: a[0] in (pymath.inf, -pymath.inf)),
        "Pi": pymath.pi,
        "E": pymath.e,
        "MaxInt": 2 ** 63 - 1,
        "MinInt": -(2 ** 63),
        "MaxInt64": 2 ** 63 - 1,
        "MinInt64": -(2 ** 63),
        "MaxInt32": 2 ** 31 - 1,
        "MinInt32": -(2 ** 31),
        "MaxFloat64": sys.float_info.max,
        "SmallestNonzeroFloat64": 5e-324,
    })


def _sort(interp):
    def sort_slice(args, stable=False):
        target, less = args[0], args[1]
        items = target.items()
        import functools

        def compare(left, right):
            # sort.Slice hands the callback indices, so the values have to sit
            # in the slice while it runs.
            for index, value in enumerate((left, right)):
                target.set(index, value)
            if interp.call(less, [0, 1], 0):
                return -1
            if interp.call(less, [1, 0], 0):
                return 1
            return 0

        # Sorting through the callback needs the real slice contents, so the
        # comparison works on a scratch copy and the result is written back.
        scratch = Slice.of(list(items), target.element)
        original = target.items()

        def compare_by_index(left, right):
            scratch.set(0, left)
            scratch.set(1, right)
            return compare(left, right)

        try:
            for index, value in enumerate(original):
                target.set(index, value)
            ordered = sorted(
                range(len(original)),
                key=functools.cmp_to_key(
                    lambda a, b: -1 if interp.call(less, [a, b], 0)
                    else (1 if interp.call(less, [b, a], 0) else 0)
                ),
            )
            reordered = [original[index] for index in ordered]
            for index, value in enumerate(reordered):
                target.set(index, value)
        finally:
            pass
        return None

    def sort_in_place(args, key=None):
        target = args[0]
        values = sorted(target.items(), key=key)
        for index, value in enumerate(values):
            target.set(index, value)
        return None

    return Package("sort", {
        "Ints": Builtin("Ints", sort_in_place),
        "Strings": Builtin("Strings", sort_in_place),
        "Float64s": Builtin("Float64s", sort_in_place),
        "Slice": Builtin("Slice", sort_slice),
        "SliceStable": Builtin("SliceStable", sort_slice),
        "SearchInts": Builtin("SearchInts", lambda a: _search(a[0], a[1])),
        "IntsAreSorted": Builtin("IntsAreSorted", lambda a: a[0].items() == sorted(a[0].items())),
    })


def _search(target, wanted):
    import bisect

    return bisect.bisect_left(target.items(), wanted)


def _os(interp):
    stdout = Native("os.Stdout", {
        "Write": Builtin("Write", lambda a: interp.write(_to_string(interp, a, 0))),
        "WriteString": Builtin("WriteString", lambda a: interp.write(a[0])),
    })
    stderr = Native("os.Stderr", {
        "Write": Builtin("Write", lambda a: interp.write_error(_to_string(interp, a, 0))),
        "WriteString": Builtin("WriteString", lambda a: interp.write_error(a[0])),
    })
    stdin = Native("os.Stdin", {})

    def exit_now(args):
        raise GoExit(int(args[0]) if args else 0)

    return Package("os", {
        "Args": Slice.of(list(interp.argv), "string"),
        "Exit": Builtin("Exit", exit_now),
        "Stdout": stdout,
        "Stderr": stderr,
        "Stdin": stdin,
        "Getenv": Builtin("Getenv", lambda a: __import__("os").environ.get(a[0], "")),
        "ReadFile": Builtin("ReadFile", lambda a: _read_file(a[0])),
        "WriteFile": Builtin("WriteFile", lambda a: _write_file(a[0], a[1])),
    })


def _read_file(path):
    try:
        with open(path, "rb") as handle:
            return [Slice.of(list(handle.read()), "byte"), NIL]
    except OSError as error:
        return [NIL, ErrorValue(str(error))]


def _write_file(path, data):
    try:
        with open(path, "wb") as handle:
            if isinstance(data, str):
                handle.write(data.encode("utf-8"))
            else:
                handle.write(bytes(int(item) & 0xFF for item in data))
        return NIL
    except OSError as error:
        return ErrorValue(str(error))


def _errors(interp):
    def is_error(args):
        target, wanted = args[0], args[1]
        while isinstance(target, ErrorValue):
            if target is wanted:
                return True
            target = target.wrapped
        return False

    return Package("errors", {
        "New": Builtin("New", lambda a: ErrorValue(a[0])),
        "Is": Builtin("Is", is_error),
        "Unwrap": Builtin("Unwrap", lambda a: a[0].wrapped or NIL
                          if isinstance(a[0], ErrorValue) else NIL),
    })


def _time(interp):
    def now(args):
        moment = pytime.time()
        native = Native("time.Time", {})
        native.members.update({
            "Unix": Builtin("Unix", lambda a: int(moment)),
            "UnixNano": Builtin("UnixNano", lambda a: int(moment * 1e9)),
            "Year": Builtin("Year", lambda a: pytime.localtime(moment).tm_year),
            "Format": Builtin("Format", lambda a: pytime.strftime(
                "%Y-%m-%d %H:%M:%S", pytime.localtime(moment))),
            "String": Builtin("String", lambda a: pytime.strftime(
                "%Y-%m-%d %H:%M:%S", pytime.localtime(moment))),
            "Sub": Builtin("Sub", lambda a: int((moment - a[0].member("__at").call([])) * 1e9)),
            "__at": Builtin("__at", lambda a: moment),
        })
        return native

    def since(args):
        return int((pytime.time() - args[0].member("__at").call([])) * 1e9)

    def sleep(args):
        pytime.sleep(max(0.0, float(args[0]) / 1e9))
        return None

    return Package("time", {
        "Now": Builtin("Now", now),
        "Since": Builtin("Since", since),
        "Sleep": Builtin("Sleep", sleep),
        "Nanosecond": 1,
        "Microsecond": 1000,
        "Millisecond": 1000 * 1000,
        "Second": 1000 * 1000 * 1000,
        "Minute": 60 * 1000 * 1000 * 1000,
        "Hour": 3600 * 1000 * 1000 * 1000,
    })


def _bufio(interp):
    def new_scanner(args):
        state = {"line": ""}
        native = Native("bufio.Scanner", {})

        def scan(_args):
            line = interp.read_line()
            if line is None:
                return False
            state["line"] = line
            return True

        native.members.update({
            "Scan": Builtin("Scan", scan),
            "Text": Builtin("Text", lambda a: state["line"]),
            "Err": Builtin("Err", lambda a: NIL),
            "Split": Builtin("Split", lambda a: None),
            "Buffer": Builtin("Buffer", lambda a: None),
        })
        return native

    def new_reader(args):
        native = Native("bufio.Reader", {})

        def read_string(_args):
            line = interp.read_line()
            if line is None:
                return ["", ErrorValue("EOF")]
            return [line + "\n", NIL]

        native.members["ReadString"] = Builtin("ReadString", read_string)
        return native

    return Package("bufio", {
        "NewScanner": Builtin("NewScanner", new_scanner),
        "NewReader": Builtin("NewReader", new_reader),
        "NewWriter": Builtin("NewWriter", lambda a: Native("bufio.Writer", {
            "WriteString": Builtin("WriteString", lambda b: interp.write(b[0])),
            "Flush": Builtin("Flush", lambda b: NIL),
        })),
        "ScanLines": Builtin("ScanLines", lambda a: None),
        "ScanWords": Builtin("ScanWords", lambda a: None),
    })


def _unicode(interp):
    return Package("unicode", {
        "IsLetter": Builtin("IsLetter", lambda a: chr(int(a[0])).isalpha()),
        "IsDigit": Builtin("IsDigit", lambda a: chr(int(a[0])).isdigit()),
        "IsNumber": Builtin("IsNumber", lambda a: chr(int(a[0])).isnumeric()),
        "IsSpace": Builtin("IsSpace", lambda a: chr(int(a[0])).isspace()),
        "IsUpper": Builtin("IsUpper", lambda a: chr(int(a[0])).isupper()),
        "IsLower": Builtin("IsLower", lambda a: chr(int(a[0])).islower()),
        "IsPunct": Builtin("IsPunct", lambda a: not chr(int(a[0])).isalnum()
                           and not chr(int(a[0])).isspace()),
        "ToUpper": Builtin("ToUpper", lambda a: Rune(ord(chr(int(a[0])).upper()))),
        "ToLower": Builtin("ToLower", lambda a: Rune(ord(chr(int(a[0])).lower()))),
    })


def _rand(interp):
    return Package("rand", {
        "Intn": Builtin("Intn", lambda a: random.randrange(int(a[0]))),
        "Int": Builtin("Int", lambda a: random.randrange(2 ** 62)),
        "Int63": Builtin("Int63", lambda a: random.randrange(2 ** 62)),
        "Float64": Builtin("Float64", lambda a: random.random()),
        "Seed": Builtin("Seed", lambda a: random.seed(int(a[0]))),
        "Shuffle": Builtin("Shuffle", lambda a: None),
        "Perm": Builtin("Perm", lambda a: Slice.of(
            random.sample(range(int(a[0])), int(a[0])), "int")),
    })


def _sync(interp):
    return Package("sync", {
        "WaitGroup": Builtin("WaitGroup", lambda a: _wait_group()),
        "Mutex": Builtin("Mutex", lambda a: _mutex()),
        "RWMutex": Builtin("RWMutex", lambda a: _mutex()),
        "Once": Builtin("Once", lambda a: _once(interp)),
    })


def _wait_group():
    state = {"count": 0}
    lock = threading.Condition()

    def add(args):
        with lock:
            state["count"] += int(args[0])
            lock.notify_all()
        return None

    def done(args):
        return add([-1])

    def wait(args):
        with lock:
            while state["count"] > 0:
                lock.wait(0.02)
        return None

    return Native("sync.WaitGroup", {
        "Add": Builtin("Add", add),
        "Done": Builtin("Done", done),
        "Wait": Builtin("Wait", wait),
    })


def _mutex():
    lock = threading.RLock()
    return Native("sync.Mutex", {
        "Lock": Builtin("Lock", lambda a: (lock.acquire(), None)[1]),
        "Unlock": Builtin("Unlock", lambda a: (_release(lock), None)[1]),
        "RLock": Builtin("RLock", lambda a: (lock.acquire(), None)[1]),
        "RUnlock": Builtin("RUnlock", lambda a: (_release(lock), None)[1]),
    })


def _release(lock) -> None:
    try:
        lock.release()
    except RuntimeError:
        pass


def _once(interp):
    state = {"done": False}

    def do(args):
        if not state["done"]:
            state["done"] = True
            interp.call(args[0], [], 0)
        return None

    return Native("sync.Once", {"Do": Builtin("Do", do)})


FACTORIES = {
    "fmt": _fmt,
    "strings": _strings,
    "strconv": _strconv,
    "math": _math,
    "math/rand": _rand,
    "sort": _sort,
    "os": _os,
    "errors": _errors,
    "time": _time,
    "bufio": _bufio,
    "unicode": _unicode,
    "sync": _sync,
}

# Types a package exposes that a `var` can declare without calling anything.
NATIVE_ZEROES = {
    "sync.WaitGroup": lambda interp: _wait_group(),
    "sync.Mutex": lambda interp: _mutex(),
    "sync.RWMutex": lambda interp: _mutex(),
    "sync.Once": lambda interp: _once(interp),
    "strings.Builder": lambda interp: _strings(interp).members["Builder"].call([]),
}


def package(path, interp):
    factory = FACTORIES.get(path)
    if factory is None:
        # An unknown import is not fatal on its own: the program may never use
        # it. Reaching for a member of one is what fails, and says so.
        return Package(path.rsplit("/", 1)[-1], {})
    return factory(interp)


def zero_native(name, interp):
    factory = NATIVE_ZEROES.get(name)
    return factory(interp) if factory is not None else None
