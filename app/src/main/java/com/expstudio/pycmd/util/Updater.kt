package com.expstudio.pycmd.util

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import androidx.core.net.toUri
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** What the update manifest says the newest build is. */
data class Release(
    val versionCode: Int,
    val versionName: String,
    val url: String,
    val sha256: String,
    val bytes: Long = 0,
    val notes: String = "",
    val packageName: String = "",
) {
    /**
     * What to call the download.
     *
     * Taken from the URL but not trusted from it: the address can be set by
     * whoever the user pointed the app at, and a name like `..` would resolve
     * to the folder above - which is the app's own storage. Letters, digits
     * and the three punctuation marks a filename needs, ending in `.apk`, or
     * else a fixed name.
     */
    val fileName: String
        get() {
            val raw = url.substringAfterLast('/').substringBefore('?')
            val safe = raw.filter { it.isLetterOrDigit() || it in "-_." }.trimStart('.')
            return if (safe.length in 5..80 && safe.endsWith(".apk")) safe else "PyCmd-update.apk"
        }
}

/** One APK in the archive of past versions. */
data class KeptVersion(
    val file: File,
    val versionName: String,
    val versionCode: Int,
    val bytes: Long,
    val savedAt: Long,
    val packageName: String,
)

/** What an APK sitting on disk actually is, read out of the file itself. */
data class ApkFacts(
    val packageName: String,
    val versionCode: Int,
    val versionName: String,
    /** Lowercase hex SHA-256 of the signing certificate, or "" if unreadable. */
    val signature: String,
)

/** Where the app is in the check - download - install story. */
sealed interface UpdateState {

    /** Nothing asked for yet. */
    data object Idle : UpdateState

    /** Fetching the manifest. */
    data object Checking : UpdateState

    /** The manifest was read and this build is the newest one. */
    data class UpToDate(val versionName: String) : UpdateState

    /** There is a newer build, not downloaded yet. */
    data class Available(val release: Release) : UpdateState

    /** Pulling the APK down. [total] is 0 when the server would not say. */
    data class Downloading(val release: Release, val bytes: Long, val total: Long) : UpdateState

    /** Downloaded, hash checked, signature checked: ready for the installer. */
    data class Ready(val release: Release, val file: File) : UpdateState

    /** Something went wrong, said in a sentence rather than a stack trace. */
    data class Failed(val message: String, val detail: String = "") : UpdateState
}

/**
 * Replacing the installed app with a newer build, without uninstalling it.
 *
 * Android will let an APK replace the one already on the phone when three
 * things line up: the same package name, the same signing key, and a
 * versionCode that is not lower. Get all three and the workspace, the installed
 * packages and every setting stay exactly where they are - the app is upgraded
 * underneath them. Miss the signature and the installer refuses with "App not
 * installed", which leaves uninstall-first as the only way in, and uninstalling
 * is precisely what takes the workspace with it.
 *
 * So this checks both before it offers to install anything, rather than letting
 * the system installer be the one to break the news. The repo now carries a
 * fixed signing key for the same reason (see keystore/ and app/build.gradle.kts):
 * Gradle's per-machine debug key would have made every build a different app.
 *
 * The download is verified against the SHA-256 in the manifest before it is
 * offered. That check is what makes an update safe to take: the manifest comes
 * over HTTPS, and the hash in it is what says the bytes that arrived are the
 * bytes that were published.
 */
object Updater {

    private const val TAG = "update"

    /**
     * Where the app looks unless the user points it somewhere else.
     *
     * The repository was renamed from `space_dodge-1.0` to `pycmd` before
     * 2.6.0. Builds up to 2.5.9 have the old name in them and still find this
     * file, because GitHub redirects a renamed repository - but only until
     * somebody creates a new repository under the old name, at which point
     * those builds would follow the redirect to a stranger's file. That is
     * the reason to move every URL at once rather than leave them: it limits
     * the exposure to the versions already installed.
     */
    const val DEFAULT_MANIFEST_URL =
        "https://raw.githubusercontent.com/expstudiooficial/pycmd/" +
            "claude/python-mobile-cmd-android-dj1ixb/dist/latest.json"

    /**
     * This app's own source, as a zip.
     *
     * codeload is GitHub's plain-file host for archives: no API, no token, and
     * one redirect-free URL per branch. A fork changes this line and the one
     * above it, and its users get its source instead.
     */
    const val SOURCE_ZIP_URL =
        "https://codeload.github.com/expstudiooficial/pycmd/zip/refs/heads/" +
            "claude/python-mobile-cmd-android-dj1ixb"

    private const val CONNECT_TIMEOUT = 20_000
    private const val READ_TIMEOUT = 30_000

    /** A manifest is a few hundred bytes; this is already generous. */
    private const val MAX_MANIFEST_BYTES = 64 * 1024

    /** An APK this size is already far past anything this app ships. */
    private const val MAX_APK_BYTES = 400L * 1024 * 1024

    /** Redirect chains are normal on release hosts; a loop is not. */
    private const val MAX_REDIRECTS = 5

    /** Where a download in progress lives. Small, and emptied as it goes. */
    fun folder(context: Context): File = File(context.filesDir, "updates")

    /**
     * Where past versions are kept.
     *
     * On external app storage rather than in `filesDir`, for two reasons: the
     * app's own storage figure stays about the app rather than about an
     * archive of installers, and a phone short of room reports this space
     * where its user can see it.
     *
     * Both are still deleted when PyCmd is uninstalled - Android gives an app
     * no folder that survives that. Anything you actually want to keep across
     * an uninstall has to be saved out to the phone, which the card offers.
     */
    fun library(context: Context): File {
        val external = runCatching { context.getExternalFilesDir("versions") }.getOrNull()
        return external ?: File(context.filesDir, "versions")
    }

    /** Every APK kept, newest build first. */
    fun versions(context: Context): List<KeptVersion> {
        val files = library(context).listFiles()?.filter { it.isFile } ?: return emptyList()
        return files.mapNotNull { file ->
            val facts = inspect(context, file) ?: return@mapNotNull null
            KeptVersion(
                file = file,
                versionName = facts.versionName.ifBlank { file.name },
                versionCode = facts.versionCode,
                bytes = file.length(),
                savedAt = file.lastModified(),
                packageName = facts.packageName,
            )
        }.sortedByDescending { it.versionCode }
    }

    /**
     * Files a verified download away, and prunes the archive to [capBytes].
     *
     * Oldest build first, and never the one running: going back to the version
     * you are on is the one rollback nobody needs, but the file is also the
     * only copy of it if the update it came from is gone.
     */
    fun keep(context: Context, apk: File, capBytes: Long, currentVersionCode: Int): File? {
        if (capBytes <= 0) return null
        val library = library(context)
        library.mkdirs()
        val target = File(library, apk.name)
        if (target.absolutePath != apk.absolutePath) {
            runCatching { apk.copyTo(target, overwrite = true) }
                .onFailure {
                    DebugLog.warn(TAG, "could not keep ${apk.name}", it.message.orEmpty())
                    return null
                }
        }
        prune(context, capBytes, currentVersionCode)
        return target.takeIf { it.isFile }
    }

    /** Deletes oldest-first until the archive fits under [capBytes]. */
    fun prune(context: Context, capBytes: Long, currentVersionCode: Int) {
        if (capBytes <= 0) {
            clearLibrary(context)
            return
        }
        val kept = versions(context).sortedBy { it.versionCode }.toMutableList()
        var total = kept.sumOf { it.bytes }
        for (version in kept) {
            if (total <= capBytes) break
            if (version.versionCode == currentVersionCode) continue
            if (version.file.delete()) {
                total -= version.bytes
                DebugLog.info(TAG, "pruned an old version", version.versionName)
            }
        }
    }

    fun clearLibrary(context: Context): Int {
        val files = library(context).listFiles()?.filter { it.isFile } ?: return 0
        return files.count { it.delete() }
    }

    /** How much room the archive is using. */
    fun libraryBytes(context: Context): Long =
        library(context).listFiles()?.sumOf { it.length() } ?: 0L

    /**
     * Reads the manifest.
     *
     * HTTPS only. The whole safety of this rests on the hash in the manifest
     * being the publisher's, and plain HTTP cannot promise that - anything
     * that could swap the APK could swap the hash beside it just as easily.
     */
    suspend fun fetch(url: String): Result<Release> = withContext(Dispatchers.IO) {
        runCatching {
            val trimmed = url.trim()
            require(trimmed.startsWith("https://")) {
                "The update address has to start with https:// - a plain http one " +
                    "cannot promise the file is the published one."
            }
            val text = openStream(trimmed) { _, stream ->
                // Read a bounded amount rather than trusting Content-Length:
                // a server that declares nothing would otherwise be allowed to
                // stream until the phone ran out of memory.
                val head = ByteArray(MAX_MANIFEST_BYTES)
                var filled = 0
                while (filled < head.size) {
                    val read = stream.read(head, filled, head.size - filled)
                    if (read < 0) break
                    filled += read
                }
                require(filled < head.size) { "That address did not answer with a manifest." }
                head.decodeToString(0, filled)
            }
            parse(text)
        }.onFailure {
            // A cancelled check is not a failed one, and swallowing it here
            // would leave the caller's coroutine believing it is still alive.
            if (it is CancellationException) throw it
            DebugLog.warn(TAG, "could not read the update manifest", it.message.orEmpty())
        }
    }

    /** Turns the manifest's JSON into a [Release], complaining in plain words. */
    fun parse(text: String): Release {
        val json = runCatching { JSONObject(text) }
            .getOrElse { throw IOException("That address did not answer with a manifest.") }
        val release = Release(
            versionCode = json.optInt("versionCode", 0),
            versionName = json.optString("versionName").ifBlank { "?" },
            url = json.optString("url"),
            sha256 = json.optString("sha256").lowercase(),
            bytes = json.optLong("bytes", 0),
            notes = json.optString("notes"),
            packageName = json.optString("package"),
        )
        if (release.versionCode <= 0) throw IOException("The manifest has no versionCode in it.")
        if (!release.url.startsWith("https://")) {
            throw IOException("The manifest points at something that is not an https:// address.")
        }
        if (release.sha256.length != 64 || release.sha256.any { it !in "0123456789abcdef" }) {
            throw IOException("The manifest has no usable sha256 in it.")
        }
        return release
    }

    /**
     * Downloads the APK and checks it before saying it is ready.
     *
     * Written to a neighbouring `.part` and moved into place only once the hash
     * matches, so a download cut off halfway - a tunnel, a dropped wifi - can
     * never leave a half APK sitting there looking installable.
     */
    suspend fun download(
        context: Context,
        release: Release,
        onProgress: (Long, Long) -> Unit,
    ): Result<File> = withContext(Dispatchers.IO) {
        runCatching {
            val folder = folder(context)
            folder.mkdirs()
            val target = File(folder, release.fileName)

            // Kept from a previous run and still the right bytes: nothing to do.
            if (target.isFile && sha256(target) == release.sha256) {
                DebugLog.info(TAG, "the update was already downloaded", target.name)
                return@runCatching target
            }
            // Anything else in here is a version nobody is going to install now.
            folder.listFiles()?.forEach { it.delete() }

            val part = File(folder, release.fileName + ".part")
            val digest = MessageDigest.getInstance("SHA-256")
            var written = 0L
            openStream(release.url) { connection, stream ->
                val total = connection.contentLengthLong.takeIf { it > 0 } ?: release.bytes
                if (total > MAX_APK_BYTES) throw IOException("That download is far too big to be PyCmd.")
                onProgress(0, total)
                part.outputStream().use { out ->
                    val buffer = ByteArray(64 * 1024)
                    var lastReport = 0L
                    while (true) {
                        ensureActive()
                        val read = stream.read(buffer)
                        if (read < 0) break
                        out.write(buffer, 0, read)
                        digest.update(buffer, 0, read)
                        written += read
                        if (written > MAX_APK_BYTES) {
                            throw IOException("That download is far too big to be PyCmd.")
                        }
                        if (written - lastReport >= 128 * 1024) {
                            lastReport = written
                            onProgress(written, total)
                        }
                    }
                    out.flush()
                }
                onProgress(written, total)
            }

            val got = digest.digest().joinToString("") { "%02x".format(it) }
            if (got != release.sha256) {
                part.delete()
                DebugLog.warn(TAG, "the download did not match its hash", got)
                throw IOException(
                    "The file that arrived is not the published one - it was not installed. " +
                        "Try again on a different connection.",
                )
            }
            if (!part.renameTo(target)) {
                part.copyTo(target, overwrite = true)
                part.delete()
            }
            DebugLog.info(TAG, "downloaded ${target.name}", "$written bytes, hash matches")
            target
        }.onFailure {
            if (it is CancellationException) throw it
            DebugLog.warn(TAG, "the update download failed", it.message.orEmpty())
        }
    }

    /** Reads a downloaded APK: what it calls itself, and who signed it. */
    fun inspect(context: Context, apk: File): ApkFacts? {
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION") PackageManager.GET_SIGNATURES
        }
        val info = runCatching {
            context.packageManager.getPackageArchiveInfo(apk.absolutePath, flags)
        }.getOrNull() ?: return null
        val code = @Suppress("DEPRECATION") info.versionCode
        return ApkFacts(
            packageName = info.packageName.orEmpty(),
            versionCode = code,
            versionName = info.versionName.orEmpty(),
            signature = certificateOf(info),
        )
    }

    /** The signing certificate of the app that is running, to compare against. */
    fun installedSignature(context: Context): String {
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION") PackageManager.GET_SIGNATURES
        }
        val info = runCatching {
            context.packageManager.getPackageInfo(context.packageName, flags)
        }.getOrNull() ?: return ""
        return certificateOf(info)
    }

    private fun certificateOf(info: android.content.pm.PackageInfo): String {
        val raw = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val signing = info.signingInfo ?: return ""
            (signing.apkContentsSigners ?: return "").firstOrNull()
        } else {
            @Suppress("DEPRECATION") info.signatures?.firstOrNull()
        } ?: return ""
        val digest = MessageDigest.getInstance("SHA-256").digest(raw.toByteArray())
        return digest.joinToString("") { "%02x".format(it) }
    }

    /**
     * Says why an APK would not install over this one, or null when it will.
     *
     * Both answers are worth having before the installer is opened: a
     * mismatched signature means "App not installed" whatever the user does,
     * and knowing that first is the difference between a failed tap and
     * uninstalling an app that is holding all of your files.
     */
    fun blocker(context: Context, apk: File): String? {
        val facts = inspect(context, apk)
            ?: return "Android could not read that file as an app."
        if (facts.packageName != context.packageName) {
            return "That build calls itself ${facts.packageName}, this one is " +
                "${context.packageName}. Android would install it beside this app " +
                "instead of updating it, and your files would stay in this one."
        }
        val mine = installedSignature(context)
        if (mine.isNotEmpty() && facts.signature.isNotEmpty() && mine != facts.signature) {
            return "That build was signed with a different key, so Android will not " +
                "let it replace this one. Do not uninstall to make room for it - " +
                "that would take your workspace with it. Export your workspace first."
        }
        return null
    }

    /** True when Android will let this app hand an APK to the installer. */
    fun canInstall(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
            context.packageManager.canRequestPackageInstalls()

    /** Opens the system page where "install unknown apps" is granted. */
    fun requestInstallPermission(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val intent = Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            "package:${context.packageName}".toUri(),
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { context.startActivity(intent) }
            .onFailure { DebugLog.warn(TAG, "no unknown-sources page on this phone", it.message.orEmpty()) }
    }

    /** Hands the APK to the system installer. The user still confirms it there. */
    fun install(context: Context, apk: File): Result<Unit> = runCatching {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.updates", apk)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        DebugLog.info(TAG, "handed ${apk.name} to the installer")
    }.onFailure { DebugLog.warn(TAG, "could not open the installer", it.message.orEmpty()) }

    /**
     * Drops downloads that are not newer than what is running.
     *
     * After an update installs, the APK it came from is 30-odd MB describing
     * the app you are already using. A `.part` left by a download that never
     * finished reads as nothing at all, and goes the same way.
     */
    fun tidy(context: Context, currentVersionCode: Int) {
        val files = folder(context).listFiles() ?: return
        for (file in files) {
            val facts = inspect(context, file)
            if (facts == null || facts.versionCode <= currentVersionCode) {
                if (file.delete()) DebugLog.debug(TAG, "dropped a stale update", file.name)
            }
        }
    }

    /** Throws away a downloaded APK once it is installed or unwanted. */
    fun forget(context: Context) {
        folder(context).listFiles()?.forEach { it.delete() }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /**
     * GETs a URL and hands the body to [body], following redirects by hand.
     *
     * HttpURLConnection follows redirects itself, but silently refuses the ones
     * that change protocol - and http to https is exactly the hop a release
     * host makes. Doing it here also keeps every hop on https, which the
     * automatic follower would not guarantee.
     */
    private fun <T> openStream(
        url: String,
        body: (HttpURLConnection, java.io.InputStream) -> T,
    ): T {
        var address = url
        var hops = 0
        while (true) {
            require(address.startsWith("https://")) {
                "That address redirected somewhere that is not https."
            }
            val connection = (URL(address).openConnection() as HttpURLConnection).apply {
                connectTimeout = CONNECT_TIMEOUT
                readTimeout = READ_TIMEOUT
                instanceFollowRedirects = false
                setRequestProperty("Accept-Encoding", "identity")
                setRequestProperty("User-Agent", "PyCmd-updater")
                // A manifest published minutes ago is the whole point of
                // checking, so a cached answer is worse than a slow one.
                setRequestProperty("Cache-Control", "no-cache")
            }
            try {
                val code = connection.responseCode
                if (code in 300..399) {
                    val next = connection.getHeaderField("Location")
                        ?: throw IOException("That address redirected to nowhere.")
                    hops += 1
                    if (hops > MAX_REDIRECTS) throw IOException("That address redirects in a loop.")
                    address = if (next.startsWith("http")) next else URL(URL(address), next).toString()
                    continue
                }
                if (code == 404) {
                    throw IOException("There is nothing published at that address yet (404).")
                }
                if (code != 200) throw IOException("The server answered $code.")
                return connection.inputStream.use { body(connection, it) }
            } finally {
                connection.disconnect()
            }
        }
    }
}
