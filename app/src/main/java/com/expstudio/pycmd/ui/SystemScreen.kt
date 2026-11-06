package com.expstudio.pycmd.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.BuildConfig
import com.expstudio.pycmd.util.Branding
import com.expstudio.pycmd.util.KeptVersion
import com.expstudio.pycmd.util.UpdateState
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** What the app is using, and the housekeeping worth having a button for. */
data class SystemInfo(
    val pythonVersion: String = "",
    val appVersion: String = "",
    val abi: String = "",
    val androidVersion: String = "",
    val device: String = "",
    val workspaceBytes: Long = 0,
    val workspaceFiles: Int = 0,
    val packagesBytes: Long = 0,
    val downloadsBytes: Long = 0,
    val pluginBytes: Long = 0,
    val versionsBytes: Long = 0,
    val cacheBytes: Long = 0,
    val cacheFiles: Int = 0,
    val freeBytes: Long = 0,
    val servers: Int = 0,
    val plugins: Int = 0,
    val threads: Int = 0,
    /** Every processor this machine can run code for, best first. */
    val abis: String = "",
    /** Whether this looks like an emulator rather than a phone. */
    val emulator: Boolean = false,
    /** One line on whether this build's Python matches this processor. */
    val deviceVerdict: String = "",
    /** The whole lot as text, for the Copy button and bug reports. */
    val deviceReport: String = "",
)

/**
 * The screen that answers "what is this app doing with my phone".
 *
 * Every number here is one somebody has asked about at some point: how much
 * space the workspace takes, whether pip's packages are the thing filling the
 * disk, and how much is safe to delete.
 */
@Composable
fun SystemScreen(
    info: SystemInfo,
    busy: String,
    onRefresh: () -> Unit,
    onClearCache: () -> Unit,
    onClearPycache: () -> Unit,
    onExportLog: () -> Unit,
    update: UpdateState,
    updateSource: String,
    onCheckForUpdate: () -> Unit,
    onDownloadUpdate: () -> Unit,
    onCancelUpdate: () -> Unit,
    onInstallUpdate: () -> Unit,
    onDismissUpdate: () -> Unit,
    onSetUpdateSource: (String) -> Unit,
    backgroundChecks: Boolean,
    backgroundDownload: Boolean,
    onSetBackgroundChecks: (Boolean) -> Unit,
    onSetBackgroundDownload: (Boolean) -> Unit,
    versions: List<KeptVersion>,
    versionsCap: Long,
    onSetVersionsCap: (Long) -> Unit,
    onInstallVersion: (KeptVersion) -> Unit,
    onDeleteVersion: (KeptVersion) -> Unit,
    onDeleteAllVersions: () -> Unit,
    onSaveVersionToPhone: (KeptVersion) -> Unit,
    onBackupWorkspace: () -> Unit,
    onEmail: (String) -> Unit,
    onCopy: (String) -> Unit,
    onShowWhatsNew: () -> Unit,
    modifier: Modifier = Modifier,
    /** Null when the examples are still there and nothing needs restoring. */
    onRestoreExamples: (() -> Unit)? = null,
    /** Sections plugins have added to this screen; empty when none are on. */
    pluginSections: @Composable () -> Unit = {},
) {
    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionTitle("Runtime") }
        item {
            PyCard {
                InfoRow("Python", info.pythonVersion.ifEmpty { "starting..." })
                InfoRow(Branding.NAME, info.appVersion)
                InfoRow("Architecture", info.abi)
                InfoRow("Android", info.androidVersion)
                InfoRow("Device", info.device)
                InfoRow("Threads", info.threads.toString())
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    GhostButton(
                        "What's new in ${BuildConfig.VERSION_NAME}",
                        PyIcons.Star,
                        onClick = onShowWhatsNew,
                    )
                }
            }
        }

        // Its own section because of what it is for: this is the card people
        // are asked to paste when PyCmd will not start, and the answer is
        // nearly always on it.
        item { SectionTitle("This machine") }
        item {
            PyCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            if (info.emulator) "Emulator" else "Device",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text(
                            info.deviceVerdict.ifEmpty { "Reading..." },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (info.emulator) {
                        StatusChip("emulated", MaterialTheme.colorScheme.tertiary)
                    }
                }
                Spacer(Modifier.height(10.dp))
                InfoRow("Processors", info.abis.ifEmpty { "unknown" })
                if (info.emulator) {
                    Text(
                        "Emulators are supported. If PyCmd is slow here, start the " +
                            "emulator with hardware graphics and use an x86_64 " +
                            "system image rather than an arm64 one - an arm64 image " +
                            "on a PC is translated instruction by instruction, which " +
                            "is what reads as the app hanging. Appearance has an " +
                            "animations-off switch that helps too.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(10.dp))
                }
                GhostButton(
                    "Copy this",
                    PyIcons.ContentCopy,
                    onClick = { onCopy(info.deviceReport) },
                )
            }
        }

        item { SectionTitle("Updates") }
        item {
            UpdateCard(
                state = update,
                source = updateSource,
                backgroundChecks = backgroundChecks,
                backgroundDownload = backgroundDownload,
                onSetBackgroundChecks = onSetBackgroundChecks,
                onSetBackgroundDownload = onSetBackgroundDownload,
                onCheck = onCheckForUpdate,
                onDownload = onDownloadUpdate,
                onCancel = onCancelUpdate,
                onInstall = onInstallUpdate,
                onDismiss = onDismissUpdate,
                onSetSource = onSetUpdateSource,
            )
        }

        item { SectionTitle("Versions kept") }
        item {
            VersionsCard(
                versions = versions,
                cap = versionsCap,
                freeBytes = info.freeBytes,
                onSetCap = onSetVersionsCap,
                onInstall = onInstallVersion,
                onDelete = onDeleteVersion,
                onDeleteAll = onDeleteAllVersions,
                onSaveToPhone = onSaveVersionToPhone,
                onBackupWorkspace = onBackupWorkspace,
            )
        }

        item { SectionTitle("Storage") }
        item {
            PyCard {
                InfoRow("Workspace", "${readable(info.workspaceBytes)}  ·  ${info.workspaceFiles} files")
                InfoRow("Installed packages", readable(info.packagesBytes))
                InfoRow("Downloads", readable(info.downloadsBytes))
                InfoRow("Plugins", readable(info.pluginBytes))
                InfoRow("Versions kept", readable(info.versionsBytes))
                InfoRow("Cache", "${readable(info.cacheBytes)}  ·  ${info.cacheFiles} files")
                Spacer(Modifier.height(6.dp))
                Divider()
                Spacer(Modifier.height(6.dp))
                InfoRow("Free on this phone", readable(info.freeBytes))
            }
        }

        item { SectionTitle("Right now") }
        item {
            PyCard {
                InfoRow("Servers running", info.servers.toString())
                InfoRow("Plugins loaded", info.plugins.toString())
            }
        }

        item { SectionTitle("Getting in touch") }
        item { ContactCard(onEmail = onEmail) }

        item { SectionTitle("Housekeeping") }
        item { pluginSections() }

        item {
            PyCard {
                Text(
                    "Nothing here touches your files. The cache is what the app " +
                        "made for itself, and __pycache__ folders are rebuilt the next " +
                        "time a script runs.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                if (busy.isNotEmpty()) {
                    BusyRow(busy)
                } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        GhostButton("Clear cache", PyIcons.Delete, onClearCache, Modifier.weight(1f))
                        GhostButton("Drop __pycache__", PyIcons.Delete, onClearPycache,
                                    Modifier.weight(1f))
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        GhostButton("Save the debug log", PyIcons.Save, onExportLog,
                                    Modifier.weight(1f))
                        GhostButton("Refresh", PyIcons.RestartAlt, onRefresh, Modifier.weight(1f))
                    }
                    // Only offered once they are gone: the app no longer puts
                    // them back by itself, so this is the way back.
                    if (onRestoreExamples != null) {
                        Spacer(Modifier.height(8.dp))
                        GhostButton(
                            "Put the examples back",
                            PyIcons.NoteAdd,
                            onRestoreExamples,
                            Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
    }
}

/**
 * Checking for a newer PyCmd, and installing it over this one.
 *
 * The whole point is that nothing gets uninstalled: Android replaces the app
 * in place and every file, package and setting stays. So the card says that
 * out loud - the fear of losing a workspace is exactly what makes people leave
 * an old build sitting there.
 *
 * It never installs anything on its own. It checks when asked, downloads when
 * asked, and the system installer still puts up its own confirmation.
 */
@Composable
private fun UpdateCard(
    state: UpdateState,
    source: String,
    backgroundChecks: Boolean,
    backgroundDownload: Boolean,
    onSetBackgroundChecks: (Boolean) -> Unit,
    onSetBackgroundDownload: (Boolean) -> Unit,
    onCheck: () -> Unit,
    onDownload: () -> Unit,
    onCancel: () -> Unit,
    onInstall: () -> Unit,
    onDismiss: () -> Unit,
    onSetSource: (String) -> Unit,
) {
    PyCard {
        when (state) {
            is UpdateState.Idle -> {
                Text(
                    "Installing a newer build over this one keeps everything: your " +
                        "workspace, the packages you installed and every setting. " +
                        "Deleting PyCmd first is what loses them - so do not.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                GhostButton("Check for updates", PyIcons.Download, onCheck, Modifier.fillMaxWidth())
            }

            is UpdateState.Checking -> BusyRow("Looking for a newer build...")

            is UpdateState.UpToDate -> {
                InfoRow("Installed", state.versionName)
                Text(
                    "This is the newest build published.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                GhostButton("Check again", PyIcons.RestartAlt, onCheck, Modifier.fillMaxWidth())
            }

            is UpdateState.Available -> {
                Text(
                    "PyCmd ${state.release.versionName} is out.",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                if (state.release.notes.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        state.release.notes,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(8.dp))
                InfoRow(
                    "Download",
                    if (state.release.bytes > 0) readable(state.release.bytes) else "an APK",
                )
                Text(
                    "It installs over this one. Nothing is deleted and nothing is " +
                        "uninstalled.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ActionButton("Download", PyIcons.Download, onDownload, Modifier.weight(1f))
                    GhostButton("Not now", PyIcons.Clear, onDismiss, Modifier.weight(1f))
                }
            }

            is UpdateState.Downloading -> {
                val done = state.bytes
                val total = state.total
                Text(
                    "Downloading ${state.release.versionName}...",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(8.dp))
                // A server that will not say how big the file is gets the
                // indeterminate bar rather than a progress figure invented here.
                if (total > 0) {
                    LinearProgressIndicator(
                        progress = { (done.toFloat() / total).coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    if (total > 0) "${readable(done)} of ${readable(total)}" else readable(done),
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = MonoFamily,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                GhostButton("Stop", PyIcons.Stop, onCancel, Modifier.fillMaxWidth())
            }

            is UpdateState.Ready -> {
                Text(
                    "PyCmd ${state.release.versionName} is ready to install.",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "Checked against the published fingerprint, and it is signed with " +
                        "the same key as this build - so Android will replace this app " +
                        "and keep your files. Android asks you to confirm; PyCmd closes " +
                        "while it installs and everything is where you left it after.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ActionButton("Install", PyIcons.Download, onInstall, Modifier.weight(1f))
                    GhostButton("Delete it", PyIcons.Delete, onDismiss, Modifier.weight(1f))
                }
            }

            is UpdateState.Failed -> {
                Text(
                    state.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
                if (state.detail.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        state.detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    GhostButton("Try again", PyIcons.RestartAlt, onCheck, Modifier.weight(1f))
                    GhostButton("Close", PyIcons.Clear, onDismiss, Modifier.weight(1f))
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Divider()
        Spacer(Modifier.height(10.dp))
        BackgroundRow(
            backgroundChecks = backgroundChecks,
            backgroundDownload = backgroundDownload,
            onChecks = onSetBackgroundChecks,
            onDownload = onSetBackgroundDownload,
        )

        Spacer(Modifier.height(10.dp))
        UpdateSourceRow(source, onSetSource)
    }
}

/**
 * Looking for updates with the app closed.
 *
 * Worth saying what Android actually does here rather than implying a timer:
 * work runs when the system is willing, which is roughly daily on wifi, and a
 * force-stopped app does not run at all until it is opened again.
 */
@Composable
private fun BackgroundRow(
    backgroundChecks: Boolean,
    backgroundDownload: Boolean,
    onChecks: (Boolean) -> Unit,
    onDownload: (Boolean) -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Look while the app is closed", style = MaterialTheme.typography.bodyMedium)
            Text(
                "About once a day, on wifi, when the phone is not low on battery. " +
                    "Android decides exactly when.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = backgroundChecks, onCheckedChange = onChecks)
    }
    if (backgroundChecks) {
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Download it too", style = MaterialTheme.typography.bodyMedium)
                Text(
                    "So installing is a tap rather than a wait. Wifi only, and it " +
                        "still never installs by itself.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(checked = backgroundDownload, onCheckedChange = onDownload)
        }
    }
}

/**
 * Where the check looks, for anybody who needs it to look somewhere else.
 *
 * A branch gets renamed, a fork carries the build somebody actually wants, or
 * the update lives on a machine at home. Folded away by default: nobody needs
 * to see a URL to press one button.
 */
@Composable
private fun UpdateSourceRow(source: String, onSetSource: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    var draft by remember(source) { mutableStateOf(source) }

    TextButton(onClick = { open = !open }) {
        Text(
            if (open) "Hide where updates come from" else "Where updates come from",
            style = MaterialTheme.typography.labelSmall,
        )
    }
    if (!open) return

    OutlinedTextField(
        value = draft,
        onValueChange = { draft = it },
        label = { Text("Address of latest.json") },
        singleLine = false,
        textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = MonoFamily),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(6.dp))
    Text(
        "https only. The file it points at names the version and the fingerprint " +
            "of the APK; PyCmd checks the download against that fingerprint before " +
            "it offers to install anything.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        GhostButton("Use this", PyIcons.Save, { onSetSource(draft) }, Modifier.weight(1f))
        GhostButton("Back to default", PyIcons.RestartAlt, { onSetSource("") }, Modifier.weight(1f))
    }
}

/**
 * The builds this phone still has, and the truth about going back to one.
 *
 * Android will not install a lower versionCode over a higher one. There is no
 * flag an ordinary app can set for that, so "roll back" is not a button that
 * can work on its own - it is a sequence, and the honest thing is to say so
 * and hand over the two files that sequence needs.
 */
/**
 * Who to tell when something is wrong, and where a fork stands.
 *
 * Both belong on this screen for the same reason: it is where somebody ends up
 * when they are trying to work out what this app is doing.
 */
@Composable
private fun ContactCard(onEmail: (String) -> Unit) {
    PyCard {
        Text("Found a bug? Tell us.", style = MaterialTheme.typography.titleSmall,
             fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        Text(
            "Anything that crashes, misbehaves or is simply wrong - and anything " +
                "you wish it did. Save the debug log first if something failed; it " +
                "is worth more than a description.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            SUPPORT_EMAIL,
            style = MaterialTheme.typography.bodyMedium,
            fontFamily = MonoFamily,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.clickable { onEmail(SUPPORT_EMAIL) },
        )
        Spacer(Modifier.height(14.dp))
        Divider()
        Spacer(Modifier.height(10.dp))
        Text("Forks are welcome", style = MaterialTheme.typography.titleSmall,
             fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        Text(
            "Take the source, change it, ship it. The update address above is " +
                "editable precisely so a fork can publish its own builds, and a " +
                "fork that adds something good is the best thing that can happen " +
                "to a project like this. Guides has a walkthrough, and the source " +
                "downloads from the end of it.\n\n" +
                "Two conditions, and they are the ordinary ones: keep PyCmd's name " +
                "and credit where they are, and do not claim the original is a copy " +
                "of your fork. Beyond that it is yours to change.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/** Where to write when something here is wrong. */
const val SUPPORT_EMAIL = "andrejbaltes4@proton.me"

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VersionsCard(
    versions: List<KeptVersion>,
    cap: Long,
    /** Room left on the device, so a ceiling bigger than that can say so. */
    freeBytes: Long,
    onSetCap: (Long) -> Unit,
    onInstall: (KeptVersion) -> Unit,
    onDelete: (KeptVersion) -> Unit,
    onDeleteAll: () -> Unit,
    onSaveToPhone: (KeptVersion) -> Unit,
    onBackupWorkspace: () -> Unit,
) {
    var goingBackTo by remember { mutableStateOf<KeptVersion?>(null) }
    val used = versions.sumOf { it.bytes }
    val running = BuildConfig.VERSION_CODE

    PyCard {
        Text(
            "Every update PyCmd downloads is filed here instead of being thrown " +
                "away, so an older build is one tap from coming back - and the " +
                "downloads do not sit in the app's own storage.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(10.dp))
        InfoRow("Kept", "${versions.size}  ·  ${readable(used)} of ${capLabel(cap)}")

        if (versions.isEmpty()) {
            Text(
                "Nothing yet. The next update you take is kept automatically.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        versions.forEach { version ->
            Spacer(Modifier.height(10.dp))
            Divider()
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "PyCmd ${version.versionName}" +
                            if (version.versionCode == running) "  (running)" else "",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        fontFamily = MonoFamily,
                    )
                    Text(
                        "build ${version.versionCode}  ·  ${readable(version.bytes)}  ·  " +
                            SimpleDateFormat("dd MMM HH:mm", Locale.US)
                                .format(Date(version.savedAt)),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (version.versionCode > running) {
                    GhostButton("Install", PyIcons.Download, { onInstall(version) },
                                Modifier.weight(1f))
                } else if (version.versionCode < running) {
                    GhostButton("Go back to it", PyIcons.History, { goingBackTo = version },
                                Modifier.weight(1f))
                } else {
                    GhostButton("Reinstall", PyIcons.RestartAlt, { onInstall(version) },
                                Modifier.weight(1f))
                }
                GhostButton("Save", PyIcons.Save, { onSaveToPhone(version) }, Modifier.weight(1f))
                GhostButton("Delete", PyIcons.Delete, { onDelete(version) }, Modifier.weight(1f))
            }
        }

        Spacer(Modifier.height(12.dp))
        Divider()
        Spacer(Modifier.height(10.dp))
        Text(
            "Keep at most",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(6.dp))
        // Wrapped, not a Row: eight ceilings do not fit across a phone, and
        // the two biggest were off the edge of the screen when they did not.
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CAPS.forEach { (label, bytes) ->
                StatusChip(
                    text = label,
                    color = if (cap == bytes) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                    modifier = Modifier.clickable { onSetCap(bytes) },
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            when {
                cap == 0L ->
                    "Off: an update replaces the build on the phone and nothing is " +
                        "kept. Going back then means finding the APK again."
                freeBytes in 1 until cap ->
                    "There is ${readable(freeBytes)} free on this device, which is " +
                        "less than the ceiling. The archive will fill the space it " +
                        "can and prune the oldest build when it runs out - it will " +
                        "not fill the phone."
                else ->
                    "Oldest first when it has to prune, because the reason to keep " +
                        "an old build is to step back one, and three steps back is a " +
                        "build nobody installs. ${readable(freeBytes)} free here."
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (versions.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            GhostButton("Delete them all", PyIcons.Delete, onDeleteAll, Modifier.fillMaxWidth())
        }
    }

    val target = goingBackTo
    if (target != null) {
        ConfirmDialog(
            title = "Go back to ${target.versionName}?",
            message = "Android will not install an older build over a newer one - " +
                "there is no way around that from inside an app. Going back means " +
                "uninstalling PyCmd first, and uninstalling deletes your workspace, " +
                "your packages and this archive along with it.\n\n" +
                "So do it in this order:\n" +
                "1. Save ${target.versionName} to the phone (the Save button).\n" +
                "2. Back up the workspace - the button below writes a zip and asks " +
                "where to put it.\n" +
                "3. Uninstall PyCmd.\n" +
                "4. Open the saved APK from your Files app.\n" +
                "5. Bring the workspace back in from Files.",
            confirmLabel = "Back up the workspace",
            onDismiss = { goingBackTo = null },
            onConfirm = {
                goingBackTo = null
                onBackupWorkspace()
            },
        )
    }
}

/**
 * The ceilings offered for the archive. A gigabyte is still the default.
 *
 * Ten gigabytes at the top because people asked for it: an APK is about 20 MB,
 * so ten gigabytes is every build PyCmd will ever have and then some. It is
 * not a promise that the phone has the room - the archive prunes oldest-first
 * when it runs out of space, and the line under these chips says how much
 * there actually is.
 */
private val CAPS = listOf(
    "off" to 0L,
    "100 MB" to 100L * 1024 * 1024,
    "250 MB" to 250L * 1024 * 1024,
    "500 MB" to 500L * 1024 * 1024,
    "1 GB" to 1024L * 1024 * 1024,
    "2 GB" to 2L * 1024 * 1024 * 1024,
    "5 GB" to 5L * 1024 * 1024 * 1024,
    "10 GB" to 10L * 1024 * 1024 * 1024,
)

private fun capLabel(bytes: Long): String =
    CAPS.firstOrNull { it.second == bytes }?.first ?: readable(bytes)

@Composable
private fun InfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(150.dp),
        )
        Text(
            value.ifEmpty { "—" },
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
            fontFamily = MonoFamily,
            modifier = Modifier.weight(1f),
        )
    }
    Spacer(Modifier.height(6.dp))
}

private fun readable(bytes: Long): String = when {
    bytes >= 1024L * 1024 * 1024 -> "%.2f GB".format(bytes / 1024.0 / 1024.0 / 1024.0)
    bytes >= 1024L * 1024 -> "%.1f MB".format(bytes / 1024.0 / 1024.0)
    bytes >= 1024 -> "${bytes / 1024} KB"
    else -> "$bytes B"
}
