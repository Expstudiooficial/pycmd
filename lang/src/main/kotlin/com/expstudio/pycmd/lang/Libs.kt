package com.expstudio.pycmd.lang

import com.expstudio.pycmd.lang.Builtins.call1
import com.expstudio.pycmd.lang.Builtins.int
import java.io.File
import java.math.BigInteger
import java.security.MessageDigest

/** The standard library: `use math`, `use json` and the rest. */
object Libs {
    val ABOUT = linkedMapOf(
        "math" to "sqrt, pow, floor, ceil, sin, cos, pi, gcd, factorial, is_prime, clamp, ...",
        "random" to "int(a, b), float(), choice(xs), shuffle(xs), sample(xs, k), seed(n), chance(p)",
        "time" to "now(), ms(), clock(), sleep(s), date(), time(), stamp(pattern)",
        "json" to "parse(text), stringify(value), pretty(value)",
        "fs" to "read, write, append, lines, list, exists, mkdir, remove - inside the program's folder",
        "regex" to "test, find, find_all, groups, replace, split, escape",
        "stats" to "mean, median, mode, stdev, variance, range",
        "text" to "upper, lower, title, pad_left, center, is_palindrome, caesar, slug, wrap, ...",
        "http" to "get(url), get_json(url), post(url, data)",
        "color" to "red, green, yellow, blue, magenta, cyan, gray, bold, underline, plain",
        "sys" to "args, platform, exit(code), version",
        "collections" to "Counter, Deque, Stack, Queue, heap_push, heap_pop, default_map",
        "date" to "today(), parse(s), add_days(d, n), days_between(a, b), weekday(d), is_leap(y)",
        "csv" to "parse(text), stringify(rows), read(path), write(path, rows)",
        "hash" to "md5(s), sha1(s), sha256(s), crc32(s)",
        "base64" to "encode(s), decode(s), url_encode(s)",
        "uuid" to "new(), short()",
        "path" to "join(a, b), name(p), ext(p), dir(p), stem(p)",
        "matrix" to "zeros(r, c), identity(n), add(a, b), mul(a, b), transpose(m), det(m)",
    )
    val NAMES: Set<String> get() = ABOUT.keys

    private fun fn(name: String, f: (Array<Any?>, Map<String, Any?>?) -> Any?) = name to Native(name, f)
    private fun d(v: Any?) = Num.toDouble(v)
    private fun lst(xs: Collection<Any?>) = PList(ArrayList(xs))

    fun make(name: String, rt: Runtime): Module = Module(name, when (name) {
        "math" -> math()
        "random" -> random()
        "time" -> time()
        "json" -> mapOf(
            fn("parse") { a, _ -> Json.parse(a[0] as String) },
            fn("stringify") { a, kw -> Json.write(a[0], (a.getOrNull(1) ?: kw?.get("indent"))?.let { int(it).toInt() }) },
            fn("pretty") { a, _ -> Json.write(a[0], 2) },
        )
        "fs" -> fs(rt)
        "regex" -> regex()
        "stats" -> stats()
        "text" -> text()
        "http" -> http()
        "color" -> color()
        "sys" -> mapOf("args" to PList(ArrayList<Any?>(rt.argv)), "platform" to rt.platform,
            fn("exit") { a, _ -> throw PcExit((a.getOrNull(0) as? Long)?.toInt() ?: 0) },
            "version" to Pcmd.VERSION, "language" to "PyCmd", "engine" to "kotlin")
        "collections" -> collections()
        "date" -> date()
        "csv" -> csv(rt)
        "hash" -> hash()
        "base64" -> mapOf(
            fn("encode") { a, _ -> java.util.Base64.getEncoder().encodeToString((a[0] as String).toByteArray()) },
            fn("decode") { a, _ ->
                try { String(java.util.Base64.getDecoder().decode((a[0] as String).trim())) }
                catch (e: IllegalArgumentException) { throw Errors.value("that is not base64") }
            },
            fn("url_encode") { a, _ -> java.util.Base64.getUrlEncoder().withoutPadding().encodeToString((a[0] as String).toByteArray()) },
        )
        "uuid" -> mapOf(fn("new") { _, _ -> java.util.UUID.randomUUID().toString() },
            fn("short") { _, _ -> java.util.UUID.randomUUID().toString().substring(0, 8) })
        "path" -> mapOf(
            fn("join") { a, _ -> a.joinToString("/") { Show.show(it).trimEnd('/') } },
            fn("name") { a, _ -> (a[0] as String).substringAfterLast('/').substringAfterLast('\\') },
            fn("ext") { a, _ -> (a[0] as String).substringAfterLast('/').let { n -> if ('.' in n.drop(1)) "." + n.substringAfterLast('.') else "" } },
            fn("dir") { a, _ -> (a[0] as String).let { p -> if ('/' in p) p.substringBeforeLast('/') else "" } },
            fn("stem") { a, _ -> (a[0] as String).substringAfterLast('/').let { n -> if ('.' in n.drop(1)) n.substringBeforeLast('.') else n } },
        )
        "matrix" -> matrix()
        else -> throw Errors.name("there is no library called $name")
    })

    private fun math(): Map<String, Any?> = mapOf(
        "pi" to Math.PI, "e" to Math.E, "tau" to 2 * Math.PI, "inf" to Double.POSITIVE_INFINITY, "nan" to Double.NaN,
        fn("sqrt") { a, _ -> val x = d(a[0]); if (x < 0) throw Errors.value("that number is outside what this maths function accepts"); Math.sqrt(x) },
        fn("cbrt") { a, _ -> Math.cbrt(d(a[0])) },
        fn("pow") { a, _ -> Ops.pow(a[0], a[1]) },
        fn("abs") { a, _ -> if (Ops.compare(a[0], 0L) < 0) Ops.neg(a[0]) else a[0] },
        fn("floor") { a, _ -> if (Num.isInt(a[0])) a[0] else Builtins.toInt(Math.floor(d(a[0]))) },
        fn("ceil") { a, _ -> if (Num.isInt(a[0])) a[0] else Builtins.toInt(Math.ceil(d(a[0]))) },
        fn("round") { a, _ -> Builtins.round(a[0], a.getOrNull(1)) },
        fn("trunc") { a, _ -> Builtins.toInt(a[0]) },
        fn("sin") { a, _ -> Math.sin(d(a[0])) }, fn("cos") { a, _ -> Math.cos(d(a[0])) }, fn("tan") { a, _ -> Math.tan(d(a[0])) },
        fn("asin") { a, _ -> Math.asin(d(a[0])) }, fn("acos") { a, _ -> Math.acos(d(a[0])) }, fn("atan") { a, _ -> Math.atan(d(a[0])) },
        fn("atan2") { a, _ -> Math.atan2(d(a[0]), d(a[1])) }, fn("hypot") { a, _ -> Math.hypot(d(a[0]), d(a[1])) },
        fn("degrees") { a, _ -> Math.toDegrees(d(a[0])) }, fn("radians") { a, _ -> Math.toRadians(d(a[0])) },
        fn("log") { a, _ -> val x = d(a[0]); if (x <= 0) throw Errors.value("that number is outside what this maths function accepts")
            if (a.size > 1) Math.log(x) / Math.log(d(a[1])) else Math.log(x) },
        fn("log2") { a, _ -> Math.log(d(a[0])) / Math.log(2.0) }, fn("log10") { a, _ -> Math.log10(d(a[0])) },
        fn("exp") { a, _ -> Math.exp(d(a[0])) },
        fn("gcd") { a, _ -> Num.norm(Num.big(a[0]).gcd(Num.big(a[1]))) },
        fn("lcm") { a, _ -> val x = Num.big(a[0]); val y = Num.big(a[1]); if (x.signum() == 0 || y.signum() == 0) 0L else Num.norm(x.multiply(y).abs().divide(x.gcd(y))) },
        fn("factorial") { a, _ ->
            val n = int(a[0]); if (n < 0) throw Errors.value("factorial needs a number that is not negative")
            var r = BigInteger.ONE; for (i in 2..n) r = r.multiply(BigInteger.valueOf(i)); Num.norm(r)
        },
        fn("comb") { a, _ -> comb(int(a[0]), int(a[1])) },
        fn("perm") { a, _ -> val n = int(a[0]); val k = int(a[1]); var r = BigInteger.ONE; for (i in 0 until k) r = r.multiply(BigInteger.valueOf(n - i)); Num.norm(r) },
        fn("is_prime") { a, _ -> isPrime(int(a[0])) },
        fn("isqrt") { a, _ -> Num.norm(Num.big(a[0]).sqrt()) },
        fn("min") { a, kw -> Builtins.minMax(a, kw, false) }, fn("max") { a, kw -> Builtins.minMax(a, kw, true) },
        fn("clamp") { a, _ -> if (Ops.compare(a[0], a[1]) < 0) a[1] else if (Ops.compare(a[0], a[2]) > 0) a[2] else a[0] },
        fn("sign") { a, _ -> Ops.compare(a[0], 0L).toLong() },
        fn("is_nan") { a, _ -> d(a[0]).isNaN() }, fn("is_inf") { a, _ -> d(a[0]).isInfinite() },
        fn("lerp") { a, _ -> Ops.add(a[0], Ops.mul(Ops.sub(a[1], a[0]), a[2])) },
        fn("sum") { a, _ -> Builtins.sum(a[0]) },
        fn("primes") { a, _ -> val n = int(a[0]).toInt(); val sieve = BooleanArray(maxOf(n, 2)); val out = ArrayList<Any?>()
            for (i in 2 until n) if (!sieve[i]) { out.add(i.toLong()); var j = i.toLong() * i; while (j < n) { sieve[j.toInt()] = true; j += i } }
            PList(out) },
        fn("fib") { a, _ -> var x = BigInteger.ZERO; var y = BigInteger.ONE; repeat(int(a[0]).toInt()) { val t = x.add(y); x = y; y = t }; Num.norm(x) },
    )

    private fun comb(n: Long, k: Long): Any {
        if (k < 0 || k > n) return 0L
        var r = BigInteger.ONE
        for (i in 0 until minOf(k, n - k)) r = r.multiply(BigInteger.valueOf(n - i)).divide(BigInteger.valueOf(i + 1))
        return Num.norm(r)
    }

    fun isPrime(n: Long): Boolean {
        if (n < 2) return false
        if (n < 4) return true
        if (n % 2 == 0L) return false
        var i = 3L
        while (i * i <= n) { if (n % i == 0L) return false; i += 2 }
        return true
    }

    private fun random(): Map<String, Any?> {
        val r = java.util.Random()
        return mapOf(
            fn("int") { a, _ -> val lo = int(a[0]); val hi = int(a[1]); if (hi < lo) throw Errors.value("random.int needs low <= high"); lo + (r.nextDouble() * (hi - lo + 1)).toLong().coerceAtMost(hi - lo) },
            fn("float") { a, _ -> val lo = if (a.isNotEmpty()) d(a[0]) else 0.0; val hi = if (a.size > 1) d(a[1]) else 1.0; lo + (hi - lo) * r.nextDouble() },
            fn("choice") { a, _ -> val xs = Ops.toList(a[0]); if (xs.isEmpty()) throw Errors.index("cannot choose from an empty list"); xs[r.nextInt(xs.size)] },
            fn("shuffle") { a, _ -> (a[0] as PList).items.shuffle(r); null },
            fn("shuffled") { a, _ -> PList(Ops.toList(a[0]).also { it.shuffle(r) }) },
            fn("sample") { a, _ -> val xs = Ops.toList(a[0]).also { it.shuffle(r) }; val k = int(a[1]).toInt()
                if (k > xs.size) throw Errors.value("sample larger than the list"); PList(ArrayList(xs.take(k))) },
            fn("seed") { a, _ -> r.setSeed(Ops.hash(a.getOrNull(0)).toLong() * 2654435761L + (a.getOrNull(0) as? Long ?: 0L)); null },
            fn("chance") { a, _ -> r.nextDouble() < d(a[0]) },
            fn("random") { _, _ -> r.nextDouble() },
            fn("bool") { _, _ -> r.nextBoolean() },
        )
    }

    private val STRFTIME = mapOf('Y' to "yyyy", 'm' to "MM", 'd' to "dd", 'H' to "HH", 'M' to "mm", 'S' to "ss",
        'A' to "EEEE", 'a' to "EEE", 'B' to "MMMM", 'b' to "MMM", 'y' to "yy", 'I' to "hh", 'p' to "a", 'j' to "DDD")

    fun strftime(pattern: String, millis: Long): String {
        val sb = StringBuilder()
        var i = 0
        val cal = java.util.Date(millis)
        while (i < pattern.length) {
            val c = pattern[i]
            if (c == '%' && i + 1 < pattern.length) {
                val code = pattern[i + 1]
                if (code == '%') sb.append('%')
                else {
                    val jp = STRFTIME[code]
                    if (jp == null) sb.append('%').append(code)
                    else sb.append(java.text.SimpleDateFormat(jp, java.util.Locale.ENGLISH).format(cal))
                }
                i += 2
            } else { sb.append(c); i++ }
        }
        return sb.toString()
    }

    private fun time(): Map<String, Any?> {
        val started = System.nanoTime()
        fun now() = System.currentTimeMillis()
        return mapOf(
            fn("now") { _, _ -> now() / 1000.0 },
            fn("ms") { _, _ -> now() },
            fn("clock") { _, _ -> (System.nanoTime() - started) / 1e9 },
            fn("sleep") { a, _ -> Thread.sleep((d(a[0]).coerceIn(0.0, 600.0) * 1000).toLong()); null },
            fn("date") { _, _ -> strftime("%Y-%m-%d", now()) },
            fn("time") { _, _ -> strftime("%H:%M:%S", now()) },
            fn("stamp") { a, kw -> strftime((a.getOrNull(0) ?: "%Y-%m-%d %H:%M:%S") as String,
                (a.getOrNull(1) ?: kw?.get("at"))?.let { (d(it) * 1000).toLong() } ?: now()) },
            fn("year") { _, _ -> strftime("%Y", now()).toLong() }, fn("month") { _, _ -> strftime("%m", now()).toLong() },
            fn("day") { _, _ -> strftime("%d", now()).toLong() }, fn("hour") { _, _ -> strftime("%H", now()).toLong() },
            fn("minute") { _, _ -> strftime("%M", now()).toLong() }, fn("weekday") { _, _ -> strftime("%A", now()) },
        )
    }

    private fun fs(rt: Runtime): Map<String, Any?> {
        val root = File(rt.root).canonicalFile
        fun inside(p: Any?): File {
            val f = File(root, p as String).canonicalFile
            if (f != root && !f.path.startsWith(root.path + File.separator))
                throw PcError("$p is outside this program's folder - fs only reaches files next to the program", "File")
            return f
        }
        fun io(block: () -> Any?): Any? = try { block() } catch (e: java.io.IOException) {
            throw PcError(e.message?.substringAfter(": ")?.let { if ("No such file" in it || "cannot find" in it) "no such file" else it } ?: "file error", "File")
        }
        return mapOf(
            fn("read") { a, _ -> io { val f = inside(a[0]); if (!f.isFile) throw PcError("there is no file ${a[0]}", "File"); f.readText() } },
            fn("write") { a, _ -> io { val f = inside(a[0]); f.parentFile?.mkdirs(); f.writeText(Show.show(a[1])); null } },
            fn("append") { a, _ -> io { inside(a[0]).appendText(Show.show(a[1])); null } },
            fn("lines") { a, _ -> io { val f = inside(a[0]); if (!f.isFile) throw PcError("there is no file ${a[0]}", "File"); lst(f.readLines()) } },
            fn("list") { a, _ -> io { lst((inside(a.getOrNull(0) ?: ".").list() ?: emptyArray()).sorted()) } },
            fn("exists") { a, _ -> inside(a[0]).exists() },
            fn("is_dir") { a, _ -> inside(a[0]).isDirectory },
            fn("mkdir") { a, _ -> inside(a[0]).mkdirs(); null },
            fn("remove") { a, _ -> io { val f = inside(a[0]); if (!f.delete()) throw PcError("could not remove ${a[0]}", "File"); null } },
            fn("size") { a, _ -> inside(a[0]).length() },
            fn("folder") { _, _ -> root.path },
        )
    }

    private fun pattern(p: Any?): Regex = try { Regex(p as String) } catch (e: Exception) {
        throw Errors.value("bad pattern ${Show.quote(p)}: ${e.message?.lineSequence()?.firstOrNull()}")
    }

    private fun regex(): Map<String, Any?> = mapOf(
        fn("test") { a, _ -> pattern(a[0]).containsMatchIn(a[1] as String) },
        fn("find") { a, _ -> pattern(a[0]).find(a[1] as String)?.value },
        fn("find_all") { a, _ -> lst(pattern(a[0]).findAll(a[1] as String).map { it.value }.toList()) },
        fn("groups") { a, _ -> pattern(a[0]).find(a[1] as String)?.let { m -> lst(m.groups.drop(1).map { it?.value }) } },
        fn("replace") { a, _ ->
            val repl = (a[2] as String).replace("$", "\\$").replace(Regex("\\\\(\\d)"), "\\$$1")
            pattern(a[0]).replace(a[1] as String, repl)
        },
        fn("split") { a, _ -> lst(pattern(a[0]).split(a[1] as String)) },
        fn("escape") { a, _ -> (a[0] as String).map { if (it in "()[]{}?*+-|^$\\.&~# \t\n\r\u000b\u000c") "\\$it" else "$it" }.joinToString("") },
    )

    private fun need(xs: Any?): List<Any?> = Ops.toList(xs).also { if (it.isEmpty()) throw Errors.value("statistics of an empty list") }

    private fun stats(): Map<String, Any?> = mapOf(
        fn("mean") { a, _ -> val xs = need(a[0]); xs.sumOf { d(it) } / xs.size },
        fn("median") { a, _ ->
            val xs = need(a[0]).sortedWith(Ops.COMPARATOR)
            val n = xs.size
            if (n % 2 == 1) xs[n / 2] else Ops.div(Ops.add(xs[n / 2 - 1], xs[n / 2]), 2L)
        },
        fn("mode") { a, _ -> val xs = need(a[0]); xs.groupBy { Ops.key(it) }.maxByOrNull { it.value.size }!!.value[0] },
        fn("stdev") { a, _ -> val xs = need(a[0]); if (xs.size < 2) 0.0 else Math.sqrt(variance(xs)) },
        fn("variance") { a, _ -> val xs = need(a[0]); if (xs.size < 2) 0.0 else variance(xs) },
        fn("sum") { a, _ -> Builtins.sum(a[0]) },
        fn("min") { a, _ -> Builtins.minMax(arrayOf(a[0]), null, false) },
        fn("max") { a, _ -> Builtins.minMax(arrayOf(a[0]), null, true) },
        fn("range") { a, _ -> val xs = need(a[0]); Ops.sub(Builtins.minMax(arrayOf(a[0]), null, true), Builtins.minMax(arrayOf(a[0]), null, false)).also { xs.size } },
    )

    private fun variance(xs: List<Any?>): Double {
        val m = xs.sumOf { d(it) } / xs.size
        return xs.sumOf { (d(it) - m) * (d(it) - m) } / (xs.size - 1)
    }

    private fun text(): Map<String, Any?> = mapOf(
        fn("upper") { a, _ -> (a[0] as String).uppercase() }, fn("lower") { a, _ -> (a[0] as String).lowercase() },
        fn("title") { a, _ -> Methods.str(a[0] as String, "title", emptyArray(), null) },
        fn("trim") { a, _ -> (a[0] as String).trim() },
        fn("split") { a, _ -> Methods.str(a[0] as String, "split", a.drop(1).toTypedArray(), null) },
        fn("join") { a, _ -> Builtins.items(a[0]).joinToString((a.getOrNull(1) ?: "") as String) { Show.show(it) } },
        fn("replace") { a, _ -> (a[0] as String).replace(a[1] as String, a[2] as String) },
        fn("repeat") { a, _ -> Ops.mul(a[0], a[1]) },
        fn("reverse") { a, _ -> (a[0] as String).reversed() },
        fn("pad_left") { a, _ -> Methods.str(a[0] as String, "pad_left", a.drop(1).toTypedArray(), null) },
        fn("pad_right") { a, _ -> Methods.str(a[0] as String, "pad_right", a.drop(1).toTypedArray(), null) },
        fn("center") { a, _ -> Methods.str(a[0] as String, "center", a.drop(1).toTypedArray(), null) },
        fn("contains") { a, _ -> (a[0] as String).contains(a[1] as String) },
        fn("count") { a, _ -> Methods.str(a[0] as String, "count", arrayOf(a[1]), null) },
        fn("is_digit") { a, _ -> Methods.str(a[0] as String, "is_digit", emptyArray(), null) },
        fn("is_alpha") { a, _ -> Methods.str(a[0] as String, "is_alpha", emptyArray(), null) },
        fn("chars") { a, _ -> PList(Ops.toList(a[0])) },
        fn("lines") { a, _ -> Methods.str(a[0] as String, "lines", emptyArray(), null) },
        fn("words") { a, _ -> Methods.str(a[0] as String, "words", emptyArray(), null) },
        "letters" to "abcdefghijklmnopqrstuvwxyz", "digits" to "0123456789",
        fn("is_palindrome") { a, _ -> val t = (a[0] as String).filter { it.isLetterOrDigit() }.lowercase(); t == t.reversed() },
        fn("caesar") { a, _ ->
            val n = int(a[1]).toInt()
            (a[0] as String).map { c ->
                if (c in 'a'..'z') ('a' + Math.floorMod(c - 'a' + n, 26)) else if (c in 'A'..'Z') ('A' + Math.floorMod(c - 'A' + n, 26)) else c
            }.joinToString("")
        },
        fn("slug") { a, _ -> (a[0] as String).lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-') },
        fn("wrap") { a, _ -> wrap(a[0] as String, (a.getOrNull(1) as? Long)?.toInt() ?: 60) },
        fn("vowels") { a, _ -> (a[0] as String).count { it.lowercaseChar() in "aeiou" }.toLong() },
        fn("acronym") { a, _ -> (a[0] as String).split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString("") { it[0].uppercase() } },
    )

    private fun wrap(s: String, width: Int): String {
        val lines = ArrayList<String>()
        var line = StringBuilder()
        for (w in s.split(Regex("\\s+")).filter { it.isNotEmpty() }) {
            if (line.isNotEmpty() && line.length + 1 + w.length > width) { lines.add(line.toString()); line = StringBuilder() }
            if (line.isNotEmpty()) line.append(' ')
            line.append(w)
        }
        if (line.isNotEmpty()) lines.add(line.toString())
        return lines.joinToString("\n")
    }

    private fun http(): Map<String, Any?> {
        fun request(url: Any?, data: Any?, method: String, headers: Any?): String {
            val u = url as? String
            if (u == null || !(u.startsWith("http://") || u.startsWith("https://")))
                throw Errors.value("http needs a web address starting with http:// or https://")
            try {
                val c = java.net.URL(u).openConnection() as java.net.HttpURLConnection
                c.requestMethod = method
                c.connectTimeout = 20000; c.readTimeout = 20000
                c.setRequestProperty("User-Agent", "PyCmd")
                (headers as? PMap)?.map?.forEach { (k, v) -> c.setRequestProperty(Show.show(k), Show.show(v)) }
                if (data != null) {
                    c.doOutput = true
                    val body = if (data is PMap || data is PList) { c.setRequestProperty("Content-Type", "application/json"); Json.write(data, null) } else Show.show(data)
                    c.outputStream.use { it.write(body.toByteArray()) }
                }
                val code = c.responseCode
                if (code >= 400) throw PcError("$u answered $code", "Http")
                return c.inputStream.use { String(it.readBytes().let { b -> if (b.size > 5_000_000) b.copyOf(5_000_000) else b }) }
            } catch (e: java.io.IOException) {
                throw PcError("could not reach $u: ${e.message}", "Http")
            }
        }
        return mapOf(
            fn("get") { a, kw -> request(a[0], null, "GET", a.getOrNull(1) ?: kw?.get("headers")) },
            fn("get_json") { a, _ -> Json.parse(request(a[0], null, "GET", null)) },
            fn("post") { a, kw -> request(a[0], a.getOrNull(1), "POST", a.getOrNull(2) ?: kw?.get("headers")) },
        )
    }

    private fun color(): Map<String, Any?> {
        val codes = linkedMapOf("red" to 31, "green" to 32, "yellow" to 33, "blue" to 34, "magenta" to 35, "cyan" to 36,
            "white" to 37, "gray" to 90, "bold" to 1, "dim" to 2, "underline" to 4)
        val out = LinkedHashMap<String, Any?>()
        for ((n, c) in codes) out[n] = Native(n) { a, _ -> "\u001b[${c}m${Show.show(a[0])}\u001b[0m" }
        out["plain"] = Native("plain") { a, _ -> Show.show(a[0]).replace(Regex("\u001b\\[[0-9;]*m"), "") }
        return out
    }

    // ------------------------------------------------------------ 2.0 libraries
    private fun collections(): Map<String, Any?> = mapOf(
        fn("Counter") { a, _ ->
            val m = PMap()
            if (a.isNotEmpty() && a[0] != null) for (x in Ops.toList(a[0])) { val k = Ops.key(x); m.map[k] = Ops.add(m.map[k] ?: 0L, 1L) }
            m
        },
        fn("most_common") { a, _ ->
            val m = a[0] as PMap
            val n = (a.getOrNull(1) as? Long)?.toInt() ?: m.map.size
            lst(m.map.entries.sortedWith { x, y -> -Ops.compare(x.value, y.value) }.take(n).map { PTuple(listOf(it.key, it.value)) })
        },
        fn("Deque") { a, _ -> PList(if (a.isNotEmpty()) Ops.toList(a[0]) else ArrayList()) },
        fn("push_front") { a, _ -> (a[0] as PList).items.add(0, a[1]); null },
        fn("pop_front") { a, _ -> val xs = (a[0] as PList).items; if (xs.isEmpty()) throw Errors.index("pop from an empty deque"); xs.removeAt(0) },
        fn("Stack") { _, _ -> PList() },
        fn("Queue") { _, _ -> PList() },
        fn("heap_push") { a, _ ->
            val h = (a[0] as PList).items
            h.add(a[1]); var i = h.size - 1
            while (i > 0) { val p = (i - 1) / 2; if (Ops.compare(h[i], h[p]) < 0) { val t = h[i]; h[i] = h[p]; h[p] = t; i = p } else break }
            null
        },
        fn("heap_pop") { a, _ ->
            val h = (a[0] as PList).items
            if (h.isEmpty()) throw Errors.index("pop from an empty heap")
            val top = h[0]; val last = h.removeAt(h.size - 1)
            if (h.isNotEmpty()) {
                h[0] = last; var i = 0
                while (true) {
                    val l = 2 * i + 1; val r = l + 1; var m = i
                    if (l < h.size && Ops.compare(h[l], h[m]) < 0) m = l
                    if (r < h.size && Ops.compare(h[r], h[m]) < 0) m = r
                    if (m == i) break
                    val t = h[i]; h[i] = h[m]; h[m] = t; i = m
                }
            }
            top
        },
        fn("default_map") { a, _ -> PMap().also { m -> (a.getOrNull(0) as? PList)?.items?.forEach { k -> m.map[Ops.key(k)] = a.getOrNull(1) } } },
    )

    private fun date(): Map<String, Any?> {
        fun parse(s: Any?): java.time.LocalDate = try { java.time.LocalDate.parse(s as String) } catch (e: Exception) {
            throw Errors.value("${Show.quote(s)} is not a date like 2026-01-31")
        }
        return mapOf(
            fn("today") { _, _ -> java.time.LocalDate.now().toString() },
            fn("parse") { a, _ -> parse(a[0]).toString() },
            fn("add_days") { a, _ -> parse(a[0]).plusDays(int(a[1])).toString() },
            fn("days_between") { a, _ -> java.time.temporal.ChronoUnit.DAYS.between(parse(a[0]), parse(a[1])) },
            fn("weekday") { a, _ -> parse(a[0]).dayOfWeek.getDisplayName(java.time.format.TextStyle.FULL, java.util.Locale.ENGLISH) },
            fn("is_leap") { a, _ -> java.time.Year.isLeap(int(a[0])) },
            fn("year") { a, _ -> parse(a[0]).year.toLong() },
            fn("month") { a, _ -> parse(a[0]).monthValue.toLong() },
            fn("day") { a, _ -> parse(a[0]).dayOfMonth.toLong() },
            fn("days_in_month") { a, _ -> java.time.YearMonth.of(int(a[0]).toInt(), int(a[1]).toInt()).lengthOfMonth().toLong() },
        )
    }

    private fun csvParse(text: String): PList {
        val rows = ArrayList<Any?>()
        var row = ArrayList<Any?>()
        val cell = StringBuilder()
        var quoted = false
        var i = 0
        while (i < text.length) {
            val c = text[i]
            if (quoted) {
                if (c == '"') { if (i + 1 < text.length && text[i + 1] == '"') { cell.append('"'); i++ } else quoted = false }
                else cell.append(c)
            } else when (c) {
                '"' -> quoted = true
                ',' -> { row.add(cell.toString()); cell.setLength(0) }
                '\n' -> { row.add(cell.toString()); cell.setLength(0); rows.add(PList(row)); row = ArrayList() }
                '\r' -> {}
                else -> cell.append(c)
            }
            i++
        }
        if (cell.isNotEmpty() || row.isNotEmpty()) { row.add(cell.toString()); rows.add(PList(row)) }
        return PList(rows)
    }

    private fun csvWrite(rows: Any?): String = Ops.toList(rows).joinToString("\n", postfix = "\n") { r ->
        Ops.toList(r).joinToString(",") { v -> val s = Show.show(v); if (s.any { it in ",\"\n" }) "\"" + s.replace("\"", "\"\"") + "\"" else s }
    }

    private fun csv(rt: Runtime): Map<String, Any?> {
        val files = fs(rt)
        return mapOf(
            fn("parse") { a, _ -> csvParse(a[0] as String) },
            fn("stringify") { a, _ -> csvWrite(a[0]) },
            fn("read") { a, _ -> csvParse((files["read"] as Native).call(arrayOf(a[0]), null) as String) },
            fn("write") { a, _ -> (files["write"] as Native).call(arrayOf(a[0], csvWrite(a[1])), null) },
        )
    }

    private fun hash(): Map<String, Any?> {
        fun digest(alg: String, s: Any?) = MessageDigest.getInstance(alg).digest(Show.show(s).toByteArray()).joinToString("") { "%02x".format(it) }
        return mapOf(
            fn("md5") { a, _ -> digest("MD5", a[0]) }, fn("sha1") { a, _ -> digest("SHA-1", a[0]) },
            fn("sha256") { a, _ -> digest("SHA-256", a[0]) },
            fn("crc32") { a, _ -> java.util.zip.CRC32().also { it.update(Show.show(a[0]).toByteArray()) }.value },
        )
    }

    private fun rows(m: Any?): List<List<Any?>> = Ops.toList(m).map { Ops.toList(it) }
    private fun mat(r: List<List<Any?>>) = PList(ArrayList(r.map { PList(ArrayList(it)) }))

    private fun matrix(): Map<String, Any?> = mapOf(
        fn("zeros") { a, _ -> mat(List(int(a[0]).toInt()) { List(int(a[1]).toInt()) { 0L } }) },
        fn("identity") { a, _ -> val n = int(a[0]).toInt(); mat(List(n) { i -> List(n) { j -> if (i == j) 1L else 0L } }) },
        fn("add") { a, _ -> val x = rows(a[0]); val y = rows(a[1]); mat(x.indices.map { i -> x[i].indices.map { j -> Ops.add(x[i][j], y[i][j]) } }) },
        fn("mul") { a, _ ->
            val x = rows(a[0]); val y = rows(a[1])
            if (x.isEmpty() || x[0].size != y.size) throw Errors.value("these matrices do not fit together for mul")
            mat(x.indices.map { i -> y[0].indices.map { j -> var s: Any? = 0L; for (k in y.indices) s = Ops.add(s, Ops.mul(x[i][k], y[k][j])); s } })
        },
        fn("transpose") { a, _ -> val x = rows(a[0]); if (x.isEmpty()) PList() else mat(x[0].indices.map { j -> x.indices.map { i -> x[i][j] } }) },
        fn("det") { a, _ -> det(rows(a[0]).map { r -> r.map { d(it) } }) },
        fn("scale") { a, _ -> mat(rows(a[0]).map { r -> r.map { Ops.mul(it, a[1]) } }) },
    )

    private fun det(m: List<List<Double>>): Double {
        val n = m.size
        if (n == 1) return m[0][0]
        if (n == 2) return m[0][0] * m[1][1] - m[0][1] * m[1][0]
        var s = 0.0
        for (j in 0 until n) {
            val minor = m.drop(1).map { r -> r.filterIndexed { k, _ -> k != j } }
            s += (if (j % 2 == 0) 1 else -1) * m[0][j] * det(minor)
        }
        return s
    }
}

/** JSON in and out, in the same spacing Python's json module uses. */
object Json {
    fun parse(s: String): Any? {
        val p = P(s)
        p.ws()
        val v = p.value()
        p.ws()
        if (p.i != s.length) throw p.bad()
        return v
    }

    private class P(val s: String) {
        var i = 0
        fun bad() = Errors.value("not valid JSON: something unexpected at character ${i + 1}")
        fun ws() { while (i < s.length && s[i].isWhitespace()) i++ }
        fun value(): Any? {
            if (i >= s.length) throw bad()
            return when (s[i]) {
                '{' -> { i++; val m = PMap(); ws(); if (s.getOrNull(i) == '}') { i++; return m }
                    while (true) { ws(); val k = string(); ws(); if (s.getOrNull(i) != ':') throw bad(); i++; ws(); m.map[k] = value(); ws()
                        when (s.getOrNull(i)) { ',' -> i++; '}' -> { i++; return m }; else -> throw bad() } } ; @Suppress("UNREACHABLE_CODE") m }
                '[' -> { i++; val l = ArrayList<Any?>(); ws(); if (s.getOrNull(i) == ']') { i++; return PList(l) }
                    while (true) { ws(); l.add(value()); ws()
                        when (s.getOrNull(i)) { ',' -> i++; ']' -> { i++; return PList(l) }; else -> throw bad() } }; @Suppress("UNREACHABLE_CODE") PList(l) }
                '"' -> string()
                't' -> word("true", true); 'f' -> word("false", false); 'n' -> word("null", null)
                else -> number()
            }
        }
        fun word(w: String, v: Any?): Any? { if (!s.startsWith(w, i)) throw bad(); i += w.length; return v }
        fun number(): Any? {
            val st = i
            while (i < s.length && (s[i].isDigit() || s[i] in "+-.eE")) i++
            val t = s.substring(st, i)
            if (t.isEmpty()) throw bad()
            return if (t.any { it in ".eE" }) t.toDoubleOrNull() ?: throw bad() else t.toLongOrNull() ?: Num.norm(BigInteger(t))
        }
        fun string(): String {
            if (s.getOrNull(i) != '"') throw bad()
            i++
            val sb = StringBuilder()
            while (true) {
                if (i >= s.length) throw bad()
                val c = s[i++]
                when (c) {
                    '"' -> return sb.toString()
                    '\\' -> { val e = s[i++]
                        when (e) { 'n' -> sb.append('\n'); 't' -> sb.append('\t'); 'r' -> sb.append('\r'); 'b' -> sb.append('\b')
                            'f' -> sb.append('\u000c'); 'u' -> { sb.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4 }
                            else -> sb.append(e) } }
                    else -> sb.append(c)
                }
            }
        }
    }

    fun write(v: Any?, indent: Int?): String {
        val sb = StringBuilder()
        write(v, indent, 0, sb)
        return sb.toString()
    }

    private fun str(s: String, sb: StringBuilder) {
        sb.append('"')
        for (c in s) when (c) {
            '"' -> sb.append("\\\""); '\\' -> sb.append("\\\\"); '\n' -> sb.append("\\n"); '\t' -> sb.append("\\t"); '\r' -> sb.append("\\r")
            else -> if (c < ' ') sb.append("\\u%04x".format(c.code)) else sb.append(c)
        }
        sb.append('"')
    }

    private fun write(v: Any?, indent: Int?, depth: Int, sb: StringBuilder) {
        val nl = if (indent != null) "\n" + " ".repeat(indent * (depth + 1)) else ""
        val close = if (indent != null) "\n" + " ".repeat(indent * depth) else ""
        val sep = if (indent != null) "," else ", "
        when (v) {
            null -> sb.append("null")
            is Boolean -> sb.append(v)
            is Long, is BigInteger -> sb.append(v)
            is Double -> sb.append(if (v.isNaN()) "NaN" else if (v.isInfinite()) (if (v > 0) "Infinity" else "-Infinity") else Show.floatRepr(v))
            is String -> str(v, sb)
            is PList, is PTuple, is PSet -> {
                val items = Ops.toList(v)
                if (items.isEmpty()) { sb.append("[]"); return }
                sb.append('[')
                items.forEachIndexed { k, x -> if (k > 0) sb.append(sep); sb.append(nl); write(x, indent, depth + 1, sb) }
                sb.append(close).append(']')
            }
            is PMap -> {
                if (v.map.isEmpty()) { sb.append("{}"); return }
                sb.append('{')
                var k = 0
                for ((key, x) in v.map) {
                    if (k++ > 0) sb.append(sep)
                    sb.append(nl); str(if (key is String) key else Show.show(key), sb); sb.append(": "); write(x, indent, depth + 1, sb)
                }
                sb.append(close).append('}')
            }
            is StructObj -> write(PMap(LinkedHashMap<Any?, Any?>().also { m -> v.type.fields.forEachIndexed { i, f -> m[f] = v.values[i] } }), indent, depth, sb)
            is Variant -> str(v.name, sb)
            is VariantObj -> write(PMap(LinkedHashMap<Any?, Any?>().also { m -> m["kind"] = v.variant.name; v.variant.fields!!.forEachIndexed { i, f -> m[f] = v.values[i] } }), indent, depth, sb)
            else -> str(Show.show(v), sb)
        }
    }
}
