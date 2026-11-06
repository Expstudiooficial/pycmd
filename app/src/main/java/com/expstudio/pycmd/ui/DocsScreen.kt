package com.expstudio.pycmd.ui

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
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.plugins.InstalledPlugin
import com.expstudio.pycmd.plugins.PluginGuide
import com.expstudio.pycmd.python.LanguageInfo

/** One document that ships inside the APK. */
private data class Doc(
    val asset: String,
    val title: String,
    val summary: String,
)

private val DOCS = listOf(
    Doc(
        "docs/PLUGINS.md",
        "Writing a plugin",
        "The format, the API, the events, the panel bridge, four working " +
            "plugins, and a prompt to hand an AI.",
    ),
    Doc(
        "docs/BUILTINS.md",
        "The plugins that ship with it",
        "What every built-in switch and bundled plugin does, and the difference " +
            "between the two.",
    ),
    Doc(
        "docs/TUTORIAL.md",
        "Tutorial",
        "A walk through every tab with code to paste in and try.",
    ),
    Doc(
        "docs/README.md",
        "About this app",
        "What it is, what it can and cannot do, and how it is built.",
    ),
    Doc(
        "docs/EMULATOR.md",
        "Running it on a computer",
        "Which Android emulator image to use, the one flag that makes it fast, " +
            "and what to do when it is not.",
    ),
    Doc(
        "docs/FORKING.md",
        "Forking PyCmd",
        "How this is put together, how to build it, and how to publish updates " +
            "for a fork of your own.",
    ),
)

/**
 * The manuals, on the phone.
 *
 * The same files that are on GitHub, copied into the APK at build time, so
 * that reading how something works does not require another device.
 */
@Composable
fun DocsScreen(
    languages: List<LanguageInfo>,
    onOpen: (String, String) -> Unit,
    onDownloadSource: () -> Unit,
    modifier: Modifier = Modifier,
    sourceBusy: Boolean = false,
    /** Guides published by plugins that are switched on. */
    pluginGuides: List<Pair<InstalledPlugin, PluginGuide>> = emptyList(),
    onOpenPluginGuide: (InstalledPlugin, PluginGuide) -> Unit = { _, _ -> },
    /** Sections plugins have added to this screen; empty when none are on. */
    pluginSections: @Composable () -> Unit = {},
) {
    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionTitle("Guides") }

        DOCS.forEach { doc ->
            item(key = doc.asset) {
                PyCard(contentPadding = PaddingValues(0.dp)) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable { onOpen(doc.asset, doc.title) }
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            PyIcons.Description,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.secondary,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                doc.title,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Medium,
                            )
                            Text(
                                doc.summary,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }

        if (pluginGuides.isNotEmpty()) {
            item {
                Spacer(Modifier.height(6.dp))
                SectionTitle("From your plugins")
            }
            items(pluginGuides, key = { (plugin, guide) -> "${plugin.id}:${guide.file}" }) {
                (plugin, guide) ->
                PyCard(contentPadding = PaddingValues(0.dp)) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable { onOpenPluginGuide(plugin, guide) }
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            PyIcons.Description,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.tertiary,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                guide.title,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Medium,
                            )
                            Text(
                                guide.summary.ifBlank { "From ${plugin.name}" },
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                            )
                        }
                        StatusChip("plugin", MaterialTheme.colorScheme.tertiary)
                    }
                }
            }
        }

        item { pluginSections() }

        item {
            Spacer(Modifier.height(6.dp))
            SectionTitle("What each file type does here")
        }

        val runnable = languages.filter { it.canRun }
        val previewable = languages.filter { it.canPreview }
        val editable = languages.filterNot { it.canRun || it.canPreview }

        item {
            PyCard {
                LanguageLine("Runs on the device", runnable.joinToString(", ") { it.name },
                             MaterialTheme.colorScheme.primary)
                Spacer(Modifier.height(8.dp))
                LanguageLine("Previews", previewable.joinToString(", ") { it.name },
                             MaterialTheme.colorScheme.secondary)
                Spacer(Modifier.height(8.dp))
                LanguageLine("Edit, highlight and serve", editable.joinToString(", ") { it.name },
                             MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }

        item {
            Spacer(Modifier.height(6.dp))
            SectionTitle("Take the source")
            PyCard {
                Text(
                    "Forks are welcome, and this is the whole starting kit: the " +
                        "repository as a zip, straight onto this phone. It lands in " +
                        "Downloads, where Save to device puts it somewhere your file " +
                        "manager can see.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                if (sourceBusy) {
                    BusyRow("Fetching the source...")
                } else {
                    GhostButton(
                        "Download the source",
                        PyIcons.Download,
                        onDownloadSource,
                        Modifier.fillMaxWidth(),
                    )
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Keep PyCmd's name and credit where they are, and do not claim " +
                        "the original is a copy of your fork. Read \"Forking PyCmd\" " +
                        "above for the rest.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        items(runnable.filter { it.note.isNotEmpty() }.size) { index ->
            val language = runnable.filter { it.note.isNotEmpty() }[index]
            PyCard {
                Text(
                    language.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    language.note,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun LanguageLine(label: String, names: String, colour: androidx.compose.ui.graphics.Color) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = colour)
        Spacer(Modifier.height(2.dp))
        Text(
            names.ifEmpty { "—" },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
