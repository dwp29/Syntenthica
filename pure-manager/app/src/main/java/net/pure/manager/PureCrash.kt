package net.pure.manager

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Crash reporting that does not phone home.
 *
 * Written because the owner's report was "force close" with nothing else: no
 * logcat, no stack trace, and this sandbox cannot download CI logs or artifacts.
 * Guessing at a total launch failure is how a fix becomes three more failures.
 *
 * The report is a small JSON file inside the app's own directory. Nothing is
 * uploaded anywhere. The Settings screen shows it and can copy it to the
 * clipboard, so the owner can paste it here in one step.
 *
 * Deliberately installed as an uncaught-exception *delegate* rather than a
 * handler: the default handler still runs afterwards, so the system crash dialog
 * and any tombstone behave exactly as they would without this class.
 */
object PureCrash {

    private const val FILE_NAME = "last-crash.json"
    private const val MAX_FRAMES = 40

    /** Records the throwable, then lets the platform handler proceed. */
    fun install(context: Context) {
        val app = context.applicationContext
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching { write(app, thread, error) }
            previous?.uncaughtException(thread, error)
        }
    }

    private fun write(context: Context, thread: Thread, error: Throwable) {
        val frames = error.stackTrace
            .take(MAX_FRAMES)
            .joinToString("\n    at ") { "${it.className}.${it.methodName}(${it.fileName}:${it.lineNumber})" }

        val json = JSONObject().apply {
            put("time", SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date()))
            put("exception", error.javaClass.name)
            put("message", error.message ?: "")
            put("thread", thread.name)
            put("android", "API ${Build.VERSION.SDK_INT} (${Build.VERSION.RELEASE})")
            put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
            put("appVersion", context.appVersionName())
            put("stack", "    at $frames".trim())
            // The root cause is usually more useful than the wrapper: Haze wraps a
            // device blur failure inside an IllegalArgumentException, and the
            // interesting part is the cause.
            error.cause?.let { c ->
                put("cause", "${c.javaClass.name}: ${c.message ?: ""}")
            }
        }
        File(context.filesDir, FILE_NAME).writeText(json.toString(2))
    }

    /** The last crash as text, or null if the app has not crashed since install. */
    fun read(context: Context): String? =
        File(context.filesDir, FILE_NAME).takeIf { it.isFile }?.readText()

    /**
     * True only if the recorded crash came from the build that is running now.
     *
     * Without this, a report left behind by an older version would put every
     * later launch into safe mode with blur off -- the owner would see a working
     * fix and conclude the glass effect is broken. A crash from a previous build
     * stays readable in Setelan but no longer changes how the app starts.
     */
    fun crashedOnThisVersion(context: Context): Boolean {
        val text = read(context) ?: return false
        val recorded = runCatching { JSONObject(text).optString("appVersion") }
            .getOrDefault("")
        return recorded.isNotEmpty() && recorded == context.appVersionName()
    }

    fun clear(context: Context) {
        File(context.filesDir, FILE_NAME).delete()
    }

    private fun Context.appVersionName(): String =
        runCatching {
            packageManager.getPackageInfo(packageName, 0).versionName ?: "?"
        }.getOrDefault("?")
}
