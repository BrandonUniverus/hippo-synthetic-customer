from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from identity.configuration.groups import SyntheticGroupStore
from identity.configuration.oidc import (
    OidcSettings,
    OidcSettingsDocument,
    write_oidc_settings_document,
)
from identity.configuration.settings import ProviderSettings, SettingsDocument, write_settings_document
from identity.configuration.users import SyntheticUserStore


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
            "EEMSUITE_APPLICATION_HOME_URL": "https://localdev.energyhippo.com/Hippo/",
            "EEMSUITE_OIDC_REDIRECT_URIS": (
                "https://localhost:7310/signin-oidc;"
                "https://localdev.energyhippo.com/Hippo/signin-oidc"
            ),
            "EEMSUITE_SAML_PROFILES": "Standard",
            "EEMSUITE_SAML_STANDARD_ENTITY_ID": (
                "urn:energyhippo:eemsuite-web:saml:standard"
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
        self.assertTrue(
            all(user["realmRoles"] == ["default-roles-northlake"] for user in realm["users"])
        )
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
        self.assertEqual(
            {"total": 19, "enabled": 18, "local": 0},
            connection["userInventory"],
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
        self.assertEqual(
            "https://localdev.energyhippo.com/Hippo/signout-oidc",
            modern["attributes"]["frontchannel.logout.url"],
        )
        self.assertEqual(
            "https://localdev.energyhippo.com/Hippo/",
            modern["baseUrl"],
        )

        legacy = clients["eemsuite-web-legacy"]
        self.assertTrue(legacy["implicitFlowEnabled"])
        self.assertFalse(legacy["consentRequired"])
        self.assertNotIn("pkce.code.challenge.method", legacy["attributes"])
        self.assertEqual(
            modern["attributes"]["frontchannel.logout.url"],
            legacy["attributes"]["frontchannel.logout.url"],
        )
        self.assertEqual(modern["baseUrl"], legacy["baseUrl"])
        self.assertEqual(1800, realm["accessCodeLifespanLogin"])
        self.assertEqual(1800, realm["accessCodeLifespanUserAction"])
        self.assertEqual(modern["baseUrl"], connection["applicationHomeUrl"])

        self.assertEqual(
            "code",
            connection["eemsuiteConfiguration"]["modern"]["OpenIDConnect"]["ResponseType"],
        )
        self.assertEqual(
            "id_token token",
            connection["eemsuiteConfiguration"]["legacy"]["OpenIDConnect"]["ResponseType"],
        )

    def test_oidc_configuration_shapes_the_realm_and_connection_profile(self) -> None:
        self.environment.update(
            {
                "NORTHLAKE_OIDC_CONFIGURATION_MODE": "Authority",
                "NORTHLAKE_OIDC_PAR_BEHAVIOR": "Require",
                "NORTHLAKE_OIDC_TOKEN_ENDPOINT_AUTH_METHOD": "ClientSecretBasic",
                "NORTHLAKE_OIDC_ACCESS_TOKEN_LIFETIME_SECONDS": "420",
                "NORTHLAKE_OIDC_MODERN_CLIENT_ID": "northlake-modern-basic",
                "NORTHLAKE_OIDC_MODERN_REDIRECT_URIS": (
                    "https://localhost:7310/signin-northlake"
                ),
                "NORTHLAKE_OIDC_MODERN_POST_LOGOUT_REDIRECT_URIS": (
                    "https://localhost:7310/signed-out"
                ),
                "NORTHLAKE_OIDC_MODERN_SCOPES": "openid email northlake",
                "NORTHLAKE_OIDC_MODERN_CONSENT_REQUIRED": "false",
                "NORTHLAKE_OIDC_LEGACY_ENABLED": "false",
            }
        )

        realm, connection = self._generate()
        oidc_clients = [
            client for client in realm["clients"] if client["protocol"] == "openid-connect"
        ]

        self.assertEqual(420, realm["accessTokenLifespan"])
        self.assertEqual(1, len(oidc_clients))
        modern = oidc_clients[0]
        self.assertEqual("northlake-modern-basic", modern["clientId"])
        self.assertFalse(modern["consentRequired"])
        self.assertEqual(
            "true",
            modern["attributes"]["pushed.authorization.request.required"],
        )
        self.assertEqual(
            "https://localhost:7310/signed-out",
            modern["attributes"]["post.logout.redirect.uris"],
        )
        self.assertNotIn("profile", modern["defaultClientScopes"])

        profile = connection["clients"]["modern"]
        self.assertEqual("Authority", profile["configurationMode"])
        self.assertEqual("Require", profile["parBehavior"])
        self.assertEqual("ClientSecretBasic", profile["tokenEndpointAuthMethod"])
        self.assertEqual("openid email northlake", profile["scope"])
        self.assertNotIn("legacy", connection["clients"])
        self.assertNotIn(
            "historicalLegacy",
            connection["oidcConfiguration"]["profiles"],
        )
        self.assertEqual(
            connection["issuer"],
            connection["oidcConfiguration"]["profiles"]["modern"]["metadataAddress"],
        )

    def test_saved_oidc_document_overrides_environment_during_host_generation(self) -> None:
        values = OidcSettings.from_environment(self.environment).to_values()
        values.update(
            {
                "parBehavior": "Disable",
                "modernClientId": "saved-modern-client",
                "legacyEnabled": False,
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            env_path = temporary / ".env"
            realm_path = temporary / "realm.json"
            connection_path = temporary / "connection.json"
            oidc_path = temporary / "oidc.json"
            env_path.write_text(
                "\n".join(f"{key}={value}" for key, value in self.environment.items()),
                encoding="utf-8",
            )
            write_oidc_settings_document(
                oidc_path,
                OidcSettingsDocument(settings=OidcSettings.from_values(values)),
            )

            realm, connection = generate_realm.generate(
                self.manifest,
                env_path,
                realm_path,
                connection_path,
                oidc_settings_path=oidc_path,
            )

        oidc_clients = [
            client for client in realm["clients"] if client["protocol"] == "openid-connect"
        ]
        self.assertEqual(["saved-modern-client"], [client["clientId"] for client in oidc_clients])
        self.assertEqual("Disable", connection["clients"]["modern"]["parBehavior"])
        self.assertNotIn("legacy", connection["clients"])

    def test_saml_client_is_signed_exact_and_maps_northlake_attributes(self) -> None:
        realm, connection = self._generate()
        clients = {client["clientId"]: client for client in realm["clients"]}
        entity_id = "urn:energyhippo:eemsuite-web:saml:standard"
        saml = clients[entity_id]

        self.assertEqual("saml", saml["protocol"])
        self.assertEqual(
            "https://localdev.energyhippo.com/Hippo/",
            saml["baseUrl"],
        )
        self.assertEqual(
            [
                "https://localhost:7310/saml/northlake-saml-standard/acs",
                "https://localdev.energyhippo.com/Hippo/saml/northlake-saml-standard/acs",
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
        self.assertEqual("northlake-saml-standard", profile["providerKey"])
        self.assertEqual("Standard", profile["validationProfile"])
        self.assertTrue(profile["wantResponseSigned"])
        self.assertTrue(profile["wantAssertionsSigned"])
        self.assertFalse(profile["wantAssertionsEncrypted"])
        self.assertEqual(
            "https://localhost:8443/realms/northlake/protocol/saml/descriptor",
            connection["samlMetadataEndpoint"],
        )

    def test_saml_defaults_use_dynamic_provider_routes(self) -> None:
        self.environment.pop("EEMSUITE_SAML_STANDARD_ENTITY_ID")
        self.environment.pop("EEMSUITE_SAML_STANDARD_ACS_URLS")
        self.environment.pop("EEMSUITE_SAML_STANDARD_LOGOUT_URLS")

        realm, connection = self._generate()
        saml = next(client for client in realm["clients"] if client["protocol"] == "saml")

        self.assertEqual("urn:energyhippo:eemsuite-web:saml:standard", saml["clientId"])
        self.assertEqual(
            "https://localhost:7310/saml/northlake-saml-standard/acs",
            connection["clients"]["saml"]["defaultAssertionConsumerServiceUrl"],
        )
        self.assertEqual(
            "https://localhost:7310/saml/northlake-saml-standard/logout",
            connection["clients"]["saml"]["defaultSingleLogoutServiceUrl"],
        )

    def test_saml2int_requires_signed_requests_and_encrypted_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            certificate_path = Path(temporary_directory) / "saml2int-sp.cer"
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            now_utc = datetime.now(UTC)
            subject = issuer = x509.Name(
                [x509.NameAttribute(NameOID.COMMON_NAME, "EEMSuite SAML2Int test")]
            )
            certificate = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now_utc - timedelta(minutes=1))
                .not_valid_after(now_utc + timedelta(days=1))
                .sign(private_key, hashes.SHA256())
            )
            certificate_path.write_bytes(
                certificate.public_bytes(serialization.Encoding.DER)
            )
            self.environment["EEMSUITE_SAML_PROFILES"] = "Standard;Saml2Int"
            self.environment["EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE"] = str(
                certificate_path
            )

            realm, connection = self._generate()

        clients = {client["clientId"]: client for client in realm["clients"]}
        saml2int = clients["urn:energyhippo:eemsuite-web:saml:saml2int"]
        attributes = saml2int["attributes"]
        expected_certificate = certificate.public_bytes(serialization.Encoding.DER)
        self.assertEqual("true", attributes["saml.client.signature"])
        self.assertEqual("true", attributes["saml.encrypt"])
        self.assertEqual(
            expected_certificate,
            base64.b64decode(attributes["saml.signing.certificate"]),
        )
        self.assertEqual(
            attributes["saml.signing.certificate"],
            attributes["saml.encryption.certificate"],
        )
        profile = connection["clients"]["saml2Int"]
        self.assertEqual("northlake-saml2int", profile["providerKey"])
        self.assertEqual("Saml2Int", profile["validationProfile"])
        self.assertTrue(profile["signAuthnRequests"])
        self.assertTrue(profile["wantResponseSigned"])
        self.assertFalse(profile["wantAssertionsSigned"])
        self.assertTrue(profile["wantAssertionsEncrypted"])
        self.assertEqual(
            "/saml/northlake-saml2int/acs",
            connection["eemsuiteConfiguration"]["samlProfiles"]["saml2Int"][
                "CallbackPath"
            ],
        )

    def test_saml2int_without_public_certificate_is_rejected(self) -> None:
        self.environment["EEMSUITE_SAML_PROFILES"] = "Standard;Saml2Int"
        with self.assertRaisesRegex(
            generate_realm.RealmGenerationError,
            "EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE",
        ):
            self._generate()

    def test_saml2int_non_rsa_public_certificate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            certificate_path = Path(temporary_directory) / "saml2int-ec.cer"
            private_key = ec.generate_private_key(ec.SECP256R1())
            now_utc = datetime.now(UTC)
            subject = issuer = x509.Name(
                [x509.NameAttribute(NameOID.COMMON_NAME, "Invalid EC SAML certificate")]
            )
            certificate = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now_utc - timedelta(minutes=1))
                .not_valid_after(now_utc + timedelta(days=1))
                .sign(private_key, hashes.SHA256())
            )
            certificate_path.write_bytes(
                certificate.public_bytes(serialization.Encoding.DER)
            )
            self.environment["EEMSUITE_SAML_PROFILES"] = "Standard;Saml2Int"
            self.environment["EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE"] = str(
                certificate_path
            )
            with self.assertRaisesRegex(
                generate_realm.RealmGenerationError,
                "RSA with at least 2048 bits",
            ):
                self._generate()

    def test_unknown_or_duplicate_saml_profile_is_rejected(self) -> None:
        for value in ("Standard;Standard", "Standard;Hybrid", ""):
            with self.subTest(value=value):
                self.environment["EEMSUITE_SAML_PROFILES"] = value
                with self.assertRaises(generate_realm.RealmGenerationError):
                    self._generate()

    def test_runtime_settings_override_the_default_realm_and_protocol_clients(self) -> None:
        settings = ProviderSettings.from_environment(self.environment)
        values = settings.to_values()
        values.update(
            {
                "providerDisplayName": "Northlake Configured Identity",
                "realmKey": "northlake-lab",
                "enableOidc": False,
                "enableSaml": True,
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            env_path = temporary / ".env"
            realm_path = temporary / "realm.json"
            connection_path = temporary / "connection.json"
            settings_path = temporary / "configuration.json"
            env_path.write_text(
                "\n".join(f"{key}={value}" for key, value in self.environment.items()),
                encoding="utf-8",
            )
            write_settings_document(
                settings_path,
                SettingsDocument(settings=ProviderSettings.from_values(values)),
            )

            realm, connection = generate_realm.generate(
                self.manifest,
                env_path,
                realm_path,
                connection_path,
                settings_path,
            )

        self.assertEqual("northlake-lab", realm["realm"])
        self.assertEqual("Northlake Configured Identity", realm["displayName"])
        self.assertEqual(["saml"], [client["protocol"] for client in realm["clients"]])
        self.assertNotIn("modern", connection["clients"])
        self.assertNotIn("legacy", connection["clients"])
        self.assertIn("saml", connection["clients"])
        self.assertEqual(
            "https://localhost:8443/realms/northlake-lab",
            connection["issuer"],
        )

    def test_saml_can_be_disabled_without_removing_oidc_clients(self) -> None:
        environment = dict(self.environment)
        environment["NORTHLAKE_ENABLE_SAML"] = "false"

        realm, connection = generate_realm.build_realm(
            generate_realm._load_manifest(self.manifest),
            environment,
        )

        self.assertEqual(
            ["openid-connect", "openid-connect"],
            [client["protocol"] for client in realm["clients"]],
        )
        self.assertEqual({"modern", "legacy"}, set(connection["clients"]))
        self.assertEqual({}, connection["eemsuiteConfiguration"]["samlProfiles"])

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
            "saml.persistent.name.id.for.urn:energyhippo:eemsuite-web:saml:standard"
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

    def test_local_user_overlay_keeps_subject_and_password_across_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            overlay_path = Path(temporary_directory) / "users.json"
            store = SyntheticUserStore(
                self.manifest,
                overlay_path,
                self.environment["SYNTHETIC_USER_PASSWORD"],
            )
            user, password = store.create(
                {
                    "username": "alex.rivera",
                    "firstName": "Alex",
                    "lastName": "Rivera",
                    "email": "alex.rivera@northlake.example.edu",
                    "enabled": True,
                    "title": "Synthetic Integration Tester",
                }
            )
            manifest = generate_realm._load_manifest(self.manifest)

            first, first_connection = generate_realm.build_realm(
                manifest,
                self.environment,
                overlay_path,
            )
            second, _ = generate_realm.build_realm(
                manifest,
                self.environment,
                overlay_path,
            )

        first_user = next(
            candidate for candidate in first["users"] if candidate["username"] == "alex.rivera"
        )
        second_user = next(
            candidate for candidate in second["users"] if candidate["username"] == "alex.rivera"
        )
        self.assertEqual(user["syntheticUserId"], first_user["attributes"]["synthetic_user_id"][0])
        self.assertEqual(first_user["id"], second_user["id"])
        self.assertEqual([], first_user["groups"])
        self.assertEqual(password, first_user["credentials"][0]["value"])
        self.assertEqual(
            {"total": 20, "enabled": 19, "local": 1},
            first_connection["userInventory"],
        )

    def test_local_group_membership_is_stable_without_adding_eem_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            user_overlay_path = temporary_root / "users.json"
            group_overlay_path = temporary_root / "groups.json"
            user_store = SyntheticUserStore(
                self.manifest,
                user_overlay_path,
                self.environment["SYNTHETIC_USER_PASSWORD"],
            )
            local_user, _ = user_store.create(
                {
                    "username": "alex.rivera",
                    "firstName": "Alex",
                    "lastName": "Rivera",
                    "email": "alex.rivera@northlake.example.edu",
                    "enabled": True,
                    "title": "Synthetic Integration Tester",
                }
            )
            group_store = SyntheticGroupStore(
                self.manifest,
                group_overlay_path,
                user_store,
            )
            group_store.create(
                {"groupId": "phase3_reviewers", "displayName": "Phase 3 Reviewers"}
            )
            group_store.set_members(
                "phase3_reviewers",
                [local_user["syntheticUserId"]],
            )
            manifest = generate_realm._load_manifest(self.manifest)

            first, first_connection = generate_realm.build_realm(
                manifest,
                self.environment,
                user_overlay_path,
                group_overlay_path,
            )
            second, _ = generate_realm.build_realm(
                manifest,
                self.environment,
                user_overlay_path,
                group_overlay_path,
            )

        first_group = next(group for group in first["groups"] if group["name"] == "phase3_reviewers")
        second_group = next(group for group in second["groups"] if group["name"] == "phase3_reviewers")
        generated_user = next(user for user in first["users"] if user["username"] == "alex.rivera")
        self.assertEqual(first_group["id"], second_group["id"])
        self.assertEqual(["/phase3_reviewers"], generated_user["groups"])
        self.assertEqual([], generated_user["attributes"]["eem_company_ids"])
        self.assertEqual([], generated_user["attributes"]["eem_permission_profiles"])
        self.assertEqual({"total": 28, "local": 1}, first_connection["groupInventory"])

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
