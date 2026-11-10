import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


IDENTITY_ROOT = Path(__file__).resolve().parents[1]
SITE = IDENTITY_ROOT / "portal" / "index.html"
CONFIGURATION_HOME = IDENTITY_ROOT / "configuration" / "index.html"


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag == "a":
            self.links.append(dict(attrs))


def _links(path: Path) -> list[dict[str, str | None]]:
    parser = LinkCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.links


class PortalTests(unittest.TestCase):
    def test_site_links_to_the_account_lab_and_brand_pages(self) -> None:
        hrefs = {link.get("href") for link in _links(SITE)}

        self.assertIn("/realms/northlake/account/", hrefs)
        self.assertIn("/configure", hrefs)
        self.assertIn("https://customer.localtest.me:8443/customer/", hrefs)
        self.assertIn("/brands/", hrefs)
        self.assertIn("/meter-reading/", hrefs)
        # Utility links read NORTHLAKE_SOURCES_URL, which defaults to /utilities.
        self.assertIn("{{$sources}}/downloads/", hrefs)
        self.assertIn('default "/utilities"', SITE.read_text(encoding="utf-8"))

    def test_site_energy_hippo_links_are_sp_initiated_deep_links(self) -> None:
        document = SITE.read_text(encoding="utf-8")

        # The site is a Caddy template: the EEM address and provider key come
        # from the environment, never from the page.
        self.assertIn('env "EEMSUITE_APPLICATION_HOME_URL"', document)
        self.assertIn('env "NORTHLAKE_EEM_PROVIDER_KEY"', document)
        self.assertIn("/Account/ExternalAutoLogin?provider=%s&amp;returnRoute=", document)

        deep_links = [
            link["href"]
            for link in _links(SITE)
            if (link.get("href") or "").startswith("{{$sso}}")
        ]
        self.assertTrue(deep_links)
        for href in deep_links:
            # Every shortcut passes an encoded local hash route, which EEM keeps
            # through the sign-in and opens afterwards.
            self.assertRegex(href, r"^\{\{\$sso\}\}%23%2F[A-Za-z]")

    def test_site_does_not_collect_credentials_or_run_scripts(self) -> None:
        document = SITE.read_text(encoding="utf-8").lower()

        self.assertNotIn("<form", document)
        self.assertNotIn("<input", document)
        self.assertNotIn("<script", document)

    def test_configuration_home_carries_the_provider_test_links(self) -> None:
        links_by_href = {
            link["href"]: link for link in _links(CONFIGURATION_HOME) if link.get("href")
        }

        self.assertIn("/realms/northlake/account/", links_by_href)
        self.assertIn("/realms/northlake/protocol/saml/descriptor", links_by_href)
        self.assertIn("/realms/northlake/.well-known/openid-configuration", links_by_href)
        self.assertIn("https://customer.localtest.me:8443/customer/", links_by_href)
        # Keycloak names the IdP-initiated URL after the SAML provider key
        # (generate_realm.py: idpInitiatedSsoUrl), not after a client ID.
        self.assertEqual(
            "_blank",
            links_by_href[
                "/realms/northlake/protocol/saml/clients/northlake-saml-standard"
            ].get("target"),
        )
        self.assertIn(
            "urn:energyhippo:eemsuite-web:saml:standard",
            CONFIGURATION_HOME.read_text(encoding="utf-8"),
        )

    def test_edge_configuration_isolates_portal_from_keycloak(self) -> None:
        caddyfile = (IDENTITY_ROOT / "Caddyfile").read_text(encoding="utf-8")
        compose = (IDENTITY_ROOT / "compose.yml").read_text(encoding="utf-8")

        portal_block = re.search(r"handle @portal \{(.*?)\n\t\}", caddyfile, flags=re.S)
        self.assertIsNotNone(portal_block)
        self.assertIn("templates", portal_block.group(1))
        self.assertIn("@portal path /", caddyfile)
        self.assertIn("@energyhippo path /open-energyhippo", caddyfile)
        self.assertIn("handle_path /brands/*", caddyfile)
        self.assertIn("handle_path /documents/*", caddyfile)
        self.assertIn("reverse_proxy keycloak:8080", caddyfile)
        self.assertIn("intermediate_lifetime 180d", caddyfile)
        self.assertIn("lifetime 720h", caddyfile)
        self.assertIn("./portal:/srv/northlake-portal:ro", compose)
        self.assertIn("../brands:/srv/brands:ro", compose)
        self.assertIn("../documents:/srv/northlake-documents:ro", compose)
        self.assertIn("EEMSUITE_APPLICATION_HOME_URL:", compose)
        self.assertIn("NORTHLAKE_EEM_PROVIDER_KEY:", compose)
        self.assertIn("@configuration path /configure /configure/*", caddyfile)
        self.assertIn("reverse_proxy configuration:8081", caddyfile)
        self.assertIn("configuration:", compose)
        self.assertIn("customer-site:", compose)
        self.assertIn("reverse_proxy customer-site:8082", caddyfile)
        self.assertIn('href="/configure"', SITE.read_text(encoding="utf-8"))

    def test_edge_serves_utilities_and_meter_reading_inside_the_site(self) -> None:
        caddyfile = (IDENTITY_ROOT / "Caddyfile").read_text(encoding="utf-8")
        compose = (IDENTITY_ROOT / "compose.yml").read_text(encoding="utf-8")

        utilities = re.search(r"handle_path /utilities/\* \{(.*?)\n\t\}", caddyfile, flags=re.S)
        self.assertIsNotNone(utilities)
        # Today's stylesheets replace the bundle's older copies; the rest is proxied.
        self.assertIn("root * /srv/northlake-branding", utilities.group(1))
        self.assertIn("root * /srv/northlake-sources-web", utilities.group(1))
        self.assertIn("reverse_proxy {$NORTHLAKE_SOURCES_UPSTREAM:", utilities.group(1))
        self.assertIn("handle_path /meter-reading/*", caddyfile)
        self.assertIn("reverse_proxy {$NORTHLAKE_HANDHELD_UPSTREAM:", caddyfile)
        self.assertIn("../services/sources/web:/srv/northlake-sources-web:ro", compose)
        self.assertIn("NORTHLAKE_SOURCES_UPSTREAM:", compose)
        self.assertIn("NORTHLAKE_HANDHELD_UPSTREAM:", compose)


if __name__ == "__main__":
    unittest.main()
