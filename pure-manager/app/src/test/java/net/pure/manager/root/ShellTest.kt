package net.pure.manager.root

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * The shell layer, driven with `sh` instead of `su`.
 *
 * Root code that has only ever run on a rooted phone is code nobody tested. The
 * parts that break are not the `su` call, they are the quoting, the timeout and
 * the exit code -- all of which `sh` exercises identically.
 */
class ShellTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private val sh = "/bin/sh"

    private fun shellAvailable(): Boolean = File(sh).exists()

    @Test
    fun a_successful_command_reports_zero_and_its_output() {
        if (!shellAvailable()) return
        val r = Shell.run(sh, "echo halo")
        assertEquals(0, r.code)
        assertTrue(r.ok)
        assertEquals("halo", r.output.trim())
    }

    @Test
    fun a_failing_command_keeps_its_exit_code_and_stderr() {
        if (!shellAvailable()) return
        val r = Shell.run(sh, "echo gagal >&2; exit 7")
        assertEquals(7, r.code)
        assertFalse(r.ok)
        assertEquals("gagal", r.message)
    }

    @Test
    fun a_command_that_hangs_is_killed_not_waited_on_forever() {
        if (!shellAvailable()) return
        val started = System.currentTimeMillis()
        // 30 seconds of sleep with a 1 second budget. A root prompt nobody answers
        // looks exactly like this to the caller.
        val r = Shell.run(sh, "sleep 30", timeoutSeconds = 1)
        val elapsed = System.currentTimeMillis() - started
        assertEquals(-1, r.code)
        assertFalse(r.ok)
        assertTrue("timeout should not have waited $elapsed ms", elapsed < 10_000)
        assertTrue(r.message.contains("detik"))
    }

    @Test
    fun a_missing_binary_is_reported_not_thrown() {
        val r = Shell.run("/tidak/ada/su", "echo apa")
        assertEquals(-1, r.code)
        assertTrue(r.message.isNotBlank())
    }

    @Test
    fun a_file_name_with_a_space_and_an_apostrophe_survives_quoting() {
        if (!shellAvailable()) return
        val dir = tmp.newFolder("my folder's name")
        val file = File(dir, "laporan rahasia's.txt")
        file.writeText("isi")

        val r = Shell.run(sh, "ls -1 " + Shell.quote(dir.absolutePath))

        assertEquals(0, r.code)
        assertTrue(r.output.contains("laporan rahasia's.txt"))
    }

    @Test
    fun quoting_never_leaves_a_bare_argument() {
        assertEquals("'abc'", Shell.quote("abc"))
        assertEquals("'it'\\''s'", Shell.quote("it's"))
        // The dangerous case: a name that is a command when unquoted.
        assertEquals("'rm -rf /'", Shell.quote("rm -rf /"))
        assertEquals("''", Shell.quote(""))
    }

    @Test
    fun command_joins_and_quotes_every_part() {
        assertEquals("'cp' '-r' 'a b'", Shell.command("cp", "-r", "a b"))
    }

    @Test
    fun a_command_written_with_quotes_cannot_escape_them() {
        if (!shellAvailable()) return
        // If quoting were wrong this would run `echo` and then `echo`; with it
        // right, the whole thing is one harmless argument. Plain `echo`, not
        // `printf`: the test runner's sh prints the quotes around single
        // arguments, so comparing printf output compared shell dialects.
        val r = Shell.run(sh, "echo " + Shell.quote("a; echo disusupi"))
        assertEquals(0, r.code)
        // One occurrence, not two: a second line would mean the text was executed.
        assertEquals(1, r.output.lines().count { it.contains("echo disusupi") })
        assertEquals(1, r.output.trim().lines().size)
    }

    @Test
    fun su_is_found_only_where_it_exists() {
        assertNull(Shell.suBinary { false })
        val found = Shell.suBinary { it == "/system/bin/su" }
        assertEquals("/system/bin/su", found)
        assertNotNull(Shell.suBinary { it == "/data/adb/ksu/bin/su" })
    }

    @Test
    fun a_command_can_write_and_read_back_through_the_shell() {
        if (!shellAvailable()) return
        val target = File(tmp.root, "hasil.txt")
        val r = Shell.run(sh, "printf 'ok' > " + Shell.quote(target.absolutePath))
        assertEquals(0, r.code)
        assertEquals("ok", target.readText())
    }
}
