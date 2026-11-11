package net.pure.manager.doc

import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import java.io.File

/**
 * PDF pages as bitmaps, through Android's own `PdfRenderer`.
 *
 * No library. `PdfRenderer` has shipped since Android 5, renders a page at a
 * requested scale, and costs nothing in APK size. It cannot extract text, edit,
 * annotate or fill forms -- PDFBox could, for about 3 MB and a licence review --
 * so this is a viewer and the screen says so.
 *
 * Two constraints worth respecting:
 *
 *  - A renderer and its file descriptor must be closed, or the next open of the
 *    same PDF fails with "file already open". Everything here is inside `use`.
 *  - Rendering every page of a 400-page PDF to bitmaps is a memory bomb. Only the
 *    page being shown is rendered, and the bitmap is released when the page changes.
 */
object PdfPages {

    /** Page count, or null if the file is not a readable PDF. */
    fun pageCount(file: File): Int? = open(file) { it.pageCount }

    /**
     * Renders one page at [widthPx] wide, keeping the aspect ratio.
     *
     * Returns null rather than throwing: a damaged PDF is a message on screen, not
     * a crash. The bitmap is trimmed to the actual page instead of the padded
     * render surface.
     */
    fun render(file: File, index: Int, widthPx: Int): Bitmap? = open(file) { renderer ->
        if (index !in 0 until renderer.pageCount) return@open null
        renderer.openPage(index).use { page ->
            val height = (widthPx.toFloat() * page.height / page.width).toInt().coerceAtLeast(1)
            val bitmap = Bitmap.createBitmap(widthPx, height, Bitmap.Config.ARGB_8888)
            // A white page: the default bitmap is transparent, and a PDF with no
            // drawn background renders as black text on nothing.
            bitmap.eraseColor(android.graphics.Color.WHITE)
            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            bitmap
        }
    }

    private fun <T> open(file: File, block: (PdfRenderer) -> T): T? {
        if (!file.isFile) return null
        return runCatching {
            ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                PdfRenderer(descriptor).use(block)
            }
        }.getOrNull()
    }
}
