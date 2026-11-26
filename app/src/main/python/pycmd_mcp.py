"""PyCmd as an MCP server: AI agents control the app.

The Model Context Protocol lets an AI app (Claude Code, Claude Desktop,
Antigravity, Cursor, VS Code, Gemini CLI, Codex, Windsurf...) call tools on a
server. This module is the server - protocol, HTTP, auth - and nothing else;
each build (Windows, Android) registers its own tools on a Registry.

Transport: Streamable HTTP. POST a JSON-RPC message to /mcp, get JSON back.
Every request needs the token, as `Authorization: Bearer <token>` (or
`?token=` for clients that cannot set headers). Requests carrying an Origin
that is not this machine are refused, so a web page cannot drive PyCmd from
a browser even on localhost.
"""

from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PROTOCOL = "2025-06-18"
SUPPORTED = ("2025-06-18", "2025-03-26", "2024-11-05")


class Tool:
    __slots__ = ("name", "description", "schema", "fn", "read_only", "group")

    def __init__(self, name, description, fn, params=None, required=(), read_only=False,
                 group=""):
        self.name = name
        self.description = description
        self.fn = fn
        self.read_only = read_only
        self.group = group
        props = {}
        for key, spec in (params or {}).items():
            if isinstance(spec, str):          # "description" -> any type
                spec = {"description": spec}
            props[key] = spec
        self.schema = {"type": "object", "properties": props, "required": list(required)}

    def listing(self):
        return {"name": self.name, "description": self.description,
                "inputSchema": self.schema,
                "annotations": {"readOnlyHint": self.read_only, "title": self.name}}


class Registry:
    """The tools, and a log of the last calls (the MCP tab shows it)."""

    def __init__(self, name="pycmd", version="1"):
        self.name, self.version = name, version
        self.tools: dict = {}
        self.read_only = False
        self.calls: list = []
        self.instructions = ""

    def add(self, *args, **kwargs) -> Tool:
        tool = Tool(*args, **kwargs)
        self.tools[tool.name] = tool
        return tool

    def call(self, name, arguments):
        tool = self.tools.get(name)
        if tool is None:
            return _text({"ok": False, "error": f"there is no tool called {name}"}, True)
        if self.read_only and not tool.read_only:
            return _text({"ok": False, "error": "PyCmd's MCP server is in read-only mode; "
                          f"{name} changes things. Switch read-only off in the MCP tab."}, True)
        started = time.time()
        try:
            result = tool.fn(**(arguments or {}))
        except TypeError as error:
            result = {"ok": False, "error": f"bad arguments for {name}: {error}"}
        except Exception as error:  # noqa: BLE001 - an agent should read it, not crash us
            result = {"ok": False, "error": f"{type(error).__name__}: {error}",
                      "trace": traceback.format_exc()[-800:]}
        failed = isinstance(result, dict) and result.get("ok") is False
        self.calls = (self.calls + [{"tool": name, "at": int(started), "ok": not failed,
                                     "ms": int((time.time() - started) * 1000)}])[-50:]
        if isinstance(result, dict) and "image" in result:
            content = [{"type": "image", "data": result["image"],
                        "mimeType": result.get("mime", "image/png")}]
            extra = {k: v for k, v in result.items() if k not in ("image", "mime")}
            if extra:
                content.append({"type": "text", "text": json.dumps(extra)})
            return {"content": content, "isError": failed}
        return _text(result, failed)


def _text(result, failed=False):
    text = result if isinstance(result, str) else json.dumps(result, indent=1, default=str)
    if len(text) > 200_000:
        text = text[:200_000] + "\n... (cut: ask for less)"
    return {"content": [{"type": "text", "text": text}], "isError": bool(failed)}


def handle(registry: Registry, message):
    """One JSON-RPC message in, one reply out (None for a notification)."""
    if isinstance(message, list):
        replies = [r for r in (handle(registry, m) for m in message) if r is not None]
        return replies or None
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "not a JSON-RPC 2.0 message")
    method, ident = message.get("method"), message.get("id")
    params = message.get("params") or {}
    if ident is None:
        return None  # notifications/initialized and friends need no answer
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _result(ident, {
            "protocolVersion": asked if asked in SUPPORTED else PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": registry.name, "version": registry.version},
            "instructions": registry.instructions})
    if method == "ping":
        return _result(ident, {})
    if method == "tools/list":
        return _result(ident, {"tools": [t.listing() for t in registry.tools.values()]})
    if method == "tools/call":
        return _result(ident, registry.call(params.get("name", ""), params.get("arguments")))
    if method in ("resources/list", "prompts/list"):
        return _result(ident, {method.split("/")[0]: []})
    return _error(ident, -32601, f"PyCmd does not know {method}")


def _result(ident, result):
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def _error(ident, code, message):
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


class Server:
    """The HTTP side. start() and stop() are safe to call in any order."""

    def __init__(self, registry: Registry):
        self.registry = registry
        self.httpd = None
        self.token = ""
        self.host, self.port = "127.0.0.1", 8765

    @property
    def running(self):
        return self.httpd is not None

    def start(self, token: str, port: int = 8765, host: str = "127.0.0.1") -> dict:
        self.stop()
        self.token, self.port, self.host = token, int(port), host
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, status, body=None, headers=None):
                data = b"" if body is None else json.dumps(body).encode("utf-8")
                self.send_response(status)
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                if body is not None:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _allowed(self):
                origin = self.headers.get("Origin", "")
                if origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1",
                                                                 "::1", None):
                    return False
                given = self.headers.get("Authorization", "")
                given = given[7:] if given.lower().startswith("bearer ") else ""
                given = given or self.headers.get("X-PyCmd-Token", "") or \
                    parse_qs(urlparse(self.path).query).get("token", [""])[0]
                return bool(server.token) and hmac.compare_digest(given, server.token)

            def do_GET(self):
                if urlparse(self.path).path == "/":
                    return self._send(200, {"name": "PyCmd MCP", "mcp": "/mcp"})
                self._send(405, {"error": "POST JSON-RPC to /mcp"}, {"Allow": "POST"})

            def do_DELETE(self):
                self._send(200, {})

            def do_POST(self):
                # The body is read first, always: on a kept-alive connection an
                # unread body would be parsed as the next request.
                length = int(self.headers.get("Content-Length") or 0)
                if length > 8 * 1024 * 1024:
                    self.close_connection = True
                    return self._send(413, {"error": "too big"})
                body = self.rfile.read(length) if length else b""
                if urlparse(self.path).path.rstrip("/") != "/mcp":
                    return self._send(404, {"error": "the endpoint is /mcp"})
                if not self._allowed():
                    return self._send(401, {"error": "wrong or missing token - copy it "
                                            "from PyCmd's MCP tab"},
                                      {"WWW-Authenticate": "Bearer"})
                try:
                    message = json.loads(body or b"null")
                except ValueError:
                    return self._send(400, _error(None, -32700, "that was not JSON"))
                reply = handle(server.registry, message)
                if reply is None:
                    return self._send(202)
                headers = {}
                if isinstance(message, dict) and message.get("method") == "initialize":
                    headers["Mcp-Session-Id"] = secrets.token_hex(16)
                self._send(200, reply, headers)

        try:
            self.httpd = ThreadingHTTPServer((host, self.port), Handler)
        except OSError as error:
            self.httpd = None
            return {"ok": False, "error": f"port {self.port} is busy or not allowed: {error}"}
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, name="pycmd-mcp",
                         daemon=True).start()
        return {"ok": True, "url": f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}"
                                   f":{self.port}/mcp"}

    def stop(self):
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:  # noqa: BLE001
                pass
            self.httpd = None


def new_token() -> str:
    return "pycmd_" + secrets.token_urlsafe(24)


def client_setups(url: str, token: str) -> list:
    """Copy-paste set-up for the AI apps people use, newest spellings."""
    auth = {"Authorization": f"Bearer {token}"}
    js = lambda value: json.dumps(value, indent=2)  # noqa: E731
    return [
        {"app": "Claude Code", "where": "a terminal",
         "text": f'claude mcp add --transport http pycmd {url} --header '
                 f'"Authorization: Bearer {token}"'},
        {"app": "Claude Desktop", "where": "Settings > Developer > Edit Config "
         "(claude_desktop_config.json), needs Node.js",
         "text": js({"mcpServers": {"pycmd": {"command": "npx", "args": [
             "-y", "mcp-remote", url, "--header", f"Authorization: Bearer {token}"]}}})},
        {"app": "Antigravity", "where": "Agent panel > ... > MCP Servers > Manage > "
         "View raw config (mcp_config.json)",
         "text": js({"mcpServers": {"pycmd": {"serverUrl": url, "headers": auth}}})},
        {"app": "Cursor", "where": "~/.cursor/mcp.json",
         "text": js({"mcpServers": {"pycmd": {"url": url, "headers": auth}}})},
        {"app": "VS Code (Copilot)", "where": ".vscode/mcp.json, or MCP: Add Server",
         "text": js({"servers": {"pycmd": {"type": "http", "url": url, "headers": auth}}})},
        {"app": "Windsurf", "where": "~/.codeium/windsurf/mcp_config.json",
         "text": js({"mcpServers": {"pycmd": {"serverUrl": url, "headers": auth}}})},
        {"app": "Gemini CLI", "where": "~/.gemini/settings.json",
         "text": js({"mcpServers": {"pycmd": {"httpUrl": url, "headers": auth}}})},
        {"app": "Codex CLI", "where": "~/.codex/config.toml",
         "text": f'[mcp_servers.pycmd]\nurl = "{url}"\n'
                 f'http_headers = {{ Authorization = "Bearer {token}" }}'},
        {"app": "Any other app", "where": "anything that speaks MCP over HTTP",
         "text": f"URL:    {url}\nHeader: Authorization: Bearer {token}"},
    ]
