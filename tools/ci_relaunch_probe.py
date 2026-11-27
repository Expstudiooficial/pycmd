"""CI only: the 5.9.1 relaunch bug, on a real Windows runner.

Run inside a one-file PyCmd (`PyCmd.exe --python ci_relaunch_probe.py <installed exe> <out file>`).
It starts the installed PyCmd the way an update does - from this PyCmd, with
the environment PyCmd now gives its children - and exits at once, so this
PyCmd's temp folder is gone by the time the other one starts. The other one
must still start: `--version` lands in <out file>.
"""
import os
import subprocess
import sys

from pycmd_win.runner import clean_env, forget_dll_directory

exe, out = sys.argv[1], sys.argv[2]
script = os.path.join(os.path.dirname(os.path.abspath(out)), "relaunch.cmd")
with open(script, "w", encoding="utf-8") as handle:
    handle.write("@ping -n 5 127.0.0.1 >nul\r\n")
    handle.write(f'@"{exe}" --version > "{out}" 2>&1\r\n')
forget_dll_directory()
flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
subprocess.Popen(["cmd", "/d", "/c", script], env=clean_env(), creationflags=flags, close_fds=True)
print("started the relaunch and left")
