package com.rifsxd.ksunext.ui.component

import android.widget.Toast
import androidx.annotation.DrawableRes
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rifsxd.ksunext.ui.theme.IosPill

/**
 * Same geometry as [com.rifsxd.ksunext.ui.theme.IosRow], but the leading glyph
 * is a drawable instead of a Material icon, so brand marks (Telegram, GitHub)
 * keep their real shape.
 */
@Composable
fun BrandIconRow(
    @DrawableRes drawableRes: Int,
    badgeColor: Color,
    title: String,
    subtitle: String? = null,
    value: String? = null,
    pill: String? = null,
    pillColor: Color = androidx.compose.ui.graphics.Color.Unspecified,
    showChevron: Boolean = false,
    enabled: Boolean = true,
    onClick: (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 56.dp)
            .let { mod -> if (onClick != null && enabled) mod.clickable(onClick = onClick) else mod }
            .padding(horizontal = 15.dp, vertical = 12.5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(34.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(badgeColor.copy(alpha = 0.20f))
                .border(0.9.dp, badgeColor.copy(alpha = 0.45f), RoundedCornerShape(10.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painter = painterResource(drawableRes),
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(19.dp),
            )
        }
        Spacer(Modifier.width(13.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (!subtitle.isNullOrBlank()) {
                Spacer(Modifier.height(1.5.dp))
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (pill != null) {
            IosPill(
                text = pill,
                color = if (pillColor == Color.Unspecified) badgeColor else pillColor,
            )
            if (value != null || showChevron) Spacer(Modifier.width(6.dp))
        }
        if (value != null) {
            Spacer(Modifier.width(8.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (showChevron) {
            Spacer(Modifier.width(4.dp))
            Icon(
                imageVector = Icons.AutoMirrored.Rounded.KeyboardArrowRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.55f),
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

/**
 * An external-link opener that reports failures instead of crashing.
 *
 * `UriHandler.openUri` throws when no activity can handle the scheme (a device
 * with no browser, Telegram not installed on a `tg://` link) and on malformed
 * URIs. An About page must degrade to a toast, never to a crash.
 */
@Composable
fun rememberSafeLinkOpener(): (String, Int) -> Unit {
    val uriHandler = LocalUriHandler.current
    val context = LocalContext.current
    // remember so the lambda keeps its identity across recompositions; it is
    // captured by many click lambdas on the About page.
    return remember(uriHandler, context) {
        { url: String, failureMessageRes: Int ->
            try {
                uriHandler.openUri(url)
            } catch (_: Exception) {
                Toast.makeText(context, failureMessageRes, Toast.LENGTH_SHORT).show()
            }
        }
    }
}
