"""What compiled PyCmd programs run against: values, printing, errors, the
built-in functions, the methods on text/lists/maps, and the libraries.

Compiled code sees only what is in ``namespace()``: no Python built-ins, no
import, nothing reachable by name that is not listed here.
"""

from __future__ import annotations

import builtins as _b
import json as _json
import math as _math
import os as _os
import random as _random
import re as _re
import statistics as _stats
import sys as _sys
import time as _time

_T = _b.type
_isinst = _b.isinstance
_NUM = (int, float)


class Missing:
    __slots__ = ()

    def __repr__(self):
        return "<missing>"


MISSING = Missing()


# ---------------------------------------------------------------- errors

class PcError(Exception):
    """An error a PyCmd program can throw, catch and look at."""

    def __init__(self, message="", kind="Error", value=None, line=0):
        super().__init__(message)
        self.message = message if isinstance(message, str) else show(message)
        self.kind = kind
        self.value = value if value is not None else message
        self.line = line

    def __str__(self):
        return f"{self.kind}: {self.message}" if self.kind != "Error" else self.message


class PcExit(BaseException):
    def __init__(self, code=0):
        super().__init__(code)
        self.code = code


def Error(message="", kind="Error"):
    return PcError(message, kind)


_TYPE_WORDS = {
    "NoneType": "nil", "dict": "map", "function": "fn", "builtin_function_or_method": "fn",
    "method": "fn", "dict_keys": "list", "dict_values": "list", "dict_items": "list",
    "PcError": "Error", "Variant": "enum value",
}


def _words(text: str) -> str:
    for py, ours in _TYPE_WORDS.items():
        text = text.replace(f"'{py}'", ours).replace(f'"{py}"', ours)
    text = _re.sub(r"'(int|str|float|bool|list|map|tuple|set|range|nil|fn)' object", r"\1", text)
    text = _re.sub(r"_pc_\w+", "value", text)
    return text.replace("NoneType", "nil")


def translate(exc: BaseException):
    """(kind, message) for any error, in PyCmd's words."""
    if isinstance(exc, PcError):
        return exc.kind, exc.message
    text = str(exc)
    if isinstance(exc, ZeroDivisionError):
        return "DivideByZero", "division by zero"
    if isinstance(exc, IndexError):
        return "Index", "that index is past the end" + (" of the list" if "list" in text else
                                                        " of the text" if "string" in text else "")
    if isinstance(exc, KeyError):
        key = exc.args[0] if exc.args else "?"
        return "Key", f"the map has no key {quote(key)} - use m.get(key, default) to be safe"
    if isinstance(exc, RecursionError):
        return "Recursion", "too much recursion - a function kept calling itself"
    if isinstance(exc, UnboundLocalError) or isinstance(exc, NameError):
        m = _re.search(r"'(\w+)'", text)
        name = m.group(1).rstrip("_") if m else "a name"
        return "Name", f"{name} is used before it has a value"
    if isinstance(exc, AttributeError):
        m = _re.match(r"'(\w+)' object has no attribute '(\w+)'", text)
        if m:
            owner = _TYPE_WORDS.get(m.group(1), m.group(1))
            return "Field", f"{owner} has no field or method '{m.group(2).rstrip('_')}'"
        m = _re.match(r"type object '(\w+)' has no attribute '(\w+)'", text)
        if m:
            return "Field", f"{m.group(1)} has no field or method '{m.group(2)}'"
        return "Field", _words(text)
    if isinstance(exc, TypeError):
        m = _re.match(r"can only concatenate str \(not \"(\w+)\"\) to str", text)
        if m:
            what = _TYPE_WORDS.get(m.group(1), m.group(1))
            return "Type", (f"cannot add text and {what} with + - put the value in the text "
                            f'instead: "total: {{n}}", or use str(n)')
        m = _re.match(r"unsupported operand type\(s\) for (\S+): '(\w+)' and '(\w+)'", text)
        if m:
            a = _TYPE_WORDS.get(m.group(2), m.group(2))
            b = _TYPE_WORDS.get(m.group(3), m.group(3))
            return "Type", f"cannot use {m.group(1)} on {a} and {b}"
        m = _re.match(r"'(<|>|<=|>=)' not supported between instances of '(\w+)' and '(\w+)'", text)
        if m:
            a = _TYPE_WORDS.get(m.group(2), m.group(2))
            b = _TYPE_WORDS.get(m.group(3), m.group(3))
            return "Type", f"cannot compare {a} and {b} with {m.group(1)}"
        if "object is not callable" in text:
            m = _re.match(r"'(\w+)' object is not callable", text)
            what = _TYPE_WORDS.get(m.group(1), m.group(1)) if m else "that value"
            return "Type", f"{what} is not a function, so it cannot be called with ()"
        if "cannot be interpreted as an integer" in text:
            return "Type", "this needs a whole number (an int), not " + \
                   _words(text.split(" object")[0].strip("'"))
        if "object is not subscriptable" in text:
            return "Type", _words(text).replace("is not subscriptable", "cannot be indexed with []")
        if "object is not iterable" in text:
            return "Type", _words(text).replace("is not iterable", "cannot be looped over")
        text = _re.sub(r"(\w+)\(\) (takes|missing|got)", lambda mm: f"{mm.group(1).rstrip('_')} {mm.group(2)}",
                       text)
        return "Type", _words(text).replace("positional argument", "argument")
    if isinstance(exc, ValueError):
        m = _re.match(r"invalid literal for int\(\) with base \d+: (.*)", text)
        if m:
            return "Value", f"cannot turn {m.group(1)} into an int"
        m = _re.match(r"could not convert string to float: (.*)", text)
        if m:
            return "Value", f"cannot turn {m.group(1)} into a float"
        if "not enough values to unpack" in text or "too many values to unpack" in text:
            return "Value", text.split(" (")[0].replace("values", "items")
        if "math domain error" in text:
            return "Value", "that number is outside what this maths function accepts"
        return "Value", _words(text)
    if isinstance(exc, OverflowError):
        return "Overflow", "a number got too big for a float"
    if isinstance(exc, MemoryError):
        return "Memory", "the program ran out of memory"
    if isinstance(exc, OSError):
        return "File", _words(exc.strerror or text)
    return _T(exc).__name__, _words(text)


def catch(exc):
    if isinstance(exc, PcError):
        return exc
    kind, message = translate(exc)
    return PcError(message, kind, None)


def throw(value):
    if isinstance(value, PcError):
        return value
    if isinstance(value, Struct):
        return PcError(show(value), value._pc_name, value)
    return PcError(value if isinstance(value, str) else show(value), "Error", value)


def assert_failed(line, text, message=None):
    if message is not None:
        return PcError(message if isinstance(message, str) else show(message), "Assert")
    return PcError(f"assert failed: {text}", "Assert")


def type_error(what, expected, value):
    got = "nil" if value is None else f"{type_of(value)} {quote(value)}"
    return PcError(f"{what} should be {expected}, but got {got}", "Type")


def missing_field(struct, field):
    return PcError(f"{struct} needs a value for {field}: {struct}({field}: ...)", "Type")


# ---------------------------------------------------------------- values

class Struct:
    __slots__ = ()
    _pc_name = "struct"
    _pc_fields = ()
    _pc_shown = ()

    def __repr__(self):
        return show(self)

    __str__ = __repr__

    def __eq__(self, other):
        if _T(self) is not _T(other):
            return NotImplemented
        return all(getattr(self, f) == getattr(other, f) for f in self._pc_fields)

    def __hash__(self):
        return id(self)


class Variant:
    __slots__ = ("enum", "name", "index", "value")

    def __init__(self, enum, name, index, value):
        self.enum = enum
        self.name = name
        self.index = index
        self.value = value if value is not None else index

    def __repr__(self):
        return f"{self.enum._pc_name}.{self.name}"

    __str__ = __repr__

    def __lt__(self, other):
        if isinstance(other, Variant) and other.enum is self.enum:
            return self.index < other.index
        return NotImplemented


class Enum:
    def __init__(self, name, variants):
        self._pc_name = name
        self._pc_variants = []
        for index, (vname, value) in enumerate(variants):
            v = Variant(self, vname, index, value)
            self._pc_variants.append(v)
            object.__setattr__(self, vname, v)

    def all(self):
        return list(self._pc_variants)

    def count(self):
        return len(self._pc_variants)

    def from_value(self, value):
        for v in self._pc_variants:
            if v.value == value:
                return v
        return None

    def from_name(self, name):
        for v in self._pc_variants:
            if v.name == name:
                return v
        return None

    def __repr__(self):
        return f"enum {self._pc_name}"


def make_enum(name, variants):
    return Enum(name, variants)


class Module:
    def __init__(self, name, members):
        self._pc_name = name
        for key, value in members.items():
            object.__setattr__(self, key, value)

    def __repr__(self):
        return f"library {self._pc_name}"

    def names(self):
        return sorted(k for k in vars(self) if not k.startswith("_"))


# ---------------------------------------------------------------- printing

def quote(value) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") \
            .replace("\t", "\\t") + '"'
    return show(value)


def show(value, _seen=None) -> str:
    t = _T(value)
    if t is str:
        return value
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if t is int:
        return str(value)
    if t is float:
        if value != value:
            return "nan"
        if value in (float("inf"), float("-inf")):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if t in (list, tuple, dict, set) or isinstance(value, Struct):
        _seen = _seen or set()
        if id(value) in _seen:
            return "[...]"
        _seen = _seen | {id(value)}
        if t is list:
            return "[" + ", ".join(_inner(v, _seen) for v in value) + "]"
        if t is tuple:
            return "(" + ", ".join(_inner(v, _seen) for v in value) + ("," if len(value) == 1 else "") + ")"
        if t is dict:
            return "{" + ", ".join(f"{_inner(k, _seen)}: {_inner(v, _seen)}" for k, v in value.items()) + "}"
        if t is set:
            return "set[" + ", ".join(_inner(v, _seen) for v in _sorted_any(value)) + "]"
        fields = ", ".join(f"{shown}: {_inner(getattr(value, f), _seen)}"
                           for f, shown in zip(value._pc_fields, value._pc_shown))
        return f"{value._pc_name}({fields})"
    if t is range:
        if value.step == 1:
            return f"{value.start}..{value.stop}"
        return f"range({value.start}, {value.stop}, {value.step})"
    if isinstance(value, PcError):
        return f"{value.kind}: {value.message}" if value.kind != "Error" else f"Error: {value.message}"
    if callable(value) and not isinstance(value, (Enum, Module)) and not isinstance(value, _b.type):
        name = getattr(value, "__name__", "fn")
        if name == "<lambda>" or name.startswith("_pc_"):
            return "fn"
        return f"fn {name.strip('_')}"
    if isinstance(value, _b.type) and issubclass(value, Struct):
        return f"struct {value._pc_name}"
    if t in (_b.dict.__class__,):
        return str(value)
    return str(value)


def _inner(value, seen):
    if _T(value) is str:
        return quote(value)
    return show(value, seen)


def _sorted_any(values):
    try:
        return sorted(values)
    except TypeError:
        return list(values)


def type_of(value) -> str:
    t = _T(value)
    if value is None:
        return "nil"
    names = {bool: "bool", int: "int", float: "float", str: "str", list: "list", dict: "map",
             tuple: "tuple", set: "set", range: "range"}
    if t in names:
        return names[t]
    if isinstance(value, Struct):
        return value._pc_name
    if isinstance(value, Variant):
        return value.enum._pc_name
    if isinstance(value, PcError):
        return "Error"
    if isinstance(value, Enum):
        return "enum"
    if isinstance(value, Module):
        return "library"
    if isinstance(value, _b.type):
        return "struct"
    if callable(value):
        return "fn"
    return t.__name__


# ---------------------------------------------------------------- built-ins

class Console:
    def __init__(self, stdout=None, stdin=None):
        self.stdout = stdout if stdout is not None else _sys.stdout
        self.stdin = stdin if stdin is not None else _sys.stdin

    def print(self, *values, sep=" ", end="\n"):
        self.stdout.write(sep.join(show(v) for v in values) + end)

    def input(self, prompt=""):
        if prompt:
            self.stdout.write(show(prompt))
            flush = getattr(self.stdout, "flush", None)
            if flush:
                flush()
        line = self.stdin.readline() if self.stdin is not None else ""
        if line == "":
            return None
        return line.rstrip("\n").rstrip("\r")


def _int(value=0, base=10):
    if _T(value) is str:
        text = value.strip().replace("_", "")
        try:
            return int(text, base)
        except ValueError:
            try:
                f = float(text)
            except ValueError:
                raise PcError(f"cannot turn {quote(value)} into an int", "Value") from None
            return int(f)
    if _T(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise PcError(f"cannot turn {show(value)} into an int", "Value")
        return int(value)
    if isinstance(value, Variant):
        return value.index
    if value is None:
        raise PcError("cannot turn nil into an int", "Value")
    return int(value)


def _float(value=0.0):
    if _T(value) is str:
        try:
            return float(value.strip().replace("_", ""))
        except ValueError:
            raise PcError(f"cannot turn {quote(value)} into a float", "Value") from None
    if value is None:
        raise PcError("cannot turn nil into a float", "Value")
    return float(value)


def _bool(value=False):
    return bool(value)


def _len(value):
    if _T(value) in (list, str, dict, tuple, set, range):
        return len(value)
    if isinstance(value, Struct) and hasattr(value, "len"):
        return value.len()
    if value is None:
        raise PcError("nil has no length", "Type")
    raise PcError(f"{type_of(value)} has no length", "Type")


def _list(value=None):
    if value is None:
        return []
    if _T(value) is dict:
        return list(value.items())
    return list(value)


def _set(value=None):
    return set() if value is None else set(value)


def _range(a, b=None, step=1):
    if b is None:
        a, b = 0, a
    return range(a, b, step)


def _sorted(values, key=None, reverse=False):
    return sorted(values, key=key, reverse=reverse)


def _reversed(values):
    if _T(values) is str:
        return values[::-1]
    return list(values)[::-1]


def _enumerate(values, start=0):
    return list(enumerate(values, start))


def _zip(*lists):
    return list(zip(*lists))


def _keys(m):
    return list(m.keys())


def _values(m):
    return list(m.values())


def _items(m):
    return list(m.items())


def _map(values, fn):
    return [fn(v) for v in values]


def _filter(values, fn):
    return [v for v in values if fn(v)]


def _reduce(values, init, fn=MISSING):
    if fn is MISSING:
        fn, it = init, iter(values)
        try:
            acc = next(it)
        except StopIteration:
            raise PcError("reduce of an empty list needs a starting value", "Value") from None
    else:
        acc, it = init, iter(values)
    for v in it:
        acc = fn(acc, v)
    return acc


def _any(values, fn=None):
    return any(fn(v) for v in values) if fn else any(values)


def _all(values, fn=None):
    return all(fn(v) for v in values) if fn else all(values)


def _round(x, digits=None):
    return round(x) if digits is None else round(x, digits)


def _min(*args, by=None):
    values = args[0] if len(args) == 1 and _T(args[0]) in (list, tuple, set, range) else args
    if not values:
        raise PcError("min of nothing", "Value")
    return min(values, key=by) if by else min(values)


def _max(*args, by=None):
    values = args[0] if len(args) == 1 and _T(args[0]) in (list, tuple, set, range) else args
    if not values:
        raise PcError("max of nothing", "Value")
    return max(values, key=by) if by else max(values)


def _sum(values, start=0):
    return sum(values, start)


def _copy(value):
    import copy

    return copy.deepcopy(value)


def _exit(code=0):
    raise PcExit(code)


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _repr(value):
    return quote(value)


def _is_nil(value):
    return value is None


def _char(code):
    return chr(code)


# ---------------------------------------------------------------- methods

def _s_split(s, sep=None, limit=-1):
    if sep == "":
        return list(s)
    return s.split(sep, limit)


def _s_join(sep, values):
    return sep.join(show(v) for v in values)


def _s_format(s, *args, **kwargs):
    out = []
    i = 0
    auto = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "{":
            if s.startswith("{{", i):
                out.append("{")
                i += 2
                continue
            j = s.find("}", i)
            if j < 0:
                raise PcError("format: a { is not closed", "Value")
            key = s[i + 1:j].strip()
            if key == "":
                if auto >= len(args):
                    raise PcError("format: more {} than values", "Value")
                out.append(show(args[auto]))
                auto += 1
            elif key.isdigit():
                out.append(show(args[int(key)]))
            elif key in kwargs:
                out.append(show(kwargs[key]))
            else:
                raise PcError(f"format: no value named {key}", "Value")
            i = j + 1
            continue
        if c == "}" and s.startswith("}}", i):
            out.append("}")
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _index_of(seq, x):
    try:
        return seq.index(x)
    except ValueError:
        return -1


def _l_push(xs, *values):
    if _T(xs) is not list:
        raise PcError(f"cannot push onto {type_of(xs)} - only a list grows", "Type")
    xs.extend(values)


def _l_join(xs, sep=", "):
    return sep.join(show(v) for v in xs)


def _l_count(xs, what=MISSING):
    if what is MISSING:
        return len(xs)
    if callable(what) and not isinstance(what, (str, int, float)):
        return sum(1 for v in xs if what(v))
    return list(xs).count(what)


def _l_find(xs, fn):
    for v in xs:
        if fn(v):
            return v
    return None


def _l_find_index(xs, fn):
    for i, v in enumerate(xs):
        if fn(v):
            return i
    return -1


def _l_each(xs, fn):
    for v in xs:
        fn(v)


def _l_sort(xs, key=None, reverse=False, by=None):
    xs.sort(key=key or by, reverse=reverse)
    return xs


def _l_first(xs, default=None):
    return xs[0] if len(xs) else default


def _l_last(xs, default=None):
    return xs[-1] if len(xs) else default


def _l_get(xs, i, default=None):
    try:
        return xs[i]
    except (IndexError, KeyError, TypeError):
        return default


def _l_unique(xs):
    seen = []
    out = []
    for v in xs:
        try:
            if v in seen:
                continue
        except TypeError:
            pass
        seen.append(v)
        out.append(v)
    return out


def _l_flatten(xs):
    out = []
    for v in xs:
        if _T(v) in (list, tuple):
            out.extend(v)
        else:
            out.append(v)
    return out


def _l_chunk(xs, n):
    if n <= 0:
        raise PcError("chunk size must be at least 1", "Value")
    xs = list(xs)
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def _l_group_by(xs, fn):
    out = {}
    for v in xs:
        out.setdefault(fn(v), []).append(v)
    return out


def _l_partition(xs, fn):
    yes, no = [], []
    for v in xs:
        (yes if fn(v) else no).append(v)
    return (yes, no)


def _l_average(xs):
    xs = list(xs)
    if not xs:
        raise PcError("average of an empty list", "Value")
    return sum(xs) / len(xs)


def _l_remove_at(xs, i):
    return xs.pop(i)


def _l_insert(xs, i, value):
    xs.insert(i, value)


def _l_slice(xs, a=None, b=None):
    return xs[a:b]


def _l_contains(xs, x):
    return x in xs


def _l_is_empty(xs):
    return len(xs) == 0


def _l_take(xs, n):
    return list(xs)[:n]


def _l_skip(xs, n):
    return list(xs)[n:]


def _l_sum(xs):
    return sum(xs)


def _l_sum_by(xs, fn):
    return sum(fn(v) for v in xs)


def _l_min(xs, by=None):
    return _min(list(xs), by=by)


def _l_max(xs, by=None):
    return _max(list(xs), by=by)


def _l_sorted(xs, key=None, reverse=False, by=None):
    return sorted(xs, key=key or by, reverse=reverse)


def _m_has(m, k):
    return k in m


def _m_set(m, k, v):
    m[k] = v


def _m_remove(m, k):
    return m.pop(k, None)


def _m_merge(m, other):
    out = dict(m)
    out.update(other)
    return out


def _m_each(m, fn):
    for k, v in list(m.items()):
        fn(k, v)


def _m_filter(m, fn):
    return {k: v for k, v in m.items() if fn(k, v)}


def _m_map(m, fn):
    return {k: fn(k, v) for k, v in m.items()}


def _s_pad_left(s, n, ch=" "):
    return s.rjust(n, ch)


def _s_pad_right(s, n, ch=" "):
    return s.ljust(n, ch)


def _s_lines(s):
    return s.splitlines()


def _s_words(s):
    return s.split()


def _s_to_int(s):
    return _int(s)


def _s_to_float(s):
    return _float(s)


def _s_repeat(s, n):
    return s * n


def _s_char_at(s, i):
    return s[i] if -len(s) <= i < len(s) else None


SEQ = (list, tuple, range)

#: method name -> {python type: implementation}. Anything else falls through
#: to the value's own method (a struct's, a library's).
EXT = {
    "len": {t: len for t in (list, tuple, range, str, dict, set)},
    "push": {list: _l_push, tuple: _l_push},
    "join": {list: _l_join, tuple: _l_join, range: _l_join, set: _l_join, str: _s_join},
    "format": {str: _s_format},
    "format_map": {str: lambda s, m: _s_format(s, **m)},
    "split": {str: _s_split},
    "trim": {str: lambda s, chars=None: s.strip(chars)},
    "trim_start": {str: lambda s, chars=None: s.lstrip(chars)},
    "trim_end": {str: lambda s, chars=None: s.rstrip(chars)},
    "chars": {str: list},
    "lines": {str: _s_lines},
    "words": {str: _s_words},
    "contains": {str: lambda s, x: x in s, list: _l_contains, tuple: _l_contains,
                 range: _l_contains, dict: _m_has, set: _l_contains},
    "has": {dict: _m_has, set: _l_contains, list: _l_contains},
    "starts_with": {str: lambda s, p: s.startswith(p)},
    "ends_with": {str: lambda s, p: s.endswith(p)},
    "index_of": {str: lambda s, x: s.find(x), list: _index_of, tuple: _index_of, range: _index_of},
    "last_index_of": {str: lambda s, x: s.rfind(x)},
    "repeat": {str: _s_repeat, list: lambda xs, n: xs * n},
    "reverse": {str: lambda s: s[::-1], list: lambda xs: xs.reverse()},
    "reversed": {str: lambda s: s[::-1], list: _reversed, tuple: _reversed, range: _reversed},
    "to_int": {str: _s_to_int, float: int, int: int},
    "to_float": {str: _s_to_float, int: float, float: float},
    "to_str": {t: show for t in (int, float, str, bool, list, dict, tuple, set, range)},
    "to_list": {str: list, tuple: list, range: list, set: list, dict: _items, list: list},
    "to_set": {list: set, tuple: set, range: set, str: set},
    "is_digit": {str: lambda s: s.isdigit()},
    "is_alpha": {str: lambda s: s.isalpha()},
    "is_space": {str: lambda s: s.isspace()},
    "is_upper": {str: lambda s: s.isupper()},
    "is_lower": {str: lambda s: s.islower()},
    "pad_left": {str: _s_pad_left},
    "pad_right": {str: _s_pad_right},
    "char_at": {str: _s_char_at},
    "is_empty": {t: _l_is_empty for t in (list, tuple, range, str, dict, set)},
    "map": {list: _map, tuple: _map, range: _map, set: _map, str: _map, dict: _m_map},
    "filter": {list: _filter, tuple: _filter, range: _filter, set: _filter, str: _filter,
               dict: _m_filter},
    "reduce": {list: _reduce, tuple: _reduce, range: _reduce, set: _reduce},
    "each": {list: _l_each, tuple: _l_each, range: _l_each, set: _l_each, str: _l_each,
             dict: _m_each},
    "find": {list: _l_find, tuple: _l_find, range: _l_find, str: lambda s, x: s.find(x)},
    "find_index": {list: _l_find_index, tuple: _l_find_index},
    "any": {t: _any for t in (list, tuple, range, set)},
    "all": {t: _all for t in (list, tuple, range, set)},
    "count": {list: _l_count, tuple: _l_count, range: _l_count, str: lambda s, x=MISSING:
              len(s) if x is MISSING else s.count(x)},
    "sum": {t: _l_sum for t in (list, tuple, range, set)},
    "sum_by": {t: _l_sum_by for t in (list, tuple, range)},
    "min": {t: _l_min for t in (list, tuple, range, set)},
    "max": {t: _l_max for t in (list, tuple, range, set)},
    "average": {t: _l_average for t in (list, tuple, range)},
    "sorted": {list: _l_sorted, tuple: _l_sorted, range: _l_sorted, set: _l_sorted, str: _l_sorted},
    "sort": {list: _l_sort},
    "sort_by": {list: lambda xs, fn: _l_sort(xs, key=fn)},
    "first": {t: _l_first for t in (list, tuple, range, str)},
    "last": {t: _l_last for t in (list, tuple, range, str)},
    "take": {t: _l_take for t in (list, tuple, range)},
    "skip": {t: _l_skip for t in (list, tuple, range)},
    "unique": {t: _l_unique for t in (list, tuple)},
    "flatten": {list: _l_flatten, tuple: _l_flatten},
    "zip": {list: lambda a, b: list(zip(a, b)), tuple: lambda a, b: list(zip(a, b))},
    "enumerate": {list: _enumerate, tuple: _enumerate, str: _enumerate, range: _enumerate},
    "chunk": {t: _l_chunk for t in (list, tuple, range)},
    "group_by": {t: _l_group_by for t in (list, tuple, range)},
    "partition": {t: _l_partition for t in (list, tuple, range)},
    "remove_at": {list: _l_remove_at},
    "insert": {list: _l_insert},
    "slice": {t: _l_slice for t in (list, tuple, str)},
    "get": {list: _l_get, tuple: _l_get, str: _l_get},
    "set": {dict: _m_set},
    "remove": {dict: _m_remove},
    "merge": {dict: _m_merge},
    "keys": {dict: _keys},
    "values": {dict: _values},
    "items": {dict: _items},
}


def _dispatcher(name, table):
    get = table.get

    def call(obj, *args, **kwargs):
        impl = get(_T(obj))
        if impl is not None:
            return impl(obj, *args, **kwargs)
        if obj is None:
            raise PcError(f"nil has no method {name}() - the value is missing", "Type")
        return getattr(obj, name)(*args, **kwargs)

    call.__name__ = name
    return call


DISPATCH = {name: _dispatcher(name, table) for name, table in EXT.items()}


def bind(obj, name):
    impl = EXT.get(name, {}).get(_T(obj))
    if impl is not None:
        def bound(*args, **kwargs):
            return impl(obj, *args, **kwargs)

        bound.__name__ = name
        return bound
    return getattr(obj, name)


def opt_attr(obj, name):
    if obj is None:
        return None
    if name in EXT:
        return bind(obj, name)
    return getattr(obj, name)


def opt_call(obj, name, *args, **kwargs):
    if obj is None:
        return None
    return bind(obj, name)(*args, **kwargs)


def pairs(value):
    if _T(value) is dict:
        return value.items()
    return value


def in_range(value, lo, hi, inclusive):
    try:
        return lo <= value <= hi if inclusive else lo <= value < hi
    except TypeError:
        return False


def fmt(value, spec):
    try:
        return format(value, spec)
    except (ValueError, TypeError):
        raise PcError(f"cannot format {type_of(value)} with :{spec}", "Value") from None


def no_match(value):
    return None


# ---------------------------------------------------------------- libraries

def _lib_math():
    m = _math
    return {
        "pi": m.pi, "e": m.e, "tau": m.tau, "inf": m.inf, "nan": m.nan,
        "sqrt": m.sqrt, "cbrt": lambda x: m.copysign(abs(x) ** (1 / 3), x), "pow": pow,
        "abs": abs, "floor": m.floor, "ceil": m.ceil, "round": _round, "trunc": m.trunc,
        "sin": m.sin, "cos": m.cos, "tan": m.tan, "asin": m.asin, "acos": m.acos,
        "atan": m.atan, "atan2": m.atan2, "hypot": m.hypot, "degrees": m.degrees,
        "radians": m.radians, "log": m.log, "log2": m.log2, "log10": m.log10, "exp": m.exp,
        "gcd": m.gcd, "lcm": m.lcm, "factorial": m.factorial, "comb": m.comb, "perm": m.perm,
        "is_prime": lambda n: n > 1 and all(n % d for d in range(2, int(m.isqrt(n)) + 1)),
        "isqrt": m.isqrt, "min": _min, "max": _max, "clamp": _clamp, "sign":
            lambda x: (x > 0) - (x < 0), "is_nan": m.isnan, "is_inf": m.isinf,
        "lerp": lambda a, b, t: a + (b - a) * t, "sum": _sum,
    }


def _lib_random():
    r = _random.Random()
    return {
        "int": lambda a, b: r.randint(a, b), "float": lambda a=0.0, b=1.0: r.uniform(a, b),
        "choice": lambda xs: r.choice(list(xs)), "shuffle": lambda xs: r.shuffle(xs),
        "shuffled": lambda xs: r.sample(list(xs), len(xs)),
        "sample": lambda xs, k: r.sample(list(xs), k), "seed": r.seed,
        "chance": lambda p: r.random() < p, "random": r.random,
        "bool": lambda: r.random() < 0.5,
    }


def _lib_time():
    def sleep(seconds):
        _time.sleep(max(0.0, min(float(seconds), 600.0)))

    return {
        "now": _time.time, "ms": lambda: int(_time.time() * 1000),
        "clock": _time.perf_counter, "sleep": sleep,
        "date": lambda: _time.strftime("%Y-%m-%d"),
        "time": lambda: _time.strftime("%H:%M:%S"),
        "stamp": lambda pattern="%Y-%m-%d %H:%M:%S", at=None:
            _time.strftime(pattern, _time.localtime(at) if at is not None else _time.localtime()),
        "year": lambda: _time.localtime().tm_year, "month": lambda: _time.localtime().tm_mon,
        "day": lambda: _time.localtime().tm_mday, "hour": lambda: _time.localtime().tm_hour,
        "minute": lambda: _time.localtime().tm_min, "weekday":
            lambda: _time.strftime("%A"),
    }


def _plain(value):
    """PyCmd value -> something json can write."""
    if isinstance(value, Struct):
        return {f: _plain(getattr(value, f)) for f in value._pc_fields}
    if isinstance(value, Variant):
        return value.name
    if _T(value) in (list, tuple, set):
        return [_plain(v) for v in value]
    if _T(value) is dict:
        return {show(k) if not isinstance(k, str) else k: _plain(v) for k, v in value.items()}
    return value


def _lib_json():
    def parse(text):
        try:
            return _json.loads(text)
        except ValueError as exc:
            raise PcError(f"not valid JSON: {exc}", "Value") from None

    def stringify(value, indent=None):
        return _json.dumps(_plain(value), indent=indent, ensure_ascii=False)

    return {"parse": parse, "stringify": stringify, "pretty": lambda v: stringify(v, 2)}


def _lib_fs(root):
    root = _os.path.realpath(root)

    def inside(path):
        full = _os.path.realpath(_os.path.join(root, path))
        if full != root and not full.startswith(root + _os.sep):
            raise PcError(f"{path} is outside this program's folder - fs only reaches files "
                          "next to the program", "File")
        return full

    def read(path):
        with open(inside(path), "r", encoding="utf-8") as handle:
            return handle.read()

    def write(path, text):
        full = inside(path)
        parent = _os.path.dirname(full)
        if parent:
            _os.makedirs(parent, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(show(text))

    def append(path, text):
        with open(inside(path), "a", encoding="utf-8") as handle:
            handle.write(show(text))

    def lines(path):
        return read(path).splitlines()

    def ls(path="."):
        return sorted(_os.listdir(inside(path)))

    def remove(path):
        full = inside(path)
        if _os.path.isdir(full):
            _os.rmdir(full)
        else:
            _os.remove(full)

    return {
        "read": read, "write": write, "append": append, "lines": lines, "list": ls,
        "exists": lambda p: _os.path.exists(inside(p)),
        "is_dir": lambda p: _os.path.isdir(inside(p)),
        "mkdir": lambda p: _os.makedirs(inside(p), exist_ok=True),
        "remove": remove, "size": lambda p: _os.path.getsize(inside(p)),
        "folder": lambda: root,
    }


def _lib_regex():
    def safe(fn):
        def run(pattern, *args):
            try:
                return fn(pattern, *args)
            except _re.error as exc:
                raise PcError(f"bad pattern {quote(pattern)}: {exc}", "Value") from None
        return run

    return {
        "test": safe(lambda p, s: _re.search(p, s) is not None),
        "find": safe(lambda p, s: (lambda m: m.group(0) if m else None)(_re.search(p, s))),
        "find_all": safe(lambda p, s: [m.group(0) for m in _re.finditer(p, s)]),
        "groups": safe(lambda p, s: (lambda m: list(m.groups()) if m else None)(_re.search(p, s))),
        "replace": safe(lambda p, s, r: _re.sub(p, r, s)),
        "split": safe(lambda p, s: _re.split(p, s)),
        "escape": _re.escape,
    }


def _lib_stats():
    def need(xs):
        xs = list(xs)
        if not xs:
            raise PcError("statistics of an empty list", "Value")
        return xs

    return {
        "mean": lambda xs: _stats.fmean(need(xs)), "median": lambda xs: _stats.median(need(xs)),
        "mode": lambda xs: _stats.mode(need(xs)),
        "stdev": lambda xs: _stats.stdev(need(xs)) if len(list(xs)) > 1 else 0.0,
        "variance": lambda xs: _stats.variance(need(xs)) if len(list(xs)) > 1 else 0.0,
        "sum": _sum, "min": _l_min, "max": _l_max,
        "range": lambda xs: max(need(xs)) - min(need(xs)),
    }


def _lib_text():
    return {
        "upper": str.upper, "lower": str.lower, "title": str.title, "trim": str.strip,
        "split": _s_split, "join": lambda xs, sep="": _s_join(sep, xs),
        "replace": str.replace, "repeat": _s_repeat, "reverse": lambda s: s[::-1],
        "pad_left": _s_pad_left, "pad_right": _s_pad_right, "center": lambda s, n, c=" ": s.center(n, c),
        "contains": lambda s, x: x in s, "count": lambda s, x: s.count(x),
        "is_digit": str.isdigit, "is_alpha": str.isalpha, "chars": list, "lines": _s_lines,
        "words": _s_words, "letters": "abcdefghijklmnopqrstuvwxyz", "digits": "0123456789",
        "is_palindrome": lambda s: (lambda t: t == t[::-1])("".join(c.lower() for c in s if c.isalnum())),
        "caesar": lambda s, n: "".join(
            chr((ord(c) - base + n) % 26 + base) if c.isalpha() and c.isascii() else c
            for c in s for base in [ord("a") if c.islower() else ord("A")]),
        "slug": lambda s: _re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-"),
        "wrap": lambda s, width=60: __import__("textwrap").fill(s, width),
    }


def _lib_http():
    def request(url, data=None, method=None, headers=None):
        import urllib.request
        import urllib.error

        if not (isinstance(url, str) and url.startswith(("http://", "https://"))):
            raise PcError("http needs a web address starting with http:// or https://", "Value")
        body = None
        hdrs = {"User-Agent": "PyCmd"}
        if headers:
            hdrs.update({str(k): str(v) for k, v in headers.items()})
        if data is not None:
            if isinstance(data, (dict, list)):
                body = _json.dumps(_plain(data)).encode()
                hdrs.setdefault("Content-Type", "application/json")
            else:
                body = show(data).encode()
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read(5_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise PcError(f"{url} answered {exc.code}", "Http") from None
        except (urllib.error.URLError, OSError) as exc:
            raise PcError(f"could not reach {url}: {getattr(exc, 'reason', exc)}", "Http") from None

    return {
        "get": lambda url, headers=None: request(url, headers=headers),
        "get_json": lambda url: _json.loads(request(url)),
        "post": lambda url, data=None, headers=None: request(url, data, "POST", headers),
    }


def _lib_color():
    codes = {"red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36,
             "white": 37, "gray": 90, "bold": 1, "dim": 2, "underline": 4}
    out = {name: (lambda code: lambda s: f"\x1b[{code}m{show(s)}\x1b[0m")(code)
           for name, code in codes.items()}
    out["plain"] = lambda s: _re.sub(r"\x1b\[[0-9;]*m", "", show(s))
    return out


def _lib_sys(argv, platform):
    return {"args": list(argv), "platform": platform, "exit": _exit,
            "version": VERSION, "language": "PyCmd"}


VERSION = "1.0"

LIBRARIES = {
    "math": "sqrt, pow, floor, ceil, sin, cos, pi, gcd, factorial, is_prime, clamp, ...",
    "random": "int(a, b), float(), choice(xs), shuffle(xs), sample(xs, k), seed(n), chance(p)",
    "time": "now(), ms(), clock(), sleep(s), date(), time(), stamp(pattern)",
    "json": "parse(text), stringify(value), pretty(value)",
    "fs": "read, write, append, lines, list, exists, mkdir, remove - inside the program's folder",
    "regex": "test, find, find_all, groups, replace, split, escape",
    "stats": "mean, median, mode, stdev, variance, range",
    "text": "upper, lower, title, pad_left, center, is_palindrome, caesar, slug, wrap, ...",
    "http": "get(url), get_json(url), post(url, data)",
    "color": "red, green, yellow, blue, magenta, cyan, gray, bold, underline, plain",
    "sys": "args, platform, exit(code), version",
}


class Runtime:
    """One run's state: its console, folder, arguments and loaded libraries."""

    def __init__(self, stdout=None, stdin=None, argv=None, root=None, platform="pycmd"):
        self.console = Console(stdout, stdin)
        self.argv = list(argv or [])
        self.root = root or _os.getcwd()
        self.platform = platform
        self.libs = {}
        self.files = {}
        self.loading = set()
        self.tests = []

    def lib(self, name):
        if name not in self.libs:
            maker = {
                "math": _lib_math, "random": _lib_random, "time": _lib_time, "json": _lib_json,
                "fs": lambda: _lib_fs(self.root), "regex": _lib_regex, "stats": _lib_stats,
                "text": _lib_text, "http": _lib_http, "color": _lib_color,
                "sys": lambda: _lib_sys(self.argv, self.platform),
            }.get(name)
            if maker is None:
                raise PcError(f"there is no library called {name}", "Name")
            self.libs[name] = Module(name, maker())
        return self.libs[name]

    def namespace(self, filename="<pcmd>"):
        c = self.console
        ns = {
            "__builtins__": {"__build_class__": _b.__build_class__},
            "__name__": "pcmd",
            # helpers the compiler writes calls to
            "_pc_T": _T, "_pc_isinst": _isinst, "_pc_NUM": _NUM, "_pc_callable": callable,
            "_pc_len": len, "_pc_list_t": list, "_pc_range_t": range, "_pc_Exc": Exception,
            "_pc_static": staticmethod, "_pc_Struct": Struct, "_pc_Variant": Variant,
            "_pc_Error": PcError, "_pc_MISSING": MISSING, "_pc_show": show, "_pc_fmt": fmt,
            "_pc_catch": catch, "_pc_throw": throw, "_pc_assert": assert_failed,
            "_pc_type_err": type_error, "_pc_missing": missing_field, "_pc_enum": make_enum,
            "_pc_bind": bind, "_pc_oa": opt_attr, "_pc_oc": opt_call, "_pc_pairs": pairs,
            "_pc_inr": in_range, "_pc_lib": self.lib, "_pc_import": self.import_file,
            "_pc_tests": self.tests, "_pc_seq": SEQ, "_pc_tint": int, "_pc_tstr": str,
            "_pc_tbool": bool, "_pc_tdict": dict, "_pc_tset": set, "_pc_ttuple": tuple,
            # what programs call by name
            "print": c.print, "input": c.input, "len": _len, "str": show, "int": _int,
            "float": _float, "bool": _bool, "type": type_of, "range": _range, "abs": abs,
            "min": _min, "max": _max, "sum": _sum, "round": _round, "sorted": _sorted,
            "reversed": _reversed, "enumerate": _enumerate, "zip": _zip, "keys": _keys,
            "values": _values, "items": _items, "set": _set, "list": _list, "chr": chr,
            "ord": ord, "hex": hex, "bin": bin, "any": _any, "all": _all, "map": _map,
            "filter": _filter, "reduce": _reduce, "Error": Error, "exit": _exit,
            "copy": _copy, "clamp": _clamp, "repr": _repr, "pow": pow, "divmod": divmod,
            "is_nil": _is_nil, "char": _char, "args": list(self.argv),
        }
        for name, fn in DISPATCH.items():
            ns[f"_pc_x_{name}"] = fn
        return ns

    def import_file(self, path, from_file=None):
        from . import pcmd

        base = _os.path.dirname(from_file) if from_file and _os.path.isabs(from_file) else self.root
        full = _os.path.realpath(_os.path.join(base, path))
        if not full.endswith(".pcmd"):
            full += ".pcmd"
        if full in self.files:
            return self.files[full]
        if full in self.loading:
            raise PcError(f"{path} uses itself, through a loop of use lines", "Name")
        if not _os.path.isfile(full):
            raise PcError(f"there is no file {path} to use", "File")
        self.loading.add(full)
        try:
            with open(full, "r", encoding="utf-8") as handle:
                source = handle.read()
            exports = pcmd.execute(source, self, filename=full)
        finally:
            self.loading.discard(full)
        module = Module(_os.path.basename(full)[:-5], exports or {})
        self.files[full] = module
        return module


BUILTIN_NAMES = (
    "print input len str int float bool type range abs min max sum round sorted reversed "
    "enumerate zip keys values items set list chr ord hex bin any all map filter reduce "
    "Error exit copy clamp repr pow divmod is_nil char args"
).split()
