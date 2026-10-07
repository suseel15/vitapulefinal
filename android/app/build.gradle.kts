import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

val localProperties = Properties()
rootProject.file("local.properties").takeIf { it.isFile }?.inputStream()?.use { localProperties.load(it) }

fun localConfiguration(name: String, defaultValue: String): String =
    providers.gradleProperty(name)
        .orElse(providers.provider { localProperties.getProperty(name) })
        .orElse(providers.environmentVariable(name))
        .orElse(defaultValue)
        .get()

android {
    namespace = "app.vitapulse.android"
    compileSdk = 36

    defaultConfig {
        applicationId = "app.vitapulse.android"
        minSdk = 29
        targetSdk = 36
        versionCode = 2
        versionName = "1.0.1"
        fun escapedBuildConfig(value: String) = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
        buildConfigField(
            "String",
            "ESP32_BASE_URL",
            escapedBuildConfig(localConfiguration("VITAPULSE_ESP32_BASE_URL", "http://192.168.4.1/")),
        )
        buildConfigField(
            "String",
            "API_BASE_URL",
            escapedBuildConfig(localConfiguration("VITAPULSE_API_BASE_URL", "https://vitapulse-eosin.vercel.app/api/v1/")),
        )
        buildConfigField(
            "String",
            "WEB_APP_URL",
            escapedBuildConfig(
                localConfiguration("VITAPULSE_WEB_APP_URL", "https://vitapulse-eosin.vercel.app/"),
            ),
        )
        buildConfigField(
            "String",
            "SUPABASE_URL",
            escapedBuildConfig(localConfiguration("VITAPULSE_SUPABASE_URL", "")),
        )
        buildConfigField(
            "String",
            "SUPABASE_PUBLISHABLE_KEY",
            escapedBuildConfig(localConfiguration("VITAPULSE_SUPABASE_PUBLISHABLE_KEY", "")),
        )
        buildConfigField("long", "ESP32_POLL_INTERVAL_MS", "100L")
        buildConfigField("long", "ESP32_STALE_TIMEOUT_MS", "1500L")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.05.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.camera:camera-camera2:1.4.2")
    implementation("androidx.camera:camera-lifecycle:1.4.2")
    implementation("androidx.camera:camera-view:1.4.2")
    implementation("com.google.mlkit:face-detection:16.1.7")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.code.gson:gson:2.11.0")

    implementation("androidx.room:room-runtime:2.7.1")
    implementation("androidx.room:room-ktx:2.7.1")
    ksp("androidx.room:room-compiler:2.7.1")
    implementation("androidx.security:security-crypto:1.1.0")
    implementation("androidx.health.connect:connect-client:1.1.0")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("com.google.guava:guava:33.4.8-android")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
}
