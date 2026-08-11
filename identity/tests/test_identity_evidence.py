from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from identity.configuration.oidc import OidcSettings, OidcValidationError
from identity.configuration.saml import SamlSettings, SamlValidationError
from identity.configuration.scim import ScimSettings, ScimValidationError
from identity.evidence.catalog import (
    EvidenceCatalogError,
    FAULT_CLASSES,
    generate_pairwise_cases,
    load_json_object,
    validate_coverage_catalog,
    validate_fault_catalog,
)
from identity.scripts.identity_evidence import (
    IdentityEvidenceError,
    _artifact_status,
    _assert_redacted,
    _command_results,
    compare_stable_snapshots,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "identity" / "evidence" / "coverage-catalog.json"
FAULT_PATH = REPOSITORY_ROOT / "identity" / "evidence" / "fault-fixtures.json"


class IdentityEvidenceTests(unittest.TestCase):
    def test_catalog_covers_every_declared_checkpoint_and_fault_class(self) -> None:
        coverage = load_json_object(CATALOG_PATH)
        faults = load_json_object(FAULT_PATH)

        validate_coverage_catalog(coverage, REPOSITORY_ROOT)
        validate_fault_catalog(faults)

        self.assertEqual("adr-002b-phase-9-v1", coverage["scenarioVersion"])
        for protocol in ("oidc", "saml"):
            self.assertEqual(
                FAULT_CLASSES,
                {fixture["faultClass"] for fixture in faults["protocols"][protocol]},
            )

        invalid_stable = copy.deepcopy(coverage)
        invalid_stable["stableEnvironment"]["faultControlsPermitted"] = True
        with self.assertRaises(EvidenceCatalogError):
            validate_coverage_catalog(invalid_stable, REPOSITORY_ROOT)

    def test_oidc_ordinary_settings_have_pairwise_coverage(self) -> None:
        parameters = {
            "configurationMode": ["Authority", "Discovery", "Static"],
            "parBehavior": ["UseIfAvailable", "Require", "Disable"],
            "tokenEndpointAuthMethod": ["ClientSecretPost", "ClientSecretBasic"],
            "modernConsentRequired": [False, True],
            "legacyEnabled": [False, True],
        }
        cases = generate_pairwise_cases(parameters)
        base = OidcSettings.from_environment({}).to_values()

        for case in cases:
            OidcSettings.from_values({**base, **case})

        self._assert_all_pairs(parameters, cases)
        self.assertLess(len(cases), 3 * 3 * 2 * 2 * 2)

    def test_saml_ordinary_settings_have_pairwise_coverage(self) -> None:
        parameters = {
            "standardSubjectBindingKind": ["PersistentNameId", "Attribute"],
            "standardAllowUnsolicitedResponses": [False, True],
            "standardEnableSingleLogout": [False, True],
        }
        cases = generate_pairwise_cases(parameters)
        base = SamlSettings.from_environment({}).to_values()

        for case in cases:
            values = {**base, **case}
            values["standardSubjectAttribute"] = (
                "synthetic_user_id"
                if case["standardSubjectBindingKind"] == "Attribute"
                else ""
            )
            SamlSettings.from_values(values)

        self._assert_all_pairs(parameters, cases)
        self.assertLess(len(cases), 8)

    def test_selected_security_downgrades_are_rejected(self) -> None:
        oidc = OidcSettings.from_environment({}).to_values()
        oidc["modernRedirectUris"] = ["http://example.test/callback"]
        with self.assertRaises(OidcValidationError):
            OidcSettings.from_values(oidc)

        saml = SamlSettings.from_environment({}).to_values()
        saml["standardSubjectBindingKind"] = "Attribute"
        saml["standardSubjectAttribute"] = "urn:example:unapproved"
        with self.assertRaises(SamlValidationError):
            SamlSettings.from_values(saml)

        scim = {
            "selectedConnectionKey": "eem-local",
            "connections": [
                {
                    "connectionKey": "eem-local",
                    "displayName": "Local EnergyHippo SCIM",
                    "baseUrl": "http://localdev.energyhippo.com/Public/scim/v2",
                    "expectedCompanyIds": [1],
                    "provisioningTemplate": "External only",
                    "groupBindingAttribute": "externalId",
                    "maximumPageSize": 100,
                    "requestTimeoutSeconds": 15,
                    "trustedCaCertificate": "",
                    "groupBindings": [],
                }
            ],
        }
        with self.assertRaises(ScimValidationError):
            ScimSettings.from_values(scim)

    def test_restart_comparison_requires_every_stable_value_and_outage(self) -> None:
        snapshot = {
            "capturedAtUtc": "2026-08-11T00:00:00+00:00",
            "realm": "northlake",
            "issuer": "https://localhost:8443/realms/northlake",
            "stableClients": ["modern", "saml"],
            "subjectFingerprints": {"active.subject": "a" * 64},
            "oidcSigningKeys": [{"kid": "one"}],
            "samlMetadata": {"entityId": "northlake", "documentSha256": "b" * 64},
            "configurationHash": "c" * 64,
            "keycloakImage": {"pinnedDigest": "sha256:" + "d" * 64},
        }
        after = copy.deepcopy(snapshot)
        after["capturedAtUtc"] = "2026-08-11T00:01:00+00:00"

        passed = compare_stable_snapshots(snapshot, after, outage_observed=True)
        self.assertTrue(passed["passed"])

        after["oidcSigningKeys"] = [{"kid": "two"}]
        failed = compare_stable_snapshots(snapshot, after, outage_observed=True)
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["checks"]["oidcKeysUnchanged"])

    def test_export_contract_drops_command_output_and_rejects_secret_material(self) -> None:
        commands = _command_results(
            {
                "schemaVersion": 1,
                "commands": [
                    {
                        "id": "unit-tests",
                        "passed": True,
                        "exitCode": 0,
                        "durationMilliseconds": 12,
                        "output": "must not be retained",
                    }
                ],
            }
        )

        self.assertNotIn("output", commands["unit-tests"])
        with self.assertRaises(IdentityEvidenceError):
            _assert_redacted({"password": "synthetic-value"})
        with self.assertRaises(IdentityEvidenceError):
            _assert_redacted({"message": "Bearer synthetic-value"})

    def test_browser_artifact_requires_a_nonempty_redacted_event_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "browser-evidence.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "events": [
                            {
                                "event": "authorization-completed",
                                "outcome": "login_required",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = _artifact_status(path, "browser-evidence")

        self.assertTrue(result["present"])
        self.assertTrue(result["passed"])

    def _assert_all_pairs(self, parameters, cases) -> None:  # noqa: ANN001
        names = list(parameters)
        for left_index, left_name in enumerate(names):
            for right_name in names[left_index + 1 :]:
                expected = {
                    (left_value, right_value)
                    for left_value in parameters[left_name]
                    for right_value in parameters[right_name]
                }
                actual = {(case[left_name], case[right_name]) for case in cases}
                self.assertEqual(expected, actual, f"Missing pair for {left_name}/{right_name}")


if __name__ == "__main__":
    unittest.main()
