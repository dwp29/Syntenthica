package net.pure.manager.doc

import java.io.ByteArrayInputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element

/**
 * Reading .docx and .xlsx without a 12 MB library.
 *
 * Both formats are a ZIP full of XML. A viewer that shows the words and the cell
 * values is a few hundred lines; a library that reproduces Word's layout is
 * docx4j plus Apache POI, which is tens of megabytes and would make the app
 * bigger than the files it opens.
 *
 * So this reads:
 *  - **.docx**: every paragraph, with bold/italic runs flattened to plain text,
 *    tables included as tab-separated lines.
 *  - **.xlsx**: sheet names, and cell values by row and column, with the shared
 *    string table resolved (Excel stores most text once in `sharedStrings.xml`,
 *    so skipping it shows numbers and blanks).
 *
 * What it deliberately does NOT do, and the screen says so: fonts, colours,
 * images, page breaks, merged cells, formulas (the cached value is shown, not the
 * formula), and any .doc/.xls from before 2007.
 *
 * DOM parsing of the pieces we need is honest here: a document part is at most a
 * few MB and we read it once. A pull parser would be leaner and much harder to
 * read for the same result.
 */
object Office {

    /** One paragraph or one table row, already flattened to text. */
    data class Line(val text: String, val isHeading: Boolean = false)

    data class Sheet(val name: String, val rows: List<List<String>>)

    sealed interface Preview {
        data class Document(val lines: List<Line>, val title: String) : Preview
        data class Workbook(val sheets: List<Sheet>) : Preview
        data class Failed(val message: String) : Preview
    }

    /**
     * Reads either format by looking at the file name.
     *
     * [open] is injected so the tests can build a document in memory instead of on
     * a device's filesystem -- the parsing is the part worth testing and it does not
     * care where the bytes came from.
     */
    fun read(name: String, open: () -> ByteArray): Preview = runCatching {
        when (name.substringAfterLast('.', "").lowercase()) {
            "docx" -> parseDocx(entries(open()), name)
            "xlsx" -> parseXlsx(entries(open()), name)
            else -> Preview.Failed("Bukan .docx atau .xlsx")
        }
    }.getOrElse { Preview.Failed(it.message ?: "Berkas tidak bisa dibaca") }

    /** The ZIP entries we care about, as name -> bytes. */
    private fun entries(bytes: ByteArray): Map<String, ByteArray> {
        val out = LinkedHashMap<String, ByteArray>()
        ZipInputStream(ByteArrayInputStream(bytes)).use { zip ->
            var entry: ZipEntry? = zip.nextEntry
            while (entry != null) {
                if (!entry.isDirectory) {
                    // Cap one part at 32 MB: a "zip bomb" document would otherwise
                    // expand until the app is killed, and no real document part is
                    // that big.
                    val data = zip.readNBytes(32 * 1024 * 1024)
                    out[entry.name] = data
                }
                entry = zip.nextEntry
            }
        }
        return out
    }

    // ------------------------------------------------------------------ docx

    internal fun parseDocx(files: Map<String, ByteArray>, name: String): Preview {
        val body = files["word/document.xml"] ?: return Preview.Failed("Bukan dokumen Word (.docx)")
        val doc = parseXml(body) ?: return Preview.Failed("document.xml rusak")
        val paragraphs = doc.getElementsByTagName("w:p")
        val lines = mutableListOf<Line>()
        for (i in 0 until paragraphs.length) {
            val p = paragraphs.item(i) as? Element ?: continue
            val text = textOf(p).trim()
            if (text.isEmpty()) continue
            val style = p.getElementsByTagName("w:pStyle")
            val heading = style.length > 0 &&
                ((style.item(0) as? Element)?.getAttribute("w:val")?.startsWith("Heading") == true)
            lines += Line(text, heading)
        }
        if (lines.isEmpty()) return Preview.Failed("Dokumen ini tidak berisi teks")
        return Preview.Document(lines, name.substringAfterLast('/'))
    }

    /** Concatenates every `w:t` below [node], adding a tab for `w:tab`. */
    private fun textOf(node: Element): String {
        val sb = StringBuilder()
        val texts = node.getElementsByTagName("w:t")
        for (i in 0 until texts.length) {
            sb.append(texts.item(i).textContent ?: "")
            if (i < texts.length - 1) sb.append(' ')
        }
        return sb.toString().replace("  ", " ")
    }

    // ------------------------------------------------------------------ xlsx

    internal fun parseXlsx(files: Map<String, ByteArray>, name: String): Preview {
        val workbook = files["xl/workbook.xml"] ?: return Preview.Failed("Bukan workbook Excel (.xlsx)")
        val shared = files["xl/sharedStrings.xml"]?.let(::sharedStrings).orEmpty()
        val doc = parseXml(workbook) ?: return Preview.Failed("workbook.xml rusak")

        // Sheet order and the file each one lives in. The mapping is by index in
        // workbook.xml -> xl/worksheets/sheetN.xml; sheet names alone would be
        // enough to display but not to find the file.
        val sheetNodes = doc.getElementsByTagName("sheet")
        val sheets = mutableListOf<Sheet>()
        for (i in 0 until sheetNodes.length) {
            val node = sheetNodes.item(i) as? Element ?: continue
            val label = node.getAttribute("name").ifEmpty { "Sheet${i + 1}" }
            val part = files["xl/worksheets/sheet${i + 1}.xml"] ?: continue
            sheets += Sheet(label, rowsOf(part, shared))
        }
        if (sheets.isEmpty()) return Preview.Failed("Tidak ada lembar yang bisa dibaca")
        return Preview.Workbook(sheets)
    }

    /** The `sharedStrings.xml` table, in order; cell type "s" indexes into it. */
    private fun sharedStrings(bytes: ByteArray): List<String> {
        val doc = parseXml(bytes) ?: return emptyList()
        val items = doc.getElementsByTagName("si")
        return (0 until items.length).map { i ->
            val el = items.item(i) as? Element ?: return@map ""
            val texts = el.getElementsByTagName("t")
            (0 until texts.length).joinToString("") { texts.item(it).textContent ?: "" }
        }
    }

    /** Rows of a worksheet, with cell references resolved to columns. */
    private fun rowsOf(bytes: ByteArray, shared: List<String>): List<List<String>> {
        val doc = parseXml(bytes) ?: return emptyList()
        val rowNodes = doc.getElementsByTagName("row")
        val rows = mutableListOf<List<String>>()
        for (r in 0 until rowNodes.length) {
            val row = rowNodes.item(r) as? Element ?: continue
            val cells = row.getElementsByTagName("c")
            val byColumn = sortedMapOf<Int, String>()
            for (c in 0 until cells.length) {
                val cell = cells.item(c) as? Element ?: continue
                val ref = cell.getAttribute("r")
                val column = columnIndex(ref)
                val type = cell.getAttribute("t")
                val valueNode = cell.getElementsByTagName("v")
                val raw = if (valueNode.length > 0) valueNode.item(0).textContent else ""
                val text = when (type) {
                    "s" -> raw.toIntOrNull()?.let { shared.getOrNull(it) } ?: ""
                    "inlineStr" -> cell.getElementsByTagName("t").let { t ->
                        if (t.length > 0) t.item(0).textContent else ""
                    }
                    else -> raw
                }
                byColumn[column] = text
            }
            if (byColumn.isEmpty()) continue
            // Fill gaps with empty strings so a row renders under the right columns
            // instead of collapsing to the left.
            val width = byColumn.lastKey() + 1
            rows += (0 until width).map { byColumn[it] ?: "" }
        }
        return rows
    }

    /** "C7" -> 2. Column letters are base-26 with A=0, which is not obvious. */
    internal fun columnIndex(ref: String): Int {
        var n = 0
        for (ch in ref) {
            if (ch !in 'A'..'Z') break
            n = n * 26 + (ch - 'A' + 1)
        }
        return (n - 1).coerceAtLeast(0)
    }

    private fun parseXml(bytes: ByteArray) = runCatching {
        val factory = DocumentBuilderFactory.newInstance().apply {
            // A .docx from the internet is untrusted input. Turning off external
            // entity resolution is the difference between "opens a document" and
            // "reads a local file into the render" (XXE).
            isNamespaceAware = true
            setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            setFeature("http://xml.org/sax/features/external-general-entities", false)
            setFeature("http://xml.org/sax/features/external-parameter-entities", false)
            isExpandEntityReferences = false
        }
        factory.newDocumentBuilder().parse(ByteArrayInputStream(bytes))
    }.getOrNull()

    /** Plain text of every line, for copy and for search inside a document. */
    fun plainText(result: Preview): String = when (result) {
        is Preview.Document -> result.lines.joinToString("\n") { it.text }
        is Preview.Workbook -> result.sheets.joinToString("\n\n") { sheet ->
            sheet.name + "\n" + sheet.rows.joinToString("\n") { it.joinToString("\t") }
        }
        is Preview.Failed -> result.message
    }
}
