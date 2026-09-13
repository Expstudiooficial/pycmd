package com.expstudio.pycmd.music

import android.content.ComponentName
import android.content.Context
import android.net.Uri
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.expstudio.pycmd.util.DebugLog
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** One track as the player needs it: enough to play it and to name it. */
data class MusicTrack(
    val id: String,
    val title: String,
    val artist: String = "",
    val file: String = "",
    val bytes: Long = 0,
    val duration: Long = 0,
    val added: Long = 0,
    val video: Boolean = false,
    val missing: Boolean = false,
    val album: String = "",
    val plays: Int = 0,
    /** Milliseconds since 1970, or 0 for never. */
    val lastPlayed: Long = 0,
)

/** What is playing right now, as much of it as a screen needs to draw. */
data class Playback(
    val connected: Boolean = false,
    val playing: Boolean = false,
    val buffering: Boolean = false,
    val trackId: String = "",
    val title: String = "",
    val artist: String = "",
    val position: Long = 0,
    val duration: Long = 0,
    val count: Int = 0,
    val loop: String = "off",
    val shuffle: Boolean = false,
    val queueName: String = "",
    val error: String = "",
) {
    /** True when there is a queue loaded at all, playing or paused. */
    val loaded: Boolean get() = count > 0
}

/**
 * The one door between the app and the thing making sound.
 *
 * `MusicService` owns the player. This owns a `MediaController`, which is the
 * same `Player` interface pointed at that service across a binder - so the
 * screen presses play on a player it does not own, in a process that keeps
 * going when the screen does not. Everything the UI knows about playback comes
 * out of [playback], which is refreshed from the controller's own callbacks
 * rather than guessed at: the notification, a headset button and the lock
 * screen can all change what is playing without this app being involved, and a
 * screen that tracked its own idea of "playing" would be wrong within seconds.
 *
 * The connection is made when there is music to play, not unconditionally at
 * startup: binding a media service on a phone whose library is empty would put
 * a player in the notification shade of somebody who never opened the tab.
 */
class MusicHub(context: Context) {
    /** The sleep timer, and when it goes off. See [sleepAfter]. */
    private var sleepJob: Job? = null
    private var sleepEndsAt: Long = 0


    private val appContext = context.applicationContext
    private val scope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())

    private val _playback = MutableStateFlow(Playback())
    val playback: StateFlow<Playback> = _playback.asStateFlow()

    private var controller: MediaController? = null
    private var connecting = false
    private var ticker: Job? = null

    /** The tracks handed to the player, so the screen can highlight the row. */
    private var queue: List<MusicTrack> = emptyList()
    private var queueName: String = ""

    /** Called after every change worth writing down - loop, shuffle, track. */
    var onChanged: ((Playback) -> Unit)? = null

    private val listener = object : Player.Listener {
        override fun onEvents(player: Player, events: Player.Events) {
            snapshot()
            if (events.containsAny(
                    Player.EVENT_MEDIA_ITEM_TRANSITION,
                    Player.EVENT_REPEAT_MODE_CHANGED,
                    Player.EVENT_SHUFFLE_MODE_ENABLED_CHANGED,
                    Player.EVENT_IS_PLAYING_CHANGED,
                )
            ) {
                onChanged?.invoke(_playback.value)
            }
            if (player.isPlaying) startTicking() else stopTicking()
        }

        override fun onPlayerError(error: PlaybackException) {
            // A file that will not decode is the common one, and it has to be
            // said out loud: silence looks identical to a broken app.
            DebugLog.error(TAG, "playback stopped", error.message.orEmpty())
            _playback.value = _playback.value.copy(
                error = error.message ?: "That file would not play.",
                playing = false,
            )
        }
    }

    /**
     * Binds to the service, starting it if it is not up.
     *
     * Safe to call as often as you like: the second call while the first is
     * still in flight does nothing, and a call once connected does nothing.
     */
    fun connect() {
        if (controller != null || connecting) return
        connecting = true
        val token = SessionToken(appContext, ComponentName(appContext, MusicService::class.java))
        val pending = MediaController.Builder(appContext, token).buildAsync()
        pending.addListener(
            {
                connecting = false
                runCatching { pending.get() }
                    .onSuccess { live ->
                        controller = live
                        live.addListener(listener)
                        snapshot()
                        DebugLog.debug(TAG, "connected to the player")
                    }
                    .onFailure { failure ->
                        DebugLog.error(TAG, "could not reach the player", failure.message.orEmpty())
                        _playback.value = _playback.value.copy(
                            connected = false,
                            error = "The player did not start.",
                        )
                    }
            },
            // The controller is a main-thread object, and so is everything
            // that listens to it.
            ContextCompat.getMainExecutor(appContext),
        )
    }

    /** Plays [tracks] from [startIndex], replacing whatever was queued. */
    fun play(tracks: List<MusicTrack>, startIndex: Int, name: String) {
        val playable = tracks.filterNot { it.missing || it.file.isBlank() }
        if (playable.isEmpty()) return
        queue = playable
        queueName = name

        // The index was into the list that was asked for, which may have had
        // missing files in it. Land on the track that was tapped.
        val wanted = tracks.getOrNull(startIndex)?.id
        val index = playable.indexOfFirst { it.id == wanted }.coerceAtLeast(0)

        withController { player ->
            player.setMediaItems(playable.map(::itemFor), index, 0L)
            player.prepare()
            player.play()
        }
    }

    fun toggle() = withController { player ->
        if (player.isPlaying) player.pause() else if (player.mediaItemCount > 0) player.play()
    }

    /**
     * The next track, and it means the next one.
     *
     * Two corrections to what the player would do on its own. With loop set to
     * *one*, "next" would replay this track, because repeat-one makes every
     * track its own successor - but a person pressing next has asked for a
     * different song. And with no repeat at all the last track has no
     * successor, where wrapping round is what a next button is for.
     */
    fun next() = withController { player ->
        val count = player.mediaItemCount
        if (count == 0) return@withController
        when {
            player.repeatMode == Player.REPEAT_MODE_ONE ->
                player.seekTo((player.currentMediaItemIndex + 1) % count, 0L)
            player.hasNextMediaItem() -> player.seekToNextMediaItem()
            else -> player.seekTo(0, 0L)
        }
    }

    /**
     * Back to the start of this track, or to the one before it.
     *
     * The first press restarts, as every music player does; only a press in
     * the first few seconds goes back one. Loop-one gets the same correction
     * as [next].
     */
    fun previous() = withController { player ->
        val count = player.mediaItemCount
        if (count == 0) return@withController
        when {
            player.currentPosition > RESTART_WINDOW_MS -> player.seekTo(0L)
            player.repeatMode == Player.REPEAT_MODE_ONE ->
                player.seekTo((player.currentMediaItemIndex + count - 1) % count, 0L)
            player.hasPreviousMediaItem() -> player.seekToPreviousMediaItem()
            else -> player.seekTo(0L)
        }
    }

    fun seekTo(millis: Long) = withController { player ->
        player.seekTo(millis.coerceAtLeast(0))
    }

    fun setLoop(mode: String) = withController { player ->
        player.repeatMode = when (mode) {
            "all" -> Player.REPEAT_MODE_ALL
            "one" -> Player.REPEAT_MODE_ONE
            else -> Player.REPEAT_MODE_OFF
        }
    }

    fun setShuffle(on: Boolean) = withController { player ->
        player.shuffleModeEnabled = on
    }

    /** Clears the queue, which is also what takes the notification away. */
    /**
     * How fast to play, with the pitch corrected.
     *
     * Media3 does this properly: `setPlaybackSpeed` time-stretches rather
     * than resampling, so a podcast at 1.5x is faster and not a chipmunk.
     * Clamped here as well as in Python because this is the call that reaches
     * the audio, and a speed of zero is a stall that looks like a crash.
     */
    fun setSpeed(speed: Float) = withController { player ->
        player.setPlaybackSpeed(speed.coerceIn(0.5f, 2.0f))
    }

    /**
     * Stops the music after so many minutes. Zero cancels a timer that is set.
     *
     * A coroutine rather than an alarm: the service is already alive while
     * something is playing, and a sleep timer that survives the player being
     * killed would turn the music off during the next session instead.
     */
    fun sleepAfter(minutes: Int) {
        sleepJob?.cancel()
        sleepJob = null
        sleepEndsAt = 0
        if (minutes <= 0) return
        val wait = minutes.coerceAtMost(600) * 60_000L
        sleepEndsAt = System.currentTimeMillis() + wait
        sleepJob = scope.launch {
            delay(wait)
            if (!isActive) return@launch
            sleepEndsAt = 0
            withController { player -> player.pause() }
        }
    }

    /** When the sleep timer will fire, or 0 when none is set. */
    fun sleepEndsAt(): Long = sleepEndsAt

    fun stop() {
        queue = emptyList()
        queueName = ""
        withController { player ->
            player.stop()
            player.clearMediaItems()
        }
        _playback.value = Playback(connected = controller != null)
    }

    /** Drops a track from the queue in place, without interrupting the rest. */
    fun forget(trackId: String) {
        val position = queue.indexOfFirst { it.id == trackId }
        if (position < 0) return
        queue = queue.filterNot { it.id == trackId }
        withController { player ->
            if (position < player.mediaItemCount) player.removeMediaItem(position)
        }
    }

    fun release() {
        sleepJob?.cancel()
        sleepJob = null
        sleepEndsAt = 0
        stopTicking()
        controller?.let { live ->
            live.removeListener(listener)
            live.release()
        }
        controller = null
        _playback.value = Playback()
    }

    private fun itemFor(track: MusicTrack): MediaItem = MediaItem.Builder()
        .setMediaId(track.id)
        .setUri(Uri.fromFile(File(track.file)))
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(track.title)
                // The notification's second line. A track with no artist tag
                // says what queue it is from, which is more use than a blank
                // line and more honest than inventing an artist.
                .setArtist(track.artist.ifBlank { queueName.ifBlank { "PyCmd" } })
                .setIsBrowsable(false)
                .setIsPlayable(true)
                .build(),
        )
        .build()

    /**
     * Runs [block] against the player, connecting first if it has to.
     *
     * A tap that arrives before the binder is up would otherwise be dropped,
     * and "the first press of play does nothing" is the kind of bug people
     * work around forever instead of reporting.
     */
    private fun withController(block: (MediaController) -> Unit) {
        val live = controller
        if (live != null) {
            runCatching { block(live) }
                .onFailure { DebugLog.error(TAG, "the player refused that", it.message.orEmpty()) }
            snapshot()
            return
        }
        connect()
        scope.launch {
            var waited = 0L
            while (isActive && controller == null && waited < CONNECT_WAIT_MS) {
                delay(POLL_MS)
                waited += POLL_MS
            }
            val late = controller ?: return@launch
            runCatching { block(late) }
                .onFailure { DebugLog.error(TAG, "the player refused that", it.message.orEmpty()) }
            snapshot()
        }
    }

    private fun snapshot() {
        val player = controller
        if (player == null) {
            _playback.value = _playback.value.copy(connected = false)
            return
        }
        val length = player.duration
        _playback.value = Playback(
            connected = true,
            playing = player.isPlaying,
            buffering = player.playbackState == Player.STATE_BUFFERING,
            trackId = player.currentMediaItem?.mediaId.orEmpty(),
            title = player.mediaMetadata.title?.toString().orEmpty(),
            artist = player.mediaMetadata.artist?.toString().orEmpty(),
            position = player.currentPosition.coerceAtLeast(0),
            // An unknown duration comes back as a large negative constant, and
            // a progress bar given that draws itself inside out.
            duration = if (length > 0) length else 0,
            count = player.mediaItemCount,
            loop = when (player.repeatMode) {
                Player.REPEAT_MODE_ALL -> "all"
                Player.REPEAT_MODE_ONE -> "one"
                else -> "off"
            },
            shuffle = player.shuffleModeEnabled,
            queueName = queueName,
            error = _playback.value.error.takeIf { player.playbackState == Player.STATE_IDLE }
                .orEmpty(),
        )
    }

    /**
     * The position is the one thing no callback reports, because it changes
     * continuously. Half a second is smooth enough for a progress bar and
     * cheap enough to leave running only while something is playing.
     */
    private fun startTicking() {
        if (ticker?.isActive == true) return
        ticker = scope.launch {
            while (isActive) {
                delay(TICK_MS)
                val player = controller ?: break
                if (!player.isPlaying) break
                _playback.value = _playback.value.copy(
                    position = player.currentPosition.coerceAtLeast(0),
                    duration = player.duration.takeIf { it > 0 } ?: _playback.value.duration,
                )
            }
        }
    }

    private fun stopTicking() {
        ticker?.cancel()
        ticker = null
    }

    private companion object {
        const val TAG = "music"
        const val TICK_MS = 500L
        const val POLL_MS = 50L
        const val CONNECT_WAIT_MS = 4000L
        const val RESTART_WINDOW_MS = 4000L
    }
}
