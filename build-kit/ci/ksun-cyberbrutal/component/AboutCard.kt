package com.rifsxd.ksunext.ui.component

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.res.colorResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.fromHtml
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.rifsxd.ksunext.BuildConfig
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.theme.DepartureBoardText
import com.rifsxd.ksunext.ui.theme.FadeInText
import com.rifsxd.ksunext.ui.theme.brutalPlate

@Preview
@Composable
fun AboutCard() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .brutalPlate(active = true),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(22.dp)
        ) {
            AboutCardContent()
        }
    }
}

@Composable
fun AboutDialog(dismiss: () -> Unit) {
    Dialog(onDismissRequest = { dismiss() }) {
        AboutCard()
    }
}

@Composable
private fun AboutCardContent() {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(
                modifier = Modifier
                    .size(46.dp)
                    .border(1.dp, MaterialTheme.colorScheme.primary, MaterialTheme.shapes.small),
                color = colorResource(id = R.color.ic_launcher_background),
                shape = MaterialTheme.shapes.small
            ) {
                Image(
                    painter = painterResource(id = R.mipmap.ic_launcher_foreground),
                    contentDescription = null,
                    modifier = Modifier.scale(1.35f)
                )
            }

            Spacer(modifier = Modifier.width(14.dp))

            Column {
                DepartureBoardText(
                    text = stringResource(id = R.string.app_name).uppercase(),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Black
                )
                FadeInText(
                    text = "CYBERBRUTAL // ${BuildConfig.VERSION_NAME}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    delayMillis = 120
                )
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        FadeInText(
            text = "Synthetica Manager for Xiaomi joyeuse (SM7125) by graziemille. Paired exclusively with Synthetica 2.0+ kernel.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            delayMillis = 180
        )

        Spacer(modifier = Modifier.height(8.dp))

        val annotatedString = AnnotatedString.fromHtml(
            htmlString = stringResource(
                id = R.string.about_source_code,
                "<b><a href=\"https://github.com/KernelSU-Next/KernelSU-Next\">KernelSU-Next (GPL-3.0)</a></b>"
            ),
            linkStyles = TextLinkStyles(
                style = SpanStyle(
                    color = MaterialTheme.colorScheme.primary,
                    textDecoration = TextDecoration.Underline
                ),
                pressedStyle = SpanStyle(
                    color = MaterialTheme.colorScheme.primary,
                    background = MaterialTheme.colorScheme.secondaryContainer,
                    textDecoration = TextDecoration.Underline
                )
            )
        )
        Text(
            text = annotatedString,
            style = TextStyle(fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        )
    }
}
