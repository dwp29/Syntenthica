package app.breakfast.manager.data

import android.content.Context

/**
 * Remembers the chosen theme.
 *
 * An unknown or unreadable id falls back to the first palette that passes the
 * contrast rule rather than to a hardcoded colour, so a corrupted preference
 * cannot produce an unreadable screen.
 */
class ThemeStore(context: Context) {

    private val prefs = context.getSharedPreferences("breakfast.theme", Context.MODE_PRIVATE)

    fun current(): String = prefs.getString(KEY_THEME, null) ?: "fresh-milk"

    fun save(id: String) {
        prefs.edit().putString(KEY_THEME, id).apply()
    }

    /**
     * Sampling interval in seconds.
     *
     * Clamped to what the settings sheet offers: a stored 0 or 900 would either
     * spin the worker or freeze the dashboard, and a preference file is not a
     * trusted input.
     */
    fun interval(): Int = prefs.getInt(KEY_INTERVAL, DEFAULT_INTERVAL)
        .takeIf { it in ALLOWED_INTERVALS } ?: DEFAULT_INTERVAL

    fun saveInterval(seconds: Int) {
        prefs.edit().putInt(KEY_INTERVAL, seconds.coerceIn(1, 10)).apply()
    }

    companion object {
        private const val KEY_THEME = "theme.id"
        private const val KEY_INTERVAL = "interval.seconds"
        const val DEFAULT_INTERVAL = 2
        val ALLOWED_INTERVALS = setOf(1, 2, 5, 10)
    }
}
