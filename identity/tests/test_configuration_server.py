from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request

from identity.configuration.server import ConfigurationApplication, create_server
from identity.configuration.settings import ProviderSettings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeKeycloakAdminClient:
    def __init__(self) -> None:
        self.replacements: list[tuple[str, str | None]] = []
        self.health_checks: list[str] = []

    def replace_realm(self, realm: dict, previous_realm_key: str | None) -> None:
        self.replacements.append((realm["realm"], previous_realm_key))

    def wait_until_healthy(self, settings: ProviderSettings) -> None:
        self.health_checks.append(settings.realm_key)


class ConfigurationServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.runtime_directory = Path(self.temporary_directory.name) / "runtime"
        self.environment = {
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "IDENTITY_HTTPS_PORT": "8443",
            "IDENTITY_HOST": "localhost",
            "KEYCLOAK_ADMIN": "admin",
            "KEYCLOAK_ADMIN_PASSWORD": "admin-secret-value-123",
            "KEYCLOAK_DB_PASSWORD": "database-secret-value-123",
            "EEMSUITE_OIDC_CLIENT_SECRET": "modern-secret-value-123",
            "EEMSUITE_OIDC_LEGACY_CLIENT_SECRET": "legacy-secret-value-123",
            "SYNTHETIC_USER_PASSWORD": "A1!synthetic-user-password",
            "EEMSUITE_APPLICATION_HOME_URL": "https://localdev.energyhippo.com/Hippo/",
            "EEMSUITE_OIDC_REDIRECT_URIS": "https://localhost:7310/signin-oidc",
            "EEMSUITE_SAML_PROFILES": "Standard",
            "EEMSUITE_SAML_STANDARD_ENTITY_ID": (
                "urn:energyhippo:eemsuite-web:saml:standard"
            ),
            "EEMSUITE_SAML_STANDARD_ACS_URLS": (
                "https://localhost:7310/saml/northlake-saml-standard/acs"
            ),
            "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": (
                "https://localhost:7310/saml/northlake-saml-standard/logout"
            ),
            "EEMSUITE_SAML2INT_ENTITY_ID": (
                "urn:energyhippo:eemsuite-web:saml:saml2int"
            ),
        }
        self.keycloak = FakeKeycloakAdminClient()
        self.application = self._application(self.environment, self.keycloak)
        self.server = create_server(self.application, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary_directory.cleanup()

    def _application(
        self,
        environment: dict[str, str],
        keycloak: FakeKeycloakAdminClient,
    ) -> ConfigurationApplication:
        return ConfigurationApplication(
            environment=environment,
            runtime_directory=self.runtime_directory,
            manifest_path=(
                REPOSITORY_ROOT / "security" / "northlake-eem-security-v1.yaml"
            ),
            field_catalog_path=(
                REPOSITORY_ROOT / "identity" / "configuration" / "fields.json"
            ),
            keycloak_client=keycloak,
        )

    def _json_request(
        self,
        path: str,
        values: dict | None = None,
    ) -> tuple[int, dict]:
        body = (
            json.dumps({"values": values}).encode("utf-8")
            if values is not None
            else None
        )
        http_request = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST" if body is not None else "GET",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(http_request, timeout=10) as response:
                return response.status, json.load(response)
        except error.HTTPError as failure:
            return failure.code, json.load(failure)

    def test_form_and_state_are_available_without_authentication(self) -> None:
        with request.urlopen(f"{self.base_url}/configure", timeout=10) as response:
            document = response.read().decode("utf-8")
        status, state = self._json_request("/configure/api/state")

        self.assertEqual(200, status)
        self.assertIn("Configure one disposable identity provider", document)
        self.assertEqual("northlake", state["values"]["realmKey"])
        serialized = json.dumps(state)
        self.assertNotIn(self.environment["KEYCLOAK_ADMIN_PASSWORD"], serialized)
        self.assertNotIn(self.environment["EEMSUITE_OIDC_CLIENT_SECRET"], serialized)

    def test_invalid_apply_fails_before_writing_or_mutating_keycloak(self) -> None:
        values = ProviderSettings.from_environment(self.environment).to_values()
        values["publicBaseUrl"] = "http://localhost:8443"

        status, payload = self._json_request("/configure/api/apply", values)

        self.assertEqual(400, status)
        self.assertIn("publicBaseUrl", payload["errors"])
        self.assertFalse(self.application.settings_path.exists())
        self.assertEqual([], self.keycloak.replacements)

    def test_save_then_apply_generates_and_replaces_the_disposable_realm(self) -> None:
        values = ProviderSettings.from_environment(self.environment).to_values()
        values["providerDisplayName"] = "Northlake Test University"

        save_status, save_payload = self._json_request(
            "/configure/api/save",
            values,
        )
        apply_status, apply_payload = self._json_request(
            "/configure/api/apply",
            values,
        )

        self.assertEqual(200, save_status)
        self.assertFalse(save_payload["applied"])
        self.assertEqual(200, apply_status)
        self.assertTrue(apply_payload["applied"])
        self.assertEqual([("northlake", "northlake")], self.keycloak.replacements)
        self.assertEqual(["northlake"], self.keycloak.health_checks)
        self.assertTrue(self.application.realm_output_path.is_file())
        self.assertTrue(self.application.connection_output_path.is_file())
        document = self.application._document()
        self.assertFalse(document.pending_apply)
        self.assertEqual("Northlake Test University", document.settings.provider_display_name)

    def test_edge_change_is_pending_until_the_restarted_service_reconciles(self) -> None:
        values = ProviderSettings.from_environment(self.environment).to_values()
        values["publicBaseUrl"] = "https://localhost:9443"
        values["httpsPort"] = 9443

        status, payload = self._json_request("/configure/api/apply", values)

        self.assertEqual(202, status)
        self.assertTrue(payload["restartRequired"])
        self.assertEqual([], self.keycloak.replacements)
        self.assertTrue(self.application._document().pending_apply)

        restarted_environment = dict(self.environment)
        restarted_settings = ProviderSettings.from_values(values)
        restarted_environment.update(restarted_settings.to_environment_overlay())
        restarted_keycloak = FakeKeycloakAdminClient()
        restarted_application = self._application(
            restarted_environment,
            restarted_keycloak,
        )
        restarted_application.reconcile_pending()

        self.assertEqual([("northlake", "northlake")], restarted_keycloak.replacements)
        self.assertFalse(restarted_application._document().pending_apply)


if __name__ == "__main__":
    unittest.main()
