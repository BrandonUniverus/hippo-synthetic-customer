import os
import shutil
import tempfile
import unittest
from pathlib import Path

from services.sources.generation import source_fingerprint

ROOT = Path(__file__).resolve().parents[3]


class SourceIdentityTests(unittest.TestCase):
    def test_content_change_is_detected_even_when_mtime_and_length_do_not_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in ("data/scenarios/demo-university-v1.yaml", "implementation/stage-2-hierarchy/04-points.yaml", "implementation/stage-3-gateways-and-data/02-gateways.yaml", "documents/intake-package/sample-data/acquisuite/expected-results.json"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            path = root / "data/scenarios/demo-university-v1.yaml"
            first = source_fingerprint(root)
            self.assertEqual(first, source_fingerprint(root))
            original = path.stat()
            raw = path.read_bytes()
            self.assertIn(b"104729", raw)
            path.write_bytes(raw.replace(b"104729", b"104728", 1))
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertEqual(original.st_size, path.stat().st_size)
            self.assertNotEqual(first, source_fingerprint(root))


if __name__ == "__main__":
    unittest.main()
