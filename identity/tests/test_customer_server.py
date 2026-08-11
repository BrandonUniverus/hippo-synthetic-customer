from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from identity.customer.server import (
    CustomerLab,
    CustomerLabError,
    EvidenceStore,
    _session_cookie,
    safe_return_path,
)


class CustomerLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temporary_directory.name)
        for slot, suffix in (("labA", "a"), ("labB", "b")):
            realm = f"northlake-lab-{suffix}"
            path = self.runtime / "scenarios" / slot / "connection.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "realm": realm,
                        "issuer": f"https://localhost:8443/realms/{realm}",
                        "scenario": {"scenarioName": "Browser test"},
                        "testUsers": {"active": {"username": "alex.morgan"}},
                        "customerSite": {
                            "publicBaseUrl": "https://customer.localtest.me:8443",
                            "clients": {
                                "customer": {
                                    "clientId": f"northlake-customer-{realm}",
                                    "redirectUri": (
                                        "https://customer.localtest.me:8443/customer/oidc/"
                                        f"callback/{realm}/customer"
                                    ),
                                    "postLogoutRedirectUri": (
                                        "https://customer.localtest.me:8443/customer/"
                                        f"signed-out/{realm}"
                                    ),
                                    "frontChannelLogoutUri": (
                                        "https://customer.localtest.me:8443/customer/"
                                        f"frontchannel-logout/{realm}/customer"
                                    ),
                                    "consentRequired": False,
                                },
                                "probe": {
                                    "clientId": f"northlake-probe-{realm}",
                                    "redirectUri": (
                                        "https://customer.localtest.me:8443/customer/oidc/"
                                        f"callback/{realm}/probe"
                                    ),
                                    "postLogoutRedirectUri": (
                                        "https://customer.localtest.me:8443/customer/"
                                        f"signed-out/{realm}"
                                    ),
                                    "frontChannelLogoutUri": (
                                        "https://customer.localtest.me:8443/customer/"
                                        f"frontchannel-logout/{realm}/probe"
                                    ),
                                    "consentRequired": True,
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
        self.lab = CustomerLab(
            self.runtime,
            "https://customer.localtest.me:8443",
            "https://localhost:8443",
            "http://keycloak:8080",
            "customer-client-secret-for-tests",
            "admin",
            "admin-password-for-tests",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_safe_return_path_accepts_only_customer_relative_paths(self) -> None:
        self.assertEqual(
            "/customer/deep-link/reports/monthly?view=variance",
            safe_return_path("/customer/deep-link/reports/monthly?view=variance"),
        )
        for unsafe in (
            "https://attacker.example/customer/",
            "//attacker.example/customer/",
            "/customer/../../admin#fragment",
            "/customer/%2e%2e/admin",
            "/customer/%252e%252e/admin",
            "/other/path",
            "/customer\\evil",
        ):
            self.assertEqual("/customer/", safe_return_path(unsafe))

    def test_public_state_exposes_two_realms_without_secrets_or_tokens(self) -> None:
        state = self.lab.public_state(None)
        serialized = json.dumps(state)

        self.assertTrue(state["ready"])
        self.assertTrue(state["crossSite"])
        self.assertEqual({"labA", "labB"}, set(state["realms"]))
        self.assertTrue(state["realms"]["labA"]["probeConsentRequired"])
        self.assertNotIn("customer-client-secret-for-tests", serialized)
        self.assertNotIn("admin-password-for-tests", serialized)
        self.assertFalse(state["coverage"]["backChannelLogoutClaimed"])

    def test_authorization_is_code_pkce_and_binds_bounded_options(self) -> None:
        location = self.lab.begin_authorization(
            slot="labA",
            kind="probe",
            prompt="none",
            login_hint="alex.morgan",
            max_age=300,
            return_to="/customer/deep-link/reports/monthly?view=variance",
            cookie_mode="None",
            frame=True,
            session_id=None,
        )

        self.assertTrue(location.startswith("https://localhost:8443/realms/northlake-lab-a/"))
        self.assertIn("response_type=code", location)
        self.assertIn("code_challenge_method=S256", location)
        self.assertIn("prompt=none", location)
        self.assertIn("login_hint=alex.morgan", location)
        self.assertIn("max_age=300", location)
        event = self.lab.evidence.read()[-1]
        self.assertEqual("authorization-started", event["event"])
        self.assertTrue(event["details"]["frame"])
        self.assertTrue(event["details"]["loginHintSupplied"])

    def test_authorization_rejects_unbounded_prompt_cookie_and_max_age(self) -> None:
        common = {
            "slot": "labA",
            "kind": "customer",
            "login_hint": None,
            "return_to": "/customer/",
            "frame": False,
            "session_id": None,
        }
        with self.assertRaises(CustomerLabError):
            self.lab.begin_authorization(
                **common,
                prompt="select_account",
                max_age=None,
                cookie_mode="Lax",
            )
        with self.assertRaises(CustomerLabError):
            self.lab.begin_authorization(
                **common,
                prompt="",
                max_age=86_401,
                cookie_mode="Lax",
            )
        with self.assertRaises(CustomerLabError):
            self.lab.begin_authorization(
                **common,
                prompt="",
                max_age=None,
                cookie_mode="Strict",
            )

    def test_frontchannel_delivery_without_cookie_is_recorded_not_overclaimed(self) -> None:
        outcome, cleared = self.lab.frontchannel_logout(
            realm="northlake-lab-a",
            kind="customer",
            issuer="https://localhost:8443/realms/northlake-lab-a",
            sid="provider-session-id",
            session_id=None,
        )

        self.assertEqual("delivery-without-rp-session-cookie", outcome)
        self.assertFalse(cleared)
        event = self.lab.evidence.read()[-1]
        self.assertFalse(event["details"]["rpCookiePresent"])

    def test_browser_observation_is_bounded_and_classified(self) -> None:
        event = self.lab.record_browser_observation(
            "labA",
            "provider-frame-unavailable",
        )

        self.assertEqual("silent-iframe", event["event"])
        self.assertEqual("expected-controlled-unavailability", event["details"]["classification"])
        with self.assertRaises(CustomerLabError):
            self.lab.record_browser_observation("labA", "frame-success-assumed")

    def test_cookie_profiles_are_secure_http_only_and_expirable(self) -> None:
        lax = _session_cookie("session-id", "Lax")
        unrestricted = _session_cookie("session-id", "None")
        cleared = _session_cookie("", "None", clear=True)

        for value in (lax, unrestricted):
            self.assertIn("Secure", value)
            self.assertIn("HttpOnly", value)
            self.assertIn("Path=/customer/", value)
        self.assertIn("SameSite=Lax", lax)
        self.assertIn("SameSite=None", unrestricted)
        self.assertIn("Max-Age=0", cleared)

    def test_evidence_is_bounded_and_can_be_cleared(self) -> None:
        store = EvidenceStore(self.runtime / "evidence.json")
        for index in range(205):
            store.add("test", realm=None, outcome=str(index))
        self.assertEqual(200, len(store.read()))
        self.assertEqual("5", store.read()[0]["outcome"])
        store.clear()
        self.assertEqual([], store.read())


if __name__ == "__main__":
    unittest.main()
