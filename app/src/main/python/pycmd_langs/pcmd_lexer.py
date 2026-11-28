"""Tokens for PyCmd, the app's own language (.pcmd).

Statements end at the end of a line (or at ``;``). A line carries on to the
next when it ends with an operator or a comma, when it is inside ( ) or [ ],
or when the next line starts with ``.``, ``?.``, ``|>`` or ``??`` - so method
chains and pipelines can be spread over several lines without any marker.
"""

from __future__ import annotations

KEYWORDS = {
    "let", "var", "const", "fn", "return", "if", "elif", "else", "while", "for", "in",
    "loop", "break", "continue", "match", "struct", "enum", "extends", "true", "false",
    "nil", "and", "or", "not", "try", "catch", "finally", "throw", "use", "as", "is",
    "assert", "test", "self", "pub",
}

# Longest first: the lexer takes the first that matches.
OPERATORS = [
    "..=", "//=", "**=", "...",
    "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "->", "=>", "|>", "??", "?.",
    "..", "//", "**", "&&", "||",
    "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]", "{", "}", ",", ":",
    ".", "?", "!", "|", ";", "&", "@",
]

# A line ending in one of these goes on to the next.
CONTINUES_AFTER = {
    "+", "-", "*", "/", "%", "//", "**", "==", "!=", "<", "<=", ">", ">=", "=", "+=",
    "-=", "*=", "/=", "%=", "//=", "**=", "and", "or", "not", "&&", "||", ",", ".",
    "|>", "??", "?", ":", "=>", "->", "..", "..=", "(", "[", "in", "is", "|",
}
# A line starting with one of these belongs to the line before.
CONTINUES_BEFORE = {".", "?.", "|>", "??", ")", "]"}


class PcmdSyntaxError(Exception):
    def __init__(self, message: str, line: int, col: int = 0):
        super().__init__(f"line {line}: {message}")
        self.message = message
        self.line = line
        self.col = col


class Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind = kind      # num, str, name, kw, op, nl, eof
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.line})"

    def is_op(self, *ops):
        return self.kind == "op" and self.value in ops

    def is_kw(self, *words):
        return self.kind == "kw" and self.value in words


ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'",
           "{": "\0LBRACE\0", "}": "\0RBRACE\0", "e": "\x1b"}


def _read_string(src, i, line, quote, triple):
    """Reads a string body starting after the opening quote(s).

    Returns (parts, new_index, new_line). parts is a list of literal strings and
    ("expr", text, line) tuples for {interpolations}; single-quoted strings
    have no interpolation.
    """
    parts = []
    buf = []
    interpolate = quote == '"'
    start_line = line
    n = len(src)
    while True:
        if i >= n:
            raise PcmdSyntaxError("this string never ends - a closing quote is missing", start_line)
        ch = src[i]
        if triple and src.startswith(quote * 3, i):
            i += 3
            break
        if not triple and ch == quote:
            i += 1
            break
        if ch == "\n":
            if not triple:
                raise PcmdSyntaxError("this string never ends on its line - close the quote, "
                                      'or use """triple quotes""" for several lines', start_line)
            line += 1
            buf.append(ch)
            i += 1
            continue
        if ch == "\\":
            if i + 1 >= n:
                raise PcmdSyntaxError("a string ends in a lone backslash", line)
            nxt = src[i + 1]
            if nxt == "u" and src[i + 2:i + 3] == "{":
                end = src.find("}", i + 3)
                if end < 0:
                    raise PcmdSyntaxError("\\u{...} is not closed", line)
                try:
                    buf.append(chr(int(src[i + 3:end], 16)))
                except ValueError:
                    raise PcmdSyntaxError(f"\\u{{{src[i + 3:end]}}} is not a hex code", line) from None
                i = end + 1
                continue
            if nxt == "\n":
                line += 1
                i += 2
                continue
            esc = ESCAPES.get(nxt)
            if esc is None:
                raise PcmdSyntaxError(f"unknown escape \\{nxt}", line)
            if esc == "\0LBRACE\0":
                esc = "{"
            elif esc == "\0RBRACE\0":
                esc = "}"
            buf.append(esc)
            i += 2
            continue
        if interpolate and ch == "{":
            if src.startswith("{{", i):
                buf.append("{")
                i += 2
                continue
            depth = 1
            j = i + 1
            in_str = None
            while j < n and depth:
                c = src[j]
                if in_str:
                    if c == "\\":
                        j += 2
                        continue
                    if c == in_str:
                        in_str = None
                elif c in "\"'":
                    in_str = c
                elif c in "{([":
                    depth += 1
                elif c in "})]":
                    depth -= 1
                elif c == "\n" and not triple:
                    break
                j += 1
            if depth:
                raise PcmdSyntaxError("a { in this string is never closed - write {{ for a "
                                      "plain brace", line)
            if buf:
                parts.append("".join(buf))
                buf = []
            text = src[i + 1:j - 1]
            if not text.strip():
                raise PcmdSyntaxError("empty {} in a string - put a name or expression inside, "
                                      "or write {{}} for braces", line)
            parts.append(("expr", text, line))
            line += text.count("\n")
            i = j
            continue
        if interpolate and ch == "}" and src.startswith("}}", i):
            buf.append("}")
            i += 2
            continue
        buf.append(ch)
        i += 1
    if buf or not parts:
        parts.append("".join(buf))
    return parts, i, line


def tokenize(src: str):
    src = src.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    tokens = []
    i = 0
    line = 1
    line_start = 0
    n = len(src)
    depth = []  # open ( and [ - newlines inside them do not end a statement
    while i < n:
        ch = src[i]
        col = i - line_start + 1
        if ch == "\n":
            if not depth or depth[-1] == "{":
                tokens.append(Token("nl", "\n", line, col))
            i += 1
            line += 1
            line_start = i
            continue
        if ch in " \f\v":
            i += 1
            continue
        if ch == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and src[i + 1].isdigit()
                            and not (tokens and tokens[-1].kind in ("num", "name") or
                                     (tokens and tokens[-1].is_op(")", "]")))):
            j = i
            if src.startswith(("0x", "0X"), i):
                j = i + 2
                while j < n and (src[j] in "0123456789abcdefABCDEF_"):
                    j += 1
                text = src[i:j].replace("_", "")
                tokens.append(Token("num", int(text, 16), line, col))
                i = j
                continue
            if src.startswith(("0b", "0B"), i):
                j = i + 2
                while j < n and src[j] in "01_":
                    j += 1
                tokens.append(Token("num", int(src[i + 2:j].replace("_", ""), 2), line, col))
                i = j
                continue
            is_float = False
            while j < n and (src[j].isdigit() or src[j] == "_"):
                j += 1
            # 1..5 is a range, not the float "1." followed by ".5"
            if j < n and src[j] == "." and not src.startswith("..", j) and \
                    j + 1 < n and src[j + 1].isdigit():
                is_float = True
                j += 1
                while j < n and (src[j].isdigit() or src[j] == "_"):
                    j += 1
            if j < n and src[j] in "eE" and (j + 1 < n and (src[j + 1].isdigit() or
                                                             (src[j + 1] in "+-" and j + 2 < n and
                                                              src[j + 2].isdigit()))):
                is_float = True
                j += 2
                while j < n and src[j].isdigit():
                    j += 1
            text = src[i:j].replace("_", "")
            if text.startswith("."):
                text = "0" + text
            value = float(text) if is_float else int(text)
            if j < n and (src[j].isalpha() or src[j] == "_"):
                raise PcmdSyntaxError(f"a number runs into letters: {src[i:j + 1]}", line, col)
            tokens.append(Token("num", value, line, col))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            tokens.append(Token("kw" if word in KEYWORDS else "name", word, line, col))
            i = j
            continue
        if ch in "\"'":
            triple = src.startswith(ch * 3, i)
            start = i + (3 if triple else 1)
            parts, i, new_line = _read_string(src, start, line, ch, triple)
            tokens.append(Token("str", parts, line, col))
            # Line counting inside the string, for the lines after it.
            if new_line != line:
                line_start = src.rfind("\n", 0, i) + 1
            line = new_line
            continue
        for op in OPERATORS:
            if src.startswith(op, i):
                break
        else:
            raise PcmdSyntaxError(f"unexpected character {ch!r}", line, col)
        if op == ";":
            tokens.append(Token("nl", ";", line, col))
            i += 1
            continue
        if op in ("(", "["):
            depth.append(op)
        elif op == "{":
            depth.append("{")
        elif op in (")", "]", "}"):
            if depth:
                depth.pop()
        tokens.append(Token("op", op, line, col))
        i += len(op)
    tokens.append(Token("nl", "\n", line, 1))
    tokens.append(Token("eof", None, line, 1))
    return _join_lines(tokens)


def _join_lines(tokens):
    out = []
    for index, token in enumerate(tokens):
        if token.kind == "nl":
            prev = out[-1] if out else None
            if prev is None or prev.kind == "nl":
                continue
            if (prev.kind in ("op", "kw") and prev.value in CONTINUES_AFTER and
                    not (prev.kind == "kw" and prev.value not in ("and", "or", "not", "in", "is"))):
                continue
            # Look past blank lines for a leading . or |>.
            j = index + 1
            while j < len(tokens) and tokens[j].kind == "nl":
                j += 1
            nxt = tokens[j] if j < len(tokens) else None
            if nxt is not None and nxt.kind == "op" and nxt.value in CONTINUES_BEFORE:
                continue
        out.append(token)
    return out
