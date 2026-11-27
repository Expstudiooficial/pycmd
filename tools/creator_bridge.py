"""One plugin export, for the panel tests: argv = state folder, export name[, plugin folder]; stdin = payload."""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREATOR = os.path.join(ROOT, "app", "src", "main", "assets", "plugins",
                       sys.argv[3] if len(sys.argv) > 3 else "creator")
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))


class Api:
    def __init__(self, folder):
        self.folder, self.exports = folder, {}

    def store(self, data=None):
        path = os.path.join(self.folder, "state.json")
        if data is None:
            try:
                with open(path, encoding="utf-8") as handle:
                    return json.load(handle)
            except (OSError, ValueError):
                return {}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return data

    def export(self, function=None, *, name=None):
        self.exports[function.__name__] = function
        return function

    def command(self, name, help=""):
        return lambda function: function

    def setting(self, name, default=None):
        return default

    def workspace_path(self, *parts):
        return os.path.join(self.folder, *parts)

    def read(self, path, default=None):
        return default

    def write(self, path, text):
        full = os.path.join(self.folder, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True

    def log(self, *args):
        pass

    refresh = open_file = log

    def files(self, pattern="*"):
        import glob
        return glob.glob(os.path.join(self.folder, "**", pattern), recursive=True)


spec = importlib.util.spec_from_file_location("creator_main", os.path.join(CREATOR, "main.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
api = Api(sys.argv[1])
module.setup(api)
print(json.dumps(api.exports[sys.argv[2]](json.loads(sys.stdin.read() or "{}"))))
