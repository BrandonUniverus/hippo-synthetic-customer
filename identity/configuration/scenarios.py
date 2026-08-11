"""Bounded two-realm scenarios for Phase 6 of the Northlake identity lab."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.configuration.saml import DEFAULT_ALLOWED_CLAIMS
from identity.configuration.settings import REALM_KEY_PATTERN


SCENARIO_SCHEMA_VERSION = 1
SCENARIO_SLOTS = ("labA", "labB")
SCENARIO_PRESETS = ("IsolationBaseline", "SharedSubject", "ClaimDrift")
CLAIM_SHAPES = {
    "Full": {
        "oidc": (
            "groups",
            "synthetic_user_id",
            "primary_company_id",
            "title",
            "synthetic_status",
            "eem_company_ids",
            "eem_permission_profiles",
        ),
        "saml": DEFAULT_ALLOWED_CLAIMS,
    },
    "IdentityOnly": {
        "oidc": ("synthetic_user_id", "primary_company_id"),
        "saml": (
            "username",
            "email",
            "given_name",
            "family_name",
            "synthetic_user_id",
            "primary_company_id",
        ),
    },
    "Minimal": {
        "oidc": ("synthetic_user_id",),
        "saml": ("username", "synthetic_user_id"),
    },
}
CONFIGURATION_MODES = frozenset({"Discovery", "Authority", "Static"})
PAR_BEHAVIORS = frozenset({"Require", "UseIfAvailable", "Disable"})
TOP_LEVEL_KEYS = frozenset(
    {
        "scenarioName",
        "preset",
        "publicBaseUrl",
        "applicationHomeUrl",
        "sharedExternalSubject",
        "realms",
    }
)
REALM_KEYS = frozenset(
    {
        "realmKey",
        "displayName",
        "claimShape",
        "oidcProviderKey",
        "oidcClientId",
        "oidcConfigurationMode",
        "oidcParBehavior",
        "oidcRedirectUris",
        "oidcPostLogoutRedirectUris",
        "samlProviderKey",
        "samlEntityId",
        "samlAssertionConsumerServiceUrls",
        "samlLogoutServiceUrls",
    }
)
_PROVIDER_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class ScenarioValidationError(ValueError):
    """Raised when the bounded two-realm scenario document is invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("Northlake lab scenario is invalid.")


def _text(
    value: Any,
    field: str,
    errors: dict[str, str],
    *,
    minimum: int,
    maximum: int,
) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if (
        not minimum <= len(normalized) <= maximum
        or any(ord(character) < 32 for character in normalized)
    ):
        errors[field] = f"Enter {minimum}-{maximum} printable characters."
    return normalized


def _realm_key(value: Any, field: str, errors: dict[str, str]) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not REALM_KEY_PATTERN.fullmatch(normalized) or normalized == "master":
        errors[field] = "Use a non-master lowercase realm key."
    return normalized


def _provider_key(value: Any, field: str, errors: dict[str, str]) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not _PROVIDER_KEY_PATTERN.fullmatch(normalized):
        errors[field] = "Enter 1-128 letters, numbers, dots, underscores, or hyphens."
    return normalized


def _entity_id(value: Any, field: str, errors: dict[str, str]) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    parsed = urlparse(normalized)
    if (
        not 1 <= len(normalized) <= 1024
        or not parsed.scheme
        or parsed.fragment
        or any(character.isspace() or ord(character) < 32 for character in normalized)
    ):
        errors[field] = "Enter an absolute entity identifier without a fragment."
    return normalized


def _https_url(value: Any, field: str, errors: dict[str, str]) -> str:
    normalized = value.strip().rstrip("/") if isinstance(value, str) else ""
    try:
        parsed = urlparse(normalized)
        parsed.port
    except ValueError:
        parsed = urlparse("")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        errors[field] = "Enter an absolute HTTPS URL without credentials, query, or fragment."
    return normalized


def _https_urls(
    value: Any,
    field: str,
    errors: dict[str, str],
    *,
    suffix: str | None = None,
) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = value.replace(";", "\n").splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []
    urls = tuple(
        candidate.strip()
        for candidate in candidates
        if isinstance(candidate, str) and candidate.strip()
    )
    if not urls:
        errors[field] = "Enter at least one exact HTTPS URL."
    elif len(urls) > 20:
        errors[field] = "Enter no more than 20 URLs."
    elif len(urls) != len(set(urls)):
        errors[field] = "Remove duplicate URLs."
    else:
        for url in urls:
            try:
                parsed = urlparse(url)
                parsed.port
            except ValueError:
                parsed = urlparse("")
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or (suffix is not None and not parsed.path.endswith(suffix))
            ):
                errors[field] = (
                    f"Use exact HTTPS URLs ending in {suffix}."
                    if suffix is not None
                    else "Use exact HTTPS URLs without credentials, query, or fragment."
                )
                break
    return urls


@dataclass(frozen=True)
class LabRealmSettings:
    realm_key: str
    display_name: str
    claim_shape: str
    oidc_provider_key: str
    oidc_client_id: str
    oidc_configuration_mode: str
    oidc_par_behavior: str
    oidc_redirect_uris: tuple[str, ...]
    oidc_post_logout_redirect_uris: tuple[str, ...]
    saml_provider_key: str
    saml_entity_id: str
    saml_assertion_consumer_service_urls: tuple[str, ...]
    saml_logout_service_urls: tuple[str, ...]

    @classmethod
    def from_values(
        cls,
        values: Any,
        slot: str,
        errors: dict[str, str],
    ) -> LabRealmSettings:
        prefix = f"realms.{slot}"
        if not isinstance(values, dict):
            errors[prefix] = "Provide one bounded realm object."
            values = {}
        unknown = sorted(set(values) - REALM_KEYS)
        if unknown:
            errors[prefix] = f"Unknown realm fields: {', '.join(unknown)}."
        missing = sorted(REALM_KEYS - set(values))
        if missing:
            errors[prefix] = f"Missing realm fields: {', '.join(missing)}."

        realm_key = _realm_key(values.get("realmKey"), f"{prefix}.realmKey", errors)
        display_name = _text(
            values.get("displayName"),
            f"{prefix}.displayName",
            errors,
            minimum=3,
            maximum=80,
        )
        claim_shape = values.get("claimShape")
        if claim_shape not in CLAIM_SHAPES:
            errors[f"{prefix}.claimShape"] = "Choose Full, IdentityOnly, or Minimal."
            claim_shape = "Full"
        oidc_provider_key = _provider_key(
            values.get("oidcProviderKey"),
            f"{prefix}.oidcProviderKey",
            errors,
        )
        oidc_client_id = _text(
            values.get("oidcClientId"),
            f"{prefix}.oidcClientId",
            errors,
            minimum=1,
            maximum=255,
        )
        if any(character.isspace() for character in oidc_client_id):
            errors[f"{prefix}.oidcClientId"] = "Client ID cannot contain whitespace."
        configuration_mode = values.get("oidcConfigurationMode")
        if configuration_mode not in CONFIGURATION_MODES:
            errors[f"{prefix}.oidcConfigurationMode"] = (
                "Choose Discovery, Authority, or Static."
            )
            configuration_mode = "Discovery"
        par_behavior = values.get("oidcParBehavior")
        if par_behavior not in PAR_BEHAVIORS:
            errors[f"{prefix}.oidcParBehavior"] = (
                "Choose Require, UseIfAvailable, or Disable."
            )
            par_behavior = "UseIfAvailable"
        oidc_redirects = _https_urls(
            values.get("oidcRedirectUris"),
            f"{prefix}.oidcRedirectUris",
            errors,
        )
        oidc_logout = _https_urls(
            values.get("oidcPostLogoutRedirectUris"),
            f"{prefix}.oidcPostLogoutRedirectUris",
            errors,
        )
        saml_provider_key = _provider_key(
            values.get("samlProviderKey"),
            f"{prefix}.samlProviderKey",
            errors,
        )
        saml_entity_id = _entity_id(
            values.get("samlEntityId"),
            f"{prefix}.samlEntityId",
            errors,
        )
        saml_acs = _https_urls(
            values.get("samlAssertionConsumerServiceUrls"),
            f"{prefix}.samlAssertionConsumerServiceUrls",
            errors,
            suffix=f"/saml/{saml_provider_key}/acs",
        )
        saml_logout = _https_urls(
            values.get("samlLogoutServiceUrls"),
            f"{prefix}.samlLogoutServiceUrls",
            errors,
            suffix=f"/saml/{saml_provider_key}/logout",
        )
        return cls(
            realm_key=realm_key,
            display_name=display_name,
            claim_shape=claim_shape,
            oidc_provider_key=oidc_provider_key,
            oidc_client_id=oidc_client_id,
            oidc_configuration_mode=configuration_mode,
            oidc_par_behavior=par_behavior,
            oidc_redirect_uris=oidc_redirects,
            oidc_post_logout_redirect_uris=oidc_logout,
            saml_provider_key=saml_provider_key,
            saml_entity_id=saml_entity_id,
            saml_assertion_consumer_service_urls=saml_acs,
            saml_logout_service_urls=saml_logout,
        )

    def to_values(self) -> dict[str, Any]:
        return {
            "realmKey": self.realm_key,
            "displayName": self.display_name,
            "claimShape": self.claim_shape,
            "oidcProviderKey": self.oidc_provider_key,
            "oidcClientId": self.oidc_client_id,
            "oidcConfigurationMode": self.oidc_configuration_mode,
            "oidcParBehavior": self.oidc_par_behavior,
            "oidcRedirectUris": list(self.oidc_redirect_uris),
            "oidcPostLogoutRedirectUris": list(self.oidc_post_logout_redirect_uris),
            "samlProviderKey": self.saml_provider_key,
            "samlEntityId": self.saml_entity_id,
            "samlAssertionConsumerServiceUrls": list(
                self.saml_assertion_consumer_service_urls
            ),
            "samlLogoutServiceUrls": list(self.saml_logout_service_urls),
        }

    @property
    def oidc_allowed_claims(self) -> tuple[str, ...]:
        return tuple(CLAIM_SHAPES[self.claim_shape]["oidc"])

    @property
    def saml_allowed_claims(self) -> tuple[str, ...]:
        return tuple(CLAIM_SHAPES[self.claim_shape]["saml"])


@dataclass(frozen=True)
class ScenarioSettings:
    scenario_name: str
    preset: str
    public_base_url: str
    application_home_url: str
    shared_external_subject: bool
    realms: dict[str, LabRealmSettings]

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> ScenarioSettings:
        errors: dict[str, str] = {}
        unknown = sorted(set(values) - TOP_LEVEL_KEYS)
        if unknown:
            errors["_form"] = f"Unknown scenario fields: {', '.join(unknown)}."
        missing = sorted(TOP_LEVEL_KEYS - set(values))
        if missing:
            errors["_form"] = f"Missing scenario fields: {', '.join(missing)}."
        scenario_name = _text(
            values.get("scenarioName"),
            "scenarioName",
            errors,
            minimum=3,
            maximum=80,
        )
        preset = values.get("preset")
        if preset not in SCENARIO_PRESETS:
            errors["preset"] = "Choose a named Northlake scenario preset."
            preset = "SharedSubject"
        public_base_url = _https_url(values.get("publicBaseUrl"), "publicBaseUrl", errors)
        application_home_url = _https_url(
            values.get("applicationHomeUrl"),
            "applicationHomeUrl",
            errors,
        )
        shared_external_subject = values.get("sharedExternalSubject")
        if not isinstance(shared_external_subject, bool):
            errors["sharedExternalSubject"] = "Choose the external-subject relationship."
            shared_external_subject = True
        realm_values = values.get("realms")
        if not isinstance(realm_values, dict):
            errors["realms"] = "Provide labA and labB realm objects."
            realm_values = {}
        elif set(realm_values) != set(SCENARIO_SLOTS):
            errors["realms"] = "The bounded scenario must contain exactly labA and labB."
        realms = {
            slot: LabRealmSettings.from_values(realm_values.get(slot), slot, errors)
            for slot in SCENARIO_SLOTS
        }
        if realms["labA"].realm_key == realms["labB"].realm_key:
            errors["realms.labB.realmKey"] = "The two realms need distinct realm keys."
        if realms["labA"].oidc_provider_key == realms["labB"].oidc_provider_key:
            errors["realms.labB.oidcProviderKey"] = "The two OIDC providers need distinct keys."
        if realms["labA"].saml_provider_key == realms["labB"].saml_provider_key:
            errors["realms.labB.samlProviderKey"] = "The two SAML providers need distinct keys."
        if realms["labA"].saml_entity_id == realms["labB"].saml_entity_id:
            errors["realms.labB.samlEntityId"] = "The two SAML SP registrations need distinct IDs."
        if errors:
            raise ScenarioValidationError(errors)
        return cls(
            scenario_name=scenario_name,
            preset=preset,
            public_base_url=public_base_url,
            application_home_url=application_home_url,
            shared_external_subject=shared_external_subject,
            realms=realms,
        )

    def to_values(self) -> dict[str, Any]:
        return {
            "scenarioName": self.scenario_name,
            "preset": self.preset,
            "publicBaseUrl": self.public_base_url,
            "applicationHomeUrl": self.application_home_url,
            "sharedExternalSubject": self.shared_external_subject,
            "realms": {
                slot: self.realms[slot].to_values() for slot in SCENARIO_SLOTS
            },
        }

    def subject_namespace(self, slot: str) -> str:
        return "northlake-lab-shared" if self.shared_external_subject else self.realms[slot].realm_key

    def environment_for(
        self,
        slot: str,
        base_environment: Mapping[str, str],
    ) -> dict[str, str]:
        realm = self.realms[slot]
        environment = dict(base_environment)
        environment.update(
            {
                "IDENTITY_PUBLIC_BASE_URL": self.public_base_url,
                "IDENTITY_HOST": urlparse(self.public_base_url).hostname or "localhost",
                "IDENTITY_HTTPS_PORT": str(urlparse(self.public_base_url).port or 443),
                "NORTHLAKE_REALM_KEY": realm.realm_key,
                "NORTHLAKE_SUBJECT_NAMESPACE": self.subject_namespace(slot),
                "NORTHLAKE_PROVIDER_DISPLAY_NAME": realm.display_name,
                "NORTHLAKE_ENABLE_OIDC": "true",
                "NORTHLAKE_ENABLE_SAML": "true",
                "NORTHLAKE_CUSTOMER_SITE_ENABLED": "true",
                "EEMSUITE_APPLICATION_HOME_URL": self.application_home_url,
                "NORTHLAKE_OIDC_PROVIDER_KEY": realm.oidc_provider_key,
                "NORTHLAKE_OIDC_CONFIGURATION_MODE": realm.oidc_configuration_mode,
                "NORTHLAKE_OIDC_PAR_BEHAVIOR": realm.oidc_par_behavior,
                "NORTHLAKE_OIDC_TOKEN_ENDPOINT_AUTH_METHOD": "ClientSecretPost",
                "NORTHLAKE_OIDC_MODERN_CLIENT_ID": realm.oidc_client_id,
                "NORTHLAKE_OIDC_MODERN_REDIRECT_URIS": ";".join(realm.oidc_redirect_uris),
                "NORTHLAKE_OIDC_MODERN_POST_LOGOUT_REDIRECT_URIS": ";".join(
                    realm.oidc_post_logout_redirect_uris
                ),
                "NORTHLAKE_OIDC_MODERN_SCOPES": "openid profile email northlake",
                "NORTHLAKE_OIDC_MODERN_CONSENT_REQUIRED": "false",
                "NORTHLAKE_OIDC_LEGACY_ENABLED": "false",
                "NORTHLAKE_OIDC_ALLOWED_CLAIMS": ";".join(realm.oidc_allowed_claims),
                "EEMSUITE_SAML_PROFILES": "Standard",
                "NORTHLAKE_SAML_STANDARD_PROVIDER_KEY": realm.saml_provider_key,
                "EEMSUITE_SAML_STANDARD_ENTITY_ID": realm.saml_entity_id,
                "EEMSUITE_SAML_STANDARD_ACS_URLS": ";".join(
                    realm.saml_assertion_consumer_service_urls
                ),
                "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": ";".join(
                    realm.saml_logout_service_urls
                ),
                "NORTHLAKE_SAML_STANDARD_SUBJECT_BINDING_KIND": "PersistentNameId",
                "NORTHLAKE_SAML_STANDARD_SUBJECT_ATTRIBUTE": "",
                "NORTHLAKE_SAML_STANDARD_ALLOWED_CLAIMS": ";".join(
                    realm.saml_allowed_claims
                ),
                "NORTHLAKE_SAML_STANDARD_ALLOWED_AUTHENTICATION_CONTEXTS": (
                    "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified"
                ),
                "NORTHLAKE_SAML_STANDARD_ALLOW_UNSOLICITED_RESPONSES": "false",
                "NORTHLAKE_SAML_STANDARD_ENABLE_SINGLE_LOGOUT": "true",
            }
        )
        return environment

    def preview(self) -> dict[str, Any]:
        realm_previews: dict[str, Any] = {}
        for slot in SCENARIO_SLOTS:
            realm = self.realms[slot]
            issuer = f"{self.public_base_url}/realms/{realm.realm_key}"
            realm_previews[slot] = {
                "realmKey": realm.realm_key,
                "displayName": realm.display_name,
                "subjectNamespace": self.subject_namespace(slot),
                "claimShape": realm.claim_shape,
                "issuer": issuer,
                "discoveryEndpoint": f"{issuer}/.well-known/openid-configuration",
                "jwksEndpoint": f"{issuer}/protocol/openid-connect/certs",
                "samlMetadataEndpoint": f"{issuer}/protocol/saml/descriptor",
                "samlEntityId": issuer,
                "oidc": {
                    "providerKey": realm.oidc_provider_key,
                    "displayName": f"{realm.display_name} - Modern OIDC",
                    "clientIdentifier": realm.oidc_client_id,
                    "clientSecretSource": "identity/.env:EEMSUITE_OIDC_CLIENT_SECRET",
                    "configurationMode": realm.oidc_configuration_mode,
                    "metadataAddress": (
                        f"{issuer}/.well-known/openid-configuration"
                        if realm.oidc_configuration_mode == "Discovery"
                        else issuer if realm.oidc_configuration_mode == "Authority" else None
                    ),
                    "authority": issuer,
                    "protocolProfile": "Modern",
                    "parBehavior": realm.oidc_par_behavior,
                    "tokenEndpointAuthMethod": "ClientSecretPost",
                    "registeredRedirectUris": list(realm.oidc_redirect_uris),
                    "registeredPostLogoutRedirectUris": list(
                        realm.oidc_post_logout_redirect_uris
                    ),
                    "scopes": ["openid", "profile", "email", "northlake"],
                    "northlakeClaims": list(realm.oidc_allowed_claims),
                },
                "saml": {
                    "ProviderKey": realm.saml_provider_key,
                    "DisplayName": f"{realm.display_name} - Standard SAML",
                    "IdentityProviderMetadata": f"{issuer}/protocol/saml/descriptor",
                    "IdentityProviderEntityId": issuer,
                    "ServiceProviderEntityId": realm.saml_entity_id,
                    "ValidationProfile": "Standard",
                    "SubjectBindingKind": "PersistentNameId",
                    "AllowedClaims": list(realm.saml_allowed_claims),
                    "AllowedAuthenticationContextClassReferences": [
                        "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified"
                    ],
                    "AllowUnsolicitedResponses": False,
                    "EnableSingleLogout": True,
                    "CallbackPath": f"/saml/{realm.saml_provider_key}/acs",
                    "CallbackUris": list(realm.saml_assertion_consumer_service_urls),
                    "MetadataPath": f"/saml/{realm.saml_provider_key}/metadata",
                    "LogoutPath": f"/saml/{realm.saml_provider_key}/logout",
                    "LogoutUris": list(realm.saml_logout_service_urls),
                },
            }
        return {
            "scenarioName": self.scenario_name,
            "preset": self.preset,
            "sharedExternalSubject": self.shared_external_subject,
            "expectedSubjectRelationship": (
                "equal-subject-distinct-issuer"
                if self.shared_external_subject
                else "distinct-subject-distinct-issuer"
            ),
            "realms": realm_previews,
            "assertions": {
                "distinctOidcIssuers": (
                    realm_previews["labA"]["issuer"] != realm_previews["labB"]["issuer"]
                ),
                "distinctSamlIdpEntities": (
                    realm_previews["labA"]["samlEntityId"]
                    != realm_previews["labB"]["samlEntityId"]
                ),
                "distinctProviderKeys": True,
            },
        }

    def redacted_export(self) -> dict[str, Any]:
        values = self.to_values()
        canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {
            "schemaVersion": SCENARIO_SCHEMA_VERSION,
            "values": values,
            "preview": self.preview(),
            "secretSources": {
                "oidcClientSecret": "identity/.env:EEMSUITE_OIDC_CLIENT_SECRET",
                "syntheticUserPassword": "identity/.env:SYNTHETIC_USER_PASSWORD",
                "keycloakAdministration": "identity/.env:KEYCLOAK_ADMIN_PASSWORD",
            },
            "configurationSha256": hashlib.sha256(canonical).hexdigest().upper(),
            "redacted": True,
        }

    def clone(self, source_slot: str, target_slot: str) -> ScenarioSettings:
        if source_slot not in SCENARIO_SLOTS or target_slot not in SCENARIO_SLOTS:
            raise ScenarioValidationError({"_form": "Clone requires labA and labB slots."})
        if source_slot == target_slot:
            raise ScenarioValidationError({"_form": "Clone source and target must differ."})
        source = self.realms[source_slot]
        target = self.realms[target_slot]
        target_values = target.to_values()
        target_values.update(
            {
                "claimShape": source.claim_shape,
                "oidcConfigurationMode": source.oidc_configuration_mode,
                "oidcParBehavior": source.oidc_par_behavior,
                "oidcRedirectUris": list(source.oidc_redirect_uris),
                "oidcPostLogoutRedirectUris": list(source.oidc_post_logout_redirect_uris),
            }
        )
        values = self.to_values()
        values["realms"][target_slot] = target_values
        return ScenarioSettings.from_values(values)


@dataclass(frozen=True)
class ScenarioSettingsDocument:
    settings: ScenarioSettings
    applied_realm_keys: dict[str, str | None]
    updated_at_utc: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": SCENARIO_SCHEMA_VERSION,
            "values": self.settings.to_values(),
            "appliedRealmKeys": {
                slot: self.applied_realm_keys.get(slot) for slot in SCENARIO_SLOTS
            },
            "updatedAtUtc": self.updated_at_utc or datetime.now(UTC).isoformat(),
        }


def _realm_defaults(
    slot: str,
    *,
    claim_shape: str,
    configuration_mode: str,
    par_behavior: str,
    oidc_redirects: tuple[str, ...],
    oidc_logout: tuple[str, ...],
) -> dict[str, Any]:
    suffix = "a" if slot == "labA" else "b"
    realm_key = f"northlake-lab-{suffix}"
    saml_provider_key = f"{realm_key}-saml"
    return {
        "realmKey": realm_key,
        "displayName": f"Northlake Identity Lab {suffix.upper()}",
        "claimShape": claim_shape,
        "oidcProviderKey": f"{realm_key}-oidc",
        "oidcClientId": f"eemsuite-web-{realm_key}",
        "oidcConfigurationMode": configuration_mode,
        "oidcParBehavior": par_behavior,
        "oidcRedirectUris": list(oidc_redirects),
        "oidcPostLogoutRedirectUris": list(oidc_logout),
        "samlProviderKey": saml_provider_key,
        "samlEntityId": f"urn:energyhippo:eemsuite-web:saml:{realm_key}",
        "samlAssertionConsumerServiceUrls": [
            f"https://localhost/Hippo/saml/{saml_provider_key}/acs"
        ],
        "samlLogoutServiceUrls": [
            f"https://localhost/Hippo/saml/{saml_provider_key}/logout"
        ],
    }


def preset_settings(
    preset: str,
    environment: Mapping[str, str],
) -> ScenarioSettings:
    if preset not in SCENARIO_PRESETS:
        raise ScenarioValidationError({"preset": "Unknown Northlake scenario preset."})
    baseline_redirects = tuple(
        value.strip()
        for value in environment.get(
            "EEMSUITE_OIDC_REDIRECT_URIS",
            "https://localhost:7310/signin-oidc;https://localhost/Hippo/signin-oidc",
        ).split(";")
        if value.strip()
    )
    shared_subject = preset != "IsolationBaseline"
    realm_b_shape = "IdentityOnly" if preset == "ClaimDrift" else "Full"
    values = {
        "scenarioName": {
            "IsolationBaseline": "Two-realm issuer isolation",
            "SharedSubject": "Same subject across two issuers",
            "ClaimDrift": "Two-realm claim-shape drift",
        }[preset],
        "preset": preset,
        "publicBaseUrl": environment.get(
            "IDENTITY_PUBLIC_BASE_URL",
            "https://localhost:8443",
        ),
        "applicationHomeUrl": environment.get(
            "EEMSUITE_APPLICATION_HOME_URL",
            "https://localdev.energyhippo.com/Hippo/",
        ),
        "sharedExternalSubject": shared_subject,
        "realms": {
            "labA": _realm_defaults(
                "labA",
                claim_shape="Full",
                configuration_mode="Discovery",
                par_behavior="Require",
                oidc_redirects=baseline_redirects,
                oidc_logout=baseline_redirects,
            ),
            "labB": _realm_defaults(
                "labB",
                claim_shape=realm_b_shape,
                configuration_mode=("Static" if preset == "ClaimDrift" else "Authority"),
                par_behavior="Disable",
                oidc_redirects=baseline_redirects,
                oidc_logout=baseline_redirects,
            ),
        },
    }
    return ScenarioSettings.from_values(values)


def load_scenario_document(
    path: Path,
    default_environment: Mapping[str, str],
) -> ScenarioSettingsDocument:
    if not path.is_file():
        return ScenarioSettingsDocument(
            settings=preset_settings("SharedSubject", default_environment),
            applied_realm_keys={slot: None for slot in SCENARIO_SLOTS},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScenarioValidationError(
            {"_form": f"Unable to read saved scenario settings: {error}."}
        ) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != SCENARIO_SCHEMA_VERSION:
        raise ScenarioValidationError({"_form": "Unsupported scenario settings document."})
    if set(payload) != {"schemaVersion", "values", "appliedRealmKeys", "updatedAtUtc"}:
        raise ScenarioValidationError({"_form": "Scenario document contains unknown fields."})
    values = payload.get("values")
    applied = payload.get("appliedRealmKeys")
    updated = payload.get("updatedAtUtc")
    if not isinstance(values, dict):
        raise ScenarioValidationError({"_form": "Scenario document has no values object."})
    if not isinstance(applied, dict) or set(applied) != set(SCENARIO_SLOTS):
        raise ScenarioValidationError({"_form": "Scenario applied-realm state is invalid."})
    if any(value is not None and not isinstance(value, str) for value in applied.values()):
        raise ScenarioValidationError({"_form": "Scenario applied-realm key is invalid."})
    if updated is not None and not isinstance(updated, str):
        raise ScenarioValidationError({"_form": "Scenario settings timestamp is invalid."})
    return ScenarioSettingsDocument(
        settings=ScenarioSettings.from_values(values),
        applied_realm_keys=dict(applied),
        updated_at_utc=updated,
    )


def write_scenario_document(path: Path, document: ScenarioSettingsDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document.to_json(), indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def scenario_diff(
    before: ScenarioSettings,
    after: ScenarioSettings,
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []

    def compare(path: str, left: Any, right: Any) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                compare(f"{path}.{key}" if path else key, left.get(key), right.get(key))
        elif left != right:
            differences.append({"path": path, "before": left, "after": right})

    compare("", before.to_values(), after.to_values())
    return differences


def scenario_realm_path(output_directory: Path, realm_key: str) -> Path:
    if not REALM_KEY_PATTERN.fullmatch(realm_key) or realm_key == "master":
        raise ScenarioValidationError({"realmKey": "Use a non-master lowercase realm key."})
    return output_directory / f"{realm_key}-realm.json"


def scenario_connection_path(output_directory: Path, slot: str) -> Path:
    return output_directory / slot / "connection.json"


def generate_scenario_realm(
    settings: ScenarioSettings,
    slot: str,
    base_environment: Mapping[str, str],
    manifest_path: Path,
    realm_output_path: Path,
    connection_output_path: Path,
    user_overlay_path: Path | None = None,
    group_overlay_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if slot not in SCENARIO_SLOTS:
        raise ScenarioValidationError({"_form": "Unknown lab realm slot."})
    from identity.realm.generate_realm import generate_from_environment

    realm, connection = generate_from_environment(
        manifest_path,
        settings.environment_for(slot, base_environment),
        realm_output_path,
        connection_output_path,
        user_overlay_path,
        group_overlay_path,
    )
    connection["scenario"] = {
        "slot": slot,
        "scenarioName": settings.scenario_name,
        "preset": settings.preset,
        "claimShape": settings.realms[slot].claim_shape,
        "sharedExternalSubject": settings.shared_external_subject,
    }
    temporary_path = connection_output_path.with_suffix(
        f"{connection_output_path.suffix}.tmp"
    )
    temporary_path.write_text(
        json.dumps(connection, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, connection_output_path)
    return realm, connection


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate bounded Northlake lab realms.")
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--realm-output-directory", required=True, type=Path)
    parser.add_argument("--connection-output-directory", required=True, type=Path)
    parser.add_argument("--user-overlay", type=Path)
    parser.add_argument("--group-overlay", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    from identity.realm.generate_realm import _load_env

    try:
        environment = _load_env(args.env_file.resolve())
        document = load_scenario_document(args.settings_file.resolve(), environment)
        realm_output_directory = args.realm_output_directory.resolve()
        for slot in SCENARIO_SLOTS:
            realm_key = document.settings.realms[slot].realm_key
            realm_output_path = scenario_realm_path(realm_output_directory, realm_key)
            generate_scenario_realm(
                document.settings,
                slot,
                environment,
                args.manifest.resolve(),
                realm_output_path,
                scenario_connection_path(
                    args.connection_output_directory.resolve(),
                    slot,
                ),
                args.user_overlay.resolve() if args.user_overlay else None,
                args.group_overlay.resolve() if args.group_overlay else None,
            )
            legacy_realm_path = realm_output_directory / f"northlake-{slot.lower()}-realm.json"
            if legacy_realm_path != realm_output_path:
                legacy_realm_path.unlink(missing_ok=True)
            previous_realm_key = document.applied_realm_keys.get(slot)
            if previous_realm_key and previous_realm_key != realm_key:
                scenario_realm_path(realm_output_directory, previous_realm_key).unlink(missing_ok=True)
    except (OSError, ScenarioValidationError, ValueError) as error:
        detail = error.errors if isinstance(error, ScenarioValidationError) else str(error)
        print(json.dumps({"errors": detail}), file=os.sys.stderr)
        return 1
    print("[OK] Generated northlake-lab-a and northlake-lab-b scenario realms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
