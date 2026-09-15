"""Render every document source to its PDF.

Each Markdown file under generators/documents/sources renders to the same path
from the repository root: sources/documents/guides/x.md becomes
documents/guides/x.pdf and sources/implementation/y.md becomes
implementation/y.pdf. README.md files describe their folder and are not
rendered. Links in a source are written relative to its PDF.

    python generators/documents/build_documents.py           render every source
    python generators/documents/build_documents.py --check   exit 1 when a PDF is missing or stale

Rendering is deterministic, so an unchanged source rewrites nothing.
"""

from __future__ import annotations

import argparse
import io
import posixpath
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from generators.documents.render_northlake_pdf import render_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "generators" / "documents" / "sources"
ONBOARDING = ROOT / "data" / "scenarios" / "northlake-onboarding-v1.yaml"

# Masthead and footer defaults by folder, most specific last; front matter overrides them.
FOLDER_DEFAULTS = {
    "documents": {"prepared_by": "Northlake University"},
    "documents/intake-package": {"document_type": "Implementation intake package"},
    "documents/guides": {"document_type": "Operating guide"},
    "documents/rate-tariffs": {"department": "Finance and Accounts Payable", "document_type": "Rate tariff sheet"},
    "documents/brand": {"department": "IT and Communications", "document_type": "EEM portal brand kit"},
    "implementation": {"department": "Energy Hippo implementation", "prepared_by": "Energy Hippo implementation team"},
    "implementation/dream-customer": {"document_type": "Dream customer plan"},
    "implementation/briefs": {"document_type": "Design brief"},
}


@lru_cache
def issue_date(root: Path = ROOT) -> str:
    """Northlake's documents carry the onboarding packet's issue date."""
    onboarding = yaml.safe_load((root / ONBOARDING.relative_to(ROOT)).read_text(encoding="utf-8"))
    issued = date.fromisoformat(str(onboarding["issuedOn"]))
    return f"{issued:%B} {issued.day}, {issued.year}"


def defaults_for(pdf: str, root: Path = ROOT) -> dict[str, str]:
    """Masthead defaults for a PDF path relative to the repository root."""
    values = {"date": issue_date(root)} if pdf.startswith("documents/") else {}
    for folder in sorted(FOLDER_DEFAULTS, key=len):
        if pdf.startswith(folder + "/"):
            values.update(FOLDER_DEFAULTS[folder])
    return values


def source_files() -> list[Path]:
    return sorted(path for path in SOURCES.rglob("*.md") if path.name != "README.md")


def pdf_for(source: Path) -> str:
    return source.relative_to(SOURCES).with_suffix(".pdf").as_posix()


def link_checker(pdf: str, generated: set[str], broken: list[str]):
    """Keep a link when its target is a rendered document, a generated PDF or a file in the repository."""
    folder = posixpath.dirname(pdf)

    def resolve(href: str) -> str | None:
        path = href.partition("#")[0]
        if not path:
            return href
        target = posixpath.normpath(posixpath.join(folder, path))
        exists = (
            (ROOT / target).exists()
            or target in generated
            or (target.endswith(".pdf") and (SOURCES / target).with_suffix(".md").is_file())
        )
        if exists:
            return href
        broken.append(f"{pdf}: {href}")
        return None

    return resolve


def render_all(check: bool) -> int:
    from generators.northlake_packet import GENERATED_DOCUMENTS

    generated = set(GENERATED_DOCUMENTS)
    broken: list[str] = []
    stale: list[str] = []
    for source in source_files():
        pdf = pdf_for(source)
        buffer = io.BytesIO()
        render_markdown(source.read_text(encoding="utf-8"), buffer, defaults=defaults_for(pdf),
                        resolve_link=link_checker(pdf, generated, broken))
        target = ROOT / pdf
        if target.is_file() and target.read_bytes() == buffer.getvalue():
            continue
        stale.append(pdf)
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(buffer.getvalue())
    for link in broken:
        print(f"broken link  {link}")
    verb = "stale" if check else "rendered"
    for pdf in stale:
        print(f"{verb}  {pdf}")
    print(f"{len(source_files())} documents, {len(stale)} {verb}, {len(broken)} broken links")
    return 1 if broken or (check and stale) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Exit with status 1 when a PDF is missing or stale")
    return render_all(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
