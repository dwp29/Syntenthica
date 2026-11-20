package com.rifsxd.ksunext

/**
 * Bridge to libkernelsu.so.
 *
 * This package name is not a mistake: JNI looks symbols up by their
 * fully-qualified class name, and the library exports
 * Java_com_rifsxd_ksunext_Natives_*. Moving this class would break the binding at
 * runtime, not at compile time, so it stays where the library expects it.
 *
 * ---------------------------------------------------------------------------
 * Why every getter is optional at the call site
 *
 * The previous version put System.loadLibrary inside a `by lazy` and caught the
 * throw inside the getters. That is not enough: a `by lazy` block that throws is
 * retried on every access, and on Android an unsatisfied native method raises
 * UnsatisfiedLinkError, which is an Error rather than an Exception. Wrapping a
 * call in try/catch outside the lazy is fine, but the library also runs its own
 * initialiser when it loads, and that can call exit() or abort() when the kernel
 * is not KernelSU - which no try/catch can intercept. That is how run 30
 * force-closed on start-up.
 *
 * So the library is now loaded exactly once, from a place that is allowed to
 * fail, and nothing in this file runs unless [probeLoaded] has already returned
 * true for this process. If the load fails, every getter returns null and the
 * ROOT page says "tidak bisa dipastikan" - which is the truth.
 */
object Natives {

    /** Set once per process by [load]. Never reset: a failed load stays failed. */
    @Volatile
    private var loaded = false

    /**
     * Attempts the one System.loadLibrary call.
     *
     * Returns true only when the library really is in this process. Callers must
     * treat false as "this device has no KernelSU library", not as an error.
     */
    fun load(): Boolean {
        if (loaded) return true
        return try {
            System.loadLibrary("kernelsu")
            loaded = true
            true
        } catch (e: Throwable) {
            // UnsatisfiedLinkError and friends are Errors, not Exceptions.
            loaded = false
            false
        }
    }

    val isLoaded: Boolean get() = loaded

    // ------------------------------------------------------------------ getters
    // Each one is only reached when load() returned true, and each is still
    // guarded: a native call can fail for reasons the loader cannot predict.

    fun versionOrNull(): String? = guarded(loaded) { getVersion() }

    fun kernelUapiOrNull(): Int? = guarded(loaded) { getKernelUAPIVersion() }

    fun managerUapiOrNull(): Int? = guarded(loaded) { getManagerUAPIVersion() }

    fun suEnabledOrNull(): Boolean? = guarded(loaded) { isSuEnabled() }

    fun superuserCountOrNull(): Int? = guarded(loaded) { getSuperuserCount() }

    fun safeModeOrNull(): Boolean? = guarded(loaded) { isSafeMode() }

    fun managerProcessOrNull(): Boolean? = guarded(loaded) { isManager() }

    private inline fun <T> guarded(enabled: Boolean, block: () -> T): T? = try {
        if (enabled) block() else null
    } catch (e: Throwable) {
        null
    }

    // The JNI entry points. Their names must match the exported symbols exactly.
    private external fun getVersion(): String?
    private external fun getKernelUAPIVersion(): Int
    private external fun getManagerUAPIVersion(): Int
    private external fun isSuEnabled(): Boolean
    private external fun getSuperuserCount(): Int
    private external fun isSafeMode(): Boolean
    private external fun isManager(): Boolean
}
