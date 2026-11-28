package com.expstudio.pycmd.lang

/**
 * Tokens for PyCmd. The same rules as the first engine (pcmd_lexer.py), so a
 * program reads the same on both: statements end at a line end or `;`, a line
 * carries on when it ends in an operator or comma or sits inside ( ) / [ ],
 * and a line starting with `.`, `?.`, `|>` or `??` belongs to the one before.
 */

class PcSyntaxError(val msg: String, val line: Int, val col: Int = 0) :
    RuntimeException("line $line: $msg") {
    override fun fillInStackTrace(): Throwable = this
}

enum class T { NUM, STR, NAME, KW, OP, NL, EOF }

/** A piece of an interpolated string: literal text, or an expression's source. */
sealed class StrPart {
    class Lit(val text: String) : StrPart()
    class Expr(val src: String, val line: Int) : StrPart()
}

class Token(val kind: T, val value: Any?, val line: Int, val col: Int) {
    val text: String get() = value as? String ?: ""
    fun isOp(vararg ops: String) = kind == T.OP && value in ops
    fun isKw(vararg words: String) = kind == T.KW && value in words
    override fun toString() = "Token($kind, $value, $line)"
}

object Lexer {
    val KEYWORDS = setOf(
        "let", "var", "const", "fn", "return", "if", "elif", "else", "while", "for", "in",
        "loop", "break", "continue", "match", "struct", "enum", "extends", "true", "false",
        "nil", "and", "or", "not", "try", "catch", "finally", "throw", "use", "as", "is",
        "assert", "test", "self", "pub", "trait", "impl",
    )

    private val OPERATORS = listOf(
        "..=", "//=", "**=", "...",
        "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "->", "=>", "|>", "??", "?.",
        "..", "//", "**", "&&", "||",
        "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]", "{", "}", ",", ":",
        ".", "?", "!", "|", ";", "&", "@",
    )

    private val CONTINUES_AFTER = setOf(
        "+", "-", "*", "/", "%", "//", "**", "==", "!=", "<", "<=", ">", ">=", "=", "+=",
        "-=", "*=", "/=", "%=", "//=", "**=", "and", "or", "not", "&&", "||", ",", ".",
        "|>", "??", "?", ":", "=>", "->", "..", "..=", "(", "[", "in", "is", "|",
    )
    private val CONTINUES_BEFORE = setOf(".", "?.", "|>", "??", ")", "]")

    fun tokenize(source: String): List<Token> {
        val src = source.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
        val tokens = ArrayList<Token>()
        var i = 0
        var line = 1
        var lineStart = 0
        val n = src.length
        val depth = ArrayList<Char>()
        while (i < n) {
            val ch = src[i]
            val col = i - lineStart + 1
            if (ch == '\n') {
                if (depth.isEmpty() || depth.last() == '{') tokens.add(Token(T.NL, "\n", line, col))
                i++; line++; lineStart = i
                continue
            }
            if (ch == ' ' || ch == '\u000c' || ch == '\u000b') { i++; continue }
            if (ch == '#') {
                while (i < n && src[i] != '\n') i++
                continue
            }
            val prev = tokens.lastOrNull()
            if (ch.isDigit() || (ch == '.' && i + 1 < n && src[i + 1].isDigit() &&
                        !(prev != null && (prev.kind == T.NUM || prev.kind == T.NAME || prev.isOp(")", "]"))))) {
                if (src.startsWith("0x", i) || src.startsWith("0X", i)) {
                    var j = i + 2
                    while (j < n && (src[j].isLetterOrDigit() || src[j] == '_')) j++
                    tokens.add(Token(T.NUM, parseInt(src.substring(i + 2, j).replace("_", ""), 16, line), line, col))
                    i = j; continue
                }
                if (src.startsWith("0b", i) || src.startsWith("0B", i)) {
                    var j = i + 2
                    while (j < n && (src[j] == '0' || src[j] == '1' || src[j] == '_')) j++
                    tokens.add(Token(T.NUM, parseInt(src.substring(i + 2, j).replace("_", ""), 2, line), line, col))
                    i = j; continue
                }
                var j = i
                var isFloat = false
                while (j < n && (src[j].isDigit() || src[j] == '_')) j++
                if (j < n && src[j] == '.' && !src.startsWith("..", j) && j + 1 < n && src[j + 1].isDigit()) {
                    isFloat = true
                    j++
                    while (j < n && (src[j].isDigit() || src[j] == '_')) j++
                }
                if (j < n && (src[j] == 'e' || src[j] == 'E') && j + 1 < n &&
                    (src[j + 1].isDigit() || ((src[j + 1] == '+' || src[j + 1] == '-') && j + 2 < n && src[j + 2].isDigit()))) {
                    isFloat = true
                    j += 2
                    while (j < n && src[j].isDigit()) j++
                }
                var text = src.substring(i, j).replace("_", "")
                if (text.startsWith(".")) text = "0$text"
                if (j < n && (src[j].isLetter() || src[j] == '_'))
                    throw PcSyntaxError("a number runs into letters: ${src.substring(i, j + 1)}", line, col)
                val value: Any = if (isFloat) text.toDouble() else parseInt(text, 10, line)
                tokens.add(Token(T.NUM, value, line, col))
                i = j; continue
            }
            if (ch.isLetter() || ch == '_') {
                var j = i
                while (j < n && (src[j].isLetterOrDigit() || src[j] == '_')) j++
                val word = src.substring(i, j)
                tokens.add(Token(if (word in KEYWORDS) T.KW else T.NAME, word, line, col))
                i = j; continue
            }
            if (ch == '"' || ch == '\'') {
                val triple = src.startsWith("$ch$ch$ch", i)
                val start = i + if (triple) 3 else 1
                val r = readString(src, start, line, ch, triple)
                tokens.add(Token(T.STR, r.parts, line, col))
                i = r.end
                if (r.line != line) lineStart = src.lastIndexOf('\n', i - 1) + 1
                line = r.line
                continue
            }
            val op = OPERATORS.firstOrNull { src.startsWith(it, i) }
                ?: throw PcSyntaxError("unexpected character '$ch'", line, col)
            if (op == ";") {
                tokens.add(Token(T.NL, ";", line, col)); i++; continue
            }
            when (op) {
                "(", "[" -> depth.add(op[0])
                "{" -> depth.add('{')
                ")", "]", "}" -> if (depth.isNotEmpty()) depth.removeAt(depth.size - 1)
            }
            tokens.add(Token(T.OP, op, line, col))
            i += op.length
        }
        tokens.add(Token(T.NL, "\n", line, 1))
        tokens.add(Token(T.EOF, null, line, 1))
        return joinLines(tokens)
    }

    private fun parseInt(text: String, radix: Int, line: Int): Any {
        if (text.isEmpty()) throw PcSyntaxError("a number has no digits", line)
        return try {
            text.toLong(radix)
        } catch (e: NumberFormatException) {
            Num.norm(java.math.BigInteger(text, radix))
        }
    }

    private class StrResult(val parts: List<StrPart>, val end: Int, val line: Int)

    private fun readString(src: String, from: Int, startLine: Int, quote: Char, triple: Boolean): StrResult {
        val parts = ArrayList<StrPart>()
        val buf = StringBuilder()
        val interpolate = quote == '"'
        var i = from
        var line = startLine
        val n = src.length
        val q3 = "$quote$quote$quote"
        while (true) {
            if (i >= n) throw PcSyntaxError("this string never ends - a closing quote is missing", startLine)
            val ch = src[i]
            if (triple && src.startsWith(q3, i)) { i += 3; break }
            if (!triple && ch == quote) { i++; break }
            if (ch == '\n') {
                if (!triple) throw PcSyntaxError("this string never ends on its line - close the quote, " +
                        "or use \"\"\"triple quotes\"\"\" for several lines", startLine)
                line++; buf.append(ch); i++; continue
            }
            if (ch == '\\') {
                if (i + 1 >= n) throw PcSyntaxError("a string ends in a lone backslash", line)
                val nx = src[i + 1]
                if (nx == 'u' && i + 2 < n && src[i + 2] == '{') {
                    val end = src.indexOf('}', i + 3)
                    if (end < 0) throw PcSyntaxError("\\u{...} is not closed", line)
                    val code = src.substring(i + 3, end).toIntOrNull(16)
                        ?: throw PcSyntaxError("\\u{${src.substring(i + 3, end)}} is not a hex code", line)
                    buf.appendCodePoint(code); i = end + 1; continue
                }
                if (nx == '\n') { line++; i += 2; continue }
                val esc = when (nx) {
                    'n' -> "\n"; 't' -> "\t"; 'r' -> "\r"; '0' -> "\u0000"; '\\' -> "\\"
                    '"' -> "\""; '\'' -> "'"; '{' -> "{"; '}' -> "}"; 'e' -> "\u001b"
                    else -> throw PcSyntaxError("unknown escape \\$nx", line)
                }
                buf.append(esc); i += 2; continue
            }
            if (interpolate && ch == '{') {
                if (src.startsWith("{{", i)) { buf.append('{'); i += 2; continue }
                var depth = 1
                var j = i + 1
                var inStr: Char? = null
                while (j < n && depth > 0) {
                    val c = src[j]
                    if (inStr != null) {
                        if (c == '\\') { j += 2; continue }
                        if (c == inStr) inStr = null
                    } else if (c == '"' || c == '\'') inStr = c
                    else if (c == '{' || c == '(' || c == '[') depth++
                    else if (c == '}' || c == ')' || c == ']') depth--
                    else if (c == '\n' && !triple) break
                    j++
                }
                if (depth > 0) throw PcSyntaxError("a { in this string is never closed - write {{ for a plain brace", line)
                if (buf.isNotEmpty()) { parts.add(StrPart.Lit(buf.toString())); buf.setLength(0) }
                val text = src.substring(i + 1, j - 1)
                if (text.isBlank()) throw PcSyntaxError("empty {} in a string - put a name or expression inside, " +
                        "or write {{}} for braces", line)
                parts.add(StrPart.Expr(text, line))
                line += text.count { it == '\n' }
                i = j; continue
            }
            if (interpolate && ch == '}' && src.startsWith("}}", i)) { buf.append('}'); i += 2; continue }
            buf.append(ch); i++
        }
        if (buf.isNotEmpty() || parts.isEmpty()) parts.add(StrPart.Lit(buf.toString()))
        return StrResult(parts, i, line)
    }

    private fun joinLines(tokens: List<Token>): List<Token> {
        val out = ArrayList<Token>(tokens.size)
        for ((index, t) in tokens.withIndex()) {
            if (t.kind == T.NL) {
                val prev = out.lastOrNull()
                if (prev == null || prev.kind == T.NL) continue
                if ((prev.kind == T.OP || prev.kind == T.KW) && prev.value in CONTINUES_AFTER) continue
                var j = index + 1
                while (j < tokens.size && tokens[j].kind == T.NL) j++
                val nx = tokens.getOrNull(j)
                if (nx != null && nx.kind == T.OP && nx.value in CONTINUES_BEFORE) continue
            }
            out.add(t)
        }
        return out
    }
}
