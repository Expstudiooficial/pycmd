# Android Lab

A real Android device on this PC, with PyCmd Android installed and opened on
it. One button.

PyCmd does not contain Android - a system image alone is 2.5 GB. It sets up
and drives **Google's own emulator**, which is the tedious part. Everything it
downloads comes from Google, under Google's licence, and is checked against
the hash Google publishes.

## What Start does

1. **Java.** Google's SDK tools are Java programs and need Java 17 or newer.
   PyCmd uses yours, or Android Studio's, and if there is none installs
   Temurin 21 into its own folder - no administrator.
2. **The command-line tools**, straight from Google's repository index,
   checked against Google's SHA-1. An Android SDK you already have (from
   Android Studio, say) is used as it is, so there is one set of images on
   the disk, not two.
3. **Licences** are accepted first, so the big download never stops at a
   question nobody can see.
4. **The emulator, platform tools and Android itself** - about 2.5 GB, once.
5. **The device**, `PyCmd_Lab`, with the memory, storage, cores and graphics
   you chose.
6. **Hardware acceleration** is checked. Without it the emulator cannot run,
   so PyCmd says exactly what is missing and offers the fix (below).
7. **Boot.** The emulator's output goes to a log; if it stops before Android
   is up, the Lab says why within seconds rather than waiting ten minutes.
8. **PyCmd Android** is downloaded from the Android build's release manifest,
   checked against its SHA-256, installed, and opened.

Each step shows on the screen as it happens, with the full log beneath, and
**Stop setting up** cancels it.

## When acceleration is off

- **"Windows Hypervisor Platform is not enabled"** - press **Turn on Windows
  Hypervisor Platform**. Windows asks for administrator, turns the feature on,
  and needs a restart.
- **Prefer not to use Hyper-V?** **Install Google's hypervisor driver**
  instead.
- **"VT-x" or "SVM" is disabled** - virtualisation is switched off in the PC's
  firmware. Restart into the BIOS/UEFI setup (usually F2, F10 or Del while it
  starts), turn on Intel VT-x or AMD SVM, save, and start the Lab again.

## The device it builds

Android 13, 14, 15 or 16 with Google APIs; memory, storage, CPU cores, app
heap and the graphics mode are all settings. x86_64 on Intel and AMD - it runs
on your CPU directly, not translated. Changes apply the next time the device
starts; another Android version downloads its own image.

## Once it is running

Open PyCmd, Back / Home / Apps, type text into the device, take a screenshot
(saved to Downloads), read logcat (all of it, or only PyCmd's), install any
APK, wipe the device's data, or delete it - the image stays, so making it
again is quick.

**Phones on USB** appear in their own list - never mistaken for the lab
device - with an **Install PyCmd** button. Turn on USB debugging on the phone
first and allow the PC when it asks.

**Diagnostics** shows everything the Lab knows - Java, SDK packages,
acceleration, devices, the emulator's last words - ready to paste into a bug
report.
