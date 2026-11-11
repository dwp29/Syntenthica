package net.pure.manager.fs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AlphabetTest {

    private fun entry(name: String, dir: Boolean = false) = FileEntry(
        path = "/x/$name",
        name = name,
        isDirectory = dir,
        sizeBytes = 1,
        lastModified = 0,
        isHidden = false,
        canRead = true,
    )

    @Test
    fun a_plain_name_goes_under_its_first_letter() {
        assertEquals("L", Alphabet.sectionOf("Laporan.pdf"))
        assertEquals("L", Alphabet.sectionOf("laporan.pdf"))
        assertEquals("A", Alphabet.sectionOf("  album"))
    }

    @Test
    fun digits_and_symbols_get_their_own_group_not_a_letter() {
        // Half the folders on a real phone start with a digit. Bucketing them under
        // "A" because their char code is lower would be invisible until someone
        // looked for a folder that was not where the strip said it was.
        assertEquals(Alphabet.OTHER, Alphabet.sectionOf("2026-11-11_APK"))
        assertEquals(Alphabet.OTHER, Alphabet.sectionOf("_privat.txt"))
        assertEquals(Alphabet.OTHER, Alphabet.sectionOf("¥100"))
    }

    @Test
    fun accents_fold_to_the_base_letter() {
        assertEquals("E", Alphabet.sectionOf("Ékspor"))
        assertEquals("E", Alphabet.sectionOf("ékspor"))
        assertEquals("C", Alphabet.sectionOf("Čarape"))
        assertEquals("N", Alphabet.sectionOf("Ñandu"))
        assertEquals("A", Alphabet.sectionOf("Àlbum"))
    }

    @Test
    fun an_empty_name_does_not_throw() {
        assertEquals(Alphabet.OTHER, Alphabet.sectionOf(""))
        assertEquals(Alphabet.OTHER, Alphabet.sectionOf("   "))
    }

    @Test
    fun the_strip_has_twenty_seven_entries_with_the_fallback_last() {
        val s = Alphabet.sections
        assertEquals(27, s.size)
        assertEquals("A", s.first())
        assertEquals("Z", s[25])
        assertEquals(Alphabet.OTHER, s.last())
    }

    @Test
    fun grouping_orders_letters_and_puts_the_symbols_last() {
        val grouped = Alphabet.group(
            listOf(
                entry("zebra.txt"),
                entry("2026_apk", dir = true),
                entry("apel.txt"),
                entry("Bulan.txt"),
            ),
        )
        assertEquals(listOf("A", "B", "Z", Alphabet.OTHER), grouped.map { it.first })
    }

    @Test
    fun grouping_keeps_the_folder_first_order_inside_a_letter() {
        val grouped = Alphabet.group(
            listOf(
                entry("Album", dir = true),
                entry("apel.txt"),
                entry("arsip.zip"),
            ),
        )
        assertEquals(1, grouped.size)
        // Folders and files keep whatever order the sorter gave them; bucketing
        // must not reorder within a letter.
        assertTrue(grouped[0].second[0].isDirectory)
        assertEquals(
            listOf("Album", "apel.txt", "arsip.zip"),
            grouped[0].second.map { it.name },
        )
    }

    @Test
    fun an_empty_listing_groups_to_nothing() {
        assertEquals(emptyList<Pair<String, List<FileEntry>>>(), Alphabet.group(emptyList()))
    }
}
