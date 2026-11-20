"""One tokeniser, shared by the Go and Rust interpreters.

Both languages are C-shaped at the character level - the same comments, the
same operator soup, near-identical number literals - so they get one lexer
with the differences passed in rather than two that drift apart. What differs
is spelled out in the options: Go has backtick raw strings and `:=`, Rust has
lifetimes, `r"..."` raw strings and typed number suffixes.
"""

from __future__ import annotations

HEX = "0123456789abcdefABCDEF"

SIMPLE_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\",
    "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "v": "\v",
    "`": "`",
}


class LangSyntaxError(Exception):
    """Anything the lexer or a parser cannot make sense of."""

    def __init__(self, message: str, line: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: str, value, line: int) -> None:
        # kind: id, kw, int, float, str, char, op, eof
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.kind}, {self.value!r}, line {self.line})"


class Options:
    """How one language differs from the other."""

    __slots__ = (
        "keywords", "operators", "backtick_raw", "raw_prefix", "lifetimes",
        "nested_comments", "number_suffixes", "char_as_int",
    )

    def __init__(
        self,
        keywords,
        operators,
        backtick_raw=False,
        raw_prefix=False,
        lifetimes=False,
        nested_comments=False,
        number_suffixes=(),
        char_as_int=False,
    ) -> None:
        self.keywords = keywords
        # Longest first: the lexer takes the first match, so "<<=" has to be
        # tried before "<<", and "<<" before "<".
        self.operators = sorted(operators, key=len, reverse=True)
        self.backtick_raw = backtick_raw
        self.raw_prefix = raw_prefix
        self.lifetimes = lifetimes
        self.nested_comments = nested_comments
        self.number_suffixes = number_suffixes
        self.char_as_int = char_as_int


def tokenize(source: str, options: Options) -> list:
    tokens = []
    index = 0
    line = 1
    length = len(source)

    def peek(offset=0):
        position = index + offset
        return source[position] if position < length else ""

    while index < length:
        char = source[index]

        if char == "\n":
            line += 1
            index += 1
            continue
        if char in " \t\r\f\v":
            index += 1
            continue

        # ---------------------------------------------------------- comments
        if char == "/" and peek(1) == "/":
            while index < length and source[index] != "\n":
                index += 1
            continue
        if char == "/" and peek(1) == "*":
            index += 2
            depth = 1
            while index < length and depth:
                if source[index] == "\n":
                    line += 1
                elif options.nested_comments and source[index] == "/" and peek(1) == "*":
                    depth += 1
                    index += 1
                elif source[index] == "*" and peek(1) == "/":
                    depth -= 1
                    index += 1
                index += 1
            continue

        # ----------------------------------------------------- raw strings
        if options.backtick_raw and char == "`":
            index += 1
            start = index
            while index < length and source[index] != "`":
                if source[index] == "\n":
                    line += 1
                index += 1
            if index >= length:
                raise LangSyntaxError("unterminated raw string", line)
            tokens.append(Token("str", source[start:index], line))
            index += 1
            continue

        if options.raw_prefix and char == "r" and peek(1) in ('"', "#"):
            hashes = 0
            probe = index + 1
            while probe < length and source[probe] == "#":
                hashes += 1
                probe += 1
            if probe < length and source[probe] == '"':
                index = probe + 1
                closer = '"' + "#" * hashes
                end = source.find(closer, index)
                if end < 0:
                    raise LangSyntaxError("unterminated raw string", line)
                text = source[index:end]
                line += text.count("\n")
                tokens.append(Token("str", text, line))
                index = end + len(closer)
                continue

        # ------------------------------------------------------ byte strings
        if options.raw_prefix and char == "b" and peek(1) == '"':
            index += 1
            char = source[index]

        # --------------------------------------------------------- strings
        if char == '"':
            index += 1
            pieces = []
            while index < length and source[index] != '"':
                if source[index] == "\\":
                    value, index = _escape(source, index + 1, line)
                    pieces.append(value)
                    continue
                if source[index] == "\n":
                    raise LangSyntaxError("unterminated string", line)
                pieces.append(source[index])
                index += 1
            if index >= length:
                raise LangSyntaxError("unterminated string", line)
            index += 1
            tokens.append(Token("str", "".join(pieces), line))
            continue

        # ---------------------------------------- characters, runes, lifetimes
        if char == "'":
            # In Rust `'a` is a lifetime, not a character: a quote followed by
            # an identifier with no closing quote after it.
            if options.lifetimes and _looks_like_lifetime(source, index, length):
                index += 1
                start = index
                while index < length and (source[index].isalnum() or source[index] == "_"):
                    index += 1
                tokens.append(Token("lifetime", source[start:index], line))
                continue

            index += 1
            if index >= length:
                raise LangSyntaxError("unterminated character literal", line)
            if source[index] == "\\":
                value, index = _escape(source, index + 1, line)
            else:
                value = source[index]
                index += 1
            if index >= length or source[index] != "'":
                raise LangSyntaxError("unterminated character literal", line)
            index += 1
            if options.char_as_int:
                tokens.append(Token("int", ord(value), line))
            else:
                tokens.append(Token("char", value, line))
            continue

        # --------------------------------------------------------- numbers
        # `.5` is a number, but the dot in `point.5` is field access on a
        # tuple: what decides is whether the previous token could end an
        # expression.
        leading_dot = char == "." and peek(1).isdigit() and not (
            tokens and (tokens[-1].kind in ("id", "int", "float")
                        or tokens[-1].value in (")", "]", "}")
                        # `self.0` - the receiver of a tuple struct is a
                        # keyword, not a name, and a keyword that ends an
                        # expression needs the same treatment or `.0` reads
                        # as the number 0.0 and `self` is left on its own.
                        or (tokens[-1].kind == "kw"
                            and tokens[-1].value in ("self", "Self", "this", "super")))
        )
        if char.isdigit() or leading_dot:
            start = index
            is_float = False
            if char == "0" and peek(1) in "xXbBoO":
                base = {"x": 16, "b": 2, "o": 8}[peek(1).lower()]
                index += 2
                digits = ""
                while index < length and (source[index] in HEX or source[index] == "_"):
                    if source[index] != "_":
                        digits += source[index]
                    index += 1
                index = _skip_suffix(source, index, length, options)
                if not digits:
                    raise LangSyntaxError("number has no digits", line)
                tokens.append(Token("int", int(digits, base), line))
                continue

            while index < length and (source[index].isdigit() or source[index] == "_"):
                index += 1
            # `.` starts a fraction only when a digit follows: in `b.1.cmp()`
            # the dots are field access, and `1.` there is not a float.
            if index < length and source[index] == "." and peek(1).isdigit():
                is_float = True
                index += 1
                while index < length and (source[index].isdigit() or source[index] == "_"):
                    index += 1
            if index < length and source[index] in "eE":
                probe = index + 1
                if probe < length and source[probe] in "+-":
                    probe += 1
                if probe < length and source[probe].isdigit():
                    is_float = True
                    index = probe
                    while index < length and source[index].isdigit():
                        index += 1

            text = source[start:index].replace("_", "")
            after = _skip_suffix(source, index, length, options)
            if after != index:
                # A float suffix makes an integer literal a float: 1f64.
                if source[index] in "fF":
                    is_float = True
                index = after
            if is_float:
                tokens.append(Token("float", float(text), line))
            else:
                # A leading zero is octal in Go, as in C.
                if len(text) > 1 and text[0] == "0" and text.isdigit():
                    tokens.append(Token("int", int(text, 8), line))
                else:
                    tokens.append(Token("int", int(text), line))
            continue

        # ----------------------------------------------------- identifiers
        if char.isalpha() or char == "_":
            start = index
            while index < length and (source[index].isalnum() or source[index] == "_"):
                index += 1
            word = source[start:index]
            tokens.append(Token("kw" if word in options.keywords else "id", word, line))
            continue

        # ------------------------------------------------------- operators
        for operator in options.operators:
            if source.startswith(operator, index):
                tokens.append(Token("op", operator, line))
                index += len(operator)
                break
        else:
            raise LangSyntaxError(f"unexpected character {char!r}", line)

    tokens.append(Token("eof", None, line))
    return tokens


def _looks_like_lifetime(source: str, index: int, length: int) -> bool:
    """`'a` is a lifetime; `'a'` is a character."""
    probe = index + 1
    if probe < length and source[probe] == "\\":
        return False
    start = probe
    while probe < length and (source[probe].isalnum() or source[probe] == "_"):
        probe += 1
    if probe == start:
        return False
    return not (probe - start == 1 and probe < length and source[probe] == "'")


def _skip_suffix(source: str, index: int, length: int, options: Options) -> int:
    for suffix in options.number_suffixes:
        if source.startswith(suffix, index):
            after = index + len(suffix)
            # A suffix must not swallow the start of an identifier.
            if after >= length or not (source[after].isalnum() or source[after] == "_"):
                return after
    return index


def _escape(source: str, index: int, line: int):
    """Reads one escape sequence, starting just after the backslash."""
    if index >= len(source):
        raise LangSyntaxError("string ends inside an escape", line)
    char = source[index]

    if char in SIMPLE_ESCAPES:
        return SIMPLE_ESCAPES[char], index + 1
    if char == "x":
        digits = source[index + 1:index + 3]
        if len(digits) < 2 or any(d not in HEX for d in digits):
            raise LangSyntaxError("bad \\x escape", line)
        return chr(int(digits, 16)), index + 3
    if char == "u":
        if index + 1 < len(source) and source[index + 1] == "{":
            end = source.find("}", index)
            if end < 0:
                raise LangSyntaxError("bad \\u{...} escape", line)
            return chr(int(source[index + 2:end], 16)), end + 1
        digits = source[index + 1:index + 5]
        if len(digits) < 4:
            raise LangSyntaxError("bad \\u escape", line)
        return chr(int(digits, 16)), index + 5
    if char == "U":
        digits = source[index + 1:index + 9]
        if len(digits) < 8:
            raise LangSyntaxError("bad \\U escape", line)
        return chr(int(digits, 16)), index + 9
    if char == "\n":
        # Rust: a backslash at the end of a line eats the newline and the
        # indentation that follows it.
        probe = index + 1
        while probe < len(source) and source[probe] in " \t":
            probe += 1
        return "", probe
    raise LangSyntaxError(f"unknown escape \\{char}", line)
