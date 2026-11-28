"""PyCmd source -> a tree of Nodes. See pcmd_compiler for what each one means."""

from __future__ import annotations

from .pcmd_lexer import PcmdSyntaxError, Token, tokenize


class Node:
    __slots__ = ("kind", "line", "f")

    def __init__(self, kind, line, **fields):
        self.kind = kind
        self.line = line
        self.f = fields

    def __getattr__(self, name):
        try:
            return self.f[name]
        except KeyError:
            raise AttributeError(name) from None

    def __repr__(self):
        return f"{self.kind}({', '.join(f'{k}={v!r}' for k, v in self.f.items())})"


_OTHER_WORDS = {
    "def": "PyCmd writes fn for functions: fn name(x) { ... }",
    "function": "PyCmd writes fn for functions: fn name(x) { ... }",
    "func": "PyCmd writes fn for functions: fn name(x) { ... }",
    "class": "PyCmd writes struct for types: struct Name { field: int }",
    "import": "PyCmd writes use for libraries: use math",
    "elsif": "PyCmd writes elif", "elseif": "PyCmd writes elif",
    "switch": "PyCmd writes match: match value { 1 => ..., _ => ... }",
    "int": "PyCmd puts the type after the name: let n: int = 5",
    "string": "PyCmd puts the type after the name: let s: str = \"hi\"",
    "auto": "PyCmd writes let (or var to change it later): let n = 5",
}

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "//=", "**="}
COMPARE = {"==", "!=", "<", "<=", ">", ">="}

# Binding power of each infix operator (higher binds tighter).
INFIX = {
    "?": 2, "??": 3, "|>": 4, "or": 5, "||": 5, "and": 6, "&&": 6,
    "==": 8, "!=": 8, "<": 8, "<=": 8, ">": 8, ">=": 8, "in": 8, "not": 8, "is": 8,
    "..": 9, "..=": 9, "+": 10, "-": 10, "*": 11, "/": 11, "//": 11, "%": 11, "**": 13,
    "(": 14, "[": 14, ".": 14, "?.": 14,
}
PREFIX_BP = {"-": 12, "!": 7, "not": 7, "+": 12}


class Parser:
    def __init__(self, source: str, line_offset: int = 0):
        self.tokens = tokenize(source)
        if line_offset:
            for t in self.tokens:
                t.line += line_offset
        self.i = 0

    # -- token helpers -----------------------------------------------------
    @property
    def tok(self) -> Token:
        return self.tokens[self.i]

    def peek(self, k=1) -> Token:
        j = min(self.i + k, len(self.tokens) - 1)
        return self.tokens[j]

    def advance(self) -> Token:
        t = self.tokens[self.i]
        if self.i < len(self.tokens) - 1:
            self.i += 1
        return t

    def error(self, message, token=None):
        token = token or self.tok
        raise PcmdSyntaxError(message, token.line, token.col)

    def describe(self, t: Token) -> str:
        if t.kind == "eof":
            return "the end of the file"
        if t.kind == "nl":
            return "the end of the line"
        if t.kind == "str":
            return "a string"
        if t.kind == "num":
            return f"the number {t.value}"
        return f"'{t.value}'"

    def expect_op(self, op, what=""):
        if not self.tok.is_op(op):
            hint = f" {what}" if what else ""
            self.error(f"expected '{op}'{hint}, found {self.describe(self.tok)}")
        return self.advance()

    def expect_name(self, what="a name"):
        t = self.tok
        if t.kind != "name":
            if t.kind == "kw":
                self.error(f"'{t.value}' is a keyword and cannot be used as {what}")
            self.error(f"expected {what}, found {self.describe(t)}")
        if t.value.startswith("__") or t.value.startswith("_pc_"):
            self.error(f"names cannot start with {'__' if t.value.startswith('__') else '_pc_'}")
        return self.advance()

    def skip_nl(self):
        while self.tok.kind == "nl":
            self.advance()

    def end_statement(self):
        t = self.tok
        if t.kind == "nl":
            self.skip_nl()
            return
        if t.kind == "eof" or t.is_op("}"):
            return
        self.error(f"expected the end of the statement, found {self.describe(t)}")

    def peek_past_nl(self) -> Token:
        j = self.i
        while self.tokens[j].kind == "nl":
            j += 1
        return self.tokens[j]

    def skip_nl_if_then(self, *words):
        """Skips newlines only when what follows them continues this statement
        (else, elif, catch, finally)."""
        t = self.peek_past_nl()
        if t.is_kw(*words):
            self.skip_nl()
            return True
        return False

    # -- program and blocks ------------------------------------------------
    def program(self):
        body = []
        self.skip_nl()
        while self.tok.kind != "eof":
            body.append(self.statement())
            self.end_statement()
        return Node("program", 1, body=body)

    def block(self, what="here"):
        start = self.tok
        if not self.tok.is_op("{"):
            self.error(f"expected '{{' to start a block {what}, found {self.describe(self.tok)}")
        self.advance()
        body = []
        self.skip_nl()
        while not self.tok.is_op("}"):
            if self.tok.kind == "eof":
                self.error(f"the block opened on line {start.line} is never closed - "
                           "a '}' is missing", start)
            body.append(self.statement())
            self.end_statement()
        self.advance()
        return body

    # -- statements --------------------------------------------------------
    def statement(self):
        t = self.tok
        if t.is_kw("pub"):
            self.advance()
            t = self.tok
        if t.kind == "name" and t.value in _OTHER_WORDS and self.peek().kind == "name":
            self.error(_OTHER_WORDS[t.value])
        if t.kind == "kw":
            handler = getattr(self, f"st_{t.value}", None)
            if handler is not None:
                # `fn(` at the start of a statement is a lambda being called,
                # not a declaration; `match` and `if` are always statements here.
                if not (t.value == "fn" and self.peek().is_op("(")):
                    return handler()
        expr = self.expression()
        if self.tok.is_op(","):
            items = [expr]
            while self.tok.is_op(","):
                self.advance()
                items.append(self.expression())
            expr = Node("tuple", t.line, items=items)
            if not self.tok.is_op("="):
                self.error("a list of names like a, b needs = after it: a, b = b, a")
        if self.tok.kind == "op" and self.tok.value in ASSIGN_OPS:
            op = self.advance().value
            self._check_target(expr)
            value = self.expression()
            if self.tok.is_op(","):
                items = [value]
                while self.tok.is_op(","):
                    self.advance()
                    items.append(self.expression())
                value = Node("tuple", t.line, items=items)
            return Node("assign", t.line, target=expr, op=op, value=value)
        return Node("expr", t.line, expr=expr)

    def _check_target(self, node):
        if node.kind in ("name", "attr", "index"):
            return
        if node.kind == "tuple" and all(e.kind in ("name", "attr", "index") for e in node.items):
            return
        if node.kind == "self":
            self.error("cannot assign to self")
        self.error("the left side of = must be a name, a field (a.b) or an item (a[i])")

    def st_let(self, mutable=False):
        t = self.advance()
        kind = t.value
        mutable = kind == "var"
        names = []
        type_ = None
        if self.tok.is_op("(") or self.tok.is_op("["):
            close = ")" if self.tok.value == "(" else "]"
            self.advance()
            while not self.tok.is_op(close):
                if self.tok.is_op("..."):
                    self.advance()
                    names.append("..." + self.expect_name().value)
                else:
                    names.append(self.expect_name().value)
                if not self.tok.is_op(","):
                    break
                self.advance()
            self.expect_op(close)
            unpack = True
        else:
            names.append(self.expect_name().value)
            unpack = False
            while self.tok.is_op(","):
                self.advance()
                names.append(self.expect_name().value)
                unpack = True
            if not unpack and self.tok.is_op(":"):
                self.advance()
                type_ = self.type_expr()
        if not self.tok.is_op("="):
            if mutable and not unpack:
                return Node("let", t.line, names=names, mutable=True, type=type_, value=None,
                            unpack=False)
            self.error(f"'{kind} {names[0]}' needs a value: {kind} {names[0]} = ..." +
                       ("" if mutable else "  (a var can start empty: var x: int)"))
        self.advance()
        value = self.expression()
        if unpack and self.tok.is_op(","):
            items = [value]
            while self.tok.is_op(","):
                self.advance()
                items.append(self.expression())
            value = Node("tuple", t.line, items=items)
        return Node("let", t.line, names=names, mutable=mutable, type=type_, value=value,
                    unpack=unpack)

    st_var = st_let
    st_const = st_let

    def params(self):
        self.expect_op("(")
        params = []
        seen_default = False
        while not self.tok.is_op(")"):
            self.skip_nl()
            if self.tok.is_op(")"):
                break
            rest = False
            if self.tok.is_op("..."):
                self.advance()
                rest = True
            if self.tok.is_kw("self"):
                name = self.advance().value
            else:
                name = self.expect_name("a parameter name").value
            type_ = None
            default = None
            if self.tok.is_op(":"):
                self.advance()
                type_ = self.type_expr()
            if self.tok.is_op("="):
                self.advance()
                default = self.expression()
                seen_default = True
            elif seen_default and not rest:
                self.error(f"parameter '{name}' needs a default, like the ones before it")
            params.append({"name": name, "type": type_, "default": default, "rest": rest})
            self.skip_nl()
            if not self.tok.is_op(","):
                break
            self.advance()
        self.skip_nl()
        self.expect_op(")", "to close the parameters")
        return params

    def st_fn(self):
        t = self.advance()
        name = self.expect_name("a function name").value
        params = self.params()
        ret = None
        if self.tok.is_op("->"):
            self.advance()
            ret = self.type_expr()
        if self.tok.is_op("=>"):
            self.advance()
            line = self.tok.line
            body = [Node("return", line, value=self.expression())]
        else:
            body = self.block(f"for fn {name}")
        return Node("fn", t.line, name=name, params=params, ret=ret, body=body)

    def st_struct(self):
        t = self.advance()
        name = self.expect_name("a struct name").value
        parent = None
        if self.tok.is_kw("extends") or self.tok.is_op(":"):
            self.advance()
            parent = self.expect_name("the struct it extends").value
        self.expect_op("{", f"to start struct {name}")
        fields, methods = [], []
        self.skip_nl()
        while not self.tok.is_op("}"):
            if self.tok.kind == "eof":
                self.error(f"struct {name} is never closed - a '}}' is missing", t)
            if self.tok.is_kw("pub"):
                self.advance()
            if self.tok.is_kw("fn"):
                methods.append(self.st_fn())
            else:
                ft = self.expect_name("a field name")
                ftype = None
                default = None
                if self.tok.is_op(":"):
                    self.advance()
                    ftype = self.type_expr()
                if self.tok.is_op("="):
                    self.advance()
                    default = self.expression()
                fields.append({"name": ft.value, "type": ftype, "default": default,
                               "line": ft.line})
            if self.tok.is_op(","):
                self.advance()
            self.skip_nl()
        self.advance()
        return Node("struct", t.line, name=name, parent=parent, fields=fields, methods=methods)

    def st_enum(self):
        t = self.advance()
        name = self.expect_name("an enum name").value
        self.expect_op("{", f"to start enum {name}")
        variants = []
        self.skip_nl()
        while not self.tok.is_op("}"):
            v = self.expect_name("a variant name").value
            value = None
            if self.tok.is_op("="):
                self.advance()
                value = self.expression()
            variants.append((v, value))
            if self.tok.is_op(","):
                self.advance()
            self.skip_nl()
        self.advance()
        if not variants:
            self.error(f"enum {name} has no variants", t)
        return Node("enum", t.line, name=name, variants=variants)

    def st_if(self):
        t = self.advance()
        branches = []
        cond = self.expression()
        branches.append((cond, self.block("after if")))
        other = None
        while self.skip_nl_if_then("elif", "else"):
            if self.tok.is_kw("elif"):
                self.advance()
                cond = self.expression()
                branches.append((cond, self.block("after elif")))
                continue
            self.advance()  # else
            if self.tok.is_kw("if"):
                self.advance()
                cond = self.expression()
                branches.append((cond, self.block("after else if")))
                continue
            other = self.block("after else")
            break
        return Node("if", t.line, branches=branches, other=other)

    def st_while(self):
        t = self.advance()
        cond = self.expression()
        return Node("while", t.line, cond=cond, body=self.block("after while"))

    def st_loop(self):
        t = self.advance()
        return Node("while", t.line, cond=Node("const", t.line, value=True),
                    body=self.block("after loop"))

    def st_for(self):
        t = self.advance()
        names = [self.expect_name("a loop variable").value]
        while self.tok.is_op(","):
            self.advance()
            names.append(self.expect_name("a loop variable").value)
        if not self.tok.is_kw("in"):
            self.error(f"expected 'in' after the loop variable, found {self.describe(self.tok)}"
                       " - write: for x in list { ... }")
        self.advance()
        it = self.expression()
        return Node("for", t.line, names=names, iter=it, body=self.block("after for"))

    def st_return(self):
        t = self.advance()
        if self.tok.kind in ("nl", "eof") or self.tok.is_op("}"):
            return Node("return", t.line, value=None)
        return Node("return", t.line, value=self.expression())

    def st_break(self):
        return Node("break", self.advance().line)

    def st_continue(self):
        return Node("continue", self.advance().line)

    def st_throw(self):
        t = self.advance()
        return Node("throw", t.line, value=self.expression())

    def st_assert(self):
        t = self.advance()
        cond = self.expression()
        message = None
        if self.tok.is_op(","):
            self.advance()
            message = self.expression()
        return Node("assert", t.line, cond=cond, message=message)

    def st_test(self):
        t = self.advance()
        if self.tok.kind != "str" or any(isinstance(p, tuple) for p in self.tok.value):
            self.error('a test needs a plain name: test "adds numbers" { ... }')
        name = "".join(self.advance().value)
        return Node("test", t.line, name=name, body=self.block("for the test"))

    def st_try(self):
        t = self.advance()
        body = self.block("after try")
        name = None
        handler = None
        final = None
        if self.skip_nl_if_then("catch"):
            self.advance()
            if self.tok.kind == "name":
                name = self.expect_name().value
            handler = self.block("after catch")
        if self.skip_nl_if_then("finally"):
            self.advance()
            final = self.block("after finally")
        if handler is None and final is None:
            self.error("try needs a catch or a finally after it", t)
        return Node("try", t.line, body=body, name=name, handler=handler, final=final)

    def st_use(self):
        t = self.advance()
        if self.tok.kind == "str":
            path = "".join(p for p in self.advance().value if isinstance(p, str))
            if not self.tok.is_kw("as"):
                self.error(f'a file needs a name: use "{path}" as name')
            self.advance()
            alias = self.expect_name().value
            return Node("use", t.line, module=None, path=path, alias=alias, names=None)
        parts = [self.expect_name("a library name").value]
        while self.tok.is_op("."):
            self.advance()
            if self.tok.is_op("{"):
                break
            parts.append(self.expect_name().value)
        names = None
        if self.tok.is_op("{"):
            self.advance()
            names = []
            while not self.tok.is_op("}"):
                names.append(self.expect_name().value)
                if not self.tok.is_op(","):
                    break
                self.advance()
            self.expect_op("}")
        alias = parts[-1]
        if self.tok.is_kw("as"):
            self.advance()
            alias = self.expect_name().value
        return Node("use", t.line, module=".".join(parts), path=None, alias=alias, names=names)

    def st_match(self):
        node = self.match_expr()
        return Node("match_stmt", node.line, subject=node.subject, arms=node.arms)

    # -- match -------------------------------------------------------------
    def match_expr(self):
        t = self.advance()
        subject = self.expression()
        self.expect_op("{", "to start the match arms")
        arms = []
        self.skip_nl()
        while not self.tok.is_op("}"):
            if self.tok.kind == "eof":
                self.error("this match is never closed - a '}' is missing", t)
            line = self.tok.line
            pattern = self.pattern()
            guard = None
            if self.tok.is_kw("if"):
                self.advance()
                guard = self.expression()
            self.expect_op("=>", "after the pattern")
            if self.tok.is_op("{") and not self._looks_like_map():
                body = self.block("for the match arm")
                arms.append({"pattern": pattern, "guard": guard, "body": body, "expr": None,
                             "line": line})
            else:
                start = self.tok
                if start.kind == "kw" and start.value in ("return", "break", "continue",
                                                           "throw", "print"):
                    stmt = self.statement()
                    arms.append({"pattern": pattern, "guard": guard, "body": [stmt],
                                 "expr": None, "line": line})
                else:
                    expr = self.expression()
                    if self.tok.kind == "op" and self.tok.value in ASSIGN_OPS:
                        op = self.advance().value
                        self._check_target(expr)
                        stmt = Node("assign", line, target=expr, op=op, value=self.expression())
                        arms.append({"pattern": pattern, "guard": guard, "body": [stmt],
                                     "expr": None, "line": line})
                    else:
                        arms.append({"pattern": pattern, "guard": guard, "body": None,
                                     "expr": expr, "line": line})
            if self.tok.is_op(","):
                self.advance()
            self.skip_nl()
        self.advance()
        if not arms:
            self.error("a match needs at least one arm: pattern => result", t)
        return Node("match", t.line, subject=subject, arms=arms)

    def _looks_like_map(self):
        # { "a": 1 } or {} as an arm's value, not a block
        nxt = self.peek()
        if nxt.is_op("}"):
            return True
        return nxt.kind in ("str", "num") and self.peek(2).is_op(":")

    def pattern(self):
        alts = [self.pattern_one()]
        while self.tok.is_op("|"):
            self.advance()
            alts.append(self.pattern_one())
        if len(alts) == 1:
            return alts[0]
        return ("or", alts)

    def _literal_value(self):
        t = self.tok
        if t.kind == "num":
            self.advance()
            return t.value
        if t.is_op("-") and self.peek().kind == "num":
            self.advance()
            return -self.advance().value
        if t.kind == "str":
            if any(isinstance(p, tuple) for p in t.value):
                self.error("a pattern cannot contain {interpolation}")
            self.advance()
            return "".join(t.value)
        if t.is_kw("true"):
            self.advance()
            return True
        if t.is_kw("false"):
            self.advance()
            return False
        if t.is_kw("nil"):
            self.advance()
            return None
        return _NO_LITERAL

    def pattern_one(self):
        t = self.tok
        value = self._literal_value()
        if value is not _NO_LITERAL:
            if self.tok.is_op("..", "..="):
                inclusive = self.advance().value == "..="
                hi = self._literal_value()
                if hi is _NO_LITERAL:
                    self.error("a range pattern needs two plain values, like 1..=9")
                return ("range", value, hi, inclusive)
            return ("lit", value)
        if t.kind == "name" and t.value == "_":
            self.advance()
            return ("any",)
        if t.is_kw("is"):
            self.advance()
            return ("type", self.type_expr())
        if t.is_op("[") or t.is_op("("):
            close = "]" if t.value == "[" else ")"
            self.advance()
            items = []
            rest = None
            while not self.tok.is_op(close):
                if self.tok.is_op("..."):
                    self.advance()
                    rest = self.expect_name().value if self.tok.kind == "name" else "_"
                    items.append(("rest", rest))
                else:
                    items.append(self.pattern())
                if not self.tok.is_op(","):
                    break
                self.advance()
            self.expect_op(close)
            return ("list", items)
        if t.kind == "name":
            name = self.advance().value
            if self.tok.is_op("."):
                parts = [name]
                while self.tok.is_op("."):
                    self.advance()
                    parts.append(self.expect_name().value)
                return ("value", parts)
            if self.tok.is_op("("):
                # Point(x, y) - a struct, field by field in order
                self.advance()
                subs = []
                while not self.tok.is_op(")"):
                    if self.tok.kind == "name" and self.peek().is_op(":"):
                        key = self.advance().value
                        self.advance()
                        subs.append((key, self.pattern()))
                    else:
                        subs.append((None, self.pattern()))
                    if not self.tok.is_op(","):
                        break
                    self.advance()
                self.expect_op(")")
                return ("struct", name, subs)
            return ("bind", name, t.line)
        self.error(f"this cannot start a pattern: {self.describe(t)}")

    # -- types -------------------------------------------------------------
    def type_expr(self, optional=True):
        options = [self.type_one(optional)]
        while self.tok.is_op("|") and self.peek().kind in ("name", "kw"):
            self.advance()
            options.append(self.type_one(optional))
        return options[0] if len(options) == 1 else ("union", options)

    def type_one(self, optional=True):
        t = self.tok
        if t.kind == "name" or t.is_kw("fn", "nil"):
            self.advance()
            name = t.value
            args = []
            if self.tok.is_op("["):
                self.advance()
                while not self.tok.is_op("]"):
                    args.append(self.type_expr())
                    if not self.tok.is_op(","):
                        break
                    self.advance()
                self.expect_op("]")
            if name == "fn" and self.tok.is_op("("):
                # fn(int) -> int: the shape is documentation only
                depth = 0
                while True:
                    if self.tok.is_op("("):
                        depth += 1
                    elif self.tok.is_op(")"):
                        depth -= 1
                        if depth == 0:
                            self.advance()
                            break
                    elif self.tok.kind == "eof":
                        self.error("fn( ... ) type is not closed")
                    self.advance()
                if self.tok.is_op("->"):
                    self.advance()
                    self.type_expr()
            result = ("type", name, args, t.line)
            if optional and self.tok.is_op("?"):
                self.advance()
                result = ("optional", result)
            return result
        self.error(f"expected a type (int, str, list, ...), found {self.describe(t)}")

    # -- expressions -------------------------------------------------------
    def expression(self, bp=0):
        t = self.tok
        left = self.prefix()
        while True:
            t = self.tok
            if t.kind == "op":
                op = t.value
            elif t.is_kw("and", "or", "in", "is", "not"):
                op = t.value
            else:
                break
            power = INFIX.get(op)
            if power is None or power <= bp:
                break
            if op == "not":
                if not self.peek().is_kw("in"):
                    break
            left = self.infix(left, op, power)
        return left

    def prefix(self):
        t = self.tok
        line = t.line
        if t.kind == "num":
            self.advance()
            return Node("const", line, value=t.value)
        if t.kind == "str":
            self.advance()
            return self.string(t)
        if t.kind == "name":
            self.advance()
            if t.value.startswith("__") or t.value.startswith("_pc_"):
                self.error("names cannot start with __ or _pc_", t)
            return Node("name", line, name=t.value)
        if t.kind == "kw":
            v = t.value
            if v in ("true", "false"):
                self.advance()
                return Node("const", line, value=v == "true")
            if v == "nil":
                self.advance()
                return Node("const", line, value=None)
            if v == "self":
                self.advance()
                return Node("self", line)
            if v == "not":
                self.advance()
                return Node("unary", line, op="not", operand=self.expression(PREFIX_BP["not"]))
            if v == "fn":
                return self.lambda_fn()
            if v == "match":
                return self.match_expr()
            if v == "if":
                self.error("if is a statement here - for a value, write cond ? a : b")
            self.error(f"'{v}' cannot be used inside an expression")
        if t.kind == "op":
            v = t.value
            if v in ("-", "+"):
                self.advance()
                operand = self.expression(PREFIX_BP[v])
                if v == "-" and operand.kind == "const" and isinstance(operand.value, (int, float)) \
                        and not isinstance(operand.value, bool):
                    return Node("const", line, value=-operand.value)
                return Node("unary", line, op=v, operand=operand)
            if v == "!":
                self.advance()
                return Node("unary", line, op="not", operand=self.expression(PREFIX_BP["!"]))
            if v == "(":
                self.advance()
                self.skip_nl()
                if self.tok.is_op(")"):
                    self.advance()
                    return Node("tuple", line, items=[])
                first = self.expression()
                self.skip_nl()
                if self.tok.is_op(","):
                    items = [first]
                    while self.tok.is_op(","):
                        self.advance()
                        self.skip_nl()
                        if self.tok.is_op(")"):
                            break
                        items.append(self.expression())
                        self.skip_nl()
                    self.expect_op(")")
                    return Node("tuple", line, items=items)
                self.expect_op(")", "to close the bracket")
                return Node("group", line, expr=first)
            if v == "[":
                return self.list_literal()
            if v == "{":
                return self.map_literal()
            if v in ("|", "||"):
                return self.lambda_bar()
            if v == "...":
                self.error("... spreads a list into a call or a list: f(...xs), [...a, ...b]")
        if t.kind in ("nl", "eof"):
            self.error("an expression is missing here - the line stops too early")
        self.error(f"unexpected {self.describe(t)}")

    def string(self, t):
        parts = []
        for part in t.value:
            if isinstance(part, str):
                parts.append(part)
                continue
            _, text, line = part
            spec = None
            # {value:.2f} - a format spec after the last top-level colon,
            # unless a ? before it makes it part of a ternary.
            depth = 0
            question = False
            cut = -1
            in_str = None
            for k, c in enumerate(text):
                if in_str:
                    if c == in_str:
                        in_str = None
                    continue
                if c in "\"'":
                    in_str = c
                elif c in "([{":
                    depth += 1
                elif c in ")]}":
                    depth -= 1
                elif depth == 0 and c == "?" and text[k + 1:k + 2] not in (".", "?") and \
                        text[k - 1:k] != "?":
                    question = True
                elif depth == 0 and c == ":" and not question:
                    cut = k
            if cut >= 0:
                spec = text[cut + 1:]
                text = text[:cut]
            sub = Parser(text, line - 1)
            sub.skip_nl()
            expr = sub.expression()
            sub.skip_nl()
            if sub.tok.kind != "eof":
                raise PcmdSyntaxError(f"in a string, {{{text}}} is not one expression", line)
            parts.append(("expr", expr, spec))
        if len(parts) == 1 and isinstance(parts[0], str):
            return Node("const", t.line, value=parts[0])
        return Node("interp", t.line, parts=parts)

    def list_literal(self):
        t = self.advance()
        items = []
        self.skip_nl()
        if self.tok.is_op("]"):
            self.advance()
            return Node("list", t.line, items=[])
        first = self.list_item()
        self.skip_nl()
        if self.tok.is_kw("for"):
            loops, cond = self.comprehension_tail()
            self.skip_nl()
            self.expect_op("]")
            return Node("listcomp", t.line, expr=first, loops=loops, cond=cond)
        items.append(first)
        while self.tok.is_op(","):
            self.advance()
            self.skip_nl()
            if self.tok.is_op("]"):
                break
            items.append(self.list_item())
            self.skip_nl()
        self.expect_op("]", "to close the list")
        return Node("list", t.line, items=items)

    def list_item(self):
        if self.tok.is_op("..."):
            line = self.advance().line
            return Node("spread", line, expr=self.expression())
        return self.expression()

    def comprehension_tail(self):
        loops = []
        cond = None
        while self.tok.is_kw("for"):
            self.advance()
            names = [self.expect_name("a loop variable").value]
            while self.tok.is_op(","):
                self.advance()
                names.append(self.expect_name().value)
            if not self.tok.is_kw("in"):
                self.error("expected 'in' in the comprehension")
            self.advance()
            loops.append((names, self.expression(INFIX["?"])))
            self.skip_nl()
        if self.tok.is_kw("if"):
            self.advance()
            cond = self.expression()
        return loops, cond

    def map_literal(self):
        t = self.advance()
        self.skip_nl()
        pairs = []
        if self.tok.is_op("}"):
            self.advance()
            return Node("map", t.line, pairs=[])
        while True:
            self.skip_nl()
            if self.tok.is_op("}"):
                break
            if self.tok.is_op("..."):
                self.advance()
                pairs.append((None, self.expression()))
            else:
                # {name: 1} - a bare name as a key is the string "name"
                bare = None
                if self.tok.kind == "name" and self.peek().is_op(":"):
                    bare = self.tok
                    key = Node("const", self.tok.line, value=self.advance().value)
                else:
                    key = self.expression()
                self.skip_nl()
                self.expect_op(":", "between a key and its value")
                self.skip_nl()
                value = self.expression()
                self.skip_nl()
                if self.tok.is_kw("for") and not pairs:
                    if bare is not None:
                        key = Node("name", bare.line, name=bare.value)
                    loops, cond = self.comprehension_tail()
                    self.skip_nl()
                    self.expect_op("}")
                    return Node("mapcomp", t.line, key=key, value=value, loops=loops, cond=cond)
                pairs.append((key, value))
            self.skip_nl()
            if not self.tok.is_op(","):
                break
            self.advance()
        self.skip_nl()
        self.expect_op("}", "to close the map")
        return Node("map", t.line, pairs=pairs)

    def lambda_fn(self):
        t = self.advance()
        params = self.params()
        ret = None
        if self.tok.is_op("->"):
            self.advance()
            ret = self.type_expr()
        if self.tok.is_op("=>"):
            self.advance()
            return Node("lambda", t.line, params=params, ret=ret, expr=self.expression(), body=None)
        return Node("lambda", t.line, params=params, ret=ret, expr=None,
                    body=self.block("for the fn"))

    def lambda_bar(self):
        t = self.advance()
        params = []
        if t.value == "|":
            while not self.tok.is_op("|"):
                name = self.expect_name("a parameter name").value
                type_ = None
                if self.tok.is_op(":"):
                    self.advance()
                    type_ = self.type_one()
                params.append({"name": name, "type": type_, "default": None, "rest": False})
                if not self.tok.is_op(","):
                    break
                self.advance()
            self.expect_op("|", "to close the parameters")
        if self.tok.is_op("{"):
            return Node("lambda", t.line, params=params, ret=None, expr=None,
                        body=self.block("for the fn"))
        return Node("lambda", t.line, params=params, ret=None, expr=self.expression(INFIX["?"] - 1),
                    body=None)

    def call_args(self):
        args, kwargs = [], []
        self.skip_nl()
        while not self.tok.is_op(")"):
            if self.tok.is_op("..."):
                line = self.advance().line
                args.append(Node("spread", line, expr=self.expression()))
            elif self.tok.kind == "name" and self.peek().is_op(":"):
                key = self.advance().value
                self.advance()
                kwargs.append((key, self.expression()))
            else:
                if kwargs:
                    self.error("plain arguments go before named ones (name: value)")
                args.append(self.expression())
            self.skip_nl()
            if not self.tok.is_op(","):
                break
            self.advance()
            self.skip_nl()
        self.expect_op(")", "to close the call")
        return args, kwargs

    def infix(self, left, op, power):
        t = self.advance()
        line = t.line
        if op == "(":
            args, kwargs = self.call_args()
            return Node("call", line, func=left, args=args, kwargs=kwargs)
        if op == "[":
            self.skip_nl()
            index = self.slice_or_index()
            self.skip_nl()
            self.expect_op("]", "to close the index")
            return Node("index", line, obj=left, index=index)
        if op in (".", "?."):
            if self.tok.kind == "num" and isinstance(self.tok.value, int) and op == ".":
                n = self.advance().value
                return Node("index", line, obj=left, index=Node("const", line, value=n))
            name_tok = self.tok
            if name_tok.kind not in ("name", "kw"):
                self.error(f"expected a field or method name after '{op}'")
            self.advance()
            name = name_tok.value
            if name.startswith("_"):
                self.error("fields starting with _ cannot be reached from outside", name_tok)
            return Node("attr" if op == "." else "optattr", line, obj=left, name=name)
        if op == "?":
            self.skip_nl()
            a = self.expression()
            self.skip_nl()
            self.expect_op(":", "in cond ? a : b")
            self.skip_nl()
            b = self.expression(power - 1)
            return Node("ternary", line, cond=left, a=a, b=b)
        if op == "not":
            self.advance()  # in
            right = self.expression(power)
            return Node("binary", line, op="not in", left=left, right=right)
        if op == "is":
            negate = False
            if self.tok.is_kw("not"):
                self.advance()
                negate = True
            type_ = self.type_expr(optional=False)
            return Node("is", line, value=left, type=type_, negate=negate)
        if op in ("..", "..="):
            right = self.expression(power)
            return Node("range", line, lo=left, hi=right, inclusive=op == "..=")
        if op == "|>":
            right = self.expression(power)
            return Node("pipe", line, value=left, func=right)
        if op == "**":
            right = self.expression(power - 1)
            return Node("binary", line, op="**", left=left, right=right)
        right = self.expression(power)
        if op in ("&&", "and"):
            return Node("logic", line, op="and", left=left, right=right)
        if op in ("||", "or"):
            return Node("logic", line, op="or", left=left, right=right)
        if op == "??":
            return Node("coalesce", line, left=left, right=right)
        if op in COMPARE and left.kind == "compare":
            left.f["ops"].append(op)
            left.f["items"].append(right)
            return left
        if op in COMPARE:
            return Node("compare", line, ops=[op], items=[left, right])
        return Node("binary", line, op=op, left=left, right=right)

    def slice_or_index(self):
        line = self.tok.line
        parts = [None, None, None]
        k = 0
        is_slice = False
        while True:
            if self.tok.is_op(":"):
                self.advance()
                is_slice = True
                k += 1
                if k > 2:
                    self.error("a slice has at most two colons: [start:stop:step]")
                continue
            if self.tok.is_op("]"):
                break
            parts[k] = self.expression()
            if not self.tok.is_op(":"):
                break
        if not is_slice:
            if parts[0] is None:
                self.error("[] needs an index inside it")
            return parts[0]
        return Node("slice", line, start=parts[0], stop=parts[1], step=parts[2])


class _NoLiteral:
    pass


_NO_LITERAL = _NoLiteral()


def parse(source: str) -> Node:
    return Parser(source).program()
