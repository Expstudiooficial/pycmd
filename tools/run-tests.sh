#!/usr/bin/env bash
# Runs every check that does not need a device or an emulator.
#
#   tools/run-tests.sh
#
# Covers the embedded Python modules, the WebView JavaScript, and a debug
# build with Android Lint. Set PYTHON to point at a CPython 3.13 if it is not
# on PATH as python3.13.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3.13}"

echo "== Python engine =="
"$PYTHON" tools/test_runtime.py

echo
echo "== Language interpreters =="
"$PYTHON" tools/test_c.py
"$PYTHON" tools/test_go.py
"$PYTHON" tools/test_rust.py

echo
echo "== The app still says what it is called =="
"$PYTHON" tools/test_branding.py

echo
echo "== The console's commands =="
"$PYTHON" tools/test_shell.py

echo
echo "== Pages, the tunnel and Cloudflare =="
"$PYTHON" tools/test_pages.py

echo
echo "== The music library =="
"$PYTHON" tools/test_music.py

echo
echo "== Creator: the blocks and what they compile to =="
"$PYTHON" tools/test_creator.py

echo
echo "== Music Pro: what it asks the app for, and what it refuses =="
"$PYTHON" tools/test_music_pro.py

echo
echo "== Plugins, doctor, preview, cloud, bundled =="
"$PYTHON" tools/test_plugins.py
"$PYTHON" tools/test_doctor.py
"$PYTHON" tools/test_preview.py
"$PYTHON" tools/test_cloud.py
"$PYTHON" tools/test_bundled.py

echo
echo "== The published update manifest =="
"$PYTHON" tools/make_latest.py

echo
echo "== WebView JavaScript =="
node tools/test_js.js
node tools/test_editor.js
node tools/test_bridge.js
node tools/test_creator_ui.js
node tools/test_music_pro_ui.js
node tools/test_panel_sliders.js

echo
echo "== Panels, laid out at a phone's size =="
# The only check here that measures rather than reads. Needs playwright-core
# and a Chromium; says so and skips when they are not installed.
node tools/test_panels.js

echo
echo "== Build and lint =="
# The release build too, because that is what is published: R8 runs there and
# nowhere else, and a keep rule that stopped being right would otherwise only
# show up on somebody's phone. And the JVM unit tests, which is where the
# rules that are pure arithmetic live - who owns a drag inside a panel, for
# one, which took every plugin's sliders with it when it was wrong.
./gradlew :app:assembleDebug :app:assembleRelease :app:testDebugUnitTest \
    :app:lintDebug --console=plain

echo
echo "All checks passed."
