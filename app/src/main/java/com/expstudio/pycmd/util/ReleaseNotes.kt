package com.expstudio.pycmd.util

import android.content.Context
import androidx.core.content.edit
import com.expstudio.pycmd.BuildConfig

/**
 * One release's worth of changes.
 *
 * Three lists rather than one, because "what did you add" and "what did you
 * take away" are different questions and people scan for different ones.
 *
 * Not called `Release`: [com.expstudio.pycmd.util.Updater] already has one of
 * those, and it means a build available to download rather than a list of what
 * changed in it.
 */
data class ReleaseNote(
    val versionCode: Int,
    val versionName: String,
    val headline: String,
    val added: List<String> = emptyList(),
    val fixed: List<String> = emptyList(),
    val removed: List<String> = emptyList(),
) {
    val total: Int get() = added.size + fixed.size + removed.size
}

/**
 * What changed, shipped inside the build it describes.
 *
 * In the APK rather than fetched, for two reasons. It works on a phone with no
 * signal, which is where this app gets used; and it cannot disagree with the
 * build it is describing, which a changelog downloaded from a branch can and
 * eventually does.
 *
 * Newest first. `dist/README.md` carries the same text for people reading on
 * GitHub, and `tools/test_release_notes.py` checks the top entry here matches
 * the version actually being built.
 */
object ReleaseNotes {

    val ALL: List<ReleaseNote> = listOf(
        ReleaseNote(
            versionCode = 28,
            versionName = "2.8.1",
            headline = "Every \"Spot the mistake\" lesson is a real question now.",
            fixed = listOf(
                "\"Spot the mistake\" on a one-line program showed a single line " +
                    "to tap, so it could not be got wrong and taught nothing. Those " +
                    "164 lessons are gone; every one left has at least two lines " +
                    "to choose from. PyCmdTeach has 8,874 lessons.",
                "If you missed one of those lessons, Review no longer counts it, " +
                    "so the number on the button matches what it opens.",
                "If the last lesson you opened was one of them, Continue takes you " +
                    "to the next lesson in the same topic instead of disappearing.",
            ),
        ),
        ReleaseNote(
            versionCode = 27,
            versionName = "2.8.0",
            headline = "PyCmdTeach more than doubled, and Show me shows you.",
            added = listOf(
                "PyCmdTeach has 9,038 lessons now, up from 3,781. Every one of the " +
                    "28 courses gained new units - Python alone went from 625 " +
                    "lessons to over 1,500.",
                "Two new kinds of lesson: \"Which one prints it?\" puts four " +
                    "snippets side by side and asks which gives the output, and " +
                    "\"Spot the mistake\" breaks one line of a program and asks " +
                    "you to find it.",
                "Review: every answer you get wrong is kept, and the Review " +
                    "button takes you back through them until you get them right.",
                "Continue: the Teach tab opens on the lesson you were last in.",
                "A daily goal, with - and + to set it, and a bar that fills as " +
                    "you go.",
                "Search every lesson in every course from the top of the tab.",
                "Write-it-yourself lessons in the languages a phone cannot run " +
                    "now tell you how the answer starts.",
            ),
            fixed = listOf(
                "Show me showed nothing. A write-it-yourself lesson never carried " +
                    "its own answer, so the button opened an empty box. It shows " +
                    "the answer now.",
                "The Editor button opened the wrong code: a fill-the-gap lesson " +
                    "opened its code with the gap still in it, an ordering lesson " +
                    "opened its lines shuffled, and a write lesson opened an " +
                    "empty file. All of them open the real snippet now.",
                "Answers compared rather than run no longer fail over spacing or " +
                    "over ' versus \".",
                "The C interpreter: static locals kept resetting, sizeof on an " +
                    "array gave the size of a pointer, sizeof *p dereferenced p, " +
                    "function pointers could not be declared, unions did not " +
                    "share their memory, and qsort and bsearch were missing. All " +
                    "fixed - every one of them was found by a lesson.",
                "The Rust interpreter: BTreeMap and BTreeSet walked their keys " +
                    "in insertion order rather than sorted, and self.0 on a tuple " +
                    "struct read as the number 0.0.",
                "The Go interpreter: reading a missing key from a map of slices " +
                    "gave 0 instead of an empty slice, so append refused it.",
                "Two lessons in 2.7.0 stated the wrong output - Lua's ipairs and " +
                    "a shell pipe. Every lesson is now checked against the real " +
                    "node, ruby, php, lua, java, g++, gcc, go, rustc, bash and " +
                    "sqlite3 before release.",
            ),
        ),
        ReleaseNote(
            versionCode = 26,
            versionName = "2.7.0",
            headline = "PyCmdTeach, themes, and PyCmd on an emulator.",
            added = listOf(
                "PyCmdTeach: a new tab with 28 courses and over 3,700 lessons, " +
                    "covering every language the app can run, edit or highlight - " +
                    "and regular expressions. Free, offline, no account.",
                "Lessons are interactive five ways: read it, predict what it " +
                    "prints, fill the gap, put the lines in order, write it " +
                    "yourself. For Python, C, Rust and Go the last one is marked " +
                    "by actually running what you wrote.",
                "Appearance: six themes, including Halloween 2026 - pumpkin and " +
                    "purple - plus Terminal Green, Amber CRT, Paper and Slate. " +
                    "Classic Green is still the default and still the one it " +
                    "goes back to.",
                "Your own themes: copy any of the six and edit all twenty of its " +
                    "colours. Corner roundness, code text size and an " +
                    "animations-off switch too.",
                "Themes reach everything. The console, the editor and every " +
                    "plugin panel take the same palette as the chrome around them.",
                "A what's new screen after an update. This one. It is dismissed " +
                    "with Read and does not come back until the next version.",
                "The version archive goes up to 10 GB, from 2, with 100 MB added " +
                    "at the bottom - and it now says how much room the phone " +
                    "actually has.",
                "System has a Device card: the processor, whether this is an " +
                    "emulator, and whether the Python in this build matches. " +
                    "Copy it into a bug report in one tap.",
            ),
            fixed = listOf(
                "PyCmd runs on an emulator. The published APK is now the " +
                    "universal one, so an x86_64 emulator - which is what an " +
                    "emulator on a PC is - can install it and start Python. The " +
                    "arm64-only build it used to publish could not, which is why " +
                    "it crashed or hung on every emulator anybody tried.",
                "Plugin panels look like part of the app. The blue palette they " +
                    "had of their own is gone, along with their own button shape " +
                    "and their own spacing; cards, buttons, fields, sliders, " +
                    "check boxes, tabs and tables are the app's now.",
                "Sliders, check boxes and radio buttons in panels are drawn by " +
                    "the app instead of by Android, so they are the accent colour " +
                    "rather than system blue.",
                "A panel opened while the app was being themed no longer paints " +
                    "once in the old colours first.",
                "Python's `input()` lesson no longer assumes there is something " +
                    "on standard input.",
            ),
            removed = listOf(
                "The blue plugin stylesheet, which was the only part of the app " +
                    "that was not the app's colours.",
                "The hard-coded 14 dp corner on cards and buttons - it is a " +
                    "setting now.",
            ),
        ),
        ReleaseNote(
            versionCode = 25,
            versionName = "2.6.1",
            headline = "Sliders in plugin panels work again.",
            fixed = listOf(
                "Dragging a slider in any plugin panel handed the gesture to the " +
                    "app's scrolling list a few pixels in, so the thumb stopped " +
                    "following your finger. The rule that decides who owns a drag " +
                    "now measures from where the finger landed and settles once.",
            ),
        ),
        ReleaseNote(
            versionCode = 24,
            versionName = "2.6.0",
            headline = "Creator grew, Music was rebuilt, Music Pro arrived.",
            added = listOf(
                "Creator: 904 blocks across 10 languages.",
                "The Music tab, rebuilt - a real library, queue, and playback " +
                    "that keeps going with the app closed.",
                "Music Pro: a DJ mixer with two decks, an equaliser and effects, " +
                    "and a way to hand a search to any music app on the phone.",
            ),
        ),
    )

    /** The notes for the build that is running, or null if there are none. */
    val current: ReleaseNote? get() = ALL.firstOrNull { it.versionCode == BuildConfig.VERSION_CODE }

    private const val PREFS = "pycmd-release-notes"
    private const val KEY_SEEN = "seen-version"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /**
     * Whether the what's-new screen is due.
     *
     * Not on a fresh install. Somebody who has never used PyCmd does not want
     * a list of what changed since a version they never had; they want the
     * console. So the first launch records the version silently and the screen
     * appears the first time that recorded number is behind.
     */
    fun due(context: Context): ReleaseNote? {
        val seen = prefs(context).getInt(KEY_SEEN, 0)
        val running = BuildConfig.VERSION_CODE
        if (seen == 0) {
            markSeen(context)
            return null
        }
        if (seen >= running) return null
        return current
    }

    /** Called when Read is pressed, and after a fresh install. */
    fun markSeen(context: Context) {
        prefs(context).edit { putInt(KEY_SEEN, BuildConfig.VERSION_CODE) }
    }

    /** For the System tab's "show me again" row, which ignores whether it is due. */
    fun forVersion(code: Int): ReleaseNote? = ALL.firstOrNull { it.versionCode == code }
}
