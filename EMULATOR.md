# Running PyCmd on an emulator

PyCmd is an Android app, so the way to run it on a computer is an Android
emulator. This page is the short version of everything that can go wrong, in
the order it goes wrong.

Until 2.7.0 the answer was "it doesn't work", and that was our fault rather
than yours — see [Why it used to fail](#why-it-used-to-fail) at the bottom.

## The one rule

**Use an x86_64 system image.** Not arm64.

An emulator on a PC or an Intel Mac is an x86_64 machine. PyCmd carries a real
CPython compiled for a particular processor, and a build with only arm64 code
in it cannot start Python on an x86_64 machine — Android either refuses to
install it (`INSTALL_FAILED_NO_MATCHING_ABIS`) or installs it and then the app
dies the first time it reaches the interpreter.

The APK published in `dist/` is the **universal** one: it carries both
`arm64-v8a` and `x86_64`, so it installs and runs on a phone and on an
emulator from the same file. There is nothing to choose.

On an Apple Silicon Mac the opposite is true: there the host is arm64, so use
an **arm64-v8a** image. Same APK either way.

## Android Studio

1. **Tools → Device Manager → Create device.**
2. Pick any phone. Pixel 6 is a fine default.
3. On the system image page, choose the **x86_64** column (or **arm64-v8a** on
   an Apple Silicon Mac). API 30 or newer. Any of them will do — PyCmd's
   minimum is API 24.
4. Finish, start it, and drag `PyCmd-2.7.0.apk` onto the running emulator
   window. That installs it.

That is the whole procedure. If you would rather not install Android Studio,
the command line below needs about 500 MB instead of about 10 GB.

## Command line only

```sh
# The three packages that are actually needed.
sdkmanager "platform-tools" "emulator" "system-images;android-35;google_apis;x86_64"

# A device to run.
avdmanager create avd -n pycmd -k "system-images;android-35;google_apis;x86_64" -d pixel_6

# Start it. -gpu host is the important flag; see below.
emulator -avd pycmd -gpu host

# In another terminal, once it has booted.
adb install -r dist/PyCmd-2.7.0.apk
adb shell monkey -p com.expstudio.pycmd.debug -c android.intent.category.LAUNCHER 1
```

## If it is slow

A slow emulator is the other half of what used to read as "PyCmd freezes".
Four things, in the order they are worth trying:

1. **`-gpu host`.** Without it the emulator draws everything on the CPU.
   PyCmd's console and editor are WebViews, and software-rendered WebViews on
   an emulator are genuinely painful. In Android Studio this is
   *Graphics: Hardware* in the AVD's advanced settings.
2. **Hardware virtualisation.** On Linux that means `/dev/kvm` exists and you
   can read it (`ls -l /dev/kvm`; add yourself to the `kvm` group if not). On
   Windows, WHPX or the Intel HAXM driver. Without it every instruction is
   interpreted, and the app will take minutes to start rather than seconds.
   `emulator -accel-check` says what it found.
3. **The right image for the host.** An arm64 image on an x86 PC runs under
   full processor emulation. It works, in the sense that it eventually
   finishes. It is about thirty times slower than the native image and it is
   the single most common reason somebody reports PyCmd as hanging.
4. **PyCmd's own switch.** *More → Appearance → Short animations* turns off
   the transitions in plugin panels. On a software-rendered emulator those
   cost real frames.

## First start takes a while

The first time PyCmd opens, Chaquopy unpacks the Python standard library into
the app's storage. On a phone that is a few seconds; on an emulator without
hardware acceleration it can be the best part of a minute, and the console
says `Python ... ready` when it is done. It happens once per install.

## Checking what the app thinks it is on

**More → System → This machine.** It shows:

* whether PyCmd believes it is on an emulator, and which tests said so
* every processor the machine reports
* whether this build's native Python matches that processor — the line that
  tells you immediately if you have the wrong APK

The **Copy this** button puts the lot on the clipboard. If you report a
problem, paste that.

## Why it used to fail

`dist/latest.json` published the `arm64-v8a` split rather than the universal
APK. The build has produced all three APKs — arm64, x86_64 and universal — for
a long time; the release just pointed at the wrong one. So every emulator on
every PC got an APK with no code it could run, and the two failures people
reported ("it crashes" and "it freezes") were the two shapes that takes: a
refused install or a dead interpreter, and an arm64 image under full
translation.

2.7.0 publishes the universal APK, and `tools/make_latest.py` now refuses to
write a manifest for an APK that has no `x86_64` in it. The same mistake
cannot be released again without the release script saying so.
