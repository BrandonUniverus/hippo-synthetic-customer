from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from identity.configuration.saml import (
    SamlSettings,
    SamlSettingsDocument,
    SamlValidationError,
    describe_public_certificate,
    load_saml_settings_document,
    parse_public_certificate_base64,
    read_public_certificate_summary,
    validate_public_certificate,
    write_saml_settings_document,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAML_MODEL_PATH = REPOSITORY_ROOT / "identity" / "configuration" / "saml.py"


def create_public_certificate(
    *,
    not_valid_before: datetime | None = None,
    not_valid_after: datetime | None = None,
) -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Northlake Test SP")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before or now - timedelta(minutes=1))
        .not_valid_after(not_valid_after or now + timedelta(days=30))
        .sign(private_key, hashes.SHA256())
    )
    return (
        certificate.public_bytes(serialization.Encoding.DER),
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


def create_expired_public_certificate() -> tuple[bytes, bytes]:
    now = datetime.now(UTC)
    return create_public_certificate(
        not_valid_before=now - timedelta(days=400),
        not_valid_after=now - timedelta(days=35),
    )


class SamlSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = {
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "NORTHLAKE_PROVIDER_DISPLAY_NAME": "Northlake Synthetic Identity",
            "NORTHLAKE_REALM_KEY": "northlake",
            "EEMSUITE_SAML_PROFILES": "Standard",
            "EEMSUITE_SAML_STANDARD_ENTITY_ID": "urn:energyhippo:eemsuite-web:saml:standard",
            "EEMSUITE_SAML_STANDARD_ACS_URLS": "https://localhost:7310/saml/northlake-saml-standard/acs",
            "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": "https://localhost:7310/saml/northlake-saml-standard/logout",
        }

    def test_environment_defaults_are_bounded_standard_and_saml2int_profiles(self) -> None:
        settings = SamlSettings.from_environment(self.environment)

        self.assertTrue(settings.standard.enabled)
        self.assertFalse(settings.saml2int.enabled)
        self.assertEqual("PersistentNameId", settings.standard.subject_binding_kind)
        self.assertIn("groups", settings.standard.allowed_claims)
        self.assertEqual(
            (
                "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified",
            ),
            settings.standard.allowed_authentication_context_class_references,
        )

    def test_callbacks_subject_binding_and_profile_identity_are_validated(self) -> None:
        values = SamlSettings.from_environment(self.environment).to_values()
        values.update(
            {
                "standardAssertionConsumerServiceUrls": ["https://localhost/wrong"],
                "standardSubjectBindingKind": "Attribute",
                "standardSubjectAttribute": "synthetic_user_id",
                "standardAllowedClaims": ["email"],
                "saml2IntEnabled": True,
                "saml2IntProviderKey": values["standardProviderKey"],
                "saml2IntEntityId": values["standardEntityId"],
                "saml2IntAssertionConsumerServiceUrls": [
                    "https://localhost:7310/saml/northlake-saml-standard/acs"
                ],
                "saml2IntLogoutServiceUrls": [
                    "https://localhost:7310/saml/northlake-saml-standard/logout"
                ],
            }
        )

        with self.assertRaises(SamlValidationError) as context:
            SamlSettings.from_values(values)

        self.assertEqual(
            {
                "standardAssertionConsumerServiceUrls",
                "standardSubjectAttribute",
                "saml2IntProviderKey",
                "saml2IntEntityId",
            },
            set(context.exception.errors),
        )

    def test_document_and_cli_round_trip_to_existing_environment_contract(self) -> None:
        settings = SamlSettings.from_environment(self.environment)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            settings_path = temporary / "saml.json"
            certificate_path = temporary / "certs" / "saml2int-sp-public.cer"
            write_saml_settings_document(
                settings_path,
                SamlSettingsDocument(settings=settings),
            )
            loaded = load_saml_settings_document(settings_path, {})
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SAML_MODEL_PATH),
                    "--settings-file",
                    str(settings_path),
                    "--certificate-file",
                    str(certificate_path),
                    "--print-environment-overlay",
                ],
                cwd=temporary,
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(settings, loaded.settings)
        self.assertEqual(0, completed.returncode, completed.stderr)
        overlay = json.loads(completed.stdout)
        self.assertEqual("Standard", overlay["EEMSUITE_SAML_PROFILES"])
        self.assertEqual(
            "northlake-saml-standard",
            overlay["NORTHLAKE_SAML_STANDARD_PROVIDER_KEY"],
        )

    def test_public_certificate_accepts_only_current_rsa_x509_without_private_key(self) -> None:
        certificate_der, private_key = create_public_certificate()
        parsed_der, summary = parse_public_certificate_base64(
            base64.b64encode(certificate_der).decode("ascii")
        )

        self.assertEqual(certificate_der, parsed_der)
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["valid"])
        self.assertEqual("RSA", summary["keyType"])
        with self.assertRaises(SamlValidationError):
            validate_public_certificate(private_key)

    def test_expired_stored_certificate_is_described_instead_of_rejected(self) -> None:
        expired_der, _ = create_expired_public_certificate()

        summary = describe_public_certificate(expired_der)

        self.assertTrue(summary["configured"])
        self.assertFalse(summary["valid"])
        self.assertIn("expired on", summary["reason"])
        self.assertIn(summary["notAfterUtc"], summary["reason"])
        self.assertIn("Northlake Test SP", summary["subject"])
        self.assertEqual(2048, summary["keySize"])
        with self.assertRaises(SamlValidationError):
            validate_public_certificate(expired_der)

    def test_unreadable_stored_certificate_is_described_without_leaking_material(self) -> None:
        _, private_key = create_public_certificate()

        corrupt = describe_public_certificate(b"not an X.509 certificate")
        stored_private_key = describe_public_certificate(private_key)

        for summary in (corrupt, stored_private_key):
            self.assertTrue(summary["configured"])
            self.assertFalse(summary["valid"])
            self.assertNotIn("sha256Thumbprint", summary)
            self.assertIn("Upload EnergyHippo's current public certificate", summary["reason"])
        self.assertNotIn("BEGIN PRIVATE KEY", stored_private_key["reason"])

    def test_stored_certificate_summary_reads_the_saved_file_or_reports_none(self) -> None:
        current_der, _ = create_public_certificate()
        expired_der, _ = create_expired_public_certificate()
        with tempfile.TemporaryDirectory() as temporary_directory:
            certificate_path = Path(temporary_directory) / "certs" / "saml2int-sp-public.cer"
            missing = read_public_certificate_summary(certificate_path)
            certificate_path.parent.mkdir(parents=True)
            certificate_path.write_bytes(current_der)
            current = read_public_certificate_summary(certificate_path)
            certificate_path.write_bytes(expired_der)
            expired = read_public_certificate_summary(certificate_path)

        self.assertIsNone(missing)
        self.assertTrue(current["valid"])
        self.assertNotIn("reason", current)
        self.assertFalse(expired["valid"])

    def test_preview_exposes_exact_eem_values_without_certificate_material(self) -> None:
        values = SamlSettings.from_environment(self.environment).to_values()
        values["standardSubjectBindingKind"] = "Attribute"
        values["standardSubjectAttribute"] = "synthetic_user_id"
        values["saml2IntEnabled"] = True
        settings = SamlSettings.from_values(values)
        preview = settings.preview(
            public_base_url="https://localhost:8443",
            realm_key="northlake",
            provider_display_name="Northlake Synthetic Identity",
            certificate=None,
        )

        standard = preview["profiles"]["standard"]
        self.assertEqual("/saml/northlake-saml-standard/acs", standard["CallbackPath"])
        self.assertEqual("Attribute", standard["SubjectBindingKind"])
        self.assertEqual("synthetic_user_id", standard["SubjectAttribute"])
        self.assertTrue(
            preview["profiles"]["saml2Int"]["ServiceProviderCredential"][
                "requiredForSigning"
            ]
        )
        self.assertNotIn("BEGIN CERTIFICATE", json.dumps(preview))
        self.assertNotIn("BEGIN PRIVATE KEY", json.dumps(preview))


if __name__ == "__main__":
    unittest.main()
