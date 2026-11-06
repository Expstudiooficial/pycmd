package com.expstudio.pycmd.ui

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf

/**
 * What the app looks like, held where both the theme and the screen that edits
 * it can reach it.
 *
 * Not in the view model. The theme has to be known before the first frame and
 * the view model is built inside the composition, so the chrome would have
 * drawn once in the default colours and then corrected itself - a flash of
 * green on the way into the Halloween theme, every single launch.
 *
 * One instance, made by the activity. Writes go to disk straight away: there
 * is no Save button on an appearance screen, and a theme that did not survive
 * the app being swiped away would be worse than no theme picker.
 */
class Appearance(context: Context) {

    private val store = ThemeStore(context)

    /** The theme in use. */
    var theme by mutableStateOf(store.theme())
        private set

    /** Every theme on offer, built-ins first. */
    var themes by mutableStateOf(store.allThemes())
        private set

    /** Card corner radius in dp. */
    var corner by mutableIntStateOf(store.corner)
        private set

    /** Whether to keep animations short. */
    var reducedMotion by mutableStateOf(store.reducedMotion)
        private set

    /** Console and editor text size, as a multiplier. */
    var textScale by mutableFloatStateOf(store.textScale)
        private set

    fun choose(id: String) {
        store.chosenId = id
        theme = store.theme()
    }

    fun chooseCorner(value: Int) {
        store.corner = value
        corner = store.corner
    }

    fun chooseReducedMotion(value: Boolean) {
        store.reducedMotion = value
        reducedMotion = store.reducedMotion
    }

    fun chooseTextScale(value: Float) {
        store.textScale = value
        textScale = store.textScale
    }

    /**
     * Copies a theme into an editable one and switches to it.
     *
     * Starting from a copy rather than from a blank palette because nobody
     * wants to pick twenty colours to get going - the first edit people make
     * is the accent, and the other nineteen should already look like an app.
     */
    fun forkTheme(base: PyTheme, name: String = "My ${base.name}"): PyTheme {
        val id = store.freshCustomId()
        val made = base.copy(id = id, name = name, blurb = "Based on ${base.name}.")
        store.saveCustom(made, base = if (base.custom) Themes.DEFAULT_ID else base.id)
        themes = store.allThemes()
        choose(id)
        return themes.firstOrNull { it.id == id } ?: made
    }

    /** Writes an edited custom theme back. No-op for a built-in. */
    fun updateCustom(edited: PyTheme) {
        if (!edited.custom) return
        store.saveCustom(edited)
        themes = store.allThemes()
        if (theme.id == edited.id) theme = store.theme()
    }

    fun deleteCustom(id: String) {
        store.deleteCustom(id)
        themes = store.allThemes()
        theme = store.theme()
    }

    /** Back to how the app shipped. */
    fun reset() {
        store.chosenId = Themes.DEFAULT_ID
        store.corner = 14
        store.reducedMotion = false
        store.textScale = 1f
        theme = store.theme()
        corner = store.corner
        reducedMotion = store.reducedMotion
        textScale = store.textScale
    }
}

/**
 * The live appearance, for the screens that change it.
 *
 * Fails loudly rather than defaulting: a screen reading a throwaway Appearance
 * would save the user's choices into an object nobody else can see, and that
 * is a bug that looks exactly like "the theme picker does nothing".
 */
val LocalAppearance = staticCompositionLocalOf<Appearance> {
    error("No Appearance provided. MainActivity provides it around PyCmdRoot.")
}
