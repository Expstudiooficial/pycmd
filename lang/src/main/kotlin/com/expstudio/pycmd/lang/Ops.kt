package com.expstudio.pycmd.lang

import java.math.BigInteger

/** Arithmetic, comparison, indexing and looping, with PyCmd's rules and words. */
object Ops {
    fun truthy(v: Any?): Boolean = when (v) {
        null -> false
        is Boolean -> v
        is Long -> v != 0L
        is Double -> v != 0.0
        is String -> v.isNotEmpty()
        is PList -> v.items.isNotEmpty()
        is PMap -> v.map.isNotEmpty()
        is PSet -> v.set.isNotEmpty()
        is PTuple -> v.items.isNotEmpty()
        is PRange -> v.size > 0
        is BigInteger -> v.signum() != 0
        else -> true
    }

    // ------------------------------------------------------------ numbers
    private fun asIntish(v: Any?): Any? = if (v is Boolean) (if (v) 1L else 0L) else v

    fun neg(v: Any?): Any? = when (val x = asIntish(v)) {
        is Long -> if (x == Long.MIN_VALUE) BigInteger.valueOf(x).negate() else -x
        is Double -> -x
        is BigInteger -> Num.norm(x.negate())
        is StructObj -> x.type.findMethod("neg")?.call(arrayOf(x), null) ?: throw Errors.type("cannot use - on ${Show.typeName(x)}")
        else -> throw Errors.type("cannot use - on ${Show.typeName(v)}")
    }

    fun pos(v: Any?): Any? = if (Num.isNum(asIntish(v))) asIntish(v) else throw Errors.type("cannot use + on ${Show.typeName(v)}")

    private fun bad(op: String, a: Any?, b: Any?): PcError {
        if (op == "+" && a is String) return Errors.type("cannot add text and ${Show.typeName(b)} with + - put the value " +
                "in the text instead: \"total: {n}\", or use str(n)")
        return Errors.type("cannot use $op on ${Show.typeName(a)} and ${Show.typeName(b)}")
    }

    fun add(a: Any?, b: Any?): Any? {
        if (a is Long && b is Long) {
            val r = a + b
            if (((a xor r) and (b xor r)) < 0) return BigInteger.valueOf(a).add(BigInteger.valueOf(b))
            return r
        }
        if (a is Double && b is Double) return a + b
        if (a is String && b is String) return a + b
        return addSlow(a, b)
    }

    private fun addSlow(a0: Any?, b0: Any?): Any? {
        val a = asIntish(a0); val b = asIntish(b0)
        if (a is Long && b is Long) return add(a, b)
        if (Num.isNum(a) && Num.isNum(b)) {
            if (a is Double || b is Double) return Num.toDouble(a) + Num.toDouble(b)
            return Num.norm(Num.big(a).add(Num.big(b)))
        }
        if (a is PList && b is PList) return PList(ArrayList<Any?>(a.items.size + b.items.size).apply { addAll(a.items); addAll(b.items) })
        if (a is PTuple && b is PTuple) return PTuple(a.items + b.items)
        if (a0 is StructObj) a0.type.findMethod("plus")?.let { return it.call(arrayOf(a0, b0), null) }
        throw bad("+", a0, b0)
    }

    fun sub(a: Any?, b: Any?): Any? {
        if (a is Long && b is Long) {
            val r = a - b
            if (((a xor b) and (a xor r)) < 0) return BigInteger.valueOf(a).subtract(BigInteger.valueOf(b))
            return r
        }
        if (a is Double && b is Double) return a - b
        val x = asIntish(a); val y = asIntish(b)
        if (Num.isNum(x) && Num.isNum(y)) {
            if (x is Double || y is Double) return Num.toDouble(x) - Num.toDouble(y)
            return Num.norm(Num.big(x).subtract(Num.big(y)))
        }
        if (a is PSet && b is PSet) return PSet(LinkedHashSet(a.set).apply { removeAll(b.set) })
        if (a is StructObj) a.type.findMethod("minus")?.let { return it.call(arrayOf(a, b), null) }
        throw bad("-", a, b)
    }

    fun mul(a: Any?, b: Any?): Any? {
        if (a is Long && b is Long) {
            val hi = Math.multiplyHigh(a, b)
            val lo = a * b
            if ((hi == 0L && lo >= 0) || (hi == -1L && lo < 0)) return lo
            return Num.norm(BigInteger.valueOf(a).multiply(BigInteger.valueOf(b)))
        }
        if (a is Double && b is Double) return a * b
        val x = asIntish(a); val y = asIntish(b)
        if (Num.isNum(x) && Num.isNum(y)) {
            if (x is Double || y is Double) return Num.toDouble(x) * Num.toDouble(y)
            return Num.norm(Num.big(x).multiply(Num.big(y)))
        }
        if (x is String && y is Long) return if (y <= 0) "" else x.repeat(checkRepeat(y, x.length))
        if (x is Long && y is String) return mul(y, x)
        if (x is PList && y is Long) {
            val out = ArrayList<Any?>()
            repeat(if (y <= 0) 0 else checkRepeat(y, x.items.size)) { out.addAll(x.items) }
            return PList(out)
        }
        if (x is Long && y is PList) return mul(y, x)
        if (a is StructObj) a.type.findMethod("times")?.let { return it.call(arrayOf(a, b), null) }
        throw bad("*", a, b)
    }

    private fun checkRepeat(n: Long, size: Int): Int {
        if (n * maxOf(size, 1) > 50_000_000) throw PcError("that would make something too big to hold", "Memory")
        return n.toInt()
    }

    fun div(a: Any?, b: Any?): Any? {
        val x = asIntish(a); val y = asIntish(b)
        if (Num.isNum(x) && Num.isNum(y)) {
            val d = Num.toDouble(y)
            if (d == 0.0) throw Errors.divZero()
            if (x is BigInteger || y is BigInteger) {
                return java.math.BigDecimal(Num.big(x)).divide(java.math.BigDecimal(Num.big(y)), java.math.MathContext.DECIMAL64).toDouble()
            }
            return Num.toDouble(x) / d
        }
        if (a is StructObj) a.type.findMethod("div")?.let { return it.call(arrayOf(a, b), null) }
        throw bad("/", a, b)
    }

    fun floorDiv(a: Any?, b: Any?): Any? {
        val x = asIntish(a); val y = asIntish(b)
        if (x is Long && y is Long) {
            if (y == 0L) throw Errors.divZero()
            if (x == Long.MIN_VALUE && y == -1L) return BigInteger.valueOf(x).negate()
            return Math.floorDiv(x, y)
        }
        if (Num.isNum(x) && Num.isNum(y)) {
            if (x is Double || y is Double) {
                val d = Num.toDouble(y)
                if (d == 0.0) throw Errors.divZero()
                return Math.floor(Num.toDouble(x) / d)
            }
            val bb = Num.big(y)
            if (bb.signum() == 0) throw Errors.divZero()
            val qr = Num.big(x).divideAndRemainder(bb)
            var q = qr[0]
            if (qr[1].signum() != 0 && (qr[1].signum() != bb.signum())) q = q.subtract(BigInteger.ONE)
            return Num.norm(q)
        }
        throw bad("//", a, b)
    }

    fun mod(a: Any?, b: Any?): Any? {
        val x = asIntish(a); val y = asIntish(b)
        if (x is Long && y is Long) {
            if (y == 0L) throw Errors.divZero()
            return Math.floorMod(x, y)
        }
        if (Num.isNum(x) && Num.isNum(y)) {
            if (x is Double || y is Double) {
                val p = Num.toDouble(x); val q = Num.toDouble(y)
                if (q == 0.0) throw Errors.divZero()
                val r = p % q
                return if (r != 0.0 && (r < 0) != (q < 0)) r + q else r
            }
            val bb = Num.big(y)
            if (bb.signum() == 0) throw Errors.divZero()
            var r = Num.big(x).mod(bb.abs())
            if (bb.signum() < 0 && r.signum() != 0) r = r.add(bb)
            return Num.norm(r)
        }
        if (a is StructObj) a.type.findMethod("rem")?.let { return it.call(arrayOf(a, b), null) }
        throw bad("%", a, b)
    }

    fun pow(a: Any?, b: Any?): Any? {
        val x = asIntish(a); val y = asIntish(b)
        if (Num.isInt(x) && Num.isInt(y)) {
            val e = Num.big(y)
            if (e.signum() >= 0) {
                if (e.bitLength() > 31 || (Num.big(x).bitLength().toLong() * e.toLong() > 10_000_000))
                    throw PcError("that number would be too big to hold", "Overflow")
                return Num.norm(Num.big(x).pow(e.toInt()))
            }
            return Math.pow(Num.toDouble(x), Num.toDouble(y))
        }
        if (Num.isNum(x) && Num.isNum(y)) {
            val r = Math.pow(Num.toDouble(x), Num.toDouble(y))
            if (r.isNaN() && !Num.toDouble(x).isNaN()) throw Errors.value("that number is outside what this maths function accepts")
            return r
        }
        throw bad("**", a, b)
    }

    // ------------------------------------------------------------ comparing
    fun eq(a: Any?, b: Any?): Boolean {
        if (a === b) return true
        if (a == null || b == null) return false
        if (a is Long && b is Long) return a == b
        if (a is String && b is String) return a == b
        val x = asIntish(a); val y = asIntish(b)
        if (Num.isNum(x) && Num.isNum(y)) {
            if (x is Double || y is Double) return Num.toDouble(x) == Num.toDouble(y)
            return Num.big(x) == Num.big(y)
        }
        if (a is PList && b is PList) return listEq(a.items, b.items)
        if (a is PTuple && b is PTuple) return listEq(a.items, b.items)
        return a == b
    }

    fun listEq(a: List<Any?>, b: List<Any?>): Boolean {
        if (a.size != b.size) return false
        for (i in a.indices) if (!eq(a[i], b[i])) return false
        return true
    }

    fun hash(v: Any?): Int = when (v) {
        null -> 0
        is Long -> v.toDouble().hashCode()
        is Double -> v.hashCode()
        is Boolean -> if (v) 1.0.hashCode() else 0.0.hashCode()
        else -> v.hashCode()
    }

    /** <0, 0, >0 - or an error saying the two cannot be ordered. */
    fun compare(a: Any?, b: Any?, op: String = "<"): Int {
        if (a is Long && b is Long) return a.compareTo(b)
        if (a is String && b is String) return a.compareTo(b)
        val x = asIntish(a); val y = asIntish(b)
        if (Num.isNum(x) && Num.isNum(y)) {
            if (x is Double || y is Double) {
                val p = Num.toDouble(x); val q = Num.toDouble(y)
                return if (p < q) -1 else if (p > q) 1 else 0
            }
            return Num.big(x).compareTo(Num.big(y))
        }
        if ((a is PList && b is PList) || (a is PTuple && b is PTuple)) {
            val p = if (a is PList) a.items else (a as PTuple).items
            val q = if (b is PList) b.items else (b as PTuple).items
            for (i in 0 until minOf(p.size, q.size)) {
                if (!eq(p[i], q[i])) return compare(p[i], q[i], op)
            }
            return p.size.compareTo(q.size)
        }
        if (a is Variant && b is Variant && a.enum === b.enum) return a.index.compareTo(b.index)
        if (a is StructObj) a.type.findMethod("compare")?.let {
            return Num.toDouble(it.call(arrayOf(a, b), null)).let { d -> if (d < 0) -1 else if (d > 0) 1 else 0 }
        }
        throw Errors.type("cannot compare ${Show.typeName(a)} and ${Show.typeName(b)} with $op")
    }

    fun cmpOp(op: String, a: Any?, b: Any?): Boolean = when (op) {
        "==" -> eq(a, b)
        "!=" -> !eq(a, b)
        "<" -> compare(a, b, op) < 0
        "<=" -> compare(a, b, op) <= 0
        ">" -> compare(a, b, op) > 0
        else -> compare(a, b, op) >= 0
    }

    val COMPARATOR = Comparator<Any?> { a, b -> compare(a, b) }

    fun sortedOrSame(xs: List<Any?>): List<Any?> = try { xs.sortedWith(COMPARATOR) } catch (e: PcError) { xs }

    // ------------------------------------------------------------ containers
    fun contains(container: Any?, item: Any?): Boolean = when (container) {
        is String -> if (item is String) container.contains(item)
        else throw Errors.type("'in' on text needs text on the left, not ${Show.typeName(item)}")
        is PList -> container.items.any { eq(it, item) }
        is PTuple -> container.items.any { eq(it, item) }
        is PMap -> container.map.containsKey(key(item))
        is PSet -> container.set.contains(key(item))
        is PRange -> { val x = asIntish(item); x is Long && container.contains(x) }
        is StructObj -> {
            val m = container.type.findMethod("contains")
            if (m != null) truthy(m.call(arrayOf(container, item), null))
            else Ops.toList(container).any { eq(it, item) }
        }
        else -> throw Errors.type("${Show.typeName(container)} cannot be looped over")
    }

    /** Keys: a float with a whole value and a bool find the same entry as the int. */
    fun key(k: Any?): Any? = when (k) {
        is Double -> if (k == Math.floor(k) && !k.isInfinite() && Math.abs(k) < 9e15) k.toLong() else k
        is Boolean -> if (k) 1L else 0L
        is BigInteger -> Num.norm(k)
        else -> k
    }

    fun iterate(v: Any?): Iterator<Any?> = when (v) {
        is PList -> object : Iterator<Any?> {
            var i = 0
            override fun hasNext() = i < v.items.size
            override fun next() = v.items[i++]
        }
        is PTuple -> v.items.iterator()
        is PRange -> object : Iterator<Any?> {
            var i = 0L
            val n = v.size
            override fun hasNext() = i < n
            override fun next(): Any? = v.get(i++)
        }
        is String -> object : Iterator<Any?> {
            var i = 0
            override fun hasNext() = i < v.length
            override fun next(): Any? {
                val cp = v.codePointAt(i)
                val s = String(Character.toChars(cp))
                i += s.length
                return s
            }
        }
        is PMap -> ArrayList(v.map.keys).iterator()
        is PSet -> ArrayList(v.set).iterator()
        is StructObj -> {
            val m = v.type.findMethod("iter") ?: throw Errors.type("${v.type.name} cannot be looped over - give it fn iter(self)")
            iterate(m.call(arrayOf(v), null))
        }
        is Variant, is EnumType -> if (v is EnumType) v.variants.iterator() else throw Errors.type("enum value cannot be looped over")
        else -> throw Errors.type("${Show.typeName(v)} cannot be looped over")
    }

    fun toList(v: Any?): ArrayList<Any?> = when (v) {
        is PList -> ArrayList(v.items)
        is PTuple -> ArrayList(v.items)
        is PMap -> ArrayList(v.map.entries.map { PTuple(listOf(it.key, it.value)) })
        else -> ArrayList<Any?>().also { out -> iterate(v).forEach { out.add(it) } }
    }

    fun len(v: Any?): Long = when (v) {
        is String -> v.codePointCount(0, v.length).toLong()
        is PList -> v.items.size.toLong()
        is PMap -> v.map.size.toLong()
        is PSet -> v.set.size.toLong()
        is PTuple -> v.items.size.toLong()
        is PRange -> v.size
        is StructObj -> v.type.findMethod("len")?.let { Num.toDouble(it.call(arrayOf(v), null)).toLong() }
            ?: throw Errors.type("${v.type.name} has no length")
        null -> throw Errors.type("nil has no length")
        else -> throw Errors.type("${Show.typeName(v)} has no length")
    }

    private fun idx(i: Any?, size: Int, what: String): Int {
        val x = asIntish(i)
        if (x !is Long) throw Errors.type("list indices must be int, not ${Show.typeName(i)}".replace("list", what))
        val j = if (x < 0) x + size else x
        if (j < 0 || j >= size) throw Errors.index(
            when (what) { "list" -> "that index is past the end of the list"; "text" -> "that index is past the end of the text"; else -> "that index is past the end" })
        return j.toInt()
    }

    fun getIndex(obj: Any?, i: Any?): Any? = when (obj) {
        is PList -> obj.items[idx(i, obj.items.size, "list")]
        is PMap -> { val k = key(i); if (obj.map.containsKey(k)) obj.map[k] else throw Errors.key(i) }
        is String -> {
            if (obj.length == obj.codePointCount(0, obj.length)) obj[idx(i, obj.length, "text")].toString()
            else { val cps = obj.codePoints().toArray(); String(Character.toChars(cps[idx(i, cps.size, "text")])) }
        }
        is PTuple -> obj.items[idx(i, obj.items.size, "tuple")]
        is PRange -> obj.get(idx(i, obj.size.toInt(), "range").toLong())
        is StructObj -> {
            val m = obj.type.findMethod("get") ?: throw Errors.type("${obj.type.name} cannot be indexed with [] - give it fn get(self, i)")
            m.call(arrayOf(obj, i), null)
        }
        null -> throw Errors.type("nil cannot be indexed with []")
        else -> throw Errors.type("${Show.typeName(obj)} cannot be indexed with []")
    }

    fun setIndex(obj: Any?, i: Any?, v: Any?) {
        when (obj) {
            is PList -> obj.items[idx(i, obj.items.size, "list")] = v
            is PMap -> obj.map[key(i)] = v
            is StructObj -> {
                val m = obj.type.findMethod("set") ?: throw Errors.type("${obj.type.name} cannot be changed with [] - give it fn set(self, i, value)")
                m.call(arrayOf(obj, i, v), null)
            }
            is String -> throw Errors.type("text cannot be changed in place - make a new one")
            is PTuple -> throw Errors.type("a tuple cannot be changed - use a list")
            else -> throw Errors.type("${Show.typeName(obj)} cannot be changed with []")
        }
    }

    fun slice(obj: Any?, start: Any?, stop: Any?, step: Any?): Any? {
        val st = if (step == null) 1L else asIntish(step) as? Long ?: throw Errors.type("a slice step must be an int")
        if (st == 0L) throw Errors.value("a slice step cannot be zero")
        fun bounds(n: Int): IntArray {
            fun norm(v: Any?, def: Long): Long {
                if (v == null) return def
                var x = asIntish(v) as? Long ?: throw Errors.type("slice indices must be int")
                if (x < 0) x += n
                return if (st > 0) x.coerceIn(0, n.toLong()) else x.coerceIn(-1, n.toLong() - 1)
            }
            val a = norm(start, if (st > 0) 0 else n.toLong() - 1)
            val b = norm(stop, if (st > 0) n.toLong() else -1)
            return intArrayOf(a.toInt(), b.toInt())
        }
        fun <T> pick(src: List<T>): ArrayList<T> {
            val (a, b) = bounds(src.size).let { it[0] to it[1] }
            val out = ArrayList<T>()
            var k = a.toLong()
            if (st > 0) while (k < b) { out.add(src[k.toInt()]); k += st }
            else while (k > b) { out.add(src[k.toInt()]); k += st }
            return out
        }
        return when (obj) {
            is PList -> PList(pick(obj.items))
            is PTuple -> PTuple(pick(obj.items))
            is String -> {
                if (st == 1L && obj.length == obj.codePointCount(0, obj.length)) {
                    val (a, b) = bounds(obj.length).let { it[0] to it[1] }
                    if (a >= b) "" else obj.substring(a, b)
                } else {
                    val cps = obj.codePoints().toArray().toList()
                    pick(cps).joinToString("") { String(Character.toChars(it)) }
                }
            }
            is PRange -> PList(pick(toList(obj)))
            else -> throw Errors.type("${Show.typeName(obj)} cannot be sliced")
        }
    }
}
