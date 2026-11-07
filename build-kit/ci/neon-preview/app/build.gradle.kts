plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}
android {
    // The namespace keeps R imports in the shared UI source valid; the app ID is
    // deliberately distinct from the trusted Manager package.
    namespace = "com.rifsxd.ksunext"
    compileSdk = 36
    defaultConfig {
        applicationId = "net.ember.labs.neonpreview"
        minSdk = 26
        targetSdk = 36
        versionCode = 40000
        versionName = "3.0.0-preview"
    }
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
    kotlinOptions { jvmTarget = "21" }
}
dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.07.00"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.2")
}
