package net.pure.manager.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import net.pure.manager.doc.Office
import net.pure.manager.doc.PdfPages
import net.pure.manager.fs.FileEntry
import net.pure.manager.theme.PureThemeSpec

/**
 * Opening a .docx, .xlsx or .pdf inside the app.
 *
 * The browser could already hand a file to another app. That is the right default
 * and stays the default; this screen exists because the owner asked for the app to
 * open the things a file manager is expected to open, and because a phone without
 * Word installed cannot open a .docx at all.
 *
 * What it does not pretend to be: a Word layout engine. A .docx is shown as its
 * paragraphs, a .xlsx as a table of values, a .pdf as rendered pages. Fonts,
 * colours, images and page breaks are gone, and the screen says so above the text
 * rather than letting the owner wonder why their document looks different.
 */
@Composable
fun DocumentScreen(
    spec: PureThemeSpec,
    entry: FileEntry,
    onClose: () -> Unit,
) {
    val p = spec.palette
    val width = LocalConfiguration.current.screenWidthDp
    var preview by remember { mutableStateOf<Office.Preview?>(null) }
    var busy by remember { mutableStateOf(true) }
    var page by remember { mutableIntStateOf(0) }
    var pageCount by remember { mutableStateOf<Int?>(null) }
    var bitmap by remember { mutableStateOf<Bitmap?>(null) }
    var sheet by remember { mutableIntStateOf(0) }

    val isPdf = entry.extension == "pdf"

    LaunchedEffect(entry.path) {
        busy = true
        if (isPdf) {
            pageCount = withContext(Dispatchers.IO) { PdfPages.pageCount(File(entry.path)) }
        } else {
            preview = withContext(Dispatchers.IO) {
                val file = File(entry.path)
                Office.read(entry.name) { runCatching { file.readBytes() }.getOrDefault(ByteArray(0)) }
            }
        }
        busy = false
    }

    LaunchedEffect(entry.path, page, isPdf) {
        if (!isPdf) return@LaunchedEffect
        bitmap = null
        bitmap = withContext(Dispatchers.IO) {
            // Render at screen width: rendering at the PDF's own width for a phone
            // is several times the pixels for no visible gain.
            PdfPages.render(File(entry.path), page, (width * 2).coerceIn(600, 2000))
        }
    }

    Column(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    entry.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = p.onBackground,
                    maxLines = 1,
                )
                Text(
                    when {
                        busy -> "Membuka\u2026"
                        isPdf -> if (pageCount == null) "PDF tidak bisa dibuka" else "Halaman ${page + 1} dari $pageCount"
                        preview is Office.Preview.Document -> "Word \u00b7 teks saja"
                        preview is Office.Preview.Workbook -> "Excel \u00b7 nilai sel"
                        else -> (preview as? Office.Preview.Failed)?.message ?: ""
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = p.onSurfaceVariant,
                )
            }
            Text(
                "Tutup",
                style = MaterialTheme.typography.bodyLarge,
                color = p.accent,
                modifier = Modifier
                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                    .clickable(onClick = onClose)
                    .padding(horizontal = 10.dp, vertical = 6.dp),
            )
        }

        Spacer(Modifier.height(10.dp))

        // The limitation, on screen, before the content. A viewer that silently
        // drops layout gets blamed for the document, not for its limits.
        Text(
            if (isPdf) {
                "Dirender dengan PdfRenderer Android. Teks tidak bisa disalin, formulir " +
                    "tidak bisa diisi, dan berkas tidak bisa diedit."
            } else {
                "Hanya teks dan nilai sel. Font, warna, gambar, dan tabel bergabung " +
                    "tidak ditampilkan. .doc dan .xls lama tidak didukung."
            },
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
        )

        Spacer(Modifier.height(12.dp))

        when {
            busy -> Box(
                Modifier.fillMaxWidth().padding(vertical = 30.dp),
                contentAlignment = Alignment.Center,
            ) { androidx.compose.material3.CircularProgressIndicator(color = p.accent) }

            isPdf -> {
                Row(
                    Modifier.fillMaxWidth().padding(bottom = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    PageButton("Sebelum", enabled = page > 0) { page -= 1 }
                    Text(
                        "${page + 1}" + (pageCount?.let { " / $it" } ?: ""),
                        style = MaterialTheme.typography.bodyMedium,
                        color = p.onBackground,
                    )
                    PageButton(
                        "Berikut",
                        enabled = pageCount != null && page < pageCount!! - 1,
                    ) { page += 1 }
                }
                val bmp = bitmap
                if (bmp == null) {
                    Text("Halaman tidak bisa dirender.", style = MaterialTheme.typography.bodyMedium, color = p.onSurfaceVariant)
                } else {
                    Image(
                        bitmap = bmp.asImageBitmap(),
                        contentDescription = "Halaman ${page + 1}",
                        contentScale = ContentScale.FillWidth,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(androidx.compose.ui.graphics.Color.White),
                    )
                }
            }

            preview is Office.Preview.Document -> {
                val doc = preview as Office.Preview.Document
                GroupCard(spec) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .padding(14.dp)
                            .verticalScroll(rememberScrollState()),
                    ) {
                        doc.lines.forEach { line ->
                            Text(
                                line.text,
                                style = if (line.isHeading) {
                                    MaterialTheme.typography.titleMedium
                                } else {
                                    MaterialTheme.typography.bodyMedium
                                },
                                fontWeight = if (line.isHeading) FontWeight.SemiBold else FontWeight.Normal,
                                color = p.onBackground,
                                modifier = Modifier.padding(bottom = if (line.isHeading) 8.dp else 4.dp),
                            )
                        }
                    }
                }
            }

            preview is Office.Preview.Workbook -> {
                val book = preview as Office.Preview.Workbook
                val current = book.sheets.getOrNull(sheet) ?: book.sheets.first()
                if (book.sheets.size > 1) {
                    Row(
                        Modifier.fillMaxWidth().padding(bottom = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        book.sheets.forEachIndexed { i, s ->
                            val on = i == sheet
                            Text(
                                s.name,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (on) p.onAccent else p.accent,
                                modifier = Modifier
                                    .clip(RoundedCornerShape(spec.cornerDp.dp))
                                    .background(if (on) p.accent else p.surfaceVariant)
                                    .clickable { sheet = i }
                                    .padding(horizontal = 10.dp, vertical = 6.dp),
                            )
                        }
                    }
                }
                GroupCard(spec) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .padding(8.dp)
                            .verticalScroll(rememberScrollState()),
                    ) {
                        if (current.rows.isEmpty()) {
                            Text(
                                "Lembar ini kosong.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = p.onSurfaceVariant,
                            )
                        }
                        current.rows.forEachIndexed { index, row ->
                            Row(Modifier.fillMaxWidth()) {
                                row.forEach { cell ->
                                    Text(
                                        cell,
                                        style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                                        color = p.onBackground,
                                        maxLines = 2,
                                        modifier = Modifier
                                            .weight(1f)
                                            .padding(horizontal = 4.dp, vertical = 3.dp),
                                    )
                                }
                            }
                            if (index == 0) {
                                // A hairline under the first row reads as a header;
                                // Excel files usually put labels there.
                                Box(
                                    Modifier
                                        .fillMaxWidth()
                                        .height(0.5.dp)
                                        .background(p.separator),
                                )
                            }
                        }
                    }
                }
            }

            preview is Office.Preview.Failed -> MessageCard(
                spec = spec,
                title = "Tidak bisa ditampilkan",
                body = (preview as Office.Preview.Failed).message +
                    "\n\nCoba buka dengan aplikasi lain lewat menu panjang-tekan \u2192 Buka.",
            )
        }

        Spacer(Modifier.height(12.dp))
        Text(
            "Berkas tidak diubah. Untuk mengedit, pakai aplikasi lain.",
            style = MaterialTheme.typography.bodySmall,
            color = p.onSurfaceVariant,
        )
    }
}

@Composable
private fun PageButton(label: String, enabled: Boolean, onClick: () -> Unit) {
    val spec = net.pure.manager.theme.LocalPureSpec.current
    val p = spec.palette
    Text(
        label,
        style = MaterialTheme.typography.bodySmall,
        color = if (enabled) p.accent else p.onSurfaceVariant.copy(alpha = 0.5f),
        modifier = Modifier
            .clip(RoundedCornerShape(spec.cornerDp.dp))
            .background(if (enabled) p.surfaceVariant else p.surface)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 6.dp),
    )
}
