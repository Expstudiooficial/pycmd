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
"$PYTHON" tools/test_pcmd.py

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
echo "== PyCmdTeach: every course, and every snippet it can run =="
# Runs every Python, C, Rust and Go snippet in the courses and compares what
# came out with what the lesson claims. A course that states the wrong output
# is wrong in five lessons at once, so this is not optional.
"$PYTHON" tools/test_teach.py

echo
echo "== PyCmdTeach practice: every question about a document, asked of the real thing =="
"$PYTHON" tools/test_practice.py

echo
echo "== Accounts: the website's API, and the app's client against it =="
if command -v node >/dev/null; then
  node --test --no-warnings website/test/api.test.mjs
fi
"$PYTHON" tools/test_account.py

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
node tools/test_board_ui.js
node tools/test_music_pro_ui.js
node tools/test_panel_sliders.js

echo
echo "== A theme reaching every bundled panel =="
# The mechanism themes are built on: a panel declares its colours as CSS
# variables and the app appends a :root block that overrides them. Easy to
# break with one literal colour, and nothing else would notice.
node tools/test_panel_theme.js

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
