package app.breakfast.manager

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import app.breakfast.manager.data.KernelPairing
import app.breakfast.manager.data.PairingGenerated
import app.breakfast.manager.data.StabilityLedger
import app.breakfast.manager.ui.Copy
import app.breakfast.manager.ui.ThemeCatalog

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
        val unreadable = StabilityLedger.unreadable()
        root.addView(row("Skor", Copy.ledgerUnavailable()))
        root.addView(body("dmesg belum dibaca pada layar ini. Skor tidak dikarang."))
        root.addView(row("Beban", unreadable.burden.toString()))
        for (event in StabilityLedger.Event.entries) {
            root.addView(row(event.label, "0", ThemeCatalog.TEXT_SECONDARY))
        }

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

        root.addView(section("TENTANG"))
        root.addView(row("Manager UAPI", KernelPairing.MANAGER_UAPI.toString()))
        root.addView(row("Kernel UAPI", if (decision.known) "4" else "—"))
        root.addView(body("Aplikasi ini tidak meminta root sampai kamu menekan tombol yang membutuhkannya."))

        setContentView(scroll)
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
