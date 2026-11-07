package com.rifsxd.ksunext

import android.content.Context
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.ui.component.rememberConfirmDialog
import com.rifsxd.ksunext.ui.preflight.AndroidZipPreflight
import com.rifsxd.ksunext.ui.screen.FlashIt
import com.rifsxd.ksunext.ui.screen.deleteApprovedZipStages
import com.rifsxd.ksunext.ui.screen.prepareZipInstall
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

private enum class Demo { MODULE, KERNEL, INVALID, TAMPER, BATCH, UNEXPECTED_KERNEL }

/** Exercises the real preflight/confirmation/verified-copy code, never a root installer. */
@Composable
internal fun PreviewPreflightDemo(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var running by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf("Choose a sample. No installation will occur.") }
    val dialog = rememberConfirmDialog()
    fun runDemo(kind: Demo) {
        if (running) return
        running = true
        result = "Checking sample…"
        scope.launch {
            val inputs = mutableListOf<File>()
            var approved: FlashIt? = null
            try {
                withContext(Dispatchers.IO) {
                    inputs.add(createSample(context, kind))
                    if (kind == Demo.BATCH) inputs.add(createSample(context, Demo.MODULE))
                }
                val requested = FlashIt.FlashModules(inputs.map(Uri::fromFile), allowAnyKernel = kind != Demo.UNEXPECTED_KERNEL)
                approved = prepareZipInstall(context, requested, dialog)
                val selection = approved
                result = if (selection == null) {
                    "Blocked or canceled; no installation occurred."
                } else {
                    val verified = withContext(Dispatchers.IO) { verifySample(context, selection, kind == Demo.TAMPER) }
                    when {
                        kind == Demo.TAMPER && !verified -> "Tamper blocked; no installation occurred."
                        verified -> "Verified approved copy; no installation occurred."
                        else -> "Verification failed; no installation occurred."
                    }
                }
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                result = "Preview test failed; no installation occurred."
            } finally {
                withContext(NonCancellable + Dispatchers.IO) {
                    approved?.let { deleteApprovedZipStages(context, it) }
                    inputs.forEach { it.delete() }
                }
                running = false
            }
        }
    }
    Column(
        modifier = Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("ZIP preflight preview", style = MaterialTheme.typography.headlineSmall)
        Text("PREVIEW ONLY — these samples never invoke an installer or root.")
        Button(onClick = { runDemo(Demo.MODULE) }, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Test module ZIP") }
        Button(onClick = { runDemo(Demo.KERNEL) }, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Test kernel ZIP") }
        Button(onClick = { runDemo(Demo.INVALID) }, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Test unknown ZIP") }
        Button(onClick = { runDemo(Demo.TAMPER) }, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Test changed ZIP") }
        Button(onClick = { runDemo(Demo.BATCH) }, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Test two modules") }
        Button(onClick = { runDemo(Demo.UNEXPECTED_KERNEL) }, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Test unexpected kernel") }
        Text(result, style = MaterialTheme.typography.bodyMedium)
        TextButton(onClick = onBack, enabled = !running) { Text("Back to preview") }
    }

}

private fun createSample(context: Context, kind: Demo): File {
    val file = File.createTempFile("preview-sample-", ".zip", context.cacheDir)
    try {
        ZipOutputStream(file.outputStream()).use { zip ->
            fun entry(name: String, content: String) {
                zip.putNextEntry(ZipEntry(name))
                zip.write(content.toByteArray())
                zip.closeEntry()
            }
            when (kind) {
                Demo.KERNEL, Demo.UNEXPECTED_KERNEL -> {
                    entry("anykernel.sh", "#!/bin/sh\n# preview, never executed\n")
                    entry("META-INF/com/google/android/update-binary", "#!/bin/sh\n# preview, never executed\n")
                }
                Demo.INVALID -> entry("readme.txt", "No recognized markers")
                else -> entry("module.prop", "id=preview.module\nname=Example module\nversion=1\nauthor=Preview\n")
            }
        }
        return file
    } catch (error: Exception) {
        file.delete()
        throw error
    }
}

private fun verifySample(context: Context, selection: FlashIt, tamper: Boolean): Boolean {
    val approved = when (selection) {
        is FlashIt.FlashModules -> selection.uris.zip(selection.approvedHashes)
        is FlashIt.FlashAnyKernel -> listOf(selection.uri to selection.approvedHash)
    }
    if (approved.isEmpty()) return false
    return approved.all { (uri, sha) ->
        if (tamper) File(uri.path ?: return@all false).appendText("changed")
        val destination = File.createTempFile("preview-copy-", ".zip", context.cacheDir)
        try { AndroidZipPreflight.copyVerified(context, uri, destination, sha) }
        finally { destination.delete() }
    }
}
