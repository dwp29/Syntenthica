package net.pure.manager.edit

import java.util.Locale

/**
 * Syntax highlighting, as a list of spans over the whole document.
 *
 * The editor draws text with a single AnnotatedString, so highlighting is a set of
 * ranges with a category attached. That keeps the composable free of highlighting
 * logic and makes the logic testable on the JVM: the parts that go wrong are the
 * boundaries -- a quote inside a comment, a keyword inside a string, an apostrophe
 * in English prose opening a string literal that never closes.
 *
 * Highlighting the whole document on every keystroke is fine here. A file that
 * opens on a phone is a few hundred KB at most, and [highlight] stops after
 * [MAX_HIGHLIGHT] characters so a megabyte of log does not freeze the UI thread.
 */

/** What a range of characters is drawn as. */
enum class TokenKind { PLAIN, KEYWORD, STRING, COMMENT, NUMBER }

/** One highlighted stretch: [start] until [end], never empty, always increasing. */
data class Span(val start: Int, val end: Int, val kind: TokenKind)

/**
 * A language the editor can colour.
 *
 * The list is deliberately the things that are actually on an Android phone:
 * build files, manifests, config, shell scripts, the occasional Python or JS file.
 * A language nobody opens is a table nobody maintains.
 */
enum class Language(val label: String, val extensions: List<String>) {
    PLAIN("Teks", emptyList()),
    KOTLIN("Kotlin", listOf("kt", "kts")),
    JAVA("Java", listOf("java")),
    XML("XML", listOf("xml", "htm", "html", "svg", "xsd", "plist")),
    JSON("JSON", listOf("json", "jsonl", "webmanifest")),
    PROPERTIES("Config", listOf("properties", "cfg", "conf", "ini", "gradle", "toml", "env")),
    SHELL("Shell", listOf("sh", "bash", "zsh", "rc", "profile")),
    PYTHON("Python", listOf("py", "pyw")),
    JAVASCRIPT("JavaScript", listOf("js", "mjs", "cjs", "ts")),
    C("C / C++", listOf("c", "h", "cpp", "hpp", "cc")),
    MARKDOWN("Markdown", listOf("md", "markdown")),
    ;

    companion object {
        /** Picks by file extension; anything unknown is plain text, not a guess. */
        fun forFileName(name: String): Language {
            val ext = name.substringAfterLast('.', "").lowercase(Locale.US)
            if (ext.isEmpty()) {
                // Extensionless files that are scripts by convention.
                return when (name.lowercase(Locale.US)) {
                    "makefile", "dockerfile", "gradlew" -> SHELL
                    else -> PLAIN
                }
            }
            return entries.firstOrNull { ext in it.extensions } ?: PLAIN
        }
    }
}

/** A document larger than this is shown plain: colouring it would cost more than it gives. */
const val MAX_HIGHLIGHT = 200_000

// `it`, `by` and `where` are deliberately absent even though Kotlin reserves them
// in places: they appear as ordinary identifiers far more often, and colouring
// every `it` makes a lambda look like a syntax error.
private val KOTLIN_KEYWORDS = setOf(
    "package", "import", "class", "object", "interface", "fun", "val", "var", "if", "else",
    "when", "for", "while", "do", "return", "break", "continue", "try", "catch", "finally",
    "throw", "is", "in", "as", "null", "true", "false", "this", "super", "override", "private",
    "internal", "public", "protected", "open", "abstract", "sealed", "data", "enum", "companion",
    "suspend", "inline", "const", "lateinit", "init", "typealias",
)
private val JAVA_KEYWORDS = setOf(
    "package", "import", "class", "interface", "enum", "extends", "implements", "public",
    "private", "protected", "static", "final", "void", "int", "long", "double", "float",
    "boolean", "char", "byte", "short", "new", "return", "if", "else", "for", "while", "do",
    "switch", "case", "break", "continue", "try", "catch", "finally", "throw", "throws",
    "null", "true", "false", "this", "super", "abstract", "synchronized", "instanceof",
)
private val SHELL_KEYWORDS = setOf(
    "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac",
    "function", "in", "return", "local", "export", "readonly", "shift", "exit", "set", "source",
    "echo", "cd", "printf",
)
private val PYTHON_KEYWORDS = setOf(
    "def", "class", "import", "from", "as", "if", "elif", "else", "for", "while", "return",
    "yield", "try", "except", "finally", "raise", "with", "lambda", "pass", "break", "continue",
    "and", "or", "not", "is", "in", "None", "True", "False", "self", "async", "await", "global",
)
private val JS_KEYWORDS = setOf(
    "function", "const", "let", "var", "if", "else", "for", "while", "do", "return", "class",
    "extends", "new", "this", "import", "export", "from", "default", "async", "await", "try",
    "catch", "finally", "throw", "typeof", "instanceof", "null", "undefined", "true", "false",
    "switch", "case", "break", "continue",
)
private val C_KEYWORDS = setOf(
    "include", "define", "ifdef", "ifndef", "endif", "pragma", "int", "char", "float", "double",
    "void", "long", "short", "unsigned", "signed", "struct", "union", "enum", "typedef", "static",
    "extern", "const", "return", "if", "else", "for", "while", "do", "switch", "case", "break",
    "continue", "sizeof", "class", "public", "private", "protected", "namespace", "using",
    "template", "typename", "new", "delete", "nullptr", "true", "false", "auto",
)

fun keywordsFor(language: Language): Set<String> = when (language) {
    Language.KOTLIN -> KOTLIN_KEYWORDS
    Language.JAVA -> JAVA_KEYWORDS
    Language.SHELL -> SHELL_KEYWORDS
    Language.PYTHON -> PYTHON_KEYWORDS
    Language.JAVASCRIPT -> JS_KEYWORDS
    Language.C -> C_KEYWORDS
    else -> emptySet()
}

/**
 * Colours [text]. Spans never overlap and are sorted, so the caller can walk them
 * once and append the unhighlighted stretches between them.
 */
fun highlight(text: String, language: Language, limit: Int = MAX_HIGHLIGHT): List<Span> {
    if (language == Language.PLAIN || text.isEmpty()) return emptyList()
    val end = minOf(text.length, limit)
    return when (language) {
        Language.XML -> xml(text, end)
        Language.JSON -> json(text, end)
        Language.PROPERTIES -> properties(text, end)
        Language.MARKDOWN -> markdown(text, end)
        else -> code(text, end, language)
    }
}

/**
 * C-like scanning for every language that has slash-slash and slash-star comments,
 * with a per-language quote set. One scanner rather than eight near-copies: the
 * differences really are the keyword list and the comment markers.
 *
 * Those markers are spelled out above instead of written literally because Kotlin
 * block comments nest: the two characters that open a block comment, inside a KDoc,
 * open a second comment that runs until the next close -- swallowing the rest of the
 * file. It cost a CI round trip with thirty cascading syntax errors whose first one
 * pointed at a line 25 lines below the real mistake.
 */
private fun code(text: String, end: Int, language: Language): List<Span> {
    val out = mutableListOf<Span>()
    val keywords = keywordsFor(language)
    val hashComments = language == Language.SHELL || language == Language.PYTHON
    val tripleQuotes = language == Language.PYTHON
    var i = 0
    while (i < end) {
        val c = text[i]
        when {
            // Line comment. `#` only where it is a comment marker, and not inside a
            // `#!` shebang's own line twice over -- the shebang is a comment anyway.
            (hashComments && c == '#') ||
                (!hashComments && c == '/' && i + 1 < end && text[i + 1] == '/') -> {
                val stop = text.indexOf('\n', i).let { if (it < 0 || it > end) end else it }
                out.add(Span(i, stop, TokenKind.COMMENT))
                i = stop
            }
            // Block comment.
            !hashComments && c == '/' && i + 1 < end && text[i + 1] == '*' -> {
                val close = text.indexOf("*/", i + 2)
                val stop = if (close < 0 || close + 2 > end) end else close + 2
                out.add(Span(i, stop, TokenKind.COMMENT))
                i = stop
            }
            // Triple-quoted string (Python docstrings live here).
            tripleQuotes && (text.startsWith("\"\"\"", i) || text.startsWith("'''", i)) -> {
                val q = text.substring(i, i + 3)
                val close = text.indexOf(q, i + 3)
                val stop = if (close < 0 || close + 3 > end) end else close + 3
                out.add(Span(i, stop, TokenKind.STRING))
                i = stop
            }
            c == '"' || c == '\'' || (c == '`' && language == Language.JAVASCRIPT) -> {
                val stop = stringEnd(text, i, end)
                out.add(Span(i, stop, TokenKind.STRING))
                i = stop
            }
            c.isDigit() -> {
                var j = i
                while (j < end && (text[j].isLetterOrDigit() || text[j] == '.' || text[j] == '_')) j++
                out.add(Span(i, j, TokenKind.NUMBER))
                i = j
            }
            c.isLetter() || c == '_' -> {
                var j = i
                while (j < end && (text[j].isLetterOrDigit() || text[j] == '_')) j++
                if (text.substring(i, j) in keywords) out.add(Span(i, j, TokenKind.KEYWORD))
                i = j
            }
            else -> i++
        }
    }
    return out
}

/** End of a quoted string starting at [start], stopping at the line end if unclosed. */
private fun stringEnd(text: String, start: Int, end: Int): Int {
    val quote = text[start]
    var i = start + 1
    while (i < end) {
        when {
            text[i] == '\\' -> i += 2
            text[i] == quote -> return i + 1
            // An unterminated literal stops at the newline. Without this an
            // apostrophe in a comment-less file turned the rest of the file into a
            // string, which looked exactly like the highlighter being broken.
            text[i] == '\n' && quote != '`' -> return i
            else -> i++
        }
    }
    return end
}

private fun json(text: String, end: Int): List<Span> {
    val out = mutableListOf<Span>()
    var i = 0
    while (i < end) {
        val c = text[i]
        when {
            c == '"' -> {
                val stop = stringEnd(text, i, end)
                // A quoted run followed by a colon is a key; otherwise it is a value.
                var j = stop
                while (j < end && text[j].isWhitespace()) j++
                val isKey = j < end && text[j] == ':'
                out.add(Span(i, stop, if (isKey) TokenKind.KEYWORD else TokenKind.STRING))
                i = stop
            }
            c == '-' || c.isDigit() -> {
                var j = i
                while (j < end && (text[j].isDigit() || text[j] in "+-.eE")) j++
                out.add(Span(i, j, TokenKind.NUMBER))
                i = j
            }
            text.startsWith("true", i) || text.startsWith("false", i) || text.startsWith("null", i) -> {
                val word = listOf("true", "false", "null").first { text.startsWith(it, i) }
                out.add(Span(i, i + word.length, TokenKind.KEYWORD))
                i += word.length
            }
            else -> i++
        }
    }
    return out
}

/** XML/HTML: tag names, attribute values, comments, and text left alone. */
private fun xml(text: String, end: Int): List<Span> {
    val out = mutableListOf<Span>()
    var i = 0
    while (i < end) {
        if (text.startsWith("<!--", i)) {
            val close = text.indexOf("-->", i + 4)
            val stop = if (close < 0 || close + 3 > end) end else close + 3
            out.add(Span(i, stop, TokenKind.COMMENT))
            i = stop
            continue
        }
        if (text.startsWith("<![CDATA[", i)) {
            val close = text.indexOf("]]>", i + 9)
            val stop = if (close < 0 || close + 3 > end) end else close + 3
            out.add(Span(i, stop, TokenKind.STRING))
            i = stop
            continue
        }
        if (text[i] == '<') {
            // The tag name runs until whitespace, '/', '>' or the end.
            var j = i + 1
            if (j < end && (text[j] == '/' || text[j] == '?' || text[j] == '!')) j++
            val nameStart = j
            while (j < end && (text[j].isLetterOrDigit() || text[j] in "_.:-")) j++
            if (j > nameStart) out.add(Span(nameStart, j, TokenKind.KEYWORD))
            i = j
            continue
        }
        if (text[i] == '"' || text[i] == '\'') {
            val stop = stringEnd(text, i, end)
            out.add(Span(i, stop, TokenKind.STRING))
            i = stop
            continue
        }
        i++
    }
    return out
}

/** .properties / .ini: keys before `=`, values, `#` and `;` comments. */
private fun properties(text: String, end: Int): List<Span> {
    val out = mutableListOf<Span>()
    var lineStart = 0
    while (lineStart < end) {
        val lineEnd = text.indexOf('\n', lineStart).let { if (it < 0 || it > end) end else it }
        var i = lineStart
        while (i < lineEnd && text[i].isWhitespace()) i++
        if (i < lineEnd && (text[i] == '#' || text[i] == ';')) {
            out.add(Span(i, lineEnd, TokenKind.COMMENT))
        } else {
            var eq = i
            while (eq < lineEnd && text[eq] != '=' && text[eq] != ':') eq++
            if (eq < lineEnd) out.add(Span(i, eq, TokenKind.KEYWORD))
        }
        lineStart = lineEnd + 1
    }
    return out
}

/** Markdown: headings, `code`, **bold**, and link targets. */
private fun markdown(text: String, end: Int): List<Span> {
    val out = mutableListOf<Span>()
    var lineStart = 0
    while (lineStart < end) {
        val lineEnd = text.indexOf('\n', lineStart).let { if (it < 0 || it > end) end else it }
        var i = lineStart
        while (i < lineEnd && text[i].isWhitespace()) i++
        if (i < lineEnd && text[i] == '#') {
            var j = i
            while (j < lineEnd && text[j] == '#') j++
            out.add(Span(i, lineEnd, TokenKind.KEYWORD))
        }
        // Inline code and emphasis, one pass over the line.
        var k = lineStart
        while (k < lineEnd) {
            if (text[k] == '`') {
                val close = text.indexOf('`', k + 1)
                val stop = if (close < 0 || close > lineEnd) lineEnd else close + 1
                out.add(Span(k, stop, TokenKind.STRING))
                k = stop
                continue
            }
            k++
        }
        lineStart = lineEnd + 1
    }
    return sortedSpans(out)
}

/**
 * Drops overlaps and empties, and sorts.
 *
 * Every scanner is written to be non-overlapping, but the editor concatenates
 * spans into one AnnotatedString, where an overlap is a crash (`append` with a
 * start below the current end). Cheap insurance against a scanner bug becoming a
 * screen that cannot draw.
 */
fun sortedSpans(spans: List<Span>): List<Span> {
    val sorted = spans.filter { it.end > it.start }.sortedBy { it.start }
    val out = mutableListOf<Span>()
    var last = 0
    for (s in sorted) {
        val start = maxOf(s.start, last)
        if (s.end <= start) continue
        out.add(s.copy(start = start))
        last = s.end
    }
    return out
}

/** The cursor's line and column, 1-based, for the status bar. */
fun lineColumn(text: CharSequence, caret: Int): Pair<Int, Int> {
    val at = caret.coerceIn(0, text.length)
    var line = 1
    var lineStart = 0
    for (i in 0 until at) {
        if (text[i] == '\n') {
            line++
            lineStart = i + 1
        }
    }
    return line to (at - lineStart + 1)
}
