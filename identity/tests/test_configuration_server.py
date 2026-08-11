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
        self.verifier_calls: list[tuple[Path, Path]] = []
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
        def verify_oidc(connection_path: Path, ca_path: Path) -> dict:
            self.verifier_calls.append((connection_path, ca_path))
            return {
                "passed": True,
                "exitCode": 0,
                "classification": "passed",
                "output": "[OK] Focused OIDC verifier passed.",
            }

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
            oidc_verifier=verify_oidc,
        )

    def _json_request(
        self,
        path: str,
        values: dict | None = None,
        method: str | None = None,
    ) -> tuple[int, dict]:
        body = (
            json.dumps({"values": values}).encode("utf-8")
            if values is not None
            else None
        )
        http_request = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method or ("POST" if body is not None else "GET"),
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

    def test_user_form_lists_base_users_without_authentication_or_secrets(self) -> None:
        with request.urlopen(f"{self.base_url}/configure/users", timeout=10) as response:
            document = response.read().decode("utf-8")
        status, payload = self._json_request("/configure/api/users")

        self.assertEqual(200, status)
        self.assertIn("Shape fictional identities", document)
        self.assertEqual({"total": 19, "enabled": 18, "local": 0}, payload["counts"])
        serialized = json.dumps(payload)
        self.assertNotIn(self.environment["SYNTHETIC_USER_PASSWORD"], serialized)
        self.assertNotIn("generatedPassword", serialized)

    def test_group_form_lists_base_groups_without_authentication_or_eem_mutation(self) -> None:
        with request.urlopen(f"{self.base_url}/configure/groups", timeout=10) as response:
            document = response.read().decode("utf-8")
        status, payload = self._json_request("/configure/api/groups")

        self.assertEqual(200, status)
        self.assertIn("Shape protocol claims", document)
        self.assertIn("does not grant EnergyHippo authorization", document)
        self.assertEqual({"total": 27, "base": 27, "local": 0}, payload["counts"])
        self.assertNotIn("password", json.dumps(payload).lower())

    def test_oidc_form_and_secret_free_copy_values_are_available_without_authentication(self) -> None:
        with request.urlopen(f"{self.base_url}/configure/oidc", timeout=10) as response:
            document = response.read().decode("utf-8")
        status, payload = self._json_request("/configure/api/oidc")

        self.assertEqual(200, status)
        self.assertIn("Configure bounded OIDC profiles", document)
        self.assertEqual("Discovery", payload["values"]["configurationMode"])
        self.assertIn("modern", payload["preview"]["profiles"])
        serialized = json.dumps(payload)
        self.assertNotIn(self.environment["EEMSUITE_OIDC_CLIENT_SECRET"], serialized)
        self.assertNotIn(self.environment["EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"], serialized)

    def test_oidc_validation_rejects_an_unregistered_configuration_shape(self) -> None:
        _, state = self._json_request("/configure/api/oidc")
        values = state["values"]
        values["configurationMode"] = "Invented"

        status, payload = self._json_request("/configure/api/oidc/apply", values)

        self.assertEqual(400, status)
        self.assertIn("configurationMode", payload["errors"])
        self.assertEqual([], self.keycloak.replacements)
        self.assertEqual([], self.verifier_calls)

    def test_oidc_apply_regenerates_realm_runs_verifier_and_persists_safe_result(self) -> None:
        _, state = self._json_request("/configure/api/oidc")
        values = state["values"]
        values.update(
            {
                "configurationMode": "Static",
                "parBehavior": "Require",
                "tokenEndpointAuthMethod": "ClientSecretBasic",
                "accessTokenLifetimeSeconds": 420,
                "modernConsentRequired": False,
                "legacyEnabled": False,
            }
        )

        status, payload = self._json_request("/configure/api/oidc/apply", values)
        _, persisted = self._json_request("/configure/api/oidc")

        self.assertEqual(200, status)
        self.assertTrue(payload["applied"])
        self.assertTrue(payload["verification"]["passed"])
        self.assertEqual("Static", persisted["values"]["configurationMode"])
        self.assertEqual("Require", persisted["values"]["parBehavior"])
        self.assertFalse(persisted["values"]["legacyEnabled"])
        self.assertTrue(persisted["lastVerification"]["passed"])
        self.assertEqual(1, len(self.keycloak.replacements))
        self.assertEqual(1, len(self.keycloak.health_checks))
        self.assertEqual(1, len(self.verifier_calls))
        generated_realm = json.loads(
            self.application.realm_output_path.read_text(encoding="utf-8")
        )
        oidc_clients = [
            client
            for client in generated_realm["clients"]
            if client["protocol"] == "openid-connect"
        ]
        self.assertEqual(1, len(oidc_clients))
        self.assertEqual(
            "true",
            oidc_clients[0]["attributes"]["pushed.authorization.request.required"],
        )
        self.assertNotIn(
            self.environment["EEMSUITE_OIDC_CLIENT_SECRET"],
            json.dumps(persisted),
        )

        save_status, saved = self._json_request("/configure/api/oidc/save", values)
        _, after_save = self._json_request("/configure/api/oidc")
        self.assertEqual(200, save_status)
        self.assertFalse(saved["applied"])
        self.assertIsNone(after_save["lastVerification"])

    def test_create_membership_rename_and_delete_group_regenerates_the_realm(self) -> None:
        _, users = self._json_request("/configure/api/users")
        member_id = users["users"][0]["syntheticUserId"]

        create_status, created = self._json_request(
            "/configure/api/groups/create",
            {"groupId": "phase3_reviewers", "displayName": "Phase 3 Reviewers"},
        )
        member_status, with_member = self._json_request(
            "/configure/api/groups/phase3_reviewers/members",
            {"members": [member_id]},
        )
        claim_status, claims = self._json_request(
            f"/configure/api/groups/claims?userId={member_id}"
        )
        rename_status, renamed = self._json_request(
            "/configure/api/groups/phase3_reviewers/update",
            {"groupId": "phase3_identity_reviewers", "displayName": "Identity Reviewers"},
        )
        delete_status, deleted = self._json_request(
            "/configure/api/groups/phase3_identity_reviewers/delete",
            method="POST",
        )
        _, listed = self._json_request("/configure/api/groups")

        self.assertEqual(200, create_status)
        self.assertEqual("local", created["group"]["source"])
        self.assertEqual(200, member_status)
        self.assertEqual([member_id], with_member["group"]["memberIds"])
        self.assertEqual(200, claim_status)
        self.assertIn("phase3_reviewers", claims["oidc"]["groups"])
        self.assertIn("phase3_reviewers", claims["saml"]["groups"])
        self.assertEqual(200, rename_status)
        self.assertEqual("phase3_identity_reviewers", renamed["group"]["groupId"])
        self.assertEqual(200, delete_status)
        self.assertTrue(deleted["group"]["deleted"])
        self.assertEqual({"total": 27, "base": 27, "local": 0}, listed["counts"])
        self.assertEqual(4, len(self.keycloak.replacements))

    def test_invalid_group_changes_fail_before_overlay_or_realm_mutation(self) -> None:
        _, state = self._json_request("/configure/api/groups")
        base_group_id = state["groups"][0]["groupId"]

        invalid_status, invalid = self._json_request(
            "/configure/api/groups/create",
            {"groupId": "INVALID GROUP", "displayName": "Invalid Group"},
        )
        rename_status, rename = self._json_request(
            f"/configure/api/groups/{base_group_id}/update",
            {"groupId": "renamed_base", "displayName": "Renamed Base"},
        )
        delete_status, delete = self._json_request(
            f"/configure/api/groups/{base_group_id}/delete",
            method="POST",
        )

        self.assertEqual(400, invalid_status)
        self.assertIn("groupId", invalid["errors"])
        self.assertEqual(400, rename_status)
        self.assertIn("_form", rename["errors"])
        self.assertEqual(400, delete_status)
        self.assertIn("_form", delete["errors"])
        self.assertFalse(self.application.group_overlay_path.exists())
        self.assertEqual([], self.keycloak.replacements)

    def test_create_disable_reenable_and_reset_password_regenerates_the_realm(self) -> None:
        values = {
            "username": "alex.rivera",
            "firstName": "Alex",
            "lastName": "Rivera",
            "email": "alex.rivera@northlake.example.edu",
            "enabled": True,
            "title": "Synthetic Integration Tester",
        }

        create_status, created = self._json_request(
            "/configure/api/users/create",
            values,
        )
        user_id = created["user"]["syntheticUserId"]
        disable_status, disabled = self._json_request(
            f"/configure/api/users/{user_id}/update",
            {**values, "enabled": False},
        )
        enable_status, enabled = self._json_request(
            f"/configure/api/users/{user_id}/update",
            values,
        )
        reset_status, reset = self._json_request(
            f"/configure/api/users/{user_id}/reset-password",
            method="POST",
        )
        list_status, listed = self._json_request("/configure/api/users")

        self.assertEqual(200, create_status)
        self.assertEqual(28, len(created["generatedPassword"]))
        self.assertEqual(200, disable_status)
        self.assertFalse(disabled["user"]["enabled"])
        self.assertEqual(200, enable_status)
        self.assertTrue(enabled["user"]["enabled"])
        self.assertEqual(200, reset_status)
        self.assertNotEqual(created["generatedPassword"], reset["generatedPassword"])
        self.assertEqual(200, list_status)
        self.assertEqual(20, listed["counts"]["total"])
        self.assertEqual(1, listed["counts"]["local"])
        self.assertNotIn("generatedPassword", json.dumps(listed))
        self.assertEqual(4, len(self.keycloak.replacements))
        self.assertTrue(self.application.user_overlay_path.is_file())

    def test_invalid_user_fails_before_overlay_or_realm_mutation(self) -> None:
        status, payload = self._json_request(
            "/configure/api/users/create",
            {
                "username": "alex.rivera",
                "firstName": "Alex",
                "lastName": "Rivera",
                "email": "alex@real-company.org",
                "enabled": True,
                "title": "Synthetic Integration Tester",
                "password": "must-not-be-accepted",
            },
        )

        self.assertEqual(400, status)
        self.assertIn("_form", payload["errors"])
        self.assertFalse(self.application.user_overlay_path.exists())
        self.assertEqual([], self.keycloak.replacements)

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
