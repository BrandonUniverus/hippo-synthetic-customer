from __future__ import annotations

import json
import base64
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request

from identity.configuration.server import ConfigurationApplication, create_server
from identity.configuration.scenarios import ScenarioValidationError
from identity.tests.test_configuration_saml import create_public_certificate
from identity.configuration.settings import ProviderSettings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeKeycloakAdminClient:
    def __init__(self) -> None:
        self.replacements: list[tuple[str, str | None]] = []
        self.health_checks: list[str] = []
        self.impersonations: list[tuple[str, str]] = []

    def replace_realm(self, realm: dict, previous_realm_key: str | None) -> None:
        self.replacements.append((realm["realm"], previous_realm_key))

    def wait_until_healthy(self, settings: ProviderSettings) -> None:
        self.health_checks.append(settings.realm_key)

    def impersonate(self, realm_key: str, username: str) -> list[str]:
        self.impersonations.append((realm_key, username))
        return [
            f"KEYCLOAK_IDENTITY=test; Path=/realms/{realm_key}/; HttpOnly; SameSite=Lax; Secure",
            f"KEYCLOAK_SESSION=test; Path=/realms/{realm_key}/; SameSite=Lax; Secure",
        ]


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
            "NORTHLAKE_CUSTOMER_CLIENT_SECRET": "customer-secret-value-123",
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
        self.saml_verifier_calls: list[tuple[Path, Path]] = []
        self.scenario_verifier_calls: list[tuple[list[Path], Path]] = []
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

        def verify_saml(connection_path: Path, ca_path: Path) -> dict:
            self.saml_verifier_calls.append((connection_path, ca_path))
            return {
                "passed": True,
                "exitCode": 0,
                "classification": "provider-ready-eem-proof-required",
                "output": "[OK] Focused SAML verifier passed.\n[GAP] Installed EEM proof required.",
            }

        def verify_scenarios(connection_paths: list[Path], ca_path: Path) -> dict:
            self.scenario_verifier_calls.append((connection_paths, ca_path))
            return {
                "passed": True,
                "exitCode": 0,
                "classification": "provider-ready-eem-proof-required",
                "output": "[OK] Two provider realms passed.\n[GAP] Installed EEM proof required.",
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
            saml_verifier=verify_saml,
            scenario_verifier=verify_scenarios,
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

    def test_saml_form_and_secret_free_copy_values_are_available_without_authentication(self) -> None:
        with request.urlopen(f"{self.base_url}/configure/saml", timeout=10) as response:
            document = response.read().decode("utf-8")
        status, payload = self._json_request("/configure/api/saml")

        self.assertEqual(200, status)
        self.assertIn("Configure Standard and Saml2Int", document)
        self.assertTrue(payload["values"]["standardEnabled"])
        self.assertFalse(payload["values"]["saml2IntEnabled"])
        self.assertFalse(payload["certificate"]["configured"])
        serialized = json.dumps(payload)
        self.assertNotIn("BEGIN CERTIFICATE", serialized)
        self.assertNotIn("BEGIN PRIVATE KEY", serialized)

    def test_saml2int_requires_public_certificate_before_realm_mutation(self) -> None:
        _, state = self._json_request("/configure/api/saml")
        values = state["values"]
        values["saml2IntEnabled"] = True

        status, payload = self._json_request("/configure/api/saml/apply", values)

        self.assertEqual(400, status)
        self.assertIn("saml2IntCertificateBase64", payload["errors"])
        self.assertEqual([], self.keycloak.replacements)
        self.assertEqual([], self.saml_verifier_calls)

    def test_saml_apply_installs_both_profiles_and_only_public_certificate(self) -> None:
        certificate_der, _ = create_public_certificate()
        _, state = self._json_request("/configure/api/saml")
        values = state["values"]
        values.update(
            {
                "saml2IntEnabled": True,
                "saml2IntCertificateBase64": base64.b64encode(certificate_der).decode(
                    "ascii"
                ),
                "saml2IntCertificateName": "eem-public.cer",
            }
        )

        status, payload = self._json_request("/configure/api/saml/apply", values)
        _, persisted = self._json_request("/configure/api/saml")

        self.assertEqual(200, status)
        self.assertTrue(payload["applied"])
        self.assertTrue(payload["verification"]["passed"])
        self.assertEqual(
            "provider-ready-eem-proof-required",
            payload["verification"]["classification"],
        )
        self.assertTrue(persisted["values"]["saml2IntEnabled"])
        self.assertTrue(persisted["certificate"]["configured"])
        self.assertEqual(certificate_der, self.application.saml2int_certificate_path.read_bytes())
        self.assertEqual(1, len(self.keycloak.replacements))
        self.assertEqual(1, len(self.saml_verifier_calls))
        generated_realm = json.loads(
            self.application.realm_output_path.read_text(encoding="utf-8")
        )
        saml_clients = [
            client for client in generated_realm["clients"] if client["protocol"] == "saml"
        ]
        self.assertEqual(2, len(saml_clients))
        saml2int = next(
            client
            for client in saml_clients
            if client["attributes"]["saml.encrypt"] == "true"
        )
        expected_encryption_attributes = {
            "saml.encryption.algorithm": "http://www.w3.org/2009/xmlenc11#aes256-gcm",
            "saml.encryption.keyAlgorithm": "http://www.w3.org/2009/xmlenc11#rsa-oaep",
            "saml.encryption.digestMethod": "http://www.w3.org/2001/04/xmlenc#sha256",
            "saml.encryption.maskGenerationFunction": "http://www.w3.org/2009/xmlenc11#mgf1sha256",
        }
        for attribute, value in expected_encryption_attributes.items():
            self.assertEqual(value, saml2int["attributes"][attribute])
        serialized = json.dumps(persisted)
        self.assertNotIn(base64.b64encode(certificate_der).decode("ascii"), serialized)
        self.assertNotIn("PRIVATE KEY", serialized)

    def test_scenario_form_and_redacted_presets_are_available_without_authentication(self) -> None:
        with request.urlopen(f"{self.base_url}/configure/scenarios", timeout=10) as response:
            document = response.read().decode("utf-8")
        status, payload = self._json_request("/configure/api/scenarios")

        self.assertEqual(200, status)
        self.assertIn("Run two identity providers together", document)
        self.assertEqual({"labA", "labB"}, set(payload["values"]["realms"]))
        self.assertEqual(
            {"IsolationBaseline", "SharedSubject", "ClaimDrift"},
            set(payload["presets"]),
        )
        serialized = json.dumps(payload)
        self.assertNotIn(self.environment["KEYCLOAK_ADMIN_PASSWORD"], serialized)
        self.assertNotIn(self.environment["EEMSUITE_OIDC_CLIENT_SECRET"], serialized)
        self.assertTrue(payload["export"]["redacted"])

    def test_scenario_apply_clone_and_per_realm_reset_are_bounded(self) -> None:
        _, state = self._json_request("/configure/api/scenarios")
        values = state["values"]
        values["realms"]["labB"]["claimShape"] = "Minimal"

        clone_status, cloned = self._json_request(
            "/configure/api/scenarios/clone/labA/labB",
            values,
        )
        self.assertEqual(200, clone_status)
        self.assertEqual("Full", cloned["values"]["realms"]["labB"]["claimShape"])
        self.assertEqual(
            "northlake-lab-b",
            cloned["values"]["realms"]["labB"]["realmKey"],
        )

        apply_status, applied = self._json_request(
            "/configure/api/scenarios/apply",
            cloned["values"],
        )
        self.assertEqual(200, apply_status)
        self.assertTrue(applied["applied"])
        self.assertTrue(applied["verification"]["passed"])
        self.assertEqual(
            [("northlake-lab-a", None), ("northlake-lab-b", None)],
            self.keycloak.replacements,
        )
        self.assertEqual(["northlake-lab-a", "northlake-lab-b"], self.keycloak.health_checks)
        self.assertEqual(1, len(self.scenario_verifier_calls))
        for connection_path in self.scenario_verifier_calls[0][0]:
            self.assertTrue(connection_path.is_file())

        reset_status, reset = self._json_request(
            "/configure/api/scenarios/reset/labB",
            applied["values"],
        )
        self.assertEqual(200, reset_status)
        self.assertTrue(reset["applied"])
        self.assertEqual(
            ("northlake-lab-b", "northlake-lab-b"),
            self.keycloak.replacements[-1],
        )
        self.assertEqual(2, len(self.scenario_verifier_calls))

    def test_browser_session_bootstrap_is_explicit_bounded_and_password_free(self) -> None:
        with request.urlopen(
            f"{self.base_url}/configure/browser-session/labA?cookieMode=Lax",
            timeout=10,
        ) as response:
            document = response.read().decode("utf-8")
        self.assertIn("Keycloak administrator impersonation", document)
        self.assertIn("not counted as password-authentication evidence", document)
        self.assertNotIn(self.environment["SYNTHETIC_USER_PASSWORD"], document)

        _, state = self._json_request("/configure/api/scenarios")
        apply_status, _ = self._json_request(
            "/configure/api/scenarios/apply",
            state["values"],
        )
        self.assertEqual(200, apply_status)

        location, cookies = self.application.bootstrap_browser_session("labA", "None")
        self.assertEqual(
            [("northlake-lab-a", "samantha.ireland")],
            self.keycloak.impersonations,
        )
        self.assertTrue(location.startswith("https://customer.localtest.me:8443/customer/login?"))
        self.assertIn("cookieMode=None", location)
        self.assertEqual({"KEYCLOAK_IDENTITY", "KEYCLOAK_SESSION"}, {
            cookie.partition("=")[0] for cookie in cookies
        })
        self.assertTrue(all("Secure" in cookie for cookie in cookies))

        with self.assertRaises(ScenarioValidationError):
            self.application.bootstrap_browser_session("labC", "None")
        with self.assertRaises(ScenarioValidationError):
            self.application.bootstrap_browser_session("labA", "Strict")

    def test_scenario_rejects_arbitrary_keycloak_json_before_realm_mutation(self) -> None:
        _, state = self._json_request("/configure/api/scenarios")
        values = state["values"]
        values["rawKeycloakJson"] = {"clients": [{"publicClient": True}]}

        status, payload = self._json_request(
            "/configure/api/scenarios/apply",
            values,
        )

        self.assertEqual(400, status)
        self.assertIn("_form", payload["errors"])
        self.assertEqual([], self.keycloak.replacements)
        self.assertFalse(self.application.scenario_settings_path.exists())

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
