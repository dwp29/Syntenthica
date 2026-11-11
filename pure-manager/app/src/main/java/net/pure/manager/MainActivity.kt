package net.pure.manager

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import net.pure.manager.theme.PureTheme
import net.pure.manager.theme.ThemePrefs
import net.pure.manager.theme.ThemePrefsSaver
import net.pure.manager.ui.FallbackScreen
import net.pure.manager.ui.PureShell

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Installed before the first frame, so a crash inside composition or
        // inside a draw effect is still recorded.
        PureCrash.install(this)
        enableEdgeToEdge()
        setContent {
            // 0.1.0 persists nothing yet: the Customisation tab must first prove the
            // tokens work before their storage format is fixed. DataStore lands in
            // stage 1b together with the settings repository.
            var prefs by rememberSaveable(stateSaver = ThemePrefsSaver) {
                mutableStateOf(ThemePrefs())
            }
            // A failure inside the theme system must not be indistinguishable
            // from a failure at launch. If composition throws, the app falls back
            // to the plainest possible screen and records what happened.
            // Fallback colours follow the system, so a failure on a light-themed
            // phone does not produce a black screen that looks like another crash.
            val systemDark = (resources.configuration.uiMode and
                android.content.res.Configuration.UI_MODE_NIGHT_MASK) ==
                android.content.res.Configuration.UI_MODE_NIGHT_YES
            var failed by rememberSaveable { mutableStateOf<String?>(null) }
            if (failed == null) {
                try {
                    PureTheme(prefs) {
                        PureShell(
                            prefs = prefs,
                            onPrefs = { prefs = it },
                        )
                    }
                } catch (e: Throwable) {
                    failed = "${e.javaClass.simpleName}: ${e.message}"
                }
            }
            failed?.let { reason ->
                FallbackScreen(
                    reason = reason,
                    dark = systemDark,
                    onReset = {
                        prefs = ThemePrefs()
                        failed = null
                    },
                )
            }
        }
    }
}
