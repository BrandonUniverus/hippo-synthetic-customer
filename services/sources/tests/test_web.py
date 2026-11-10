import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from services.sources.web import render_pages


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.downloads = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "download" in values:
            self.downloads.append(values["href"])
        for name, value in attrs:
            if name in {"href", "src"}:
                self.targets.append(value)


class ProviderNavigationTests(unittest.TestCase):
    def test_provider_month_pagination_and_download_links_resolve_to_published_files(self):
        source_root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary)
            records = []
            for number in range(103):
                relative = f"valley/files/day {number}.csv"
                url = "releases/test/files/" + relative
                target = public / url
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"data")
                records.append({"path": relative, "url": url, "size": 4, "metadata": {"provider": "valley_electric_district", "kind": "gateway", "source": "valley", "period_start": "2024-02-01"}})
            (public / "catalog.json").write_text("{}")
            render_pages(public, source_root, iter(records), {"identity": {"version": "test"}, "completed_through": "2024-03-01T00:00:00Z"})
            html_pages = list(public.rglob("*.html"))
            self.assertGreater(len(html_pages), 8)
            for page in html_pages:
                links = Links()
                links.feed(page.read_text(encoding="utf-8"))
                for link in links.targets:
                    path = unquote(urlsplit(link).path)
                    resolved = (page.parent / path).resolve()
                    self.assertTrue(resolved.is_relative_to(public.resolve()), (page, link))
                    self.assertTrue(resolved.exists(), (page, link))
                    if path.endswith("/"):
                        self.assertTrue((resolved / "index.html").is_file(), (page, link))

    def test_account_and_year_links_filter_downloads_without_cross_account_leakage(self):
        source_root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary)
            records = []
            for account, period in (("account-a", "2024-01-01"), ("account-a", "2024-02-01"), ("account-a", "2025-03-01"), ("account-b", "2024-02-01"), ("account-b", "2025-03-01")):
                path = f"bills/{account}/{period}.pdf"
                url = "releases/test/files/" + path
                target = public / url
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"bill")
                records.append({"path": path, "url": url, "size": 4, "metadata": {"provider": "valley_electric_district", "account": account, "source": account, "kind": "bill", "period_start": period}})
            (public / "catalog.json").write_text("{}")
            render_pages(public, source_root, iter(records), {"identity": {"version": "test"}, "completed_through": "2025-04-01T00:00:00Z"})
            provider = public / "providers/valley-electric-district"
            navigation = Links()
            navigation.feed((provider / "index.html").read_text(encoding="utf-8"))
            destinations = {(provider / unquote(urlsplit(link).path)).resolve() for link in navigation.targets}
            self.assertIn((provider / "accounts/account-a").resolve(), destinations)
            self.assertIn((provider / "years/2024").resolve(), destinations)
            for directory, account, year in ((provider / "accounts/account-a", "account-a", None), (provider / "accounts/account-a/years/2024", "account-a", "2024"), (provider / "years/2024", None, "2024")):
                downloads = set()
                for page in directory.rglob("*.html"):
                    links = Links()
                    links.feed(page.read_text(encoding="utf-8"))
                    for link in links.targets:
                        resolved = (page.parent / unquote(urlsplit(link).path)).resolve()
                        self.assertTrue(resolved.is_relative_to(public.resolve()), (page, link))
                        self.assertTrue(resolved.exists(), (page, link))
                    downloads.update((page.parent / unquote(urlsplit(link).path)).resolve().relative_to(public.resolve()).as_posix() for link in links.downloads)
                expected = {record["url"] for record in records if (account is None or record["metadata"]["account"] == account) and (year is None or record["metadata"]["period_start"].startswith(year))}
                self.assertEqual(expected, downloads)


if __name__ == "__main__":
    unittest.main()
