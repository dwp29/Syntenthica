package net.pure.manager.edit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The editor's arithmetic, pinned.
 *
 * Every case here is a bug that was actually written first and then found by a
 * test: undo that pasted the new text over itself, auto-indent that indented past
 * the line, backspace that ate one space out of two, replace-all that re-read its
 * own output. The composable above this is thin on purpose; this is where the
 * behaviour lives.
 */
class EditorTest {

    // ---------------------------------------------------------------- buffer

    @Test
    fun typingThenUndoRestoresTheOriginalText() {
        val b = Buffer("halo")
        b.replace(4, 4, " dunia", 4)
        assertEquals("halo dunia", b.text)
        assertEquals(4, b.undo())
        assertEquals("halo", b.text)
    }

    /**
     * A paste is not `typed`: one Edit that happens to be one character long must not
     * merge with the word before it, or undoing a paste would eat the word too.
     */
    @Test
    fun aSingleCharacterPasteDoesNotMerge() {
        val b = Buffer("ab")
        b.replace(2, 2, "c", 2, typed = true)
        b.replace(3, 3, "d", 3) // no typed flag: a paste
        assertEquals(2, b.undoDepth)
    }

    /**
     * The first version stored only the inserted text, so undo computed the string
     * to remove from the buffer it had already changed -- and put the new text back
     * over itself. Undo looked like it did nothing. The edit has to carry what it
     * deleted.
     */
    @Test
    fun undoOfADeletionBringsTheDeletedTextBack() {
        val b = Buffer("baris satu\nbaris dua")
        b.replace(0, 10, "", 0) // delete "baris satu"
        assertEquals("\nbaris dua", b.text)
        b.undo()
        assertEquals("baris satu\nbaris dua", b.text)
    }

    @Test
    fun redoReappliesWhatUndoTookAway() {
        val b = Buffer("abc")
        b.replace(3, 3, "d", 3)
        b.undo()
        assertEquals("abc", b.text)
        assertEquals(4, b.redo())
        assertEquals("abcd", b.text)
    }

    @Test
    fun aNewEditAfterUndoDiscardsTheRedoTrail() {
        val b = Buffer("abc")
        b.replace(3, 3, "d", 3)
        b.undo()
        b.replace(0, 0, "z", 0)
        assertFalse(b.canRedo)
        assertNull(b.redo())
        assertEquals("zabc", b.text)
    }

    @Test
    fun typingAWordIsOneUndoStep() {
        val b = Buffer("")
        "kata".forEachIndexed { i, c -> b.replace(i, i, c.toString(), i, typed = true) }
        assertEquals(1, b.undoDepth)
        b.undo()
        assertEquals("", b.text)
    }

    @Test
    fun aPasteIsItsOwnUndoStep() {
        val b = Buffer("a")
        b.replace(1, 1, "b", 1)
        b.replace(2, 2, "tempel", 2) // multi-character: not merged
        assertEquals(2, b.undoDepth)
        b.undo()
        assertEquals("ab", b.text)
    }

    @Test
    fun enterStartsANewUndoStep() {
        val b = Buffer("")
        b.replace(0, 0, "x", 0, typed = true)
        b.replace(1, 1, "\n", 1, typed = true)
        assertEquals(2, b.undoDepth)
    }

    @Test
    fun offsetsAreClampedInsteadOfThrowing() {
        val b = Buffer("abc")
        assertEquals(4, b.replace(99, 120, "!"))
        assertEquals("abc!", b.text)
    }

    @Test
    fun anEmptyEditIsNotRecorded() {
        val b = Buffer("abc")
        b.replace(1, 1, "")
        assertFalse(b.canUndo)
    }

    // ----------------------------------------------------------- indentation

    @Test
    fun enterCarriesTheCurrentIndent() {
        assertEquals("\n    ", newlineInsertion("    val x = 1", 13))
    }

    @Test
    fun enterAfterABraceAddsOneLevel() {
        assertEquals("\n      ", newlineInsertion("    if (a) {", 12))
    }

    @Test
    fun enterInPlainTextAddsNothing() {
        assertEquals("\n", newlineInsertion("kata", 4))
    }

    /** Enter at the very start of an indented line must not indent the new line. */
    @Test
    fun enterAtTheStartOfAnIndentedLineUsesThatLinesIndent() {
        assertEquals("\n    ", newlineInsertion("    abc", 4))
    }

    @Test
    fun backspaceOnAnEmptyIndentedLineRemovesOneLevel() {
        val text = "    "
        assertEquals(0..1, dedentRange(text, 4))
    }

    @Test
    fun backspaceMidWordDoesNotDedent() {
        assertNull(dedentRange("    abc", 6))
    }

    @Test
    fun backspaceOnAnUnindentedLineIsANormalDelete() {
        assertNull(dedentRange("abc", 3))
    }

    /**
     * A 3-space indent is one level plus a leftover. Removing the whole 3 would
     * jump two levels' worth of intent; removing 2 leaves a single stray space,
     * which is what every editor that does this correctly does.
     */
    @Test
    fun anOddIndentLosesExactlyOneLevel() {
        val r = dedentRange("   x", 3)
        assertNotNull(r)
        assertEquals(2, r!!.last + 1)
    }

    @Test
    fun tabWithNoSelectionReturnsNullSoTheCallerInsertsOneLevel() {
        assertNull(indentBlock("abc", 1, 1, outdent = false))
    }

    @Test
    fun tabIndentsEverySelectedLine() {
        val text = "a\nb\nc"
        val block = indentBlock(text, 0, 5, outdent = false)
        assertNotNull(block)
        assertEquals(3, block!!.splices.size)
        // Applied bottom-up, the text becomes one level deeper on all three lines.
        var out = text
        block.splices.forEach { e ->
            out = out.substring(0, e.start) + e.inserted + out.substring(e.start + e.removed.length)
        }
        assertEquals("  a\n  b\n  c", out)
    }

    @Test
    fun shiftTabOutdentsSelectedLines() {
        val text = "  a\n  b"
        val block = indentBlock(text, 0, 7, outdent = true)
        assertNotNull(block)
        var out = text
        block.splices.forEach { e ->
            out = out.substring(0, e.start) + e.inserted + out.substring(e.start + e.removed.length)
        }
        assertEquals("a\nb", out)
    }

    @Test
    fun outdentingLinesWithNothingToRemoveChangesNothing() {
        assertNull(indentBlock("a\nb", 0, 3, outdent = true))
    }

    /** A selection ending exactly at a line start does not own that line. */
    @Test
    fun theLineAfterTheSelectionIsLeftAlone() {
        val block = indentBlock("a\nb", 0, 2, outdent = false)
        assertEquals(1, block!!.splices.size)
    }

    // ------------------------------------------------------------- brackets

    @Test
    fun aBracketIsClosedAutomatically() {
        val r = autoCloseFor("", 0, '(')
        assertEquals("(" to ")", r)
    }

    @Test
    fun typingAClosingBracketTheFileAlreadyHasTypesOverIt() {
        assertNull(autoCloseFor("()", 1, ')'))
    }

    @Test
    fun anApostropheAfterALetterIsNotAQuote() {
        assertNull(autoCloseFor("dont", 4, '\''))
    }

    @Test
    fun aQuoteAfterASpaceOpensAString() {
        assertEquals("\"" to "\"", autoCloseFor("x = ", 4, '"'))
    }

    @Test
    fun wrappingASelectionReturnsBothHalves() {
        assertEquals("\"" to "\"", autoCloseFor("kata", 0, '"', selectionLength = 4))
    }

    @Test
    fun backspaceRemovesBothHalvesOfAnEmptyPair() {
        assertTrue(deletesPair("()", 1))
        assertFalse(deletesPair("(x", 1))
        assertFalse(deletesPair("()", 0))
    }

    @Test
    fun theMatchingBracketIsFoundThroughNesting() {
        val text = "f(a, (b + c), d)"
        assertEquals(text.lastIndexOf(')'), matchingBracket(text, 1, Language.KOTLIN))
    }

    /**
     * Scanning outward from a closing bracket is refused on purpose. Commas balance,
     * so a backward scan from `)` in `f(a, b)` lands on the comma after `a` and
     * reports a "pair" that is not one. A right answer on flat code and a wrong one
     * on the common case is worse than no highlight, so there is no highlight.
     */
    @Test
    fun aClosingBracketIsNotMatchedBackwards() {
        val text = "f(a, (b + c), d)"
        assertNull(matchingBracket(text, text.lastIndexOf(')'), Language.KOTLIN))
    }

    @Test
    fun aBracketInsideAStringDoesNotCount() {
        assertNull(matchingBracket("f(\")\", x)", 1, Language.KOTLIN))
    }

    @Test
    fun anUnbalancedBracketHasNoMatch() {
        assertNull(matchingBracket("f(a", 1, Language.KOTLIN))
    }

    @Test
    fun aBracketFoundBeforeACommentIsStillAPair() {
        val text = "f(a) // )"
        assertEquals(3, matchingBracket(text, 1, Language.KOTLIN))
    }

    // ------------------------------------------------------------ highlight

    @Test
    fun aKeywordIsHighlightedButNotInsideAString() {
        val spans = highlight("val x = \"val\"", Language.KOTLIN)
        val keywordAt = spans.filter { it.kind == TokenKind.KEYWORD }
        assertEquals(1, keywordAt.size)
        assertEquals(0, keywordAt[0].start)
        assertTrue(spans.any { it.kind == TokenKind.STRING && it.start == 8 })
    }

    /**
     * The apostrophe bug: an unclosed quote used to swallow the rest of the file,
     * so everything after a contraction rendered as a string. A string stops at the
     * newline.
     */
    @Test
    fun anUnclosedQuoteStopsAtTheEndOfTheLine() {
        val spans = highlight("x = 'abc\ny = 1", Language.PYTHON)
        val string = spans.first { it.kind == TokenKind.STRING }
        assertTrue(string.end <= 7)
        assertTrue(spans.any { it.kind == TokenKind.NUMBER })
    }

    @Test
    fun aCommentRunsToTheEndOfTheLineOnly() {
        val spans = highlight("x = 1 // catatan\nval y = 2", Language.KOTLIN)
        val comment = spans.first { it.kind == TokenKind.COMMENT }
        assertEquals(6, comment.start)
        assertEquals(15, comment.end)
        assertTrue(spans.any { it.kind == TokenKind.KEYWORD && it.start == 16 })
    }

    @Test
    fun jsonKeysAreDistinguishedFromValues() {
        val spans = highlight("""{"nama": "budi"}""", Language.JSON)
        assertTrue(spans.any { it.kind == TokenKind.KEYWORD && it.start == 1 })
        assertTrue(spans.any { it.kind == TokenKind.STRING && it.start == 9 })
    }

    @Test
    fun xmlTagsAreHighlightedAndTextIsNot() {
        val spans = highlight("<akun nama=\"budi\">halo</akun>", Language.XML)
        assertTrue(spans.any { it.kind == TokenKind.KEYWORD && it.start == 1 })
        assertTrue(spans.any { it.kind == TokenKind.STRING && it.start == 11 })
    }

    @Test
    fun propertiesHighlightKeysAndComments() {
        val spans = highlight("# catatan\nnama=budi", Language.PROPERTIES)
        assertTrue(spans.any { it.kind == TokenKind.COMMENT && it.start == 0 })
        assertTrue(spans.any { it.kind == TokenKind.KEYWORD && it.start == 10 })
    }

    @Test
    fun shellTreatsHashAsAComment() {
        val spans = highlight("echo hi # halo", Language.SHELL)
        assertTrue(spans.any { it.kind == TokenKind.COMMENT && it.start == 8 })
    }

    @Test
    fun plainTextHasNoSpansAtAll() {
        assertTrue(highlight("apa saja {}", Language.PLAIN).isEmpty())
    }

    /**
     * Spans must not overlap: the screen appends them into one AnnotatedString, and
     * an overlap there is a runtime crash, not a cosmetic bug.
     */
    @Test
    fun spansNeverOverlapAndAreSorted() {
        val samples = listOf(
            "fun main() { val x = \"a(b)\" // (c)" to Language.KOTLIN,
            "<?xml version=\"1.0\"?><a b=\"c\">d</a>" to Language.XML,
            "# title\n`code` and **bold**" to Language.MARKDOWN,
            "{\"a\": [1, 2, null]}" to Language.JSON,
        )
        for ((text, lang) in samples) {
            val spans = highlight(text, lang)
            var last = 0
            for (s in spans) {
                assertTrue("overlap in $lang at ${s.start}", s.start >= last)
                assertTrue("empty span in $lang at ${s.start}", s.end > s.start)
                last = s.end
            }
        }
    }

    @Test
    fun aHugeDocumentIsNotColouredPastTheLimit() {
        val text = "val ".repeat(60_000)
        val spans = highlight(text, Language.KOTLIN, limit = 1_000)
        assertTrue(spans.all { it.end <= 1_000 })
    }

    @Test
    fun theLanguageIsPickedFromTheExtension() {
        assertEquals(Language.KOTLIN, Language.forFileName("MainActivity.kt"))
        assertEquals(Language.SHELL, Language.forFileName("gradlew"))
        assertEquals(Language.PLAIN, Language.forFileName("catatan.txt"))
        assertEquals(Language.XML, Language.forFileName("AndroidManifest.XML"))
    }

    @Test
    fun lineAndColumnAreOneBased() {
        assertEquals(1 to 1, lineColumn("abc", 0))
        assertEquals(2 to 1, lineColumn("abc\ndef", 4))
        assertEquals(2 to 4, lineColumn("abc\ndef", 7))
    }

    // --------------------------------------------------------------- search

    @Test
    fun findIsCaseInsensitiveByDefault() {
        val m = findIn("Nama Berkas", "berkas")
        assertEquals(Found(5, 11), m)
    }

    @Test
    fun findCanBeCaseSensitive() {
        assertNull(findIn("Nama Berkas", "berkas", caseSensitive = true))
    }

    @Test
    fun wholeWordDoesNotMatchInsideAnotherWord() {
        assertNull(findIn("berkasnya", "berkas", wholeWord = true))
        assertNotNull(findIn("berkas itu", "berkas", wholeWord = true))
    }

    /**
     * The replacement contains the needle. A naive loop re-reads its own output and
     * either runs forever or replaces inside the replacement it just wrote.
     */
    @Test
    fun replaceAllHandlesAReplacementThatContainsTheNeedle() {
        assertEquals("a-b a-b", replaceAll("a a", "a", "a-b"))
    }

    @Test
    fun replaceAllHandlesACaseInsensitiveNeedle() {
        assertEquals("X X X", replaceAll("a A a", "a", "X"))
    }

    @Test
    fun replaceAllWithNoMatchReturnsTheSameText() {
        assertEquals("abc", replaceAll("abc", "zz", "!"))
    }

    @Test
    fun findNextWrapsAroundTheEnd() {
        val matches = findAllIn("a a a", "a")
        assertEquals(3, matches.size)
        assertEquals(0, nextMatchIndex(matches, 5, forward = true, current = 2))
    }

    @Test
    fun findPreviousWrapsAroundTheStart() {
        val matches = findAllIn("a a a", "a")
        assertEquals(2, nextMatchIndex(matches, 0, forward = false, current = 0))
    }

    @Test
    fun searchingAnEmptyNeedleFindsNothing() {
        assertTrue(findAllIn("abc", "").isEmpty())
        assertNull(findIn("abc", ""))
    }

    @Test
    fun aOneLetterSearchIsBounded() {
        val many = findAllIn("a".repeat(10_000), "a", limit = 50)
        assertEquals(50, many.size)
    }
}
