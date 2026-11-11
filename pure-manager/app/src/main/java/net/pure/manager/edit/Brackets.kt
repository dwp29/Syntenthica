package net.pure.manager.edit

/**
 * Bracket matching and auto-closing.
 *
 * Small, but every editor that skips it feels wrong within a minute: typing `(` and
 * getting no `)`, then deleting one and having to delete both. The rules below are
 * the ones a phone keyboard forces -- there is no Shift key for `{`, so the editor
 * supplies the pairs.
 */

private val PAIRS = mapOf(
    '(' to ')',
    '[' to ']',
    '{' to '}',
    '"' to '"',
    '\'' to '\'',
    '`' to '`',
)

/** Auto-closing is offered for brackets only. Quotes have their own rules below. */
private val BRACKETS = setOf('(', '[', '{')

val OPENERS: Set<Char> = PAIRS.keys
val CLOSERS: Set<Char> = PAIRS.values.toSet()

/**
 * What to insert for one typed character: the text and the caret offset inside it.
 *
 * Null means "insert the character and put the caret after it", which is what plain
 * text editing does. Auto-closing is declined when it would fight the user:
 *
 *  - a quote after a letter is an apostrophe (`dont'` is not a string);
 *  - a bracket or quote the file already has at the caret is typed over, not
 *    doubled -- otherwise every closing bracket had to be typed twice.
 */
fun autoCloseFor(
    text: CharSequence,
    caret: Int,
    typed: Char,
    selectionLength: Int = 0,
): Pair<String, Int>? {
    val close = PAIRS[typed] ?: return null
    // Wrapping a selection is the one place an editor earns its keep on a phone:
    // select the text, press a quote, done, instead of deleting and retyping.
    if (selectionLength > 0) return typed.toString() + close to 1
    if (typed !in BRACKETS) {
        if (caret > 0 && caret <= text.length && text[caret - 1].isLetterOrDigit()) return null
        if (caret < text.length && text[caret] == typed) return null
        return typed.toString() + close to 1
    }
    if (caret < text.length && text[caret] == close) return null
    return typed.toString() + close to 1
}

/**
 * Whether Backspace at [caret] should delete both halves of an empty pair.
 *
 * True when the character before the caret is an opening bracket or a quote and the
 * character at the caret is its partner.
 */
fun deletesPair(text: CharSequence, caret: Int): Boolean {
    if (caret <= 0 || caret >= text.length) return false
    val open = text[caret - 1]
    val close = PAIRS[open] ?: return false
    return text[caret] == close
}

/**
 * The bracket paired with the one at [index], or null.
 *
 * The scan starts at the neighbour, never at the character itself: counting from
 * the character made every bracket match itself at depth zero, so `f(a` reported a
 * match at the `(` that had none.
 *
 * Text inside strings and comments is skipped, so a `)` inside `"..."` does not end
 * the paren before it. It is not a parser and does not try to be; it is right for the
 * code people actually open on a phone.
 */
fun matchingBracket(text: String, index: Int, language: Language = Language.PLAIN): Int? {
    if (index !in text.indices) return null
    val c = text[index]
    val open = c in PAIRS.keys && c in BRACKETS
    val close = c in PAIRS.values && c in BRACKETS
    if (!open && !close) return null
    val target = if (open) PAIRS[c]!! else c
    val step = if (open) 1 else -1
    val skip = language != Language.PLAIN && language != Language.PROPERTIES
    var depth = 0
    var i = index + step
    while (i in text.indices) {
        if (skip) {
            val jumped = skipStringOrComment(text, i, step, language)
            if (jumped != i) {
                // A region that ends past the current position is opaque. When
                // scanning backwards only its START is skipped, so a bracket that
                // sits before the comment is still seen.
                i = if (step > 0) jumped else i + step
                continue
            }
        }
        val ch = text[i]
        if (ch == c) depth++
        if (ch == target) {
            if (depth == 0) return i
            depth--
        }
        i += step
    }
    return null
}

/**
 * If a string or comment starts at [i], the index to jump to; otherwise [i].
 *
 * Only forward scanning can skip a region whole; backwards, the caller steps one
 * character at a time and only ignores the start of a comment or string. Treating a
 * region as opaque in both directions is what made a bracket before a comment look
 * unmatched when it was not.
 */
private fun skipStringOrComment(text: String, i: Int, step: Int, language: Language): Int {
    if (step < 0) return i
    val c = text[i]
    if (c == '"' || c == '\'' || (c == '`' && language == Language.JAVASCRIPT)) {
        // A quote preceded by a letter is prose or a contraction, not an opener.
        if (i > 0 && text[i - 1].isLetterOrDigit()) return i
        var j = i + 1
        while (j < text.length && text[j] != c && text[j] != '\n') {
            j += if (text[j] == '\\') 2 else 1
        }
        return j
    }
    if (c == '/' && i + 1 < text.length) {
        if (text[i + 1] == '/') {
            val nl = text.indexOf('\n', i)
            return if (nl < 0) text.length - 1 else nl
        }
        if (text[i + 1] == '*') {
            val close = text.indexOf("*/", i + 2)
            return if (close < 0) text.length - 1 else close + 1
        }
    }
    if (c == '#' && (language == Language.SHELL || language == Language.PYTHON)) {
        val nl = text.indexOf('\n', i)
        return if (nl < 0) text.length - 1 else nl
    }
    return i
}
