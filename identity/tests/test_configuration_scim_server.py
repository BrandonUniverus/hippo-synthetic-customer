from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib import error, request

from identity.configuration.scim import ScimClient
from identity.configuration.server import ConfigurationApplication, create_server
from identity.tests.test_configuration_scim import CREDENTIAL, FakeScimTransport


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class UnusedKeycloakClient:
    pass


class ConfigurationScimServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.runtime_directory = Path(self.temporary_directory.name) / "runtime"
        self.transport = FakeScimTransport()
        environment = {
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "IDENTITY_HTTPS_PORT": "8443",
            "IDENTITY_HOST": "localhost",
            "NORTHLAKE_PROVIDER_DISPLAY_NAME": "Northlake Synthetic Identity",
            "NORTHLAKE_REALM_KEY": "northlake",
            "NORTHLAKE_ENABLE_OIDC": "true",
            "NORTHLAKE_ENABLE_SAML": "true",
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
            "EEMSUITE_SAML_STANDARD_ENTITY_ID": "urn:energyhippo:eemsuite-web:saml:standard",
            "EEMSUITE_SAML_STANDARD_ACS_URLS": "https://localhost:7310/saml/northlake-saml-standard/acs",
            "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": "https://localhost:7310/saml/northlake-saml-standard/logout",
            "EEMSUITE_SAML2INT_ENTITY_ID": "urn:energyhippo:eemsuite-web:saml:saml2int",
        }
        self.application = ConfigurationApplication(
            environment=environment,
            runtime_directory=self.runtime_directory,
            manifest_path=REPOSITORY_ROOT / "security" / "northlake-eem-security-v1.yaml",
            field_catalog_path=REPOSITORY_ROOT / "identity" / "configuration" / "fields.json",
            keycloak_client=UnusedKeycloakClient(),
            scim_client_factory=lambda connection, credential, runtime: ScimClient(
                connection,
                credential,
                self.transport,
            ),
        )
        self.server = create_server(self.application, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary_directory.cleanup()

    def json_request(self, path: str, values: dict | None = None) -> tuple[int, dict]:
        body = json.dumps({"values": values}).encode("utf-8") if values is not None else None
        http_request = request.Request(
            self.base_url + path,
            data=body,
            method="POST" if body is not None else "GET",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(http_request, timeout=10) as response:
                return response.status, json.load(response)
        except error.HTTPError as failure:
            return failure.code, json.load(failure)

    def test_scim_page_state_save_and_discovery_never_return_credential(self) -> None:
        with request.urlopen(self.base_url + "/configure/scim", timeout=10) as response:
            document = response.read().decode("utf-8")
        state_status, state = self.json_request("/configure/api/scim")
        values = json.loads(json.dumps(state["values"]))
        values["credential"] = CREDENTIAL

        save_status, saved = self.json_request("/configure/api/scim/save", values)
        verify_status, verified = self.json_request(
            "/configure/api/scim/verify",
            {"connectionKey": "eem-local"},
        )
        _, reloaded = self.json_request("/configure/api/scim")

        self.assertEqual(200, state_status)
        self.assertEqual(200, save_status)
        self.assertEqual(200, verify_status)
        self.assertIn("Provision EnergyHippo", document)
        self.assertTrue(saved["credentialStatus"]["eem-local"])
        self.assertTrue(verified["verification"]["passed"])
        self.assertEqual("discovery-passed", verified["verification"]["classification"])
        serialized = json.dumps([state, saved, verified, reloaded])
        self.assertNotIn(CREDENTIAL, serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertTrue(self.application.scim_credentials_path.is_file())
        self.assertTrue(self.application.scim_verification_path.is_file())

    def test_scim_lifecycle_and_manual_deactivate_reactivate_handoff(self) -> None:
        _, state = self.json_request("/configure/api/scim")
        values = state["values"]
        values["credential"] = CREDENTIAL
        save_status, _ = self.json_request("/configure/api/scim/save", values)

        lifecycle_status, lifecycle = self.json_request(
            "/configure/api/scim/lifecycle",
            {
                "connectionKey": "eem-local",
                "syntheticUserId": "samantha.ireland",
                "groupBindingKey": "nlu-company-admins",
            },
        )
        deactivate_status, deactivated = self.json_request(
            "/configure/api/scim/deactivate",
            {"connectionKey": "eem-local"},
        )
        reactivate_status, reactivated = self.json_request(
            "/configure/api/scim/reactivate",
            {"connectionKey": "eem-local"},
        )

        self.assertEqual(200, save_status)
        self.assertEqual(200, lifecycle_status)
        self.assertEqual(200, deactivate_status)
        self.assertEqual(200, reactivate_status)
        self.assertTrue(lifecycle["lifecycle"]["passed"])
        self.assertEqual(
            "scim-lifecycle-passed-authentication-proof-required",
            lifecycle["lifecycle"]["classification"],
        )
        self.assertFalse(deactivated["lifecycle"]["active"])
        self.assertEqual("deny-local-session", deactivated["lifecycle"]["crossProtocol"]["expectedEemDecision"])
        self.assertTrue(reactivated["lifecycle"]["active"])
        serialized = json.dumps([lifecycle, deactivated, reactivated])
        self.assertNotIn(CREDENTIAL, serialized)
        self.assertNotIn("samantha.ireland@", serialized)

    def test_scim_rejects_unknown_configuration_before_secret_write(self) -> None:
        _, state = self.json_request("/configure/api/scim")
        values = state["values"]
        values["credential"] = CREDENTIAL
        values["connections"][0]["allowHttp"] = True

        status, payload = self.json_request("/configure/api/scim/save", values)

        self.assertEqual(400, status)
        self.assertIn("connections[0]", payload["errors"])
        self.assertFalse(self.application.scim_settings_path.exists())
        self.assertFalse(self.application.scim_credentials_path.exists())


if __name__ == "__main__":
    unittest.main()
