"""Unauthenticated loopback control surface for the disposable Northlake realm."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib import error, parse, request

from identity.configuration.groups import GroupValidationError, SyntheticGroupStore
from identity.configuration.oidc import (
    OidcSettings,
    OidcSettingsDocument,
    OidcValidationError,
    load_oidc_settings_document,
    write_oidc_settings_document,
)
from identity.configuration.saml import (
    CERTIFICATE_INPUT_KEYS,
    SamlSettings,
    SamlSettingsDocument,
    SamlValidationError,
    load_saml_settings_document,
    parse_public_certificate_base64,
    read_public_certificate,
    write_public_certificate,
    write_saml_settings_document,
)
from identity.configuration.scenarios import (
    SCENARIO_PRESETS,
    SCENARIO_SLOTS,
    ScenarioSettings,
    ScenarioSettingsDocument,
    ScenarioValidationError,
    generate_scenario_realm,
    load_scenario_document,
    preset_settings,
    scenario_connection_path,
    scenario_diff,
    scenario_realm_path,
    write_scenario_document,
)
from identity.configuration.settings import (
    FIELD_KEYS,
    ProviderSettings,
    SettingsDocument,
    SettingsValidationError,
    load_settings_document,
    write_settings_document,
)
from identity.configuration.users import SyntheticUserStore, UserValidationError
from identity.realm.generate_realm import generate_from_environment


MAX_REQUEST_BYTES = 128 * 1024


class KeycloakApplyError(RuntimeError):
    """Raised when the disposable realm cannot be replaced through Keycloak."""


class KeycloakAdminClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    def _token(self) -> str:
        body = parse.urlencode(
            {
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
        ).encode("utf-8")
        token_request = request.Request(
            f"{self.base_url}/realms/master/protocol/openid-connect/token",
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with request.urlopen(token_request, timeout=10) as response:
                payload = json.load(response)
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as failure:
            raise KeycloakApplyError("Keycloak administrator authentication failed.") from failure
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise KeycloakApplyError("Keycloak returned no administrator access token.")
        return token

    def _admin_request(
        self,
        token: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected_statuses: tuple[int, ...] = (HTTPStatus.NO_CONTENT,),
    ) -> int:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        admin_request = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(admin_request, timeout=20) as response:
                status = response.status
        except error.HTTPError as failure:
            status = failure.code
        except (error.URLError, TimeoutError) as failure:
            raise KeycloakApplyError("Keycloak administration is unavailable.") from failure
        if status not in expected_statuses:
            raise KeycloakApplyError(
                f"Keycloak administration returned HTTP {status} for {method} {path}."
            )
        return status

    def replace_realm(
        self,
        realm: dict[str, Any],
        previous_realm_key: str | None,
    ) -> None:
        realm_key = realm.get("realm")
        if not isinstance(realm_key, str) or not realm_key or realm_key == "master":
            raise KeycloakApplyError("Generated realm key is unsafe.")
        token = self._token()
        for candidate in dict.fromkeys([previous_realm_key, realm_key]):
            if not candidate:
                continue
            escaped_candidate = parse.quote(candidate, safe="")
            self._admin_request(
                token,
                "DELETE",
                f"/admin/realms/{escaped_candidate}",
                expected_statuses=(HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND),
            )
        self._admin_request(
            token,
            "POST",
            "/admin/realms",
            payload=realm,
            expected_statuses=(HTTPStatus.CREATED,),
        )

    def wait_until_healthy(
        self,
        settings: ProviderSettings,
        timeout_seconds: int = 45,
    ) -> None:
        internal_discovery = (
            f"{self.base_url}/realms/{parse.quote(settings.realm_key, safe='')}"
            "/.well-known/openid-configuration"
        )
        expected_issuer = settings.endpoint_preview()["issuer"]
        deadline = time.monotonic() + timeout_seconds
        last_error = "no response"
        while time.monotonic() < deadline:
            try:
                with request.urlopen(internal_discovery, timeout=5) as response:
                    payload = json.load(response)
                if payload.get("issuer") == expected_issuer:
                    return
                last_error = f"unexpected issuer {payload.get('issuer')!r}"
            except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as failure:
                last_error = str(failure)
            time.sleep(1)
        raise KeycloakApplyError(
            f"The generated realm did not become healthy: {last_error}."
        )


class ConfigurationApplication:
    def __init__(
        self,
        *,
        environment: dict[str, str],
        runtime_directory: Path,
        manifest_path: Path,
        field_catalog_path: Path,
        keycloak_client: KeycloakAdminClient,
        oidc_verifier: Callable[[Path, Path], dict[str, Any]] | None = None,
        saml_verifier: Callable[[Path, Path], dict[str, Any]] | None = None,
        scenario_verifier: Callable[[list[Path], Path], dict[str, Any]] | None = None,
    ):
        self.environment = dict(environment)
        self.runtime_directory = runtime_directory
        self.manifest_path = manifest_path
        self.field_catalog_path = field_catalog_path
        self.settings_path = runtime_directory / "configuration.json"
        self.user_overlay_path = runtime_directory / "users.json"
        self.group_overlay_path = runtime_directory / "groups.json"
        self.oidc_settings_path = runtime_directory / "oidc.json"
        self.oidc_verification_path = runtime_directory / "oidc-verification.json"
        self.saml_settings_path = runtime_directory / "saml.json"
        self.saml_verification_path = runtime_directory / "saml-verification.json"
        self.saml2int_certificate_path = (
            runtime_directory / "certs" / "saml2int-sp-public.cer"
        )
        self.scenario_settings_path = runtime_directory / "scenarios.json"
        self.scenario_verification_path = runtime_directory / "scenario-verification.json"
        self.scenario_connection_directory = runtime_directory / "scenarios"
        self.root_certificate_path = runtime_directory / "certs" / "caddy-local-root.crt"
        self.realm_output_path = runtime_directory / "import" / "northlake-realm.json"
        self.connection_output_path = runtime_directory / "connection.json"
        self.keycloak_client = keycloak_client
        self.oidc_verifier = oidc_verifier
        self.saml_verifier = saml_verifier
        self.scenario_verifier = scenario_verifier
        self.startup_settings = ProviderSettings.from_environment(self.environment)
        self.last_apply_error: str | None = None
        self._apply_lock = threading.Lock()
        self.field_catalog = self._load_field_catalog()
        self.user_store = SyntheticUserStore(
            manifest_path,
            self.user_overlay_path,
            self.environment["SYNTHETIC_USER_PASSWORD"],
        )
        self.group_store = SyntheticGroupStore(
            manifest_path,
            self.group_overlay_path,
            self.user_store,
        )

    def _load_field_catalog(self) -> dict[str, Any]:
        payload = json.loads(self.field_catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
            raise RuntimeError("The configuration field catalog has an unsupported schema.")
        catalog_keys = {
            field.get("key")
            for group in payload.get("groups", [])
            if isinstance(group, dict)
            for field in group.get("fields", [])
            if isinstance(field, dict)
        }
        if catalog_keys != FIELD_KEYS:
            raise RuntimeError("The configuration field catalog does not match the typed model.")
        return payload

    def _document(self) -> SettingsDocument:
        return load_settings_document(self.settings_path, self.environment)

    def _generate(
        self,
        settings: ProviderSettings,
        oidc_settings: OidcSettings | None = None,
        saml_settings: SamlSettings | None = None,
    ) -> dict[str, Any]:
        effective_environment = dict(self.environment)
        effective_environment.update(settings.to_environment_overlay())
        selected_oidc_settings = oidc_settings or load_oidc_settings_document(
            self.oidc_settings_path,
            effective_environment,
        ).settings
        effective_environment.update(selected_oidc_settings.to_environment_overlay())
        selected_saml_settings = saml_settings or load_saml_settings_document(
            self.saml_settings_path,
            effective_environment,
        ).settings
        effective_environment.update(
            selected_saml_settings.to_environment_overlay(
                self.saml2int_certificate_path
            )
        )
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="northlake-config-",
            dir=self.runtime_directory,
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            temporary_realm = temporary_root / "realm.json"
            temporary_connection = temporary_root / "connection.json"
            realm, _ = generate_from_environment(
                self.manifest_path,
                effective_environment,
                temporary_realm,
                temporary_connection,
                self.user_overlay_path,
                self.group_overlay_path,
            )
            self.realm_output_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_realm, self.realm_output_path)
            os.replace(temporary_connection, self.connection_output_path)
        return realm

    def _oidc_document(self) -> OidcSettingsDocument:
        provider = self._document().settings
        effective_environment = dict(self.environment)
        effective_environment.update(provider.to_environment_overlay())
        return load_oidc_settings_document(self.oidc_settings_path, effective_environment)

    def _last_oidc_verification(self) -> dict[str, Any] | None:
        if not self.oidc_verification_path.is_file():
            return None
        payload = json.loads(self.oidc_verification_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def _clear_oidc_verification(self) -> None:
        self.oidc_verification_path.unlink(missing_ok=True)

    def oidc_state(self) -> dict[str, Any]:
        provider = self._document().settings
        document = self._oidc_document()
        return {
            "values": document.settings.to_values(),
            "preview": document.settings.preview(provider),
            "updatedAtUtc": document.updated_at_utc,
            "lastVerification": self._last_oidc_verification(),
        }

    def preview_oidc(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = OidcSettings.from_values(values)
        return {
            "values": settings.to_values(),
            "preview": settings.preview(self._document().settings),
        }

    def save_oidc(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = OidcSettings.from_values(values)
        write_oidc_settings_document(
            self.oidc_settings_path,
            OidcSettingsDocument(settings=settings),
        )
        self._clear_oidc_verification()
        return {
            "message": "OIDC profiles saved locally. Apply to regenerate the disposable realm.",
            "values": settings.to_values(),
            "preview": settings.preview(self._document().settings),
            "applied": False,
        }

    def _default_oidc_verifier(self, connection_path: Path, ca_path: Path) -> dict[str, Any]:
        verifier_path = Path(
            os.environ.get(
                "NORTHLAKE_OIDC_VERIFIER_PATH",
                "/app/identity/scripts/verify_oidc_baseline.py",
            )
        )
        command = [
            sys.executable,
            str(verifier_path),
            "--connection",
            str(connection_path),
            "--ca-file",
            str(ca_path),
        ]
        host_alias = os.environ.get("NORTHLAKE_VERIFIER_HOST_ALIAS", "").strip()
        if host_alias:
            command.extend(["--resolve-host", f"localhost={host_alias}"])
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as failure:
            return {
                "passed": False,
                "exitCode": None,
                "classification": "verifier-error",
                "output": str(failure),
            }
        output = "\n".join(
            part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
        )
        return {
            "passed": completed.returncode == 0,
            "exitCode": completed.returncode,
            "classification": (
                "passed" if completed.returncode == 0 else "provider-contract-break"
            ),
            "output": output[-24_000:],
        }

    def verify_oidc(self) -> dict[str, Any]:
        verifier = self.oidc_verifier or self._default_oidc_verifier
        result = dict(verifier(self.connection_output_path, self.root_certificate_path))
        result["checkedAtUtc"] = datetime.now(UTC).isoformat()
        self.oidc_verification_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.oidc_verification_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + os.linesep,
            encoding="utf-8",
        )
        os.replace(temporary_path, self.oidc_verification_path)
        return result

    def apply_oidc(self, values: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        oidc_settings = OidcSettings.from_values(values)
        with self._apply_lock:
            provider_document = self._document()
            write_oidc_settings_document(
                self.oidc_settings_path,
                OidcSettingsDocument(settings=oidc_settings),
            )
            self._clear_oidc_verification()
            realm = self._generate(provider_document.settings, oidc_settings)
            try:
                self.keycloak_client.replace_realm(
                    realm,
                    provider_document.applied_realm_key,
                )
                self.keycloak_client.wait_until_healthy(provider_document.settings)
            except KeycloakApplyError as failure:
                return HTTPStatus.BAD_GATEWAY, {
                    "message": (
                        "OIDC profiles were saved, but the disposable realm could not be applied."
                    ),
                    "values": oidc_settings.to_values(),
                    "preview": oidc_settings.preview(provider_document.settings),
                    "applied": False,
                    "applyError": str(failure),
                }
            verification = self.verify_oidc()
            return HTTPStatus.OK, {
                "message": (
                    "OIDC profiles applied and verified."
                    if verification.get("passed")
                    else "OIDC profiles applied; the focused verifier found a contract break."
                ),
                "values": oidc_settings.to_values(),
                "preview": oidc_settings.preview(provider_document.settings),
                "applied": True,
                "verification": verification,
            }

    def _saml_document(self) -> SamlSettingsDocument:
        provider = self._document().settings
        effective_environment = dict(self.environment)
        effective_environment.update(provider.to_environment_overlay())
        return load_saml_settings_document(self.saml_settings_path, effective_environment)

    def _saml_certificate(self) -> tuple[bytes, dict[str, Any]] | None:
        return read_public_certificate(self.saml2int_certificate_path)

    def _last_saml_verification(self) -> dict[str, Any] | None:
        if not self.saml_verification_path.is_file():
            return None
        payload = json.loads(self.saml_verification_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def _clear_saml_verification(self) -> None:
        self.saml_verification_path.unlink(missing_ok=True)

    def _parse_saml_update(
        self,
        values: dict[str, Any],
    ) -> tuple[SamlSettings, bytes | None, dict[str, Any] | None]:
        settings_values = {
            key: value for key, value in values.items() if key not in CERTIFICATE_INPUT_KEYS
        }
        settings = SamlSettings.from_values(settings_values)
        certificate_value = values.get("saml2IntCertificateBase64")
        uploaded_certificate: bytes | None = None
        certificate_summary: dict[str, Any] | None = None
        if certificate_value:
            uploaded_certificate, certificate_summary = parse_public_certificate_base64(
                certificate_value
            )
        else:
            existing = self._saml_certificate()
            if existing is not None:
                _, certificate_summary = existing
        if settings.saml2int.enabled and certificate_summary is None:
            raise SamlValidationError(
                {
                    "saml2IntCertificateBase64": (
                        "Enable Saml2Int only after choosing EEM's public RSA certificate."
                    )
                }
            )
        return settings, uploaded_certificate, certificate_summary

    def saml_state(self) -> dict[str, Any]:
        provider = self._document().settings
        document = self._saml_document()
        certificate = self._saml_certificate()
        certificate_summary = certificate[1] if certificate is not None else None
        return {
            "values": document.settings.to_values(),
            "preview": document.settings.preview(
                public_base_url=provider.public_base_url,
                realm_key=provider.realm_key,
                provider_display_name=provider.provider_display_name,
                certificate=certificate_summary,
            ),
            "certificate": certificate_summary or {"configured": False},
            "updatedAtUtc": document.updated_at_utc,
            "lastVerification": self._last_saml_verification(),
        }

    def preview_saml(self, values: dict[str, Any]) -> dict[str, Any]:
        settings, _, certificate = self._parse_saml_update(values)
        provider = self._document().settings
        return {
            "values": settings.to_values(),
            "preview": settings.preview(
                public_base_url=provider.public_base_url,
                realm_key=provider.realm_key,
                provider_display_name=provider.provider_display_name,
                certificate=certificate,
            ),
            "certificate": certificate or {"configured": False},
        }

    def save_saml(self, values: dict[str, Any]) -> dict[str, Any]:
        settings, uploaded_certificate, certificate = self._parse_saml_update(values)
        if uploaded_certificate is not None:
            write_public_certificate(self.saml2int_certificate_path, uploaded_certificate)
        write_saml_settings_document(
            self.saml_settings_path,
            SamlSettingsDocument(settings=settings),
        )
        self._clear_saml_verification()
        provider = self._document().settings
        return {
            "message": "SAML profiles saved locally. Apply to regenerate the disposable realm.",
            "values": settings.to_values(),
            "preview": settings.preview(
                public_base_url=provider.public_base_url,
                realm_key=provider.realm_key,
                provider_display_name=provider.provider_display_name,
                certificate=certificate,
            ),
            "certificate": certificate or {"configured": False},
            "applied": False,
        }

    def _default_saml_verifier(self, connection_path: Path, ca_path: Path) -> dict[str, Any]:
        verifier_path = Path(
            os.environ.get(
                "NORTHLAKE_SAML_VERIFIER_PATH",
                "/app/identity/scripts/verify_saml_baseline.py",
            )
        )
        command = [
            sys.executable,
            str(verifier_path),
            "--connection",
            str(connection_path),
            "--ca-file",
            str(ca_path),
        ]
        host_alias = os.environ.get("NORTHLAKE_VERIFIER_HOST_ALIAS", "").strip()
        if host_alias:
            command.extend(["--resolve-host", f"localhost={host_alias}"])
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as failure:
            return {
                "passed": False,
                "exitCode": None,
                "classification": "verifier-error",
                "output": str(failure),
            }
        output = "\n".join(
            part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
        )
        return {
            "passed": completed.returncode == 0,
            "exitCode": completed.returncode,
            "classification": (
                "provider-ready-eem-proof-required"
                if completed.returncode == 0
                else "provider-contract-break"
            ),
            "output": output[-24_000:],
        }

    def verify_saml(self) -> dict[str, Any]:
        verifier = self.saml_verifier or self._default_saml_verifier
        result = dict(verifier(self.connection_output_path, self.root_certificate_path))
        result["checkedAtUtc"] = datetime.now(UTC).isoformat()
        self.saml_verification_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.saml_verification_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + os.linesep,
            encoding="utf-8",
        )
        os.replace(temporary_path, self.saml_verification_path)
        return result

    def apply_saml(self, values: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        saml_settings, uploaded_certificate, certificate = self._parse_saml_update(values)
        with self._apply_lock:
            provider_document = self._document()
            if uploaded_certificate is not None:
                write_public_certificate(
                    self.saml2int_certificate_path,
                    uploaded_certificate,
                )
            write_saml_settings_document(
                self.saml_settings_path,
                SamlSettingsDocument(settings=saml_settings),
            )
            self._clear_saml_verification()
            realm = self._generate(
                provider_document.settings,
                saml_settings=saml_settings,
            )
            preview = saml_settings.preview(
                public_base_url=provider_document.settings.public_base_url,
                realm_key=provider_document.settings.realm_key,
                provider_display_name=provider_document.settings.provider_display_name,
                certificate=certificate,
            )
            try:
                self.keycloak_client.replace_realm(
                    realm,
                    provider_document.applied_realm_key,
                )
                self.keycloak_client.wait_until_healthy(provider_document.settings)
            except KeycloakApplyError as failure:
                return HTTPStatus.BAD_GATEWAY, {
                    "message": (
                        "SAML profiles were saved, but the disposable realm could not be applied."
                    ),
                    "values": saml_settings.to_values(),
                    "preview": preview,
                    "certificate": certificate or {"configured": False},
                    "applied": False,
                    "applyError": str(failure),
                }
            verification = self.verify_saml()
            return HTTPStatus.OK, {
                "message": (
                    "SAML profiles applied and provider-side verification passed. "
                    "Installed EnergyHippo proof remains separate."
                    if verification.get("passed")
                    else "SAML profiles applied; the focused verifier found a contract break."
                ),
                "values": saml_settings.to_values(),
                "preview": preview,
                "certificate": certificate or {"configured": False},
                "applied": True,
                "verification": verification,
            }

    def _scenario_default_environment(self) -> dict[str, str]:
        environment = dict(self.environment)
        environment.update(self._document().settings.to_environment_overlay())
        return environment

    def _scenario_document(self) -> ScenarioSettingsDocument:
        return load_scenario_document(
            self.scenario_settings_path,
            self._scenario_default_environment(),
        )

    def _last_scenario_verification(self) -> dict[str, Any] | None:
        if not self.scenario_verification_path.is_file():
            return None
        payload = json.loads(
            self.scenario_verification_path.read_text(encoding="utf-8")
        )
        return payload if isinstance(payload, dict) else None

    def _clear_scenario_verification(self) -> None:
        self.scenario_verification_path.unlink(missing_ok=True)

    def _scenario_payload(
        self,
        settings: ScenarioSettings,
        *,
        before: ScenarioSettings | None = None,
    ) -> dict[str, Any]:
        return {
            "values": settings.to_values(),
            "preview": settings.preview(),
            "export": settings.redacted_export(),
            "diff": scenario_diff(before, settings) if before is not None else [],
        }

    def scenario_state(self) -> dict[str, Any]:
        document = self._scenario_document()
        return {
            **self._scenario_payload(document.settings),
            "presets": {
                preset: preset_settings(
                    preset,
                    self._scenario_default_environment(),
                ).to_values()
                for preset in SCENARIO_PRESETS
            },
            "appliedRealmKeys": document.applied_realm_keys,
            "updatedAtUtc": document.updated_at_utc,
            "lastVerification": self._last_scenario_verification(),
        }

    def preview_scenarios(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = ScenarioSettings.from_values(values)
        return self._scenario_payload(
            settings,
            before=self._scenario_document().settings,
        )

    def save_scenarios(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = ScenarioSettings.from_values(values)
        current = self._scenario_document()
        write_scenario_document(
            self.scenario_settings_path,
            ScenarioSettingsDocument(
                settings=settings,
                applied_realm_keys=current.applied_realm_keys,
            ),
        )
        self._clear_scenario_verification()
        return {
            "message": "Two-realm scenario saved locally. Apply to replace the lab realms.",
            **self._scenario_payload(settings, before=current.settings),
            "appliedRealmKeys": current.applied_realm_keys,
            "applied": False,
        }

    def clone_scenario(
        self,
        values: dict[str, Any],
        source_slot: str,
        target_slot: str,
    ) -> dict[str, Any]:
        settings = ScenarioSettings.from_values(values)
        cloned = settings.clone(source_slot, target_slot)
        return {
            "message": (
                f"Cloned {source_slot} behavior into {target_slot}; target provider identities "
                "and SAML callbacks stayed distinct."
            ),
            **self._scenario_payload(cloned, before=settings),
        }

    def _generate_scenario(
        self,
        settings: ScenarioSettings,
        slot: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f"northlake-{slot.lower()}-",
            dir=self.runtime_directory,
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            temporary_realm = temporary_root / "realm.json"
            temporary_connection = temporary_root / "connection.json"
            realm, connection = generate_scenario_realm(
                settings,
                slot,
                self.environment,
                self.manifest_path,
                temporary_realm,
                temporary_connection,
                self.user_overlay_path,
                self.group_overlay_path,
            )
            realm_path = scenario_realm_path(self.realm_output_path.parent, slot)
            connection_path = scenario_connection_path(
                self.scenario_connection_directory,
                slot,
            )
            realm_path.parent.mkdir(parents=True, exist_ok=True)
            connection_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_realm, realm_path)
            os.replace(temporary_connection, connection_path)
        return realm, connection

    def _default_scenario_verifier(
        self,
        connection_paths: list[Path],
        ca_path: Path,
    ) -> dict[str, Any]:
        verifier_path = Path(
            os.environ.get(
                "NORTHLAKE_SCENARIO_VERIFIER_PATH",
                "/app/identity/scripts/verify_scenarios.py",
            )
        )
        command = [sys.executable, str(verifier_path)]
        for connection_path in connection_paths:
            command.extend(["--connection", str(connection_path)])
        command.extend(["--ca-file", str(ca_path)])
        host_alias = os.environ.get("NORTHLAKE_VERIFIER_HOST_ALIAS", "").strip()
        if host_alias:
            command.extend(["--resolve-host", f"localhost={host_alias}"])
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=240,
            )
        except (OSError, subprocess.TimeoutExpired) as failure:
            return {
                "passed": False,
                "exitCode": None,
                "classification": "verifier-error",
                "output": str(failure),
            }
        output = "\n".join(
            part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
        )
        return {
            "passed": completed.returncode == 0,
            "exitCode": completed.returncode,
            "classification": (
                "provider-ready-eem-proof-required"
                if completed.returncode == 0
                else "provider-contract-break"
            ),
            "output": output[-32_000:],
        }

    def verify_scenarios(self) -> dict[str, Any]:
        connection_paths = [
            scenario_connection_path(self.scenario_connection_directory, slot)
            for slot in SCENARIO_SLOTS
        ]
        if any(not path.is_file() for path in connection_paths):
            raise RuntimeError("Apply both lab realms before running scenario verification.")
        verifier = self.scenario_verifier or self._default_scenario_verifier
        result = dict(verifier(connection_paths, self.root_certificate_path))
        result["checkedAtUtc"] = datetime.now(UTC).isoformat()
        self.scenario_verification_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.scenario_verification_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + os.linesep,
            encoding="utf-8",
        )
        os.replace(temporary_path, self.scenario_verification_path)
        return result

    def apply_scenarios(
        self,
        values: dict[str, Any],
        slots: tuple[str, ...] = SCENARIO_SLOTS,
    ) -> tuple[int, dict[str, Any]]:
        if not slots or any(slot not in SCENARIO_SLOTS for slot in slots):
            raise ScenarioValidationError({"_form": "Select labA, labB, or both realms."})
        settings = ScenarioSettings.from_values(values)
        with self._apply_lock:
            current = self._scenario_document()
            applied_keys = dict(current.applied_realm_keys)
            write_scenario_document(
                self.scenario_settings_path,
                ScenarioSettingsDocument(
                    settings=settings,
                    applied_realm_keys=applied_keys,
                ),
            )
            self._clear_scenario_verification()
            for slot in slots:
                realm, _ = self._generate_scenario(settings, slot)
                provider_settings = ProviderSettings.from_environment(
                    settings.environment_for(slot, self.environment)
                )
                try:
                    self.keycloak_client.replace_realm(
                        realm,
                        applied_keys.get(slot),
                    )
                    self.keycloak_client.wait_until_healthy(provider_settings)
                except KeycloakApplyError as failure:
                    return HTTPStatus.BAD_GATEWAY, {
                        "message": (
                            f"Scenario saved, but {slot} could not be applied to Keycloak."
                        ),
                        **self._scenario_payload(settings, before=current.settings),
                        "appliedRealmKeys": applied_keys,
                        "applied": False,
                        "applyError": str(failure),
                    }
                applied_keys[slot] = realm["realm"]
                write_scenario_document(
                    self.scenario_settings_path,
                    ScenarioSettingsDocument(
                        settings=settings,
                        applied_realm_keys=applied_keys,
                    ),
                )
            verification = (
                self.verify_scenarios()
                if all(applied_keys.get(slot) for slot in SCENARIO_SLOTS)
                else None
            )
            return HTTPStatus.OK, {
                "message": (
                    "Both lab realms applied and provider-side isolation verification passed. "
                    "Installed EnergyHippo proof remains separate."
                    if verification and verification.get("passed")
                    else (
                        "Selected lab realm reset; apply both realms for full isolation verification."
                        if verification is None
                        else "Both lab realms applied; the verifier found a scenario contract break."
                    )
                ),
                **self._scenario_payload(settings, before=current.settings),
                "appliedRealmKeys": applied_keys,
                "applied": True,
                "verification": verification,
            }

    def state(self) -> dict[str, Any]:
        document = self._document()
        return {
            "schema": self.field_catalog,
            "values": document.settings.to_values(),
            "preview": document.settings.endpoint_preview(),
            "status": {
                "pendingApply": document.pending_apply,
                "appliedRealmKey": document.applied_realm_key,
                "updatedAtUtc": document.updated_at_utc,
                "lastApplyError": self.last_apply_error,
            },
        }

    def preview(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = ProviderSettings.from_values(values)
        return {
            "values": settings.to_values(),
            "preview": settings.endpoint_preview(),
        }

    def save(self, values: dict[str, Any]) -> dict[str, Any]:
        settings = ProviderSettings.from_values(values)
        current = self._document()
        document = SettingsDocument(
            settings=settings,
            applied_realm_key=current.applied_realm_key,
            pending_apply=False,
        )
        write_settings_document(self.settings_path, document)
        self.last_apply_error = None
        return {
            "message": "Configuration saved locally.",
            "values": settings.to_values(),
            "preview": settings.endpoint_preview(),
            "applied": False,
            "restartRequired": False,
        }

    def apply(self, values: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        settings = ProviderSettings.from_values(values)
        with self._apply_lock:
            current = self._document()
            realm = self._generate(settings)
            pending_document = SettingsDocument(
                settings=settings,
                applied_realm_key=current.applied_realm_key,
                pending_apply=True,
            )
            write_settings_document(self.settings_path, pending_document)
            if settings.edge_signature() != self.startup_settings.edge_signature():
                self.last_apply_error = None
                return HTTPStatus.ACCEPTED, {
                    "message": (
                        "Configuration saved and generated. Restart Northlake to apply the "
                        "new public hostname or port."
                    ),
                    "values": settings.to_values(),
                    "preview": settings.endpoint_preview(),
                    "applied": False,
                    "restartRequired": True,
                }
            try:
                self.keycloak_client.replace_realm(realm, current.applied_realm_key)
                self.keycloak_client.wait_until_healthy(settings)
            except KeycloakApplyError as failure:
                self.last_apply_error = str(failure)
                return HTTPStatus.BAD_GATEWAY, {
                    "message": (
                        "Configuration was saved, but the disposable realm could not be applied. "
                        "Northlake will retry after the next stack start."
                    ),
                    "values": settings.to_values(),
                    "preview": settings.endpoint_preview(),
                    "applied": False,
                    "restartRequired": False,
                    "applyError": self.last_apply_error,
                }
            write_settings_document(
                self.settings_path,
                SettingsDocument(
                    settings=settings,
                    applied_realm_key=settings.realm_key,
                    pending_apply=False,
                ),
            )
            self.last_apply_error = None
            return HTTPStatus.OK, {
                "message": "Configuration applied. The disposable realm was regenerated.",
                "values": settings.to_values(),
                "preview": settings.endpoint_preview(),
                "applied": True,
                "restartRequired": False,
            }

    def reconcile_pending(self) -> None:
        for _ in range(60):
            with self._apply_lock:
                document = self._document()
                if not document.pending_apply:
                    return
                try:
                    realm = self._generate(document.settings)
                    self.keycloak_client.replace_realm(realm, document.applied_realm_key)
                    self.keycloak_client.wait_until_healthy(document.settings)
                except (KeycloakApplyError, OSError, ValueError) as failure:
                    self.last_apply_error = str(failure)
                else:
                    write_settings_document(
                        self.settings_path,
                        SettingsDocument(
                            settings=document.settings,
                            applied_realm_key=document.settings.realm_key,
                            pending_apply=False,
                        ),
                    )
                    self.last_apply_error = None
                    return
            time.sleep(2)

    def users(self) -> dict[str, Any]:
        users = self.user_store.public_users()
        return {
            "users": users,
            "counts": {
                "total": len(users),
                "enabled": sum(user["enabled"] for user in users),
                "local": sum(user["source"] == "local" for user in users),
            },
        }

    def _apply_identity_overlay(
        self,
        result_key: str,
        result: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        document = self._document()
        realm = self._generate(document.settings)
        try:
            self.keycloak_client.replace_realm(realm, document.applied_realm_key)
            self.keycloak_client.wait_until_healthy(document.settings)
        except KeycloakApplyError as failure:
            self.last_apply_error = str(failure)
            return HTTPStatus.BAD_GATEWAY, {
                "message": (
                    "The ignored identity overlay was saved, but the disposable realm could not "
                    "be regenerated. Northlake will include it on the next ordinary start."
                ),
                result_key: result,
                "applied": False,
                "applyError": self.last_apply_error,
            }
        self.last_apply_error = None
        payload: dict[str, Any] = {
            "message": "Identity overlay saved and the disposable realm was regenerated.",
            result_key: result,
            "applied": True,
        }
        return HTTPStatus.OK, payload

    def create_user(self, values: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self._apply_lock:
            user, password = self.user_store.create(values)
            status, payload = self._apply_identity_overlay("user", user)
            payload["generatedPassword"] = password
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Synthetic user saved. Copy the generated development password now."
                )
            return status, payload

    def update_user(
        self,
        synthetic_user_id: str,
        values: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        with self._apply_lock:
            user = self.user_store.update(synthetic_user_id, values)
            status, payload = self._apply_identity_overlay("user", user)
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Synthetic user saved and the disposable realm was regenerated."
                )
            return status, payload

    def reset_user_password(self, synthetic_user_id: str) -> tuple[int, dict[str, Any]]:
        with self._apply_lock:
            user, password = self.user_store.reset_password(synthetic_user_id)
            status, payload = self._apply_identity_overlay("user", user)
            payload["generatedPassword"] = password
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Synthetic user saved. Copy the generated development password now."
                )
            return status, payload

    def groups(self) -> dict[str, Any]:
        return self.group_store.public_state()

    def group_claims(self, synthetic_user_id: str) -> dict[str, Any]:
        return self.group_store.user_claim_preview(synthetic_user_id)

    def create_group(self, values: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        with self._apply_lock:
            group = self.group_store.create(values)
            status, payload = self._apply_identity_overlay("group", group)
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Synthetic group created and the disposable realm was regenerated."
                )
            return status, payload

    def update_group(
        self,
        group_id: str,
        values: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        with self._apply_lock:
            group = self.group_store.update(group_id, values)
            status, payload = self._apply_identity_overlay("group", group)
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Synthetic group renamed and the disposable realm was regenerated."
                )
            return status, payload

    def delete_group(self, group_id: str) -> tuple[int, dict[str, Any]]:
        with self._apply_lock:
            self.group_store.delete(group_id)
            result = {"groupId": group_id, "deleted": True}
            status, payload = self._apply_identity_overlay("group", result)
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Local synthetic group removed and the disposable realm was regenerated."
                )
            return status, payload

    def set_group_members(
        self,
        group_id: str,
        values: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if set(values) != {"members"}:
            raise GroupValidationError({"_form": "Membership updates require only a members list."})
        with self._apply_lock:
            group = self.group_store.set_members(group_id, values["members"])
            status, payload = self._apply_identity_overlay("group", group)
            if status == HTTPStatus.OK:
                payload["message"] = (
                    "Synthetic memberships saved and the disposable realm was regenerated."
                )
            return status, payload


class ConfigurationRequestHandler(BaseHTTPRequestHandler):
    application: ConfigurationApplication
    static_directory: Path

    def _headers(self, status: int, content_type: str, content_length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _static(self, filename: str, content_type: str) -> None:
        body = (self.static_directory / filename).read_bytes()
        self._headers(HTTPStatus.OK, content_type, len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = parse.urlparse(self.path).path
        try:
            if path in {"/configure", "/configure/"}:
                self._static("index.html", "text/html; charset=utf-8")
            elif path == "/configure/app.js":
                self._static("app.js", "text/javascript; charset=utf-8")
            elif path == "/configure/users":
                self._static("users.html", "text/html; charset=utf-8")
            elif path == "/configure/users.js":
                self._static("users.js", "text/javascript; charset=utf-8")
            elif path == "/configure/groups":
                self._static("groups.html", "text/html; charset=utf-8")
            elif path == "/configure/groups.js":
                self._static("groups.js", "text/javascript; charset=utf-8")
            elif path == "/configure/oidc":
                self._static("oidc.html", "text/html; charset=utf-8")
            elif path == "/configure/oidc.js":
                self._static("oidc.js", "text/javascript; charset=utf-8")
            elif path == "/configure/saml":
                self._static("saml.html", "text/html; charset=utf-8")
            elif path == "/configure/saml.js":
                self._static("saml.js", "text/javascript; charset=utf-8")
            elif path == "/configure/scenarios":
                self._static("scenarios.html", "text/html; charset=utf-8")
            elif path == "/configure/scenarios.js":
                self._static("scenarios.js", "text/javascript; charset=utf-8")
            elif path == "/configure/styles.css":
                self._static("styles.css", "text/css; charset=utf-8")
            elif path == "/configure/api/state":
                self._json(HTTPStatus.OK, self.application.state())
            elif path == "/configure/api/users":
                self._json(HTTPStatus.OK, self.application.users())
            elif path == "/configure/api/groups":
                self._json(HTTPStatus.OK, self.application.groups())
            elif path == "/configure/api/oidc":
                self._json(HTTPStatus.OK, self.application.oidc_state())
            elif path == "/configure/api/saml":
                self._json(HTTPStatus.OK, self.application.saml_state())
            elif path == "/configure/api/scenarios":
                self._json(HTTPStatus.OK, self.application.scenario_state())
            elif path == "/configure/api/groups/claims":
                query = parse.parse_qs(parse.urlparse(self.path).query)
                user_ids = query.get("userId", [])
                if len(user_ids) != 1:
                    self._json(HTTPStatus.BAD_REQUEST, {"message": "Select one synthetic user."})
                else:
                    self._json(HTTPStatus.OK, self.application.group_claims(user_ids[0]))
            elif path == "/configure/health":
                self._json(HTTPStatus.OK, {"status": "ok"})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Not found."})
        except (
            OSError,
            SettingsValidationError,
            OidcValidationError,
            SamlValidationError,
            ScenarioValidationError,
            UserValidationError,
            GroupValidationError,
            RuntimeError,
        ) as failure:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"message": "Configuration service state is unavailable.", "detail": str(failure)},
            )

    def _request_values(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            raise SettingsValidationError({"_form": "The request body is empty or too large."})
        try:
            payload = json.loads(self.rfile.read(content_length))
        except json.JSONDecodeError as failure:
            raise SettingsValidationError({"_form": "The request body is not valid JSON."}) from failure
        if not isinstance(payload, dict) or not isinstance(payload.get("values"), dict):
            raise SettingsValidationError({"_form": "The request must contain a values object."})
        return payload["values"]

    def do_POST(self) -> None:
        path = parse.urlparse(self.path).path
        oidc_routes = {
            "/configure/api/oidc/preview",
            "/configure/api/oidc/save",
            "/configure/api/oidc/apply",
            "/configure/api/oidc/verify",
        }
        saml_routes = {
            "/configure/api/saml/preview",
            "/configure/api/saml/save",
            "/configure/api/saml/apply",
            "/configure/api/saml/verify",
        }
        scenario_routes = {
            "/configure/api/scenarios/preview",
            "/configure/api/scenarios/save",
            "/configure/api/scenarios/apply",
            "/configure/api/scenarios/verify",
            "/configure/api/scenarios/clone/labA/labB",
            "/configure/api/scenarios/clone/labB/labA",
            "/configure/api/scenarios/reset/labA",
            "/configure/api/scenarios/reset/labB",
        }
        if path in scenario_routes:
            try:
                values = self._request_values()
                if path == "/configure/api/scenarios/preview":
                    self._json(HTTPStatus.OK, self.application.preview_scenarios(values))
                elif path == "/configure/api/scenarios/save":
                    self._json(HTTPStatus.OK, self.application.save_scenarios(values))
                elif path == "/configure/api/scenarios/apply":
                    status, payload = self.application.apply_scenarios(values)
                    self._json(status, payload)
                elif path == "/configure/api/scenarios/verify":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "message": "Two-realm isolation verification completed.",
                            "verification": self.application.verify_scenarios(),
                        },
                    )
                elif "/clone/" in path:
                    source_slot, target_slot = path.rsplit("/", 2)[-2:]
                    self._json(
                        HTTPStatus.OK,
                        self.application.clone_scenario(
                            values,
                            source_slot,
                            target_slot,
                        ),
                    )
                else:
                    slot = path.rsplit("/", 1)[-1]
                    status, payload = self.application.apply_scenarios(
                        values,
                        (slot,),
                    )
                    self._json(status, payload)
            except ScenarioValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "message": "Check the highlighted two-realm scenario values.",
                        "errors": failure.errors,
                    },
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "message": "The two-realm scenario operation failed.",
                        "detail": str(failure),
                    },
                )
            return
        if path in saml_routes:
            try:
                values = self._request_values()
                if path == "/configure/api/saml/preview":
                    self._json(HTTPStatus.OK, self.application.preview_saml(values))
                elif path == "/configure/api/saml/save":
                    self._json(HTTPStatus.OK, self.application.save_saml(values))
                elif path == "/configure/api/saml/apply":
                    status, payload = self.application.apply_saml(values)
                    self._json(status, payload)
                else:
                    self._json(
                        HTTPStatus.OK,
                        {
                            "message": "Focused SAML verification completed.",
                            "verification": self.application.verify_saml(),
                        },
                    )
            except SamlValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"message": "Check the highlighted SAML values.", "errors": failure.errors},
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"message": "The SAML configuration operation failed.", "detail": str(failure)},
                )
            return
        if path in oidc_routes:
            try:
                values = self._request_values()
                if path == "/configure/api/oidc/preview":
                    self._json(HTTPStatus.OK, self.application.preview_oidc(values))
                elif path == "/configure/api/oidc/save":
                    self._json(HTTPStatus.OK, self.application.save_oidc(values))
                elif path == "/configure/api/oidc/apply":
                    status, payload = self.application.apply_oidc(values)
                    self._json(status, payload)
                else:
                    self._json(
                        HTTPStatus.OK,
                        {
                            "message": "Focused OIDC verification completed.",
                            "verification": self.application.verify_oidc(),
                        },
                    )
            except OidcValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"message": "Check the highlighted OIDC values.", "errors": failure.errors},
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"message": "The OIDC configuration operation failed.", "detail": str(failure)},
                )
            return
        if path == "/configure/api/groups/create":
            try:
                status, payload = self.application.create_group(self._request_values())
                self._json(status, payload)
            except GroupValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"message": "Check the highlighted synthetic-group values.", "errors": failure.errors},
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"message": "The synthetic-group operation failed.", "detail": str(failure)},
                )
            return
        group_route_prefix = "/configure/api/groups/"
        group_suffixes = ("/update", "/delete", "/members")
        matching_group_suffix = next(
            (suffix for suffix in group_suffixes if path.endswith(suffix)),
            None,
        )
        if path.startswith(group_route_prefix) and matching_group_suffix is not None:
            encoded_group_id = path[
                len(group_route_prefix) : -len(matching_group_suffix)
            ]
            group_id = parse.unquote(encoded_group_id)
            if not group_id or "/" in group_id:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Synthetic group not found."})
                return
            try:
                if matching_group_suffix == "/update":
                    status, payload = self.application.update_group(
                        group_id,
                        self._request_values(),
                    )
                elif matching_group_suffix == "/delete":
                    status, payload = self.application.delete_group(group_id)
                else:
                    status, payload = self.application.set_group_members(
                        group_id,
                        self._request_values(),
                    )
                self._json(status, payload)
            except GroupValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"message": "Check the highlighted synthetic-group values.", "errors": failure.errors},
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"message": "The synthetic-group operation failed.", "detail": str(failure)},
                )
            return
        if path == "/configure/api/users/create":
            try:
                status, payload = self.application.create_user(self._request_values())
                self._json(status, payload)
            except UserValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"message": "Check the highlighted synthetic-user values.", "errors": failure.errors},
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"message": "The synthetic-user operation failed.", "detail": str(failure)},
                )
            return
        user_route_prefix = "/configure/api/users/"
        if path.startswith(user_route_prefix) and (
            path.endswith("/update") or path.endswith("/reset-password")
        ):
            suffix = "/update" if path.endswith("/update") else "/reset-password"
            encoded_user_id = path[len(user_route_prefix) : -len(suffix)]
            synthetic_user_id = parse.unquote(encoded_user_id)
            if not synthetic_user_id or "/" in synthetic_user_id:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Synthetic user not found."})
                return
            try:
                if suffix == "/update":
                    status, payload = self.application.update_user(
                        synthetic_user_id,
                        self._request_values(),
                    )
                else:
                    status, payload = self.application.reset_user_password(
                        synthetic_user_id
                    )
                self._json(status, payload)
            except UserValidationError as failure:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"message": "Check the highlighted synthetic-user values.", "errors": failure.errors},
                )
            except (OSError, ValueError, RuntimeError) as failure:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"message": "The synthetic-user operation failed.", "detail": str(failure)},
                )
            return
        if path not in {
            "/configure/api/preview",
            "/configure/api/save",
            "/configure/api/apply",
        }:
            self._json(HTTPStatus.NOT_FOUND, {"message": "Not found."})
            return
        try:
            values = self._request_values()
            if path == "/configure/api/preview":
                self._json(HTTPStatus.OK, self.application.preview(values))
            elif path == "/configure/api/save":
                self._json(HTTPStatus.OK, self.application.save(values))
            else:
                status, payload = self.application.apply(values)
                self._json(status, payload)
        except SettingsValidationError as failure:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"message": "Check the highlighted configuration values.", "errors": failure.errors},
            )
        except (OSError, ValueError, RuntimeError) as failure:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"message": "The configuration operation failed.", "detail": str(failure)},
            )

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"[configuration] {self.address_string()} {format_string % args}")


def create_server(
    application: ConfigurationApplication,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    class BoundConfigurationRequestHandler(ConfigurationRequestHandler):
        pass

    BoundConfigurationRequestHandler.application = application
    BoundConfigurationRequestHandler.static_directory = Path(__file__).resolve().parent
    return ThreadingHTTPServer((host, port), BoundConfigurationRequestHandler)


def main() -> int:
    configuration_directory = Path(__file__).resolve().parent
    runtime_directory = Path(
        os.environ.get("NORTHLAKE_RUNTIME_DIRECTORY", "/runtime")
    ).resolve()
    manifest_path = Path(
        os.environ.get(
            "NORTHLAKE_MANIFEST_PATH",
            "/app/security/northlake-eem-security-v1.yaml",
        )
    ).resolve()
    keycloak_client = KeycloakAdminClient(
        os.environ.get("NORTHLAKE_KEYCLOAK_INTERNAL_URL", "http://keycloak:8080"),
        os.environ.get("KEYCLOAK_ADMIN", "admin"),
        os.environ["KEYCLOAK_ADMIN_PASSWORD"],
    )
    application = ConfigurationApplication(
        environment=dict(os.environ),
        runtime_directory=runtime_directory,
        manifest_path=manifest_path,
        field_catalog_path=configuration_directory / "fields.json",
        keycloak_client=keycloak_client,
    )
    reconciliation_thread = threading.Thread(
        target=application.reconcile_pending,
        name="northlake-pending-apply",
        daemon=True,
    )
    reconciliation_thread.start()
    host = os.environ.get("NORTHLAKE_CONFIGURATION_HOST", "0.0.0.0")
    port = int(os.environ.get("NORTHLAKE_CONFIGURATION_PORT", "8081"))
    server = create_server(application, host, port)
    print(f"[OK] Northlake configuration service listening on {host}:{port}.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
