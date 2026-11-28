package com.expstudio.pycmd.lang

import java.math.BigDecimal
import java.math.BigInteger
import java.math.RoundingMode

/*
 * PyCmd values on the JVM:
 *   nil -> null, bool -> Boolean, int -> Long (BigInteger past 64 bits, never
 *   overflowing), float -> Double, str -> String, list -> PList, map -> PMap
 *   (insertion order), set -> PSet, tuple -> PTuple, range -> PRange,
 *   fn -> Callable, struct -> StructType/StructObj, enum -> EnumType/Variant,
 *   errors -> PcError, libraries -> Module.
 */

class PcError(
    var msg: String,
    var kind: String = "Error",
    var value: Any? = null,
    var line: Int = 0,
) : RuntimeException(msg) {
    override fun fillInStackTrace(): Throwable = this
    override val message: String get() = msg
    val shown: String get() = if (kind == "Error") "Error: $msg" else "$kind: $msg"
}

/** Thrown by exit(); not catchable by a program's try. */
class PcExit(val code: Int) : RuntimeException() {
    override fun fillInStackTrace(): Throwable = this
}

class PList(val items: ArrayList<Any?> = ArrayList()) {
    constructor(c: Collection<Any?>) : this(ArrayList(c))
    override fun equals(other: Any?) = other is PList && Ops.listEq(items, other.items)
    override fun hashCode() = System.identityHashCode(this)
    override fun toString() = Show.show(this)
}

class PTuple(val items: List<Any?>) {
    override fun equals(other: Any?) = other is PTuple && Ops.listEq(items, other.items)
    override fun hashCode(): Int {
        var h = 7
        for (x in items) h = h * 31 + Ops.hash(x)
        return h
    }
    override fun toString() = Show.show(this)
}

/** Map keys go through Key so that 1 and 1.0 (and true) find the same entry, as in Python. */
class PMap(val map: LinkedHashMap<Any?, Any?> = LinkedHashMap()) {
    override fun equals(other: Any?) = other is PMap && map.size == other.map.size &&
            map.all { (k, v) -> other.map.containsKey(k) && Ops.eq(v, other.map[k]) }
    override fun hashCode() = System.identityHashCode(this)
    override fun toString() = Show.show(this)
}

class PSet(val set: LinkedHashSet<Any?> = LinkedHashSet()) {
    override fun equals(other: Any?) = other is PSet && set == other.set
    override fun hashCode() = System.identityHashCode(this)
    override fun toString() = Show.show(this)
}

class PRange(val start: Long, val stop: Long, val step: Long) {
    val size: Long
        get() = if (step > 0) maxOf(0L, (stop - start + step - 1) / step) else maxOf(0L, (start - stop - step - 1) / -step)
    fun get(i: Long) = start + i * step
    fun contains(v: Long) = if (step > 0) v >= start && v < stop && (v - start) % step == 0L
    else v <= start && v > stop && (start - v) % (-step) == 0L
    override fun equals(other: Any?) = other is PRange && start == other.start && stop == other.stop && step == other.step
    override fun hashCode() = (start * 31 + stop).toInt()
}

/** Anything that can be called with (args, named args). */
interface Callable {
    val name: String
    fun call(args: Array<Any?>, kw: Map<String, Any?>?): Any?
}

/** A built-in function. */
class Native(override val name: String, val fn: (Array<Any?>, Map<String, Any?>?) -> Any?) : Callable {
    override fun call(args: Array<Any?>, kw: Map<String, Any?>?) = fn(args, kw)
    override fun toString() = "fn $name"
}

class TraitType(val name: String, val required: List<String>, val defaults: Map<String, Callable>) {
    override fun toString() = "trait $name"
}

class StructType(
    val name: String,
    val parent: StructType?,
    val fields: Array<String>,
) {
    lateinit var init: (StructObj, Array<Any?>, Map<String, Any?>?) -> Unit
    val methods = HashMap<String, Callable>()      // take self
    val statics = HashMap<String, Callable>()      // do not
    val traits = ArrayList<TraitType>()
    val index = HashMap<String, Int>().also { m -> fields.forEachIndexed { i, f -> m[f] = i } }

    fun findMethod(name: String): Callable? {
        var t: StructType? = this
        while (t != null) {
            t.methods[name]?.let { return it }
            t = t.parent
        }
        return null
    }

    fun findStatic(name: String): Callable? {
        var t: StructType? = this
        while (t != null) {
            t.statics[name]?.let { return it }
            t = t.parent
        }
        return null
    }

    fun isA(other: StructType): Boolean {
        var t: StructType? = this
        while (t != null) { if (t === other) return true; t = t.parent }
        return false
    }

    fun hasTrait(trait: TraitType): Boolean {
        var t: StructType? = this
        while (t != null) { if (t.traits.any { it === trait }) return true; t = t.parent }
        return false
    }

    override fun toString() = "struct $name"
}

class StructObj(val type: StructType, val values: Array<Any?>) {
    override fun equals(other: Any?): Boolean {
        if (other !is StructObj || other.type !== type) return false
        val custom = type.findMethod("equals")
        if (custom != null) return Ops.truthy(custom.call(arrayOf(this, other), null))
        for (i in values.indices) if (!Ops.eq(values[i], other.values[i])) return false
        return true
    }
    override fun hashCode() = System.identityHashCode(this)
    override fun toString() = Show.show(this)
}

class EnumType(val name: String) {
    val variants = ArrayList<Variant>()
    val byName = HashMap<String, Variant>()
    val methods = HashMap<String, Callable>()
    override fun toString() = "enum $name"
}

/** One option of an enum. With fields (Circle(r: float)) it is a constructor too. */
class Variant(val enum: EnumType, val name: String, val index: Int, val value: Any?, val fields: Array<String>?) {
    override fun toString() = "${enum.name}.$name"
}

/** A variant made with data: Shape.Circle(2.0). */
class VariantObj(val variant: Variant, val values: Array<Any?>) {
    override fun equals(other: Any?) = other is VariantObj && other.variant === variant &&
            values.indices.all { Ops.eq(values[it], other.values[it]) }
    override fun hashCode() = System.identityHashCode(this)
    override fun toString() = Show.show(this)
}

class Module(val name: String, val members: Map<String, Any?>) {
    override fun toString() = "library $name"
}

class Cell(@JvmField var v: Any?)

object Num {
    private val LMIN = BigInteger.valueOf(Long.MIN_VALUE)
    private val LMAX = BigInteger.valueOf(Long.MAX_VALUE)

    fun norm(b: BigInteger): Any = if (b >= LMIN && b <= LMAX) b.toLong() else b
    fun big(x: Any?): BigInteger = when (x) {
        is Long -> BigInteger.valueOf(x)
        is BigInteger -> x
        is Boolean -> if (x) BigInteger.ONE else BigInteger.ZERO
        else -> throw IllegalStateException()
    }
    fun isInt(x: Any?) = x is Long || x is BigInteger
    fun isNum(x: Any?) = x is Long || x is Double || x is BigInteger
    fun toDouble(x: Any?): Double = when (x) {
        is Long -> x.toDouble()
        is Double -> x
        is BigInteger -> x.toDouble()
        is Boolean -> if (x) 1.0 else 0.0
        else -> throw Errors.type("this needs a number, not ${Show.typeName(x)}")
    }
}

object Show {
    fun typeName(v: Any?): String = when (v) {
        null -> "nil"
        is Boolean -> "bool"
        is Long, is BigInteger -> "int"
        is Double -> "float"
        is String -> "str"
        is PList -> "list"
        is PMap -> "map"
        is PTuple -> "tuple"
        is PSet -> "set"
        is PRange -> "range"
        is StructObj -> v.type.name
        is Variant -> v.enum.name
        is VariantObj -> v.variant.enum.name
        is PcError -> "Error"
        is EnumType -> "enum"
        is Module -> "library"
        is StructType -> "struct"
        is TraitType -> "trait"
        is Callable -> "fn"
        else -> v.javaClass.simpleName
    }

    fun quote(v: Any?): String {
        if (v is String) {
            val sb = StringBuilder("\"")
            for (c in v) when (c) {
                '\\' -> sb.append("\\\\"); '"' -> sb.append("\\\""); '\n' -> sb.append("\\n"); '\t' -> sb.append("\\t")
                else -> sb.append(c)
            }
            return sb.append('"').toString()
        }
        return show(v)
    }

    fun show(v: Any?): String = show(v, null)

    private fun inner(v: Any?, seen: MutableSet<Any>?): String = if (v is String) quote(v) else show(v, seen)

    fun show(v: Any?, seenIn: MutableSet<Any>?): String {
        when (v) {
            is String -> return v
            null -> return "nil"
            is Boolean -> return if (v) "true" else "false"
            is Long -> return v.toString()
            is BigInteger -> return v.toString()
            is Double -> return floatRepr(v)
        }
        if (v is PList || v is PTuple || v is PMap || v is PSet || v is StructObj || v is VariantObj) {
            val seen = seenIn ?: java.util.Collections.newSetFromMap(java.util.IdentityHashMap())
            if (!seen.add(v!!)) return "[...]"
            try {
                return when (v) {
                    is PList -> v.items.joinToString(", ", "[", "]") { inner(it, seen) }
                    is PTuple -> v.items.joinToString(", ", "(", if (v.items.size == 1) ",)" else ")") { inner(it, seen) }
                    is PMap -> v.map.entries.joinToString(", ", "{", "}") { "${inner(it.key, seen)}: ${inner(it.value, seen)}" }
                    is PSet -> Ops.sortedOrSame(v.set.toList()).joinToString(", ", "set[", "]") { inner(it, seen) }
                    is StructObj -> {
                        val custom = v.type.findMethod("show")
                        if (custom != null) show(custom.call(arrayOf(v), null))
                        else v.type.fields.indices.joinToString(", ", "${v.type.name}(", ")") {
                            "${v.type.fields[it]}: ${inner(v.values[it], seen)}"
                        }
                    }
                    is VariantObj -> v.variant.fields!!.indices.joinToString(", ", "${v.variant}(", ")") {
                        "${v.variant.fields[it]}: ${inner(v.values[it], seen)}"
                    }
                    else -> ""
                }
            } finally {
                seen.remove(v)
            }
        }
        return when (v) {
            is PRange -> if (v.step == 1L) "${v.start}..${v.stop}" else "range(${v.start}, ${v.stop}, ${v.step})"
            is PcError -> v.shown
            is Native -> "fn ${v.name.trim('_')}"
            is Callable -> if (v.name.isEmpty() || v.name == "<lambda>") "fn" else "fn ${v.name}"
            else -> v.toString()
        }
    }

    /** Python's repr(float): the shortest digits that read back, in Python's layout. */
    fun floatRepr(d: Double): String {
        if (d.isNaN()) return "nan"
        if (d.isInfinite()) return if (d > 0) "inf" else "-inf"
        if (d == 0.0) return if (1.0 / d < 0) "-0.0" else "0.0"
        val s = java.lang.Double.toString(Math.abs(d))
        // digits and decimal exponent from Java's shortest form
        var mant = s
        var exp = 0
        val e = s.indexOf('E')
        if (e >= 0) { mant = s.substring(0, e); exp = s.substring(e + 1).toInt() }
        val dot = mant.indexOf('.')
        var digits = mant.substring(0, dot) + mant.substring(dot + 1)
        var pointPos = dot + exp           // digits[0 until pointPos] are before the point
        val lead = digits.indexOfFirst { it != '0' }
        digits = digits.substring(lead)
        pointPos -= lead
        digits = digits.trimEnd('0')
        if (digits.isEmpty()) digits = "0"
        val sciExp = pointPos - 1
        val sign = if (d < 0) "-" else ""
        if (sciExp < -4 || sciExp >= 16) {
            val m = if (digits.length == 1) digits else digits[0] + "." + digits.substring(1)
            val es = if (sciExp < 0) "-" + String.format("%02d", -sciExp) else "+" + String.format("%02d", sciExp)
            return "$sign${m}e$es"
        }
        val out = when {
            pointPos <= 0 -> "0." + "0".repeat(-pointPos) + digits
            pointPos >= digits.length -> digits + "0".repeat(pointPos - digits.length) + ".0"
            else -> digits.substring(0, pointPos) + "." + digits.substring(pointPos)
        }
        return sign + out
    }

    /** Python's format(value, spec), for the specs people write: [[fill]align][sign][0][width][,][.prec][type]. */
    fun format(v: Any?, spec: String): String {
        var i = 0
        var fill = ' '
        var align: Char? = null
        if (spec.length >= 2 && spec[1] in "<>^=") { fill = spec[0]; align = spec[1]; i = 2 }
        else if (spec.isNotEmpty() && spec[0] in "<>^=") { align = spec[0]; i = 1 }
        var sign = '-'
        if (i < spec.length && spec[i] in "+- ") { sign = spec[i]; i++ }
        if (i < spec.length && spec[i] == '#') i++
        if (i < spec.length && spec[i] == '0') { if (align == null) { fill = '0'; align = '=' }; i++ }
        var width = 0
        while (i < spec.length && spec[i].isDigit()) { width = width * 10 + (spec[i] - '0'); i++ }
        var comma = false
        if (i < spec.length && (spec[i] == ',' || spec[i] == '_')) { comma = true; i++ }
        var prec = -1
        if (i < spec.length && spec[i] == '.') {
            i++; prec = 0
            while (i < spec.length && spec[i].isDigit()) { prec = prec * 10 + (spec[i] - '0'); i++ }
        }
        val type = if (i < spec.length) spec[i] else null
        if (i < spec.length - 1) throw Errors.value("cannot format ${typeName(v)} with :$spec")
        val body: String
        var negative = false
        when {
            v is String || v == null || v is Boolean || !(Num.isNum(v)) -> {
                if (type != null && type != 's') throw Errors.value("cannot format ${typeName(v)} with :$spec")
                var s = show(v)
                if (prec >= 0 && s.length > prec) s = s.substring(0, prec)
                return pad(s, width, fill, align ?: '<')
            }
            else -> {
                val t = type ?: if (Num.isInt(v)) 'd' else if (prec >= 0) 'g' else 'r'
                if (Num.isInt(v) && t in "dxXbo" ) {
                    val b = Num.big(v)
                    negative = b.signum() < 0
                    val a = b.abs()
                    var s = when (t) { 'x' -> a.toString(16); 'X' -> a.toString(16).uppercase(); 'b' -> a.toString(2); 'o' -> a.toString(8); else -> a.toString() }
                    if (comma) s = group(s)
                    body = s
                } else {
                    val d = Num.toDouble(v)
                    negative = d < 0 || (d == 0.0 && 1.0 / d < 0)
                    val a = Math.abs(d)
                    body = when (t) {
                        'f', 'F', '%' -> {
                            val x = if (t == '%') a * 100 else a
                            val p = if (prec < 0) 6 else prec
                            var s = if (x.isInfinite()) "inf" else if (x.isNaN()) "nan"
                            else BigDecimal(x).setScale(p, RoundingMode.HALF_EVEN).toPlainString()
                            if (comma) { val dot = s.indexOf('.'); s = if (dot < 0) group(s) else group(s.substring(0, dot)) + s.substring(dot) }
                            if (t == '%') "$s%" else s
                        }
                        'e', 'E' -> {
                            val p = if (prec < 0) 6 else prec
                            var s = String.format(java.util.Locale.ROOT, "%.${p}e", a)
                            s = s.replace(Regex("e([+-])(\\d)$"), "e$10$2")
                            if (t == 'E') s.uppercase() else s
                        }
                        'g', 'G' -> {
                            val p = if (prec <= 0) (if (prec == 0) 1 else 6) else prec
                            if (a == 0.0) "0" else {
                                val bd = BigDecimal(a).round(java.math.MathContext(p, RoundingMode.HALF_EVEN))
                                val exp = bd.precision() - bd.scale() - 1
                                if (exp < -4 || exp >= p) {
                                    var s = String.format(java.util.Locale.ROOT, "%.${p - 1}e", a)
                                    val mant = s.substringBefore('e').let { if (it.contains('.')) it.trimEnd('0').trimEnd('.') else it }
                                    val ex = s.substringAfter('e').toInt()
                                    s = mant + "e" + (if (ex < 0) "-" else "+") + String.format("%02d", Math.abs(ex))
                                    s
                                } else bd.toPlainString().let { if (it.contains('.')) it.trimEnd('0').trimEnd('.') else it }
                            }
                        }
                        'd' -> throw Errors.value("cannot format a float with :d - use :.0f")
                        else -> floatRepr(a)
                    }
                }
            }
        }
        val signStr = if (negative) "-" else if (sign == '+') "+" else if (sign == ' ') " " else ""
        if (align == '=') {
            val total = signStr.length + body.length
            return signStr + fill.toString().repeat(maxOf(0, width - total)) + body
        }
        return pad(signStr + body, width, fill, align ?: '>')
    }

    private fun group(s: String): String {
        val sb = StringBuilder()
        for ((k, c) in s.withIndex()) {
            if (k > 0 && (s.length - k) % 3 == 0) sb.append(',')
            sb.append(c)
        }
        return sb.toString()
    }

    private fun pad(s: String, width: Int, fill: Char, align: Char): String {
        if (s.length >= width) return s
        val n = width - s.length
        return when (align) {
            '<' -> s + fill.toString().repeat(n)
            '^' -> fill.toString().repeat(n / 2) + s + fill.toString().repeat(n - n / 2)
            else -> fill.toString().repeat(n) + s
        }
    }
}

object Errors {
    fun type(m: String) = PcError(m, "Type")
    fun value(m: String) = PcError(m, "Value")
    fun index(m: String = "that index is past the end of the list") = PcError(m, "Index")
    fun key(k: Any?) = PcError("the map has no key ${Show.quote(k)} - use m.get(key, default) to be safe", "Key")
    fun field(owner: String, name: String) = PcError("$owner has no field or method '$name'", "Field")
    fun divZero() = PcError("division by zero", "DivideByZero")
    fun name(m: String) = PcError(m, "Name")
}
