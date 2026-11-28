package com.expstudio.pycmd.lang

import java.math.BigDecimal
import java.math.BigInteger
import java.math.RoundingMode

/** Built-in functions, fields and methods. */
object Builtins {
    // ------------------------------------------------------------ helpers
    fun arg(a: Array<Any?>, i: Int, kw: Map<String, Any?>?, name: String, def: Any? = MISSING): Any? {
        if (i < a.size) return a[i]
        if (kw != null && kw.containsKey(name)) return kw[name]
        if (def === MISSING) throw Errors.type("missing the value for $name")
        return def
    }

    val MISSING = Any()

    fun call1(fn: Any?, x: Any?): Any? = if (fn is PcFunction) fn.call1(x) else Calls.call(fn, arrayOf(x), null)
    fun call2(fn: Any?, x: Any?, y: Any?): Any? = Calls.call(fn, arrayOf(x, y), null)

    fun int(v: Any?): Long = when (v) {
        is Long -> v
        is Boolean -> if (v) 1 else 0
        is Double -> if (v == Math.floor(v)) v.toLong() else throw Errors.type("this needs a whole number (an int), not float")
        else -> throw Errors.type("this needs a whole number (an int), not ${Show.typeName(v)}")
    }

    private fun str(v: Any?, what: String = "text"): String = v as? String ?: throw Errors.type("this needs $what, not ${Show.typeName(v)}")

    fun items(v: Any?): List<Any?> = when (v) {
        is PList -> v.items
        is PTuple -> v.items
        else -> Ops.toList(v)
    }

    fun toInt(v: Any?, base: Any? = null): Any? = when (v) {
        is String -> {
            val text = v.trim().replace("_", "")
            val radix = if (base == null) 10 else int(base).toInt()
            val t2 = if (radix == 16) text.removePrefix("0x").removePrefix("0X") else if (radix == 2) text.removePrefix("0b") else text
            try { t2.toLong(radix) } catch (e: NumberFormatException) {
                try { Num.norm(BigInteger(t2, radix)) } catch (e2: NumberFormatException) {
                    val d = t2.toDoubleOrNull() ?: throw Errors.value("cannot turn ${Show.quote(v)} into an int")
                    d.toLong()
                }
            }
        }
        is Double -> {
            if (v.isNaN() || v.isInfinite()) throw Errors.value("cannot turn ${Show.show(v)} into an int")
            if (Math.abs(v) < 9e18) v.toLong() else Num.norm(BigDecimal(v).toBigInteger())
        }
        is Long, is BigInteger -> v
        is Boolean -> if (v) 1L else 0L
        is Variant -> v.index.toLong()
        null -> throw Errors.value("cannot turn nil into an int")
        else -> throw Errors.type("int() cannot take ${Show.typeName(v)}")
    }

    fun toFloat(v: Any?): Double = when (v) {
        is String -> v.trim().replace("_", "").let { t ->
            when (t.lowercase()) { "inf", "infinity", "+inf" -> Double.POSITIVE_INFINITY; "-inf" -> Double.NEGATIVE_INFINITY; "nan" -> Double.NaN
                else -> t.toDoubleOrNull() ?: throw Errors.value("cannot turn ${Show.quote(v)} into a float") }
        }
        null -> throw Errors.value("cannot turn nil into a float")
        else -> Num.toDouble(v)
    }

    fun round(x: Any?, digits: Any?): Any? {
        if (digits == null) {
            return when (x) {
                is Long, is BigInteger -> x
                is Double -> { if (x.isNaN() || x.isInfinite()) throw Errors.value("cannot round ${Show.show(x)}"); Num.norm(BigDecimal(x).setScale(0, RoundingMode.HALF_EVEN).toBigInteger()) }
                else -> throw Errors.type("round needs a number")
            }
        }
        val n = int(digits).toInt()
        return when (x) {
            is Long, is BigInteger -> if (n >= 0) x else Num.norm(BigDecimal(Num.big(x)).setScale(n, RoundingMode.HALF_EVEN).toBigInteger())
            is Double -> if (x.isNaN() || x.isInfinite()) x else BigDecimal(x).setScale(n, RoundingMode.HALF_EVEN).toDouble()
            else -> throw Errors.type("round needs a number")
        }
    }

    fun minMax(args: Array<Any?>, kw: Map<String, Any?>?, max: Boolean): Any? {
        val values: List<Any?> = if (args.size == 1 && (args[0] is PList || args[0] is PTuple || args[0] is PSet || args[0] is PRange))
            Ops.toList(args[0]) else args.toList()
        if (values.isEmpty()) throw Errors.value(if (max) "max of nothing" else "min of nothing")
        val by = kw?.get("by") ?: kw?.get("key")
        var best = values[0]
        var bestKey = if (by != null) call1(by, best) else best
        for (i in 1 until values.size) {
            val k = if (by != null) call1(by, values[i]) else values[i]
            val c = Ops.compare(k, bestKey)
            if (if (max) c > 0 else c < 0) { best = values[i]; bestKey = k }
        }
        return best
    }

    fun sum(xs: Any?, start: Any? = 0L): Any? {
        var acc = start
        for (x in items(xs)) acc = Ops.add(acc, x)
        return acc
    }

    fun sortedList(xs: Any?, key: Any?, reverse: Boolean): ArrayList<Any?> {
        val list = Ops.toList(xs)
        if (key == null) list.sortWith(Ops.COMPARATOR)
        else {
            val keys = HashMap<Int, Any?>()
            val withKeys = list.map { it to call1(key, it) }
            val sorted = withKeys.sortedWith { a, b -> Ops.compare(a.second, b.second) }
            list.clear(); sorted.forEach { list.add(it.first) }
            keys.clear()
        }
        if (reverse) list.reverse()
        return list
    }

    fun deepCopy(v: Any?): Any? = when (v) {
        is PList -> PList(ArrayList(v.items.map { deepCopy(it) }))
        is PMap -> PMap(LinkedHashMap<Any?, Any?>().also { m -> v.map.forEach { (k, x) -> m[k] = deepCopy(x) } })
        is PSet -> PSet(LinkedHashSet(v.set))
        is PTuple -> PTuple(v.items.map { deepCopy(it) })
        is StructObj -> StructObj(v.type, Array(v.values.size) { deepCopy(v.values[it]) })
        else -> v
    }

    // ------------------------------------------------------------ the functions
    fun functions(rt: Runtime): Map<String, Any?> {
        val m = LinkedHashMap<String, Any?>()
        fun def(name: String, fn: (Array<Any?>, Map<String, Any?>?) -> Any?) { m[name] = Native(name, fn) }
        def("print") { a, kw ->
            val sep = kw?.get("sep")?.let { Show.show(it) } ?: " "
            val end = kw?.get("end")?.let { Show.show(it) } ?: "\n"
            val sb = StringBuilder()
            for ((i, v) in a.withIndex()) { if (i > 0) sb.append(sep); sb.append(Show.show(v)) }
            sb.append(end)
            rt.write(sb.toString())
            null
        }
        def("input") { a, _ ->
            if (a.isNotEmpty() && a[0] != null) rt.write(Show.show(a[0]))
            rt.flush()
            rt.readLine()
        }
        def("len") { a, _ -> Ops.len(a.getOrNull(0)) }
        def("str") { a, _ -> if (a.isEmpty()) "" else Show.show(a[0]) }
        def("int") { a, kw -> if (a.isEmpty()) 0L else toInt(a[0], a.getOrNull(1) ?: kw?.get("base")) }
        def("float") { a, _ -> if (a.isEmpty()) 0.0 else toFloat(a[0]) }
        def("bool") { a, _ -> if (a.isEmpty()) false else Ops.truthy(a[0]) }
        def("type") { a, _ -> Show.typeName(a.getOrNull(0)) }
        def("range") { a, _ ->
            when (a.size) {
                1 -> PRange(0, int(a[0]), 1)
                2 -> PRange(int(a[0]), int(a[1]), 1)
                3 -> { val st = int(a[2]); if (st == 0L) throw Errors.value("a range step cannot be zero"); PRange(int(a[0]), int(a[1]), st) }
                else -> throw Errors.type("range takes 1 to 3 numbers")
            }
        }
        def("abs") { a, _ ->
            when (val x = a[0]) {
                is Long -> if (x == Long.MIN_VALUE) BigInteger.valueOf(x).abs() else Math.abs(x)
                is Double -> Math.abs(x)
                is BigInteger -> x.abs()
                is Boolean -> if (x) 1L else 0L
                else -> throw Errors.type("abs needs a number, not ${Show.typeName(x)}")
            }
        }
        def("min") { a, kw -> minMax(a, kw, false) }
        def("max") { a, kw -> minMax(a, kw, true) }
        def("sum") { a, _ -> sum(a[0], a.getOrNull(1) ?: 0L) }
        def("round") { a, kw -> round(a[0], a.getOrNull(1) ?: kw?.get("digits")) }
        def("sorted") { a, kw -> PList(sortedList(a[0], kw?.get("key") ?: kw?.get("by"), Ops.truthy(kw?.get("reverse")))) }
        def("reversed") { a, _ -> reversed(a[0]) }
        def("enumerate") { a, kw ->
            val start = int(a.getOrNull(1) ?: kw?.get("start") ?: 0L)
            PList(ArrayList(Ops.toList(a[0]).mapIndexed { i, x -> PTuple(listOf(start + i, x)) }))
        }
        def("zip") { a, _ -> zip(a.map { Ops.toList(it) }) }
        def("keys") { a, _ -> PList(ArrayList((a[0] as? PMap ?: throw Errors.type("keys needs a map")).map.keys)) }
        def("values") { a, _ -> PList(ArrayList((a[0] as? PMap ?: throw Errors.type("values needs a map")).map.values)) }
        def("items") { a, _ -> PList(ArrayList((a[0] as? PMap ?: throw Errors.type("items needs a map")).map.entries.map { PTuple(listOf(it.key, it.value)) })) }
        def("set") { a, _ -> PSet(LinkedHashSet<Any?>().also { s -> if (a.isNotEmpty() && a[0] != null) Ops.iterate(a[0]).forEach { s.add(Ops.key(it)) } }) }
        def("list") { a, _ -> if (a.isEmpty() || a[0] == null) PList() else PList(Ops.toList(a[0])) }
        def("tuple") { a, _ -> if (a.isEmpty()) PTuple(emptyList()) else PTuple(Ops.toList(a[0])) }
        def("chr") { a, _ -> String(Character.toChars(int(a[0]).toInt())) }
        def("char") { a, _ -> String(Character.toChars(int(a[0]).toInt())) }
        def("ord") { a, _ ->
            val s = str(a[0])
            if (s.codePointCount(0, s.length) != 1) throw Errors.type("ord needs a single character, not text of length ${s.length}")
            s.codePointAt(0).toLong()
        }
        def("hex") { a, _ -> Num.big(int0(a[0])).let { if (it.signum() < 0) "-0x" + it.negate().toString(16) else "0x" + it.toString(16) } }
        def("bin") { a, _ -> Num.big(int0(a[0])).let { if (it.signum() < 0) "-0b" + it.negate().toString(2) else "0b" + it.toString(2) } }
        def("any") { a, _ -> val fn = a.getOrNull(1); Ops.toList(a[0]).any { Ops.truthy(if (fn != null) call1(fn, it) else it) } }
        def("all") { a, _ -> val fn = a.getOrNull(1); Ops.toList(a[0]).all { Ops.truthy(if (fn != null) call1(fn, it) else it) } }
        def("map") { a, _ -> PList(ArrayList(Ops.toList(a[0]).map { call1(a[1], it) })) }
        def("filter") { a, _ -> PList(ArrayList(Ops.toList(a[0]).filter { Ops.truthy(call1(a[1], it)) })) }
        def("reduce") { a, _ -> reduce(a[0], a.drop(1)) }
        def("Error") { a, kw -> PcError(Show.show(a.getOrNull(0) ?: kw?.get("message") ?: ""), Show.show(a.getOrNull(1) ?: kw?.get("kind") ?: "Error")) }
        def("exit") { a, _ -> throw PcExit((a.getOrNull(0) as? Long)?.toInt() ?: 0) }
        def("copy") { a, _ -> deepCopy(a[0]) }
        def("clamp") { a, _ -> if (Ops.compare(a[0], a[1]) < 0) a[1] else if (Ops.compare(a[0], a[2]) > 0) a[2] else a[0] }
        def("repr") { a, _ -> Show.quote(a[0]) }
        def("pow") { a, _ ->
            if (a.size == 3) Num.norm(Num.big(a[0]).modPow(Num.big(a[1]), Num.big(a[2]))) else Ops.pow(a[0], a[1])
        }
        def("divmod") { a, _ -> PTuple(listOf(Ops.floorDiv(a[0], a[1]), Ops.mod(a[0], a[1]))) }
        def("is_nil") { a, _ -> a[0] == null }
        m["args"] = PList(ArrayList<Any?>(rt.argv))
        return m
    }

    private fun int0(v: Any?): Any = when (v) { is Long, is BigInteger -> v; is Boolean -> if (v) 1L else 0L; else -> throw Errors.type("this needs an int") }

    fun reversed(v: Any?): Any? = if (v is String) StringBuilder(v).reverse().toString() else PList(Ops.toList(v).also { it.reverse() })

    fun zip(lists: List<List<Any?>>): PList {
        if (lists.isEmpty()) return PList()
        val n = lists.minOf { it.size }
        return PList(ArrayList((0 until n).map { i -> PTuple(lists.map { it[i] }) }))
    }

    fun reduce(xs: Any?, rest: List<Any?>): Any? {
        val items = Ops.toList(xs)
        val (fn, start) = if (rest.size == 1) rest[0] to MISSING else rest[1] to rest[0]
        var acc: Any?
        var i = 0
        if (start === MISSING) {
            if (items.isEmpty()) throw Errors.value("reduce of an empty list needs a starting value")
            acc = items[0]; i = 1
        } else acc = start
        while (i < items.size) { acc = call2(fn, acc, items[i]); i++ }
        return acc
    }

    // ------------------------------------------------------------ fields
    fun getAttr(o: Any?, name: String): Any? {
        when (o) {
            is StructObj -> {
                val i = o.type.index[name]
                if (i != null) return o.values[i]
                o.type.findMethod(name)?.let { return Bound(o, it) }
                throw Errors.field(o.type.name, name)
            }
            is Module -> {
                if (o.members.containsKey(name)) return o.members[name]
                val hint = Similar.closest(name, o.members.keys)?.let { " - did you mean $it?" } ?: ""
                throw PcError("library ${o.name} has no $name$hint", "Field")
            }
            is EnumType -> {
                o.byName[name]?.let { return it }
                o.methods[name]?.let { return it }
                return when (name) {
                    "all" -> Native("all") { _, _ -> PList(ArrayList<Any?>(o.variants)) }
                    "count" -> Native("count") { _, _ -> o.variants.size.toLong() }
                    "from_value" -> Native("from_value") { a, _ -> o.variants.firstOrNull { Ops.eq(it.value, a[0]) } }
                    "from_name" -> Native("from_name") { a, _ -> o.byName[a[0]] }
                    "name" -> o.name
                    else -> throw Errors.field(o.name, name)
                }
            }
            is StructType -> {
                o.findStatic(name)?.let { return it }
                o.findMethod(name)?.let { return it }
                if (name == "name") return o.name
                if (name == "fields") return PList(ArrayList<Any?>(o.fields.toList()))
                throw Errors.field(o.name, name)
            }
            is Variant -> return when (name) {
                "name" -> o.name; "index" -> o.index.toLong(); "value" -> o.value
                else -> o.enum.methods[name]?.let { Bound(o, it) } ?: throw Errors.field("${o.enum.name}.${o.name}", name)
            }
            is VariantObj -> {
                val i = o.variant.fields!!.indexOf(name)
                if (i >= 0) return o.values[i]
                return when (name) {
                    "name" -> o.variant.name; "index" -> o.variant.index.toLong()
                    else -> o.variant.enum.methods[name]?.let { Bound(o, it) } ?: throw Errors.field(o.variant.toString(), name)
                }
            }
            is PcError -> return when (name) {
                "message" -> o.msg; "kind" -> o.kind; "value" -> o.value ?: o.msg; "line" -> o.line.toLong()
                else -> throw Errors.field("Error", name)
            }
            is PRange -> return when (name) {
                "start" -> o.start; "stop" -> o.stop; "step" -> o.step
                else -> bindNative(o, name)
            }
            is TraitType -> if (name == "name") return o.name else throw Errors.field("trait ${o.name}", name)
            null -> throw PcError("nil has no field $name - the value is missing (use ?. to allow nil)", "Type")
        }
        return bindNative(o, name)
    }

    private fun bindNative(o: Any?, name: String): Any? {
        val id = methodId(name)
        if (id < 0 || !supports(o, name)) throw Errors.field(Show.typeName(o), name)
        return Native(name) { a, kw -> callMethod(o, name, id, a, kw) }
    }

    private fun supports(o: Any?, name: String): Boolean = try {
        // A cheap probe: ask the method table without running anything.
        when (o) {
            is String -> name in STR
            is PList -> name in LIST
            is PTuple, is PRange -> name in SEQ
            is PMap -> name in MAP
            is PSet -> name in SET
            is Long, is Double, is BigInteger, is Boolean -> name in NUM
            else -> false
        }
    } catch (e: Exception) { false }

    fun setAttr(o: Any?, name: String, v: Any?) {
        when (o) {
            is StructObj -> {
                val i = o.type.index[name] ?: throw Errors.field(o.type.name, name)
                o.values[i] = v
            }
            is Module -> throw Errors.type("a library cannot be changed")
            null -> throw PcError("nil has no field $name - the value is missing", "Type")
            else -> throw Errors.type("${Show.typeName(o)} has no fields to change")
        }
    }

    // ------------------------------------------------------------ methods
    private val STR = setOf("len", "upper", "lower", "title", "capitalize", "swapcase", "trim", "strip", "trim_start", "lstrip",
        "trim_end", "rstrip", "split", "lines", "splitlines", "words", "join", "replace", "starts_with", "startswith",
        "ends_with", "endswith", "find", "index_of", "rfind", "last_index_of", "index", "count", "contains", "has", "chars",
        "repeat", "reverse", "reversed", "to_int", "to_float", "to_str", "to_list", "to_set", "is_digit", "isdigit",
        "is_alpha", "isalpha", "is_alnum", "isalnum", "is_space", "isspace", "is_upper", "isupper", "is_lower", "islower",
        "pad_left", "rjust", "pad_right", "ljust", "center", "zfill", "char_at", "is_empty", "map", "filter", "each", "first",
        "last", "slice", "get", "sorted", "format", "format_map", "remove_prefix", "removeprefix", "remove_suffix",
        "removesuffix", "partition", "enumerate", "bytes", "code", "is_numeric")
    private val SEQ = setOf("len", "join", "contains", "has", "index_of", "index", "count", "map", "filter", "reduce", "each",
        "find", "find_index", "any", "all", "sum", "sum_by", "min", "max", "average", "sorted", "reversed", "first", "last",
        "take", "skip", "unique", "flatten", "zip", "enumerate", "chunk", "group_by", "partition", "slice", "get", "is_empty",
        "to_list", "to_set", "to_str", "copy", "window", "count_by", "max_by", "min_by", "distinct", "sort_by_key")
    private val LIST = SEQ + setOf("push", "append", "pop", "insert", "remove", "remove_at", "clear", "extend", "sort",
        "sort_by", "reverse", "repeat", "fill", "swap", "shuffle", "retain", "set")
    private val MAP = setOf("len", "keys", "values", "items", "get", "set", "has", "contains", "remove", "pop", "merge",
        "update", "clear", "copy", "is_empty", "each", "map", "filter", "to_list", "setdefault", "get_or_set", "count",
        "any", "all", "find", "to_str", "sorted_keys", "invert")
    private val SET = setOf("len", "add", "remove", "discard", "has", "contains", "union", "intersection", "difference",
        "symmetric_difference", "is_subset", "issubset", "is_superset", "is_empty", "each", "map", "filter", "to_list",
        "copy", "sorted", "clear", "to_str", "any", "all", "count", "sum", "min", "max")
    private val NUM = setOf("to_str", "to_int", "to_float", "is_integer", "abs", "times", "upto", "clamp", "is_even", "is_odd")

    private val IDS = HashMap<String, Int>().also { m ->
        (STR + LIST + MAP + SET + NUM).sorted().forEachIndexed { i, n -> m[n] = i }
    }

    fun methodId(name: String): Int = IDS[name] ?: -1

    fun callMethod(o: Any?, name: String, id: Int, a: Array<Any?>, kw: Map<String, Any?>?): Any? {
        when (o) {
            is StructObj -> {
                val m = o.type.findMethod(name)
                if (m != null) {
                    val all = arrayOfNulls<Any?>(a.size + 1)
                    all[0] = o; System.arraycopy(a, 0, all, 1, a.size)
                    return m.call(all, kw)
                }
                val i = o.type.index[name]
                if (i != null) return Calls.call(o.values[i], a, kw)
                throw Errors.field(o.type.name, name)
            }
            is Module -> return Calls.call(getAttr(o, name), a, kw)
            is EnumType, is StructType, is PcError, is TraitType -> return Calls.call(getAttr(o, name), a, kw)
            is Variant, is VariantObj -> {
                val enum = if (o is Variant) o.enum else (o as VariantObj).variant.enum
                val m = enum.methods[name] ?: return Calls.call(getAttr(o, name), a, kw)
                val all = arrayOfNulls<Any?>(a.size + 1)
                all[0] = o; System.arraycopy(a, 0, all, 1, a.size)
                return m.call(all, kw)
            }
            null -> throw PcError("nil has no method $name() - the value is missing", "Type")
        }
        if (id < 0) throw Errors.field(Show.typeName(o), name)
        return when (o) {
            is String -> if (name in STR) Methods.str(o, name, a, kw) else throw Errors.field("str", name)
            is PList -> if (name in LIST) Methods.list(o, name, a, kw) else throw Errors.field("list", name)
            is PTuple -> if (name in SEQ) Methods.seq(o.items, o, name, a, kw) else throw Errors.field("tuple", name)
            is PRange -> if (name in SEQ) Methods.seq(Ops.toList(o), o, name, a, kw) else throw Errors.field("range", name)
            is PMap -> if (name in MAP) Methods.map(o, name, a, kw) else throw Errors.field("map", name)
            is PSet -> if (name in SET) Methods.set(o, name, a, kw) else throw Errors.field("set", name)
            is Long, is Double, is BigInteger, is Boolean -> if (name in NUM) Methods.num(o, name, a) else throw Errors.field(Show.typeName(o), name)
            is Callable -> throw Errors.field("fn", name)
            else -> throw Errors.field(Show.typeName(o), name)
        }
    }
}
