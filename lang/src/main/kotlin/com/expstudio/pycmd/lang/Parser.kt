package com.expstudio.pycmd.lang

/** PyCmd source -> Ast. A Pratt parser; the same grammar as pcmd_parser.py, plus 2.0. */
class Parser(source: String, lineOffset: Int = 0) {
    private val tokens: List<Token> = Lexer.tokenize(source).let { list ->
        if (lineOffset == 0) list else list.map { Token(it.kind, it.value, it.line + lineOffset, it.col) }
    }
    private var i = 0

    companion object {
        val ASSIGN_OPS = setOf("=", "+=", "-=", "*=", "/=", "%=", "//=", "**=")
        val COMPARE = setOf("==", "!=", "<", "<=", ">", ">=")
        val INFIX = mapOf(
            "?" to 2, "??" to 3, "|>" to 4, "or" to 5, "||" to 5, "and" to 6, "&&" to 6,
            "==" to 8, "!=" to 8, "<" to 8, "<=" to 8, ">" to 8, ">=" to 8, "in" to 8, "not" to 8, "is" to 8,
            ".." to 9, "..=" to 9, "+" to 10, "-" to 10, "*" to 11, "/" to 11, "//" to 11, "%" to 11,
            "**" to 13, "(" to 14, "[" to 14, "." to 14, "?." to 14,
        )
        val PREFIX_BP = mapOf("-" to 12, "!" to 7, "not" to 7, "+" to 12)
        val OTHER_WORDS = mapOf(
            "def" to "PyCmd writes fn for functions: fn name(x) { ... }",
            "function" to "PyCmd writes fn for functions: fn name(x) { ... }",
            "func" to "PyCmd writes fn for functions: fn name(x) { ... }",
            "fun" to "PyCmd writes fn for functions: fn name(x) { ... }",
            "class" to "PyCmd writes struct for types: struct Name { field: int }",
            "interface" to "PyCmd writes trait for interfaces: trait Name { fn method(self) }",
            "import" to "PyCmd writes use for libraries: use math",
            "elsif" to "PyCmd writes elif", "elseif" to "PyCmd writes elif",
            "switch" to "PyCmd writes match: match value { 1 => ..., _ => ... }",
            "int" to "PyCmd puts the type after the name: let n: int = 5",
            "string" to "PyCmd puts the type after the name: let s: str = \"hi\"",
            "auto" to "PyCmd writes let (or var to change it later): let n = 5",
        )
        private val NO_LITERAL = Any()

        fun parse(source: String): List<St> = Parser(source).program()
    }

    private val tok: Token get() = tokens[i]
    private fun peek(k: Int = 1) = tokens[minOf(i + k, tokens.size - 1)]
    private fun advance(): Token { val t = tokens[i]; if (i < tokens.size - 1) i++; return t }
    private fun error(message: String, t: Token = tok): Nothing = throw PcSyntaxError(message, t.line, t.col)

    private fun describe(t: Token) = when (t.kind) {
        T.EOF -> "the end of the file"
        T.NL -> "the end of the line"
        T.STR -> "a string"
        T.NUM -> "the number ${t.value}"
        else -> "'${t.value}'"
    }

    private fun expectOp(op: String, what: String = ""): Token {
        if (!tok.isOp(op)) error("expected '$op'${if (what.isNotEmpty()) " $what" else ""}, found ${describe(tok)}")
        return advance()
    }

    private fun expectName(what: String = "a name"): Token {
        val t = tok
        if (t.kind != T.NAME) {
            if (t.kind == T.KW) error("'${t.value}' is a keyword and cannot be used as $what")
            error("expected $what, found ${describe(t)}")
        }
        if (t.text.startsWith("__") || t.text.startsWith("_pc_"))
            error("names cannot start with ${if (t.text.startsWith("__")) "__" else "_pc_"}")
        return advance()
    }

    private fun skipNl() { while (tok.kind == T.NL) advance() }

    private fun endStatement() {
        val t = tok
        if (t.kind == T.NL) { skipNl(); return }
        if (t.kind == T.EOF || t.isOp("}")) return
        error("expected the end of the statement, found ${describe(t)}")
    }

    private fun peekPastNl(): Token { var j = i; while (tokens[j].kind == T.NL) j++; return tokens[j] }

    private fun skipNlIfThen(vararg words: String): Boolean {
        if (peekPastNl().isKw(*words)) { skipNl(); return true }
        return false
    }

    fun program(): List<St> {
        val body = ArrayList<St>()
        skipNl()
        while (tok.kind != T.EOF) { body.add(statement()); endStatement() }
        return body
    }

    private fun block(what: String = "here"): List<St> {
        val start = tok
        if (!tok.isOp("{")) error("expected '{' to start a block $what, found ${describe(tok)}")
        advance()
        val body = ArrayList<St>()
        skipNl()
        while (!tok.isOp("}")) {
            if (tok.kind == T.EOF) error("the block opened on line ${start.line} is never closed - a '}' is missing", start)
            body.add(statement()); endStatement()
        }
        advance()
        return body
    }

    // ------------------------------------------------------------------ statements
    private fun statement(): St {
        var t = tok
        if (t.isKw("pub")) { advance(); t = tok }
        if (t.kind == T.NAME && t.text in OTHER_WORDS && peek().kind == T.NAME) error(OTHER_WORDS.getValue(t.text))
        if (t.kind == T.KW && !(t.text == "fn" && peek().isOp("("))) {
            when (t.text) {
                "let", "var", "const" -> return stLet()
                "fn" -> return stFn()
                "struct" -> return stStruct()
                "enum" -> return stEnum()
                "trait" -> return stTrait()
                "if" -> return stIf()
                "while" -> { advance(); val c = expression(); return St.While(t.line, c, block("after while")) }
                "loop" -> { advance(); return St.While(t.line, null, block("after loop")) }
                "for" -> return stFor()
                "return" -> {
                    advance()
                    if (tok.kind == T.NL || tok.kind == T.EOF || tok.isOp("}")) return St.Return(t.line, null)
                    return St.Return(t.line, expression())
                }
                "break" -> { advance(); return St.Break(t.line) }
                "continue" -> { advance(); return St.Continue(t.line) }
                "throw" -> { advance(); return St.Throw(t.line, expression()) }
                "assert" -> {
                    advance()
                    val cond = expression()
                    var msg: Ex? = null
                    if (tok.isOp(",")) { advance(); msg = expression() }
                    return St.Assert(t.line, cond, msg)
                }
                "test" -> {
                    advance()
                    val parts = tok.value as? List<*>
                    if (tok.kind != T.STR || parts!!.any { it is StrPart.Expr })
                        error("a test needs a plain name: test \"adds numbers\" { ... }")
                    val name = parts.joinToString("") { (it as StrPart.Lit).text }
                    advance()
                    return St.Test(t.line, name, block("for the test"))
                }
                "try" -> return stTry()
                "use" -> return stUse()
                "match" -> { val m = matchExpr(); return St.MatchS(m.line, m.subject, m.arms) }
            }
        }
        var expr = expression()
        if (tok.isOp(",")) {
            val items = arrayListOf(expr)
            while (tok.isOp(",")) { advance(); items.add(expression()) }
            expr = Ex.TupleLit(t.line, items)
            if (!tok.isOp("=")) error("a list of names like a, b needs = after it: a, b = b, a")
        }
        if (tok.kind == T.OP && tok.text in ASSIGN_OPS) {
            val op = advance().text
            checkTarget(expr)
            var value = expression()
            if (tok.isOp(",")) {
                val items = arrayListOf(value)
                while (tok.isOp(",")) { advance(); items.add(expression()) }
                value = Ex.TupleLit(t.line, items)
            }
            return St.Assign(t.line, expr, op, value)
        }
        return St.ExprS(t.line, expr)
    }

    private fun checkTarget(node: Ex) {
        if (node is Ex.Name || node is Ex.Attr || node is Ex.Index) return
        if (node is Ex.TupleLit && node.items.all { it is Ex.Name || it is Ex.Attr || it is Ex.Index }) return
        if (node is Ex.Self_) error("cannot assign to self")
        error("the left side of = must be a name, a field (a.b) or an item (a[i])")
    }

    private fun stLet(): St {
        val t = advance()
        val kind = t.text
        val mutable = kind == "var"
        val names = ArrayList<String>()
        var type: TypeRef? = null
        val unpack: Boolean
        if (tok.isOp("(") || tok.isOp("[")) {
            val close = if (tok.text == "(") ")" else "]"
            advance()
            while (!tok.isOp(close)) {
                if (tok.isOp("...")) { advance(); names.add("..." + expectName().text) } else names.add(expectName().text)
                if (!tok.isOp(",")) break
                advance()
            }
            expectOp(close)
            unpack = true
        } else {
            names.add(expectName().text)
            var u = false
            while (tok.isOp(",")) { advance(); names.add(expectName().text); u = true }
            unpack = u
            if (!unpack && tok.isOp(":")) { advance(); type = typeExpr() }
        }
        if (!tok.isOp("=")) {
            if (mutable && !unpack) return St.Let(t.line, names, true, type, null, false)
            error("'$kind ${names[0]}' needs a value: $kind ${names[0]} = ..." +
                    if (mutable) "" else "  (a var can start empty: var x: int)")
        }
        advance()
        var value = expression()
        if (unpack && tok.isOp(",")) {
            val items = arrayListOf(value)
            while (tok.isOp(",")) { advance(); items.add(expression()) }
            value = Ex.TupleLit(t.line, items)
        }
        return St.Let(t.line, names, mutable, type, value, unpack)
    }

    private fun params(): List<Param> {
        expectOp("(")
        val out = ArrayList<Param>()
        var seenDefault = false
        while (!tok.isOp(")")) {
            skipNl()
            if (tok.isOp(")")) break
            var rest = false
            if (tok.isOp("...")) { advance(); rest = true }
            val name = if (tok.isKw("self")) advance().text else expectName("a parameter name").text
            var type: TypeRef? = null
            var default: Ex? = null
            if (tok.isOp(":")) { advance(); type = typeExpr() }
            if (tok.isOp("=")) { advance(); default = expression(); seenDefault = true }
            else if (seenDefault && !rest) error("parameter '$name' needs a default, like the ones before it")
            out.add(Param(name, type, default, rest))
            skipNl()
            if (!tok.isOp(",")) break
            advance()
        }
        skipNl()
        expectOp(")", "to close the parameters")
        return out
    }

    /** In a trait, a fn may have no body: it is what implementers must write. */
    private fun stFn(bodyOptional: Boolean = false): St.Fn {
        val t = advance()
        val name = expectName("a function name").text
        val ps = params()
        var ret: TypeRef? = null
        if (tok.isOp("->")) { advance(); ret = typeExpr() }
        val body: List<St>? = when {
            tok.isOp("=>") -> { advance(); val line = tok.line; listOf(St.Return(line, expression())) }
            bodyOptional && !tok.isOp("{") -> null
            else -> block("for fn $name")
        }
        return St.Fn(t.line, name, ps, ret, body)
    }

    private fun nameList(): List<String> {
        val out = arrayListOf(expectName("a trait name").text)
        while (tok.isOp(",")) { advance(); out.add(expectName("a trait name").text) }
        return out
    }

    private fun stStruct(): St {
        val t = advance()
        val name = expectName("a struct name").text
        var parent: String? = null
        var impls: List<String> = emptyList()
        if (tok.isKw("extends") || tok.isOp(":")) { advance(); parent = expectName("the struct it extends").text }
        if (tok.isKw("impl")) { advance(); impls = nameList() }
        expectOp("{", "to start struct $name")
        val fields = ArrayList<Param>()
        val lines = ArrayList<Int>()
        val methods = ArrayList<St.Fn>()
        skipNl()
        while (!tok.isOp("}")) {
            if (tok.kind == T.EOF) error("struct $name is never closed - a '}' is missing", t)
            if (tok.isKw("pub")) advance()
            if (tok.isKw("fn")) methods.add(stFn())
            else {
                val ft = expectName("a field name")
                var ftype: TypeRef? = null
                var default: Ex? = null
                if (tok.isOp(":")) { advance(); ftype = typeExpr() }
                if (tok.isOp("=")) { advance(); default = expression() }
                fields.add(Param(ft.text, ftype, default, false))
                lines.add(ft.line)
            }
            if (tok.isOp(",")) advance()
            skipNl()
        }
        advance()
        return St.Struct(t.line, name, parent, impls, fields, lines, methods)
    }

    private fun stEnum(): St {
        val t = advance()
        val name = expectName("an enum name").text
        expectOp("{", "to start enum $name")
        val variants = ArrayList<VariantDecl>()
        val methods = ArrayList<St.Fn>()
        skipNl()
        while (!tok.isOp("}")) {
            if (tok.kind == T.EOF) error("enum $name is never closed - a '}' is missing", t)
            if (tok.isKw("fn")) { methods.add(stFn()); skipNl(); continue }
            val v = expectName("a variant name").text
            var value: Ex? = null
            var fields: List<Param>? = null
            if (tok.isOp("(")) fields = params()
            else if (tok.isOp("=")) { advance(); value = expression() }
            variants.add(VariantDecl(v, value, fields))
            if (tok.isOp(",")) advance()
            skipNl()
        }
        advance()
        if (variants.isEmpty()) error("enum $name has no variants", t)
        return St.EnumS(t.line, name, variants, methods)
    }

    private fun stTrait(): St {
        val t = advance()
        val name = expectName("a trait name").text
        expectOp("{", "to start trait $name")
        val methods = ArrayList<St.Fn>()
        skipNl()
        while (!tok.isOp("}")) {
            if (tok.kind == T.EOF) error("trait $name is never closed - a '}' is missing", t)
            if (!tok.isKw("fn")) error("a trait holds fn lines only: fn area(self) -> float")
            methods.add(stFn(bodyOptional = true))
            if (tok.isOp(",")) advance()
            skipNl()
        }
        advance()
        return St.Trait(t.line, name, methods)
    }

    private fun stIf(): St {
        val t = advance()
        val branches = ArrayList<Pair<Ex, List<St>>>()
        branches.add(expression() to block("after if"))
        var other: List<St>? = null
        while (skipNlIfThen("elif", "else")) {
            if (tok.isKw("elif")) { advance(); branches.add(expression() to block("after elif")); continue }
            advance()
            if (tok.isKw("if")) { advance(); branches.add(expression() to block("after else if")); continue }
            other = block("after else")
            break
        }
        return St.If(t.line, branches, other)
    }

    private fun stFor(): St {
        val t = advance()
        val names = arrayListOf(expectName("a loop variable").text)
        while (tok.isOp(",")) { advance(); names.add(expectName("a loop variable").text) }
        if (!tok.isKw("in")) error("expected 'in' after the loop variable, found ${describe(tok)} - write: for x in list { ... }")
        advance()
        val it = expression()
        return St.For(t.line, names, it, block("after for"))
    }

    private fun stTry(): St {
        val t = advance()
        val body = block("after try")
        var name: String? = null
        var handler: List<St>? = null
        var final: List<St>? = null
        if (skipNlIfThen("catch")) {
            advance()
            if (tok.kind == T.NAME) name = expectName().text
            handler = block("after catch")
        }
        if (skipNlIfThen("finally")) { advance(); final = block("after finally") }
        if (handler == null && final == null) error("try needs a catch or a finally after it", t)
        return St.Try(t.line, body, name, handler, final)
    }

    private fun stUse(): St {
        val t = advance()
        if (tok.kind == T.STR) {
            @Suppress("UNCHECKED_CAST")
            val path = (advance().value as List<StrPart>).filterIsInstance<StrPart.Lit>().joinToString("") { it.text }
            if (!tok.isKw("as")) error("a file needs a name: use \"$path\" as name")
            advance()
            return St.Use(t.line, null, path, expectName().text, null)
        }
        val parts = arrayListOf(expectName("a library name").text)
        while (tok.isOp(".")) {
            advance()
            if (tok.isOp("{")) break
            parts.add(expectName().text)
        }
        var names: ArrayList<String>? = null
        if (tok.isOp("{")) {
            advance()
            names = ArrayList()
            while (!tok.isOp("}")) {
                names.add(expectName().text)
                if (!tok.isOp(",")) break
                advance()
            }
            expectOp("}")
        }
        var alias = parts.last()
        if (tok.isKw("as")) { advance(); alias = expectName().text }
        return St.Use(t.line, parts.joinToString("."), null, alias, names)
    }

    // ------------------------------------------------------------------ match
    private fun matchExpr(): Ex.MatchE {
        val t = advance()
        val subject = expression()
        expectOp("{", "to start the match arms")
        val arms = ArrayList<Arm>()
        skipNl()
        while (!tok.isOp("}")) {
            if (tok.kind == T.EOF) error("this match is never closed - a '}' is missing", t)
            val line = tok.line
            val pattern = pattern()
            var guard: Ex? = null
            if (tok.isKw("if")) { advance(); guard = expression() }
            expectOp("=>", "after the pattern")
            if (tok.isOp("{") && !looksLikeMap()) {
                arms.add(Arm(pattern, guard, block("for the match arm"), null, line))
            } else if (tok.kind == T.KW && tok.text in setOf("return", "break", "continue", "throw")) {
                arms.add(Arm(pattern, guard, listOf(statement()), null, line))
            } else {
                val expr = expression()
                if (tok.kind == T.OP && tok.text in ASSIGN_OPS) {
                    val op = advance().text
                    checkTarget(expr)
                    arms.add(Arm(pattern, guard, listOf(St.Assign(line, expr, op, expression())), null, line))
                } else arms.add(Arm(pattern, guard, null, expr, line))
            }
            if (tok.isOp(",")) advance()
            skipNl()
        }
        advance()
        if (arms.isEmpty()) error("a match needs at least one arm: pattern => result", t)
        return Ex.MatchE(t.line, subject, arms)
    }

    private fun looksLikeMap(): Boolean {
        val nx = peek()
        if (nx.isOp("}")) return true
        return (nx.kind == T.STR || nx.kind == T.NUM) && peek(2).isOp(":")
    }

    private fun pattern(): Pat {
        val alts = arrayListOf(patternOne())
        while (tok.isOp("|")) { advance(); alts.add(patternOne()) }
        return if (alts.size == 1) alts[0] else Pat.Or(alts)
    }

    private fun literalValue(): Any? {
        val t = tok
        if (t.kind == T.NUM) { advance(); return t.value }
        if (t.isOp("-") && peek().kind == T.NUM) { advance(); return Ops.neg(advance().value) }
        if (t.kind == T.STR) {
            @Suppress("UNCHECKED_CAST")
            val parts = t.value as List<StrPart>
            if (parts.any { it is StrPart.Expr }) error("a pattern cannot contain {interpolation}")
            advance()
            return parts.joinToString("") { (it as StrPart.Lit).text }
        }
        if (t.isKw("true")) { advance(); return true }
        if (t.isKw("false")) { advance(); return false }
        if (t.isKw("nil")) { advance(); return null }
        return NO_LITERAL
    }

    private fun subPatterns(): List<Pair<String?, Pat>> {
        advance()
        val subs = ArrayList<Pair<String?, Pat>>()
        while (!tok.isOp(")")) {
            if (tok.kind == T.NAME && peek().isOp(":")) {
                val key = advance().text; advance()
                subs.add(key to pattern())
            } else subs.add(null to pattern())
            if (!tok.isOp(",")) break
            advance()
        }
        expectOp(")")
        return subs
    }

    private fun patternOne(): Pat {
        val t = tok
        val value = literalValue()
        if (value !== NO_LITERAL) {
            if (tok.isOp("..", "..=")) {
                val inclusive = advance().text == "..="
                val hi = literalValue()
                if (hi === NO_LITERAL) error("a range pattern needs two plain values, like 1..=9")
                return Pat.Range(value, hi, inclusive)
            }
            return Pat.Lit(value)
        }
        if (t.kind == T.NAME && t.text == "_") { advance(); return Pat.Any_ }
        if (t.isKw("is")) { advance(); return Pat.Type(typeExpr()) }
        if (t.isOp("[") || t.isOp("(")) {
            val close = if (t.text == "[") "]" else ")"
            advance()
            val items = ArrayList<Pat>()
            while (!tok.isOp(close)) {
                if (tok.isOp("...")) {
                    advance()
                    items.add(Pat.Rest(if (tok.kind == T.NAME) expectName().text else "_"))
                } else items.add(pattern())
                if (!tok.isOp(",")) break
                advance()
            }
            expectOp(close)
            return Pat.ListP(items)
        }
        if (t.kind == T.NAME) {
            val name = advance().text
            if (tok.isOp(".")) {
                val parts = arrayListOf(name)
                while (tok.isOp(".")) { advance(); parts.add(expectName().text) }
                if (tok.isOp("(")) return Pat.VariantP(parts, subPatterns())
                return Pat.Value(parts)
            }
            if (tok.isOp("(")) return Pat.StructP(name, subPatterns())
            return Pat.Bind(name, t.line)
        }
        error("this cannot start a pattern: ${describe(t)}")
    }

    // ------------------------------------------------------------------ types
    private fun typeExpr(optional: Boolean = true): TypeRef {
        val options = arrayListOf(typeOne(optional))
        while (tok.isOp("|") && (peek().kind == T.NAME || peek().kind == T.KW)) { advance(); options.add(typeOne(optional)) }
        return if (options.size == 1) options[0] else TypeRef.Union(options)
    }

    private fun typeOne(optional: Boolean = true): TypeRef {
        val t = tok
        if (t.kind == T.NAME || t.isKw("fn", "nil")) {
            advance()
            val args = ArrayList<TypeRef>()
            if (tok.isOp("[")) {
                advance()
                while (!tok.isOp("]")) {
                    args.add(typeExpr())
                    if (!tok.isOp(",")) break
                    advance()
                }
                expectOp("]")
            }
            if (t.text == "fn" && tok.isOp("(")) {
                var depth = 0
                while (true) {
                    if (tok.isOp("(")) depth++
                    else if (tok.isOp(")")) { depth--; if (depth == 0) { advance(); break } }
                    else if (tok.kind == T.EOF) error("fn( ... ) type is not closed")
                    advance()
                }
                if (tok.isOp("->")) { advance(); typeExpr() }
            }
            var result: TypeRef = TypeRef.Simple(t.text, args, t.line)
            if (optional && tok.isOp("?")) { advance(); result = TypeRef.Optional(result) }
            return result
        }
        error("expected a type (int, str, list, ...), found ${describe(t)}")
    }

    // ------------------------------------------------------------------ expressions
    fun expression(bp: Int = 0): Ex {
        var left = prefix()
        while (true) {
            val t = tok
            val op = when {
                t.kind == T.OP -> t.text
                t.isKw("and", "or", "in", "is", "not") -> t.text
                else -> break
            }
            val power = INFIX[op] ?: break
            if (power <= bp) break
            if (op == "not" && !peek().isKw("in")) break
            left = infix(left, op, power)
        }
        return left
    }

    private fun prefix(): Ex {
        val t = tok
        val line = t.line
        when (t.kind) {
            T.NUM -> { advance(); return Ex.Const(line, t.value) }
            T.STR -> { advance(); return string(t) }
            T.NAME -> {
                advance()
                if (t.text.startsWith("__") || t.text.startsWith("_pc_")) error("names cannot start with __ or _pc_", t)
                return Ex.Name(line, t.text)
            }
            T.KW -> {
                when (t.text) {
                    "true", "false" -> { advance(); return Ex.Const(line, t.text == "true") }
                    "nil" -> { advance(); return Ex.Const(line, null) }
                    "self" -> { advance(); return Ex.Self_(line) }
                    "not" -> { advance(); return Ex.Unary(line, "not", expression(PREFIX_BP.getValue("not"))) }
                    "fn" -> return lambdaFn()
                    "match" -> return matchExpr()
                    "if" -> error("if is a statement here - for a value, write cond ? a : b")
                }
                error("'${t.text}' cannot be used inside an expression")
            }
            T.OP -> {
                when (t.text) {
                    "-", "+" -> {
                        advance()
                        val operand = expression(PREFIX_BP.getValue(t.text))
                        if (t.text == "-" && operand is Ex.Const && (operand.value is Long || operand.value is Double ||
                                    operand.value is java.math.BigInteger))
                            return Ex.Const(line, Ops.neg(operand.value))
                        return Ex.Unary(line, t.text, operand)
                    }
                    "!" -> { advance(); return Ex.Unary(line, "not", expression(PREFIX_BP.getValue("!"))) }
                    "(" -> {
                        advance(); skipNl()
                        if (tok.isOp(")")) { advance(); return Ex.TupleLit(line, emptyList()) }
                        val first = expression()
                        skipNl()
                        if (tok.isOp(",")) {
                            val items = arrayListOf(first)
                            while (tok.isOp(",")) {
                                advance(); skipNl()
                                if (tok.isOp(")")) break
                                items.add(expression()); skipNl()
                            }
                            expectOp(")")
                            return Ex.TupleLit(line, items)
                        }
                        expectOp(")", "to close the bracket")
                        return Ex.Group(line, first)
                    }
                    "[" -> return listLiteral()
                    "{" -> return mapLiteral()
                    "|", "||" -> return lambdaBar()
                    "..." -> error("... spreads a list into a call or a list: f(...xs), [...a, ...b]")
                }
            }
            T.NL, T.EOF -> error("an expression is missing here - the line stops too early")
        }
        error("unexpected ${describe(t)}")
    }

    private fun string(t: Token): Ex {
        @Suppress("UNCHECKED_CAST")
        val raw = t.value as List<StrPart>
        val parts = ArrayList<Any>()
        for (part in raw) {
            if (part is StrPart.Lit) { parts.add(part.text); continue }
            part as StrPart.Expr
            var text = part.src
            var spec: String? = null
            var depth = 0
            var question = false
            var cut = -1
            var inStr: Char? = null
            for ((k, c) in text.withIndex()) {
                if (inStr != null) { if (c == inStr) inStr = null; continue }
                when {
                    c == '"' || c == '\'' -> inStr = c
                    c in "([{" -> depth++
                    c in ")]}" -> depth--
                    depth == 0 && c == '?' && text.getOrNull(k + 1) != '.' && text.getOrNull(k + 1) != '?' &&
                            text.getOrNull(k - 1) != '?' -> question = true
                    depth == 0 && c == ':' && !question -> cut = k
                }
            }
            if (cut >= 0) { spec = text.substring(cut + 1); text = text.substring(0, cut) }
            val sub = Parser(text, part.line - 1)
            sub.skipNl()
            val expr = sub.expression()
            sub.skipNl()
            if (sub.tok.kind != T.EOF) throw PcSyntaxError("in a string, {$text} is not one expression", part.line)
            parts.add(Ex.InterpPart(expr, spec))
        }
        if (parts.size == 1 && parts[0] is String) return Ex.Const(t.line, parts[0])
        return Ex.Interp(t.line, parts)
    }

    private fun listItem(): Ex {
        if (tok.isOp("...")) { val line = advance().line; return Ex.Spread(line, expression()) }
        return expression()
    }

    private fun listLiteral(): Ex {
        val t = advance()
        skipNl()
        if (tok.isOp("]")) { advance(); return Ex.ListLit(t.line, emptyList()) }
        val first = listItem()
        skipNl()
        if (tok.isKw("for")) {
            val (loops, cond) = comprehensionTail()
            skipNl(); expectOp("]")
            return Ex.ListComp(t.line, first, loops, cond)
        }
        val items = arrayListOf(first)
        while (tok.isOp(",")) {
            advance(); skipNl()
            if (tok.isOp("]")) break
            items.add(listItem()); skipNl()
        }
        expectOp("]", "to close the list")
        return Ex.ListLit(t.line, items)
    }

    private fun comprehensionTail(): Pair<List<CompLoop>, Ex?> {
        val loops = ArrayList<CompLoop>()
        var cond: Ex? = null
        while (tok.isKw("for")) {
            val line = advance().line
            val names = arrayListOf(expectName("a loop variable").text)
            while (tok.isOp(",")) { advance(); names.add(expectName().text) }
            if (!tok.isKw("in")) error("expected 'in' in the comprehension")
            advance()
            loops.add(CompLoop(names, expression(INFIX.getValue("?")), line))
            skipNl()
        }
        if (tok.isKw("if")) { advance(); cond = expression() }
        return loops to cond
    }

    private fun mapLiteral(): Ex {
        val t = advance()
        skipNl()
        val pairs = ArrayList<Pair<Ex?, Ex>>()
        if (tok.isOp("}")) { advance(); return Ex.MapLit(t.line, pairs) }
        while (true) {
            skipNl()
            if (tok.isOp("}")) break
            if (tok.isOp("...")) { advance(); pairs.add(null to expression()) }
            else {
                var bare: Token? = null
                var key: Ex
                if (tok.kind == T.NAME && peek().isOp(":")) { bare = tok; key = Ex.Const(tok.line, advance().text) }
                else key = expression()
                skipNl()
                expectOp(":", "between a key and its value")
                skipNl()
                val value = expression()
                skipNl()
                if (tok.isKw("for") && pairs.isEmpty()) {
                    if (bare != null) key = Ex.Name(bare.line, bare.text)
                    val (loops, cond) = comprehensionTail()
                    skipNl(); expectOp("}")
                    return Ex.MapComp(t.line, key, value, loops, cond)
                }
                pairs.add(key to value)
            }
            skipNl()
            if (!tok.isOp(",")) break
            advance()
        }
        skipNl()
        expectOp("}", "to close the map")
        return Ex.MapLit(t.line, pairs)
    }

    private fun lambdaFn(): Ex {
        val t = advance()
        val ps = params()
        var ret: TypeRef? = null
        if (tok.isOp("->")) { advance(); ret = typeExpr() }
        if (tok.isOp("=>")) { advance(); return Ex.Lambda(t.line, ps, ret, expression(), null) }
        return Ex.Lambda(t.line, ps, ret, null, block("for the fn"))
    }

    private fun lambdaBar(): Ex {
        val t = advance()
        val ps = ArrayList<Param>()
        if (t.text == "|") {
            while (!tok.isOp("|")) {
                val name = expectName("a parameter name").text
                var type: TypeRef? = null
                if (tok.isOp(":")) { advance(); type = typeOne() }
                ps.add(Param(name, type, null, false))
                if (!tok.isOp(",")) break
                advance()
            }
            expectOp("|", "to close the parameters")
        }
        if (tok.isOp("{")) return Ex.Lambda(t.line, ps, null, null, block("for the fn"))
        return Ex.Lambda(t.line, ps, null, expression(INFIX.getValue("?") - 1), null)
    }

    private fun callArgs(): Pair<List<Ex>, List<Pair<String, Ex>>> {
        val args = ArrayList<Ex>()
        val kwargs = ArrayList<Pair<String, Ex>>()
        skipNl()
        while (!tok.isOp(")")) {
            if (tok.isOp("...")) { val line = advance().line; args.add(Ex.Spread(line, expression())) }
            else if (tok.kind == T.NAME && peek().isOp(":")) {
                val key = advance().text; advance()
                kwargs.add(key to expression())
            } else {
                if (kwargs.isNotEmpty()) error("plain arguments go before named ones (name: value)")
                args.add(expression())
            }
            skipNl()
            if (!tok.isOp(",")) break
            advance(); skipNl()
        }
        expectOp(")", "to close the call")
        return args to kwargs
    }

    private fun infix(left: Ex, op: String, power: Int): Ex {
        val t = advance()
        val line = t.line
        when (op) {
            "(" -> { val (a, k) = callArgs(); return Ex.Call(line, left, a, k) }
            "[" -> {
                skipNl()
                val index = sliceOrIndex()
                skipNl()
                expectOp("]", "to close the index")
                return Ex.Index(line, left, index)
            }
            ".", "?." -> {
                if (tok.kind == T.NUM && tok.value is Long && op == ".") {
                    val n = advance().value
                    return Ex.Index(line, left, Ex.Const(line, n))
                }
                val nt = tok
                if (nt.kind != T.NAME && nt.kind != T.KW) error("expected a field or method name after '$op'")
                advance()
                if (nt.text.startsWith("_")) error("fields starting with _ cannot be reached from outside", nt)
                return if (op == ".") Ex.Attr(line, left, nt.text) else Ex.OptAttr(line, left, nt.text)
            }
            "?" -> {
                skipNl()
                val a = expression()
                skipNl(); expectOp(":", "in cond ? a : b"); skipNl()
                val b = expression(power - 1)
                return Ex.Ternary(line, left, a, b)
            }
            "not" -> { advance(); return Ex.Binary(line, "not in", left, expression(power)) }
            "is" -> {
                var negate = false
                if (tok.isKw("not")) { advance(); negate = true }
                return Ex.Is(line, left, typeExpr(optional = false), negate)
            }
            "..", "..=" -> return Ex.RangeE(line, left, expression(power), op == "..=")
            "|>" -> return Ex.Pipe(line, left, expression(power))
            "**" -> return Ex.Binary(line, "**", left, expression(power - 1))
        }
        val right = expression(power)
        return when {
            op == "&&" || op == "and" -> Ex.Logic(line, "and", left, right)
            op == "||" || op == "or" -> Ex.Logic(line, "or", left, right)
            op == "??" -> Ex.Coalesce(line, left, right)
            op in COMPARE && left is Ex.Compare -> { left.ops.add(op); left.items.add(right); left }
            op in COMPARE -> Ex.Compare(line, arrayListOf(op), arrayListOf(left, right))
            else -> Ex.Binary(line, op, left, right)
        }
    }

    private fun sliceOrIndex(): Ex {
        val line = tok.line
        val parts = arrayOfNulls<Ex>(3)
        var k = 0
        var isSlice = false
        while (true) {
            if (tok.isOp(":")) {
                advance(); isSlice = true; k++
                if (k > 2) error("a slice has at most two colons: [start:stop:step]")
                continue
            }
            if (tok.isOp("]")) break
            parts[k] = expression()
            if (!tok.isOp(":")) break
        }
        if (!isSlice) return parts[0] ?: error("[] needs an index inside it")
        return Ex.Slice(line, parts[0], parts[1], parts[2])
    }
}
