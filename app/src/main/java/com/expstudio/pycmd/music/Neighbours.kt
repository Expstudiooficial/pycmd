package com.expstudio.pycmd.music

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.net.Uri
import android.provider.MediaStore
import android.service.notification.NotificationListenerService
import com.expstudio.pycmd.util.DebugLog
import org.json.JSONArray
import org.json.JSONObject

private const val TAG = "neighbours"

/**
 * The service that exists so the permission can be granted.
 *
 * Reading other apps' media sessions needs notification access, and Android
 * only offers that switch to an app that declares a `NotificationListenerService`.
 * This one listens to nothing and overrides nothing: it never reads a
 * notification, never posts one, and never touches anything but its own
 * existence in the manifest. That is the entire job.
 *
 * It is worth being blunt about the trade, because notification access is a
 * powerful permission and PyCmd is asking for it to do something small: with
 * it, PyCmd can see and control whatever is playing on this phone. Without
 * it, everything else in Music Pro still works. Nothing in PyCmd turns it on
 * for you; the switch is in Android's own settings and you are taken to it.
 */
class SessionAccess : NotificationListenerService()

/**
 * Whatever else is playing on this phone, and the apps that could play more.
 *
 * ## Controlling another app
 *
 * Every well-behaved Android music app publishes a media session - it is what
 * puts the track on the lock screen. `MediaSessionManager` hands out
 * controllers for those sessions to an app with notification access, and a
 * controller's transport controls are the real thing: play, pause, skip, seek.
 * So "connect almost any music app" is not a plugin for each one. It is one
 * mechanism that works for all of them because they all already speak it.
 *
 * What it cannot do is reach inside another app: it cannot read their
 * library, search their catalogue, download their tracks, or play something
 * they have not been told to play. It drives the transport of whatever that
 * app is already doing. Anything more would need that service's own API and
 * your own account with them.
 *
 * ## Searching in another app
 *
 * For "play me something", Android has an intent every music app is expected
 * to answer - `INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH` - which hands a query to
 * the app and lets *it* decide what that means. One search box, every app
 * that is installed, and no API keys: the app does the searching with the
 * account you already pay it for. That is as far as this goes, and it is
 * further than it sounds.
 */
class Neighbours(private val context: Context) {

    private val manager: MediaSessionManager? by lazy {
        runCatching {
            context.getSystemService(Context.MEDIA_SESSION_SERVICE) as? MediaSessionManager
        }.getOrNull()
    }

    private val listener = ComponentName(context, SessionAccess::class.java)

    /** Whether notification access has been granted to PyCmd. */
    fun allowed(): Boolean = runCatching {
        val enabled = android.provider.Settings.Secure.getString(
            context.contentResolver, "enabled_notification_listeners",
        ).orEmpty()
        enabled.split(":").any { part ->
            part.contains(context.packageName) && part.contains("SessionAccess")
        }
    }.getOrDefault(false)

    /** The settings screen with the switch on it. */
    fun permissionIntent(): Intent =
        Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    private fun controllers(): List<MediaController> {
        if (!allowed()) return emptyList()
        return runCatching {
            manager?.getActiveSessions(listener).orEmpty()
                // PyCmd's own session is in this list too, and offering to
                // control the thing you are looking at from inside itself is
                // a loop nobody wanted.
                .filterNot { it.packageName == context.packageName }
        }.getOrElse { error ->
            DebugLog.warn(TAG, "could not read the active sessions", error.message.orEmpty())
            emptyList()
        }
    }

    /** What every other app is playing, as much as each will say. */
    fun playing(): JSONObject {
        val rows = JSONArray()
        controllers().forEach { controller ->
            val metadata = controller.metadata
            val state = controller.playbackState
            rows.put(
                JSONObject()
                    .put("package", controller.packageName)
                    .put("app", labelFor(controller.packageName))
                    .put(
                        "title",
                        metadata?.getString(android.media.MediaMetadata.METADATA_KEY_TITLE)
                            .orEmpty(),
                    )
                    .put(
                        "artist",
                        metadata?.getString(android.media.MediaMetadata.METADATA_KEY_ARTIST)
                            .orEmpty(),
                    )
                    .put(
                        "album",
                        metadata?.getString(android.media.MediaMetadata.METADATA_KEY_ALBUM)
                            .orEmpty(),
                    )
                    .put(
                        "duration",
                        metadata?.getLong(android.media.MediaMetadata.METADATA_KEY_DURATION)
                            ?: 0L,
                    )
                    .put("position", state?.position ?: 0L)
                    .put("playing", state?.state == PlaybackState.STATE_PLAYING),
            )
        }
        return JSONObject()
            .put("ok", true)
            .put("allowed", allowed())
            .put("sessions", rows)
    }

    /**
     * Tells one app to do something: play, pause, next, previous or stop.
     *
     * `packageName` blank means whatever is playing, which is what a single
     * play/pause button on a panel wants.
     */
    fun control(packageName: String, what: String): Boolean {
        val found = controllers().firstOrNull { controller ->
            packageName.isEmpty() ||
                controller.packageName.equals(packageName, ignoreCase = true)
        } ?: return false
        return runCatching {
            when (what) {
                "play" -> found.transportControls.play()
                "pause" -> found.transportControls.pause()
                "toggle" ->
                    if (found.playbackState?.state == PlaybackState.STATE_PLAYING) {
                        found.transportControls.pause()
                    } else {
                        found.transportControls.play()
                    }
                "next" -> found.transportControls.skipToNext()
                "previous" -> found.transportControls.skipToPrevious()
                "stop" -> found.transportControls.stop()
                else -> return false
            }
            true
        }.getOrElse { error ->
            DebugLog.warn(TAG, "could not control ${found.packageName}", error.message.orEmpty())
            false
        }
    }

    /** Seeks inside another app's track, when that app allows it. */
    fun seek(packageName: String, position: Long): Boolean {
        val found = controllers().firstOrNull { controller ->
            packageName.isEmpty() ||
                controller.packageName.equals(packageName, ignoreCase = true)
        } ?: return false
        return runCatching {
            found.transportControls.seekTo(position.coerceAtLeast(0))
            true
        }.getOrDefault(false)
    }

    /**
     * Every installed app that says it can play something from a search.
     *
     * Declared in the manifest's `<queries>` block, because since Android 11
     * an app cannot see what else is installed unless it says what it is
     * looking for.
     */
    fun searchApps(): JSONObject {
        val intent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH)
        val rows = JSONArray()
        runCatching {
            val packages = context.packageManager.queryIntentActivities(intent, 0)
            packages.forEach { info ->
                val name = info.activityInfo?.packageName.orEmpty()
                if (name.isNotEmpty() && name != context.packageName) {
                    rows.put(
                        JSONObject()
                            .put("package", name)
                            .put("app", labelFor(name)),
                    )
                }
            }
        }.onFailure { error ->
            DebugLog.warn(TAG, "could not list the music apps", error.message.orEmpty())
        }
        return JSONObject().put("ok", true).put("apps", rows)
    }

    /**
     * Hands a search to one music app, or to whichever the phone picks.
     *
     * The query is the app's to interpret. "blue monday" means whatever that
     * app decides it means, with the account you have with it, which is the
     * only honest way for one app to search another's catalogue.
     */
    fun searchIn(packageName: String, query: String): Boolean {
        if (query.isBlank()) return false
        val intent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH)
            .putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
            .putExtra(android.app.SearchManager.QUERY, query)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (packageName.isNotEmpty()) intent.setPackage(packageName)
        return runCatching {
            context.startActivity(intent)
            true
        }.getOrElse { error ->
            DebugLog.warn(TAG, "no app took the search", error.message.orEmpty())
            false
        }
    }

    /** Opens another app, for when driving it from here is not enough. */
    fun openApp(packageName: String): Boolean = runCatching {
        val intent = context.packageManager.getLaunchIntentForPackage(packageName)
            ?: return false
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    }.getOrDefault(false)

    /** Opens a web address, for a catalogue that has no app installed. */
    fun openLink(address: String): Boolean = runCatching {
        val uri = Uri.parse(address)
        if (uri.scheme != "https" && uri.scheme != "http") return false
        context.startActivity(
            Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
        true
    }.getOrDefault(false)

    private fun labelFor(packageName: String): String = runCatching {
        val manager = context.packageManager
        manager.getApplicationLabel(
            manager.getApplicationInfo(packageName, PackageManager.GET_META_DATA),
        ).toString()
    }.getOrDefault(packageName)
}
