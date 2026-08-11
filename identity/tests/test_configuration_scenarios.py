from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from identity.configuration.scenarios import (
    SCENARIO_PRESETS,
    ScenarioSettings,
    ScenarioSettingsDocument,
    ScenarioValidationError,
    generate_scenario_realm,
    load_scenario_document,
    preset_settings,
    scenario_diff,
    write_scenario_document,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "security" / "northlake-eem-security-v1.yaml"


class ScenarioSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = {
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "IDENTITY_HOST": "localhost",
            "IDENTITY_HTTPS_PORT": "8443",
            "KEYCLOAK_ADMIN": "admin",
            "KEYCLOAK_ADMIN_PASSWORD": "admin-secret-value-123",
            "KEYCLOAK_DB_PASSWORD": "database-secret-value-123",
            "EEMSUITE_OIDC_CLIENT_SECRET": "modern-secret-value-123",
            "EEMSUITE_OIDC_LEGACY_CLIENT_SECRET": "legacy-secret-value-123",
            "NORTHLAKE_CUSTOMER_CLIENT_SECRET": "customer-secret-value-123",
            "SYNTHETIC_USER_PASSWORD": "A1!synthetic-user-password",
            "EEMSUITE_APPLICATION_HOME_URL": "https://localhost/Hippo/",
            "EEMSUITE_OIDC_REDIRECT_URIS": "https://localhost:7310/signin-oidc",
        }

    def _generate_pair(self, settings: ScenarioSettings) -> tuple[dict, dict, dict, dict]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            realm_a, connection_a = generate_scenario_realm(
                settings,
                "labA",
                self.environment,
                MANIFEST_PATH,
                temporary / "realm-a.json",
                temporary / "connection-a.json",
            )
            realm_b, connection_b = generate_scenario_realm(
                settings,
                "labB",
                self.environment,
                MANIFEST_PATH,
                temporary / "realm-b.json",
                temporary / "connection-b.json",
            )
        return realm_a, connection_a, realm_b, connection_b

    def test_named_presets_are_bounded_and_export_no_secret_values(self) -> None:
        for preset in SCENARIO_PRESETS:
            settings = preset_settings(preset, self.environment)
            exported = settings.redacted_export()
            serialized = json.dumps(exported)

            self.assertEqual(preset, settings.preset)
            self.assertEqual({"labA", "labB"}, set(exported["preview"]["realms"]))
            self.assertTrue(exported["preview"]["assertions"]["distinctOidcIssuers"])
            self.assertTrue(exported["preview"]["assertions"]["distinctSamlIdpEntities"])
            self.assertTrue(exported["redacted"])
            self.assertNotIn(self.environment["EEMSUITE_OIDC_CLIENT_SECRET"], serialized)
            self.assertNotIn(self.environment["SYNTHETIC_USER_PASSWORD"], serialized)
            self.assertNotIn("clientSecret\"", serialized)

    def test_shared_subject_preset_generates_equal_subjects_under_distinct_issuers(self) -> None:
        settings = preset_settings("SharedSubject", self.environment)
        realm_a, connection_a, realm_b, connection_b = self._generate_pair(settings)

        self.assertEqual("northlake-lab-a", realm_a["realm"])
        self.assertEqual("northlake-lab-b", realm_b["realm"])
        self.assertNotEqual(connection_a["issuer"], connection_b["issuer"])
        self.assertNotEqual(connection_a["samlMetadataEndpoint"], connection_b["samlMetadataEndpoint"])
        self.assertEqual(
            connection_a["testUsers"]["active"]["subject"],
            connection_b["testUsers"]["active"]["subject"],
        )
        self.assertEqual(
            connection_a["testUsers"]["active"]["samlNameId"],
            connection_b["testUsers"]["active"]["samlNameId"],
        )
        self.assertNotEqual(realm_a["users"][0]["id"], realm_b["users"][0]["id"])
        self.assertEqual(
            realm_a["users"][0]["attributes"]["northlake_oidc_subject"],
            realm_b["users"][0]["attributes"]["northlake_oidc_subject"],
        )
        self.assertNotEqual(
            connection_a["clients"]["modern"]["providerKey"],
            connection_b["clients"]["modern"]["providerKey"],
        )
        self.assertEqual(
            {"customer", "probe"},
            set(connection_a["customerSite"]["clients"]),
        )
        self.assertNotEqual(
            connection_a["customerSite"]["clients"]["customer"]["clientId"],
            connection_b["customerSite"]["clients"]["customer"]["clientId"],
        )
        customer_a = {
            client["clientId"]: client
            for client in realm_a["clients"]
            if client["clientId"].startswith("northlake-")
        }
        self.assertFalse(customer_a["northlake-customer-northlake-lab-a"]["consentRequired"])
        self.assertTrue(customer_a["northlake-probe-northlake-lab-a"]["consentRequired"])
        self.assertEqual(
            "S256",
            customer_a["northlake-probe-northlake-lab-a"]["attributes"][
                "pkce.code.challenge.method"
            ],
        )

    def test_isolation_and_claim_drift_change_only_the_bounded_dimensions(self) -> None:
        isolation = preset_settings("IsolationBaseline", self.environment)
        _, isolation_a, _, isolation_b = self._generate_pair(isolation)
        self.assertNotEqual(
            isolation_a["testUsers"]["active"]["subject"],
            isolation_b["testUsers"]["active"]["subject"],
        )

        drift = preset_settings("ClaimDrift", self.environment)
        realm_a, connection_a, realm_b, connection_b = self._generate_pair(drift)
        scope_a = next(scope for scope in realm_a["clientScopes"] if scope["name"] == "northlake")
        scope_b = next(scope for scope in realm_b["clientScopes"] if scope["name"] == "northlake")
        self.assertEqual(7, len(scope_a["protocolMappers"]))
        self.assertEqual(2, len(scope_b["protocolMappers"]))
        self.assertEqual(
            7,
            len(connection_a["clients"]["modern"]["allowedClaims"]),
        )
        self.assertEqual(
            ["synthetic_user_id", "primary_company_id"],
            connection_b["clients"]["modern"]["allowedClaims"],
        )
        saml_b = next(client for client in realm_b["clients"] if client["protocol"] == "saml")
        self.assertEqual(
            set(connection_b["clients"]["saml"]["allowedClaims"]),
            {mapper["name"] for mapper in saml_b["protocolMappers"]},
        )

    def test_arbitrary_fields_and_identity_collisions_are_rejected(self) -> None:
        values = preset_settings("SharedSubject", self.environment).to_values()
        values["rawKeycloakJson"] = {"clients": []}
        with self.assertRaises(ScenarioValidationError) as unknown_error:
            ScenarioSettings.from_values(values)
        self.assertIn("_form", unknown_error.exception.errors)

        values = preset_settings("SharedSubject", self.environment).to_values()
        values["realms"]["labB"]["realmKey"] = values["realms"]["labA"]["realmKey"]
        values["realms"]["labB"]["oidcProviderKey"] = values["realms"]["labA"][
            "oidcProviderKey"
        ]
        with self.assertRaises(ScenarioValidationError) as collision_error:
            ScenarioSettings.from_values(values)
        self.assertIn("realms.labB.realmKey", collision_error.exception.errors)
        self.assertIn("realms.labB.oidcProviderKey", collision_error.exception.errors)

    def test_clone_diff_and_document_round_trip_preserve_target_identity(self) -> None:
        settings = preset_settings("ClaimDrift", self.environment)
        cloned = settings.clone("labA", "labB")
        differences = scenario_diff(settings, cloned)

        self.assertEqual("Full", cloned.realms["labB"].claim_shape)
        self.assertEqual(
            settings.realms["labB"].realm_key,
            cloned.realms["labB"].realm_key,
        )
        self.assertEqual(
            settings.realms["labB"].saml_provider_key,
            cloned.realms["labB"].saml_provider_key,
        )
        self.assertTrue(any(item["path"] == "realms.labB.claimShape" for item in differences))

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "scenarios.json"
            write_scenario_document(
                path,
                ScenarioSettingsDocument(
                    settings=cloned,
                    applied_realm_keys={"labA": "northlake-lab-a", "labB": None},
                ),
            )
            loaded = load_scenario_document(path, self.environment)
        self.assertEqual(cloned.to_values(), loaded.settings.to_values())
        self.assertEqual("northlake-lab-a", loaded.applied_realm_keys["labA"])

    def test_cli_runs_outside_the_repository_working_directory(self) -> None:
        settings = preset_settings("SharedSubject", self.environment)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            settings_path = temporary / "scenarios.json"
            environment_path = temporary / ".env"
            write_scenario_document(
                settings_path,
                ScenarioSettingsDocument(settings=settings, applied_realm_keys={}),
            )
            environment_path.write_text(
                "\n".join(f"{key}={value}" for key, value in self.environment.items()) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "identity" / "configuration" / "scenarios.py"),
                    "--settings-file",
                    str(settings_path),
                    "--env-file",
                    str(environment_path),
                    "--manifest",
                    str(MANIFEST_PATH),
                    "--realm-output-directory",
                    str(temporary / "import"),
                    "--connection-output-directory",
                    str(temporary / "connections"),
                ],
                cwd=temporary,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((temporary / "import" / "northlake-laba-realm.json").is_file())
            self.assertTrue((temporary / "import" / "northlake-labb-realm.json").is_file())
            self.assertTrue((temporary / "connections" / "labA" / "connection.json").is_file())
            self.assertTrue((temporary / "connections" / "labB" / "connection.json").is_file())


if __name__ == "__main__":
    unittest.main()
