package com.rifsxd.ksunext.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.State
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.layer.drawLayer
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.Velocity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.lifecycleScope
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.ramcosta.composedestinations.DestinationsNavHost
import com.ramcosta.composedestinations.animations.NavHostAnimatedDestinationStyle
import com.ramcosta.composedestinations.generated.NavGraphs
import com.ramcosta.composedestinations.generated.destinations.ExecuteModuleActionScreenDestination
import com.ramcosta.composedestinations.generated.destinations.FlashScreenDestination
import com.ramcosta.composedestinations.generated.destinations.ModuleScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SettingScreenDestination
import com.ramcosta.composedestinations.generated.destinations.SuperUserScreenDestination
import com.ramcosta.composedestinations.utils.isRouteOnBackStackAsState
import com.ramcosta.composedestinations.utils.rememberDestinationsNavigator
import com.rifsxd.ksunext.Natives
import com.rifsxd.ksunext.R
import com.rifsxd.ksunext.ui.screen.BottomBarDestination
import com.rifsxd.ksunext.ui.screen.FlashIt
import com.rifsxd.ksunext.ui.theme.GlassBackground
import com.rifsxd.ksunext.ui.theme.GlassSplash
import com.rifsxd.ksunext.ui.theme.KernelSUTheme
import com.rifsxd.ksunext.ui.theme.LocalGlassContentLayer
import com.rifsxd.ksunext.ui.theme.LocalGlassStyle
import com.rifsxd.ksunext.ui.theme.LocalGlassWallpaperLayer
import com.rifsxd.ksunext.ui.theme.iosGlass
import com.rifsxd.ksunext.ui.util.AppLockManager
import com.rifsxd.ksunext.ui.util.BiometricAuthenticator
import com.rifsxd.ksunext.ui.util.LocalSnackbarHost
import com.rifsxd.ksunext.ui.util.LocaleHelper
import com.rifsxd.ksunext.ui.util.ZipUtils
import com.rifsxd.ksunext.ui.util.install
import com.rifsxd.ksunext.ui.viewmodel.ModuleViewModel
import com.rifsxd.ksunext.ui.viewmodel.SuperUserViewModel
import kotlin.math.abs
import kotlin.math.roundToInt
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

data class ScrollState(
    val isScrollingDown: MutableState<Boolean>,
    val scrollOffset: MutableState<Float>,
    val previousScrollOffset: MutableState<Float>,
)

val LocalScrollState = compositionLocalOf<ScrollState?> { null }
val LocalNavBarEnabled = compositionLocalOf<State<Boolean>?> { null }

@Composable
fun rememberScrollConnection(
    isScrollingDown: MutableState<Boolean>,
    scrollOffset: MutableState<Float>,
    previousScrollOffset: MutableState<Float>,
    threshold: Float = 50f,
): NestedScrollConnection {
    return remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                val delta = available.y
                val newOffset = scrollOffset.value + delta
                scrollOffset.value = newOffset
                val scrollDelta = previousScrollOffset.value - newOffset
                if (abs(scrollDelta) > threshold) {
                    isScrollingDown.value = scrollDelta > 0
                    previousScrollOffset.value = newOffset
                }
                return Offset.Zero
            }

            override suspend fun onPostFling(consumed: Velocity, available: Velocity): Velocity {
                previousScrollOffset.value = scrollOffset.value
                return super.onPostFling(consumed, available)
            }
        }
    }
}

fun Modifier.horizontalSwipeNavigator(
    currentRoute: String?,
    destinations: List<BottomBarDestination>,
    onNavigate: (Int) -> Unit,
): Modifier = pointerInput(currentRoute, destinations) {
    var totalDrag = 0f
    detectHorizontalDragGestures(
        onDragStart = { totalDrag = 0f },
        onHorizontalDrag = { change, dragAmount ->
            change.consume()
            totalDrag += dragAmount
        },
        onDragEnd = {
            if (abs(totalDrag) > 150f) {
                val currentIndex = destinations.indexOfFirst { it.direction.route == currentRoute }
                if (currentIndex == -1) return@detectHorizontalDragGestures
                if (totalDrag < 0) {
                    val next = (currentIndex + 1).coerceAtMost(destinations.lastIndex)
                    if (next != currentIndex) onNavigate(next)
                } else {
                    val prev = (currentIndex - 1).coerceAtLeast(0)
                    if (prev != currentIndex) onNavigate(prev)
                }
            }
        },
    )
}

fun Modifier.trackScroll(
    isScrollingDown: MutableState<Boolean>,
    scrollOffset: MutableState<Float>,
    previousScrollOffset: MutableState<Float>,
    threshold: Float = 50f,
): Modifier {
    val scrollConnection = object : NestedScrollConnection {
        override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
            val delta = available.y
            val newOffset = scrollOffset.value + delta
            scrollOffset.value = newOffset
            val scrollDelta = previousScrollOffset.value - newOffset
            if (abs(scrollDelta) > threshold) {
                isScrollingDown.value = scrollDelta > 0
                previousScrollOffset.value = newOffset
            }
            return Offset.Zero
        }

        override suspend fun onPostFling(consumed: Velocity, available: Velocity): Velocity {
            previousScrollOffset.value = scrollOffset.value
            return super.onPostFling(consumed, available)
        }
    }
    return this.nestedScroll(scrollConnection)
}

class MainActivity : FragmentActivity() {

    private val appLockState = mutableStateOf(false)
    private var pendingIntent: Intent? = null

    var zipUri by mutableStateOf<ArrayList<Uri>?>(null)

    enum class NavigateLocation { SUPERUSER, MODULES, SETTINGS }

    var navigateLoc by mutableStateOf<NavigateLocation?>(null)
    var moduleActionId by mutableStateOf<String?>(null)
    var amoledModeState = mutableStateOf(false)
    var navBarEnabled = mutableStateOf(true)

    val moduleViewModel: ModuleViewModel by viewModels()
    val superUserViewModel: SuperUserViewModel by viewModels()

    override fun attachBaseContext(newBase: Context?) {
        super.attachBaseContext(newBase?.let { LocaleHelper.applyLanguage(it) })
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        lifecycleScope.launch {
            if (superUserViewModel.appList.isEmpty()) {
                superUserViewModel.fetchAppList()
            }
            if (moduleViewModel.moduleList.isEmpty()) {
                moduleViewModel.fetchModuleList()
            }
        }

        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isNavigationBarContrastEnforced = false
        }

        try {
            val prefsInit = getSharedPreferences("settings", MODE_PRIVATE)
            amoledModeState.value = prefsInit.getBoolean("enable_amoled", false)
            navBarEnabled.value = prefsInit.getBoolean("enable_navbar", true)
            // Disable upstream KernelSU-Next GitHub release nag by default
            if (!prefsInit.contains("check_update")) {
                prefsInit.edit().putBoolean("check_update", false).apply()
            }
        } catch (_: Exception) {
        }

        if (Natives.isManager) install()

        if ((intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0) {
            intent.extras?.clear()
            intent = null
        }

        val prefsInit = getSharedPreferences("settings", MODE_PRIVATE)
        val requireBiometric = prefsInit.getBoolean("enable_biometric_lock", false)
        appLockState.value = savedInstanceState?.getBoolean("appLockState", requireBiometric) ?: requireBiometric

        if (intent != null) {
            handleIntent(intent)
        }

        setContent {
            KernelSUTheme(amoledMode = amoledModeState.value) {
                val wallpaperLayer = rememberGraphicsLayer()
                val contentLayer = rememberGraphicsLayer()

                var showSplash by rememberSaveable { mutableStateOf(true) }
                LaunchedEffect(appLockState.value) {
                    if (!appLockState.value && showSplash) {
                        delay(1150L)
                        showSplash = false
                    }
                }

                val navController = rememberNavController()
                val snackBarHostState = remember { SnackbarHostState() }
                val currentBackStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = currentBackStackEntry?.destination?.route
                val bottomBarRoutes = remember {
                    BottomBarDestination.entries.map { it.direction.route }.toSet()
                }
                val navigator = navController.rememberDestinationsNavigator()
                val fullFeatured = Natives.isFullFeatured()

                val homeDestination = BottomBarDestination.entries.firstOrNull()
                val startRoute = homeDestination?.direction?.route
                if (homeDestination != null && startRoute != null) {
                    BackHandler(enabled = currentRoute != startRoute && currentRoute in bottomBarRoutes) {
                        navigator.navigate(homeDestination.direction) {
                            popUpTo(NavGraphs.root) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                }

                val isScrollingDown = remember { mutableStateOf(false) }
                val scrollOffset = remember { mutableStateOf(0f) }
                val previousScrollOffset = remember { mutableStateOf(0f) }
                val lastValidNavbarSelection = remember { mutableStateOf(0) }

                LaunchedEffect(zipUri, navigateLoc, moduleActionId, showSplash) {
                    if (showSplash) return@LaunchedEffect

                    if (moduleActionId != null) {
                        navigator.navigate(ExecuteModuleActionScreenDestination(moduleActionId!!))
                        moduleActionId = null
                    }

                    if (!zipUri.isNullOrEmpty()) {
                        val uris = zipUri!!
                        val component = intent?.component?.className
                        val flashIt = when {
                            component?.endsWith("FlashAnyKernel") == true -> FlashIt.FlashAnyKernel(uris.first())
                            uris.size == 1 && ZipUtils.isAnyKernel3Zip(applicationContext, uris.first()) ->
                                FlashIt.FlashAnyKernel(uris.first())
                            else -> FlashIt.FlashModules(uris)
                        }
                        navigator.navigate(FlashScreenDestination(flashIt = flashIt))
                        zipUri = null
                    }

                    if (zipUri.isNullOrEmpty() && navigateLoc != null) {
                        when (navigateLoc) {
                            NavigateLocation.SUPERUSER -> navigator.navigate(SuperUserScreenDestination) {
                                popUpTo(NavGraphs.root.startRoute) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                            NavigateLocation.MODULES -> navigator.navigate(ModuleScreenDestination) {
                                popUpTo(NavGraphs.root.startRoute) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                            NavigateLocation.SETTINGS -> navigator.navigate(SettingScreenDestination) {
                                popUpTo(NavGraphs.root.startRoute) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                            else -> {}
                        }
                        navigateLoc = null
                    }
                }

                val showBottomBar = !showSplash &&
                    currentRoute in bottomBarRoutes &&
                    currentRoute != FlashScreenDestination.route &&
                    currentRoute != ExecuteModuleActionScreenDestination.route &&
                    !isScrollingDown.value &&
                    navBarEnabled.value

                CompositionLocalProvider(
                    LocalGlassWallpaperLayer provides wallpaperLayer,
                    LocalGlassContentLayer provides contentLayer,
                    LocalSnackbarHost provides snackBarHostState,
                    LocalScrollState provides ScrollState(
                        isScrollingDown = isScrollingDown,
                        scrollOffset = scrollOffset,
                        previousScrollOffset = previousScrollOffset,
                    ),
                    LocalNavBarEnabled provides navBarEnabled,
                ) {
                    Box(modifier = Modifier.fillMaxSize()) {
                        // Layer 1: Living aurora wallpaper + screen host recorded into contentLayer
                        // so the floating GlassBottomBar blurs scrolling cards in real time.
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .drawWithContent {
                                    contentLayer.record {
                                        this@drawWithContent.drawContent()
                                    }
                                    drawLayer(contentLayer)
                                }
                        ) {
                            GlassBackground(wallpaperLayer = wallpaperLayer)

                            Scaffold(
                                containerColor = Color.Transparent,
                                contentWindowInsets = WindowInsets(0, 0, 0, 0),
                            ) { innerPadding ->
                                val visibleDestinations = remember(fullFeatured) {
                                    BottomBarDestination.entries.filter { fullFeatured || !it.rootRequired }
                                }

                                fun navigateToIndex(index: Int) {
                                    val destination = visibleDestinations.getOrNull(index) ?: return
                                    if (destination.direction.route == currentRoute) return
                                    navigator.navigate(destination.direction) {
                                        popUpTo(NavGraphs.root.startRoute) { saveState = true }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }

                                val haptic = LocalHapticFeedback.current
                                val hostModifier = Modifier
                                    .padding(innerPadding)
                                    .fillMaxSize()
                                    .horizontalSwipeNavigator(
                                        currentRoute = currentRoute,
                                        destinations = visibleDestinations,
                                        onNavigate = {
                                            haptic.performHapticFeedback(HapticFeedbackType.GestureEnd)
                                            navigateToIndex(it)
                                        },
                                    )

                                DestinationsNavHost(
                                    modifier = hostModifier,
                                    navGraph = NavGraphs.root,
                                    navController = navController,
                                    defaultTransitions = object : NavHostAnimatedDestinationStyle() {
                                        override val enterTransition: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
                                            val targetRoute = targetState.destination.route
                                            val initialRoute = initialState.destination.route
                                            val targetIndex = BottomBarDestination.entries.indexOfFirst { it.direction.route == targetRoute }
                                            val initialIndex = BottomBarDestination.entries.indexOfFirst { it.direction.route == initialRoute }
                                            when {
                                                targetIndex != -1 && initialIndex != -1 -> {
                                                    val sign = if (targetIndex > initialIndex) 1 else -1
                                                    slideInHorizontally(initialOffsetX = { it * sign }, animationSpec = tween(280)) + fadeIn(tween(220))
                                                }
                                                targetRoute in bottomBarRoutes && initialRoute !in bottomBarRoutes ->
                                                    slideInHorizontally(initialOffsetX = { -it / 3 }, animationSpec = tween(280)) + fadeIn(tween(220))
                                                else ->
                                                    slideInHorizontally(initialOffsetX = { it }, animationSpec = tween(280)) + fadeIn(tween(220))
                                            }
                                        }

                                        override val exitTransition: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = {
                                            val targetRoute = targetState.destination.route
                                            val initialRoute = initialState.destination.route
                                            val targetIndex = BottomBarDestination.entries.indexOfFirst { it.direction.route == targetRoute }
                                            val initialIndex = BottomBarDestination.entries.indexOfFirst { it.direction.route == initialRoute }
                                            when {
                                                targetIndex != -1 && initialIndex != -1 -> {
                                                    val sign = if (targetIndex > initialIndex) -1 else 1
                                                    slideOutHorizontally(targetOffsetX = { it * sign }, animationSpec = tween(280)) + fadeOut(tween(200))
                                                }
                                                else ->
                                                    slideOutHorizontally(targetOffsetX = { -it / 3 }, animationSpec = tween(280)) + fadeOut(tween(200))
                                            }
                                        }

                                        override val popEnterTransition: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
                                            slideInHorizontally(initialOffsetX = { -it / 3 }, animationSpec = tween(280)) + fadeIn(tween(220))
                                        }

                                        override val popExitTransition: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = {
                                            slideOutHorizontally(targetOffsetX = { it }, animationSpec = tween(280)) + fadeOut(tween(200))
                                        }
                                    },
                                )
                            }
                        }

                        // Layer 2: Sibling Floating Liquid Glass Capsule Dock (blurs contentLayer!)
                        AnimatedVisibility(
                            visible = showBottomBar,
                            modifier = Modifier.align(Alignment.BottomCenter),
                            enter = slideInVertically(initialOffsetY = { it }) + fadeIn(tween(220)),
                            exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(tween(180)),
                        ) {
                            GlassBottomBar(navController, lastValidNavbarSelection)
                        }

                        // Layer 3: Redesigned Synthetica 2.0 3D Liquid Glass Splash
                        GlassSplash(
                            visible = showSplash,
                            modifier = Modifier.fillMaxSize(),
                        )

                        // Layer 4: Biometric App Lock Overlay
                        AppLockOverlay(amoledModeState.value)
                    }
                }
            }
        }
    }

    @Composable
    private fun AppLockOverlay(amoledMode: Boolean) {
        if (appLockState.value) {
            KernelSUTheme(amoledMode = amoledMode) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.surfaceContainerHigh,
                ) {
                    val lifecycleOwner = LocalLifecycleOwner.current
                    var isPromptShowing by remember { mutableStateOf(false) }
                    DisposableEffect(lifecycleOwner) {
                        val observer = LifecycleEventObserver { _, event ->
                            if (event == Lifecycle.Event.ON_RESUME) {
                                val prefs = getSharedPreferences("settings", MODE_PRIVATE)
                                val timeout = prefs.getLong("app_lock_timeout", 60000L)
                                if (!AppLockManager.shouldPrompt(timeout)) {
                                    appLockState.value = false
                                    pendingIntent?.let {
                                        handleIntent(it)
                                        pendingIntent = null
                                    }
                                    return@LifecycleEventObserver
                                }

                                if (!isPromptShowing) {
                                    isPromptShowing = true
                                    BiometricAuthenticator(this@MainActivity).authenticate(
                                        title = getString(R.string.biometric_prompt_subtitle),
                                        subtitle = null,
                                        onSuccess = {
                                            isPromptShowing = false
                                            appLockState.value = false
                                            AppLockManager.unlock()
                                            pendingIntent?.let {
                                                handleIntent(it)
                                                pendingIntent = null
                                            }
                                        },
                                        onError = {
                                            isPromptShowing = false
                                            Toast.makeText(this@MainActivity, "Auth failed: $it", Toast.LENGTH_SHORT).show()
                                            finish()
                                        },
                                    )
                                }
                            }
                        }
                        lifecycleOwner.lifecycle.addObserver(observer)
                        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
                    }
                }
            }
        }
    }

    fun setAmoledMode(enabled: Boolean) {
        try {
            val prefs = getSharedPreferences("settings", MODE_PRIVATE)
            prefs.edit().putBoolean("enable_amoled", enabled).apply()
        } catch (_: Exception) {
        }
        amoledModeState.value = enabled
    }

    fun setNavBarEnabled(enabled: Boolean) {
        try {
            val prefs = getSharedPreferences("settings", MODE_PRIVATE)
            prefs.edit().putBoolean("enable_navbar", enabled).apply()
        } catch (_: Exception) {
        }
        navBarEnabled.value = enabled
    }

    override fun onStart() {
        super.onStart()
        AppLockManager.onActivityStart()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
        setIntent(intent)
    }

    override fun onStop() {
        super.onStop()
        AppLockManager.onActivityStop(this)
        val prefsInit = getSharedPreferences("settings", MODE_PRIVATE)
        if (prefsInit.getBoolean("enable_biometric_lock", false)) {
            appLockState.value = true
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putBoolean("appLockState", appLockState.value)
    }

    private fun handleIntent(intent: Intent) {
        if (appLockState.value) {
            pendingIntent = intent
            return
        }
        val shortcutType = intent.getStringExtra("shortcut_type")
        if (shortcutType == "module_action") {
            moduleActionId = intent.getStringExtra("module_id")
        }

        when (intent.action) {
            Intent.ACTION_VIEW -> {
                zipUri = intent.data?.let { arrayListOf(it) }
                    ?: if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        intent.getParcelableArrayListExtra("uris", Uri::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableArrayListExtra("uris")
                    }
            }
            "ACTION_SETTINGS" -> navigateLoc = NavigateLocation.SETTINGS
            "ACTION_SUPERUSER" -> navigateLoc = NavigateLocation.SUPERUSER
            "ACTION_MODULES" -> navigateLoc = NavigateLocation.MODULES
            else -> {}
        }
    }
}

/**
 * APK 1.16-style Floating Liquid Glass Capsule Dock with real-time GPU backdrop blur
 * over [LocalGlassContentLayer], icon + label tabs, and spring-animated glass pill.
 */
@Composable
private fun GlassBottomBar(
    navController: NavHostController,
    lastValidSelection: MutableState<Int>,
) {
    val glass = LocalGlassStyle.current
    val navigator = navController.rememberDestinationsNavigator()
    val fullFeatured = Natives.isFullFeatured()
    val haptic = LocalHapticFeedback.current

    val visibleDestinations = remember(fullFeatured) {
        BottomBarDestination.entries.filter { fullFeatured || !it.rootRequired }
    }

    val currentBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = currentBackStackEntry?.destination?.route

    val isOnBackStack = visibleDestinations.map { destination ->
        navController.isRouteOnBackStackAsState(destination.direction).value
    }

    val selectedIndex = run {
        val exactMatch = visibleDestinations.indexOfFirst { it.direction.route == currentRoute }
        if (exactMatch != -1) exactMatch else isOnBackStack.indexOfLast { it }
    }

    if (selectedIndex != -1) {
        lastValidSelection.value = selectedIndex.coerceIn(0, (visibleDestinations.size - 1).coerceAtLeast(0))
    }
    val effectiveSelectedIndex = (if (selectedIndex != -1) selectedIndex else lastValidSelection.value)
        .coerceIn(0, (visibleDestinations.size - 1).coerceAtLeast(0))

    var isDraggingPill by remember { mutableStateOf(false) }
    var dragTargetIndex by remember { mutableStateOf(effectiveSelectedIndex) }

    val animatedSelectedIndex by animateFloatAsState(
        targetValue = (if (isDraggingPill) dragTargetIndex else effectiveSelectedIndex).toFloat(),
        animationSpec = if (isDraggingPill) {
            spring(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = Spring.StiffnessMedium)
        } else {
            spring(dampingRatio = 0.78f, stiffness = Spring.StiffnessMediumLow)
        },
        label = "dock-pill",
    )

    fun navigateToIndex(index: Int) {
        val destination = visibleDestinations.getOrNull(index) ?: return
        if (destination.direction.route == currentRoute) return
        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        navigator.navigate(destination.direction) {
            popUpTo(NavGraphs.root.startRoute) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    val navBottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = navBottomInset)
            .padding(horizontal = 18.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        val dockShape = RoundedCornerShape(30.dp)
        val innerPad = 6.dp
        val count = visibleDestinations.size.coerceAtLeast(1)
        val dockWidth = maxWidth.coerceAtMost(420.dp)
        val itemWidth = (dockWidth - innerPad * 2) / count
        val density = LocalDensity.current
        val itemWidthPx = with(density) { itemWidth.toPx() }
        val innerPadPx = with(density) { innerPad.toPx() }

        Box(
            modifier = Modifier
                .width(dockWidth)
                .height(68.dp)
                .iosGlass(
                    shape = dockShape,
                    blurRadius = glass.dockBlurRadius,
                    tintTop = glass.dockTintTop,
                    tintBottom = glass.dockTintBottom,
                    borderWidth = 1.1.dp,
                    elevation = 14.dp,
                    blurContent = true,
                )
                .pointerInput(visibleDestinations, effectiveSelectedIndex, itemWidthPx) {
                    detectDragGestures(
                        onDragStart = { offset ->
                            isDraggingPill = true
                            val idx = ((offset.x - innerPadPx) / itemWidthPx)
                                .toInt()
                                .coerceIn(0, visibleDestinations.lastIndex)
                            dragTargetIndex = idx
                        },
                        onDragEnd = {
                            if (isDraggingPill) {
                                navigateToIndex(dragTargetIndex)
                                isDraggingPill = false
                            }
                        },
                        onDragCancel = { isDraggingPill = false },
                        onDrag = { change, _ ->
                            if (isDraggingPill) {
                                change.consume()
                                val idx = ((change.position.x - innerPadPx) / itemWidthPx)
                                    .toInt()
                                    .coerceIn(0, visibleDestinations.lastIndex)
                                if (idx != dragTargetIndex) {
                                    haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    dragTargetIndex = idx
                                }
                            }
                        },
                    )
                }
                .padding(horizontal = innerPad, vertical = 6.dp),
        ) {
            // Active Liquid Glass Sliding Pill
            val pillShape = RoundedCornerShape(24.dp)
            Box(
                modifier = Modifier
                    .offset { IntOffset((animatedSelectedIndex * itemWidthPx).roundToInt(), 0) }
                    .width(itemWidth)
                    .fillMaxHeight()
                    .graphicsLayer {
                        val s = if (isDraggingPill) 1.04f else 1f
                        scaleX = s
                        scaleY = s
                    }
                    .clip(pillShape)
                    .background(glass.dockActivePill)
                    .border(
                        width = 0.85.dp,
                        color = glass.borderHighlight.copy(alpha = if (glass.isDark) 0.42f else 0.90f),
                        shape = pillShape,
                    )
            )

            Row(
                modifier = Modifier.fillMaxSize(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                visibleDestinations.forEachIndexed { index, destination ->
                    val isSelected = index == (if (isDraggingPill) dragTargetIndex else effectiveSelectedIndex)
                    Column(
                        modifier = Modifier
                            .width(itemWidth)
                            .fillMaxHeight()
                            .clip(pillShape)
                            .clickable(
                                interactionSource = remember { MutableInteractionSource() },
                                indication = null,
                            ) { navigateToIndex(index) },
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Icon(
                            imageVector = if (isSelected) destination.iconSelected else destination.iconNotSelected,
                            contentDescription = stringResource(destination.label),
                            tint = if (isSelected) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                            modifier = Modifier.size(22.dp),
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            text = stringResource(destination.label),
                            fontSize = 10.5.sp,
                            lineHeight = 12.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                            color = if (isSelected) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}
