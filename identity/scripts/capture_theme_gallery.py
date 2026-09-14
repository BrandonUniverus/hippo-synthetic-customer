"""Capture the Northlake identity pages as screenshots for a visual review.

Walks the real Keycloak flows in a headless browser and writes PNG files to
``identity/.runtime/evidence/theme-gallery/`` (desktop and phone widths):
sign-in, invalid password, password reset, forced password update,
authenticator setup, one-time-code prompt, sign-out, consent, error and expired
pages, the account console and the realm administration console.

Requirements: the identity stack must be running, and Playwright must be
installed once::

    python -m pip install playwright
    python -m playwright install chromium
    python identity/scripts/capture_theme_gallery.py

A throwaway ``theme.preview`` user is created through the administration API
for the flows that need a required action or a second factor and is deleted
at the end unless ``--keep-user`` is given. Checked-in synthetic identities are
not modified.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import re
import ssl
import struct
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib import error, parse, request

IDENTITY_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_FILE = IDENTITY_ROOT / ".env"
CERTIFICATE_DIRECTORY = IDENTITY_ROOT / ".runtime" / "certs"
DEFAULT_OUTPUT = IDENTITY_ROOT / ".runtime" / "evidence" / "theme-gallery"

PREVIEW_USER = "theme.preview"
PREVIEW_PASSWORD = "Preview-Pass-2026!"
PREVIEW_RENEWED_PASSWORD = "Preview-Pass-2026-Renewed!"

DESKTOP = {"width": 1280, "height": 900}
PHONE = {"width": 390, "height": 844}


class GalleryError(RuntimeError):
    """Raised when the gallery cannot be captured at all."""


def read_environment() -> dict[str, str]:
    if not ENVIRONMENT_FILE.is_file():
        raise GalleryError(f"{ENVIRONMENT_FILE} is missing. Run Initialize-Identity.ps1 first.")
    values: dict[str, str] = {}
    for line in ENVIRONMENT_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ssl_context() -> ssl.SSLContext:
    """Trust the local Caddy CA when it has been exported, otherwise localhost only."""
    for candidate in sorted(CERTIFICATE_DIRECTORY.glob("*")):
        if candidate.suffix.lower() in {".crt", ".pem", ".cer"} and "root" in candidate.name.lower():
            try:
                return ssl.create_default_context(cafile=str(candidate))
            except ssl.SSLError:
                continue
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class AdminApi:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.context = ssl_context()
        self.username = username
        self.password = password
        self.token = self._sign_in()

    def _sign_in(self) -> str:
        """Administrator access tokens last about a minute, so this is called on demand."""
        body = parse.urlencode(
            {
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
        ).encode()
        token = self._json(
            request.Request(
                f"{self.base_url}/realms/master/protocol/openid-connect/token",
                data=body,
                method="POST",
            )
        )
        return token["access_token"]

    def _json(self, req: request.Request) -> Any:
        try:
            with request.urlopen(req, context=self.context, timeout=20) as response:
                payload = response.read()
                return json.loads(payload) if payload else None
        except error.HTTPError as failure:
            detail = failure.read().decode("utf-8", "replace")
            raise GalleryError(f"{req.get_method()} {req.full_url} failed: {failure.code} {detail}") from failure

    def call(self, method: str, path: str, body: Any | None = None) -> Any:
        for attempt in range(2):
            data = json.dumps(body).encode() if body is not None else None
            req = request.Request(f"{self.base_url}/admin/realms/{path}", data=data, method=method)
            req.add_header("Authorization", f"Bearer {self.token}")
            if data is not None:
                req.add_header("Content-Type", "application/json")
            try:
                return self._json(req)
            except GalleryError as failure:
                if attempt == 0 and "401" in str(failure):
                    self.token = self._sign_in()
                    continue
                raise
        return None

    def clear_lockout(self, realm: str, user_id: str) -> None:
        """Brute-force protection counts the deliberate failed sign-ins; reset it."""
        self.call("DELETE", f"{realm}/attack-detection/brute-force/users/{user_id}")

    def delete_preview_user(self, realm: str) -> None:
        for user in self.call("GET", f"{realm}/users?username={PREVIEW_USER}&exact=true") or []:
            self.call("DELETE", f"{realm}/users/{user['id']}")

    def create_preview_user(self, realm: str, with_required_actions: bool = True) -> str:
        self.delete_preview_user(realm)
        self.call(
            "POST",
            f"{realm}/users",
            {
                "username": PREVIEW_USER,
                "enabled": True,
                "emailVerified": True,
                "firstName": "Theme",
                "lastName": "Preview",
                "email": f"{PREVIEW_USER}@northlake.example.edu",
                "requiredActions": ["UPDATE_PASSWORD", "CONFIGURE_TOTP"] if with_required_actions else [],
                "credentials": [{"type": "password", "value": PREVIEW_PASSWORD, "temporary": False}],
                "attributes": {"synthetic_note": ["throwaway account for theme screenshots"]},
            },
        )
        user_id = self.call("GET", f"{realm}/users?username={PREVIEW_USER}&exact=true")[0]["id"]
        # Realm administration rights let the gallery open the realm console.
        clients = self.call("GET", f"{realm}/clients?clientId=realm-management") if with_required_actions else []
        if clients:
            role = self.call("GET", f"{realm}/clients/{clients[0]['id']}/roles/realm-admin")
            self.call(
                "POST",
                f"{realm}/users/{user_id}/role-mappings/clients/{clients[0]['id']}",
                [{"id": role["id"], "name": role["name"]}],
            )
        return user_id


def totp_now(encoded_secret: str, digits: int = 6, period: int = 30) -> str:
    """Compute the current TOTP for the Base32 secret Keycloak shows on the setup page."""
    # A code computed a moment before the 30-second window rolls over is
    # rejected by the time the form arrives; wait for the next window instead.
    remaining = period - (time.time() % period)
    if remaining < 5:
        time.sleep(remaining + 0.5)
    normalized = re.sub(r"\s+", "", encoded_secret).upper()
    normalized += "=" * (-len(normalized) % 8)
    secret = base64.b32decode(normalized)
    counter = int(time.time() // period)
    digest = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return f"{code:0{digits}d}"


class Gallery:
    def __init__(self, output: Path, prefix: str) -> None:
        self.output = output
        self.prefix = prefix
        self.index = 0
        self.captured: list[str] = []
        self.failures: list[str] = []

    def shot(self, page: Any, name: str) -> None:
        self.index += 1
        target = self.output / f"{self.prefix}-{self.index:02d}-{name}.png"
        page.screenshot(path=str(target), full_page=True)
        self.captured.append(target.name)
        print(f"  captured {target.name}")

    def step(self, name: str, action: Callable[[], None], page: Any | None = None) -> None:
        try:
            action()
        except Exception as failure:  # noqa: BLE001 - keep walking, report at the end
            self.failures.append(f"{self.prefix} {name}: {failure}")
            print(f"  skipped {name}: {str(failure).splitlines()[0][:160]}")
            if page is not None:
                try:
                    page.screenshot(path=str(self.output / f"{self.prefix}-failed-{name}.png"), full_page=True)
                except Exception:  # noqa: BLE001
                    pass


def open_login(page: Any, account_url: str) -> None:
    page.goto(account_url)
    page.wait_for_selector("#kc-form-login", timeout=20000)


def sign_in(page: Any, username: str, password: str) -> None:
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("#kc-login")


def capture_desktop(
    browser: Any,
    gallery: Gallery,
    admin: AdminApi,
    user_id: str,
    env: dict[str, str],
    base: str,
    realm: str,
    customer: str,
) -> None:
    context = browser.new_context(viewport=DESKTOP, ignore_https_errors=True, locale="en-US")
    page = context.new_page()
    account_url = f"{base}/realms/{realm}/account/"
    logout_url = f"{base}/realms/{realm}/protocol/openid-connect/logout"
    otp_secret: dict[str, str] = {}

    def fresh_attempt() -> None:
        """Deliberate failures precede real sign-ins; keep the lockout from firing."""
        admin.clear_lockout(realm, user_id)
        page.wait_for_timeout(1500)

    def end_session() -> None:
        page.goto(logout_url)
        if page.query_selector("#kc-logout"):
            page.click("#kc-logout")
            page.wait_for_load_state("networkidle")

    def login() -> None:
        open_login(page, account_url)
        gallery.shot(page, "login")

    def login_invalid() -> None:
        sign_in(page, PREVIEW_USER, "not-the-password")
        page.wait_for_selector(".pf-v5-c-form-control.pf-m-error", timeout=15000)
        gallery.shot(page, "login-invalid")

    def page_expired() -> None:
        # Keycloak answers a sign-in form whose session code no longer matches
        # (an old tab submitted after the flow moved on) with the expired page.
        fresh_attempt()
        open_login(page, account_url)
        page.evaluate(
            "() => { const form = document.getElementById('kc-form-login');"
            " form.action = form.action.replace(/session_code=[^&]+/, 'session_code=stale-for-gallery'); }"
        )
        sign_in(page, PREVIEW_USER, PREVIEW_RENEWED_PASSWORD)
        page.wait_for_selector("#loginRestartLink, .pf-v5-c-alert.pf-m-danger", timeout=15000)
        gallery.shot(page, "page-expired")
        if page.query_selector("#loginRestartLink"):
            page.click("#loginRestartLink")
            page.wait_for_load_state("networkidle")

    def reset_password() -> None:
        open_login(page, account_url)
        page.click('a[href*="reset-credentials"]')
        page.wait_for_selector("#kc-reset-password-form", timeout=15000)
        gallery.shot(page, "reset-password")
        page.fill("#username", PREVIEW_USER)
        page.click("#kc-form-buttons")
        page.wait_for_selector("#kc-page-title", timeout=15000)
        page.wait_for_timeout(500)
        gallery.shot(page, "reset-password-submitted")

    def update_password() -> None:
        page.wait_for_selector("#kc-passwd-update-form", timeout=15000)
        gallery.shot(page, "update-password")
        page.fill("#password-new", "short")
        page.fill("#password-confirm", "different")
        page.click("#kc-submit")
        page.wait_for_selector(".pf-v5-c-form-control.pf-m-error, .pf-v5-c-alert", timeout=15000)
        gallery.shot(page, "update-password-invalid")
        page.fill("#password-new", PREVIEW_RENEWED_PASSWORD)
        page.fill("#password-confirm", PREVIEW_RENEWED_PASSWORD)
        page.click("#kc-submit")

    def otp_setup() -> None:
        page.wait_for_selector("#kc-totp-settings", timeout=15000)
        gallery.shot(page, "otp-setup")
        page.click("#mode-manual")
        page.wait_for_selector("#kc-totp-secret-key", timeout=15000)
        gallery.shot(page, "otp-setup-manual")
        otp_secret["value"] = page.inner_text("#kc-totp-secret-key")
        page.fill("#totp", "000000")
        page.fill("#userLabel", "Gallery phone")
        page.click("#saveTOTPBtn")
        page.wait_for_selector(".pf-v5-c-form-control.pf-m-error, .pf-v5-c-alert", timeout=15000)
        gallery.shot(page, "otp-setup-invalid")
        fresh_attempt()
        page.fill("#totp", totp_now(otp_secret["value"]))
        page.fill("#userLabel", "Gallery phone")
        page.click("#saveTOTPBtn")

    def update_password_and_otp() -> None:
        # Keycloak orders required actions by priority (authenticator setup
        # before the password update), so take whichever page arrives.
        open_login(page, account_url)
        sign_in(page, PREVIEW_USER, PREVIEW_PASSWORD)
        for _ in range(3):
            page.wait_for_selector("#kc-passwd-update-form, #kc-totp-settings, .pf-v5-c-page__main", timeout=20000)
            if page.query_selector("#kc-totp-settings"):
                otp_setup()
            elif page.query_selector("#kc-passwd-update-form"):
                update_password()
            else:
                break
        page.wait_for_url(re.compile(r".*/account/.*"), timeout=20000)

    def account_console() -> None:
        page.wait_for_selector(".pf-v5-c-page__main", timeout=30000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        gallery.shot(page, "account-personal-info")
        page.goto(f"{account_url}account-security/signing-in")
        page.wait_for_load_state("networkidle")
        page.get_by_role("heading", name=re.compile(r"^Signing in$", re.I)).wait_for(timeout=20000)
        page.wait_for_timeout(800)
        gallery.shot(page, "account-signing-in")
        page.goto(f"{account_url}account-security/device-activity")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        gallery.shot(page, "account-device-activity")

    def passkey_registration() -> None:
        page.goto(f"{account_url}account-security/signing-in")
        page.wait_for_load_state("networkidle")
        button = page.get_by_role("button", name=re.compile(r"passkey|security key", re.I))
        if button.count() == 0:
            print("  passkey registration is not enabled in this realm; skipped")
            return
        button.first.click()
        page.wait_for_selector("#kc-page-title", timeout=20000)
        page.wait_for_timeout(500)
        gallery.shot(page, "passkey-register")
        page.click("#cancelWebAuthnAIA")
        page.wait_for_load_state("networkidle")

    def recovery_codes() -> None:
        page.goto(f"{account_url}account-security/signing-in")
        page.wait_for_load_state("networkidle")
        button = page.get_by_role("button", name=re.compile(r"recovery", re.I))
        if button.count() == 0:
            print("  recovery codes are not enabled in this realm; skipped")
            return
        button.first.click()
        page.wait_for_selector("#kc-recovery-codes-list", timeout=20000)
        gallery.shot(page, "recovery-codes")
        page.click("#cancelRecoveryAuthnCodesBtn")
        page.wait_for_load_state("networkidle")

    def admin_console() -> None:
        page.goto(f"{base}/admin/{realm}/console/")
        page.wait_for_selector(".pf-v5-c-page__sidebar", timeout=30000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        gallery.shot(page, "admin-console")

    def sign_out() -> None:
        page.goto(logout_url)
        page.wait_for_selector("#kc-logout", timeout=15000)
        gallery.shot(page, "logout-confirm")
        page.click("#kc-logout")
        page.wait_for_selector("#kc-page-title", timeout=15000)
        page.wait_for_timeout(500)
        gallery.shot(page, "logged-out")

    def login_otp() -> None:
        open_login(page, account_url)
        sign_in(page, PREVIEW_USER, PREVIEW_RENEWED_PASSWORD)
        page.wait_for_selector("#kc-otp-login-form", timeout=15000)
        gallery.shot(page, "login-otp")
        page.fill("#otp", "000000")
        page.click("#kc-login")
        page.wait_for_selector(".pf-v5-c-form-control.pf-m-error, .pf-v5-c-alert", timeout=15000)
        gallery.shot(page, "login-otp-invalid")
        fresh_attempt()
        page.fill("#otp", totp_now(otp_secret["value"]))
        page.click("#kc-login")
        page.wait_for_url(re.compile(r".*/account/.*"), timeout=20000)

    def error_page() -> None:
        page.goto(f"{base}/realms/{realm}/protocol/openid-connect/auth?client_id=does-not-exist&response_type=code")
        page.wait_for_selector("#kc-error-message", timeout=15000)
        gallery.shot(page, "error")

    def consent() -> None:
        page.goto(f"{customer}/customer/")
        page.wait_for_selector("#realm-grid a", timeout=20000)
        page.get_by_role("link", name=re.compile(r"grant probe consent", re.I)).first.click()
        page.wait_for_selector("#kc-form-login, #kc-oauth", timeout=20000)
        if page.query_selector("#kc-form-login"):
            sign_in(page, PREVIEW_USER, PREVIEW_PASSWORD)
        page.wait_for_selector("#kc-oauth", timeout=20000)
        gallery.shot(page, "consent")
        page.click("#kc-cancel")
        page.wait_for_load_state("networkidle")

    # Successful sign-ins first: the deliberate failures later in the walk
    # would otherwise trip brute-force protection for the real ones.
    gallery.step("update-password-and-otp", update_password_and_otp, page)
    gallery.step("account-console", account_console, page)
    gallery.step("passkey-registration", passkey_registration, page)
    gallery.step("recovery-codes", recovery_codes, page)
    gallery.step("admin-console", admin_console, page)
    gallery.step("sign-out", sign_out, page)
    if otp_secret:
        gallery.step("login-otp", login_otp, page)
        gallery.step("end-session", end_session, page)
    gallery.step("login", login, page)
    gallery.step("login-invalid", login_invalid, page)
    if otp_secret:
        gallery.step("page-expired", page_expired, page)
    gallery.step("reset-password", reset_password, page)
    gallery.step("error-page", error_page, page)
    gallery.step("consent", consent, page)
    context.close()


def capture_phone(browser: Any, gallery: Gallery, admin: AdminApi, user_id: str, base: str, realm: str) -> None:
    context = browser.new_context(
        viewport=PHONE,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        ignore_https_errors=True,
        locale="en-US",
    )
    page = context.new_page()
    account_url = f"{base}/realms/{realm}/account/"

    def login() -> None:
        open_login(page, account_url)
        gallery.shot(page, "login")
        sign_in(page, PREVIEW_USER, "not-the-password")
        page.wait_for_selector(".pf-v5-c-form-control.pf-m-error", timeout=15000)
        gallery.shot(page, "login-invalid")

    def reset_password() -> None:
        page.click('a[href*="reset-credentials"]')
        page.wait_for_selector("#kc-reset-password-form", timeout=15000)
        gallery.shot(page, "reset-password")

    def login_otp() -> None:
        admin.clear_lockout(realm, user_id)
        page.wait_for_timeout(1500)
        open_login(page, account_url)
        sign_in(page, PREVIEW_USER, PREVIEW_RENEWED_PASSWORD)
        page.wait_for_selector("#kc-otp-login-form", timeout=15000)
        gallery.shot(page, "login-otp")

    def sign_out() -> None:
        page.goto(f"{base}/realms/{realm}/protocol/openid-connect/logout")
        page.wait_for_selector("#kc-logout", timeout=15000)
        gallery.shot(page, "logout-confirm")

    gallery.step("login", login, page)
    gallery.step("reset-password", reset_password, page)
    gallery.step("login-otp", login_otp, page)
    gallery.step("sign-out", sign_out, page)
    context.close()


def capture_sites(browser: Any, gallery: Gallery, base: str, customer: str) -> None:
    """The launchpad, configuration pages and customer lab share the login chrome."""
    pages = [
        ("launchpad", f"{base}/"),
        ("configure-provider", f"{base}/configure"),
        ("configure-oidc", f"{base}/configure/oidc"),
        ("configure-saml", f"{base}/configure/saml"),
        ("configure-scenarios", f"{base}/configure/scenarios"),
        ("configure-scim", f"{base}/configure/scim"),
        ("configure-users", f"{base}/configure/users"),
        ("configure-groups", f"{base}/configure/groups"),
        ("customer-lab", f"{customer}/customer/"),
    ]
    for viewport, phone in ((DESKTOP, False), (PHONE, True)):
        context = browser.new_context(viewport=viewport, ignore_https_errors=True, locale="en-US")
        page = context.new_page()
        for name, url in pages:
            if phone and name not in {"launchpad", "configure-provider", "configure-users", "customer-lab"}:
                continue

            def capture(name: str = name, url: str = url) -> None:
                page.goto(url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(600)
                gallery.shot(page, name + ("-phone" if phone else ""))

            gallery.step(name, capture, page)
        context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory for the PNG files.")
    parser.add_argument("--keep-user", action="store_true", help=f"Leave the {PREVIEW_USER} account in place.")
    arguments = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run: python -m pip install playwright && python -m playwright install chromium")
        return 2

    env = read_environment()
    base = env.get("IDENTITY_PUBLIC_BASE_URL", "https://localhost:8443").rstrip("/")
    customer = env.get("NORTHLAKE_CUSTOMER_PUBLIC_BASE_URL", "https://customer.localtest.me:8443").rstrip("/")
    realm = env.get("NORTHLAKE_REALM_KEY", "northlake")
    admin = AdminApi(base, env["KEYCLOAK_ADMIN"], env["KEYCLOAK_ADMIN_PASSWORD"])

    output = arguments.output
    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("*.png"):
        stale.unlink()

    print(f"Creating {PREVIEW_USER} in realm {realm}")
    user_id = admin.create_preview_user(realm)
    # The customer lab signs in against the first scenario realm for the consent page.
    lab_realm = "northlake-lab-a"
    try:
        admin.create_preview_user(lab_realm, with_required_actions=False)
        lab_realm_ready = True
    except GalleryError as failure:
        print(f"  consent capture unavailable: {str(failure)[:120]}")
        lab_realm_ready = False
    desktop = Gallery(output, "desktop")
    phone = Gallery(output, "phone")
    sites = Gallery(output, "site")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            print("Desktop")
            capture_desktop(browser, desktop, admin, user_id, env, base, realm, customer)
            print("Phone")
            capture_phone(browser, phone, admin, user_id, base, realm)
            print("Sites")
            capture_sites(browser, sites, base, customer)
            browser.close()
    finally:
        if not arguments.keep_user:
            admin.delete_preview_user(realm)
            if lab_realm_ready:
                admin.delete_preview_user(lab_realm)
            print(f"Deleted {PREVIEW_USER}")

    print(f"\n{len(desktop.captured) + len(phone.captured) + len(sites.captured)} screenshots in {output}")
    for failure in desktop.failures + phone.failures + sites.failures:
        print(f"  not captured: {failure}")
    return 1 if not desktop.captured else 0


if __name__ == "__main__":
    sys.exit(main())
