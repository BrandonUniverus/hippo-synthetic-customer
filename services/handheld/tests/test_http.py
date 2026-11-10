import base64
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from services.handheld.contracts import digest, json_bytes
from services.handheld.fixtures import FIXTURE_SOURCE, demo
from services.handheld.server import Server
from services.handheld.remote import sync
from services.sources.delivery import deliver


class HttpTests(unittest.TestCase):
    def test_round_api_original_bytes_restart_eligibility_and_http_sync(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state"
            server = Server(("127.0.0.1", 0), state, None, source_override=FIXTURE_SOURCE)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_port}"
            def call(path, body=None, origin=None):
                headers = {"Content-Type": "application/json"}
                if origin:
                    headers["Origin"] = origin
                with urlopen(Request(base + path, json_bytes(body) if body is not None else None, headers), timeout=5) as response:
                    return json.load(response)
            try:
                raw, binding = demo()
                payload = {"export_base64": base64.b64encode(raw).decode(), "binding_base64": base64.b64encode(json_bytes(binding)).decode(), "route": "CRBMW"}
                self.assertEqual(2, len(call("/api/preflight", payload)["channels"]))
                with self.assertRaises(HTTPError) as failure:
                    call("/api/rounds", payload, "https://unrelated.example")
                self.assertEqual(403, failure.exception.code)
                doc = call("/api/rounds", payload)
                self.assertEqual([], call("/catalog.json")["artifacts"])
                doc = call(f"/api/rounds/{doc['id']}/save", {"revision": 1, "observation": {"action": "read", "value": 1125,
                           "reader": "NLR002", "observed_at": "2026-10-15T12:00:00-07:00", "note": "Access clear"}})
                with self.assertRaises(HTTPError) as failure:
                    call(f"/api/rounds/{doc['id']}/finalize", {"revision": 1})
                self.assertEqual(409, failure.exception.code)
                doc = call(f"/api/rounds/{doc['id']}/finalize", {"revision": 2})
                record = call("/catalog.json")["artifacts"][0]
                self.assertEqual(doc["artifact"], record)
                with urlopen(base + "/download/" + doc["id"], timeout=5) as response:
                    downloaded = response.read()
                self.assertEqual(record["sha256"], digest(downloaded))
                local, http = Path(folder) / "local/Input", Path(folder) / "http/Input"
                deliver([record], local, state=state)
                deliver([record], http, url=base)
                self.assertEqual(downloaded, (local / record["path"]).read_bytes())
                self.assertEqual(downloaded, (http / record["path"]).read_bytes())
                targets = {"fixture-only": {"enabled": True, "fixture_only": True, "environment_id": "fixture-only",
                                            "gateway_profile": doc["channel"]["gateway_profile"], "destination": str(http)}}
                (http / record["path"]).unlink()
                self.assertEqual("previously_delivered", sync(base, doc["id"], targets, "fixture-only")["files"][0]["status"])
                self.assertFalse((http / record["path"]).exists())
                sync(base, doc["id"], targets, "fixture-only", replay=True)
                self.assertEqual(downloaded, (http / record["path"]).read_bytes())
                targets["fixture-only"]["fixture_only"] = False
                with self.assertRaises(ValueError):
                    sync(base, doc["id"], targets, "fixture-only")
                # Public paths only expose a committed artifact, never an orphan/partial.
                orphan = state / "public/releases/orphan/files/test.imp"
                orphan.parent.mkdir(parents=True)
                orphan.write_bytes(b"incomplete")
                with self.assertRaises(HTTPError) as failure:
                    urlopen(base + "/releases/orphan/files/test.imp", timeout=5)
                self.assertEqual(404, failure.exception.code)
                with server.store.connection() as db:
                    saved = db.execute("SELECT export FROM imports").fetchone()[0]
                self.assertEqual(raw, saved)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
