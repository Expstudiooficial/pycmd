package com.expstudio.pycmd.music

import android.content.Context
import android.media.audiofx.BassBoost
import android.media.audiofx.Equalizer
import android.media.audiofx.LoudnessEnhancer
import android.media.audiofx.PresetReverb
import android.media.audiofx.Virtualizer
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.expstudio.pycmd.util.DebugLog
import java.io.File
import kotlin.math.cos
import kotlin.math.sin
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

private const val TAG = "mixer"

/**
 * Two decks, a crossfader and the effects Android already has.
 *
 * ## Why this is not the Music tab's player
 *
 * The Music tab plays through a `MediaController` bound to a media session in
 * a service, because music has to keep going with the app closed and the lock
 * screen has to be able to pause it. A DJ deck is the opposite kind of thing:
 * it is used while you are looking at it, two things play at once on purpose,
 * and neither of them belongs on the lock screen. So the decks are two
 * ordinary ExoPlayers living in this process, and the moment the panel closes
 * they are released.
 *
 * ## The crossfader is equal-power, not linear
 *
 * Sliding one volume from 1 to 0 while the other goes 0 to 1 sounds like a
 * dip in the middle: at halfway both are at 0.5 and two half-volume signals
 * are quieter than one full one. Every mixer ever built uses the quarter-turn
 * of a circle instead - `cos` and `sin` of the same angle - where the two
 * sides square to one and the loudness stays put across the whole sweep.
 *
 * ## The effects are the phone's own
 *
 * `android.media.audiofx` has had a five-band equaliser, a bass boost, a
 * stereo widener, a reverb and a loudness enhancer since Android 2.3, and
 * they attach to a player's audio session rather than to the file. Writing
 * DSP in Kotlin to do worse versions of these would be daft. They can be
 * refused by the device - some phones have no reverb, and an audio session
 * that is not ready yet has none of them - so every one is wrapped: a missing
 * effect switches itself off and says so rather than taking the panel down.
 */
class MixerHub(private val context: Context) {

    /** One deck: a player, what is on it, and the effects hanging off it. */
    private inner class Deck(val name: String) {
        var player: ExoPlayer? = null
        var path: String = ""
        var title: String = ""
        var cue: Long = 0
        var loopStart: Long = 0
        var loopEnd: Long = 0
        var tempo: Float = 1.0f
        var gain: Float = 1.0f

        var equaliser: Equalizer? = null
        var bass: BassBoost? = null
        var width: Virtualizer? = null
        var reverb: PresetReverb? = null
        var louder: LoudnessEnhancer? = null

        /** Which effects this phone actually gave us. */
        val available = mutableSetOf<String>()

        fun ensure(): ExoPlayer {
            player?.let { return it }
            val made = ExoPlayer.Builder(context).build()
            made.addListener(object : Player.Listener {
                override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                    DebugLog.warn(TAG, "$name could not play", error.message.orEmpty())
                }
            })
            player = made
            attachEffects(made)
            return made
        }

        /**
         * Hangs the effects off the player's audio session.
         *
         * Each one separately, because a phone that has no reverb should still
         * get an equaliser rather than nothing.
         */
        private fun attachEffects(made: ExoPlayer) {
            val session = made.audioSessionId
            if (session == 0) return
            try {
                equaliser = Equalizer(0, session).apply { enabled = true }
                available += "equaliser"
            } catch (error: Throwable) {
                DebugLog.warn(TAG, "$name has no equaliser", error.message.orEmpty())
            }
            try {
                bass = BassBoost(0, session).apply { enabled = true }
                available += "bass"
            } catch (error: Throwable) {
                DebugLog.warn(TAG, "$name has no bass boost", error.message.orEmpty())
            }
            try {
                width = Virtualizer(0, session).apply { enabled = true }
                available += "width"
            } catch (error: Throwable) {
                DebugLog.warn(TAG, "$name has no stereo widener", error.message.orEmpty())
            }
            try {
                reverb = PresetReverb(0, session).apply { enabled = true }
                available += "reverb"
            } catch (error: Throwable) {
                DebugLog.warn(TAG, "$name has no reverb", error.message.orEmpty())
            }
            try {
                louder = LoudnessEnhancer(session).apply { enabled = true }
                available += "louder"
            } catch (error: Throwable) {
                DebugLog.warn(TAG, "$name has no loudness enhancer", error.message.orEmpty())
            }
        }

        fun release() {
            runCatching { equaliser?.release() }
            runCatching { bass?.release() }
            runCatching { width?.release() }
            runCatching { reverb?.release() }
            runCatching { louder?.release() }
            equaliser = null; bass = null; width = null; reverb = null; louder = null
            available.clear()
            runCatching { player?.release() }
            player = null
            path = ""; title = ""; cue = 0; loopStart = 0; loopEnd = 0
        }

        fun describe(): JSONObject {
            val live = player
            val bands = JSONArray()
            equaliser?.let { unit ->
                runCatching {
                    for (band in 0 until unit.numberOfBands) {
                        bands.put(
                            JSONObject()
                                .put("hz", unit.getCenterFreq(band.toShort()) / 1000)
                                .put("level", unit.getBandLevel(band.toShort()).toInt()),
                        )
                    }
                }
            }
            return JSONObject()
                .put("name", name)
                .put("loaded", path.isNotEmpty())
                .put("title", title)
                .put("file", path)
                .put("playing", live?.isPlaying ?: false)
                .put("position", live?.currentPosition ?: 0L)
                .put("duration", (live?.duration ?: 0L).coerceAtLeast(0L))
                .put("cue", cue)
                .put("loopStart", loopStart)
                .put("loopEnd", loopEnd)
                .put("looping", loopEnd > loopStart)
                .put("tempo", tempo.toDouble())
                .put("gain", gain.toDouble())
                .put("bands", bands)
                .put("effects", JSONArray(available.toList()))
        }
    }

    private val decks = mapOf("a" to Deck("a"), "b" to Deck("b"))
    private val scope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())
    private var watching: Job? = null

    /** Where the fader is: 0 is all deck A, 1 is all deck B. */
    private var crossfade: Float = 0.5f

    /** Called after anything changes, with the whole state as JSON. */
    var onChanged: ((JSONObject) -> Unit)? = null

    /** True once either deck has been used, so the panel knows to draw. */
    var open: Boolean = false
        private set

    // ---------------------------------------------------------------- decks

    fun load(deckName: String, path: String, title: String): Boolean {
        val deck = decks[deckName] ?: return false
        val file = File(path)
        if (!file.isFile) {
            DebugLog.warn(TAG, "nothing to load on $deckName", path)
            return false
        }
        open = true
        val player = deck.ensure()
        player.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
        player.prepare()
        player.playWhenReady = false
        deck.path = path
        deck.title = title.ifEmpty { file.nameWithoutExtension }
        deck.cue = 0
        deck.loopStart = 0
        deck.loopEnd = 0
        applyLevels()
        report()
        startWatching()
        return true
    }

    fun play(deckName: String) {
        val deck = decks[deckName] ?: return
        deck.player?.play()
        startWatching()
        report()
    }

    fun pause(deckName: String) {
        decks[deckName]?.player?.pause()
        report()
    }

    /**
     * The cue button, which does what a cue button does.
     *
     * Pressed while stopped, it sets the cue point here. Pressed while
     * playing, it jumps back to the cue point - which is how you line a track
     * up against one that is already going.
     */
    fun cue(deckName: String) {
        val deck = decks[deckName] ?: return
        val player = deck.player ?: return
        if (player.isPlaying) {
            player.seekTo(deck.cue)
        } else {
            deck.cue = player.currentPosition
        }
        report()
    }

    fun seek(deckName: String, position: Long) {
        decks[deckName]?.player?.seekTo(position.coerceAtLeast(0))
        report()
    }

    /** Sets a loop between two points, or clears it when they are the same. */
    fun loop(deckName: String, start: Long, end: Long) {
        val deck = decks[deckName] ?: return
        deck.loopStart = start.coerceAtLeast(0)
        deck.loopEnd = if (end > start) end else 0
        startWatching()
        report()
    }

    /** How fast this deck runs, with the pitch corrected. */
    fun tempo(deckName: String, rate: Double) {
        val deck = decks[deckName] ?: return
        deck.tempo = rate.coerceIn(0.5, 2.0).toFloat()
        deck.player?.setPlaybackSpeed(deck.tempo)
        report()
    }

    /** This deck's own level, before the crossfader has its say. */
    fun gain(deckName: String, level: Double) {
        val deck = decks[deckName] ?: return
        deck.gain = level.coerceIn(0.0, 1.0).toFloat()
        applyLevels()
        report()
    }

    fun fader(position: Double) {
        crossfade = position.coerceIn(0.0, 1.0).toFloat()
        applyLevels()
        report()
    }

    /**
     * Both decks' volumes, from the fader and their own gains.
     *
     * Equal power: at the middle both sides are 0.707 rather than 0.5, which
     * is where two signals add up to the same loudness as one.
     */
    private fun applyLevels() {
        val angle = crossfade * (Math.PI / 2).toFloat()
        val left = cos(angle.toDouble()).toFloat()
        val right = sin(angle.toDouble()).toFloat()
        decks["a"]?.let { it.player?.volume = (left * it.gain).coerceIn(0f, 1f) }
        decks["b"]?.let { it.player?.volume = (right * it.gain).coerceIn(0f, 1f) }
    }

    // -------------------------------------------------------------- effects

    /**
     * Sets one effect on one deck.
     *
     * `level` is 0 to 1 for everything, and each effect maps it onto whatever
     * range Android gave it, so a panel never has to know that bass boost
     * counts to 1000 and reverb has six named presets.
     */
    fun effect(deckName: String, name: String, level: Double): Boolean {
        val deck = decks[deckName] ?: return false
        val amount = level.coerceIn(0.0, 1.0)
        return runCatching {
            when (name) {
                "bass" -> deck.bass?.setStrength((amount * 1000).toInt().toShort())
                "width" -> deck.width?.setStrength((amount * 1000).toInt().toShort())
                "louder" -> deck.louder?.setTargetGain((amount * 1500).toInt())
                "reverb" -> deck.reverb?.preset = when {
                    amount <= 0.01 -> PresetReverb.PRESET_NONE
                    amount < 0.25 -> PresetReverb.PRESET_SMALLROOM
                    amount < 0.5 -> PresetReverb.PRESET_MEDIUMROOM
                    amount < 0.75 -> PresetReverb.PRESET_LARGEROOM
                    amount < 0.95 -> PresetReverb.PRESET_MEDIUMHALL
                    else -> PresetReverb.PRESET_PLATE
                }
                else -> return false
            }
            report()
            true
        }.getOrElse { error ->
            DebugLog.warn(TAG, "$deckName could not set $name", error.message.orEmpty())
            false
        }
    }

    /** One equaliser band, from -1 (cut) through 0 (flat) to 1 (boost). */
    fun band(deckName: String, index: Int, level: Double): Boolean {
        val unit = decks[deckName]?.equaliser ?: return false
        return runCatching {
            val band = index.toShort()
            if (band < 0 || band >= unit.numberOfBands) return false
            val range = unit.bandLevelRange
            val low = range[0].toInt()
            val high = range[1].toInt()
            val amount = level.coerceIn(-1.0, 1.0)
            val decibels = if (amount >= 0) amount * high else -amount * low
            unit.setBandLevel(band, decibels.toInt().toShort())
            report()
            true
        }.getOrElse { error ->
            DebugLog.warn(TAG, "$deckName could not set band $index", error.message.orEmpty())
            false
        }
    }

    /** Puts every band back to flat. */
    fun flatten(deckName: String) {
        val unit = decks[deckName]?.equaliser ?: return
        runCatching {
            for (band in 0 until unit.numberOfBands) {
                unit.setBandLevel(band.toShort(), 0)
            }
        }
        report()
    }

    // --------------------------------------------------------------- state

    fun state(): JSONObject = JSONObject()
        .put("ok", true)
        .put("open", open)
        .put("crossfade", crossfade.toDouble())
        .put("a", decks["a"]?.describe() ?: JSONObject())
        .put("b", decks["b"]?.describe() ?: JSONObject())

    private fun report() {
        onChanged?.invoke(state())
    }

    /**
     * The loop watcher, and the thing that keeps the panel's clock moving.
     *
     * A quarter of a second: fast enough that a loop lands where it should and
     * the position readout does not stutter, slow enough that it costs
     * nothing. It stops itself the moment neither deck is playing and there is
     * no loop to police, so an idle panel is not a timer.
     */
    private fun startWatching() {
        if (watching?.isActive == true) return
        watching = scope.launch {
            while (isActive) {
                var busy = false
                decks.values.forEach { deck ->
                    val player = deck.player ?: return@forEach
                    if (player.isPlaying) {
                        busy = true
                        if (deck.loopEnd > deck.loopStart &&
                            player.currentPosition >= deck.loopEnd
                        ) {
                            player.seekTo(deck.loopStart)
                        }
                    }
                }
                if (busy) report()
                if (!busy) break
                delay(250)
            }
        }
    }

    /** Empties a deck. */
    fun eject(deckName: String) {
        decks[deckName]?.release()
        report()
    }

    /** Everything goes: both decks, both sets of effects, the watcher. */
    fun release() {
        watching?.cancel()
        watching = null
        decks.values.forEach { it.release() }
        open = false
    }
}
