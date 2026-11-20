package app.breakfast.manager.data

/**
 * What the ROOT page can say beyond "granted" or "not granted".
 *
 * The page used to be a placeholder with a single button, which is why it looked
 * unfinished. It now reports the facts the app actually depends on: whether a
 * kernel manager is installed, which su it found, whether root is currently
 * granted to this process, and which privileged reads are therefore available.
 *
 * Every field is something we checked. None of them is a guess.
 */
object RootStatus {

    data class Snapshot(
        val manager: String?,
        val suPath: String?,
        val uid: String?,
        val granted: Boolean,
        val canReadDmesg: Boolean,
        val canWriteNodes: Boolean,
        val checkedAtMs: Long,
    ) {
        /** Lines for the ROOT page, in order, already worded for a human. */
        fun lines(): List<Pair<String, String>> = listOf(
            "pengelola root" to (manager ?: "tidak ditemukan"),
            "su" to (suPath ?: "tidak ditemukan di jalur yang diperiksa"),
            "uid proses" to (uid ?: "tidak terbaca"),
            "root" to if (granted) "diberikan" else "belum diberikan",
            "dmesg" to if (canReadDmesg) "bisa dibaca" else "tidak bisa dibaca",
            "menulis node" to if (canWriteNodes) "diizinkan" else "tidak diizinkan",
        )
    }

    private val MANAGERS = listOf(
        "/data/adb/ksu" to "KernelSU",
        "/data/adb/ksud" to "KernelSU",
        "/sbin/ksud" to "KernelSU",
        "/data/adb/magisk" to "Magisk",
        "/data/adb/ap" to "APatch",
    )

    private val SU_PATHS = listOf(
        "/system/bin/su",
        "/system/xbin/su",
        "/sbin/su",
        "/data/adb/ksu/bin/su",
        "/debug_ramdisk/su",
    )

    /** Existence check that treats a denied path as "not found", never as a crash. */
    private fun exists(path: String): Boolean = try {
        java.io.File(path).exists()
    } catch (e: SecurityException) {
        false
    }

    fun snapshot(root: RootBridge = RootBridge): Snapshot {
        // MANAGERS holds (path, name) pairs, so the lambda argument is a Pair and
        // the path is its first element. Passing the Pair to File() was the
        // compile error: none of File's constructors takes a Pair.
        val manager = MANAGERS.firstOrNull { (path, _) -> exists(path) }?.second
        val suPath = SU_PATHS.firstOrNull { path -> exists(path) }
        val id = root.run("id -u")
        val uid = id.stdout.trim().takeIf { it.isNotEmpty() }
        val granted = uid == "0"
        // These two probes are what the rest of the app promises the user; running
        // them here means the ROOT page reports capabilities, not a promise.
        val dmesg = if (granted) root.run("dmesg -r | tail -n 1").ok else false
        val writable = if (granted) root.run("test -w /sys/block/zram0/mem_limit").ok else false
        return Snapshot(
            manager = manager,
            suPath = suPath,
            uid = uid,
            granted = granted,
            canReadDmesg = dmesg,
            canWriteNodes = writable,
            checkedAtMs = System.currentTimeMillis(),
        )
    }
}
