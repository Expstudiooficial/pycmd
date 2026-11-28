package com.expstudio.pycmd.lang

import com.expstudio.pycmd.lang.Builtins.call1
import com.expstudio.pycmd.lang.Builtins.call2
import com.expstudio.pycmd.lang.Builtins.int

/** The methods of text, lists, tuples, ranges, maps, sets and numbers. */
object Methods {
    private fun s(v: Any?, what: String = "text"): String = v as? String ?: throw Errors.type("this needs $what, not ${Show.typeName(v)}")
    private fun list(xs: Collection<Any?>) = PList(ArrayList(xs))

    fun str(o: String, name: String, a: Array<Any?>, kw: Map<String, Any?>?): Any? = when (name) {
        "len" -> Ops.len(o)
        "upper" -> o.uppercase()
        "lower" -> o.lowercase()
        "title" -> titleCase(o)
        "capitalize" -> if (o.isEmpty()) o else o.substring(0, 1).uppercase() + o.substring(1).lowercase()
        "swapcase" -> o.map { if (it.isUpperCase()) it.lowercaseChar() else it.uppercaseChar() }.joinToString("")
        "trim", "strip" -> a.getOrNull(0)?.let { c -> o.trim { it in s(c) } } ?: o.trim { it.isWhitespace() }
        "trim_start", "lstrip" -> a.getOrNull(0)?.let { c -> o.trimStart { it in s(c) } } ?: o.trimStart { it.isWhitespace() }
        "trim_end", "rstrip" -> a.getOrNull(0)?.let { c -> o.trimEnd { it in s(c) } } ?: o.trimEnd { it.isWhitespace() }
        "split" -> split(o, a.getOrNull(0) ?: kw?.get("sep"), (a.getOrNull(1) ?: kw?.get("limit"))?.let { int(it).toInt() } ?: -1)
        "lines", "splitlines" -> list(o.split(Regex("\r\n|\n|\r")).let { if (it.isNotEmpty() && it.last().isEmpty()) it.dropLast(1) else it })
        "words" -> list(o.trim().split(Regex("\\s+")).filter { it.isNotEmpty() })
        "join" -> Builtins.items(a[0]).joinToString(o) { Show.show(it) }
        "replace" -> {
            val count = (a.getOrNull(2) as? Long)?.toInt() ?: -1
            if (count < 0) o.replace(s(a[0]), s(a[1])) else {
                var out = o; var n = 0; var from = 0
                val old = s(a[0]); val new = s(a[1])
                val sb = StringBuilder()
                while (n < count) { val i = out.indexOf(old, from); if (i < 0) break; sb.append(out, from, i).append(new); from = i + old.length; n++ }
                sb.append(out.substring(from)); out = sb.toString(); out
            }
        }
        "starts_with", "startswith" -> o.startsWith(s(a[0]))
        "ends_with", "endswith" -> o.endsWith(s(a[0]))
        "find", "index_of" -> o.indexOf(s(a[0])).toLong()
        "rfind", "last_index_of" -> o.lastIndexOf(s(a[0])).toLong()
        "index" -> o.indexOf(s(a[0])).let { if (it < 0) throw Errors.value("substring not found") else it.toLong() }
        "count" -> if (a.isEmpty()) Ops.len(o) else countOf(o, s(a[0]))
        "contains", "has" -> o.contains(s(a[0]))
        "chars" -> list(Ops.toList(o))
        "repeat" -> Ops.mul(o, a[0])
        "reverse", "reversed" -> StringBuilder(o).reverse().toString()
        "to_int" -> Builtins.toInt(o)
        "to_float" -> Builtins.toFloat(o)
        "to_str" -> o
        "to_list" -> list(Ops.toList(o))
        "to_set" -> PSet(LinkedHashSet(Ops.toList(o)))
        "is_digit", "isdigit", "is_numeric" -> o.isNotEmpty() && o.all { it.isDigit() }
        "is_alpha", "isalpha" -> o.isNotEmpty() && o.all { it.isLetter() }
        "is_alnum", "isalnum" -> o.isNotEmpty() && o.all { it.isLetterOrDigit() }
        "is_space", "isspace" -> o.isNotEmpty() && o.all { it.isWhitespace() }
        "is_upper", "isupper" -> o.any { it.isLetter() } && o.filter { it.isLetter() }.all { it.isUpperCase() }
        "is_lower", "islower" -> o.any { it.isLetter() } && o.filter { it.isLetter() }.all { it.isLowerCase() }
        "pad_left", "rjust" -> o.padStart(int(a[0]).toInt(), (a.getOrNull(1) as? String)?.firstOrNull() ?: ' ')
        "pad_right", "ljust" -> o.padEnd(int(a[0]).toInt(), (a.getOrNull(1) as? String)?.firstOrNull() ?: ' ')
        "center" -> { val w = int(a[0]).toInt(); val c = (a.getOrNull(1) as? String)?.firstOrNull() ?: ' '
            if (o.length >= w) o else { val n = w - o.length; val left = n / 2 + (n and w and 1)
                c.toString().repeat(left) + o + c.toString().repeat(n - left) } }
        "zfill" -> { val w = int(a[0]).toInt(); if (o.startsWith("-")) "-" + o.substring(1).padStart(w - 1, '0') else o.padStart(w, '0') }
        "char_at" -> { val i = int(a[0]); val n = o.length; if (i >= -n && i < n) Ops.getIndex(o, i) else null }
        "is_empty" -> o.isEmpty()
        "map" -> list(Ops.toList(o).map { call1(a[0], it) })
        "filter" -> list(Ops.toList(o).filter { Ops.truthy(call1(a[0], it)) })
        "each" -> { Ops.toList(o).forEach { call1(a[0], it) }; null }
        "first" -> if (o.isEmpty()) a.getOrNull(0) else Ops.getIndex(o, 0L)
        "last" -> if (o.isEmpty()) a.getOrNull(0) else Ops.getIndex(o, -1L)
        "slice" -> Ops.slice(o, a.getOrNull(0), a.getOrNull(1), null)
        "get" -> try { Ops.getIndex(o, a[0]) } catch (e: PcError) { a.getOrNull(1) }
        "sorted" -> list(Builtins.sortedList(o, kw?.get("key") ?: kw?.get("by"), Ops.truthy(kw?.get("reverse"))))
        "format" -> format(o, a, kw)
        "format_map" -> format(o, emptyArray(), (a[0] as? PMap)?.map?.mapKeys { Show.show(it.key) })
        "remove_prefix", "removeprefix" -> o.removePrefix(s(a[0]))
        "remove_suffix", "removesuffix" -> o.removeSuffix(s(a[0]))
        "partition" -> { val sep = s(a[0]); val i = o.indexOf(sep)
            if (i < 0) PTuple(listOf(o, "", "")) else PTuple(listOf(o.substring(0, i), sep, o.substring(i + sep.length))) }
        "enumerate" -> PList(ArrayList(Ops.toList(o).mapIndexed { i, x -> PTuple(listOf(i.toLong(), x)) }))
        "bytes" -> list(o.toByteArray(Charsets.UTF_8).map { (it.toInt() and 0xff).toLong() })
        "code" -> o.codePointAt(0).toLong()
        else -> throw Errors.field("str", name)
    }

    private fun countOf(o: String, x: String): Long {
        if (x.isEmpty()) return (o.length + 1).toLong()
        var c = 0L
        var i = o.indexOf(x)
        while (i >= 0) { c++; i = o.indexOf(x, i + x.length) }
        return c
    }

    private fun titleCase(o: String): String {
        val sb = StringBuilder()
        var prevLetter = false
        for (c in o) {
            sb.append(if (c.isLetter()) (if (prevLetter) c.lowercaseChar() else c.uppercaseChar()) else c)
            prevLetter = c.isLetter()
        }
        return sb.toString()
    }

    private fun split(o: String, sep: Any?, limit: Int): PList {
        if (sep == null) {
            val parts = o.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
            return list(parts)
        }
        val sp = s(sep)
        if (sp.isEmpty()) return list(Ops.toList(o))
        return list(if (limit < 0) o.split(sp) else o.split(sp, limit = limit + 1))
    }

    fun format(o: String, args: Array<Any?>, kw: Map<String, Any?>?): String {
        val out = StringBuilder()
        var i = 0
        var auto = 0
        while (i < o.length) {
            val c = o[i]
            if (c == '{') {
                if (o.startsWith("{{", i)) { out.append('{'); i += 2; continue }
                val j = o.indexOf('}', i)
                if (j < 0) throw Errors.value("format: a { is not closed")
                val key = o.substring(i + 1, j).trim()
                when {
                    key.isEmpty() -> { if (auto >= args.size) throw Errors.value("format: more {} than values"); out.append(Show.show(args[auto++])) }
                    key.all { it.isDigit() } -> out.append(Show.show(args.getOrNull(key.toInt()) ?: throw Errors.value("format: no value $key")))
                    kw != null && kw.containsKey(key) -> out.append(Show.show(kw[key]))
                    else -> throw Errors.value("format: no value named $key")
                }
                i = j + 1; continue
            }
            if (c == '}' && o.startsWith("}}", i)) { out.append('}'); i += 2; continue }
            out.append(c); i++
        }
        return out.toString()
    }

    fun list(o: PList, name: String, a: Array<Any?>, kw: Map<String, Any?>?): Any? {
        val xs = o.items
        return when (name) {
            "push", "append" -> { for (v in a) xs.add(v); null }
            "pop" -> {
                if (xs.isEmpty()) throw Errors.index("pop from an empty list")
                if (a.isEmpty()) xs.removeAt(xs.size - 1) else { val i = int(a[0]); val j = if (i < 0) i + xs.size else i
                    if (j < 0 || j >= xs.size) throw Errors.index("pop index past the end of the list"); xs.removeAt(j.toInt()) }
            }
            "insert" -> { val i = int(a[0]); val j = (if (i < 0) i + xs.size else i).coerceIn(0, xs.size.toLong()); xs.add(j.toInt(), a[1]); null }
            "remove" -> { val i = xs.indexOfFirst { Ops.eq(it, a[0]) }
                if (i < 0) throw Errors.value("${Show.quote(a[0])} is not in the list"); xs.removeAt(i); null }
            "remove_at" -> { val i = int(a[0]); val j = if (i < 0) i + xs.size else i
                if (j < 0 || j >= xs.size) throw Errors.index(); xs.removeAt(j.toInt()) }
            "clear" -> { xs.clear(); null }
            "extend" -> { xs.addAll(Ops.toList(a[0])); null }
            "sort" -> {
                val sorted = Builtins.sortedList(o, kw?.get("key") ?: kw?.get("by") ?: a.getOrNull(0), Ops.truthy(kw?.get("reverse")))
                xs.clear(); xs.addAll(sorted); o
            }
            "sort_by" -> { val sorted = Builtins.sortedList(o, a[0], Ops.truthy(kw?.get("reverse"))); xs.clear(); xs.addAll(sorted); o }
            "reverse" -> { xs.reverse(); null }
            "repeat" -> Ops.mul(o, a[0])
            "fill" -> { for (i in xs.indices) xs[i] = a[0]; o }
            "swap" -> { val i = int(a[0]).toInt(); val j = int(a[1]).toInt(); val t = xs[i]; xs[i] = xs[j]; xs[j] = t; null }
            "shuffle" -> { xs.shuffle(); null }
            "retain" -> { xs.removeAll { !Ops.truthy(call1(a[0], it)) }; null }
            "set" -> { Ops.setIndex(o, a[0], a[1]); null }
            else -> seq(xs, o, name, a, kw)
        }
    }

    fun seq(xs: List<Any?>, o: Any, name: String, a: Array<Any?>, kw: Map<String, Any?>?): Any? = when (name) {
        "len" -> xs.size.toLong()
        "join" -> xs.joinToString((a.getOrNull(0) ?: ", ") as String) { Show.show(it) }
        "contains", "has" -> xs.any { Ops.eq(it, a[0]) }
        "index_of" -> xs.indexOfFirst { Ops.eq(it, a[0]) }.toLong()
        "index" -> xs.indexOfFirst { Ops.eq(it, a[0]) }.let { if (it < 0) throw Errors.value("${Show.quote(a[0])} is not in the list") else it.toLong() }
        "count" -> when {
            a.isEmpty() -> xs.size.toLong()
            a[0] is Callable -> xs.count { Ops.truthy(call1(a[0], it)) }.toLong()
            else -> xs.count { Ops.eq(it, a[0]) }.toLong()
        }
        "map" -> list(xs.map { call1(a[0], it) })
        "filter" -> list(xs.filter { Ops.truthy(call1(a[0], it)) })
        "reduce" -> Builtins.reduce(o, a.toList())
        "each" -> { for (x in ArrayList(xs)) call1(a[0], x); null }
        "find" -> xs.firstOrNull { Ops.truthy(call1(a[0], it)) }
        "find_index" -> xs.indexOfFirst { Ops.truthy(call1(a[0], it)) }.toLong()
        "any" -> if (a.isEmpty()) xs.any { Ops.truthy(it) } else xs.any { Ops.truthy(call1(a[0], it)) }
        "all" -> if (a.isEmpty()) xs.all { Ops.truthy(it) } else xs.all { Ops.truthy(call1(a[0], it)) }
        "sum" -> Builtins.sum(o)
        "sum_by" -> { var acc: Any? = 0L; for (x in xs) acc = Ops.add(acc, call1(a[0], x)); acc }
        "min" -> Builtins.minMax(arrayOf(o), kw ?: a.getOrNull(0)?.let { mapOf("by" to it) }, false)
        "max" -> Builtins.minMax(arrayOf(o), kw ?: a.getOrNull(0)?.let { mapOf("by" to it) }, true)
        "min_by" -> Builtins.minMax(arrayOf(o), mapOf("by" to a[0]), false)
        "max_by" -> Builtins.minMax(arrayOf(o), mapOf("by" to a[0]), true)
        "average" -> { if (xs.isEmpty()) throw Errors.value("average of an empty list"); Ops.div(Builtins.sum(o), xs.size.toLong()) }
        "sorted" -> list(Builtins.sortedList(o, kw?.get("key") ?: kw?.get("by") ?: a.getOrNull(0), Ops.truthy(kw?.get("reverse"))))
        "sort_by_key" -> list(Builtins.sortedList(o, a[0], false))
        "reversed" -> list(xs.reversed())
        "first" -> if (xs.isEmpty()) a.getOrNull(0) else xs[0]
        "last" -> if (xs.isEmpty()) a.getOrNull(0) else xs[xs.size - 1]
        "take" -> list(xs.take(int(a[0]).toInt().coerceAtLeast(0)))
        "skip" -> list(xs.drop(int(a[0]).toInt().coerceAtLeast(0)))
        "unique", "distinct" -> { val out = ArrayList<Any?>(); for (x in xs) if (out.none { Ops.eq(it, x) }) out.add(x); PList(out) }
        "flatten" -> { val out = ArrayList<Any?>(); for (x in xs) if (x is PList || x is PTuple) out.addAll(Builtins.items(x)) else out.add(x); PList(out) }
        "zip" -> Builtins.zip(listOf(xs, Ops.toList(a[0])))
        "enumerate" -> PList(ArrayList(xs.mapIndexed { i, x -> PTuple(listOf(i.toLong() + int(a.getOrNull(0) ?: 0L), x)) }))
        "chunk" -> { val n = int(a[0]).toInt(); if (n <= 0) throw Errors.value("chunk size must be at least 1"); list(xs.chunked(n).map { PList(ArrayList(it)) }) }
        "window" -> { val n = int(a[0]).toInt(); if (n <= 0) throw Errors.value("window size must be at least 1"); list(xs.windowed(n).map { PList(ArrayList(it)) }) }
        "group_by" -> { val m = PMap(); for (x in xs) { val k = Ops.key(call1(a[0], x)); (m.map.getOrPut(k) { PList() } as PList).items.add(x) }; m }
        "count_by" -> { val m = PMap(); for (x in xs) { val k = Ops.key(call1(a[0], x)); m.map[k] = Ops.add(m.map[k] ?: 0L, 1L) }; m }
        "partition" -> { val yes = ArrayList<Any?>(); val no = ArrayList<Any?>(); for (x in xs) (if (Ops.truthy(call1(a[0], x))) yes else no).add(x); PTuple(listOf(PList(yes), PList(no))) }
        "slice" -> Ops.slice(o, a.getOrNull(0), a.getOrNull(1), null)
        "get" -> { val i = a[0]; if (i is Long) { val j = if (i < 0) i + xs.size else i; if (j >= 0 && j < xs.size) xs[j.toInt()] else a.getOrNull(1) } else a.getOrNull(1) }
        "is_empty" -> xs.isEmpty()
        "to_list", "copy" -> PList(ArrayList(xs))
        "to_set" -> PSet(LinkedHashSet(xs.map { Ops.key(it) }))
        "to_str" -> Show.show(o)
        else -> throw Errors.field(Show.typeName(o), name)
    }

    fun map(o: PMap, name: String, a: Array<Any?>, kw: Map<String, Any?>?): Any? {
        val m = o.map
        return when (name) {
            "len", "count" -> m.size.toLong()
            "keys" -> list(m.keys)
            "values" -> list(m.values)
            "items", "to_list" -> list(m.entries.map { PTuple(listOf(it.key, it.value)) })
            "get" -> { val k = Ops.key(a[0]); if (m.containsKey(k)) m[k] else a.getOrNull(1) }
            "set" -> { m[Ops.key(a[0])] = a[1]; null }
            "has", "contains" -> m.containsKey(Ops.key(a[0]))
            "remove" -> m.remove(Ops.key(a[0]))
            "pop" -> { val k = Ops.key(a[0]); if (m.containsKey(k)) m.remove(k) else if (a.size > 1) a[1] else throw Errors.key(a[0]) }
            "merge" -> PMap(LinkedHashMap(m).also { it.putAll((a[0] as PMap).map) })
            "update" -> { m.putAll((a[0] as PMap).map); null }
            "clear" -> { m.clear(); null }
            "copy" -> PMap(LinkedHashMap(m))
            "is_empty" -> m.isEmpty()
            "each" -> { for ((k, v) in ArrayList(m.entries)) call2(a[0], k, v); null }
            "map" -> PMap(LinkedHashMap<Any?, Any?>().also { out -> m.forEach { (k, v) -> out[k] = call2(a[0], k, v) } })
            "filter" -> PMap(LinkedHashMap<Any?, Any?>().also { out -> m.forEach { (k, v) -> if (Ops.truthy(call2(a[0], k, v))) out[k] = v } })
            "any" -> m.any { (k, v) -> Ops.truthy(call2(a[0], k, v)) }
            "all" -> m.all { (k, v) -> Ops.truthy(call2(a[0], k, v)) }
            "find" -> m.entries.firstOrNull { (k, v) -> Ops.truthy(call2(a[0], k, v)) }?.let { PTuple(listOf(it.key, it.value)) }
            "setdefault", "get_or_set" -> { val k = Ops.key(a[0]); if (!m.containsKey(k)) m[k] = a.getOrNull(1); m[k] }
            "sorted_keys" -> list(Ops.sortedOrSame(m.keys.toList()))
            "invert" -> PMap(LinkedHashMap<Any?, Any?>().also { out -> m.forEach { (k, v) -> out[Ops.key(v)] = k } })
            "to_str" -> Show.show(o)
            else -> throw Errors.field("map", name)
        }
    }

    fun set(o: PSet, name: String, a: Array<Any?>, kw: Map<String, Any?>?): Any? {
        val st = o.set
        fun other() = (a[0] as? PSet)?.set ?: LinkedHashSet(Ops.toList(a[0]).map { Ops.key(it) })
        return when (name) {
            "len", "count" -> st.size.toLong()
            "add" -> { st.add(Ops.key(a[0])); null }
            "remove" -> { if (!st.remove(Ops.key(a[0]))) throw Errors.key(a[0]); null }
            "discard" -> { st.remove(Ops.key(a[0])); null }
            "has", "contains" -> st.contains(Ops.key(a[0]))
            "union" -> PSet(LinkedHashSet(st).also { it.addAll(other()) })
            "intersection" -> PSet(LinkedHashSet(st).also { it.retainAll(other()) })
            "difference" -> PSet(LinkedHashSet(st).also { it.removeAll(other()) })
            "symmetric_difference" -> { val b = other(); PSet(LinkedHashSet<Any?>().also { r -> st.forEach { if (it !in b) r.add(it) }; b.forEach { if (it !in st) r.add(it) } }) }
            "is_subset", "issubset" -> other().containsAll(st)
            "is_superset" -> st.containsAll(other())
            "is_empty" -> st.isEmpty()
            "each" -> { for (x in ArrayList(st)) call1(a[0], x); null }
            "map" -> list(st.map { call1(a[0], it) })
            "filter" -> PSet(LinkedHashSet(st.filter { Ops.truthy(call1(a[0], it)) }))
            "any" -> st.any { Ops.truthy(call1(a[0], it)) }
            "all" -> st.all { Ops.truthy(call1(a[0], it)) }
            "to_list" -> list(st)
            "copy" -> PSet(LinkedHashSet(st))
            "sorted" -> list(Builtins.sortedList(o, kw?.get("key"), Ops.truthy(kw?.get("reverse"))))
            "clear" -> { st.clear(); null }
            "sum" -> Builtins.sum(o)
            "min" -> Builtins.minMax(arrayOf(o), null, false)
            "max" -> Builtins.minMax(arrayOf(o), null, true)
            "to_str" -> Show.show(o)
            else -> throw Errors.field("set", name)
        }
    }

    fun num(o: Any, name: String, a: Array<Any?>): Any? = when (name) {
        "to_str" -> Show.show(o)
        "to_int" -> Builtins.toInt(o)
        "to_float" -> Num.toDouble(o)
        "is_integer" -> o !is Double || o == Math.floor(o)
        "abs" -> if (Ops.compare(o, 0L) < 0) Ops.neg(o) else o
        "is_even" -> Ops.eq(Ops.mod(o, 2L), 0L)
        "is_odd" -> !Ops.eq(Ops.mod(o, 2L), 0L)
        "clamp" -> if (Ops.compare(o, a[0]) < 0) a[0] else if (Ops.compare(o, a[1]) > 0) a[1] else o
        "times" -> { val n = int(o); for (i in 0 until n) call1(a[0], i); null }
        "upto" -> PRange(int(o), int(a[0]) + 1, 1)
        else -> throw Errors.field(Show.typeName(o), name)
    }
}
