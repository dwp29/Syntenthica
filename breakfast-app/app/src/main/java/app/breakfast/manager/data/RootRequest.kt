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

        /** No su binary on this device at all. */
        data object NotRooted : Outcome

        /** KernelSU answered, but with something other than uid 0. */
        data class Unexpected(val detail: String) : Outcome
    }

    fun request(root: RootBridge = RootBridge): Outcome {
        val result = root.run("id -u")
        if (!result.ok && result.stdout.isBlank()) {
            return if (root.suExists()) Outcome.Denied else Outcome.NotRooted
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
        Outcome.NotRooted -> "Perangkat ini tidak punya su. Tanpa KernelSU, hanya pembacaan tanpa root yang bisa dilakukan."
        is Outcome.Unexpected -> "Root menjawab dengan ${outcome.detail}, bukan uid 0. Periksa pengaturan KernelSU."
    }
}
