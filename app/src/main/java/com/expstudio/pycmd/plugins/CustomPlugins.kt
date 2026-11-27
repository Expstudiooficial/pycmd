package com.expstudio.pycmd.plugins

import android.content.Context
import android.content.SharedPreferences
import com.expstudio.pycmd.util.DebugLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

/**
 * One plugin the user installed themselves.
 *
 * Everything here comes from the plugin's own manifest, which means every
 * field is text somebody else wrote. It is shown, never trusted: the UI treats
 * a name as a label and nothing more.
 */
data class InstalledPlugin(
    val id: String,
    val name: String,
    val version: String,
    val author: String,
    val description: String,
    val panel: String?,
    val tabTitle: String?,
    /** One line under the tab's name in More. */
    val tabDescription: String,
    /** Absolute path of the image the plugin ships for its tab, if any. */
    val tabImage: String,
    val commands: List<PluginCommand>,
    val permissions: List<String>,
    val sizeBytes: Long,
    val files: List<String>,
    val loaded: Boolean,
    val error: String?,
    val broken: Boolean,
    /** True when this plugin came out of the APK rather than from the user. */
    val bundled: Boolean,
    /** Sections this plugin adds to the app's own screens. */
    val extensions: List<PluginExtension>,
    /** Settings the app renders as a form in this plugin's row. */
    val settings: List<PluginSetting>,
    /** Lines this plugin adds to a file's or folder's menu in Files. */
    val actions: List<PluginFileAction>,
    /** Documents this plugin wants listed in the Guides screen. */
    val guides: List<PluginGuide>,
) {
    val hasPanel: Boolean get() = !panel.isNullOrEmpty()

    /** Whether this plugin asked for a place of its own in the More screen. */
    val hasTab: Boolean get() = !tabTitle.isNullOrEmpty() && hasPanel

    val readableSize: String
        get() = when {
            sizeBytes >= 1024 * 1024 -> "%.1f MB".format(sizeBytes / 1024.0 / 1024.0)
            sizeBytes >= 1024 -> "${sizeBytes / 1024} KB"
            else -> "$sizeBytes B"
        }

    companion object {
        fun from(json: JSONObject): InstalledPlugin {
            val tab = json.optJSONObject("tab")
            val commands = mutableListOf<PluginCommand>()
            json.optJSONArray("commands")?.let { array ->
                for (index in 0 until array.length()) {
                    val row = array.optJSONObject(index) ?: continue
                    val name = row.optString("name")
                    if (name.isNotEmpty()) {
                        commands += PluginCommand(name, row.optString("help"))
                    }
                }
            }
            val permissions = mutableListOf<String>()
            json.optJSONArray("permissions")?.let { array ->
                for (index in 0 until array.length()) permissions += array.optString(index)
            }
            val files = mutableListOf<String>()
            json.optJSONArray("files")?.let { array ->
                for (index in 0 until array.length()) files += array.optString(index)
            }
            val extensions = mutableListOf<PluginExtension>()
            json.optJSONArray("extends")?.let { array ->
                for (index in 0 until array.length()) {
                    val row = array.optJSONObject(index) ?: continue
                    val tab = row.optString("tab")
                    val panel = row.optString("panel")
                    if (tab.isEmpty() || panel.isEmpty()) continue
                    extensions += PluginExtension(
                        tab = tab,
                        title = row.optString("title"),
                        description = row.optString("description"),
                        panel = panel,
                        height = row.optString("height").ifEmpty { "medium" },
                        startsOpen = row.optBoolean("open"),
                        image = row.optString("image"),
                    )
                }
            }

            val settings = mutableListOf<PluginSetting>()
            json.optJSONArray("settings")?.let { array ->
                for (index in 0 until array.length()) {
                    val row = array.optJSONObject(index) ?: continue
                    val name = row.optString("name")
                    if (name.isEmpty()) continue
                    val options = mutableListOf<String>()
                    row.optJSONArray("options")?.let { list ->
                        for (i in 0 until list.length()) options += list.optString(i)
                    }
                    settings += PluginSetting(
                        name = name,
                        type = row.optString("type").ifEmpty { "text" },
                        label = row.optString("label").ifEmpty { name },
                        help = row.optString("help"),
                        default = row.opt("default").takeIf { it != JSONObject.NULL },
                        options = options,
                    )
                }
            }
            val actions = mutableListOf<PluginFileAction>()
            json.optJSONArray("actions")?.let { array ->
                for (index in 0 until array.length()) {
                    val row = array.optJSONObject(index) ?: continue
                    val label = row.optString("label")
                    val export = row.optString("export")
                    if (label.isEmpty() || export.isEmpty()) continue
                    val types = mutableListOf<String>()
                    row.optJSONArray("types")?.let { list ->
                        for (i in 0 until list.length()) types += list.optString(i).lowercase()
                    }
                    actions += PluginFileAction(
                        target = row.optString("target").ifEmpty { "file" },
                        label = label,
                        export = export,
                        types = types,
                    )
                }
            }

            val guides = mutableListOf<PluginGuide>()
            json.optJSONArray("guides")?.let { array ->
                for (index in 0 until array.length()) {
                    val row = array.optJSONObject(index) ?: continue
                    val file = row.optString("file")
                    if (file.isEmpty()) continue
                    guides += PluginGuide(
                        file = file,
                        title = row.optString("title").ifEmpty { file },
                        summary = row.optString("summary"),
                    )
                }
            }

            return InstalledPlugin(
                id = json.optString("id"),
                name = json.optString("name").ifEmpty { json.optString("id") },
                version = json.optString("version"),
                author = json.optString("author"),
                description = json.optString("description"),
                panel = json.optString("panel").takeIf { it.isNotEmpty() },
                tabTitle = tab?.optString("title")?.takeIf { it.isNotEmpty() },
                tabDescription = tab?.optString("description").orEmpty(),
                tabImage = tab?.optString("image").orEmpty(),
                commands = commands,
                permissions = permissions,
                sizeBytes = json.optLong("size"),
                files = files,
                loaded = json.optBoolean("loaded"),
                error = json.optString("error").takeIf { it.isNotEmpty() },
                broken = json.optBoolean("broken"),
                bundled = json.optBoolean("bundled"),
                extensions = extensions,
                settings = settings,
                actions = actions,
                guides = guides,
            )
        }
    }
}

data class PluginCommand(val name: String, val help: String)

/**
 * A setting a plugin declared, rendered by the app as a real control.
 *
 * A plugin with one switch used to need a whole HTML panel to offer it. The
 * plugin reads whatever the user chose with `api.setting("name")`.
 */
data class PluginSetting(
    val name: String,
    /** "text", "number", "switch" or "choice". */
    val type: String,
    val label: String,
    val help: String,
    val default: Any?,
    val options: List<String>,
)

/**
 * A document a plugin wants listed alongside the app's own guides.
 *
 * A plugin can be installed, switched on, and still leave nobody any the wiser
 * about what to type. Its guide belongs where the guides are.
 */
data class PluginGuide(val file: String, val title: String, val summary: String)

/**
 * A line a plugin adds to a file's or a folder's menu in the Files tab.
 *
 * Tapping it calls the named export with the path, which is how a plugin gets
 * to act on something the user picked rather than something it went looking
 * for.
 */
data class PluginFileAction(
    /** "file" or "folder". */
    val target: String,
    val label: String,
    val export: String,
    /** Extensions it applies to, lower case with the dot. Empty means all. */
    val types: List<String>,
) {
    fun appliesTo(name: String, isDirectory: Boolean): Boolean {
        if (isDirectory != (target == "folder")) return false
        if (types.isEmpty()) return true
        val extension = "." + name.substringAfterLast('.', "").lowercase()
        return extension in types
    }
}

/**
 * A section a plugin adds to one of the app's own screens.
 *
 * The counterpart of a tab: a tab is a place of your own, this is a card
 * inside a screen that already exists - which is what you want when the
 * plugin is *about* that screen. `tab` is one of the names in
 * `EXTENDABLE_TABS` in pycmd_plugins.py.
 */
data class PluginExtension(
    val tab: String,
    val title: String,
    val description: String,
    val panel: String,
    val height: String,
    val startsOpen: Boolean,
    /** Absolute path of a picture the plugin ships for this section, if any. */
    val image: String,
)

/**
 * Which installed plugins the user has switched on.
 *
 * Only the on/off state lives here; the plugins themselves live on disk and
 * are listed by the Python side. Keeping the two apart means a plugin folder
 * can be deleted from under the app without leaving a dead switch behind.
 *
 * New plugins default to **off**. That is deliberate: installing something is
 * a decision to keep it, and running it is a second decision. A plugin that
 * started running the moment it landed would make the warning screen a lie.
 */
object CustomPlugins {

    private const val PREFS = "pycmd-custom-plugins"
    private const val KEY_ENABLED = "enabled"
    private const val KEY_OFFERED = "offered_default_on"
    private val DEFAULT_ON = setOf("pycmd.board")
    private const val TAG = "plugins"

    private var prefs: SharedPreferences? = null

    private val _enabled = MutableStateFlow<Set<String>>(emptySet())
    val enabled: StateFlow<Set<String>> = _enabled.asStateFlow()

    private val _installed = MutableStateFlow<List<InstalledPlugin>>(emptyList())
    val installed: StateFlow<List<InstalledPlugin>> = _installed.asStateFlow()

    fun init(context: Context) {
        val store = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs = store
        _enabled.value = store.getStringSet(KEY_ENABLED, emptySet())?.toSet().orEmpty()
    }

    fun isOn(id: String): Boolean = id in _enabled.value

    fun setEnabled(id: String, on: Boolean) {
        val next = _enabled.value.toMutableSet().apply { if (on) add(id) else remove(id) }
        _enabled.value = next
        prefs?.edit()?.putStringSet(KEY_ENABLED, next)?.apply()
        DebugLog.info(TAG, "custom plugin $id ${if (on) "enabled" else "disabled"}")
    }

    /** Replaces the listing after an install, a removal, or a refresh. */
    fun setInstalled(plugins: List<InstalledPlugin>) {
        _installed.value = plugins
        // A plugin that is no longer on disk should not keep a switch.
        val alive = plugins.map { it.id }.toSet()
        var pruned = _enabled.value.filter { it in alive }.toSet()
        // Built-in plugins that start switched on - once. Turned off, they stay off.
        val offered = prefs?.getStringSet(KEY_OFFERED, emptySet()).orEmpty()
        val fresh = DEFAULT_ON.filter { it in alive && it !in offered }
        if (fresh.isNotEmpty()) {
            pruned = pruned + fresh
            prefs?.edit()?.putStringSet(KEY_OFFERED, offered + fresh)?.apply()
        }
        if (pruned != _enabled.value) {
            _enabled.value = pruned
            prefs?.edit()?.putStringSet(KEY_ENABLED, pruned)?.apply()
        }
    }

    fun forget(id: String) {
        setEnabled(id, false)
        _installed.value = _installed.value.filterNot { it.id == id }
    }

    /** The plugins that asked for a tab and are switched on. */
    fun tabs(): List<InstalledPlugin> =
        _installed.value.filter { it.id in _enabled.value && it.hasPanel && it.tabTitle != null }
}
