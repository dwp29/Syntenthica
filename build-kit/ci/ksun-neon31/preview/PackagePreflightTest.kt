package com.rifsxd.ksunext.ui.preflight

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class PackagePreflightTest {
    private val root = Files.createTempDirectory("preflight-test-").toFile()
    @After fun cleanup() { root.deleteRecursively() }

    private fun zip(vararg entries: Pair<String, String>): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { zip ->
            entries.forEach { (name, text) ->
                zip.putNextEntry(ZipEntry(name))
                zip.write(text.toByteArray())
                zip.closeEntry()
            }
        }
        return out.toByteArray()
    }

    private fun inspect(bytes: ByteArray, maxBytes: Long = PackagePreflight.MAX_ARCHIVE_BYTES,
                        maxEntries: Int = PackagePreflight.MAX_ENTRIES): PackageReport {
        val destination = File.createTempFile("pkg31-", ".zip", root)
        return PackagePreflight.stageAndInspect(ByteArrayInputStream(bytes), destination, "Demo.zip", maxBytes, maxEntries)
    }

    private fun rejects(bytes: ByteArray, problem: PreflightProblem,
                        maxBytes: Long = PackagePreflight.MAX_ARCHIVE_BYTES,
                        maxEntries: Int = PackagePreflight.MAX_ENTRIES) {
        val destination = File.createTempFile("pkg31-", ".zip", root)
        try {
            PackagePreflight.stageAndInspect(ByteArrayInputStream(bytes), destination, "Demo.zip", maxBytes, maxEntries)
            fail("expected $problem")
        } catch (error: PreflightException) {
            assertEquals(problem, error.problem)
            assertFalse("failed stage should be deleted", destination.exists())
        }
    }

    @Test fun moduleIsIdentifiedAndExactCopyIsHashed() {
        val bytes = zip("module.prop" to "id=test.module\nname=Example\nversion=1.2\nauthor=Developer\n",
            "customize.sh" to "touch must-not-execute")
        val report = inspect(bytes)
        assertEquals(PackageKind.MODULE, report.kind)
        assertEquals("test.module", report.metadata["id"])
        assertEquals("Example", report.metadata["name"])
        assertEquals(bytes.size.toLong(), report.size)
        assertArrayEquals(bytes, report.file.readBytes())
        val expected = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals(expected, report.sha256)
        assertTrue(PackagePreflight.matchesSha256(report.file, report.sha256))
        assertFalse(File(root, "must-not-execute").exists())
        report.file.appendText("tamper")
        assertFalse(PackagePreflight.matchesSha256(report.file, report.sha256))
        assertFalse(PackagePreflight.matchesSha256(report.file, "not-a-hash"))
    }

    @Test fun anyKernelNeedsItsOwnMarkerAndInstaller() {
        val valid = zip("anykernel.sh" to "#!/bin/sh\n", "META-INF/com/google/android/update-binary" to "#!/bin/sh\n")
        assertEquals(PackageKind.ANYKERNEL, inspect(valid).kind)
        rejects(zip("anykernel.sh" to "#!/bin/sh\n"), PreflightProblem.MISSING_INSTALLER)
        rejects(zip("anykernel.sh" to "", "META-INF/com/google/android/update-binary" to "x"), PreflightProblem.MISSING_INSTALLER)
    }

    @Test fun unknownAmbiguousAndCorruptArchivesCannotProceed() {
        rejects("not a zip".toByteArray(), PreflightProblem.INVALID_ZIP)
        rejects(zip("readme.txt" to "hello"), PreflightProblem.UNKNOWN_TYPE)
        rejects(zip("module.prop" to "id=a", "anykernel.sh" to "x"), PreflightProblem.AMBIGUOUS_TYPE)
        rejects(zip("module.prop" to "name=no id"), PreflightProblem.INVALID_METADATA)
        rejects(zip("module.prop" to "id=first\nid=second\n"), PreflightProblem.INVALID_METADATA)
        rejects(zip("module.prop" to "id=a\nname=first\nname=second\n"), PreflightProblem.INVALID_METADATA)
        rejects(zip("./module.prop" to "id=a"), PreflightProblem.UNKNOWN_TYPE)
        rejects(zip("./anykernel.sh" to "x", "META-INF/com/google/android/update-binary" to "x"), PreflightProblem.UNKNOWN_TYPE)
        rejects(zip("anykernel.sh" to "x", "./META-INF/com/google/android/update-binary" to "x"), PreflightProblem.MISSING_INSTALLER)
    }

    @Test fun traversalDuplicatePathsAndLimitsAreRejected() {
        rejects(zip("module.prop" to "id=a", "../escape" to "x"), PreflightProblem.UNSAFE_PATH)
        rejects(zip("module.prop" to "id=a", "a\\b" to "x"), PreflightProblem.UNSAFE_PATH)
        rejects(zip("module.prop" to "id=a", "/absolute" to "x"), PreflightProblem.UNSAFE_PATH)
        rejects(zip("module.prop" to "id=a", "a" to "1", "./a" to "2"), PreflightProblem.DUPLICATE_PATH)
        val bytes = zip("module.prop" to "id=a", "other" to "x")
        rejects(bytes, PreflightProblem.TOO_LARGE, maxBytes = 10)
        rejects(bytes, PreflightProblem.TOO_MANY_ENTRIES, maxEntries = 1)
        rejects(zip("module.prop" to ("id=" + "a".repeat(65_536))), PreflightProblem.INVALID_METADATA)
    }

    @Test fun stalledOrFailedInputIsRejectedAndTheStageIsDeleted() {
        val stalled = object : java.io.InputStream() {
            override fun read(): Int = 0
            override fun read(bytes: ByteArray, offset: Int, length: Int): Int = 0
        }
        val destination = File.createTempFile("pkg31-", ".zip", root)
        try {
            PackagePreflight.stageAndInspect(stalled, destination, "stalled.zip")
            fail("expected unreadable input")
        } catch (error: PreflightException) {
            assertEquals(PreflightProblem.UNREADABLE, error.problem)
            assertFalse(destination.exists())
        }
        val broken = object : java.io.InputStream() {
            override fun read(): Int = throw java.io.IOException("simulated read failure")
        }
        val failedDestination = File.createTempFile("pkg31-", ".zip", root)
        try {
            PackagePreflight.stageAndInspect(broken, failedDestination, "broken.zip")
            fail("expected failed input")
        } catch (error: PreflightException) {
            assertEquals(PreflightProblem.UNREADABLE, error.problem)
            assertFalse(failedDestination.exists())
        }
    }

    @Test fun centralAndLocalHeadersCannotDisagreeOrHideSpecialEntries() {
        fun central(bytes: ByteArray): Int {
            for (i in 0 until bytes.size - 4) {
                if (bytes[i] == 0x50.toByte() && bytes[i + 1] == 0x4b.toByte() &&
                    bytes[i + 2] == 0x01.toByte() && bytes[i + 3] == 0x02.toByte()) return i
            }
            error("central directory missing")
        }
        val mismatch = zip("module.prop" to "id=a")
        val unsafeLocalName = "../evilXXXX".toByteArray()
        assertEquals("module.prop".length, unsafeLocalName.size)
        unsafeLocalName.copyInto(mismatch, destinationOffset = 30)
        rejects(mismatch, PreflightProblem.INVALID_ZIP)

        val symlink = zip("module.prop" to "id=a")
        val c = central(symlink)
        symlink[c + 5] = 3 // Unix creator
        symlink[c + 40] = 0xff.toByte()
        symlink[c + 41] = 0xa1.toByte() // Unix symlink mode 0120777
        rejects(symlink, PreflightProblem.UNSAFE_PATH)

        val encrypted = zip("module.prop" to "id=a")
        encrypted[6] = (encrypted[6].toInt() or 1).toByte()
        val encryptedCentral = central(encrypted)
        encrypted[encryptedCentral + 8] = (encrypted[encryptedCentral + 8].toInt() or 1).toByte()
        rejects(encrypted, PreflightProblem.UNSUPPORTED_ZIP)

        val badCrc = zip("module.prop" to "id=a")
        val crcCentral = central(badCrc)
        badCrc[crcCentral + 16] = (badCrc[crcCentral + 16].toInt() xor 1).toByte()
        rejects(badCrc, PreflightProblem.INVALID_ZIP)
    }

    @Test fun metadataCannotInjectMultilineOrBidiUiText() {
        val report = inspect(zip("module.prop" to "id=a\nname=hello\u202Eworld\nauthor=valid\n"))
        assertFalse(report.metadata.getValue("name").contains('\u202E'))
        assertEquals("hello world", report.metadata["name"])
    }
}
