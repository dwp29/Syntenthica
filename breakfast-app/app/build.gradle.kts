import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// CI passes these as -P properties. Nothing is committed and no private key is
// ever stored in this repository.
val ciStoreFile: String? = project.findProperty("ciStoreFile") as String?
val ciVersionCode: Int = (project.findProperty("breakfastVersionCode") as String? ?: "1").toInt()
val ciVersionName: String = project.findProperty("breakfastVersionName") as String? ?: "0.0.0"

android {
    namespace = "app.breakfast.manager"
    compileSdk = 36

    defaultConfig {
        applicationId = "app.breakfast.manager"
        minSdk = 26
        targetSdk = 36
        versionCode = ciVersionCode
        versionName = ciVersionName
    }

    signingConfigs {
        if (ciStoreFile != null) {
            create("ci") {
                storeFile = file(ciStoreFile)
                storePassword = project.findProperty("ciStorePassword") as String?
                keyAlias = project.findProperty("ciKeyAlias") as String?
                keyPassword = project.findProperty("ciKeyPassword") as String?
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.findByName("ci")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // setOf() because the DSL exposes the target as a Property.
    kotlin {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_17)
        }
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }

    packaging {
        resources.excludes += setOf("META-INF/*.kotlin_module")
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
