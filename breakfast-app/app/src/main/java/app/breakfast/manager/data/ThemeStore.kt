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

    companion object {
        private const val KEY_THEME = "theme.id"
    }
}
