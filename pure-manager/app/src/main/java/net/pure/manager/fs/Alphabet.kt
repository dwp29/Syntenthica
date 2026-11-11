package net.pure.manager.fs

import java.util.Locale

/**
 * The A–Z strip along the side of a list, the way Contacts and Files do it.
 *
 * The work that matters is not drawing the letters, it is deciding which letter a
 * file goes under. Three rules, each of which is a bug if it gets it wrong:
 *
 *  - **Digits and symbols group under `#`.** Many real folders start with a digit
 *    (`2026-11-11_APK`), and dropping them into "A" because someone compared
 *    `'2' < 'a'` incorrectly is worse than giving them their own group.
 *  - **Accents fold to their base letter.** `Ékspor` belongs under E, not in a
 *    group nothing can reach.
 *  - **Case is never significant.**
 *
 * All of it is plain Kotlin over strings so the JVM tests cover the cases a phone
 * camera would be needed to check by hand otherwise.
 */
object Alphabet {

    /** The header used for anything that is not a Latin letter. */
    const val OTHER: String = "#"

    /**
     * The section letter for one name.
     *
     * Returns [OTHER] for an empty name rather than throwing: a listing can contain
     * a name the filesystem allows and the UI should still render.
     */
    fun sectionOf(name: String): String {
        val first = name.trim().firstOrNull() ?: return OTHER
        val folded = fold(first)
        return if (folded in 'a'..'z') folded.uppercase(Locale.US) else OTHER
    }

    /**
     * Groups entries under their section letters, in alphabetical order with `#`
     * last.
     *
     * Folders and files are kept in the order they arrive, so a caller that already
     * sorted folders-first keeps that property; this only buckets.
     */
    fun group(entries: List<FileEntry>): List<Pair<String, List<FileEntry>>> {
        val buckets = LinkedHashMap<String, MutableList<FileEntry>>()
        for (e in entries) {
            buckets.getOrPut(sectionOf(e.name)) { mutableListOf() }.add(e)
        }
        return buckets.entries
            .sortedWith(compareBy({ it.key == OTHER }, { it.key }))
            .map { it.key to it.value.toList() }
    }

    /**
     * Lowercase and strip the diacritics that Indonesian and European file names
     * actually contain.
     *
     * A table beats `java.text.Normalizer` here: Normalizer is fine on the JVM but
     * needs care on older Android runtimes, and the set of characters that shows up
     * in a file name is small and known.
     */
    fun fold(c: Char): Char = when (c.lowercaseChar()) {
        'à', 'á', 'â', 'ã', 'ä', 'å', 'ā', 'ă', 'ą' -> 'a'
        'ç', 'ć', 'č' -> 'c'
        'ď', 'đ' -> 'd'
        'è', 'é', 'ê', 'ë', 'ē', 'ė', 'ę' -> 'e'
        'ğ' -> 'g'
        'ì', 'í', 'î', 'ï', 'ī', 'į' -> 'i'
        'ł', 'ľ', 'ñ', 'ń' -> 'n'
        'ò', 'ó', 'ô', 'õ', 'ö', 'ø', 'ō', 'ő' -> 'o'
        'ř', 'ŕ' -> 'r'
        'ś', 'š', 'ş' -> 's'
        'ť', 'ţ' -> 't'
        'ù', 'ú', 'û', 'ü', 'ū', 'ů', 'ű' -> 'u'
        'ý', 'ÿ' -> 'y'
        'ž', 'ź', 'ż' -> 'z'
        else -> c.lowercaseChar()
    }

    /** Every letter the strip draws, in order, with the fallback last. */
    val sections: List<String>
        get() = ('A'..'Z').map { it.toString() } + OTHER
}
