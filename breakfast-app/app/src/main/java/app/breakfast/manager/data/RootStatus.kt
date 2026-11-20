package app.breakfast.manager.data

import com.rifsxd.ksunext.Natives

/**
 * What the ROOT page reports, and how sure it is.
 *
 * The previous version printed "pengelola root: tidak ditemukan" and "su: tidak
 * ditemukan" on a device whose TUNING screen showed readable schedutil nodes and
 * sysfs in use - things an unrooted phone cannot do. The page was not lying on
 * purpose: it looked for /data/adb/ksu with File.exists(), which returns false
 * when the sandbox may not traverse /data/adb at all.
 *
 * So every row now carries a confidence level, and "not found" is only said when
 * we could actually look. When we cannot look, the page says so.
 */
object RootStatus {

    /** How a fact was established. */
    enum class Sure {
        /** Read from libkernelsu.so, which only a KernelSU kernel answers. */
        LIBRARY,
        /** From a su command that returned a value. */
        SHELL,
        /** From a filesystem probe that could actually see the directory. */
        FILESYSTEM,
        /** We could not look; this is the absence of an answer, not an answer. */
        UNKNOWN,
    }

    data class Fact(val value: String, val sure: Sure, val note: String? = null)

    data class Snapshot(
        val manager: Fact,
        val su: Fact,
        val uid: Fact,
        val granted: Boolean,
        val dmesg: Fact,
        val writeNodes: Fact,
        val kernelVersion: String?,
        val kernelUapi: Int?,
        val suEnabled: Boolean?,
        val superuserCount: Int?,
        val safeMode: Boolean?,
        val libraryLoaded: Boolean,
        val librarySkippedReason: String?,
        val checkedAtMs: Long,
    ) {
        /**
         * The rows the ROOT page draws, in order.
         *
         * A value of "tidak bisa dipastikan" means exactly that; it never means
         * "no". The distinction is the whole point of this type.
         */
        fun lines(): List<Pair<String, Fact>> = listOf(
            "pengelola root" to manager,
            "su" to su,
            "uid proses" to uid,
            "root" to Fact(
                if (granted) "diberikan" else "belum diberikan",
                if (uid.sure == Sure.UNKNOWN) Sure.UNKNOWN else Sure.SHELL,
            ),
            "dmesg" to dmesg,
            "menulis node" to writeNodes,
        )

        /** Extra rows drawn only when the KernelSU library answered. */
        fun libraryLines(): List<Pair<String, String>> = buildList {
            kernelVersion?.let { add("versi kernel" to it) }
            kernelUapi?.let { add("UAPI kernel" to it.toString()) }
            suEnabled?.let { add("su aktif" to if (it) "ya" else "tidak") }
            superuserCount?.let { add("aplikasi ber-root" to "$it aplikasi") }
            safeMode?.let { add("safe mode" to if (it) "ya - modul dinonaktifkan" else "tidak") }
        }

        /** One sentence a person can act on. */
        fun verdict(): String = when {
            granted -> "Root diberikan. Pembacaan istimewa berjalan."
            manager.sure == Sure.UNKNOWN ->
                "Aplikasi tidak bisa memeriksa root sama sekali: jalur /data/adb tidak " +
                    "terbaca oleh sandbox. Status root di perangkat ini BELUM DIKETAHUI, " +
                    "bukan negatif."
            su.sure == Sure.UNKNOWN -> "Keberadaan su belum bisa dipastikan. Tekan BERI ROOT untuk mencoba."
            su.value == "tidak ditemukan" -> "Tidak ada su yang bisa dijangkau dari aplikasi ini."
            else -> "su ada tetapi belum memberi izin. Tekan BERI ROOT."
        }
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

    private data class LibraryFacts(
        val version: String?,
        val uapi: Int?,
        val suEnabled: Boolean?,
        val superusers: Int?,
        val safeMode: Boolean?,
    )

    /** Probes one directory. Reports "unknown" rather than "absent" when blind. */
    private fun probeDir(path: String): Fact {
        val file = java.io.File(path)
        val exists = try {
            file.exists()
        } catch (e: SecurityException) {
            false
        }
        if (exists) return Fact(path, Sure.FILESYSTEM)
        // Not seen: but could we look at all? /data/adb is the usual blind spot.
        val parent = file.parentFile
        val listed = try {
            parent?.list()
        } catch (e: SecurityException) {
            null
        }
        return if (listed == null) {
            Fact("tidak bisa dipastikan", Sure.UNKNOWN)
        } else {
            Fact("tidak ditemukan", Sure.FILESYSTEM)
        }
    }

    fun snapshot(root: RootBridge = RootBridge, allowLibrary: Boolean = false): Snapshot {
        // The library is the strongest signal: only a KernelSU kernel answers it.
        // Any JNI call can throw on a device without the library, so all five are
        // wrapped once, here, rather than trusting each getter to be safe.
        // Only loaded when the caller says it is safe: at start-up the answer is
        // no, because run 30 proved this library can kill the process while
        // loading, and that cannot be caught. See NativeGuard.
        val loaded = allowLibrary && Natives.load()
        val lib = if (!loaded) {
            LibraryFacts(null, null, null, null, null)
        } else try {
            LibraryFacts(
                version = Natives.versionOrNull(),
                uapi = Natives.kernelUapiOrNull(),
                suEnabled = Natives.suEnabledOrNull(),
                superusers = Natives.superuserCountOrNull(),
                safeMode = Natives.safeModeOrNull(),
            )
        } catch (e: Throwable) {
            LibraryFacts(null, null, null, null, null)
        }
        val skippedReason = if (allowLibrary) null else
            "libkernelsu.so tidak dimuat otomatis karena percobaan sebelumnya menutup aplikasi. " +
                "Tekan PERIKSA ULANG untuk mencoba sekali lagi."
        val libVersion = lib.version
        val libUapi = lib.uapi
        val suEnabled = lib.suEnabled
        val superusers = lib.superusers
        val safe = lib.safeMode

        val manager: Fact = when {
            libVersion != null || libUapi != null ->
                Fact("KernelSU${libVersion?.let { " $it" } ?: ""}", Sure.LIBRARY,
                    "dijawab oleh libkernelsu.so di dalam aplikasi")
            else -> {
                val found = MANAGERS.firstOrNull { (path, _) -> probeDir(path).sure == Sure.FILESYSTEM }
                when {
                    found != null -> Fact(found.second, Sure.FILESYSTEM, found.first)
                    else -> {
                        // None found by listing; was any directory blind?
                        val blind = MANAGERS.any { (path, _) -> probeDir(path).sure == Sure.UNKNOWN }
                        if (blind) Fact("tidak bisa dipastikan", Sure.UNKNOWN,
                            "/data/adb tidak bisa dibaca oleh sandbox")
                        else Fact("tidak ditemukan", Sure.FILESYSTEM)
                    }
                }
            }
        }

        val suFound = SU_PATHS.map { it to probeDir(it) }
        val su: Fact = when {
            suFound.any { it.second.sure == Sure.FILESYSTEM } -> {
                val hit = suFound.first { it.second.sure == Sure.FILESYSTEM }
                Fact(hit.first, Sure.FILESYSTEM)
            }
            suFound.any { (_, fact) -> fact.sure == Sure.UNKNOWN } ->
                Fact("tidak bisa dipastikan", Sure.UNKNOWN, "jalurnya tidak terbaca")
            else -> Fact("tidak ditemukan", Sure.FILESYSTEM)
        }

        val id = root.run("id -u")
        val uidText = id.stdout.trim()
        val uid: Fact = when {
            id.timedOut -> Fact("tidak menjawab (timeout)", Sure.UNKNOWN)
            uidText.isNotEmpty() -> Fact(uidText, Sure.SHELL)
            manager.sure == Sure.LIBRARY || manager.sure == Sure.FILESYSTEM ->
                Fact("tidak terbaca", Sure.UNKNOWN, "su tidak menjawab, padahal pengelola root ada")
            else -> Fact("tidak terbaca", Sure.UNKNOWN)
        }
        val granted = uidText == "0"

        val dmesg: Fact = when {
            !granted -> Fact("tidak bisa dibaca", Sure.SHELL, "butuh uid 0")
            root.run("dmesg -r | tail -n 1").ok -> Fact("bisa dibaca", Sure.SHELL)
            else -> Fact("tidak bisa dibaca", Sure.SHELL, "uid 0 diberikan tetapi dmesg menolak")
        }
        val write: Fact = if (!granted) {
            Fact("tidak diizinkan", Sure.SHELL, "butuh uid 0")
        } else {
            Fact("diperiksa saat menulis", Sure.SHELL, "TUNING membaca balik setiap nilai")
        }

        return Snapshot(
            manager = manager,
            su = su,
            uid = uid,
            granted = granted,
            dmesg = dmesg,
            writeNodes = write,
            kernelVersion = libVersion,
            kernelUapi = libUapi,
            suEnabled = suEnabled,
            superuserCount = superusers,
            safeMode = safe,
            libraryLoaded = loaded,
            librarySkippedReason = skippedReason,
            checkedAtMs = System.currentTimeMillis(),
        )
    }
}
