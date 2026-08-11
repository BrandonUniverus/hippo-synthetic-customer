"""Ignored synthetic-user overlays for the Northlake identity lab."""

from __future__ import annotations

import json
import os
import re
import secrets
import string
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


USER_OVERLAY_SCHEMA_VERSION = 1
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,63}$")
ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "northlake.example.edu",
        "energyhippo.example.com",
    }
)
USER_VALUE_KEYS = frozenset(
    {
        "username",
        "firstName",
        "lastName",
        "email",
        "enabled",
        "title",
    }
)
OVERLAY_RECORD_KEYS = USER_VALUE_KEYS | frozenset(
    {
        "syntheticUserId",
        "source",
        "password",
    }
)
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_.!@#"


class UserValidationError(ValueError):
    """Raised when a synthetic-user request or overlay is invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("Synthetic user is invalid.")


@dataclass(frozen=True)
class SyntheticUserValues:
    username: str
    first_name: str
    last_name: str
    email: str
    enabled: bool
    title: str

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> SyntheticUserValues:
        errors: dict[str, str] = {}
        unknown_keys = sorted(set(values) - USER_VALUE_KEYS)
        if unknown_keys:
            errors["_form"] = f"Unknown user fields: {', '.join(unknown_keys)}."

        username_value = values.get("username")
        username = username_value.strip().lower() if isinstance(username_value, str) else ""
        if not USERNAME_PATTERN.fullmatch(username):
            errors["username"] = (
                "Use 3-64 lowercase letters, numbers, dots, underscores, or hyphens, "
                "starting with a letter."
            )

        first_name = _text_value(values.get("firstName"), "firstName", errors, 1, 60)
        last_name = _text_value(values.get("lastName"), "lastName", errors, 1, 60)
        title = _text_value(values.get("title"), "title", errors, 0, 100)

        email_value = values.get("email")
        email = email_value.strip().lower() if isinstance(email_value, str) else ""
        email_parts = email.rsplit("@", maxsplit=1)
        if (
            len(email_parts) != 2
            or not email_parts[0]
            or email_parts[1] not in ALLOWED_EMAIL_DOMAINS
            or any(character.isspace() for character in email)
        ):
            errors["email"] = (
                "Use a fictional northlake.example.edu or energyhippo.example.com address."
            )

        enabled = values.get("enabled")
        if not isinstance(enabled, bool):
            errors["enabled"] = "Choose whether the synthetic user is enabled."
            enabled = False

        if errors:
            raise UserValidationError(errors)
        return cls(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            enabled=enabled,
            title=title,
        )

    def to_values(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "email": self.email,
            "enabled": self.enabled,
            "title": self.title,
        }


def _text_value(
    value: Any,
    field: str,
    errors: dict[str, str],
    minimum_length: int,
    maximum_length: int,
) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if (
        not minimum_length <= len(normalized) <= maximum_length
        or any(ord(character) < 32 for character in normalized)
    ):
        if minimum_length == 0:
            errors[field] = f"Enter no more than {maximum_length} printable characters."
        else:
            errors[field] = (
                f"Enter between {minimum_length} and {maximum_length} printable characters."
            )
    return normalized


def _new_password() -> str:
    while True:
        password = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(28))
        if (
            any(character.islower() for character in password)
            and any(character.isupper() for character in password)
            and any(character.isdigit() for character in password)
            and any(character in "-_.!@#" for character in password)
        ):
            return password


def _base_user_values(user: Mapping[str, Any]) -> SyntheticUserValues:
    display_name = str(user.get("displayName", "")).strip()
    name_parts = display_name.split(maxsplit=1)
    return SyntheticUserValues.from_values(
        {
            "username": user.get("username"),
            "firstName": name_parts[0] if name_parts else "",
            "lastName": name_parts[1] if len(name_parts) > 1 else "",
            "email": user.get("email"),
            "enabled": user.get("status") == "active",
            "title": user.get("title", ""),
        }
    )


def _read_overlay(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UserValidationError({"_form": f"Unable to read synthetic-user overlay: {error}."}) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != USER_OVERLAY_SCHEMA_VERSION:
        raise UserValidationError({"_form": "Unsupported synthetic-user overlay document."})
    records = payload.get("users")
    if not isinstance(records, list):
        raise UserValidationError({"_form": "Synthetic-user overlay contains no users list."})
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise UserValidationError({"_form": "Synthetic-user overlay contains a malformed record."})
        unknown_keys = sorted(set(record) - OVERLAY_RECORD_KEYS)
        synthetic_user_id = record.get("syntheticUserId")
        source = record.get("source")
        password = record.get("password")
        if unknown_keys:
            raise UserValidationError(
                {"_form": f"Synthetic-user overlay contains unknown fields: {', '.join(unknown_keys)}."}
            )
        if not isinstance(synthetic_user_id, str) or not synthetic_user_id:
            raise UserValidationError({"_form": "Synthetic-user overlay contains an invalid id."})
        if synthetic_user_id in result:
            raise UserValidationError({"_form": f"Duplicate synthetic user id: {synthetic_user_id}."})
        if source not in {"base", "local"}:
            raise UserValidationError({"_form": f"Synthetic user {synthetic_user_id} has an invalid source."})
        if password is not None and (not isinstance(password, str) or len(password) < 20):
            raise UserValidationError({"_form": f"Synthetic user {synthetic_user_id} has an invalid password."})
        values = SyntheticUserValues.from_values(
            {key: record.get(key) for key in USER_VALUE_KEYS}
        )
        result[synthetic_user_id] = {
            "syntheticUserId": synthetic_user_id,
            "source": source,
            **values.to_values(),
            **({"password": password} if password is not None else {}),
        }
    return result


def _write_overlay(path: Path, records: Mapping[str, Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": USER_OVERLAY_SCHEMA_VERSION,
        "users": [records[key] for key in sorted(records)],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _load_base_users(manifest_path: Path) -> list[dict[str, Any]]:
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise UserValidationError({"_form": f"Unable to read the synthetic manifest: {error}."}) from error
    users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(users, list) or any(not isinstance(user, dict) for user in users):
        raise UserValidationError({"_form": "The synthetic manifest contains no valid users list."})
    return users


def merge_user_overlay(
    base_users: list[dict[str, Any]],
    overlay_path: Path | None,
    default_password: str,
) -> list[dict[str, Any]]:
    records = _read_overlay(overlay_path) if overlay_path is not None else {}
    base_by_id = {str(user.get("id")): user for user in base_users}
    effective_users: list[dict[str, Any]] = []

    for user in base_users:
        synthetic_user_id = str(user["id"])
        record = records.get(synthetic_user_id)
        if record is not None and record["source"] != "base":
            raise UserValidationError(
                {"_form": f"Synthetic user {synthetic_user_id} must retain its base source."}
            )
        values = (
            SyntheticUserValues.from_values(
                {key: record.get(key) for key in USER_VALUE_KEYS}
            )
            if record
            else _base_user_values(user)
        )
        effective_users.append(
            {
                **user,
                "username": values.username,
                "displayName": f"{values.first_name} {values.last_name}".strip(),
                "email": values.email,
                "title": values.title,
                "status": "active" if values.enabled else "disabled",
                "_password": record.get("password", default_password) if record else default_password,
                "_source": "base",
                "_hasCustomPassword": bool(record and record.get("password")),
            }
        )

    for synthetic_user_id, record in records.items():
        if synthetic_user_id in base_by_id:
            continue
        if record["source"] != "local" or not synthetic_user_id.startswith("local-"):
            raise UserValidationError(
                {"_form": f"Synthetic user {synthetic_user_id} is not a valid local addition."}
            )
        values = SyntheticUserValues.from_values(
            {key: record.get(key) for key in USER_VALUE_KEYS}
        )
        password = record.get("password")
        if not isinstance(password, str):
            raise UserValidationError(
                {"_form": f"Local synthetic user {synthetic_user_id} has no generated password."}
            )
        effective_users.append(
            {
                "id": synthetic_user_id,
                "username": values.username,
                "displayName": f"{values.first_name} {values.last_name}".strip(),
                "email": values.email,
                "title": values.title,
                "primaryCompanyId": "",
                "status": "active" if values.enabled else "disabled",
                "_password": password,
                "_source": "local",
                "_hasCustomPassword": True,
            }
        )

    usernames: set[str] = set()
    emails: set[str] = set()
    for user in effective_users:
        username = user["username"].casefold()
        email = user["email"].casefold()
        if username in usernames:
            raise UserValidationError({"username": f"Duplicate username: {user['username']}."})
        if email in emails:
            raise UserValidationError({"email": f"Duplicate email: {user['email']}."})
        usernames.add(username)
        emails.add(email)
    if not any(user["status"] == "active" for user in effective_users):
        raise UserValidationError({"enabled": "Keep at least one synthetic user enabled."})
    return effective_users


def _public_user(user: Mapping[str, Any]) -> dict[str, Any]:
    display_name = str(user["displayName"])
    name_parts = display_name.split(maxsplit=1)
    return {
        "syntheticUserId": user["id"],
        "source": user.get("_source", "base"),
        "username": user["username"],
        "firstName": name_parts[0] if name_parts else "",
        "lastName": name_parts[1] if len(name_parts) > 1 else "",
        "email": user["email"],
        "enabled": user["status"] == "active",
        "attributes": {
            "title": user.get("title", ""),
            "syntheticStatus": user["status"],
        },
        "credentialSource": "generated" if user.get("_hasCustomPassword") else "shared",
    }


class SyntheticUserStore:
    def __init__(self, manifest_path: Path, overlay_path: Path, default_password: str):
        self.manifest_path = manifest_path
        self.overlay_path = overlay_path
        self.default_password = default_password

    def effective_users(self) -> list[dict[str, Any]]:
        return merge_user_overlay(
            _load_base_users(self.manifest_path),
            self.overlay_path,
            self.default_password,
        )

    def public_users(self) -> list[dict[str, Any]]:
        return sorted(
            (_public_user(user) for user in self.effective_users()),
            key=lambda user: user["username"],
        )

    def create(self, values: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        parsed = SyntheticUserValues.from_values(values)
        records = _read_overlay(self.overlay_path)
        synthetic_user_id = f"local-{uuid.uuid4()}"
        password = _new_password()
        records[synthetic_user_id] = {
            "syntheticUserId": synthetic_user_id,
            "source": "local",
            **parsed.to_values(),
            "password": password,
        }
        self._validate_records(records)
        _write_overlay(self.overlay_path, records)
        return self._public_by_id(synthetic_user_id), password

    def update(self, synthetic_user_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        parsed = SyntheticUserValues.from_values(values)
        current = self._effective_by_id(synthetic_user_id)
        records = _read_overlay(self.overlay_path)
        existing_record = records.get(synthetic_user_id, {})
        record = {
            "syntheticUserId": synthetic_user_id,
            "source": current.get("_source", "base"),
            **parsed.to_values(),
        }
        if existing_record.get("password"):
            record["password"] = existing_record["password"]
        records[synthetic_user_id] = record
        self._validate_records(records)
        _write_overlay(self.overlay_path, records)
        return self._public_by_id(synthetic_user_id)

    def reset_password(self, synthetic_user_id: str) -> tuple[dict[str, Any], str]:
        current = self._effective_by_id(synthetic_user_id)
        records = _read_overlay(self.overlay_path)
        values = _public_user(current)
        password = _new_password()
        records[synthetic_user_id] = {
            "syntheticUserId": synthetic_user_id,
            "source": current.get("_source", "base"),
            "username": values["username"],
            "firstName": values["firstName"],
            "lastName": values["lastName"],
            "email": values["email"],
            "enabled": values["enabled"],
            "title": values["attributes"]["title"],
            "password": password,
        }
        self._validate_records(records)
        _write_overlay(self.overlay_path, records)
        return self._public_by_id(synthetic_user_id), password

    def _validate_records(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        base_users = _load_base_users(self.manifest_path)
        temporary_path = self.overlay_path.with_suffix(f"{self.overlay_path.suffix}.validation")
        try:
            _write_overlay(temporary_path, records)
            merge_user_overlay(base_users, temporary_path, self.default_password)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _effective_by_id(self, synthetic_user_id: str) -> dict[str, Any]:
        for user in self.effective_users():
            if user["id"] == synthetic_user_id:
                return user
        raise UserValidationError({"_form": "The selected synthetic user no longer exists."})

    def _public_by_id(self, synthetic_user_id: str) -> dict[str, Any]:
        return _public_user(self._effective_by_id(synthetic_user_id))
