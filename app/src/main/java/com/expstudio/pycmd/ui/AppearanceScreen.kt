package com.expstudio.pycmd.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.expstudio.pycmd.util.Branding

/**
 * The screen where the app's looks are chosen.
 *
 * Everything here applies the moment it is touched. There is no Save and no
 * preview pane, because the app *is* the preview - a theme you have to commit
 * to before you can see it is a theme nobody tries.
 */
@Composable
fun AppearanceScreen(modifier: Modifier = Modifier) {
    val appearance = LocalAppearance.current
    val chosen = appearance.theme

    // Which custom theme has its colour list open. One at a time: twenty hex
    // fields is enough of a wall without two sets of them.
    var editing by remember { mutableStateOf("") }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { SectionTitle("Theme") }
        item {
            Text(
                "Tap one to wear it. The console, the editor and every plugin " +
                    "panel change with the rest of the app.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
            )
        }

        items(Themes.BUILT_IN, key = { it.id }) { theme ->
            ThemeCard(
                theme = theme,
                chosen = theme.id == chosen.id,
                onPick = { appearance.choose(theme.id) },
                onFork = { appearance.forkTheme(theme) },
            )
        }

        val mine = appearance.themes.filter { it.custom }
        item {
            Spacer(Modifier.height(4.dp))
            SectionTitle("Your themes")
        }
        if (mine.isEmpty()) {
            item {
                PyCard {
                    Text(
                        "None yet. Open a theme above and press Copy to get an " +
                            "editable version of it - then change as many of its " +
                            "twenty colours as you like.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        } else {
            items(mine, key = { it.id }) { theme ->
                Column {
                    ThemeCard(
                        theme = theme,
                        chosen = theme.id == chosen.id,
                        onPick = { appearance.choose(theme.id) },
                        onFork = { appearance.forkTheme(theme) },
                        onEdit = { editing = if (editing == theme.id) "" else theme.id },
                        onDelete = { appearance.deleteCustom(theme.id) },
                        editing = editing == theme.id,
                    )
                    if (editing == theme.id) {
                        Spacer(Modifier.height(6.dp))
                        ColourEditor(theme) { appearance.updateCustom(it) }
                    }
                }
            }
        }

        item {
            Spacer(Modifier.height(4.dp))
            SectionTitle("Layout")
        }
        item {
            PyCard {
                SettingRow(
                    "Corners",
                    "${appearance.corner} dp" + if (appearance.corner == 0) "  ·  square" else "",
                )
                Slider(
                    value = appearance.corner.toFloat(),
                    onValueChange = { appearance.chooseCorner(it.toInt()) },
                    valueRange = 0f..28f,
                    steps = 13,
                )
                Spacer(Modifier.height(10.dp))
                SettingRow("Code text size", "${(appearance.textScale * 100).toInt()}%")
                Text(
                    "The console and the editor. The rest of the app follows " +
                        "Android's own text size.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Slider(
                    value = appearance.textScale,
                    onValueChange = { appearance.chooseTextScale(it) },
                    valueRange = 0.75f..1.75f,
                    steps = 7,
                )
                Spacer(Modifier.height(6.dp))
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("Short animations", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "Turns off the transitions in panels. Worth having on an " +
                                "emulator or an older phone, where they cost real frames.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(
                        checked = appearance.reducedMotion,
                        onCheckedChange = { appearance.chooseReducedMotion(it) },
                    )
                }
            }
        }

        item {
            Spacer(Modifier.height(4.dp))
            PyCard {
                Text(
                    "Back to how ${Branding.NAME} shipped",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    "Classic Green, 14 dp corners, 100% text, animations on. " +
                        "Your saved themes are left alone.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                GhostButton("Reset", PyIcons.RestartAlt, onClick = { appearance.reset() })
            }
        }
    }
}

@Composable
private fun SettingRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        Text(
            value,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = MonoFamily,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/**
 * One theme, as a row you can wear.
 *
 * The swatches are the point: a name and a sentence tell nobody what a theme
 * looks like, and six screenshots would be six screenshots out of date.
 */
@Composable
private fun ThemeCard(
    theme: PyTheme,
    chosen: Boolean,
    onPick: () -> Unit,
    onFork: () -> Unit,
    onEdit: (() -> Unit)? = null,
    onDelete: (() -> Unit)? = null,
    editing: Boolean = false,
) {
    val corner = LocalCorner.current
    PyCard(contentPadding = PaddingValues(0.dp)) {
        Column(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onPick)
                .padding(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // A little tile in the theme's own colours, which reads faster
                // than any amount of prose.
                Box(
                    Modifier
                        .size(44.dp)
                        .clip(RoundedCornerShape((corner - 4).coerceAtLeast(2).dp))
                        .background(Color(Hex.argb(theme.palette.bg)))
                        .border(
                            1.dp,
                            Color(Hex.argb(theme.palette.outline)),
                            RoundedCornerShape((corner - 4).coerceAtLeast(2).dp),
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        theme.glyph.ifEmpty { ">_" },
                        style = MaterialTheme.typography.labelLarge,
                        fontFamily = if (theme.glyph.isEmpty()) MonoFamily else null,
                        color = Color(Hex.argb(theme.palette.accent)),
                        textAlign = TextAlign.Center,
                    )
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        theme.name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                    )
                    Text(
                        theme.blurb,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                    )
                }
                if (chosen) {
                    Spacer(Modifier.width(8.dp))
                    StatusChip("on", MaterialTheme.colorScheme.primary)
                }
            }

            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (hex in listOf(
                    theme.palette.accent,
                    theme.palette.info,
                    theme.palette.warning,
                    theme.palette.danger,
                    theme.palette.kw,
                    theme.palette.fg,
                    theme.palette.surfaceHigh,
                )) {
                    Box(
                        Modifier
                            .size(20.dp)
                            .clip(CircleShape)
                            .background(Color(Hex.argb(hex)))
                            .border(1.dp, Color(Hex.argb(theme.palette.outline)), CircleShape),
                    )
                }
            }

            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                GhostButton(if (theme.custom) "Duplicate" else "Copy", PyIcons.ContentCopy, onClick = onFork)
                if (onEdit != null) {
                    Spacer(Modifier.width(4.dp))
                    GhostButton(if (editing) "Done" else "Colours", PyIcons.Palette, onClick = onEdit)
                }
                Spacer(Modifier.weight(1f))
                if (onDelete != null) {
                    GhostButton("Delete", PyIcons.Delete, destructive = true, onClick = onDelete)
                }
            }
        }
    }
}

/**
 * The twenty colours of a custom theme, each as a hex field.
 *
 * A field is only written back when what is in it parses, so typing over a
 * value does not blank the app out between the `#` and the six digits. The
 * swatch beside each field is the current value, not the field's text, for the
 * same reason.
 */
@Composable
private fun ColourEditor(theme: PyTheme, onChange: (PyTheme) -> Unit) {
    PyCard {
        Text(
            "Colours",
            style = MaterialTheme.typography.titleMedium,
        )
        Text(
            "Hex, with or without the #. Three digits work too (#0f0). " +
                "Anything that does not parse is ignored, so the app never " +
                "half-applies a colour you are still typing.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(10.dp))

        var name by remember(theme.id) { mutableStateOf(theme.name) }
        OutlinedTextField(
            value = name,
            onValueChange = {
                name = it.take(40)
                if (name.isNotBlank()) onChange(theme.copy(name = name.trim()))
            },
            label = { Text("Name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(4.dp))

        for ((field, label, help) in COLOUR_FIELDS) {
            val current = theme.palette.toMap()[field].orEmpty()
            ColourField(
                key = "${theme.id}:$field",
                label = label,
                help = help,
                value = current,
                onValue = { hex ->
                    onChange(theme.copy(palette = theme.palette.with(mapOf(field to hex))))
                },
            )
        }
    }
}

@Composable
private fun ColourField(
    key: String,
    label: String,
    help: String,
    value: String,
    onValue: (String) -> Unit,
) {
    // Keyed on the field, not on its value.
    //
    // Keyed on the value, a six-digit hex was impossible to type: `#ff0` is a
    // valid three-digit shorthand, so it was committed as #FFFF00, the key
    // changed, the field was rewritten with that, and the next three
    // characters landed on the end of it. The field now keeps what was typed
    // and the swatch shows what was committed.
    var text by remember(key) { mutableStateOf(value) }
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(30.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(Color(Hex.argb(value)))
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp)),
        )
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            Text(
                help,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(8.dp))
        OutlinedTextField(
            value = text,
            onValueChange = {
                text = it.take(9)
                Hex.tidy(text)?.let(onValue)
            },
            singleLine = true,
            textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = MonoFamily),
            modifier = Modifier.width(118.dp),
        )
    }
}

/**
 * Which colours are editable, in the order somebody would want to change them.
 *
 * Accent first, because it is the one everybody changes, and the twelve
 * chrome colours before the eight syntax ones.
 */
private val COLOUR_FIELDS: List<Triple<String, String, String>> = listOf(
    Triple("accent", "Accent", "Buttons, switches, the caret"),
    Triple("accentDim", "Accent, pressed", "The filled half of a slider"),
    Triple("onAccent", "On accent", "Text on top of an accent button"),
    Triple("bg", "Background", "Behind everything"),
    Triple("surface", "Cards", "The title bar and the bottom bar too"),
    Triple("surfaceHigh", "Raised", "A card on a card"),
    Triple("outline", "Lines", "Card edges and hairlines"),
    Triple("fg", "Text", "Body text"),
    Triple("muted", "Quiet text", "Labels and captions"),
    Triple("info", "Info", "Links and the console's own messages"),
    Triple("warning", "Warning", "\"Careful\""),
    Triple("danger", "Danger", "Errors, stderr, delete"),
    Triple("kw", "Keyword", "def, class, if"),
    Triple("builtin", "Built-in", "print, len, range"),
    Triple("str", "String", "Quoted text"),
    Triple("num", "Number", "Literals"),
    Triple("comment", "Comment", "The parts the computer skips"),
    Triple("def", "Name", "What a def or class is called"),
    Triple("self", "self", "And cls"),
    Triple("decorator", "Decorator", "@property and friends"),
)
