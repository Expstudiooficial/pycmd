package com.expstudio.pycmd.lang

import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.io.PrintWriter

/**
 * The pcmd command:
 *   pcmd run app.pcmd [args]   pcmd test app.pcmd   pcmd check app.pcmd
 *   pcmd -e "print(1)"         pcmd libs            pcmd version
 *   pcmd serve                 - JSON requests on stdin, one per line (what the apps use)
 */
object Main {
    private val stdout = PrintWriter(OutputStreamWriter(System.out, Charsets.UTF_8), false)
    private val stdin = BufferedReader(InputStreamReader(System.`in`, Charsets.UTF_8))

    private val console = object : PcmdIO {
        override fun write(text: String) { stdout.print(text); stdout.flush() }
        override fun readLine(): String? = stdin.readLine()
    }

    private fun err(text: String) { stdout.flush(); System.err.println(text); System.err.flush() }

    @JvmStatic
    fun main(args: Array<String>) {
        val code = try { main0(args) } finally { stdout.flush() }
        System.exit(code)
    }

    private fun readSource(path: String): String? {
        val f = File(path)
        if (!f.isFile) { err("pcmd: $path: no such file"); return null }
        return f.readText()
    }

    private fun main0(args: Array<String>): Int {
        val cmd = args.getOrNull(0) ?: "help"
        when (cmd) {
            "version", "--version", "-v" -> { stdout.println("PyCmd ${Pcmd.VERSION}"); return 0 }
            "libs" -> { for ((n, w) in Libs.ABOUT) stdout.println("  use ${n.padEnd(11)} $w"); return 0 }
            "-e", "eval" -> {
                val r = Pcmd.run(args.drop(1).joinToString(" "), null, emptyArray(), console, "cli", 0)
                if (!r.ok) { err("PyCmd error, ${r.error}"); return 1 }
                return r.exit
            }
            "run" -> {
                val path = args.getOrNull(1) ?: run { err("pcmd run: which file?"); return 1 }
                val src = readSource(path) ?: return 1
                val argv = arrayOf(File(path).name) + args.drop(2)
                val r = Pcmd.run(src, path, argv, console, platform(), 0)
                if (!r.ok) { err("PyCmd error, ${r.error}"); return 1 }
                return r.exit
            }
            "test" -> {
                val path = args.getOrNull(1) ?: run { err("pcmd test: which file?"); return 1 }
                val src = readSource(path) ?: return 1
                return if (Pcmd.test(src, path, console).ok) 0 else 1
            }
            "check" -> {
                val path = args.getOrNull(1) ?: run { err("pcmd check: which file?"); return 1 }
                val src = readSource(path) ?: return 1
                val r = Pcmd.check(src)
                if (r.ok) { stdout.println("$path: no problems found"); return 0 }
                err("$path, line ${r.line}: ${r.error}")
                return 1
            }
            "serve" -> return serve()
            "help", "-h", "--help" -> {
                stdout.println("PyCmd ${Pcmd.VERSION} - pcmd run file.pcmd | test | check | -e \"code\" | libs | version")
                return 0
            }
        }
        if (cmd.endsWith(".pcmd") || cmd.endsWith(".pycmd")) return main0(arrayOf("run") + args)
        err("pcmd: no '$cmd' - try: pcmd help")
        return 2
    }

    private fun platform(): String = System.getProperty("os.name", "").lowercase().let {
        when { "win" in it -> "windows"; "mac" in it -> "mac"; else -> "linux" }
    }

    /** One JSON request per line in, one JSON answer per line out. */
    private fun serve(): Int {
        while (true) {
            val line = stdin.readLine() ?: return 0
            if (line.isBlank()) continue
            val reply = PMap()
            try {
                val req = Json.parse(line) as PMap
                fun get(k: String) = req.map[k]
                reply.map["id"] = get("id")
                val out = StringBuilder()
                val input = ((get("stdin") as? String) ?: "").split("\n").toMutableList()
                if (input.lastOrNull() == "") input.removeAt(input.size - 1)
                val io = object : PcmdIO {
                    override fun write(text: String) { if (out.length < 2_000_000) out.append(text) }
                    override fun readLine(): String? = if (input.isEmpty()) null else input.removeAt(0)
                }
                val source = get("source") as? String ?: ""
                val path = get("path") as? String
                val timeout = Num.toDouble(get("timeout") ?: 0L)
                val argv = ((get("argv") as? PList)?.items?.map { Show.show(it) } ?: emptyList()).toTypedArray()
                val r = when (get("op")) {
                    "check" -> Pcmd.check(source)
                    "parse" -> Pcmd.parse(source)
                    "test" -> Pcmd.test(source, path, io)
                    "version" -> RunResult(true, 0, Pcmd.VERSION, 0, "")
                    else -> Pcmd.run(source, path, argv, io, (get("platform") as? String) ?: platform(), (timeout * 1000).toLong())
                }
                reply.map["ok"] = r.ok; reply.map["exit"] = r.exit.toLong(); reply.map["error"] = r.error
                reply.map["line"] = r.line.toLong(); reply.map["kind"] = r.kind; reply.map["out"] = out.toString()
                reply.map["passed"] = r.passed.toLong(); reply.map["failed"] = r.failed.toLong()
            } catch (t: Throwable) {
                reply.map["ok"] = false
                reply.map["error"] = "the engine could not read that request: ${t.message}"
            }
            stdout.println(Json.write(reply, null))
            stdout.flush()
        }
    }
}
