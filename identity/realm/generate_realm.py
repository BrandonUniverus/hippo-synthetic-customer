#!/usr/bin/env python3
"""Generate a deterministic Keycloak realm from the Northlake security manifest."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from identity.configuration.settings import (
    ProviderSettings,
    REALM_KEY_PATTERN,
    SettingsValidationError,
    load_settings_document,
)
from identity.configuration.oidc import (
    OidcSettings,
    OidcValidationError,
    load_oidc_settings_document,
)
from identity.configuration.saml import (
    SamlSettings,
    SamlValidationError,
    load_saml_settings_document,
)
from identity.configuration.groups import GroupValidationError, merge_group_overlay
from identity.configuration.users import UserValidationError, merge_user_overlay


DEFAULT_REALM_NAME = "northlake"
DEFAULT_EEMSUITE_APPLICATION_HOME_URL = "https://localdev.energyhippo.com/Hippo/"
DEFAULT_STANDARD_SAML_ENTITY_ID = "urn:energyhippo:eemsuite-web:saml:standard"
DEFAULT_SAML2INT_ENTITY_ID = "urn:energyhippo:eemsuite-web:saml:saml2int"
SAML_NAME_ID_FORMAT = "persistent"
SAML_NAME_ID_FORMAT_URN = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
SAML_POST_BINDING_URN = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
SAML_AES_256_GCM = "http://www.w3.org/2009/xmlenc11#aes256-gcm"
SAML_RSA_OAEP_11 = "http://www.w3.org/2009/xmlenc11#rsa-oaep"
SAML_SHA_256 = "http://www.w3.org/2001/04/xmlenc#sha256"
SAML_MGF1_SHA_256 = "http://www.w3.org/2009/xmlenc11#mgf1sha256"
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


def _load_rsa_public_certificate(path_value: str) -> str:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise RealmGenerationError(
            "EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE must identify an existing public certificate."
        )

    document = path.read_bytes()
    try:
        certificate = (
            x509.load_pem_x509_certificate(document)
            if b"-----BEGIN CERTIFICATE-----" in document
            else x509.load_der_x509_certificate(document)
        )
    except ValueError as error:
        raise RealmGenerationError(
            "EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE did not contain an X.509 certificate."
        ) from error

    public_key = certificate.public_key()
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
        raise RealmGenerationError(
            "The SAML2Int service-provider certificate must use RSA with at least 2048 bits."
        )
    now_utc = datetime.now(UTC)
    if certificate.not_valid_before_utc > now_utc or certificate.not_valid_after_utc <= now_utc:
        raise RealmGenerationError(
            "The SAML2Int service-provider certificate is not currently valid."
        )
    return base64.b64encode(
        certificate.public_bytes(serialization.Encoding.DER)
    ).decode("ascii")


def _stable_id(realm_name: str, kind: str, value: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"{realm_name}/{kind}/{value}"))


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


def _environment_boolean(values: dict[str, str], key: str, default: bool) -> bool:
    raw_value = values.get(key)
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise RealmGenerationError(f"{key} must be true or false.")


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


def _standard_client_scopes(realm_name: str) -> list[dict[str, Any]]:
    common_attributes = {
        "include.in.token.scope": "true",
        "display.on.consent.screen": "true",
    }
    return [
        {
            "id": _stable_id(realm_name, "client-scope", "basic"),
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
            "id": _stable_id(realm_name, "client-scope", "profile"),
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
            "id": _stable_id(realm_name, "client-scope", "email"),
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
            "id": _stable_id(realm_name, "client-scope", "roles"),
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


def _northlake_client_scope(realm_name: str) -> dict[str, Any]:
    return {
        "id": _stable_id(realm_name, "client-scope", "northlake"),
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
    realm_name: str,
    client_id: str,
    secret: str,
    redirect_uris: list[str],
    post_logout_redirect_uris: list[str],
    application_home_url: str,
    scopes: tuple[str, ...],
    *,
    implicit_enabled: bool,
    require_pkce: bool,
    consent_required: bool,
    par_behavior: str,
) -> dict[str, Any]:
    attributes = {
        "backchannel.logout.revoke.offline.tokens": "true",
        "backchannel.logout.session.required": "true",
        "frontchannel.logout.url": f"{application_home_url.rstrip('/')}/signout-oidc",
        "frontchannel.logout.session.required": "true",
        "oauth2.device.authorization.grant.enabled": "false",
        "oidc.ciba.grant.enabled": "false",
        "par.request.uri.lifespan": "60",
        "post.logout.redirect.uris": "##".join(post_logout_redirect_uris),
        "pushed.authorization.request.required": str(par_behavior == "Require").lower(),
        "use.refresh.tokens": "true",
    }
    if require_pkce:
        attributes["pkce.code.challenge.method"] = "S256"

    return {
        "id": _stable_id(realm_name, "client", client_id),
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
        "consentRequired": consent_required,
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
            *[
                scope
                for scope in ("profile", "email", "northlake")
                if scope in scopes
            ],
        ],
        "optionalClientScopes": ["offline_access"],
    }


def _saml_claim_mapper(entity_id: str, claim: str) -> dict[str, Any]:
    property_claims = {
        "username": "username",
        "email": "email",
        "given_name": "firstName",
        "family_name": "lastName",
    }
    if claim in property_claims:
        return _saml_property_mapper(property_claims[claim], claim)
    if claim == "groups":
        return {
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
        }
    if claim == "realm_roles":
        return {
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
        }
    attribute_source = (
        f"saml.subject.id.for.{entity_id}"
        if claim == "urn:oasis:names:tc:SAML:attribute:subject-id"
        else claim
    )
    return _saml_attribute_mapper(attribute_source, claim)


def _saml_client(
    realm_name: str,
    entity_id: str,
    assertion_consumer_service_urls: list[str],
    single_logout_service_urls: list[str],
    application_home_url: str,
    *,
    validation_profile: str,
    idp_initiated_url_name: str,
    allowed_claims: tuple[str, ...],
    enable_single_logout: bool,
    service_provider_certificate: str | None = None,
) -> dict[str, Any]:
    saml2int = validation_profile == "Saml2Int"
    if validation_profile not in {"Standard", "Saml2Int"}:
        raise RealmGenerationError(f"Unsupported SAML validation profile: {validation_profile}.")
    if saml2int and not service_provider_certificate:
        raise RealmGenerationError(
            "The SAML2Int profile requires EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE."
        )
    if enable_single_logout and not single_logout_service_urls:
        raise RealmGenerationError(
            f"The {validation_profile} profile enables SLO without a logout callback."
        )

    attributes = {
        "saml.assertion.signature": str(not saml2int).lower(),
        "saml.server.signature": "true",
        "saml.signature.algorithm": "RSA_SHA256",
        "saml_signature_canonicalization_method": (
            "http://www.w3.org/2001/10/xml-exc-c14n#"
        ),
        "saml.server.signature.keyinfo.ext": "false",
        "saml.server.signature.keyinfo.xmlSigKeyInfoKeyNameTransformer": "KEY_ID",
        "saml.client.signature": str(saml2int).lower(),
        "saml.encrypt": str(saml2int).lower(),
        "saml.force.post.binding": "true",
        "saml.authnstatement": "true",
        "saml.onetimeuse.condition": "true",
        "saml.assertion.lifespan": "300",
        "saml_force_name_id_format": "true",
        "saml_name_id_format": SAML_NAME_ID_FORMAT,
        "saml.artifact.binding": "false",
        "saml.allow.ecp.flow": "false",
        "saml_assertion_consumer_url_post": assertion_consumer_service_urls[0],
        "saml_idp_initiated_sso_url_name": idp_initiated_url_name,
        "saml_idp_initiated_sso_relay_state": f"northlake-{validation_profile.lower()}",
    }
    if enable_single_logout:
        attributes["saml_single_logout_service_url_post"] = single_logout_service_urls[0]
        attributes["saml_single_logout_service_url_redirect"] = single_logout_service_urls[0]
    if service_provider_certificate:
        attributes["saml.signing.certificate"] = service_provider_certificate
        attributes["saml.encryption.certificate"] = service_provider_certificate
        attributes["saml.encryption.algorithm"] = SAML_AES_256_GCM
        attributes["saml.encryption.keyAlgorithm"] = SAML_RSA_OAEP_11
        attributes["saml.encryption.digestMethod"] = SAML_SHA_256
        attributes["saml.encryption.maskGenerationFunction"] = SAML_MGF1_SHA_256

    return {
        "id": _stable_id(realm_name, "client", entity_id),
        "clientId": entity_id,
        "name": f"EEMSuite Web - SAML 2.0 {validation_profile}",
        "description": (
            f"Synthetic {validation_profile} SAML service provider with signed responses, "
            "persistent NameID, exact dynamic-provider callbacks, and mapped Northlake attributes."
        ),
        "enabled": True,
        "consentRequired": False,
        "alwaysDisplayInConsole": True,
        "redirectUris": assertion_consumer_service_urls,
        "rootUrl": application_home_url,
        "baseUrl": application_home_url,
        "frontchannelLogout": enable_single_logout,
        "protocol": "saml",
        "attributes": attributes,
        "fullScopeAllowed": True,
        "protocolMappers": [
            _saml_claim_mapper(entity_id, claim) for claim in allowed_claims
        ],
    }


def _expected_identity_attributes(
    realm_name: str,
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
        "urn:oasis:names:tc:SAML:attribute:subject-id": (
            f"{_stable_id(realm_name, 'saml-subject-id', user['id'])}@northlake.example"
        ),
    }


def build_realm(
    manifest: dict[str, Any],
    environment: dict[str, str],
    user_overlay_path: Path | None = None,
    group_overlay_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the Keycloak realm and local connection profile."""

    _require_environment(environment)
    realm_name = environment.get("NORTHLAKE_REALM_KEY", DEFAULT_REALM_NAME).strip()
    if not REALM_KEY_PATTERN.fullmatch(realm_name) or realm_name == "master":
        raise RealmGenerationError(
            "NORTHLAKE_REALM_KEY must be a non-master lowercase realm key."
        )
    provider_display_name = environment.get(
        "NORTHLAKE_PROVIDER_DISPLAY_NAME",
        "Northlake Synthetic Identity",
    ).strip()
    if not 3 <= len(provider_display_name) <= 80 or any(
        ord(character) < 32 for character in provider_display_name
    ):
        raise RealmGenerationError(
            "NORTHLAKE_PROVIDER_DISPLAY_NAME must contain 3-80 printable characters."
        )
    enable_oidc = _environment_boolean(environment, "NORTHLAKE_ENABLE_OIDC", True)
    enable_saml = _environment_boolean(environment, "NORTHLAKE_ENABLE_SAML", True)
    if not enable_oidc and not enable_saml:
        raise RealmGenerationError("At least one of OIDC or SAML must be enabled.")
    oidc_settings = OidcSettings.from_environment(environment) if enable_oidc else None

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
    raw_saml_profiles = [
        value.strip()
        for value in environment.get("EEMSUITE_SAML_PROFILES", "Standard").split(";")
        if value.strip()
    ]
    if enable_saml and (
        not raw_saml_profiles
        or len(raw_saml_profiles) != len(set(raw_saml_profiles))
        or any(value not in {"Standard", "Saml2Int"} for value in raw_saml_profiles)
    ):
        raise RealmGenerationError(
            "EEMSUITE_SAML_PROFILES must contain unique Standard or Saml2Int values."
        )
    saml_settings = SamlSettings.from_environment(environment) if enable_saml else None
    configured_saml_profiles = (
        [
            *(("Standard",) if saml_settings and saml_settings.standard.enabled else ()),
            *(("Saml2Int",) if saml_settings and saml_settings.saml2int.enabled else ()),
        ]
        if enable_saml
        else []
    )
    standard_profile = saml_settings.standard if saml_settings is not None else None
    saml2int_profile = saml_settings.saml2int if saml_settings is not None else None
    standard_saml_entity_id = (
        standard_profile.entity_id if standard_profile is not None else DEFAULT_STANDARD_SAML_ENTITY_ID
    )
    saml2int_entity_id = (
        saml2int_profile.entity_id if saml2int_profile is not None else DEFAULT_SAML2INT_ENTITY_ID
    )
    standard_saml_acs_urls = (
        list(standard_profile.assertion_consumer_service_urls)
        if standard_profile is not None and standard_profile.enabled
        else []
    )
    standard_saml_logout_urls = (
        list(standard_profile.logout_service_urls)
        if standard_profile is not None and standard_profile.enabled
        else []
    )
    saml2int_acs_urls = (
        list(saml2int_profile.assertion_consumer_service_urls)
        if saml2int_profile is not None and saml2int_profile.enabled
        else []
    )
    saml2int_logout_urls = (
        list(saml2int_profile.logout_service_urls)
        if saml2int_profile is not None and saml2int_profile.enabled
        else []
    )
    saml2int_certificate = None
    saml2int_certificate_thumbprint = None
    if "Saml2Int" in configured_saml_profiles:
        saml2int_certificate = _load_rsa_public_certificate(
            environment.get("EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE", "")
        )
        saml2int_certificate_thumbprint = hashlib.sha256(
            base64.b64decode(saml2int_certificate)
        ).hexdigest().upper()

    source_groups = _collect_groups(manifest)
    _validate_manifest(manifest, source_groups)

    password = environment["SYNTHETIC_USER_PASSWORD"]
    users = merge_user_overlay(
        manifest["users"],
        user_overlay_path,
        password,
    )
    source_groups = merge_group_overlay(
        source_groups,
        group_overlay_path,
        {user["id"] for user in users},
    )
    user_groups: dict[str, list[str]] = defaultdict(list)
    user_companies: dict[str, set[str]] = defaultdict(set)
    user_profiles: dict[str, set[str]] = defaultdict(set)

    keycloak_groups: list[dict[str, Any]] = []
    for group in source_groups:
        group_id = group["id"]
        permission_profiles = sorted(group.get("permissionProfiles", []))
        company_id = group.get("companyId", "")
        for user_id in group.get("users", []):
            user_groups[user_id].append(f"/{group_id}")
            if company_id:
                user_companies[user_id].add(company_id)
            user_profiles[user_id].update(permission_profiles)

        attributes = {
            "synthetic_group_id": [group_id],
            "company_id": [company_id],
            "company_display_name": [group["companyDisplayName"]],
            "permission_profiles": permission_profiles,
        }
        if group.get("nodeScope"):
            attributes["node_scope"] = [str(value) for value in group["nodeScope"]]

        keycloak_groups.append(
            {
                "id": _stable_id(realm_name, "group", group_id),
                "name": group_id,
                "path": f"/{group_id}",
                "attributes": attributes,
                "realmRoles": permission_profiles,
                "subGroups": [],
            }
        )

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
        }
        for entity_id in (
            [standard_saml_entity_id] if "Standard" in configured_saml_profiles else []
        ) + ([saml2int_entity_id] if "Saml2Int" in configured_saml_profiles else []):
            attributes[f"saml.persistent.name.id.for.{entity_id}"] = [
                _stable_id(realm_name, "saml-nameid", user["id"])
            ]
            attributes[f"saml.subject.id.for.{entity_id}"] = [
                f"{_stable_id(realm_name, 'saml-subject-id', user['id'])}@northlake.example"
            ]
        keycloak_users.append(
            {
                "id": _stable_id(realm_name, "user", user["id"]),
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
                        "value": user.get("_password", password),
                        "temporary": False,
                    }
                ],
                "requiredActions": [],
                "realmRoles": [f"default-roles-{realm_name}"],
                "groups": sorted(user_groups[user["id"]]),
            }
        )

    role_definitions = [
        {
            "id": _stable_id(realm_name, "role", profile["id"]),
            "name": profile["id"],
            "description": profile.get("intent", profile["displayName"]),
            "composite": False,
            "clientRole": False,
        }
        for profile in manifest.get("permissionProfiles", [])
    ]

    base_url = environment.get("IDENTITY_PUBLIC_BASE_URL", "https://localhost:8443").rstrip("/")
    issuer = f"{base_url}/realms/{realm_name}"
    discovery = f"{issuer}/.well-known/openid-configuration"

    saml_clients: list[dict[str, Any]] = []
    if "Standard" in configured_saml_profiles:
        if standard_profile is None:
            raise RealmGenerationError("The Standard SAML profile is unavailable.")
        saml_clients.append(
            _saml_client(
                realm_name,
                standard_saml_entity_id,
                standard_saml_acs_urls,
                standard_saml_logout_urls,
                application_home_url,
                validation_profile="Standard",
                idp_initiated_url_name=standard_profile.provider_key,
                allowed_claims=standard_profile.allowed_claims,
                enable_single_logout=standard_profile.enable_single_logout,
            )
        )
    if "Saml2Int" in configured_saml_profiles:
        if saml2int_profile is None:
            raise RealmGenerationError("The Saml2Int SAML profile is unavailable.")
        saml_clients.append(
            _saml_client(
                realm_name,
                saml2int_entity_id,
                saml2int_acs_urls,
                saml2int_logout_urls,
                application_home_url,
                validation_profile="Saml2Int",
                idp_initiated_url_name=saml2int_profile.provider_key,
                allowed_claims=saml2int_profile.allowed_claims,
                enable_single_logout=saml2int_profile.enable_single_logout,
                service_provider_certificate=saml2int_certificate,
            )
        )

    oidc_clients = (
        [
            _client(
                realm_name,
                oidc_settings.modern_client_id,
                environment["EEMSUITE_OIDC_CLIENT_SECRET"],
                list(oidc_settings.modern_redirect_uris),
                list(oidc_settings.modern_post_logout_redirect_uris),
                application_home_url,
                oidc_settings.modern_scopes,
                implicit_enabled=False,
                require_pkce=True,
                consent_required=oidc_settings.modern_consent_required,
                par_behavior=oidc_settings.par_behavior,
            ),
            *(
                [
                    _client(
                        realm_name,
                        oidc_settings.legacy_client_id,
                        environment["EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"],
                        list(oidc_settings.legacy_redirect_uris),
                        list(oidc_settings.legacy_post_logout_redirect_uris),
                        application_home_url,
                        oidc_settings.legacy_scopes,
                        implicit_enabled=True,
                        require_pkce=False,
                        consent_required=False,
                        par_behavior="Disable",
                    )
                ]
                if oidc_settings.legacy_enabled
                else []
            ),
        ]
        if enable_oidc and oidc_settings is not None
        else []
    )

    realm = {
        "id": _stable_id(realm_name, "realm", realm_name),
        "realm": realm_name,
        "displayName": provider_display_name,
        "displayNameHtml": f"<strong>{html.escape(provider_display_name)}</strong>",
        "enabled": True,
        "notBefore": 0,
        "defaultSignatureAlgorithm": "RS256",
        "revokeRefreshToken": True,
        "refreshTokenMaxReuse": 0,
        "accessTokenLifespan": (
            oidc_settings.access_token_lifetime_seconds if oidc_settings is not None else 300
        ),
        "accessTokenLifespanForImplicitFlow": (
            oidc_settings.access_token_lifetime_seconds if oidc_settings is not None else 300
        ),
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
        "clientScopes": [
            *_standard_client_scopes(realm_name),
            _northlake_client_scope(realm_name),
        ],
        "clients": [*oidc_clients, *saml_clients],
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
    saml_connection_profiles: dict[str, dict[str, Any]] = {}
    if "Standard" in configured_saml_profiles:
        if standard_profile is None:
            raise RealmGenerationError("The Standard SAML profile is unavailable.")
        saml_connection_profiles["saml"] = {
            "clientId": standard_saml_entity_id,
            "entityId": standard_saml_entity_id,
            "providerKey": standard_profile.provider_key,
            "validationProfile": "Standard",
            "protocol": "saml",
            "redirectUris": standard_saml_acs_urls,
            "assertionConsumerServiceUrls": standard_saml_acs_urls,
            "singleLogoutServiceUrls": standard_saml_logout_urls,
            "defaultAssertionConsumerServiceUrl": standard_saml_acs_urls[0],
            "defaultSingleLogoutServiceUrl": (
                standard_saml_logout_urls[0] if standard_saml_logout_urls else None
            ),
            "nameIdFormat": SAML_NAME_ID_FORMAT_URN,
            "responseBinding": SAML_POST_BINDING_URN,
            "signAuthnRequests": False,
            "wantResponseSigned": True,
            "wantAssertionsSigned": True,
            "wantAssertionsEncrypted": False,
            "subjectBindingKind": standard_profile.subject_binding_kind,
            "subjectAttribute": standard_profile.subject_attribute,
            "allowedClaims": list(standard_profile.allowed_claims),
            "allowedAuthenticationContextClassReferences": list(
                standard_profile.allowed_authentication_context_class_references
            ),
            "allowUnsolicitedResponses": standard_profile.allow_unsolicited_responses,
            "enableSingleLogout": standard_profile.enable_single_logout,
            "idpInitiatedSsoUrl": (
                f"{issuer}/protocol/saml/clients/{standard_profile.provider_key}"
            ),
            "idpInitiatedRelayState": "northlake-standard",
        }
    if "Saml2Int" in configured_saml_profiles:
        if saml2int_profile is None:
            raise RealmGenerationError("The Saml2Int SAML profile is unavailable.")
        saml_connection_profiles["saml2Int"] = {
            "clientId": saml2int_entity_id,
            "entityId": saml2int_entity_id,
            "providerKey": saml2int_profile.provider_key,
            "validationProfile": "Saml2Int",
            "protocol": "saml",
            "redirectUris": saml2int_acs_urls,
            "assertionConsumerServiceUrls": saml2int_acs_urls,
            "singleLogoutServiceUrls": saml2int_logout_urls,
            "defaultAssertionConsumerServiceUrl": saml2int_acs_urls[0],
            "defaultSingleLogoutServiceUrl": (
                saml2int_logout_urls[0] if saml2int_logout_urls else None
            ),
            "nameIdFormat": SAML_NAME_ID_FORMAT_URN,
            "responseBinding": SAML_POST_BINDING_URN,
            "signAuthnRequests": True,
            "wantResponseSigned": True,
            "wantAssertionsSigned": False,
            "wantAssertionsEncrypted": True,
            "serviceProviderCertificateSha256": saml2int_certificate_thumbprint,
            "subjectBindingKind": saml2int_profile.subject_binding_kind,
            "subjectAttribute": saml2int_profile.subject_attribute,
            "allowedClaims": list(saml2int_profile.allowed_claims),
            "allowedAuthenticationContextClassReferences": list(
                saml2int_profile.allowed_authentication_context_class_references
            ),
            "allowUnsolicitedResponses": saml2int_profile.allow_unsolicited_responses,
            "enableSingleLogout": saml2int_profile.enable_single_logout,
            "idpInitiatedSsoUrl": (
                f"{issuer}/protocol/saml/clients/{saml2int_profile.provider_key}"
            ),
            "idpInitiatedRelayState": "northlake-saml2int",
        }
    oidc_connection_profiles = (
        {
            "modern": {
                "clientId": oidc_settings.modern_client_id,
                "clientSecret": environment["EEMSUITE_OIDC_CLIENT_SECRET"],
                "responseType": "code",
                "scope": " ".join(oidc_settings.modern_scopes),
                "redirectUris": list(oidc_settings.modern_redirect_uris),
                "postLogoutRedirectUris": list(
                    oidc_settings.modern_post_logout_redirect_uris
                ),
                "protocolProfile": "Modern",
                "configurationMode": oidc_settings.configuration_mode,
                "parBehavior": oidc_settings.par_behavior,
                "tokenEndpointAuthMethod": oidc_settings.token_endpoint_auth_method,
                "consentRequired": oidc_settings.modern_consent_required,
            },
            **(
                {
                    "legacy": {
                        "clientId": oidc_settings.legacy_client_id,
                        "clientSecret": environment[
                            "EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"
                        ],
                        "responseType": "id_token token",
                        "scope": " ".join(oidc_settings.legacy_scopes),
                        "redirectUris": list(oidc_settings.legacy_redirect_uris),
                        "postLogoutRedirectUris": list(
                            oidc_settings.legacy_post_logout_redirect_uris
                        ),
                        "protocolProfile": "Legacy",
                        "configurationMode": oidc_settings.configuration_mode,
                        "parBehavior": "Disable",
                        "tokenEndpointAuthMethod": (
                            oidc_settings.token_endpoint_auth_method
                        ),
                        "consentRequired": False,
                        "historicalExistingProviderOnly": True,
                    }
                }
                if oidc_settings.legacy_enabled
                else {}
            ),
        }
        if enable_oidc and oidc_settings is not None
        else {}
    )
    oidc_eemsuite_configuration = (
        {
            "modern": {
                "OpenIDConnect": {
                    "Description": f"{provider_display_name} - modern",
                    "ClientID": oidc_settings.modern_client_id,
                    "ClientSecret": environment["EEMSUITE_OIDC_CLIENT_SECRET"],
                    "ResponseType": "code",
                    "Scope": " ".join(oidc_settings.modern_scopes),
                    "DiscoveryEndpoint": discovery,
                    "ProtocolProfile": "Modern",
                    "ParBehavior": oidc_settings.par_behavior,
                    "TokenEndpointAuthMethod": oidc_settings.token_endpoint_auth_method,
                }
            },
            **(
                {
                    "legacy": {
                        "OpenIDConnect": {
                            "Description": f"{provider_display_name} - historical legacy",
                            "ClientID": oidc_settings.legacy_client_id,
                            "ClientSecret": environment[
                                "EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"
                            ],
                            "ResponseType": "id_token token",
                            "Scope": " ".join(oidc_settings.legacy_scopes),
                            "DiscoveryEndpoint": discovery,
                            "ProtocolProfile": "Legacy",
                            "ParBehavior": "Disable",
                            "TokenEndpointAuthMethod": (
                                oidc_settings.token_endpoint_auth_method
                            ),
                        }
                    }
                }
                if oidc_settings.legacy_enabled
                else {}
            ),
        }
        if enable_oidc and oidc_settings is not None
        else {}
    )
    provider_settings = ProviderSettings.from_environment(environment)
    oidc_configuration_preview = (
        oidc_settings.preview(provider_settings) if oidc_settings is not None else None
    )
    connection_profile = {
        "realm": realm_name,
        "realmSource": {
            "manifestId": manifest["id"],
            "manifestVersion": manifest["manifestVersion"],
            "customerScenarioId": manifest["customerScenarioId"],
        },
        "userInventory": {
            "total": len(users),
            "enabled": sum(user["status"] == "active" for user in users),
            "local": sum(user.get("_source") == "local" for user in users),
        },
        "groupInventory": {
            "total": len(source_groups),
            "local": sum(group.get("_source") == "local" for group in source_groups),
        },
        "oidcConfiguration": oidc_configuration_preview,
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
        "adminConsole": f"{base_url}/admin/{realm_name}/console/",
        "masterAdminConsole": f"{base_url}/admin/master/console/",
        "accountConsole": f"{issuer}/account/",
        "clients": {**oidc_connection_profiles, **saml_connection_profiles},
        "testUsers": {
            "active": {
                "username": active_user["username"],
                "subject": _stable_id(realm_name, "user", active_user["id"]),
                "samlNameId": _stable_id(
                    realm_name,
                    "saml-nameid",
                    active_user["id"],
                ),
                "expectedAttributes": _expected_identity_attributes(
                    realm_name,
                    active_user,
                    user_groups,
                    user_companies,
                    user_profiles,
                ),
            },
            "disabled": {
                "username": disabled_user["username"],
                "subject": _stable_id(realm_name, "user", disabled_user["id"]),
                "samlNameId": _stable_id(
                    realm_name,
                    "saml-nameid",
                    disabled_user["id"],
                ),
                "expectedAttributes": _expected_identity_attributes(
                    realm_name,
                    disabled_user,
                    user_groups,
                    user_companies,
                    user_profiles,
                ),
            },
            "password": active_user.get("_password", password),
        },
        "admin": {
            "username": environment.get("KEYCLOAK_ADMIN", "admin"),
            "password": environment["KEYCLOAK_ADMIN_PASSWORD"],
        },
        "eemsuiteConfiguration": {
            **oidc_eemsuite_configuration,
            "samlProfiles": {
                key: {
                    "ProviderKey": value["providerKey"],
                    "DisplayName": (
                        f"{provider_display_name} - SAML2Int"
                        if value["validationProfile"] == "Saml2Int"
                        else f"{provider_display_name} - Standard SAML"
                    ),
                    "IdentityProviderMetadata": f"{issuer}/protocol/saml/descriptor",
                    "ServiceProviderEntityID": value["entityId"],
                    "ValidationProfile": value["validationProfile"],
                    "SubjectBindingKind": value["subjectBindingKind"],
                    "SubjectAttribute": value["subjectAttribute"],
                    "AllowedClaims": value["allowedClaims"],
                    "AllowedAuthenticationContextClassReferences": value[
                        "allowedAuthenticationContextClassReferences"
                    ],
                    "AllowUnsolicitedResponses": value["allowUnsolicitedResponses"],
                    "EnableSingleLogout": value["enableSingleLogout"],
                    "CallbackPath": (
                        f"/saml/{value['providerKey']}/acs"
                    ),
                    "MetadataPath": (
                        f"/saml/{value['providerKey']}/metadata"
                    ),
                    "LogoutPath": (
                        f"/saml/{value['providerKey']}/logout"
                    ),
                }
                for key, value in saml_connection_profiles.items()
            },
        },
    }
    return realm, connection_profile


def generate(
    manifest_path: Path,
    env_path: Path,
    output_path: Path,
    connection_output_path: Path,
    settings_path: Path | None = None,
    user_overlay_path: Path | None = None,
    group_overlay_path: Path | None = None,
    oidc_settings_path: Path | None = None,
    saml_settings_path: Path | None = None,
    saml_certificate_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    environment = _load_env(env_path)
    if settings_path is not None and settings_path.is_file():
        settings_document = load_settings_document(settings_path, environment)
        environment.update(settings_document.settings.to_environment_overlay())
    if oidc_settings_path is not None and oidc_settings_path.is_file():
        oidc_document = load_oidc_settings_document(oidc_settings_path, environment)
        environment.update(oidc_document.settings.to_environment_overlay())
    if saml_settings_path is not None and saml_settings_path.is_file():
        saml_document = load_saml_settings_document(saml_settings_path, environment)
        certificate_path = saml_certificate_path or (
            saml_settings_path.parent / "certs" / "saml2int-sp-public.cer"
        )
        environment.update(
            saml_document.settings.to_environment_overlay(certificate_path)
        )
    return generate_from_environment(
        manifest_path,
        environment,
        output_path,
        connection_output_path,
        user_overlay_path,
        group_overlay_path,
    )


def generate_from_environment(
    manifest_path: Path,
    environment: dict[str, str],
    output_path: Path,
    connection_output_path: Path,
    user_overlay_path: Path | None = None,
    group_overlay_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _load_manifest(manifest_path)
    realm, connection_profile = build_realm(
        manifest,
        environment,
        user_overlay_path,
        group_overlay_path,
    )

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
    parser.add_argument("--settings-file", type=Path)
    parser.add_argument("--users-file", type=Path)
    parser.add_argument("--groups-file", type=Path)
    parser.add_argument("--oidc-settings-file", type=Path)
    parser.add_argument("--saml-settings-file", type=Path)
    parser.add_argument("--saml-certificate-file", type=Path)
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
            args.settings_file.resolve() if args.settings_file else None,
            args.users_file.resolve() if args.users_file else None,
            args.groups_file.resolve() if args.groups_file else None,
            args.oidc_settings_file.resolve() if args.oidc_settings_file else None,
            args.saml_settings_file.resolve() if args.saml_settings_file else None,
            args.saml_certificate_file.resolve() if args.saml_certificate_file else None,
        )
    except (
        OSError,
        RealmGenerationError,
        SettingsValidationError,
        GroupValidationError,
        OidcValidationError,
        SamlValidationError,
        UserValidationError,
        yaml.YAMLError,
    ) as error:
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
