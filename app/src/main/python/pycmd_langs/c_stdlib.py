"""The slice of the C standard library the interpreter provides.

Everything here is implemented against the interpreter's memory model rather
than emulated: `malloc` really does hand back a pointer into a fresh storage,
`strcpy` really does write through the destination pointer, and `scanf` reads
the same stdin the Python console does. That is what makes a program that walks
a `char *` behave the way it would anywhere else.
"""

from __future__ import annotations

import math
import time

from .c_interp import NULL, CRuntimeError, CStruct, Pointer


def _fmt_int(value) -> int:
    if isinstance(value, Pointer):
        raise CRuntimeError("a pointer was passed where a number was expected")
    return int(value)


def format_printf(interp, fmt: str, args: list) -> str:
    """Implements the printf conversions, including width and precision."""
    out = []
    i = 0
    arg_index = 0
    length = len(fmt)

    while i < length:
        ch = fmt[i]
        if ch != "%":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i < length and fmt[i] == "%":
            out.append("%")
            i += 1
            continue

        flags = ""
        while i < length and fmt[i] in "-+ 0#":
            flags += fmt[i]
            i += 1

        width = ""
        if i < length and fmt[i] == "*":
            width = str(_fmt_int(args[arg_index]))
            arg_index += 1
            i += 1
        else:
            while i < length and fmt[i].isdigit():
                width += fmt[i]
                i += 1

        precision = ""
        has_precision = False
        if i < length and fmt[i] == ".":
            has_precision = True
            i += 1
            if i < length and fmt[i] == "*":
                precision = str(_fmt_int(args[arg_index]))
                arg_index += 1
                i += 1
            else:
                while i < length and fmt[i].isdigit():
                    precision += fmt[i]
                    i += 1

        # Length modifiers change nothing here: Python integers are arbitrary
        # precision and the interpreter has one float type.
        while i < length and fmt[i] in "hlLzjt":
            i += 1

        if i >= length:
            out.append("%")
            break

        conversion = fmt[i]
        i += 1

        if conversion not in "diufFeEgGxXocsp":
            out.append("%" + conversion)
            continue

        if arg_index >= len(args):
            raise CRuntimeError(
                f"printf: the format asks for more arguments than were passed "
                f"(%{conversion} has none)"
            )
        value = args[arg_index]
        arg_index += 1

        spec = "%" + flags + width + (("." + precision) if has_precision else "")

        if conversion in "di":
            out.append((spec + "d") % _fmt_int(value))
        elif conversion == "u":
            number = _fmt_int(value)
            out.append((spec + "d") % (number if number >= 0 else number + (1 << 32)))
        elif conversion in "fF":
            out.append((spec + "f") % float(value))
        elif conversion in "eEgG":
            out.append((spec + conversion) % float(value))
        elif conversion in "xX":
            out.append((spec + conversion) % (_fmt_int(value) & 0xFFFFFFFF))
        elif conversion == "o":
            out.append((spec + "o") % _fmt_int(value))
        elif conversion == "c":
            out.append((spec + "s") % chr(_fmt_int(value) & 0xFF))
        elif conversion == "s":
            text = interp.read_string(value) if isinstance(value, Pointer) else str(value)
            out.append((spec + "s") % text)
        elif conversion == "p":
            if isinstance(value, Pointer):
                out.append("(nil)" if value.is_null else f"0x{id(value.storage) & 0xFFFFFF:x}+{value.index}")
            else:
                out.append(str(value))

    return "".join(out)


def _scan_values(interp, fmt: str, pointers: list) -> int:
    """A workable scanf: %d %f %s %c and literal whitespace/characters."""
    assigned = 0
    pointer_index = 0
    i = 0

    while i < len(fmt):
        ch = fmt[i]

        if ch.isspace():
            i += 1
            continue

        if ch != "%":
            i += 1
            continue

        i += 1
        while i < len(fmt) and (fmt[i].isdigit() or fmt[i] in "hlL*"):
            i += 1
        if i >= len(fmt):
            break
        conversion = fmt[i]
        i += 1

        token = interp.next_token(conversion == "c")
        if token is None:
            break

        if pointer_index >= len(pointers):
            break
        destination = pointers[pointer_index]
        pointer_index += 1

        if not isinstance(destination, Pointer):
            raise CRuntimeError("scanf needs a pointer, e.g. scanf(\"%d\", &n)")

        try:
            if conversion in "di":
                destination.write(int(token))
            elif conversion in "fFeEgG":
                destination.write(float(token))
            elif conversion == "c":
                destination.write(ord(token[0]) if token else 0)
            elif conversion == "s":
                storage = destination.storage
                start = destination.index
                for offset, character in enumerate(token):
                    if start + offset < len(storage):
                        storage[start + offset] = ord(character) & 0xFF
                if start + len(token) < len(storage):
                    storage[start + len(token)] = 0
            else:
                continue
        except ValueError:
            break
        assigned += 1

    return assigned


def _comparator(interp, compare, line):
    """A user's comparison function, as something Python's sort can call.

    qsort hands the comparator two `const void *`, which the program casts to
    whatever it is sorting and dereferences. Each element is handed over in a
    one-slot storage of its own, so the cast-and-dereference reads it back
    exactly as it would read the real array.
    """
    if not (isinstance(compare, tuple) and len(compare) == 2 and compare[0] == "__function__"):
        raise CRuntimeError("qsort's last argument has to be a function", line)
    function = interp.functions.get(compare[1])
    if function is None:
        raise CRuntimeError(f"'{compare[1]}' is not a function", line)

    def compare_two(a, b, base="int"):
        result = interp.call_function(
            function, [Pointer([a], 0, base), Pointer([b], 0, base)], line)
        return int(result or 0)

    return compare_two


def call_builtin(interp, name, args, arg_nodes, scope, line):
    """Returns (handled, result). Unknown names fall through to the caller."""

    # ---------------------------------------------------------------- stdlib
    if name == "qsort":
        import functools

        if len(args) < 4:
            raise CRuntimeError("qsort takes a base, a count, a size and a comparator", line)
        base, count = args[0], int(args[1])
        compare = _comparator(interp, args[3], line)
        storage = base.storage
        start = base.index
        values = list(storage[start:start + count])
        values.sort(key=functools.cmp_to_key(lambda a, b: compare(a, b, base.base)))
        for offset, value in enumerate(values):
            storage[start + offset] = value
        return True, 0

    if name == "bsearch":
        if len(args) < 5:
            raise CRuntimeError("bsearch takes a key, a base, a count, a size and a comparator", line)
        key, base, count = args[0], args[1], int(args[2])
        compare = _comparator(interp, args[4], line)
        wanted = key.read() if hasattr(key, "read") else key
        low, high = 0, count - 1
        while low <= high:
            middle = (low + high) // 2
            order = compare(wanted, base.storage[base.index + middle], base.base)
            if order == 0:
                return True, Pointer(base.storage, base.index + middle, base.base)
            if order < 0:
                high = middle - 1
            else:
                low = middle + 1
        return True, Pointer(None, 0, base.base)

    # ------------------------------------------------------------------ stdio
    if name == "printf":
        if not args:
            raise CRuntimeError("printf needs a format string", line)
        text = format_printf(interp, interp.read_string(args[0]), args[1:])
        interp.write(text)
        return True, len(text)

    if name == "puts":
        text = interp.read_string(args[0]) if args else ""
        interp.write(text + "\n")
        return True, len(text) + 1

    if name == "putchar":
        interp.write(chr(int(args[0]) & 0xFF))
        return True, int(args[0])

    if name in ("fprintf",):
        # The stream argument is accepted and ignored: both stdout and stderr
        # reach the same console, and a program that writes to stderr should
        # still show its output rather than fail.
        if len(args) < 2:
            raise CRuntimeError("fprintf needs a stream and a format", line)
        text = format_printf(interp, interp.read_string(args[1]), args[2:])
        interp.write(text)
        return True, len(text)

    if name in ("sprintf", "snprintf"):
        if name == "sprintf":
            destination, fmt_pointer, rest = args[0], args[1], args[2:]
            limit = None
        else:
            destination, limit, fmt_pointer, rest = args[0], int(args[1]), args[2], args[3:]
        text = format_printf(interp, interp.read_string(fmt_pointer), rest)
        if limit is not None:
            text = text[: max(0, limit - 1)]
        storage = destination.storage
        start = destination.index
        for offset, character in enumerate(text):
            if start + offset < len(storage):
                storage[start + offset] = ord(character) & 0xFF
        if start + len(text) < len(storage):
            storage[start + len(text)] = 0
        return True, len(text)

    if name == "scanf":
        fmt = interp.read_string(args[0]) if args else ""
        return True, _scan_values(interp, fmt, args[1:])

    if name == "getchar":
        character = interp.next_char()
        return True, ord(character) if character else -1

    if name in ("fgets", "gets"):
        destination = args[0]
        limit = int(args[1]) if name == "fgets" and len(args) > 1 else 1 << 30
        line_text = interp.read_line()
        if not line_text:
            return True, NULL
        if name == "gets":
            line_text = line_text.rstrip("\n")
        line_text = line_text[: max(0, limit - 1)]
        storage = destination.storage
        start = destination.index
        for offset, character in enumerate(line_text):
            if start + offset < len(storage):
                storage[start + offset] = ord(character) & 0xFF
        if start + len(line_text) < len(storage):
            storage[start + len(line_text)] = 0
        return True, destination

    # ----------------------------------------------------------------- stdlib
    if name in ("malloc", "calloc", "realloc"):
        if name == "calloc":
            count = int(args[0]) * int(args[1])
            return True, Pointer([0] * max(count, 0), 0)
        if name == "realloc":
            old, size = args[0], int(args[1])
            fresh = [0] * max(size, 0)
            if isinstance(old, Pointer) and not old.is_null:
                for index in range(min(len(old.storage) - old.index, size)):
                    fresh[index] = old.storage[old.index + index]
            return True, Pointer(fresh, 0)
        size = int(args[0])
        # Bytes are not modelled individually; one slot per byte is the closest
        # honest mapping and makes malloc(n * sizeof(int)) behave sensibly.
        return True, Pointer([0] * max(size, 0), 0)

    if name == "free":
        # Storage is reclaimed by Python's own collector; free() is accepted so
        # correct C still reads correctly.
        return True, 0

    if name == "exit":
        from .c_interp import _Exit

        raise _Exit(int(args[0]) if args else 0)

    if name == "abort":
        raise CRuntimeError("abort() was called", line)

    if name in ("atoi", "atol"):
        text = interp.read_string(args[0]).strip()
        digits = ""
        for index, character in enumerate(text):
            if character in "+-" and index == 0:
                digits += character
            elif character.isdigit():
                digits += character
            else:
                break
        return True, int(digits) if digits not in ("", "+", "-") else 0

    if name == "atof":
        text = interp.read_string(args[0]).strip()
        collected = ""
        for index, character in enumerate(text):
            if character.isdigit() or character == "." or (character in "+-" and index == 0):
                collected += character
            else:
                break
        try:
            return True, float(collected)
        except ValueError:
            return True, 0.0

    if name == "abs":
        return True, abs(int(args[0]))
    if name in ("labs",):
        return True, abs(int(args[0]))
    if name == "fabs":
        return True, abs(float(args[0]))

    if name == "rand":
        return True, interp._random.randint(0, 32767)
    if name == "srand":
        interp._random.seed(int(args[0]) if args else 0)
        return True, 0
    if name == "time":
        return True, int(time.time())

    # ----------------------------------------------------------------- string
    if name == "strlen":
        return True, len(interp.read_string(args[0]))

    if name in ("strcpy", "strncpy"):
        destination, source = args[0], args[1]
        text = interp.read_string(source)
        if name == "strncpy":
            text = text[: int(args[2])]
        storage = destination.storage
        start = destination.index
        for offset, character in enumerate(text):
            if start + offset < len(storage):
                storage[start + offset] = ord(character) & 0xFF
        if start + len(text) < len(storage):
            storage[start + len(text)] = 0
        return True, destination

    if name == "strcat":
        destination, source = args[0], args[1]
        existing = interp.read_string(destination)
        addition = interp.read_string(source)
        storage = destination.storage
        start = destination.index + len(existing)
        for offset, character in enumerate(addition):
            if start + offset < len(storage):
                storage[start + offset] = ord(character) & 0xFF
        if start + len(addition) < len(storage):
            storage[start + len(addition)] = 0
        return True, destination

    if name in ("strcmp", "strncmp"):
        left = interp.read_string(args[0])
        right = interp.read_string(args[1])
        if name == "strncmp":
            count = int(args[2])
            left, right = left[:count], right[:count]
        return True, (0 if left == right else (-1 if left < right else 1))

    if name == "strchr":
        pointer = args[0]
        target = int(args[1]) & 0xFF
        text = interp.read_string(pointer)
        position = text.find(chr(target))
        if position == -1:
            return True, NULL
        return True, pointer.offset(position)

    if name == "strstr":
        haystack_pointer = args[0]
        haystack = interp.read_string(haystack_pointer)
        needle = interp.read_string(args[1])
        position = haystack.find(needle)
        if position == -1:
            return True, NULL
        return True, haystack_pointer.offset(position)

    if name in ("memset",):
        destination, value, count = args[0], int(args[1]) & 0xFF, int(args[2])
        storage = destination.storage
        for offset in range(count):
            if destination.index + offset < len(storage):
                storage[destination.index + offset] = value
        return True, destination

    if name in ("memcpy", "memmove"):
        destination, source, count = args[0], args[1], int(args[2])
        chunk = [source.storage[source.index + i] for i in range(count)
                 if source.index + i < len(source.storage)]
        for offset, item in enumerate(chunk):
            if destination.index + offset < len(destination.storage):
                destination.storage[destination.index + offset] = item
        return True, destination

    # ------------------------------------------------------------------- math
    unary_math = {
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "exp": math.exp, "log": math.log, "log10": math.log10,
        "floor": math.floor, "ceil": math.ceil,
    }
    if name in unary_math:
        try:
            result = unary_math[name](float(args[0]))
        except ValueError as exc:
            raise CRuntimeError(f"{name}(): {exc}", line) from None
        return True, float(result)

    if name == "pow":
        return True, float(math.pow(float(args[0]), float(args[1])))
    if name == "fmod":
        return True, float(math.fmod(float(args[0]), float(args[1])))
    if name == "atan2":
        return True, float(math.atan2(float(args[0]), float(args[1])))
    if name == "round":
        return True, float(math.floor(float(args[0]) + 0.5))

    # ------------------------------------------------------------------ ctype
    single_char = {
        "isalpha": str.isalpha, "isdigit": str.isdigit, "isalnum": str.isalnum,
        "isspace": str.isspace, "isupper": str.isupper, "islower": str.islower,
    }
    if name in single_char:
        character = chr(int(args[0]) & 0xFF)
        return True, 1 if single_char[name](character) else 0
    if name == "toupper":
        return True, ord(chr(int(args[0]) & 0xFF).upper())
    if name == "tolower":
        return True, ord(chr(int(args[0]) & 0xFF).lower())
    if name == "ispunct":
        character = chr(int(args[0]) & 0xFF)
        return True, 1 if character.isprintable() and not character.isalnum() and not character.isspace() else 0

    return False, None
