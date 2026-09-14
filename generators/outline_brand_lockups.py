"""Outline the Northlake University lockups into font-independent SVG files.

The wordmark SVGs in ``output/branding/images/custom`` originally used live
``<text>`` elements, which only render correctly where Open Sans is installed
or can be fetched. Browsers never load fonts for an SVG referenced through an
``<img>`` tag, a favicon or an email client, so this script converts the two
text lines into glyph outlines using the self-hosted Open Sans faces in
``identity/branding/fonts``. The result renders identically everywhere.

Run from the repository root::

    python generators/outline_brand_lockups.py

The geometry follows ``output/branding/Brand Assets.dc.html``: the mark on the
left, "Northlake" in Open Sans ExtraBold with a slight negative tracking, and
"UNIVERSITY" in Open Sans Semibold with wide tracking beneath it.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "identity" / "branding" / "fonts"
OUTPUTS = (
    ROOT / "output" / "branding" / "images" / "custom",
    ROOT / "identity" / "branding",
)

NAVY = "#1F3A5F"
GOLD = "#C9A227"
SLATE = "#5B6573"
WHITE = "#FFFFFF"

STAR = "M32 9 L35 18 L43.5 21 L35 24 L32 33 L29 24 L20.5 21 L29 18 Z"
LAKE = "M15 43 Q32 35.8 49 43 Q32 50.8 15 43 Z"
WATERLINE = "M20.5 43 H43.5"

TEXT_X = 80.0
WORDMARK_SIZE = 30.0
WORDMARK_TRACKING = -0.3  # -0.01em at 30px, as in the brand sheet
CAPTION_SIZE = 12.0
CAPTION_TRACKING = 4.08  # 0.34em at 12px, as in the brand sheet
CAPTION_GAP = 19.0  # baseline-to-baseline distance between the two lines


def _cap_height(font: TTFont, size: float) -> float:
    upem = font["head"].unitsPerEm
    return font["OS/2"].sCapHeight / upem * size


def _kerning(font: TTFont) -> dict[tuple[str, str], int]:
    if "kern" not in font:
        return {}
    pairs: dict[tuple[str, str], int] = {}
    for table in font["kern"].kernTables:
        if getattr(table, "format", 0) == 0:
            pairs.update(table.kernTable)
    return pairs


def _line_to_path(
    font: TTFont, text: str, size: float, x: float, baseline: float, tracking: float
) -> tuple[str, float]:
    """Return one SVG path for ``text`` and the x position after it."""
    upem = font["head"].unitsPerEm
    scale = size / upem
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    kerning = _kerning(font)
    names = [cmap[ord(character)] for character in text]
    pen = SVGPathPen(glyph_set, ntos=lambda value: f"{value:.2f}".rstrip("0").rstrip("."))
    cursor = x
    for index, name in enumerate(names):
        transform = (scale, 0, 0, -scale, cursor, baseline)
        glyph_set[name].draw(TransformPen(pen, transform))
        cursor += glyph_set[name].width * scale
        if index + 1 < len(names):
            cursor += kerning.get((name, names[index + 1]), 0) * scale + tracking
    return pen.getCommands(), cursor


def _lockup(reversed_colours: bool) -> str:
    wordmark_font = TTFont(FONTS / "OpenSans-ExtraBold.woff2")
    caption_font = TTFont(FONTS / "OpenSans-Semibold.woff2")

    # Centre the visual text block (cap top of the wordmark to the caption
    # baseline) on the mark's vertical centre at y=32.
    wordmark_caps = _cap_height(wordmark_font, WORDMARK_SIZE)
    block_height = wordmark_caps + CAPTION_GAP
    wordmark_baseline = round(32 - block_height / 2 + wordmark_caps, 2)
    caption_baseline = round(wordmark_baseline + CAPTION_GAP, 2)

    wordmark_path, wordmark_end = _line_to_path(
        wordmark_font, "Northlake", WORDMARK_SIZE, TEXT_X, wordmark_baseline, WORDMARK_TRACKING
    )
    caption_path, caption_end = _line_to_path(
        caption_font, "UNIVERSITY", CAPTION_SIZE, TEXT_X + 1.5, caption_baseline, CAPTION_TRACKING
    )
    width = round(max(wordmark_end, caption_end) + 1, 0)

    if reversed_colours:
        roundel = ""
        lake_fill = WHITE
        wordmark_fill = WHITE
        caption_fill = GOLD
    else:
        roundel = f'  <circle cx="32" cy="32" r="31" fill="{NAVY}"/>\n'
        lake_fill = GOLD
        wordmark_fill = NAVY
        caption_fill = SLATE

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width:.0f} 64" width="{width:.0f}" height="64" '
        'role="img" aria-label="Northlake University">\n'
        "  <title>Northlake University</title>\n"
        f"{roundel}"
        f'  <path d="{STAR}" fill="{GOLD}"/>\n'
        f'  <path d="{LAKE}" fill="{lake_fill}"/>\n'
        f'  <path d="{WATERLINE}" stroke="{NAVY}" stroke-width="1.5" stroke-linecap="round" fill="none"/>\n'
        f'  <path d="{wordmark_path}" fill="{wordmark_fill}"/>\n'
        f'  <path d="{caption_path}" fill="{caption_fill}"/>\n'
        "</svg>\n"
    )


def main() -> None:
    files = {
        "northlake-logo.svg": _lockup(reversed_colours=False),
        "northlake-logo-reversed.svg": _lockup(reversed_colours=True),
    }
    for directory in OUTPUTS:
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (directory / name).write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {directory / name}")


if __name__ == "__main__":
    main()
