package app.breakfast.manager.data

/**
 * Asks for root on purpose, at a moment the user chose.
 *
 * The previous build called `su` silently during start-up. On a device where the
 * KernelSU prompt was missed, every screen showed an em dash and the app never
 * said why or offered a way to fix it - which is what made the dashboard look
 * broken rather than unpermitted.
 *
 * A request is: run `id -u`, wait for the answer, and report which of three
 * things happened. "Denied" and "not installed" are different problems with
 * different fixes, so they are never merged into one message.
 */
object RootRequest {

    sealed interface Outcome {
        data object Granted : Outcome

        /** su exists but the user (or the manager) refused this time. */
        data object Denied : Outcome

        /** A kernel manager is present, but its su is unreachable from this sandbox. */
        data object ManagerPresentSuUnreachable : Outcome

        /** No su binary and no kernel manager: the device really has no root. */
        data object NotRooted : Outcome

        /** su started but never answered; the prompt was probably never seen. */
        data object TimedOut : Outcome

        /** KernelSU answered, but with something other than uid 0. */
        data class Unexpected(val detail: String) : Outcome
    }

    /**
     * Paths that only exist when a kernel-level root manager is installed.
     *
     * Used to avoid the false statement "perangkat ini tidak punya su". On the
     * reporting device the app was told exactly that, while TUNING showed
     * schedutil nodes readable, dmesg and sysfs in use, and a paired
     * Fresh-Milk kernel - none of which happens on an unrooted phone.
     */
    private val MANAGER_MARKERS = listOf(
        "/data/adb/ksu",
        "/data/adb/ksud",
        "/data/adb/magisk",
        "/data/adb/ap",
        "/sbin/ksud",
    )

    fun managerPresent(): Boolean = MANAGER_MARKERS.any { path ->
        try {
            java.io.File(path).exists()
        } catch (e: SecurityException) {
            false
        }
    }

    fun request(root: RootBridge = RootBridge): Outcome {
        val result = root.run("id -u")
        if (result.timedOut) return Outcome.TimedOut
        if (!result.ok && result.stdout.isBlank()) {
            // Order matters: a present manager means the su exists somewhere this
            // process cannot reach, which is a policy problem, not an absent root.
            return when {
                root.suExists() -> Outcome.Denied
                managerPresent() -> Outcome.ManagerPresentSuUnreachable
                else -> Outcome.NotRooted
            }
        }
        val uid = result.stdout.trim()
        return when {
            uid == "0" -> Outcome.Granted
            uid.isEmpty() -> Outcome.Denied
            else -> Outcome.Unexpected("uid=$uid")
        }
    }

    /** Plain-language explanation for each outcome; never "terjadi kesalahan". */
    fun message(outcome: Outcome): String = when (outcome) {
        Outcome.Granted -> "Root diberikan. Audit dijalankan ulang dengan izin penuh."
        Outcome.Denied -> "Permintaan root ditolak. Buka KernelSU, izinkan BREAKFAST, lalu coba lagi."
        Outcome.NotRooted ->
            "Tidak ada su dan tidak ada pengelola root di perangkat ini. Hanya pembacaan tanpa root yang bisa dilakukan."
        Outcome.ManagerPresentSuUnreachable ->
            "Pengelola root ada di perangkat, tetapi su tidak bisa dijangkau aplikasi ini. " +
                "Buka KernelSU, beri izin untuk BREAKFAST, lalu tekan BERI ROOT lagi."
        Outcome.TimedOut ->
            "su tidak menjawab dalam 10 detik. Permintaan izinnya mungkin tidak terlihat; " +
                "buka KernelSU untuk memeriksa antrean izin."
        is Outcome.Unexpected -> "Root menjawab dengan ${outcome.detail}, bukan uid 0. Periksa pengaturan KernelSU."
    }
}
