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
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.expstudio.pycmd.util.Branding
import com.expstudio.pycmd.util.ReleaseNote

/**
 * What changed, shown once after an update.
 *
 * A full-screen dialog rather than a tab, because it has one job and then it
 * is finished. It cannot be dismissed by tapping outside or by the back
 * button: the only way out is Read, which is what records that it has been
 * read. A changelog that can be swiped away by accident is a changelog that
 * comes back tomorrow and annoys somebody.
 */
@Composable
fun WhatsNewDialog(release: ReleaseNote, onRead: () -> Unit) {
    Dialog(
        onDismissRequest = { /* Read is the only way out; see above. */ },
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            dismissOnBackPress = false,
            dismissOnClickOutside = false,
        ),
    ) {
        // Read out here: the body of a LazyColumn is not a composable scope,
        // so a theme lookup inside it does not compile.
        val newColour = MaterialTheme.colorScheme.primary
        val fixedColour = MaterialTheme.colorScheme.secondary
        val goneColour = MaterialTheme.colorScheme.tertiary

        Surface(
            Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
        ) {
            Column(
                Modifier
                    .fillMaxSize()
                    .windowInsetsPadding(WindowInsets.systemBars),
            ) {
                LazyColumn(
                    Modifier.weight(1f),
                    contentPadding = PaddingValues(start = 14.dp, end = 14.dp, top = 14.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                Modifier
                                    .size(40.dp)
                                    .clip(CircleShape)
                                    .background(MaterialTheme.colorScheme.primary),
                                contentAlignment = Alignment.Center,
                            ) {
                                Icon(
                                    PyIcons.Star,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onPrimary,
                                    modifier = Modifier.size(22.dp),
                                )
                            }
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(
                                    "${Branding.NAME} ${release.versionName}",
                                    style = MaterialTheme.typography.titleLarge,
                                )
                                Text(
                                    "${release.total} change" +
                                        if (release.total == 1) "" else "s",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }

                    item {
                        PyCard {
                            Text(
                                release.headline,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Medium,
                            )
                        }
                    }

                    changeSection("New", release.added, newColour)
                    changeSection("Fixed", release.fixed, fixedColour)
                    changeSection("Gone", release.removed, goneColour)

                    item { Spacer(Modifier.height(4.dp)) }
                }

                // The one way out, pinned where a thumb is.
                Column(
                    Modifier
                        .fillMaxWidth()
                        .background(MaterialTheme.colorScheme.surface)
                        .padding(14.dp),
                ) {
                    ActionButton(
                        "Read",
                        PyIcons.PlayArrow,
                        onClick = onRead,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "This will not appear again until the next update. " +
                            "System has it if you want to read it twice.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

/**
 * One headed list of changes, or nothing at all when there were none.
 *
 * A heading with an empty list under it reads as a release where something was
 * meant to go and did not.
 */
private fun LazyListScope.changeSection(
    title: String,
    rows: List<String>,
    accent: Color,
) {
    if (rows.isEmpty()) return
    item(key = "head-$title") {
        Spacer(Modifier.height(4.dp))
        SectionTitle(title)
    }
    for ((index, text) in rows.withIndex()) {
        item(key = "$title-$index") {
            PyCard {
                Row {
                    Box(
                        Modifier
                            .padding(top = 6.dp)
                            .size(7.dp)
                            .clip(CircleShape)
                            .background(accent),
                    )
                    Spacer(Modifier.width(10.dp))
                    Text(
                        text,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}
