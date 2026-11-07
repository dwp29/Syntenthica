package com.rifsxd.ksunext.ui.device

/** Only explicitly selected sections are copied; callers provide visible values. */
internal data class SummarySection(
    val id: String,
    val title: String,
    val fields: List<Pair<String, String>>,
)

internal fun renderSelectedSummary(title: String, sections: List<SummarySection>, selected: Set<String>): String {
    val chosen = sections.filter { it.id in selected }
    if (chosen.isEmpty()) return ""
    fun safe(value: String): String = value.replace(Regex("[\\p{Cntrl}\\p{Cf}]"), " ").trim()
    return buildString {
        appendLine(safe(title))
        chosen.forEach { section ->
            appendLine()
            appendLine(safe(section.title))
            section.fields.forEach { (label, value) ->
                append(safe(label)).append(": ").appendLine(safe(value))
            }
        }
    }.trimEnd()
}
