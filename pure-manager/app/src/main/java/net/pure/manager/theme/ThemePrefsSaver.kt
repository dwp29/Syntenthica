package net.pure.manager.theme

import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.listSaver

/**
 * Survives rotation and process death without a persistence layer.
 *
 * Deliberately not DataStore yet: the token set is still moving, and writing a
 * storage format for it now would mean migrating it next week.
 */
val ThemePrefsSaver: Saver<ThemePrefs, Any> = listSaver(
    save = { p ->
        listOf(
            p.themeId, p.mode.name, p.accentIndex,
            p.cornerScale, p.densityScale, p.animations, p.blur,
        )
    },
    restore = { v ->
        ThemePrefs(
            themeId = v[0] as String,
            mode = runCatching { AppMode.valueOf(v[1] as String) }.getOrDefault(AppMode.DARK),
            accentIndex = (v[2] as Int).coerceIn(0, AccentChoices.lastIndex),
            cornerScale = v[3] as Float,
            densityScale = v[4] as Float,
            animations = v[5] as Boolean,
            blur = if (v.size > 6) v[6] as Boolean else true,
        )
    },
)
