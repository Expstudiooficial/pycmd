package com.expstudio.pycmd.python

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.expstudio.pycmd.js.JsEngine
import com.expstudio.pycmd.util.DebugLog
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** The main console's channel name. Servers use their own handle. */
const val CONSOLE_CHANNEL = "console"

/** One line of console output, tagged with where it came from. */
data class OutputChunk(
    val stream: Stream,
    val text: String,
    val id: Long,
    val channel: String = CONSOLE_CHANNEL,
) {
    enum class Stream { STDOUT, STDERR, INPUT, SYSTEM }
}

/** What the console needs to know about the interpreter right now. */
data class EngineStatus(
    val ready: Boolean = false,
    val running: Boolean = false,
    val awaitingInput: Boolean = false,
    val pythonVersion: String = "",
    val startupError: String? = null,
)

/**
 * Owns the embedded CPython interpreter.
 *
 * Python runs on one dedicated thread for its whole life: CPython keeps
 * per-thread state, and Chaquopy is happiest when calls come from a consistent
 * thread. Everything the UI asks for is funnelled onto that thread, and output
 * comes back through [output].
 *
 * Stopping and killing servers deliberately do *not* use that thread. If a
 * script has wedged the interpreter, a stop request queued behind it would
 * never arrive — which is exactly when the user needs it most — so those calls
 * go through [controlDispatcher] and reach Python by taking the GIL from a
 * second thread.
 */
object PythonEngine {

    private const val TAG = "engine"
    private const val OUTPUT_BUFFER = 512

    /** Log tag for anything a custom plugin does. */
    private const val TAG_PLUGIN = "plugin"

    /** Files the device's own JavaScript engine runs, rather than Python. */
    private val JS_EXTENSIONS = setOf("js", "mjs", "cjs")

    /** The single thread every ordinary Python call runs on. */
    private val pythonExecutor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "python-main").apply { isDaemon = true }
    }
    private val pythonDispatcher = pythonExecutor.asCoroutineDispatcher()

    /**
     * Control operations — stop, kill, listing — that must not queue behind the
     * code they are trying to control, nor block the UI thread waiting for the
     * GIL.
     */
    private val controlExecutor = Executors.newFixedThreadPool(4) { runnable ->
        Thread(runnable, "python-control").apply { isDaemon = true }
    }
    private val controlDispatcher = controlExecutor.asCoroutineDispatcher()

    /**
     * Stop and Kill, and nothing else.
     *
     * These used to share the control pool with downloads, exports, previews
     * and the doctor's fixes. Two of those running at once filled the pool,
     * and the Kill button - the one thing that must always get through -
     * queued behind a 60 MB download. Its own threads is the only honest way
     * to promise that a rescue is never waiting on ordinary work.
     */
    private val rescueExecutor = Executors.newFixedThreadPool(2) { runnable ->
        Thread(runnable, "python-rescue").apply {
            isDaemon = true
            priority = Thread.NORM_PRIORITY + 2
        }
    }
    private val rescueDispatcher = rescueExecutor.asCoroutineDispatcher()

    /**
     * Everything a plugin panel asks for, on one thread of its own.
     *
     * Panels poll: the ones that ship here refresh every two and five seconds,
     * and every refresh is a Python call that wants the GIL. Sharing the
     * control pool meant that while a script was running, four of those could
     * take all four control threads - and then the Files tab's listing, the
     * Servers tab's refresh and anything else the screen needed queued behind
     * them, which reads as the app freezing and coming back. One thread means
     * panels can be as chatty as they like and never crowd anything else out.
     */
    private val pluginExecutor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "python-plugins").apply { isDaemon = true }
    }
    private val pluginDispatcher = pluginExecutor.asCoroutineDispatcher()

    private val _output = MutableSharedFlow<OutputChunk>(
        replay = OUTPUT_BUFFER,
        extraBufferCapacity = OUTPUT_BUFFER,
        // A script that floods stdout must not stall the interpreter thread
        // waiting for the UI: the oldest output scrolls away instead, which is
        // what a terminal does anyway.
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val output: SharedFlow<OutputChunk> = _output.asSharedFlow()

    private val _status = MutableStateFlow(EngineStatus())
    val status: StateFlow<EngineStatus> = _status.asStateFlow()

    private val _serverCount = MutableStateFlow(0)
    val serverCount: StateFlow<Int> = _serverCount.asStateFlow()

    /** Channels currently blocked inside `input()`. */
    private val _awaitingInput = MutableStateFlow<Set<String>>(emptySet())
    val awaitingInput: StateFlow<Set<String>> = _awaitingInput.asStateFlow()

    /** Hand-off between each channel's input box and its `input()` call. */
    private val stdinQueues = ConcurrentHashMap<String, LinkedBlockingQueue<String>>()
    private val cancelledChannels = ConcurrentHashMap<String, Boolean>()
    private val chunkId = AtomicLong(0)

    /** Groups stderr fragments arriving in quick succession into one entry. */
    private const val STDERR_COALESCE_MS = 180L
    private val stderrLock = Any()
    private val stderrBuffers = HashMap<String, StringBuilder>()
    private val stderrFlushes = HashMap<String, ScheduledFuture<*>>()
    private val stderrFlusher = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "python-stderr").apply { isDaemon = true }
    }

    private lateinit var runtime: PyObject
    private lateinit var packages: PyObject
    private lateinit var servers: PyObject
    private lateinit var downloads: PyObject
    private lateinit var tools: PyObject
    private lateinit var preview: PyObject
    private lateinit var pluginRuntime: PyObject
    private lateinit var cloudRuntime: PyObject
    private lateinit var pages: PyObject
    private lateinit var tunnel: PyObject
    private lateinit var cloudflare: PyObject
    private lateinit var music: PyObject

    private lateinit var appContext: Context
    private lateinit var workspaceDir: File
    private lateinit var sitePackagesDir: File
    private lateinit var downloadsDir: File

    /** Where downloads land, for the UI to describe what is already there. */
    val downloadsFolder: File get() = downloadsDir

    private lateinit var musicTracksDir: File

    /** Where an imported track is copied to before the library adopts it. */
    val musicFolder: File get() = musicTracksDir
    private lateinit var pluginsDir: File

    private fun queueFor(channel: String): LinkedBlockingQueue<String> =
        stdinQueues.getOrPut(channel) { LinkedBlockingQueue(64) }

    /** Receives stdout/stderr from Python and supplies stdin. Called on Python threads. */
    @Suppress("unused") // Called from pycmd_runtime.py
    private val sink = object {
        fun onOutput(stream: String, text: String, channel: String) {
            val kind = when (stream) {
                "stderr" -> OutputChunk.Stream.STDERR
                "system" -> OutputChunk.Stream.SYSTEM
                else -> OutputChunk.Stream.STDOUT
            }
            emit(kind, text, channel)
            if (kind == OutputChunk.Stream.STDERR) {
                // Tracebacks are the single most useful thing in the debug log,
                // but they can arrive one line per write. Buffer the burst so a
                // traceback becomes one entry rather than a dozen.
                bufferStderr(channel, text)
            }
        }

        fun onReadLine(channel: String): String? = readLineFor(channel)

        fun onFinished(runId: Int, status: String, millis: Int) {
            DebugLog.debug(TAG, "run $runId finished: $status in ${millis}ms")
        }
    }

    /**
     * Collects stderr into one debug entry per burst.
     *
     * `sys.stderr.write` is called once per traceback by our own runner, but
     * anything writing line by line - threading's excepthook, a third-party
     * logger - would otherwise fill the debug console with fragments and
     * inflate the error count. A short quiet period marks the end of a burst.
     */
    private fun bufferStderr(channel: String, text: String) {
        synchronized(stderrLock) {
            stderrBuffers.getOrPut(channel) { StringBuilder() }.append(text)
            stderrFlushes.remove(channel)?.cancel(false)
            stderrFlushes[channel] = stderrFlusher.schedule(
                { flushStderr(channel) },
                STDERR_COALESCE_MS,
                TimeUnit.MILLISECONDS,
            )
        }
    }

    private fun flushStderr(channel: String) {
        val text = synchronized(stderrLock) {
            stderrFlushes.remove(channel)
            stderrBuffers.remove(channel)?.toString()
        } ?: return
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        val tag = if (channel == CONSOLE_CHANNEL) "python" else "server:$channel"
        // The first line is the headline; a traceback's body is the detail.
        val lines = trimmed.lineSequence().toList()
        if (lines.size <= 1) {
            DebugLog.error(tag, trimmed)
        } else {
            DebugLog.error(tag, lines.last().ifBlank { lines.first() }, trimmed)
        }
    }

    /**
     * Waits for one line on [channel].
     *
     * Shared by Python's `input()` and JavaScript's `readLine()`: both are the
     * same promise to the user - the console shows an input box, and whatever
     * they type comes back here - so both should queue in the same place.
     */
    private fun readLineFor(channel: String): String? {
        markAwaiting(channel, true)
        try {
            val queue = queueFor(channel)
            while (true) {
                if (cancelledChannels.remove(channel) != null) return null
                val line = queue.poll(150, TimeUnit.MILLISECONDS)
                if (line != null) return line
            }
        } catch (interrupted: InterruptedException) {
            Thread.currentThread().interrupt()
            return null
        } finally {
            markAwaiting(channel, false)
        }
    }

    private fun markAwaiting(channel: String, waiting: Boolean) {
        _awaitingInput.value = _awaitingInput.value.toMutableSet().apply {
            if (waiting) add(channel) else remove(channel)
        }
        if (channel == CONSOLE_CHANNEL) {
            _status.value = _status.value.copy(awaitingInput = waiting)
        }
    }

    /** Reports installer progress back to the UI. Called on the Python thread. */
    private class ProgressSink(private val onMessage: (String) -> Unit) {
        @Suppress("unused") // Called from pycmd_packages.py
        fun onProgress(message: String) = onMessage(message)
    }

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------

    /** Starts CPython. Safe to call more than once; later calls are no-ops. */
    suspend fun start(context: Context): EngineStatus = withContext(pythonDispatcher) {
        if (_status.value.ready) return@withContext _status.value

        appContext = context.applicationContext
        workspaceDir = File(appContext.filesDir, "workspace").apply { mkdirs() }
        sitePackagesDir = File(appContext.filesDir, "site-packages").apply { mkdirs() }

        val startedAt = System.currentTimeMillis()
        DebugLog.info(TAG, "starting interpreter")
        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(appContext))
            }
            val python = Python.getInstance()
            runtime = python.getModule("pycmd_runtime")
            packages = python.getModule("pycmd_packages")
            servers = python.getModule("pycmd_servers")
            downloads = python.getModule("pycmd_download")
            tools = python.getModule("pycmd_tools")
            preview = python.getModule("pycmd_preview")
            pluginRuntime = python.getModule("pycmd_plugins")
            cloudRuntime = python.getModule("pycmd_cloud")
            pages = python.getModule("pycmd_pages")
            tunnel = python.getModule("pycmd_tunnel")
            cloudflare = python.getModule("pycmd_cloudflare")
            music = python.getModule("pycmd_music")

            val version = runtime.callAttr(
                "configure",
                sink,
                workspaceDir.absolutePath,
                sitePackagesDir.absolutePath,
            ).toString()
            packages.callAttr("configure", sitePackagesDir.absolutePath)
            downloadsDir = File(appContext.filesDir, "downloads").apply { mkdirs() }
            downloads.callAttr("configure", downloadsDir.absolutePath, workspaceDir.absolutePath)
            // Cloud keys live in the app's own storage, never in the
            // workspace: the workspace is the folder people export and share.
            val cloudDir = File(appContext.filesDir, "cloud").apply { mkdirs() }
            cloudRuntime.callAttr("configure_storage", cloudDir.absolutePath)
            // The registry of pages, and the Cloudflare token, live beside the
            // cloud keys for the same reason: neither belongs in the workspace,
            // which is the folder people export and hand to other people.
            val pagesDir = File(appContext.filesDir, "pages").apply { mkdirs() }
            pages.callAttr("configure", pagesDir.absolutePath)
            cloudflare.callAttr("configure_storage", cloudDir.absolutePath)
            // The music library is app storage too, and for a third reason:
            // it is the one folder here holding files that are not the user's
            // code, and nobody wants their album in a workspace export.
            val musicDir = File(appContext.filesDir, "music").apply { mkdirs() }
            musicTracksDir = File(music.callAttr("configure", musicDir.absolutePath).toString())
            pluginsDir = File(appContext.filesDir, "plugins").apply { mkdirs() }
            pluginRuntime.callAttr(
                "configure", pluginsDir.absolutePath, workspaceDir.absolutePath, pluginHost,
            )
            // JavaScript is the one runnable language Python cannot start, so
            // the Servers tab reaches it by handing Python a way back out.
            val jsNote = "Runs in the device's own JavaScript engine. One at a time."
            for (extension in JS_EXTENSIONS) {
                servers.callAttr("register_runner", ".$extension", jsFileRunner, jsNote)
            }

            val short = version.trim().split(" ").firstOrNull().orEmpty()
            _status.value = EngineStatus(ready = true, pythonVersion = short)
            emit(OutputChunk.Stream.SYSTEM, "Python $short ready. Type code and press Run.\n")
            DebugLog.info(
                TAG,
                "interpreter ready in ${System.currentTimeMillis() - startedAt}ms",
                "Python $short",
            )
        } catch (error: Throwable) {
            _status.value = EngineStatus(
                ready = false,
                startupError = error.message ?: error.javaClass.simpleName,
            )
            emit(OutputChunk.Stream.STDERR, "Interpreter failed to start: ${error.message}\n")
            DebugLog.error(TAG, "interpreter failed to start", error)
        }
        _status.value
    }

    private fun emit(
        stream: OutputChunk.Stream,
        text: String,
        channel: String = CONSOLE_CHANNEL,
    ) {
        if (text.isEmpty()) return
        // emit() is reached from the Python threads and the UI thread alike.
        _output.tryEmit(OutputChunk(stream, text, chunkId.incrementAndGet(), channel))
    }

    /** Echo something into a channel without going through Python. */
    fun echo(
        text: String,
        stream: OutputChunk.Stream = OutputChunk.Stream.SYSTEM,
        channel: String = CONSOLE_CHANNEL,
    ) = emit(stream, text, channel)

    // ------------------------------------------------------------------
    // Running code
    // ------------------------------------------------------------------

    /**
     * Runs [source] and suspends until it completes.
     *
     * Because every ordinary Python call shares one thread, a second run can
     * only begin once the first has returned — which is the behaviour a console
     * wants.
     */
    /**
     * A line typed into the console, which may be a command rather than Python.
     *
     * Python is still what most of it is; the split happens on the Python side
     * so a command runs on the same thread, with the same output routing and
     * the same Stop button as everything else.
     */
    suspend fun runConsoleLine(source: String): String {
        if (!_status.value.ready) return "error"
        cancelledChannels.remove(CONSOLE_CHANNEL)
        queueFor(CONSOLE_CHANNEL).clear()
        _status.value = _status.value.copy(running = true)
        return try {
            withContext(pythonDispatcher) {
                runtime.callAttr("run_console", source).toString()
            }
        } catch (error: Throwable) {
            emit(OutputChunk.Stream.STDERR, "Internal error: ${error.message}\n")
            DebugLog.error(TAG, "console line failed", error)
            "error"
        } finally {
            _status.value = _status.value.copy(running = false)
        }
    }

    /** The console's own command names, for completion. */
    suspend fun consoleCommands(): List<String> = withContext(pythonDispatcher) {
        runCatching {
            runtime.callAttr("console_commands").asList().map { it.toString() }
        }.getOrDefault(emptyList())
    }

    suspend fun run(source: String, sourceName: String = "<console>", echoResult: Boolean = true): String {
        if (!_status.value.ready) return "error"
        cancelledChannels.remove(CONSOLE_CHANNEL)
        queueFor(CONSOLE_CHANNEL).clear()
        _status.value = _status.value.copy(running = true)
        return try {
            withContext(pythonDispatcher) {
                runtime.callAttr("run_source", source, sourceName, echoResult).toString()
            }
        } catch (error: Throwable) {
            emit(OutputChunk.Stream.STDERR, "Internal error: ${error.message}\n")
            DebugLog.error(TAG, "run failed", error)
            "error"
        } finally {
            _status.value = _status.value.copy(running = false, awaitingInput = false)
            refreshServerCount()
        }
    }

    /**
     * Runs a file with whichever engine its extension calls for.
     *
     * Python keeps the console's namespace; C goes through the interpreter
     * built into the app; anything without an engine reports why rather than
     * failing silently.
     */
    suspend fun runAny(path: String): String {
        if (!_status.value.ready) return "error"
        if (path.substringAfterLast('.', "").lowercase() in JS_EXTENSIONS) {
            return runJavaScript(path)
        }
        cancelledChannels.remove(CONSOLE_CHANNEL)
        queueFor(CONSOLE_CHANNEL).clear()
        _status.value = _status.value.copy(running = true)
        return try {
            withContext(pythonDispatcher) { runtime.callAttr("run_any", path).toString() }
        } catch (error: Throwable) {
            emit(OutputChunk.Stream.STDERR, "Internal error: ${error.message}\n")
            DebugLog.error(TAG, "run_any failed: $path", error)
            "error"
        } finally {
            _status.value = _status.value.copy(running = false, awaitingInput = false)
            refreshServerCount()
        }
    }

    /**
     * Runs a `.js` file in the device's own JavaScript engine.
     *
     * This one deliberately never reaches Python. Writing a JavaScript
     * interpreter in Python, to run on a device that already ships a complete
     * one, would be slower and less correct in every corner that matters -
     * so the file goes straight to the real engine, and its output arrives on
     * the console channel exactly as Python's does.
     */
    private suspend fun runJavaScript(path: String): String {
        val file = File(path)
        val source = try {
            file.readText()
        } catch (error: Throwable) {
            emit(OutputChunk.Stream.STDERR, "cannot open $path: ${error.message}\n")
            return "error"
        }

        cancelledChannels.remove(CONSOLE_CHANNEL)
        queueFor(CONSOLE_CHANNEL).clear()
        _status.value = _status.value.copy(running = true)
        emit(OutputChunk.Stream.SYSTEM, "Running ${file.name} as JavaScript\n")

        val host = object : JsEngine.Host {
            override fun stdout(text: String) = emit(OutputChunk.Stream.STDOUT, text)
            override fun stderr(text: String) {
                emit(OutputChunk.Stream.STDERR, text)
                bufferStderr(CONSOLE_CHANNEL, text)
            }
            override fun readLine(): String? = readLineFor(CONSOLE_CHANNEL)
        }

        val started = System.currentTimeMillis()
        return try {
            val result = JsEngine.run(appContext, source, file.name, host)
            val millis = (System.currentTimeMillis() - started).toInt()
            when {
                result.status == "stopped" -> {
                    emit(OutputChunk.Stream.STDERR, "\nJavaScript stopped\n")
                    DebugLog.debug(TAG, "javascript run stopped after ${millis}ms")
                    "stopped"
                }
                result.status != "ok" -> "error"
                result.exitCode != 0 -> {
                    emit(
                        OutputChunk.Stream.STDERR,
                        "JavaScript exited with status ${result.exitCode}\n",
                    )
                    "error"
                }
                else -> "ok"
            }
        } catch (error: Throwable) {
            emit(OutputChunk.Stream.STDERR, "Internal error: ${error.message}\n")
            DebugLog.error(TAG, "javascript run failed: $path", error)
            "error"
        } finally {
            _status.value = _status.value.copy(running = false, awaitingInput = false)
        }
    }

    /**
     * Builds the page a previewable file shows.
     *
     * HTML is passed through, Markdown is converted, and a stylesheet gets a
     * demo page - a CSS file previewed on its own would otherwise render as a
     * blank screen, which looks like a bug rather than an answer.
     */
    suspend fun previewPage(path: String): PreviewPage? = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext null
        runCatching {
            val map = preview.callAttr("serve", path).asMap()
            if (map.str("ok") != "True") {
                DebugLog.warn(TAG, "preview failed", map.str("error"))
                return@runCatching null
            }
            val served = map.str("served") == "True"
            if (!served && map.str("error").isNotEmpty()) {
                DebugLog.warn(TAG, "preview is not being served", map.str("error"))
            }
            PreviewPage(
                name = map.str("name"),
                html = map.str("html"),
                baseDirectory = map.str("base"),
                url = map.str("url"),
                served = served,
            )
        }.getOrElse {
            DebugLog.error(TAG, "preview failed: $path", it)
            null
        }
    }

    /**
     * Answers a fix the app offered after an error.
     *
     * Goes through the rescue dispatcher so a server whose script is wedged
     * can still be answered, and returns whether the line was consumed - a
     * server's stdin is a real thing people type into, and "yes" might have
     * been meant for the program rather than for us.
     *
     * It returns as soon as the reply is understood. `done` says whether the
     * fix is already finished; when it is false the work is running on its own
     * thread and narrating itself into the console it was asked in.
     */
    suspend fun answerFix(channel: String, text: String): JSONObject =
        withContext(rescueDispatcher) {
            if (!_status.value.ready) return@withContext JSONObject().put("handled", false)
            runCatching {
                // The console's offers live in the runtime, a server's in the
                // server module, because that is where each one's output goes.
                val module = if (channel == CONSOLE_CHANNEL) runtime else servers
                val map = module.callAttr("answer_fix", channel, text).asMap()
                JSONObject()
                    .put("handled", map.str("handled") == "True")
                    .put("applied", map.str("applied") == "True")
                    .put("done", map.str("done") == "True")
                    .put("message", map.str("message"))
                    .put("kind", map.str("fix_kind"))
                    .put("port", map.str("port"))
            }.getOrElse {
                DebugLog.debug(TAG, "no fix was pending", it.message.orEmpty())
                JSONObject().put("handled", false)
            }
        }

    /** Every extension the preview can show, so the file list knows. */
    // ---- Pages: projects that are websites --------------------------------

    /** Every page, with whether it is up, where, and what it costs. */
    suspend fun pages(): JSONArray = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext JSONArray()
        runCatching { JSONArray(pages.callAttr("listing").toString()) }
            .getOrDefault(JSONArray())
    }

    /** The two ceilings, and where this phone is against them. */
    suspend fun pageCounts(): JSONObject = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext JSONObject()
        runCatching { JSONObject(pages.callAttr("counts").toString()) }
            .getOrDefault(JSONObject())
    }

    /** What a new page can start as. */
    suspend fun pageTemplates(): JSONArray = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext JSONArray()
        runCatching { JSONArray(pages.callAttr("templates").toString()) }
            .getOrDefault(JSONArray())
    }

    /** The workspace folders a page could point at, for the picker. */
    suspend fun pageFolders(): JSONArray = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext JSONArray()
        runCatching {
            JSONArray(pages.callAttr("folders", workspaceDir.absolutePath).toString())
        }.getOrDefault(JSONArray())
    }

    private suspend fun pageCall(name: String, vararg args: Any?): JSONObject =
        withContext(controlDispatcher) {
            if (!_status.value.ready) {
                return@withContext failed("The interpreter is not ready yet.")
            }
            runCatching {
                JSONObject(
                    when (args.size) {
                        0 -> pages.callAttr(name)
                        1 -> pages.callAttr(name, args[0])
                        2 -> pages.callAttr(name, args[0], args[1])
                        else -> pages.callAttr(name, args[0], args[1], args[2])
                    }.toString(),
                )
            }.getOrElse { failed(it.message.orEmpty()) }
        }

    private fun failed(message: String) = JSONObject()
        .put("ok", false)
        .put("error", message.ifBlank { "That did not work." })

    suspend fun createPage(name: String, template: String): JSONObject =
        pageCall("create", name, template, workspaceDir.absolutePath)

    suspend fun adoptPage(name: String, folder: String): JSONObject =
        pageCall("adopt", name, folder)

    suspend fun renamePage(id: String, name: String): JSONObject = pageCall("rename", id, name)

    suspend fun removePage(id: String, deleteFiles: Boolean): JSONObject =
        pageCall("remove", id, deleteFiles)

    suspend fun startPage(id: String): JSONObject = pageCall("start", id, true)

    suspend fun stopPage(id: String): JSONObject = pageCall("stop", id)

    suspend fun stopAllPages(): JSONObject = pageCall("stop_all")

    suspend fun sharePage(id: String): JSONObject = pageCall("share", id)

    suspend fun unsharePage(id: String): JSONObject = pageCall("unshare", id)

    suspend fun setPageHost(id: String, host: String): JSONObject = pageCall("set_host", id, host)

    /** Remembers where a page was last deployed, so its card can link to it. */
    suspend fun notePageDeployment(
        id: String,
        url: String,
        project: String,
        files: Int,
        bytes: Long,
    ): JSONObject = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext failed("The interpreter is not ready yet.")
        runCatching {
            JSONObject(
                pages.callAttr("note_deployment", id, url, project, files, bytes).toString(),
            )
        }.getOrElse { failed(it.message.orEmpty()) }
    }

    /** Copies what would be deployed into the page's own build folder. */
    suspend fun stagePage(id: String): JSONObject = pageCall("stage", id)

    /** Everywhere this page has been sent, newest first. */
    suspend fun pageDeployments(id: String): JSONObject = pageCall("deployments", id)

    /** Throws away the build copy; the history stays. */
    suspend fun clearPageBuild(id: String): JSONObject = pageCall("clear_build", id)

    // ---- Music: the library, not the playing ------------------------------

    /**
     * Everything the Music tab draws: tracks, playlists and what was last on.
     *
     * Playback itself never comes through here - it is a media session in
     * Kotlin, because only Kotlin can keep sound going with the app closed.
     * This is the library that decides what there is to play.
     */
    suspend fun musicLibrary(): JSONObject = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext JSONObject()
        runCatching { JSONObject(music.callAttr("library").toString()) }
            .getOrDefault(JSONObject())
    }

    /** The tracks of one playlist in order, or the whole library for "". */
    suspend fun musicQueue(playlistId: String): JSONObject =
        musicCall("queue", playlistId)

    private suspend fun musicCall(name: String, vararg args: Any?): JSONObject =
        withContext(controlDispatcher) {
            if (!_status.value.ready) {
                return@withContext failed("The interpreter is not ready yet.")
            }
            runCatching {
                JSONObject(
                    when (args.size) {
                        0 -> music.callAttr(name)
                        1 -> music.callAttr(name, args[0])
                        2 -> music.callAttr(name, args[0], args[1])
                        3 -> music.callAttr(name, args[0], args[1], args[2])
                        4 -> music.callAttr(name, args[0], args[1], args[2], args[3])
                        5 -> music.callAttr(
                            name, args[0], args[1], args[2], args[3], args[4],
                        )
                        // `remember` takes six since 2.6.0. The list used to
                        // stop at four and silently drop everything past it,
                        // which is the kind of limit that is fine until the
                        // day a call quietly loses its last argument.
                        else -> music.callAttr(
                            name, args[0], args[1], args[2], args[3], args[4], args[5],
                        )
                    }.toString(),
                )
            }.getOrElse { failed(it.message.orEmpty()) }
        }

    suspend fun adoptTrack(path: String, title: String, artist: String, duration: Long):
        JSONObject = musicCall("adopt", path, title, artist, duration)

    suspend fun renameTrack(id: String, title: String): JSONObject =
        musicCall("rename_track", id, title)

    suspend fun removeTrack(id: String): JSONObject = musicCall("remove_track", id, true)

    suspend fun createPlaylist(name: String): JSONObject = musicCall("create_playlist", name)

    suspend fun renamePlaylist(id: String, name: String): JSONObject =
        musicCall("rename_playlist", id, name)

    suspend fun removePlaylist(id: String): JSONObject = musicCall("remove_playlist", id)

    suspend fun addToPlaylist(playlistId: String, trackId: String): JSONObject =
        musicCall("add_to_playlist", playlistId, trackId)

    suspend fun removeFromPlaylist(playlistId: String, trackId: String): JSONObject =
        musicCall("remove_from_playlist", playlistId, trackId)

    suspend fun moveInPlaylist(playlistId: String, trackId: String, delta: Int): JSONObject =
        musicCall("move_in_playlist", playlistId, trackId, delta)

    /** Keeps the loop and shuffle choice, the speed, the timer, and what was playing. */
    suspend fun rememberMusic(
        loop: String,
        shuffle: Boolean,
        trackId: String,
        playlistId: String,
        speed: Double = 1.0,
        sleepMinutes: Int = 0,
    ): JSONObject =
        musicCall("remember", loop, shuffle, trackId, playlistId, speed, sleepMinutes)

    /** The library, searched, sorted and narrowed to a smart list. */
    suspend fun browseMusic(
        search: String,
        sort: String,
        playlistId: String,
        collection: String,
    ): JSONObject = musicCall("browse", search, sort, playlistId, collection)

    /** The smart lists that have anything in them. */
    suspend fun musicCollections(): JSONObject = musicCall("collections")

    /** Counts a play. Called once a track has been going long enough to count. */
    suspend fun countPlay(trackId: String): JSONObject = musicCall("played", trackId)

    /** What was played, most recent first. */
    suspend fun musicHistory(limit: Int = 25): JSONObject = musicCall("history", limit)

    /** Everything known about one track. */
    suspend fun describeTrack(trackId: String): JSONObject = musicCall("describe", trackId)

    /** Corrects a track's title, artist or album. Blank leaves one alone. */
    suspend fun setTrackDetails(
        trackId: String,
        title: String,
        artist: String,
        album: String,
    ): JSONObject = musicCall("set_details", trackId, title, artist, album)

    /** The numbers: how many, how long, how often, and by whom. */
    suspend fun musicStats(): JSONObject = musicCall("stats")

    /** Drops rows whose file has gone, and files no row points at. */
    suspend fun tidyMusic(): JSONObject = musicCall("tidy")

    // ---- Cloudflare -------------------------------------------------------

    private suspend fun cloudflareCall(name: String, vararg args: Any?): JSONObject =
        withContext(controlDispatcher) {
            if (!_status.value.ready) {
                return@withContext failed("The interpreter is not ready yet.")
            }
            runCatching {
                JSONObject(
                    when (args.size) {
                        0 -> cloudflare.callAttr(name)
                        1 -> cloudflare.callAttr(name, args[0])
                        2 -> cloudflare.callAttr(name, args[0], args[1])
                        else -> cloudflare.callAttr(name, args[0], args[1], args[2])
                    }.toString(),
                )
            }.getOrElse { failed(it.message.orEmpty()) }
        }

    suspend fun cloudflareState(): JSONObject = cloudflareCall("state")

    suspend fun connectCloudflare(account: String, token: String): JSONObject =
        cloudflareCall("connect", account, token)

    suspend fun forgetCloudflare(): JSONObject = cloudflareCall("forget")

    suspend fun cloudflareProjects(): JSONObject = cloudflareCall("projects")

    /**
     * Uploads a folder to Cloudflare Pages.
     *
     * On the control dispatcher rather than the Python one: a deploy is minutes
     * of network, and the interpreter must stay free to run everything else
     * while it happens.
     */
    suspend fun deployToCloudflare(
        folder: String,
        project: String,
        onProgress: (String) -> Unit,
    ): JSONObject = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext failed("The interpreter is not ready yet.")
        runCatching {
            JSONObject(
                cloudflare.callAttr(
                    "deploy_folder", folder, project, "main", ProgressSink(onProgress),
                ).toString(),
            )
        }.getOrElse { failed(it.message.orEmpty()) }
    }

    suspend fun publishWorker(name: String, script: String): JSONObject =
        cloudflareCall("put_worker", name, script)

    /** The starter Worker, so the app never asks for a blank page. */
    suspend fun workerTemplate(): String = withContext(controlDispatcher) {
        runCatching { cloudflare["WORKER_TEMPLATE"]?.toString().orEmpty() }.getOrDefault("")
    }

        /**
     * What PyPI says about a package, before anything is downloaded.
     *
     * The Packages tab used to find out a package cannot work here by trying
     * it: a minute of downloading, then a sentence about compiled wheels.
     */
    suspend fun packageInfo(name: String): JSONObject = withContext(pythonDispatcher) {
        runCatching {
            JSONObject(packages.callAttr("info", name).toString())
        }.getOrElse { JSONObject().put("ok", false).put("error", it.message.orEmpty()) }
    }

    suspend fun previewableExtensions(): Set<String> = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext emptySet()
        runCatching {
            preview.callAttr("extensions").toString()
                .split(",")
                .map { it.trim().removePrefix(".").lowercase() }
                .filter { it.isNotEmpty() }
                .toSet()
        }.getOrDefault(emptySet())
    }

    /** Shuts the preview server down when the preview closes. */
    suspend fun stopPreview() = withContext(controlDispatcher) {
        runCatching { preview.callAttr("stop") }
        Unit
    }

    /** Renders text the app is holding - a shipped document, say - as a page. */
    suspend fun previewText(text: String, name: String): PreviewPage? =
        withContext(controlDispatcher) {
            if (!_status.value.ready) return@withContext null
            runCatching {
                // Served over the same loopback path as a file preview, so a
                // shipped guide behaves like every other page: anchors jump,
                // scrolling is the browser's own, nothing is a special case.
                val map = preview.callAttr("serve_text", text, name).asMap()
                PreviewPage(
                    name = map.str("name"),
                    html = map.str("html"),
                    baseDirectory = map.str("base"),
                    url = map.str("url"),
                    served = map.str("served") == "True",
                )
            }.getOrElse {
                DebugLog.error(TAG, "could not render $name", it)
                null
            }
        }

    /** Every file type the new-file menu offers. */
    suspend fun languageCatalogue(includeAll: Boolean): List<LanguageInfo> =
        withContext(pythonDispatcher) {
            if (!_status.value.ready) return@withContext emptyList()
            runCatching {
                runtime.callAttr("language_catalogue", includeAll).asList().map { row ->
                    val map = row.asMap()
                    LanguageInfo(
                        id = map.str("id"),
                        name = map.str("name"),
                        extension = map.str("extension"),
                        mode = map.str("mode"),
                        highlight = map.str("highlight"),
                        note = map.str("note"),
                        extensions = map.str("extensions"),
                        mime = map.str("mime"),
                    )
                }
            }.getOrElse {
                DebugLog.error(TAG, "language catalogue failed", it)
                emptyList()
            }
        }

    suspend fun languageFor(path: String): LanguageInfo = withContext(pythonDispatcher) {
        val fallback = LanguageInfo("text", "Plain text", ".txt", "edit", "text", "")
        if (!_status.value.ready) return@withContext fallback
        runCatching {
            val map = runtime.callAttr("language_for", path).asMap()
            LanguageInfo(
                id = map.str("id"),
                name = map.str("name"),
                extension = map.str("extension"),
                mode = map.str("mode"),
                highlight = map.str("highlight"),
                note = map.str("note"),
                extensions = map.str("extensions"),
            )
        }.getOrDefault(fallback)
    }

    /** Starter content for a new file, chosen by its name. */
    suspend fun templateFor(name: String): String = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext ""
        runCatching { runtime.callAttr("template_for", name).toString() }.getOrDefault("")
    }

    suspend fun runFile(path: String): String {
        if (!_status.value.ready) return "error"
        cancelledChannels.remove(CONSOLE_CHANNEL)
        queueFor(CONSOLE_CHANNEL).clear()
        _status.value = _status.value.copy(running = true)
        return try {
            withContext(pythonDispatcher) { runtime.callAttr("run_file", path).toString() }
        } catch (error: Throwable) {
            emit(OutputChunk.Stream.STDERR, "Internal error: ${error.message}\n")
            DebugLog.error(TAG, "run_file failed: $path", error)
            "error"
        } finally {
            _status.value = _status.value.copy(running = false, awaitingInput = false)
            refreshServerCount()
        }
    }

    /**
     * Asks the console's running code to stop.
     *
     * Never goes through [pythonDispatcher] — that thread is busy running the
     * user's code, so a queued call would never arrive.
     */
    fun requestStop() {
        cancelledChannels[CONSOLE_CHANNEL] = true
        queueFor(CONSOLE_CHANNEL).clear()
        // Harmless when no JavaScript is running, and the only thing that
        // works when some is.
        JsEngine.stop()
        if (!_status.value.ready) return
        DebugLog.info(TAG, "stop requested")
        controlExecutor.execute {
            runCatching { runtime.callAttr("request_stop") }
                .onFailure { DebugLog.warn(TAG, "stop request failed", it.stackTraceToString()) }
        }
    }

    /** Feeds a line to a waiting `input()` on the given channel. */
    fun submitInput(line: String, channel: String = CONSOLE_CHANNEL) {
        emit(OutputChunk.Stream.INPUT, line + "\n", channel)
        if (!queueFor(channel).offer(line + "\n")) {
            emit(OutputChunk.Stream.STDERR, "Input buffer is full; nothing is reading stdin.\n", channel)
        }
    }

    suspend fun resetNamespace() = withContext(pythonDispatcher) {
        runCatching { runtime.callAttr("reset_namespace") }
            .onFailure { DebugLog.error(TAG, "namespace reset failed", it) }
        emit(OutputChunk.Stream.SYSTEM, "Namespace cleared.\n")
        DebugLog.info(TAG, "namespace cleared")
    }

    suspend fun completions(prefix: String): List<String> = withContext(pythonDispatcher) {
        if (!_status.value.ready || prefix.isBlank()) return@withContext emptyList()
        runCatching {
            runtime.callAttr("completions", prefix).asList().map { it.toString() }
        }.getOrDefault(emptyList())
    }

    suspend fun runtimeInfo(): Map<String, String> = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext emptyMap()
        runCatching {
            val info = runtime.callAttr("runtime_info").asMap()
            info.entries.associate { (key, value) -> key.toString() to value.toString() }
        }.getOrDefault(emptyMap())
    }

    // ------------------------------------------------------------------
    // Packages
    // ------------------------------------------------------------------

    suspend fun installPackage(name: String, version: String?, onProgress: (String) -> Unit): PackageResult =
        withContext(pythonDispatcher) {
            if (!_status.value.ready) return@withContext PackageResult(false, error = "Interpreter is not ready.")
            DebugLog.info(TAG, "installing $name${version?.let { "==$it" } ?: ""}")
            runCatching {
                val result = packages.callAttr(
                    "install",
                    name,
                    version?.takeIf { it.isNotBlank() },
                    ProgressSink(onProgress),
                ).asMap()
                result.toPackageResult()
            }.getOrElse {
                DebugLog.error(TAG, "install of $name failed", it)
                PackageResult(false, error = it.friendlyMessage())
            }.also {
                if (!it.ok) DebugLog.warn(TAG, "install of $name failed: ${it.error}")
            }
        }

    suspend fun uninstallPackage(name: String): PackageResult = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext PackageResult(false, error = "Interpreter is not ready.")
        runCatching { packages.callAttr("uninstall", name).asMap().toPackageResult() }
            .getOrElse {
                DebugLog.error(TAG, "uninstall of $name failed", it)
                PackageResult(false, error = it.friendlyMessage())
            }
    }

    suspend fun installedPackages(): List<InstalledPackage> = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext emptyList()
        runCatching {
            packages.callAttr("installed").asList().map { row ->
                val map = row.asMap()
                InstalledPackage(
                    name = map.str("name"),
                    version = map.str("version"),
                    summary = map.str("summary"),
                    fileCount = map.str("files").toIntOrNull() ?: 0,
                )
            }
        }.getOrDefault(emptyList())
    }

    suspend fun bundledPackages(): List<String> = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext emptyList()
        runCatching { packages.callAttr("bundled").asList().map { it.toString() } }
            .getOrDefault(emptyList())
    }

    // ------------------------------------------------------------------
    // Downloads
    // ------------------------------------------------------------------

    suspend fun downloadUrl(url: String, onProgress: (String) -> Unit): DownloadResult =
        withContext(controlDispatcher) {
            if (!_status.value.ready) return@withContext DownloadResult(false, error = "Interpreter is not ready.")
            DebugLog.info(TAG, "downloading $url")
            runCatching {
                val map = downloads.callAttr("download", url, ProgressSink(onProgress)).asMap()
                DownloadResult(
                    ok = map.str("ok") == "True",
                    name = map.str("name"),
                    path = map.str("path"),
                    bytes = map.str("bytes").toLongOrNull() ?: 0L,
                    error = map.str("error"),
                )
            }.getOrElse {
                DebugLog.error(TAG, "download failed", it)
                DownloadResult(false, error = it.friendlyMessage())
            }
        }.also { if (!it.ok) DebugLog.warn(TAG, "download failed: ${it.error}") }

    /** Whether Downloads already holds a file of that name. */
    suspend fun downloadsHas(name: String): Boolean = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext false
        runCatching { downloads.callAttr("has", name).toBoolean() }.getOrDefault(false)
    }

    /**
     * Puts a file the app has already copied off the phone into Downloads.
     *
     * The copy out of the content URI is Kotlin's job - only Kotlin can read
     * one - and this gives it a home and a name that will not collide.
     */
    suspend fun adoptDownload(path: String, name: String, replace: Boolean): DownloadResult =
        withContext(controlDispatcher) {
            if (!_status.value.ready) {
                return@withContext DownloadResult(false, error = "Interpreter is not ready.")
            }
            runCatching {
                downloads.callAttr("adopt", path, name, if (replace) "1" else "")
                    .asMap()
                    .let { map ->
                        DownloadResult(
                            ok = map.str("ok") == "True",
                            name = map.str("name"),
                            path = map.str("path"),
                            bytes = map.str("bytes").toLongOrNull() ?: 0L,
                            error = map.str("error"),
                        )
                    }
            }.getOrElse {
                DebugLog.error(TAG, "could not add $name to downloads", it)
                DownloadResult(false, error = it.friendlyMessage())
            }
        }

    suspend fun exportWorkspace(): DownloadResult = exportZip(null)

    /** Zips one folder of the workspace, or the whole thing when [folder] is null. */
    suspend fun exportZip(folder: String?): DownloadResult = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext DownloadResult(false, error = "Interpreter is not ready.")
        runCatching {
            val map = if (folder == null) {
                downloads.callAttr("export_workspace", "").asMap()
            } else {
                downloads.callAttr("export_folder", folder, "").asMap()
            }
            DownloadResult(
                ok = map.str("ok") == "True",
                name = map.str("name"),
                path = map.str("path"),
                bytes = map.str("bytes").toLongOrNull() ?: 0L,
                files = map.str("files").toIntOrNull() ?: 0,
                error = map.str("error"),
            )
        }.getOrElse {
            DebugLog.error(TAG, "export failed", it)
            DownloadResult(false, error = it.friendlyMessage())
        }
    }


    /**
     * Runs a `.js` file as a server, on the server's own thread.
     *
     * Registered into `pycmd_servers` at startup so that a JavaScript file is
     * a first-class thing to launch from the Servers tab, rather than the one
     * runnable language the tab could not start. Python cannot run it - the
     * engine is a WebView - so Python calls back out here instead.
     *
     * The thread it runs on is blocked for the whole run, which is what makes
     * the server's lifetime honest. A kill marks the channel cancelled, and
     * this notices within a tick and tears the engine down: a `while (true)`
     * in JavaScript cannot be interrupted any other way.
     */
    @Suppress("unused") // Called from pycmd_servers.py
    private val jsFileRunner = object {
        fun run(path: String, channel: String) {
            val file = File(path)
            val source = file.readText()
            cancelledChannels.remove(channel)
            queueFor(channel).clear()

            val host = object : JsEngine.Host {
                override fun stdout(text: String) = emit(OutputChunk.Stream.STDOUT, text, channel)
                override fun stderr(text: String) {
                    emit(OutputChunk.Stream.STDERR, text, channel)
                    bufferStderr(channel, text)
                }
                override fun readLine(): String? = readLineFor(channel)
            }

            val result = runBlocking {
                val run = async { JsEngine.run(appContext, source, file.name, host) }
                val watcher = launch {
                    while (isActive) {
                        if (cancelledChannels.containsKey(channel)) {
                            JsEngine.stop()
                            return@launch
                        }
                        delay(120)
                    }
                }
                try {
                    run.await()
                } finally {
                    watcher.cancel()
                }
            }

            if (result.status == "error") {
                throw RuntimeException("JavaScript exited with status ${result.exitCode}")
            }
        }
    }

    /**
     * What a custom plugin reaches when it logs, toasts, or messages its panel.
     *
     * Called from whichever thread the plugin happens to be on, so it does the
     * same thing the output sink does: hand the value to a flow and get out.
     */
    @Suppress("unused") // Called from pycmd_plugins.py
    private val pluginHost = object {
        fun onPluginLog(level: String, message: String, detail: String) {
            when (level) {
                "error" -> DebugLog.error(TAG_PLUGIN, message, detail)
                "warn" -> DebugLog.warn(TAG_PLUGIN, message, detail)
                else -> DebugLog.info(TAG_PLUGIN, message, detail)
            }
        }

        fun onToast(message: String) {
            _pluginToasts.tryEmit(message)
        }

        fun onPluginMessage(pluginId: String, body: String) {
            _pluginMessages.tryEmit(pluginId to body)
        }

        /**
         * A plugin asking the app to do something - open a file, run one,
         * switch screens.
         *
         * A request rather than a call: the plugin is on whatever thread it
         * happens to be on, and every one of these has to happen on the app's
         * own. Handing it to a flow and returning is the whole contract, which
         * is also why a plugin cannot wait on the result.
         */
        fun onPluginAction(pluginId: String, action: String, detail: String) {
            _pluginActions.tryEmit(PluginAction(pluginId, action, detail))
        }
    }

    private val _pluginActions = MutableSharedFlow<PluginAction>(
        extraBufferCapacity = 32, onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    /** Things plugins have asked the app to do. */
    val pluginActions: SharedFlow<PluginAction> = _pluginActions.asSharedFlow()

    private val _pluginToasts = MutableSharedFlow<String>(extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST)

    /** Toasts a plugin asked for. */
    val pluginToasts: SharedFlow<String> = _pluginToasts.asSharedFlow()

    private val _pluginMessages = MutableSharedFlow<Pair<String, String>>(
        extraBufferCapacity = 64, onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    /** Messages a plugin pushed to its own panel. */
    val pluginMessages: SharedFlow<Pair<String, String>> = _pluginMessages.asSharedFlow()

    /**
     * Installs a plugin from a file, folder or zip already on disk.
     *
     * Everything about custom plugins runs on the control dispatcher: a plugin
     * that hangs on load must not take the console's thread with it, and the
     * user needs the list to keep answering so they can switch the thing off.
     */
    suspend fun installPlugin(
        path: String,
        sourceName: String = "",
        bundled: Boolean = false,
    ): JSONObject = pluginCall("install", path, sourceName, if (bundled) "1" else "")

    suspend fun listPlugins(): JSONObject = pluginCall("listing")

    suspend fun removePlugin(id: String): JSONObject = pluginCall("remove", id)

    suspend fun loadPlugins(enabled: Collection<String>): JSONObject =
        // On the plugin thread with everything else that touches a plugin
        // folder. Loading imports a module out of that folder and installing
        // replaces it; on two different threads they can happen at once, and
        // then a plugin is imported while its own files are being moved out
        // from under it.
        withContext(pluginDispatcher) {
            runCatching {
                // Sent as one string rather than a collection: Chaquopy hands
                // Kotlin's EmptyList across as an object Python cannot iterate,
                // and a comma-separated list has no such corner.
                val ids = enabled.joinToString(",")
                JSONObject(pluginRuntime.callAttr("load_all", ids).toString())
            }.getOrElse { failure("load_all", it) }
        }

    suspend fun callPluginExport(id: String, name: String, payload: String): JSONObject =
        pluginCall("call_export", id, name, payload)

    suspend fun pluginCommands(): JSONObject = pluginCall("commands")

    /** The text of one of a plugin's own guides. */
    suspend fun pluginGuide(id: String, file: String): JSONObject =
        pluginCall("guide_text", id, file)

    /** What a plugin declared as settings, with whatever the user has chosen. */
    suspend fun pluginSettings(id: String): JSONObject = pluginCall("plugin_settings", id)

    /** Saves one setting. The value is typed on the Python side, where the
     * manifest that says what type it is lives. */
    suspend fun setPluginSetting(id: String, name: String, value: String): JSONObject =
        pluginCall("set_plugin_setting", id, name, value)

    suspend fun runPluginCommand(name: String, argument: String): JSONObject =
        withContext(pythonDispatcher) {
            // This one does go on the interpreter thread: a command prints to
            // the console and may touch the same namespace a script does.
            runCatching {
                JSONObject(pluginRuntime.callAttr("run_command", name, argument).toString())
            }.getOrElse { failure("run_command", it) }
        }

    suspend fun firePluginEvent(event: String, payload: String = "{}"): JSONObject =
        pluginCall("fire", event, payload)

    /** Where a plugin's files live, so its panel can load its own assets. */
    fun pluginDirectory(id: String): File = File(pluginsDir, id)

    suspend fun pluginPanel(id: String, panelFile: String = ""): String =
        withContext(pluginDispatcher) {
        runCatching { pluginRuntime.callAttr("panel_html", id, panelFile).toString() }
            .getOrElse { error ->
                DebugLog.error(TAG_PLUGIN, "panel failed for $id", error)
                "<h2>That panel could not be built.</h2>"
            }
    }

    private suspend fun pluginCall(function: String, vararg arguments: String): JSONObject =
        withContext(pluginDispatcher) {
            if (!_status.value.ready) {
                return@withContext JSONObject()
                    .put("ok", false)
                    .put("error", "the interpreter is not ready yet")
            }
            runCatching {
                val reply = when (arguments.size) {
                    0 -> pluginRuntime.callAttr(function)
                    1 -> pluginRuntime.callAttr(function, arguments[0])
                    2 -> pluginRuntime.callAttr(function, arguments[0], arguments[1])
                    else -> pluginRuntime.callAttr(
                        function, arguments[0], arguments[1], arguments[2],
                    )
                }
                JSONObject(reply.toString())
            }.getOrElse { failure(function, it) }
        }

    private fun failure(what: String, error: Throwable): JSONObject {
        DebugLog.error(TAG_PLUGIN, "plugin call failed: $what", error)
        return JSONObject()
            .put("ok", false)
            .put("error", error.message ?: error.javaClass.simpleName)
    }

    /**
     * Runs one of the plugin tools.
     *
     * These go through the control dispatcher rather than the interpreter
     * thread: formatting a bit of JSON or sending an HTTP request has nothing
     * to do with the script that is running, and should not have to wait for
     * it to finish - least of all when that script is stuck.
     */
    suspend fun tool(name: String, arguments: JSONObject): JSONObject =
        withContext(controlDispatcher) {
            if (!_status.value.ready) {
                return@withContext JSONObject()
                    .put("ok", false)
                    .put("error", "the interpreter is not ready yet")
            }
            try {
                val reply = tools.callAttr("invoke", name, arguments.toString()).toString()
                JSONObject(reply)
            } catch (error: Throwable) {
                DebugLog.error(TAG, "tool $name failed", error)
                JSONObject()
                    .put("ok", false)
                    .put("error", error.message ?: error.javaClass.simpleName)
            }
        }

    suspend fun listDownloads(): List<DownloadedFile> = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext emptyList()
        runCatching {
            downloads.callAttr("listing").asList().map { row ->
                val map = row.asMap()
                DownloadedFile(
                    name = map.str("name"),
                    path = map.str("path"),
                    bytes = map.str("bytes").toLongOrNull() ?: 0L,
                    modifiedSeconds = map.str("modified").toLongOrNull() ?: 0L,
                )
            }
        }.getOrDefault(emptyList())
    }

    suspend fun deleteDownload(path: String): Boolean = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext false
        runCatching { downloads.callAttr("delete", path).asMap().str("ok") == "True" }
            .getOrDefault(false)
    }

    suspend fun copyDownloadToWorkspace(path: String): DownloadResult =
        withContext(controlDispatcher) {
            if (!_status.value.ready) return@withContext DownloadResult(false, error = "Interpreter is not ready.")
            runCatching {
                val map = downloads.callAttr("copy_to_workspace", path).asMap()
                DownloadResult(
                    ok = map.str("ok") == "True",
                    name = map.str("name"),
                    path = map.str("path"),
                    error = map.str("error"),
                )
            }.getOrElse { DownloadResult(false, error = it.friendlyMessage()) }
        }

    // ------------------------------------------------------------------
    // Servers
    // ------------------------------------------------------------------

    suspend fun startStaticServer(
        directory: String,
        port: Int,
        host: String,
        label: String,
        logRequests: Boolean,
    ): ServerActionResult = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext ServerActionResult(false, "Interpreter is not ready.")
        DebugLog.info(TAG, "starting static server on $host:$port", directory)
        runCatching {
            servers.callAttr("start_static", directory, port, host, label, logRequests)
                .asMap().toServerActionResult()
        }.getOrElse {
            DebugLog.error(TAG, "static server failed to start", it)
            ServerActionResult(false, it.friendlyMessage())
        }
    }.also { logServerResult("static", it); refreshServerCount() }

    /**
     * Starts whatever kind of file this is as a server.
     *
     * A script, a C or Go or Rust program, a JavaScript file, a page whose
     * folder gets served, or a type a plugin taught the app about - the choice
     * is Python's, which is where the language registry and the plugin runners
     * both live.
     */
    suspend fun startFileServer(
        path: String,
        port: Int,
        host: String,
        label: String,
    ): ServerActionResult = withContext(pythonDispatcher) {
        if (!_status.value.ready) return@withContext ServerActionResult(false, "Interpreter is not ready.")
        DebugLog.info(TAG, "starting a server on port $port", path)
        runCatching {
            servers.callAttr("start_file", path, port, host, label)
                .asMap().toServerActionResult()
        }.getOrElse {
            DebugLog.error(TAG, "server failed to start", it)
            ServerActionResult(false, it.friendlyMessage())
        }
    }.also { logServerResult("file", it); refreshServerCount() }

    /** What starting this file would do, so the launcher can say so up front. */
    suspend fun howToRun(path: String): RunPlan = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext RunPlan()
        runCatching {
            val map = servers.callAttr("how_to_run", path).asMap()
            RunPlan(map.str("how"), map.str("language"), map.str("note"), map.str("entry"))
        }.getOrDefault(RunPlan())
    }

    private fun logServerResult(kind: String, result: ServerActionResult) {
        if (result.ok) {
            DebugLog.info(TAG, "$kind server ${result.handle} started", result.url)
        } else {
            DebugLog.warn(TAG, "$kind server refused to start", result.error)
        }
    }

    /** Graceful stop. Runs off the main Python thread so it works while it is busy. */
    suspend fun stopServer(handle: String): ServerActionResult = withContext(rescueDispatcher) {
        if (!_status.value.ready) return@withContext ServerActionResult(false, "Interpreter is not ready.")
        DebugLog.info(TAG, "stopping server $handle")
        runCatching {
            val map = servers.callAttr("stop", handle).asMap()
            ServerActionResult(
                ok = map.str("ok") == "True",
                error = map.str("error"),
                needsKill = map.str("needs_kill") == "True",
            )
        }.getOrElse {
            DebugLog.error(TAG, "stop of $handle failed", it)
            ServerActionResult(false, it.friendlyMessage())
        }
    }.also { refreshServerCount() }

    /**
     * The kill switch.
     *
     * Frees the port, raises SystemExit inside the server's thread, and stops
     * tracking it either way, so a thread wedged in a blocking call can never
     * hold the UI or the port hostage.
     */
    suspend fun killServer(handle: String): ServerActionResult = withContext(rescueDispatcher) {
        if (!_status.value.ready) return@withContext ServerActionResult(false, "Interpreter is not ready.")
        DebugLog.warn(TAG, "killing server $handle")
        cancelledChannels[handle] = true
        runCatching {
            val map = servers.callAttr("kill", handle).asMap()
            ServerActionResult(
                ok = map.str("ok") == "True",
                error = map.str("error"),
                detached = map.str("detached") == "True",
            )
        }.getOrElse {
            DebugLog.error(TAG, "kill of $handle failed", it)
            ServerActionResult(false, it.friendlyMessage())
        }
    }.also { refreshServerCount() }

    suspend fun stopAllServers(): Int = withContext(rescueDispatcher) {
        if (!_status.value.ready) return@withContext 0
        runCatching { servers.callAttr("stop_all").asMap().str("stopped").toIntOrNull() ?: 0 }
            .getOrElse {
                DebugLog.error(TAG, "stop_all failed", it)
                0
            }
    }.also { refreshServerCount() }

    /** Panic button: force every server down regardless of state. */
    suspend fun killAllServers(): Int = withContext(rescueDispatcher) {
        if (!_status.value.ready) return@withContext 0
        DebugLog.warn(TAG, "killing every server")
        cancelledChannels.clear()
        runCatching { servers.callAttr("kill_all").asMap().str("killed").toIntOrNull() ?: 0 }
            .getOrElse {
                DebugLog.error(TAG, "kill_all failed", it)
                0
            }
    }.also { refreshServerCount() }

    suspend fun listServers(): List<RunningServer> = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext emptyList()
        runCatching {
            servers.callAttr("listing").asList().map { row ->
                val map = row.asMap()
                RunningServer(
                    handle = map.str("handle"),
                    label = map.str("label"),
                    kind = map.str("kind"),
                    port = map.str("port").toIntOrNull() ?: 0,
                    host = map.str("host"),
                    status = map.str("status"),
                    url = map.str("url"),
                    error = map.str("error"),
                    target = map.str("target"),
                    uptimeSeconds = map.str("uptime").toIntOrNull() ?: 0,
                    requests = map.str("requests").toIntOrNull() ?: 0,
                )
            }
        }.getOrElse {
            DebugLog.error(TAG, "server listing failed", it)
            emptyList()
        }
    }

    /** Replays a server's own log, so reopening its console is not blank. */
    suspend fun serverLog(handle: String): List<OutputChunk> = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext emptyList()
        runCatching {
            servers.callAttr("log_lines", handle).asList().map { row ->
                val map = row.asMap()
                val stream = when (map.str("stream")) {
                    "stderr" -> OutputChunk.Stream.STDERR
                    "system" -> OutputChunk.Stream.SYSTEM
                    else -> OutputChunk.Stream.STDOUT
                }
                OutputChunk(stream, map.str("text"), chunkId.incrementAndGet(), handle)
            }
        }.getOrDefault(emptyList())
    }

    suspend fun suggestPort(from: Int): Int = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext from
        runCatching { servers.callAttr("suggest_port", from).toInt() }.getOrDefault(from)
    }

    suspend fun localIp(): String = withContext(controlDispatcher) {
        if (!_status.value.ready) return@withContext "127.0.0.1"
        runCatching { servers.callAttr("local_ip").toString() }.getOrDefault("127.0.0.1")
    }

    /** Queues the refresh onto a control thread; never blocks the caller. */
    private fun refreshServerCount() {
        if (!_status.value.ready) return
        controlExecutor.execute {
            runCatching { _serverCount.value = servers.callAttr("count").toInt() }
        }
    }
}

/** What the app knows about a file type. */
/**
 * The language whose extensions include [name]'s.
 *
 * Lives here rather than in the view model so that a composable can match on
 * the catalogue it already collects: matching through the view model reads a
 * flow's value without subscribing to it, and the row then never notices when
 * the catalogue finally arrives.
 */
/**
 * The catalogue as an extension lookup, built once.
 *
 * [forFileName] splits every language's extension list on every call, which is
 * nothing once and a great deal per row: the file list asks for one language
 * per file, and Compose redraws rows as they scroll. Two hundred files times
 * thirty-odd languages is seven thousand string splits to answer a question
 * whose answer cannot change until the catalogue does.
 *
 * First registration wins, matching [forFileName]: `.svg` is XML because XML
 * claims it first, not an image.
 */
fun List<LanguageInfo>.byExtension(): Map<String, LanguageInfo> {
    val index = HashMap<String, LanguageInfo>(size * 3)
    for (info in this) {
        for (raw in info.extensions.split(",")) {
            val key = raw.trim().removePrefix(".").lowercase()
            if (key.isNotEmpty() && !index.containsKey(key)) index[key] = info
        }
    }
    return index
}

fun List<LanguageInfo>.forFileName(name: String): LanguageInfo? {
    val extension = name.substringAfterLast('.', "").lowercase()
    if (extension.isEmpty()) return null
    return firstOrNull { info ->
        info.extensions.split(",").any { it.trim().removePrefix(".") == extension }
    }
}

/**
 * A page ready to show.
 *
 * When [served] is true the page is coming off a loopback HTTP server rooted
 * at its own folder, which is the only way a preview behaves like a browser:
 * modules load, fetch works, relative paths resolve, and a link to the next
 * page of the site actually goes there. [html] is kept as the fallback for
 * the rare case where no socket could be opened.
 */
data class PreviewPage(
    val name: String,
    val html: String,
    val baseDirectory: String,
    val url: String = "",
    val served: Boolean = false,
) {
    /** The origin the preview is allowed to navigate inside. */
    val origin: String get() = url.substringBefore("/", "").let {
        if (url.startsWith("http")) url.split("/").take(3).joinToString("/") else ""
    }
}

data class LanguageInfo(
    val id: String,
    val name: String,
    val extension: String,
    /** "run", "preview", "edit" or "media". */
    val mode: String,
    val highlight: String,
    val note: String,
    /** Every extension this language claims, comma separated. */
    val extensions: String = extension,
    /** What the file picker should offer when importing one. Media only. */
    val mime: String = "",
) {
    val canRun: Boolean get() = mode == "run"
    val canPreview: Boolean get() = mode == "preview"

    /**
     * Whether a new one can be written from a template.
     *
     * False for media: an empty .mp3 is not a file anybody wanted, so picking
     * one in the new-file menu brings a real one in from the phone instead.
     */
    val creatable: Boolean get() = mode != "media"
}

data class DownloadResult(
    val ok: Boolean,
    val name: String = "",
    val path: String = "",
    val bytes: Long = 0L,
    val files: Int = 0,
    val error: String = "",
)

data class DownloadedFile(
    val name: String,
    val path: String,
    val bytes: Long,
    val modifiedSeconds: Long,
) {
    val readableSize: String
        get() = when {
            bytes < 1024 -> "$bytes B"
            bytes < 1024 * 1024 -> "%.1f KB".format(java.util.Locale.US, bytes / 1024.0)
            else -> "%.1f MB".format(java.util.Locale.US, bytes / (1024.0 * 1024.0))
        }
}

data class PackageResult(
    val ok: Boolean,
    val name: String = "",
    val version: String = "",
    val error: String = "",
)

data class InstalledPackage(
    val name: String,
    val version: String,
    val summary: String,
    val fileCount: Int,
)

data class RunningServer(
    val handle: String,
    val label: String,
    val kind: String,
    val port: Int,
    val host: String,
    val status: String,
    val url: String,
    val error: String,
    val target: String,
    val uptimeSeconds: Int,
    val requests: Int,
) {
    val isRunning: Boolean get() = status == "running"

    val readableUptime: String
        get() = when {
            uptimeSeconds < 60 -> "${uptimeSeconds}s"
            uptimeSeconds < 3600 -> "${uptimeSeconds / 60}m ${uptimeSeconds % 60}s"
            else -> "${uptimeSeconds / 3600}h ${(uptimeSeconds % 3600) / 60}m"
        }
}

data class ServerActionResult(
    val ok: Boolean,
    val error: String = "",
    val url: String = "",
    val handle: String = "",
    val needsKill: Boolean = false,
    val detached: Boolean = false,
)

/**
 * What starting a given file as a server would actually do.
 *
 * `how` is one of `script`, `language`, `javascript`, `serve`, `plugin`,
 * `unsupported` or `unknown`. The launcher shows [note] before anything runs,
 * so a page that is about to be served rather than executed says so first.
 */
/** Something a plugin asked the app to do, with its JSON detail. */
data class PluginAction(val pluginId: String, val action: String, val detail: String)

data class RunPlan(
    val how: String = "",
    val language: String = "",
    val note: String = "",
    /** For a folder: the file inside it that Run would start. Empty otherwise. */
    val entry: String = "",
) {
    val runnable: Boolean get() = how.isNotEmpty() && how != "unsupported" && how != "unknown"
}

/** Chaquopy maps are `Map<PyObject, PyObject>`; missing keys must read as empty. */
private fun Map<PyObject, PyObject>.str(key: String): String =
    entries.firstOrNull { it.key.toString() == key }?.value?.toString().orEmpty()

private fun Map<PyObject, PyObject>.toPackageResult(): PackageResult =
    PackageResult(
        ok = str("ok") == "True",
        name = str("name"),
        version = str("version"),
        error = str("error"),
    )

private fun Map<PyObject, PyObject>.toServerActionResult(): ServerActionResult =
    ServerActionResult(
        ok = str("ok") == "True",
        error = str("error"),
        url = str("url"),
        handle = str("handle"),
    )

/** Chaquopy wraps Python exceptions; the raw message is long and noisy. */
private fun Throwable.friendlyMessage(): String {
    val raw = message ?: javaClass.simpleName
    return raw.lineSequence().firstOrNull { it.isNotBlank() } ?: raw
}
