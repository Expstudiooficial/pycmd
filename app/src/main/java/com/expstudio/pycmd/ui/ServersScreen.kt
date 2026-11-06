package com.expstudio.pycmd.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.python.OutputChunk
import com.expstudio.pycmd.python.RunningServer

@Composable
fun ServersScreen(
    state: ServersState,
    consoles: Map<String, List<OutputChunk>>,
    awaitingInput: Set<String>,
    workspaceRootName: String,
    relativePath: (String) -> String,
    onFormChange: ((LaunchForm) -> LaunchForm) -> Unit,
    onPickTarget: () -> Unit,
    onSuggestPort: () -> Unit,
    onLaunch: () -> Unit,
    onOpenConsole: (String) -> Unit,
    onCloseConsole: () -> Unit,
    onServerInput: (String, String) -> Unit,
    onClearConsole: (String) -> Unit,
    onStop: (String) -> Unit,
    onKill: (String) -> Unit,
    onStopAll: () -> Unit,
    onKillAll: () -> Unit,
    onCopy: (String) -> Unit,
    onView: (RunningServer) -> Unit,
    modifier: Modifier = Modifier,
    /** Sections plugins have added to this screen; empty when none are on. */
    pluginSections: @Composable () -> Unit = {},
) {
    val open = state.openConsole
    if (open != null) {
        val server = state.servers.firstOrNull { it.handle == open }
        ServerConsole(
            handle = open,
            server = server,
            lines = consoles[open].orEmpty(),
            awaitingInput = open in awaitingInput,
            onBack = onCloseConsole,
            onSubmit = { line -> onServerInput(open, line) },
            onClear = { onClearConsole(open) },
            onStop = { onStop(open) },
            onKill = { onKill(open) },
            onCopy = onCopy,
            modifier = modifier,
        )
        return
    }

    var confirmKillAll by remember { mutableStateOf(false) }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            LaunchCard(
                form = state.form,
                busy = state.busy,
                localIp = state.localIp,
                relativePath = relativePath,
                workspaceRootName = workspaceRootName,
                onFormChange = onFormChange,
                onPickTarget = onPickTarget,
                onSuggestPort = onSuggestPort,
                onLaunch = onLaunch,
            )
        }

        item {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SectionTitle("Running (${state.running})")
                if (state.servers.isNotEmpty()) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = onStopAll, enabled = state.running > 0) {
                            Text("Stop all", style = MaterialTheme.typography.labelLarge)
                        }
                        TextButton(onClick = { confirmKillAll = true }) {
                            Text(
                                "Kill all",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                }
            }
        }

        if (state.servers.isEmpty()) {
            item {
                EmptyState(
                    icon = PyIcons.Dns,
                    title = "Nothing running",
                    hint = "Fill in the form above and press Run.",
                )
            }
        } else {
            items(state.servers, key = { it.handle }) { server ->
                ServerRow(
                    server = server,
                    relativePath = relativePath,
                    onOpen = { onOpenConsole(server.handle) },
                    onStop = { onStop(server.handle) },
                    onKill = { onKill(server.handle) },
                    onCopy = onCopy,
                    onView = { onView(server) },
                )
            }
        }

        item { pluginSections() }

        item {
            PyCard {
                Text("Stop vs Kill", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(6.dp))
                Text(
                    text = "Stop asks the server to close and waits a few seconds. Kill frees " +
                        "the port immediately and forces the thread down - use it when a " +
                        "script hangs before it ever finishes starting, which Stop cannot " +
                        "help with.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

    if (confirmKillAll) {
        ConfirmDialog(
            title = "Kill every server?",
            message = "All listening ports are freed immediately and running scripts are " +
                "forced down. Anything they were part-way through is lost.",
            confirmLabel = "Kill all",
            destructive = true,
            onDismiss = { confirmKillAll = false },
            onConfirm = {
                confirmKillAll = false
                onKillAll()
            },
        )
    }
}

// ---------------------------------------------------------------- launch form

@Composable
private fun LaunchCard(
    form: LaunchForm,
    busy: Boolean,
    localIp: String,
    relativePath: (String) -> String,
    workspaceRootName: String,
    onFormChange: ((LaunchForm) -> LaunchForm) -> Unit,
    onPickTarget: () -> Unit,
    onSuggestPort: () -> Unit,
    onLaunch: () -> Unit,
) {
    val problem = form.problem()

    PyCard {
        Text("Start a server", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(10.dp))

        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            ServerKind.entries.forEachIndexed { index, kind ->
                SegmentedButton(
                    selected = form.kind == kind,
                    onClick = { onFormChange { it.copy(kind = kind) } },
                    shape = SegmentedButtonDefaults.itemShape(index, ServerKind.entries.size),
                ) {
                    Text(kind.label, style = MaterialTheme.typography.labelLarge)
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        // Target
        FieldLabel(if (form.kind == ServerKind.STATIC) "Folder" else "File")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = form.target?.let {
                    val shown = relativePath(it.absolutePath)
                    if (shown.isBlank() || shown == "/") workspaceRootName else shown
                } ?: "Nothing chosen",
                style = MaterialTheme.typography.bodyMedium,
                fontFamily = MonoFamily,
                color = if (form.target == null) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
                maxLines = 1,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            GhostButton("Choose", PyIcons.Folder, onPickTarget)
        }

        // What pressing Run will actually do with it. Worth saying before it
        // happens: a page is served rather than executed, a .go file goes to
        // an interpreter, and a .java file cannot run here at all.
        //
        // A folder gets the same treatment in either mode. In "serve" mode the
        // note is what stops the surprise this exists to prevent: a Flask
        // project handed to a file server shows a list of static/ and
        // templates/, and the reason is worth reading before pressing Run,
        // not after.
        val servingSomethingRunnable = form.kind == ServerKind.STATIC &&
            form.plan.how == "script" && form.plan.entry.isNotBlank()
        if (form.plan.note.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            Text(
                text = if (servingSomethingRunnable) {
                    "There is ${form.plan.entry} in here. Serving this folder hands " +
                        "over the files as they are; running it starts the app."
                } else {
                    form.plan.note
                },
                style = MaterialTheme.typography.labelSmall,
                color = if (form.plan.runnable || form.kind == ServerKind.STATIC) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.error
                },
            )
            if (servingSomethingRunnable) {
                Spacer(Modifier.height(8.dp))
                GhostButton(
                    "Run ${form.plan.entry} instead",
                    PyIcons.PlayArrow,
                    { onFormChange { it.copy(kind = ServerKind.SCRIPT, script = it.folder) } },
                    Modifier.fillMaxWidth(),
                )
            }
        }

        Spacer(Modifier.height(12.dp))

        // Port
        FieldLabel("Port")
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = form.port,
                onValueChange = { text -> onFormChange { it.copy(port = text.filter(Char::isDigit).take(5)) } },
                modifier = Modifier.weight(1f),
                singleLine = true,
                placeholder = { Text("8000", fontFamily = MonoFamily) },
                supportingText = if (form.kind == ServerKind.SCRIPT) {
                    {
                        Text(
                            if (form.plan.how == "serve") {
                                "The folder this file sits in is served on this port."
                            } else {
                                "Optional - only so the address can be shown and the port checked."
                            },
                        )
                    }
                } else {
                    null
                },
                shape = RoundedCornerShape(12.dp),
                textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = MonoFamily),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primary,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                ),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Done,
                ),
            )
            Spacer(Modifier.width(8.dp))
            GhostButton("Free one", PyIcons.RestartAlt, onSuggestPort)
        }

        Spacer(Modifier.height(12.dp))

        FieldLabel("Name (optional)")
        OutlinedTextField(
            value = form.label,
            onValueChange = { text -> onFormChange { it.copy(label = text.take(40)) } },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            placeholder = { Text("How it appears in the list") },
            shape = RoundedCornerShape(12.dp),
            textStyle = MaterialTheme.typography.bodyMedium,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = MaterialTheme.colorScheme.primary,
                unfocusedBorderColor = MaterialTheme.colorScheme.outline,
            ),
        )

        Spacer(Modifier.height(6.dp))

        ToggleRow(
            title = "Reachable on Wi-Fi",
            subtitle = if (form.exposeToNetwork) {
                if (localIp.isBlank()) "Other devices on this network can connect." else "http://$localIp:${form.port}/"
            } else {
                "This device only (127.0.0.1)."
            },
            checked = form.exposeToNetwork,
            onCheckedChange = { on -> onFormChange { it.copy(exposeToNetwork = on) } },
        )

        if (form.kind == ServerKind.STATIC) {
            ToggleRow(
                title = "Log each request",
                subtitle = "Every hit is printed to this server's console.",
                checked = form.logRequests,
                onCheckedChange = { on -> onFormChange { it.copy(logRequests = on) } },
            )
        }

        Spacer(Modifier.height(12.dp))

        ActionButton(
            text = if (busy) "Starting..." else "Run",
            icon = PyIcons.PlayArrow,
            onClick = onLaunch,
            enabled = !busy && problem == null,
            modifier = Modifier.fillMaxWidth(),
        )

        if (problem != null) {
            Spacer(Modifier.height(6.dp))
            Text(
                problem,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (busy) BusyRow("Starting...")
    }
}

@Composable
private fun FieldLabel(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(bottom = 4.dp),
    )
}

@Composable
private fun ToggleRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium)
            Text(
                subtitle,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

// ------------------------------------------------------------------ list rows

@Composable
private fun ServerRow(
    server: RunningServer,
    relativePath: (String) -> String,
    onOpen: () -> Unit,
    onStop: () -> Unit,
    onKill: () -> Unit,
    onCopy: (String) -> Unit,
    onView: () -> Unit,
) {
    val statusColor = when (server.status) {
        "running" -> MaterialTheme.colorScheme.primary
        "error" -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    PyCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        server.label,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    Spacer(Modifier.width(8.dp))
                    StatusChip(server.status, statusColor)
                }
                Spacer(Modifier.height(3.dp))
                Text(
                    text = buildString {
                        append(if (server.kind == "static") "folder" else "script")
                        append("  ")
                        append(relativePath(server.target).ifBlank { server.target })
                    },
                    style = MaterialTheme.typography.labelSmall,
                    fontFamily = MonoFamily,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }

        if (server.url.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    server.url,
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = MonoFamily,
                    color = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                )
                IconButton(onClick = { onCopy(server.url) }, modifier = Modifier.size(34.dp)) {
                    Icon(
                        PyIcons.ContentCopy,
                        contentDescription = "Copy address",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(16.dp),
                    )
                }
            }
        }

        if (server.error.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(
                server.error,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }

        Spacer(Modifier.height(4.dp))
        Text(
            text = buildString {
                append("up ").append(server.readableUptime)
                if (server.kind == "static") append("   ").append(server.requests).append(" requests")
            },
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GhostButton("Console", PyIcons.Terminal, onOpen, Modifier.weight(1f))
            // A server you can look at is a server you can check. Opening it in
            // the preview beats reading the address and typing it elsewhere.
            GhostButton(
                "View",
                PyIcons.PlayArrow,
                onView,
                Modifier.weight(1f),
                enabled = server.isRunning && server.url.isNotBlank(),
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GhostButton("Stop", PyIcons.Stop, onStop, Modifier.weight(1f), enabled = server.isRunning)
            ActionButton(
                text = "Kill",
                icon = PyIcons.Delete,
                onClick = onKill,
                modifier = Modifier.weight(1f),
                containerColor = MaterialTheme.colorScheme.error,
                contentColor = MaterialTheme.colorScheme.onPrimary,
            )
        }
    }
}

// -------------------------------------------------------------- server console

@Composable
private fun ServerConsole(
    handle: String,
    server: RunningServer?,
    lines: List<OutputChunk>,
    awaitingInput: Boolean,
    onBack: () -> Unit,
    onSubmit: (String) -> Unit,
    onClear: () -> Unit,
    onStop: () -> Unit,
    onKill: () -> Unit,
    onCopy: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize()) {
        Row(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(
                    PyIcons.ArrowBack,
                    contentDescription = "Back to the server list",
                    tint = MaterialTheme.colorScheme.onSurface,
                )
            }
            Column(Modifier.weight(1f)) {
                Text(
                    server?.label ?: handle,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                )
                Text(
                    text = server?.let { "${it.status}   up ${it.readableUptime}" } ?: "not tracked",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (server?.url?.isNotBlank() == true) {
                IconButton(onClick = { onCopy(server.url) }) {
                    Icon(
                        PyIcons.ContentCopy,
                        contentDescription = "Copy address",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
            IconButton(onClick = onClear) {
                Icon(
                    PyIcons.Clear,
                    contentDescription = "Clear this console",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp),
                )
            }
        }

        Divider()

        Box(Modifier.weight(1f).fillMaxWidth().background(MaterialTheme.colorScheme.background)) {
            if (lines.isEmpty()) {
                EmptyState(
                    icon = PyIcons.Terminal,
                    title = "No output yet",
                    hint = "Anything this server prints shows up here.",
                    modifier = Modifier.padding(top = 40.dp),
                )
            } else {
                LogList(
                    lines = lines.map { chunk ->
                        LogLine(
                            text = chunk.text,
                            color = when (chunk.stream) {
                                OutputChunk.Stream.STDERR -> MaterialTheme.colorScheme.error
                                OutputChunk.Stream.SYSTEM -> MaterialTheme.colorScheme.secondary
                                OutputChunk.Stream.INPUT -> MaterialTheme.colorScheme.primary
                                OutputChunk.Stream.STDOUT -> MaterialTheme.colorScheme.onBackground
                            },
                        )
                    },
                )
            }
        }

        ConsoleInputBar(
            placeholder = if (awaitingInput) "The server is waiting for input" else "Send a line to stdin",
            highlighted = awaitingInput,
            onSubmit = onSubmit,
        )

        Row(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            GhostButton(
                "Stop",
                PyIcons.Stop,
                onStop,
                Modifier.weight(1f),
                enabled = server?.isRunning == true,
            )
            ActionButton(
                text = "Kill",
                icon = PyIcons.Delete,
                onClick = onKill,
                modifier = Modifier.weight(1f),
                containerColor = MaterialTheme.colorScheme.error,
                contentColor = MaterialTheme.colorScheme.onPrimary,
            )
        }
    }
}
