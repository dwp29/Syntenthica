package net.pure.manager.fs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests for the decisions that were wrong in 0.3.0.
 *
 * Each test here exists because the bug it covers was reachable from the UI: an up
 * button that returned the same path, a count line that read "0 folder · 0 berkas"
 * for an empty folder, and destinations that a copy would happily accept.
 */
class SupportTest {

    // ---------------------------------------------------------------- parentOf

    @Test
    fun `parent of a nested file path is its directory`() {
        assertEquals("/storage/emulated/0/Download", Support.parentOf("/storage/emulated/0/Download/a.txt"))
    }

    @Test
    fun `parent of the volume root is null`() {
        assertNull(Support.parentOf("/storage/emulated/0"))
    }

    @Test
    fun `parent of a SAF document is the real parent, not the same path`() {
        val child = "content://com.android.externalstorage.documents/tree/primary%3ADCIM/" +
            "document/primary%3ADCIM%2FCamera"
        val parent = Support.parentOf(child)
        assertEquals(
            "content://com.android.externalstorage.documents/tree/primary%3ADCIM/" +
                "document/primary%3ADCIM",
            parent,
        )
    }

    @Test
    fun `parent of a SAF volume root is null`() {
        val root = "content://com.android.externalstorage.documents/tree/primary%3A/" +
            "document/primary%3A"
        assertNull(Support.parentOf(root))
    }

    // -------------------------------------------------------------- isInside

    @Test
    fun `a folder is inside itself`() {
        assertTrue(Support.isInside("/sdcard/a", "/sdcard/a"))
    }

    @Test
    fun `a sibling with a shared prefix is not inside`() {
        assertTrue(!Support.isInside("/sdcard/ab", "/sdcard/a"))
    }

    @Test
    fun `nothing is inside the empty path`() {
        assertTrue(!Support.isInside("/sdcard/a", ""))
    }

    // ---------------------------------------------------- invalidDestination

    @Test
    fun `copying into itself is refused`() {
        assertEquals(
            "Tujuan sama dengan sumber",
            Support.invalidDestination("/sdcard/a", "/sdcard/a"),
        )
    }

    @Test
    fun `copying into a child folder is refused`() {
        assertEquals(
            "Tidak bisa menyalin folder ke dalam dirinya sendiri",
            Support.invalidDestination("/sdcard/a", "/sdcard/a/b"),
        )
    }

    @Test
    fun `copying next to itself is allowed`() {
        assertNull(Support.invalidDestination("/sdcard/a", "/sdcard"))
    }

    // ----------------------------------------------------------------- places

    @Test
    fun `places start with internal storage and include every tree`() {
        val places = Support.places(
            internalPath = "/storage/emulated/0",
            volumes = listOf(Triple("SD card", "/storage/1A2B", true)),
            trees = listOf("DCIM" to "content://tree/dcim"),
        )
        assertEquals(3, places.size)
        assertEquals("Internal", places[0].label)
        assertEquals("SD card", places[1].label)
        assertEquals("Folder pilihan", places[2].description)
    }

    @Test
    fun `an unmounted volume says so instead of pretending`() {
        val places = Support.places(
            internalPath = "/storage/emulated/0",
            volumes = listOf(Triple("SD card", "/storage/1A2B", false)),
            trees = emptyList(),
        )
        assertEquals("Tidak terpasang", places[1].description)
    }

    // -------------------------------------------------------------- countLabel

    @Test
    fun `an empty folder says Kosong, not zero of everything`() {
        assertEquals("Kosong", Support.countLabel(emptyList()))
    }

    @Test
    fun `folders only, files only, and both`() {
        val folder = FileEntry("/a", "a", true, 0, 0, false, true)
        val file = FileEntry("/a/b", "b", false, 10, 0, false, true)
        assertEquals("1 folder", Support.countLabel(listOf(folder)))
        assertEquals("1 berkas", Support.countLabel(listOf(file)))
        assertEquals("1 folder \u00b7 1 berkas", Support.countLabel(listOf(folder, file)))
    }

    // ------------------------------------------------------------------- mime

    @Test
    fun `the mime type matches what the opener needs`() {
        assertEquals("image/png", Support.mimeFor("Foto.PNG"))
        assertEquals("text/plain", Support.mimeFor("catatan.md"))
        assertEquals("application/vnd.android.package-archive", Support.mimeFor("app.apk"))
    }

    @Test
    fun `an unknown type is binary, not empty`() {
        // An empty type matches no application, so the chooser would come up blank.
        assertEquals("application/octet-stream", Support.mimeFor("data.xyzzy"))
    }

    // ------------------------------------------------------- percent encoding

    @Test
    fun `plus is not decoded as a space`() {
        assertEquals("a+b", Support.percentDecode("a+b"))
    }

    @Test
    fun `encoding and decoding round-trip a path with spaces`() {
        val original = "primary:DCIM/Camera Roll"
        assertEquals(original, Support.percentDecode(Support.percentEncode(original)))
    }

    @Test
    fun `encoding leaves unreserved characters alone`() {
        assertEquals("abc-_.~123", Support.percentEncode("abc-_.~123"))
    }
}
