package net.pure.manager.root

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class TerminalTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private val sh = "/bin/sh"

    private fun terminal(
        binary: String? = "/bin/sh",
        home: String = "/",
    ) = Terminal(
        binary = binary,
        homeDirectory = home,
        runner = { bin, cmd -> Shell.run(bin, cmd, timeoutSeconds = 10) },
    )

    private fun Terminal.text() = lines.joinToString("\n") { it.text }

    @Test
    fun an_empty_submit_prints_nothing() {
        val t = terminal()
        assertTrue(t.submit("   "))
        assertEquals(emptyList<Terminal.Line>(), t.lines)
    }

    @Test
    fun a_command_prints_its_output_and_returns_true() {
        if (!File(sh).exists()) return
        val t = terminal()
        assertTrue(t.submit("echo halo"))
        assertTrue(t.text().contains("halo"))
    }

    @Test
    fun exit_asks_the_caller_to_close_the_screen() {
        val t = terminal()
        assertFalse(t.submit("exit"))
        assertFalse(t.submit("keluar"))
    }

    @Test
    fun clear_empties_the_scrollback() {
        if (!File(sh).exists()) return
        val t = terminal()
        t.submit("echo sesuatu")
        assertTrue(t.lines.isNotEmpty())
        t.submit("clear")
        assertEquals(emptyList<Terminal.Line>(), t.lines)
    }

    @Test
    fun pwd_prints_the_directory_and_cd_moves_it() {
        val dir = tmp.newFolder("kerja")
        val t = terminal(home = dir.absolutePath)
        t.submit("pwd")
        assertTrue(t.text().contains(dir.absolutePath))

        t.submit("cd ..")
        assertEquals(tmp.root.absolutePath, t.directory)
    }

    @Test
    fun cd_into_a_missing_folder_reports_it_and_stays_put() {
        val dir = tmp.newFolder("tetap")
        val t = terminal(home = dir.absolutePath)
        t.submit("cd tidak-ada")
        assertEquals(dir.absolutePath, t.directory)
        assertTrue(t.lines.last().isError)
        assertTrue(t.lines.last().text.contains("tidak ada folder"))
    }

    @Test
    fun cd_without_an_argument_goes_home() {
        val dir = tmp.newFolder("rumah")
        val t = terminal(home = dir.absolutePath)
        t.submit("cd /")
        t.submit("cd")
        assertEquals(dir.absolutePath, t.directory)
    }

    @Test
    fun normalisation_collapses_dots_and_double_slashes() {
        assertEquals("/a/b", Terminal.normalise("/a/./b"))
        assertEquals("/a", Terminal.normalise("/a/b/.."))
        assertEquals("/", Terminal.normalise("/a/.."))
        assertEquals("/a/b", Terminal.normalise("/a//b/"))
        // Never above the root.
        assertEquals("/", Terminal.normalise("/../../.."))
    }

    @Test
    fun a_command_runs_in_the_prompted_directory() {
        if (!File(sh).exists()) return
        val dir = tmp.newFolder("di-sini")
        File(dir, "penanda.txt").writeText("x")
        val t = terminal(home = dir.absolutePath)
        t.submit("ls")
        assertTrue(t.text().contains("penanda.txt"))
    }

    @Test
    fun without_root_the_command_is_refused_with_a_reason_not_a_crash() {
        val t = terminal(binary = null)
        assertTrue(t.submit("rm -rf /data"))
        assertFalse(t.hasRoot)
        val last = t.lines.last()
        assertTrue(last.isError)
        assertTrue(last.text.contains("root"))
    }

    @Test
    fun a_nonzero_exit_code_is_printed() {
        if (!File(sh).exists()) return
        val t = terminal()
        t.submit("exit 3")
        assertTrue(t.text().contains("[kode 3]"))
    }

    @Test
    fun history_keeps_what_was_typed_in_order() {
        if (!File(sh).exists()) return
        val t = terminal()
        t.submit("echo satu")
        t.submit("echo dua")
        assertEquals(listOf("echo satu", "echo dua"), t.history)
    }

    @Test
    fun the_scrollback_is_capped() {
        if (!File(sh).exists()) return
        val t = terminal()
        repeat(Terminal.MAX_LINES + 40) { t.submit("echo $it") }
        assertTrue(t.lines.size <= Terminal.MAX_LINES)
    }

    @Test
    fun a_command_with_nothing_to_say_says_so() {
        if (!File(sh).exists()) return
        val t = terminal()
        t.submit("true")
        assertTrue(t.text().contains("tidak ada keluaran"))
    }

    @Test
    fun the_prompt_says_whether_root_is_available() {
        assertTrue(terminal(binary = "/system/bin/su").prompt().startsWith("root:"))
        assertTrue(terminal(binary = null).prompt().startsWith("tanpa-root:"))
    }
}
