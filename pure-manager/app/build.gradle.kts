plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "net.pure.manager"
    compileSdk = 36

    defaultConfig {
        applicationId = "net.pure.manager"
        // Android 10 is the floor the owner asked for. targetSdk 36 is what the CI
        // image ships; Android 17 has no stable SDK yet, and raising targetSdk
        // later does not change this code.
        minSdk = 29
        targetSdk = 36
        versionCode = 10
        versionName = "0.4.0"
        vectorDrawables.useSupportLibrary = true
    }

    // 0.1.0 is signed with the debug key. That is deliberate but temporary: an
    // unsigned APK cannot be installed at all, so the alternative is an artifact
    // nobody can open. The release keystore (RSA 4096, fingerprint
    // 5C:C7:E1:A7:...:69:7B) replaces this in stage 4, before any module is
    // published -- modules are signed separately and must match the app key.
    // Two signing configs, in order of preference.
    //
    // "release" reads the real key from the environment. It is absent here on
    // purpose: this repository is public, so a keystore in it would be a keystore
    // leaked, and the CI token in this sandbox cannot write Actions secrets. The
    // key itself is archived in the owner's Drive; the CI workflow asks for it at
    // build time and falls back to the debug key only when it cannot get one, in
    // which case the APK filename says DEBUGKEY.
    //
    // Every APK before 0.4.0 was signed with a throwaway key generated on each
    // runner, which meant the app could not be updated without uninstalling and
    // could never ship a module that checks the signature. That is the bug this
    // fixes; the archive in Drive is the durable half of the fix.
    signingConfigs {
        create("release") {
            val storePath = System.getenv("PM_KEYSTORE_PATH")
            if (!storePath.isNullOrBlank() && file(storePath).exists()) {
                storeFile = file(storePath)
                storePassword = System.getenv("PM_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("PM_KEY_ALIAS") ?: "pure-manager-release"
                keyPassword = System.getenv("PM_KEY_PASSWORD") ?: System.getenv("PM_KEYSTORE_PASSWORD")
            }
        }
        create("debugkey") {
            storeFile = file(System.getProperty("user.home") + "/.android/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            // No shrinking in 0.1.0: the theme system is the only thing here and
            // R8 would obscure the very classes the tab exercises. R8 lands with
            // the file layer in stage 2, together with its keep rules.
            isMinifyEnabled = false
            // Build type picks whichever config actually holds a key, so a build
            // without the release material still produces something installable
            // instead of an unsigned APK that silently "succeeds".
            val releaseKey = signingConfigs.getByName("release")
            signingConfig = if (releaseKey.storeFile != null) releaseKey
                else signingConfigs.getByName("debugkey")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }

    testOptions { unitTests.isReturnDefaultValues = true }

    packaging {
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "/META-INF/DEPENDENCIES",
        )
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")

    // Real blurred chrome, not a translucent rectangle. Pinned to 1.1.1 because
    // it is the last Haze built against Kotlin 2.0.21 / Compose 1.7.5; 1.2+
    // requires Kotlin 2.1 and would drag the whole toolchain up with it.
    implementation("dev.chrisbanes.haze:haze:1.1.1")

    // Stage 2: the browser reads the real file system, so it needs permission to
    // ask for all-files access and a choice between the two ways of getting it.
    // Core-ktx already provides ActivityResultContracts; nothing extra is added.
    implementation("androidx.documentfile:documentfile:1.0.1")

    testImplementation("junit:junit:4.13.2")

    // Kept out on purpose for now: libsu (root), docx4j (Office), sora-editor
    // (code), ffmpeg (audio). Each lands with the stage that needs it, so the
    // first APK stays small and the licence surface stays empty.
}
