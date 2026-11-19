package app.breakfast.manager.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persists the last audit report.
 *
 * Storage is deliberately plain JSON in shared preferences rather than a
 * database: the payload is one report for one kernel, and a schema that can be
 * read by eye is easier to trust than a migration path.
 *
 * The kernel release is stored with the report because it is the key that
 * decides whether the report may be used at all after a flash.
 */
class AuditStore(context: Context) {

    private val prefs = context.getSharedPreferences("breakfast.audit", Context.MODE_PRIVATE)

    fun load(): DeviceAudit.Report? {
        val raw = prefs.getString(KEY_REPORT, null) ?: return null
        return try {
            fromJson(JSONObject(raw))
        } catch (e: Exception) {
            // A corrupt report must not crash the app or silently disappear into
            // a "never audited" state that hides the corruption.
            prefs.edit().remove(KEY_REPORT).apply()
            null
        }
    }

    fun save(report: DeviceAudit.Report) {
        prefs.edit().putString(KEY_REPORT, toJson(report).toString()).apply()
    }

    fun clear() {
        prefs.edit().remove(KEY_REPORT).apply()
    }

    fun lastAuditMs(): Long? = load()?.timestampMs

    companion object {
        private const val KEY_REPORT = "report.v1"

        fun toJson(report: DeviceAudit.Report): JSONObject {
            val nodes = JSONArray()
            for (node in report.nodes) {
                nodes.put(
                    JSONObject().apply {
                        put("group", node.group)
                        put("path", node.path)
                        put("support", node.support.name)
                        put("permissions", node.nodePermissions ?: JSONObject.NULL)
                        put("readable", node.readable)
                        put("value", node.value ?: JSONObject.NULL)
                        put("note", node.note ?: JSONObject.NULL)
                    }
                )
            }
            return JSONObject().apply {
                put("version", 1)
                put("kernel", report.kernelRelease)
                put("timestamp", report.timestampMs)
                put("nodes", nodes)
            }
        }

        fun fromJson(json: JSONObject): DeviceAudit.Report {
            if (json.getInt("version") != 1) throw IllegalArgumentException("unsupported audit version")
            val array = json.getJSONArray("nodes")
            val nodes = (0 until array.length()).map { index ->
                val node = array.getJSONObject(index)
                DeviceAudit.Node(
                    group = node.getString("group"),
                    path = node.getString("path"),
                    support = DeviceAudit.Support.valueOf(node.getString("support")),
                    nodePermissions = if (node.isNull("permissions")) null else node.getString("permissions"),
                    readable = node.getBoolean("readable"),
                    value = if (node.isNull("value")) null else node.getString("value"),
                    note = if (node.isNull("note")) null else node.getString("note"),
                )
            }
            return DeviceAudit.Report(
                kernelRelease = json.getString("kernel"),
                timestampMs = json.getLong("timestamp"),
                nodes = nodes,
            )
        }
    }
}
