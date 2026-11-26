package com.expstudio.pycmd.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.plugins.InstalledPlugin

/**
 * The destinations that do not fit in the bottom bar.
 *
 * Five items is the most a phone-width navigation bar can label without
 * wrapping, and there are eight screens, so the least-used sit here - along
 * with any a plugin has published, which is the only way a plugin can add a
 * place of its own without the app's source changing to make room for it.
 */
@Composable
fun MoreScreen(
    serverCount: Int,
    downloadCount: Int,
    pluginCount: Int,
    errorCount: Int,
    /** How many pages are running, so More can say so without being opened. */
    pageCount: Int,
    /** True while something is playing, so More shows it without being opened. */
    musicPlaying: Boolean,
    /** Lessons finished in PyCmdTeach, so the row can nudge. */
    teachDone: Int,
    /** Days in a row, shown as a badge when there is one. */
    teachStreak: Int,
    onSelect: (Tab) -> Unit,
    /** True when a newer build is waiting in System, so the row says so. */
    updateWaiting: Boolean,
    modifier: Modifier = Modifier,
    pluginTabs: List<InstalledPlugin> = emptyList(),
    onOpenPluginTab: (InstalledPlugin) -> Unit = {},
) {
    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionTitle("More") }

        item {
            DestinationRow(
                icon = PyIcons.Dns,
                title = "Pages",
                subtitle = "Websites that live in the app, switched on and off",
                badge = if (pageCount > 0) pageCount.toString() else null,
                onClick = { onSelect(Tab.PAGES) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.MusicNote,
                title = "Music",
                subtitle = "Your own audio, playing while you work - and with the app closed",
                badge = if (musicPlaying) "on" else null,
                onClick = { onSelect(Tab.MUSIC) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.School,
                title = "PyCmdTeach",
                subtitle = if (teachDone > 0) {
                    "$teachDone lessons done - keep going"
                } else {
                    "Learn every language the app runs, one lesson at a time"
                },
                badge = if (teachStreak > 0) "${teachStreak}d" else null,
                onClick = { onSelect(Tab.TEACH) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.Terminal,
                title = "MCP · AI agents",
                subtitle = "Let Claude Code, Antigravity, Cursor and others drive PyCmd",
                badge = null,
                onClick = { onSelect(Tab.MCP) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.Palette,
                title = "Appearance",
                subtitle = "Themes, including the Halloween one, and your own colours",
                badge = null,
                onClick = { onSelect(Tab.APPEARANCE) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.Inventory2,
                title = "Packages",
                subtitle = "Install Python libraries from PyPI onto the device",
                badge = null,
                onClick = { onSelect(Tab.PACKAGES) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.FileUpload,
                title = "Downloads",
                subtitle = "Files fetched from a URL, and workspace exports",
                badge = if (downloadCount > 0) downloadCount.toString() else null,
                onClick = { onSelect(Tab.DOWNLOADS) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.Add,
                title = "Plugins",
                subtitle = "Built-in features you can switch on and off",
                badge = if (pluginCount > 0) pluginCount.toString() else null,
                onClick = { onSelect(Tab.PLUGINS) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.Description,
                title = "Guides",
                subtitle = "How to write a plugin, the tutorial, and what each file type does",
                badge = null,
                onClick = { onSelect(Tab.DOCS) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.Tune,
                title = "System",
                subtitle = if (updateWaiting) {
                    "A newer PyCmd is out - and storage, versions and housekeeping"
                } else {
                    "Storage, versions, what is running, and the housekeeping buttons"
                },
                badge = if (updateWaiting) "1" else null,
                onClick = { onSelect(Tab.SYSTEM) },
            )
        }
        item {
            DestinationRow(
                icon = PyIcons.BugReport,
                title = "Debug console",
                subtitle = "Errors, server events and everything else the app did",
                badge = if (errorCount > 0) errorCount.toString() else null,
                destructiveBadge = errorCount > 0,
                onClick = { onSelect(Tab.DEBUG) },
            )
        }

        if (pluginTabs.isNotEmpty()) {
            item {
                Spacer(Modifier.height(4.dp))
                SectionTitle("From your plugins")
            }
            items(pluginTabs, key = { it.id }) { plugin ->
                PluginTabRow(plugin) { onOpenPluginTab(plugin) }
            }
        }

        if (serverCount > 0) {
            item {
                Spacer(Modifier.height(4.dp))
                PyCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            PyIcons.Dns,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.width(10.dp))
                        Text(
                            "$serverCount server${if (serverCount == 1) "" else "s"} running",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }
}

/**
 * A destination a plugin published.
 *
 * The icon is a file the plugin ships, decoded from its own folder: an author
 * writing a plugin cannot add a drawable to this app, so the picture has to
 * come from their side of the line. A plugin with no usable image still gets
 * a row - a missing icon is not a reason to hide the tab.
 */
@Composable
private fun PluginTabRow(plugin: InstalledPlugin, onClick: () -> Unit) {
    val image = pluginImage(plugin.tabImage)

    PyCard(contentPadding = PaddingValues(0.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (image != null) {
                Image(
                    bitmap = image,
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.size(24.dp).clip(RoundedCornerShape(6.dp)),
                )
            } else {
                Icon(
                    PyIcons.Add,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.tertiary,
                    modifier = Modifier.size(22.dp),
                )
            }
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    plugin.tabTitle ?: plugin.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    plugin.tabDescription.ifBlank { plugin.description }.ifBlank { plugin.name },
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
            }
            StatusChip("plugin", MaterialTheme.colorScheme.tertiary)
        }
    }
}

@Composable
private fun DestinationRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    badge: String?,
    onClick: () -> Unit,
    destructiveBadge: Boolean = false,
) {
    PyCard(contentPadding = PaddingValues(0.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.size(22.dp),
            )
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (badge != null) {
                StatusChip(
                    badge,
                    if (destructiveBadge) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
                )
            }
        }
    }
}
