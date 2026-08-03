#!/usr/bin/env python3
"""Generate a deterministic Keycloak realm from the Northlake security manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


REALM_NAME = "northlake"
MODERN_CLIENT_ID = "eemsuite-web"
LEGACY_CLIENT_ID = "eemsuite-web-legacy"
DEFAULT_EEMSUITE_APPLICATION_HOME_URL = "https://localdev.energyhippo.com/Hippo/"
DEFAULT_SAML_ENTITY_ID = "urn:energyhippo:eemsuite-web:saml"
DEFAULT_SAML_ACS_URLS = (
    "https://localhost:7310/saml/acs",
    "https://localdev.energyhippo.com/Hippo/saml/acs",
    "https://localhost/Hippo/saml/acs",
)
DEFAULT_SAML_LOGOUT_URLS = (
    "https://localhost:7310/saml/logout",
    "https://localdev.energyhippo.com/Hippo/saml/logout",
    "https://localhost/Hippo/saml/logout",
)
SAML_IDP_INITIATED_URL_NAME = "eemsuite-web-saml"
SAML_NAME_ID_FORMAT = "persistent"
SAML_NAME_ID_FORMAT_URN = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
SAML_POST_BINDING_URN = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
UUID_NAMESPACE = uuid.UUID("b275b995-9df7-5c6c-92d7-892302b2397e")
REQUIRED_SECRET_KEYS = (
    "KEYCLOAK_ADMIN_PASSWORD",
    "KEYCLOAK_DB_PASSWORD",
    "EEMSUITE_OIDC_CLIENT_SECRET",
    "EEMSUITE_OIDC_LEGACY_CLIENT_SECRET",
    "SYNTHETIC_USER_PASSWORD",
)


class RealmGenerationError(ValueError):
    """Raised when the source manifest or local environment is invalid."""


def _stable_id(kind: str, value: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"{REALM_NAME}/{kind}/{value}"))


def _load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RealmGenerationError(
            f"Identity environment file not found: {path}. "
            "Run identity/scripts/Initialize-Identity.ps1 first."
        )

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RealmGenerationError(f"{path}:{line_number}: expected KEY=VALUE.")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _require_environment(values: dict[str, str]) -> None:
    for key in REQUIRED_SECRET_KEYS:
        value = values.get(key, "")
        if len(value) < 16 or value.startswith("replace-"):
            raise RealmGenerationError(
                f"{key} is missing or is still a placeholder. "
                "Run identity/scripts/Initialize-Identity.ps1."
            )

    base_url = values.get("IDENTITY_PUBLIC_BASE_URL", "https://localhost:8443").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RealmGenerationError("IDENTITY_PUBLIC_BASE_URL must be an absolute HTTPS URL.")

    configured_host = values.get("IDENTITY_HOST", "localhost")
    configured_port = int(values.get("IDENTITY_HTTPS_PORT", "8443"))
    effective_port = parsed.port or 443
    if parsed.hostname.lower() != configured_host.lower() or effective_port != configured_port:
        raise RealmGenerationError(
            "IDENTITY_PUBLIC_BASE_URL must use IDENTITY_HOST and IDENTITY_HTTPS_PORT."
        )


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        manifest = yaml.safe_load(stream)
    if not isinstance(manifest, dict):
        raise RealmGenerationError(f"{path} did not contain a YAML object.")
    return manifest


def _collect_groups(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []

    system_company = manifest.get("systemCompany", {})
    for source_group in system_company.get("groups", []):
        groups.append(
            {
                **source_group,
                "companyId": system_company.get("id", "system"),
                "companyDisplayName": system_company.get("displayName", "System"),
            }
        )

    for company in manifest.get("companies", []):
        for source_group in company.get("groups", []):
            groups.append(
                {
                    **source_group,
                    "companyId": company["id"],
                    "companyDisplayName": company["displayName"],
                }
            )
    return groups


def _validate_manifest(
    manifest: dict[str, Any],
    source_groups: list[dict[str, Any]],
) -> None:
    users = manifest.get("users", [])
    user_ids = [user.get("id") for user in users]
    group_ids = [group.get("id") for group in source_groups]

    if any(not value for value in user_ids) or len(user_ids) != len(set(user_ids)):
        raise RealmGenerationError("Every user must have a unique non-empty id.")
    if any(not value for value in group_ids) or len(group_ids) != len(set(group_ids)):
        raise RealmGenerationError("Every group must have a unique non-empty id.")

    known_users = set(user_ids)
    memberships: dict[str, int] = defaultdict(int)
    for group in source_groups:
        for user_id in group.get("users", []):
            if user_id not in known_users:
                raise RealmGenerationError(
                    f"Group {group['id']} references unknown user {user_id}."
                )
            memberships[user_id] += 1

    for user in users:
        if user.get("status") == "active" and memberships[user["id"]] == 0:
            raise RealmGenerationError(f"Active user {user['id']} has no group membership.")

    expected = manifest.get("validationExpectations", {}).get("counts", {})
    actual = {
        "groups": len(source_groups),
        "users": len(users),
        "activeUsers": sum(user.get("status") == "active" for user in users),
        "disabledUsers": sum(user.get("status") == "disabled" for user in users),
    }
    for key, value in actual.items():
        if key in expected and expected[key] != value:
            raise RealmGenerationError(
                f"Manifest expected {expected[key]} {key}, but generated source has {value}."
            )


def _attribute_mapper(attribute: str, claim: str, *, multivalued: bool = False) -> dict[str, Any]:
    return {
        "name": claim,
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-attribute-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": attribute,
            "claim.name": claim,
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
            "multivalued": str(multivalued).lower(),
            "aggregate.attrs": "false",
        },
    }


def _property_mapper(
    name: str,
    property_name: str,
    claim: str,
    *,
    json_type: str = "String",
) -> dict[str, Any]:
    return {
        "name": name,
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-property-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": property_name,
            "claim.name": claim,
            "jsonType.label": json_type,
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true",
        },
    }


def _saml_attribute_mapper(attribute: str, assertion_attribute: str) -> dict[str, Any]:
    return {
        "name": assertion_attribute,
        "protocol": "saml",
        "protocolMapper": "saml-user-attribute-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": attribute,
            "friendly.name": assertion_attribute,
            "attribute.name": assertion_attribute,
            "attribute.nameformat": "Basic",
            "aggregate.attrs": "false",
        },
    }


def _saml_property_mapper(property_name: str, assertion_attribute: str) -> dict[str, Any]:
    return {
        "name": assertion_attribute,
        "protocol": "saml",
        "protocolMapper": "saml-user-property-mapper",
        "consentRequired": False,
        "config": {
            "user.attribute": property_name,
            "friendly.name": assertion_attribute,
            "attribute.name": assertion_attribute,
            "attribute.nameformat": "Basic",
        },
    }


def _standard_client_scopes() -> list[dict[str, Any]]:
    common_attributes = {
        "include.in.token.scope": "true",
        "display.on.consent.screen": "true",
    }
    return [
        {
            "id": _stable_id("client-scope", "basic"),
            "name": "basic",
            "description": "Core session claims used for OIDC validation.",
            "protocol": "openid-connect",
            "attributes": {
                "include.in.token.scope": "false",
                "display.on.consent.screen": "false",
            },
            "protocolMappers": [
                {
                    "name": "auth_time",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-usersessionmodel-note-mapper",
                    "consentRequired": False,
                    "config": {
                        "user.session.note": "AUTH_TIME",
                        "claim.name": "auth_time",
                        "jsonType.label": "long",
                        "id.token.claim": "true",
                        "access.token.claim": "true",
                        "userinfo.token.claim": "false",
                    },
                },
                {
                    "name": "acr",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-acr-mapper",
                    "consentRequired": False,
                    "config": {
                        "id.token.claim": "true",
                        "access.token.claim": "true",
                    },
                },
            ],
        },
        {
            "id": _stable_id("client-scope", "profile"),
            "name": "profile",
            "description": "Standard OpenID Connect profile claims.",
            "protocol": "openid-connect",
            "attributes": {
                **common_attributes,
                "consent.screen.text": "User profile",
            },
            "protocolMappers": [
                {
                    "name": "full name",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-full-name-mapper",
                    "consentRequired": False,
                    "config": {
                        "id.token.claim": "true",
                        "access.token.claim": "true",
                        "userinfo.token.claim": "true",
                    },
                },
                _property_mapper("username", "username", "preferred_username"),
                _property_mapper("given name", "firstName", "given_name"),
                _property_mapper("family name", "lastName", "family_name"),
            ],
        },
        {
            "id": _stable_id("client-scope", "email"),
            "name": "email",
            "description": "Standard OpenID Connect email claims.",
            "protocol": "openid-connect",
            "attributes": {
                **common_attributes,
                "consent.screen.text": "Email address",
            },
            "protocolMappers": [
                _property_mapper("email", "email", "email"),
                _property_mapper(
                    "email verified",
                    "emailVerified",
                    "email_verified",
                    json_type="boolean",
                ),
            ],
        },
        {
            "id": _stable_id("client-scope", "roles"),
            "name": "roles",
            "description": "Synthetic EEM permission-profile intent as realm roles.",
            "protocol": "openid-connect",
            "attributes": {
                **common_attributes,
                "consent.screen.text": "Synthetic role intent",
            },
            "protocolMappers": [
                {
                    "name": "realm roles",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-usermodel-realm-role-mapper",
                    "consentRequired": False,
                    "config": {
                        "multivalued": "true",
                        "claim.name": "realm_access.roles",
                        "jsonType.label": "String",
                        "id.token.claim": "true",
                        "access.token.claim": "true",
                        "userinfo.token.claim": "true",
                    },
                }
            ],
        },
    ]


def _northlake_client_scope() -> dict[str, Any]:
    return {
        "id": _stable_id("client-scope", "northlake"),
        "name": "northlake",
        "description": "Synthetic Northlake identity and authorization-shape claims.",
        "protocol": "openid-connect",
        "attributes": {
            "include.in.token.scope": "true",
            "display.on.consent.screen": "true",
            "consent.screen.text": "Northlake synthetic customer identity",
        },
        "protocolMappers": [
            {
                "name": "groups",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "full.path": "false",
                    "claim.name": "groups",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "jsonType.label": "String",
                },
            },
            _attribute_mapper("synthetic_user_id", "synthetic_user_id"),
            _attribute_mapper("primary_company_id", "primary_company_id"),
            _attribute_mapper("title", "title"),
            _attribute_mapper("synthetic_status", "synthetic_status"),
            _attribute_mapper("eem_company_ids", "eem_company_ids", multivalued=True),
            _attribute_mapper(
                "eem_permission_profiles",
                "eem_permission_profiles",
                multivalued=True,
            ),
        ],
    }


def _origins(redirect_uris: list[str]) -> list[str]:
    values: list[str] = []
    for redirect_uri in redirect_uris:
        parsed = urlparse(redirect_uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RealmGenerationError(f"Redirect URI is not absolute: {redirect_uri}")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in values:
            values.append(origin)
    return values


def _url_list(
    environment: dict[str, str],
    key: str,
    *,
    default: tuple[str, ...] = (),
) -> list[str]:
    values = [
        value.strip()
        for value in environment.get(key, ";".join(default)).split(";")
        if value.strip()
    ]
    if not values:
        raise RealmGenerationError(f"{key} must contain at least one URI.")
    _origins(values)
    return values


def _client(
    client_id: str,
    secret: str,
    redirect_uris: list[str],
    application_home_url: str,
    *,
    implicit_enabled: bool,
    require_pkce: bool,
) -> dict[str, Any]:
    attributes = {
        "backchannel.logout.revoke.offline.tokens": "true",
        "backchannel.logout.session.required": "true",
        "frontchannel.logout.url": f"{application_home_url.rstrip('/')}/signout-oidc",
        "frontchannel.logout.session.required": "true",
        "oauth2.device.authorization.grant.enabled": "false",
        "oidc.ciba.grant.enabled": "false",
        "par.request.uri.lifespan": "60",
        "post.logout.redirect.uris": "##".join(redirect_uris),
        "pushed.authorization.request.required": "false",
        "use.refresh.tokens": "true",
    }
    if require_pkce:
        attributes["pkce.code.challenge.method"] = "S256"

    return {
        "id": _stable_id("client", client_id),
        "clientId": client_id,
        "name": (
            "EEMSuite Web - modern code and PKCE"
            if require_pkce
            else "EEMSuite Web - legacy implicit compatibility"
        ),
        "description": (
            "Modern confidential client. Authorization code and PKCE S256 are required."
            if require_pkce
            else "Compatibility client for EEMSuite's current id_token token response type."
        ),
        "enabled": True,
        "consentRequired": require_pkce,
        "alwaysDisplayInConsole": True,
        "clientAuthenticatorType": "client-secret",
        "secret": secret,
        "redirectUris": redirect_uris,
        "webOrigins": _origins(redirect_uris),
        "rootUrl": application_home_url,
        "baseUrl": application_home_url,
        "adminUrl": application_home_url,
        "standardFlowEnabled": True,
        "implicitFlowEnabled": implicit_enabled,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "publicClient": False,
        "frontchannelLogout": True,
        "protocol": "openid-connect",
        "attributes": attributes,
        "fullScopeAllowed": True,
        "defaultClientScopes": [
            "basic",
            "roles",
            "profile",
            "email",
            "northlake",
        ],
        "optionalClientScopes": ["offline_access"],
    }


def _saml_client(
    entity_id: str,
    assertion_consumer_service_urls: list[str],
    single_logout_service_urls: list[str],
    application_home_url: str,
) -> dict[str, Any]:
    return {
        "id": _stable_id("client", entity_id),
        "clientId": entity_id,
        "name": "EEMSuite Web - SAML 2.0",
        "description": (
            "Synthetic SAML service provider with signed responses and assertions, "
            "persistent NameID, exact ACS validation, and mapped Northlake attributes."
        ),
        "enabled": True,
        "consentRequired": False,
        "alwaysDisplayInConsole": True,
        "redirectUris": assertion_consumer_service_urls,
        "rootUrl": application_home_url,
        "baseUrl": application_home_url,
        "frontchannelLogout": True,
        "protocol": "saml",
        "attributes": {
            "saml.assertion.signature": "true",
            "saml.server.signature": "true",
            "saml.signature.algorithm": "RSA_SHA256",
            "saml_signature_canonicalization_method": (
                "http://www.w3.org/2001/10/xml-exc-c14n#"
            ),
            "saml.server.signature.keyinfo.ext": "false",
            "saml.server.signature.keyinfo.xmlSigKeyInfoKeyNameTransformer": "KEY_ID",
            "saml.client.signature": "false",
            "saml.encrypt": "false",
            "saml.force.post.binding": "true",
            "saml.authnstatement": "true",
            "saml.onetimeuse.condition": "true",
            "saml.assertion.lifespan": "300",
            "saml_force_name_id_format": "true",
            "saml_name_id_format": SAML_NAME_ID_FORMAT,
            "saml.artifact.binding": "false",
            "saml.allow.ecp.flow": "false",
            "saml_assertion_consumer_url_post": assertion_consumer_service_urls[0],
            "saml_single_logout_service_url_post": single_logout_service_urls[0],
            "saml_single_logout_service_url_redirect": single_logout_service_urls[0],
            "saml_idp_initiated_sso_url_name": SAML_IDP_INITIATED_URL_NAME,
            "saml_idp_initiated_sso_relay_state": "northlake-idp-initiated",
        },
        "fullScopeAllowed": True,
        "protocolMappers": [
            _saml_property_mapper("username", "username"),
            _saml_property_mapper("email", "email"),
            _saml_property_mapper("firstName", "given_name"),
            _saml_property_mapper("lastName", "family_name"),
            {
                "name": "groups",
                "protocol": "saml",
                "protocolMapper": "saml-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "attribute.name": "groups",
                    "friendly.name": "groups",
                    "attribute.nameformat": "Basic",
                    "single": "true",
                    "full.path": "false",
                },
            },
            _saml_attribute_mapper("synthetic_user_id", "synthetic_user_id"),
            _saml_attribute_mapper("primary_company_id", "primary_company_id"),
            _saml_attribute_mapper("title", "title"),
            _saml_attribute_mapper("synthetic_status", "synthetic_status"),
            _saml_attribute_mapper("eem_company_ids", "eem_company_ids"),
            _saml_attribute_mapper("eem_permission_profiles", "eem_permission_profiles"),
            {
                "name": "realm_roles",
                "protocol": "saml",
                "protocolMapper": "saml-role-list-mapper",
                "consentRequired": False,
                "config": {
                    "attribute.name": "realm_roles",
                    "friendly.name": "realm_roles",
                    "attribute.nameformat": "Basic",
                    "single": "true",
                },
            },
        ],
    }


def _expected_identity_attributes(
    user: dict[str, Any],
    user_groups: dict[str, list[str]],
    user_companies: dict[str, set[str]],
    user_profiles: dict[str, set[str]],
) -> dict[str, Any]:
    display_name_parts = user["displayName"].strip().split(maxsplit=1)
    return {
        "username": user["username"],
        "email": user["email"],
        "given_name": display_name_parts[0],
        "family_name": display_name_parts[1] if len(display_name_parts) > 1 else "",
        "synthetic_user_id": user["id"],
        "primary_company_id": user["primaryCompanyId"],
        "title": user.get("title", ""),
        "synthetic_status": user["status"],
        "groups": sorted(group.removeprefix("/") for group in user_groups[user["id"]]),
        "eem_company_ids": sorted(user_companies[user["id"]]),
        "eem_permission_profiles": sorted(user_profiles[user["id"]]),
    }


def build_realm(
    manifest: dict[str, Any],
    environment: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the Keycloak realm and local connection profile."""

    _require_environment(environment)
    application_home_url = environment.get(
        "EEMSUITE_APPLICATION_HOME_URL",
        DEFAULT_EEMSUITE_APPLICATION_HOME_URL,
    ).strip()
    parsed_application_home_url = urlparse(application_home_url)
    if (
        parsed_application_home_url.scheme != "https"
        or not parsed_application_home_url.netloc
    ):
        raise RealmGenerationError(
            "EEMSUITE_APPLICATION_HOME_URL must be an absolute HTTPS URL."
        )
    saml_entity_id = environment.get(
        "EEMSUITE_SAML_ENTITY_ID",
        DEFAULT_SAML_ENTITY_ID,
    ).strip()
    if not saml_entity_id or any(character.isspace() for character in saml_entity_id):
        raise RealmGenerationError(
            "EEMSUITE_SAML_ENTITY_ID must be a non-empty entity identifier without whitespace."
        )
    saml_assertion_consumer_service_urls = _url_list(
        environment,
        "EEMSUITE_SAML_ACS_URLS",
        default=DEFAULT_SAML_ACS_URLS,
    )
    saml_single_logout_service_urls = _url_list(
        environment,
        "EEMSUITE_SAML_LOGOUT_URLS",
        default=DEFAULT_SAML_LOGOUT_URLS,
    )

    source_groups = _collect_groups(manifest)
    _validate_manifest(manifest, source_groups)

    users = manifest["users"]
    user_groups: dict[str, list[str]] = defaultdict(list)
    user_companies: dict[str, set[str]] = defaultdict(set)
    user_profiles: dict[str, set[str]] = defaultdict(set)

    keycloak_groups: list[dict[str, Any]] = []
    for group in source_groups:
        group_id = group["id"]
        permission_profiles = sorted(group.get("permissionProfiles", []))
        for user_id in group.get("users", []):
            user_groups[user_id].append(f"/{group_id}")
            user_companies[user_id].add(group["companyId"])
            user_profiles[user_id].update(permission_profiles)

        attributes = {
            "synthetic_group_id": [group_id],
            "company_id": [group["companyId"]],
            "company_display_name": [group["companyDisplayName"]],
            "permission_profiles": permission_profiles,
        }
        if group.get("nodeScope"):
            attributes["node_scope"] = [str(value) for value in group["nodeScope"]]

        keycloak_groups.append(
            {
                "id": _stable_id("group", group_id),
                "name": group_id,
                "path": f"/{group_id}",
                "attributes": attributes,
                "realmRoles": permission_profiles,
                "subGroups": [],
            }
        )

    password = environment["SYNTHETIC_USER_PASSWORD"]
    keycloak_users: list[dict[str, Any]] = []
    for user in users:
        display_name = user["displayName"].strip()
        name_parts = display_name.split(maxsplit=1)
        attributes = {
            "synthetic_user_id": [user["id"]],
            "primary_company_id": [user["primaryCompanyId"]],
            "title": [user.get("title", "")],
            "synthetic_status": [user["status"]],
            "eem_company_ids": sorted(user_companies[user["id"]]),
            "eem_permission_profiles": sorted(user_profiles[user["id"]]),
            f"saml.persistent.name.id.for.{saml_entity_id}": [
                _stable_id("saml-nameid", user["id"])
            ],
        }
        keycloak_users.append(
            {
                "id": _stable_id("user", user["id"]),
                "username": user["username"],
                "enabled": user["status"] == "active",
                "emailVerified": True,
                "firstName": name_parts[0],
                "lastName": name_parts[1] if len(name_parts) > 1 else "",
                "email": user["email"],
                "attributes": attributes,
                "credentials": [
                    {
                        "type": "password",
                        "value": password,
                        "temporary": False,
                    }
                ],
                "requiredActions": [],
                "realmRoles": [f"default-roles-{REALM_NAME}"],
                "groups": sorted(user_groups[user["id"]]),
            }
        )

    role_definitions = [
        {
            "id": _stable_id("role", profile["id"]),
            "name": profile["id"],
            "description": profile.get("intent", profile["displayName"]),
            "composite": False,
            "clientRole": False,
        }
        for profile in manifest.get("permissionProfiles", [])
    ]

    redirect_uris = _url_list(environment, "EEMSUITE_OIDC_REDIRECT_URIS")

    base_url = environment.get("IDENTITY_PUBLIC_BASE_URL", "https://localhost:8443").rstrip("/")
    issuer = f"{base_url}/realms/{REALM_NAME}"
    discovery = f"{issuer}/.well-known/openid-configuration"

    realm = {
        "id": _stable_id("realm", REALM_NAME),
        "realm": REALM_NAME,
        "displayName": "Northlake Synthetic Identity",
        "displayNameHtml": "<strong>Northlake</strong> Synthetic Identity",
        "enabled": True,
        "notBefore": 0,
        "defaultSignatureAlgorithm": "RS256",
        "revokeRefreshToken": True,
        "refreshTokenMaxReuse": 0,
        "accessTokenLifespan": 300,
        "accessTokenLifespanForImplicitFlow": 300,
        "accessCodeLifespanLogin": 1800,
        "accessCodeLifespanUserAction": 1800,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 28800,
        "offlineSessionIdleTimeout": 2592000,
        "offlineSessionMaxLifespanEnabled": True,
        "offlineSessionMaxLifespan": 5184000,
        "sslRequired": "external",
        "registrationAllowed": False,
        "registrationEmailAsUsername": False,
        "rememberMe": True,
        "verifyEmail": False,
        "loginWithEmailAllowed": True,
        "duplicateEmailsAllowed": False,
        "resetPasswordAllowed": True,
        "editUsernameAllowed": False,
        "bruteForceProtected": True,
        "permanentLockout": False,
        "maxFailureWaitSeconds": 900,
        "minimumQuickLoginWaitSeconds": 60,
        "waitIncrementSeconds": 60,
        "quickLoginCheckMilliSeconds": 1000,
        "maxDeltaTimeSeconds": 43200,
        "failureFactor": 5,
        "roles": {"realm": role_definitions},
        "groups": keycloak_groups,
        "users": keycloak_users,
        "clientScopes": [*_standard_client_scopes(), _northlake_client_scope()],
        "clients": [
            _client(
                MODERN_CLIENT_ID,
                environment["EEMSUITE_OIDC_CLIENT_SECRET"],
                redirect_uris,
                application_home_url,
                implicit_enabled=False,
                require_pkce=True,
            ),
            _client(
                LEGACY_CLIENT_ID,
                environment["EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"],
                redirect_uris,
                application_home_url,
                implicit_enabled=True,
                require_pkce=False,
            ),
            _saml_client(
                saml_entity_id,
                saml_assertion_consumer_service_urls,
                saml_single_logout_service_urls,
                application_home_url,
            ),
        ],
        "eventsEnabled": True,
        "eventsExpiration": 604800,
        "eventsListeners": ["jboss-logging"],
        "adminEventsEnabled": True,
        "adminEventsDetailsEnabled": True,
        "internationalizationEnabled": True,
        "supportedLocales": ["en"],
        "defaultLocale": "en",
    }

    active_user = next(user for user in users if user["status"] == "active")
    disabled_user = next(user for user in users if user["status"] == "disabled")
    connection_profile = {
        "realm": REALM_NAME,
        "realmSource": {
            "manifestId": manifest["id"],
            "manifestVersion": manifest["manifestVersion"],
            "customerScenarioId": manifest["customerScenarioId"],
        },
        "applicationHomeUrl": application_home_url,
        "baseUrl": base_url,
        "issuer": issuer,
        "discoveryEndpoint": discovery,
        "jwksEndpoint": f"{issuer}/protocol/openid-connect/certs",
        "authorizationEndpoint": f"{issuer}/protocol/openid-connect/auth",
        "tokenEndpoint": f"{issuer}/protocol/openid-connect/token",
        "userinfoEndpoint": f"{issuer}/protocol/openid-connect/userinfo",
        "logoutEndpoint": f"{issuer}/protocol/openid-connect/logout",
        "samlMetadataEndpoint": f"{issuer}/protocol/saml/descriptor",
        "samlSingleSignOnEndpoint": f"{issuer}/protocol/saml",
        "samlSingleLogoutEndpoint": f"{issuer}/protocol/saml",
        "adminConsole": f"{base_url}/admin/{REALM_NAME}/console/",
        "masterAdminConsole": f"{base_url}/admin/master/console/",
        "accountConsole": f"{issuer}/account/",
        "clients": {
            "modern": {
                "clientId": MODERN_CLIENT_ID,
                "clientSecret": environment["EEMSUITE_OIDC_CLIENT_SECRET"],
                "responseType": "code",
                "scope": "openid profile email northlake",
                "redirectUris": redirect_uris,
            },
            "legacy": {
                "clientId": LEGACY_CLIENT_ID,
                "clientSecret": environment["EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"],
                "responseType": "id_token token",
                "scope": "openid profile email northlake",
                "redirectUris": redirect_uris,
            },
            "saml": {
                "clientId": saml_entity_id,
                "entityId": saml_entity_id,
                "protocol": "saml",
                "redirectUris": saml_assertion_consumer_service_urls,
                "assertionConsumerServiceUrls": saml_assertion_consumer_service_urls,
                "singleLogoutServiceUrls": saml_single_logout_service_urls,
                "defaultAssertionConsumerServiceUrl": (
                    saml_assertion_consumer_service_urls[0]
                ),
                "defaultSingleLogoutServiceUrl": saml_single_logout_service_urls[0],
                "nameIdFormat": SAML_NAME_ID_FORMAT_URN,
                "responseBinding": SAML_POST_BINDING_URN,
                "signAuthnRequests": False,
                "wantResponseSigned": True,
                "wantAssertionsSigned": True,
                "wantAssertionsEncrypted": False,
                "idpInitiatedSsoUrl": (
                    f"{issuer}/protocol/saml/clients/{SAML_IDP_INITIATED_URL_NAME}"
                ),
                "idpInitiatedRelayState": "northlake-idp-initiated",
            },
        },
        "testUsers": {
            "active": {
                "username": active_user["username"],
                "subject": _stable_id("user", active_user["id"]),
                "samlNameId": _stable_id("saml-nameid", active_user["id"]),
                "expectedAttributes": _expected_identity_attributes(
                    active_user,
                    user_groups,
                    user_companies,
                    user_profiles,
                ),
            },
            "disabled": {
                "username": disabled_user["username"],
                "subject": _stable_id("user", disabled_user["id"]),
                "samlNameId": _stable_id("saml-nameid", disabled_user["id"]),
                "expectedAttributes": _expected_identity_attributes(
                    disabled_user,
                    user_groups,
                    user_companies,
                    user_profiles,
                ),
            },
            "password": password,
        },
        "admin": {
            "username": environment.get("KEYCLOAK_ADMIN", "admin"),
            "password": environment["KEYCLOAK_ADMIN_PASSWORD"],
        },
        "eemsuiteConfiguration": {
            "legacy": {
                "OpenIDConnect": {
                    "Description": "Northlake Synthetic Identity - legacy",
                    "ClientID": LEGACY_CLIENT_ID,
                    "ClientSecret": environment["EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"],
                    "ResponseType": "id_token token",
                    "Scope": "openid profile email northlake",
                    "DiscoveryEndpoint": discovery,
                }
            },
            "modern": {
                "OpenIDConnect": {
                    "Description": "Northlake Synthetic Identity - modern",
                    "ClientID": MODERN_CLIENT_ID,
                    "ClientSecret": environment["EEMSUITE_OIDC_CLIENT_SECRET"],
                    "ResponseType": "code",
                    "Scope": "openid profile email northlake",
                    "DiscoveryEndpoint": discovery,
                }
            },
        },
    }
    return realm, connection_profile


def generate(
    manifest_path: Path,
    env_path: Path,
    output_path: Path,
    connection_output_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    environment = _load_env(env_path)
    manifest = _load_manifest(manifest_path)
    realm, connection_profile = build_realm(manifest, environment)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(realm, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    connection_output_path.write_text(
        json.dumps(connection_profile, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    return realm, connection_profile


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Northlake Keycloak realm and local connection profile."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--connection-output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        realm, _ = generate(
            args.manifest.resolve(),
            args.env_file.resolve(),
            args.output.resolve(),
            args.connection_output.resolve(),
        )
    except (OSError, RealmGenerationError, yaml.YAMLError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1

    enabled_users = sum(user["enabled"] for user in realm["users"])
    print(
        f"[OK] Generated realm '{realm['realm']}' with "
        f"{len(realm['users'])} users ({enabled_users} enabled), "
        f"{len(realm['groups'])} groups, and {len(realm['clients'])} clients."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
