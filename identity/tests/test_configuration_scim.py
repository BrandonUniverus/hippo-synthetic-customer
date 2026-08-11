from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from urllib import parse

from identity.configuration.scim import (
    CORE_GROUP_SCHEMA,
    CORE_USER_SCHEMA,
    LIST_RESPONSE_SCHEMA,
    PATCH_OPERATION_SCHEMA,
    SCIM_MEDIA_TYPE,
    SERVICE_PROVIDER_CONFIG_SCHEMA,
    ScimClient,
    ScimGroupBinding,
    ScimProtocolError,
    ScimResponse,
    ScimSettings,
    ScimSettingsDocument,
    ScimUserFixture,
    ScimValidationError,
    load_scim_credentials,
    load_scim_settings_document,
    safe_scim_preview,
    write_redacted_evidence,
    write_scim_credentials,
    write_scim_settings_document,
)


CREDENTIAL = "credential-key.secret-value-for-tests"
USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
GROUP_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def settings_values() -> dict[str, Any]:
    return {
        "selectedConnectionKey": "eem-local",
        "connections": [
            {
                "connectionKey": "eem-local",
                "displayName": "Local EnergyHippo SCIM",
                "baseUrl": "https://localdev.energyhippo.com/Public/scim/v2",
                "expectedCompanyIds": [2, 1],
                "provisioningTemplate": "Northlake external-only users",
                "groupBindingAttribute": "externalId",
                "maximumPageSize": 100,
                "requestTimeoutSeconds": 15,
                "trustedCaCertificate": "",
                "groupBindings": [
                    {
                        "bindingKey": "nlu-company-admins",
                        "syntheticGroupId": "nlu_company_admins",
                        "externalId": "northlake:nlu_company_admins",
                        "displayName": "NLU Company Admins",
                    }
                ],
            }
        ],
    }


def fixture() -> ScimUserFixture:
    return ScimUserFixture.from_public_user(
        {
            "syntheticUserId": "samantha.ireland",
            "username": "samantha.ireland",
            "firstName": "Samantha",
            "lastName": "Ireland",
            "email": "samantha.ireland@northlake.example.edu",
            "enabled": True,
            "attributes": {"title": "Energy Manager"},
        }
    )


class FakeScimTransport:
    def __init__(self) -> None:
        self.user: dict[str, Any] | None = None
        self.group: dict[str, Any] | None = None
        self.version = 0
        self.requests: list[tuple[str, str, Mapping[str, str], Any]] = []

    def send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: int,
    ) -> ScimResponse:
        self.assert_request(headers, timeout_seconds)
        parsed = parse.urlsplit(url)
        path = parsed.path.removeprefix("/Public/scim/v2")
        payload = json.loads(body) if body else None
        self.requests.append((method, path, dict(headers), payload))
        if method in {"PUT", "PATCH"} and "If-match" not in headers and "If-Match" not in headers:
            raise AssertionError("A SCIM replacement or patch omitted If-Match.")
        if method == "GET" and path == "/ServiceProviderConfig":
            return self.response(
                200,
                {
                    "schemas": [SERVICE_PROVIDER_CONFIG_SCHEMA],
                    "patch": {"supported": True},
                    "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
                    "filter": {"supported": True, "maxResults": 100},
                    "changePassword": {"supported": False},
                    "sort": {"supported": False},
                    "etag": {"supported": True},
                    "authenticationSchemes": [{"type": "oauthbearertoken", "primary": True}],
                },
            )
        if method == "GET" and path == "/ResourceTypes":
            return self.list_response(
                [
                    {"schemas": [], "id": "User", "name": "User", "endpoint": "/Users"},
                    {"schemas": [], "id": "Group", "name": "Group", "endpoint": "/Groups"},
                ]
            )
        if method == "GET" and path == "/Schemas":
            return self.list_response(
                [
                    {"schemas": [], "id": CORE_USER_SCHEMA, "name": "User"},
                    {"schemas": [], "id": CORE_GROUP_SCHEMA, "name": "Group"},
                ]
            )
        if method == "GET" and path == "/Users":
            return self._filtered_list(parsed.query, self.user)
        if method == "GET" and path == f"/Users/{USER_ID}" and self.user is not None:
            return self.response(200, self.user, etag=self.user["meta"]["version"])
        if method == "POST" and path == "/Users":
            self.user = self._resource(payload, USER_ID, CORE_USER_SCHEMA)
            return self.response(201, self.user, etag=self.user["meta"]["version"])
        if method == "PUT" and path == f"/Users/{USER_ID}":
            self.user = self._resource(payload, USER_ID, CORE_USER_SCHEMA)
            return self.response(200, self.user, etag=self.user["meta"]["version"])
        if method == "PATCH" and path == f"/Users/{USER_ID}":
            self._require_patch(payload)
            self.user = dict(self.user or {})
            self.user["active"] = payload["Operations"][0]["value"]
            self._version(self.user)
            return self.response(200, self.user, etag=self.user["meta"]["version"])
        if method == "GET" and path == "/Groups":
            return self._filtered_list(parsed.query, self.group)
        if method == "POST" and path == "/Groups":
            self.group = self._resource(payload, GROUP_ID, CORE_GROUP_SCHEMA)
            return self.response(201, self.group, etag=self.group["meta"]["version"])
        if method == "PATCH" and path == f"/Groups/{GROUP_ID}":
            self._require_patch(payload)
            self.group = dict(self.group or {})
            operation = payload["Operations"][0]
            member = operation["value"][0]
            members = [value for value in self.group.get("members", []) if value["value"] != member["value"]]
            if operation["op"] == "add":
                members.append(member)
            self.group["members"] = members
            self._version(self.group)
            return self.response(200, self.group, etag=self.group["meta"]["version"])
        return self.response(
            404,
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "status": "404",
            },
        )

    def assert_request(self, headers: Mapping[str, str], timeout_seconds: int) -> None:
        if headers.get("Authorization") != "Bearer " + CREDENTIAL:
            raise AssertionError("The SCIM bearer credential was missing.")
        if headers.get("Accept") != SCIM_MEDIA_TYPE:
            raise AssertionError("The SCIM Accept header was missing.")
        if timeout_seconds != 15:
            raise AssertionError("The configured request timeout was not used.")

    def response(
        self,
        status: int,
        payload: Any,
        *,
        etag: str | None = None,
    ) -> ScimResponse:
        headers = {"content-type": SCIM_MEDIA_TYPE}
        if etag:
            headers["etag"] = etag
        return ScimResponse(status, headers, payload, 3)

    def list_response(self, resources: list[dict[str, Any]]) -> ScimResponse:
        return self.response(
            200,
            {
                "schemas": [LIST_RESPONSE_SCHEMA],
                "totalResults": len(resources),
                "startIndex": 1,
                "itemsPerPage": len(resources),
                "Resources": resources,
            },
        )

    def _filtered_list(self, query: str, resource: dict[str, Any] | None) -> ScimResponse:
        resources = [] if resource is None else [resource]
        return self.list_response(resources)

    def _resource(self, payload: Mapping[str, Any], resource_id: str, schema: str) -> dict[str, Any]:
        if schema not in payload.get("schemas", []):
            raise AssertionError("The expected core schema was missing.")
        resource = dict(payload)
        resource["id"] = resource_id
        self._version(resource)
        return resource

    def _version(self, resource: dict[str, Any]) -> None:
        self.version += 1
        resource["meta"] = {"version": f'W/"{self.version:016x}"'}

    def _require_patch(self, payload: Mapping[str, Any]) -> None:
        if payload.get("schemas") != [PATCH_OPERATION_SCHEMA]:
            raise AssertionError("The PATCH schema was missing.")


class ConfigurationScimTests(unittest.TestCase):
    def test_settings_are_typed_multi_connection_and_secret_free(self) -> None:
        values = settings_values()
        second = dict(values["connections"][0])
        second.update(
            {
                "connectionKey": "eem-second",
                "displayName": "Second connection",
                "baseUrl": "https://second.example.test/scim/v2",
                "expectedCompanyIds": [3],
                "groupBindings": [],
            }
        )
        values["connections"].append(second)
        settings = ScimSettings.from_values(values)
        preview = safe_scim_preview(settings, {"eem-local": True, "eem-second": False})

        self.assertEqual((1, 2), settings.connection().expected_company_ids)
        self.assertEqual(2, len(settings.connections))
        self.assertTrue(preview["redacted"])
        self.assertNotIn(CREDENTIAL, json.dumps(preview))
        self.assertIn("[stored separately]", json.dumps(preview))

    def test_settings_reject_http_unknown_fields_and_duplicate_scope(self) -> None:
        values = settings_values()
        values["connections"][0]["baseUrl"] = "http://localhost/scim/v2"
        with self.assertRaises(ScimValidationError):
            ScimSettings.from_values(values)

        values = settings_values()
        values["connections"][0]["unexpected"] = True
        with self.assertRaises(ScimValidationError):
            ScimSettings.from_values(values)

        values = settings_values()
        values["connections"][0]["expectedCompanyIds"] = [1, 1]
        with self.assertRaises(ScimValidationError):
            ScimSettings.from_values(values)

    def test_settings_and_credentials_use_separate_ignored_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "scim.json"
            credential_path = root / "scim-credentials.json"
            settings = ScimSettings.from_values(settings_values())
            write_scim_settings_document(settings_path, ScimSettingsDocument(settings))
            write_scim_credentials(credential_path, {"eem-local": CREDENTIAL})

            loaded = load_scim_settings_document(settings_path, {})
            credentials = load_scim_credentials(credential_path)

            self.assertEqual("eem-local", loaded.settings.selected_connection_key)
            self.assertEqual(CREDENTIAL, credentials["eem-local"])
            self.assertNotIn(CREDENTIAL, settings_path.read_text(encoding="utf-8"))

    def test_discovery_and_full_user_group_lifecycle_pass_with_redacted_evidence(self) -> None:
        settings = ScimSettings.from_values(settings_values())
        transport = FakeScimTransport()
        client = ScimClient(settings.connection(), CREDENTIAL, transport)

        result = client.run_lifecycle(
            fixture(),
            settings.connection().binding("nlu-company-admins"),
        )

        self.assertTrue(result["passed"])
        self.assertEqual(
            "scim-lifecycle-passed-authentication-proof-required",
            result["classification"],
        )
        self.assertTrue(result["finalState"]["userActive"])
        self.assertTrue(result["finalState"]["groupMembershipPresent"])
        self.assertEqual("authentication-proof-required", result["crossProtocol"]["status"])
        serialized = json.dumps(result)
        self.assertNotIn(CREDENTIAL, serialized)
        self.assertNotIn(fixture().email, serialized)
        self.assertNotIn(fixture().user_name, serialized)
        self.assertEqual(USER_ID, result["userResourceId"])
        self.assertEqual(GROUP_ID, result["groupResourceId"])
        self.assertTrue(any(request_item[0] == "PUT" for request_item in transport.requests))
        self.assertEqual(4, sum(request_item[0] == "PATCH" for request_item in transport.requests))

    def test_protocol_failure_is_classified_without_body_or_credential(self) -> None:
        class RejectingTransport(FakeScimTransport):
            def send(self, method, url, headers, body, timeout_seconds):  # noqa: ANN001
                return self.response(
                    401,
                    {
                        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                        "detail": "reflected synthetic user value",
                        "status": "401",
                    },
                )

        settings = ScimSettings.from_values(settings_values())
        client = ScimClient(settings.connection(), CREDENTIAL, RejectingTransport())

        with self.assertRaises(ScimProtocolError) as captured:
            client.discover()

        evidence = captured.exception.evidence()
        self.assertEqual("credential-rejected", evidence["classification"])
        self.assertNotIn(CREDENTIAL, json.dumps(evidence))
        self.assertNotIn("reflected synthetic user value", json.dumps(evidence))

    def test_discovery_rejects_missing_bearer_advertisement(self) -> None:
        class MissingBearerTransport(FakeScimTransport):
            def send(self, method, url, headers, body, timeout_seconds):  # noqa: ANN001
                response = super().send(method, url, headers, body, timeout_seconds)
                if parse.urlsplit(url).path.endswith("/ServiceProviderConfig"):
                    payload = dict(response.payload)
                    payload["authenticationSchemes"] = []
                    return ScimResponse(
                        response.status,
                        response.headers,
                        payload,
                        response.elapsed_milliseconds,
                    )
                return response

        settings = ScimSettings.from_values(settings_values())
        client = ScimClient(settings.connection(), CREDENTIAL, MissingBearerTransport())

        with self.assertRaises(ScimProtocolError) as captured:
            client.discover()

        self.assertEqual("unsupported-service-contract", captured.exception.classification)

    def test_nonconforming_scim_error_is_rejected(self) -> None:
        class InvalidErrorTransport(FakeScimTransport):
            def send(self, method, url, headers, body, timeout_seconds):  # noqa: ANN001
                return self.response(401, {"status": "403"})

        settings = ScimSettings.from_values(settings_values())
        client = ScimClient(settings.connection(), CREDENTIAL, InvalidErrorTransport())

        with self.assertRaises(ScimProtocolError) as captured:
            client.discover()

        self.assertEqual("invalid-provider-response", captured.exception.classification)

    def test_evidence_writer_rejects_bearer_material(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "result.json"
            with self.assertRaises(RuntimeError):
                write_redacted_evidence(output, {"header": "Bearer " + CREDENTIAL})
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
