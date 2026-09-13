package com.expstudio.pycmd.ui

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.core.content.edit
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.expstudio.pycmd.python.CONSOLE_CHANNEL
import com.expstudio.pycmd.python.EngineStatus
import com.expstudio.pycmd.python.DownloadedFile
import com.expstudio.pycmd.python.InstalledPackage
import com.expstudio.pycmd.python.LanguageInfo
import com.expstudio.pycmd.python.OutputChunk
import com.expstudio.pycmd.python.PreviewPage
import com.expstudio.pycmd.python.forFileName
import com.expstudio.pycmd.python.PluginAction
import com.expstudio.pycmd.python.PythonEngine
import com.expstudio.pycmd.python.RunPlan
import com.expstudio.pycmd.python.RunningServer
import com.expstudio.pycmd.python.ServerService
import com.expstudio.pycmd.music.MixerHub
import com.expstudio.pycmd.music.MusicHub
import com.expstudio.pycmd.music.Neighbours
import com.expstudio.pycmd.music.MusicImport
import com.expstudio.pycmd.music.MusicTrack
import com.expstudio.pycmd.music.Playback
import com.expstudio.pycmd.plugins.CustomPlugins
import com.expstudio.pycmd.plugins.InstalledPlugin
import com.expstudio.pycmd.plugins.PluginExtension
import com.expstudio.pycmd.plugins.PluginFileAction
import com.expstudio.pycmd.plugins.PluginGuide
import com.expstudio.pycmd.plugins.PluginIds
import com.expstudio.pycmd.plugins.PluginScreen
import com.expstudio.pycmd.plugins.PluginSpec
import com.expstudio.pycmd.plugins.Plugins
import com.expstudio.pycmd.BuildConfig
import com.expstudio.pycmd.util.DebugLog
import com.expstudio.pycmd.util.LogEntry
import com.expstudio.pycmd.util.Exports
import com.expstudio.pycmd.util.Imports
import com.expstudio.pycmd.util.KeptVersion
import com.expstudio.pycmd.util.UpdateState
import com.expstudio.pycmd.util.UpdateWorker
import com.expstudio.pycmd.util.Updater
import com.expstudio.pycmd.util.Workspace
import com.expstudio.pycmd.util.WorkspaceEntry
import java.io.File
import java.io.IOException
import org.json.JSONArray
import org.json.JSONObject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Which screen is showing.
 *
 * Only the first five are in the bottom bar - seven destinations wrap their
 * labels onto two lines on a phone - so Packages, Downloads and Plugins live
 * behind More, and Debug stays in the top bar where it is reachable from
 * anywhere.
 */
enum class Tab(val label: String) {
    CONSOLE("Console"),
    EDITOR("Editor"),
    FILES("Files"),
    SERVERS("Servers"),
    MORE("More"),
    PACKAGES("Packages"),
    DOWNLOADS("Downloads"),
    PLUGINS("Plugins"),
    DEBUG("Debug"),
    TOOL("Tool"),
    PLUGIN_PANEL("Plugin"),
    DOCS("Guides"),
    PAGES("Pages"),
    MUSIC("Music"),
    SYSTEM("System");

    /**
     * What a plugin manifest calls this screen, or null if it cannot be
     * extended. Kept as its own name rather than the enum's so that renaming
     * a tab in the app never breaks a plugin that was written against it.
     */
    val extensionName: String?
        get() = when (this) {
            FILES -> "files"
            SERVERS -> "servers"
            PACKAGES -> "packages"
            DOWNLOADS -> "downloads"
            PLUGINS -> "plugins"
            SYSTEM -> "system"
            DEBUG -> "debug"
            DOCS -> "guides"
            PAGES -> "pages"
            MUSIC -> "music"
            // The console and the editor are a full-screen WebView each, with
            // nowhere to put a card that would not be in the way.
            CONSOLE, EDITOR, MORE, TOOL, PLUGIN_PANEL -> null
        }
}

/** The five destinations in the bottom bar; the rest live behind More. */
val BOTTOM_TABS = listOf(Tab.CONSOLE, Tab.EDITOR, Tab.FILES, Tab.SERVERS, Tab.MORE)

data class DownloadsState(
    val files: List<DownloadedFile> = emptyList(),
    val busy: Boolean = false,
    val progress: String = "",
)

/** What a launch form is set up to start. */
/** What to do about an import whose name is already taken. */
enum class ImportChoice { REPLACE, KEEP_BOTH, CANCEL }

/**
 * An import waiting on that answer.
 *
 * [decide] carries on with whichever the user picked; nothing has been written
 * yet when this exists, except a folder already staged in the cache.
 */
data class PendingImport(
    val name: String,
    val isFolder: Boolean,
    val existing: File,
    val decide: (ImportChoice) -> Unit,
)

enum class ServerKind(val label: String) {
    STATIC("Serve a folder"),
    SCRIPT("Run a file"),
}

/**
 * The Servers tab's launch form.
 *
 * Held in the ViewModel rather than the composable so a half-filled form
 * survives a trip to the Files tab to pick a target.
 */
data class LaunchForm(
    val kind: ServerKind = ServerKind.STATIC,
    val folder: File? = null,
    val script: File? = null,
    val port: String = "8000",
    val label: String = "",
    val exposeToNetwork: Boolean = true,
    val logRequests: Boolean = true,
    /** What starting the picked file would do, looked up before it is started. */
    val plan: RunPlan = RunPlan(),
) {
    val target: File? get() = if (kind == ServerKind.STATIC) folder else script

    val portNumber: Int? get() = port.trim().toIntOrNull()

    /** Why the Run button is disabled, or null when it is ready to go. */
    fun problem(): String? = when {
        target == null -> if (kind == ServerKind.STATIC) "Pick a folder to serve." else "Pick a file or folder."
        kind == ServerKind.SCRIPT && plan.how.isNotEmpty() && !plan.runnable -> plan.note
        port.isNotBlank() && portNumber == null -> "Port must be a number."
        portNumber != null && portNumber !in 1..65535 -> "Port must be between 1 and 65535."
        kind == ServerKind.STATIC && portNumber == null -> "A folder server needs a port."
        else -> null
    }
}

data class EditorState(
    val file: File? = null,
    val content: String = DEFAULT_SNIPPET,
    val savedContent: String = DEFAULT_SNIPPET,
    val line: Int = 1,
    val column: Int = 1,
    /**
     * Bumped whenever a different document is loaded. The editor WebView keys
     * off this to know when to replace its buffer - the file path alone cannot
     * tell "new untitled" from "still untitled".
     */
    val epoch: Long = 0,
) {
    val fileName: String get() = file?.name ?: "untitled.py"
    val isDirty: Boolean get() = content != savedContent
}

data class FilesState(
    val directory: File? = null,
    val entries: List<WorkspaceEntry> = emptyList(),
    val loading: Boolean = true,
)

/** One project in the Pages tab. */
data class PageProject(
    val id: String,
    val name: String,
    val folder: String,
    val template: String,
    val port: Int,
    val running: Boolean,
    val url: String,
    val publicUrl: String,
    val requests: Int,
    val files: Int,
    val bytes: Long,
    val host: String,
    val deployedUrl: String,
    val exists: Boolean,
) {
    /** Where it is hosted, said the way the card says it. */
    val onCloudflare: Boolean get() = host == "cloudflare"
}

/** What a new page can start as. */
data class PageTemplate(val id: String, val title: String, val about: String)

/**
 * A workspace folder a page could point at.
 *
 * [taken] is why this is a type rather than a string: offering a folder that
 * is already a page, and then refusing it after the tap, is worse than saying
 * so on the row.
 */
data class WorkspaceFolder(
    val path: String,
    val name: String,
    val relative: String,
    val files: Int,
    val bytes: Long,
    val taken: Boolean,
)

/** Whether a Cloudflare account is connected, and which. */
data class CloudflareState(
    val connected: Boolean = false,
    val account: String = "",
    val tokenTail: String = "",
    val busy: String = "",
)

data class PagesState(
    val projects: List<PageProject> = emptyList(),
    val templates: List<PageTemplate> = emptyList(),
    /** Workspace folders the picker offers, refreshed with the tab. */
    val folders: List<WorkspaceFolder> = emptyList(),
    val used: Int = 0,
    val maxProjects: Int = 70,
    val active: Int = 0,
    val maxActive: Int = 25,
    val busy: String = "",
    val cloudflare: CloudflareState = CloudflareState(),
) {
    val full: Boolean get() = used >= maxProjects
    val atRunningLimit: Boolean get() = active >= maxActive
}

/** A playlist as the Music tab draws it: the order, and what is in it. */
data class MusicPlaylist(
    val id: String,
    val name: String,
    val trackIds: List<String> = emptyList(),
    val count: Int = 0,
    val duration: Long = 0,
    val bytes: Long = 0,
    val preview: String = "",
)

/**
 * The music library, and which part of it the screen is looking at.
 *
 * What is *playing* is not in here: that lives in the media session, which
 * outlives this view model and every screen it draws, and comes back through
 * [MainViewModel.playback].
 */
/** One of the smart lists - recently added, most played - and how many it holds. */
data class MusicCollection(val id: String, val name: String, val count: Int)

/** The numbers the statistics card shows. */
data class MusicNumbers(
    val tracks: Int = 0,
    val playlists: Int = 0,
    val bytes: Long = 0,
    val duration: Long = 0,
    val plays: Int = 0,
    val artists: Int = 0,
    val topArtist: String = "",
    val videos: Int = 0,
    val neverPlayed: Int = 0,
)

data class MusicState(
    val tracks: List<MusicTrack> = emptyList(),
    val playlists: List<MusicPlaylist> = emptyList(),
    val openPlaylist: String = "",
    val bytes: Long = 0,
    val missing: Int = 0,
    val maxTracks: Int = 2000,
    val maxPlaylists: Int = 200,
    val busy: String = "",
    val importing: Boolean = false,
    // What the list is narrowed to. Searching and sorting are done in Python
    // rather than here, so that the order the screen shows and the order the
    // player is handed are worked out by the same code - a list sorted one
    // way and played another is the oldest bug in music players.
    val search: String = "",
    val sort: String = "added",
    val collection: String = "",
    val shown: List<MusicTrack> = emptyList(),
    val collections: List<MusicCollection> = emptyList(),
    val numbers: MusicNumbers = MusicNumbers(),
    val speed: Double = 1.0,
    val sleepMinutes: Int = 0,
    val detail: MusicTrack? = null,
    val detailPlaylists: List<String> = emptyList(),
) {
    /** The playlist the screen has open, or null when it is showing everything. */
    val current: MusicPlaylist? get() = playlists.firstOrNull { it.id == openPlaylist }

    /** True when something is narrowing the list. */
    val filtered: Boolean get() = search.isNotBlank() || collection.isNotEmpty()

    /**
     * What the list shows.
     *
     * `shown` is Python's answer - searched, sorted, narrowed - and it is
     * used whenever there is one. The fallback is the plain view, so the
     * first frame after opening the tab has the library on it rather than
     * nothing while a call is in flight.
     */
    val visible: List<MusicTrack>
        get() = shown.ifEmpty {
            if (filtered) {
                emptyList()
            } else {
                current?.let { playlist ->
                    val byId = tracks.associateBy { it.id }
                    playlist.trackIds.mapNotNull { byId[it] }
                } ?: tracks
            }
        }
}

data class PackagesState(
    val installed: List<InstalledPackage> = emptyList(),
    val bundled: List<String> = emptyList(),
    val busy: Boolean = false,
    val progress: String = "",
    /** What PyPI says about the package somebody just looked up. */
    val lookup: PackageLookup? = null,
    val looking: Boolean = false,
)

/**
 * A package, as PyPI describes it, before anything is downloaded.
 *
 * The point of the whole type is [installable]: a package with only compiled
 * wheels cannot work here, and finding that out after a minute of downloading
 * is the worst time to find it out.
 */
data class PackageLookup(
    val name: String,
    val version: String,
    val summary: String,
    val installable: Boolean,
    val whyNot: String,
    val requiresPython: String,
    val sizeBytes: Long,
    val versions: List<String>,
)

data class ServersState(
    val servers: List<RunningServer> = emptyList(),
    val localIp: String = "",
    val busy: Boolean = false,
    val form: LaunchForm = LaunchForm(),
    /** Handle of the server whose console is open, or null for the list. */
    val openConsole: String? = null,
) {
    val running: Int get() = servers.count { it.isRunning }
}

/** A transient message shown in the snackbar. */
data class Toast(val text: String, val id: Long)

/** How many lines each server console keeps. */
private const val CONSOLE_LIMIT = 1500

/** Log tag for the view model's own messages. */
private const val TAG_VIEW = "ui"

/** How long typing has to stop before Autosave writes the file. */
private const val AUTOSAVE_DELAY_MS = 2000L

/** Remembered so a fork or a moved branch stays pointed at after a restart. */
private const val KEY_UPDATE_SOURCE = "manifest-url"

/** The console's own commands reach the app under this id. */
private const val SHELL_ID = "pycmd.shell"

/** How much room the kept-versions archive may take. */
private const val KEY_VERSIONS_CAP = "versions-cap"

/** A gigabyte: room for several builds, and a number people recognise. */
private const val DEFAULT_VERSIONS_CAP = 1024L * 1024 * 1024

/** When the app last looked, so it looks once a day rather than every launch. */
private const val KEY_UPDATE_CHECKED = "checked-at"

private const val DAY_MS = 24L * 60 * 60 * 1000

/**
 * The guides that ship in `assets/docs`, so a link from one to another opens
 * the guide instead of hunting for a file that is not on the phone.
 */
/**
 * The two shapes of JSON array this file reads, as one line each.
 *
 * Everything crossing the bridge from Python is JSON, and `for (i in 0 until
 * length())` written out eleven times is eleven chances to write `optString`
 * where `optJSONObject` belonged.
 */
private fun JSONArray?.rows(): List<JSONObject> =
    if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }

private fun JSONArray?.strings(): List<String> =
    if (this == null) {
        emptyList()
    } else {
        (0 until length()).map { optString(it) }.filter { it.isNotBlank() }
    }

private val SHIPPED_GUIDES = setOf(
    "README.md", "TUTORIAL.md", "PLUGINS.md", "BUILTINS.md", "FORKING.md",
)

private const val DEFAULT_SNIPPET = """# Welcome to PyCmd.
# Write Python here, then press Run. Output lands in the Console tab.

import sys


def main() -> None:
    print("Hello from PyCmd")
    print("Running Python", sys.version.split()[0])


if __name__ == "__main__":
    main()
"""

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val workspace = Workspace(application)
    private val engine = PythonEngine

    val engineStatus: StateFlow<EngineStatus> = engine.status
    val output: SharedFlow<OutputChunk> = engine.output
    val serverCount: StateFlow<Int> = engine.serverCount

    private val _tab = MutableStateFlow(Tab.CONSOLE)
    val tab: StateFlow<Tab> = _tab.asStateFlow()

    private val _editor = MutableStateFlow(EditorState())
    val editor: StateFlow<EditorState> = _editor.asStateFlow()

    private val _files = MutableStateFlow(FilesState())
    val files: StateFlow<FilesState> = _files.asStateFlow()

    private val _pages = MutableStateFlow(PagesState())
    val pages: StateFlow<PagesState> = _pages.asStateFlow()

    private val _packages = MutableStateFlow(PackagesState())
    val packages: StateFlow<PackagesState> = _packages.asStateFlow()

    private val _downloads = MutableStateFlow(DownloadsState())
    val downloads: StateFlow<DownloadsState> = _downloads.asStateFlow()

    val pluginsEnabled: StateFlow<Set<String>> = Plugins.enabled

    /** Extensions the preview can show, which is wider than what can run. */
    private val _previewable = MutableStateFlow<Set<String>>(emptySet())
    val previewable: StateFlow<Set<String>> = _previewable.asStateFlow()

    private val _languages = MutableStateFlow<List<LanguageInfo>>(emptyList())
    val languages: StateFlow<List<LanguageInfo>> = _languages.asStateFlow()

    private val _servers = MutableStateFlow(ServersState())
    val servers: StateFlow<ServersState> = _servers.asStateFlow()

    /** Plugins the user installed themselves, and which of them are on. */
    val customPlugins: StateFlow<List<InstalledPlugin>> = CustomPlugins.installed
    val customPluginsEnabled: StateFlow<Set<String>> = CustomPlugins.enabled

    private val _pluginBusy = MutableStateFlow("")
    val pluginBusy: StateFlow<String> = _pluginBusy.asStateFlow()

    /** The custom plugin whose panel is open, if any. */
    private val _openPanel = MutableStateFlow<InstalledPlugin?>(null)
    val openPanel: StateFlow<InstalledPlugin?> = _openPanel.asStateFlow()

    /** Commands the loaded plugins have registered, by name. */
    private val _pluginCommands = MutableStateFlow<Map<String, String>>(emptyMap())
    val pluginCommands: StateFlow<Map<String, String>> = _pluginCommands.asStateFlow()

    /** The page shown by the preview overlay, when one is open. */
    private val _preview = MutableStateFlow<PreviewPage?>(null)
    val preview: StateFlow<PreviewPage?> = _preview.asStateFlow()

    /** Which plugin tool is open, if any. */
    private val _activeTool = MutableStateFlow<PluginScreen?>(null)
    val activeTool: StateFlow<PluginScreen?> = _activeTool.asStateFlow()

    private val _toast = MutableStateFlow<Toast?>(null)
    val toast: StateFlow<Toast?> = _toast.asStateFlow()

    private val _history = MutableStateFlow<List<String>>(emptyList())
    val history: StateFlow<List<String>> = _history.asStateFlow()

    /**
     * Bumped when something asks for the console to be wiped.
     *
     * The scrollback lives in the WebView, not here, so `clear` cannot empty a
     * list - it has to reach the page. A timestamp rather than a flag: two
     * clears in a row are two events, and a flag would only be one.
     */
    private val _clearConsole = MutableStateFlow(0L)
    val clearConsole: StateFlow<Long> = _clearConsole.asStateFlow()

    /** Output per server channel, so each server console has its own scrollback. */
    private val _serverConsoles = MutableStateFlow<Map<String, List<OutputChunk>>>(emptyMap())
    val serverConsoles: StateFlow<Map<String, List<OutputChunk>>> = _serverConsoles.asStateFlow()

    val awaitingInput: StateFlow<Set<String>> = engine.awaitingInput

    val debugEntries: StateFlow<List<LogEntry>> = DebugLog.entries
    val debugErrorCount: StateFlow<Int> = DebugLog.errorCount

    val workspaceRoot: File get() = workspace.root

    /** Path shown in the UI, relative to the workspace root. */
    fun relativePath(file: File): String = workspace.relativePath(file)

    init {
        // Everything a server prints is tagged with its handle; the console
        // ignores those and each server console keeps only its own.
        //
        // Batched, because the state this writes is a map of immutable lists:
        // copying both for every single line meant a server logging a request
        // per file did more work rebuilding lists than serving. Collecting a
        // burst first turns hundreds of copies into one.
        // On a background thread, deliberately. Rebuilding a fifteen-hundred
        // line scrollback is real work, and a server printing steadily made
        // the main thread do it sixty times a second - which is a phone that
        // stops responding to a finger while something is logging.
        viewModelScope.launch(Dispatchers.Default) {
            val queue = Channel<OutputChunk>(4096, BufferOverflow.DROP_OLDEST)
            launch {
                engine.output.collect { chunk ->
                    if (chunk.channel != CONSOLE_CHANNEL) queue.send(chunk)
                }
            }
            val batch = ArrayList<OutputChunk>(CONSOLE_LIMIT)
            while (isActive) {
                batch.clear()
                batch += queue.receive()
                while (batch.size < CONSOLE_LIMIT) {
                    batch += queue.tryReceive().getOrNull() ?: break
                }
                val grouped = batch.groupBy { it.channel }
                var consoles = _serverConsoles.value
                for ((channel, chunks) in grouped) {
                    val current = consoles[channel].orEmpty()
                    consoles = consoles + (channel to (current + chunks).takeLast(CONSOLE_LIMIT))
                }
                _serverConsoles.value = consoles
                delay(16)
            }
        }

        // A plugin's toast went into a flow nobody read, so api.toast() has
        // never shown anything. It does now.
        viewModelScope.launch {
            engine.pluginToasts.collect { showToast(it) }
        }

        // And the things a plugin asks the app to do.
        viewModelScope.launch {
            engine.pluginActions.collect(::handlePluginAction)
        }

        viewModelScope.launch {
            workspace.seedExamples()
            _files.value = FilesState(directory = workspace.root, loading = true)
            engine.start(getApplication())
            refreshFiles(workspace.root)
            refreshPackages()
            refreshServers()
            refreshDownloads()
            refreshLanguages()
            _previewable.value = engine.previewableExtensions()
            // Bundled plugins first, and this order is not arbitrary.
            // Installing one replaces its folder on disk; loading one imports
            // a module out of that folder. Listing first meant the two ran at
            // once - a plugin being imported while its own folder was being
            // taken apart underneath it, which is a FileNotFoundError on a
            // file that was there a moment ago. Nothing is loaded until the
            // folders have stopped moving.
            installBundledPlugins()
            refreshCustomPlugins()
            quietlyCheckForUpdate()
            refreshVersions()
            refreshPages()
            // Read at startup rather than when the tab is opened, so that
            // music left playing from before is already on the controls - and
            // so that More can say something is on without being visited.
            refreshMusic()
        }
    }

    /**
     * The activity is going for good.
     *
     * The controller is a binder held to another process; letting it go is
     * not stopping the music. The service keeps whatever it was playing, and
     * the notification stays the way to stop it.
     */
    override fun onCleared() {
        hub.release()
        // The decks are two ExoPlayers and up to ten audio effects; leaving
        // them behind would keep an audio session and its DSP alive for as
        // long as the process is.
        mixer.release()
        PanelViews.clear()
        super.onCleared()
    }

    /**
     * Installs the plugins that ship with the app, without switching them on.
     *
     * A bundled plugin is still a plugin: it lands in the same folder, shows
     * the same switch, and stays off until the user turns it on. Installing it
     * for them only saves the file-picker trip - it does not decide anything
     * on their behalf. A version already installed is replaced only when the
     * app ships a different one, so a plugin somebody edited is left alone
     * between updates.
     */
    private suspend fun installBundledPlugins() {
        val staged = workspace.stageBundledPlugins()
        if (staged.isEmpty()) return

        // Asked for here rather than read off the state flow. This runs at
        // startup, before anything has filled that in, so an empty list read
        // as "none of them are installed" - and every bundled plugin was
        // deleted and written again on every single launch, for nothing.
        val installed = mutableMapOf<String, String>()
        val listing = engine.listPlugins()
        val rows = listing.optJSONArray("plugins")
        if (rows != null) {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONObject(index) ?: continue
                // A folder that cannot be read is not a version to match
                // against: leaving it alone is how a half-written plugin
                // would stay half-written for ever.
                if (row.optBoolean("broken")) continue
                installed[row.optString("id")] = row.optString("version")
            }
        }

        var installedAny = false
        for (folder in staged) {
            val manifest = runCatching {
                JSONObject(File(folder, "plugin.json").readText())
            }.getOrNull() ?: continue
            val id = manifest.optString("id")
            val version = manifest.optString("version")
            if (id.isEmpty()) continue

            if (installed[id] == version) continue

            val reply = engine.installPlugin(folder.absolutePath, folder.name, bundled = true)
            if (reply.optBoolean("ok")) {
                installedAny = true
                DebugLog.info(TAG_VIEW, "bundled plugin ready: $id", version)
            } else {
                DebugLog.warn(TAG_VIEW, "bundled plugin $id failed", reply.optString("error"))
            }
        }
        if (installedAny) DebugLog.info(TAG_VIEW, "bundled plugins refreshed")
    }

    // --------------------------------------------------------------- plugins

    fun setPluginEnabled(id: String, on: Boolean) {
        Plugins.setEnabled(id, on)
        // Polyglot Files decides which file types exist, so the catalogue has
        // to follow it rather than be read once at startup.
        if (id == PluginIds.POLYGLOT_FILES || id == PluginIds.POWER_PACK) refreshLanguages()
    }

    fun enableAllPlugins() {
        Plugins.enableAll()
        refreshLanguages()
        showToast("Every plugin is on")
    }

    fun resetPlugins() {
        Plugins.resetToDefaults()
        refreshLanguages()
        showToast("Plugins reset")
    }

    fun isPluginOn(id: String): Boolean = Plugins.isOn(id)

    // ------------------------------------------------------- custom plugins

    /** Re-reads what is on disk, then loads whatever is switched on. */
    /**
     * Tells every loaded plugin that something happened.
     *
     * Fire-and-forget on purpose: a plugin that is slow, or broken, must not
     * make saving a file feel slow or fail. Errors are caught on the Python
     * side and reported against the plugin that caused them.
     */
    private fun firePlugins(event: String, payload: JSONObject = JSONObject()) {
        if (CustomPlugins.enabled.value.isEmpty()) return
        viewModelScope.launch { engine.firePluginEvent(event, payload.toString()) }
    }

    fun refreshCustomPlugins(reload: Boolean = true) {
        viewModelScope.launch {
            val reply = engine.listPlugins()
            if (!reply.optBoolean("ok")) {
                DebugLog.warn(TAG_VIEW, "could not list plugins", reply.optString("error"))
                return@launch
            }
            val rows = reply.optJSONArray("plugins") ?: return@launch
            val parsed = (0 until rows.length()).mapNotNull { index ->
                rows.optJSONObject(index)?.let(InstalledPlugin::from)
            }
            CustomPlugins.setInstalled(parsed)
            if (reload) loadEnabledPlugins()
        }
    }

    private suspend fun loadEnabledPlugins() {
        val wanted = CustomPlugins.enabled.value
        engine.loadPlugins(wanted)
        val commands = engine.pluginCommands()
        val rows = commands.optJSONArray("commands")
        val table = mutableMapOf<String, String>()
        if (rows != null) {
            for (index in 0 until rows.length()) {
                val row = rows.optJSONObject(index) ?: continue
                table[row.optString("name")] = row.optString("help")
            }
        }
        _pluginCommands.value = table
        // The listing carries a loaded flag and any load error, so it has to
        // be read back after loading rather than before.
        val reply = engine.listPlugins()
        val listed = reply.optJSONArray("plugins")
        if (listed != null) {
            CustomPlugins.setInstalled(
                (0 until listed.length()).mapNotNull { index ->
                    listed.optJSONObject(index)?.let(InstalledPlugin::from)
                },
            )
        }
    }

    fun setCustomPluginEnabled(id: String, on: Boolean) {
        CustomPlugins.setEnabled(id, on)
        // A panel kept warm for a plugin that has just been switched off is a
        // page that can still call into it. It goes now, not when something
        // else needs the room.
        if (!on) PanelViews.forget(id)
        viewModelScope.launch {
            loadEnabledPlugins()
            val plugin = CustomPlugins.installed.value.firstOrNull { it.id == id }
            val failure = plugin?.error
            if (on && !failure.isNullOrEmpty()) {
                showToast("${plugin.name} failed to load - see the debug console")
            }
        }
    }

    /** Installs a plugin the user picked from outside the app. */
    fun installPluginFromUri(uri: Uri, isFolder: Boolean) {
        _pluginBusy.value = if (isFolder) "Copying the folder..." else "Copying the file..."
        viewModelScope.launch {
            val staged = if (isFolder) {
                Imports.stageTree(getApplication(), uri)
            } else {
                Imports.stageFile(getApplication(), uri)
            }
            staged
                .onSuccess { install(it.root.absolutePath, it.name) }
                .onFailure {
                    _pluginBusy.value = ""
                    showToast(it.message ?: "That could not be read.")
                }
        }
    }

    /** Installs a plugin that is already in the workspace. */
    fun installPluginFromWorkspace(file: File) {
        _pluginBusy.value = "Installing..."
        viewModelScope.launch { install(file.absolutePath, file.name) }
    }

    private suspend fun install(path: String, name: String) {
        _pluginBusy.value = "Installing..."
        val reply = engine.installPlugin(path, name)
        _pluginBusy.value = ""
        if (!reply.optBoolean("ok")) {
            val problem = reply.optString("error", "that is not a plugin")
            showToast(problem)
            DebugLog.warn(TAG_VIEW, "plugin install refused", "$name: $problem")
            return
        }
        val manifest = reply.optJSONObject("manifest")
        val installed = manifest?.optString("name").orEmpty().ifEmpty { name }
        showToast(
            if (reply.optBoolean("replaced")) "$installed updated" else "$installed installed",
        )
        DebugLog.info(TAG_VIEW, "installed plugin $installed", manifest?.optString("id").orEmpty())
        refreshCustomPlugins()
    }

    fun removeCustomPlugin(plugin: InstalledPlugin) {
        viewModelScope.launch {
            val reply = engine.removePlugin(plugin.id)
            if (reply.optBoolean("ok")) {
                CustomPlugins.forget(plugin.id)
                PanelViews.forget(plugin.id)
                showToast("${plugin.name} removed")
                refreshCustomPlugins()
            } else {
                showToast(reply.optString("error", "could not remove that"))
            }
        }
    }

    private val _system = MutableStateFlow(SystemInfo())
    val system: StateFlow<SystemInfo> = _system.asStateFlow()

    private val _systemBusy = MutableStateFlow("")
    val systemBusy: StateFlow<String> = _systemBusy.asStateFlow()

    /**
     * Measures what the app is using.
     *
     * Walking the whole of private storage is not free, so it happens when the
     * screen is opened and when the user asks, never on a timer.
     */
    fun refreshSystem() {
        viewModelScope.launch {
            _systemBusy.value = "Measuring..."
            _system.value = withContext(Dispatchers.IO) {
                tidyUpdates()
                measureSystem()
            }
            _systemBusy.value = ""
        }
    }

    private fun measureSystem(): SystemInfo {
        val context = getApplication<Application>()
        val files = context.filesDir
        val workspace = File(files, "workspace")
        val packages = File(files, "site-packages")
        val downloads = File(files, "downloads")
        val plugins = File(files, "plugins")
        val cache = context.cacheDir

        val version = runCatching {
            val info = context.packageManager.getPackageInfo(context.packageName, 0)
            "${info.versionName} (${@Suppress("DEPRECATION") info.versionCode})"
        }.getOrDefault("")

        return SystemInfo(
            pythonVersion = engine.status.value.pythonVersion,
            appVersion = version,
            abi = android.os.Build.SUPPORTED_ABIS.firstOrNull().orEmpty(),
            androidVersion = "${android.os.Build.VERSION.RELEASE} " +
                "(API ${android.os.Build.VERSION.SDK_INT})",
            device = "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}",
            workspaceBytes = folderSize(workspace),
            workspaceFiles = countFiles(workspace),
            packagesBytes = folderSize(packages),
            downloadsBytes = folderSize(downloads),
            pluginBytes = folderSize(plugins),
            versionsBytes = Updater.libraryBytes(context),
            cacheBytes = folderSize(cache),
            cacheFiles = countFiles(cache),
            freeBytes = runCatching { files.usableSpace }.getOrDefault(0L),
            servers = engine.serverCount.value,
            plugins = CustomPlugins.installed.value.count { it.loaded },
            threads = Thread.activeCount(),
        )
    }

    private fun folderSize(root: File): Long =
        root.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    private fun countFiles(root: File): Int =
        root.walkTopDown().count { it.isFile }

    fun clearCache() {
        viewModelScope.launch {
            _systemBusy.value = "Clearing..."
            val freed = withContext(Dispatchers.IO) {
                val cache = getApplication<Application>().cacheDir
                val before = folderSize(cache)
                cache.listFiles()?.forEach { it.deleteRecursively() }
                before - folderSize(cache)
            }
            _systemBusy.value = ""
            showToast("Freed ${freed / 1024} KB")
            refreshSystem()
        }
    }

    fun clearPycache() {
        viewModelScope.launch {
            _systemBusy.value = "Clearing..."
            val removed = withContext(Dispatchers.IO) {
                var count = 0
                workspace.root.walkTopDown()
                    .filter { it.isDirectory && it.name == "__pycache__" }
                    .toList()
                    .forEach { if (it.deleteRecursively()) count += 1 }
                count
            }
            _systemBusy.value = ""
            showToast(if (removed == 0) "Nothing to clear" else "Removed $removed __pycache__ folders")
            refreshFiles(_files.value.directory ?: workspace.root)
            refreshSystem()
        }
    }

    // ---- Updating in place -------------------------------------------------

    private val _update = MutableStateFlow<UpdateState>(UpdateState.Idle)
    val update: StateFlow<UpdateState> = _update.asStateFlow()

    private val _updateSource = MutableStateFlow(readUpdateSource())

    /** Where the check looks. Editable, because a branch can move. */
    val updateSource: StateFlow<String> = _updateSource.asStateFlow()

    private var updateJob: Job? = null

    private fun updatePreferences() = getApplication<Application>()
        .getSharedPreferences("pycmd-update", Context.MODE_PRIVATE)

    private fun readUpdateSource(): String =
        updatePreferences().getString(KEY_UPDATE_SOURCE, null)?.takeIf { it.isNotBlank() }
            ?: Updater.DEFAULT_MANIFEST_URL

    /**
     * Points the check somewhere else: a fork, another branch, a server of
     * your own. Blank puts it back to where PyCmd itself is published.
     */
    fun setUpdateSource(url: String) {
        val cleaned = url.trim().ifBlank { Updater.DEFAULT_MANIFEST_URL }
        if (cleaned == _updateSource.value) return
        _updateSource.value = cleaned
        updatePreferences().edit { putString(KEY_UPDATE_SOURCE, cleaned) }
        // What was found at the old address says nothing about the new one.
        updateJob?.cancel()
        _update.value = UpdateState.Idle
    }

    /**
     * A quiet look for a newer build, at most once a day.
     *
     * Without this the whole feature is invisible: nobody opens System to ask
     * whether there is an update, so the update they wanted sits unfound. It
     * reads one small file and stops there - nothing is downloaded and nothing
     * is installed without a tap, and a check that fails says nothing at all,
     * because a phone with no signal is not an error the user asked about.
     */
    private fun quietlyCheckForUpdate() {
        val store = updatePreferences()
        val last = store.getLong(KEY_UPDATE_CHECKED, 0)
        val age = System.currentTimeMillis() - last
        // A clock moved backwards gives a negative age; that is a reason to
        // check, not a reason to wait until the phone catches up with itself.
        if (age in 0 until DAY_MS) return
        store.edit { putLong(KEY_UPDATE_CHECKED, System.currentTimeMillis()) }

        viewModelScope.launch {
            Updater.fetch(_updateSource.value).onSuccess { release ->
                val mine = getApplication<Application>().packageName
                val newer = release.versionCode > BuildConfig.VERSION_CODE &&
                    (release.packageName.isBlank() || release.packageName == mine)
                // Never over the top of something the user started.
                if (newer && _update.value is UpdateState.Idle) {
                    _update.value = UpdateState.Available(release)
                    DebugLog.info(TAG_VIEW, "an update is available", release.versionName)
                }
            }
        }
    }

    private val _backgroundChecks = MutableStateFlow(
        updatePreferences().getBoolean(UpdateWorker.KEY_BACKGROUND, false),
    )

    /** Whether Android is asked to look for updates while the app is closed. */
    val backgroundChecks: StateFlow<Boolean> = _backgroundChecks.asStateFlow()

    private val _backgroundDownload = MutableStateFlow(
        updatePreferences().getBoolean(UpdateWorker.KEY_AUTO_DOWNLOAD, false),
    )

    /** And whether it may spend the download too, on wifi. */
    val backgroundDownload: StateFlow<Boolean> = _backgroundDownload.asStateFlow()

    fun setBackgroundChecks(on: Boolean) {
        _backgroundChecks.value = on
        updatePreferences().edit { putBoolean(UpdateWorker.KEY_BACKGROUND, on) }
        UpdateWorker.sync(getApplication())
        showToast(
            if (on) {
                "PyCmd will look about once a day, on wifi"
            } else {
                "Background checks are off"
            },
        )
    }

    fun setBackgroundDownload(on: Boolean) {
        _backgroundDownload.value = on
        updatePreferences().edit { putBoolean(UpdateWorker.KEY_AUTO_DOWNLOAD, on) }
    }

    /** Reads the manifest and says whether there is anything newer. */
    fun checkForUpdate() {
        if (_update.value is UpdateState.Downloading) return
        updateJob?.cancel()
        updateJob = viewModelScope.launch {
            _update.value = UpdateState.Checking
            Updater.fetch(_updateSource.value)
                .onSuccess { release ->
                    val mine = getApplication<Application>().packageName
                    _update.value = when {
                        release.versionCode <= BuildConfig.VERSION_CODE ->
                            UpdateState.UpToDate(BuildConfig.VERSION_NAME)
                        // Said before the download rather than after it: 35 MB
                        // is a lot to spend on finding out it is another app.
                        release.packageName.isNotBlank() && release.packageName != mine ->
                            UpdateState.Failed(
                                "That address publishes a different app.",
                                "It offers ${release.packageName}; this is $mine. " +
                                    "Installing it would put a second app on the phone " +
                                    "rather than updating this one.",
                            )
                        else -> UpdateState.Available(release)
                    }
                }
                .onFailure {
                    _update.value = UpdateState.Failed(
                        "Could not check for an update.",
                        it.message.orEmpty(),
                    )
                }
        }
    }

    /** Downloads the APK the check found, and verifies it before offering it. */
    fun downloadUpdate() {
        val release = (_update.value as? UpdateState.Available)?.release ?: return
        updateJob?.cancel()
        updateJob = viewModelScope.launch {
            val context = getApplication<Application>()
            _update.value = UpdateState.Downloading(release, 0, release.bytes)
            Updater.download(context, release) { got, total ->
                _update.value = UpdateState.Downloading(release, got, total)
            }
                .onSuccess { file ->
                    // Better to say why it cannot install now than to let the
                    // system installer say "App not installed" and leave the
                    // user reaching for uninstall.
                    val blocker = withContext(Dispatchers.IO) { Updater.blocker(context, file) }
                    if (blocker == null) {
                        // Filed away before it is installed, so going back to
                        // this build later does not need another download.
                        withContext(Dispatchers.IO) {
                            Updater.keep(context, file, versionsCap(), BuildConfig.VERSION_CODE)
                        }
                        refreshVersions()
                    }
                    _update.value = if (blocker == null) {
                        UpdateState.Ready(release, file)
                    } else {
                        Updater.forget(context)
                        UpdateState.Failed("That build will not install over this one.", blocker)
                    }
                    refreshSystem()
                }
                .onFailure {
                    _update.value = UpdateState.Failed(
                        "The download did not finish.",
                        it.message.orEmpty(),
                    )
                }
        }
    }

    /** Stops a download and puts the offer back the way it was. */
    fun cancelUpdate() {
        val release = (_update.value as? UpdateState.Downloading)?.release
        updateJob?.cancel()
        updateJob = null
        _update.value = release?.let { UpdateState.Available(it) } ?: UpdateState.Idle
    }

    /** Hands the verified APK to the system installer. */
    fun installUpdate() {
        val ready = _update.value as? UpdateState.Ready ?: return
        val context = getApplication<Application>()
        if (!Updater.canInstall(context)) {
            showToast("Let PyCmd install apps, then press Install again.")
            Updater.requestInstallPermission(context)
            return
        }
        Updater.install(context, ready.file)
            .onFailure { showToast(it.message ?: "Could not open the installer.") }
    }

    // ---- The versions you can go back to -----------------------------------

    private val _versions = MutableStateFlow<List<KeptVersion>>(emptyList())

    /** Every build kept on the device, newest first. */
    val versions: StateFlow<List<KeptVersion>> = _versions.asStateFlow()

    private val _versionsCap = MutableStateFlow(readVersionsCap())

    /** How much room the archive may take, in bytes. 0 means keep none. */
    val versionsCap: StateFlow<Long> = _versionsCap.asStateFlow()

    private fun versionsCap(): Long = _versionsCap.value

    private fun readVersionsCap(): Long =
        updatePreferences().getLong(KEY_VERSIONS_CAP, DEFAULT_VERSIONS_CAP)

    /**
     * Changes the ceiling on the archive, and prunes to it straight away.
     *
     * Oldest first: the reason to keep an old build is to go back one step,
     * and three steps back is a build nobody is going to install.
     */
    fun setVersionsCap(bytes: Long) {
        val chosen = bytes.coerceAtLeast(0L)
        _versionsCap.value = chosen
        updatePreferences().edit { putLong(KEY_VERSIONS_CAP, chosen) }
        viewModelScope.launch {
            withContext(Dispatchers.IO) {
                Updater.prune(getApplication(), chosen, BuildConfig.VERSION_CODE)
            }
            refreshVersions()
            refreshSystem()
        }
    }

    fun refreshVersions() {
        viewModelScope.launch {
            _versions.value = withContext(Dispatchers.IO) { Updater.versions(getApplication()) }
        }
    }

    /** Hands one of the kept APKs to the installer. */
    fun installVersion(version: KeptVersion) {
        val context = getApplication<Application>()
        if (!Updater.canInstall(context)) {
            showToast("Let PyCmd install apps, then press Install again.")
            Updater.requestInstallPermission(context)
            return
        }
        Updater.install(context, version.file)
            .onFailure { showToast(it.message ?: "Could not open the installer.") }
    }

    fun deleteVersion(version: KeptVersion) {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { version.file.delete() }
            refreshVersions()
            refreshSystem()
        }
    }

    fun deleteAllVersions() {
        viewModelScope.launch {
            val gone = withContext(Dispatchers.IO) { Updater.clearLibrary(getApplication()) }
            showToast(if (gone == 0) "Nothing kept" else "Deleted $gone")
            refreshVersions()
            refreshSystem()
        }
    }

    /**
     * Writes the workspace to a zip and hands it back for saving out.
     *
     * The one thing that has to happen before going back to an older build:
     * Android will not install a lower versionCode over a higher one, so a
     * real rollback means uninstalling - and uninstalling takes the workspace,
     * this archive and everything else the app owns with it.
     */
    fun backupWorkspaceForRollback(onReady: (File) -> Unit) {
        viewModelScope.launch {
            _systemBusy.value = "Packing the workspace..."
            val result = engine.exportWorkspace()
            _systemBusy.value = ""
            if (result.ok && result.path.isNotEmpty()) {
                onReady(File(result.path))
            } else {
                showToast(result.error.ifBlank { "Could not pack the workspace." })
            }
        }
    }

    /** Clears the card, and the download with it. */
    fun dismissUpdate() {
        updateJob?.cancel()
        updateJob = null
        val context = getApplication<Application>()
        Updater.forget(context)
        _update.value = UpdateState.Idle
        refreshSystem()
    }

    /**
     * Throws away a download that is no longer worth its 30-odd MB.
     *
     * Once the update has been installed, the APK it came from is the version
     * that is now running - it would sit there forever otherwise.
     */
    private fun tidyUpdates() {
        if (_update.value is UpdateState.Downloading || _update.value is UpdateState.Ready) return
        Updater.tidy(getApplication(), BuildConfig.VERSION_CODE)
    }

    private val _pluginCandidates = MutableStateFlow<List<File>>(emptyList())

    /** Plugins sitting in the workspace, which the system picker cannot see. */
    val pluginCandidates: StateFlow<List<File>> = _pluginCandidates.asStateFlow()

    fun refreshPluginCandidates() {
        viewModelScope.launch { _pluginCandidates.value = workspace.pluginCandidates() }
    }

    /** Opens one of them, rendered the same way the app's own guides are. */
    fun openPluginGuide(plugin: InstalledPlugin, guide: PluginGuide) {
        viewModelScope.launch {
            val reply = engine.pluginGuide(plugin.id, guide.file)
            if (!reply.optBoolean("ok")) {
                showToast(reply.optString("error").ifBlank { "That guide could not be read." })
                return@launch
            }
            _preview.value = engine.previewText(reply.optString("text"), guide.file)
        }
    }

    /** Shows the plugin authoring guide that ships in the APK. */
    fun openGuide(asset: String = "docs/PLUGINS.md", title: String = "PLUGINS.md") {
        viewModelScope.launch {
            val text = workspace.readAsset(asset)
            if (text == null) {
                showToast("That guide is missing from this build.")
                return@launch
            }
            _preview.value = engine.previewText(text, title)
        }
    }

    /** Where the open panel was opened from, so closing it goes back there. */
    private var panelCameFrom = Tab.PLUGINS

    /**
     * Does what a plugin asked for, if the plugin is still switched on.
     *
     * Checked again here rather than trusted: the request may have been queued
     * before the user turned the plugin off, and a plugin that has been
     * switched off should not still be moving the app around.
     */
    private fun handlePluginAction(request: PluginAction) {
        // The console's own commands come through the same bridge under a
        // reserved id: `open notes.md` and `serve .` need exactly what a
        // plugin needs, and a second bridge would be the same code twice.
        if (request.pluginId != SHELL_ID && !CustomPlugins.isOn(request.pluginId)) return
        val detail = runCatching { JSONObject(request.detail) }.getOrDefault(JSONObject())
        val path = detail.optString("path")

        when (request.action) {
            "open_file" -> if (path.isNotEmpty()) openInEditor(File(path))
            "run_file" -> if (path.isNotEmpty()) runFile(File(path))
            "preview" -> if (path.isNotEmpty()) previewFile(File(path))
            "serve" -> if (path.isNotEmpty()) {
                updateLaunchForm {
                    val target = File(path)
                    if (target.isDirectory) {
                        it.copy(kind = ServerKind.STATIC, folder = target)
                    } else {
                        it.copy(kind = ServerKind.SCRIPT, script = target, plan = RunPlan())
                    }
                }
                detail.optInt("port").takeIf { it > 0 }?.let { port ->
                    updateLaunchForm { it.copy(port = port.toString()) }
                }
                launchServer()
            }

            "go_to" -> tabNamed(detail.optString("tab"))?.let { selectTab(it) }

            "clear_console" -> _clearConsole.value = System.currentTimeMillis()

            "open_panel" -> CustomPlugins.installed.value
                .firstOrNull { it.id == request.pluginId }
                ?.let { openPluginPanel(it, detail.optString("panel")) }

            "refresh" -> when (detail.optString("what")) {
                "servers" -> refreshServers()
                "downloads" -> refreshDownloads()
                "packages" -> refreshPackages()
                "plugins" -> refreshCustomPlugins()
                "pages" -> refreshPages()
                "music" -> refreshMusic()
                else -> refreshFiles(_files.value.directory ?: workspace.root)
            }

            // -- the decks -------------------------------------------------
            //
            // Everything Music Pro's panel does to the mixer arrives here.
            // Fire and forget, like every other plugin action: the answer
            // comes back as a `mixer_state` event rather than as a return
            // value, because a plugin is on whatever thread it is on and
            // nothing here can be waited for.
            "mixer.load" -> mixer.load(
                detail.optString("deck", "a"),
                detail.optString("path"),
                detail.optString("title"),
            )

            "mixer.play" -> mixer.play(detail.optString("deck", "a"))
            "mixer.pause" -> mixer.pause(detail.optString("deck", "a"))
            "mixer.cue" -> mixer.cue(detail.optString("deck", "a"))
            "mixer.eject" -> mixer.eject(detail.optString("deck", "a"))
            "mixer.seek" -> mixer.seek(
                detail.optString("deck", "a"), detail.optLong("position"),
            )
            "mixer.loop" -> mixer.loop(
                detail.optString("deck", "a"),
                detail.optLong("start"),
                detail.optLong("end"),
            )
            "mixer.tempo" -> mixer.tempo(
                detail.optString("deck", "a"), detail.optDouble("rate", 1.0),
            )
            "mixer.gain" -> mixer.gain(
                detail.optString("deck", "a"), detail.optDouble("level", 1.0),
            )
            "mixer.fader" -> mixer.fader(detail.optDouble("position", 0.5))
            "mixer.effect" -> mixer.effect(
                detail.optString("deck", "a"),
                detail.optString("name"),
                detail.optDouble("level", 0.0),
            )
            "mixer.band" -> mixer.band(
                detail.optString("deck", "a"),
                detail.optInt("index"),
                detail.optDouble("level", 0.0),
            )
            "mixer.flatten" -> mixer.flatten(detail.optString("deck", "a"))
            "mixer.state" -> tellMixerStateAlways()
            "mixer.release" -> {
                mixer.release()
                tellMixerStateAlways()
            }

            // -- the other apps on this phone --------------------------------
            "apps.state" -> viewModelScope.launch {
                engine.firePluginEvent("apps_state", neighbours.playing().toString())
            }
            "apps.list" -> viewModelScope.launch {
                engine.firePluginEvent("apps_list", neighbours.searchApps().toString())
            }
            "apps.control" -> {
                val done = neighbours.control(
                    detail.optString("package"), detail.optString("what", "toggle"),
                )
                if (!done) showToast("Nothing is playing that PyCmd can reach.")
                viewModelScope.launch {
                    engine.firePluginEvent("apps_state", neighbours.playing().toString())
                }
            }
            "apps.seek" -> neighbours.seek(
                detail.optString("package"), detail.optLong("position"),
            )
            "apps.search" -> {
                if (!neighbours.searchIn(detail.optString("package"), detail.optString("query"))) {
                    showToast("No app on this phone took that search.")
                }
            }
            "apps.open" -> {
                if (!neighbours.openApp(detail.optString("package"))) {
                    showToast("That app is not installed any more.")
                }
            }
            "apps.link" -> {
                if (!neighbours.openLink(detail.optString("url"))) {
                    showToast("That link would not open.")
                }
            }
            "apps.permission" -> runCatching {
                getApplication<Application>().startActivity(neighbours.permissionIntent())
            }.onFailure {
                showToast("This phone has no notification-access screen.")
            }

            else -> DebugLog.warn(
                TAG_VIEW, "a plugin asked for something unknown", request.action,
            )
        }
    }

    /** Sends the mixer state whether or not it changed, for a panel just opened. */
    private fun tellMixerStateAlways() {
        lastMixerState = ""
        tellMixerState(mixer.state())
    }

    /** The screen a plugin named, or null if there is no such screen. */
    private fun tabNamed(name: String): Tab? = when (name) {
        "console" -> Tab.CONSOLE
        "editor" -> Tab.EDITOR
        "files" -> Tab.FILES
        "servers" -> Tab.SERVERS
        "packages" -> Tab.PACKAGES
        "downloads" -> Tab.DOWNLOADS
        "plugins" -> Tab.PLUGINS
        "system" -> Tab.SYSTEM
        "debug" -> Tab.DEBUG
        "guides", "docs" -> Tab.DOCS
        "pages" -> Tab.PAGES
        "music" -> Tab.MUSIC
        "more" -> Tab.MORE
        else -> null
    }

    /** Which of the plugin's pages the full-screen panel is showing. */
    private val _openPanelFile = MutableStateFlow("")
    val openPanelFile: StateFlow<String> = _openPanelFile.asStateFlow()

    fun openPluginPanel(plugin: InstalledPlugin, panelFile: String = "") {
        if (!CustomPlugins.isOn(plugin.id)) {
            showToast("${plugin.name} is switched off.")
            return
        }
        panelCameFrom = _tab.value.takeIf { it != Tab.PLUGIN_PANEL } ?: Tab.PLUGINS
        _openPanel.value = plugin
        _openPanelFile.value = panelFile
        _tab.value = Tab.PLUGIN_PANEL
    }

    fun closePluginPanel() {
        _openPanel.value = null
        _openPanelFile.value = ""
        // A panel opened from its tab in More belongs to More; closing it into
        // the plugin list would be a different screen than the one you left.
        _tab.value = panelCameFrom
    }

    suspend fun pluginPanelHtml(id: String, panelFile: String = ""): String =
        engine.pluginPanel(id, panelFile)

    /** The current value of every setting a plugin declared. */
    suspend fun pluginSettings(id: String): Map<String, Any?> {
        val reply = engine.pluginSettings(id)
        val rows = reply.optJSONArray("settings") ?: return emptyMap()
        val values = mutableMapOf<String, Any?>()
        for (index in 0 until rows.length()) {
            val row = rows.optJSONObject(index) ?: continue
            // JSONObject.NULL is an object, not null, and it would reach a
            // switch as something that is neither true nor false.
            val value = row.opt("value").takeIf { it != JSONObject.NULL }
            values[row.optString("name")] = value
        }
        return values
    }

    /** One pending save per setting, so typing does not write once per letter. */
    private val settingSaves = mutableMapOf<String, Job>()

    fun setPluginSetting(id: String, name: String, value: String) {
        val key = "$id:$name"
        settingSaves.remove(key)?.cancel()
        settingSaves[key] = viewModelScope.launch {
            // A text field calls this on every keystroke. Waiting for a pause
            // turns a word into one write rather than one per character, and
            // a switch or a choice still lands almost immediately.
            delay(250)
            val reply = engine.setPluginSetting(id, name, value)
            if (!reply.optBoolean("ok")) {
                showToast(reply.optString("error").ifBlank { "Could not save that." })
            }
            settingSaves.remove(key)
        }
    }

    /**
     * The menu lines switched-on plugins want on this file or folder.
     *
     * Returned with the plugin, because acting on one means calling that
     * plugin's export - and two plugins can both want a line on the same file.
     */
    /**
     * What switched-on plugins offer to do with one file.
     *
     * Takes the name and whether it is a folder rather than the [File],
     * because this is called for every row of the Files tab on every redraw
     * and `File.isDirectory` is a trip to the filesystem each time. The list
     * already knows; asking the disk two hundred times while a finger is
     * moving is how scrolling a big folder came to stutter.
     *
     * The early return matters for the same reason: with no plugins on there
     * is nothing to work out, and that is most people most of the time.
     */
    fun actionsFor(name: String, isDirectory: Boolean): List<Pair<InstalledPlugin, PluginFileAction>> {
        val on = CustomPlugins.enabled.value
        if (on.isEmpty()) return emptyList()
        return CustomPlugins.installed.value
            .filter { it.id in on }
            .flatMap { plugin ->
                plugin.actions
                    .filter { it.appliesTo(name, isDirectory) }
                    .map { plugin to it }
            }
    }

    /** Runs a plugin's file action on the file the user picked. */
    fun runFileAction(plugin: InstalledPlugin, action: PluginFileAction, file: File) {
        viewModelScope.launch {
            val payload = JSONObject()
                .put("path", file.absolutePath)
                .put("name", file.name)
                .put("is_folder", file.isDirectory)
                .toString()
            val reply = engine.callPluginExport(plugin.id, action.export, payload)
            if (!reply.optBoolean("ok")) {
                showToast(
                    reply.optString("error").ifBlank { "${action.label} did not work." },
                )
            }
            refreshFiles(_files.value.directory ?: workspace.root)
        }
    }



    suspend fun callPluginExport(id: String, name: String, payload: String): JSONObject =
        engine.callPluginExport(id, name, payload)

    fun isPluginPoweredUp(id: String): Boolean = Plugins.isPoweredUp(id)

    /** Opens a plugin's own screen. */
    fun openPlugin(spec: PluginSpec) {
        val screen = spec.screen ?: return
        if (!Plugins.isOn(spec.id)) {
            showToast("${spec.name} is off.")
            return
        }
        _activeTool.value = screen
        _tab.value = Tab.TOOL
    }

    fun closeTool() {
        _activeTool.value = null
        _tab.value = Tab.PLUGINS
    }

    /**
     * Runs a plugin tool and hands back what it said.
     *
     * The tools live in Python because that is where the batteries are, and
     * because Regex Lab has to use the same `re` module the user's script
     * will - a regex tester that disagrees with the language is worse than
     * none at all.
     */
    suspend fun runTool(name: String, arguments: JSONObject): JSONObject =
        engine.tool(name, arguments)

    /** The text of the file open in the editor, for the tools that offer it. */
    fun editorContent(): String = _editor.value.content

    fun replaceEditorContent(content: String) {
        val state = _editor.value
        if (state.file == null) {
            showToast("Open a file first.")
            return
        }
        _editor.value = state.copy(content = content, epoch = nextEpoch())
        showToast("Editor updated")
    }

    /** Opens a search hit at the right file. */
    fun openSearchHit(path: String) {
        val file = File(path)
        if (!file.exists()) {
            showToast("That file is gone.")
            return
        }
        _activeTool.value = null
        openInEditor(file)
    }

    private fun refreshLanguages() {
        viewModelScope.launch {
            _languages.value = engine.languageCatalogue(Plugins.isOn(PluginIds.POLYGLOT_FILES))
        }
    }

    // ------------------------------------------------------------- downloads

    private var downloadsGeneration = 0L

    fun refreshDownloads() {
        val generation = ++downloadsGeneration
        viewModelScope.launch {
            val listed = engine.listDownloads()
            // Same reason as the file list: a slower listing must not overwrite
            // a newer one just because it came back second.
            if (generation != downloadsGeneration) return@launch
            _downloads.value = _downloads.value.copy(files = listed)
        }
    }

    fun downloadUrl(url: String) {
        if (url.isBlank()) {
            showToast("Enter a URL.")
            return
        }
        viewModelScope.launch {
            _downloads.value = _downloads.value.copy(busy = true, progress = "Starting...")
            val result = engine.downloadUrl(url) { message ->
                _downloads.value = _downloads.value.copy(progress = message)
            }
            _downloads.value = _downloads.value.copy(busy = false, progress = "")
            showToast(if (result.ok) "Saved ${result.name}" else result.error.ifBlank { "Download failed." })
            refreshDownloads()
        }
    }

    private val _sourceBusy = MutableStateFlow(false)

    /** True while the repository zip is coming down. */
    val sourceBusy: StateFlow<Boolean> = _sourceBusy.asStateFlow()

    /**
     * Pulls this app's own source onto the phone, as a zip in Downloads.
     *
     * The Kotlin is not in the APK - only the Python is - so this fetches the
     * repository rather than unpacking itself. From Downloads, "Save to
     * device" puts it somewhere a file manager can see, which is the whole
     * starting kit for a fork.
     */
    fun downloadSource() {
        if (_sourceBusy.value) return
        viewModelScope.launch {
            _sourceBusy.value = true
            _downloads.value = _downloads.value.copy(busy = true, progress = "Fetching the source...")
            val result = engine.downloadUrl(Updater.SOURCE_ZIP_URL) { message ->
                _downloads.value = _downloads.value.copy(progress = message)
            }
            _downloads.value = _downloads.value.copy(busy = false, progress = "")
            _sourceBusy.value = false
            showToast(
                if (result.ok) {
                    "Saved ${result.name} to Downloads"
                } else {
                    result.error.ifBlank { "Could not fetch the source." }
                },
            )
            refreshDownloads()
            if (result.ok) selectTab(Tab.DOWNLOADS)
        }
    }

    /**
     * A link the preview would not load, handed back for the app to answer.
     *
     * Three kinds arrive here. A `pycmd://` address is a button written into a
     * document - the guides use one so the **Download the source** the fork
     * guide talks about is actually at the end of the fork guide, instead of
     * being a sentence about a button on another screen. A link from one
     * shipped guide to another is opened as that guide, because a document
     * rendered from memory has no folder behind it to serve the sibling from.
     * Anything else leads out of the app, and this says so rather than
     * swallowing the tap in silence, which is what it used to do.
     */
    fun previewLink(url: String) {
        val target = url.trim()
        val guide = target.substringAfterLast('/').substringBefore('?')
        when {
            target.startsWith("pycmd://source") || target == Updater.SOURCE_ZIP_URL -> {
                closePreview()
                downloadSource()
            }
            target.startsWith("pycmd://") -> {
                DebugLog.warn("preview", "a document asked for something this build has no answer for", target)
                showToast("This build does not know that button.")
            }
            guide.endsWith(".md") && guide in SHIPPED_GUIDES -> openGuide("docs/$guide", guide)
            else -> {
                DebugLog.info("preview", "a link out of the preview", target)
                showToast("That link goes outside PyCmd.")
            }
        }
    }

    fun exportWorkspace() {
        viewModelScope.launch {
            _downloads.value = _downloads.value.copy(busy = true, progress = "Zipping the workspace...")
            val result = engine.exportWorkspace()
            _downloads.value = _downloads.value.copy(busy = false, progress = "")
            showToast(
                if (result.ok) "Exported ${result.files} files to ${result.name}"
                else result.error.ifBlank { "Export failed." },
            )
            refreshDownloads()
        }
    }

    /**
     * Zips one workspace folder into Downloads.
     *
     * From there it can be saved out to the phone's own storage, which is the
     * only route a folder has off the device: a picker hands over one file at
     * a time, never a tree.
     */
    fun exportFolder(folder: File) {
        viewModelScope.launch {
            _downloads.value = _downloads.value.copy(busy = true, progress = "Zipping ${folder.name}...")
            val result = engine.exportZip(folder.absolutePath)
            _downloads.value = _downloads.value.copy(busy = false, progress = "")
            showToast(
                if (result.ok) "Exported ${result.files} files to ${result.name}"
                else result.error.ifBlank { "Export failed." },
            )
            refreshDownloads()
            if (result.ok) selectTab(Tab.DOWNLOADS)
        }
    }

    /** Copies a file we hold out to wherever the user pointed the picker. */
    fun saveToDevice(source: File, target: Uri) {
        viewModelScope.launch {
            Exports.saveTo(getApplication(), source, target)
                .onSuccess { showToast("Saved ${source.name} to the device") }
                .onFailure { showToast(it.message ?: "Could not save it there.") }
        }
    }

    /**
     * Adds one file from the phone to Downloads.
     *
     * Downloads used to be a folder only the app could fill - a URL fetch or a
     * workspace export - which made it the one place you could not simply put
     * something. The same collision question is asked here as in Files.
     */
    fun addToDownloads(uri: Uri) {
        viewModelScope.launch {
            val name = Imports.displayName(getApplication(), uri) ?: "imported"
            if (engine.downloadsHas(name)) {
                ask(
                    PendingImport(
                        name = name,
                        isFolder = false,
                        existing = File(engine.downloadsFolder, name),
                    ) { choice -> copyIntoDownloads(uri, name, choice) },
                )
                return@launch
            }
            copyIntoDownloads(uri, name, ImportChoice.KEEP_BOTH)
        }
    }

    private fun copyIntoDownloads(uri: Uri, name: String, choice: ImportChoice) {
        if (choice == ImportChoice.CANCEL) return
        viewModelScope.launch {
            _downloads.value = _downloads.value.copy(busy = true, progress = "Copying $name...")
            val staged = Imports.stageFile(getApplication(), uri)
            val result = staged.mapCatching { file ->
                engine.adoptDownload(
                    file.root.absolutePath, name, choice == ImportChoice.REPLACE,
                ).also { withContext(Dispatchers.IO) { file.root.parentFile?.deleteRecursively() } }
            }
            _downloads.value = _downloads.value.copy(busy = false, progress = "")

            result
                .onSuccess { reply ->
                    showToast(
                        if (reply.ok) "Added ${reply.name}"
                        else reply.error.ifBlank { "Could not add that file." },
                    )
                }
                .onFailure { showToast(it.message ?: "Could not read that file.") }
            refreshDownloads()
        }
    }

    fun deleteDownload(file: DownloadedFile) {
        viewModelScope.launch {
            if (engine.deleteDownload(file.path)) {
                showToast("Deleted ${file.name}")
            } else {
                showToast("Could not delete it.")
            }
            refreshDownloads()
        }
    }

    fun copyDownloadToWorkspace(file: DownloadedFile) {
        viewModelScope.launch {
            val result = engine.copyDownloadToWorkspace(file.path)
            if (result.ok) {
                showToast("Copied to the workspace")
                refreshFiles(_files.value.directory ?: workspace.root)
            } else {
                showToast(result.error.ifBlank { "Could not copy it." })
            }
        }
    }

    /** Opens a download in the editor, copying it across first. */
    fun openDownload(file: DownloadedFile) {
        viewModelScope.launch {
            val result = engine.copyDownloadToWorkspace(file.path)
            if (!result.ok) {
                showToast(result.error.ifBlank { "Could not open it." })
                return@launch
            }
            refreshFiles(_files.value.directory ?: workspace.root)
            openInEditor(File(result.path))
        }
    }

    // ------------------------------------------------------------------ toasts

    fun showToast(text: String) {
        _toast.value = Toast(text, System.currentTimeMillis())
    }

    fun consumeToast() {
        _toast.value = null
    }

    fun selectTab(tab: Tab) {
        // Measuring storage walks the whole of private storage, so it happens
        // when the screen is asked for rather than on a timer.
        if (tab == Tab.SYSTEM) refreshSystem()
        if (tab == Tab.PLUGINS) refreshCustomPlugins(reload = false)
        _tab.value = tab
        when (tab) {
            Tab.FILES -> refreshFiles(_files.value.directory ?: workspace.root)
            Tab.PACKAGES -> refreshPackages()
            Tab.SERVERS -> refreshServers()
            Tab.DOWNLOADS -> refreshDownloads()
            // A page whose server died on its own is only noticed by looking,
            // and opening the tab is when somebody is looking.
            Tab.PAGES -> refreshPages()
            // The library is small and reading it is cheap; a track deleted
            // from the notification would otherwise still be listed here.
            Tab.MUSIC -> refreshMusic()
            else -> Unit
        }
    }

    // ----------------------------------------------------------------- console

    fun runConsole(source: String) {
        val trimmed = source.trim()
        if (trimmed.isEmpty()) return
        rememberHistory(trimmed)
        viewModelScope.launch {
            engine.echo(trimmed + "\n", OutputChunk.Stream.INPUT)

            // A plugin command gets first refusal, because `todo add milk` is
            // a syntax error in Python and a sensible command everywhere else.
            // Only a bare word that a plugin actually registered qualifies, so
            // nothing a Python line can start with is ever swallowed.
            val head = trimmed.substringBefore(' ').trim()
            if (head in _pluginCommands.value && !trimmed.contains('=')) {
                val reply = engine.runPluginCommand(head, trimmed.substringAfter(' ', ""))
                if (reply.optBoolean("handled")) {
                    refreshServers()
                    return@launch
                }
            }

            engine.runConsoleLine(trimmed)
            engine.firePluginEvent("console_run", JSONObject().put("source", trimmed).toString())
            refreshServers()
        }
    }

    /**
     * A line typed into the console.
     *
     * If the app offered a fix and this is the yes or no, it answers that
     * rather than becoming input for a program - and anything else falls
     * through untouched, because a script waiting on `input()` may well want
     * the word "yes" itself.
     */
    fun submitStdin(line: String) {
        viewModelScope.launch {
            val reply = engine.answerFix(CONSOLE_CHANNEL, line)
            if (reply.optBoolean("handled")) {
                applyFixSideEffects(reply)
                return@launch
            }
            engine.submitInput(line)
        }
    }

    /** A port fix has to move the launcher form; the rest are done in Python. */
    private fun applyFixSideEffects(reply: JSONObject) {
        val port = reply.optString("port").toIntOrNull() ?: return
        _servers.value = _servers.value.copy(
            form = _servers.value.form.copy(port = port.toString()),
        )
        showToast("Launcher moved to port $port")
    }

    fun stopExecution() {
        engine.requestStop()
        showToast("Stopping...")
    }

    fun clearNamespace() {
        viewModelScope.launch { engine.resetNamespace() }
    }

    private fun rememberHistory(entry: String) {
        val current = _history.value.filterNot { it == entry }
        _history.value = (listOf(entry) + current).take(60)
    }

    suspend fun completionsFor(prefix: String): List<String> = engine.completions(prefix)

    suspend fun runtimeInfo(): Map<String, String> = engine.runtimeInfo()

    // ------------------------------------------------------------------ editor

    fun onEditorContentChanged(content: String) {
        _editor.value = _editor.value.copy(content = content)
        scheduleAutosave()
    }

    fun onCursorMoved(line: Int, column: Int) {
        _editor.value = _editor.value.copy(line = line, column = column)
    }

    fun newFile() {
        _editor.value = EditorState(file = null, content = "", savedContent = "", epoch = nextEpoch())
        _tab.value = Tab.EDITOR
    }

    private var epochCounter = 0L

    /** The pending autosave, cancelled and replaced on every keystroke. */
    private var autosaveJob: kotlinx.coroutines.Job? = null

    private fun nextEpoch(): Long = ++epochCounter

    /**
     * Opens a file the way that file wants to be opened.
     *
     * Music, video and anything else that is bytes rather than text goes to
     * the preview, which can actually play it. The editor would show it as
     * mojibake and - worse - saving that back would write the mojibake over
     * the real file, so it is not offered as a choice.
     */
    fun openInEditor(file: File) {
        viewModelScope.launch {
            val extension = "." + file.name.substringAfterLast('.', "").lowercase()
            val isMedia = languageForName(file.name)?.mode == "media"
            if (isMedia || workspace.looksBinary(file)) {
                when {
                    extension in _previewable.value -> previewFile(file)
                    isMedia -> showToast(
                        "${file.name} can be kept and served, but nothing here plays it."
                    )
                    else -> showToast("${file.name} is not text - there is nothing to edit in it.")
                }
                return@launch
            }
            workspace.read(file)
                .onSuccess { text ->
                    _editor.value = EditorState(
                        file = file,
                        content = text,
                        savedContent = text,
                        epoch = nextEpoch(),
                    )
                    _tab.value = Tab.EDITOR
                    firePlugins(
                        "file_opened",
                        JSONObject().put("path", file.absolutePath).put("name", file.name),
                    )
                }
                .onFailure { showToast(it.message ?: "Could not open the file.") }
        }
    }

    /** Saves the open buffer, asking for a name first if it has never been saved. */
    /**
     * Saves a couple of seconds after typing stops, when Autosave is on.
     *
     * Debounced rather than saving on every keystroke: writing a file per
     * character would spend the flash budget for nothing, and the point is
     * only to survive a phone call or a tab switch, not to save mid-word. A
     * file that has never been named is left alone - there is nowhere to put
     * it without asking.
     */
    private fun scheduleAutosave() {
        if (!Plugins.isOn(PluginIds.AUTOSAVE)) return
        val state = _editor.value
        if (state.file == null || !state.isDirty) return

        autosaveJob?.cancel()
        autosaveJob = viewModelScope.launch {
            delay(AUTOSAVE_DELAY_MS)
            val current = _editor.value
            val target = current.file ?: return@launch
            if (!current.isDirty) return@launch
            runCatching { workspace.write(target, current.content) }
                .onSuccess {
                    _editor.value = _editor.value.copy(savedContent = current.content)
                    DebugLog.debug(TAG_VIEW, "autosaved ${target.name}")
                    firePlugins(
                        "file_saved",
                        JSONObject().put("path", target.absolutePath).put("name", target.name),
                    )
                    _files.value.directory?.let { refreshFiles(it) }
                }
                .onFailure { error ->
                    DebugLog.error(TAG_VIEW, "autosave failed for ${target.name}", error)
                }
        }
    }

    fun saveEditor(nameIfUntitled: String? = null, onSaved: (File) -> Unit = {}) {
        val state = _editor.value
        val target = state.file ?: run {
            val name = nameIfUntitled?.trim().orEmpty().ifEmpty { "untitled.py" }
            File(_files.value.directory ?: workspace.root, if (name.endsWith(".py")) name else "$name.py")
        }
        viewModelScope.launch {
            workspace.write(target, state.content)
                .onSuccess {
                    _editor.value = state.copy(file = target, savedContent = state.content)
                    showToast("Saved ${target.name}")
                    refreshFiles(_files.value.directory ?: workspace.root)
                    firePlugins(
                        "file_saved",
                        JSONObject().put("path", target.absolutePath).put("name", target.name),
                    )
                    onSaved(target)
                }
                .onFailure { showToast(it.message ?: "Could not save.") }
        }
    }

    /** Saves first when needed, then runs the buffer as a real file. */
    fun runEditor() {
        val state = _editor.value
        val previewable = state.file != null &&
            languageForName(state.file.name)?.canPreview == true

        viewModelScope.launch {
            val file = state.file
            if (file != null && state.isDirty) {
                workspace.write(file, state.content).onFailure {
                    showToast(it.message ?: "Could not save before running.")
                    return@launch
                }
                _editor.value = _editor.value.copy(savedContent = state.content)
            }
            // Save first either way: a preview reads the file from disk, so an
            // unsaved buffer would show the previous version.
            if (previewable && file != null) {
                previewFile(file)
                return@launch
            }

            _tab.value = Tab.CONSOLE
            engine.echo("\n", OutputChunk.Stream.SYSTEM)
            if (file != null) {
                engine.echo("Running ${file.name}\n", OutputChunk.Stream.SYSTEM)
                // runAny, not runFile: the editor runs whatever the file is,
                // and calling the Python runner on a .go file would try to
                // execute Go as Python.
                engine.runAny(file.absolutePath)
            } else {
                engine.echo("Running untitled buffer\n", OutputChunk.Stream.SYSTEM)
                engine.run(state.content, sourceName = "untitled.py", echoResult = false)
            }
            refreshServers()
            refreshFiles(_files.value.directory ?: workspace.root)
        }
    }

    /** Saves the buffer if needed, then hands it to the Servers tab as a script. */
    fun runEditorAsServer() {
        val state = _editor.value
        val file = state.file
        if (file == null) {
            showToast("Save the file first, then run it as a server.")
            return
        }
        viewModelScope.launch {
            if (state.isDirty) {
                workspace.write(file, state.content).onFailure {
                    showToast(it.message ?: "Could not save before running.")
                    return@launch
                }
                _editor.value = _editor.value.copy(savedContent = state.content)
            }
            updateLaunchForm { it.copy(kind = ServerKind.SCRIPT, script = file, plan = RunPlan()) }
            _tab.value = Tab.SERVERS
            showToast("Set as the file to run - check the port, then press Run")
            refreshRunPlan(file)
        }
    }

    // ------------------------------------------------------------------- files

    /**
     * Which listing request is the newest.
     *
     * Two refreshes can be in flight at once - an import finishing while a
     * plugin asks for one, or a tap on a folder while the last one is still
     * reading - and whichever finished last used to win, however old its
     * answer was. That is one way a file list shows a folder as it used to be.
     */
    private var filesGeneration = 0L

    fun refreshFiles(directory: File) {
        val generation = ++filesGeneration
        viewModelScope.launch {
            _files.value = _files.value.copy(directory = directory, loading = true)
            val entries = workspace.list(directory)
            if (generation != filesGeneration) return@launch
            _files.value = FilesState(directory = directory, entries = entries, loading = false)
        }
    }

    fun openDirectory(directory: File) = refreshFiles(directory)

    fun navigateUp(): Boolean {
        val current = _files.value.directory ?: return false
        if (current.absolutePath == workspace.root.absolutePath) return false
        val parent = current.parentFile ?: return false
        refreshFiles(parent)
        return true
    }

    fun createFile(name: String) {
        val directory = _files.value.directory ?: workspace.root
        viewModelScope.launch {
            val fileName = if (name.endsWith(".py") || name.contains('.')) name else "$name.py"
            workspace.createFile(directory, fileName)
                .onSuccess {
                    refreshFiles(directory)
                    showToast("Created ${it.name}")
                    openInEditor(it)
                }
                .onFailure { showToast(it.message ?: "Could not create the file.") }
        }
    }

    fun createFolder(name: String) {
        val directory = _files.value.directory ?: workspace.root
        viewModelScope.launch {
            workspace.createFolder(directory, name)
                .onSuccess {
                    refreshFiles(directory)
                    showToast("Created ${it.name}/")
                }
                .onFailure { showToast(it.message ?: "Could not create the folder.") }
        }
    }

    fun renameEntry(file: File, newName: String) {
        val directory = _files.value.directory ?: workspace.root
        viewModelScope.launch {
            workspace.rename(file, newName)
                .onSuccess { renamed ->
                    if (_editor.value.file?.absolutePath == file.absolutePath) {
                        _editor.value = _editor.value.copy(file = renamed)
                    }
                    refreshFiles(directory)
                    showToast("Renamed to ${renamed.name}")
                }
                .onFailure { showToast(it.message ?: "Could not rename.") }
        }
    }

    /** Whether the bundled examples are still in the workspace. */
    val hasExamples: Boolean get() = workspace.hasExamples()

    /**
     * Puts the examples back after they were deleted.
     *
     * Deliberate, because the automatic version was the bug: an app that
     * re-creates a folder you deleted is one you cannot tidy.
     */
    fun restoreExamples() {
        viewModelScope.launch {
            val copied = workspace.restoreExamples()
            refreshFiles(_files.value.directory ?: workspace.root)
            showToast(
                if (copied > 0) "Restored $copied example files" else "The examples are already there",
            )
        }
    }

    fun deleteEntry(file: File) {
        val directory = _files.value.directory ?: workspace.root
        viewModelScope.launch {
            workspace.delete(file)
                .onSuccess {
                    if (_editor.value.file?.absolutePath == file.absolutePath) {
                        _editor.value = EditorState(
                            file = null,
                            content = "",
                            savedContent = "",
                            epoch = nextEpoch(),
                        )
                    }
                    refreshFiles(directory)
                    showToast("Deleted ${file.name}")
                }
                .onFailure { showToast(it.message ?: "Could not delete.") }
        }
    }

    /**
     * An import that would overwrite something, waiting on the user's answer.
     *
     * Not a question the app can answer for them: bringing in a corrected file
     * used to become `notes-2.md` in silence, so the old one stayed where
     * every script still pointed at it.
     */
    private val _pendingImport = MutableStateFlow<PendingImport?>(null)
    val pendingImport: StateFlow<PendingImport?> = _pendingImport.asStateFlow()

    /**
     * The questions still to be asked.
     *
     * Picking several files at once can raise several collisions, and one
     * slot would mean each new question quietly replaced the one before it -
     * so all but the last file would be dropped without a word. They queue.
     */
    private val importQueue = ArrayDeque<PendingImport>()

    private fun ask(pending: PendingImport) {
        if (_pendingImport.value == null) {
            _pendingImport.value = pending
        } else {
            importQueue.addLast(pending)
        }
    }

    /** Answers the question on screen and brings up the next one, if any. */
    fun answerPendingImport(choice: ImportChoice) {
        val current = _pendingImport.value ?: return
        _pendingImport.value = importQueue.removeFirstOrNull()
        current.decide(choice)
    }

    fun importFile(uri: Uri) {
        val directory = _files.value.directory ?: workspace.root
        val clash = workspace.collisionFor(uri, directory)
        if (clash != null) {
            ask(
                PendingImport(name = clash.name, isFolder = false, existing = clash) { choice ->
                    copyFileIn(uri, directory, choice)
                },
            )
            return
        }
        copyFileIn(uri, directory, ImportChoice.KEEP_BOTH)
    }

    private fun copyFileIn(uri: Uri, directory: File, choice: ImportChoice) {
        if (choice == ImportChoice.CANCEL) return
        viewModelScope.launch {
            val mode = if (choice == ImportChoice.REPLACE) {
                Workspace.OnCollision.REPLACE
            } else {
                Workspace.OnCollision.KEEP_BOTH
            }
            workspace.importFrom(uri, directory, mode)
                .onSuccess {
                    refreshFiles(directory)
                    showToast(
                        if (choice == ImportChoice.REPLACE) {
                            "Replaced ${it.name}"
                        } else {
                            "Imported ${it.name}"
                        },
                    )
                }
                .onFailure { showToast(it.message ?: "Could not import that file.") }
        }
    }

    /**
     * Copies a folder the user picked from outside into the workspace.
     *
     * Staged into the cache first and then moved, so a folder that turns out
     * to be enormous, or that fails halfway, leaves nothing behind in the
     * user's files.
     */
    fun importFolder(uri: Uri) {
        val directory = _files.value.directory ?: workspace.root
        showToast("Copying the folder...")
        viewModelScope.launch {
            Imports.stageTree(getApplication(), uri)
                .onSuccess { staged ->
                    val target = File(directory, staged.root.name)
                    if (!target.exists()) {
                        finishFolderImport(staged, directory, target, ImportChoice.REPLACE)
                        return@onSuccess
                    }
                    // It is already there. Copying over it with overwrite off
                    // threw partway through, leaving some new files beside some
                    // old ones - which is how "it uploaded an old version"
                    // happens. Ask instead.
                    ask(
                        PendingImport(name = target.name, isFolder = true, existing = target) {
                            choice ->
                            viewModelScope.launch {
                                finishFolderImport(staged, directory, target, choice)
                            }
                        },
                    )
                }
                .onFailure { showToast(it.message ?: "That folder could not be read.") }
        }
    }

    private suspend fun finishFolderImport(
        staged: Imports.Staged,
        directory: File,
        target: File,
        choice: ImportChoice,
    ) {
        if (choice == ImportChoice.CANCEL) {
            withContext(Dispatchers.IO) { staged.root.deleteRecursively() }
            return
        }

        val result = withContext(Dispatchers.IO) {
            runCatching {
                val destination = when (choice) {
                    ImportChoice.KEEP_BOTH -> freeName(directory, target.name)
                    ImportChoice.REPLACE -> {
                        if (target.exists() && !target.deleteRecursively()) {
                            throw IOException("Could not remove the old ${target.name}.")
                        }
                        target
                    }
                    else -> target
                }
                staged.root.copyRecursively(destination, overwrite = true)
                destination
            }.also { staged.root.deleteRecursively() }
        }

        result
            .onSuccess {
                refreshFiles(directory)
                showToast("Copied ${staged.files} files into ${it.name}")
            }
            .onFailure {
                DebugLog.error(TAG_VIEW, "folder import failed", it)
                showToast(it.message ?: "That folder could not be copied in.")
            }
    }

    /** `name`, `name-2`, `name-3`... whichever is free. */
    private fun freeName(directory: File, name: String): File {
        var candidate = File(directory, name)
        var index = 2
        while (candidate.exists() && index < 500) {
            candidate = File(directory, "$name-$index")
            index += 1
        }
        return candidate
    }

    /** The language of a file, from the catalogue already loaded. */
    fun languageForName(name: String): LanguageInfo? = _languages.value.forFileName(name)

    /**
     * Renders a previewable file.
     *
     * The base directory is handed to the WebView so a page's own stylesheet
     * and images load: a preview that shows unstyled HTML because the CSS
     * next to it could not be found is not much of a preview.
     */
    fun previewFile(file: File) {
        if (!Plugins.isOn(PluginIds.POLYGLOT_RUNNER)) {
            showToast("Turn on Polyglot Runner to preview files.")
            return
        }
        viewModelScope.launch {
            val page = engine.previewPage(file.absolutePath)
            if (page == null) {
                showToast("Could not build a preview of ${file.name}.")
                return@launch
            }
            _preview.value = page
        }
    }

    fun closePreview() {
        _preview.value = null
        // The preview server exists for the length of the preview and no
        // longer: a socket left open after the screen closes is a leak the
        // user has no way to see.
        viewModelScope.launch { engine.stopPreview() }
    }

    fun runFile(file: File) {
        // HTML, CSS, Markdown, JSON, CSV, SVG and images have nothing to
        // print; the button on those means "show me", so it opens the preview
        // rather than the console.
        val extension = file.name.substringAfterLast('.', "").lowercase()
        val previewOnly = languageForName(file.name)?.canRun != true &&
            (languageForName(file.name)?.canPreview == true || extension in _previewable.value)
        if (previewOnly) {
            previewFile(file)
            return
        }
        _tab.value = Tab.CONSOLE
        viewModelScope.launch {
            engine.echo("\n", OutputChunk.Stream.SYSTEM)
            firePlugins(
                "run_started",
                JSONObject()
                    .put("path", file.absolutePath)
                    .put("language", languageForName(file.name)?.id ?: "text"),
            )
            // runAny picks the engine from the extension: Python keeps the
            // console namespace, C, Go and Rust go through their interpreters,
            // JavaScript to the device's engine, and anything without one
            // explains itself rather than failing silently.
            val status = engine.runAny(file.absolutePath)
            firePlugins(
                "run_finished",
                JSONObject().put("path", file.absolutePath).put("status", status),
            )
            refreshServers()
        }
    }

    /** New-file creation with a starter template for the chosen type. */
    fun createFileOfType(name: String, extension: String) {
        val directory = _files.value.directory ?: workspace.root
        val fileName = if (name.contains('.') || extension.isEmpty()) name else name + extension
        viewModelScope.launch {
            workspace.createFile(directory, fileName)
                .onSuccess { created ->
                    val template = engine.templateFor(created.name)
                    if (template.isNotEmpty()) {
                        workspace.write(created, template)
                    }
                    refreshFiles(directory)
                    showToast("Created ${created.name}")
                    openInEditor(created)
                }
                .onFailure { showToast(it.message ?: "Could not create the file.") }
        }
    }

    // ---------------------------------------------------------------- packages

    private var packagesGeneration = 0L

    fun refreshPackages() {
        val generation = ++packagesGeneration
        viewModelScope.launch {
            val installed = engine.installedPackages()
            val bundled = engine.bundledPackages()
            if (generation != packagesGeneration) return@launch
            _packages.value = _packages.value.copy(installed = installed, bundled = bundled)
        }
    }

    fun installPackage(name: String, version: String?) {
        if (name.isBlank()) {
            showToast("Enter a package name.")
            return
        }
        viewModelScope.launch {
            _packages.value = _packages.value.copy(busy = true, progress = "Resolving...")
            val result = engine.installPackage(name.trim(), version) { message ->
                _packages.value = _packages.value.copy(progress = message)
            }
            _packages.value = _packages.value.copy(busy = false, progress = "")
            if (result.ok) {
                showToast("Installed ${result.name} ${result.version}")
                refreshPackages()
            } else {
                showToast(result.error.ifBlank { "Install failed." })
            }
        }
    }

    /** Asks PyPI what a package is, without installing it. */
    fun lookUpPackage(name: String) {
        val wanted = name.trim().substringBefore("==")
        if (wanted.isBlank()) return
        viewModelScope.launch {
            _packages.value = _packages.value.copy(looking = true, lookup = null)
            val reply = engine.packageInfo(wanted)
            val found = if (reply.optBoolean("ok")) {
                PackageLookup(
                    name = reply.optString("name", wanted),
                    version = reply.optString("version"),
                    summary = reply.optString("summary"),
                    installable = reply.optBoolean("installable"),
                    whyNot = reply.optString("why_not"),
                    requiresPython = reply.optString("requires_python"),
                    sizeBytes = reply.optLong("size"),
                    versions = reply.optJSONArray("versions")?.let { array ->
                        (0 until array.length()).map { array.optString(it) }
                    }.orEmpty(),
                )
            } else {
                null
            }
            _packages.value = _packages.value.copy(looking = false, lookup = found)
            if (found == null) showToast(reply.optString("error", "Could not reach PyPI."))
        }
    }

    fun clearPackageLookup() {
        _packages.value = _packages.value.copy(lookup = null)
    }

    fun uninstallPackage(name: String) {
        viewModelScope.launch {
            _packages.value = _packages.value.copy(busy = true, progress = "Removing $name...")
            val result = engine.uninstallPackage(name)
            _packages.value = _packages.value.copy(busy = false, progress = "")
            if (result.ok) {
                showToast("Removed $name")
                refreshPackages()
            } else {
                showToast(result.error.ifBlank { "Could not remove $name." })
            }
        }
    }

    // ------------------------------------------------------------------- pages

    private var pagesGeneration = 0L

    /** Reads the registry and what is listening, and puts them together. */
    fun refreshPages() {
        val generation = ++pagesGeneration
        viewModelScope.launch {
            val rows = engine.pages()
            val counts = engine.pageCounts()
            val templates = engine.pageTemplates()
            val choices = engine.pageFolders()
            val cloud = engine.cloudflareState()
            if (generation != pagesGeneration) return@launch
            _pages.value = _pages.value.copy(
                projects = (0 until rows.length()).mapNotNull { index ->
                    rows.optJSONObject(index)?.let(::readPage)
                },
                templates = (0 until templates.length()).mapNotNull { index ->
                    templates.optJSONObject(index)?.let { row ->
                        PageTemplate(
                            id = row.optString("id"),
                            title = row.optString("title"),
                            about = row.optString("about"),
                        )
                    }
                },
                folders = choices.rows().map { row ->
                    WorkspaceFolder(
                        path = row.optString("path"),
                        name = row.optString("name"),
                        relative = row.optString("relative"),
                        files = row.optInt("files"),
                        bytes = row.optLong("bytes"),
                        taken = row.optBoolean("taken"),
                    )
                },
                used = counts.optInt("projects"),
                maxProjects = counts.optInt("max_projects", 70),
                active = counts.optInt("active"),
                maxActive = counts.optInt("max_active", 25),
                cloudflare = _pages.value.cloudflare.copy(
                    connected = cloud.optBoolean("connected"),
                    account = cloud.optString("account"),
                    tokenTail = cloud.optString("token_tail"),
                ),
            )
        }
    }

    private fun readPage(row: JSONObject) = PageProject(
        id = row.optString("id"),
        name = row.optString("name"),
        folder = row.optString("folder"),
        template = row.optString("template"),
        port = row.optInt("port"),
        running = row.optBoolean("running"),
        url = row.optString("url"),
        publicUrl = row.optString("public_url"),
        requests = row.optInt("requests"),
        files = row.optInt("files"),
        bytes = row.optLong("bytes"),
        host = row.optString("host", "local"),
        deployedUrl = row.optString("deployed_url"),
        exists = row.optBoolean("exists", true),
    )

    private fun pagesBusy(what: String) {
        _pages.value = _pages.value.copy(busy = what)
    }

    /**
     * Runs one page action, keeping the card honest while it happens.
     *
     * Every one of these ends the same way - say what happened, read the list
     * back - so they share a body rather than repeating it eight times.
     */
    private fun pageAction(busy: String, success: (JSONObject) -> String,
                           block: suspend () -> JSONObject) {
        viewModelScope.launch {
            pagesBusy(busy)
            val reply = block()
            pagesBusy("")
            if (reply.optBoolean("ok")) {
                val said = success(reply)
                if (said.isNotEmpty()) showToast(said)
            } else {
                showToast(reply.optString("error", "That did not work."))
            }
            refreshPages()
            refreshServers()
        }
    }

    fun createPage(name: String, template: String) {
        pageAction("Making $name...", { "$name is ready" }) {
            engine.createPage(name, template)
        }
    }

    /**
     * Points a page at a folder somebody picked out of the workspace.
     *
     * This is how a page is normally made now. The app inventing a folder was
     * the old way and is still there behind "start from a template", but a
     * page is usually something you already have.
     */
    fun adoptPage(folder: WorkspaceFolder, name: String) {
        val title = name.trim().ifBlank { folder.name }
        pageAction("Adding $title...", { "$title is a page now" }) {
            engine.adoptPage(title, folder.path)
        }
    }

    fun renamePage(id: String, name: String) {
        pageAction("Renaming...", { "Renamed to $name" }) { engine.renamePage(id, name) }
    }

    fun removePage(id: String, deleteFiles: Boolean) {
        pageAction("Removing...", { reply ->
            val name = reply.optString("name", "the page")
            if (reply.optBoolean("files_deleted")) "$name and its files are gone" else "$name removed"
        }) { engine.removePage(id, deleteFiles) }
    }

    fun startPage(id: String) {
        pageAction("Starting...", { reply ->
            if (reply.optBoolean("already")) "" else "Running on ${reply.optString("url")}"
        }) { engine.startPage(id) }
    }

    fun stopPage(id: String) {
        pageAction("Stopping...", { "" }) { engine.stopPage(id) }
    }

    fun stopAllPages() {
        pageAction("Stopping everything...", { reply ->
            "Stopped ${reply.optInt("stopped")}"
        }) { engine.stopAllPages() }
    }

    /** Opens a tunnel, so the page has an address off this network. */
    fun sharePage(id: String) {
        pageAction("Asking for a public address...", { reply ->
            "Public at ${reply.optString("url")}"
        }) { engine.sharePage(id) }
    }

    fun unsharePage(id: String) {
        pageAction("Closing the tunnel...", { "It is off the internet again" }) {
            engine.unsharePage(id)
        }
    }

    fun setPageHost(id: String, host: String) {
        pageAction("", { "" }) { engine.setPageHost(id, host) }
    }

    /** Shows a page's folder in the Files tab, where it can be edited. */
    fun openPageFolder(page: PageProject) {
        val folder = File(page.folder)
        if (!folder.isDirectory) {
            showToast("Its folder is not there any more.")
            return
        }
        openDirectory(folder)
        selectTab(Tab.FILES)
    }

    /**
     * Opens a running page in the preview, at its own address.
     *
     * Its address rather than its files: a Flask page has no index.html to
     * render, and the whole point of a page being *up* is that something is
     * answering on a port.
     */
    fun openPage(page: PageProject) {
        if (!page.running || page.url.isBlank()) {
            showToast("Start it first.")
            return
        }
        _preview.value = PreviewPage(
            name = page.name,
            html = "",
            baseDirectory = "",
            url = page.url,
            served = true,
        )
    }

    // ---- Music ------------------------------------------------------------

    /**
     * The player, which is not in this process's control at all.
     *
     * It lives in a media session in a service, so the sound carries on when
     * this view model, this screen and the whole activity have gone. What is
     * here is a controller pointed at it, and a library that says what there
     * is to play.
     */
    private val hub = MusicHub(application).also { live ->
        live.onChanged = { state -> rememberPlayback(state) }
    }

    /**
     * The DJ decks, and whatever else on this phone is making a noise.
     *
     * Both are driven by Music Pro's panel through the plugin action channel
     * rather than by a screen in this app, because both are that plugin's
     * whole reason to exist. They are made here because they need the
     * application context and have to outlive the panel being scrolled away.
     */
    private val mixer = MixerHub(application).also { desk ->
        desk.onChanged = { state -> tellMixerState(state) }
    }

    private val neighbours = Neighbours(application)

    /** The last mixer state sent to the plugin, so identical ones are dropped. */
    private var lastMixerState = ""

    private fun tellMixerState(state: JSONObject) {
        val text = state.toString()
        if (text == lastMixerState) return
        lastMixerState = text
        viewModelScope.launch { engine.firePluginEvent("mixer_state", text) }
    }

    val playback: StateFlow<Playback> = hub.playback

    private val _music = MutableStateFlow(MusicState())
    val music: StateFlow<MusicState> = _music.asStateFlow()

    /** The last thing written down, so a pause does not rewrite the file. */
    private var lastRemembered = ""

    private var musicLoaded = false

    /** Reads the library back. Cheap; the registry is one small JSON file. */
    fun refreshMusic() {
        viewModelScope.launch {
            val reply = engine.musicLibrary()
            if (!reply.has("tracks")) return@launch

            val tracks = reply.optJSONArray("tracks").rows().map(::readTrack)
            val playlists = reply.optJSONArray("playlists").rows().map { row ->
                MusicPlaylist(
                    id = row.optString("id"),
                    name = row.optString("name"),
                    trackIds = row.optJSONArray("tracks").strings(),
                    count = row.optInt("count"),
                    duration = row.optLong("duration"),
                    bytes = row.optLong("bytes"),
                    preview = row.optString("preview"),
                )
            }
            val limits = reply.optJSONObject("limits") ?: JSONObject()
            val open = _music.value.openPlaylist
                .takeIf { id -> playlists.any { it.id == id } }
                .orEmpty()

            _music.value = _music.value.copy(
                tracks = tracks,
                playlists = playlists,
                openPlaylist = open,
                bytes = reply.optLong("bytes"),
                missing = reply.optInt("missing"),
                maxTracks = limits.optInt("tracks", 2000),
                maxPlaylists = limits.optInt("playlists", 200),
            )

            // Once per run: put back the loop and shuffle somebody chose, and
            // connect to the player so the notification's buttons and this
            // screen agree with each other from the first frame.
            if (!musicLoaded && tracks.isNotEmpty()) {
                musicLoaded = true
                val state = reply.optJSONObject("state") ?: JSONObject()
                // Only once there is music to play: binding the media service
                // on a phone with an empty library would put a player in the
                // notification shade of somebody who never opened this tab.
                hub.connect()
                hub.setLoop(state.optString("loop", "off"))
                hub.setShuffle(state.optBoolean("shuffle"))
                val speed = state.optDouble("speed", 1.0)
                _music.value = _music.value.copy(speed = speed)
                hub.setSpeed(speed.toFloat())
            }

            refreshMusicView()
            refreshMusicNumbers()
        }
    }

    /**
     * Asks Python for the list as it should be shown.
     *
     * Every narrowing - the search, the sort, the smart list, the open
     * playlist - is decided in one place so that the order on screen and the
     * order handed to the player cannot disagree.
     */
    fun refreshMusicView() {
        viewModelScope.launch {
            val here = _music.value
            val reply = engine.browseMusic(
                here.search, here.sort, here.openPlaylist, here.collection,
            )
            if (!reply.optBoolean("ok")) {
                // A collection or playlist that has gone: fall back to the
                // whole library rather than showing an empty screen with no
                // way to explain itself.
                _music.value = _music.value.copy(collection = "", shown = emptyList())
                return@launch
            }
            _music.value = _music.value.copy(
                shown = reply.optJSONArray("tracks").rows().map(::readTrack),
            )
        }
    }

    private fun refreshMusicNumbers() {
        viewModelScope.launch {
            val chips = engine.musicCollections()
            val numbers = engine.musicStats()
            _music.value = _music.value.copy(
                collections = chips.optJSONArray("collections").rows().map { row ->
                    MusicCollection(
                        id = row.optString("id"),
                        name = row.optString("name"),
                        count = row.optInt("count"),
                    )
                },
                numbers = MusicNumbers(
                    tracks = numbers.optInt("tracks"),
                    playlists = numbers.optInt("playlists"),
                    bytes = numbers.optLong("bytes"),
                    duration = numbers.optLong("duration"),
                    plays = numbers.optInt("plays"),
                    artists = numbers.optInt("artists"),
                    topArtist = numbers.optString("top_artist"),
                    videos = numbers.optInt("videos"),
                    neverPlayed = numbers.optInt("never_played"),
                ),
            )
        }
    }

    /** Types into the search box. Nothing is stored; this is a view. */
    fun searchMusic(text: String) {
        _music.value = _music.value.copy(search = text)
        refreshMusicView()
    }

    fun sortMusic(sort: String) {
        _music.value = _music.value.copy(sort = sort)
        refreshMusicView()
    }

    /** Opens a smart list, or closes the one that is open by naming it again. */
    fun showCollection(id: String) {
        val wanted = if (_music.value.collection == id) "" else id
        _music.value = _music.value.copy(collection = wanted, openPlaylist = "")
        refreshMusicView()
    }

    /** How fast to play. Half to double; the player clamps it too. */
    fun setMusicSpeed(speed: Double) {
        val wanted = speed.coerceIn(0.5, 2.0)
        _music.value = _music.value.copy(speed = wanted)
        hub.setSpeed(wanted.toFloat())
        viewModelScope.launch {
            engine.rememberMusic(
                playback.value.loop, playback.value.shuffle, playback.value.trackId,
                _music.value.openPlaylist, wanted, _music.value.sleepMinutes,
            )
        }
    }

    /** Stops the music in so many minutes. Zero cancels it. */
    fun setSleepTimer(minutes: Int) {
        val wanted = minutes.coerceIn(0, 600)
        _music.value = _music.value.copy(sleepMinutes = wanted)
        hub.sleepAfter(wanted)
        viewModelScope.launch {
            engine.rememberMusic(
                playback.value.loop, playback.value.shuffle, playback.value.trackId,
                _music.value.openPlaylist, _music.value.speed, wanted,
            )
        }
    }

    /** Opens the sheet that shows everything about one track. */
    fun openTrackDetail(trackId: String) {
        viewModelScope.launch {
            val reply = engine.describeTrack(trackId)
            if (!reply.optBoolean("ok")) {
                showToast(reply.optString("error", "That track is not there any more."))
                return@launch
            }
            _music.value = _music.value.copy(
                detail = readTrack(reply.optJSONObject("track") ?: JSONObject()),
                detailPlaylists = reply.optJSONArray("playlists").strings(),
            )
        }
    }

    fun closeTrackDetail() {
        _music.value = _music.value.copy(detail = null, detailPlaylists = emptyList())
    }

    /** Corrects what a track says it is. A blank field is left alone. */
    fun setTrackDetails(trackId: String, title: String, artist: String, album: String) {
        musicAction("Saving", { "Saved." }) {
            engine.setTrackDetails(trackId, title, artist, album)
        }
        closeTrackDetail()
    }

    private fun readTrack(row: JSONObject) = MusicTrack(
        id = row.optString("id"),
        title = row.optString("title"),
        artist = row.optString("artist"),
        file = row.optString("file"),
        bytes = row.optLong("bytes"),
        duration = row.optLong("duration"),
        added = row.optLong("added"),
        video = row.optBoolean("video"),
        missing = row.optBoolean("missing"),
        album = row.optString("album"),
        plays = row.optInt("plays"),
        lastPlayed = row.optLong("last_played"),
    )

    /**
     * Writes down the loop, the shuffle and what is playing - but only when
     * one of them actually changed.
     *
     * The player reports an event for every pause and every resume, and
     * rewriting the library on each one would be a file write per tap.
     */
    private fun rememberPlayback(state: Playback) {
        countIfListened(state)

        val key = "${state.loop}|${state.shuffle}|${state.trackId}"
        if (key == lastRemembered) return
        lastRemembered = key
        viewModelScope.launch {
            engine.rememberMusic(
                state.loop,
                state.shuffle,
                state.trackId,
                _music.value.openPlaylist,
                _music.value.speed,
                _music.value.sleepMinutes,
            )
        }
    }

    /** The track a play is being counted for, and whether it has been. */
    private var countingTrack = ""
    private var counted = false

    /**
     * Counts a play once the track has actually been listened to.
     *
     * "Played" has to mean something, or the most-played list is a list of
     * whatever was skipped past most. Thirty seconds is the line the streaming
     * services draw and it is a reasonable one; anything shorter than a minute
     * counts at halfway instead, so a twenty-second clip is not unplayable.
     *
     * The position comes from the player rather than from a timer here, so
     * pausing does not count and seeking to the end does not either - the
     * check is on where the playhead is, not how long the screen has been up.
     */
    private fun countIfListened(state: Playback) {
        if (state.trackId != countingTrack) {
            countingTrack = state.trackId
            counted = false
        }
        if (counted || state.trackId.isEmpty() || !state.playing) return

        val enough = if (state.duration in 1 until 60_000) {
            state.duration / 2
        } else {
            30_000L
        }
        if (state.position < enough) return

        counted = true
        val id = state.trackId
        viewModelScope.launch {
            engine.countPlay(id)
            refreshMusicNumbers()
        }
    }

    private fun musicBusy(what: String) {
        _music.value = _music.value.copy(busy = what)
    }

    /**
     * Runs one library action and reads the library back afterwards.
     *
     * Same shape as the Pages tab's, and for the same reason: every one of
     * these ends by saying what happened and refreshing the list.
     */
    private fun musicAction(busy: String, success: (JSONObject) -> String,
                            block: suspend () -> JSONObject) {
        viewModelScope.launch {
            musicBusy(busy)
            val reply = block()
            musicBusy("")
            if (reply.optBoolean("ok")) {
                val said = success(reply)
                if (said.isNotEmpty()) showToast(said)
            } else {
                showToast(reply.optString("error", "That did not work."))
            }
            refreshMusic()
        }
    }

    /**
     * Copies picked files into the library, one at a time.
     *
     * Sequentially rather than at once: these are large files on a phone's
     * flash, and three copies racing each other is slower than three in a row
     * as well as being impossible to report progress for.
     */
    fun importMusic(uris: List<Uri>) {
        if (uris.isEmpty()) return
        if (!engineStatus.value.ready) {
            // The library folder is decided while the interpreter starts, so
            // there is nowhere to copy to before that has happened.
            showToast("The interpreter is still starting - try again in a moment.")
            return
        }
        viewModelScope.launch {
            _music.value = _music.value.copy(importing = true)
            var added = 0
            var failed = ""
            for ((index, uri) in uris.withIndex()) {
                musicBusy("Importing ${index + 1} of ${uris.size}...")
                val copied = MusicImport.copy(getApplication<Application>(), uri, engine.musicFolder)
                    .getOrElse { error ->
                        failed = error.message ?: "that file could not be copied"
                        DebugLog.warn(TAG_VIEW, "an import failed", failed)
                        null
                    } ?: continue

                val reply = engine.adoptTrack(
                    copied.file.absolutePath,
                    copied.title,
                    copied.artist,
                    copied.duration,
                )
                if (reply.optBoolean("ok")) {
                    added += 1
                } else {
                    // The library would not take it, so the copy is dead
                    // weight: nothing can ever reach it again.
                    copied.file.delete()
                    failed = reply.optString("error", "that file was not taken")
                }
            }
            musicBusy("")
            _music.value = _music.value.copy(importing = false)
            showToast(
                when {
                    added > 0 && failed.isEmpty() -> "Added $added"
                    added > 0 -> "Added $added, and one did not: $failed"
                    failed.isNotEmpty() -> failed.replaceFirstChar { it.uppercase() }
                    else -> "Nothing was added."
                },
            )
            refreshMusic()
        }
    }

    /** Plays the list the screen is showing, starting at [track]. */
    fun playTrack(track: MusicTrack) {
        if (track.missing) {
            showToast("That file is not on the phone any more.")
            return
        }
        val visible = _music.value.visible
        val index = visible.indexOfFirst { it.id == track.id }.coerceAtLeast(0)
        hub.play(visible, index, _music.value.current?.name ?: "Everything")
    }

    /** Plays a playlist from the top, and opens it while it is at it. */
    fun playPlaylist(playlist: MusicPlaylist) {
        val byId = _music.value.tracks.associateBy { it.id }
        val tracks = playlist.trackIds.mapNotNull { byId[it] }.filterNot { it.missing }
        if (tracks.isEmpty()) {
            showToast("There is nothing in ${playlist.name} to play.")
            return
        }
        _music.value = _music.value.copy(openPlaylist = playlist.id)
        hub.play(tracks, 0, playlist.name)
    }

    /**
     * Plays the whole library, whatever the screen happens to be showing.
     *
     * The button is on the library card rather than the playlist one, so it
     * means the library: a playlist has its own play button, and having both
     * do the same thing would leave no way to say "all of it".
     */
    fun playEverything() {
        val tracks = _music.value.tracks.filterNot { it.missing }
        if (tracks.isEmpty()) {
            showToast("Import something first.")
            return
        }
        hub.play(tracks, 0, "Everything")
    }

    fun togglePlayback() = hub.toggle()

    fun skipNext() = hub.next()

    fun skipPrevious() = hub.previous()

    fun seekMusic(millis: Long) = hub.seekTo(millis)

    fun stopMusic() = hub.stop()

    /** Off, then all, then one, then off again - one button, three states. */
    fun cycleLoop() {
        hub.setLoop(
            when (playback.value.loop) {
                "off" -> "all"
                "all" -> "one"
                else -> "off"
            },
        )
    }

    fun toggleShuffle() = hub.setShuffle(!playback.value.shuffle)

    fun openPlaylist(id: String) {
        // Opening a playlist puts away whichever smart list was showing:
        // "the most played, inside Evening" is a thing nobody meant to ask
        // for and a screen that showed it would be lying about both.
        _music.value = _music.value.copy(openPlaylist = id, collection = "")
        refreshMusicView()
    }

    fun renameTrack(id: String, title: String) {
        musicAction("Renaming...", { "Renamed to $title" }) { engine.renameTrack(id, title) }
    }

    fun removeTrack(track: MusicTrack) {
        // Out of the player first: deleting the file under a playing track is
        // how a music app ends up making a noise it cannot stop.
        hub.forget(track.id)
        musicAction("Deleting...", { reply ->
            "${reply.optString("title", "It")} is gone"
        }) { engine.removeTrack(track.id) }
    }

    fun createPlaylist(name: String) {
        musicAction("Making $name...", { "$name is ready" }) { engine.createPlaylist(name) }
    }

    fun renamePlaylist(id: String, name: String) {
        musicAction("Renaming...", { "Renamed to $name" }) { engine.renamePlaylist(id, name) }
    }

    fun removePlaylist(playlist: MusicPlaylist) {
        if (_music.value.openPlaylist == playlist.id) {
            _music.value = _music.value.copy(openPlaylist = "")
        }
        musicAction("Removing...", { "${playlist.name} is gone - the tracks stayed" }) {
            engine.removePlaylist(playlist.id)
        }
    }

    fun addToPlaylist(playlistId: String, trackId: String) {
        musicAction("Adding...", { reply ->
            if (reply.optInt("added") > 0) "Added" else "It is already in there"
        }) { engine.addToPlaylist(playlistId, trackId) }
    }

    fun removeFromPlaylist(playlistId: String, trackId: String) {
        musicAction("Removing...", { "Taken out" }) {
            engine.removeFromPlaylist(playlistId, trackId)
        }
    }

    fun moveInPlaylist(playlistId: String, trackId: String, delta: Int) {
        musicAction("", { "" }) { engine.moveInPlaylist(playlistId, trackId, delta) }
    }

    /** Clears out rows with no file and files with no row. */
    fun tidyMusic() {
        musicAction("Tidying...", { reply ->
            val dropped = reply.optInt("dropped")
            val orphans = reply.optInt("orphans")
            if (dropped == 0 && orphans == 0) {
                "Nothing to tidy"
            } else {
                "Dropped $dropped, freed ${orphans} stray file(s)"
            }
        }) { engine.tidyMusic() }
    }

    // ---- Cloudflare --------------------------------------------------------

    private fun cloudflareBusy(what: String) {
        _pages.value = _pages.value.copy(
            cloudflare = _pages.value.cloudflare.copy(busy = what),
        )
    }

    fun connectCloudflare(account: String, token: String) {
        viewModelScope.launch {
            cloudflareBusy("Checking the token...")
            val reply = engine.connectCloudflare(account.trim(), token.trim())
            cloudflareBusy("")
            if (reply.optBoolean("ok")) {
                showToast("Connected to Cloudflare")
            } else {
                showToast(reply.optString("error", "Cloudflare would not take that."))
            }
            refreshPages()
        }
    }

    fun forgetCloudflare() {
        viewModelScope.launch {
            engine.forgetCloudflare()
            showToast("The token is off this device")
            refreshPages()
        }
    }

    /**
     * Uploads a page to Cloudflare Pages.
     *
     * Minutes of network on a phone connection, so the card carries the
     * progress the deploy reports rather than a spinner that says nothing.
     */
    /**
     * Sends a page to Cloudflare - from a copy, not from the live folder.
     *
     * The copy is made first, in the page's own storage outside the workspace,
     * so what went up is a thing that still exists afterwards and can be
     * looked at. Uploading straight out of the workspace means uploading
     * whatever each file happened to contain at the moment the upload reached
     * it, which is not something anybody can reason about later.
     */
    fun deployPage(page: PageProject) {
        viewModelScope.launch {
            cloudflareBusy("Packing ${page.name}...")
            val staged = engine.stagePage(page.id)
            if (!staged.optBoolean("ok")) {
                cloudflareBusy("")
                showToast(staged.optString("error", "That folder could not be packed."))
                return@launch
            }
            val folder = staged.optString("folder")
            val files = staged.optInt("files")
            val bytes = staged.optLong("bytes")

            cloudflareBusy("Deploying ${page.name} - $files file(s)...")
            val reply = engine.deployToCloudflare(folder, page.name) { message ->
                cloudflareBusy(message)
            }
            cloudflareBusy("")
            if (reply.optBoolean("ok")) {
                val url = reply.optString("url")
                engine.notePageDeployment(page.id, url, reply.optString("project"), files, bytes)
                showToast("Live at $url")
            } else {
                showToast(reply.optString("error", "The deploy did not finish."))
            }
            refreshPages()
        }
    }

    /** Throws away a page's build copy, keeping its deployment history. */
    fun clearPageBuild(page: PageProject) {
        pageAction("Clearing...", { reply ->
            "Freed ${readableSize(reply.optLong("freed"))}"
        }) { engine.clearPageBuild(page.id) }
    }

    // ----------------------------------------------------------------- servers

    private var serversGeneration = 0L

    fun refreshServers() {
        val generation = ++serversGeneration
        viewModelScope.launch {
            val list = engine.listServers()
            val address = engine.localIp()
            // The Servers tab polls every three seconds and other things ask
            // for a refresh too; an older answer arriving late would show a
            // server that has already stopped.
            if (generation != serversGeneration) return@launch
            _servers.value = _servers.value.copy(servers = list, localIp = address)
            syncForegroundService(list)
        }
    }

    fun updateLaunchForm(transform: (LaunchForm) -> LaunchForm) {
        val before = _servers.value.form
        val after = transform(before)
        _servers.value = _servers.value.copy(form = after)
        // The plan describes whatever the form points at now, in either mode.
        // A folder in "serve" mode has one too: it is how the form can say
        // there is an app.py in there before serving a list of files instead.
        val target = after.target
        if (target != null && (target != before.target || after.kind != before.kind)) {
            refreshRunPlan(target)
        }
    }

    /** Fills the form's port with the first one actually free. */
    fun suggestPort() {
        viewModelScope.launch {
            val from = _servers.value.form.portNumber ?: 8000
            val free = engine.suggestPort(from)
            updateLaunchForm { it.copy(port = free.toString()) }
            if (free != from) showToast("Port $from is taken; using $free")
        }
    }

    /** Sends the user to Files to choose the folder or script to launch. */
    fun pickLaunchTarget() {
        _pickingFor.value = _servers.value.form.kind
        _tab.value = Tab.FILES
        showToast(
            if (_servers.value.form.kind == ServerKind.STATIC) {
                "Open the folder to serve, then tap Use this folder"
            } else {
                "Tap the script to run"
            },
        )
    }

    private val _pickingFor = MutableStateFlow<ServerKind?>(null)
    val pickingFor: StateFlow<ServerKind?> = _pickingFor.asStateFlow()

    fun cancelPicking() {
        _pickingFor.value = null
    }

    /** Called from Files when the user confirms a target for the launch form. */
    fun useAsLaunchTarget(file: File) {
        val kind = _pickingFor.value ?: return
        _pickingFor.value = null
        updateLaunchForm { form ->
            if (kind == ServerKind.STATIC) {
                form.copy(kind = ServerKind.STATIC, folder = file)
            } else {
                form.copy(kind = ServerKind.SCRIPT, script = file, plan = RunPlan())
            }
        }
        _tab.value = Tab.SERVERS
        showToast("Selected ${file.name}")
        if (kind == ServerKind.SCRIPT) refreshRunPlan(file)
    }

    /**
     * Asks what starting this target would do, and puts the answer in the form.
     *
     * The Servers tab used to run Python and nothing else, so there was
     * nothing to say. Now a page is served, a Go file is interpreted, a plugin
     * may claim a type of its own, and a folder is looked into for the file
     * that is actually its front door - so the form says which it will be
     * before anything starts, and refuses up front what cannot run at all.
     */
    private fun refreshRunPlan(file: File) {
        viewModelScope.launch {
            val plan = engine.howToRun(file.absolutePath)
            updateLaunchForm { form ->
                // Only if the form is still pointing where it was: choosing
                // twice quickly must not label the second choice with the
                // first one's answer.
                if (form.target?.absolutePath == file.absolutePath) form.copy(plan = plan) else form
            }
        }
    }

    fun launchServer() {
        val form = _servers.value.form
        val problem = form.problem()
        if (problem != null) {
            showToast(problem)
            return
        }
        val target = form.target ?: return
        val host = if (form.exposeToNetwork) "0.0.0.0" else "127.0.0.1"
        val port = form.portNumber ?: 0

        viewModelScope.launch {
            _servers.value = _servers.value.copy(busy = true)
            val result = when (form.kind) {
                ServerKind.STATIC -> engine.startStaticServer(
                    directory = target.absolutePath,
                    port = port,
                    host = host,
                    label = form.label.trim(),
                    logRequests = form.logRequests,
                )

                ServerKind.SCRIPT -> engine.startFileServer(
                    path = target.absolutePath,
                    port = port,
                    host = host,
                    label = form.label.trim(),
                )
            }
            _servers.value = _servers.value.copy(busy = false)
            if (result.ok) {
                showToast(if (result.url.isNotBlank()) "Started - ${result.url}" else "Started ${target.name}")
                // Drop straight into the new server's console: that is where
                // its output and any startup failure will show up.
                _servers.value = _servers.value.copy(openConsole = result.handle.ifBlank { null })
                firePlugins(
                    "server_started",
                    JSONObject()
                        .put("handle", result.handle)
                        .put("port", port)
                        .put("kind", form.kind.name.lowercase()),
                )
            } else {
                showToast(result.error.ifBlank { "Could not start." })
            }
            refreshServers()
        }
    }

    /**
     * Opens a running server in the preview.
     *
     * The preview is already a browser view of a loopback address, so a server
     * is exactly the kind of thing it exists for - and reading the address off
     * the card to type it somewhere else was the only way to look at your own
     * server from inside the app.
     */
    fun viewServer(server: RunningServer) {
        val url = server.url
        if (url.isBlank()) {
            showToast("That server has no address to open.")
            return
        }
        _preview.value = PreviewPage(
            name = server.label.ifBlank { "Server" },
            html = "",
            baseDirectory = "",
            url = url,
            served = true,
        )
    }

    fun openServerConsole(handle: String) {
        _servers.value = _servers.value.copy(openConsole = handle)
        if (_serverConsoles.value[handle].isNullOrEmpty()) {
            // Only as a safety net. The live collector has been capturing this
            // channel since the process started, and for a script server it
            // holds more than Python's own log does - a script's print() goes
            // straight through the output sink and never reaches that log - so
            // replaying over a populated buffer would lose output, not restore it.
            viewModelScope.launch {
                val existing = engine.serverLog(handle)
                if (existing.isNotEmpty() && _serverConsoles.value[handle].isNullOrEmpty()) {
                    _serverConsoles.value =
                        _serverConsoles.value + (handle to existing.takeLast(CONSOLE_LIMIT))
                }
            }
        }
    }

    fun closeServerConsole() {
        _servers.value = _servers.value.copy(openConsole = null)
    }

    fun submitServerInput(handle: String, line: String) {
        viewModelScope.launch {
            val reply = engine.answerFix(handle, line)
            if (reply.optBoolean("handled")) {
                applyFixSideEffects(reply)
                return@launch
            }
            engine.submitInput(line, handle)
        }
    }

    fun clearServerConsole(handle: String) {
        _serverConsoles.value = _serverConsoles.value + (handle to emptyList())
    }

    fun stopServer(handle: String) {
        viewModelScope.launch {
            val result = engine.stopServer(handle)
            if (!result.ok) {
                showToast(
                    if (result.needsKill) {
                        "It would not stop. Use Kill to force it."
                    } else {
                        result.error.ifBlank { "Could not stop." }
                    },
                )
            } else {
                showToast("Stopped")
                firePlugins("server_stopped", JSONObject().put("handle", handle))
            }
            refreshServers()
        }
    }

    fun killServer(handle: String) {
        viewModelScope.launch {
            val result = engine.killServer(handle)
            when {
                !result.ok -> showToast(result.error.ifBlank { "Could not kill." })
                result.detached -> showToast("Killed. The port is free; the thread is finishing a blocking call.")
                else -> showToast("Killed")
            }
            refreshServers()
        }
    }

    fun stopAllServers() {
        viewModelScope.launch {
            val stopped = engine.stopAllServers()
            showToast(if (stopped > 0) "Stopped $stopped server(s)" else "Nothing was running")
            refreshServers()
        }
    }

    fun killAllServers() {
        viewModelScope.launch {
            val killed = engine.killAllServers()
            showToast(if (killed > 0) "Killed $killed server(s)" else "Nothing was running")
            refreshServers()
        }
    }

    // ------------------------------------------------------------------- debug

    fun clearDebugLog() {
        DebugLog.clear()
        DebugLog.info("debug", "log cleared")
    }

    fun debugLogText(): String = DebugLog.exportText()

    /** Writes the debug log into the workspace so it can be shared or kept. */
    fun saveDebugLog() {
        viewModelScope.launch {
            val name = "debug-" + System.currentTimeMillis() + ".log"
            val target = File(workspace.root, name)
            workspace.write(target, DebugLog.exportText())
                .onSuccess {
                    showToast("Saved $name to the workspace")
                    refreshFiles(_files.value.directory ?: workspace.root)
                }
                .onFailure { showToast(it.message ?: "Could not save the log.") }
        }
    }

    /** Last summary handed to the service, so an unchanged state is left alone. */
    private var serviceSummary: String? = null

    /**
     * The notification exists exactly while something is listening.
     *
     * refreshServers() runs often, so this only touches the service when the
     * state it would show actually changed.
     */
    private fun syncForegroundService(list: List<RunningServer>) {
        val running = list.count { it.status == "running" }
        val context = getApplication<Application>()
        if (running > 0) {
            val summary = if (running == 1) {
                list.firstOrNull { it.status == "running" }?.let { server ->
                    if (server.url.isNotBlank()) "${server.label} - ${server.url}" else server.label
                } ?: "1 server running"
            } else {
                "$running servers running"
            }
            if (summary != serviceSummary) {
                serviceSummary = summary
                ServerService.start(context, summary)
            }
        } else if (serviceSummary != null) {
            serviceSummary = null
            ServerService.stop(context)
        }
    }
}
