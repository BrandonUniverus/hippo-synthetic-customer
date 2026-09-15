"""Document checks: every source has a current PDF and every link resolves."""

import io
import unittest

from pypdf import PdfReader

from generators.documents.build_documents import ROOT, defaults_for, pdf_for, render_all, source_files
from generators.documents.render_northlake_pdf import render_markdown


class DocumentTests(unittest.TestCase):
    def test_checked_in_pdfs_match_their_sources_and_links_resolve(self):
        self.assertEqual(0, render_all(check=True), "run python generators/documents/build_documents.py")

    def test_every_source_is_a_northlake_pdf_with_a_title_and_owner(self):
        for source in source_files():
            reader = PdfReader(ROOT / pdf_for(source))
            self.assertTrue(reader.metadata.title, source)
            self.assertTrue(reader.metadata.author, source)
            self.assertIn("Northlake", reader.pages[0].extract_text(), source)

    def test_rendering_is_deterministic_and_prints_symbols_without_emoji(self):
        text = "# Status\n\n| Area | State |\n| --- | --- |\n| Rates | \N{LARGE GREEN CIRCLE} covered \N{RIGHTWARDS ARROW} CO\N{SUBSCRIPT TWO} |\n"
        first, second = io.BytesIO(), io.BytesIO()
        render_markdown(text, first, defaults=defaults_for("documents/guides/status.pdf"))
        render_markdown(text, second, defaults=defaults_for("documents/guides/status.pdf"))
        self.assertEqual(first.getvalue(), second.getvalue())
        with self.assertRaisesRegex(ValueError, "No Northlake print font"):
            render_markdown("# Title\n\nUnsupported \N{PILE OF POO}\n", io.BytesIO())


if __name__ == "__main__":
    unittest.main()
