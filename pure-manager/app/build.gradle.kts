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
        versionCode = 1
        versionName = "0.1.0"
        vectorDrawables.useSupportLibrary = true
    }

    buildTypes {
        release {
            // No shrinking in 0.1.0: the theme system is the only thing here and
            // R8 would obscure the very classes the tab exercises.
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }

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
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    // Kept out on purpose for now: libsu (root), docx4j (Office), sora-editor
    // (code), ffmpeg (audio). Each lands with the stage that needs it, so the
    // first APK stays small and the licence surface stays empty.
}
