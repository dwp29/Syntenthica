package net.pure.manager.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.pure.manager.fs.Storage
import net.pure.manager.root.Shell
import net.pure.manager.root.Terminal
import net.pure.manager.theme.PureThemeSpec

/** One size for command text, so output and input cannot drift apart. */
private val CommandText = 13.sp

/**
 * The terminal.
 *
 * Monospace on a dark card regardless of the theme, because that is what a terminal
 * is: the one screen where the app's palette would be actively unhelpful. Command
 * output is untrusted text from a shell, so it is drawn as plain text with no
 * interpretation.
 *
 * The parts that could be wrong are not here. Parsing, `cd`, history, the scrollback
 * cap and the refusal to run without root live in [Terminal], which the JVM tests
 * drive with `sh`. This composable only draws and forwards what was typed.
 */
@Composable
fun TerminalScreen(spec: PureThemeSpec, onClose: () -> Unit) {
    val scope = rememberCoroutineScope()
    val ink = Color(0xFF0E1116)
    val text = Color(0xFFD7E2EE)
    val dim = Color(0xFF7D8B99)
    val good = Color(0xFF6FD08C)
    val bad = Color(0xFFFF7A72)
    val action = Color(0xFF6FA8FF)

    // Probed once. A su binary that exists is not the same as a grant; the grant
    // arrives as a system dialog the first time a command runs, which is the moment
    // the user is looking at a terminal and expects one.
    var suPath by remember { mutableStateOf(Shell.suBinary()) }
    val terminal = remember { Terminal(binary = suPath, homeDirectory = Storage.homeDirectory()) }
    var input by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var version by remember { mutableIntStateOf(1) }
    val scroll = rememberScrollState()

    LaunchedEffect(version) { scroll.animateScrollTo(scroll.maxValue) }

    // The palette is ignored here on purpose; `spec` is still a parameter so the
    // screen keeps the same shape as every other one and can be moved without a
    // rewrite if the theme ever needs to reach the terminal.
    Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(
                Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(if (suPath != null) good else dim),
            )
            Text(
                if (suPath != null) "root tersedia: $suPath" else "tanpa root",
                style = MaterialTheme.typography.bodySmall,
                color = dim,
            )
            Spacer(Modifier.weight(1f))
            Text(
                "Periksa",
                style = MaterialTheme.typography.bodySmall,
                color = action,
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .clickable { suPath = Shell.suBinary() }
                    .padding(horizontal = 8.dp, vertical = 4.dp),
            )
            Text(
                "Tutup",
                style = MaterialTheme.typography.bodySmall,
                color = dim,
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .clickable(onClick = onClose)
                    .padding(horizontal = 8.dp, vertical = 4.dp),
            )
        }
        Spacer(Modifier.size(spec.cornerDp.dp / 2))
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(ink)
                .padding(12.dp),
        ) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = 200.dp, max = 360.dp)
                    .verticalScroll(scroll),
            ) {
                if (terminal.lines.isEmpty()) {
                    Text(
                        "Pure Manager terminal. Ketik help untuk perintah bawaan.\n" +
                            "Tanpa pty: top, vi dan program layar-penuh lain tidak akan " +
                            "tampil benar.",
                        style = TextStyle(fontFamily = FontFamily.Monospace, fontSize = CommandText),
                        color = dim,
                    )
                }
                terminal.lines.forEach { line ->
                    Text(
                        line.text,
                        style = TextStyle(fontFamily = FontFamily.Monospace, fontSize = CommandText),
                        color = when {
                            line.isCommand -> Color(0xFF9CDCFE)
                            line.isError -> bad
                            else -> text
                        },
                    )
                }
                if (busy) {
                    Text(
                        "menjalankan\u2026",
                        style = TextStyle(fontFamily = FontFamily.Monospace, fontSize = CommandText),
                        color = dim,
                    )
                }
            }
        }
        Spacer(Modifier.size(8.dp))
        Row(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(ink)
                .padding(horizontal = 10.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                terminal.prompt(),
                style = TextStyle(
                    fontFamily = FontFamily.Monospace,
                    fontSize = CommandText,
                    fontWeight = FontWeight.Medium,
                ),
                color = if (terminal.hasRoot) good else dim,
                modifier = Modifier
                    .widthIn(max = 148.dp)
                    .horizontalScroll(rememberScrollState()),
            )
            Spacer(Modifier.size(6.dp))
            BasicTextField(
                value = input,
                onValueChange = { input = it },
                singleLine = true,
                // BasicTextField does not inherit the Material type ramp, so the
                // size is stated once instead of being whatever the default is.
                textStyle = TextStyle(
                    fontFamily = FontFamily.Monospace,
                    color = text,
                    fontSize = CommandText,
                ),
                modifier = Modifier.weight(1f),
                decorationBox = { inner ->
                    if (input.isEmpty()) {
                        Text(
                            "ketik perintah",
                            style = TextStyle(
                                fontFamily = FontFamily.Monospace,
                                fontSize = CommandText,
                            ),
                            color = dim,
                        )
                    }
                    inner()
                },
            )
            Text(
                "\u23CE",
                style = MaterialTheme.typography.titleMedium,
                color = action,
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .clickable(enabled = !busy) {
                        val line = input
                        input = ""
                        busy = true
                        scope.launch {
                            val keepGoing = withContext(Dispatchers.IO) { terminal.submit(line) }
                            busy = false
                            version += 1
                            if (!keepGoing) onClose()
                        }
                    }
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            )
        }
        Spacer(Modifier.size(8.dp))
        Text(
            "Perintah berjalan dengan hak aplikasi biasa kecuali root tersedia. " +
                "Folder aktif tertulis di prompt; cd mengubahnya.",
            style = MaterialTheme.typography.bodySmall,
            color = dim,
        )
    }
}
