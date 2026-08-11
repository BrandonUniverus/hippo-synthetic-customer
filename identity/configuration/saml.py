"""Typed Phase 5 SAML profiles for the Northlake identity lab."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


SAML_SETTINGS_SCHEMA_VERSION = 1
SUBJECT_BINDING_KINDS = frozenset({"PersistentNameId", "Attribute"})
KNOWN_SAML_CLAIMS = frozenset(
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
        "urn:oasis:names:tc:SAML:attribute:subject-id",
    }
)
DEFAULT_ALLOWED_CLAIMS = tuple(
    claim
    for claim in (
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
    )
)
DEFAULT_AUTHENTICATION_CONTEXTS = (
    "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified",
)
PROFILE_PREFIXES = {
    "standard": "standard",
    "saml2int": "saml2Int",
}
SAML_FIELD_KEYS = frozenset(
    {
        f"{prefix}{suffix}"
        for prefix in PROFILE_PREFIXES.values()
        for suffix in (
            "Enabled",
            "ProviderKey",
            "EntityId",
            "AssertionConsumerServiceUrls",
            "LogoutServiceUrls",
            "SubjectBindingKind",
            "SubjectAttribute",
            "AllowedClaims",
            "AllowedAuthenticationContextClassReferences",
            "AllowUnsolicitedResponses",
            "EnableSingleLogout",
        )
    }
)
CERTIFICATE_INPUT_KEYS = frozenset(
    {"saml2IntCertificateBase64", "saml2IntCertificateName"}
)
_PROVIDER_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class SamlValidationError(ValueError):
    """Raised when the bounded Northlake SAML profile document is invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("SAML profile configuration is invalid.")


def _environment_boolean(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise SamlValidationError(
        {"_form": f"Invalid SAML boolean environment value: {value}."}
    )


def _environment_list(value: str | None, defaults: tuple[str, ...]) -> list[str]:
    if value is None or not value.strip():
        return list(defaults)
    return [item.strip() for item in value.split(";") if item.strip()]


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


def _https_url_list(
    value: Any,
    field: str,
    errors: dict[str, str],
    *,
    required: bool,
    expected_suffix: str,
) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = value.replace(";", "\n").splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []
    items = tuple(
        item.strip() for item in candidates if isinstance(item, str) and item.strip()
    )
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
            or not parsed.path.endswith(expected_suffix)
        ):
            errors[field] = (
                f"Use an exact HTTPS URL ending in {expected_suffix}."
            )
            break
    return items


def _claim_list(value: Any, field: str, errors: dict[str, str]) -> tuple[str, ...]:
    if isinstance(value, str):
        items = tuple(
            item.strip()
            for item in value.replace(";", "\n").splitlines()
            if item.strip()
        )
    elif isinstance(value, list):
        items = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    else:
        items = ()
    if len(items) > 64:
        errors[field] = "Enter no more than 64 claims."
    elif len(items) != len(set(items)):
        errors[field] = "Remove duplicate claims."
    else:
        unknown = sorted(set(items) - KNOWN_SAML_CLAIMS)
        if unknown:
            errors[field] = f"Unsupported Northlake SAML claim: {unknown[0]}."
    return items


def _authentication_contexts(
    value: Any,
    field: str,
    errors: dict[str, str],
) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = value.replace(";", "\n").splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []
    items = tuple(
        item.strip() for item in candidates if isinstance(item, str) and item.strip()
    )
    if len(items) > 16:
        errors[field] = "Enter no more than 16 authentication-context URIs."
    elif len(items) != len(set(items)):
        errors[field] = "Remove duplicate authentication-context URIs."
    elif any(
        not urlparse(item).scheme
        or len(item) > 1024
        or any(ord(character) < 32 for character in item)
        for item in items
    ):
        errors[field] = "Each authentication context must be an absolute URI."
    return items


@dataclass(frozen=True)
class SamlProfileSettings:
    enabled: bool
    provider_key: str
    entity_id: str
    assertion_consumer_service_urls: tuple[str, ...]
    logout_service_urls: tuple[str, ...]
    subject_binding_kind: str
    subject_attribute: str | None
    allowed_claims: tuple[str, ...]
    allowed_authentication_context_class_references: tuple[str, ...]
    allow_unsolicited_responses: bool
    enable_single_logout: bool

    @classmethod
    def from_values(
        cls,
        values: Mapping[str, Any],
        prefix: str,
        errors: dict[str, str],
    ) -> SamlProfileSettings:
        enabled_field = f"{prefix}Enabled"
        enabled = values.get(enabled_field)
        if not isinstance(enabled, bool):
            errors[enabled_field] = "Choose whether this SAML profile is enabled."
            enabled = False

        provider_key_field = f"{prefix}ProviderKey"
        provider_key = _provider_key(values.get(provider_key_field), provider_key_field, errors)
        entity_id_field = f"{prefix}EntityId"
        entity_id = _entity_id(values.get(entity_id_field), entity_id_field, errors)
        expected_acs_suffix = f"/saml/{provider_key}/acs"
        expected_logout_suffix = f"/saml/{provider_key}/logout"
        acs_field = f"{prefix}AssertionConsumerServiceUrls"
        acs_urls = _https_url_list(
            values.get(acs_field),
            acs_field,
            errors,
            required=enabled,
            expected_suffix=expected_acs_suffix,
        )

        slo_field = f"{prefix}EnableSingleLogout"
        enable_single_logout = values.get(slo_field)
        if not isinstance(enable_single_logout, bool):
            errors[slo_field] = "Choose whether EEM single logout is enabled."
            enable_single_logout = True
        logout_field = f"{prefix}LogoutServiceUrls"
        logout_urls = _https_url_list(
            values.get(logout_field),
            logout_field,
            errors,
            required=enabled and enable_single_logout,
            expected_suffix=expected_logout_suffix,
        )

        binding_field = f"{prefix}SubjectBindingKind"
        subject_binding_kind = values.get(binding_field)
        if subject_binding_kind not in SUBJECT_BINDING_KINDS:
            errors[binding_field] = "Choose PersistentNameId or Attribute."
            subject_binding_kind = "PersistentNameId"
        subject_field = f"{prefix}SubjectAttribute"
        subject_value = values.get(subject_field)
        subject_attribute = (
            subject_value.strip() if isinstance(subject_value, str) and subject_value.strip() else None
        )
        claims_field = f"{prefix}AllowedClaims"
        allowed_claims = _claim_list(values.get(claims_field), claims_field, errors)
        if subject_binding_kind == "Attribute":
            if subject_attribute not in KNOWN_SAML_CLAIMS:
                errors[subject_field] = "Choose one supported Northlake SAML claim."
            elif subject_attribute not in allowed_claims:
                errors[subject_field] = "The subject attribute must also be allowlisted."
        elif subject_attribute is not None:
            errors[subject_field] = "Persistent NameID does not use a subject attribute."

        contexts_field = f"{prefix}AllowedAuthenticationContextClassReferences"
        contexts = _authentication_contexts(values.get(contexts_field), contexts_field, errors)
        unsolicited_field = f"{prefix}AllowUnsolicitedResponses"
        allow_unsolicited = values.get(unsolicited_field)
        if not isinstance(allow_unsolicited, bool):
            errors[unsolicited_field] = "Choose the IdP-initiated response policy."
            allow_unsolicited = False

        return cls(
            enabled=enabled,
            provider_key=provider_key,
            entity_id=entity_id,
            assertion_consumer_service_urls=acs_urls,
            logout_service_urls=logout_urls,
            subject_binding_kind=subject_binding_kind,
            subject_attribute=subject_attribute,
            allowed_claims=allowed_claims,
            allowed_authentication_context_class_references=contexts,
            allow_unsolicited_responses=allow_unsolicited,
            enable_single_logout=enable_single_logout,
        )

    def to_values(self, prefix: str) -> dict[str, Any]:
        return {
            f"{prefix}Enabled": self.enabled,
            f"{prefix}ProviderKey": self.provider_key,
            f"{prefix}EntityId": self.entity_id,
            f"{prefix}AssertionConsumerServiceUrls": list(
                self.assertion_consumer_service_urls
            ),
            f"{prefix}LogoutServiceUrls": list(self.logout_service_urls),
            f"{prefix}SubjectBindingKind": self.subject_binding_kind,
            f"{prefix}SubjectAttribute": self.subject_attribute or "",
            f"{prefix}AllowedClaims": list(self.allowed_claims),
            f"{prefix}AllowedAuthenticationContextClassReferences": list(
                self.allowed_authentication_context_class_references
            ),
            f"{prefix}AllowUnsolicitedResponses": self.allow_unsolicited_responses,
            f"{prefix}EnableSingleLogout": self.enable_single_logout,
        }


@dataclass(frozen=True)
class SamlSettings:
    standard: SamlProfileSettings
    saml2int: SamlProfileSettings

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> SamlSettings:
        errors: dict[str, str] = {}
        unknown_keys = sorted(set(values) - SAML_FIELD_KEYS)
        if unknown_keys:
            errors["_form"] = f"Unknown SAML fields: {', '.join(unknown_keys)}."
        standard = SamlProfileSettings.from_values(values, "standard", errors)
        saml2int = SamlProfileSettings.from_values(values, "saml2Int", errors)
        if not standard.enabled and not saml2int.enabled:
            errors["_form"] = "Enable Standard, Saml2Int, or disable SAML on the Provider page."
        if standard.enabled and saml2int.enabled:
            if standard.provider_key == saml2int.provider_key:
                errors["saml2IntProviderKey"] = "The two profiles need distinct provider keys."
            if standard.entity_id == saml2int.entity_id:
                errors["saml2IntEntityId"] = "The two profiles need distinct SP entity IDs."
        if errors:
            raise SamlValidationError(errors)
        return cls(standard=standard, saml2int=saml2int)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> SamlSettings:
        configured = {
            value.strip()
            for value in environment.get("EEMSUITE_SAML_PROFILES", "Standard").split(";")
            if value.strip()
        }
        if not configured:
            configured = {"Standard"}

        def profile_values(
            *,
            prefix: str,
            environment_prefix: str,
            enabled: bool,
            default_provider_key: str,
            default_entity_id: str,
            default_acs_urls: tuple[str, ...],
            default_logout_urls: tuple[str, ...],
        ) -> dict[str, Any]:
            subject_binding = environment.get(
                f"NORTHLAKE_SAML_{environment_prefix}_SUBJECT_BINDING_KIND",
                "PersistentNameId",
            )
            return {
                f"{prefix}Enabled": enabled,
                f"{prefix}ProviderKey": environment.get(
                    f"NORTHLAKE_SAML_{environment_prefix}_PROVIDER_KEY",
                    default_provider_key,
                ),
                f"{prefix}EntityId": environment.get(
                    f"EEMSUITE_SAML_{environment_prefix}_ENTITY_ID",
                    default_entity_id,
                ),
                f"{prefix}AssertionConsumerServiceUrls": _environment_list(
                    environment.get(f"EEMSUITE_SAML_{environment_prefix}_ACS_URLS"),
                    default_acs_urls,
                ),
                f"{prefix}LogoutServiceUrls": _environment_list(
                    environment.get(f"EEMSUITE_SAML_{environment_prefix}_LOGOUT_URLS"),
                    default_logout_urls,
                ),
                f"{prefix}SubjectBindingKind": subject_binding,
                f"{prefix}SubjectAttribute": environment.get(
                    f"NORTHLAKE_SAML_{environment_prefix}_SUBJECT_ATTRIBUTE",
                    "",
                ),
                f"{prefix}AllowedClaims": _environment_list(
                    environment.get(f"NORTHLAKE_SAML_{environment_prefix}_ALLOWED_CLAIMS"),
                    DEFAULT_ALLOWED_CLAIMS,
                ),
                f"{prefix}AllowedAuthenticationContextClassReferences": _environment_list(
                    environment.get(
                        f"NORTHLAKE_SAML_{environment_prefix}_ALLOWED_AUTHENTICATION_CONTEXTS"
                    ),
                    DEFAULT_AUTHENTICATION_CONTEXTS,
                ),
                f"{prefix}AllowUnsolicitedResponses": _environment_boolean(
                    environment.get(
                        f"NORTHLAKE_SAML_{environment_prefix}_ALLOW_UNSOLICITED_RESPONSES"
                    ),
                    False,
                ),
                f"{prefix}EnableSingleLogout": _environment_boolean(
                    environment.get(
                        f"NORTHLAKE_SAML_{environment_prefix}_ENABLE_SINGLE_LOGOUT"
                    ),
                    True,
                ),
            }

        standard_values = profile_values(
            prefix="standard",
            environment_prefix="STANDARD",
            enabled="Standard" in configured,
            default_provider_key="northlake-saml-standard",
            default_entity_id="urn:energyhippo:eemsuite-web:saml:standard",
            default_acs_urls=(
                "https://localhost:7310/saml/northlake-saml-standard/acs",
            ),
            default_logout_urls=(
                "https://localhost:7310/saml/northlake-saml-standard/logout",
            ),
        )
        saml2int_values = profile_values(
            prefix="saml2Int",
            environment_prefix="SAML2INT",
            enabled="Saml2Int" in configured,
            default_provider_key="northlake-saml2int",
            default_entity_id="urn:energyhippo:eemsuite-web:saml:saml2int",
            default_acs_urls=(
                "https://localhost/Hippo/saml/northlake-saml2int/acs",
            ),
            default_logout_urls=(
                "https://localhost/Hippo/saml/northlake-saml2int/logout",
            ),
        )
        return cls.from_values({**standard_values, **saml2int_values})

    def to_values(self) -> dict[str, Any]:
        return {
            **self.standard.to_values("standard"),
            **self.saml2int.to_values("saml2Int"),
        }

    def to_environment_overlay(self, certificate_path: Path) -> dict[str, str]:
        profiles = []
        if self.standard.enabled:
            profiles.append("Standard")
        if self.saml2int.enabled:
            profiles.append("Saml2Int")

        def profile_overlay(profile: SamlProfileSettings, prefix: str) -> dict[str, str]:
            return {
                f"NORTHLAKE_SAML_{prefix}_PROVIDER_KEY": profile.provider_key,
                f"NORTHLAKE_SAML_{prefix}_SUBJECT_BINDING_KIND": profile.subject_binding_kind,
                f"NORTHLAKE_SAML_{prefix}_SUBJECT_ATTRIBUTE": profile.subject_attribute or "",
                f"NORTHLAKE_SAML_{prefix}_ALLOWED_CLAIMS": ";".join(profile.allowed_claims),
                f"NORTHLAKE_SAML_{prefix}_ALLOWED_AUTHENTICATION_CONTEXTS": ";".join(
                    profile.allowed_authentication_context_class_references
                ),
                f"NORTHLAKE_SAML_{prefix}_ALLOW_UNSOLICITED_RESPONSES": str(
                    profile.allow_unsolicited_responses
                ).lower(),
                f"NORTHLAKE_SAML_{prefix}_ENABLE_SINGLE_LOGOUT": str(
                    profile.enable_single_logout
                ).lower(),
            }

        return {
            "EEMSUITE_SAML_PROFILES": ";".join(profiles),
            "EEMSUITE_SAML_STANDARD_ENTITY_ID": self.standard.entity_id,
            "EEMSUITE_SAML_STANDARD_ACS_URLS": ";".join(
                self.standard.assertion_consumer_service_urls
            ),
            "EEMSUITE_SAML_STANDARD_LOGOUT_URLS": ";".join(
                self.standard.logout_service_urls
            ),
            "EEMSUITE_SAML2INT_ENTITY_ID": self.saml2int.entity_id,
            "EEMSUITE_SAML2INT_ACS_URLS": ";".join(
                self.saml2int.assertion_consumer_service_urls
            ),
            "EEMSUITE_SAML2INT_LOGOUT_URLS": ";".join(
                self.saml2int.logout_service_urls
            ),
            "EEMSUITE_SAML2INT_SP_CERTIFICATE_FILE": (
                str(certificate_path.resolve()) if self.saml2int.enabled else ""
            ),
            **profile_overlay(self.standard, "STANDARD"),
            **profile_overlay(self.saml2int, "SAML2INT"),
        }

    def preview(
        self,
        *,
        public_base_url: str,
        realm_key: str,
        provider_display_name: str,
        certificate: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        issuer = f"{public_base_url.rstrip('/')}/realms/{realm_key}"
        metadata = f"{issuer}/protocol/saml/descriptor"
        sso = f"{issuer}/protocol/saml"

        def profile_preview(
            profile: SamlProfileSettings,
            validation_profile: str,
        ) -> dict[str, Any]:
            callback_suffix = f"/saml/{profile.provider_key}/acs"
            metadata_uris = [
                uri[: -len(callback_suffix)]
                + f"/saml/{profile.provider_key}/metadata"
                for uri in profile.assertion_consumer_service_urls
            ]
            return {
                "ProviderKey": profile.provider_key,
                "DisplayName": f"{provider_display_name} - {validation_profile}",
                "IdentityProviderMetadata": metadata,
                "IdentityProviderEntityId": issuer,
                "ServiceProviderEntityId": profile.entity_id,
                "ValidationProfile": validation_profile,
                "SubjectBindingKind": profile.subject_binding_kind,
                "SubjectAttribute": profile.subject_attribute,
                "AllowedClaims": list(profile.allowed_claims),
                "AllowedAuthenticationContextClassReferences": list(
                    profile.allowed_authentication_context_class_references
                ),
                "AllowUnsolicitedResponses": profile.allow_unsolicited_responses,
                "EnableSingleLogout": profile.enable_single_logout,
                "CallbackPath": f"/saml/{profile.provider_key}/acs",
                "CallbackUris": list(profile.assertion_consumer_service_urls),
                "MetadataPath": f"/saml/{profile.provider_key}/metadata",
                "MetadataUris": metadata_uris,
                "LogoutPath": f"/saml/{profile.provider_key}/logout",
                "LogoutUris": list(profile.logout_service_urls),
                "ServiceProviderCredential": {
                    "requiredForSigning": (
                        profile.enable_single_logout or validation_profile == "Saml2Int"
                    ),
                    "requiredForEncryption": validation_profile == "Saml2Int",
                    "privateKeyCustody": "EnergyHippo only",
                    "northlakePublicCertificate": (
                        dict(certificate)
                        if validation_profile == "Saml2Int" and certificate is not None
                        else None
                    ),
                },
            }

        profiles: dict[str, Any] = {}
        if self.standard.enabled:
            profiles["standard"] = profile_preview(self.standard, "Standard")
        if self.saml2int.enabled:
            profiles["saml2Int"] = profile_preview(self.saml2int, "Saml2Int")
        return {
            "identityProvider": {
                "entityId": issuer,
                "metadataAddress": metadata,
                "singleSignOnEndpoint": sso,
                "singleLogoutEndpoint": sso,
                "responseBinding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "profiles": profiles,
            "notes": [
                "Northlake stores only the public Saml2Int certificate; the private key remains in EnergyHippo.",
                "Apply runs provider-side protocol checks. Installed EnergyHippo login and decryption remain separate evidence.",
                "Callbacks are exact provider-specific non-root routes.",
            ],
        }


@dataclass(frozen=True)
class SamlSettingsDocument:
    settings: SamlSettings
    updated_at_utc: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": SAML_SETTINGS_SCHEMA_VERSION,
            "values": self.settings.to_values(),
            "updatedAtUtc": self.updated_at_utc or datetime.now(UTC).isoformat(),
        }


def load_saml_settings_document(
    path: Path,
    default_environment: Mapping[str, str],
) -> SamlSettingsDocument:
    if not path.is_file():
        return SamlSettingsDocument(settings=SamlSettings.from_environment(default_environment))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SamlValidationError(
            {"_form": f"Unable to read saved SAML settings: {error}."}
        ) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != SAML_SETTINGS_SCHEMA_VERSION:
        raise SamlValidationError({"_form": "Unsupported SAML settings document."})
    if set(payload) != {"schemaVersion", "values", "updatedAtUtc"}:
        raise SamlValidationError({"_form": "SAML settings document contains unknown fields."})
    values = payload.get("values")
    if not isinstance(values, dict):
        raise SamlValidationError({"_form": "SAML settings document contains no values object."})
    updated_at = payload.get("updatedAtUtc")
    if updated_at is not None and not isinstance(updated_at, str):
        raise SamlValidationError({"_form": "SAML settings timestamp is invalid."})
    return SamlSettingsDocument(
        settings=SamlSettings.from_values(values),
        updated_at_utc=updated_at,
    )


def write_saml_settings_document(path: Path, document: SamlSettingsDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document.to_json(), indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def parse_public_certificate_base64(value: Any) -> tuple[bytes, dict[str, Any]]:
    if not isinstance(value, str) or not value.strip():
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "Choose an EEM public RSA certificate."}
        )
    try:
        document = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "The certificate upload was not valid base64."}
        ) from error
    return validate_public_certificate(document)


def validate_public_certificate(document: bytes) -> tuple[bytes, dict[str, Any]]:
    if not document or len(document) > 65_536:
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "The certificate must be 1-65,536 bytes."}
        )
    if b"PRIVATE KEY" in document.upper():
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "Upload only the public certificate, never a private key."}
        )
    try:
        certificate = (
            x509.load_pem_x509_certificate(document)
            if b"-----BEGIN CERTIFICATE-----" in document
            else x509.load_der_x509_certificate(document)
        )
    except ValueError as error:
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "The upload did not contain one X.509 certificate."}
        ) from error
    public_key = certificate.public_key()
    if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size < 2048:
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "Use an RSA certificate with a key of at least 2048 bits."}
        )
    now_utc = datetime.now(UTC)
    if certificate.not_valid_before_utc > now_utc or certificate.not_valid_after_utc <= now_utc:
        raise SamlValidationError(
            {"saml2IntCertificateBase64": "The public certificate is not currently valid."}
        )
    der = certificate.public_bytes(serialization.Encoding.DER)
    summary = {
        "configured": True,
        "sha256Thumbprint": hashlib.sha256(der).hexdigest().upper(),
        "subject": certificate.subject.rfc4514_string(),
        "notBeforeUtc": certificate.not_valid_before_utc.isoformat(),
        "notAfterUtc": certificate.not_valid_after_utc.isoformat(),
        "keyType": "RSA",
        "keySize": public_key.key_size,
    }
    return der, summary


def read_public_certificate(path: Path) -> tuple[bytes, dict[str, Any]] | None:
    if not path.is_file():
        return None
    return validate_public_certificate(path.read_bytes())


def write_public_certificate(path: Path, der: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_bytes(der)
    os.replace(temporary_path, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read a Northlake SAML settings document.")
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--certificate-file", type=Path)
    parser.add_argument("--print-environment-overlay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.print_environment_overlay:
        print("[ERROR] Select --print-environment-overlay.")
        return 1
    settings_path = args.settings_file.resolve()
    certificate_path = (
        args.certificate_file.resolve()
        if args.certificate_file is not None
        else settings_path.parent / "certs" / "saml2int-sp-public.cer"
    )
    try:
        document = load_saml_settings_document(settings_path, {})
        if document.settings.saml2int.enabled:
            read_result = read_public_certificate(certificate_path)
            if read_result is None:
                raise SamlValidationError(
                    {"saml2IntCertificateBase64": "The saved Saml2Int public certificate is missing."}
                )
    except SamlValidationError as error:
        print(json.dumps({"errors": error.errors}), file=os.sys.stderr)
        return 1
    print(
        json.dumps(
            document.settings.to_environment_overlay(certificate_path),
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
