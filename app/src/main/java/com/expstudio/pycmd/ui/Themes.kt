package com.expstudio.pycmd.ui

import android.content.Context
import androidx.core.content.edit
import org.json.JSONObject

/**
 * Every colour the app draws, in one place, as hex.
 *
 * Hex strings rather than Compose `Color`s because three of the four things
 * that need these are web pages. The Compose chrome, the console, the editor
 * and the plugin panels all read the same palette, so a theme is one object
 * and not four stylesheets that drift apart - which is exactly what happened
 * with the old blue panel CSS: nothing was wrong with it except that nothing
 * else in the app looked like it.
 *
 * Field names double as the keys a saved custom theme is stored under, so
 * renaming one here orphans whatever somebody had saved. Add instead.
 */
data class Palette(
    /** Behind everything. */
    val bg: String,
    /** Cards, the bottom bar, the title bar. */
    val surface: String,
    /** A card on a card: list rows, the raised half of a split. */
    val surfaceHigh: String,
    /** Hairlines and card edges. */
    val outline: String,
    /** Body text. */
    val fg: String,
    /** Labels, captions, the half of a row nobody reads first. */
    val muted: String,
    /** The one colour the app is known by. Buttons, switches, the caret. */
    val accent: String,
    /** The accent with the lights off: pressed buttons, filled tracks. */
    val accentDim: String,
    /** Text on top of the accent. */
    val onAccent: String,
    /** Links, notices, the console's own messages. */
    val info: String,
    /** "Careful." */
    val warning: String,
    /** Errors, stderr, delete. */
    val danger: String,
    // Syntax. The editor needs eight; the console borrows four of them for
    // its ANSI palette so that coloured output and coloured code agree.
    val kw: String,
    val builtin: String,
    val str: String,
    val num: String,
    val comment: String,
    val def: String,
    val self: String,
    val decorator: String,
) {
    /** Hex for every field, keyed by field name. What gets saved and sent to JS. */
    fun toMap(): Map<String, String> = linkedMapOf(
        "bg" to bg, "surface" to surface, "surfaceHigh" to surfaceHigh, "outline" to outline,
        "fg" to fg, "muted" to muted, "accent" to accent, "accentDim" to accentDim,
        "onAccent" to onAccent, "info" to info, "warning" to warning, "danger" to danger,
        "kw" to kw, "builtin" to builtin, "str" to str, "num" to num,
        "comment" to comment, "def" to def, "self" to self, "decorator" to decorator,
    )

    /** This palette with [overrides] applied; anything unparseable is ignored. */
    fun with(overrides: Map<String, String>): Palette {
        if (overrides.isEmpty()) return this
        fun pick(key: String, fallback: String): String =
            overrides[key]?.let { Hex.tidy(it) } ?: fallback
        return Palette(
            bg = pick("bg", bg),
            surface = pick("surface", surface),
            surfaceHigh = pick("surfaceHigh", surfaceHigh),
            outline = pick("outline", outline),
            fg = pick("fg", fg),
            muted = pick("muted", muted),
            accent = pick("accent", accent),
            accentDim = pick("accentDim", accentDim),
            onAccent = pick("onAccent", onAccent),
            info = pick("info", info),
            warning = pick("warning", warning),
            danger = pick("danger", danger),
            kw = pick("kw", kw),
            builtin = pick("builtin", builtin),
            str = pick("str", str),
            num = pick("num", num),
            comment = pick("comment", comment),
            def = pick("def", def),
            self = pick("self", self),
            decorator = pick("decorator", decorator),
        )
    }
}

/**
 * Hex arithmetic, because a palette of twenty colours cannot also carry a
 * palette of sixteen ANSI colours without becoming a spreadsheet.
 *
 * Everything is `#RRGGBB` in and `#RRGGBB` out. Nothing here allocates a
 * Compose `Color`, so the whole lot runs in a plain JVM test.
 */
object Hex {

    /** `#rgb`, `#rrggbb`, `rrggbb` and whitespace all land as `#RRGGBB`. */
    fun tidy(raw: String): String? {
        val text = raw.trim().removePrefix("#").uppercase()
        val full = when (text.length) {
            3 -> text.map { "$it$it" }.joinToString("")
            6 -> text
            8 -> text.substring(2) // #AARRGGBB pasted from Kotlin source
            else -> return null
        }
        if (!full.all { it in '0'..'9' || it in 'A'..'F' }) return null
        return "#$full"
    }

    fun rgb(hex: String): Triple<Int, Int, Int> {
        val text = tidy(hex) ?: return Triple(0, 0, 0)
        return Triple(
            text.substring(1, 3).toInt(16),
            text.substring(3, 5).toInt(16),
            text.substring(5, 7).toInt(16),
        )
    }

    private fun clamp(value: Int) = value.coerceIn(0, 255)

    private fun pack(r: Int, g: Int, b: Int) =
        "#%02X%02X%02X".format(clamp(r), clamp(g), clamp(b))

    /** [amount] of 1.0 is white. */
    fun lighten(hex: String, amount: Double): String {
        val (r, g, b) = rgb(hex)
        return pack(
            (r + (255 - r) * amount).toInt(),
            (g + (255 - g) * amount).toInt(),
            (b + (255 - b) * amount).toInt(),
        )
    }

    /** [amount] of 1.0 is black. */
    fun darken(hex: String, amount: Double): String {
        val (r, g, b) = rgb(hex)
        return pack((r * (1 - amount)).toInt(), (g * (1 - amount)).toInt(), (b * (1 - amount)).toInt())
    }

    fun mix(a: String, b: String, ratio: Double): String {
        val (r1, g1, b1) = rgb(a)
        val (r2, g2, b2) = rgb(b)
        val t = ratio.coerceIn(0.0, 1.0)
        return pack(
            (r1 + (r2 - r1) * t).toInt(),
            (g1 + (g2 - g1) * t).toInt(),
            (b1 + (b2 - b1) * t).toInt(),
        )
    }

    /** `rgba(r, g, b, a)`, for the CSS that wants a translucent colour. */
    fun rgba(hex: String, alpha: Double): String {
        val (r, g, b) = rgb(hex)
        return "rgba($r, $g, $b, ${"%.3f".format(java.util.Locale.US, alpha)})"
    }

    /**
     * Rough perceived brightness, 0..1.
     *
     * The sRGB luma weights. Used for one decision only - whether a palette is
     * a dark theme or a light one - so it does not need to be colorimetry.
     */
    fun luma(hex: String): Double {
        val (r, g, b) = rgb(hex)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
    }

    /** Black or white, whichever can be read on top of [hex]. */
    fun readableOn(hex: String): String = if (luma(hex) > 0.55) "#101418" else "#FFFFFF"

    /** As an `0xAARRGGBB` Long, which is what Compose's `Color(...)` wants. */
    fun argb(hex: String): Long {
        val (r, g, b) = rgb(hex)
        return (0xFFL shl 24) or (r.toLong() shl 16) or (g.toLong() shl 8) or b.toLong()
    }
}

/**
 * A theme: a palette, a name, and the small amount of character that is not a
 * colour.
 */
data class PyTheme(
    val id: String,
    val name: String,
    val blurb: String,
    val palette: Palette,
    /**
     * Drawn after the app's name in the title bar. Empty for every theme but
     * the seasonal one - a permanent emoji in the chrome gets old fast, and a
     * seasonal one is the point.
     */
    val glyph: String = "",
    /** What the console prints in front of a line you typed. */
    val prompt: String = ">>>",
) {
    val dark: Boolean get() = Hex.luma(palette.bg) < 0.5

    /** Whether this is a saved copy somebody has edited. */
    val custom: Boolean get() = id.startsWith(Themes.CUSTOM_PREFIX)
}

/**
 * The themes that ship with the app.
 *
 * Six, not sixteen. A theme list long enough to scroll is a list nobody reads
 * past the third entry, and anybody who wants the seventh can make it - the
 * Appearance screen copies any of these into an editable one.
 */
object Themes {

    const val CUSTOM_PREFIX = "custom:"
    const val DEFAULT_ID = "classic"

    /**
     * The green one. What PyCmd has looked like since the first build, and
     * what it goes back to when anything else is switched off.
     */
    val CLASSIC = PyTheme(
        id = "classic",
        name = "Classic Green",
        blurb = "The original. Green on slate.",
        palette = Palette(
            bg = "#0B0F14",
            surface = "#111823",
            surfaceHigh = "#17202D",
            outline = "#243044",
            fg = "#D7E0EA",
            muted = "#8A9AAF",
            accent = "#4DD0A0",
            accentDim = "#2C8A6B",
            onAccent = "#04231A",
            info = "#7AA2F7",
            warning = "#F2C97D",
            danger = "#FF6B6B",
            kw = "#C792EA",
            builtin = "#7AA2F7",
            str = "#4DD0A0",
            num = "#F2C97D",
            comment = "#5A6B80",
            def = "#56D4DD",
            self = "#FF8A8A",
            decorator = "#FFD98A",
        ),
    )

    /**
     * Halloween 2026.
     *
     * Pumpkin on a black that is not quite black - there is a little purple in
     * it, which is what stops the orange looking like a warning. Switched on
     * by hand and switched off by hand; the app does not read the calendar and
     * decide to redecorate itself.
     */
    val HALLOWEEN = PyTheme(
        id = "halloween",
        name = "Halloween 2026",
        blurb = "Pumpkin, purple and a very dark night.",
        palette = Palette(
            bg = "#0C0711",
            surface = "#150E1D",
            surfaceHigh = "#1E1429",
            outline = "#39235A",
            fg = "#EFE3D4",
            muted = "#A58FB8",
            accent = "#FF7518",
            accentDim = "#A8450A",
            onAccent = "#1A0A00",
            info = "#B06CFF",
            warning = "#FFC759",
            danger = "#E5383B",
            kw = "#C77DFF",
            builtin = "#FF9E4A",
            str = "#8FD694",
            num = "#FFC759",
            comment = "#6E5A80",
            def = "#59D8C8",
            self = "#FF6B6B",
            decorator = "#FFD98A",
        ),
        glyph = "🎃",
        prompt = ">>>",
    )

    /** Green all the way down, for anybody who thought Classic was restrained. */
    val TERMINAL = PyTheme(
        id = "terminal",
        name = "Terminal Green",
        blurb = "One colour, two shades, no apologies.",
        palette = Palette(
            bg = "#02110A",
            surface = "#04190F",
            surfaceHigh = "#072316",
            outline = "#115C38",
            fg = "#9BF6C4",
            muted = "#4E9E76",
            accent = "#39FF9A",
            accentDim = "#1C8F55",
            onAccent = "#01150C",
            info = "#7BFFC9",
            warning = "#D9FF7B",
            danger = "#FF7B7B",
            kw = "#6EFFB8",
            builtin = "#43E39B",
            str = "#C8FFE2",
            num = "#D9FF7B",
            comment = "#2F7050",
            def = "#7BFFC9",
            self = "#FF9E9E",
            decorator = "#B6FF8A",
        ),
    )

    /** The other terminal everybody remembers. */
    val AMBER = PyTheme(
        id = "amber",
        name = "Amber CRT",
        blurb = "Monochrome amber, like the monitor your dad had.",
        palette = Palette(
            bg = "#120B02",
            surface = "#1A1004",
            surfaceHigh = "#241706",
            outline = "#5C3C10",
            fg = "#FFC777",
            muted = "#A8783A",
            accent = "#FFB13B",
            accentDim = "#A86A12",
            onAccent = "#1A0E00",
            info = "#FFD9A0",
            warning = "#FFE9B0",
            danger = "#FF8A5C",
            kw = "#FFD080",
            builtin = "#E8A94E",
            str = "#FFE3B0",
            num = "#FFCF6B",
            comment = "#7A5520",
            def = "#FFDFA8",
            self = "#FF9A6A",
            decorator = "#FFE9B0",
        ),
    )

    /**
     * The light one.
     *
     * Added because of where this app gets used: a phone outdoors at midday,
     * where a dark terminal is a mirror. The syntax colours are darkened
     * rather than reused, or none of them would be readable on paper.
     */
    val PAPER = PyTheme(
        id = "paper",
        name = "Paper",
        blurb = "Light, for reading code in daylight.",
        palette = Palette(
            bg = "#F6F4EF",
            surface = "#FFFFFF",
            surfaceHigh = "#ECE8DF",
            outline = "#D3CCBE",
            fg = "#1E242B",
            muted = "#6A7480",
            accent = "#107A55",
            accentDim = "#0B5B3F",
            onAccent = "#FFFFFF",
            info = "#20558F",
            warning = "#8A5A09",
            danger = "#A52020",
            kw = "#7A2A9E",
            builtin = "#20558F",
            str = "#0F6E4A",
            num = "#8A5A09",
            comment = "#8B8577",
            def = "#0E6672",
            self = "#A52020",
            decorator = "#8A5A09",
        ),
    )

    /** Grey, and almost nothing else. For long sessions and tired eyes. */
    val SLATE = PyTheme(
        id = "slate",
        name = "Slate",
        blurb = "Quiet greys. Nothing shouts.",
        palette = Palette(
            bg = "#14161A",
            surface = "#1B1E23",
            surfaceHigh = "#23272E",
            outline = "#333942",
            fg = "#D3D7DD",
            muted = "#8A9099",
            accent = "#7FBFA3",
            accentDim = "#4E7E69",
            onAccent = "#0E1A15",
            info = "#9AAFC4",
            warning = "#D8BC8A",
            danger = "#D98A8A",
            kw = "#B6A7CF",
            builtin = "#9AAFC4",
            str = "#8FBFA6",
            num = "#D8BC8A",
            comment = "#5F666F",
            def = "#8FBAC0",
            self = "#D98A8A",
            decorator = "#D8BC8A",
        ),
    )

    val BUILT_IN: List<PyTheme> = listOf(CLASSIC, HALLOWEEN, TERMINAL, AMBER, PAPER, SLATE)

    fun byId(id: String): PyTheme? = BUILT_IN.firstOrNull { it.id == id }

    /** The theme a saved id means, falling back to the green one. */
    fun resolve(id: String): PyTheme = byId(id) ?: CLASSIC
}

/**
 * The chosen theme, on disk.
 *
 * Plain SharedPreferences and not DataStore: the theme is read once before the
 * first frame, and a suspending read there would mean drawing the app in the
 * wrong colours and then correcting itself, which looks like a bug.
 */
class ThemeStore(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences("pycmd-appearance", Context.MODE_PRIVATE)

    /** The id of the theme in use. */
    var chosenId: String
        get() = prefs.getString(KEY_THEME, Themes.DEFAULT_ID) ?: Themes.DEFAULT_ID
        set(value) = prefs.edit { putString(KEY_THEME, value) }

    /** Whether the UI should keep its animations short. */
    var reducedMotion: Boolean
        get() = prefs.getBoolean(KEY_REDUCED_MOTION, false)
        set(value) = prefs.edit { putBoolean(KEY_REDUCED_MOTION, value) }

    /** Editor and console text size, as a multiplier of 13px. */
    var textScale: Float
        get() = prefs.getFloat(KEY_TEXT_SCALE, 1f).coerceIn(0.75f, 1.75f)
        set(value) = prefs.edit { putFloat(KEY_TEXT_SCALE, value.coerceIn(0.75f, 1.75f)) }

    /** How round a card's corners are, in dp. */
    var corner: Int
        get() = prefs.getInt(KEY_CORNER, 14).coerceIn(0, 28)
        set(value) = prefs.edit { putInt(KEY_CORNER, value.coerceIn(0, 28)) }

    /** The saved custom themes, newest last. */
    fun customThemes(): List<PyTheme> {
        val raw = prefs.getString(KEY_CUSTOM, null) ?: return emptyList()
        val root = runCatching { JSONObject(raw) }.getOrNull() ?: return emptyList()
        val out = mutableListOf<PyTheme>()
        for (key in root.keys()) {
            val entry = root.optJSONObject(key) ?: continue
            val base = Themes.resolve(entry.optString("base", Themes.DEFAULT_ID))
            val overrides = mutableMapOf<String, String>()
            val colours = entry.optJSONObject("colours")
            if (colours != null) {
                for (field in colours.keys()) {
                    colours.optString(field).takeIf { it.isNotEmpty() }?.let { overrides[field] = it }
                }
            }
            out += PyTheme(
                id = key,
                name = entry.optString("name").ifEmpty { "My theme" },
                blurb = entry.optString("blurb").ifEmpty { "Yours." },
                palette = base.palette.with(overrides),
                glyph = entry.optString("glyph"),
                prompt = entry.optString("prompt").ifEmpty { ">>>" },
            )
        }
        return out.sortedBy { it.id }
    }

    /** Every theme on offer: the built-ins, then anything saved. */
    fun allThemes(): List<PyTheme> = Themes.BUILT_IN + customThemes()

    fun theme(): PyTheme {
        val id = chosenId
        return allThemes().firstOrNull { it.id == id } ?: Themes.CLASSIC
    }

    /**
     * Saves a custom theme, replacing one with the same id.
     *
     * The palette is stored as a full set of overrides against the base rather
     * than as a diff: a theme that quietly changed because a built-in was
     * retouched in an update is a theme somebody has to fix twice.
     */
    fun saveCustom(theme: PyTheme, base: String = Themes.DEFAULT_ID) {
        val raw = prefs.getString(KEY_CUSTOM, null)
        val root = runCatching { JSONObject(raw ?: "{}") }.getOrNull() ?: JSONObject()
        val colours = JSONObject()
        for ((field, value) in theme.palette.toMap()) colours.put(field, value)
        root.put(
            theme.id,
            JSONObject()
                .put("name", theme.name)
                .put("blurb", theme.blurb)
                .put("base", base)
                .put("glyph", theme.glyph)
                .put("prompt", theme.prompt)
                .put("colours", colours),
        )
        prefs.edit { putString(KEY_CUSTOM, root.toString()) }
    }

    fun deleteCustom(id: String) {
        val raw = prefs.getString(KEY_CUSTOM, null) ?: return
        val root = runCatching { JSONObject(raw) }.getOrNull() ?: return
        root.remove(id)
        prefs.edit { putString(KEY_CUSTOM, root.toString()) }
        if (chosenId == id) chosenId = Themes.DEFAULT_ID
    }

    /** An id nothing is using yet. */
    fun freshCustomId(): String {
        val taken = customThemes().map { it.id }.toSet()
        var index = 1
        while ("${Themes.CUSTOM_PREFIX}$index" in taken) index++
        return "${Themes.CUSTOM_PREFIX}$index"
    }

    private companion object {
        const val KEY_THEME = "theme"
        const val KEY_CUSTOM = "custom-themes"
        const val KEY_REDUCED_MOTION = "reduced-motion"
        const val KEY_TEXT_SCALE = "text-scale"
        const val KEY_CORNER = "corner"
    }
}
