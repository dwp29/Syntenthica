package net.pure.manager.edit

/**
 * Find and replace inside the open file.
 *
 * Separate from `fs.Search`, which walks the file system. This one is arithmetic
 * over a string and nothing else, so it can be pinned by JVM tests -- which matters
 * because "replace all" that shifts its own offsets is the classic way to corrupt a
 * file.
 *
 * The lookups are named [findIn] and [findAllIn] rather than `find`: a package-level
 * `find` shadows the Kotlin stdlib's collection `find` inside this package, and the
 * mistake it causes -- a call that silently resolves to the wrong overload -- reads
 * as a wrong result, not as a compiler error.
 */

data class Found(val start: Int, val end: Int)

/**
 * Comparison is done with `regionMatches(ignoreCase = true)` rather than by
 * lowercasing both sides. Lowercasing is not length-preserving for every script
 * (Turkish dotted I, German sharp S), and a match offset computed in a lowercased
 * copy does not necessarily point at the same place in the original -- which then
 * deletes the wrong characters. Comparing in place cannot drift.
 */
fun findIn(
    text: String,
    needle: String,
    from: Int = 0,
    caseSensitive: Boolean = false,
    wholeWord: Boolean = false,
): Found? {
    if (needle.isEmpty()) return null
    var i = from.coerceIn(0, text.length)
    val last = text.length - needle.length
    while (i <= last) {
        if (text.regionMatches(i, needle, 0, needle.length, ignoreCase = !caseSensitive)) {
            if (!wholeWord || isWholeWord(text, i, i + needle.length)) {
                return Found(i, i + needle.length)
            }
            i++
        } else {
            i++
        }
    }
    return null
}

/** Every match, in order. Bounded so a one-letter search cannot build a huge list. */
fun findAllIn(
    text: String,
    needle: String,
    caseSensitive: Boolean = false,
    wholeWord: Boolean = false,
    limit: Int = 5_000,
): List<Found> {
    if (needle.isEmpty()) return emptyList()
    val out = mutableListOf<Found>()
    var at = 0
    while (out.size < limit) {
        val m = findIn(text, needle, at, caseSensitive, wholeWord) ?: break
        out.add(m)
        at = maxOf(m.end, m.start + 1)
    }
    return out
}

private fun isWholeWord(text: String, start: Int, end: Int): Boolean {
    val before = start == 0 || !text[start - 1].isLetterOrDigit() && text[start - 1] != '_'
    val after = end >= text.length || !text[end].isLetterOrDigit() && text[end] != '_'
    return before && after
}

/**
 * Replaces every match and returns the new text.
 *
 * Built in one pass over the matches instead of repeated `replaceFirst` on a
 * shrinking string, which is where "replace all" usually goes wrong. A replacement
 * may contain the needle (`a` -> `a-b`); because the scan continues after each
 * original match rather than re-reading the output, that terminates and terminates
 * in the right place.
 */
fun replaceAll(
    text: String,
    needle: String,
    replacement: String,
    caseSensitive: Boolean = false,
    wholeWord: Boolean = false,
): String {
    val matches = findAllIn(text, needle, caseSensitive, wholeWord, limit = Int.MAX_VALUE)
    if (matches.isEmpty()) return text
    val sb = StringBuilder(text.length + matches.size * (replacement.length - needle.length))
    var at = 0
    for (m in matches) {
        sb.append(text, at, m.start)
        sb.append(replacement)
        at = m.end
    }
    sb.append(text, at, text.length)
    return sb.toString()
}

/**
 * The index of the match Find Next / Find Previous should jump to.
 *
 * Wraps around instead of stopping at the end: a Find bar that refuses to continue
 * past the last match makes the user scroll up and start over, which is the single
 * most annoying thing a Find bar does.
 */
fun nextMatchIndex(matches: List<Found>, caret: Int, forward: Boolean, current: Int = -1): Int {
    if (matches.isEmpty()) return -1
    if (forward) {
        val afterCurrent = if (current in matches.indices) matches[current].end else caret
        val idx = matches.indexOfFirst { it.start >= afterCurrent }
        return if (idx >= 0) idx else 0
    }
    val beforeCurrent = if (current in matches.indices) matches[current].start else caret
    val idx = matches.indexOfLast { it.end <= beforeCurrent }
    return if (idx >= 0) idx else matches.lastIndex
}

/**
 * Thresholds the Find bar uses to warn about its own cost.
 *
 * Named constants rather than a literal in the composable so the number is stated
 * once and the screen does not silently disagree with it.
 */
object FindBar {
    /** Above this many matches, Replace All on a phone is a wait, not an instant. */
    const val WARN_ABOVE = 500

    /** The longest text a single Find All call will scan, matching the highlighter. */
    const val SCAN_LIMIT = 200_000
}
