"""Unauthenticated loopback control surface for the disposable Northlake realm."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from identity.configuration.settings import (
    FIELD_KEYS,
    ProviderSettings,
    SettingsDocument,
    SettingsValidationError,
    load_settings_document,
    write_settings_document,
)
from identity.realm.generate_realm import generate_from_environment


MAX_REQUEST_BYTES = 64 * 1024


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
    ):
        self.environment = dict(environment)
        self.runtime_directory = runtime_directory
        self.manifest_path = manifest_path
        self.field_catalog_path = field_catalog_path
        self.settings_path = runtime_directory / "configuration.json"
        self.realm_output_path = runtime_directory / "import" / "northlake-realm.json"
        self.connection_output_path = runtime_directory / "connection.json"
        self.keycloak_client = keycloak_client
        self.startup_settings = ProviderSettings.from_environment(self.environment)
        self.last_apply_error: str | None = None
        self._apply_lock = threading.Lock()
        self.field_catalog = self._load_field_catalog()

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

    def _generate(self, settings: ProviderSettings) -> dict[str, Any]:
        effective_environment = dict(self.environment)
        effective_environment.update(settings.to_environment_overlay())
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
            )
            self.realm_output_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_realm, self.realm_output_path)
            os.replace(temporary_connection, self.connection_output_path)
        return realm

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
            elif path == "/configure/styles.css":
                self._static("styles.css", "text/css; charset=utf-8")
            elif path == "/configure/api/state":
                self._json(HTTPStatus.OK, self.application.state())
            elif path == "/configure/health":
                self._json(HTTPStatus.OK, {"status": "ok"})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Not found."})
        except (OSError, SettingsValidationError, RuntimeError) as failure:
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
