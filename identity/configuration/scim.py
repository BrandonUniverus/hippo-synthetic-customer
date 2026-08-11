"""Typed SCIM 2.0 client configuration and deterministic lifecycle runner.

Northlake is the provisioning client. EnergyHippo remains the SCIM service
provider, and Keycloak remains the OIDC/SAML identity provider.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib import error, parse, request


CORE_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
CORE_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
SERVICE_PROVIDER_CONFIG_SCHEMA = (
    "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"
)
LIST_RESPONSE_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
PATCH_OPERATION_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_MEDIA_TYPE = "application/scim+json"

_CONNECTION_KEY = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
_BINDING_KEY = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_CERTIFICATE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_CONNECTION_KEYS = {
    "connectionKey",
    "displayName",
    "baseUrl",
    "expectedCompanyIds",
    "provisioningTemplate",
    "groupBindingAttribute",
    "maximumPageSize",
    "requestTimeoutSeconds",
    "trustedCaCertificate",
    "groupBindings",
}
_ALLOWED_BINDING_KEYS = {
    "bindingKey",
    "syntheticGroupId",
    "externalId",
    "displayName",
}


class ScimValidationError(ValueError):
    """Raised when the ignored local SCIM configuration is invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__(next(iter(self.errors.values()), "Invalid SCIM configuration."))


class ScimProtocolError(RuntimeError):
    """A redacted SCIM transport or protocol failure."""

    def __init__(
        self,
        message: str,
        *,
        classification: str,
        status: int | None = None,
        scim_type: str | None = None,
    ):
        self.classification = classification
        self.status = status
        self.scim_type = scim_type
        super().__init__(message)

    def evidence(self) -> dict[str, Any]:
        return {
            "passed": False,
            "classification": self.classification,
            "status": self.status,
            "scimType": self.scim_type,
            "message": str(self),
        }


@dataclass(frozen=True)
class ScimGroupBinding:
    binding_key: str
    synthetic_group_id: str
    external_id: str
    display_name: str

    @classmethod
    def from_values(cls, values: Any, index: int) -> "ScimGroupBinding":
        field = f"connections.groupBindings[{index}]"
        if not isinstance(values, Mapping):
            raise ScimValidationError({field: "Each group binding must be an object."})
        extra = set(values) - _ALLOWED_BINDING_KEYS
        if extra:
            raise ScimValidationError(
                {field: "Unknown group-binding values are not allowed: " + ", ".join(sorted(extra))}
            )
        binding_key = _required_string(values, "bindingKey", field, 64)
        if not _BINDING_KEY.fullmatch(binding_key):
            raise ScimValidationError(
                {field: "bindingKey must use lowercase letters, digits, and hyphens."}
            )
        synthetic_group_id = _required_string(values, "syntheticGroupId", field, 128)
        external_id = _required_string(values, "externalId", field, 256)
        display_name = _required_string(values, "displayName", field, 256)
        return cls(binding_key, synthetic_group_id, external_id, display_name)

    def to_values(self) -> dict[str, str]:
        return {
            "bindingKey": self.binding_key,
            "syntheticGroupId": self.synthetic_group_id,
            "externalId": self.external_id,
            "displayName": self.display_name,
        }


@dataclass(frozen=True)
class ScimConnectionSettings:
    connection_key: str
    display_name: str
    base_url: str
    expected_company_ids: tuple[int, ...]
    provisioning_template: str
    group_binding_attribute: str
    maximum_page_size: int
    request_timeout_seconds: int
    trusted_ca_certificate: str | None
    group_bindings: tuple[ScimGroupBinding, ...]

    @classmethod
    def from_values(cls, values: Any, index: int) -> "ScimConnectionSettings":
        field = f"connections[{index}]"
        if not isinstance(values, Mapping):
            raise ScimValidationError({field: "Each SCIM connection must be an object."})
        extra = set(values) - _ALLOWED_CONNECTION_KEYS
        if extra:
            raise ScimValidationError(
                {field: "Unknown connection values are not allowed: " + ", ".join(sorted(extra))}
            )
        connection_key = _required_string(values, "connectionKey", field, 32)
        if not _CONNECTION_KEY.fullmatch(connection_key):
            raise ScimValidationError(
                {field: "connectionKey must use lowercase letters, digits, and hyphens."}
            )
        display_name = _required_string(values, "displayName", field, 128)
        base_url = _validated_base_url(values.get("baseUrl"), field)
        company_values = values.get("expectedCompanyIds")
        if (
            not isinstance(company_values, list)
            or not company_values
            or len(company_values) > 100
            or any(not isinstance(company_id, int) or isinstance(company_id, bool) or company_id <= 0 for company_id in company_values)
            or len(set(company_values)) != len(company_values)
        ):
            raise ScimValidationError(
                {field: "expectedCompanyIds must contain unique positive integer company IDs."}
            )
        provisioning_template = _required_string(values, "provisioningTemplate", field, 128)
        group_binding_attribute = values.get("groupBindingAttribute")
        if group_binding_attribute not in {"externalId", "displayName"}:
            raise ScimValidationError(
                {field: "groupBindingAttribute must be externalId or displayName."}
            )
        maximum_page_size = _bounded_integer(values, "maximumPageSize", field, 1, 1000)
        request_timeout_seconds = _bounded_integer(
            values, "requestTimeoutSeconds", field, 2, 120
        )
        trusted_ca_value = values.get("trustedCaCertificate")
        trusted_ca_certificate: str | None
        if trusted_ca_value in {None, ""}:
            trusted_ca_certificate = None
        elif not isinstance(trusted_ca_value, str) or not _CERTIFICATE_NAME.fullmatch(
            trusted_ca_value
        ) or Path(trusted_ca_value).suffix.lower() not in {".pem", ".crt"}:
            raise ScimValidationError(
                {field: "trustedCaCertificate must be one safe filename in the runtime certs folder."}
            )
        else:
            trusted_ca_certificate = trusted_ca_value
        binding_values = values.get("groupBindings", [])
        if not isinstance(binding_values, list) or len(binding_values) > 100:
            raise ScimValidationError({field: "groupBindings must be a list of at most 100 bindings."})
        group_bindings = tuple(
            ScimGroupBinding.from_values(binding, binding_index)
            for binding_index, binding in enumerate(binding_values)
        )
        binding_keys = [binding.binding_key for binding in group_bindings]
        synthetic_group_ids = [binding.synthetic_group_id for binding in group_bindings]
        if len(set(binding_keys)) != len(binding_keys):
            raise ScimValidationError({field: "Group binding keys must be unique."})
        if len(set(synthetic_group_ids)) != len(synthetic_group_ids):
            raise ScimValidationError({field: "Synthetic groups may be bound only once per connection."})
        selected_values = [
            binding.external_id if group_binding_attribute == "externalId" else binding.display_name
            for binding in group_bindings
        ]
        if len({value.casefold() for value in selected_values}) != len(selected_values):
            raise ScimValidationError(
                {field: f"Group {group_binding_attribute} values must be unique per connection."}
            )
        return cls(
            connection_key,
            display_name,
            base_url,
            tuple(sorted(company_values)),
            provisioning_template,
            group_binding_attribute,
            maximum_page_size,
            request_timeout_seconds,
            trusted_ca_certificate,
            group_bindings,
        )

    def to_values(self) -> dict[str, Any]:
        return {
            "connectionKey": self.connection_key,
            "displayName": self.display_name,
            "baseUrl": self.base_url,
            "expectedCompanyIds": list(self.expected_company_ids),
            "provisioningTemplate": self.provisioning_template,
            "groupBindingAttribute": self.group_binding_attribute,
            "maximumPageSize": self.maximum_page_size,
            "requestTimeoutSeconds": self.request_timeout_seconds,
            "trustedCaCertificate": self.trusted_ca_certificate or "",
            "groupBindings": [binding.to_values() for binding in self.group_bindings],
        }

    def binding(self, binding_key: str) -> ScimGroupBinding:
        matches = [binding for binding in self.group_bindings if binding.binding_key == binding_key]
        if len(matches) != 1:
            raise ScimValidationError(
                {"groupBindingKey": "Select one configured sanctioned-group binding."}
            )
        return matches[0]


@dataclass(frozen=True)
class ScimSettings:
    selected_connection_key: str
    connections: tuple[ScimConnectionSettings, ...]

    @classmethod
    def from_values(cls, values: Any) -> "ScimSettings":
        if not isinstance(values, Mapping):
            raise ScimValidationError({"_form": "SCIM settings must be an object."})
        extra = set(values) - {"selectedConnectionKey", "connections", "credential"}
        if extra:
            raise ScimValidationError(
                {"_form": "Unknown SCIM values are not allowed: " + ", ".join(sorted(extra))}
            )
        connection_values = values.get("connections")
        if not isinstance(connection_values, list) or not 1 <= len(connection_values) <= 8:
            raise ScimValidationError(
                {"connections": "Configure between one and eight SCIM connections."}
            )
        connections = tuple(
            ScimConnectionSettings.from_values(connection, index)
            for index, connection in enumerate(connection_values)
        )
        keys = [connection.connection_key for connection in connections]
        if len(set(keys)) != len(keys):
            raise ScimValidationError({"connections": "SCIM connection keys must be unique."})
        selected_connection_key = values.get("selectedConnectionKey")
        if not isinstance(selected_connection_key, str) or selected_connection_key not in keys:
            raise ScimValidationError(
                {"selectedConnectionKey": "Select one configured SCIM connection."}
            )
        credential = values.get("credential", "")
        if credential is not None and credential != "":
            _validate_credential(credential)
        return cls(selected_connection_key, connections)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "ScimSettings":
        company_text = environment.get("EEMSUITE_SCIM_EXPECTED_COMPANY_IDS", "1")
        try:
            company_ids = [int(value.strip()) for value in company_text.split(",") if value.strip()]
        except ValueError as failure:
            raise ScimValidationError(
                {"expectedCompanyIds": "EEMSUITE_SCIM_EXPECTED_COMPANY_IDS is invalid."}
            ) from failure
        values = {
            "selectedConnectionKey": "eem-local",
            "connections": [
                {
                    "connectionKey": "eem-local",
                    "displayName": "Local EnergyHippo SCIM",
                    "baseUrl": environment.get(
                        "EEMSUITE_SCIM_BASE_URL",
                        "https://localdev.energyhippo.com/Public/scim/v2",
                    ),
                    "expectedCompanyIds": company_ids,
                    "provisioningTemplate": environment.get(
                        "EEMSUITE_SCIM_PROVISIONING_TEMPLATE",
                        "Northlake external-only users",
                    ),
                    "groupBindingAttribute": environment.get(
                        "EEMSUITE_SCIM_GROUP_BINDING_ATTRIBUTE", "externalId"
                    ),
                    "maximumPageSize": 100,
                    "requestTimeoutSeconds": 15,
                    "trustedCaCertificate": environment.get(
                        "EEMSUITE_SCIM_TRUSTED_CA_CERTIFICATE", ""
                    ),
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
        return cls.from_values(values)

    def connection(self, connection_key: str | None = None) -> ScimConnectionSettings:
        selected = connection_key or self.selected_connection_key
        matches = [connection for connection in self.connections if connection.connection_key == selected]
        if len(matches) != 1:
            raise ScimValidationError(
                {"selectedConnectionKey": "Select one configured SCIM connection."}
            )
        return matches[0]

    def to_values(self) -> dict[str, Any]:
        return {
            "selectedConnectionKey": self.selected_connection_key,
            "connections": [connection.to_values() for connection in self.connections],
        }


@dataclass(frozen=True)
class ScimSettingsDocument:
    settings: ScimSettings
    updated_at_utc: str | None = None


@dataclass(frozen=True)
class ScimUserFixture:
    synthetic_user_id: str
    external_id: str
    user_name: str
    given_name: str
    family_name: str
    display_name: str
    email: str
    title: str
    active: bool

    @classmethod
    def from_public_user(cls, user: Mapping[str, Any]) -> "ScimUserFixture":
        synthetic_user_id = _required_public_string(user, "syntheticUserId")
        user_name = _required_public_string(user, "username")
        given_name = _required_public_string(user, "firstName")
        family_name = _required_public_string(user, "lastName")
        email = _required_public_string(user, "email")
        attributes = user.get("attributes")
        title = attributes.get("title", "") if isinstance(attributes, Mapping) else ""
        if not isinstance(title, str):
            title = ""
        active = user.get("enabled")
        if not isinstance(active, bool):
            raise ScimValidationError({"syntheticUserId": "The synthetic user is malformed."})
        return cls(
            synthetic_user_id,
            f"northlake:{synthetic_user_id}",
            user_name,
            given_name,
            family_name,
            f"{given_name} {family_name}".strip(),
            email,
            title,
            active,
        )

    def resource(self, *, active: bool | None = None) -> dict[str, Any]:
        return {
            "schemas": [CORE_USER_SCHEMA],
            "externalId": self.external_id,
            "userName": self.user_name,
            "active": self.active if active is None else active,
            "name": {
                "givenName": self.given_name,
                "familyName": self.family_name,
                "formatted": self.display_name,
            },
            "displayName": self.display_name,
            "title": self.title,
            "emails": [{"value": self.email, "type": "work", "primary": True}],
        }


@dataclass(frozen=True)
class ScimResponse:
    status: int
    headers: Mapping[str, str]
    payload: Any
    elapsed_milliseconds: int


class ScimTransport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: int,
    ) -> ScimResponse: ...


class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class UrlLibScimTransport:
    """HTTPS transport that never follows redirects with a bearer credential."""

    def __init__(self, trusted_ca_path: Path | None = None):
        context = ssl.create_default_context()
        if trusted_ca_path is not None:
            try:
                context.load_verify_locations(cafile=str(trusted_ca_path))
            except (OSError, ssl.SSLError) as failure:
                raise ScimProtocolError(
                    "The configured SCIM trust certificate could not be loaded.",
                    classification="tls-configuration-error",
                ) from failure
        self.opener = request.build_opener(
            _NoRedirectHandler(),
            request.HTTPSHandler(context=context),
        )

    def send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: int,
    ) -> ScimResponse:
        started = time.monotonic()
        http_request = request.Request(url, data=body, method=method, headers=dict(headers))
        try:
            with self.opener.open(http_request, timeout=timeout_seconds) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ScimProtocolError(
                        "The SCIM response exceeded the two-megabyte test limit.",
                        classification="invalid-provider-response",
                    )
                return _scim_response(response.status, response.headers, raw, started)
        except error.HTTPError as failure:
            raw = failure.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raw = b""
            return _scim_response(failure.code, failure.headers, raw, started)
        except ssl.SSLCertVerificationError as failure:
            raise ScimProtocolError(
                "The SCIM service certificate is not trusted or does not match its hostname.",
                classification="tls-verification-failed",
            ) from failure
        except (error.URLError, TimeoutError, OSError) as failure:
            reason = getattr(failure, "reason", failure)
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise ScimProtocolError(
                    "The SCIM service certificate is not trusted or does not match its hostname.",
                    classification="tls-verification-failed",
                ) from failure
            raise ScimProtocolError(
                "The configured SCIM service is unavailable.",
                classification="service-unavailable",
            ) from failure


class ScimClient:
    def __init__(
        self,
        connection: ScimConnectionSettings,
        credential: str,
        transport: ScimTransport,
    ):
        _validate_credential(credential)
        self.connection = connection
        self.credential = credential
        self.transport = transport

    def discover(self) -> dict[str, Any]:
        config_response = self._request("GET", "/ServiceProviderConfig")
        resource_types_response = self._request("GET", "/ResourceTypes")
        schemas_response = self._request("GET", "/Schemas")
        config = _required_object(config_response.payload, "ServiceProviderConfig")
        _require_schema(config, SERVICE_PROVIDER_CONFIG_SCHEMA, "ServiceProviderConfig")
        resource_types = _list_resources(resource_types_response.payload, "ResourceTypes")
        schemas = _list_resources(schemas_response.payload, "Schemas")
        resource_type_names = sorted(
            value.get("name")
            for value in resource_types
            if isinstance(value, Mapping) and isinstance(value.get("name"), str)
        )
        schema_ids = sorted(
            value.get("id")
            for value in schemas
            if isinstance(value, Mapping) and isinstance(value.get("id"), str)
        )
        if "User" not in resource_type_names or CORE_USER_SCHEMA not in schema_ids:
            raise ScimProtocolError(
                "SCIM discovery does not advertise the required User resource.",
                classification="unsupported-service-contract",
            )
        patch_supported = _feature_supported(config, "patch")
        filter_value = config.get("filter")
        filter_supported = isinstance(filter_value, Mapping) and filter_value.get("supported") is True
        advertised_maximum = filter_value.get("maxResults") if isinstance(filter_value, Mapping) else None
        etag_supported = _feature_supported(config, "etag")
        authentication_schemes = config.get("authenticationSchemes")
        bearer_advertised = isinstance(authentication_schemes, list) and any(
            isinstance(scheme, Mapping)
            and isinstance(scheme.get("type"), str)
            and scheme["type"].casefold() == "oauthbearertoken"
            for scheme in authentication_schemes
        )
        if not patch_supported or not filter_supported or not etag_supported or not bearer_advertised:
            raise ScimProtocolError(
                "SCIM discovery is missing bearer authentication, PATCH, filter, or ETag support required by this lifecycle.",
                classification="unsupported-service-contract",
            )
        if not isinstance(advertised_maximum, int) or advertised_maximum < 1:
            raise ScimProtocolError(
                "SCIM discovery returned no valid filter result limit.",
                classification="invalid-provider-response",
            )
        if advertised_maximum > self.connection.maximum_page_size:
            raise ScimProtocolError(
                "The service advertises a page limit above the configured Northlake safety ceiling.",
                classification="limit-mismatch",
            )
        return {
            "passed": True,
            "classification": "discovery-passed",
            "resourceTypes": resource_type_names,
            "schemas": schema_ids,
            "features": {
                "patch": patch_supported,
                "filter": filter_supported,
                "etag": etag_supported,
                "bearerAuthentication": bearer_advertised,
                "bulk": _feature_supported(config, "bulk"),
                "changePassword": _feature_supported(config, "changePassword"),
                "sort": _feature_supported(config, "sort"),
                "maximumPageSize": advertised_maximum,
            },
            "requests": [
                _response_evidence("ServiceProviderConfig", config_response),
                _response_evidence("ResourceTypes", resource_types_response),
                _response_evidence("Schemas", schemas_response),
            ],
        }

    def find_user(self, attribute: str, value: str) -> dict[str, Any] | None:
        if attribute not in {"externalId", "userName"}:
            raise ValueError("Unsupported SCIM User lookup attribute.")
        response = self._request(
            "GET",
            "/Users",
            query={"filter": f'{attribute} eq "{_filter_value(value)}"', "count": "2"},
        )
        resources = _list_resources(response.payload, "Users")
        if len(resources) > 1:
            raise ScimProtocolError(
                "The SCIM User lookup returned more than one resource.",
                classification="non-unique-provider-state",
            )
        return resources[0] if resources else None

    def create_user(self, fixture: ScimUserFixture) -> tuple[dict[str, Any], str | None, ScimResponse]:
        response = self._request("POST", "/Users", payload=fixture.resource(), expected=(201,))
        resource = _required_resource(response.payload, CORE_USER_SCHEMA, "User")
        return resource, _etag(response), response

    def get_user(self, resource_id: str) -> tuple[dict[str, Any], str | None, ScimResponse]:
        response = self._request("GET", f"/Users/{_resource_id(resource_id)}")
        return _required_resource(response.payload, CORE_USER_SCHEMA, "User"), _etag(response), response

    def replace_user(
        self,
        resource_id: str,
        fixture: ScimUserFixture,
        etag: str | None,
    ) -> tuple[dict[str, Any], str | None, ScimResponse]:
        response = self._request(
            "PUT",
            f"/Users/{_resource_id(resource_id)}",
            payload=fixture.resource(),
            etag=etag,
        )
        return _required_resource(response.payload, CORE_USER_SCHEMA, "User"), _etag(response), response

    def set_user_active(
        self,
        resource_id: str,
        active: bool,
        etag: str | None,
    ) -> tuple[dict[str, Any], str | None, ScimResponse]:
        response = self._request(
            "PATCH",
            f"/Users/{_resource_id(resource_id)}",
            payload={
                "schemas": [PATCH_OPERATION_SCHEMA],
                "Operations": [{"op": "replace", "path": "active", "value": active}],
            },
            etag=etag,
        )
        return _required_resource(response.payload, CORE_USER_SCHEMA, "User"), _etag(response), response

    def find_group(self, binding: ScimGroupBinding) -> dict[str, Any] | None:
        attribute = self.connection.group_binding_attribute
        value = binding.external_id if attribute == "externalId" else binding.display_name
        response = self._request(
            "GET",
            "/Groups",
            query={"filter": f'{attribute} eq "{_filter_value(value)}"', "count": "2"},
        )
        resources = _list_resources(response.payload, "Groups")
        if len(resources) > 1:
            raise ScimProtocolError(
                "The SCIM Group lookup returned more than one resource.",
                classification="non-unique-provider-state",
            )
        return resources[0] if resources else None

    def create_group(
        self,
        binding: ScimGroupBinding,
        member_id: str,
    ) -> tuple[dict[str, Any], str | None, ScimResponse]:
        response = self._request(
            "POST",
            "/Groups",
            payload={
                "schemas": [CORE_GROUP_SCHEMA],
                "externalId": binding.external_id,
                "displayName": binding.display_name,
                "members": [{"value": _resource_id(member_id)}],
            },
            expected=(201,),
        )
        return _required_resource(response.payload, CORE_GROUP_SCHEMA, "Group"), _etag(response), response

    def change_group_member(
        self,
        group_id: str,
        member_id: str,
        *,
        add: bool,
        etag: str | None,
    ) -> tuple[dict[str, Any], str | None, ScimResponse]:
        response = self._request(
            "PATCH",
            f"/Groups/{_resource_id(group_id)}",
            payload={
                "schemas": [PATCH_OPERATION_SCHEMA],
                "Operations": [
                    {
                        "op": "add" if add else "remove",
                        "path": "members",
                        "value": [{"value": _resource_id(member_id)}],
                    }
                ],
            },
            etag=etag,
        )
        return _required_resource(response.payload, CORE_GROUP_SCHEMA, "Group"), _etag(response), response

    def run_lifecycle(
        self,
        fixture: ScimUserFixture,
        binding: ScimGroupBinding | None,
    ) -> dict[str, Any]:
        discovery = self.discover()
        steps: list[dict[str, Any]] = []
        user = self.find_user("externalId", fixture.external_id)
        if user is None:
            user, user_etag, response = self.create_user(fixture)
            steps.append(_response_evidence("user-created", response))
        else:
            user_etag = _resource_etag(user)
            steps.append({"step": "user-reconciled", "status": 200})
        user_id = _resource_id_value(user, "User")
        filtered = self.find_user("userName", fixture.user_name)
        if filtered is None or _resource_id_value(filtered, "User") != user_id:
            raise ScimProtocolError(
                "The userName filter did not return the provisioned User.",
                classification="correlation-mismatch",
            )
        steps.append({"step": "user-filter-correlated", "status": 200})
        user, user_etag, response = self.replace_user(user_id, fixture, user_etag)
        steps.append(_response_evidence("user-replaced", response))
        user, user_etag, response = self.set_user_active(user_id, False, user_etag)
        if user.get("active") is not False:
            raise ScimProtocolError(
                "The SCIM User did not become inactive.",
                classification="lifecycle-state-mismatch",
            )
        steps.append(_response_evidence("user-deactivated", response))
        user, user_etag, response = self.set_user_active(user_id, True, user_etag)
        if user.get("active") is not True:
            raise ScimProtocolError(
                "The SCIM User did not become active again.",
                classification="lifecycle-state-mismatch",
            )
        steps.append(_response_evidence("user-reactivated", response))

        group_id: str | None = None
        if binding is not None:
            group = self.find_group(binding)
            if group is None:
                group, group_etag, response = self.create_group(binding, user_id)
                steps.append(_response_evidence("group-bound", response))
            else:
                group_etag = _resource_etag(group)
                steps.append({"step": "group-reconciled", "status": 200})
            group_id = _resource_id_value(group, "Group")
            group, group_etag, response = self.change_group_member(
                group_id, user_id, add=False, etag=group_etag
            )
            steps.append(_response_evidence("group-member-removed", response))
            group, group_etag, response = self.change_group_member(
                group_id, user_id, add=True, etag=group_etag
            )
            steps.append(_response_evidence("group-member-restored", response))
            member_ids = {
                member.get("value")
                for member in group.get("members", [])
                if isinstance(member, Mapping)
            }
            if user_id not in member_ids:
                raise ScimProtocolError(
                    "The final SCIM Group representation omitted the provisioned User.",
                    classification="group-state-mismatch",
                )

        return {
            "passed": True,
            "classification": "scim-lifecycle-passed-authentication-proof-required",
            "checkedAtUtc": datetime.now(UTC).isoformat(),
            "connectionKey": self.connection.connection_key,
            "companyScopeCount": len(self.connection.expected_company_ids),
            "userResourceId": user_id,
            "groupResourceId": group_id,
            "finalState": {
                "userActive": True,
                "groupMembershipPresent": group_id is not None,
            },
            "discovery": discovery,
            "steps": steps,
            "crossProtocol": {
                "status": "authentication-proof-required",
                "next": "Authenticate this synthetic subject through the configured OIDC or SAML provider, then deactivate it and prove EEM denies the next local session decision.",
            },
            "redacted": True,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
        etag: str | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> ScimResponse:
        if not path.startswith("/") or ".." in path:
            raise ValueError("Unsafe SCIM request path.")
        url = self.connection.base_url + path
        if query:
            url += "?" + parse.urlencode(query)
        headers = {
            "Authorization": "Bearer " + self.credential,
            "Accept": SCIM_MEDIA_TYPE,
            "User-Agent": "Northlake-Synthetic-SCIM/1.0",
        }
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = SCIM_MEDIA_TYPE
        if etag:
            if "\r" in etag or "\n" in etag or len(etag) > 256:
                raise ScimProtocolError(
                    "The SCIM service returned an unsafe ETag.",
                    classification="invalid-provider-response",
                )
            headers["If-Match"] = etag
        response = self.transport.send(
            method,
            url,
            headers,
            body,
            self.connection.request_timeout_seconds,
        )
        if response.status not in expected:
            raise _protocol_failure(response)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if response.status != 204 and content_type != SCIM_MEDIA_TYPE:
            raise ScimProtocolError(
                "The SCIM service returned an unsupported content type.",
                classification="invalid-provider-response",
                status=response.status,
            )
        return response


def load_scim_settings_document(
    path: Path,
    environment: Mapping[str, str],
) -> ScimSettingsDocument:
    if not path.is_file():
        return ScimSettingsDocument(ScimSettings.from_environment(environment))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise ScimValidationError({"_form": "The saved SCIM settings cannot be read."}) from failure
    if not isinstance(payload, Mapping) or payload.get("schemaVersion") != 1:
        raise ScimValidationError({"_form": "The saved SCIM settings use an unsupported schema."})
    return ScimSettingsDocument(
        ScimSettings.from_values(payload.get("values")),
        payload.get("updatedAtUtc") if isinstance(payload.get("updatedAtUtc"), str) else None,
    )


def write_scim_settings_document(path: Path, document: ScimSettingsDocument) -> None:
    payload = {
        "schemaVersion": 1,
        "updatedAtUtc": document.updated_at_utc or datetime.now(UTC).isoformat(),
        "values": document.settings.to_values(),
    }
    _atomic_json(path, payload, secret=False)


def load_scim_credentials(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise ScimValidationError({"credential": "The saved SCIM credential store cannot be read."}) from failure
    if not isinstance(payload, Mapping) or payload.get("schemaVersion") != 1:
        raise ScimValidationError({"credential": "The saved SCIM credential store is invalid."})
    values = payload.get("credentials")
    if not isinstance(values, Mapping):
        raise ScimValidationError({"credential": "The saved SCIM credential store is invalid."})
    credentials: dict[str, str] = {}
    for key, credential in values.items():
        if not isinstance(key, str) or not _CONNECTION_KEY.fullmatch(key):
            raise ScimValidationError({"credential": "The saved SCIM credential store is invalid."})
        _validate_credential(credential)
        credentials[key] = credential
    return credentials


def write_scim_credentials(path: Path, credentials: Mapping[str, str]) -> None:
    for key, credential in credentials.items():
        if not _CONNECTION_KEY.fullmatch(key):
            raise ScimValidationError({"credential": "The SCIM credential key is invalid."})
        _validate_credential(credential)
    _atomic_json(
        path,
        {"schemaVersion": 1, "credentials": dict(sorted(credentials.items()))},
        secret=True,
    )


def create_scim_client(
    connection: ScimConnectionSettings,
    credential: str,
    runtime_directory: Path,
) -> ScimClient:
    trusted_ca_path = None
    if connection.trusted_ca_certificate:
        trusted_ca_path = runtime_directory / "certs" / connection.trusted_ca_certificate
        if not trusted_ca_path.is_file():
            raise ScimProtocolError(
                "The configured SCIM trust certificate is missing from the runtime certs folder.",
                classification="tls-configuration-error",
            )
    return ScimClient(connection, credential, UrlLibScimTransport(trusted_ca_path))


def safe_scim_preview(
    settings: ScimSettings,
    credential_status: Mapping[str, bool],
) -> dict[str, Any]:
    return {
        "role": "SCIM 2.0 client",
        "serviceProvider": "EnergyHippo",
        "authenticationProvider": "Northlake Keycloak (separate)",
        "selectedConnectionKey": settings.selected_connection_key,
        "connections": [
            {
                **connection.to_values(),
                "credentialConfigured": bool(credential_status.get(connection.connection_key)),
                "credential": "[stored separately]" if credential_status.get(connection.connection_key) else "[not configured]",
                "adminContract": {
                    "companyIds": list(connection.expected_company_ids),
                    "provisioningTemplate": connection.provisioning_template,
                    "requiredCapabilities": [
                        capability
                        for capability in (
                            "UsersRead",
                            "UsersWrite",
                            "GroupsRead" if connection.group_bindings else None,
                            "GroupsWrite" if connection.group_bindings else None,
                        )
                        if capability is not None
                    ],
                    "groupBindingAttribute": connection.group_binding_attribute,
                    "sanctionedGroupCount": len(connection.group_bindings),
                },
            }
            for connection in settings.connections
        ],
        "unsupported": [
            "password provisioning",
            "Bulk",
            "cursor pagination (RFC 9865)",
            "SCIM Security Event Tokens (RFC 9967)",
        ],
        "redacted": True,
    }


def write_redacted_evidence(path: Path, evidence: Mapping[str, Any]) -> None:
    serialized = json.dumps(evidence, ensure_ascii=False)
    if "authorization" in serialized.casefold() or "bearer " in serialized.casefold():
        raise RuntimeError("Refusing to persist evidence that may contain a SCIM credential.")
    _atomic_json(path, dict(evidence), secret=False)


def _scim_response(status: int, headers: Any, raw: bytes, started: float) -> ScimResponse:
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    if raw:
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as failure:
            raise ScimProtocolError(
                "The SCIM service returned invalid JSON.",
                classification="invalid-provider-response",
                status=status,
            ) from failure
    else:
        payload = None
    return ScimResponse(
        status,
        normalized_headers,
        payload,
        max(0, round((time.monotonic() - started) * 1000)),
    )


def _protocol_failure(response: ScimResponse) -> ScimProtocolError:
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    payload = response.payload if isinstance(response.payload, Mapping) else {}
    schemas = payload.get("schemas")
    reported_status = payload.get("status")
    valid_reported_status = reported_status in {response.status, str(response.status)}
    if (
        content_type != SCIM_MEDIA_TYPE
        or not isinstance(schemas, list)
        or ERROR_SCHEMA not in schemas
        or not valid_reported_status
    ):
        return ScimProtocolError(
            "The SCIM service returned a non-conforming error response.",
            classification="invalid-provider-response",
            status=response.status,
        )
    scim_type = payload.get("scimType") if isinstance(payload.get("scimType"), str) else None
    classification = {
        400: "request-rejected",
        401: "credential-rejected",
        403: "capability-rejected",
        404: "resource-or-capability-unavailable",
        409: "state-conflict",
        412: "stale-etag",
        429: "rate-limited",
        503: "service-unavailable",
    }.get(response.status, "provider-error" if response.status >= 500 else "unexpected-status")
    return ScimProtocolError(
        f"The SCIM service returned HTTP {response.status}.",
        classification=classification,
        status=response.status,
        scim_type=scim_type,
    )


def _response_evidence(step: str, response: ScimResponse) -> dict[str, Any]:
    return {
        "step": step,
        "status": response.status,
        "elapsedMilliseconds": response.elapsed_milliseconds,
        "etagPresent": bool(_etag(response)),
    }


def _required_object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ScimProtocolError(
            f"The SCIM {name} response is not a JSON object.",
            classification="invalid-provider-response",
        )
    return value


def _require_schema(value: Mapping[str, Any], schema: str, name: str) -> None:
    schemas = value.get("schemas")
    if not isinstance(schemas, list) or schema not in schemas:
        raise ScimProtocolError(
            f"The SCIM {name} response omitted its required schema.",
            classification="invalid-provider-response",
        )


def _list_resources(value: Any, name: str) -> list[Mapping[str, Any]]:
    document = _required_object(value, name)
    _require_schema(document, LIST_RESPONSE_SCHEMA, name)
    resources = document.get("Resources")
    if not isinstance(resources, list) or any(not isinstance(item, Mapping) for item in resources):
        raise ScimProtocolError(
            f"The SCIM {name} response contains an invalid resource list.",
            classification="invalid-provider-response",
        )
    total_results = document.get("totalResults")
    if not isinstance(total_results, int) or total_results < len(resources):
        raise ScimProtocolError(
            f"The SCIM {name} response contains invalid paging metadata.",
            classification="invalid-provider-response",
        )
    return list(resources)


def _required_resource(value: Any, schema: str, name: str) -> dict[str, Any]:
    resource = dict(_required_object(value, name))
    _require_schema(resource, schema, name)
    _resource_id_value(resource, name)
    return resource


def _resource_id_value(resource: Mapping[str, Any], name: str) -> str:
    value = resource.get("id")
    try:
        return _resource_id(value)
    except ValueError as failure:
        raise ScimProtocolError(
            f"The SCIM {name} response omitted a canonical resource id.",
            classification="invalid-provider-response",
        ) from failure


def _resource_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        value,
    ):
        raise ValueError("SCIM resource IDs must be canonical lowercase UUIDs.")
    return value


def _resource_etag(resource: Mapping[str, Any]) -> str | None:
    meta = resource.get("meta")
    if not isinstance(meta, Mapping):
        return None
    version = meta.get("version")
    return version if isinstance(version, str) and version else None


def _etag(response: ScimResponse) -> str | None:
    value = response.headers.get("etag")
    if value is None:
        return _resource_etag(response.payload) if isinstance(response.payload, Mapping) else None
    return value


def _feature_supported(config: Mapping[str, Any], name: str) -> bool:
    value = config.get(name)
    return isinstance(value, Mapping) and value.get("supported") is True


def _filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _validated_base_url(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ScimValidationError({field: "baseUrl is required."})
    candidate = value.strip().rstrip("/")
    parsed = parse.urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith("/scim/v2")
        or ".." in parsed.path.split("/")
    ):
        raise ScimValidationError(
            {field: "baseUrl must be an HTTPS URL ending in /scim/v2 with no credentials, query, or fragment."}
        )
    return candidate


def _required_string(values: Mapping[str, Any], key: str, field: str, maximum: int) -> str:
    value = values.get(key)
    if not isinstance(value, str):
        raise ScimValidationError({field: f"{key} is required."})
    result = value.strip()
    if not result or len(result) > maximum or any(character in "\r\n\x00" for character in result):
        raise ScimValidationError({field: f"{key} is invalid."})
    return result


def _required_public_string(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScimValidationError({"syntheticUserId": "The synthetic user is malformed."})
    return value.strip()


def _bounded_integer(
    values: Mapping[str, Any],
    key: str,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    value = values.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ScimValidationError({field: f"{key} must be between {minimum} and {maximum}."})
    return value


def _validate_credential(value: Any) -> None:
    if (
        not isinstance(value, str)
        or not 16 <= len(value) <= 4096
        or any(character.isspace() or ord(character) < 33 or ord(character) == 127 for character in value)
    ):
        raise ScimValidationError(
            {"credential": "Enter a non-whitespace bearer credential between 16 and 4096 characters."}
        )


def _atomic_json(path: Path, payload: Mapping[str, Any], *, secret: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    if secret:
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
    os.replace(temporary, path)
    if secret:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
