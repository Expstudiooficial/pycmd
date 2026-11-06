package com.expstudio.pycmd.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
/** One language's course, as the list shows it. */
data class TeachCourse(
    val id: String,
    val name: String,
    val blurb: String,
    val extension: String,
    /** "run" when the app marks written answers by running them. */
    val graded: String,
    val lessons: Int,
    val units: Int,
    val done: Int,
)

data class TeachTotals(
    val courses: Int = 0,
    val lessons: Int = 0,
    val done: Int = 0,
    val xp: Int = 0,
    val streak: Int = 0,
    val bestStreak: Int = 0,
    val todayDone: Boolean = false,
)

data class TeachHome(
    val loading: Boolean = true,
    val error: String = "",
    val courses: List<TeachCourse> = emptyList(),
    val totals: TeachTotals = TeachTotals(),
)

data class TeachLessonRef(val id: String, val kind: String, val title: String, val done: Boolean)

data class TeachUnit(val title: String, val goal: String, val lessons: List<TeachLessonRef>)

data class TeachCourseDetail(
    val id: String,
    val name: String,
    val blurb: String,
    val graded: String,
    val units: List<TeachUnit>,
    val total: Int,
    val done: Int,
)

data class TeachLesson(
    val course: String,
    val id: String,
    val kind: String,
    val title: String,
    val language: String,
    val extension: String,
    val teach: String,
    val code: String,
    val output: String,
    val note: String,
    val prompt: String,
    val graded: String,
    val options: List<String>,
    val lines: List<String>,
    val index: Int,
    val total: Int,
    val next: String,
    val previous: String,
    val done: Boolean,
)

data class TeachMark(
    val right: Boolean,
    val message: String,
    val expected: String,
    val output: String,
    /** True when the answer was marked by running it rather than by comparing it. */
    val ran: Boolean,
)

/**
 * PyCmdTeach: the courses.
 *
 * Three screens in one composable, chosen by which of the two "open" states is
 * set. A nav graph for three screens that always nest the same way would be
 * more machinery than the thing it organises.
 */
@Composable
fun TeachScreen(
    home: TeachHome,
    course: TeachCourseDetail?,
    lesson: TeachLesson?,
    mark: TeachMark?,
    busy: Boolean,
    onOpenCourse: (String) -> Unit,
    onCloseCourse: () -> Unit,
    onOpenLesson: (String, String) -> Unit,
    onCloseLesson: () -> Unit,
    onAnswer: (String) -> Unit,
    onNext: () -> Unit,
    onPrevious: () -> Unit,
    onReset: (String) -> Unit,
    onOpenSnippet: () -> Unit,
    modifier: Modifier = Modifier,
    pluginSections: @Composable () -> Unit = {},
) {
    when {
        lesson != null -> LessonPlayer(
            lesson = lesson,
            mark = mark,
            busy = busy,
            onAnswer = onAnswer,
            onNext = onNext,
            onPrevious = onPrevious,
            onClose = onCloseLesson,
            onOpenSnippet = onOpenSnippet,
            modifier = modifier,
        )

        course != null -> CourseScreen(
            course = course,
            onOpenLesson = { onOpenLesson(course.id, it) },
            onClose = onCloseCourse,
            onReset = { onReset(course.id) },
            modifier = modifier,
        )

        else -> CourseList(
            home = home,
            busy = busy,
            onOpenCourse = onOpenCourse,
            modifier = modifier,
            pluginSections = pluginSections,
        )
    }
}

// --------------------------------------------------------------- the courses

@Composable
private fun CourseList(
    home: TeachHome,
    busy: Boolean,
    onOpenCourse: (String) -> Unit,
    modifier: Modifier = Modifier,
    pluginSections: @Composable () -> Unit = {},
) {
    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            PyCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            "PyCmdTeach",
                            style = MaterialTheme.typography.titleLarge,
                        )
                        Text(
                            if (home.loading) {
                                "Loading the courses..."
                            } else {
                                "${home.totals.courses} languages  ·  " +
                                    "${home.totals.lessons} lessons  ·  free, and offline"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (home.totals.streak > 0) {
                        StatusChip(
                            "${home.totals.streak} day${if (home.totals.streak == 1) "" else "s"}",
                            MaterialTheme.colorScheme.primary,
                        )
                    }
                }
                if (home.totals.done > 0) {
                    Spacer(Modifier.height(12.dp))
                    LinearProgressIndicator(
                        progress = {
                            if (home.totals.lessons == 0) 0f
                            else home.totals.done.toFloat() / home.totals.lessons
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "${home.totals.done} done  ·  ${home.totals.xp} XP" +
                            if (home.totals.bestStreak > home.totals.streak) {
                                "  ·  best streak ${home.totals.bestStreak} days"
                            } else {
                                ""
                            },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        if (home.error.isNotEmpty()) {
            item {
                PyCard {
                    Text(
                        "The courses could not be read",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Text(
                        home.error,
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = MonoFamily,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        if (home.loading && home.courses.isEmpty()) {
            item { BusyRow("Reading the courses") }
        }

        if (home.courses.isNotEmpty()) {
            item { SectionTitle("Languages") }
        }

        items(home.courses, key = { it.id }) { course ->
            CourseRow(course) { onOpenCourse(course.id) }
        }

        if (home.courses.isNotEmpty()) {
            item {
                Spacer(Modifier.height(4.dp))
                PyCard {
                    Text(
                        "How this works",
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Each lesson is one idea, taught five ways: read it, " +
                            "predict what it prints, fill the gap, put the lines in " +
                            "order, then write it yourself.\n\n" +
                            "For Python, C, Rust and Go the last one is marked by " +
                            "actually running what you wrote, in the same " +
                            "interpreters the Console tab uses - so any program that " +
                            "gives the right answer is right. For the languages this " +
                            "phone cannot run, your answer is compared with the " +
                            "lesson's, and the lesson says so.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            item { pluginSections() }
        }
    }
}

@Composable
private fun CourseRow(course: TeachCourse, onClick: () -> Unit) {
    val done = course.done
    val fraction = if (course.lessons == 0) 0f else done.toFloat() / course.lessons
    PyCard(contentPadding = PaddingValues(0.dp)) {
        Column(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        course.name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        course.blurb,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    "$done/${course.lessons}",
                    style = MaterialTheme.typography.labelSmall,
                    fontFamily = MonoFamily,
                    color = if (done > 0) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }
            if (done > 0) {
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = { fraction },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

// ----------------------------------------------------------------- a course

@Composable
private fun CourseScreen(
    course: TeachCourseDetail,
    onOpenLesson: (String) -> Unit,
    onClose: () -> Unit,
    onReset: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // The first unfinished lesson, which is where "Continue" goes.
    val next = remember(course) {
        course.units.asSequence()
            .flatMap { it.lessons.asSequence() }
            .firstOrNull { !it.done }
    }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            PyCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(course.name, style = MaterialTheme.typography.titleLarge)
                        Text(
                            course.blurb,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                LinearProgressIndicator(
                    progress = {
                        if (course.total == 0) 0f else course.done.toFloat() / course.total
                    },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "${course.done} of ${course.total} lessons  ·  " +
                        "${course.units.size} units  ·  " +
                        if (course.graded == "run") {
                            "answers are run on the device"
                        } else {
                            "answers are checked against the lesson"
                        },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (next != null) {
                        ActionButton(
                            if (course.done == 0) "Start" else "Continue",
                            PyIcons.PlayArrow,
                            onClick = { onOpenLesson(next.id) },
                        )
                        Spacer(Modifier.width(8.dp))
                    }
                    GhostButton("Back", PyIcons.ArrowBack, onClick = onClose)
                    Spacer(Modifier.weight(1f))
                    if (course.done > 0) {
                        GhostButton(
                            "Reset",
                            PyIcons.RestartAlt,
                            onClick = onReset,
                            destructive = true,
                        )
                    }
                }
            }
        }

        course.units.forEachIndexed { index, unit ->
            item(key = "unit-$index") {
                Spacer(Modifier.height(4.dp))
                SectionTitle("${index + 1}. ${unit.title}")
                if (unit.goal.isNotEmpty()) {
                    Text(
                        unit.goal,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                    )
                }
            }
            items(unit.lessons, key = { "${index}-${it.id}" }) { row ->
                LessonRow(row) { onOpenLesson(row.id) }
            }
        }
    }
}

@Composable
private fun LessonRow(row: TeachLessonRef, onClick: () -> Unit) {
    PyCard(contentPadding = PaddingValues(0.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier
                    .size(22.dp)
                    .clip(CircleShape)
                    .background(
                        if (row.done) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.surfaceVariant
                        },
                    )
                    .border(1.dp, MaterialTheme.colorScheme.outline, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    if (row.done) "✓" else kindGlyph(row.kind),
                    style = MaterialTheme.typography.labelSmall,
                    color = if (row.done) {
                        MaterialTheme.colorScheme.onPrimary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                    textAlign = TextAlign.Center,
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    row.title,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                )
                Text(
                    kindName(row.kind),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private fun kindGlyph(kind: String): String = when (kind) {
    "read" -> "i"
    "predict" -> "?"
    "fill" -> "_"
    "order" -> "↕"
    else -> "✎"
}

private fun kindName(kind: String): String = when (kind) {
    "read" -> "Read it"
    "predict" -> "What does it print?"
    "fill" -> "Fill the gap"
    "order" -> "Put it in order"
    else -> "Write it yourself"
}

// ------------------------------------------------------------ one lesson

@Composable
private fun LessonPlayer(
    lesson: TeachLesson,
    mark: TeachMark?,
    busy: Boolean,
    onAnswer: (String) -> Unit,
    onNext: () -> Unit,
    onPrevious: () -> Unit,
    onClose: () -> Unit,
    onOpenSnippet: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // Everything the user has typed or tapped, reset when the lesson changes.
    var written by remember(lesson.id) { mutableStateOf("") }
    var picked by remember(lesson.id) { mutableStateOf<String?>(null) }
    var ordered by remember(lesson.id) { mutableStateOf(listOf<String>()) }
    var revealed by remember(lesson.id) { mutableStateOf(false) }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                GhostButton("Course", PyIcons.ArrowBack, onClick = onClose)
                Spacer(Modifier.weight(1f))
                Text(
                    "${lesson.index + 1} / ${lesson.total}",
                    style = MaterialTheme.typography.labelSmall,
                    fontFamily = MonoFamily,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = {
                    if (lesson.total == 0) 0f else (lesson.index + 1f) / lesson.total
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }

        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(lesson.title, style = MaterialTheme.typography.titleLarge)
                    Text(
                        "${lesson.language}  ·  ${kindName(lesson.kind)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (lesson.done) {
                    StatusChip("done", MaterialTheme.colorScheme.primary)
                }
            }
        }

        when (lesson.kind) {
            "read" -> {
                item {
                    PyCard {
                        Text(lesson.teach, style = MaterialTheme.typography.bodyLarge)
                        if (lesson.note.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            Text(
                                lesson.note,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                item { CodeBlock(lesson.code) }
                if (lesson.output.isNotEmpty()) {
                    item {
                        SectionTitle("It prints")
                        CodeBlock(lesson.output, accent = true)
                    }
                }
            }

            "predict" -> {
                item { Prompt(lesson.prompt) }
                item { CodeBlock(lesson.code) }
                itemsIndexed(lesson.options, key = { index, _ -> index }) { _, option ->
                    ChoiceRow(
                        text = option,
                        chosen = picked == option,
                        verdict = verdictFor(option, picked, mark),
                        mono = true,
                    ) {
                        if (mark?.right != true) {
                            picked = option
                            onAnswer(option)
                        }
                    }
                }
            }

            "fill" -> {
                item { Prompt(lesson.prompt) }
                item { CodeBlock(lesson.code) }
                itemsIndexed(lesson.options, key = { index, _ -> index }) { _, option ->
                    ChoiceRow(
                        text = option,
                        chosen = picked == option,
                        verdict = verdictFor(option, picked, mark),
                        mono = true,
                    ) {
                        if (mark?.right != true) {
                            picked = option
                            onAnswer(option)
                        }
                    }
                }
            }

            "order" -> {
                item { Prompt(lesson.prompt) }
                item {
                    PyCard {
                        Text(
                            "Your order",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(6.dp))
                        if (ordered.isEmpty()) {
                            Text(
                                "Tap the lines below, top line first.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        } else {
                            for ((position, line) in ordered.withIndex()) {
                                Row(
                                    Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            ordered = ordered.toMutableList()
                                                .also { it.removeAt(position) }
                                        }
                                        .padding(vertical = 3.dp),
                                ) {
                                    Text(
                                        "${position + 1}.",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = MonoFamily,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.width(26.dp),
                                    )
                                    Text(
                                        line,
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = MonoFamily,
                                    )
                                }
                            }
                        }
                        Spacer(Modifier.height(10.dp))
                        Row {
                            ActionButton(
                                "Check",
                                PyIcons.PlayArrow,
                                onClick = { onAnswer(ordered.joinToString("\n")) },
                                enabled = ordered.isNotEmpty() && !busy,
                            )
                            Spacer(Modifier.width(8.dp))
                            GhostButton(
                                "Clear",
                                PyIcons.Clear,
                                onClick = { ordered = emptyList() },
                                enabled = ordered.isNotEmpty(),
                            )
                        }
                    }
                }
                item { SectionTitle("The lines") }
                // Keyed by position, not by the line.
                //
                // The lines of a snippet are not unique: a class in any
                // brace language has several `}` lines, and 56 of the
                // generated ordering lessons repeat at least one line. A
                // LazyColumn whose key appears twice throws, so this used to
                // be a crash on every one of them.
                itemsIndexed(lesson.lines, key = { index, _ -> index }) { _, line ->
                    val used = ordered.count { it == line } >=
                        lesson.lines.count { it == line }
                    ChoiceRow(
                        text = line,
                        chosen = false,
                        verdict = null,
                        mono = true,
                        dim = used,
                    ) {
                        if (!used) ordered = ordered + line
                    }
                }
            }

            else -> {
                item { Prompt(lesson.prompt) }
                item {
                    PyCard {
                        Text(
                            if (lesson.graded == "run") {
                                "This is run on the device and marked on what it " +
                                    "prints, so any ${lesson.language} that gives the " +
                                    "right answer passes."
                            } else {
                                "This phone cannot run ${lesson.language}, so your " +
                                    "answer is compared with the lesson's - " +
                                    "whitespace is ignored."
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(10.dp))
                        OutlinedTextField(
                            value = written,
                            onValueChange = { written = it },
                            label = { Text("Your ${lesson.language}") },
                            textStyle = MaterialTheme.typography.bodyMedium
                                .copy(fontFamily = MonoFamily),
                            keyboardOptions = KeyboardOptions(
                                capitalization = KeyboardCapitalization.None,
                                autoCorrectEnabled = false,
                            ),
                            minLines = 4,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(10.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            ActionButton(
                                if (lesson.graded == "run") "Run it" else "Check",
                                PyIcons.PlayArrow,
                                onClick = { onAnswer(written) },
                                enabled = written.isNotBlank() && !busy,
                            )
                            Spacer(Modifier.width(8.dp))
                            GhostButton(
                                if (revealed) "Hide" else "Show me",
                                PyIcons.Info,
                                onClick = { revealed = !revealed },
                            )
                        }
                    }
                }
                if (revealed) {
                    item {
                        SectionTitle("One way to write it")
                        CodeBlock(lesson.code)
                    }
                }
            }
        }

        if (mark != null) {
            item {
                PyCard {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            if (mark.right) PyIcons.Star else PyIcons.Info,
                            contentDescription = null,
                            tint = if (mark.right) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.tertiary
                            },
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(
                            mark.message,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                    if (mark.output.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Your program printed",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(4.dp))
                        CodeBlock(mark.output.trimEnd())
                    }
                    if (!mark.right && mark.expected.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            if (mark.ran) "It should have printed" else "The answer",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(4.dp))
                        CodeBlock(mark.expected)
                    }
                }
            }
        }

        item {
            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (lesson.previous.isNotEmpty()) {
                    GhostButton("Back", PyIcons.ArrowBack, onClick = onPrevious)
                    Spacer(Modifier.width(8.dp))
                }
                if (lesson.kind == "read") {
                    ActionButton(
                        if (lesson.done) "Next" else "Got it",
                        PyIcons.PlayArrow,
                        onClick = {
                            if (lesson.done) onNext() else onAnswer("")
                        },
                        enabled = !busy,
                    )
                } else if (mark?.right == true || lesson.done) {
                    ActionButton("Next", PyIcons.PlayArrow, onClick = onNext, enabled = !busy)
                }
                Spacer(Modifier.weight(1f))
                if (lesson.code.isNotEmpty()) {
                    GhostButton("Editor", PyIcons.Edit, onClick = onOpenSnippet)
                }
            }
            if (mark?.right != true && !lesson.done && lesson.kind != "read") {
                Spacer(Modifier.height(8.dp))
                GhostButton("Skip for now", PyIcons.SkipNext, onClick = onNext)
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Prompt(text: String) {
    if (text.isEmpty()) return
    PyCard {
        Text(text, style = MaterialTheme.typography.bodyLarge)
    }
}

/**
 * A snippet, in the editor's own colours.
 *
 * Scrolls sideways rather than wrapping. A wrapped line of code on a phone is
 * a line somebody has to decode before they can read it, and the ordering
 * lessons would be unanswerable.
 */
@Composable
private fun CodeBlock(code: String, accent: Boolean = false) {
    val palette = LocalPalette.current
    val scroll = rememberScrollState()
    Box(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape((LocalCorner.current - 4).coerceAtLeast(2).dp))
            .background(MaterialTheme.colorScheme.background)
            .border(
                1.dp,
                if (accent) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.outline
                },
                RoundedCornerShape((LocalCorner.current - 4).coerceAtLeast(2).dp),
            )
            .horizontalScroll(scroll)
            .padding(12.dp),
    ) {
        Text(
            code,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = MonoFamily,
            color = if (accent) {
                androidx.compose.ui.graphics.Color(Hex.argb(palette.accent))
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
    }
}

/** Null until an answer has been marked; then true for right and false for wrong. */
private fun verdictFor(option: String, picked: String?, mark: TeachMark?): Boolean? {
    if (mark == null || picked == null) return null
    if (option == picked) return mark.right
    // Once the right answer is known, show it even if it was not the one tapped.
    if (!mark.right && option == mark.expected) return true
    return null
}

@Composable
private fun ChoiceRow(
    text: String,
    chosen: Boolean,
    verdict: Boolean?,
    mono: Boolean,
    dim: Boolean = false,
    onClick: () -> Unit,
) {
    val border = when (verdict) {
        true -> MaterialTheme.colorScheme.primary
        false -> MaterialTheme.colorScheme.error
        null -> if (chosen) {
            MaterialTheme.colorScheme.primary
        } else {
            MaterialTheme.colorScheme.outline
        }
    }
    PyCard(contentPadding = PaddingValues(0.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .border(
                    1.dp,
                    border,
                    RoundedCornerShape(LocalCorner.current.dp),
                )
                .clickable(enabled = !dim, onClick = onClick)
                .padding(horizontal = 13.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text,
                style = MaterialTheme.typography.bodyMedium,
                fontFamily = if (mono) MonoFamily else null,
                color = if (dim) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
                modifier = Modifier.weight(1f),
            )
            if (verdict == true) {
                Text("✓", style = MaterialTheme.typography.bodyMedium, color = border)
            } else if (verdict == false) {
                Text("✕", style = MaterialTheme.typography.bodyMedium, color = border)
            }
        }
    }
}
