package com.expstudio.pycmd.lang

import java.io.File

/**
 * How a running program talks to whatever hosts it: the Android app (through
 * Python), the Windows app (through the pcmd process), or a terminal.
 * Java code implements this as an ordinary interface.
 */
interface PcmdIO {
    fun write(text: String)
    /** One line without its newline, or null at the end of input. */
    fun readLine(): String?
    /** Called every few thousand steps. Return true to stop the program. */
    fun tick(): Boolean = false
}

/** Stops a program from outside. A program's own try cannot catch it. */
class PcStop(val why: String) : RuntimeException(why) {
    override fun fillInStackTrace(): Throwable = this
}

class Runtime(
    val io: PcmdIO,
    val root: String,
    val argv: List<String>,
    val platform: String,
) {
    @JvmField var steps = 0L
    @JvmField var depth = 0
    var maxDepth = 10000
    var deadlineNanos = 0L
    var deadlineText = ""
    val tests = ArrayList<Triple<String, Callable, Int>>()
    val builtins: Map<String, Any?> by lazy { Builtins.functions(this) }
    private val libs = HashMap<String, Module>()
    private val files = HashMap<String, Module>()
    private val loading = HashSet<String>()

    // Output is gathered and handed over in pieces: one call per print would
    // be thousands of trips across the bridge to the app.
    private val out = StringBuilder()
    private var lastFlush = System.nanoTime()

    fun write(text: String) {
        out.append(text)
        if (out.length > 8192 || System.nanoTime() - lastFlush > 50_000_000L) flush()
    }

    fun flush() {
        if (out.isNotEmpty()) {
            io.write(out.toString())
            out.setLength(0)
        }
        lastFlush = System.nanoTime()
    }

    fun readLine(): String? {
        flush()
        return io.readLine()
    }

    fun check() {
        if (out.isNotEmpty() && System.nanoTime() - lastFlush > 50_000_000L) flush()
        if (deadlineNanos != 0L && System.nanoTime() > deadlineNanos) throw PcStop(deadlineText)
        if (Thread.currentThread().isInterrupted) throw PcStop("stopped")
        if (io.tick()) throw PcStop("stopped")
    }

    // ------------------------------------------------------------ libraries
    private fun packageFile(name: String): File? {
        val dirs = listOf(File(root, "pcmd_packages"), File(root, "../pcmd_packages"), File(root))
        for (d in dirs) for (ext in listOf(".pcmd", ".pycmd")) {
            val f = File(d, name + ext)
            if (f.isFile && d.name == "pcmd_packages") return f
        }
        return null
    }

    fun hasPackage(name: String) = packageFile(name) != null

    fun lib(name: String): Module {
        libs[name]?.let { return it }
        val m = if (name in Libs.NAMES) Libs.make(name, this) else {
            val f = packageFile(name) ?: throw Errors.name("there is no library called $name - add it with: pcmd add $name")
            importFile(f.path, null)
        }
        libs[name] = m
        return m
    }

    fun importFile(path: String, from: String?): Module {
        val base = if (from != null && File(from).isAbsolute) File(from).parentFile else File(root)
        var f = File(path).let { if (it.isAbsolute) it else File(base, path) }.canonicalFile
        if (!f.isFile) {
            val withExt = listOf(".pcmd", ".pycmd").map { File(f.path + it) }.firstOrNull { it.isFile }
            if (withExt != null) f = withExt.canonicalFile
        }
        val key = f.path
        files[key]?.let { return it }
        if (key in loading) throw Errors.name("$path uses itself, through a loop of use lines")
        if (!f.isFile) throw PcError("there is no file $path to use", "File")
        loading.add(key)
        try {
            val exports = Pcmd.execute(f.readText(), this, key)
            val name = f.name.substringBeforeLast('.')
            val members = LinkedHashMap<String, Any?>()
            for ((k, v) in exports.map) members[k as String] = v
            val m = Module(name, members)
            files[key] = m
            return m
        } finally {
            loading.remove(key)
        }
    }

    companion object {
        /** A failure as a program sees it in catch - or null if it is not the program's to catch. */
        fun asError(t: Throwable): PcError? = when (t) {
            is PcError -> t
            is StackOverflowError -> PcError("too much recursion - a function kept calling itself", "Recursion")
            is OutOfMemoryError -> PcError("the program ran out of memory", "Memory")
            is ArithmeticException -> PcError(t.message ?: "maths error", "Value")
            is NumberFormatException -> PcError(t.message ?: "not a number", "Value")
            is ClassCastException -> PcError("a value of the wrong type was used here", "Type")
            is IndexOutOfBoundsException -> PcError("that index is past the end", "Index")
            is NullPointerException -> PcError("a value is missing (nil) here", "Type")
            else -> null
        }
    }
}
