package net.pure.manager.module

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ModuleManagerTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun entry(sha: String, id: String = "doc", version: String = "1.0.0") =
        ModuleManager.Entry(
            id = id,
            name = "Dokumen",
            version = version,
            description = "Baca PDF",
            sha256 = sha,
            asset = "$id-$version.pmod",
        )

    private fun fileWith(content: String, name: String = "download.pmod"): File {
        val f = File(tmp.root, name)
        f.writeText(content)
        return f
    }

    @Test
    fun a_matching_hash_installs_and_keeps_the_file() {
        val f = fileWith("isi modul")
        val outcome = ModuleManager.verify(f, entry(ModuleManager.sha256(f)))

        assertTrue(outcome is ModuleManager.Outcome.Installed)
        assertTrue(f.exists())
    }

    @Test
    fun a_wrong_hash_is_refused_and_the_file_is_deleted() {
        val f = fileWith("isi yang diubah")
        val wrong = "0".repeat(64)

        val outcome = ModuleManager.verify(f, entry(wrong))

        assertEquals(ModuleManager.Outcome.HashMismatch, outcome)
        // Leaving it on disk is one tap from being installed by a later version.
        assertFalse("a refused module must not stay on disk", f.exists())
    }

    @Test
    fun a_file_that_vanished_reports_failure_not_a_crash() {
        val outcome = ModuleManager.verify(File(tmp.root, "hilang.pmod"), entry("a".repeat(64)))
        assertTrue(outcome is ModuleManager.Outcome.Failed)
    }

    @Test
    fun the_hash_is_the_known_sha256_of_the_text() {
        val f = fileWith("abc")
        // Known value: SHA-256("abc")
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            ModuleManager.sha256(f),
        )
    }

    @Test
    fun hash_comparison_ignores_case_and_surrounding_spaces() {
        val f = fileWith("abc")
        val upper = ModuleManager.sha256(f).uppercase()
        assertTrue(ModuleManager.verify(f, entry("  $upper  ")) is ModuleManager.Outcome.Installed)
    }

    @Test
    fun a_large_file_is_hashed_without_being_read_whole() {
        // 4 MB, well past the 64 KB buffer, to prove the streaming loop covers more
        // than a single read.
        val f = File(tmp.root, "besar.pmod")
        f.outputStream().use { out ->
            val chunk = ByteArray(64 * 1024) { 7 }
            repeat(64) { out.write(chunk) }
        }
        assertEquals(4L * 1024 * 1024, f.length())
        assertEquals(ModuleManager.sha256(f), ModuleManager.sha256(f))
        assertEquals(64, ModuleManager.sha256(f).length)
    }

    @Test
    fun installed_lists_only_modules_whose_hash_still_matches() {
        val dir = tmp.newFolder("modules")
        val good = File(dir, "doc.pmod").apply { writeText("baik") }
        File(dir, "pdf.pmod").writeText("dirusak")

        val catalog = listOf(
            entry(ModuleManager.sha256(good), id = "doc"),
            entry("f".repeat(64), id = "pdf"),
        )

        val installed = ModuleManager.installed(dir, catalog)

        assertEquals(listOf("doc"), installed.map { it.id })
    }

    @Test
    fun a_missing_module_folder_is_not_a_crash() {
        assertEquals(emptyList<ModuleManager.Entry>(), ModuleManager.installed(File(tmp.root, "tidak-ada"), listOf(entry("a".repeat(64)))))
        assertEquals(emptyList<File>(), ModuleManager.orphans(File(tmp.root, "tidak-ada"), emptyList()))
    }

    @Test
    fun orphans_are_files_that_no_entry_claims() {
        val dir = tmp.newFolder("modules")
        File(dir, "doc.pmod").writeText("x")
        File(dir, "sisa.pmod").writeText("y")
        File(dir, "catatan.txt").writeText("z")

        val orphans = ModuleManager.orphans(dir, listOf(entry("a".repeat(64), id = "doc")))

        assertEquals(listOf("sisa.pmod"), orphans.map { it.name })
    }

    @Test
    fun version_comparison_is_numeric_not_lexicographic() {
        // "10" < "9" as text, which is how a version check quietly stops offering
        // updates.
        assertTrue(ModuleManager.isNewer("1.10.0", "1.9.0"))
        assertTrue(ModuleManager.isNewer("2.0.0", "1.99.99"))
        assertTrue(ModuleManager.isNewer("1.0.1", "1.0.0"))
        assertFalse(ModuleManager.isNewer("1.0.0", "1.0.0"))
        assertFalse(ModuleManager.isNewer("1.0", "1.0.1"))
        // Different lengths are compared as if the short one had zeros.
        assertFalse(ModuleManager.isNewer("1.0", "1.0.0"))
        assertTrue(ModuleManager.isNewer("1.0.1", "1.0"))
    }

    @Test
    fun a_module_file_that_is_a_directory_is_not_installed() {
        val dir = tmp.newFolder("modules")
        File(dir, "doc.pmod").mkdirs()
        assertEquals(emptyList<ModuleManager.Entry>(), ModuleManager.installed(dir, listOf(entry("a".repeat(64)))))
    }
}
