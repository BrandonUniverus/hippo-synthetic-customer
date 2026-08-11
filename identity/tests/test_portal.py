import unittest
from html.parser import HTMLParser
from pathlib import Path


IDENTITY_ROOT = Path(__file__).resolve().parents[1]


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


class PortalTests(unittest.TestCase):
    def test_launchpad_uses_provider_and_application_routes(self) -> None:
        document = (IDENTITY_ROOT / "portal" / "index.html").read_text(
            encoding="utf-8"
        )
        parser = LinkCollector()
        parser.feed(document)

        links_by_href = {
            link["href"]: link for link in parser.links if link.get("href")
        }
        account_links = [
            link
            for link in parser.links
            if link.get("href") == "/realms/northlake/account/"
        ]
        self.assertTrue(account_links)
        self.assertTrue(
            any(link.get("target") == "_blank" for link in account_links),
        )
        self.assertIn("/open-energyhippo", links_by_href)
        self.assertIn("/configure/users", links_by_href)
        self.assertIn(
            "/realms/northlake/.well-known/openid-configuration",
            links_by_href,
        )
        self.assertIn(
            "/realms/northlake/protocol/saml/descriptor",
            links_by_href,
        )
        self.assertIn(
            "/realms/northlake/protocol/saml/clients/eemsuite-web-saml-standard",
            links_by_href,
        )
        self.assertEqual(
            "_blank",
            links_by_href[
                "/realms/northlake/protocol/saml/clients/eemsuite-web-saml-standard"
            ].get("target"),
        )

    def test_launchpad_exposes_the_northlake_saml_contract(self) -> None:
        document = (IDENTITY_ROOT / "portal" / "index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("urn:energyhippo:eemsuite-web:saml:standard", document)
        self.assertIn("(IdP entity ID, persistent NameID)", document)
        self.assertIn("Response + Assertion · RSA-SHA256", document)
        self.assertIn("HTTP-POST", document)
        self.assertIn("the focused verifier checks signatures", document)

    def test_launchpad_does_not_collect_credentials_or_process_tokens(self) -> None:
        document = (IDENTITY_ROOT / "portal" / "index.html").read_text(
            encoding="utf-8"
        ).lower()

        self.assertNotIn("<form", document)
        self.assertNotIn("<input", document)
        self.assertNotIn("<script", document)
        self.assertIn("never handles passwords or tokens", document)

    def test_edge_configuration_isolates_portal_from_keycloak(self) -> None:
        caddyfile = (IDENTITY_ROOT / "Caddyfile").read_text(encoding="utf-8")
        compose = (IDENTITY_ROOT / "compose.yml").read_text(encoding="utf-8")

        self.assertIn("@portal path /", caddyfile)
        self.assertIn("@energyhippo path /open-energyhippo", caddyfile)
        self.assertIn("reverse_proxy keycloak:8080", caddyfile)
        self.assertIn("intermediate_lifetime 180d", caddyfile)
        self.assertIn("lifetime 720h", caddyfile)
        self.assertIn("./portal:/srv/northlake-portal:ro", compose)
        self.assertIn("EEMSUITE_APPLICATION_HOME_URL:", compose)
        self.assertIn("@configuration path /configure /configure/*", caddyfile)
        self.assertIn("reverse_proxy configuration:8081", caddyfile)
        self.assertIn("configuration:", compose)
        self.assertIn('href="/configure"', (IDENTITY_ROOT / "portal" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
