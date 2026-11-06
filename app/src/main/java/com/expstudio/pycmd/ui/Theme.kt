package com.expstudio.pycmd.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * The palette the app was built around, kept as named constants because a
 * handful of places want a colour without being inside a theme.
 *
 * Anything drawing inside the app should use [MaterialTheme] or
 * [LocalPalette]: these are the Classic Green values and do not change when
 * somebody picks another theme.
 */
object PyColors {
    val Background = Color(0xFF0B0F14)
    val Accent = Color(0xFF4DD0A0)
}

/** The palette in use. Read it rather than [PyColors] unless you want the default. */
val LocalPalette = staticCompositionLocalOf { Themes.CLASSIC.palette }

/** The whole theme, for the two or three places that want its name or glyph. */
val LocalPyTheme = staticCompositionLocalOf { Themes.CLASSIC }

/** How round a card is, in dp, as chosen in Appearance. */
val LocalCorner = staticCompositionLocalOf { 14 }

/** True when the user has asked for short animations. */
val LocalReducedMotion = staticCompositionLocalOf { false }

/** Console and editor text size, as a multiplier of the 13px default. */
val LocalTextScale = staticCompositionLocalOf { 1f }

private fun color(hex: String) = Color(Hex.argb(hex))

/**
 * Turns a [Palette] into the forty-odd slots Material wants.
 *
 * Light and dark are the same mapping with the two ends swapped - what makes a
 * light theme readable is that the palette itself was written light, not that
 * the chrome does something different with it.
 */
fun Palette.scheme() = if (Hex.luma(bg) < 0.5) {
    darkColorScheme(
        primary = color(accent),
        onPrimary = color(onAccent),
        primaryContainer = color(accentDim),
        onPrimaryContainer = color(Hex.lighten(accent, 0.75)),
        inversePrimary = color(accentDim),
        secondary = color(info),
        onSecondary = color(Hex.readableOn(info)),
        secondaryContainer = color(Hex.darken(info, 0.7)),
        onSecondaryContainer = color(Hex.lighten(info, 0.6)),
        tertiary = color(warning),
        onTertiary = color(Hex.readableOn(warning)),
        background = color(bg),
        onBackground = color(fg),
        surface = color(surface),
        onSurface = color(fg),
        surfaceVariant = color(surfaceHigh),
        onSurfaceVariant = color(muted),
        surfaceContainer = color(surface),
        surfaceContainerHigh = color(surfaceHigh),
        surfaceContainerHighest = color(Hex.lighten(surfaceHigh, 0.06)),
        surfaceContainerLow = color(Hex.mix(bg, surface, 0.5)),
        surfaceContainerLowest = color(bg),
        outline = color(outline),
        outlineVariant = color(Hex.mix(bg, outline, 0.5)),
        error = color(danger),
        onError = color(Hex.readableOn(danger)),
        errorContainer = color(Hex.darken(danger, 0.75)),
        onErrorContainer = color(Hex.lighten(danger, 0.5)),
        scrim = Color(0xCC000000),
    )
} else {
    lightColorScheme(
        primary = color(accent),
        onPrimary = color(onAccent),
        primaryContainer = color(Hex.lighten(accent, 0.8)),
        onPrimaryContainer = color(Hex.darken(accent, 0.4)),
        inversePrimary = color(Hex.lighten(accent, 0.6)),
        secondary = color(info),
        onSecondary = color(Hex.readableOn(info)),
        secondaryContainer = color(Hex.lighten(info, 0.82)),
        onSecondaryContainer = color(Hex.darken(info, 0.4)),
        tertiary = color(warning),
        onTertiary = color(Hex.readableOn(warning)),
        background = color(bg),
        onBackground = color(fg),
        surface = color(surface),
        onSurface = color(fg),
        surfaceVariant = color(surfaceHigh),
        onSurfaceVariant = color(muted),
        surfaceContainer = color(surface),
        surfaceContainerHigh = color(surfaceHigh),
        surfaceContainerHighest = color(Hex.darken(surfaceHigh, 0.04)),
        surfaceContainerLow = color(Hex.mix(bg, surface, 0.5)),
        surfaceContainerLowest = color(surface),
        outline = color(outline),
        outlineVariant = color(Hex.mix(bg, outline, 0.5)),
        error = color(danger),
        onError = color(Hex.readableOn(danger)),
        errorContainer = color(Hex.lighten(danger, 0.8)),
        onErrorContainer = color(Hex.darken(danger, 0.35)),
        scrim = Color(0x99000000),
    )
}

val MonoFamily = FontFamily.Monospace

private val PyTypography = Typography(
    titleLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    bodyLarge = TextStyle(fontSize = 15.sp, lineHeight = 21.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 17.sp),
    labelLarge = TextStyle(fontWeight = FontWeight.Medium, fontSize = 14.sp),
    labelSmall = TextStyle(fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 0.4.sp),
)

/**
 * The chrome, in whichever theme is on.
 *
 * The console, the editor and every plugin panel are WebViews with their own
 * stylesheets, and they are handed the same palette as a block of CSS
 * variables by [WebTheme] - which is the whole reason a palette is hex strings
 * and not `Color`s. Before 2.7.0 the panels had a blue palette of their own and
 * looked like a different app bolted on, because they were.
 */
@Composable
fun PyCmdTheme(
    theme: PyTheme = Themes.CLASSIC,
    corner: Int = 14,
    reducedMotion: Boolean = false,
    textScale: Float = 1f,
    content: @Composable () -> Unit,
) {
    androidx.compose.runtime.CompositionLocalProvider(
        LocalPalette provides theme.palette,
        LocalPyTheme provides theme,
        LocalCorner provides corner,
        LocalReducedMotion provides reducedMotion,
        LocalTextScale provides textScale,
    ) {
        MaterialTheme(
            colorScheme = theme.palette.scheme(),
            typography = PyTypography,
            shapes = androidx.compose.material3.Shapes(
                extraSmall = androidx.compose.foundation.shape.RoundedCornerShape((corner / 3).dp),
                small = androidx.compose.foundation.shape.RoundedCornerShape((corner / 2).dp),
                medium = androidx.compose.foundation.shape.RoundedCornerShape(corner.dp),
                large = androidx.compose.foundation.shape.RoundedCornerShape((corner + 4).dp),
                extraLarge = androidx.compose.foundation.shape.RoundedCornerShape((corner + 12).dp),
            ),
            content = content,
        )
    }
}

/**
 * The same palette, as the CSS the web pages read.
 *
 * Every page in the app - console, editor, every plugin panel - declares its
 * colours as `:root` custom properties and then this block is appended to the
 * document, overriding them. One palette, four surfaces, and no stylesheet
 * that has to be edited when a theme is added.
 */
object WebTheme {

    /**
     * A JSON string literal.
     *
     * Everything that goes through here is generated - hex colours, a theme id
     * and two fixed words - so none of it can contain a quote today. It is
     * escaped anyway: a custom theme's name is one change away from ending up
     * in this block, and a stray quote would be a panel whose script does not
     * parse, which looks like the theme simply not working.
     */
    private fun quote(text: String): String = buildString {
        append('"')
        for (character in text) {
            when {
                character == '"' -> append("\\\"")
                character == '\\' -> append("\\\\")
                character == '\n' -> append("\\n")
                character == '\r' -> append("\\r")
                character == '\t' -> append("\\t")
                character < ' ' -> append("\\u%04x".format(character.code))
                else -> append(character)
            }
        }
        append('"')
    }

    /** The `:root { ... }` body. Names cover console.css, editor.css and the panel CSS. */
    fun variables(palette: Palette, textScale: Float = 1f, corner: Int = 14): String {
        val p = palette
        val size = (13 * textScale).coerceIn(9f, 24f)
        val line = (size * 1.62f)
        val dim = Hex.mix(p.muted, p.bg, 0.25)
        return buildString {
            append("--bg:${p.bg};")
            append("--fg:${p.fg};")
            append("--surface:${p.surface};")
            append("--surface-high:${p.surfaceHigh};")
            append("--outline:${p.outline};")
            append("--muted:${p.muted};")
            append("--dim:$dim;")
            append("--accent:${p.accent};")
            append("--accent-dim:${p.accentDim};")
            append("--accent-soft:${Hex.rgba(p.accent, 0.14)};")
            append("--on-accent:${p.onAccent};")
            append("--info:${p.info};")
            append("--warning:${p.warning};")
            append("--danger:${p.danger};")
            // Console
            append("--stderr:${Hex.lighten(p.danger, 0.15)};")
            append("--system:${p.info};")
            append("--input:${p.accent};")
            append("--selection:${Hex.rgba(p.info, 0.35)};")
            // Editor
            append("--gutter-bg:${Hex.mix(p.bg, p.surface, 0.6)};")
            append("--gutter-fg:${Hex.mix(p.muted, p.bg, 0.45)};")
            append("--gutter-active:${p.accent};")
            append("--caret:${p.accent};")
            append("--current-line:${Hex.rgba(p.accent, 0.08)};")
            append("--kw:${p.kw};")
            append("--builtin:${p.builtin};")
            append("--str:${p.str};")
            append("--num:${p.num};")
            append("--comment:${p.comment};")
            append("--decorator:${p.decorator};")
            append("--def:${p.def};")
            append("--self:${p.self};")
            append("--font-size:${"%.1f".format(java.util.Locale.US, size)}px;")
            append("--line-height:${"%.1f".format(java.util.Locale.US, line)}px;")
            append("--radius:${corner}px;")
            // ANSI. Derived rather than listed: sixteen more fields per theme
            // would be sixteen more chances for a theme to be half-finished.
            append("--ansi-0:${Hex.mix(p.outline, p.bg, 0.2)};")
            append("--ansi-1:${p.danger};")
            append("--ansi-2:${p.accent};")
            append("--ansi-3:${p.warning};")
            append("--ansi-4:${p.info};")
            append("--ansi-5:${p.kw};")
            append("--ansi-6:${p.def};")
            append("--ansi-7:${p.fg};")
            append("--ansi-8:${Hex.lighten(p.outline, 0.25)};")
            append("--ansi-9:${Hex.lighten(p.danger, 0.2)};")
            append("--ansi-10:${Hex.lighten(p.accent, 0.2)};")
            append("--ansi-11:${Hex.lighten(p.warning, 0.2)};")
            append("--ansi-12:${Hex.lighten(p.info, 0.2)};")
            append("--ansi-13:${Hex.lighten(p.kw, 0.2)};")
            append("--ansi-14:${Hex.lighten(p.def, 0.2)};")
            append("--ansi-15:${if (Hex.luma(p.bg) < 0.5) "#FFFFFF" else "#000000"};")
        }
    }

    /**
     * JS that drops the block into a page and marks it.
     *
     * Appended as a `<style>` rather than written onto the element's inline
     * style: an inline style would have to be rebuilt from scratch to change
     * one colour, and the pages set inline styles of their own.
     *
     * `data-pycmd-dark` and `data-pycmd-motion` go on the root element so a
     * page can key off them in CSS - the panel stylesheet uses the motion one
     * to turn its transitions off.
     */
    fun script(theme: PyTheme, textScale: Float = 1f, corner: Int = 14, reducedMotion: Boolean = false): String {
        val css = ":root{" + variables(theme.palette, textScale, corner) + "}"
        // Built by hand rather than with org.json, for a dull but real reason:
        // Android's org.json is a stub on the JVM, so a unit test for this
        // throws rather than failing, and this is the one piece of the theme
        // system worth having a test for.
        val json = "{" +
            "\"css\":" + quote(css) + "," +
            "\"dark\":" + theme.dark + "," +
            "\"motion\":" + quote(if (reducedMotion) "reduced" else "full") + "," +
            "\"theme\":" + quote(theme.id) +
            "}"
        return """
        (function(){
          var t = $json;
          try {
            var el = document.getElementById('pycmd-theme');
            if (!el) {
              el = document.createElement('style');
              el.id = 'pycmd-theme';
              (document.head || document.documentElement).appendChild(el);
            }
            el.textContent = t.css;
            var root = document.documentElement;
            root.setAttribute('data-pycmd-dark', t.dark ? 'true' : 'false');
            root.setAttribute('data-pycmd-motion', t.motion);
            root.setAttribute('data-pycmd-theme', t.theme);
            if (window.__pycmdOnTheme) { try { window.__pycmdOnTheme(t); } catch (e) {} }
          } catch (e) {}
        })();
        """.trimIndent()
    }
}
