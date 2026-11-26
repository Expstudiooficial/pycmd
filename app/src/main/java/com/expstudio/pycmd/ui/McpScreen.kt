package com.expstudio.pycmd.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp

/** One AI app's set-up, as the MCP tab shows it. */
data class McpSetup(val app: String, val where: String, val text: String)

data class McpState(
    val on: Boolean = false,
    val lan: Boolean = false,
    val readOnly: Boolean = false,
    val running: Boolean = false,
    val url: String = "",
    val error: String = "",
    val tools: Int = 0,
    val token: String = "",
    val calls: List<String> = emptyList(),
    val setups: List<McpSetup> = emptyList(),
)

/**
 * MCP: an AI agent on a computer (Claude Code, Antigravity, Cursor...) drives
 * PyCmd on this phone - files, Python, PyCmdTeach, cloud storage and the
 * screen. Off until switched on; on Wi-Fi only when that is switched on too.
 */
@Composable
fun McpScreen(
    state: McpState,
    onToggle: (Boolean) -> Unit,
    onLan: (Boolean) -> Unit,
    onReadOnly: (Boolean) -> Unit,
    onNewToken: () -> Unit,
    onCopied: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val clipboard = LocalClipboardManager.current
    val copy: (String) -> Unit = { clipboard.setText(AnnotatedString(it)); onCopied() }
    LazyColumn(modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            PyCard {
                Text("MCP · AI agents", style = MaterialTheme.typography.titleLarge)
                Text(
                    "Let an AI app on your computer use PyCmd on this phone: ${state.tools} " +
                        "tools - files, Python, PyCmdTeach, cloud storage, and the screen " +
                        "itself (tabs, console, editor, screenshots).",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
                SwitchRow(if (state.running) "On" else "Off",
                    state.error.ifEmpty { if (state.running) state.url else "Switch it on to start" },
                    state.on, onToggle)
                SwitchRow("Allow Wi-Fi", "A computer on the same Wi-Fi can connect (with the token)",
                    state.lan, onLan)
                SwitchRow("Read-only", "Agents can look but not change anything",
                    state.readOnly, onReadOnly)
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    GhostButton("Copy token", PyIcons.ContentCopy, onClick = { copy(state.token) })
                    Spacer(Modifier.width(8.dp))
                    GhostButton("New token", PyIcons.RestartAlt, onClick = onNewToken,
                        destructive = true)
                }
            }
        }
        if (state.setups.isNotEmpty()) item { SectionTitle("Set it up in your AI app") }
        items(state.setups, key = { it.app }) { setup ->
            PyCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(setup.app, style = MaterialTheme.typography.titleMedium)
                        Text(setup.where, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    GhostButton("Copy", PyIcons.ContentCopy, onClick = { copy(setup.text) })
                }
                Spacer(Modifier.height(6.dp))
                Text(setup.text, style = MaterialTheme.typography.bodySmall, fontFamily = MonoFamily,
                    modifier = Modifier.horizontalScroll(rememberScrollState()))
            }
        }
        if (state.calls.isNotEmpty()) {
            item { SectionTitle("Last calls") }
            items(state.calls) { line ->
                Text(line, style = MaterialTheme.typography.bodySmall, fontFamily = MonoFamily)
            }
        }
    }
}

@Composable
private fun SwitchRow(title: String, detail: String, on: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            Text(detail, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = on, onCheckedChange = onChange)
    }
}
