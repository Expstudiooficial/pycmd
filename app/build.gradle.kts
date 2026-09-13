plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.chaquopy)
}

/**
 * Which ABIs to build for.
 *
 * Chaquopy's Python 3.13 runtime is 64-bit only, which matches every device
 * Play still accepts uploads for. x86_64 is included by default so the app also
 * runs on an emulator. Pass -Ppycmd.abi=arm64-v8a for a build aimed only at
 * real phones: Chaquopy bundles its Python assets for every ABI listed here and
 * does not take part in the APK splits, so dropping x86_64 saves about 3 MB
 * that no phone can use.
 */
val targetAbis: List<String> = (findProperty("pycmd.abi") as String?)
    ?.split(",")
    ?.map { it.trim() }
    ?.filter { it.isNotEmpty() }
    ?: listOf("arm64-v8a", "x86_64")

android {
    namespace = "com.expstudio.pycmd"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.expstudio.pycmd"
        minSdk = 24
        targetSdk = 35
        versionCode = 24
        versionName = "2.6.0"

        ndk {
            abiFilters += targetAbis
        }
    }

    /**
     * One signing key, kept in the repo, so an update installs over the build
     * already on the phone.
     *
     * Android only lets an APK replace an installed one when both were signed
     * by the same key. Gradle's own debug key is generated per machine and
     * lives outside the checkout, so two builds from two machines are two
     * different apps as far as the installer is concerned - which is what
     * turns "update" into "uninstall first", and uninstalling is what takes
     * the workspace with it.
     *
     * This is that key, captured and committed: the standard Android debug
     * certificate (alias androiddebugkey, password android). It is not a
     * secret and it is not a Play upload key - anybody can build an APK that
     * this one will accept as an update, which is the price of shipping an
     * APK by hand. Do not use it for anything published to a store.
     */
    signingConfigs {
        getByName("debug") {
            storeFile = rootProject.file("keystore/pycmd.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            // What is published. R8 removes the AndroidX and Compose code
            // nothing here calls, which is most of the dex - about a third of
            // the download, for an app whose own classes are a small part of
            // it. Everything reflective is kept by name in proguard-rules.pro:
            // Python calls back into Kotlin by method name, and a renamed
            // method is a crash nobody sees until the phone runs it.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")

            // The same key the debug builds used, because that is the one on
            // people's phones and Android replaces an app only when the
            // signature matches.
            signingConfig = signingConfigs.getByName("debug")

            // And the same application id, which is why it says ".debug" on a
            // release build. Android has no way to change an installed app's
            // id: a new one installs *beside* the old app rather than over it,
            // and the workspace stays behind in the one nobody opens any more.
            // The id is a name, not a claim about the build; every copy in the
            // wild carries this one, so it stays.
            applicationIdSuffix = ".debug"
        }
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        // So the About dialog reads the version rather than repeating it. It
        // said 1.0 for four releases because a string in a composable has no
        // way of knowing it is out of date.
        buildConfig = true
    }

    // One APK per ABI, plus a universal one, so a phone downloads only the
    // slice it can run. The split list is driven by the same targetAbis as the
    // native filters above: splitting on an ABI that was filtered out would
    // emit an APK with no native libraries in it at all.
    splits {
        abi {
            isEnable = targetAbis.size > 1
            reset()
            include(*targetAbis.toTypedArray())
            isUniversalApk = true
        }
    }

    lint {
        textReport = true
        xmlReport = true
        // A missing translation or a newer-dependency notice should not stop a
        // build; real correctness issues still surface in the report.
        abortOnError = false
        // ChromeOsAbiSupport: dropping x86_64 is a deliberate choice for the
        // phone-only build (-Ppycmd.abi=arm64-v8a); the default build keeps it.
        disable += setOf(
            "GradleDependency",
            "AndroidGradlePluginVersion",
            "OldTargetApi",
            "ChromeOsAbiSupport",
        )
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
        jniLibs {
            // CPython and its OpenSSL are 10 MB of native library, and modern
            // packaging stores them uncompressed so Android can map them
            // straight out of the APK. That is the right trade for an app
            // downloaded through a store, which compresses the transfer
            // itself. This one is downloaded as a raw APK over somebody's
            // phone connection, where those 10 MB are 10 MB: compressed they
            // are 3.7, and the download goes from 26 MB to 18.
            //
            // The cost is real and worth knowing: Android unpacks the
            // libraries at install time, so the app takes about 10 MB more
            // room on the device and the install itself is a little slower.
            useLegacyPackaging = true
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        // Chaquopy resolves the pip requirements below with a local CPython of
        // the same minor version. Override with
        // -Ppycmd.buildPython=/path/to/python3.13 if it is not on PATH.
        buildPython((findProperty("pycmd.buildPython") as String?) ?: "python3.13")

        pip {
            // Pure-Python batteries that are useful on a phone and always resolvable.
            install("requests==2.32.3")
            install("flask==3.0.3")
            install("rich==13.9.4")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.documentfile)
    implementation(libs.androidx.work.runtime.ktx)
    // Playback, and the media session that puts it on the lock screen.
    implementation(libs.androidx.media3.exoplayer)
    implementation(libs.androidx.media3.session)
    implementation(libs.kotlinx.coroutines.android)

    debugImplementation(libs.androidx.ui.tooling)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
}

/**
 * Keeps the in-app copies of the documentation in step with the real ones.
 *
 * The app shows README, TUTORIAL and PLUGINS on the phone, and an asset copy
 * that drifts from the file people read on GitHub is worse than no copy: one
 * of the two is then lying. Copying at build time means there is one source.
 */
val syncDocs by tasks.registering(Copy::class) {
    from(rootProject.file("README.md"))
    from(rootProject.file("TUTORIAL.md"))
    from(rootProject.file("PLUGINS.md"))
    from(rootProject.file("BUILTINS.md"))
    from(rootProject.file("FORKING.md"))
    into(layout.projectDirectory.dir("src/main/assets/docs"))
}

tasks.named("preBuild") { dependsOn(syncDocs) }
