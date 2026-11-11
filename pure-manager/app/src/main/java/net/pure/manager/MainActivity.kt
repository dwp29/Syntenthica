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
import net.pure.manager.ui.PureShell

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // 0.1.0 persists nothing yet: the Customisation tab must first prove the
            // tokens work before their storage format is fixed. DataStore lands in
            // stage 1b together with the settings repository.
            var prefs by rememberSaveable(stateSaver = ThemePrefsSaver) {
                mutableStateOf(ThemePrefs())
            }
            PureTheme(prefs) {
                PureShell(
                    prefs = prefs,
                    onPrefs = { prefs = it },
                )
            }
        }
    }
}
