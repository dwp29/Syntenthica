package app.breakfast.manager

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import app.breakfast.manager.data.DeviceFiles
import app.breakfast.manager.data.KernelPairing
import app.breakfast.manager.data.LedgerReader
import app.breakfast.manager.data.PairingGenerated
import app.breakfast.manager.data.TuningWhitelist
import app.breakfast.manager.ui.Copy
import app.breakfast.manager.ui.FailureKind
import app.breakfast.manager.ui.LedgerView
import app.breakfast.manager.ui.ThemeCatalog
import java.util.concurrent.Executors

/**
 * Single-activity shell with no third-party UI dependency.
 *
 * Views instead of Compose is a deliberate constraint: it keeps the build to the
 * Android Gradle Plugin alone, so the APK can be built and verified in CI
 * without a Compose compiler or a dependency graph to audit. The data layer is
 * UI-agnostic, so a Compose front end can be added later without touching it.
 */
class MainActivity : Activity() {

    private lateinit var palette: ThemeCatalog.Palette

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        palette = ThemeCatalog.byId("fresh-milk") ?: ThemeCatalog.ALL.first()

        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 64, 48, 64)
            setBackgroundColor(palette.background.toInt())
        }
        scroll.addView(root)

        root.addView(heading("BREAKFAST"))
        root.addView(body("Kernel control surface. Read-only until a kernel audit has been run."))

        val release = System.getProperty("os.version") ?: ""
        val decision = KernelPairing.decide(release, PairingGenerated.KERNELS)

        root.addView(section("KERNEL"))
        root.addView(row("Release", release.ifEmpty { "—" }))
        root.addView(row("Variant", decision.variant ?: "tidak dikenali"))
        root.addView(
            row(
                "Tuning",
                if (decision.tuningAllowed) "tersedia" else "dinonaktifkan (${decision.reason})",
                if (decision.tuningAllowed) ThemeCatalog.STATUS_STABLE else ThemeCatalog.STATUS_ATTENTION,
            )
        )
        root.addView(
            row(
                "Status kernel",
                "dikompilasi, belum diuji boot",
                ThemeCatalog.STATUS_ATTENTION,
            )
        )

        root.addView(section("STABILITY LEDGER"))
        // Reading dmesg needs root and can take a moment; do it off the main
        // thread and fill the section in when it arrives. The rows show "—"
        // until then, so a slow read never looks like a score of zero.
        val ledgerSection = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(ledgerSection)
        root.addView(row("Skor", Copy.ledgerUnavailable(), ThemeCatalog.STATUS_ATTENTION))
        root.addView(body("Membaca dmesg…"))
        loadLedger(ledgerSection)

        root.addView(section("TEMA"))
        root.addView(
            row(
                "Aktif",
                palette.displayName,
                ThemeCatalog.STATUS_NORMAL,
            )
        )
        root.addView(body("${ThemeCatalog.offered().size} tema lolos kontras WCAG: " +
            ThemeCatalog.offered().joinToString(", ") { it.displayName }))

        root.addView(section("TUNING"))
        root.addView(body("Hanya parameter yang terbukti ada di kernel ini yang ditampilkan. " +
            "Audit dijalankan ulang saat uname -r berubah."))
        val tuningSection = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(tuningSection)
        loadTuning(tuningSection, decision.tuningAllowed)

        root.addView(section("TENTANG"))
        root.addView(row("Manager UAPI", KernelPairing.MANAGER_UAPI.toString()))
        root.addView(row("Kernel UAPI", if (decision.known) "4" else "—"))
        root.addView(body("Aplikasi ini tidak meminta root sampai kamu menekan tombol yang membutuhkannya."))

        setContentView(scroll)
    }

    /**
     * Reads the ring buffer on a worker thread and renders the outcome.
     *
     * There is no spinner: the section shows a dash and a sentence, then either
     * numbers or the reason it could not read them.
     */
    private fun loadLedger(section: LinearLayout) {
        Executors.newSingleThreadExecutor().execute {
            val result = LedgerReader.read()
            runOnUiThread {
                section.removeAllViews()
                for (item in LedgerView.rows(result)) {
                    section.addView(row(item.label, item.value, item.color))
                }
                if (result is LedgerReader.Result.Read) {
                    section.addView(
                        body(
                            "Skor ${result.score.value} · ${LedgerView.bandLabel(result.score)} · " +
                                "dihitung sejak boot, bukan sejak aplikasi dibuka."
                        )
                    )
                } else {
                    section.addView(body("Skor tidak ditampilkan karena dmesg tidak terbaca. " +
                        "Angka nol di sini akan menyesatkan, jadi tidak ditampilkan."))
                }
            }
        }
    }

    /**
     * Shows the current value of each whitelisted node, read-only.
     *
     * A node that is absent is labelled "tidak tersedia" rather than hidden: on
     * this kernel tree zram is a module, so a device that has never used swap
     * will legitimately have no /sys/block/zram0 yet. Hiding it would look like
     * the app had lost a feature; naming it tells the truth.
     */
    private fun loadTuning(section: LinearLayout, allowed: Boolean) {
        if (!allowed) {
            section.addView(row("Status", "dinonaktifkan: kernel tidak dikenali", ThemeCatalog.STATUS_ATTENTION))
            section.addView(body("Tuning dibuka hanya untuk kernel yang tercantum di tabel pairing."))
            return
        }
        Executors.newSingleThreadExecutor().execute {
            val values = TuningWhitelist.PARAMETERS.map { parameter ->
                val raw = DeviceFiles.read(parameter.path)
                val shown = when {
                    raw == null -> "tidak tersedia"
                    parameter.key == "zram_comp_algorithm" -> TuningWhitelist.parseActive(raw) ?: raw.trim()
                    else -> raw.trim()
                }
                val color = when {
                    raw == null -> ThemeCatalog.STATUS_ATTENTION
                    parameter.mode == TuningWhitelist.WriteMode.NEEDS_REBOOT -> ThemeCatalog.TEXT_SECONDARY
                    else -> ThemeCatalog.TEXT_PRIMARY
                }
                Triple(parameter.key, shown, color)
            }
            runOnUiThread {
                section.removeAllViews()
                for ((key, shown, color) in values) {
                    section.addView(row(key, shown, color))
                }
                section.addView(body("disksize hanya berlaku sebelum zram dipakai: perubahan perlu reboot."))
                section.addView(body("Parameter schedutil ditandai perlu audit: nilainya dibaca, bukan dikarang."))
            }
        }
    }

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

    private fun body(text: String) = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTextColor(ThemeCatalog.TEXT_SECONDARY.toInt())
        setPadding(0, 0, 0, 8)
        setLineSpacing(0f, 1.3f)
    }

    private fun row(label: String, value: String, valueColor: Long = ThemeCatalog.TEXT_PRIMARY) =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, 12, 0, 12)
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
}
