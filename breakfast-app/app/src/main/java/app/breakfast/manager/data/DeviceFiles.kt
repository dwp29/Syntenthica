package app.breakfast.manager.data

import java.io.File

/**
 * Reads device nodes through the kernel directly, with no shell in between.
 *
 * If the app has not been granted root this simply fails with a permission
 * error, which the engine reports as "permission denied" rather than pretending
 * the node does not exist. That distinction is the whole point of the four
 * failure messages.
 */
object DeviceFiles : TuningEngine.Files {

    override fun exists(path: String): Boolean = try {
        File(path).exists()
    } catch (e: SecurityException) {
        false
    }

    override fun read(path: String): String? = try {
        File(path).readText()
    } catch (e: Exception) {
        null
    }

    override fun write(path: String, value: String): Boolean = try {
        File(path).writeText(value)
        true
    } catch (e: Exception) {
        false
    }
}
