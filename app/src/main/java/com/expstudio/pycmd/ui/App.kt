package com.expstudio.pycmd.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.core.net.toUri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.expstudio.pycmd.plugins.PluginIds
import com.expstudio.pycmd.python.byExtension
import com.expstudio.pycmd.python.forFileName
import com.expstudio.pycmd.util.Branding
import com.expstudio.pycmd.util.UpdateState
import com.expstudio.pycmd.util.WorkspaceEntry
import com.expstudio.pycmd.BuildConfig
import com.expstudio.pycmd.python.OutputChunk
import java.io.File
import java.util.Locale
import java.util.Date
import java.text.SimpleDateFormat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PyCmdRoot(viewModel: MainViewModel = viewModel()) {
    val context = LocalContext.current
    val snackbarHost = remember { SnackbarHostState() }

    val tab by viewModel.tab.collectAsState()
    val status by viewModel.engineStatus.collectAsState()
    val editorState by viewModel.editor.collectAsState()
    val filesState by viewModel.files.collectAsState()
    val packagesState by viewModel.packages.collectAsState()
    val serversState by viewModel.servers.collectAsState()
    val history by viewModel.history.collectAsState()
    val toast by viewModel.toast.collectAsState()
    val serverCount by viewModel.serverCount.collectAsState()
    val serverConsoles by viewModel.serverConsoles.collectAsState()
    val awaitingInput by viewModel.awaitingInput.collectAsState()
    val debugEntries by viewModel.debugEntries.collectAsState()
    val debugErrors by viewModel.debugErrorCount.collectAsState()
    val pickingFor by viewModel.pickingFor.collectAsState()
    val downloadsState by viewModel.downloads.collectAsState()
    val pluginsEnabled by viewModel.pluginsEnabled.collectAsState()
    val languages by viewModel.languages.collectAsState()
    val activeTool by viewModel.activeTool.collectAsState()
    val previewPage by viewModel.preview.collectAsState()
    val previewable by viewModel.previewable.collectAsState()
    val installedPlugins by viewModel.customPlugins.collectAsState()
    val installedEnabled by viewModel.customPluginsEnabled.collectAsState()
    val pluginBusy by viewModel.pluginBusy.collectAsState()
    val pluginCandidates by viewModel.pluginCandidates.collectAsState()
    val openPanel by viewModel.openPanel.collectAsState()
    val openPanelFile by viewModel.openPanelFile.collectAsState()
    val pendingImport by viewModel.pendingImport.collectAsState()
    val systemInfo by viewModel.system.collectAsState()
    val systemBusy by viewModel.systemBusy.collectAsState()
    val clearConsoleAt by viewModel.clearConsole.collectAsState()
    val pagesState by viewModel.pages.collectAsState()
    val musicState by viewModel.music.collectAsState()
    val playback by viewModel.playback.collectAsState()
    val backgroundChecks by viewModel.backgroundChecks.collectAsState()
    val backgroundDownload by viewModel.backgroundDownload.collectAsState()
    // Recomputed whenever a switch moves, because the Cloudflare half of the
    // Pages tab appears and disappears with the kit.
    val kitOn = remember(pluginsEnabled) { com.expstudio.pycmd.plugins.Plugins.kitOn }
    val sourceBusy by viewModel.sourceBusy.collectAsState()
    val keptVersions by viewModel.versions.collectAsState()
    val versionsCap by viewModel.versionsCap.collectAsState()
    val updateState by viewModel.update.collectAsState()
    val updateSource by viewModel.updateSource.collectAsState()

    // Worth a dot on More: a newer build found but not yet installed is the
    // one thing in System somebody would want to be told about.
    val updateWaiting = updateState is UpdateState.Available ||
        updateState is UpdateState.Ready

    // Picking a plugin from outside the app: one launcher for a file or zip,
    // one for a whole folder. Both are only reached after the warning dialog.
    val pluginFileLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri -> if (uri != null) viewModel.installPluginFromUri(uri, isFolder = false) }

    val pluginFolderLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocumentTree(),
    ) { uri -> if (uri != null) viewModel.installPluginFromUri(uri, isFolder = true) }

    // Music comes in through the same picker as everything else, filtered to
    // what can be played. Several at once, because a picked album is a picked
    // album and importing it one tap at a time is nobody's idea of a library.
    val musicLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments(),
    ) { uris -> viewModel.importMusic(uris) }

    // Saving a file out of the app: the picker only tells us where afterwards,
    // so the file being saved is held until it comes back.
    var pendingSave by remember { mutableStateOf<File?>(null) }
    val saveLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/octet-stream"),
    ) { uri ->
        val source = pendingSave
        pendingSave = null
        if (uri != null && source != null) viewModel.saveToDevice(source, uri)
    }
    val saveToDevice: (File) -> Unit = { file ->
        pendingSave = file
        saveLauncher.launch(file.name)
    }

    // Which language the open file is, so the snippet bar and the header can
    // say so. Derived rather than stored: the file name is the only input.
    val editorLanguage = remember(editorState.fileName, languages) {
        languages.forFileName(editorState.fileName)
    }

    // Keyed on the catalogue, so the play buttons appear the moment it loads
    // rather than the next time something else happens to redraw the list.
    // Built once per catalogue rather than searched per row: see byExtension.
    val languageIndex = remember(languages) { languages.byExtension() }

    val fileAction: (WorkspaceEntry) -> FileAction = remember(languageIndex, previewable) {
        { entry ->
            val extension = entry.name.substringAfterLast('.', "").lowercase()
            val language = languageIndex[extension]
            when {
                entry.isDirectory -> FileAction.NONE
                language?.canRun == true -> FileAction.RUN
                // Wider than the language table on purpose: JSON, CSV, SVG and
                // images have no language to run but plenty to show.
                language?.canPreview == true || extension in previewable -> FileAction.PREVIEW
                else -> FileAction.NONE
            }
        }
    }

    // Both WebViews are created once and reused for the life of the screen, so
    // console history and editor state survive tab switches.
    val consoleHost = rememberWebHost("console.html")
    val editorHost = rememberWebHost("editor.html")

    // `clear` typed in the console has to reach the page that holds the
    // scrollback. Keyed on the timestamp so a second clear fires again.
    LaunchedEffect(clearConsoleAt) {
        if (clearConsoleAt > 0L) consoleHost.eval("PyConsole.clear();")
    }

    var aboutOpen by remember { mutableStateOf(false) }
    var saveAsOpen by remember { mutableStateOf(false) }
    var runtimeInfo by remember { mutableStateOf<Map<String, String>>(emptyMap()) }

    // Collected here rather than inside ConsoleScreen: output must keep
    // arriving while the user is looking at another tab.
    //
    // Chunks are coalesced before they cross into the WebView. A script that
    // prints in a loop emits one chunk per line, and one `evaluateJavascript`
    // per line is what made a chatty program crawl; waiting a frame and
    // sending the burst as one script costs nothing when output is slow and
    // everything when it is fast.
    LaunchedEffect(consoleHost) {
        // Bounded and dropping the oldest, the same bargain the output flow
        // itself makes: a program that outruns the screen loses its earliest
        // lines rather than growing a queue until memory runs out.
        val queue = Channel<OutputChunk>(4096, BufferOverflow.DROP_OLDEST)
        launch { viewModel.output.collect { queue.send(it) } }
        val batch = ArrayList<OutputChunk>(CONSOLE_BATCH)
        while (isActive) {
            batch.clear()
            // Suspends here while nothing is happening, so an idle console
            // costs no wake-ups at all.
            batch += queue.receive()
            while (batch.size < CONSOLE_BATCH) {
                batch += queue.tryReceive().getOrNull() ?: break
            }
            // Turning four hundred chunks into one script is string work, and
            // string work between two frames is a console that stutters while
            // a program is talking. The main thread only gets the result.
            val script = withContext(Dispatchers.Default) { consoleAppendScript(batch) }
            consoleHost.eval(script)
            // Let the next burst gather rather than returning immediately for
            // the line that arrived while this one was being sent.
            delay(16)
        }
    }

    LaunchedEffect(toast) {
        val message = toast ?: return@LaunchedEffect
        snackbarHost.showSnackbar(message.text)
        viewModel.consumeToast()
    }

    LaunchedEffect(aboutOpen) {
        if (aboutOpen) runtimeInfo = viewModel.runtimeInfo()
    }

    // A script server can exit on its own, so the list needs polling while it
    // is on screen; nothing polls when the tab is not visible.
    LaunchedEffect(tab) {
        while (tab == Tab.SERVERS) {
            delay(3000)
            viewModel.refreshServers()
        }
    }

    // Back inside Files walks up the tree before leaving the app; anywhere
    // else it returns to the console first.
    BackHandler(enabled = tab != Tab.CONSOLE) {
        if (tab == Tab.FILES && viewModel.navigateUp()) return@BackHandler
        // A tool or a plugin panel was opened from the plugin list, so that is
        // where back goes.
        if (tab == Tab.TOOL) {
            viewModel.closeTool()
            return@BackHandler
        }
        if (tab == Tab.PLUGIN_PANEL) {
            viewModel.closePluginPanel()
            return@BackHandler
        }
        // A destination reached through More goes back to More first.
        val parent = if (tab in setOf(
                Tab.PACKAGES, Tab.DOWNLOADS, Tab.PLUGINS, Tab.DOCS, Tab.SYSTEM,
                Tab.PAGES, Tab.MUSIC,
            )
        ) {
            Tab.MORE
        } else {
            Tab.CONSOLE
        }
        viewModel.selectTab(parent)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(snackbarHost) },
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface,
                ),
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(Branding.NAME, style = MaterialTheme.typography.titleLarge)
                        Spacer(Modifier.width(10.dp))
                        when {
                            status.startupError != null -> StatusChip(
                                "interpreter failed",
                                MaterialTheme.colorScheme.error,
                            )

                            status.ready -> StatusChip(
                                "Python ${status.pythonVersion}",
                                MaterialTheme.colorScheme.primary,
                            )

                            else -> Row(verticalAlignment = Alignment.CenterVertically) {
                                CircularProgressIndicator(
                                    strokeWidth = 2.dp,
                                    modifier = Modifier.size(13.dp),
                                    color = MaterialTheme.colorScheme.primary,
                                )
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    "starting",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                },
                navigationIcon = {
                    if (tab == Tab.PLUGIN_PANEL) {
                        IconButton(onClick = { viewModel.closePluginPanel() }) {
                            Icon(
                                PyIcons.ArrowBack,
                                contentDescription = "Back to the plugin list",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    if (tab == Tab.TOOL) {
                        IconButton(onClick = { viewModel.closeTool() }) {
                            Icon(
                                PyIcons.ArrowBack,
                                contentDescription = "Back to the plugin list",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.clearNamespace() }, enabled = status.ready) {
                        Icon(
                            PyIcons.RestartAlt,
                            contentDescription = "Reset variables",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    IconButton(onClick = { viewModel.selectTab(Tab.DEBUG) }) {
                        BadgedBox(
                            badge = { if (debugErrors > 0) Badge { Text(debugErrors.toString()) } },
                        ) {
                            Icon(
                                PyIcons.BugReport,
                                contentDescription = "Debug console",
                                tint = if (tab == Tab.DEBUG) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                },
                            )
                        }
                    }
                    IconButton(onClick = { aboutOpen = true }) {
                        Icon(
                            PyIcons.Info,
                            contentDescription = "About",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                TabItem(Tab.CONSOLE, PyIcons.Terminal, tab, viewModel::selectTab)
                TabItem(Tab.EDITOR, PyIcons.Edit, tab, viewModel::selectTab, dot = editorState.isDirty)
                TabItem(Tab.FILES, PyIcons.Folder, tab, viewModel::selectTab)
                TabItem(Tab.SERVERS, PyIcons.Dns, tab, viewModel::selectTab, count = serverCount)
                TabItem(
                    Tab.MORE,
                    PyIcons.MoreVert,
                    tab,
                    viewModel::selectTab,
                    // A newer build is behind this tab; a dot is how anybody
                    // finds that out without going looking for it.
                    dot = updateWaiting,
                    // The other destinations live here, so More has to show
                    // that one of them is the current screen.
                    forceSelected = tab in setOf(
                        Tab.PACKAGES, Tab.DOWNLOADS, Tab.PLUGINS, Tab.TOOL,
                        Tab.PLUGIN_PANEL, Tab.DOCS, Tab.SYSTEM, Tab.PAGES,
                        Tab.MUSIC,
                    ),
                )
            }
        },
    ) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background),
        ) {
            when (tab) {
                Tab.CONSOLE -> ConsoleScreen(
                    host = consoleHost,
                    status = status,
                    history = history,
                    onRun = viewModel::runConsole,
                    onStdin = viewModel::submitStdin,
                    onStop = viewModel::stopExecution,
                    onClear = { consoleHost.eval("PyConsole.clear();") },
                    onWrapChanged = { wrap -> consoleHost.eval("PyConsole.setWrap($wrap);") },
                    onCompletions = viewModel::completionsFor,
                )

                Tab.EDITOR -> EditorScreen(
                    host = editorHost,
                    state = editorState,
                    ready = status.ready,
                    onContentChanged = viewModel::onEditorContentChanged,
                    onCursorMoved = viewModel::onCursorMoved,
                    onRun = viewModel::runEditor,
                    onSave = {
                        if (editorState.file == null) saveAsOpen = true else viewModel.saveEditor()
                    },
                    onNew = viewModel::newFile,
                    onSaveAs = { saveAsOpen = true },
                    onRunAsServer = viewModel::runEditorAsServer,
                    onOpenDebug = { viewModel.selectTab(Tab.DEBUG) },
                    onCopyAll = { text ->
                        copyToClipboard(context, text)
                        viewModel.showToast("Copied the file")
                    },
                    languageId = editorLanguage?.id ?: "text",
                    highlightAs = editorLanguage?.highlight ?: "text",
                    languageName = editorLanguage?.name.orEmpty(),
                    snippetsOn = viewModel.isPluginOn(PluginIds.SNIPPETS),
                    snippetsPoweredUp = viewModel.isPluginPoweredUp(PluginIds.SNIPPETS),
                )

                Tab.FILES -> FilesScreen(
                    state = filesState,
                    rootPath = viewModel.workspaceRoot.absolutePath,
                    relativePath = viewModel::relativePath,
                    onOpenDirectory = viewModel::openDirectory,
                    onOpenFile = viewModel::openInEditor,
                    onRunFile = viewModel::runFile,
                    actionFor = fileAction,
                    onUp = { viewModel.navigateUp() },
                    onNewFile = viewModel::createFile,
                    onNewFileOfType = viewModel::createFileOfType,
                    languages = languages,
                    onNewFolder = viewModel::createFolder,
                    onRename = viewModel::renameEntry,
                    onDelete = viewModel::deleteEntry,
                    onImport = viewModel::importFile,
                    onImportFolder = viewModel::importFolder,
                    onExportFolder = viewModel::exportFolder,
                    onSaveToDevice = saveToDevice,
                    pluginActionsFor = viewModel::actionsFor,
                    onPluginAction = viewModel::runFileAction,
                    pickingFor = pickingFor,
                    onUseAsTarget = viewModel::useAsLaunchTarget,
                    onCancelPicking = viewModel::cancelPicking,
                
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.FILES, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.PACKAGES -> PackagesScreen(
                    state = packagesState,
                    pythonVersion = status.pythonVersion.ifBlank { "3.13" },
                    onInstall = viewModel::installPackage,
                    onUninstall = viewModel::uninstallPackage,
                    onLookUp = viewModel::lookUpPackage,
                    onClearLookup = viewModel::clearPackageLookup,
                
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.PACKAGES, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.SERVERS -> ServersScreen(
                    state = serversState,
                    consoles = serverConsoles,
                    awaitingInput = awaitingInput,
                    workspaceRootName = "workspace root",
                    relativePath = { path -> viewModel.relativePath(File(path)) },
                    onFormChange = viewModel::updateLaunchForm,
                    onPickTarget = viewModel::pickLaunchTarget,
                    onSuggestPort = viewModel::suggestPort,
                    onLaunch = viewModel::launchServer,
                    onOpenConsole = viewModel::openServerConsole,
                    onCloseConsole = viewModel::closeServerConsole,
                    onServerInput = viewModel::submitServerInput,
                    onClearConsole = viewModel::clearServerConsole,
                    onStop = viewModel::stopServer,
                    onKill = viewModel::killServer,
                    onStopAll = viewModel::stopAllServers,
                    onKillAll = viewModel::killAllServers,
                    onCopy = { text ->
                        copyToClipboard(context, text)
                        viewModel.showToast("Copied $text")
                    },
                    onView = viewModel::viewServer,
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.SERVERS, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.DOCS -> DocsScreen(
                    languages = languages,
                    onOpen = { asset, title -> viewModel.openGuide(asset, title) },
                    onDownloadSource = viewModel::downloadSource,
                    sourceBusy = sourceBusy,
                    pluginGuides = guidesFor(installedPlugins, installedEnabled),
                    onOpenPluginGuide = viewModel::openPluginGuide,
                
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.DOCS, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.SYSTEM -> SystemScreen(
                    info = systemInfo,
                    busy = systemBusy,
                    onRefresh = viewModel::refreshSystem,
                    onClearCache = viewModel::clearCache,
                    onClearPycache = viewModel::clearPycache,
                    onExportLog = viewModel::saveDebugLog,
                    update = updateState,
                    updateSource = updateSource,
                    onCheckForUpdate = viewModel::checkForUpdate,
                    onDownloadUpdate = viewModel::downloadUpdate,
                    onCancelUpdate = viewModel::cancelUpdate,
                    onInstallUpdate = viewModel::installUpdate,
                    onDismissUpdate = viewModel::dismissUpdate,
                    onSetUpdateSource = viewModel::setUpdateSource,
                    backgroundChecks = backgroundChecks,
                    backgroundDownload = backgroundDownload,
                    onSetBackgroundChecks = viewModel::setBackgroundChecks,
                    onSetBackgroundDownload = viewModel::setBackgroundDownload,
                    versions = keptVersions,
                    versionsCap = versionsCap,
                    onSetVersionsCap = viewModel::setVersionsCap,
                    onInstallVersion = viewModel::installVersion,
                    onDeleteVersion = viewModel::deleteVersion,
                    onDeleteAllVersions = viewModel::deleteAllVersions,
                    onSaveVersionToPhone = { saveToDevice(it.file) },
                    onBackupWorkspace = { viewModel.backupWorkspaceForRollback(saveToDevice) },
                    onEmail = { address ->
                        val intent = android.content.Intent(
                            android.content.Intent.ACTION_SENDTO,
                            ("mailto:$address?subject=${Branding.NAME}" +
                                "%20${BuildConfig.VERSION_NAME}").toUri(),
                        )
                        runCatching { context.startActivity(intent) }
                            .onFailure {
                                // No mail app is ordinary on a phone used for
                                // one thing; the address is no use unread, so
                                // it goes to the clipboard instead.
                                copyToClipboard(context, address)
                                viewModel.showToast("No mail app - address copied")
                            }
                    },
                    // Keyed on the file list so deleting the folder makes the
                    // button appear without a trip somewhere else and back.
                    onRestoreExamples = remember(filesState.entries, systemInfo) {
                        if (viewModel.hasExamples) null else viewModel::restoreExamples
                    },
                
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.SYSTEM, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.PAGES -> PagesScreen(
                    state = pagesState,
                    kitOn = kitOn,
                    onCreate = viewModel::createPage,
                    onAdopt = viewModel::adoptPage,
                    onStart = { viewModel.startPage(it.id) },
                    onStop = { viewModel.stopPage(it.id) },
                    onOpen = viewModel::openPage,
                    onShare = { viewModel.sharePage(it.id) },
                    onUnshare = { viewModel.unsharePage(it.id) },
                    onRename = { project, name -> viewModel.renamePage(project.id, name) },
                    onRemove = { project, files -> viewModel.removePage(project.id, files) },
                    onOpenFolder = viewModel::openPageFolder,
                    onCopy = { text ->
                        copyToClipboard(context, text)
                        viewModel.showToast("Copied")
                    },
                    onStopAll = viewModel::stopAllPages,
                    onConnectCloudflare = viewModel::connectCloudflare,
                    onForgetCloudflare = viewModel::forgetCloudflare,
                    onDeploy = viewModel::deployPage,
                    onClearBuild = viewModel::clearPageBuild,
                    onSetHost = { project, host -> viewModel.setPageHost(project.id, host) },
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.PAGES, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.MUSIC -> MusicScreen(
                    state = musicState,
                    playback = playback,
                    onImport = { musicLauncher.launch(arrayOf("audio/*", "video/*")) },
                    onPlay = viewModel::playTrack,
                    onPlayAll = viewModel::playEverything,
                    onPlayPlaylist = viewModel::playPlaylist,
                    onToggle = viewModel::togglePlayback,
                    onNext = viewModel::skipNext,
                    onPrevious = viewModel::skipPrevious,
                    onSeek = viewModel::seekMusic,
                    onStop = viewModel::stopMusic,
                    onCycleLoop = viewModel::cycleLoop,
                    onToggleShuffle = viewModel::toggleShuffle,
                    onOpenPlaylist = viewModel::openPlaylist,
                    onNewPlaylist = viewModel::createPlaylist,
                    onRenamePlaylist = { playlist, name ->
                        viewModel.renamePlaylist(playlist.id, name)
                    },
                    onRemovePlaylist = viewModel::removePlaylist,
                    onRenameTrack = { track, title -> viewModel.renameTrack(track.id, title) },
                    onRemoveTrack = viewModel::removeTrack,
                    onAddToPlaylist = { id, track -> viewModel.addToPlaylist(id, track.id) },
                    onRemoveFromPlaylist = { id, track ->
                        viewModel.removeFromPlaylist(id, track.id)
                    },
                    onMove = { id, track, delta -> viewModel.moveInPlaylist(id, track.id, delta) },
                    onTidy = viewModel::tidyMusic,
                    onSearch = viewModel::searchMusic,
                    onSort = viewModel::sortMusic,
                    onCollection = viewModel::showCollection,
                    onOpenDetail = { track -> viewModel.openTrackDetail(track.id) },
                    onCloseDetail = viewModel::closeTrackDetail,
                    onSaveDetails = { track, title, artist, album ->
                        viewModel.setTrackDetails(track.id, title, artist, album)
                    },
                    onSpeed = viewModel::setMusicSpeed,
                    onSleep = viewModel::setSleepTimer,
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.MUSIC, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.MORE -> MoreScreen(
                    serverCount = serverCount,
                    downloadCount = downloadsState.files.size,
                    pluginCount = pluginsEnabled.size,
                    errorCount = debugErrors,
                    pageCount = pagesState.active,
                    musicPlaying = playback.playing,
                    onSelect = viewModel::selectTab,
                    updateWaiting = updateWaiting,
                    // Only tabs from plugins that are switched on: a tab is a
                    // way into running code, so an installed-but-off plugin
                    // must not have one.
                    pluginTabs = installedPlugins.filter {
                        it.hasTab && installedEnabled.contains(it.id)
                    },
                    onOpenPluginTab = viewModel::openPluginPanel,
                )

                Tab.DOWNLOADS -> DownloadsScreen(
                    state = downloadsState,
                    downloaderOn = viewModel.isPluginOn(PluginIds.DOWNLOADER),
                    exportOn = viewModel.isPluginOn(PluginIds.WORKSPACE_EXPORT),
                    onDownload = viewModel::downloadUrl,
                    onOpen = viewModel::openDownload,
                    onCopyToWorkspace = viewModel::copyDownloadToWorkspace,
                    onDelete = viewModel::deleteDownload,
                    onExport = viewModel::exportWorkspace,
                    onSaveToDevice = { saveToDevice(File(it.path)) },
                    onAddFile = viewModel::addToDownloads,
                
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.DOWNLOADS, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.PLUGINS -> PluginsScreen(
                    enabled = pluginsEnabled,
                    installed = installedPlugins,
                    installedEnabled = installedEnabled,
                    busy = pluginBusy,
                    workspaceCandidates = pluginCandidates,
                    onToggle = viewModel::setPluginEnabled,
                    onOpen = viewModel::openPlugin,
                    onEnableAll = viewModel::enableAllPlugins,
                    onReset = viewModel::resetPlugins,
                    onInstallFile = { pluginFileLauncher.launch(arrayOf("*/*")) },
                    onInstallFolder = { pluginFolderLauncher.launch(null) },
                    onInstallWorkspace = viewModel::installPluginFromWorkspace,
                    onRefreshCandidates = viewModel::refreshPluginCandidates,
                    onToggleInstalled = viewModel::setCustomPluginEnabled,
                    onOpenPanel = viewModel::openPluginPanel,
                    onRemoveInstalled = viewModel::removeCustomPlugin,
                    onReadGuide = { viewModel.openGuide() },
                    settingsFor = viewModel::pluginSettings,
                    onSetting = viewModel::setPluginSetting,
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.PLUGINS, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )

                Tab.PLUGIN_PANEL -> {
                    val panel = openPanel
                    if (panel == null) {
                        LaunchedEffect(Unit) { viewModel.selectTab(Tab.PLUGINS) }
                    } else {
                        PluginPanelScreen(
                            plugin = panel,
                            viewModel = viewModel,
                            onClose = viewModel::closePluginPanel,
                            panelFile = openPanelFile,
                        )
                    }
                }

                Tab.TOOL -> {
                    val tool = activeTool
                    if (tool == null) {
                        // Nothing to show without a chosen tool; the plugin
                        // list is where one gets chosen.
                        LaunchedEffect(Unit) { viewModel.selectTab(Tab.PLUGINS) }
                    } else {
                        ToolScreen(screen = tool, viewModel = viewModel)
                    }
                }

                Tab.DEBUG -> DebugScreen(
                    entries = debugEntries,
                    onClear = viewModel::clearDebugLog,
                    onCopy = { text ->
                        copyToClipboard(context, text)
                        viewModel.showToast("Copied to the clipboard")
                    },
                    onSave = viewModel::saveDebugLog,
                    exportText = viewModel::debugLogText,
                
                    pluginSections = {
                        PluginSections(
                            sectionsFor(Tab.DEBUG, installedPlugins, installedEnabled),
                            viewModel,
                        )
                    },
                )
            }
        }
    }

    // The preview sits over everything: it is a mode, not a destination, and
    // closing it puts the user back exactly where they were.
    previewPage?.let { page ->
        Box(
            Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                // The overlay sits outside the Scaffold, so it has to inset
                // itself: without this its header hides under the status bar.
                .windowInsetsPadding(WindowInsets.systemBars),
        ) {
            PreviewScreen(
                page = page,
                onClose = viewModel::closePreview,
                onReload = { viewModel.previewFile(File(page.baseDirectory + page.name)) },
                onLinkOut = viewModel::previewLink,
            )
        }
        BackHandler(enabled = true) { viewModel.closePreview() }
    }

    // An import that would overwrite something waits here for an answer.
    pendingImport?.let { pending ->
        ImportCollisionDialog(
            name = pending.name,
            isFolder = pending.isFolder,
            existingSummary = remember(pending.existing) { describeExisting(pending.existing) },
            onReplace = { viewModel.answerPendingImport(ImportChoice.REPLACE) },
            onKeepBoth = { viewModel.answerPendingImport(ImportChoice.KEEP_BOTH) },
            onCancel = { viewModel.answerPendingImport(ImportChoice.CANCEL) },
        )
    }

    if (saveAsOpen) {
        TextPromptDialog(
            title = "Save as",
            label = "File name",
            initial = "script.py",
            confirmLabel = "Save",
            onDismiss = { saveAsOpen = false },
            onConfirm = { name ->
                saveAsOpen = false
                viewModel.saveEditor(name)
            },
        )
    }

    if (aboutOpen) {
        AboutDialog(
            info = runtimeInfo,
            status = status,
            onDismiss = { aboutOpen = false },
            onOpenUpdates = {
                aboutOpen = false
                viewModel.selectTab(Tab.SYSTEM)
                viewModel.checkForUpdate()
            },
        )
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.TabItem(
    target: Tab,
    icon: ImageVector,
    current: Tab,
    onSelect: (Tab) -> Unit,
    count: Int = 0,
    dot: Boolean = false,
    forceSelected: Boolean = false,
) {
    NavigationBarItem(
        selected = current == target || forceSelected,
        onClick = { onSelect(target) },
        icon = {
            BadgedBox(
                badge = {
                    when {
                        count > 0 -> Badge { Text(count.toString()) }
                        dot -> Badge()
                        else -> Unit
                    }
                },
            ) {
                Icon(icon, contentDescription = target.label)
            }
        },
        label = { Text(target.label, style = MaterialTheme.typography.labelSmall) },
        colors = NavigationBarItemDefaults.colors(
            selectedIconColor = MaterialTheme.colorScheme.onPrimary,
            selectedTextColor = MaterialTheme.colorScheme.primary,
            indicatorColor = MaterialTheme.colorScheme.primary,
            unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
        ),
    )
}

@Composable
private fun AboutDialog(
    info: Map<String, String>,
    status: com.expstudio.pycmd.python.EngineStatus,
    onDismiss: () -> Unit,
    onOpenUpdates: () -> Unit,
) {
    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            // The build type appends "-debug"; the title wants the version.
            val version = BuildConfig.VERSION_NAME.substringBefore('-')
            Text("${Branding.NAME} $version", style = MaterialTheme.typography.titleMedium)
        },
        text = {
            Column {
                Text(
                    "A Python command line, editor and server runner for Android.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
                InfoRow(
                    "App",
                    "${BuildConfig.VERSION_NAME} (build ${BuildConfig.VERSION_CODE})",
                )
                InfoRow("Python", info["full_version"] ?: status.pythonVersion)
                InfoRow("Platform", info["platform"] ?: "android")
                InfoRow("Working dir", info["cwd"] ?: "")
                if (status.startupError != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Startup error: ${status.startupError}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        },
        confirmButton = {
            androidx.compose.material3.TextButton(onClick = onDismiss) { Text("Close") }
        },
        // The version is right here, so this is where somebody wonders whether
        // it is the current one. It goes to System and starts the check.
        dismissButton = {
            androidx.compose.material3.TextButton(onClick = onOpenUpdates) {
                Text("Check for updates")
            }
        },
    )
}

@Composable
private fun InfoRow(label: String, value: String) {
    if (value.isBlank()) return
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(
            label.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(value, style = MaterialTheme.typography.bodySmall, fontFamily = MonoFamily)
    }
}

private fun streamName(stream: OutputChunk.Stream): String = when (stream) {
    OutputChunk.Stream.STDERR -> "stderr"
    OutputChunk.Stream.SYSTEM -> "system"
    OutputChunk.Stream.INPUT -> "input"
    OutputChunk.Stream.STDOUT -> "stdout"
}

/**
 * Builds the JS that appends a batch of chunks.
 *
 * A batch rather than a chunk because every call to `evaluateJavascript` is a
 * separate parse and a separate hop to the WebView's thread, and a loop that
 * prints a thousand lines produces a thousand chunks. One script carrying a
 * thousand entries is the difference between a console that keeps up and one
 * that falls behind the program it is showing.
 *
 * Output can arrive before console.js has finished loading, so anything early
 * is parked in a queue the script drains on start-up.
 */
private fun consoleAppendScript(chunks: List<OutputChunk>): String {
    val payload = StringBuilder(chunks.sumOf { it.text.length } + 64 * chunks.size)
    payload.append('[')
    chunks.forEachIndexed { index, chunk ->
        if (index > 0) payload.append(',')
        payload.append("{s:").append(jsString(streamName(chunk.stream)))
            .append(",t:").append(jsString(chunk.text)).append('}')
    }
    payload.append(']')

    return """
        (function () {
          var batch = $payload;
          if (window.PyConsole) {
            for (var i = 0; i < batch.length; i += 1) {
              window.PyConsole.append(batch[i].s, batch[i].t);
            }
          } else {
            window.PyConsoleQueue = window.PyConsoleQueue || [];
            for (var j = 0; j < batch.length; j += 1) {
              window.PyConsoleQueue.push({ stream: batch[j].s, text: batch[j].t });
            }
          }
        })();
    """.trimIndent()
}

/** How many lines go into the WebView in one script. */
private const val CONSOLE_BATCH = 400

/** What is already at that name, so the choice is an informed one. */
private fun describeExisting(file: File): String {
    val when_ = SimpleDateFormat("dd MMM HH:mm", Locale.US).format(Date(file.lastModified()))
    if (file.isDirectory) {
        val count = file.listFiles()?.size ?: 0
        return "Here now: a folder of $count item${if (count == 1) "" else "s"}, last changed $when_"
    }
    val size = file.length()
    val readable = when {
        size >= 1024 * 1024 -> "%.1f MB".format(size / 1024.0 / 1024.0)
        size >= 1024 -> "${size / 1024} KB"
        else -> "$size B"
    }
    return "Here now: $readable, last changed $when_"
}

private fun copyToClipboard(context: Context, text: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
    clipboard?.setPrimaryClip(ClipData.newPlainText("PyCmd", text))
}
