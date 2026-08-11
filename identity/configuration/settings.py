"""Typed settings for the localhost Northlake provider configuration form."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


SETTINGS_SCHEMA_VERSION = 1
REALM_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
FIELD_KEYS = frozenset(
    {
        "providerDisplayName",
        "realmKey",
        "publicBaseUrl",
        "httpsPort",
        "applicationHomeUrl",
        "oidcRedirectUris",
        "samlAcsUrls",
        "samlLogoutUrls",
        "enableOidc",
        "enableSaml",
        "preset",
    }
)


class SettingsValidationError(ValueError):
    """Raised when one or more public configuration fields are invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("Provider configuration is invalid.")


def _environment_boolean(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise SettingsValidationError({"_form": f"Invalid boolean environment value: {value}."})


def _environment_uri_list(value: str | None, defaults: tuple[str, ...]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return defaults
    return tuple(item.strip() for item in value.split(";") if item.strip())


def _validated_https_url(
    value: Any,
    field: str,
    errors: dict[str, str],
    *,
    origin_only: bool = False,
) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    try:
        parsed = urlparse(normalized)
        parsed_port = parsed.port
    except ValueError:
        parsed = urlparse("")
        parsed_port = None
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
    if origin_only and parsed.path not in {"", "/"}:
        errors[field] = "The provider base URL must contain only an HTTPS origin."
    if parsed_port is not None and not 1 <= parsed_port <= 65535:
        errors[field] = "The URL port must be between 1 and 65535."
    return normalized.rstrip("/") if origin_only else normalized


def _validated_uri_list(
    value: Any,
    field: str,
    errors: dict[str, str],
    *,
    required: bool,
) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = [item.strip() for item in value.replace(";", "\n").splitlines()]
    elif isinstance(value, list):
        candidates = [item.strip() if isinstance(item, str) else "" for item in value]
    else:
        candidates = []
    items = tuple(item for item in candidates if item)
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
        item_errors: dict[str, str] = {}
        _validated_https_url(item, field, item_errors)
        if item_errors:
            errors[field] = f"Invalid URL: {item}"
            break
    return items


@dataclass(frozen=True)
class ProviderSettings:
    provider_display_name: str
    realm_key: str
    public_base_url: str
    https_port: int
    application_home_url: str
    oidc_redirect_uris: tuple[str, ...]
    saml_acs_urls: tuple[str, ...]
    saml_logout_urls: tuple[str, ...]
    enable_oidc: bool
    enable_saml: bool
    preset: str = "Default"

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> ProviderSettings:
        errors: dict[str, str] = {}
        unknown_keys = sorted(set(values) - FIELD_KEYS)
        if unknown_keys:
            errors["_form"] = f"Unknown configuration fields: {', '.join(unknown_keys)}."

        display_name_value = values.get("providerDisplayName")
        display_name = display_name_value.strip() if isinstance(display_name_value, str) else ""
        if not 3 <= len(display_name) <= 80 or any(ord(character) < 32 for character in display_name):
            errors["providerDisplayName"] = "Enter a display name between 3 and 80 characters."

        realm_key_value = values.get("realmKey")
        realm_key = realm_key_value.strip() if isinstance(realm_key_value, str) else ""
        if not REALM_KEY_PATTERN.fullmatch(realm_key) or realm_key == "master":
            errors["realmKey"] = (
                "Use 2-63 lowercase letters, numbers, or hyphens, starting with a letter; "
                "master is reserved."
            )

        port_value = values.get("httpsPort")
        try:
            https_port = int(port_value) if not isinstance(port_value, bool) else 0
        except (TypeError, ValueError):
            https_port = 0
        if not 1 <= https_port <= 65535:
            errors["httpsPort"] = "Enter a port between 1 and 65535."

        public_base_url = _validated_https_url(
            values.get("publicBaseUrl"),
            "publicBaseUrl",
            errors,
            origin_only=True,
        )
        if public_base_url and "publicBaseUrl" not in errors:
            parsed_base_url = urlparse(public_base_url)
            effective_port = parsed_base_url.port or 443
            if effective_port != https_port:
                errors["publicBaseUrl"] = "The URL port must match the HTTPS port field."

        application_home_url = _validated_https_url(
            values.get("applicationHomeUrl"),
            "applicationHomeUrl",
            errors,
        )

        enable_oidc = values.get("enableOidc")
        enable_saml = values.get("enableSaml")
        if not isinstance(enable_oidc, bool):
            errors["enableOidc"] = "Choose whether OIDC clients are enabled."
            enable_oidc = False
        if not isinstance(enable_saml, bool):
            errors["enableSaml"] = "Choose whether the SAML client is enabled."
            enable_saml = False
        if not enable_oidc and not enable_saml:
            errors["_form"] = "Enable at least one identity protocol."

        oidc_redirect_uris = _validated_uri_list(
            values.get("oidcRedirectUris"),
            "oidcRedirectUris",
            errors,
            required=enable_oidc,
        )
        saml_acs_urls = _validated_uri_list(
            values.get("samlAcsUrls"),
            "samlAcsUrls",
            errors,
            required=enable_saml,
        )
        saml_logout_urls = _validated_uri_list(
            values.get("samlLogoutUrls"),
            "samlLogoutUrls",
            errors,
            required=enable_saml,
        )

        preset_value = values.get("preset")
        preset = preset_value.strip() if isinstance(preset_value, str) else ""
        if preset != "Default":
            errors["preset"] = "Phase 1 supports only the Default preset."

        if errors:
            raise SettingsValidationError(errors)
        return cls(
            provider_display_name=display_name,
            realm_key=realm_key,
            public_base_url=public_base_url,
            https_port=https_port,
            application_home_url=application_home_url,
            oidc_redirect_uris=oidc_redirect_uris,
            saml_acs_urls=saml_acs_urls,
            saml_logout_urls=saml_logout_urls,
            enable_oidc=enable_oidc,
            enable_saml=enable_saml,
            preset=preset,
        )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> ProviderSettings:
        standard_acs_defaults = (
            "https://localhost:7310/saml/northlake-saml-standard/acs",
            "https://localdev.energyhippo.com/Hippo/saml/northlake-saml-standard/acs",
            "https://localhost/Hippo/saml/northlake-saml-standard/acs",
        )
        standard_logout_defaults = (
            "https://localhost:7310/saml/northlake-saml-standard/logout",
            "https://localdev.energyhippo.com/Hippo/saml/northlake-saml-standard/logout",
            "https://localhost/Hippo/saml/northlake-saml-standard/logout",
        )
        oidc_defaults = (
            "https://localhost:7310/signin-oidc",
            "https://localdev.energyhippo.com/Hippo/signin-oidc",
            "https://localhost/Hippo/signin-oidc",
        )
        return cls.from_values(
            {
                "providerDisplayName": environment.get(
                    "NORTHLAKE_PROVIDER_DISPLAY_NAME",
                    "Northlake Synthetic Identity",
                ),
                "realmKey": environment.get("NORTHLAKE_REALM_KEY", "northlake"),
                "publicBaseUrl": environment.get(
                    "IDENTITY_PUBLIC_BASE_URL",
                    "https://localhost:8443",
                ),
                "httpsPort": environment.get("IDENTITY_HTTPS_PORT", "8443"),
                "applicationHomeUrl": environment.get(
                    "EEMSUITE_APPLICATION_HOME_URL",
                    "https://localdev.energyhippo.com/Hippo/",
                ),
                "oidcRedirectUris": list(
                    _environment_uri_list(
                        environment.get("EEMSUITE_OIDC_REDIRECT_URIS"),
                        oidc_defaults,
                    )
                ),
                "samlAcsUrls": list(
                    _environment_uri_list(
                        environment.get("EEMSUITE_SAML_STANDARD_ACS_URLS"),
                        standard_acs_defaults,
                    )
                ),
                "samlLogoutUrls": list(
                    _environment_uri_list(
                        environment.get("EEMSUITE_SAML_STANDARD_LOGOUT_URLS"),
                        standard_logout_defaults,
                    )
                ),
                "enableOidc": _environment_boolean(
                    environment.get("NORTHLAKE_ENABLE_OIDC"),
                    True,
                ),
                "enableSaml": _environment_boolean(
                    environment.get("NORTHLAKE_ENABLE_SAML"),
                    True,
                ),
                "preset": "Default",
            }
        )

    def to_values(self) -> dict[str, Any]:
        return {
            "providerDisplayName": self.provider_display_name,
            "realmKey": self.realm_key,
            "publicBaseUrl": self.public_base_url,
            "httpsPort": self.https_port,
            "applicationHomeUrl": self.application_home_url,
            "oidcRedirectUris": list(self.oidc_redirect_uris),
            "samlAcsUrls": list(self.saml_acs_urls),
            "samlLogoutUrls": list(self.saml_logout_urls),
            "enableOidc": self.enable_oidc,
            "enableSaml": self.enable_saml,
            "preset": self.preset,
        }

    def to_environment_overlay(self) -> dict[str, str]:
        provider_host = urlparse(self.public_base_url).hostname
        if provider_host is None:
            raise SettingsValidationError({"publicBaseUrl": "The provider URL has no host."})
        return {
            "NORTHLAKE_PROVIDER_DISPLAY_NAME": self.provider_display_name,
            "NORTHLAKE_REALM_KEY": self.realm_key,
            "NORTHLAKE_ENABLE_OIDC": str(self.enable_oidc).lower(),
            "NORTHLAKE_ENABLE_SAML": str(self.enable_saml).lower(),
            "IDENTITY_HOST": provider_host,
            "IDENTITY_HTTPS_PORT": str(self.https_port),
            "IDENTITY_PUBLIC_BASE_URL": self.public_base_url,
            "EEMSUITE_APPLICATION_HOME_URL": self.application_home_url,
            "EEMSUITE_OIDC_REDIRECT_URIS": ";".join(self.oidc_redirect_uris),
            "EEMSUITE_SAML_PROFILES": "Standard" if self.enable_saml else "",
            "EEMSUITE_SAML_STANDARD_ACS_URLS": ";".join(self.saml_acs_urls),
            "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": ";".join(self.saml_logout_urls),
        }

    def endpoint_preview(self) -> dict[str, Any]:
        issuer = f"{self.public_base_url}/realms/{self.realm_key}"
        return {
            "providerDisplayName": self.provider_display_name,
            "realmKey": self.realm_key,
            "preset": self.preset,
            "issuer": issuer,
            "account": f"{issuer}/account/",
            "adminConsole": f"{self.public_base_url}/admin/{self.realm_key}/console/",
            "oidc": {
                "enabled": self.enable_oidc,
                "discovery": f"{issuer}/.well-known/openid-configuration",
                "redirectUris": list(self.oidc_redirect_uris),
            },
            "saml": {
                "enabled": self.enable_saml,
                "metadata": f"{issuer}/protocol/saml/descriptor",
                "assertionConsumerServiceUrls": list(self.saml_acs_urls),
                "singleLogoutServiceUrls": list(self.saml_logout_urls),
            },
            "applicationHomeUrl": self.application_home_url,
        }

    def edge_signature(self) -> tuple[str, int]:
        return self.public_base_url, self.https_port


@dataclass(frozen=True)
class SettingsDocument:
    settings: ProviderSettings
    applied_realm_key: str | None = None
    pending_apply: bool = False
    updated_at_utc: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": SETTINGS_SCHEMA_VERSION,
            "values": self.settings.to_values(),
            "appliedRealmKey": self.applied_realm_key,
            "pendingApply": self.pending_apply,
            "updatedAtUtc": self.updated_at_utc or datetime.now(UTC).isoformat(),
        }


def load_settings_document(
    path: Path,
    default_environment: Mapping[str, str],
) -> SettingsDocument:
    if not path.is_file():
        settings = ProviderSettings.from_environment(default_environment)
        return SettingsDocument(settings=settings, applied_realm_key=settings.realm_key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SettingsValidationError({"_form": f"Unable to read saved settings: {error}."}) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != SETTINGS_SCHEMA_VERSION:
        raise SettingsValidationError({"_form": "Unsupported provider settings document."})
    values = payload.get("values")
    if not isinstance(values, dict):
        raise SettingsValidationError({"_form": "Saved provider settings contain no values object."})
    applied_realm_key = payload.get("appliedRealmKey")
    if applied_realm_key is not None and not isinstance(applied_realm_key, str):
        raise SettingsValidationError({"_form": "Saved applied realm key is invalid."})
    return SettingsDocument(
        settings=ProviderSettings.from_values(values),
        applied_realm_key=applied_realm_key,
        pending_apply=payload.get("pendingApply") is True,
        updated_at_utc=payload.get("updatedAtUtc") if isinstance(payload.get("updatedAtUtc"), str) else None,
    )


def write_settings_document(path: Path, document: SettingsDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document.to_json(), indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read a Northlake provider settings document.")
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--print-environment-overlay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.print_environment_overlay:
        print("[ERROR] Select --print-environment-overlay.")
        return 1
    try:
        document = load_settings_document(args.settings_file.resolve(), {})
    except SettingsValidationError as error:
        print(json.dumps({"errors": error.errors}), file=os.sys.stderr)
        return 1
    print(json.dumps(document.settings.to_environment_overlay(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
