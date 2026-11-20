package com.rifsxd.ksunext

/**
 * Bridge to libkernelsu.so.
 *
 * This package name is not a mistake or a leftover: JNI looks symbols up by
 * their fully-qualified class name, and the library exports
 * Java_com_rifsxd_ksunext_Natives_getKernelUAPIVersion. Moving this class would
 * break the binding at runtime, not at compile time, so it stays where the
 * library expects it.
 *
 * The library was already inside this APK and never called. On the reporting
 * device the app said "tidak punya su" and "tidak ada pengelola root" while
 * TUNING showed schedutil nodes readable and sysfs in use - things that do not
 * happen on an unrooted phone. Asking the library directly is both more accurate
 * than guessing from a shell and cheaper than a su round trip.
 *
 * Every getter can throw on a device without KernelSU, so all access goes
 * through [probe], which turns a failure into null rather than a crash.
 */
object Natives {

    /**
     * True when libkernelsu.so loaded. Loading is attempted once, lazily: a
     * device without the library must not crash on app start.
     */
    val available: Boolean by lazy {
        try {
            System.loadLibrary("kernelsu")
            true
        } catch (e: Throwable) {
            false
        }
    }

    /** Version tag reported by the kernel side, e.g. "v0.9.2"; null if unavailable. */
    fun versionOrNull(): String? = probe { getVersion() }

    /** Kernel UAPI version, which is the number that decides compatibility. */
    fun kernelUapiOrNull(): Int? = probe { getKernelUAPIVersion() }

    fun managerUapiOrNull(): Int? = probe { getManagerUAPIVersion() }

    /** Whether the manager reports su as enabled at all. */
    fun suEnabledOrNull(): Boolean? = probe { isSuEnabled() }

    /** Number of apps granted superuser; a coarse but real signal. */
    fun superuserCountOrNull(): Int? = probe { getSuperuserCount() }

    /** Safe mode means the manager disabled modules after a bad boot. */
    fun safeModeOrNull(): Boolean? = probe { isSafeMode() }

    /** Whether the kernel reports itself as a manager process. */
    fun managerProcessOrNull(): Boolean? = probe { isManager() }

    private inline fun <T> probe(block: () -> T): T? = try {
        if (available) block() else null
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
