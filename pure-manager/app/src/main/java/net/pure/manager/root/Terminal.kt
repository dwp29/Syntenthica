package net.pure.manager.root

/**
 * A small command line.
 *
 * Not a terminal emulator: there is no pty, no cursor addressing, no `top`. It runs
 * one command at a time through [Shell], keeps a scrollback and a current
 * directory, and supports the handful of built-ins a person actually types
 * (`cd`, `pwd`, `clear`, `exit`). `top`, `vi` and anything else that redraws the
 * screen will not work here, and pretending otherwise in the UI would be a lie.
 *
 * Keeping it a plain class with injected I/O means the JVM tests can drive the
 * whole thing: command parsing, `cd ..`, history, and the refusal to run when root
 * is missing.
 */
class Terminal(
    private val binary: String?,
    private val homeDirectory: String = "/",
    private val timeoutSeconds: Long = 20L,
    // Defaults to the real shell; a test passes its own so the whole class can be
    // driven with `sh`. The timeout is the constructor field, otherwise shortening
    // it in a test would leave a hidden 20 seconds behind.
    private val runner: (String, String) -> Shell.Output = { bin, cmd ->
        Shell.run(bin, cmd, timeoutSeconds = timeoutSeconds)
    },
) {

    /** One printed line. [isCommand] lets the UI shade what the user typed. */
    data class Line(val text: String, val isCommand: Boolean = false, val isError: Boolean = false)

    private val buffer = mutableListOf<Line>()

    var directory: String = homeDirectory
        private set

    /** Commands typed this session, newest last. */
    val history: MutableList<String> = mutableListOf()

    val lines: List<Line> get() = buffer.toList()

    val hasRoot: Boolean get() = binary != null

    /** The prompt string, e.g. `root@android:/sdcard #`. */
    fun prompt(): String =
        if (hasRoot) "root:$directory #" else "tanpa-root:$directory $"

    fun clear() {
        buffer.clear()
    }

    /**
     * Runs one line and appends its output.
     *
     * Returns false when the user typed `exit`, which is the only signal the UI
     * needs to close the terminal.
     */
    fun submit(raw: String): Boolean {
        val input = raw.trim()
        if (input.isEmpty()) return true
        history += input
        buffer += Line(prompt() + " " + input, isCommand = true)

        when (input) {
            "exit", "keluar" -> return false
            "clear", "cls" -> {
                clear()
                return true
            }
            "pwd" -> {
                buffer += Line(directory)
                return true
            }
            "help", "bantuan" -> {
                buffer += Line(
                    "Perintah bawaan: cd, pwd, ls, clear, exit.\n" +
                        "Selain itu dijalankan lewat shell. Tanpa pty, jadi top/vi " +
                        "tidak akan tampil benar.",
                )
                return true
            }
        }
        if (input == "cd" || input.startsWith("cd ")) {
            changeDirectory(input.removePrefix("cd").trim())
            return true
        }

        val root = binary
        if (root == null) {
            buffer += Line(
                "Belum ada akses root. Buka Setelan → Root untuk memeriksa dan " +
                    "meminta izin. Perintah biasa tetap bisa dijalankan tanpa root.",
                isError = true,
            )
            return true
        }

        // `cd <dir> && <command>` so that a relative path in the command means what
        // the prompt says it means. The cd is inside the same shell, so it cannot
        // affect this process.
        val wrapped = "cd " + Shell.quote(directory) + " && " + input
        val result = runner(root, wrapped)
        val text = buildString {
            if (result.output.isNotBlank()) append(result.output.trimEnd())
            if (result.error.isNotBlank()) {
                if (isNotEmpty()) append('\n')
                append(result.error.trimEnd())
            }
            if (result.code != 0) {
                if (isNotEmpty()) append('\n')
                append("[kode ${result.code}]")
            }
            if (isEmpty()) append("(tidak ada keluaran)")
        }
        buffer += Line(text, isError = !result.ok)
        // Cap the scrollback: a `find /` can print a hundred thousand lines, and a
        // list that never shrinks is how the app runs out of memory.
        if (buffer.size > MAX_LINES) {
            val drop = buffer.size - MAX_LINES
            repeat(drop) { buffer.removeAt(0) }
        }
        return true
    }

    private fun changeDirectory(arg: String) {
        val target = when {
            arg.isEmpty() -> homeDirectory
            arg == "~" -> homeDirectory
            arg.startsWith("/") -> arg
            else -> directory.trimEnd('/') + "/" + arg
        }
        // Normalise .. without touching the filesystem: a symlinked folder makes
        // canonicalisation surprising, and the shell below resolves the real path
        // anyway.
        val resolved = normalise(target)
        if (exists(resolved)) {
            directory = resolved
        } else {
            buffer += Line("cd: tidak ada folder $resolved", isError = true)
        }
    }

    companion object {
        const val MAX_LINES: Int = 500

        /** Collapses `.` and `..` and duplicate slashes. Pure string work. */
        fun normalise(path: String): String {
            val absolute = path.startsWith("/")
            val parts = mutableListOf<String>()
            for (part in path.split('/')) {
                when (part) {
                    "", "." -> Unit
                    ".." -> if (parts.isNotEmpty()) parts.removeAt(parts.size - 1)
                    else -> parts += part
                }
            }
            val joined = parts.joinToString("/")
            return if (absolute) "/$joined" else joined.ifEmpty { "." }
        }
    }
}

/** Whether a directory exists; separated so [Terminal] stays testable. */
internal fun exists(path: String): Boolean = java.io.File(path).isDirectory
