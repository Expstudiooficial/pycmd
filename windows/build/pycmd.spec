# PyInstaller recipe for PyCmd.exe
#
# One file, no console window, everything the app needs inside it: the shared
# engine, the web assets, the bundled plugins, the guides and the UI.
#
# Run it from the repository root on Windows:
#
#     pip install -r windows/build/requirements.txt
#     pyinstaller windows/build/pycmd.spec --noconfirm
#
# What comes out is dist\PyCmd.exe and nothing else - no folder of DLLs to
# keep beside it, no installer, no registry. That is deliberate: the phone
# build is one APK you can hand somebody, and this should be one exe.
#
# It is not signed here. Signing needs a certificate, which is not something a
# repository can hold, so a downloaded PyCmd.exe will show Windows SmartScreen
# the first time until enough people have run it. FORKING.md says how to sign
# your own build if you have a certificate.

import os

block_cipher = None

ROOT = os.path.abspath(os.getcwd())
ENGINE = os.path.join(ROOT, "app", "src", "main", "python")
ASSETS = os.path.join(ROOT, "app", "src", "main", "assets")
WINDOWS = os.path.join(ROOT, "windows")

# Shipped as data rather than imported, because the plugin runtime finds them
# on disk by path - it is the same code the phone runs, and it expects files.
datas = [
    (ENGINE, "engine"),
    (os.path.join(ASSETS, "web"), "assets/web"),
    (os.path.join(ASSETS, "plugins"), "assets/plugins"),
    (os.path.join(ASSETS, "docs"), "assets/docs"),
    (os.path.join(ASSETS, "examples"), "assets/examples"),
    (os.path.join(WINDOWS, "ui"), "ui"),
    (os.path.join(WINDOWS, "docs"), "windows/docs"),
]
datas = [(source, target) for source, target in datas if os.path.exists(source)]

# The engine imports these lazily or by name, so PyInstaller's scanner does
# not always see them. Missing one shows up as a screen that is empty on a
# built exe and fine from a checkout, which is a miserable bug to chase.
hiddenimports = [
    "pycmd_cloud", "pycmd_cloudflare", "pycmd_doctor", "pycmd_download",
    "pycmd_music", "pycmd_packages", "pycmd_pages", "pycmd_plugins",
    "pycmd_preview", "pycmd_runtime", "pycmd_servers", "pycmd_shell",
    "pycmd_tools", "pycmd_tunnel",
    "pycmd_langs", "pycmd_langs.registry",
    "pycmd_langs.c_interp", "pycmd_langs.c_lexer", "pycmd_langs.c_parser",
    "pycmd_langs.c_stdlib", "pycmd_langs.clike_lexer",
    "pycmd_langs.go_interp", "pycmd_langs.go_parser", "pycmd_langs.go_stdlib",
    "pycmd_langs.go_values",
    "pycmd_langs.rust_interp", "pycmd_langs.rust_parser",
    "pycmd_langs.rust_stdlib", "pycmd_langs.rust_values",
    # PyCmd Learn: the engine loads its course modules by name, and the
    # Windows-only courses are loaded the same way from pycmd_win.courses.
    "pycmd_teach",
    "pycmd_teach.courses_core", "pycmd_teach.courses_systems",
    "pycmd_teach.courses_script", "pycmd_teach.courses_markup",
    "pycmd_teach.extra_core", "pycmd_teach.extra_systems",
    "pycmd_teach.extra_script", "pycmd_teach.extra_markup",
    # 4.5: practice rounds and accounts. Imported inside functions and behind
    # try/except ImportError, so a build without them would not fail - it
    # would quietly ship 14,700 lessons instead of 90,000 and no sign-in.
    "pycmd_teach.practice", "pycmd_teach.practice_docs", "pycmd_teach.cloud",
    "pycmd_win.courses.practice_more",
    "pycmd_win.courses", "pycmd_win.courses.functional", "pycmd_win.courses.dotnet",
    "pycmd_win.courses.beam", "pycmd_win.courses.jvm", "pycmd_win.courses.data",
    "pycmd_win.courses.classic", "pycmd_win.courses.scripting",
    "pycmd_win.features", "pycmd_win.learn", "pycmd_win.fetch", "pycmd_win.portable",
    "xml.etree.ElementTree",
    # Standard library corners the engine reaches for at runtime.
    "sqlite3", "ssl", "hashlib", "zipfile", "tarfile", "email.mime.text",
    "http.server", "socketserver", "webbrowser", "ctypes.wintypes",
]

a = Analysis(
    [os.path.join(WINDOWS, "build", "entry.py")],
    pathex=[ROOT, WINDOWS, ENGINE],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Nothing here needs a GUI toolkit of its own: the window is WebView2
    # through pywebview, and dragging tkinter or PyQt in would add tens of
    # megabytes for nothing.
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6",
              "matplotlib", "numpy", "test", "unittest", "pydoc_data"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PyCmd",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # No console window behind the app. Anything worth saying goes to the
    # debug log, which has a screen of its own.
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(WINDOWS, "build", "pycmd.ico")
    if os.path.exists(os.path.join(WINDOWS, "build", "pycmd.ico")) else None,
    version=os.path.join(WINDOWS, "build", "version.txt")
    if os.path.exists(os.path.join(WINDOWS, "build", "version.txt")) else None,
)
