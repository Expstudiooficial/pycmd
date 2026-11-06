package com.expstudio.pycmd.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.util.LogEntry
import com.expstudio.pycmd.util.LogLevel

/**
 * Everything the app knows went wrong, in one place.
 *
 * The console shows what a script printed. This shows the machinery around it:
 * interpreter startup, server lifecycles, package installs, file errors,
 * JavaScript errors from the WebViews and uncaught Java exceptions. When
 * something misbehaves and the console has nothing useful to say, this does.
 */
@Composable
fun DebugScreen(
    entries: List<LogEntry>,
    onClear: () -> Unit,
    onCopy: (String) -> Unit,
    onSave: () -> Unit,
    exportText: () -> String,
    modifier: Modifier = Modifier,
    /** Sections plugins have added to this screen; empty when none are on. */
    pluginSections: @Composable () -> Unit = {},
) {
    var minLevel by remember { mutableStateOf(LogLevel.DEBUG) }
    var query by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf<Long?>(null) }

    val counts = remember(entries) { entries.groupingBy { it.level }.eachCount() }

    val visible = remember(entries, minLevel, query) {
        val needle = query.trim().lowercase()
        entries.filter { entry ->
            entry.level.ordinal >= minLevel.ordinal &&
                (
                    needle.isEmpty() ||
                        entry.message.lowercase().contains(needle) ||
                        entry.tag.lowercase().contains(needle) ||
                        entry.detail?.lowercase()?.contains(needle) == true
                    )
        }
    }

    val listState = rememberLazyListState()

    // Follow the tail as new entries land, unless the user has scrolled up.
    val atBottom by remember(listState) {
        androidx.compose.runtime.derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()
            last == null || last.index >= listState.layoutInfo.totalItemsCount - 2
        }
    }
    LaunchedEffect(visible.size, atBottom) {
        if (atBottom && visible.isNotEmpty()) listState.scrollToItem(visible.lastIndex)
    }

    Column(modifier.fillMaxSize()) {
        Column(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surface)
                .padding(horizontal = 12.dp, vertical = 10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Debug console", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${entries.size} entries, ${counts[LogLevel.ERROR] ?: 0} errors",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                IconButton(onClick = { onCopy(exportText()) }) {
                    Icon(
                        PyIcons.ContentCopy,
                        contentDescription = "Copy the whole log",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(18.dp),
                    )
                }
                IconButton(onClick = onSave) {
                    Icon(
                        PyIcons.Save,
                        contentDescription = "Save the log to the workspace",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(18.dp),
                    )
                }
                IconButton(onClick = onClear) {
                    Icon(
                        PyIcons.Delete,
                        contentDescription = "Clear the log",
                        tint = MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("Filter by text or tag", style = MaterialTheme.typography.bodySmall) },
                shape = RoundedCornerShape(12.dp),
                textStyle = MaterialTheme.typography.bodyMedium,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primary,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outline,
                ),
            )
        }

        Row(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 10.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LogLevel.entries.forEach { level ->
                val count = counts[level] ?: 0
                val selected = level == minLevel
                Surface(
                    color = if (selected) {
                        level.color().copy(alpha = 0.22f)
                    } else {
                        MaterialTheme.colorScheme.surface
                    },
                    contentColor = if (selected) level.color() else MaterialTheme.colorScheme.onSurfaceVariant,
                    shape = RoundedCornerShape(999.dp),
                    modifier = Modifier.clickable { minLevel = level },
                ) {
                    Text(
                        text = if (count > 0) "${level.label}  $count" else level.label,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    )
                }
            }
        }

        Divider()

        if (visible.isEmpty()) {
            Column(Modifier.fillMaxSize()) {
                EmptyState(
                    icon = PyIcons.BugReport,
                    title = if (entries.isEmpty()) "Nothing logged yet" else "Nothing matches",
                    hint = if (entries.isEmpty()) {
                        "Errors, server events and interpreter messages appear here."
                    } else {
                        "Try a lower level or a different search."
                    },
                    modifier = Modifier.padding(top = 40.dp),
                )
                // Also here: a plugin's section should not disappear just
                // because there is nothing in the log to scroll past.
                Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                    pluginSections()
                }
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background),
                contentPadding = PaddingValues(vertical = 6.dp),
            ) {
                items(visible, key = { it.id }) { entry ->
                    DebugRow(
                        entry = entry,
                        expanded = expanded == entry.id,
                        onToggle = { expanded = if (expanded == entry.id) null else entry.id },
                        onCopy = { onCopy(entry.toPlainText()) },
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
}

@Composable
private fun DebugRow(
    entry: LogEntry,
    expanded: Boolean,
    onToggle: () -> Unit,
    onCopy: () -> Unit,
) {
    val color = entry.level.color()

    Column(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onToggle)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Text(
                entry.time,
                style = MaterialTheme.typography.labelSmall,
                fontFamily = MonoFamily,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.width(8.dp))
            Text(
                entry.level.short,
                style = MaterialTheme.typography.labelSmall,
                fontFamily = MonoFamily,
                fontWeight = FontWeight.Bold,
                color = color,
            )
            Spacer(Modifier.width(8.dp))
            Text(
                entry.tag,
                style = MaterialTheme.typography.labelSmall,
                fontFamily = MonoFamily,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
            )
        }
        Spacer(Modifier.height(2.dp))
        Text(
            entry.message,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = MonoFamily,
            color = if (entry.level == LogLevel.ERROR) color else MaterialTheme.colorScheme.onBackground,
            maxLines = if (expanded) Int.MAX_VALUE else 3,
        )

        if (!entry.detail.isNullOrBlank()) {
            if (expanded) {
                Spacer(Modifier.height(6.dp))
                Box(
                    Modifier
                        .fillMaxWidth()
                        .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(8.dp))
                        .padding(8.dp),
                ) {
                    Text(
                        entry.detail,
                        style = MaterialTheme.typography.labelSmall,
                        fontFamily = MonoFamily,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.horizontalScroll(rememberScrollState()),
                        softWrap = false,
                    )
                }
                Spacer(Modifier.height(4.dp))
                Row {
                    Text(
                        "Copy entry",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.clickable(onClick = onCopy).padding(vertical = 4.dp),
                    )
                }
            } else {
                Text(
                    "tap for detail",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
    Box(
        Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(MaterialTheme.colorScheme.outlineVariant),
    )
}

@Composable
private fun LogLevel.color(): Color = when (this) {
    LogLevel.DEBUG -> MaterialTheme.colorScheme.onSurfaceVariant
    LogLevel.INFO -> MaterialTheme.colorScheme.secondary
    LogLevel.WARN -> MaterialTheme.colorScheme.tertiary
    LogLevel.ERROR -> MaterialTheme.colorScheme.error
}
