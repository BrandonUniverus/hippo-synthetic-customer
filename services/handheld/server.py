"""Small local HTTP service following identity/configuration/server.py's stdlib pattern."""
import base64
import json
import mimetypes
import os
import re
import sqlite3
from decimal import InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import READERS, json_bytes, validate_binding
from .fixtures import demo
from .store import Conflict, Store, source_identity

ROOT = Path(__file__).resolve().parents[2]
# Not every platform's MIME table knows WOFF2; the Northlake fonts are served as fonts.
mimetypes.add_type("font/woff2", ".woff2")


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state, source_root, *, source_override=None):
        self.store = Store(state)
        self.source_root = source_root
        self.source_override = source_override
        super().__init__(address, Handler)

    def source(self):
        return self.source_override or source_identity(self.source_root)

    def targets(self):
        path = Path(os.environ.get("NORTHLAKE_HANDHELD_TARGETS", str(self.store.root / "targets.json")))
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, media="application/json", *, filename=None):
        if not isinstance(data, bytes):
            data = json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path in {"/api/status", "/health/ready"}:
                return self.send(200, {"source": self.server.source(), "readers": READERS,
                                       "targets": [{"id": key, "enabled": item.get("enabled") is True,
                                                    "environment_id": item.get("environment_id"), "gateway_profile": item.get("gateway_profile"),
                                                    "fixture_only": item.get("fixture_only") is True} for key, item in self.server.targets().items()]})
            if path == "/api/rounds":
                return self.send(200, self.server.store.list())
            if match := re.fullmatch(r"/api/rounds/([a-f0-9]{32})", path):
                return self.send(200, self.server.store.get(match[1]))
            if path == "/api/demo":
                raw, binding = demo(self.server.source())
                return self.send(200, {"export_base64": base64.b64encode(raw).decode(), "binding_base64": base64.b64encode(json_bytes(binding)).decode()})
            if path == "/catalog.json":
                return self.send(200, self.server.store.catalog())
            if match := re.fullmatch(r"/download/([a-f0-9]{32})", path):
                data, filename = self.server.store.download(match[1])
                return self.send(200, data, "application/octet-stream", filename=filename)
            if path.startswith("/releases/"):
                # Orphan files from interrupted publication are never HTTP eligible.
                catalog = self.server.store.catalog()
                for artifact in catalog["artifacts"]:
                    if path == "/" + artifact["url"]:
                        key = artifact["metadata"]["artifact"]
                        data, filename = self.server.store.download(key)
                        return self.send(200, data, "application/octet-stream", filename=filename)
                    if path == "/releases/handheld-" + artifact["metadata"]["artifact"] + "/manifest.json":
                        return self.send(200, (self.server.store.root / "public" / path[1:]).read_bytes())
            static = {"/": ROOT / "services/handheld/web/index.html", "/app.js": ROOT / "services/handheld/web/app.js",
                      "/model.js": ROOT / "services/handheld/web/model.js", "/handheld.css": ROOT / "services/handheld/web/handheld.css"}
            file = static.get(path)
            if path.startswith("/branding/"):
                candidate = (ROOT / "identity" / path.lstrip("/")).resolve()
                if candidate.is_relative_to((ROOT / "identity/branding").resolve()):
                    file = candidate
            if path.startswith("/brands/"):
                # branding/brand.css imports ../brands/northlake/{fonts,tokens}.css.
                candidate = (ROOT / path.lstrip("/")).resolve()
                if candidate.is_relative_to((ROOT / "brands").resolve()):
                    file = candidate
            if file and file.is_file():
                return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            self.send(404, {"error": "Not found"})
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
            self.send(503 if path in {"/api/status", "/health/ready"} else 400, {"error": str(error)})

    def do_POST(self):
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send(415, {"error": "JSON is required"})
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + self.headers.get("Host", ""), "https://" + self.headers.get("Host", "")}:
                return self.send(403, {"error": "Cross-origin writes are not allowed"})
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 6_000_000:
                return self.send(413, {"error": "Request must be between 1 byte and 6 MB"})
            body = json.loads(self.rfile.read(size))
            path = urlsplit(self.path).path
            if path in {"/api/preflight", "/api/rounds"}:
                raw = base64.b64decode(body["export_base64"], validate=True)
                binding_raw = base64.b64decode(body["binding_base64"], validate=True)
                source = self.server.source()
                if path == "/api/preflight":
                    binding = json.loads(binding_raw)
                    return self.send(200, {"channels": validate_binding(raw, binding, source), "source": source,
                                           "environment_id": binding["environment_id"], "database": binding["database"]})
                return self.send(201, self.server.store.create(raw, binding_raw, source, body["route"]))
            if match := re.fullmatch(r"/api/rounds/([a-f0-9]{32})/(save|finalize|correction|follow-up|deliver)", path):
                key, action = match.groups()
                if action == "save":
                    result = self.server.store.edit(key, body["revision"], body["observation"])
                elif action == "finalize":
                    result = self.server.store.finalize(key, body["revision"])
                elif action == "deliver":
                    if not isinstance(body.get("replay", False), bool):
                        raise ValueError("Replay must be an explicit boolean")
                    result = self.server.store.deliver(key, self.server.targets(), body["target"], body.get("replay", False))
                else:
                    result = self.server.store.linked(key, body["revision"], action)
                return self.send(200, result)
            self.send(404, {"error": "Not found"})
        except Conflict as error:
            self.send(409, {"error": str(error)})
        except (ValueError, KeyError, TypeError, InvalidOperation, OSError) as error:
            self.send(400, {"error": str(error)})

def run(state, source_root, host, port):
    with Server((host, port), state, source_root) as server:
        print(f"Northlake handheld listening on {host}:{port}", flush=True)
        server.serve_forever()
