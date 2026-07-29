from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPOSITORY_ROOT / "identity" / "realm" / "generate_realm.py"
SPEC = importlib.util.spec_from_file_location("generate_realm", GENERATOR_PATH)
assert SPEC and SPEC.loader
generate_realm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_realm)


class GenerateRealmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = REPOSITORY_ROOT / "security" / "northlake-eem-security-v1.yaml"
        self.environment = {
            "IDENTITY_HOST": "localhost",
            "IDENTITY_HTTPS_PORT": "8443",
            "IDENTITY_PUBLIC_BASE_URL": "https://localhost:8443",
            "KEYCLOAK_ADMIN": "admin",
            "KEYCLOAK_ADMIN_PASSWORD": "A1!admin-password-for-tests",
            "KEYCLOAK_DB_PASSWORD": "A1!database-password-for-tests",
            "EEMSUITE_OIDC_CLIENT_SECRET": "modern-client-secret-for-tests",
            "EEMSUITE_OIDC_LEGACY_CLIENT_SECRET": "legacy-client-secret-for-tests",
            "SYNTHETIC_USER_PASSWORD": "A1!synthetic-user-password-for-tests",
            "EEMSUITE_OIDC_REDIRECT_URIS": (
                "https://localhost:7310/signin-oidc;"
                "https://localdev.energyhippo.com/Hippo/signin-oidc"
            ),
            "EEMSUITE_SAML_ENTITY_ID": "urn:energyhippo:eemsuite-web:saml",
            "EEMSUITE_SAML_ACS_URLS": (
                "https://localhost:7310/saml/acs;"
                "https://localdev.energyhippo.com/Hippo/saml/acs"
            ),
            "EEMSUITE_SAML_LOGOUT_URLS": (
                "https://localhost:7310/saml/logout;"
                "https://localdev.energyhippo.com/Hippo/saml/logout"
            ),
        }

    def _generate(self) -> tuple[dict, dict]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            env_path = temporary / ".env"
            env_path.write_text(
                "\n".join(f"{key}={value}" for key, value in self.environment.items()),
                encoding="utf-8",
            )
            realm_path = temporary / "northlake-realm.json"
            connection_path = temporary / "connection.json"
            realm, connection = generate_realm.generate(
                self.manifest,
                env_path,
                realm_path,
                connection_path,
            )
            self.assertEqual(realm, json.loads(realm_path.read_text(encoding="utf-8")))
            self.assertEqual(connection, json.loads(connection_path.read_text(encoding="utf-8")))
            return realm, connection

    def test_expected_users_groups_and_disabled_case_are_generated(self) -> None:
        realm, connection = self._generate()

        self.assertEqual(19, len(realm["users"]))
        self.assertEqual(18, sum(user["enabled"] for user in realm["users"]))
        self.assertEqual(27, len(realm["groups"]))
        casey = next(user for user in realm["users"] if user["username"] == "casey.holt")
        self.assertFalse(casey["enabled"])
        self.assertIn("/nlu_bill_entry", casey["groups"])
        self.assertEqual(
            {
                "manifestId": "northlake_eem_security_v1",
                "manifestVersion": 1,
                "customerScenarioId": "demo_university_v1",
            },
            connection["realmSource"],
        )

    def test_clients_separate_modern_and_legacy_behavior(self) -> None:
        realm, connection = self._generate()
        clients = {client["clientId"]: client for client in realm["clients"]}

        modern = clients["eemsuite-web"]
        self.assertFalse(modern["implicitFlowEnabled"])
        self.assertTrue(modern["consentRequired"])
        self.assertEqual("S256", modern["attributes"]["pkce.code.challenge.method"])
        self.assertFalse(modern["directAccessGrantsEnabled"])
        self.assertIn("basic", modern["defaultClientScopes"])
        self.assertIn("offline_access", modern["optionalClientScopes"])

        legacy = clients["eemsuite-web-legacy"]
        self.assertTrue(legacy["implicitFlowEnabled"])
        self.assertFalse(legacy["consentRequired"])
        self.assertNotIn("pkce.code.challenge.method", legacy["attributes"])

        self.assertEqual(
            "code",
            connection["eemsuiteConfiguration"]["modern"]["OpenIDConnect"]["ResponseType"],
        )
        self.assertEqual(
            "id_token token",
            connection["eemsuiteConfiguration"]["legacy"]["OpenIDConnect"]["ResponseType"],
        )

    def test_saml_client_is_signed_exact_and_maps_northlake_attributes(self) -> None:
        realm, connection = self._generate()
        clients = {client["clientId"]: client for client in realm["clients"]}
        entity_id = "urn:energyhippo:eemsuite-web:saml"
        saml = clients[entity_id]

        self.assertEqual("saml", saml["protocol"])
        self.assertEqual(
            [
                "https://localhost:7310/saml/acs",
                "https://localdev.energyhippo.com/Hippo/saml/acs",
            ],
            saml["redirectUris"],
        )
        self.assertEqual("true", saml["attributes"]["saml.server.signature"])
        self.assertEqual("true", saml["attributes"]["saml.assertion.signature"])
        self.assertEqual("RSA_SHA256", saml["attributes"]["saml.signature.algorithm"])
        self.assertEqual("true", saml["attributes"]["saml.force.post.binding"])
        self.assertEqual("false", saml["attributes"]["saml.client.signature"])
        self.assertEqual("true", saml["attributes"]["saml.onetimeuse.condition"])
        self.assertEqual("persistent", saml["attributes"]["saml_name_id_format"])

        mapper_names = {mapper["name"] for mapper in saml["protocolMappers"]}
        self.assertEqual(
            {
                "username",
                "email",
                "given_name",
                "family_name",
                "groups",
                "synthetic_user_id",
                "primary_company_id",
                "title",
                "synthetic_status",
                "eem_company_ids",
                "eem_permission_profiles",
                "realm_roles",
            },
            mapper_names,
        )

        profile = connection["clients"]["saml"]
        self.assertEqual(entity_id, profile["entityId"])
        self.assertTrue(profile["wantResponseSigned"])
        self.assertTrue(profile["wantAssertionsSigned"])
        self.assertFalse(profile["wantAssertionsEncrypted"])
        self.assertEqual(
            "https://localhost:8443/realms/northlake/protocol/saml/descriptor",
            connection["samlMetadataEndpoint"],
        )

    def test_saml_defaults_keep_existing_identity_environment_compatible(self) -> None:
        self.environment.pop("EEMSUITE_SAML_ENTITY_ID")
        self.environment.pop("EEMSUITE_SAML_ACS_URLS")
        self.environment.pop("EEMSUITE_SAML_LOGOUT_URLS")

        realm, connection = self._generate()
        saml = next(client for client in realm["clients"] if client["protocol"] == "saml")

        self.assertEqual("urn:energyhippo:eemsuite-web:saml", saml["clientId"])
        self.assertEqual(
            "https://localhost:7310/saml/acs",
            connection["clients"]["saml"]["defaultAssertionConsumerServiceUrl"],
        )
        self.assertEqual(
            "https://localhost:7310/saml/logout",
            connection["clients"]["saml"]["defaultSingleLogoutServiceUrl"],
        )

    def test_subjects_and_group_ids_are_deterministic(self) -> None:
        first, first_connection = self._generate()
        second, _ = self._generate()

        self.assertEqual(
            [user["id"] for user in first["users"]],
            [user["id"] for user in second["users"]],
        )
        self.assertEqual(
            [group["id"] for group in first["groups"]],
            [group["id"] for group in second["groups"]],
        )
        persistent_attribute = (
            "saml.persistent.name.id.for.urn:energyhippo:eemsuite-web:saml"
        )
        first_name_ids = [
            user["attributes"][persistent_attribute]
            for user in first["users"]
        ]
        second_name_ids = [
            user["attributes"][persistent_attribute]
            for user in second["users"]
        ]
        self.assertEqual(first_name_ids, second_name_ids)
        active_user = next(
            user
            for user in first["users"]
            if user["username"] == first_connection["testUsers"]["active"]["username"]
        )
        self.assertEqual(
            active_user["attributes"][persistent_attribute][0],
            first_connection["testUsers"]["active"]["samlNameId"],
        )

    def test_userinfo_claim_sources_include_groups_and_eem_shapes(self) -> None:
        realm, _ = self._generate()
        scope = next(scope for scope in realm["clientScopes"] if scope["name"] == "northlake")
        claim_names = {
            mapper["config"]["claim.name"]
            for mapper in scope["protocolMappers"]
        }
        self.assertEqual(
            {
                "groups",
                "synthetic_user_id",
                "primary_company_id",
                "title",
                "synthetic_status",
                "eem_company_ids",
                "eem_permission_profiles",
            },
            claim_names,
        )

    def test_placeholder_secrets_are_rejected(self) -> None:
        self.environment["SYNTHETIC_USER_PASSWORD"] = "replace-with-generated-value"
        with self.assertRaises(generate_realm.RealmGenerationError):
            self._generate()


if __name__ == "__main__":
    unittest.main()
