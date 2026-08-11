from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from identity.configuration.groups import SyntheticGroupStore, GroupValidationError
from identity.configuration.users import SyntheticUserStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class SyntheticGroupStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary_directory.name)
        self.user_overlay_path = temporary_root / "users.json"
        self.group_overlay_path = temporary_root / "groups.json"
        self.manifest_path = (
            REPOSITORY_ROOT / "security" / "northlake-eem-security-v1.yaml"
        )
        self.user_store = SyntheticUserStore(
            self.manifest_path,
            self.user_overlay_path,
            "A1!shared-synthetic-password",
        )
        self.store = SyntheticGroupStore(
            self.manifest_path,
            self.group_overlay_path,
            self.user_store,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lists_checked_in_groups_and_protocol_claim_previews(self) -> None:
        state = self.store.public_state()

        self.assertEqual({"total": 27, "base": 27, "local": 0}, state["counts"])
        self.assertTrue(all(group["source"] == "base" for group in state["groups"]))
        first_group = state["groups"][0]
        self.assertEqual(
            {"oidc": {"groups": [first_group["groupId"]]}, "saml": {"groups": [first_group["groupId"]]}},
            first_group["claimPreview"],
        )
        self.assertNotIn("password", json.dumps(state).lower())

    def test_local_group_membership_rename_and_delete_round_trip(self) -> None:
        member_ids = [user["syntheticUserId"] for user in self.user_store.public_users()[:2]]

        created = self.store.create(
            {"groupId": "phase3_reviewers", "displayName": "Phase 3 Reviewers"}
        )
        with_members = self.store.set_members("phase3_reviewers", member_ids)
        before_rename_claims = self.store.user_claim_preview(member_ids[0])
        renamed = self.store.update(
            "phase3_reviewers",
            {"groupId": "phase3_identity_reviewers", "displayName": "Identity Reviewers"},
        )
        after_rename_claims = self.store.user_claim_preview(member_ids[0])
        self.store.delete("phase3_identity_reviewers")

        self.assertEqual("local", created["source"])
        self.assertEqual([], created["permissionProfiles"])
        self.assertEqual("", created["companyId"])
        self.assertEqual(sorted(member_ids), with_members["memberIds"])
        self.assertIn("phase3_reviewers", before_rename_claims["oidc"]["groups"])
        self.assertIn("phase3_reviewers", before_rename_claims["saml"]["groups"])
        self.assertEqual(sorted(member_ids), renamed["memberIds"])
        self.assertNotIn("phase3_reviewers", after_rename_claims["oidc"]["groups"])
        self.assertIn("phase3_identity_reviewers", after_rename_claims["oidc"]["groups"])
        self.assertEqual(27, self.store.public_state()["counts"]["total"])

    def test_checked_in_group_membership_override_can_be_restored(self) -> None:
        state = self.store.public_state()
        user_ids = [user["syntheticUserId"] for user in state["users"]]
        group = next(
            candidate
            for candidate in state["groups"]
            if any(user_id not in candidate["memberIds"] for user_id in user_ids)
        )
        additional_user = next(user_id for user_id in user_ids if user_id not in group["memberIds"])
        changed_members = sorted([*group["memberIds"], additional_user])

        changed = self.store.set_members(group["groupId"], changed_members)
        restored = self.store.set_members(group["groupId"], group["memberIds"])
        overlay = json.loads(self.group_overlay_path.read_text(encoding="utf-8"))

        self.assertEqual(changed_members, changed["memberIds"])
        self.assertEqual(group["memberIds"], restored["memberIds"])
        self.assertEqual([], overlay["membershipOverrides"])

    def test_rejects_base_mutation_duplicates_and_unknown_members_without_overwrite(self) -> None:
        base_group_id = self.store.public_state()["groups"][0]["groupId"]
        with self.assertRaises(GroupValidationError):
            self.store.update(
                base_group_id,
                {"groupId": "renamed_base", "displayName": "Renamed Base"},
            )
        with self.assertRaises(GroupValidationError):
            self.store.delete(base_group_id)

        self.store.create(
            {"groupId": "phase3_reviewers", "displayName": "Phase 3 Reviewers"}
        )
        before_invalid_membership = self.group_overlay_path.read_bytes()
        with self.assertRaises(GroupValidationError):
            self.store.create(
                {"groupId": "phase3_reviewers", "displayName": "Duplicate Reviewers"}
            )
        with self.assertRaises(GroupValidationError):
            self.store.set_members("phase3_reviewers", ["unknown-synthetic-user"])

        self.assertEqual(before_invalid_membership, self.group_overlay_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
