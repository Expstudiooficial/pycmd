package com.expstudio.pycmd.util

import android.content.Context
import android.os.Build
import java.io.File

/**
 * What kind of machine this is, and whether this build fits it.
 *
 * PyCmd carries a CPython built for a particular processor. That is fine on a
 * phone, where there is only one answer, and it is where every emulator
 * problem this app has ever had comes from: a desktop emulator is an x86_64
 * machine, and an APK holding only arm64 code either refuses to install or
 * installs and then dies the moment Python is asked to start.
 *
 * None of that is visible from inside the app unless somebody writes it down,
 * so this is where it gets written down. [report] is what the System tab shows
 * and what people paste into a bug report; [verdict] is the one line that says
 * whether the download they picked was the right one.
 */
object Device {

    private const val TAG = "device"

    /** The processors this machine can run code for, best first. */
    val abis: List<String> get() = Build.SUPPORTED_ABIS.orEmpty().toList()

    /** The processor the app is actually running as. */
    val abi: String get() = abis.firstOrNull().orEmpty()

    /**
     * Whether this looks like an emulator rather than a phone.
     *
     * Deliberately a vote rather than a single test. Every individual signal
     * here is one some real phone gets wrong - Google's own Pixels report a
     * `google` brand, cheap tablets ship with `generic` product names, and a
     * rooted phone can say anything - so no one of them decides on its own.
     * Two or more agreeing has never been a phone in practice.
     */
    val isEmulator: Boolean by lazy { looksEmulated(signals()) }

    /** Which of the tests fired, for the System tab and the log. */
    val emulatorSignals: List<String> by lazy { signals().filterValues { it }.keys.toList() }

    private fun signals(): Map<String, Boolean> = linkedMapOf(
        "fingerprint" to (
            Build.FINGERPRINT.startsWith("generic") ||
                Build.FINGERPRINT.startsWith("unknown") ||
                Build.FINGERPRINT.contains("generic_x86") ||
                Build.FINGERPRINT.contains("vbox") ||
                Build.FINGERPRINT.contains("emulator", ignoreCase = true)
            ),
        "model" to (
            Build.MODEL.contains("google_sdk") ||
                Build.MODEL.contains("sdk_gphone") ||
                Build.MODEL.contains("Emulator") ||
                Build.MODEL.contains("Android SDK built for")
            ),
        "brand" to (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic")),
        "product" to (
            Build.PRODUCT == "google_sdk" ||
                Build.PRODUCT == "sdk" ||
                Build.PRODUCT == "sdk_x86" ||
                Build.PRODUCT == "sdk_gphone64_x86_64" ||
                Build.PRODUCT.startsWith("sdk_gphone") ||
                Build.PRODUCT.contains("vbox") ||
                Build.PRODUCT.contains("emulator", ignoreCase = true)
            ),
        "hardware" to (
            Build.HARDWARE == "goldfish" ||
                Build.HARDWARE == "ranchu" ||
                Build.HARDWARE == "cutf_cvm" ||
                Build.HARDWARE.startsWith("vbox")
            ),
        "manufacturer" to (Build.MANUFACTURER == "Genymotion" || Build.MANUFACTURER == "unknown"),
        "qemu-files" to QEMU_FILES.any { runCatching { File(it).exists() }.getOrDefault(false) },
    )

    private val QEMU_FILES = listOf(
        "/dev/socket/qemud",
        "/dev/qemu_pipe",
        "/system/lib/libc_malloc_debug_qemu.so",
        "/system/bin/qemu-props",
    )

    /**
     * The rule, split out so a test can hand it made-up signals.
     *
     * `hardware` and `qemu-files` are each enough alone: `goldfish` and
     * `ranchu` are the names of Android's own emulated boards and nothing else
     * uses them, and `/dev/qemu_pipe` is a device node only QEMU creates. The
     * rest are brand strings a real phone can trip, so they need company.
     */
    fun looksEmulated(signals: Map<String, Boolean>): Boolean {
        if (signals["hardware"] == true) return true
        if (signals["qemu-files"] == true) return true
        return signals.values.count { it } >= 2
    }

    /**
     * Whether Python can start at all on this machine.
     *
     * CPython is 64-bit here, so a 32-bit-only machine has no interpreter to
     * run. That is not a configuration anybody ships any more, but it is the
     * one failure worth naming rather than letting Python die with a link
     * error nobody can read.
     */
    val has64Bit: Boolean get() = abis.any { it == "arm64-v8a" || it == "x86_64" }

    /**
     * Whether the native libraries in this APK match this machine.
     *
     * Checked by looking for the interpreter itself rather than by comparing
     * ABI strings: an APK can carry code for a processor the installer threw
     * away, and the only thing that matters is whether the library is on disk
     * now.
     */
    fun nativeCodeMatches(context: Context): Boolean {
        val dir = runCatching { File(context.applicationInfo.nativeLibraryDir) }.getOrNull()
            ?: return true
        val names = runCatching { dir.list().orEmpty().toList() }.getOrDefault(emptyList())
        // An empty directory is not a mismatch on its own: with extractNativeLibs
        // off, Android maps the libraries straight out of the APK and there is
        // nothing on disk to list. PyCmd packages them the old way, so there
        // should be files - but guessing wrong here would mean shouting at
        // somebody whose app is working.
        if (names.isEmpty()) return true
        return names.any { it.startsWith("libchaquopy") || it.startsWith("libpython") }
    }

    /** One line about whether this download was the right one for this machine. */
    fun verdict(context: Context): String = when {
        !has64Bit ->
            "This machine is 32-bit only. PyCmd's Python is 64-bit, so it cannot run here."
        !nativeCodeMatches(context) ->
            "This copy of PyCmd has no Python for $abi. Install the universal APK, " +
                "or the one built for $abi."
        isEmulator ->
            "Emulator ($abi). Python is here and matches - this is a supported setup."
        else -> "Device ($abi). Python matches this processor."
    }

    /** Everything above as text, for the System tab's copy button and bug reports. */
    fun report(context: Context): String = buildString {
        appendLine("machine: ${if (isEmulator) "emulator" else "device"}")
        if (emulatorSignals.isNotEmpty()) appendLine("signals: ${emulatorSignals.joinToString(", ")}")
        appendLine("abis: ${abis.joinToString(", ").ifEmpty { "unknown" }}")
        appendLine("board: ${Build.HARDWARE} / ${Build.BOARD}")
        appendLine("product: ${Build.PRODUCT}")
        appendLine("model: ${Build.MANUFACTURER} ${Build.MODEL}")
        appendLine("android: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
        appendLine("native: ${runCatching { context.applicationInfo.nativeLibraryDir }.getOrNull()}")
        appendLine("verdict: ${verdict(context)}")
    }

    /** Writes the lot to the debug log once, at start-up. */
    fun log(context: Context) {
        runCatching {
            if (isEmulator) {
                DebugLog.info(
                    TAG,
                    "running on an emulator",
                    "$abi; ${emulatorSignals.joinToString(", ")}",
                )
            } else {
                DebugLog.info(TAG, "running on a device", abi)
            }
            if (!nativeCodeMatches(context)) {
                DebugLog.error(TAG, "no native Python for this processor", verdict(context))
            }
        }
    }
}
