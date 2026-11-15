package com.rifsxd.ksunext.ui.screen

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
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
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.Sort
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.IconButton
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
import androidx.core.content.edit
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
import kotlinx.coroutines.coroutineScope
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
 *   point at, so the default entry is the one the old list shipped with; the user can
 *   add or replace it from the manage-repositories dialog, and that choice persists.
 * - A module without a banner gets a drawn placeholder, not a stock photo. Faking
 *   artwork for someone else's module would misrepresent it.
 */
data class ModuleRepo(
    val name: String,
    val description: String,
    val author: String,
    val repoUrl: String,
    val bannerLink: String = "",
    val license: String = "",
    val visibility: Int = 1,
    val latestVersion: String = "",
    val downloadUrl: String = "",
    val stars: Int = -1,
    val isLoading: Boolean = true
)

sealed class ModuleRepoState {
    object Loading : ModuleRepoState()
    data class Success(val modules: List<ModuleRepo>) : ModuleRepoState()
    data class Error(val message: String) : ModuleRepoState()
}

// SharedPreferences helper functions
private const val PREFS_NAME = "module_repo_prefs"
private const val KEY_JSON_URLS = "json_urls"
private const val KEY_NON_FREE_ENABLED = "non_free_enabled"
private const val DEFAULT_JSON_URL = "https://raw.githubusercontent.com/KernelSU-Next/KernelSU-Next-Modules-Repo/refs/heads/main/modules.json"
private const val NON_FREE_JSON_URL = "https://raw.githubusercontent.com/KernelSU-Next/KernelSU-Next-Modules-Repo/refs/heads/main/non_free_modules.json"
private const val URL_SEPARATOR = "|||"

private fun getModuleRepoPrefs(context: Context): SharedPreferences {
    return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
}

private fun saveJsonUrls(context: Context, urls: List<String>) {
    val joined = urls.joinToString(URL_SEPARATOR)
    getModuleRepoPrefs(context).edit().putString(KEY_JSON_URLS, joined).apply()
}

private fun loadJsonUrls(context: Context): List<String> {
    val raw = getModuleRepoPrefs(context).getString(KEY_JSON_URLS, null)
    return if (raw.isNullOrBlank()) {
        listOf(DEFAULT_JSON_URL)
    } else {
        raw.split(URL_SEPARATOR).filter { it.isNotBlank() }
    }
}

private fun saveNonFreeEnabled(context: Context, enabled: Boolean) {
    getModuleRepoPrefs(context).edit().putBoolean(KEY_NON_FREE_ENABLED, enabled).apply()
}

private fun loadNonFreeEnabled(context: Context): Boolean {
    return getModuleRepoPrefs(context).getBoolean(KEY_NON_FREE_ENABLED, false)
}


// The one entry every install starts with. A Synthetica-hosted JSON, when it exists,
// is either this default or an entry the user adds from the dialog.

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

private suspend fun fetchLatestReleaseInfo(repoUrl: String): ReleaseInfoModuleRepo? {
    return withContext(Dispatchers.IO) {
        try {
            val stars = try {
                val htmlConn = URL(repoUrl).openConnection() as java.net.HttpURLConnection
                htmlConn.setRequestProperty("User-Agent", "KernelSU-Next/${BuildConfig.VERSION_CODE}")
                htmlConn.setRequestProperty("Accept", "text/html")
                val html = BufferedReader(InputStreamReader(htmlConn.inputStream)).use { it.readText() }
                htmlConn.disconnect()
                val titleMatch = """id="repo-stars-counter-star"[^>]*title="([^"]+)"""".toRegex()
                    .find(html)?.groupValues?.get(1)
                titleMatch?.replace(",", "")?.trim()?.toIntOrNull() ?: -1
            } catch (e: Exception) {
                e.printStackTrace()
                -1
            }

            val latestUrl = "$repoUrl/releases/latest"
            val connection = URL(latestUrl).openConnection() as java.net.HttpURLConnection
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("User-Agent", "KernelSU-Next/${BuildConfig.VERSION_CODE}")

            val redirectUrl = connection.getHeaderField("Location")
            connection.disconnect()

            if (redirectUrl == null) return@withContext ReleaseInfoModuleRepo(
                version = "null",
                zipUrl = "",
                stars = stars
            )

            val tagMatch = """/tag/([^/?\s]+)""".toRegex()
                .find(redirectUrl)?.groupValues?.get(1)
                ?: return@withContext ReleaseInfoModuleRepo(version = "null", zipUrl = "", stars = stars)

            val releasePageUrl = "$repoUrl/releases/expanded_assets/$tagMatch"
            val pageConnection = URL(releasePageUrl).openConnection()
            pageConnection.setRequestProperty("User-Agent", "KernelSU-Next/${BuildConfig.VERSION_CODE}")

            val pageHtml = BufferedReader(InputStreamReader(pageConnection.getInputStream())).use {
                it.readText()
            }

            val zipUrlMatch = """href="(/[^"]+/releases/download/[^"]+\.zip)"""".toRegex()
                .find(pageHtml)?.groupValues?.get(1)

            ReleaseInfoModuleRepo(
                version = tagMatch,
                zipUrl = if (zipUrlMatch != null) "https://github.com$zipUrlMatch" else "",
                stars = stars
            )
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }
}

data class ReleaseInfoModuleRepo(
    val version: String,
    val zipUrl: String,
    val stars: Int = -1
)


@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
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

    val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    var jsonUrls by remember { mutableStateOf(loadJsonUrls(context)) }
    var nonFreeEnabled by remember { mutableStateOf(loadNonFreeEnabled(context)) }
    var entries by remember { mutableStateOf<List<ModuleRepo>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var downloading by remember { mutableStateOf<String?>(null) }
    var query by remember { mutableStateOf("") }
    // Newest release per repo is fetched separately; this keeps the banner text on
    // screen while the network answers.
    var sortMode by remember { mutableStateOf(prefs.getString("module_sort_mode", "az") ?: "az") }
    var showRepos by remember { mutableStateOf(false) }
    var editingIndex by remember { mutableStateOf<Int?>(null) }
    var pendingUrl by remember { mutableStateOf("") }
    var showUrlDialog by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    suspend fun load() {
        entries = null
        val effective = if (nonFreeEnabled) jsonUrls + NON_FREE_JSON_URL else jsonUrls
        val base = runCatching { fetchCatalogue(effective) }.getOrDefault(emptyList())
        failed = base.isEmpty()
        entries = base
        // Version, zip URL and stars arrive one repository at a time.
        coroutineScope {
        base.forEach { module ->
            launch {
                val info = runCatching { fetchLatestReleaseInfo(module.repoUrl) }.getOrNull()
                entries = entries?.map { current ->
                    if (current.name == module.name && current.repoUrl == module.repoUrl) {
                        current.copy(
                            latestVersion = info?.version ?: "",
                            downloadUrl = info?.zipUrl ?: "",
                            stars = info?.stars ?: -1,
                        )
                    } else current
                }
            }
        }
        }
    }

    LaunchedEffect(jsonUrls, nonFreeEnabled) { load() }

    DownloadListener(context) { uri ->
        downloading = null
        navigator.navigate(FlashScreenDestination(FlashIt.FlashModules(listOf(uri))))
    }

    val visible = remember(entries, query, sortMode) {
        val list = entries.orEmpty().filter { module ->
            query.isBlank() ||
                module.name.contains(query, ignoreCase = true) ||
                module.description.contains(query, ignoreCase = true) ||
                module.author.contains(query, ignoreCase = true)
        }
        when (sortMode) {
            "za" -> list.sortedByDescending { it.name.lowercase() }
            "stars" -> list.sortedWith(compareByDescending { it.stars })
            else -> list.sortedBy { it.name.lowercase() }
        }
    }

    if (showRepos) {
        AlertDialog(
            onDismissRequest = { showRepos = false },
            title = { Text(stringResource(R.string.manage_repositories)) },
            text = {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(stringResource(R.string.non_free_repo), style = MaterialTheme.typography.bodyMedium)
                            Text(
                                stringResource(R.string.non_free_repo_summary),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        androidx.compose.material3.Switch(
                            checked = nonFreeEnabled,
                            onCheckedChange = { enabled ->
                                nonFreeEnabled = enabled
                                saveNonFreeEnabled(context, enabled)
                            },
                        )
                    }
                    androidx.compose.material3.HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                    if (jsonUrls.isEmpty()) {
                        Text(
                            stringResource(R.string.no_repositories_configured),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    jsonUrls.forEachIndexed { index, url ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                url,
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.weight(1f),
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                            IconButton(onClick = {
                                editingIndex = index
                                pendingUrl = url
                                showUrlDialog = true
                            }) {
                                Icon(Icons.Rounded.Edit, contentDescription = null, modifier = Modifier.size(18.dp))
                            }
                            IconButton(
                                onClick = {
                                    val updated = jsonUrls.toMutableList().also { it.removeAt(index) }
                                    jsonUrls = updated
                                    saveJsonUrls(context, updated)
                                },
                                // The last repository is the only thing the screen
                                // can read; removing it leaves a blank page.
                                enabled = jsonUrls.size > 1,
                            ) {
                                Icon(Icons.Rounded.Delete, contentDescription = null, modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                    androidx.compose.material3.OutlinedButton(
                        onClick = {
                            editingIndex = null
                            pendingUrl = ""
                            showUrlDialog = true
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(stringResource(R.string.add_repository)) }
                    androidx.compose.material3.TextButton(
                        onClick = {
                            jsonUrls = listOf(DEFAULT_JSON_URL)
                            saveJsonUrls(context, listOf(DEFAULT_JSON_URL))
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(stringResource(R.string.reset_to_default)) }
                }
            },
            confirmButton = {
                androidx.compose.material3.TextButton(onClick = { showRepos = false }) {
                    Text(stringResource(R.string.close))
                }
            },
        )
    }

    if (showUrlDialog) {
        AlertDialog(
            onDismissRequest = { showUrlDialog = false },
            title = { Text(stringResource(if (editingIndex == null) R.string.add_repository else R.string.module_repo_screen)) },
            text = {
                androidx.compose.material3.OutlinedTextField(
                    value = pendingUrl,
                    onValueChange = { pendingUrl = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("https://…") },
                    maxLines = 3,
                )
            },
            confirmButton = {
                androidx.compose.material3.TextButton(
                    onClick = {
                        val trimmed = pendingUrl.trim()
                        if (trimmed.isNotBlank()) {
                            val updated = jsonUrls.toMutableList()
                            val idx = editingIndex
                            if (idx == null) updated.add(trimmed) else updated[idx] = trimmed
                            jsonUrls = updated
                            saveJsonUrls(context, updated)
                            showUrlDialog = false
                            pendingUrl = ""
                        }
                    },
                ) { Text(stringResource(R.string.install)) }
            },
            dismissButton = {
                androidx.compose.material3.TextButton(onClick = { showUrlDialog = false }) {
                    Text(stringResource(R.string.close))
                }
            },
        )
    }

    Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            Column {
                GlassTopBar(
                    title = stringResource(R.string.download_title),
                    subtitle = stringResource(R.string.download_sub),
                    actions = {
                        IconButton(onClick = { showRepos = true }) {
                            Icon(Icons.Rounded.Edit, contentDescription = stringResource(R.string.manage_repositories))
                        }
                        IconButton(onClick = {
                            sortMode = when (sortMode) { "az" -> "za"; "za" -> "stars"; else -> "az" }
                            // Without this the order resets on every visit, which
                            // reads as the button not working.
                            prefs.edit().putString("module_sort_mode", sortMode).apply()
                        }) {
                            Icon(Icons.Rounded.Sort, contentDescription = null)
                        }
                        IconButton(onClick = { scope.launch { load() } }) {
                            Icon(Icons.Rounded.Refresh, contentDescription = null)
                        }
                    },
                )
                androidx.compose.material3.OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    placeholder = { Text(stringResource(R.string.module_repo_screen)) },
                    singleLine = true,
                    leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
                )
            }
        },
    ) { innerPadding ->
        when {
            entries == null -> Box(
                modifier = Modifier.fillMaxSize().padding(innerPadding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }

            visible.isEmpty() -> Box(
                modifier = Modifier.fillMaxSize().padding(innerPadding),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(24.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(
                        text = stringResource(if (failed) R.string.download_offline else R.string.download_empty),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
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
                items(visible, key = { "${it.name}||${it.repoUrl}" }) { module ->
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
