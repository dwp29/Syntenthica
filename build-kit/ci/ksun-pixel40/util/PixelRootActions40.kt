package com.rifsxd.ksunext.ui.util

import android.content.Context
import com.rifsxd.ksunext.ui.pixel.PixelActionResult40
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** User-initiated helpers only. No command arguments come from free-form input. */
private val pixelActionMutex40 = Mutex()

suspend fun runPixelAction40(context: Context, kind: String, action: String): PixelActionResult40 =
    pixelActionMutex40.withLock {
        withContext(Dispatchers.IO) {
            val allowed = when (kind) {
                "control" -> Regex("profile_(daily|gaming|revert)")
                "boost" -> Regex("status|remove_legacy|network_apply|network_restore|audio_restore|audio_apply:(8[4-9]|9[0-6])")
                else -> return@withContext PixelActionResult40(false, "Rejected: unknown helper")
            }
            if (!allowed.matches(action)) return@withContext PixelActionResult40(false, "Rejected: unknown action")
            runCatching {
                val asset = if (kind == "control") "synthetica-control40.sh" else "synthetica-boost40.sh"
                val script = context.assets.open(asset).bufferedReader().use { it.readText() }
                require(script.length < 100_000 && script.lineSequence().none { it == "SYNTHETICA_PIXEL40_SCRIPT" })
                // Test roots must never influence production execution. The argument
                // is separately allowlisted and the heredoc delimiter is literal.
                val cmd = "unset SP_SYSROOT SP_PROCSYS SP_STATE_DIR SP_SERVICE_DIR\n" +
                    "sh -s -- '$action' <<'SYNTHETICA_PIXEL40_SCRIPT'\n$script\nSYNTHETICA_PIXEL40_SCRIPT"
                createRootShell(true).use { shell ->
                    val out = ArrayList<String>()
                    val err = ArrayList<String>()
                    val result = shell.newJob().add(cmd).to(out, err).exec()
                    val all = out + err
                    val lines = all.take(300).map { it.take(600) }.toMutableList()
                    if (all.size > 300) lines.add("Output truncated; inspect device state before retrying.")
                    PixelActionResult40(result.isSuccess && all.size <= 300, lines.joinToString("\n").ifBlank { "No output from root shell" })
                }
            }.getOrElse { PixelActionResult40(false, "Root shell or bundled helper unavailable; inspect device state before retrying.") }
        }
    }
