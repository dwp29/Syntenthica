package net.pure.manager

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import net.pure.manager.theme.PureTheme
import net.pure.manager.theme.ThemePrefs
import net.pure.manager.theme.ThemePrefsSaver
import net.pure.manager.ui.PureShell

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Installed before the first frame, so a crash inside composition or
        // inside a draw effect is still recorded.
        PureCrash.install(this)
        enableEdgeToEdge()
        setContent {
            // Preferences are still session-only; DataStore lands with the file
            // layer, once the token set stops moving.
            //
            // Safe mode. Compose does not allow try/catch around composable calls,
            // so a failure inside composition cannot be caught where it happens --
            // the process dies. What it can do is not happen twice: if the last
            // run left a crash report, this run starts with blur off, the plain
            // theme and default density, which is enough to reach Setelan and read
            // or copy the report.
            val recovered = remember { PureCrash.read(this@MainActivity) != null }
            var prefs by rememberSaveable(stateSaver = ThemePrefsSaver) {
                mutableStateOf(if (recovered) ThemePrefs(blur = false) else ThemePrefs())
            }
            PureTheme(prefs) {
                PureShell(
                    prefs = prefs,
                    onPrefs = { prefs = it },
                    recoveredFromCrash = recovered,
                )
            }
        }
    }
}
