"""One Notes-board call, for tools/test_board_ui.js: argv = workspace, call name; stdin = payload."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "src", "main", "python"))
import pycmd_board  # noqa: E402

print(pycmd_board.api(sys.argv[2], sys.stdin.read() or "{}", sys.argv[1]))
