"""Apply narrowly scoped ZIP-preflight changes to the pinned Manager UI.

The daemon, native UAPI, root authentication, installer commands and kernel are
not changed. File-copy verification gates the existing installer entry points.
"""
from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one source anchor, found {count}')
    return text.replace(old, new, 1)


def patch_module(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    old = '''        // auto-detect: an AnyKernel3 zip picked here flashes as a kernel
        if (uris.size == 1 && ZipUtils.isAnyKernel3Zip(context, uris.first())) {
            navigator.navigate(FlashScreenDestination(FlashIt.FlashAnyKernel(uris.first())))
            return@rememberLauncherForActivityResult
        }

        viewModel.updateZipUris(uris)

        navigator.navigate(FlashScreenDestination(FlashIt.FlashModules(uris)))'''
    new = '''        // Classification happens off the UI thread in the bounded preflight.
        viewModel.updateZipUris(uris)

        navigator.navigate(FlashScreenDestination(FlashIt.FlashModules(uris, allowAnyKernel = uris.size == 1)))'''
    path.write_text(replace_once(text, old, new, 'module ZIP entry'), encoding='utf-8')


def patch_install(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    old = '''                // auto-detect: a module zip picked here flashes as module(s)
                if (ZipUtils.isAnyKernel3Zip(context, uri)) {
                    onSelected(InstallMethod.AnyKernel(uri))
                } else {
                    onFlashModulesRequested(uri)
                }'''
    new = '''                // The confirmation screen classifies the private copy safely.
                onSelected(InstallMethod.AnyKernel(uri))'''
    path.write_text(replace_once(text, old, new, 'install ZIP entry'), encoding='utf-8')


def patch_main(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    old = '''                        val flashIt = when {
                            component?.endsWith("FlashAnyKernel") == true -> FlashIt.FlashAnyKernel(uris.first())
                            uris.size == 1 && ZipUtils.isAnyKernel3Zip(applicationContext, uris.first()) ->
                                FlashIt.FlashAnyKernel(uris.first())
                            else -> FlashIt.FlashModules(uris)
                        }'''
    new = '''                        val flashIt = when {
                            component?.endsWith("FlashAnyKernel") == true && uris.size == 1 -> FlashIt.FlashAnyKernel(uris.first())
                            else -> FlashIt.FlashModules(uris, allowAnyKernel = uris.size == 1)
                        }'''
    path.write_text(replace_once(text, old, new, 'external ZIP entry'), encoding='utf-8')


def patch_flash(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, 'import com.rifsxd.ksunext.R\n',
                        'import com.rifsxd.ksunext.R\nimport com.rifsxd.ksunext.ksuApp\n', 'application context import')
    text = replace_once(text, 'import kotlinx.coroutines.Dispatchers\n',
                        'import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.NonCancellable\n', 'cleanup import')
    text = replace_once(text, '''    uris: List<Uri>,
    onStdout: (String) -> Unit,
    onStderr: (String) -> Unit
): FlashResult {
    for (uri in uris) {
        flashModule(uri, onStdout, onStderr).apply {''', '''    uris: List<Uri>,
    approvedHashes: List<String>,
    onStdout: (String) -> Unit,
    onStderr: (String) -> Unit
): FlashResult {
    if (uris.isEmpty() || uris.size != approvedHashes.size) {
        val message = ksuApp.getString(R.string.zip31_changed)
        onStderr(message)
        return FlashResult(1, message, false)
    }
    for ((index, uri) in uris.withIndex()) {
        flashModule(uri, approvedHashes[index], onStdout, onStderr).apply {''', 'sequential module digest')
    text = replace_once(text, '''                return FlashResult(code, err, showReboot)
''', '''                val partial = if (index > 0) ksuApp.getString(R.string.zip31_partial, index) else ""
                if (partial.isNotEmpty()) onStderr(partial)
                return FlashResult(code, listOf(err, partial).filter { it.isNotEmpty() }.joinToString("\\n"), showReboot)
''', 'partial module warning')
    text = replace_once(text, '''    BackHandler(enabled = flashing == FlashingStatus.FLASHING) {
        // Disable back button if flashing is running
    }
''', '''    var preflightActive by remember { mutableStateOf(false) }
    BackHandler(enabled = flashing == FlashingStatus.FLASHING && !preflightActive) {
        // Do not interrupt an installer once it starts.
    }
    BackHandler(enabled = preflightActive) { navigator.popBackStack() }
''', 'allow cancellation during preflight')
    marker_start = '    LaunchedEffect(flashIt) {\n'
    marker_end = '    LaunchedEffect(confirmed, pendingFlashIt) {\n'
    if text.count(marker_start) != 1 or text.count(marker_end) != 1:
        raise RuntimeError('flash confirmation block anchors changed')
    start, end = text.index(marker_start), text.index(marker_end)
    if start >= end:
        raise RuntimeError('flash confirmation block order changed')
    text = text[:start] + '''    LaunchedEffect(flashIt) {
        when (flashIt) {
            is FlashIt.FlashModules, is FlashIt.FlashAnyKernel -> if (!confirmed) {
                preflightActive = true
                val approved = try {
                    prepareZipInstall(context, flashIt, confirmDialog)
                } finally {
                    preflightActive = false
                }
                if (approved == null) {
                    navigator.popBackStack()
                } else {
                    pendingFlashIt = approved
                    confirmed = true
                }
            }
            else -> {
                confirmed = true
                pendingFlashIt = flashIt
            }
        }
    }

''' + text[end:]
    old_start = '''        hasFlashed = true
        withContext(Dispatchers.IO) {
            flashIt(pendingFlashIt!!, onStdout = {'''
    new_start = '''        hasFlashed = true
        val approved = pendingFlashIt!!
        try {
            withContext(Dispatchers.IO) {
                flashIt(approved, onStdout = {'''
    text = replace_once(text, old_start, new_start, 'verified flash start')
    old_end = '''                flashing = if (code == 0) FlashingStatus.SUCCESS else FlashingStatus.FAILED
            }
        }
    }

    Scaffold('''
    new_end = '''                flashing = if (code == 0) FlashingStatus.SUCCESS else FlashingStatus.FAILED
                }
            }
        } finally {
            withContext(NonCancellable + Dispatchers.IO) { deleteApprovedZipStages(context, approved) }
        }
    }

    val resolvedFlashIt = pendingFlashIt ?: flashIt
    Scaffold('''
    text = replace_once(text, old_end, new_end, 'verified flash cleanup')
    for kind in ('FlashModules', 'FlashAnyKernel'):
        for state in ('SUCCESS', 'FAILED'):
            old = f'if (flashIt is FlashIt.{kind} && (flashing == FlashingStatus.{state}))'
            new = f'if (resolvedFlashIt is FlashIt.{kind} && (flashing == FlashingStatus.{state}))'
            text = replace_once(text, old, new, f'{kind} {state} display')
    text = replace_once(text, '''                text = if (developerOptionsEnabled) logContent.toString() else text,''',
                        '''                text = if (preflightActive) stringResource(R.string.zip31_checking)
                    else if (developerOptionsEnabled) logContent.toString() else text,''', 'checking state')
    text = replace_once(text, '''    data class FlashModules(val uris: List<Uri>) : FlashIt()

    data class FlashAnyKernel(val uri: Uri) : FlashIt()''', '''    data class FlashModules(
        val uris: List<Uri>, val allowAnyKernel: Boolean = false, val approvedHashes: List<String> = emptyList()
    ) : FlashIt()

    data class FlashAnyKernel(val uri: Uri, val approvedHash: String = "") : FlashIt()''', 'approved digest state')
    text = replace_once(text, '''        is FlashIt.FlashAnyKernel -> flashAnyKernelZip(
            flashIt.uri,
            onStdout,''', '''        is FlashIt.FlashAnyKernel -> flashAnyKernelZip(
            flashIt.uri,
            flashIt.approvedHash,
            onStdout,''', 'kernel digest handoff')
    text = replace_once(text, 'flashModulesSequentially(flashIt.uris, onStdout, onStderr)',
                        'flashModulesSequentially(flashIt.uris, flashIt.approvedHashes, onStdout, onStderr)', 'module digest handoff')
    path.write_text(text, encoding='utf-8')


def patch_dialog(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, 'import androidx.compose.foundation.layout.Box\n',
                        'import androidx.compose.foundation.rememberScrollState\n'
                        'import androidx.compose.foundation.verticalScroll\n'
                        'import androidx.compose.foundation.layout.heightIn\n'
                        'import androidx.compose.foundation.layout.Box\n', 'scrollable confirmation imports')
    text = replace_once(text, 'Text(text = visuals.content)',
                        'Text(text = visuals.content, modifier = Modifier.heightIn(max = 390.dp).verticalScroll(rememberScrollState()))',
                        'scrollable confirmation text')
    old = '''                .onEach { result ->
                    awaitContinuation?.let {
                        awaitContinuation = null
                        if (it.isActive) {
                            it.resume(result)
                        }
                    }
                }
                .onEach { hide() }
'''
    new = '''                .onEach { result ->
                    // Hide the completed dialog before resuming; the next ZIP
                    // may immediately ask for a separate confirmation.
                    visible.value = false
                    awaitContinuation?.let {
                        awaitContinuation = null
                        if (it.isActive) {
                            it.resume(result)
                        }
                    }
                }
'''
    path.write_text(replace_once(text, old, new, 'sequential confirmation ordering'), encoding='utf-8')


def patch_ksu_cli(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, 'import com.rifsxd.ksunext.Natives\n',
                        'import com.rifsxd.ksunext.Natives\nimport com.rifsxd.ksunext.R\nimport com.rifsxd.ksunext.ui.preflight.AndroidZipPreflight\n',
                        'installer hash guard imports')
    start_anchor = 'fun flashModule(\n'
    end_anchor = 'fun runModuleAction(\n'
    if text.count(start_anchor) != 1 or text.count(end_anchor) != 1:
        raise RuntimeError('module installer anchors changed')
    start, end = text.index(start_anchor), text.index(end_anchor)
    if start >= end:
        raise RuntimeError('module installer anchors out of order')
    replacement = '''fun flashModule(
    uri: Uri,
    approvedSha256: String,
    onStdout: (String) -> Unit,
    onStderr: (String) -> Unit
): FlashResult {
    val file = runCatching { File.createTempFile("module31-", ".zip", ksuApp.cacheDir) }.getOrNull()
    if (file == null || !AndroidZipPreflight.copyVerified(ksuApp, uri, file, approvedSha256)) {
        val message = ksuApp.getString(R.string.zip31_changed)
        onStderr(message)
        return FlashResult(1, message, false)
    }
    try {
        val cmd = "module install ${file.absolutePath}"
        val result = flashWithIO("${getKsuDaemonPath()} $cmd", onStdout, onStderr)
        Log.i("KernelSU", "install module $uri result: $result")
        return FlashResult(result)
    } finally {
        file.delete()
    }
}

'''
    text = text[:start] + replacement + text[end:]
    text = replace_once(text, '''fun flashAnyKernelZip(
    uri: Uri,
    onStdout:''', '''fun flashAnyKernelZip(
    uri: Uri,
    approvedSha256: String,
    onStdout:''', 'kernel installer signature')
    old = '''    val resolver = ksuApp.contentResolver

    val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
    val tmpFile = File(ksuApp.cacheDir, "anykernel_${timestamp}.zip")
    resolver.openInputStream(uri).use { input ->
        tmpFile.outputStream().use { out ->
            input?.copyTo(out)
        }
    }

    val destZip = tmpFile.absolutePath'''
    new = '''    val tmpFile = runCatching { File.createTempFile("anykernel31-", ".zip", ksuApp.cacheDir) }.getOrNull()
    if (tmpFile == null || !AndroidZipPreflight.copyVerified(ksuApp, uri, tmpFile, approvedSha256)) {
        val message = ksuApp.getString(R.string.zip31_changed)
        onStderr(message)
        return FlashResult(1, message, false)
    }

    val destZip = tmpFile.absolutePath'''
    text = replace_once(text, old, new, 'kernel verified private copy')
    text = replace_once(text, 'val destDirFile = File(ksuApp.cacheDir, "anykernel3_${timestamp}")',
                        'val destDirFile = File(ksuApp.cacheDir, tmpFile.name + ".work")', 'unique kernel work directory')
    text = replace_once(text, r'''                $BUSYBOX unzip -p -o '$destZip' "META-INF/com/google/android/update-binary" > '$destDir/update-binary' 2>/dev/null && \
                cp '$destZip' '$destDir/$destZipName' 2>/dev/null || true && \
''', r'''                cp '$destZip' '$destDir/$destZipName' && \
                echo '$approvedSha256  $destDir/$destZipName' | $BUSYBOX sha256sum -c - >/dev/null && \
                $BUSYBOX unzip -p -o '$destDir/$destZipName' "META-INF/com/google/android/update-binary" > '$destDir/update-binary' 2>/dev/null && \
''', 'verify exact kernel installer copy')
    text = replace_once(text, '''    val result = flashWithIO_ak3(cmd, onStdout, onStderr)
    try {
        return FlashResult(result, result.isSuccess)
    } finally {
''', '''    try {
        val result = flashWithIO_ak3(cmd, onStdout, onStderr)
        return FlashResult(result, result.isSuccess)
    } finally {
        tmpFile.delete()
''', 'kernel cleanup on failure')
    path.write_text(text, encoding='utf-8')
