from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509

from identity.configuration.saml import validate_public_certificate
from identity.scripts.create_saml2int_dev_certificate import create_development_certificate
from identity.tests.test_configuration_saml import create_expired_public_certificate


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    REPOSITORY_ROOT / "identity" / "scripts" / "create_saml2int_dev_certificate.py"
)


def run_generator(certificate_path: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            "--certificate-file",
            str(certificate_path),
            *arguments,
        ],
        capture_output=True,
        check=False,
        text=True,
    )


class Saml2IntDevCertificateTests(unittest.TestCase):
    def test_generated_certificate_is_accepted_for_the_requested_lifetime(self) -> None:
        der = create_development_certificate(365)

        _, summary = validate_public_certificate(der)
        certificate = x509.load_der_x509_certificate(der)
        lifetime = certificate.not_valid_after_utc - certificate.not_valid_before_utc

        self.assertTrue(summary["valid"])
        self.assertEqual("RSA", summary["keyType"])
        self.assertEqual(2048, summary["keySize"])
        self.assertEqual(365, lifetime.days)
        self.assertGreater(
            certificate.not_valid_after_utc,
            datetime.now(UTC) + timedelta(days=364),
        )

    def test_generated_certificate_carries_no_private_key_material(self) -> None:
        der = create_development_certificate(30)

        self.assertNotIn(b"PRIVATE KEY", der.upper())
        self.assertNotIn(b"BEGIN", der.upper())

    def test_cli_replaces_an_expired_certificate_but_protects_a_valid_one(self) -> None:
        expired_der, _ = create_expired_public_certificate()
        with tempfile.TemporaryDirectory() as temporary_directory:
            certificate_path = Path(temporary_directory) / "certs" / "saml2int-sp-public.cer"
            certificate_path.parent.mkdir(parents=True)
            certificate_path.write_bytes(expired_der)

            replaced = run_generator(certificate_path, "--days", "365")
            after_replacement = certificate_path.read_bytes()
            protected = run_generator(certificate_path, "--days", "365")
            unchanged = certificate_path.read_bytes()
            forced = run_generator(certificate_path, "--days", "365", "--force")

        self.assertEqual(0, replaced.returncode, replaced.stderr)
        self.assertNotEqual(expired_der, after_replacement)
        self.assertTrue(validate_public_certificate(after_replacement)[1]["valid"])

        self.assertEqual(1, protected.returncode)
        self.assertIn("--force", protected.stderr)
        self.assertEqual(after_replacement, unchanged)

        self.assertEqual(0, forced.returncode, forced.stderr)

    def test_cli_rejects_an_unreasonable_lifetime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            certificate_path = Path(temporary_directory) / "saml2int-sp-public.cer"
            completed = run_generator(certificate_path, "--days", "0")

        self.assertEqual(1, completed.returncode)
        self.assertFalse(certificate_path.exists())


if __name__ == "__main__":
    unittest.main()
