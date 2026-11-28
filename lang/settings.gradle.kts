// PyCmd, the language - its fast engine, in Kotlin. A build of its own so the
// Windows CI can make a native exe from it without the Android SDK; the
// Android app compiles the same sources straight into the APK.
pluginManagement {
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositories { mavenCentral() }
}
rootProject.name = "pycmd-lang"
