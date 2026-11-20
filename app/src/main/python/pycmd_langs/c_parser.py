"""Recursive-descent parser for the C interpreter.

Produces a small tuple-based AST. Tuples rather than classes because the tree
is walked far more often than it is built, and a tuple tag dispatches in the
evaluator with no attribute lookups.

Precedence follows the C standard, lowest binding first:
    assignment  ?:  ||  &&  |  ^  &  == !=  < > <= >=  << >>  + -  * / %
then the unary operators, then postfix (call, index, member, ++/--).
"""

from __future__ import annotations

from .c_lexer import CSyntaxError, Token, tokenize

TYPE_KEYWORDS = {
    "void", "char", "short", "int", "long", "float", "double",
    "signed", "unsigned", "_Bool", "struct", "union", "enum",
    "const", "volatile", "static", "extern", "register", "auto",
}

# Binary operators grouped by precedence, loosest first.
BINARY_LEVELS = [
    ["||"],
    ["&&"],
    ["|"],
    ["^"],
    ["&"],
    ["==", "!="],
    ["<", ">", "<=", ">="],
    ["<<", ">>"],
    ["+", "-"],
    ["*", "/", "%"],
]

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}


class CType:
    """A parsed type: a base name, a pointer depth, and optional array sizes."""

    __slots__ = ("base", "pointer", "array", "struct_name")

    def __init__(self, base: str, pointer: int = 0, array=None, struct_name: str = "") -> None:
        self.base = base
        self.pointer = pointer
        self.array = array or []          # list of dimension expressions (or None)
        self.struct_name = struct_name

    @property
    def is_pointer(self) -> bool:
        return self.pointer > 0

    @property
    def is_array(self) -> bool:
        return bool(self.array)

    @property
    def is_float(self) -> bool:
        return self.pointer == 0 and not self.array and self.base in ("float", "double")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CType({self.base}{'*' * self.pointer}{'[]' * len(self.array)})"


class Parser:
    def __init__(self, tokens: list) -> None:
        self.tokens = tokens
        self.pos = 0
        # Names introduced by typedef, so `Point p;` parses as a declaration.
        self.typedefs: dict[str, CType] = {}
        self.structs: dict[str, list] = {}
        self.unions: set = set()

    # ------------------------------------------------------------------ tokens

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        index = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def advance(self) -> Token:
        token = self.tokens[self.pos]
        if token.kind != "eof":
            self.pos += 1
        return token

    def at(self, kind: str, value=None) -> bool:
        token = self.current
        return token.kind == kind and (value is None or token.value == value)

    def at_op(self, *values) -> bool:
        return self.current.kind == "op" and self.current.value in values

    def accept(self, kind: str, value=None):
        if self.at(kind, value):
            return self.advance()
        return None

    def expect(self, kind: str, value=None) -> Token:
        if self.at(kind, value):
            return self.advance()
        wanted = value if value is not None else kind
        got = self.current.value if self.current.kind != "eof" else "end of file"
        raise CSyntaxError(f"expected {wanted!r} but found {got!r}", self.current.line)

    # ------------------------------------------------------------ declarations

    def looks_like_type(self) -> bool:
        token = self.current
        if token.kind == "kw" and token.value in TYPE_KEYWORDS:
            return True
        return token.kind == "id" and token.value in self.typedefs

    def parse_type(self) -> CType:
        """Reads a type specifier, including struct bodies and typedef names."""
        base_parts = []
        struct_name = ""

        while True:
            token = self.current
            if token.kind == "kw" and token.value in ("const", "volatile", "static", "extern", "register", "auto"):
                self.advance()
                continue
            if token.kind == "kw" and token.value in ("struct", "union"):
                is_union = token.value == "union"
                self.advance()
                name = ""
                if self.at("id"):
                    name = self.advance().value
                if self.at_op("{"):
                    fields = self.parse_struct_body()
                    if not name:
                        name = f"__anon{len(self.structs)}"
                    self.structs[name] = fields
                    if is_union:
                        # A union is a struct whose fields share one place.
                        # The interpreter needs to know which names those are.
                        self.unions.add(name)
                elif name not in self.structs:
                    # Forward reference; the body may come later.
                    self.structs.setdefault(name, [])
                base_parts.append("struct")
                struct_name = name
                break
            if token.kind == "kw" and token.value == "enum":
                self.advance()
                if self.at("id"):
                    self.advance()
                if self.at_op("{"):
                    self.parse_enum_body()
                base_parts.append("int")
                break
            if token.kind == "kw" and token.value in TYPE_KEYWORDS:
                base_parts.append(self.advance().value)
                continue
            if token.kind == "id" and token.value in self.typedefs and not base_parts:
                named = self.typedefs[self.advance().value]
                return CType(named.base, named.pointer, list(named.array), named.struct_name)
            break

        if not base_parts:
            raise CSyntaxError("expected a type", self.current.line)

        base = " ".join(p for p in base_parts if p not in ("signed",)) or "int"
        # Normalise the spellings that mean the same storage to the interpreter.
        if base in ("unsigned", "unsigned int", "short", "unsigned short",
                    "long", "long long", "unsigned long", "unsigned long long",
                    "unsigned char", "short int", "long int"):
            base = "int" if "char" not in base else "char"
        if base == "long double":
            base = "double"

        pointer = 0
        while self.at_op("*"):
            self.advance()
            pointer += 1
            while self.current.kind == "kw" and self.current.value in ("const", "volatile"):
                self.advance()

        return CType(base, pointer, struct_name=struct_name)

    def parse_struct_body(self) -> list:
        self.expect("op", "{")
        fields = []
        while not self.at_op("}"):
            field_type = self.parse_type()
            while True:
                name = self.expect("id").value
                this_type = CType(field_type.base, field_type.pointer, [], field_type.struct_name)
                while self.at_op("["):
                    self.advance()
                    size = None if self.at_op("]") else self.parse_expression()
                    self.expect("op", "]")
                    this_type.array.append(size)
                fields.append((name, this_type))
                if not self.accept("op", ","):
                    break
                extra = 0
                while self.at_op("*"):
                    self.advance()
                    extra += 1
                field_type = CType(field_type.base, extra, struct_name=field_type.struct_name)
            self.expect("op", ";")
        self.expect("op", "}")
        return fields

    def parse_enum_body(self) -> None:
        """Enumerators become plain integer constants in the global scope."""
        self.expect("op", "{")
        self.enum_constants = getattr(self, "enum_constants", {})
        next_value = 0
        while not self.at_op("}"):
            name = self.expect("id").value
            if self.accept("op", "="):
                expression = self.parse_conditional()
                value = _constant_value(expression)
                if value is None:
                    raise CSyntaxError(f"enum {name} needs a constant value", self.current.line)
                next_value = value
            self.enum_constants[name] = next_value
            next_value += 1
            if not self.accept("op", ","):
                break
        self.expect("op", "}")

    # ------------------------------------------------------------------- units

    def parse_program(self) -> dict:
        functions = {}
        globals_ = []
        self.enum_constants = getattr(self, "enum_constants", {})

        while not self.at("eof"):
            if self.accept("op", ";"):
                continue

            if self.current.kind == "kw" and self.current.value == "typedef":
                self.advance()
                base = self.parse_type()
                name = self.expect("id").value
                while self.at_op("["):
                    self.advance()
                    if not self.at_op("]"):
                        self.parse_expression()
                    self.expect("op", "]")
                self.typedefs[name] = base
                self.expect("op", ";")
                continue

            if not self.looks_like_type():
                raise CSyntaxError(
                    f"expected a declaration but found {self.current.value!r}",
                    self.current.line,
                )

            declared = self.parse_type()

            # A struct/enum declaration with no declarator: `struct P { .. };`
            if self.at_op(";"):
                self.advance()
                continue

            name_token = self.expect("id")
            name = name_token.value

            if self.at_op("("):
                params, variadic = self.parse_parameters()
                if self.at_op(";"):  # prototype
                    self.advance()
                    continue
                body = self.parse_block()
                functions[name] = {
                    "name": name,
                    "return": declared,
                    "params": params,
                    "variadic": variadic,
                    "body": body,
                    "line": name_token.line,
                }
                continue

            # Global variable, possibly several per declaration.
            while True:
                var_type = CType(declared.base, declared.pointer, [], declared.struct_name)
                while self.at_op("["):
                    self.advance()
                    size = None if self.at_op("]") else self.parse_expression()
                    self.expect("op", "]")
                    var_type.array.append(size)
                init = None
                if self.accept("op", "="):
                    init = self.parse_initializer()
                globals_.append((name, var_type, init, name_token.line))
                if not self.accept("op", ","):
                    break
                extra = 0
                while self.at_op("*"):
                    self.advance()
                    extra += 1
                declared = CType(declared.base, extra, struct_name=declared.struct_name)
                name_token = self.expect("id")
                name = name_token.value
            self.expect("op", ";")

        return {
            "functions": functions,
            "globals": globals_,
            "structs": self.structs,
            "unions": self.unions,
            "enums": self.enum_constants,
            "typedefs": self.typedefs,
        }

    def parse_parameters(self):
        self.expect("op", "(")
        params = []
        variadic = False
        if self.at_op(")"):
            self.advance()
            return params, variadic
        # `f(void)` means no parameters.
        if self.current.kind == "kw" and self.current.value == "void" and self.peek().value == ")":
            self.advance()
            self.advance()
            return params, variadic
        while True:
            if self.at_op("..."):
                self.advance()
                variadic = True
                break
            param_type = self.parse_type()
            if self.at_op("("):
                # `int (*cmp)(int, int)` - a function pointer parameter.
                self.advance()
                self.expect("op", "*")
                param_name = self.advance().value if self.at("id") else ""
                self.expect("op", ")")
                self.skip_parameter_list()
                params.append((param_name, CType("fn", 1)))
                if not self.accept("op", ","):
                    break
                continue
            param_name = self.advance().value if self.at("id") else ""
            while self.at_op("["):
                self.advance()
                if not self.at_op("]"):
                    self.parse_expression()
                self.expect("op", "]")
                param_type = CType(param_type.base, param_type.pointer + 1,
                                   struct_name=param_type.struct_name)
            params.append((param_name, param_type))
            if not self.accept("op", ","):
                break
        self.expect("op", ")")
        return params, variadic

    def parse_initializer(self):
        if self.at_op("{"):
            self.advance()
            items = []
            while not self.at_op("}"):
                items.append(self.parse_initializer())
                if not self.accept("op", ","):
                    break
            self.expect("op", "}")
            return ("initlist", items)
        return self.parse_assignment()

    # -------------------------------------------------------------- statements

    def parse_block(self):
        self.expect("op", "{")
        statements = []
        while not self.at_op("}"):
            if self.at("eof"):
                raise CSyntaxError("unterminated block - missing '}'", self.current.line)
            statements.append(self.parse_statement())
        self.expect("op", "}")
        return ("block", statements)

    def parse_statement(self):
        line = self.current.line

        if self.at_op("{"):
            return self.parse_block()

        if self.accept("op", ";"):
            return ("empty",)

        if self.current.kind == "kw":
            word = self.current.value

            if word == "if":
                self.advance()
                self.expect("op", "(")
                condition = self.parse_expression()
                self.expect("op", ")")
                then_branch = self.parse_statement()
                else_branch = None
                if self.current.kind == "kw" and self.current.value == "else":
                    self.advance()
                    else_branch = self.parse_statement()
                return ("if", condition, then_branch, else_branch, line)

            if word == "while":
                self.advance()
                self.expect("op", "(")
                condition = self.parse_expression()
                self.expect("op", ")")
                return ("while", condition, self.parse_statement(), line)

            if word == "do":
                self.advance()
                body = self.parse_statement()
                if not (self.current.kind == "kw" and self.current.value == "while"):
                    raise CSyntaxError("expected 'while' after do-block", self.current.line)
                self.advance()
                self.expect("op", "(")
                condition = self.parse_expression()
                self.expect("op", ")")
                self.expect("op", ";")
                return ("dowhile", condition, body, line)

            if word == "for":
                self.advance()
                self.expect("op", "(")
                if self.at_op(";"):
                    self.advance()
                    init = None
                elif self.looks_like_type():
                    init = self.parse_declaration_statement()
                else:
                    init = ("expr", self.parse_expression(), line)
                    self.expect("op", ";")
                condition = None if self.at_op(";") else self.parse_expression()
                self.expect("op", ";")
                step = None if self.at_op(")") else self.parse_expression()
                self.expect("op", ")")
                return ("for", init, condition, step, self.parse_statement(), line)

            if word == "switch":
                self.advance()
                self.expect("op", "(")
                subject = self.parse_expression()
                self.expect("op", ")")
                return ("switch", subject, self.parse_switch_body(), line)

            if word == "return":
                self.advance()
                value = None if self.at_op(";") else self.parse_expression()
                self.expect("op", ";")
                return ("return", value, line)

            if word == "break":
                self.advance()
                self.expect("op", ";")
                return ("break", line)

            if word == "continue":
                self.advance()
                self.expect("op", ";")
                return ("continue", line)

            if word == "typedef":
                self.advance()
                base = self.parse_type()
                name = self.expect("id").value
                self.typedefs[name] = base
                self.expect("op", ";")
                return ("empty",)

        if self.looks_like_type():
            return self.parse_declaration_statement()

        expression = self.parse_expression()
        self.expect("op", ";")
        return ("expr", expression, line)

    def parse_switch_body(self):
        """Returns a flat list of (case_value_or_None, statements)."""
        self.expect("op", "{")
        cases = []
        current = None
        while not self.at_op("}"):
            if self.at("eof"):
                raise CSyntaxError("unterminated switch", self.current.line)
            if self.current.kind == "kw" and self.current.value == "case":
                self.advance()
                value = self.parse_conditional()
                self.expect("op", ":")
                current = (value, [])
                cases.append(current)
                continue
            if self.current.kind == "kw" and self.current.value == "default":
                self.advance()
                self.expect("op", ":")
                current = (None, [])
                cases.append(current)
                continue
            statement = self.parse_statement()
            if current is None:
                # Unreachable code before the first label; C allows it, and
                # dropping it keeps the evaluator simple.
                continue
            current[1].append(statement)
        self.expect("op", "}")
        return cases

    def skip_parameter_list(self) -> None:
        """Steps over `( ... )` without reading it: a function pointer's
        parameter list says what it takes, and the interpreter calls through
        it without checking - the same way C would let a mismatch through."""
        self.expect("op", "(")
        depth = 1
        while depth:
            if self.at("eof"):
                raise CSyntaxError("unterminated parameter list", self.current.line)
            if self.at_op("("):
                depth += 1
            elif self.at_op(")"):
                depth -= 1
            self.advance()

    def parse_declaration_statement(self):
        line = self.current.line
        # `static int n = 0;` inside a function keeps its value between calls.
        # The type parser skips the word, so it has to be noticed here first.
        is_static = self.current.kind == "kw" and self.current.value == "static"
        declared = self.parse_type()
        entries = []
        while True:
            if self.at_op("("):
                # `int (*f)(int) = twice;` - a pointer to a function. Kept as
                # a one-level pointer whose value is the function itself.
                self.advance()
                self.expect("op", "*")
                name = self.expect("id").value
                self.expect("op", ")")
                self.skip_parameter_list()
                var_type = CType("fn", 1)
                init = self.parse_initializer() if self.accept("op", "=") else None
                entries.append((name, var_type, init))
                if not self.accept("op", ","):
                    break
                continue
            name = self.expect("id").value
            var_type = CType(declared.base, declared.pointer, [], declared.struct_name)
            while self.at_op("["):
                self.advance()
                size = None if self.at_op("]") else self.parse_expression()
                self.expect("op", "]")
                var_type.array.append(size)
            init = self.parse_initializer() if self.accept("op", "=") else None
            entries.append((name, var_type, init))
            if not self.accept("op", ","):
                break
            extra = 0
            while self.at_op("*"):
                self.advance()
                extra += 1
            declared = CType(declared.base, extra, struct_name=declared.struct_name)
        self.expect("op", ";")
        if is_static:
            return ("declare", entries, line, "static")
        return ("declare", entries, line)

    # ------------------------------------------------------------- expressions

    def parse_expression(self):
        expression = self.parse_assignment()
        while self.at_op(","):
            self.advance()
            expression = ("comma", expression, self.parse_assignment())
        return expression

    def parse_assignment(self):
        left = self.parse_conditional()
        if self.current.kind == "op" and self.current.value in ASSIGN_OPS:
            op = self.advance().value
            right = self.parse_assignment()
            return ("assign", op, left, right)
        return left

    def parse_conditional(self):
        condition = self.parse_binary(0)
        if self.at_op("?"):
            self.advance()
            then_value = self.parse_expression()
            self.expect("op", ":")
            else_value = self.parse_conditional()
            return ("ternary", condition, then_value, else_value)
        return condition

    def parse_binary(self, level: int):
        if level >= len(BINARY_LEVELS):
            return self.parse_unary()
        operators = BINARY_LEVELS[level]
        left = self.parse_binary(level + 1)
        while self.current.kind == "op" and self.current.value in operators:
            op = self.advance().value
            right = self.parse_binary(level + 1)
            left = ("binary", op, left, right)
        return left

    def parse_unary(self):
        token = self.current

        if token.kind == "op" and token.value in ("+", "-", "!", "~", "*", "&"):
            self.advance()
            operand = self.parse_unary()
            if token.value == "*":
                return ("deref", operand, token.line)
            if token.value == "&":
                return ("addressof", operand, token.line)
            return ("unary", token.value, operand)

        if token.kind == "op" and token.value in ("++", "--"):
            self.advance()
            return ("preincr", token.value, self.parse_unary())

        if token.kind == "kw" and token.value == "sizeof":
            self.advance()
            if self.at_op("(") and self._type_follows_paren():
                self.advance()
                sized = self.parse_type()
                while self.at_op("["):
                    self.advance()
                    if not self.at_op("]"):
                        self.parse_expression()
                    self.expect("op", "]")
                self.expect("op", ")")
                return ("sizeof_type", sized)
            return ("sizeof_expr", self.parse_unary())

        # Cast: '(' type ')' unary
        if self.at_op("(") and self._type_follows_paren():
            self.advance()
            cast_type = self.parse_type()
            self.expect("op", ")")
            return ("cast", cast_type, self.parse_unary())

        return self.parse_postfix()

    def _type_follows_paren(self) -> bool:
        after = self.peek()
        if after.kind == "kw" and after.value in TYPE_KEYWORDS:
            return True
        return after.kind == "id" and after.value in self.typedefs

    def parse_postfix(self):
        expression = self.parse_primary()
        while True:
            if self.at_op("("):
                self.advance()
                args = []
                if not self.at_op(")"):
                    while True:
                        args.append(self.parse_assignment())
                        if not self.accept("op", ","):
                            break
                self.expect("op", ")")
                expression = ("call", expression, args, self.current.line)
            elif self.at_op("["):
                self.advance()
                index = self.parse_expression()
                self.expect("op", "]")
                expression = ("index", expression, index, self.current.line)
            elif self.at_op("."):
                self.advance()
                expression = ("member", expression, self.expect("id").value, False)
            elif self.at_op("->"):
                self.advance()
                expression = ("member", expression, self.expect("id").value, True)
            elif self.at_op("++", "--"):
                op = self.advance().value
                expression = ("postincr", op, expression)
            else:
                return expression

    def parse_primary(self):
        token = self.current

        if token.kind in ("int", "float", "char"):
            self.advance()
            return ("const", token.value, token.kind)

        if token.kind == "str":
            self.advance()
            return ("string", token.value)

        if token.kind == "id":
            self.advance()
            if token.value in getattr(self, "enum_constants", {}):
                return ("const", self.enum_constants[token.value], "int")
            return ("name", token.value, token.line)

        if self.at_op("("):
            self.advance()
            expression = self.parse_expression()
            self.expect("op", ")")
            return expression

        raise CSyntaxError(f"unexpected {token.value!r}", token.line)


def _constant_value(node):
    """Folds the constant expressions an enum initialiser is allowed to use."""
    if node[0] == "const":
        return node[1]
    if node[0] == "unary" and node[1] == "-":
        inner = _constant_value(node[2])
        return None if inner is None else -inner
    if node[0] == "binary":
        left = _constant_value(node[2])
        right = _constant_value(node[3])
        if left is None or right is None:
            return None
        try:
            return {
                "+": left + right, "-": left - right, "*": left * right,
                "<<": left << right, ">>": left >> right,
                "|": left | right, "&": left & right, "^": left ^ right,
            }.get(node[1])
        except (TypeError, ValueError):
            return None
    return None


def parse(source: str) -> dict:
    return Parser(tokenize(source)).parse_program()
