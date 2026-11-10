"""Every brand folder is complete and speaks the shared token names.

Run from the repository root:

    python -m unittest discover -s brands/tests -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

BRANDS = Path(__file__).resolve().parents[1]
FOLDERS = ["northlake", "valley-electric", "river-city", "sierra-gas", "helios", "thermal-plant", "ridgeline-wind"]

# The names every template may rely on (brands/README.md, "Token names").
SHARED = [
    "primary", "primary-strong", "on-primary", "accent", "accent-ink", "on-accent", "support",
    "ink", "muted", "canvas", "surface", "tint", "line", "line-strong", "link", "heading-ink",
    "positive", "negative", "caution", "positive-tint", "negative-tint", "caution-tint",
    "topbar-bg", "topbar-ink", "header-bg", "header-ink", "header-rule", "footer-bg", "footer-ink",
    "font-display", "font-text", "font-mono", "weight-display", "weight-strong", "tracking-display",
    "case-heading", "case-label", "case-button", "size-h1", "size-body", "leading-body",
    "space-1", "space-8", "content-width", "radius", "rule", "rule-accent", "logo-height", "logo-min-height",
]


def _token_names(folder: str) -> set[str]:
    text = (BRANDS / folder / "tokens.css").read_text(encoding="utf-8")
    names = set(re.findall(r"--([a-z0-9-]+):", text))
    for imported in re.findall(r'@import url\("\.\./([a-z-]+)/tokens\.css"\)', text):
        names |= _token_names(imported)
    return names


class BrandTests(unittest.TestCase):
    def test_every_brand_defines_the_shared_token_names(self) -> None:
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                self.assertEqual([], sorted(set(SHARED) - _token_names(folder)))

    def test_logos_are_outlined(self) -> None:
        # Browsers never load web fonts for an SVG shown through <img>.
        for folder in FOLDERS:
            for name in ("logo.svg", "logo-reversed.svg", "mark.svg"):
                with self.subTest(folder=folder, file=name):
                    svg = (BRANDS / folder / name).read_text(encoding="utf-8")
                    self.assertTrue(svg.startswith("<svg"))
                    self.assertNotIn("<text", svg)

    def test_font_faces_point_at_vendored_files_with_their_licence(self) -> None:
        for folder in FOLDERS:
            css = (BRANDS / folder / "fonts.css").read_text(encoding="utf-8")
            for source in re.findall(r'url\("(fonts/[^"]+)"\)', css):
                with self.subTest(folder=folder, font=source):
                    self.assertTrue((BRANDS / folder / source).is_file())
            fonts = BRANDS / folder / "fonts"
            if fonts.exists():
                with self.subTest(folder=folder, licence="OFL"):
                    self.assertTrue(list(fonts.glob("OFL-*.txt")))


if __name__ == "__main__":
    unittest.main()
