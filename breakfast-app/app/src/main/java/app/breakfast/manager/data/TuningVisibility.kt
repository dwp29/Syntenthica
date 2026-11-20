package app.breakfast.manager.data

/**
 * Which whitelist parameters TUNING actually renders as a row.
 *
 * This used to be a hardcoded list in the screen, and it was wrong: it claimed
 * `iowait_boost_enable` was shown in its group, while the group only draws nodes
 * it can use, so the parameter appeared nowhere at all. A device with a real
 * iowait_boost_enable node showed no row for it.
 *
 * The rule is derived from the same conditions the groups use, so it cannot
 * drift from them, and it is a pure function so a test can hold it still.
 */
object TuningVisibility {

    private fun usable(report: DeviceAudit.Report, key: String): DeviceAudit.Node? =
        report.nodes.firstOrNull { DeviceAudit.nodeToKey(it.path) == key }
            ?.takeIf {
                it.support == DeviceAudit.Support.SUPPORTED ||
                    it.support == DeviceAudit.Support.READ_ONLY
            }

    fun renderedKeys(report: DeviceAudit.Report): Set<String> {
        val keys = mutableSetOf<String>()
        // ZRAM: a row is drawn for comp_algorithm when it has a value we can
        // read, for mem_limit when the node exists at all (slider or status
        // row), and for disksize only when it can actually be changed.
        usable(report, "zram_comp_algorithm")
            ?.value?.takeIf { it.isNotBlank() }
            ?.let { keys += "zram_comp_algorithm" }
        if (report.nodes.any { DeviceAudit.nodeToKey(it.path) == "zram_mem_limit" }) {
            keys += "zram_mem_limit"
        }
        // disksize is drawn whenever the audit recorded it, whatever the verdict,
        // because its row explains why it cannot be changed.
        if (report.nodes.any { DeviceAudit.nodeToKey(it.path) == "zram_disksize" }) {
            keys += "zram_disksize"
        }
        // SCHEDUTIL: every node the group can display.
        for (key in listOf("schedutil_up_rate", "schedutil_down_rate", "schedutil_iowait")) {
            if (usable(report, key) != null) keys += key
        }
        return keys
    }

    /** Whitelist keys with no row on screen; these must be listed, never hidden. */
    fun missingKeys(report: DeviceAudit.Report): List<TuningWhitelist.Parameter> {
        val rendered = renderedKeys(report)
        return TuningWhitelist.PARAMETERS.filter { it.key !in rendered }
    }
}
