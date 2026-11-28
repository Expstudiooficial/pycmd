plugins {
    kotlin("jvm") version "2.1.20"
}

// Bytecode Android can take (17), built by whatever JDK is installed.
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

tasks.jar {
    archiveFileName.set("pcmd.jar")
    manifest { attributes("Main-Class" to "com.expstudio.pycmd.lang.Main") }
    from(configurations.runtimeClasspath.get().map { if (it.isDirectory) it else zipTree(it) })
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
}
