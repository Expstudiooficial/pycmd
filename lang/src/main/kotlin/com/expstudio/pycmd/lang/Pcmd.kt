package com.expstudio.pycmd.lang

/**
 * PyCmd, the language - the fast engine. One entry point for everyone:
 *
 *     val r = Pcmd.run(source, "/path/app.pcmd", arrayOf(), io, "android", 0)
 *
 * From Java it is the same call: `Pcmd.run(source, path, args, io, "pc", 0)`.
 */
class RunResult(
    @JvmField val ok: Boolean,
    @JvmField val exit: Int,
    @JvmField val error: String,
    @JvmField val line: Int,
    @JvmField val kind: String,
    @JvmField val passed: Int = 0,
    @JvmField val failed: Int = 0,
)

object Pcmd {
    const val VERSION = "2.0"

    @JvmStatic fun version(): String = VERSION

    /** Compiles a program and runs it in this thread. Returns what it exported. */
    fun execute(source: String, rt: Runtime, filename: String): PMap {
        val program = Compiler(source, rt, filename).compileProgram(Parser.parse(source))
        val result = PcFunction(program.main, null).call(emptyArray(), null)
        return result as? PMap ?: PMap()
    }

    private fun failure(t: Throwable): RunResult {
        when (t) {
            is PcSyntaxError -> return RunResult(false, 1, "line ${t.line}: ${t.msg}", t.line, "Syntax")
            is PcStop -> return RunResult(false, 1, t.why, 0, "Stopped")
            is PcExit -> return RunResult(true, t.code, "", 0, "")
        }
        val e = Runtime.asError(t) ?: return RunResult(false, 1, "internal error: ${t.javaClass.simpleName}: ${t.message}", 0, "Internal")
        val where = if (e.line > 0) "line ${e.line}: " else ""
        val text = if (e.kind == "Error") "$where${e.msg}" else "$where${e.kind}: ${e.msg}"
        return RunResult(false, 1, text, e.line, e.kind)
    }

    /** Runs on a thread with a deep stack, so deep recursion is an error message, not a crash. */
    private fun <T> deep(stackBytes: Long, body: () -> T): T {
        var result: Result<T>? = null
        val t = Thread(null, { result = runCatching(body) }, "pycmd", stackBytes)
        t.start()
        try {
            t.join()
        } catch (e: InterruptedException) {
            t.interrupt()
            t.join(2000)
            throw e
        }
        return result!!.getOrThrow()
    }

    private val stack: Long get() = if (System.getProperty("java.vendor", "").contains("Android", true)) 256L shl 20 else 1L shl 30

    /**
     * The same as run, on the calling thread - for hosts that call back into
     * themselves from io (Python on Android). Recursion is capped lower; a
     * stack that still runs out is caught and reported, not a crash.
     */
    @JvmStatic
    fun runHere(source: String, path: String?, argv: Array<String>, io: PcmdIO, platform: String, timeoutMs: Long): RunResult =
        run0(source, path, argv, io, platform, timeoutMs, inline = true)

    @JvmStatic
    fun testHere(source: String, path: String?, io: PcmdIO): RunResult = test0(source, path, io, inline = true)

    @JvmStatic
    fun run(source: String, path: String?, argv: Array<String>, io: PcmdIO, platform: String, timeoutMs: Long): RunResult =
        run0(source, path, argv, io, platform, timeoutMs, inline = false)

    private fun <T> where(inline: Boolean, body: () -> T): T = if (inline) body() else deep(stack, body)

    private fun run0(source: String, path: String?, argv: Array<String>, io: PcmdIO, platform: String, timeoutMs: Long,
                     inline: Boolean): RunResult {
        val root = path?.let { java.io.File(it).absoluteFile.parent } ?: System.getProperty("user.dir") ?: "."
        val rt = Runtime(io, root, argv.toList(), platform)
        if (timeoutMs > 0) {
            rt.deadlineNanos = System.nanoTime() + timeoutMs * 1_000_000
            rt.deadlineText = "it took longer than ${timeoutMs / 1000.0} seconds - an endless loop?"
        }
        if (inline) rt.maxDepth = 1500
        return where(inline) {
            try {
                execute(source, rt, path?.let { java.io.File(it).absolutePath } ?: "<pcmd>")
                rt.flush()
                RunResult(true, 0, "", 0, "")
            } catch (t: Throwable) {
                rt.flush()
                failure(t)
            }
        }
    }

    /** Only the grammar: is this PyCmd at all? (Names are not looked up.) */
    @JvmStatic
    fun parse(source: String): RunResult = try {
        Parser.parse(source)
        RunResult(true, 0, "", 0, "")
    } catch (e: PcSyntaxError) {
        RunResult(false, 1, e.msg, e.line, "Syntax")
    }

    /** Checks a program without running a line of it. */
    @JvmStatic
    fun check(source: String): RunResult {
        val quiet = object : PcmdIO { override fun write(text: String) {}; override fun readLine(): String? = null }
        return try {
            Compiler(source, Runtime(quiet, ".", emptyList(), "check"), "<pcmd>").compileProgram(Parser.parse(source))
            RunResult(true, 0, "", 0, "")
        } catch (e: PcSyntaxError) {
            RunResult(false, 1, e.msg, e.line, "Syntax")
        }
    }

    /** Runs the `test "name" { }` blocks; what they say goes to io. */
    @JvmStatic
    fun test(source: String, path: String?, io: PcmdIO): RunResult = test0(source, path, io, inline = false)

    private fun test0(source: String, path: String?, io: PcmdIO, inline: Boolean): RunResult {
        val quiet = object : PcmdIO { override fun write(text: String) {}; override fun readLine(): String? = null }
        val root = path?.let { java.io.File(it).absoluteFile.parent } ?: "."
        val rt = Runtime(quiet, root, emptyList(), "test")
        if (inline) rt.maxDepth = 1500
        return where(inline) {
            try {
                execute(source, rt, path ?: "<pcmd>")
            } catch (t: Throwable) {
                if (t !is PcExit) {
                    val f = failure(t)
                    io.write(if (t is PcSyntaxError) "${f.error}\n" else "the program failed before its tests ran: ${f.error}\n")
                    return@where RunResult(false, 1, f.error, f.line, f.kind)
                }
            }
            var passed = 0
            var failed = 0
            for ((name, fn, _) in rt.tests) {
                try {
                    fn.call(emptyArray(), null)
                    passed++
                    io.write("  pass  $name\n")
                } catch (t: Throwable) {
                    if (t is PcStop) throw t
                    failed++
                    io.write("  FAIL  $name - ${failure(t).error}\n")
                }
            }
            val total = passed + failed
            if (total == 0) io.write("no tests - write one with: test \"it adds\" { assert add(1, 2) == 3 }\n")
            else io.write("$passed of $total tests passed\n")
            RunResult(failed == 0, if (failed == 0) 0 else 1, "", 0, "", passed, failed)
        }
    }

    @JvmStatic fun libraries(): Map<String, String> = Libs.ABOUT
}
