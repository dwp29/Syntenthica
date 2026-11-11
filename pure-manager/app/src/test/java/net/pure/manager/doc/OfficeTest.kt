package net.pure.manager.doc

import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The parsers are driven with documents built in memory.
 *
 * Building a real .docx here would mean carrying a binary fixture into a public
 * repository; building the smallest ZIP that has the same shape tests exactly the
 * part that breaks -- the XML, the shared string table and the cell references.
 */
class OfficeTest {

    private fun zip(parts: Map<String, String>): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { z ->
            parts.forEach { (name, content) ->
                z.putNextEntry(ZipEntry(name))
                z.write(content.toByteArray())
                z.closeEntry()
            }
        }
        return out.toByteArray()
    }

    private fun docx(vararg paragraphs: String): ByteArray = zip(
        mapOf(
            "word/document.xml" to
                """<?xml version="1.0"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>${paragraphs.joinToString("") { "<w:p><w:r><w:t>$it</w:t></w:r></w:p>" }}</w:body>
                </w:document>""",
        ),
    )

    private fun xlsx(sheetNames: List<String>, rows: String): ByteArray {
        val sheets = sheetNames.mapIndexed { i, name ->
            "<sheet name=\"$name\" sheetId=\"${i + 1}\" r:id=\"rId${i + 1}\"/>"
        }.joinToString("")
        val parts = mutableMapOf(
            "xl/workbook.xml" to
                """<?xml version="1.0"?>
                <workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                <sheets>$sheets</sheets></workbook>""",
            "xl/sharedStrings.xml" to
                """<?xml version="1.0"?>
                <sst><si><t>Nama</t></si><si><t>Harga</t></si><si><t>Apel</t></si><si><t>Jeruk</t></si></sst>""",
        )
        sheetNames.indices.forEach { i -> parts["xl/worksheets/sheet${i + 1}.xml"] = rows }
        return zip(parts)
    }

    // ------------------------------------------------------------------ docx

    @Test
    fun docx_paragraphs_become_lines() {
        val r = Office.read("surat.docx") { docx("Kepada Yth.", "Bapak Direktur") }
        assertTrue(r is Office.Preview.Document)
        r as Office.Preview.Document
        assertEquals(listOf("Kepada Yth.", "Bapak Direktur"), r.lines.map { it.text })
    }

    @Test
    fun docx_empty_paragraphs_do_not_become_blank_lines() {
        val r = Office.read("a.docx") { docx("Satu", "", "Dua") }
        r as Office.Preview.Document
        assertEquals(listOf("Satu", "Dua"), r.lines.map { it.text })
    }

    @Test
    fun docx_headings_are_marked() {
        val xml = zip(
            mapOf(
                "word/document.xml" to
                    """<?xml version="1.0"?>
                    <w:document xmlns:w="x"><w:body>
                    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Bab 1</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Isi biasa</w:t></w:r></w:p>
                    </w:body></w:document>""",
            ),
        )
        val r = Office.read("b.docx") { xml }
        r as Office.Preview.Document
        assertTrue(r.lines.first().isHeading)
        assertTrue(!r.lines.last().isHeading)
    }

    @Test
    fun a_zip_that_is_not_a_docx_is_refused_not_crashed() {
        val r = Office.read("salah.docx") { zip(mapOf("halo.txt" to "bukan dokumen")) }
        assertTrue(r is Office.Preview.Failed)
    }

    @Test
    fun a_document_with_no_text_says_so() {
        val r = Office.read("kosong.docx") { docx("", "   ") }
        assertTrue(r is Office.Preview.Failed)
        assertEquals("Dokumen ini tidak berisi teks", (r as Office.Preview.Failed).message)
    }

    @Test
    fun a_corrupt_zip_is_a_message_not_an_exception() {
        val r = Office.read("rusak.docx") { ByteArray(64) { 0x7f } }
        assertTrue(r is Office.Preview.Failed)
    }

    @Test
    fun an_unknown_extension_is_refused() {
        val r = Office.read("foto.jpg") { ByteArray(4) }
        assertTrue(r is Office.Preview.Failed)
    }

    // ------------------------------------------------------------------ xlsx

    @Test
    fun xlsx_shared_strings_are_resolved() {
        val rows = """<worksheet><sheetData>
            <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
            <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>15000</v></c></row>
            </sheetData></worksheet>"""
        val r = Office.read("harga.xlsx") { xlsx(listOf("Harga"), rows) }
        r as Office.Preview.Workbook
        assertEquals(listOf("Nama", "Harga"), r.sheets[0].rows[0])
        // The second row is the one that breaks when sharedStrings.xml is ignored:
        // "Apel" would render as "2".
        assertEquals(listOf("Apel", "15000"), r.sheets[0].rows[1])
    }

    @Test
    fun xlsx_cells_land_under_the_right_columns() {
        val rows = """<worksheet><sheetData>
            <row r="1"><c r="A1" t="s"><v>0</v></c><c r="D1"><v>99</v></c></row>
            </sheetData></worksheet>"""
        val r = Office.read("geser.xlsx") { xlsx(listOf("S"), rows) }
        r as Office.Preview.Workbook
        // A1 and D1: the gap has to be filled or "99" appears under "Nama".
        assertEquals(listOf("Nama", "", "", "99"), r.sheets[0].rows[0])
    }

    @Test
    fun xlsx_sheet_names_are_kept() {
        val rows = """<worksheet><sheetData><row r="1"><c r="A1"><v>1</v></c></row></sheetData></worksheet>"""
        val r = Office.read("dua.xlsx") { xlsx(listOf("Januari", "Februari"), rows) }
        r as Office.Preview.Workbook
        assertEquals(listOf("Januari", "Februari"), r.sheets.map { it.name })
    }

    @Test
    fun column_letters_are_base_26_not_ascii() {
        assertEquals(0, Office.columnIndex("A1"))
        assertEquals(2, Office.columnIndex("C7"))
        assertEquals(25, Office.columnIndex("Z9"))
        // AA is column 27, not 1: a naive A-Z mapping collapses every column past
        // Z onto the first twenty-six.
        assertEquals(26, Office.columnIndex("AA1"))
        assertEquals(27, Office.columnIndex("AB1"))
        assertEquals(701, Office.columnIndex("ZZ1"))
    }

    @Test
    fun a_zip_that_is_not_a_workbook_is_refused() {
        val r = Office.read("salah.xlsx") { zip(mapOf("x.txt" to "x")) }
        assertTrue(r is Office.Preview.Failed)
    }

    // ------------------------------------------------------------------ text

    @Test
    fun plain_text_keeps_lines_and_sheets_apart() {
        val doc = Office.read("a.docx") { docx("Satu", "Dua") }
        assertEquals("Satu\nDua", Office.plainText(doc))

        val rows = """<worksheet><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>"""
        val book = Office.read("b.xlsx") { xlsx(listOf("S1"), rows) }
        assertTrue(Office.plainText(book).startsWith("S1\n"))
    }

    @Test
    fun external_entities_are_not_resolved() {
        // XXE: a document that tries to pull /etc/passwd into its text must fail to
        // parse rather than read the file. The DOCTYPE declaration is refused.
        val evil = zip(
            mapOf(
                "word/document.xml" to
                    """<?xml version="1.0"?>
                    <!DOCTYPE w:document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
                    <w:document xmlns:w="x"><w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>""",
            ),
        )
        val r = Office.read("jahat.docx") { evil }
        assertTrue("an XXE document must not be read", r is Office.Preview.Failed)
    }
}
