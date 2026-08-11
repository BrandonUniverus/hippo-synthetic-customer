"""Ignored synthetic-group and membership overlays for the Northlake identity lab."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from identity.configuration.users import SyntheticUserStore


GROUP_OVERLAY_SCHEMA_VERSION = 1
GROUP_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
GROUP_VALUE_KEYS = frozenset({"groupId", "displayName"})


class GroupValidationError(ValueError):
    """Raised when a synthetic group or membership overlay is invalid."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("Synthetic group is invalid.")


@dataclass(frozen=True)
class SyntheticGroupValues:
    group_id: str
    display_name: str

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> SyntheticGroupValues:
        errors: dict[str, str] = {}
        unknown_keys = sorted(set(values) - GROUP_VALUE_KEYS)
        if unknown_keys:
            errors["_form"] = f"Unknown group fields: {', '.join(unknown_keys)}."
        group_id_value = values.get("groupId")
        group_id = group_id_value.strip().lower() if isinstance(group_id_value, str) else ""
        if not GROUP_ID_PATTERN.fullmatch(group_id):
            errors["groupId"] = (
                "Use 3-64 lowercase letters, numbers, underscores, or hyphens, "
                "starting with a letter."
            )
        display_name_value = values.get("displayName")
        display_name = display_name_value.strip() if isinstance(display_name_value, str) else ""
        if (
            not 3 <= len(display_name) <= 80
            or any(ord(character) < 32 for character in display_name)
        ):
            errors["displayName"] = "Enter a display name between 3 and 80 characters."
        if errors:
            raise GroupValidationError(errors)
        return cls(group_id=group_id, display_name=display_name)

    def to_values(self) -> dict[str, str]:
        return {"groupId": self.group_id, "displayName": self.display_name}


def _load_base_groups(manifest_path: Path) -> list[dict[str, Any]]:
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise GroupValidationError({"_form": f"Unable to read the synthetic manifest: {error}."}) from error
    if not isinstance(payload, dict):
        raise GroupValidationError({"_form": "The synthetic manifest is not an object."})
    groups: list[dict[str, Any]] = []
    system_company = payload.get("systemCompany", {})
    if isinstance(system_company, dict):
        for source_group in system_company.get("groups", []):
            groups.append(
                {
                    **source_group,
                    "companyId": system_company.get("id", "system"),
                    "companyDisplayName": system_company.get("displayName", "System"),
                }
            )
    for company in payload.get("companies", []):
        if not isinstance(company, dict):
            continue
        for source_group in company.get("groups", []):
            groups.append(
                {
                    **source_group,
                    "companyId": company.get("id", ""),
                    "companyDisplayName": company.get("displayName", ""),
                }
            )
    if any(not isinstance(group, dict) for group in groups):
        raise GroupValidationError({"_form": "The synthetic manifest contains a malformed group."})
    return groups


def _read_overlay(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    if not path.is_file():
        return {}, {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GroupValidationError({"_form": f"Unable to read synthetic-group overlay: {error}."}) from error
    if not isinstance(payload, dict) or payload.get("schemaVersion") != GROUP_OVERLAY_SCHEMA_VERSION:
        raise GroupValidationError({"_form": "Unsupported synthetic-group overlay document."})
    if set(payload) != {"schemaVersion", "localGroups", "membershipOverrides"}:
        raise GroupValidationError({"_form": "Synthetic-group overlay contains unknown fields."})
    local_groups_payload = payload.get("localGroups")
    overrides_payload = payload.get("membershipOverrides")
    if not isinstance(local_groups_payload, list) or not isinstance(overrides_payload, list):
        raise GroupValidationError({"_form": "Synthetic-group overlay lists are malformed."})

    local_groups: dict[str, dict[str, Any]] = {}
    for record in local_groups_payload:
        if not isinstance(record, dict) or set(record) != {"groupId", "displayName", "users"}:
            raise GroupValidationError({"_form": "A local synthetic-group record is malformed."})
        values = SyntheticGroupValues.from_values(
            {"groupId": record.get("groupId"), "displayName": record.get("displayName")}
        )
        users = _validated_user_ids(record.get("users"), "users")
        if values.group_id in local_groups:
            raise GroupValidationError({"groupId": f"Duplicate group id: {values.group_id}."})
        local_groups[values.group_id] = {**values.to_values(), "users": users}

    membership_overrides: dict[str, list[str]] = {}
    for record in overrides_payload:
        if not isinstance(record, dict) or set(record) != {"groupId", "users"}:
            raise GroupValidationError({"_form": "A membership override record is malformed."})
        group_id = record.get("groupId")
        if not isinstance(group_id, str) or not GROUP_ID_PATTERN.fullmatch(group_id):
            raise GroupValidationError({"_form": "A membership override has an invalid group id."})
        if group_id in membership_overrides:
            raise GroupValidationError({"_form": f"Duplicate membership override: {group_id}."})
        membership_overrides[group_id] = _validated_user_ids(record.get("users"), "members")
    return local_groups, membership_overrides


def _validated_user_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(user_id, str) or not user_id for user_id in value):
        raise GroupValidationError({field: "Memberships must contain synthetic user ids."})
    if len(value) != len(set(value)):
        raise GroupValidationError({field: "Remove duplicate synthetic user memberships."})
    return sorted(value)


def _write_overlay(
    path: Path,
    local_groups: Mapping[str, Mapping[str, Any]],
    membership_overrides: Mapping[str, list[str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": GROUP_OVERLAY_SCHEMA_VERSION,
        "localGroups": [local_groups[key] for key in sorted(local_groups)],
        "membershipOverrides": [
            {"groupId": key, "users": membership_overrides[key]}
            for key in sorted(membership_overrides)
        ],
    }
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + os.linesep,
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def merge_group_overlay(
    base_groups: list[dict[str, Any]],
    overlay_path: Path | None,
    known_user_ids: set[str],
) -> list[dict[str, Any]]:
    local_groups, membership_overrides = (
        _read_overlay(overlay_path) if overlay_path is not None else ({}, {})
    )
    base_ids = {str(group.get("id")) for group in base_groups}
    if len(base_ids) != len(base_groups) or any(not group_id for group_id in base_ids):
        raise GroupValidationError({"_form": "Base synthetic groups do not have unique ids."})
    collisions = sorted(base_ids & set(local_groups))
    if collisions:
        raise GroupValidationError({"groupId": f"Local group collides with base group: {collisions[0]}."})
    unknown_overrides = sorted(set(membership_overrides) - base_ids)
    if unknown_overrides:
        raise GroupValidationError({"_form": f"Membership override references unknown group: {unknown_overrides[0]}."})

    effective_groups: list[dict[str, Any]] = []
    for group in base_groups:
        group_id = str(group["id"])
        users = membership_overrides.get(group_id, sorted(group.get("users", [])))
        effective_groups.append({**group, "users": users, "_source": "base"})
    for group_id, record in local_groups.items():
        effective_groups.append(
            {
                "id": group_id,
                "displayName": record["displayName"],
                "users": record["users"],
                "companyId": "",
                "companyDisplayName": "Unassigned synthetic provider group",
                "permissionProfiles": [],
                "_source": "local",
            }
        )
    for group in effective_groups:
        unknown_users = sorted(set(group.get("users", [])) - known_user_ids)
        if unknown_users:
            raise GroupValidationError(
                {"members": f"Group {group['id']} references unknown user {unknown_users[0]}."}
            )
    return effective_groups


def _public_group(group: Mapping[str, Any]) -> dict[str, Any]:
    group_id = str(group["id"])
    return {
        "groupId": group_id,
        "displayName": group.get("displayName", group_id),
        "source": group.get("_source", "base"),
        "companyId": group.get("companyId", ""),
        "companyDisplayName": group.get("companyDisplayName", ""),
        "memberIds": sorted(group.get("users", [])),
        "permissionProfiles": sorted(group.get("permissionProfiles", [])),
        "claimPreview": {
            "oidc": {"groups": [group_id]},
            "saml": {"groups": [group_id]},
        },
    }


class SyntheticGroupStore:
    def __init__(
        self,
        manifest_path: Path,
        overlay_path: Path,
        user_store: SyntheticUserStore,
    ):
        self.manifest_path = manifest_path
        self.overlay_path = overlay_path
        self.user_store = user_store

    def effective_groups(self) -> list[dict[str, Any]]:
        known_user_ids = {user["id"] for user in self.user_store.effective_users()}
        return merge_group_overlay(
            _load_base_groups(self.manifest_path),
            self.overlay_path,
            known_user_ids,
        )

    def public_state(self) -> dict[str, Any]:
        groups = sorted(
            (_public_group(group) for group in self.effective_groups()),
            key=lambda group: group["groupId"],
        )
        users = [
            {
                "syntheticUserId": user["syntheticUserId"],
                "username": user["username"],
                "displayName": f"{user['firstName']} {user['lastName']}",
                "enabled": user["enabled"],
            }
            for user in self.user_store.public_users()
        ]
        return {
            "groups": groups,
            "users": users,
            "counts": {
                "total": len(groups),
                "base": sum(group["source"] == "base" for group in groups),
                "local": sum(group["source"] == "local" for group in groups),
            },
        }

    def create(self, values: Mapping[str, Any]) -> dict[str, Any]:
        parsed = SyntheticGroupValues.from_values(values)
        local_groups, overrides = _read_overlay(self.overlay_path)
        existing_group_ids = {group["id"] for group in self.effective_groups()}
        if parsed.group_id in existing_group_ids:
            raise GroupValidationError({"groupId": "Choose a unique synthetic group id."})
        local_groups[parsed.group_id] = {**parsed.to_values(), "users": []}
        self._validate_and_write(local_groups, overrides)
        return self._public_by_id(parsed.group_id)

    def update(self, current_group_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        parsed = SyntheticGroupValues.from_values(values)
        local_groups, overrides = _read_overlay(self.overlay_path)
        current = local_groups.get(current_group_id)
        if current is None:
            raise GroupValidationError({"_form": "Checked-in base groups cannot be renamed."})
        existing_group_ids = {group["id"] for group in self.effective_groups()}
        if parsed.group_id != current_group_id and parsed.group_id in existing_group_ids:
            raise GroupValidationError({"groupId": "Choose a unique synthetic group id."})
        if parsed.group_id != current_group_id:
            local_groups.pop(current_group_id)
        local_groups[parsed.group_id] = {
            **parsed.to_values(),
            "users": current["users"],
        }
        self._validate_and_write(local_groups, overrides)
        return self._public_by_id(parsed.group_id)

    def delete(self, group_id: str) -> None:
        local_groups, overrides = _read_overlay(self.overlay_path)
        if group_id not in local_groups:
            raise GroupValidationError({"_form": "Checked-in base groups cannot be removed."})
        local_groups.pop(group_id)
        self._validate_and_write(local_groups, overrides)

    def set_members(self, group_id: str, user_ids: Any) -> dict[str, Any]:
        members = _validated_user_ids(user_ids, "members")
        local_groups, overrides = _read_overlay(self.overlay_path)
        base_groups = {str(group["id"]): group for group in _load_base_groups(self.manifest_path)}
        if group_id in local_groups:
            local_groups[group_id] = {**local_groups[group_id], "users": members}
        elif group_id in base_groups:
            base_members = sorted(base_groups[group_id].get("users", []))
            if members == base_members:
                overrides.pop(group_id, None)
            else:
                overrides[group_id] = members
        else:
            raise GroupValidationError({"_form": "The selected synthetic group no longer exists."})
        self._validate_and_write(local_groups, overrides)
        return self._public_by_id(group_id)

    def user_claim_preview(self, synthetic_user_id: str) -> dict[str, Any]:
        if synthetic_user_id not in {user["id"] for user in self.user_store.effective_users()}:
            raise GroupValidationError({"_form": "The selected synthetic user no longer exists."})
        memberships = sorted(
            group["id"]
            for group in self.effective_groups()
            if synthetic_user_id in group.get("users", [])
        )
        return {
            "syntheticUserId": synthetic_user_id,
            "oidc": {"groups": memberships},
            "saml": {"groups": memberships},
        }

    def _validate_and_write(
        self,
        local_groups: Mapping[str, Mapping[str, Any]],
        overrides: Mapping[str, list[str]],
    ) -> None:
        temporary_path = self.overlay_path.with_suffix(f"{self.overlay_path.suffix}.validation")
        try:
            _write_overlay(temporary_path, local_groups, overrides)
            known_user_ids = {user["id"] for user in self.user_store.effective_users()}
            merge_group_overlay(
                _load_base_groups(self.manifest_path),
                temporary_path,
                known_user_ids,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        _write_overlay(self.overlay_path, local_groups, overrides)

    def _public_by_id(self, group_id: str) -> dict[str, Any]:
        for group in self.effective_groups():
            if group["id"] == group_id:
                return _public_group(group)
        raise GroupValidationError({"_form": "The selected synthetic group no longer exists."})
