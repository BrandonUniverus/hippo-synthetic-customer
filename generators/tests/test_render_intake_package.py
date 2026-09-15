"""Intake binder checks: it carries every source word, the current packet and no stale draft."""

import re
import unittest
from datetime import date
from html.parser import HTMLParser

import yaml

from generators.render_intake_package import CUSTOMER, ONBOARDING, ROOT, SECTIONS, TARGET, parse_blocks, render_package


class VisibleText(HTMLParser):
    """Collect page text per section, ignoring the embedded stylesheet."""

    def __init__(self):
        super().__init__()
        self.sections = {}
        self.current = None
        self.depth = 0
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.skip = True
        if tag == "section":
            if self.current is None and dict(attrs).get("id", "").startswith("section-"):
                self.current = dict(attrs)["id"][len("section-"):]
                self.sections[self.current] = []
                self.depth = 0
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "style":
            self.skip = False
        if tag == "section" and self.current is not None:
            self.depth -= 1
            if self.depth == 0:
                self.current = None

    def handle_data(self, data):
        if self.current is not None and not self.skip:
            self.sections[self.current].append(data)


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def source_words(markdown):
    """Words a reader sees: link targets and list markers (drawn by the browser) are not text."""
    text = re.sub(r"\]\([^)]*\)", "]", markdown)
    text = re.sub(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])\s+", "", text, flags=re.M)
    return words(text)


def first_missing(needle, haystack):
    """Index of the first needle word that cannot be matched in order, or None."""
    position = 0
    for index, word in enumerate(needle):
        while position < len(haystack) and haystack[position] != word:
            position += 1
        if position == len(haystack):
            return index
        position += 1
    return None


class IntakePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = render_package()
        parser = VisibleText()
        parser.feed(cls.html)
        cls.sections = {key: words(" ".join(parts)) for key, parts in parser.sections.items()}
        cls.onboarding = yaml.safe_load((ROOT / ONBOARDING).read_text(encoding="utf-8"))

    def assertContains(self, needle):
        self.assertTrue(needle in self.html, f"binder is missing: {needle[:160]}")

    def test_every_source_word_is_rendered_in_order_within_its_section(self):
        for section in SECTIONS:
            expected = []
            for source in section["sources"]:
                expected += source_words((ROOT / CUSTOMER / source).read_text(encoding="utf-8"))
            rendered = self.sections[section["key"]]
            missing = first_missing(expected, rendered)
            context = " ".join(expected[max(0, (missing or 0) - 6):(missing or 0) + 6])
            self.assertIsNone(missing, f"{section['key']}: source text not rendered near '{context}'")

    def test_every_table_row_is_rendered(self):
        tables = [block for section in SECTIONS for source in section["sources"] for block in parse_blocks((ROOT / CUSTOMER / source).read_text(encoding="utf-8")) if block["kind"] == "table"]
        self.assertEqual(self.html.count("<tr>"), sum(len(table["rows"]) + 1 for table in tables))

    def test_packet_version_and_issue_date_come_from_the_onboarding_manifest(self):
        version = str(self.onboarding["packetVersion"])
        issued = date.fromisoformat(str(self.onboarding["issuedOn"]))
        self.assertContains(f"<title>Northlake University \u2014 Onboarding Data Package \u2014 Packet {version}</title>")
        self.assertEqual(self.html.count(f"Synthetic<br>Packet {version}"), len(SECTIONS))
        self.assertContains(f"Onboarding Data Package \\00B7 Packet {version}")
        self.assertEqual(set(re.findall(r"Packet (\d+(?:\.\d+)*)", self.html)), {version})
        self.assertContains(f'<div class="fact-k">Version</div><div class="fact-v">Packet {version}</div>')
        self.assertFalse("<br>Draft" in self.html, "a section chip still says Draft")
        self.assertContains(f'<div class="fact-k">Issued</div><div class="fact-v">{issued:%B} {issued.day}, {issued.year}</div>')

    def test_contents_lists_every_section_and_every_tariff_sheet_is_linked(self):
        for number, section in enumerate(SECTIONS, start=1):
            self.assertContains(f'href="#section-{section["key"]}"><span class="toc-n">{number:02d}</span>')
            self.assertContains(f'id="section-{section["key"]}"')
        self.assertContains('<a href="#section-register">Facilities and Meter Register</a>')
        self.assertEqual(self.html.count('class="sheet-band"'), 5)

    def test_checked_in_binder_matches_regeneration(self):
        checked_in = (ROOT / TARGET).read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertTrue(checked_in == self.html, f"{TARGET.as_posix()} is stale; run python generators/render_intake_package.py")


if __name__ == "__main__":
    unittest.main()
