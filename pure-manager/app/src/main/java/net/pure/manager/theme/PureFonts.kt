package net.pure.manager.theme

import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import net.pure.manager.R

/**
 * Inter, the family this UI was designed against.
 *
 * Every round so far rendered in Roboto, the platform's default sans, because the
 * theme asked for `FontFamily.SansSerif`. Roboto is a fine screen face but it is not
 * the one the layout was drawn for: its x-height is larger, its terminals are open
 * and its numerals are wider, so iOS-sized rows came out looking dense and the
 * large titles lost the weight contrast that makes the reference read as calm.
 *
 * Inter is shipped in `res/font` as four static weights, Latin subset, 66 KB each.
 * SIL Open Font License, and the licence text travels with the files. The four
 * weights are the ones the typography actually asks for: 400 body, 500 medium
 * labels, 600 semibold titles, 700 bold headings.
 */
val InterFamily: FontFamily = FontFamily(
    Font(R.font.inter_400, FontWeight.Normal),
    Font(R.font.inter_500, FontWeight.Medium),
    Font(R.font.inter_600, FontWeight.SemiBold),
    Font(R.font.inter_700, FontWeight.Bold),
)
