from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from identity.configuration.users import SyntheticUserStore, UserValidationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class SyntheticUserStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.overlay_path = Path(self.temporary_directory.name) / "users.json"
        self.store = SyntheticUserStore(
            REPOSITORY_ROOT / "security" / "northlake-eem-security-v1.yaml",
            self.overlay_path,
            "A1!shared-synthetic-password",
        )
        self.values = {
            "username": "alex.rivera",
            "firstName": "Alex",
            "lastName": "Rivera",
            "email": "alex.rivera@northlake.example.edu",
            "enabled": True,
            "title": "Synthetic Integration Tester",
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lists_checked_in_users_without_exposing_passwords(self) -> None:
        users = self.store.public_users()

        self.assertEqual(19, len(users))
        self.assertEqual(18, sum(user["enabled"] for user in users))
        self.assertTrue(all(user["source"] == "base" for user in users))
        serialized = json.dumps(users).lower()
        self.assertNotIn("password", serialized)
        self.assertNotIn("a1!shared", serialized)

    def test_create_persists_a_generated_password_only_in_the_ignored_overlay(self) -> None:
        user, password = self.store.create(self.values)

        self.assertTrue(user["syntheticUserId"].startswith("local-"))
        self.assertEqual(28, len(password))
        self.assertNotIn("password", json.dumps(user).lower())
        overlay = json.loads(self.overlay_path.read_text(encoding="utf-8"))
        self.assertEqual(password, overlay["users"][0]["password"])
        self.assertEqual(20, len(self.store.public_users()))

    def test_update_disable_reenable_and_password_reset_keep_the_same_identity(self) -> None:
        created, original_password = self.store.create(self.values)
        synthetic_user_id = created["syntheticUserId"]
        disabled_values = {**self.values, "enabled": False, "title": "Disabled test persona"}

        disabled = self.store.update(synthetic_user_id, disabled_values)
        enabled = self.store.update(synthetic_user_id, self.values)
        reset_user, reset_password = self.store.reset_password(synthetic_user_id)

        self.assertEqual(synthetic_user_id, disabled["syntheticUserId"])
        self.assertFalse(disabled["enabled"])
        self.assertEqual(synthetic_user_id, enabled["syntheticUserId"])
        self.assertTrue(enabled["enabled"])
        self.assertEqual(synthetic_user_id, reset_user["syntheticUserId"])
        self.assertNotEqual(original_password, reset_password)

    def test_rejects_real_email_password_input_and_duplicate_username(self) -> None:
        with self.assertRaises(UserValidationError) as real_email_error:
            self.store.create({**self.values, "email": "alex@real-company.org"})
        with self.assertRaises(UserValidationError) as password_input_error:
            self.store.create({**self.values, "password": "do-not-accept"})

        self.store.create(self.values)
        with self.assertRaises(UserValidationError) as duplicate_error:
            self.store.create({**self.values, "email": "other@northlake.example.edu"})

        self.assertIn("email", real_email_error.exception.errors)
        self.assertIn("_form", password_input_error.exception.errors)
        self.assertIn("username", duplicate_error.exception.errors)


if __name__ == "__main__":
    unittest.main()
