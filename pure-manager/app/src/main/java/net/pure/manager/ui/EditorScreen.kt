package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.pure.manager.edit.Buffer
import net.pure.manager.edit.EditIO
import net.pure.manager.edit.FindBar
import net.pure.manager.edit.Language
import net.pure.manager.edit.MAX_HIGHLIGHT
import net.pure.manager.edit.TokenKind
import net.pure.manager.edit.autoCloseFor
import net.pure.manager.edit.dedentRange
import net.pure.manager.edit.deletesPair
import net.pure.manager.edit.findAllIn
import net.pure.manager.edit.highlight
import net.pure.manager.edit.lineColumn
import net.pure.manager.edit.newlineInsertion
import net.pure.manager.edit.nextMatchIndex
import net.pure.manager.edit.replaceAll
import net.pure.manager.edit.sortedSpans
import net.pure.manager.fs.FileEntry
import net.pure.manager.theme.PureThemeSpec

/**
 * Editing a text file in place.
 *
 * The owner asked for a code editor, and the honest version of that on a phone is
 * this: a real text field with syntax colouring, auto-indent, bracket pairing,
 * undo/redo, find and replace, and save that writes back to the same file. Not VS
 * Code -- no autocomplete, no project index, no git -- and the screen says so at the
 * bottom instead of letting the owner discover it.
 *
 * The behaviour worth testing lives in `edit/` as plain Kotlin: [Buffer] for undo,
 * `highlight` for colouring, `findAllIn` for search. This file wires them to a
 * [BasicTextField], because a composable cannot be executed in this sandbox.
 */
@Composable
fun EditorScreen(
    spec: PureThemeSpec,
    entry: FileEntry,
    onClose: () -> Unit,
    // Not `= {}`: a lambda with no parameter list only satisfies `() -> Unit`, and
    // the compiler rejects it for a callback that takes a String.
    onSaved: (String) -> Unit = { _ -> },
    /** Shown when the caller already knows the file is unreadable. */
    initialError: String? = null,
) {
    val p = spec.palette
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val language = remember(entry.name) { Language.forFileName(entry.name) }

    var loaded by remember { mutableStateOf<EditIO.Loaded?>(null) }
    var error by remember { mutableStateOf<String?>(initialError) }
    var busy by remember { mutableStateOf(true) }
    var value by remember { mutableStateOf(TextFieldValue("")) }
    var dirty by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var showFind by remember { mutableStateOf(false) }
    var findQuery by remember { mutableStateOf("") }
    var replaceWith by remember { mutableStateOf("") }
    var showReplace by remember { mutableStateOf(false) }
    var currentMatch by remember { mutableStateOf(-1) }

    // The undo history is a plain object rather than Compose state: it is a stack of
    // edits, and recomposing on every push is work for nothing. The two booleans the
    // buttons need are mirrored into state so they enable and disable.
    val buffer = remember(entry.path) { Buffer() }
    var canUndo by remember { mutableStateOf(false) }
    var canRedo by remember { mutableStateOf(false) }

    fun refreshHistory() {
        canUndo = buffer.canUndo
        canRedo = buffer.canRedo
    }

    /** Applies one edit to both the buffer and the field, then refreshes the buttons. */
    fun edit(start: Int, end: Int, inserted: String, typed: Boolean) {
        val caret = buffer.replace(start, end, inserted, caretBefore = start, typed = typed)
        value = TextFieldValue(buffer.text, selection = TextRange(caret.coerceIn(0, buffer.length)))
        dirty = true
        refreshHistory()
    }

    LaunchedEffect(entry.path) {
        busy = true
        try {
            val result = withContext(Dispatchers.IO) { EditIO.read(context, entry.path) }
            buffer.load(result.text)
            loaded = result
            value = TextFieldValue(result.text, selection = TextRange(0))
            error = null
        } catch (e: EditIO.NotText) {
            error = e.message
        } catch (e: IOException) {
            error = e.message ?: "Berkas tidak bisa dibaca"
        } catch (e: SecurityException) {
            error = "Aplikasi tidak diizinkan membaca berkas ini"
        } finally {
            busy = false
            refreshHistory()
        }
    }

    val found = remember(value.text, findQuery) {
        if (findQuery.isEmpty()) emptyList() else findAllIn(value.text, findQuery)
    }

    fun jump(forward: Boolean) {
        val idx = nextMatchIndex(found, value.selection.start, forward, currentMatch)
        currentMatch = idx
        if (idx >= 0) {
            val m = found[idx]
            value = value.copy(selection = TextRange(m.start, m.end))
        }
    }

    Column(Modifier.fillMaxSize().padding(horizontal = spec.contentPaddingDp.dp)) {
        // ------------------------------------------------------------- header
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "\u2039 Kembali",
                style = MaterialTheme.typography.bodyLarge,
                color = p.accent,
                modifier = Modifier
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable {
                        if (dirty) message = "Ada perubahan yang belum disimpan"
                        else onClose()
                    }
                    .padding(horizontal = 8.dp, vertical = 6.dp),
            )
            Spacer(Modifier.width(4.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    entry.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = p.onBackground,
                    maxLines = 1,
                )
                Text(
                    subtitle(busy, error, dirty, language, loaded),
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                    maxLines = 1,
                )
            }
            ToolbarText(
                if (dirty) "Simpan" else "Tersimpan",
                enabled = dirty && !busy && error == null,
            ) {
                val snapshot = loaded ?: return@ToolbarText
                scope.launch {
                    val result = withContext(Dispatchers.IO) {
                        runCatching {
                            EditIO.write(
                                context, entry.path, buffer.text,
                                snapshot.encoding, snapshot.lineEnding,
                            )
                        }
                    }
                    if (result.isSuccess) {
                        dirty = false
                        message = "Tersimpan"
                        onSaved(entry.path)
                    } else {
                        message = result.exceptionOrNull()?.message ?: "Gagal menyimpan"
                    }
                }
            }
        }

        Spacer(Modifier.height(6.dp))

        // --------------------------------------------------------- tool row
        Row(
            Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ToolbarText("Undo", enabled = canUndo) {
                buffer.undo()?.let { caret ->
                    value = TextFieldValue(buffer.text, selection = TextRange(caret))
                    dirty = true
                    refreshHistory()
                }
            }
            ToolbarText("Redo", enabled = canRedo) {
                buffer.redo()?.let { caret ->
                    value = TextFieldValue(buffer.text, selection = TextRange(caret))
                    dirty = true
                    refreshHistory()
                }
            }
            ToolbarText("Cari", enabled = true) {
                showFind = !showFind
                if (!showFind) {
                    findQuery = ""
                    currentMatch = -1
                }
            }
            ToolbarText("Simpan sebagai\u2026", enabled = true) {
                message = "Belum ada: Simpan menulis ke berkas ini sendiri"
            }
        }

        if (showFind) {
            FindRow(
                spec = spec,
                query = findQuery,
                onQuery = {
                    findQuery = it
                    currentMatch = -1
                },
                showReplace = showReplace,
                replaceWith = replaceWith,
                onReplaceWith = { replaceWith = it },
                matchCount = found.size,
                current = currentMatch,
                onPrev = { jump(false) },
                onNext = { jump(true) },
                onToggleReplace = { showReplace = !showReplace },
                onReplaceOne = {
                    if (currentMatch in found.indices) {
                        val m = found[currentMatch]
                        edit(m.start, m.end, replaceWith, typed = false)
                        currentMatch = -1
                    }
                },
                onReplaceAll = {
                    val count = found.size
                    if (count > 0) {
                        val caret = value.selection.start
                        val next = replaceAll(buffer.text, findQuery, replaceWith)
                        buffer.load(next)
                        value = TextFieldValue(next, selection = TextRange(caret.coerceIn(0, next.length)))
                        dirty = true
                        refreshHistory()
                        currentMatch = -1
                        message = "$count penggantian"
                    }
                },
            )
        }

        Spacer(Modifier.height(6.dp))

        // -------------------------------------------------------------- body
        when {
            busy -> Box(Modifier.fillMaxWidth().padding(vertical = 40.dp), Alignment.Center) {
                Text("Membuka\u2026", style = MaterialTheme.typography.bodyMedium, color = p.onSurfaceVariant)
            }

            error != null -> MessageCard(
                spec = spec,
                title = "Tidak bisa diedit",
                body = error!! + "\n\nBuka dengan aplikasi lain lewat panjang-tekan \u2192 Buka.",
            )

            else -> {
                // Colouring is a VisualTransformation: the field owns the text, the
                // caret and the selection, and the transformation only decides how
                // each character is painted. Drawing a coloured copy behind an
                // invisible field was the other option and it desynchronises the
                // moment the two wrap differently.
                val transform = remember(language, spec) { SyntaxColour(spec, language) }
                BasicTextField(
                    value = value,
                    onValueChange = { next ->
                        val old = value.text
                        if (next.text != old) applyChange(old, next, buffer, ::edit)
                        value = next
                        dirty = true
                        refreshHistory()
                    },
                    textStyle = MaterialTheme.typography.bodyMedium.copy(
                        fontFamily = FontFamily.Monospace,
                        color = p.onBackground,
                    ),
                    cursorBrush = androidx.compose.ui.graphics.SolidColor(p.accent),
                    visualTransformation = transform,
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .clip(RoundedCornerShape(spec.cornerDp.dp))
                        .background(p.surface)
                        .padding(10.dp)
                        .verticalScroll(rememberScrollState()),
                )
            }
        }

        // ------------------------------------------------------------- footer
        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            val (line, col) = lineColumn(value.text, value.selection.start)
            Text(
                "$line:$col",
                style = MaterialTheme.typography.labelSmall,
                fontFamily = FontFamily.Monospace,
                color = p.onSurfaceVariant,
            )
            Spacer(Modifier.width(10.dp))
            Text(
                message ?: if (dirty) "Belum disimpan" else "Tersimpan",
                style = MaterialTheme.typography.labelSmall,
                color = if (message == null && dirty) p.onSurfaceVariant else p.accent,
                maxLines = 1,
            )
        }
    }
}

/**
 * Computes what the buffer should record for a change the text field just made.
 *
 * A [BasicTextField] hands over the whole new string, not the delta, so the delta has
 * to be recovered: common prefix, common suffix, and the span between them. This is
 * the one place in the screen that could corrupt an undo step, so it is a named
 * function with its own rules rather than inline arithmetic -- and it is what decides
 * whether a change counts as one typed character (mergeable) or a paste (not).
 */
internal fun applyChange(
    old: String,
    next: TextFieldValue,
    buffer: Buffer,
    edit: (Int, Int, String, Boolean) -> Unit,
) {
    val new = next.text
    val max = minOf(old.length, new.length)
    var prefix = 0
    while (prefix < max && old[prefix] == new[prefix]) prefix++
    var suffix = 0
    while (suffix < max - prefix && old[old.length - 1 - suffix] == new[new.length - 1 - suffix]) suffix++

    val start = prefix
    val oldEnd = old.length - suffix
    val inserted = new.substring(prefix, new.length - suffix)

    // Enter: replace the typed newline with an auto-indented one.
    if (inserted == "\n" && oldEnd == start) {
        val indent = newlineInsertion(old, start)
        if (indent != "\n") {
            edit(start, start, indent, false)
            return
        }
    }

    // Backspace inside an empty pair: remove both halves.
    if (inserted.isEmpty() && oldEnd - start == 1 && deletesPair(old, oldEnd)) {
        edit(start, start + 1, "", false)
        return
    }

    // Backspace on an otherwise blank indented line: go up one level.
    if (inserted.isEmpty() && oldEnd - start == 1 && old[start] in " \t") {
        val range = dedentRange(old, start)
        if (range != null && range.last == start - 1) {
            edit(range.first, range.last + 1, "", false)
            return
        }
    }

    // Typing a bracket or a quote: add its partner.
    if (inserted.length == 1 && oldEnd == start) {
        val auto = autoCloseFor(old, start, inserted[0])
        if (auto != null) {
            edit(start, start, auto.first, false)
            return
        }
    }

    edit(start, oldEnd, inserted, inserted.length == 1 && oldEnd == start)
}

/**
 * Paints the text with syntax colours without touching the text itself.
 *
 * A transformation may change how the text looks but not what it contains, so the
 * selection offsets the field keeps stay valid. Above [MAX_HIGHLIGHT] it returns the
 * text unstyled rather than styled halfway: a colour run that stops mid-file reads as
 * a corrupted document.
 */
internal class SyntaxColour(
    private val spec: PureThemeSpec,
    private val language: Language,
) : VisualTransformation {
    override fun filter(text: AnnotatedString): TransformedText {
        if (text.length > MAX_HIGHLIGHT || language == Language.PLAIN) return TransformedText(text, OffsetMapping.Identity)
        val spans = sortedSpans(highlight(text.text, language))
        val styled = buildAnnotatedString {
            append(text.text)
            for (s in spans) addStyle(SpanStyle(color = colourFor(s.kind, spec)), s.start, s.end)
        }
        return TransformedText(styled, OffsetMapping.Identity)
    }

    /** Identity mapping: nothing is added or removed, so offsets are unchanged. */
    private object OffsetMapping : androidx.compose.ui.text.input.OffsetMapping {
        override fun originalToTransformed(offset: Int): Int = offset
        override fun transformedToOriginal(offset: Int): Int = offset
    }
}

private fun subtitle(
    busy: Boolean,
    error: String?,
    dirty: Boolean,
    language: Language,
    loaded: EditIO.Loaded?,
): String = when {
    busy -> "Membuka\u2026"
    error != null -> error
    else -> buildString {
        append(language.label)
        append(" \u00b7 ")
        append(loaded?.encoding?.label ?: "UTF-8")
        if (loaded?.lineEnding == EditIO.LineEnding.CRLF) append(" \u00b7 CRLF")
        if (dirty) append(" \u00b7 belum disimpan")
    }
}

/** Colours come from the palette, so every theme gets a readable set. */
internal fun colourFor(kind: TokenKind, spec: PureThemeSpec): Color {
    val p = spec.palette
    return when (kind) {
        TokenKind.PLAIN -> p.onBackground
        TokenKind.KEYWORD -> p.accent
        TokenKind.STRING -> blend(p.onBackground, p.accent, 0.3f)
        TokenKind.COMMENT -> p.onSurfaceVariant
        TokenKind.NUMBER -> blend(p.accent, p.onBackground, 0.35f)
    }
}

/** Mixes two colours; kept here so the editor carries no colour constants of its own. */
private fun blend(a: Color, b: Color, t: Float): Color = Color(
    red = a.red * (1 - t) + b.red * t,
    green = a.green * (1 - t) + b.green * t,
    blue = a.blue * (1 - t) + b.blue * t,
    alpha = 1f,
)

@Composable
private fun ToolbarText(label: String, enabled: Boolean, onClick: () -> Unit) {
    val spec = net.pure.manager.theme.LocalPureSpec.current
    val p = spec.palette
    Text(
        label,
        style = MaterialTheme.typography.labelMedium,
        color = if (enabled) p.accent else p.onSurfaceVariant.copy(alpha = 0.5f),
        modifier = Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(if (enabled) p.surfaceVariant else Color.Transparent)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 6.dp),
    )
}

@Composable
private fun FindRow(
    spec: PureThemeSpec,
    query: String,
    onQuery: (String) -> Unit,
    showReplace: Boolean,
    replaceWith: String,
    onReplaceWith: (String) -> Unit,
    matchCount: Int,
    current: Int,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onToggleReplace: () -> Unit,
    onReplaceOne: () -> Unit,
    onReplaceAll: () -> Unit,
) {
    val p = spec.palette
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(p.surfaceVariant)
            .padding(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            FindField(spec, query, "Cari di berkas", Modifier.weight(1f), onQuery)
            Spacer(Modifier.width(6.dp))
            Text(
                if (matchCount == 0) "0" else "${current + 1}/$matchCount",
                style = MaterialTheme.typography.labelSmall,
                color = p.onSurfaceVariant,
            )
            Spacer(Modifier.width(6.dp))
            ToolbarText("\u2191", enabled = matchCount > 0, onClick = onPrev)
            ToolbarText("\u2193", enabled = matchCount > 0, onClick = onNext)
            ToolbarText(if (showReplace) "Ganti \u2212" else "Ganti +", enabled = true, onClick = onToggleReplace)
        }
        if (showReplace) {
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                FindField(spec, replaceWith, "Ganti dengan", Modifier.weight(1f), onReplaceWith)
                Spacer(Modifier.width(6.dp))
                ToolbarText("Ganti", enabled = matchCount > 0, onClick = onReplaceOne)
                ToolbarText("Semua", enabled = matchCount > 0, onClick = onReplaceAll)
            }
        }
        if (matchCount >= FindBar.WARN_ABOVE) {
            Spacer(Modifier.height(4.dp))
            Text(
                "$matchCount cocok. Mengganti semuanya bisa terasa lambat di berkas sebesar ini.",
                style = MaterialTheme.typography.labelSmall,
                color = p.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun FindField(
    spec: PureThemeSpec,
    value: String,
    hint: String,
    inputModifier: Modifier = Modifier,
    onValue: (String) -> Unit,
) {
    val p = spec.palette
    BasicTextField(
        value = value,
        onValueChange = onValue,
        singleLine = true,
        textStyle = MaterialTheme.typography.bodyMedium.copy(color = p.onBackground),
        cursorBrush = androidx.compose.ui.graphics.SolidColor(p.accent),
        modifier = inputModifier
            .clip(RoundedCornerShape(8.dp))
            .background(p.surface)
            .padding(horizontal = 8.dp, vertical = 6.dp),
        decorationBox = { inner ->
            Box {
                if (value.isEmpty()) {
                    Text(hint, style = MaterialTheme.typography.bodyMedium, color = p.onSurfaceVariant)
                }
                inner()
            }
        },
    )
}
