package com.expstudio.pycmd.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.plugins.InstalledPlugin
import com.expstudio.pycmd.plugins.PluginFileAction
import com.expstudio.pycmd.python.LanguageInfo
import com.expstudio.pycmd.util.WorkspaceEntry
import java.io.File

/** What pressing the button on a file row does. */
enum class FileAction { NONE, RUN, PREVIEW }

@Composable
fun FilesScreen(
    state: FilesState,
    rootPath: String,
    relativePath: (File) -> String,
    onOpenDirectory: (File) -> Unit,
    onOpenFile: (File) -> Unit,
    onRunFile: (File) -> Unit,
    /** What the play button on a row would do, if anything. */
    actionFor: (WorkspaceEntry) -> FileAction,
    onUp: () -> Unit,
    onNewFile: (String) -> Unit,
    onNewFileOfType: (String, String) -> Unit,
    languages: List<LanguageInfo>,
    onNewFolder: (String) -> Unit,
    onRename: (File, String) -> Unit,
    onDelete: (File) -> Unit,
    onImport: (android.net.Uri) -> Unit,
    onImportFolder: (android.net.Uri) -> Unit,
    onExportFolder: (File) -> Unit,
    onSaveToDevice: (File) -> Unit,
    modifier: Modifier = Modifier,
    /** Menu lines plugins want on this file or folder, and how to run one. */
    pluginActionsFor: (String, Boolean) -> List<Pair<InstalledPlugin, PluginFileAction>> =
        { _, _ -> emptyList() },
    onPluginAction: (InstalledPlugin, PluginFileAction, File) -> Unit = { _, _, _ -> },
    pickingFor: ServerKind? = null,
    onUseAsTarget: (File) -> Unit = {},
    onCancelPicking: () -> Unit = {},
    /** The account, for the Cloud folder: signed in or not, and its files. */
    cloudAccount: TeachAccount = TeachAccount(),
    onCloudOpen: () -> Unit = {},
    onCloudUpload: () -> Unit = {},
    onCloudDownload: (String) -> Unit = {},
    onCloudEdit: (String) -> Unit = {},
    onCloudDelete: (String) -> Unit = {},
    onCloudDownloadAll: () -> Unit = {},
    onSignIn: () -> Unit = {},
    /** Sections plugins have added to this screen; empty when none are on. */
    pluginSections: @Composable () -> Unit = {},
) {
    var dialog by remember { mutableStateOf<FileDialog?>(null) }
    // The Cloud folder is a place inside Files, not a folder on the phone:
    // it lists the account's cloud storage and moves files both ways.
    var inCloud by remember { mutableStateOf(false) }
    BackHandler(enabled = inCloud) { inCloud = false }
    if (inCloud) {
        CloudFolder(
            account = cloudAccount,
            onBack = { inCloud = false },
            onRefresh = onCloudOpen,
            onUpload = onCloudUpload,
            onDownload = onCloudDownload,
            onEdit = onCloudEdit,
            onDelete = onCloudDelete,
            onDownloadAll = onCloudDownloadAll,
            onSignIn = onSignIn,
            modifier = modifier,
        )
        return
    }

    var importMenuOpen by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }

    val importLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments(),
    ) { uris -> uris.forEach(onImport) }

    val folderLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocumentTree(),
    ) { uri -> if (uri != null) onImportFolder(uri) }

    val atRoot = state.directory?.absolutePath == rootPath

    Column(modifier.fillMaxSize()) {
        Row(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onUp, enabled = !atRoot) {
                Icon(
                    PyIcons.ArrowBack,
                    contentDescription = "Up one folder",
                    tint = if (atRoot) MaterialTheme.colorScheme.outline else MaterialTheme.colorScheme.onSurface,
                )
            }
            Column(Modifier.weight(1f)) {
                Text("Workspace", style = MaterialTheme.typography.titleMedium)
                Text(
                    text = state.directory?.let { relativePath(it) } ?: "/",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
            Box {
                IconButton(onClick = { importMenuOpen = true }) {
                    Icon(
                        PyIcons.FileUpload,
                        contentDescription = "Upload from this phone",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                DropdownMenu(
                    expanded = importMenuOpen,
                    onDismissRequest = { importMenuOpen = false },
                ) {
                    DropdownMenuItem(
                        text = { Text("Upload files") },
                        leadingIcon = {
                            Icon(PyIcons.Description, contentDescription = null,
                                 modifier = Modifier.size(18.dp))
                        },
                        onClick = {
                            importMenuOpen = false
                            importLauncher.launch(arrayOf("*/*"))
                        },
                    )
                    DropdownMenuItem(
                        text = { Text("Upload a folder") },
                        leadingIcon = {
                            Icon(PyIcons.Folder, contentDescription = null,
                                 modifier = Modifier.size(18.dp))
                        },
                        onClick = {
                            importMenuOpen = false
                            folderLauncher.launch(null)
                        },
                    )
                }
            }
            IconButton(onClick = { dialog = FileDialog.NewFolder }) {
                Icon(
                    PyIcons.CreateNewFolder,
                    contentDescription = "New folder",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = { dialog = FileDialog.NewFile }) {
                Icon(
                    PyIcons.NoteAdd,
                    contentDescription = "New file",
                    tint = MaterialTheme.colorScheme.primary,
                )
            }
        }

        Box(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 12.dp, vertical = 4.dp),
        ) {
            SearchField(
                value = query,
                onValueChange = { query = it },
                placeholder = "Filter this folder",
            )
        }

        if (pickingFor != null) {
            PickerBanner(
                kind = pickingFor,
                directory = state.directory,
                onUse = { dir -> onUseAsTarget(dir) },
                onCancel = onCancelPicking,
            )
        }

        Divider()

        when {
            state.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }

            state.entries.isEmpty() -> Column(Modifier.fillMaxSize()) {
                if (atRoot && pickingFor == null) CloudEntryRow(cloudAccount) { inCloud = true; onCloudOpen() }
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    EmptyState(
                        icon = PyIcons.FolderOpen,
                        title = "This folder is empty",
                        hint = "Create a script or import one from your device.",
                    )
                }
            }

            else -> LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(bottom = 24.dp),
            ) {
                val needle = query.trim().lowercase()
                val shown = if (needle.isEmpty()) {
                    state.entries
                } else {
                    state.entries.filter { it.name.lowercase().contains(needle) }
                }

                if (shown.isEmpty()) {
                    item {
                        EmptyState(
                            icon = PyIcons.Search,
                            title = "Nothing here matches",
                            hint = "${state.entries.size} items in this folder. " +
                                "Workspace Search looks inside files, across every folder.",
                        )
                    }
                }

                if (atRoot && needle.isEmpty() && pickingFor == null) {
                    item(key = "pycmd-cloud") {
                        CloudEntryRow(cloudAccount) { inCloud = true; onCloudOpen() }
                    }
                }

                items(shown, key = { it.file.absolutePath }) { entry ->
                    FileRow(
                        entry = entry,
                        action = actionFor(entry),
                        onOpen = {
                            when {
                                entry.isDirectory -> onOpenDirectory(entry.file)
                                pickingFor == ServerKind.SCRIPT -> onUseAsTarget(entry.file)
                                else -> onOpenFile(entry.file)
                            }
                        },
                        onRun = { onRunFile(entry.file) },
                        onRename = { dialog = FileDialog.Rename(entry.file) },
                        onDelete = { dialog = FileDialog.ConfirmDelete(entry.file) },
                        onExportFolder = { onExportFolder(entry.file) },
                        onSaveToDevice = { onSaveToDevice(entry.file) },
                        pluginActions = pluginActionsFor(entry.name, entry.isDirectory),
                        onPluginAction = { plugin, pluginAction ->
                            onPluginAction(plugin, pluginAction, entry.file)
                        },
                    )
                }

                item {
                    Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                        pluginSections()
                    }
                }
            }
        }
    }

    when (val current = dialog) {
        FileDialog.NewFile -> NewFileDialog(
            languages = languages,
            onDismiss = { dialog = null },
            onCreate = { name, extension ->
                dialog = null
                if (extension.isEmpty()) onNewFile(name) else onNewFileOfType(name, extension)
            },
            onImportType = { language ->
                dialog = null
                importLauncher.launch(arrayOf(language.mime.ifBlank { "*/*" }))
            },
        )

        FileDialog.NewFolder -> TextPromptDialog(
            title = "New folder",
            label = "Folder name",
            initial = "",
            confirmLabel = "Create",
            onDismiss = { dialog = null },
            onConfirm = {
                dialog = null
                onNewFolder(it)
            },
        )

        is FileDialog.Rename -> TextPromptDialog(
            title = "Rename",
            label = "New name",
            initial = current.file.name,
            confirmLabel = "Rename",
            onDismiss = { dialog = null },
            onConfirm = {
                dialog = null
                onRename(current.file, it)
            },
        )

        is FileDialog.ConfirmDelete -> ConfirmDialog(
            title = "Delete ${current.file.name}?",
            message = if (current.file.isDirectory) {
                "The folder and everything inside it will be removed. This cannot be undone."
            } else {
                "This cannot be undone."
            },
            confirmLabel = "Delete",
            destructive = true,
            onDismiss = { dialog = null },
            onConfirm = {
                dialog = null
                onDelete(current.file)
            },
        )

        null -> Unit
    }
}

private sealed interface FileDialog {
    data object NewFile : FileDialog
    data object NewFolder : FileDialog
    data class Rename(val file: File) : FileDialog
    data class ConfirmDelete(val file: File) : FileDialog
}

@Composable
private fun FileRow(
    entry: WorkspaceEntry,
    action: FileAction,
    onOpen: () -> Unit,
    onRun: () -> Unit,
    onRename: () -> Unit,
    onDelete: () -> Unit,
    onExportFolder: () -> Unit,
    onSaveToDevice: () -> Unit,
    pluginActions: List<Pair<InstalledPlugin, PluginFileAction>>,
    onPluginAction: (InstalledPlugin, PluginFileAction) -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }

    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onOpen)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = if (entry.isDirectory) PyIcons.Folder else PyIcons.Description,
            contentDescription = null,
            tint = when {
                entry.isDirectory -> MaterialTheme.colorScheme.secondary
                entry.isPython -> MaterialTheme.colorScheme.primary
                else -> MaterialTheme.colorScheme.onSurfaceVariant
            },
            modifier = Modifier.size(22.dp),
        )
        Spacer(Modifier.width(14.dp))

        Column(Modifier.weight(1f)) {
            Text(
                text = entry.name,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = if (entry.isDirectory) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
            )
            Text(
                text = buildString {
                    append(entry.readableDate)
                    if (!entry.isDirectory) {
                        append("  -  ")
                        append(entry.readableSize)
                    }
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        // Anything the device can actually run or show gets the button: it
        // was Python-only until C, Go, Rust and JavaScript could run too.
        if (action != FileAction.NONE) {
            IconButton(onClick = onRun, modifier = Modifier.size(38.dp)) {
                Icon(
                    PyIcons.PlayArrow,
                    contentDescription = if (action == FileAction.PREVIEW) {
                        "Preview ${entry.name}"
                    } else {
                        "Run ${entry.name}"
                    },
                    tint = if (action == FileAction.PREVIEW) {
                        MaterialTheme.colorScheme.secondary
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
                    modifier = Modifier.size(20.dp),
                )
            }
        }

        Box {
            IconButton(onClick = { menuOpen = true }, modifier = Modifier.size(38.dp)) {
                Icon(
                    PyIcons.MoreVert,
                    contentDescription = "More actions",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(20.dp),
                )
            }
            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                if (entry.isDirectory) {
                    // A folder cannot be handed to another app as it is, so
                    // it goes out the way a computer expects one: as a zip in
                    // Downloads, which can then be saved anywhere.
                    DropdownMenuItem(
                        text = { Text("Export as zip") },
                        leadingIcon = { Icon(PyIcons.Inventory2, contentDescription = null) },
                        onClick = {
                            menuOpen = false
                            onExportFolder()
                        },
                    )
                } else {
                    DropdownMenuItem(
                        text = { Text("Save to device") },
                        leadingIcon = { Icon(PyIcons.FileUpload, contentDescription = null) },
                        onClick = {
                            menuOpen = false
                            onSaveToDevice()
                        },
                    )
                }
                DropdownMenuItem(
                    text = { Text("Rename") },
                    leadingIcon = { Icon(PyIcons.DriveFileRenameOutline, contentDescription = null) },
                    onClick = {
                        menuOpen = false
                        onRename()
                    },
                )
                // A plugin's own lines, below the app's and above Delete, so
                // the destructive one stays last wherever it is.
                pluginActions.forEach { (plugin, action) ->
                    DropdownMenuItem(
                        text = { Text(action.label) },
                        leadingIcon = {
                            Icon(
                                PyIcons.Add,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.tertiary,
                            )
                        },
                        trailingIcon = {
                            Text(
                                plugin.name,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        },
                        onClick = {
                            menuOpen = false
                            onPluginAction(plugin, action)
                        },
                    )
                }
                DropdownMenuItem(
                    text = { Text("Delete", color = MaterialTheme.colorScheme.error) },
                    leadingIcon = {
                        Icon(
                            PyIcons.Delete,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.error,
                        )
                    },
                    onClick = {
                        menuOpen = false
                        onDelete()
                    },
                )
            }
        }
    }
    Box(
        Modifier
            .padding(start = 50.dp)
            .fillMaxWidth()
            .height(1.dp)
            .background(MaterialTheme.colorScheme.outlineVariant),
    )
}

/**
 * Shown while the Servers tab is waiting for a folder or script.
 *
 * A folder is confirmed with the button (you have to be standing in it); a
 * script is picked by tapping it in the list.
 */
@Composable
private fun PickerBanner(
    kind: ServerKind,
    directory: File?,
    onUse: (File) -> Unit,
    onCancel: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.primaryContainer)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                text = if (kind == ServerKind.STATIC) {
                    "Choose a folder to serve"
                } else {
                    "Tap the file to run, or use this folder"
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            Text(
                text = if (kind == ServerKind.STATIC) {
                    "Open the folder you want, then confirm."
                } else {
                    "Any file the app can run, a page to serve, or a whole folder."
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
        if (directory != null) {
            // Also offered while picking a file: a folder is a perfectly good
            // thing to run - it gets served - and making the user cancel and
            // switch modes to say so would be a pointless detour.
            TextButton(onClick = { onUse(directory) }) { Text("Use this folder") }
        }
        TextButton(onClick = onCancel) { Text("Cancel") }
    }
}

/**
 * New-file dialog with a type picker.
 *
 * The list comes from the language registry, so it grows and shrinks with the
 * Polyglot Files plugin rather than being hard-coded here. Each type carries a
 * starter template, which is what makes "new Dockerfile" useful rather than
 * just an empty buffer with a name.
 */
@Composable
private fun NewFileDialog(
    languages: List<LanguageInfo>,
    onDismiss: () -> Unit,
    onCreate: (String, String) -> Unit,
    /** Media is imported rather than written; this opens the picker for it. */
    onImportType: (LanguageInfo) -> Unit,
) {
    var name by remember { mutableStateOf("script") }
    var chosen by remember(languages) {
        mutableStateOf(languages.firstOrNull { it.id == "python" } ?: languages.firstOrNull())
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(18.dp),
        title = { Text("New file", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column {
                // Media keeps the name it arrives with, so asking for one
                // would only be a box whose answer is thrown away.
                if (chosen?.creatable != false) {
                    OutlinedTextField(
                        value = name,
                        onValueChange = { name = it },
                        label = { Text("Name") },
                        singleLine = true,
                        shape = RoundedCornerShape(12.dp),
                        textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = MonoFamily),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = MaterialTheme.colorScheme.primary,
                            unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                        ),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }

                Spacer(Modifier.height(6.dp))
                Text(
                    text = when {
                        chosen == null -> name
                        // Nothing is written for media, so promising a name
                        // would be a lie: it arrives with the one it has.
                        !chosen!!.creatable -> "${chosen!!.name}  ->  pick one from this phone"
                        else -> "${chosen!!.name}  ->  $name${chosen!!.extension}"
                    },
                    style = MaterialTheme.typography.labelSmall,
                    fontFamily = MonoFamily,
                    color = MaterialTheme.colorScheme.secondary,
                )

                if (chosen?.note?.isNotBlank() == true) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        chosen!!.note,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Spacer(Modifier.height(10.dp))
                SectionTitle("Type")
                LazyColumn(Modifier.heightIn(max = 260.dp)) {
                    items(languages, key = { it.id }) { language ->
                        val selected = chosen?.id == language.id
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable { chosen = language }
                                .padding(vertical = 8.dp, horizontal = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    language.name,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (selected) {
                                        MaterialTheme.colorScheme.primary
                                    } else {
                                        MaterialTheme.colorScheme.onSurface
                                    },
                                )
                                Text(
                                    language.extension + runLabel(language),
                                    style = MaterialTheme.typography.labelSmall,
                                    fontFamily = MonoFamily,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (selected) {
                                Text(
                                    "selected",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            val importing = chosen?.creatable == false
            TextButton(
                onClick = {
                    val language = chosen ?: return@TextButton
                    if (importing) onImportType(language) else onCreate(name.trim(), language.extension)
                },
                enabled = chosen != null && (importing || name.isNotBlank()),
            ) { Text(if (importing) "Choose a file" else "Create") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

private fun runLabel(language: LanguageInfo): String = when (language.mode) {
    "run" -> "   runs on the device"
    "preview" -> "   previewable"
    "media" -> "   brought in from the phone"
    else -> ""
}


private fun sizeText(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> "%.1f MB".format(bytes / 1024.0 / 1024.0)
    bytes >= 1024 -> "${bytes / 1024} KB"
    else -> "$bytes B"
}

/** The Cloud folder's row at the top of the workspace. */
@Composable
private fun CloudEntryRow(account: TeachAccount, onOpen: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onOpen)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(PyIcons.Cloud, contentDescription = null, tint = MaterialTheme.colorScheme.primary,
             modifier = Modifier.size(22.dp))
        Column(Modifier.weight(1f).padding(start = 12.dp)) {
            Text("Cloud", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
            Text(
                if (account.signedIn) {
                    "${account.cloudFiles.size} file${if (account.cloudFiles.size == 1) "" else "s"} · " +
                        "${sizeText(account.cloudUsed)} of ${sizeText(account.cloudQuota)}"
                } else "Your account's cloud storage - sign in to use it",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    Divider()
}

/** The account's cloud storage, inside Files: download, open, upload, delete. */
@Composable
private fun CloudFolder(
    account: TeachAccount,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onUpload: () -> Unit,
    onDownload: (String) -> Unit,
    onEdit: (String) -> Unit,
    onDelete: (String) -> Unit,
    onDownloadAll: () -> Unit,
    onSignIn: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var confirm by remember { mutableStateOf<String?>(null) }
    Column(modifier.fillMaxSize()) {
        Row(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) { Icon(PyIcons.ArrowBack, contentDescription = "Back to the workspace") }
            Column(Modifier.weight(1f)) {
                Text("Cloud", style = MaterialTheme.typography.titleMedium)
                Text(
                    if (account.signedIn) "${account.username} · ${sizeText(account.cloudUsed)} of ${sizeText(account.cloudQuota)}"
                    else "not signed in",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (account.signedIn) {
                IconButton(onClick = onRefresh) { Icon(PyIcons.Sync, contentDescription = "Refresh") }
                IconButton(onClick = onUpload) { Icon(PyIcons.FileUpload, contentDescription = "Upload a file to the cloud") }
            }
        }
        Divider()
        if (!account.signedIn) {
            Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
                   verticalArrangement = Arrangement.Center) {
                EmptyState(
                    icon = PyIcons.Cloud,
                    title = "Sign in to use the cloud",
                    hint = "A free PyCmd account gives you 800 KB of cloud storage, the same on your phone and your PC.",
                )
                TextButton(onClick = onSignIn) { Text("Sign in or make an account") }
            }
            return@Column
        }
        if (account.cloudFiles.isNotEmpty()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp)) {
                TextButton(onClick = onDownloadAll) {
                    Icon(PyIcons.Download, contentDescription = null, modifier = Modifier.size(18.dp))
                    Text("  Download all to workspace/cloud")
                }
            }
        }
        if (account.cloudFiles.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                EmptyState(
                    icon = PyIcons.Cloud,
                    title = "Nothing in the cloud yet",
                    hint = "Upload a file with the arrow above, or use cloud upload in the console.",
                )
            }
            return@Column
        }
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
            items(account.cloudFiles, key = { it.path }) { file ->
                Row(
                    Modifier.fillMaxWidth().clickable { onEdit(file.path) }.padding(start = 14.dp, end = 4.dp, top = 6.dp, bottom = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(PyIcons.Description, contentDescription = null, modifier = Modifier.size(20.dp),
                         tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(file.path, style = MaterialTheme.typography.bodyMedium, maxLines = 1)
                        Text(sizeText(file.size), style = MaterialTheme.typography.labelSmall,
                             color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    IconButton(onClick = { onDownload(file.path) }) {
                        Icon(PyIcons.Download, contentDescription = "Download ${file.path}",
                             tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = { confirm = file.path }) {
                        Icon(PyIcons.Delete, contentDescription = "Delete ${file.path} from the cloud",
                             tint = MaterialTheme.colorScheme.error)
                    }
                }
                Divider()
            }
        }
    }
    confirm?.let { path ->
        ConfirmDialog(
            title = "Delete $path from the cloud?",
            message = "It is removed from your cloud storage on every device. A copy you downloaded stays.",
            confirmLabel = "Delete",
            destructive = true,
            onDismiss = { confirm = null },
            onConfirm = { confirm = null; onDelete(path) },
        )
    }
}
