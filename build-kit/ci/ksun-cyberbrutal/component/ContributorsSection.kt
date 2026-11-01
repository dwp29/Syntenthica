package com.rifsxd.ksunext.ui.component

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.rifsxd.ksunext.R

// Preserve the upstream KernelSU-Next credits, profiles, roles and donation destinations.
private data class Contributor(
    val login: String,
    val name: String? = null,
    val githubUrl: String,
    val role: String,
    val donationUrl: String,
)

private val contributors = listOf(
    Contributor(
        login = "rifsxd",
        name = "Rifat Azad",
        githubUrl = "https://github.com/rifsxd",
        role = "Lead Developer",
        donationUrl = "https://github.com/KernelSU-Next/KernelSU-Next/tree/dev?tab=readme-ov-file#-donations",
    ),
    Contributor(
        login = "tiann",
        name = "Weishu",
        githubUrl = "https://github.com/tiann",
        role = "KernelSU Author",
        donationUrl = "https://www.patreon.com/weishu",
    ),
    Contributor(
        login = "fatalcoder524",
        githubUrl = "https://github.com/fatalcoder524",
        role = "Frontend Maintainer",
        donationUrl = "https://github.com/sponsors/fatalcoder524",
    ),
    Contributor(
        login = "pershoot",
        githubUrl = "https://github.com/pershoot",
        role = "Backend Maintainer",
        donationUrl = "https://github.com/sponsors/pershoot",
    ),
    Contributor(
        login = "maxsteeel",
        name = "Max",
        githubUrl = "https://github.com/maxsteeel",
        role = "Legacy Maintainer",
        donationUrl = "https://github.com/sponsors/maxsteeel",
    ),
)

@Composable
fun ContributorsSection() {
    val uriHandler = LocalUriHandler.current
    val supportLabel = stringResource(R.string.support)

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = stringResource(R.string.contributors).uppercase(),
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "// ${contributors.size.toString().padStart(2, '0')}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            text = "KERNELSU-NEXT // CREDITS",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(bottom = 4.dp),
        )
        contributors.forEach { contributor ->
            ContributorRow(
                contributor = contributor,
                supportLabel = supportLabel,
                onProfileClick = { uriHandler.openUri(contributor.githubUrl) },
                onDonateClick = { uriHandler.openUri(contributor.donationUrl) },
            )
        }
    }
}

@Composable
private fun ContributorRow(
    contributor: Contributor,
    supportLabel: String,
    onProfileClick: () -> Unit,
    onDonateClick: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier
                .weight(1f)
                .clip(MaterialTheme.shapes.extraSmall)
                .clickable(role = Role.Button, onClick = onProfileClick)
                .heightIn(min = 48.dp)
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // An initial remains visible if GitHub avatars cannot be loaded offline.
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(MaterialTheme.shapes.extraSmall)
                    .background(MaterialTheme.colorScheme.surfaceContainerHighest)
                    .border(1.dp, MaterialTheme.colorScheme.outline, MaterialTheme.shapes.extraSmall),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = contributor.login.take(1).uppercase(),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
                AsyncImage(
                    model = "https://avatars.githubusercontent.com/${contributor.login}?s=80",
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = contributor.name?.let { "${contributor.login} ($it)" } ?: contributor.login,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = contributor.role,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        OutlinedButton(
            onClick = onDonateClick,
            modifier = Modifier
                .heightIn(min = 48.dp)
                .semantics { contentDescription = "$supportLabel ${contributor.login}" },
            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
            shape = MaterialTheme.shapes.extraSmall,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Icon(
                imageVector = Icons.Filled.Favorite,
                contentDescription = null,
                modifier = Modifier.size(13.dp),
                tint = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.width(4.dp))
            Text(
                text = supportLabel.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
            )
        }
    }
}
