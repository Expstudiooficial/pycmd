package com.expstudio.pycmd.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The theme system's arithmetic and the themes themselves.
 *
 * Worth a real test rather than a look at the screen, because a theme is
 * twenty colours and the ways it can be wrong are not all visible: a palette
 * can look fine and still have text nobody can read on one of its four
 * surfaces, and a CSS variable that was never emitted shows up as a plugin
 * panel going half black weeks later.
 */
class ThemesTest {

    // ----------------------------------------------------------------- Hex

    @Test
    fun `tidy accepts the forms people actually type`() {
        assertEquals("#AABBCC", Hex.tidy("#aabbcc"))
        assertEquals("#AABBCC", Hex.tidy("aabbcc"))
        assertEquals("#AABBCC", Hex.tidy("  #AABBCC  "))
        // Three digits, each doubled.
        assertEquals("#00FF00", Hex.tidy("#0f0"))
        // Eight digits is an 0xAARRGGBB pasted out of Kotlin source.
        assertEquals("#4DD0A0", Hex.tidy("FF4DD0A0"))
    }

    @Test
    fun `tidy refuses what is not a colour`() {
        assertNull(Hex.tidy(""))
        assertNull(Hex.tidy("#"))
        assertNull(Hex.tidy("#12"))
        assertNull(Hex.tidy("#12345"))
        assertNull(Hex.tidy("#gggggg"))
        assertNull(Hex.tidy("rebeccapurple"))
    }

    @Test
    fun `lighten and darken move towards white and black`() {
        assertEquals("#FFFFFF", Hex.lighten("#808080", 1.0))
        assertEquals("#000000", Hex.darken("#808080", 1.0))
        assertEquals("#808080", Hex.lighten("#808080", 0.0))
        assertTrue(Hex.luma(Hex.lighten("#4DD0A0", 0.4)) > Hex.luma("#4DD0A0"))
        assertTrue(Hex.luma(Hex.darken("#4DD0A0", 0.4)) < Hex.luma("#4DD0A0"))
    }

    @Test
    fun `mix at the ends is each end`() {
        assertEquals("#000000", Hex.mix("#000000", "#FFFFFF", 0.0))
        assertEquals("#FFFFFF", Hex.mix("#000000", "#FFFFFF", 1.0))
        assertEquals("#7F7F7F", Hex.mix("#000000", "#FFFFFF", 0.5))
    }

    @Test
    fun `luma knows black from white`() {
        assertTrue(Hex.luma("#000000") < 0.05)
        assertTrue(Hex.luma("#FFFFFF") > 0.95)
    }

    @Test
    fun `readableOn picks the one you can see`() {
        assertEquals("#FFFFFF", Hex.readableOn("#0B0F14"))
        assertEquals("#101418", Hex.readableOn("#F6F4EF"))
    }

    @Test
    fun `argb is opaque and in the right order`() {
        assertEquals(0xFF4DD0A0, Hex.argb("#4DD0A0"))
        assertEquals(0xFF000000, Hex.argb("#000000"))
    }

    @Test
    fun `rgba prints a CSS colour`() {
        assertEquals("rgba(77, 208, 160, 0.140)", Hex.rgba("#4DD0A0", 0.14))
    }

    // -------------------------------------------------------------- palettes

    @Test
    fun `every built-in theme has twenty readable colours`() {
        for (theme in Themes.BUILT_IN) {
            val colours = theme.palette.toMap()
            assertEquals("${theme.id} has every field", 20, colours.size)
            for ((field, value) in colours) {
                assertNotNull("${theme.id}.$field is a colour", Hex.tidy(value))
            }
        }
    }

    @Test
    fun `text can be read on every surface of every theme`() {
        for (theme in Themes.BUILT_IN) {
            val p = theme.palette
            // Not a contrast-ratio check: this is the cruder question of
            // whether the text is on the same side of the midpoint as its
            // background, which is how a palette ends up with invisible text.
            val dark = Hex.luma(p.bg) < 0.5
            for (surface in listOf(p.bg, p.surface, p.surfaceHigh)) {
                assertEquals(
                    "${theme.id}: surface $surface matches the theme's side",
                    dark,
                    Hex.luma(surface) < 0.5,
                )
            }
            assertTrue(
                "${theme.id}: body text stands out from the background",
                kotlin.math.abs(Hex.luma(p.fg) - Hex.luma(p.bg)) > 0.3,
            )
            assertTrue(
                "${theme.id}: quiet text stands out from the background",
                kotlin.math.abs(Hex.luma(p.muted) - Hex.luma(p.bg)) > 0.12,
            )
            assertTrue(
                "${theme.id}: text on the accent stands out from it",
                kotlin.math.abs(Hex.luma(p.onAccent) - Hex.luma(p.accent)) > 0.25,
            )
        }
    }

    @Test
    fun `the default is the green one and it is first`() {
        assertEquals("classic", Themes.DEFAULT_ID)
        assertEquals(Themes.CLASSIC, Themes.BUILT_IN.first())
        assertEquals(Themes.CLASSIC, Themes.resolve("not-a-theme"))
        assertEquals("#4DD0A0", Themes.CLASSIC.palette.accent)
    }

    @Test
    fun `ids are unique and the seasonal one is the only one with a glyph`() {
        assertEquals(Themes.BUILT_IN.size, Themes.BUILT_IN.map { it.id }.toSet().size)
        val withGlyphs = Themes.BUILT_IN.filter { it.glyph.isNotEmpty() }
        assertEquals(listOf("halloween"), withGlyphs.map { it.id })
    }

    @Test
    fun `exactly one built-in is a light theme`() {
        assertEquals(listOf("paper"), Themes.BUILT_IN.filterNot { it.dark }.map { it.id })
    }

    @Test
    fun `overrides replace only what parses`() {
        val changed = Themes.CLASSIC.palette.with(
            mapOf("accent" to "#ff0000", "bg" to "not a colour"),
        )
        assertEquals("#FF0000", changed.accent)
        assertEquals(Themes.CLASSIC.palette.bg, changed.bg)
        // And a key nothing is called is simply ignored.
        assertEquals(changed, changed.with(mapOf("nonsense" to "#123456")))
    }

    @Test
    fun `an empty override set is the same palette`() {
        assertEquals(Themes.CLASSIC.palette, Themes.CLASSIC.palette.with(emptyMap()))
    }

    // -------------------------------------------------------------- web CSS

    /**
     * Every variable the three stylesheets read.
     *
     * Taken from console.css, editor.css and the panel CSS. A name that stops
     * being emitted is a page that falls back to whatever it declared itself,
     * which looks like one tab ignoring the theme.
     */
    private val NEEDED = listOf(
        // shared
        "--bg", "--fg", "--surface", "--surface-high", "--outline", "--muted",
        "--accent", "--accent-dim", "--accent-soft", "--on-accent",
        "--info", "--warning", "--danger", "--radius",
        // console.css
        "--dim", "--stderr", "--system", "--input", "--selection",
        // editor.css
        "--gutter-bg", "--gutter-fg", "--gutter-active", "--caret", "--current-line",
        "--kw", "--builtin", "--str", "--num", "--comment", "--decorator", "--def",
        "--self", "--font-size", "--line-height",
    ) + (0..15).map { "--ansi-$it" }

    @Test
    fun `the CSS block carries every variable the pages read`() {
        for (theme in Themes.BUILT_IN) {
            val css = WebTheme.variables(theme.palette)
            for (name in NEEDED) {
                assertTrue("${theme.id} is missing $name", css.contains("$name:"))
            }
        }
    }

    @Test
    fun `text scale and corner reach the CSS`() {
        val small = WebTheme.variables(Themes.CLASSIC.palette, textScale = 0.75f, corner = 0)
        val large = WebTheme.variables(Themes.CLASSIC.palette, textScale = 1.75f, corner = 28)
        assertTrue(small.contains("--font-size:9.8px;"))
        assertTrue(large.contains("--font-size:22.8px;"))
        assertTrue(small.contains("--radius:0px;"))
        assertTrue(large.contains("--radius:28px;"))
    }

    @Test
    fun `the script is one statement and names the theme`() {
        val script = WebTheme.script(Themes.HALLOWEEN, reducedMotion = true)
        assertTrue(script.contains("pycmd-theme"))
        assertTrue(script.contains("\"theme\":\"halloween\""))
        assertTrue(script.contains("\"motion\":\"reduced\""))
        assertTrue(script.contains("\"dark\":true"))
        // The palette goes in as a :root block so it overrides the page's own.
        assertTrue(script.contains(":root{"))
        assertTrue(script.contains("--accent:#FF7518;"))
    }

    @Test
    fun `the light theme tells the page it is light`() {
        assertTrue(WebTheme.script(Themes.PAPER).contains("\"dark\":false"))
    }

    @Test
    fun `a colour scheme comes out of every palette`() {
        // Nothing to assert beyond "it does not throw and the ends are right":
        // Material's scheme is forty slots and checking each one here would be
        // a copy of the mapping rather than a test of it.
        for (theme in Themes.BUILT_IN) {
            val scheme = theme.palette.scheme()
            assertEquals(theme.id, Hex.argb(theme.palette.accent), scheme.primary.value.toLong() ushr 32)
        }
    }
}
