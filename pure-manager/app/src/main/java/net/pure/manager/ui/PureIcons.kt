package net.pure.manager.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathBuilder
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Outline icons, drawn here rather than pulled from a library.
 *
 * The screens used to print Unicode characters as icons: `\u25A4` for a folder,
 * `\u2699` for settings, `\u2295` for "new folder". Those code points are text, so
 * they inherit a text baseline, a text weight and whatever glyph the system font
 * happens to have -- a hollow square where an archive icon belongs, an envelope in
 * place of a gear on some devices. That is what made the app look assembled from a
 * character map rather than designed.
 *
 * The replacement is a small set of 24x24 stroke icons on the same grid Apple uses
 * (1.7 stroke, round caps and joins), so they line up with each other and with the
 * system's own icons. Drawing them here keeps the dependency list unchanged: the
 * Material icon artifact is another 300 KB of resources for eleven shapes.
 *
 * A word on the paths: they are geometry, not traced artwork. Nothing in this file
 * is copied from a font or a vendor icon set.
 */
object PureIcons {

    // ---------------------------------------------------------------- viewport
    // Every icon lives on a 24x24 grid with a 2 dp margin, so any of them can be
    // dropped next to any other without looking a size off.
    private const val GRID = 24f

    private fun icon(name: String, build: ImageVector.Builder.() -> Unit): ImageVector =
        ImageVector.Builder(
            name = name,
            defaultWidth = GRID.dp,
            defaultHeight = GRID.dp,
            viewportWidth = GRID,
            viewportHeight = GRID,
        ).apply(build).build()

    /**
     * One stroke path. Round caps and joins are what separate these from the
     * square-cornered look the old glyphs had, and the 1.7 units are what keep
     * eleven differently shaped icons looking like one family.
     */
    private fun ImageVector.Builder.stroke(
        width: Float = 1.7f,
        build: PathBuilder.() -> Unit,
    ) {
        path(
            fill = null,
            stroke = SolidColor(Color.Black),
            strokeLineWidth = width,
            strokeLineCap = StrokeCap.Round,
            strokeLineJoin = StrokeJoin.Round,
            pathBuilder = build,
        )
    }

    private fun ImageVector.Builder.solid(build: PathBuilder.() -> Unit) {
        path(fill = SolidColor(Color.Black), pathBuilder = build)
    }

    /**
     * An icon built from one character, rendered as geometry instead of text.
     *
     * This exists for three shapes where a glyph is genuinely the right drawing --
     * a plus, a minus, an arrow. The difference from the text it replaces is that
     * the character sits on a 24x24 viewport with an explicit font size, so it is
     * centred by construction rather than by whatever line height the theme's
     * typography picked. A `+` at 24 sp in body text sits low in its box, which is
     * exactly the off-centre look the old toolbar had.
     *
     * The font is monospace on purpose: it is the one family Android guarantees to
     * have a complete set of these marks, and no width variation between them.
     */
    private fun textIcon(name: String, mark: String): ImageVector =
        ImageVector.Builder(
            name = name,
            defaultWidth = GRID.dp,
            defaultHeight = GRID.dp,
            viewportWidth = GRID,
            viewportHeight = GRID,
        ).addText(
            text = mark,
            fontSize = 17.sp,
            fontFamily = FontFamily.Monospace,
            x = GRID / 2f,
            y = GRID * 0.72f,
            textAlign = TextAlign.Center,
            style = TextStyle(color = Color.Black),
        ).build()

    // ------------------------------------------------------------------ files

    /** Folder, closed: the tab on the left and a body with two rounded corners. */
    val Folder: ImageVector by lazy {
        icon("Folder") {
            stroke {
                moveTo(3.2f, 7.4f)
                verticalLineTo(5.6f)
                curveTo(3.2f, 5.0f, 3.7f, 4.5f, 4.3f, 4.5f)
                horizontalLineTo(9.0f)
                curveTo(9.4f, 4.5f, 9.8f, 4.7f, 10.1f, 5.0f)
                lineTo(11.5f, 6.9f)
                horizontalLineTo(19.7f)
                curveTo(20.3f, 6.9f, 20.8f, 7.4f, 20.8f, 8.0f)
                verticalLineTo(18.0f)
                curveTo(20.8f, 18.6f, 20.3f, 19.1f, 19.7f, 19.1f)
                horizontalLineTo(4.3f)
                curveTo(3.7f, 19.1f, 3.2f, 18.6f, 3.2f, 18.0f)
                close()
            }
        }
    }

    /** Document with a folded corner. */
    val Document: ImageVector by lazy {
        icon("Document") {
            stroke {
                moveTo(13.6f, 3.6f)
                horizontalLineTo(6.6f)
                curveTo(5.9f, 3.6f, 5.4f, 4.1f, 5.4f, 4.8f)
                verticalLineTo(19.2f)
                curveTo(5.4f, 19.9f, 5.9f, 20.4f, 6.6f, 20.4f)
                horizontalLineTo(17.4f)
                curveTo(18.1f, 20.4f, 18.6f, 19.9f, 18.6f, 19.2f)
                verticalLineTo(8.6f)
                close()
                moveTo(13.6f, 3.6f)
                verticalLineTo(8.6f)
                horizontalLineTo(18.6f)
            }
        }
    }

    /** Picture: frame, horizon, sun. */
    val Image: ImageVector by lazy {
        icon("Image") {
            stroke {
                moveTo(5.0f, 4.6f)
                horizontalLineTo(19.0f)
                curveTo(19.9f, 4.6f, 20.6f, 5.3f, 20.6f, 6.2f)
                verticalLineTo(17.8f)
                curveTo(20.6f, 18.7f, 19.9f, 19.4f, 19.0f, 19.4f)
                horizontalLineTo(5.0f)
                curveTo(4.1f, 19.4f, 3.4f, 18.7f, 3.4f, 17.8f)
                verticalLineTo(6.2f)
                curveTo(3.4f, 5.3f, 4.1f, 4.6f, 5.0f, 4.6f)
                close()
            }
            stroke {
                moveTo(3.8f, 16.2f)
                lineTo(8.4f, 11.6f)
                curveTo(8.9f, 11.1f, 9.6f, 11.1f, 10.1f, 11.6f)
                lineTo(14.2f, 15.7f)
            }
            stroke {
                moveTo(12.6f, 14.1f)
                lineTo(15.4f, 11.3f)
                curveTo(15.9f, 10.8f, 16.6f, 10.8f, 17.1f, 11.3f)
                lineTo(20.4f, 14.6f)
            }
            solid {
                moveTo(8.6f, 6.9f)
                curveTo(9.4f, 6.9f, 10.0f, 7.5f, 10.0f, 8.3f)
                curveTo(10.0f, 9.1f, 9.4f, 9.7f, 8.6f, 9.7f)
                curveTo(7.8f, 9.7f, 7.2f, 9.1f, 7.2f, 8.3f)
                curveTo(7.2f, 7.5f, 7.8f, 6.9f, 8.6f, 6.9f)
                close()
            }
        }
    }

    /** Video: a rounded rectangle with a play triangle inside. */
    val Video: ImageVector by lazy {
        icon("Video") {
            stroke {
                moveTo(5.0f, 5.2f)
                horizontalLineTo(19.0f)
                curveTo(19.9f, 5.2f, 20.6f, 5.9f, 20.6f, 6.8f)
                verticalLineTo(17.2f)
                curveTo(20.6f, 18.1f, 19.9f, 18.8f, 19.0f, 18.8f)
                horizontalLineTo(5.0f)
                curveTo(4.1f, 18.8f, 3.4f, 18.1f, 3.4f, 17.2f)
                verticalLineTo(6.8f)
                curveTo(3.4f, 5.9f, 4.1f, 5.2f, 5.0f, 5.2f)
                close()
            }
            solid {
                moveTo(10.3f, 8.8f)
                lineTo(15.6f, 12.0f)
                lineTo(10.3f, 15.2f)
                close()
            }
        }
    }

    /** Music: a note with a stem. */
    val Music: ImageVector by lazy {
        icon("Music") {
            stroke {
                moveTo(9.6f, 17.4f)
                verticalLineTo(6.2f)
                lineTo(19.0f, 4.4f)
                verticalLineTo(15.2f)
            }
            solid {
                moveTo(6.6f, 15.6f)
                curveTo(7.9f, 15.6f, 9.0f, 16.5f, 9.0f, 17.6f)
                curveTo(9.0f, 18.8f, 7.9f, 19.7f, 6.6f, 19.7f)
                curveTo(5.3f, 19.7f, 4.2f, 18.8f, 4.2f, 17.6f)
                curveTo(4.2f, 16.5f, 5.3f, 15.6f, 6.6f, 15.6f)
                close()
            }
            solid {
                moveTo(16.0f, 13.4f)
                curveTo(17.3f, 13.4f, 18.4f, 14.3f, 18.4f, 15.4f)
                curveTo(18.4f, 16.6f, 17.3f, 17.5f, 16.0f, 17.5f)
                curveTo(14.7f, 17.5f, 13.6f, 16.6f, 13.6f, 15.4f)
                curveTo(13.6f, 14.3f, 14.7f, 13.4f, 16.0f, 13.4f)
                close()
            }
        }
    }

    /** Archive: a box with a lid and a handle slot. */
    val Archive: ImageVector by lazy {
        icon("Archive") {
            stroke {
                moveTo(4.0f, 8.4f)
                horizontalLineTo(20.0f)
                verticalLineTo(18.4f)
                curveTo(20.0f, 19.2f, 19.4f, 19.8f, 18.6f, 19.8f)
                horizontalLineTo(5.4f)
                curveTo(4.6f, 19.8f, 4.0f, 19.2f, 4.0f, 18.4f)
                close()
            }
            stroke {
                moveTo(3.4f, 4.2f)
                horizontalLineTo(20.6f)
                verticalLineTo(8.4f)
                horizontalLineTo(3.4f)
                close()
            }
            stroke {
                moveTo(10.0f, 12.4f)
                horizontalLineTo(14.0f)
            }
        }
    }

    /** Zip/jar: a box with a zip pull down the middle. */
    val Zip: ImageVector by lazy {
        icon("Zip") {
            stroke {
                moveTo(5.4f, 4.4f)
                horizontalLineTo(18.6f)
                curveTo(19.4f, 4.4f, 20.0f, 5.0f, 20.0f, 5.8f)
                verticalLineTo(18.2f)
                curveTo(20.0f, 19.0f, 19.4f, 19.6f, 18.6f, 19.6f)
                horizontalLineTo(5.4f)
                curveTo(4.6f, 19.6f, 4.0f, 19.0f, 4.0f, 18.2f)
                verticalLineTo(5.8f)
                curveTo(4.0f, 5.0f, 4.6f, 4.4f, 5.4f, 4.4f)
                close()
            }
            stroke {
                moveTo(12.0f, 4.4f)
                verticalLineTo(9.0f)
            }
            stroke {
                moveTo(12.0f, 11.4f)
                verticalLineTo(13.4f)
            }
            stroke {
                moveTo(12.0f, 15.6f)
                verticalLineTo(17.6f)
            }
        }
    }

    /** App package: a rounded square with a smaller square inside. */
    val Apk: ImageVector by lazy {
        icon("Apk") {
            stroke {
                moveTo(6.6f, 3.8f)
                horizontalLineTo(13.4f)
                lineTo(19.0f, 9.4f)
                verticalLineTo(19.4f)
                curveTo(19.0f, 20.2f, 18.4f, 20.8f, 17.6f, 20.8f)
                horizontalLineTo(6.6f)
                curveTo(5.8f, 20.8f, 5.2f, 20.2f, 5.2f, 19.4f)
                verticalLineTo(5.2f)
                curveTo(5.2f, 4.4f, 5.8f, 3.8f, 6.6f, 3.8f)
                close()
            }
            stroke {
                moveTo(13.4f, 3.8f)
                verticalLineTo(9.4f)
                horizontalLineTo(19.0f)
            }
            solid {
                moveTo(9.4f, 13.0f)
                horizontalLineTo(14.8f)
                verticalLineTo(15.2f)
                curveTo(14.8f, 16.9f, 13.5f, 18.2f, 11.8f, 18.2f)
                curveTo(10.1f, 18.2f, 8.8f, 16.9f, 8.8f, 15.2f)
                close()
            }
        }
    }

    /** Text/code file: document with three ruled lines. */
    val TextFile: ImageVector by lazy {
        icon("TextFile") {
            stroke {
                moveTo(13.4f, 3.8f)
                horizontalLineTo(6.6f)
                curveTo(5.8f, 3.8f, 5.2f, 4.4f, 5.2f, 5.2f)
                verticalLineTo(18.8f)
                curveTo(5.2f, 19.6f, 5.8f, 20.2f, 6.6f, 20.2f)
                horizontalLineTo(17.4f)
                curveTo(18.2f, 20.2f, 18.8f, 19.6f, 18.8f, 18.8f)
                verticalLineTo(9.2f)
                close()
                moveTo(13.4f, 3.8f)
                verticalLineTo(9.2f)
                horizontalLineTo(18.8f)
            }
            stroke {
                moveTo(8.4f, 13.0f)
                horizontalLineTo(15.0f)
            }
            stroke {
                moveTo(8.4f, 16.2f)
                horizontalLineTo(12.6f)
            }
        }
    }

    /** Unknown type: document with a question mark rounded into the corner. */
    val Unknown: ImageVector by lazy {
        icon("Unknown") {
            stroke {
                moveTo(13.4f, 3.8f)
                horizontalLineTo(6.6f)
                curveTo(5.8f, 3.8f, 5.2f, 4.4f, 5.2f, 5.2f)
                verticalLineTo(18.8f)
                curveTo(5.2f, 19.6f, 5.8f, 20.2f, 6.6f, 20.2f)
                horizontalLineTo(17.4f)
                curveTo(18.2f, 20.2f, 18.8f, 19.6f, 18.8f, 18.8f)
                verticalLineTo(9.2f)
                close()
                moveTo(13.4f, 3.8f)
                verticalLineTo(9.2f)
                horizontalLineTo(18.8f)
            }
            stroke {
                moveTo(10.0f, 14.0f)
                curveTo(10.0f, 12.9f, 10.9f, 12.1f, 12.0f, 12.1f)
                curveTo(13.1f, 12.1f, 14.0f, 12.9f, 14.0f, 14.0f)
                curveTo(14.0f, 15.1f, 12.0f, 15.3f, 12.0f, 16.6f)
            }
            solid {
                moveTo(12.0f, 18.0f)
                curveTo(12.5f, 18.0f, 12.9f, 18.4f, 12.9f, 18.9f)
                curveTo(12.9f, 19.4f, 12.5f, 19.8f, 12.0f, 19.8f)
                curveTo(11.5f, 19.8f, 11.1f, 19.4f, 11.1f, 18.9f)
                curveTo(11.1f, 18.4f, 11.5f, 18.0f, 12.0f, 18.0f)
                close()
            }
        }
    }

    // ------------------------------------------------------------ chrome/tools

    /** Chevron pointing right. */
    val Chevron: ImageVector by lazy {
        icon("Chevron") {
            stroke {
                moveTo(9.4f, 5.6f)
                lineTo(15.8f, 12.0f)
                lineTo(9.4f, 18.4f)
            }
        }
    }

    /** Back arrow, the way Files draws it in a circular button. */
    val Back: ImageVector by lazy {
        icon("Back") {
            stroke {
                moveTo(14.2f, 5.4f)
                lineTo(7.6f, 12.0f)
                lineTo(14.2f, 18.6f)
            }
        }
    }

    /** Down chevron, for disclosure in a sort control. */
    val CaretDown: ImageVector by lazy {
        icon("CaretDown") {
            stroke {
                moveTo(6.4f, 9.4f)
                lineTo(12.0f, 15.0f)
                lineTo(17.6f, 9.4f)
            }
        }
    }

    /** Up chevron. */
    val CaretUp: ImageVector by lazy {
        icon("CaretUp") {
            stroke {
                moveTo(6.4f, 14.6f)
                lineTo(12.0f, 9.0f)
                lineTo(17.6f, 14.6f)
            }
        }
    }

    /** Grid of squares: switch to icon view. */
    val Grid: ImageVector by lazy {
        icon("Grid") {
            stroke {
                moveTo(4.6f, 4.6f)
                horizontalLineTo(10.2f)
                verticalLineTo(10.2f)
                horizontalLineTo(4.6f)
                close()
            }
            stroke {
                moveTo(13.8f, 4.6f)
                horizontalLineTo(19.4f)
                verticalLineTo(10.2f)
                horizontalLineTo(13.8f)
                close()
            }
            stroke {
                moveTo(4.6f, 13.8f)
                horizontalLineTo(10.2f)
                verticalLineTo(19.4f)
                horizontalLineTo(4.6f)
                close()
            }
            stroke {
                moveTo(13.8f, 13.8f)
                horizontalLineTo(19.4f)
                verticalLineTo(19.4f)
                horizontalLineTo(13.8f)
                close()
            }
        }
    }

    /** Three stacked lines: switch to list view. */
    val List: ImageVector by lazy {
        icon("List") {
            stroke {
                moveTo(4.4f, 6.6f)
                horizontalLineTo(19.6f)
            }
            stroke {
                moveTo(4.4f, 12.0f)
                horizontalLineTo(19.6f)
            }
            stroke {
                moveTo(4.4f, 17.4f)
                horizontalLineTo(19.6f)
            }
        }
    }

    /** Pie chart: storage usage. */
    val Storage: ImageVector by lazy {
        icon("Storage") {
            stroke {
                moveTo(12.0f, 3.6f)
                curveTo(16.6f, 3.6f, 20.4f, 7.4f, 20.4f, 12.0f)
                curveTo(20.4f, 16.6f, 16.6f, 20.4f, 12.0f, 20.4f)
                curveTo(7.4f, 20.4f, 3.6f, 16.6f, 3.6f, 12.0f)
                curveTo(3.6f, 7.4f, 7.4f, 3.6f, 12.0f, 3.6f)
                close()
            }
            stroke {
                moveTo(12.0f, 12.0f)
                lineTo(12.0f, 3.6f)
            }
            stroke {
                moveTo(12.0f, 12.0f)
                lineTo(20.4f, 12.0f)
            }
        }
    }

    /** House: go to the first storage location. */
    val Home: ImageVector by lazy {
        icon("Home") {
            stroke {
                moveTo(3.8f, 10.6f)
                lineTo(12.0f, 4.2f)
                lineTo(20.2f, 10.6f)
                verticalLineTo(19.2f)
                curveTo(20.2f, 19.8f, 19.7f, 20.3f, 19.1f, 20.3f)
                horizontalLineTo(4.9f)
                curveTo(4.3f, 20.3f, 3.8f, 19.8f, 3.8f, 19.2f)
                close()
            }
        }
    }

    /** Folder with a plus: new folder. */
    val FolderPlus: ImageVector by lazy {
        icon("FolderPlus") {
            stroke {
                moveTo(3.2f, 7.6f)
                verticalLineTo(5.8f)
                curveTo(3.2f, 5.2f, 3.7f, 4.7f, 4.3f, 4.7f)
                horizontalLineTo(9.0f)
                curveTo(9.4f, 4.7f, 9.8f, 4.9f, 10.1f, 5.2f)
                lineTo(11.5f, 7.1f)
                horizontalLineTo(19.7f)
                curveTo(20.3f, 7.1f, 20.8f, 7.6f, 20.8f, 8.2f)
                verticalLineTo(18.0f)
                curveTo(20.8f, 18.6f, 20.3f, 19.1f, 19.7f, 19.1f)
                horizontalLineTo(4.3f)
                curveTo(3.7f, 19.1f, 3.2f, 18.6f, 3.2f, 18.0f)
                close()
            }
            stroke {
                moveTo(12.0f, 11.2f)
                verticalLineTo(15.4f)
            }
            stroke {
                moveTo(9.9f, 13.3f)
                horizontalLineTo(14.1f)
            }
        }
    }

    /** Magnifier. */
    val Search: ImageVector by lazy {
        icon("Search") {
            stroke {
                moveTo(10.8f, 4.4f)
                curveTo(14.3f, 4.4f, 17.2f, 7.3f, 17.2f, 10.8f)
                curveTo(17.2f, 14.3f, 14.3f, 17.2f, 10.8f, 17.2f)
                curveTo(7.3f, 17.2f, 4.4f, 14.3f, 4.4f, 10.8f)
                curveTo(4.4f, 7.3f, 7.3f, 4.4f, 10.8f, 4.4f)
                close()
            }
            stroke {
                moveTo(15.4f, 15.4f)
                lineTo(19.6f, 19.6f)
            }
        }
    }

    /** Ellipsis in a circle: the "more" affordance iOS puts at the top right. */
    val More: ImageVector by lazy {
        icon("More") {
            solid {
                moveTo(6.0f, 10.7f)
                curveTo(6.7f, 10.7f, 7.3f, 11.3f, 7.3f, 12.0f)
                curveTo(7.3f, 12.7f, 6.7f, 13.3f, 6.0f, 13.3f)
                curveTo(5.3f, 13.3f, 4.7f, 12.7f, 4.7f, 12.0f)
                curveTo(4.7f, 11.3f, 5.3f, 10.7f, 6.0f, 10.7f)
                close()
            }
            solid {
                moveTo(12.0f, 10.7f)
                curveTo(12.7f, 10.7f, 13.3f, 11.3f, 13.3f, 12.0f)
                curveTo(13.3f, 12.7f, 12.7f, 13.3f, 12.0f, 13.3f)
                curveTo(11.3f, 13.3f, 10.7f, 12.7f, 10.7f, 12.0f)
                curveTo(10.7f, 11.3f, 11.3f, 10.7f, 12.0f, 10.7f)
                close()
            }
            solid {
                moveTo(18.0f, 10.7f)
                curveTo(18.7f, 10.7f, 19.3f, 11.3f, 19.3f, 12.0f)
                curveTo(19.3f, 12.7f, 18.7f, 13.3f, 18.0f, 13.3f)
                curveTo(17.3f, 13.3f, 16.7f, 12.7f, 16.7f, 12.0f)
                curveTo(16.7f, 11.3f, 17.3f, 10.7f, 18.0f, 10.7f)
                close()
            }
        }
    }

    /** Checkmark. */
    val Check: ImageVector by lazy {
        icon("Check") {
            stroke(2.0f) {
                moveTo(5.4f, 12.6f)
                lineTo(9.8f, 17.0f)
                lineTo(18.6f, 7.2f)
            }
        }
    }

    /** Slider/gear: settings. Drawn as a gear with eight teeth. */
    val Gear: ImageVector by lazy {
        icon("Gear") {
            stroke {
                moveTo(12.0f, 8.6f)
                curveTo(13.9f, 8.6f, 15.4f, 10.1f, 15.4f, 12.0f)
                curveTo(15.4f, 13.9f, 13.9f, 15.4f, 12.0f, 15.4f)
                curveTo(10.1f, 15.4f, 8.6f, 13.9f, 8.6f, 12.0f)
                curveTo(8.6f, 10.1f, 10.1f, 8.6f, 12.0f, 8.6f)
                close()
            }
            stroke {
                moveTo(12.0f, 3.4f)
                lineTo(12.0f, 6.0f)
            }
            stroke {
                moveTo(12.0f, 18.0f)
                lineTo(12.0f, 20.6f)
            }
            stroke {
                moveTo(20.6f, 12.0f)
                lineTo(18.0f, 12.0f)
            }
            stroke {
                moveTo(6.0f, 12.0f)
                lineTo(3.4f, 12.0f)
            }
            stroke {
                moveTo(18.1f, 5.9f)
                lineTo(16.3f, 7.7f)
            }
            stroke {
                moveTo(7.7f, 16.3f)
                lineTo(5.9f, 18.1f)
            }
            stroke {
                moveTo(18.1f, 18.1f)
                lineTo(16.3f, 16.3f)
            }
            stroke {
                moveTo(7.7f, 7.7f)
                lineTo(5.9f, 5.9f)
            }
        }
    }

    /** Sparkle: the modules tab. */
    val Sparkle: ImageVector by lazy {
        icon("Sparkle") {
            stroke {
                moveTo(12.0f, 4.2f)
                lineTo(13.8f, 9.4f)
                lineTo(19.0f, 11.2f)
                lineTo(13.8f, 13.0f)
                lineTo(12.0f, 18.2f)
                lineTo(10.2f, 13.0f)
                lineTo(5.0f, 11.2f)
                lineTo(10.2f, 9.4f)
                close()
            }
        }
    }

    /** Plus. */
    val Plus: ImageVector by lazy {
        icon("Plus") {
            stroke(2.0f) {
                moveTo(12.0f, 5.6f)
                verticalLineTo(18.4f)
            }
            stroke(2.0f) {
                moveTo(5.6f, 12.0f)
                horizontalLineTo(18.4f)
            }
        }
    }

    /** Minus, for the density stepper. */
    val Minus: ImageVector by lazy {
        icon("Minus") {
            stroke(2.0f) {
                moveTo(5.6f, 12.0f)
                horizontalLineTo(18.4f)
            }
        }
    }

    /** Eye: the hidden-files toggle, in its "showing" state. */
    val Eye: ImageVector by lazy {
        icon("Eye") {
            stroke {
                moveTo(2.8f, 12.0f)
                curveTo(5.2f, 7.6f, 8.4f, 5.4f, 12.0f, 5.4f)
                curveTo(15.6f, 5.4f, 18.8f, 7.6f, 21.2f, 12.0f)
                curveTo(18.8f, 16.4f, 15.6f, 18.6f, 12.0f, 18.6f)
                curveTo(8.4f, 18.6f, 5.2f, 16.4f, 2.8f, 12.0f)
                close()
            }
            stroke {
                moveTo(12.0f, 9.2f)
                curveTo(13.5f, 9.2f, 14.8f, 10.5f, 14.8f, 12.0f)
                curveTo(14.8f, 13.5f, 13.5f, 14.8f, 12.0f, 14.8f)
                curveTo(10.5f, 14.8f, 9.2f, 13.5f, 9.2f, 12.0f)
                curveTo(9.2f, 10.5f, 10.5f, 9.2f, 12.0f, 9.2f)
                close()
            }
        }
    }

    /** Eye with a slash: hidden files are not being shown. */
    val EyeOff: ImageVector by lazy {
        icon("EyeOff") {
            stroke {
                moveTo(2.8f, 12.0f)
                curveTo(5.2f, 7.6f, 8.4f, 5.4f, 12.0f, 5.4f)
                curveTo(15.6f, 5.4f, 18.8f, 7.6f, 21.2f, 12.0f)
                curveTo(18.8f, 16.4f, 15.6f, 18.6f, 12.0f, 18.6f)
                curveTo(8.4f, 18.6f, 5.2f, 16.4f, 2.8f, 12.0f)
                close()
            }
            stroke {
                moveTo(4.4f, 4.4f)
                lineTo(19.6f, 19.6f)
            }
        }
    }

    /** Phone: search the device rather than the folder. */
    val Device: ImageVector by lazy {
        icon("Device") {
            stroke {
                moveTo(8.4f, 2.8f)
                horizontalLineTo(15.6f)
                curveTo(16.4f, 2.8f, 17.0f, 3.4f, 17.0f, 4.2f)
                verticalLineTo(19.8f)
                curveTo(17.0f, 20.6f, 16.4f, 21.2f, 15.6f, 21.2f)
                horizontalLineTo(8.4f)
                curveTo(7.6f, 21.2f, 7.0f, 20.6f, 7.0f, 19.8f)
                verticalLineTo(4.2f)
                curveTo(7.0f, 3.4f, 7.6f, 2.8f, 8.4f, 2.8f)
                close()
            }
            stroke {
                moveTo(10.6f, 18.4f)
                horizontalLineTo(13.4f)
            }
        }
    }

    /** Arrow going right out of a box: move. */
    val Move: ImageVector by lazy {
        icon("Move") {
            stroke {
                moveTo(4.4f, 8.2f)
                verticalLineTo(6.4f)
                curveTo(4.4f, 5.8f, 4.9f, 5.3f, 5.5f, 5.3f)
                horizontalLineTo(10.0f)
                curveTo(10.4f, 5.3f, 10.8f, 5.5f, 11.1f, 5.8f)
                lineTo(12.4f, 7.5f)
                horizontalLineTo(18.5f)
                curveTo(19.1f, 7.5f, 19.6f, 8.0f, 19.6f, 8.6f)
                verticalLineTo(17.6f)
                curveTo(19.6f, 18.2f, 19.1f, 18.7f, 18.5f, 18.7f)
                horizontalLineTo(5.5f)
                curveTo(4.9f, 18.7f, 4.4f, 18.2f, 4.4f, 17.6f)
                close()
            }
            stroke {
                moveTo(9.6f, 13.1f)
                horizontalLineTo(16.4f)
            }
            stroke {
                moveTo(13.6f, 10.3f)
                lineTo(16.4f, 13.1f)
                lineTo(13.6f, 15.9f)
            }
        }
    }

    /** Two overlapping squares: copy. */
    val Copy: ImageVector by lazy {
        icon("Copy") {
            stroke {
                moveTo(9.0f, 8.4f)
                horizontalLineTo(18.2f)
                curveTo(19.0f, 8.4f, 19.6f, 9.0f, 19.6f, 9.8f)
                verticalLineTo(19.0f)
                curveTo(19.6f, 19.8f, 19.0f, 20.4f, 18.2f, 20.4f)
                horizontalLineTo(9.0f)
                curveTo(8.2f, 20.4f, 7.6f, 19.8f, 7.6f, 19.0f)
                verticalLineTo(9.8f)
                curveTo(7.6f, 9.0f, 8.2f, 8.4f, 9.0f, 8.4f)
                close()
            }
            stroke {
                moveTo(15.4f, 5.4f)
                horizontalLineTo(5.8f)
                curveTo(5.0f, 5.4f, 4.4f, 6.0f, 4.4f, 6.8f)
                verticalLineTo(16.4f)
            }
        }
    }

    /** Trash can: delete. */
    val Trash: ImageVector by lazy {
        icon("Trash") {
            stroke {
                moveTo(4.6f, 6.8f)
                horizontalLineTo(19.4f)
            }
            stroke {
                moveTo(9.4f, 6.8f)
                verticalLineTo(4.6f)
                curveTo(9.4f, 4.2f, 9.7f, 3.9f, 10.1f, 3.9f)
                horizontalLineTo(13.9f)
                curveTo(14.3f, 3.9f, 14.6f, 4.2f, 14.6f, 4.6f)
                verticalLineTo(6.8f)
            }
            stroke {
                moveTo(6.4f, 6.8f)
                lineTo(7.2f, 19.4f)
                curveTo(7.2f, 19.8f, 7.5f, 20.1f, 7.9f, 20.1f)
                horizontalLineTo(16.1f)
                curveTo(16.5f, 20.1f, 16.8f, 19.8f, 16.8f, 19.4f)
                lineTo(17.6f, 6.8f)
            }
            stroke {
                moveTo(10.4f, 10.2f)
                verticalLineTo(16.6f)
            }
            stroke {
                moveTo(13.6f, 10.2f)
                verticalLineTo(16.6f)
            }
        }
    }

    /** Pencil: rename. */
    val Pencil: ImageVector by lazy {
        icon("Pencil") {
            stroke {
                moveTo(4.2f, 19.8f)
                lineTo(8.6f, 18.8f)
                lineTo(19.2f, 8.2f)
                curveTo(19.7f, 7.7f, 19.7f, 6.9f, 19.2f, 6.4f)
                lineTo(17.6f, 4.8f)
                curveTo(17.1f, 4.3f, 16.3f, 4.3f, 15.8f, 4.8f)
                lineTo(5.2f, 15.4f)
                close()
            }
        }
    }

    /** Info circle: properties. */
    val Info: ImageVector by lazy {
        icon("Info") {
            stroke {
                moveTo(12.0f, 3.6f)
                curveTo(16.6f, 3.6f, 20.4f, 7.4f, 20.4f, 12.0f)
                curveTo(20.4f, 16.6f, 16.6f, 20.4f, 12.0f, 20.4f)
                curveTo(7.4f, 20.4f, 3.6f, 16.6f, 3.6f, 12.0f)
                curveTo(3.6f, 7.4f, 7.4f, 3.6f, 12.0f, 3.6f)
                close()
            }
            stroke {
                moveTo(12.0f, 10.8f)
                verticalLineTo(16.4f)
            }
            solid {
                moveTo(12.0f, 7.0f)
                curveTo(12.6f, 7.0f, 13.0f, 7.4f, 13.0f, 8.0f)
                curveTo(13.0f, 8.6f, 12.6f, 9.0f, 12.0f, 9.0f)
                curveTo(11.4f, 9.0f, 11.0f, 8.6f, 11.0f, 8.0f)
                curveTo(11.0f, 7.4f, 11.4f, 7.0f, 12.0f, 7.0f)
                close()
            }
        }
    }

    /** Share: a box with an arrow leaving the top. */
    val Share: ImageVector by lazy {
        icon("Share") {
            stroke {
                moveTo(12.0f, 4.0f)
                verticalLineTo(14.8f)
            }
            stroke {
                moveTo(8.4f, 7.4f)
                lineTo(12.0f, 4.0f)
                lineTo(15.6f, 7.4f)
            }
            stroke {
                moveTo(7.0f, 11.4f)
                horizontalLineTo(5.4f)
                curveTo(4.8f, 11.4f, 4.4f, 11.9f, 4.4f, 12.5f)
                verticalLineTo(18.6f)
                curveTo(4.4f, 19.2f, 4.8f, 19.7f, 5.4f, 19.7f)
                horizontalLineTo(18.6f)
                curveTo(19.2f, 19.7f, 19.6f, 19.2f, 19.6f, 18.6f)
                verticalLineTo(12.5f)
                curveTo(19.6f, 11.9f, 19.2f, 11.4f, 18.6f, 11.4f)
                horizontalLineTo(17.0f)
            }
        }
    }

    /** Terminal: a window with a prompt caret. */
    val Terminal: ImageVector by lazy {
        icon("Terminal") {
            stroke {
                moveTo(4.6f, 4.6f)
                horizontalLineTo(19.4f)
                curveTo(20.0f, 4.6f, 20.4f, 5.0f, 20.4f, 5.6f)
                verticalLineTo(18.4f)
                curveTo(20.4f, 19.0f, 20.0f, 19.4f, 19.4f, 19.4f)
                horizontalLineTo(4.6f)
                curveTo(4.0f, 19.4f, 3.6f, 19.0f, 3.6f, 18.4f)
                verticalLineTo(5.6f)
                curveTo(3.6f, 5.0f, 4.0f, 4.6f, 4.6f, 4.6f)
                close()
            }
            stroke {
                moveTo(7.2f, 10.2f)
                lineTo(9.6f, 12.4f)
                lineTo(7.2f, 14.6f)
            }
            stroke {
                moveTo(12.0f, 14.8f)
                horizontalLineTo(16.4f)
            }
        }
    }

    /** Play: solid triangle, for the media transport. */
    val Play: ImageVector by lazy {
        icon("Play") {
            solid {
                moveTo(8.4f, 5.2f)
                lineTo(19.0f, 12.0f)
                lineTo(8.4f, 18.8f)
                close()
            }
        }
    }

    /** Pause: two bars. */
    val Pause: ImageVector by lazy {
        icon("Pause") {
            solid {
                moveTo(8.0f, 5.4f)
                horizontalLineTo(10.4f)
                verticalLineTo(18.6f)
                horizontalLineTo(8.0f)
                close()
            }
            solid {
                moveTo(13.6f, 5.4f)
                horizontalLineTo(16.0f)
                verticalLineTo(18.6f)
                horizontalLineTo(13.6f)
                close()
            }
        }
    }

    /** Previous track: bar and a triangle pointing left. */
    val Previous: ImageVector by lazy {
        icon("Previous") {
            solid {
                moveTo(7.0f, 5.6f)
                horizontalLineTo(8.8f)
                verticalLineTo(18.4f)
                horizontalLineTo(7.0f)
                close()
            }
            solid {
                moveTo(18.0f, 5.6f)
                lineTo(18.0f, 18.4f)
                lineTo(9.4f, 12.0f)
                close()
            }
        }
    }

    /** Next track: triangle pointing right, then a bar. */
    val Next: ImageVector by lazy {
        icon("Next") {
            solid {
                moveTo(6.0f, 5.6f)
                lineTo(6.0f, 18.4f)
                lineTo(14.6f, 12.0f)
                close()
            }
            solid {
                moveTo(15.2f, 5.6f)
                horizontalLineTo(17.0f)
                verticalLineTo(18.4f)
                horizontalLineTo(15.2f)
                close()
            }
        }
    }

    /** Rewind ten seconds: an arc with an arrowhead at the start. */
    val Rewind: ImageVector by lazy {
        icon("Rewind") {
            stroke {
                moveTo(4.8f, 12.2f)
                curveTo(5.4f, 8.2f, 8.6f, 5.2f, 12.2f, 5.2f)
                curveTo(16.2f, 5.2f, 19.4f, 8.4f, 19.4f, 12.2f)
                curveTo(19.4f, 16.0f, 16.2f, 19.2f, 12.2f, 19.2f)
                curveTo(9.6f, 19.2f, 7.4f, 17.8f, 6.2f, 15.8f)
            }
            stroke {
                moveTo(4.8f, 12.2f)
                verticalLineTo(7.8f)
            }
            stroke {
                moveTo(8.4f, 12.6f)
                lineTo(10.6f, 12.6f)
            }
            stroke {
                moveTo(9.5f, 12.6f)
                verticalLineTo(16.4f)
            }
            stroke {
                moveTo(12.8f, 14.5f)
                curveTo(12.8f, 13.3f, 13.6f, 12.6f, 14.6f, 12.6f)
                curveTo(15.6f, 12.6f, 16.4f, 13.3f, 16.4f, 14.5f)
                curveTo(16.4f, 15.7f, 15.6f, 16.4f, 14.6f, 16.4f)
                curveTo(13.6f, 16.4f, 12.8f, 15.7f, 12.8f, 14.5f)
                close()
            }
        }
    }

    /** Forward ten seconds: the same arc, mirrored. */
    val Forward: ImageVector by lazy {
        icon("Forward") {
            stroke {
                moveTo(19.2f, 12.2f)
                curveTo(18.6f, 8.2f, 15.4f, 5.2f, 11.8f, 5.2f)
                curveTo(7.8f, 5.2f, 4.6f, 8.4f, 4.6f, 12.2f)
                curveTo(4.6f, 16.0f, 7.8f, 19.2f, 11.8f, 19.2f)
                curveTo(14.4f, 19.2f, 16.6f, 17.8f, 17.8f, 15.8f)
            }
            stroke {
                moveTo(19.2f, 12.2f)
                verticalLineTo(7.8f)
            }
            stroke {
                moveTo(7.6f, 12.6f)
                lineTo(9.8f, 12.6f)
            }
            stroke {
                moveTo(8.7f, 12.6f)
                verticalLineTo(16.4f)
            }
            stroke {
                moveTo(12.0f, 14.5f)
                curveTo(12.0f, 13.3f, 12.8f, 12.6f, 13.8f, 12.6f)
                curveTo(14.8f, 12.6f, 15.6f, 13.3f, 15.6f, 14.5f)
                curveTo(15.6f, 15.7f, 14.8f, 16.4f, 13.8f, 16.4f)
                curveTo(12.8f, 16.4f, 12.0f, 15.7f, 12.0f, 14.5f)
                close()
            }
        }
    }

    /** Arrow up, for the previous search match. */
    val ArrowUp: ImageVector by lazy {
        icon("ArrowUp") {
            stroke {
                moveTo(12.0f, 19.0f)
                verticalLineTo(5.4f)
            }
            stroke {
                moveTo(6.4f, 11.0f)
                lineTo(12.0f, 5.4f)
                lineTo(17.6f, 11.0f)
            }
        }
    }

    /** Arrow down, for the next search match. */
    val ArrowDown: ImageVector by lazy {
        icon("ArrowDown") {
            stroke {
                moveTo(12.0f, 5.0f)
                verticalLineTo(18.6f)
            }
            stroke {
                moveTo(6.4f, 13.0f)
                lineTo(12.0f, 18.6f)
                lineTo(17.6f, 13.0f)
            }
        }
    }

    /** Transfer: two arrows pointing opposite ways. */
    val Transfer: ImageVector by lazy {
        icon("Transfer") {
            stroke {
                moveTo(5.4f, 8.6f)
                horizontalLineTo(18.0f)
            }
            stroke {
                moveTo(14.6f, 5.2f)
                lineTo(18.0f, 8.6f)
                lineTo(14.6f, 12.0f)
            }
            stroke {
                moveTo(18.6f, 15.4f)
                horizontalLineTo(6.0f)
            }
            stroke {
                moveTo(9.4f, 12.0f)
                lineTo(6.0f, 15.4f)
                lineTo(9.4f, 18.8f)
            }
        }
    }

    // -------------------------------------------------- marks the UI needs as text
    /**
     * Marks that are legitimately characters, given a fixed 24x24 box.
     *
     * They are separate from the drawn icons above: these are typographic marks,
     * not drawings, and pretending otherwise would produce a plussign with the
     * wrong stroke weight next to a gear drawn at 1.7 units.
     */
    val Times: ImageVector by lazy { textIcon("Times", "\u00D7") }
    val ChevronLeft: ImageVector by lazy { textIcon("ChevronLeft", "\u2039") }
    val ChevronRight: ImageVector by lazy { textIcon("ChevronRight", "\u203A") }
}
