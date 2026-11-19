package app.breakfast.manager

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Typeface
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import app.breakfast.manager.data.AuditRunner
import app.breakfast.manager.data.AuditStore
import app.breakfast.manager.data.DeviceAudit
import app.breakfast.manager.data.DeviceFiles
import app.breakfast.manager.data.KernelPairing
import app.breakfast.manager.data.LedgerReader
import app.breakfast.manager.data.PairingGenerated
import app.breakfast.manager.data.RootBridge
import app.breakfast.manager.data.ThemeStore
import app.breakfast.manager.data.TuningSession
import app.breakfast.manager.data.TuningWhitelist
import app.breakfast.manager.ui.Copy
import app.breakfast.manager.ui.LedgerView
import app.breakfast.manager.ui.ThemeCatalog
import java.util.concurrent.Executors

/**
 * Single-activity shell, built from views rather than Compose.
 *
 * Keeping to the Android Gradle Plugin alone means the APK has no Compose
 * compiler or dependency graph to audit, and the whole app can be verified from
 * its decompiled contents. All logic lives in the data package and is tested on
 * the JVM; this file only renders it and moves work off the main thread.
 */
class MainActivity : Activity() {

    private lateinit var palette: ThemeCatalog.Palette
    private lateinit var auditStore: AuditStore
    private lateinit var themeStore: ThemeStore
    private val workers = Executors.newSingleThreadExecutor()

    private lateinit var release: String
    private lateinit var decision: KernelPairing.Decision
    private lateinit var report: DeviceAudit.Report

    /** Originals captured by the most recent apply, so reset has something true to restore. */
    private var lastPlan: TuningSession.Plan? = null

    /** True while a manual audit is in flight, so the button cannot stack requests. */
    private var auditing = false

    /** Set when a write makes the stored audit stale; triggers a re-audit. */
    private var auditDirty = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        auditStore = AuditStore(this)
        themeStore = ThemeStore(this)
        palette = ThemeCatalog.byId(themeStore.current()) ?: ThemeCatalog.offered().first()

        release = RootBridge.kernelRelease() ?: "—"
        decision = KernelPairing.decide(release, PairingGenerated.KERNELS)

        // First install, or the kernel changed since the last audit: audit now.
        val stored = auditStore.load()
        val needsAudit = stored == null || stored.kernelRelease != release
        report = stored ?: emptyReport()

        render()

        if (needsAudit) {
            // Automatic audits are exempt from the manual cooldown, which exists
            // to stop spamming sysfs by hand, not to block a first run.
            runAudit(manual = false)
        }
    }

    override fun onDestroy() {
        workers.shutdownNow()
        super.onDestroy()
    }

    // ---------------------------------------------------------------- rendering

    private fun render() {
        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 96)
            setBackgroundColor(palette.background.toInt())
        }
        scroll.addView(root)

        root.addView(heading("BREAKFAST"))
        root.addView(body("Kendali kernel. Membaca tidak butuh konfirmasi; menulis selalu butuh."))

        root.addView(section("KERNEL"))
        root.addView(row("Release", release))
        root.addView(row("Varian", decision.variant ?: "tidak dikenali"))
        root.addView(
            row(
                "Tuning",
                if (decision.tuningAllowed) "tersedia" else "dinonaktifkan (${decision.reason})",
                if (decision.tuningAllowed) ThemeCatalog.STATUS_STABLE else ThemeCatalog.STATUS_ATTENTION,
            )
        )
        root.addView(row("Status kernel", "dikompilasi, belum diuji boot", ThemeCatalog.STATUS_ATTENTION))

        root.addView(section("STABILITY LEDGER"))
        val ledgerSection = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(ledgerSection)
        renderLedger(ledgerSection, null)

        root.addView(section("AUDIT PERANGKAT"))
        val auditSection = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(auditSection)
        root.addView(
            button("AUDIT SEKARANG") { runAudit(manual = true) }
        )
        root.addView(body("Audit hanya membaca, tidak mengubah apa pun."))
        renderAudit(auditSection)

        root.addView(section("TUNING"))
        val tuningSection = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(tuningSection)
        renderTuning(tuningSection)

        root.addView(section("TEMA"))
        val themeSection = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(themeSection)
        renderThemes(themeSection)

        root.addView(section("TENTANG"))
        root.addView(row("Manager UAPI", KernelPairing.MANAGER_UAPI.toString()))
        root.addView(row("Kernel UAPI", if (decision.known) "4" else "—"))
        root.addView(body("Tanpa izin apa pun. Root dipakai hanya saat membaca dmesg dan menulis parameter yang kamu konfirmasi."))

        setContentView(scroll)
    }

    private fun emptyReport() = DeviceAudit.Report(release, 0L, emptyList())

    private fun renderLedger(section: LinearLayout, result: LedgerReader.Result?) {
        section.removeAllViews()
        if (result == null) {
            section.addView(row("Skor", Copy.ledgerUnavailable(), ThemeCatalog.STATUS_ATTENTION))
            section.addView(body("Membaca dmesg…"))
            workers.execute {
                val read = LedgerReader.read()
                runOnUiThread { renderLedger(section, read) }
            }
            return
        }
        for (item in LedgerView.rows(result)) {
            section.addView(row(item.label, item.value, item.color))
        }
        if (result is LedgerReader.Result.Read) {
            section.addView(
                body("Skor ${result.score.value} · ${LedgerView.bandLabel(result.score)} · " +
                    "dihitung sejak boot, bukan sejak aplikasi dibuka.")
            )
        } else {
            section.addView(
                body("Skor tidak ditampilkan karena dmesg tidak terbaca. Angka nol di sini akan menyesatkan, jadi tidak ditampilkan.")
            )
        }
    }

    private fun renderAudit(section: LinearLayout) {
        section.removeAllViews()
        if (report.nodes.isEmpty() && report.timestampMs == 0L) {
            section.addView(row("Status", "belum pernah diaudit", ThemeCatalog.STATUS_ATTENTION))
            section.addView(body("Audit memeriksa ${DeviceAudit.totalNodeCount()} node: ada atau tidak, izin, dan nilai sekarang."))
            return
        }
        section.addView(row("Kernel", report.kernelRelease))
        section.addView(row("Hasil", report.summary()))
        val age = DeviceAudit.ageLabel((System.currentTimeMillis() - report.timestampMs).coerceAtLeast(0))
        section.addView(row("Umur hasil", "$age lalu", ThemeCatalog.TEXT_SECONDARY))
        if (report.kernelRelease != release) {
            section.addView(
                row(
                    "Perhatian",
                    "hasil untuk kernel lain, akan dibuang",
                    ThemeCatalog.STATUS_ATTENTION,
                )
            )
        }
        for ((group, _) in DeviceAudit.NODE_SPECS) {
            val nodes = report.nodes.filter { it.group == group }
            if (nodes.isEmpty()) continue
            section.addView(label(group))
            for (node in nodes) {
                val colour = when (node.support) {
                    DeviceAudit.Support.SUPPORTED -> ThemeCatalog.STATUS_STABLE
                    DeviceAudit.Support.READ_ONLY -> ThemeCatalog.STATUS_NORMAL
                    DeviceAudit.Support.ABSENT -> ThemeCatalog.STATUS_ATTENTION
                }
                section.addView(row("  ${node.name}", "${node.support.label} · ${node.value ?: "—"}", colour))
            }
        }
    }

    /**
     * Read-only view of the whitelisted nodes, plus a write flow when pairing
     * allows it. The values shown come from the last audit where possible, so
     * the screen and the audit cannot disagree.
     */
    private fun renderTuning(section: LinearLayout) {
        section.removeAllViews()
        if (!decision.tuningAllowed) {
            section.addView(row("Status", "dinonaktifkan: kernel tidak dikenali", ThemeCatalog.STATUS_ATTENTION))
            section.addView(body("Tuning dibuka hanya untuk kernel yang tercantum di tabel pairing."))
            return
        }
        if (report.nodes.isEmpty()) {
            // Distinguish "we have not looked" from "we wrote something and the
            // values on screen are no longer current".
            val status = if (auditDirty) "perlu audit ulang" else "belum diaudit"
            section.addView(row("Status", status, ThemeCatalog.STATUS_ATTENTION))
            section.addView(body("Audit diperlukan sebelum mengubah apa pun."))
            return
        }
        if (auditDirty) {
            section.addView(row("Nilai di bawah", "hasil audit sebelum penulisan terakhir", ThemeCatalog.STATUS_ATTENTION))
        }

        val offered = offeredChoices()
        val editable = mutableListOf<TuningWhitelist.Parameter>()

        for (parameter in TuningWhitelist.PARAMETERS) {
            val current = report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == parameter.key }
            val shown = when {
                current == null || current.support == DeviceAudit.Support.ABSENT -> "tidak tersedia"
                parameter.key == "zram_comp_algorithm" ->
                    TuningWhitelist.parseActive(current.value ?: "") ?: (current.value ?: "—")
                else -> current.value ?: "—"
            }
            val colour = when {
                current == null || current.support == DeviceAudit.Support.ABSENT -> ThemeCatalog.STATUS_ATTENTION
                parameter.mode == TuningWhitelist.WriteMode.NEEDS_REBOOT -> ThemeCatalog.TEXT_SECONDARY
                else -> ThemeCatalog.TEXT_PRIMARY
            }
            section.addView(row(parameter.key, shown, colour))
            if (current != null && current.support == DeviceAudit.Support.SUPPORTED) {
                editable += parameter
            }
        }

        if (editable.isEmpty()) {
            section.addView(body("Tidak ada parameter yang bisa ditulis di kernel ini. Itu hasil audit, bukan kesalahan."))
            return
        }

        section.addView(body("disksize hanya berlaku sebelum zram dipakai: perubahan perlu reboot."))
        section.addView(body("Parameter schedutil berstatus perlu audit sampai terbukti ada di perangkat ini."))

        val inputs = mutableMapOf<String, EditText>()
        for (parameter in editable) {
            val field = EditText(this).apply {
                hint = parameter.key
                setTextColor(ThemeCatalog.TEXT_PRIMARY.toInt())
                setHintTextColor(ThemeCatalog.TEXT_SECONDARY.toInt())
                inputType = InputType.TYPE_CLASS_TEXT
                textSize = 15f
            }
            inputs[parameter.key] = field
            section.addView(field)
        }

        section.addView(
            button("TERAPKAN") {
                val proposals = inputs.mapNotNull { (key, field) ->
                    val value = field.text.toString().trim()
                    if (value.isEmpty()) null else TuningSession.Proposal(key, value)
                }
                if (proposals.isEmpty()) {
                    toast("Tidak ada nilai yang diisi.")
                } else {
                    confirmAndApply(proposals, offered)
                }
            }
        )

        if (lastPlan != null) {
            section.addView(
                button("KEMBALIKAN KE DEFAULT") {
                    workers.execute {
                        val result = TuningSession.reset(DeviceFiles, lastPlan!!)
                        runOnUiThread {
                            lastPlan = null
                            auditDirty = true
                            toast(result.summary())
                            render()
                            runAudit(manual = false)
                        }
                    }
                }
            )
        }
    }

    private fun offeredChoices(): Map<String, List<String>> {
        val node = report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == "zram_comp_algorithm" }
        val raw = node?.value ?: return emptyMap()
        return mapOf("zram_comp_algorithm" to TuningWhitelist.parseOffered(raw))
    }

    /**
     * Confirmation names how many parameters change and which ones need a
     * reboot, then applies on a worker thread. Rejections are shown before
     * anything is written, so a value that cannot apply is never promised.
     */
    private fun confirmAndApply(proposals: List<TuningSession.Proposal>, offered: Map<String, List<String>>) {
        workers.execute {
            val plan = TuningSession.plan(DeviceFiles, proposals, offered)
            runOnUiThread {
                if (plan.isEmpty) {
                    val why = plan.rejected.joinToString(", ") { "${it.first.key}: ${it.second.name.lowercase()}" }
                    toast("Tidak ada yang bisa diterapkan. $why")
                    return@runOnUiThread
                }
                if (plan.rejected.isNotEmpty()) {
                    toast("${plan.rejected.size} nilai ditolak dan tidak akan ditulis.")
                }
                val rebootNote = if (plan.needsReboot.isEmpty()) "" else
                    "\n\n${plan.needsReboot.size} parameter berlaku setelah reboot."
                AlertDialog.Builder(this)
                    .setTitle("Terapkan perubahan?")
                    .setMessage("${plan.count} parameter akan diubah.$rebootNote\n\nBisa dikembalikan ke default kapan pun.")
                    .setNegativeButton("Batal", null)
                    .setPositiveButton("Terapkan") { _, _ ->
                        workers.execute {
                            val result = TuningSession.apply(DeviceFiles, plan)
                            runOnUiThread {
                                if (result.applied.isNotEmpty()) lastPlan = plan
                                auditDirty = true
                                toast(result.summary())
                                render()
                                runAudit(manual = false)
                            }
                        }
                    }
                    .show()
            }
        }
    }

    private fun runAudit(manual: Boolean) {
        if (auditing) return
        val now = System.currentTimeMillis()
        if (manual) {
            val remaining = DeviceAudit.cooldownRemainingMs(report.timestampMs.takeIf { it > 0 }, now)
            if (remaining > 0) {
                toast("Tunggu ${(remaining / 1000) + 1} detik sebelum audit lagi.")
                return
            }
        }
        // Automatic audits are for a first run, a kernel change, or a write that
        // made the stored values stale. Otherwise the last report still stands.
        val automatic = report.kernelRelease != release || report.timestampMs == 0L || auditDirty
        if (!manual && !automatic) return
        auditing = true

        workers.execute {
            val fresh = try {
                AuditRunner.run(AuditRunner.SystemFs, release, System.currentTimeMillis())
            } catch (e: Exception) {
                null
            }
            runOnUiThread {
                when (val resolved = DeviceAudit.resolve(report, fresh, release, System.currentTimeMillis())) {
                    is DeviceAudit.Resolution.Fresh -> {
                        report = resolved.report
                        auditStore.save(report)
                    }
                    is DeviceAudit.Resolution.KeptStale -> {
                        // Same kernel: the old report still describes this device.
                        report = resolved.report
                        toast("Audit gagal (${resolved.failure}). Hasil lama, ${DeviceAudit.ageLabel(resolved.ageMs)} lalu, masih dipakai.")
                    }
                    is DeviceAudit.Resolution.None -> {
                        report = emptyReport()
                        auditStore.clear()
                        toast("Audit gagal: ${resolved.reason}")
                    }
                }
                auditing = false
                auditDirty = false
                render()
            }
        }
    }

    private fun renderThemes(section: LinearLayout) {
        section.removeAllViews()
        for (candidate in ThemeCatalog.offered()) {
            val marker = if (candidate.id == palette.id) "● " else "○ "
            section.addView(
                button("$marker${candidate.displayName}") {
                    palette = candidate
                    themeStore.save(candidate.id)
                    render()
                }
            )
        }
        section.addView(body("${ThemeCatalog.offered().size} tema lolos kontras WCAG 4.5:1. Warna status tidak ikut tema."))
    }

    // ------------------------------------------------------------------ widgets

    private fun heading(text: String) = TextView(this).apply {
        this.text = text
        textSize = 30f
        setTextColor(palette.accent.toInt())
        setTypeface(typeface, Typeface.BOLD)
        letterSpacing = 0.12f
        setPadding(0, 0, 0, 12)
    }

    private fun section(text: String) = TextView(this).apply {
        this.text = text
        textSize = 13f
        setTextColor(ThemeCatalog.TEXT_SECONDARY.toInt())
        letterSpacing = 0.18f
        setPadding(0, 48, 0, 12)
        setTypeface(typeface, Typeface.BOLD)
    }

    private fun label(text: String) = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTextColor(palette.accent.toInt())
        setPadding(0, 20, 0, 4)
        setTypeface(typeface, Typeface.BOLD)
    }

    private fun body(text: String) = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTextColor(ThemeCatalog.TEXT_SECONDARY.toInt())
        setPadding(0, 4, 0, 8)
        setLineSpacing(0f, 1.3f)
    }

    private fun button(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        textSize = 13f
        setTextColor(ThemeCatalog.TEXT_PRIMARY.toInt())
        setBackgroundColor(palette.surface.toInt())
        setOnClickListener { onClick() }
    }

    private fun row(label: String, value: String, valueColor: Long = ThemeCatalog.TEXT_PRIMARY) =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, 10, 0, 10)
            addView(TextView(context).apply {
                text = label
                textSize = 15f
                setTextColor(ThemeCatalog.TEXT_SECONDARY.toInt())
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
            addView(TextView(context).apply {
                text = value
                textSize = 15f
                setTextColor(valueColor.toInt())
                gravity = Gravity.END
                setTypeface(typeface, Typeface.BOLD)
            })
        }

    private fun toast(message: String) {
        android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show()
    }
}
