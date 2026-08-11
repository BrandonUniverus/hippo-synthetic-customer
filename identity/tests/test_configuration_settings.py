from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from identity.configuration.settings import (
    ProviderSettings,
    SettingsDocument,
    SettingsValidationError,
    load_settings_document,
    write_settings_document,
)


class ConfigurationSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = {
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "IDENTITY_HTTPS_PORT": "8443",
            "EEMSUITE_APPLICATION_HOME_URL": "https://localdev.energyhippo.com/Hippo/",
            "EEMSUITE_OIDC_REDIRECT_URIS": (
                "https://localhost:7310/signin-oidc;"
                "https://localdev.energyhippo.com/Hippo/signin-oidc"
            ),
            "EEMSUITE_SAML_STANDARD_ACS_URLS": (
                "https://localhost:7310/saml/northlake-saml-standard/acs;"
                "https://localdev.energyhippo.com/Hippo/saml/northlake-saml-standard/acs"
            ),
            "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": (
                "https://localhost:7310/saml/northlake-saml-standard/logout;"
                "https://localdev.energyhippo.com/Hippo/saml/northlake-saml-standard/logout"
            ),
        }

    def test_defaults_create_a_redacted_provider_preview(self) -> None:
        settings = ProviderSettings.from_environment(self.environment)

        preview = settings.endpoint_preview()

        self.assertEqual("northlake", settings.realm_key)
        self.assertEqual(
            "https://localhost:8443/realms/northlake/.well-known/openid-configuration",
            preview["oidc"]["discovery"],
        )
        self.assertEqual(
            "https://localhost:8443/realms/northlake/protocol/saml/descriptor",
            preview["saml"]["metadata"],
        )
        serialized = json.dumps(preview)
        self.assertNotIn("clientSecret", serialized)
        self.assertNotIn("password", serialized.lower())

    def test_values_generate_the_existing_environment_contract(self) -> None:
        settings = ProviderSettings.from_environment(self.environment)

        overlay = settings.to_environment_overlay()

        self.assertEqual("localhost", overlay["IDENTITY_HOST"])
        self.assertEqual("8443", overlay["IDENTITY_HTTPS_PORT"])
        self.assertEqual("true", overlay["NORTHLAKE_ENABLE_OIDC"])
        self.assertEqual("true", overlay["NORTHLAKE_ENABLE_SAML"])
        self.assertEqual("Standard", overlay["EEMSUITE_SAML_PROFILES"])
        self.assertNotIn("KEYCLOAK_ADMIN_PASSWORD", overlay)

    def test_invalid_values_report_field_errors(self) -> None:
        values = ProviderSettings.from_environment(self.environment).to_values()
        values.update(
            {
                "realmKey": "master",
                "publicBaseUrl": "https://localhost:9443/path",
                "httpsPort": 8443,
                "enableOidc": False,
                "enableSaml": False,
            }
        )

        with self.assertRaises(SettingsValidationError) as raised:
            ProviderSettings.from_values(values)

        self.assertIn("realmKey", raised.exception.errors)
        self.assertIn("publicBaseUrl", raised.exception.errors)
        self.assertIn("_form", raised.exception.errors)

    def test_settings_document_round_trips_without_secrets(self) -> None:
        settings = ProviderSettings.from_environment(self.environment)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "configuration.json"
            write_settings_document(
                path,
                SettingsDocument(
                    settings=settings,
                    applied_realm_key="northlake",
                    pending_apply=True,
                ),
            )

            loaded = load_settings_document(path, self.environment)
            serialized = path.read_text(encoding="utf-8")

        self.assertEqual(settings, loaded.settings)
        self.assertEqual("northlake", loaded.applied_realm_key)
        self.assertTrue(loaded.pending_apply)
        self.assertNotIn("clientSecret", serialized)
        self.assertNotIn("KEYCLOAK_ADMIN", serialized)


if __name__ == "__main__":
    unittest.main()
