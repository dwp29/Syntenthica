package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CloudDownload
import androidx.compose.material.icons.rounded.Extension
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.ramcosta.composedestinations.annotation.Destination
import com.ramcosta.composedestinations.annotation.RootGraph
import com.ramcosta.composedestinations.generated.destinations.FlashScreenDestination
import com.ramcosta.composedestinations.generated.destinations.PixelSources40ScreenDestination
import com.ramcosta.composedestinations.navigation.DestinationsNavigator
import com.rifsxd.ksunext.BuildConfig
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.LocalNavBarEnabled
import com.rifsxd.ksunext.ui.LocalScrollState
import com.rifsxd.ksunext.ui.rememberScrollConnection
import com.rifsxd.ksunext.ui.theme.GlassTopBar
import com.rifsxd.ksunext.ui.theme.IosCyanDark
import com.rifsxd.ksunext.ui.theme.IosGreenDark
import com.rifsxd.ksunext.ui.theme.IosOrangeDark
import com.rifsxd.ksunext.ui.theme.iosGlass
import com.rifsxd.ksunext.ui.util.DownloadListener
import com.rifsxd.ksunext.ui.util.download
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Download: the module catalogue with a picture on every entry.
 *
 * The module list that shipped before this was a text card: name, author, one
 * paragraph, a version number. The owner asked for a browseable catalogue, so each
 * entry now leads with its banner at 16:9, then name, author, version, stars and
 * licence, and a single Install button that does exactly what the old one did:
 * download the zip and hand it to the flash screen.
 *
 * Two things are deliberately not invented:
 *
 * - There is no "Synthetica" repository. No catalogue of our own modules exists to
 *   point at, so the screen reads the same repository the old list read. When a
 *   Synthetica JSON exists, [SYNTHETICA_REPO_URL] is the one line to change.
 * - A module without a banner gets a drawn placeholder, not a stock photo. Faking
 *   artwork for someone else's module would misrepresent it.
 */
// The catalogue the old module list already read. When a Synthetica-hosted JSON
// exists, this constant is the only line that changes.
private const val SYNTHETICA_REPO_URL =
    "https://raw.githubusercontent.com/KernelSU-Next/KernelSU-Next-Modules-Repo/refs/heads/main/modules.json"

/** Same parsing as the old list; one implementation, two screens, no drift. */
private suspend fun fetchCatalogue(jsonUrls: List<String>): List<ModuleRepo> = withContext(Dispatchers.IO) {
    val seen = mutableSetOf<String>()
    jsonUrls.map { url ->
        async {
            runCatching {
                val conn = URL(url).openConnection() as HttpURLConnection
                conn.setRequestProperty("User-Agent", "KernelSU-Next/${BuildConfig.VERSION_CODE}")
                val text = BufferedReader(InputStreamReader(conn.inputStream)).use { it.readText() }
                conn.disconnect()
                val arr = JSONArray(text)
                (0 until arr.length()).mapNotNull { i ->
                    val obj = arr.optJSONObject(i) ?: return@mapNotNull null
                    ModuleRepo(
                        name = obj.optString("name"),
                        description = obj.optString("description"),
                        author = obj.optString("author"),
                        repoUrl = obj.optString("repoUrl"),
                        bannerLink = obj.optString("bannerUrl", ""),
                        license = obj.optString("license", ""),
                        visibility = obj.optInt("visibility", 1),
                    )
                }
            }.getOrDefault(emptyList())
        }
    }.awaitAll().flatten()
        .filter { it.visibility == 1 && it.name.isNotBlank() }
        .filter { seen.add("${it.name}||${it.repoUrl}") }
}

@Destination<RootGraph>
@Composable
fun DownloadScreen(navigator: DestinationsNavigator) {
    val context = LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    val scrollState = LocalScrollState.current
    val navBarEnabled = LocalNavBarEnabled.current
    val isNavBarHidden = (scrollState?.isScrollingDown?.value ?: false) || (navBarEnabled?.value == false)
    val navBarPadding =
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + if (isNavBarHidden) 0.dp else 112.dp

    val bottomBarScrollConnection = if (scrollState != null) {
        rememberScrollConnection(
            isScrollingDown = scrollState.isScrollingDown,
            scrollOffset = scrollState.scrollOffset,
            previousScrollOffset = scrollState.previousScrollOffset,
            threshold = 30f,
        )
    } else null

    var entries by remember { mutableStateOf<List<ModuleRepo>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var downloading by remember { mutableStateOf<String?>(null) }
    val listState = rememberLazyListState()

    LaunchedEffect(Unit) {
        val catalogue = runCatching { fetchCatalogue(listOf(SYNTHETICA_REPO_URL)) }.getOrDefault(emptyList())
        failed = catalogue.isEmpty()
        entries = catalogue
    }

    DownloadListener(context) { uri ->
        downloading = null
        navigator.navigate(FlashScreenDestination(FlashIt.FlashModules(listOf(uri))))
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            GlassTopBar(
                title = stringResource(R.string.download_title),
                subtitle = stringResource(R.string.download_sub),
            )
        },
    ) { innerPadding ->
        val list = entries
        when {
            list == null -> Box(
                modifier = Modifier.fillMaxSize().padding(innerPadding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }

            list.isEmpty() -> Box(
                modifier = Modifier.fillMaxSize().padding(innerPadding),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(24.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(
                        text = stringResource(R.string.download_empty),
                        style = MaterialTheme.typography.titleMedium,
                    )
                    if (failed) {
                        Text(
                            text = stringResource(R.string.download_offline),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Button(onClick = { navigator.navigate(PixelSources40ScreenDestination) }) {
                        Text(stringResource(R.string.pixel40_sources_action))
                    }
                }
            }

            else -> LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .let { mod ->
                        if (bottomBarScrollConnection != null) mod.nestedScroll(bottomBarScrollConnection) else mod
                    },
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 16.dp + navBarPadding),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(list, key = { "${it.name}||${it.repoUrl}" }) { module ->
                    CatalogueCard(
                        module = module,
                        isDownloading = downloading == module.name,
                        onOpen = {
                            runCatching {
                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(module.repoUrl)))
                            }
                        },
                        onDownload = {
                            downloading = module.name
                            scope.launch {
                                runCatching {
                                    val fileName = "${module.name.replace(" ", "_")}.zip"
                                    download(context, module.downloadUrl, fileName, "Downloading ${module.name}")
                                }.onFailure { downloading = null }
                            }
                        },
                    )
                }
            }
        }
    }
}

/**
 * One catalogue entry. The banner is 16:9 and cropped; when the repository gives no
 * banner, a drawn gradient with the module's initial stands in, so every card has
 * the same silhouette instead of a ragged list.
 */
@Composable
private fun CatalogueCard(
    module: ModuleRepo,
    isDownloading: Boolean,
    onOpen: () -> Unit,
    onDownload: () -> Unit,
) {
    val shape = RoundedCornerShape(18.dp)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .iosGlass(shape = shape)
            .clickable(onClick = onOpen),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(150.dp)
                .clip(RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp)),
            contentAlignment = Alignment.Center,
        ) {
            if (module.bannerLink.startsWith("http", ignoreCase = true)) {
                AsyncImage(
                    model = module.bannerLink,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(
                            Brush.linearGradient(
                                listOf(
                                    MaterialTheme.colorScheme.primary.copy(alpha = 0.28f),
                                    MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
                                )
                            )
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Extension,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(40.dp),
                    )
                }
            }
        }

        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = module.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = stringResource(R.string.download_by, module.author.ifBlank { "—" }),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = module.description,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (module.stars >= 0) {
                    Icon(
                        imageVector = Icons.Rounded.Star,
                        contentDescription = null,
                        tint = IosOrangeDark,
                        modifier = Modifier.size(14.dp),
                    )
                    Text(
                        text = if (module.stars >= 1_000) "%.1fk".format(module.stars / 1000.0) else "${module.stars}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (module.license.isNotBlank()) {
                    Text(
                        text = module.license,
                        style = MaterialTheme.typography.labelSmall,
                        color = IosCyanDark,
                    )
                }
                Spacer(Modifier.width(2.dp))
                Text(
                    text = stringResource(R.string.download_zip),
                    style = MaterialTheme.typography.labelSmall,
                    color = IosGreenDark,
                )
                Spacer(Modifier.weight(1f))
                Button(
                    onClick = onDownload,
                    enabled = !isDownloading,
                ) {
                    if (isDownloading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.width(8.dp))
                    } else {
                        Icon(
                            imageVector = Icons.Rounded.CloudDownload,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(stringResource(R.string.install))
                }
            }
        }
    }
}
