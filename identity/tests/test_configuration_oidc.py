from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from identity.configuration.oidc import (
    OidcSettings,
    OidcSettingsDocument,
    OidcValidationError,
    load_oidc_settings_document,
    write_oidc_settings_document,
)
from identity.configuration.settings import ProviderSettings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OIDC_MODEL_PATH = REPOSITORY_ROOT / "identity" / "configuration" / "oidc.py"


class OidcSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = {
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "IDENTITY_HTTPS_PORT": "8443",
            "NORTHLAKE_PROVIDER_DISPLAY_NAME": "Northlake Synthetic Identity",
            "NORTHLAKE_REALM_KEY": "northlake",
            "NORTHLAKE_ENABLE_OIDC": "true",
            "NORTHLAKE_ENABLE_SAML": "true",
            "EEMSUITE_OIDC_REDIRECT_URIS": "https://localhost:7310/signin-oidc",
        }

    def test_environment_defaults_are_the_recommended_bounded_profiles(self) -> None:
        settings = OidcSettings.from_environment(self.environment)

        self.assertEqual("Discovery", settings.configuration_mode)
        self.assertEqual("UseIfAvailable", settings.par_behavior)
        self.assertEqual("ClientSecretPost", settings.token_endpoint_auth_method)
        self.assertEqual(300, settings.access_token_lifetime_seconds)
        self.assertEqual("eemsuite-web", settings.modern_client_id)
        self.assertEqual(
            ("openid", "profile", "email", "northlake"),
            settings.modern_scopes,
        )
        self.assertTrue(settings.modern_consent_required)
        self.assertTrue(settings.legacy_enabled)

    def test_invalid_values_return_field_level_errors(self) -> None:
        values = OidcSettings.from_environment(self.environment).to_values()
        values.update(
            {
                "configurationMode": "Magic",
                "parBehavior": "Sometimes",
                "tokenEndpointAuthMethod": "None",
                "accessTokenLifetimeSeconds": 59,
                "modernClientId": "bad id",
                "modernRedirectUris": ["http://localhost/callback"],
                "modernScopes": ["profile"],
            }
        )

        with self.assertRaises(OidcValidationError) as context:
            OidcSettings.from_values(values)

        self.assertEqual(
            {
                "configurationMode",
                "parBehavior",
                "tokenEndpointAuthMethod",
                "accessTokenLifetimeSeconds",
                "modernClientId",
                "modernRedirectUris",
                "modernScopes",
            },
            set(context.exception.errors),
        )

    def test_document_round_trip_preserves_values(self) -> None:
        settings = OidcSettings.from_environment(self.environment)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "oidc.json"
            write_oidc_settings_document(path, OidcSettingsDocument(settings=settings))
            loaded = load_oidc_settings_document(path, {})

            self.assertEqual(settings, loaded.settings)
            self.assertIsNotNone(loaded.updated_at_utc)

    def test_direct_cli_emits_the_saved_environment_overlay_from_any_working_directory(self) -> None:
        settings = OidcSettings.from_environment(self.environment)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            path = temporary / "oidc.json"
            write_oidc_settings_document(path, OidcSettingsDocument(settings=settings))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(OIDC_MODEL_PATH),
                    "--settings-file",
                    str(path),
                    "--print-environment-overlay",
                ],
                cwd=temporary,
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            overlay = json.loads(completed.stdout)
            self.assertEqual("Discovery", overlay["NORTHLAKE_OIDC_CONFIGURATION_MODE"])
            self.assertEqual("eemsuite-web", overlay["NORTHLAKE_OIDC_MODERN_CLIENT_ID"])

    def test_all_eem_configuration_modes_have_secret_free_copy_values(self) -> None:
        provider = ProviderSettings.from_environment(self.environment)
        baseline = OidcSettings.from_environment(self.environment).to_values()

        for mode in ("Authority", "Discovery", "Static"):
            with self.subTest(mode=mode):
                values = dict(baseline)
                values["configurationMode"] = mode
                preview = OidcSettings.from_values(values).preview(provider)
                serialized = json.dumps(preview)
                modern = preview["profiles"]["modern"]
                legacy = preview["profiles"]["historicalLegacy"]

                self.assertEqual(mode, modern["configurationMode"])
                self.assertNotIn("secret-value", serialized)
                self.assertNotIn("clientSecret", modern)
                self.assertFalse(modern["historicalExistingProviderOnly"])
                self.assertTrue(legacy["historicalExistingProviderOnly"])
                if mode == "Authority":
                    self.assertEqual(preview["issuer"], modern["metadataAddress"])
                elif mode == "Discovery":
                    self.assertEqual(
                        preview["discoveryEndpoint"],
                        modern["metadataAddress"],
                    )
                else:
                    self.assertIsNone(modern["metadataAddress"])
                    self.assertEqual(
                        preview["issuer"],
                        modern["issuer"],
                    )


if __name__ == "__main__":
    unittest.main()
