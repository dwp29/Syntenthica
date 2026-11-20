package app.breakfast.manager.data

import android.content.Context

/**
 * Remembers whether loading libkernelsu.so killed the app last time.
 *
 * A native library can abort the process from its own initialiser. No Java
 * try/catch, no Thread.UncaughtExceptionHandler, and no amount of defensive code
 * in the caller can survive that: the process is gone before any Kotlin runs.
 *
 * Run 30 force-closed on start-up, and the only honest way to handle this class
 * of failure is to expect it:
 *
 *   1. Before the first load, write a marker saying "an attempt is in flight".
 *   2. Load. If the process dies here, the marker stays on disk.
 *   3. On the next start, a marker that was never cleared is proof that the last
 *      attempt killed the app, so the library is NOT loaded again. The ROOT page
 *      says so, and offers a button to try once more deliberately.
 *
 * The user is never left with an app that starts, crashes, and starts again with
 * no explanation.
 */
class NativeGuard(context: Context) {

    private val prefs = context.getSharedPreferences("breakfast.native", Context.MODE_PRIVATE)

    /** True when an attempt is recorded that never reached [clearAttempt]. */
    fun lastAttemptCrashed(): Boolean = prefs.getBoolean(KEY_IN_FLIGHT, false)

    fun markAttempt() {
        prefs.edit().putBoolean(KEY_IN_FLIGHT, true).apply()
    }

    fun clearAttempt() {
        prefs.edit().putBoolean(KEY_IN_FLIGHT, false).apply()
    }

    /** Set by the user pressing the retry button on the ROOT page. */
    fun userAllowedRetry(): Boolean = prefs.getBoolean(KEY_USER_RETRY, false)

    fun setUserAllowedRetry(allowed: Boolean) {
        prefs.edit().putBoolean(KEY_USER_RETRY, allowed).apply()
    }

    /**
     * Whether the library may be loaded in this process.
     *
     * - An in-flight marker means the previous attempt killed the app: refuse,
     *   unless the user has explicitly asked to try again.
     * - Otherwise allow it.
     */
    fun mayLoad(): Boolean = !lastAttemptCrashed() || userAllowedRetry()

    /** Clears both flags: the user accepts the risk once more. */
    fun allowOneRetry() {
        setUserAllowedRetry(true)
        clearAttempt()
    }

    companion object {
        private const val KEY_IN_FLIGHT = "load.in_flight"
        private const val KEY_USER_RETRY = "load.user_retry"
    }
}
