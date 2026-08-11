"""Typed Phase 4 OIDC profiles for the Northlake identity lab."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.configuration.settings import ProviderSettings


OIDC_SETTINGS_SCHEMA_VERSION = 1
CONFIGURATION_MODES = frozenset({"Authority", "Discovery", "Static"})
PAR_BEHAVIORS = frozenset({"UseIfAvailable", "Require", "Disable"})
TOKEN_ENDPOINT_AUTH_METHODS = frozenset({"ClientSecretPost", "ClientSecretBasic"})
KNOWN_SCOPES = frozenset({"openid", "profile", "email", "northlake", "offline_access"})
OIDC_FIELD_KEYS = frozenset(
    {
        "configurationMode",
        "parBehavior",
        "tokenEndpointAuthMethod",
        "accessTokenLifetimeSeconds",
        "modernClientId",
        "modernRedirectUris",
        "modernPostLogoutRedirectUris",
        "modernScopes",
        "modernConsentRequired",
        "legacyEnabled",
        "legacyClientId",
        "legacyRedirectUris",
        "legacyPostLogoutRedirectUris",
        "legacyScopes",
    }
)


class OidcValidationError(ValueError):
    """Raised when the bounded Northlake OIDC profile document is invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("OIDC profile configuration is invalid.")


def _environment_boolean(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise OidcValidationError({"_form": f"Invalid OIDC boolean environment value: {value}."})


def _environment_list(value: str | None, defaults: tuple[str, ...]) -> list[str]:
    if value is None or not value.strip():
        return list(defaults)
    return [item.strip() for item in value.split(";") if item.strip()]


def _client_id(value: Any, field: str, errors: dict[str, str]) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if (
        not 3 <= len(normalized) <= 128
        or any(character.isspace() or ord(character) < 33 or ord(character) > 126 for character in normalized)
    ):
        errors[field] = "Enter 3-128 visible ASCII characters without whitespace."
    return normalized


def _uri_list(
    value: Any,
    field: str,
    errors: dict[str, str],
    *,
    required: bool,
) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = value.replace(";", "\n").splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []
    items = tuple(item.strip() for item in candidates if isinstance(item, str) and item.strip())
    if required and not items:
        errors[field] = "Enter at least one exact HTTPS URL."
        return items
    if len(items) > 20:
        errors[field] = "Enter no more than 20 URLs."
        return items
    if len(items) != len(set(items)):
        errors[field] = "Remove duplicate URLs."
        return items
    for item in items:
        try:
            parsed = urlparse(item)
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
            errors[field] = f"Invalid exact HTTPS URL: {item}"
            break
    return items


def _scopes(value: Any, field: str, errors: dict[str, str]) -> tuple[str, ...]:
    if isinstance(value, str):
        items = tuple(
            item.strip()
            for item in value.replace(";", " ").replace("\n", " ").split(" ")
            if item.strip()
        )
    elif isinstance(value, list):
        items = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    else:
        items = ()
    if not items or "openid" not in items:
        errors[field] = "Include the required openid scope."
    elif len(items) != len(set(items)):
        errors[field] = "Remove duplicate scopes."
    else:
        unknown = sorted(set(items) - KNOWN_SCOPES)
        if unknown:
            errors[field] = f"Unsupported Northlake scope: {unknown[0]}."
    return items


@dataclass(frozen=True)
class OidcSettings:
    configuration_mode: str
    par_behavior: str
    token_endpoint_auth_method: str
    access_token_lifetime_seconds: int
    modern_client_id: str
    modern_redirect_uris: tuple[str, ...]
    modern_post_logout_redirect_uris: tuple[str, ...]
    modern_scopes: tuple[str, ...]
    modern_consent_required: bool
    legacy_enabled: bool
    legacy_client_id: str
    legacy_redirect_uris: tuple[str, ...]
    legacy_post_logout_redirect_uris: tuple[str, ...]
    legacy_scopes: tuple[str, ...]

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> OidcSettings:
        errors: dict[str, str] = {}
        unknown_keys = sorted(set(values) - OIDC_FIELD_KEYS)
        if unknown_keys:
            errors["_form"] = f"Unknown OIDC fields: {', '.join(unknown_keys)}."

        configuration_mode = values.get("configurationMode")
        if configuration_mode not in CONFIGURATION_MODES:
            errors["configurationMode"] = "Choose Authority, Discovery, or Static."
            configuration_mode = "Discovery"
        par_behavior = values.get("parBehavior")
        if par_behavior not in PAR_BEHAVIORS:
            errors["parBehavior"] = "Choose UseIfAvailable, Require, or Disable."
            par_behavior = "UseIfAvailable"
        token_auth_method = values.get("tokenEndpointAuthMethod")
        if token_auth_method not in TOKEN_ENDPOINT_AUTH_METHODS:
            errors["tokenEndpointAuthMethod"] = (
                "Choose ClientSecretPost or ClientSecretBasic."
            )
            token_auth_method = "ClientSecretPost"

        lifetime_value = values.get("accessTokenLifetimeSeconds")
        try:
            access_token_lifetime = int(lifetime_value) if not isinstance(lifetime_value, bool) else 0
        except (TypeError, ValueError):
            access_token_lifetime = 0
        if not 60 <= access_token_lifetime <= 3600:
            errors["accessTokenLifetimeSeconds"] = "Enter 60-3600 seconds."

        modern_client_id = _client_id(values.get("modernClientId"), "modernClientId", errors)
        modern_redirect_uris = _uri_list(
            values.get("modernRedirectUris"),
            "modernRedirectUris",
            errors,
            required=True,
        )
        modern_post_logout_uris = _uri_list(
            values.get("modernPostLogoutRedirectUris"),
            "modernPostLogoutRedirectUris",
            errors,
            required=True,
        )
        modern_scopes = _scopes(values.get("modernScopes"), "modernScopes", errors)
        modern_consent_required = values.get("modernConsentRequired")
        if not isinstance(modern_consent_required, bool):
            errors["modernConsentRequired"] = "Choose whether provider consent is required."
            modern_consent_required = True

        legacy_enabled = values.get("legacyEnabled")
        if not isinstance(legacy_enabled, bool):
            errors["legacyEnabled"] = "Choose whether the historical client is enabled."
            legacy_enabled = True
        legacy_client_id = _client_id(values.get("legacyClientId"), "legacyClientId", errors)
        legacy_redirect_uris = _uri_list(
            values.get("legacyRedirectUris"),
            "legacyRedirectUris",
            errors,
            required=legacy_enabled,
        )
        legacy_post_logout_uris = _uri_list(
            values.get("legacyPostLogoutRedirectUris"),
            "legacyPostLogoutRedirectUris",
            errors,
            required=legacy_enabled,
        )
        legacy_scopes = _scopes(values.get("legacyScopes"), "legacyScopes", errors)

        if modern_client_id and legacy_enabled and modern_client_id == legacy_client_id:
            errors["legacyClientId"] = "Modern and Historical Legacy need distinct client ids."
        if errors:
            raise OidcValidationError(errors)
        return cls(
            configuration_mode=configuration_mode,
            par_behavior=par_behavior,
            token_endpoint_auth_method=token_auth_method,
            access_token_lifetime_seconds=access_token_lifetime,
            modern_client_id=modern_client_id,
            modern_redirect_uris=modern_redirect_uris,
            modern_post_logout_redirect_uris=modern_post_logout_uris,
            modern_scopes=modern_scopes,
            modern_consent_required=modern_consent_required,
            legacy_enabled=legacy_enabled,
            legacy_client_id=legacy_client_id,
            legacy_redirect_uris=legacy_redirect_uris,
            legacy_post_logout_redirect_uris=legacy_post_logout_uris,
            legacy_scopes=legacy_scopes,
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> OidcSettings:
        redirect_defaults = (
            "https://localhost:7310/signin-oidc",
            "https://localdev.energyhippo.com/Hippo/signin-oidc",
            "https://localhost/Hippo/signin-oidc",
        )
        baseline_redirects = tuple(
            _environment_list(environment.get("EEMSUITE_OIDC_REDIRECT_URIS"), redirect_defaults)
        )
        modern_redirects = _environment_list(
            environment.get("NORTHLAKE_OIDC_MODERN_REDIRECT_URIS"),
            baseline_redirects,
        )
        legacy_redirects = _environment_list(
            environment.get("NORTHLAKE_OIDC_LEGACY_REDIRECT_URIS"),
            baseline_redirects,
        )
        return cls.from_values(
            {
                "configurationMode": environment.get(
                    "NORTHLAKE_OIDC_CONFIGURATION_MODE",
                    "Discovery",
                ),
                "parBehavior": environment.get(
                    "NORTHLAKE_OIDC_PAR_BEHAVIOR",
                    "UseIfAvailable",
                ),
                "tokenEndpointAuthMethod": environment.get(
                    "NORTHLAKE_OIDC_TOKEN_ENDPOINT_AUTH_METHOD",
                    "ClientSecretPost",
                ),
                "accessTokenLifetimeSeconds": environment.get(
                    "NORTHLAKE_OIDC_ACCESS_TOKEN_LIFETIME_SECONDS",
                    "300",
                ),
                "modernClientId": environment.get(
                    "NORTHLAKE_OIDC_MODERN_CLIENT_ID",
                    "eemsuite-web",
                ),
                "modernRedirectUris": modern_redirects,
                "modernPostLogoutRedirectUris": _environment_list(
                    environment.get("NORTHLAKE_OIDC_MODERN_POST_LOGOUT_REDIRECT_URIS"),
                    tuple(modern_redirects),
                ),
                "modernScopes": environment.get(
                    "NORTHLAKE_OIDC_MODERN_SCOPES",
                    "openid profile email northlake",
                ),
                "modernConsentRequired": _environment_boolean(
                    environment.get("NORTHLAKE_OIDC_MODERN_CONSENT_REQUIRED"),
                    True,
                ),
                "legacyEnabled": _environment_boolean(
                    environment.get("NORTHLAKE_OIDC_LEGACY_ENABLED"),
                    True,
                ),
                "legacyClientId": environment.get(
                    "NORTHLAKE_OIDC_LEGACY_CLIENT_ID",
                    "eemsuite-web-legacy",
                ),
                "legacyRedirectUris": legacy_redirects,
                "legacyPostLogoutRedirectUris": _environment_list(
                    environment.get("NORTHLAKE_OIDC_LEGACY_POST_LOGOUT_REDIRECT_URIS"),
                    tuple(legacy_redirects),
                ),
                "legacyScopes": environment.get(
                    "NORTHLAKE_OIDC_LEGACY_SCOPES",
                    "openid profile email northlake",
                ),
            }
        )

    def to_values(self) -> dict[str, Any]:
        return {
            "configurationMode": self.configuration_mode,
            "parBehavior": self.par_behavior,
            "tokenEndpointAuthMethod": self.token_endpoint_auth_method,
            "accessTokenLifetimeSeconds": self.access_token_lifetime_seconds,
            "modernClientId": self.modern_client_id,
            "modernRedirectUris": list(self.modern_redirect_uris),
            "modernPostLogoutRedirectUris": list(self.modern_post_logout_redirect_uris),
            "modernScopes": list(self.modern_scopes),
            "modernConsentRequired": self.modern_consent_required,
            "legacyEnabled": self.legacy_enabled,
            "legacyClientId": self.legacy_client_id,
            "legacyRedirectUris": list(self.legacy_redirect_uris),
            "legacyPostLogoutRedirectUris": list(self.legacy_post_logout_redirect_uris),
            "legacyScopes": list(self.legacy_scopes),
        }

    def to_environment_overlay(self) -> dict[str, str]:
        return {
            "NORTHLAKE_OIDC_CONFIGURATION_MODE": self.configuration_mode,
            "NORTHLAKE_OIDC_PAR_BEHAVIOR": self.par_behavior,
            "NORTHLAKE_OIDC_TOKEN_ENDPOINT_AUTH_METHOD": self.token_endpoint_auth_method,
            "NORTHLAKE_OIDC_ACCESS_TOKEN_LIFETIME_SECONDS": str(
                self.access_token_lifetime_seconds
            ),
            "NORTHLAKE_OIDC_MODERN_CLIENT_ID": self.modern_client_id,
            "NORTHLAKE_OIDC_MODERN_REDIRECT_URIS": ";".join(self.modern_redirect_uris),
            "NORTHLAKE_OIDC_MODERN_POST_LOGOUT_REDIRECT_URIS": ";".join(
                self.modern_post_logout_redirect_uris
            ),
            "NORTHLAKE_OIDC_MODERN_SCOPES": " ".join(self.modern_scopes),
            "NORTHLAKE_OIDC_MODERN_CONSENT_REQUIRED": str(
                self.modern_consent_required
            ).lower(),
            "NORTHLAKE_OIDC_LEGACY_ENABLED": str(self.legacy_enabled).lower(),
            "NORTHLAKE_OIDC_LEGACY_CLIENT_ID": self.legacy_client_id,
            "NORTHLAKE_OIDC_LEGACY_REDIRECT_URIS": ";".join(self.legacy_redirect_uris),
            "NORTHLAKE_OIDC_LEGACY_POST_LOGOUT_REDIRECT_URIS": ";".join(
                self.legacy_post_logout_redirect_uris
            ),
            "NORTHLAKE_OIDC_LEGACY_SCOPES": " ".join(self.legacy_scopes),
        }

    def preview(self, provider: ProviderSettings) -> dict[str, Any]:
        issuer = f"{provider.public_base_url}/realms/{provider.realm_key}"
        endpoints = {
            "authorizationEndpoint": f"{issuer}/protocol/openid-connect/auth",
            "tokenEndpoint": f"{issuer}/protocol/openid-connect/token",
            "issuer": issuer,
            "jsonWebKeySetEndpoint": f"{issuer}/protocol/openid-connect/certs",
            "userInfoEndpoint": f"{issuer}/protocol/openid-connect/userinfo",
            "introspectionEndpoint": f"{issuer}/protocol/openid-connect/token/introspect",
        }
        discovery = f"{issuer}/.well-known/openid-configuration"
        metadata_address = {
            "Authority": issuer,
            "Discovery": discovery,
            "Static": None,
        }[self.configuration_mode]

        def provider_values(
            *,
            provider_key: str,
            display_name: str,
            client_id: str,
            profile: str,
            scopes: tuple[str, ...],
            par_behavior: str,
            redirect_uris: tuple[str, ...],
            post_logout_redirect_uris: tuple[str, ...],
            historical_only: bool,
        ) -> dict[str, Any]:
            extended = endpoints if self.configuration_mode == "Static" else {
                key: None for key in endpoints
            }
            return {
                "providerKey": provider_key,
                "displayName": display_name,
                "metadataAddress": metadata_address,
                "clientIdentifier": client_id,
                "protocolProfile": profile,
                "parBehavior": par_behavior,
                "tokenEndpointAuthMethod": self.token_endpoint_auth_method,
                "configurationMode": self.configuration_mode,
                "responseType": "id_token token" if profile == "Legacy" else None,
                **extended,
                "certificatePath": None,
                "scopes": list(scopes),
                "registeredRedirectUris": list(redirect_uris),
                "registeredPostLogoutRedirectUris": list(post_logout_redirect_uris),
                "clientSecretSource": (
                    "identity/.env:EEMSUITE_OIDC_LEGACY_CLIENT_SECRET"
                    if profile == "Legacy"
                    else "identity/.env:EEMSUITE_OIDC_CLIENT_SECRET"
                ),
                "historicalExistingProviderOnly": historical_only,
            }

        profiles = {
            "modern": provider_values(
                provider_key=f"{provider.realm_key}-oidc-modern",
                display_name=f"{provider.provider_display_name} - Modern OIDC",
                client_id=self.modern_client_id,
                profile="Modern",
                scopes=self.modern_scopes,
                par_behavior=self.par_behavior,
                redirect_uris=self.modern_redirect_uris,
                post_logout_redirect_uris=self.modern_post_logout_redirect_uris,
                historical_only=False,
            )
        }
        if self.legacy_enabled:
            profiles["historicalLegacy"] = provider_values(
                provider_key=f"{provider.realm_key}-oidc-legacy",
                display_name=f"{provider.provider_display_name} - Historical Legacy OIDC",
                client_id=self.legacy_client_id,
                profile="Legacy",
                scopes=self.legacy_scopes,
                par_behavior="Disable",
                redirect_uris=self.legacy_redirect_uris,
                post_logout_redirect_uris=self.legacy_post_logout_redirect_uris,
                historical_only=True,
            )
        return {
            "configurationMode": self.configuration_mode,
            "issuer": issuer,
            "discoveryEndpoint": discovery,
            "parBehavior": self.par_behavior,
            "tokenEndpointAuthMethod": self.token_endpoint_auth_method,
            "accessTokenLifetimeSeconds": self.access_token_lifetime_seconds,
            "profiles": profiles,
            "claimMappings": {
                "profile": ["name", "preferred_username", "given_name", "family_name"],
                "email": ["email", "email_verified"],
                "northlake": [
                    "groups",
                    "synthetic_user_id",
                    "primary_company_id",
                    "title",
                    "synthetic_status",
                    "eem_company_ids",
                    "eem_permission_profiles",
                ],
            },
            "notes": [
                "Values are generated for supported System Administration fields only.",
                "Client secrets remain in ignored local state and are never returned to the browser.",
                "Historical Legacy is retained compatibility evidence, not a new-provider recommendation.",
            ],
        }


@dataclass(frozen=True)
class OidcSettingsDocument:
    settings: OidcSettings
    updated_at_utc: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": OIDC_SETTINGS_SCHEMA_VERSION,
            "values": self.settings.to_values(),
            "updatedAtUtc": self.updated_at_utc or datetime.now(UTC).isoformat(),
        }


def load_oidc_settings_document(
    path: Path,
    default_environment: Mapping[str, str],
) -> OidcSettingsDocument:
    if not path.is_file():
        return OidcSettingsDocument(settings=OidcSettings.from_environment(default_environment))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OidcValidationError({"_form": f"Unable to read saved OIDC settings: {error}."}) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != OIDC_SETTINGS_SCHEMA_VERSION:
        raise OidcValidationError({"_form": "Unsupported OIDC settings document."})
    if set(payload) != {"schemaVersion", "values", "updatedAtUtc"}:
        raise OidcValidationError({"_form": "OIDC settings document contains unknown fields."})
    values = payload.get("values")
    if not isinstance(values, dict):
        raise OidcValidationError({"_form": "OIDC settings document contains no values object."})
    updated_at = payload.get("updatedAtUtc")
    if updated_at is not None and not isinstance(updated_at, str):
        raise OidcValidationError({"_form": "OIDC settings timestamp is invalid."})
    return OidcSettingsDocument(
        settings=OidcSettings.from_values(values),
        updated_at_utc=updated_at,
    )


def write_oidc_settings_document(path: Path, document: OidcSettingsDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document.to_json(), indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read a Northlake OIDC settings document.")
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--print-environment-overlay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.print_environment_overlay:
        print("[ERROR] Select --print-environment-overlay.")
        return 1
    try:
        document = load_oidc_settings_document(args.settings_file.resolve(), {})
    except OidcValidationError as error:
        print(json.dumps({"errors": error.errors}), file=os.sys.stderr)
        return 1
    print(json.dumps(document.settings.to_environment_overlay(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
