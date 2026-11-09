package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.net.Uri
import android.text.format.Formatter
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.component.ConfirmDialogHandle
import com.rifsxd.ksunext.ui.component.ConfirmResult
import com.rifsxd.ksunext.ui.preflight.AndroidZipPreflight
import com.rifsxd.ksunext.ui.preflight.PackageKind
import com.rifsxd.ksunext.ui.preflight.PackageReport
import com.rifsxd.ksunext.ui.preflight.PreflightException
import com.rifsxd.ksunext.ui.preflight.PreflightProblem
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

/** Preflight, user confirmation, then hand off only private, hash-pinned copies. */
internal suspend fun prepareZipInstall(
    context: Context,
    request: FlashIt,
    dialog: ConfirmDialogHandle,
): FlashIt? {
    val uris = when (request) {
        is FlashIt.FlashModules -> request.uris
        is FlashIt.FlashAnyKernel -> listOf(request.uri)
        else -> return null
    }
    suspend fun refuse(message: String) {
        dialog.awaitConfirm(
            title = context.getString(R.string.zip31_blocked_title),
            content = message,
            confirm = context.getString(android.R.string.ok),
            dismiss = context.getString(android.R.string.cancel),
        )
    }
    if (uris.isEmpty() || uris.size > AndroidZipPreflight.MAX_BATCH) {
        refuse(context.getString(R.string.zip31_batch_limit, AndroidZipPreflight.MAX_BATCH))
        return null
    }
    val reports = mutableListOf<PackageReport>()
    var handedOff = false
    try {
        withContext(Dispatchers.IO) { AndroidZipPreflight.pruneStale(context) }
        var batchBytes = 0L
        for (uri in uris) {
            val remaining = AndroidZipPreflight.MAX_BATCH_BYTES - batchBytes
            if (remaining <= 0) throw PreflightException(PreflightProblem.TOO_LARGE)
            // Add from inside the IO block so cancellation cannot orphan a finished stage.
            withContext(Dispatchers.IO) { reports.add(AndroidZipPreflight.inspect(context, uri, remaining)) }
            batchBytes += reports.last().size
        }
        val kernels = reports.count { it.kind == PackageKind.ANYKERNEL }
        if (kernels > 0 && reports.size != 1) {
            refuse(context.getString(R.string.zip31_kernel_batch))
            return null
        }
        if (kernels > 0 && request is FlashIt.FlashModules && !request.allowAnyKernel) {
            refuse(context.getString(R.string.zip31_kernel_not_expected))
            return null
        }
        for ((index, report) in reports.withIndex()) {
            val title = context.getString(
                if (report.kind == PackageKind.ANYKERNEL) R.string.zip31_confirm_kernel else R.string.zip31_confirm_module,
                index + 1, reports.size,
            )
            if (dialog.awaitConfirm(title = title, content = reportText(context, report, reports.size),
                    confirm = context.getString(R.string.zip31_continue),
                    dismiss = context.getString(android.R.string.cancel)) != ConfirmResult.Confirmed) return null
        }
        val staged = reports.map { Uri.fromFile(it.file) }
        val approved = if (reports.singleOrNull()?.kind == PackageKind.ANYKERNEL) {
            FlashIt.FlashAnyKernel(staged.single(), reports.single().sha256)
        } else {
            FlashIt.FlashModules(staged, approvedHashes = reports.map { it.sha256 })
        }
        handedOff = true
        return approved
    } catch (error: CancellationException) {
        throw error
    } catch (error: PreflightException) {
        refuse(context.getString(problemMessage(error.problem)))
        return null
    } catch (_: Exception) {
        refuse(context.getString(R.string.zip31_unreadable))
        return null
    } finally {
        if (!handedOff) withContext(NonCancellable + Dispatchers.IO) {
            AndroidZipPreflight.deleteReports(context, reports)
        }
    }
}

private fun reportText(context: Context, report: PackageReport, total: Int): String = buildString {
    val unavailable = context.getString(R.string.device31_unavailable)
    appendLine(context.getString(R.string.zip31_file, report.displayName))
    appendLine(context.getString(R.string.zip31_type,
        context.getString(if (report.kind == PackageKind.MODULE) R.string.zip31_kind_module else R.string.zip31_kind_kernel)))
    appendLine(context.getString(R.string.zip31_size, Formatter.formatFileSize(context, report.size)))
    appendLine(context.getString(R.string.zip31_sha, report.sha256))
    if (report.kind == PackageKind.MODULE) {
        appendLine(context.getString(R.string.zip31_id, report.metadata["id"] ?: unavailable))
        appendLine(context.getString(R.string.zip31_name, report.metadata["name"]?.takeIf { it.isNotBlank() } ?: unavailable))
        appendLine(context.getString(R.string.zip31_version, report.metadata["version"]?.takeIf { it.isNotBlank() } ?: unavailable))
        appendLine(context.getString(R.string.zip31_author, report.metadata["author"]?.takeIf { it.isNotBlank() } ?: unavailable))
    }
    appendLine()
    if (total > 1) appendLine(context.getString(R.string.zip31_batch_warning))
    appendLine(context.getString(if (report.kind == PackageKind.MODULE) R.string.zip31_module_warning else R.string.zip31_kernel_warning))
    append(context.getString(R.string.zip31_not_security_scan))
}

private fun problemMessage(problem: PreflightProblem): Int = when (problem) {
    PreflightProblem.UNREADABLE -> R.string.zip31_unreadable
    PreflightProblem.TOO_LARGE -> R.string.zip31_too_large
    PreflightProblem.TOO_MANY_ENTRIES -> R.string.zip31_too_many
    PreflightProblem.UNSAFE_PATH, PreflightProblem.DUPLICATE_PATH -> R.string.zip31_unsafe_path
    PreflightProblem.INVALID_ZIP -> R.string.zip31_invalid
    PreflightProblem.UNSUPPORTED_ZIP -> R.string.zip31_unsupported
    PreflightProblem.UNKNOWN_TYPE -> R.string.zip31_unknown
    PreflightProblem.AMBIGUOUS_TYPE -> R.string.zip31_ambiguous
    PreflightProblem.MISSING_INSTALLER -> R.string.zip31_missing_installer
    PreflightProblem.INVALID_METADATA -> R.string.zip31_bad_metadata
}

internal fun deleteApprovedZipStages(context: Context, approved: FlashIt) {
    val uris = when (approved) {
        is FlashIt.FlashModules -> approved.uris
        is FlashIt.FlashAnyKernel -> listOf(approved.uri)
        else -> emptyList()
    }
    AndroidZipPreflight.deleteStagedUris(context, uris)
}
