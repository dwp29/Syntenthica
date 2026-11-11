package net.pure.manager.edit

/**
 * The rules a text editor needs, as plain functions.
 *
 * No Android types here, for the same reason the sorting and name rules are plain:
 * this sandbox cannot run the app, so anything written inside a composable is
 * invisible to the tests. Editing is mostly arithmetic on character offsets, and
 * offset arithmetic is exactly the kind of code that looks right and is not.
 *
 * Every function takes and returns offsets into a text that is unchanged during
 * the call. The buffer itself lives in [Buffer].
 */

/**
 * One undo step: the span `start` until `start + removed.length` was replaced by
 * [inserted].
 *
 * [removed] is stored rather than recomputed, because at undo time the original
 * text is gone -- reading it back from the buffer is what makes a naive undo
 * paste the *new* text over itself and look like it did nothing.
 */
data class Edit(
    val start: Int,
    val removed: String,
    val inserted: String,
    /** Where the caret sat before the edit, so undo also restores position. */
    val caretBefore: Int,
    val caretAfter: Int,
    /**
     * True when this came from typing one character.
     *
     * Mergeability used to be decided by asking whether the previous step inserted
     * exactly one character. That is true of the first keystroke and false of the
     * merged step that follows it, so "kata" became two undo steps instead of one --
     * the run stopped merging as soon as merging had happened once.
     */
    val typed: Boolean = inserted.length == 1 && removed.isEmpty(),
) {
    val end: Int get() = start + removed.length
}

/**
 * A bounded undo history that merges consecutive typing into one step.
 *
 * Coalescing matters more than depth: typing a word is one undo, not nine. Two
 * edits merge when both are pure single-character insertions and the newer one
 * starts exactly where the older one ended. Anything else starts a new step --
 * deleting, typing after moving the caret, pasting.
 */
class History(private val limit: Int = 200) {
    private val done = ArrayDeque<Edit>()
    private val undone = ArrayDeque<Edit>()

    val canUndo: Boolean get() = done.isNotEmpty()
    val canRedo: Boolean get() = undone.isNotEmpty()
    val undoDepth: Int get() = done.size

    fun record(edit: Edit) {
        // Any new edit invalidates the redo trail. Keeping it would let Redo paste
        // text back into a document that has moved on.
        undone.clear()
        val last = done.lastOrNull()
        if (last != null && mergeable(last, edit)) {
            done.removeLast()
            done.addLast(
                last.copy(
                    inserted = last.inserted + edit.inserted,
                    caretAfter = edit.caretAfter,
                )
            )
        } else {
            done.addLast(edit)
            if (done.size > limit) done.removeFirst()
        }
    }

    /** The edit to reverse, or null. The caller applies it. */
    fun undo(): Edit? = done.removeLastOrNull()?.also { undone.addLast(it) }

    fun redo(): Edit? = undone.removeLastOrNull()?.also { done.addLast(it) }

    fun clear() {
        done.clear()
        undone.clear()
    }

    private fun mergeable(a: Edit, b: Edit): Boolean =
        a.typed && b.typed &&
            a.removed.isEmpty() && b.removed.isEmpty() &&
            b.start == a.start + a.inserted.length &&
            // Enter closes the word, so undoing a line does not eat the line before.
            !a.inserted.contains('\n') && !b.inserted.contains('\n')
}

/**
 * What gets inserted when Enter is pressed at [caret].
 *
 * Auto-indent carries the current line's leading whitespace, and inside a block
 * that ends in `{`, `(`, `[` or `:` it adds one more level. The level is two spaces
 * because that is what this project's own sources use; a tab is one keystroke but
 * renders differently in every other editor on the phone.
 *
 * Returns the text to insert (newline plus indentation); the caller splices it.
 */
fun newlineInsertion(text: CharSequence, caret: Int, indentUnit: String = "  "): String {
    val at = caret.coerceIn(0, text.length)
    val lineStart = lineStartOf(text, at)
    var leadEnd = lineStart
    while (leadEnd < at && (text[leadEnd] == ' ' || text[leadEnd] == '\t')) leadEnd++
    val lead = text.subSequence(lineStart, leadEnd).toString()
    val before = text.subSequence(lineStart, at).toString().trimEnd()
    val opensBlock = before.endsWith("{") || before.endsWith("(") ||
        before.endsWith("[") || before.endsWith(":")
    return "\n" + lead + if (opensBlock) indentUnit else ""
}

/**
 * The span one level of indentation occupies at the start of a line, or null when
 * the line is not indented (or is not blank before the caret).
 *
 * Backspace on an otherwise empty, indented line goes up a level instead of eating
 * one character at a time. That is what every code editor does, and its absence is
 * the first thing that feels broken when typing a block.
 */
fun dedentRange(text: CharSequence, caret: Int, indentUnit: String = "  "): IntRange? {
    val at = caret.coerceIn(0, text.length)
    val lineStart = lineStartOf(text, at)
    if (text.subSequence(lineStart, at).isNotEmpty() &&
        text.subSequence(lineStart, at).toString().isNotBlank()
    ) return null
    var end = lineStart
    while (end < text.length && (text[end] == ' ' || text[end] == '\t')) end++
    if (end == lineStart) return null
    val lead = text.subSequence(lineStart, end).toString()
    val remove = when {
        lead.startsWith("\t") -> 1
        lead.length <= indentUnit.length -> lead.length
        // Never remove more than one level, and never leave a partial level behind
        // as a floating half-indent.
        lead.endsWith(indentUnit) -> indentUnit.length
        else -> lead.length % indentUnit.length
    }
    return lineStart until lineStart + remove
}

/** Indent/outdent applied to a selection: a list of splices plus the new offsets. */
data class Block(val splices: List<Edit>, val caret: Int, val selectionEnd: Int)

/**
 * Tab with several lines selected indents all of them; Shift-Tab outdents.
 *
 * Returns null when nothing would change, so the caller can fall back to inserting
 * a single level at the caret. Splices are ordered bottom-up, which is the order
 * they must be applied in to keep every other offset valid.
 */
fun indentBlock(
    text: CharSequence,
    selectionStart: Int,
    selectionEnd: Int,
    outdent: Boolean,
    indentUnit: String = "  ",
): Block? {
    val from = minOf(selectionStart, selectionEnd).coerceIn(0, text.length)
    val to = maxOf(selectionStart, selectionEnd).coerceIn(0, text.length)
    if (from == to) return null
    val starts = mutableListOf(lineStartOf(text, from))
    var i = starts[0]
    while (i < to) {
        if (text[i] == '\n') starts.add(i + 1)
        i++
    }
    // A selection that ends exactly at a line start does not include that line.
    while (starts.size > 1 && starts.last() >= to) starts.removeAt(starts.size - 1)

    val splices = mutableListOf<Edit>()
    for (start in starts.sortedDescending()) {
        if (!outdent) {
            splices.add(Edit(start, "", indentUnit, start, start + indentUnit.length))
            continue
        }
        // Outdent looks at the line itself, not at the caret inside it.
        val r = dedentRange(text.subSequence(start, text.length), 0, indentUnit)
            ?: continue
        val a = start + r.first
        splices.add(Edit(a, text.subSequence(a, start + r.last + 1).toString(), "", a, a))
    }
    if (splices.isEmpty()) return null

    // Offsets shift by the net change of the splices above them. Splices are
    // bottom-up, so walk them in reverse to get the top-down order.
    fun shift(offset: Int, inclusive: Boolean): Int {
        var out = offset
        for (e in splices.asReversed()) {
            if (e.start < offset || (inclusive && e.start == offset)) {
                out += e.inserted.length - e.removed.length
            }
        }
        return out.coerceAtLeast(0)
    }
    return Block(splices, shift(from, inclusive = true), shift(to, inclusive = false))
}

private fun lineStartOf(text: CharSequence, caret: Int): Int =
    text.lastIndexOf('\n', caret - 1).let { if (it < 0) 0 else it + 1 }

/**
 * The editable text with its undo history.
 *
 * One object that touches the string means one place to get the offsets wrong and
 * one place a test can pin. Everything here is plain Kotlin so `TextTest` can run
 * it on the JVM during every build.
 */
class Buffer(initial: String = "") {
    var text: String = initial
        private set
    private val history = History()

    val canUndo: Boolean get() = history.canUndo
    val canRedo: Boolean get() = history.canRedo
    val undoDepth: Int get() = history.undoDepth
    val length: Int get() = text.length

    /** Applies an edit, records it, and returns where the caret should now sit. */
    fun replace(
        start: Int,
        end: Int,
        inserted: String,
        caretBefore: Int = start,
        /** A single character typed at the caret merges with the run before it. */
        typed: Boolean = false,
    ): Int {
        val a = start.coerceIn(0, text.length)
        val b = end.coerceIn(a, text.length)
        if (a == b && inserted.isEmpty()) return a
        val removed = text.substring(a, b)
        text = text.substring(0, a) + inserted + text.substring(b)
        val caretAfter = a + inserted.length
        history.record(
            Edit(
                start = a,
                removed = removed,
                inserted = inserted,
                caretBefore = caretBefore,
                caretAfter = caretAfter,
                typed = typed && removed.isEmpty() && inserted.length == 1,
            )
        )
        return caretAfter
    }

    /** Reverses the last edit and returns the caret it should have, or null. */
    /**
     * Replaces everything without recording a step.
     *
     * Opening a file is not something the user did, so it must not be undoable: the
     * first Undo after opening a document should do nothing, and the version that
     * loaded by calling [replace] and then undoing in a loop left the buffer empty
     * while the screen showed the file.
     */
    fun load(text: String) {
        this.text = text
        history.clear()
    }

    fun undo(): Int? {
        val e = history.undo() ?: return null
        text = text.substring(0, e.start) + e.removed + text.substring(e.start + e.inserted.length)
        return e.caretBefore.coerceIn(0, text.length)
    }

    /** Re-applies the last undone edit and returns the caret, or null. */
    fun redo(): Int? {
        val e = history.redo() ?: return null
        text = text.substring(0, e.start) + e.inserted + text.substring(e.start + e.removed.length)
        return e.caretAfter.coerceIn(0, text.length)
    }
}
