"""The values a Go program manipulates, and how Go prints them.

Kept apart from the evaluator because the standard library needs the same
definitions, and because the printing rules are fiddly enough to be worth
reading on their own: Go's `%v` is not Python's `repr`, and a program that
prints `[1 2 3]` where Python would print `[1, 2, 3]` is the difference
between an interpreter that runs Go and one that merely resembles it.
"""

from __future__ import annotations

import math

INT_MIN = -(2 ** 63)
INT_MAX = 2 ** 63 - 1


class GoError(Exception):
    """An interpreter-level failure: the program is wrong, not the runtime."""

    def __init__(self, message: str, line: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


class GoPanic(Exception):
    """`panic(v)`, recoverable by a deferred `recover()`."""

    def __init__(self, value) -> None:
        super().__init__(value)
        self.value = value


class GoExit(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class Nil:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<nil>"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other) -> bool:
        return isinstance(other, Nil)

    def __hash__(self) -> int:
        return hash("go-nil")


NIL = Nil()


class Rune(int):
    """A rune is an int that knows it came from a character literal."""


class Slice:
    """A view over a backing array, exactly as Go describes it.

    The backing list is shared: two slices cut from the same array see each
    other's writes, and `append` only allocates when it runs out of capacity.
    Programs that rely on that aliasing - and plenty do, usually by accident -
    behave here the way they behave on a real Go build.
    """

    __slots__ = ("backing", "offset", "length", "capacity", "element")

    def __init__(self, backing, offset=0, length=None, capacity=None, element=None):
        self.backing = backing
        self.offset = offset
        self.length = len(backing) - offset if length is None else length
        self.capacity = len(backing) - offset if capacity is None else capacity
        self.element = element

    @staticmethod
    def of(items, element=None):
        items = list(items)
        return Slice(items, 0, len(items), len(items), element)

    def __len__(self) -> int:
        return self.length

    def __iter__(self):
        for index in range(self.length):
            yield self.backing[self.offset + index]

    def get(self, index):
        if index < 0 or index >= self.length:
            raise GoPanic(f"runtime error: index out of range [{index}] with length {self.length}")
        return self.backing[self.offset + index]

    def set(self, index, value) -> None:
        if index < 0 or index >= self.length:
            raise GoPanic(f"runtime error: index out of range [{index}] with length {self.length}")
        self.backing[self.offset + index] = value

    def cut(self, low, high):
        if low is None:
            low = 0
        if high is None:
            high = self.length
        if low < 0 or high > self.capacity or low > high:
            raise GoPanic(f"runtime error: slice bounds out of range [{low}:{high}]")
        return Slice(self.backing, self.offset + low, high - low, self.capacity - low, self.element)

    def items(self):
        return self.backing[self.offset:self.offset + self.length]


class Array(Slice):
    """A fixed-size array, which unlike a slice is copied when assigned."""

    def copy(self):
        return Array(list(self.items()), 0, self.length, self.length, self.element)


class Struct:
    __slots__ = ("type_name", "fields")

    def __init__(self, type_name, fields) -> None:
        self.type_name = type_name
        self.fields = fields          # an ordered dict

    def copy(self):
        return Struct(self.type_name, {k: copy_value(v) for k, v in self.fields.items()})


class Pointer:
    """A pointer, which is either at a variable slot or at an object."""

    __slots__ = ("getter", "setter", "target", "label")

    def __init__(self, getter=None, setter=None, target=None, label="") -> None:
        self.getter = getter
        self.setter = setter
        self.target = target
        self.label = label

    @staticmethod
    def to(obj):
        return Pointer(target=obj)

    def get(self):
        if self.getter is not None:
            return self.getter()
        return self.target

    def set(self, value) -> None:
        if self.setter is not None:
            self.setter(value)
            return
        if isinstance(self.target, Struct) and isinstance(value, Struct):
            # `*p = v` on a struct pointer overwrites in place, so everything
            # else pointing at the same struct sees the new value.
            self.target.fields = {k: copy_value(v) for k, v in value.fields.items()}
            return
        raise GoError("cannot assign through this pointer")

    def __eq__(self, other) -> bool:
        if isinstance(other, Nil):
            return False
        if not isinstance(other, Pointer):
            return NotImplemented
        if self.target is not None or other.target is not None:
            return self.target is other.target
        return self is other

    def __hash__(self) -> int:
        return id(self.target) if self.target is not None else id(self)


class Func:
    __slots__ = ("name", "params", "variadic", "results", "body", "env", "receiver")

    def __init__(self, name, params, variadic, results, body, env, receiver=None) -> None:
        self.name = name
        self.params = params
        self.variadic = variadic
        self.results = results
        self.body = body
        self.env = env
        self.receiver = receiver


class Bound:
    """A method with its receiver already attached."""

    __slots__ = ("func", "receiver")

    def __init__(self, func, receiver) -> None:
        self.func = func
        self.receiver = receiver


class Builtin:
    __slots__ = ("name", "call", "wants_interp")

    def __init__(self, name, call, wants_interp=False) -> None:
        self.name = name
        self.call = call
        self.wants_interp = wants_interp


class Package:
    __slots__ = ("name", "members")

    def __init__(self, name, members) -> None:
        self.name = name
        self.members = members


class ErrorValue:
    """What `errors.New` and `fmt.Errorf` hand back."""

    __slots__ = ("message", "wrapped")

    def __init__(self, message, wrapped=None) -> None:
        self.message = message
        self.wrapped = wrapped

    def __eq__(self, other) -> bool:
        if isinstance(other, Nil):
            return False
        return self is other

    def __hash__(self) -> int:
        return id(self)


def copy_value(value):
    """Go copies structs and arrays on assignment; everything else is shared."""
    if isinstance(value, Struct):
        return value.copy()
    if isinstance(value, Array):
        return value.copy()
    return value


# --------------------------------------------------------------- formatting

def format_float(value: float) -> str:
    if value != value:
        return "NaN"
    if value == math.inf:
        return "+Inf"
    if value == -math.inf:
        return "-Inf"
    text = repr(value)
    if text.endswith(".0"):
        text = text[:-2]
    if "e" in text:
        mantissa, exponent = text.split("e")
        if mantissa.endswith(".0"):
            mantissa = mantissa[:-2]
        sign = "+" if not exponent.startswith("-") else "-"
        digits = exponent.lstrip("+-")
        if len(digits) < 2:
            digits = "0" + digits
        text = f"{mantissa}e{sign}{digits}"
    return text


def type_name(value) -> str:
    if isinstance(value, Nil):
        return "<nil>"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, Rune):
        return "int32"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float64"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Array):
        return f"[{value.length}]{value.element or 'interface {}'}"
    if isinstance(value, Slice):
        return f"[]{value.element or 'interface {}'}"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, Struct):
        return value.type_name or "struct {}"
    if isinstance(value, Pointer):
        inner = value.get()
        return "*" + type_name(inner) if not isinstance(inner, Nil) else "*"
    if isinstance(value, (Func, Bound, Builtin)):
        return "func()"
    if isinstance(value, ErrorValue):
        return "*errors.errorString"
    return type(value).__name__


def go_string(value, plus=False, quote_strings=False, interp=None) -> str:
    """`%v`, which is what Println uses for everything."""
    if isinstance(value, Nil):
        return "<nil>"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, ErrorValue):
        return value.message
    if isinstance(value, float):
        return format_float(value)
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, str):
        return f'"{value}"' if quote_strings else value
    if isinstance(value, (Array, Slice)):
        return "[" + " ".join(go_string(item, plus, quote_strings, interp) for item in value) + "]"
    if isinstance(value, dict):
        pairs = sorted(value.items(), key=lambda pair: _sort_key(pair[0]))
        body = " ".join(
            f"{go_string(k, plus, False, interp)}:{go_string(v, plus, quote_strings, interp)}"
            for k, v in pairs
        )
        return "map[" + body + "]"
    if isinstance(value, Struct):
        # A type with an Error() or String() method prints through it, which
        # is what makes custom error types read properly.
        if interp is not None:
            rendered = interp.stringer(value)
            if rendered is not None:
                return rendered
        if plus:
            body = " ".join(
                f"{k}:{go_string(v, plus, quote_strings, interp)}" for k, v in value.fields.items()
            )
        else:
            body = " ".join(
                go_string(v, plus, quote_strings, interp) for v in value.fields.values()
            )
        return "{" + body + "}"
    if isinstance(value, Pointer):
        inner = value.get()
        if isinstance(inner, Struct):
            if interp is not None:
                rendered = interp.stringer(value)
                if rendered is not None:
                    return rendered
            return "&" + go_string(inner, plus, quote_strings, interp)
        return f"0x{id(value):x}"
    if isinstance(value, (Func, Bound, Builtin)):
        return f"0x{id(value):x}"
    if isinstance(value, Package):
        return f"package {value.name}"
    return str(value)


def _sort_key(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, value, "")
    return (1, 0, go_string(value))


def truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    raise GoError("expected a bool")


class Chan:
    """A channel: a queue with a close flag and Go's blocking behaviour."""

    __slots__ = ("queue", "capacity", "closed", "lock", "not_empty", "not_full", "element")

    def __init__(self, capacity=0, element=None) -> None:
        import collections
        import threading

        self.queue = collections.deque()
        self.capacity = capacity
        self.closed = False
        self.element = element
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)

    def send(self, value) -> None:
        with self.not_full:
            if self.closed:
                raise GoPanic("send on closed channel")
            # An unbuffered channel is modelled as a one-slot buffer: the
            # sender waits for a receiver to take the value, which is the part
            # that matters for the synchronisation programs rely on.
            limit = self.capacity if self.capacity > 0 else 1
            while len(self.queue) >= limit and not self.closed:
                self.not_full.wait(0.05)
            if self.closed:
                raise GoPanic("send on closed channel")
            self.queue.append(value)
            self.not_empty.notify()

    def receive(self, timeout=None):
        """Returns (value, ok); ok is False once a closed channel is drained."""
        with self.not_empty:
            waited = 0.0
            while not self.queue:
                if self.closed:
                    return NIL, False
                if timeout is not None and waited >= timeout:
                    return None, None
                self.not_empty.wait(0.05)
                waited += 0.05
            value = self.queue.popleft()
            self.not_full.notify()
            return value, True

    def ready(self) -> bool:
        with self.lock:
            return bool(self.queue) or self.closed

    def close(self) -> None:
        with self.lock:
            if self.closed:
                raise GoPanic("close of closed channel")
            self.closed = True
            self.not_empty.notify_all()
            self.not_full.notify_all()

    def __len__(self) -> int:
        return len(self.queue)

    def __iter__(self):
        while True:
            value, ok = self.receive()
            if not ok:
                return
            yield value


class TypedMap(dict):
    """A Go map that knows what its values are.

    Reading a missing key gives the value type's zero, and that zero has to
    be the right kind: `m[k] = append(m[k], 1)` on a `map[string][]int` reads
    a nil slice, appends to it, and stores the result. A plain dict had no way
    to know its values were slices, so it handed back 0 and append refused it.
    """

    __slots__ = ("value_type",)

    def __init__(self, *args, value_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.value_type = value_type
