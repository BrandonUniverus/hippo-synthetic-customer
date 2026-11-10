"""Build every brand's logo files with the lettering outlined.

Browsers never load web fonts for an SVG shown through <img>, a favicon or an
email, so each lockup's words are drawn as glyph outlines from the fonts that
sit beside the brand (brands/<id>/fonts). The result looks the same anywhere.

For every brand it writes logo.svg (for white or light surfaces),
logo-reversed.svg (for the brand's dark surfaces) and mark.svg (the symbol
alone, for favicons and app tiles).

Run from the repository root:

    python brands/tools/build_logos.py

Needs fonttools and brotli: python -m pip install fonttools brotli
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

BRANDS = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Run:
    """One line of lettering in a lockup."""

    text: str
    brand: str      # folder that holds the font
    font: str       # file name under brands/<brand>/fonts
    size: float
    x: float
    baseline: float
    tracking: float
    fill: str
    axes: tuple[tuple[str, float], ...] = ()


@lru_cache(maxsize=None)
def _font(brand: str, file: str, axes: tuple[tuple[str, float], ...]) -> TTFont:
    font = TTFont(BRANDS / brand / "fonts" / file)
    if axes and "fvar" in font:
        font = instantiateVariableFont(font, dict(axes))
    return font


def _kerning(font: TTFont) -> dict[tuple[str, str], int]:
    pairs: dict[tuple[str, str], int] = {}
    if "kern" in font:
        for table in font["kern"].kernTables:
            if getattr(table, "format", 0) == 0:
                pairs.update(table.kernTable)
    return pairs


def _outline(run: Run) -> tuple[str, float]:
    """Return the SVG path data for a run and the x position after it."""
    font = _font(run.brand, run.font, run.axes)
    scale = run.size / font["head"].unitsPerEm
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    kerning = _kerning(font)
    names = [cmap[ord(character)] for character in run.text]
    pen = SVGPathPen(glyphs, ntos=lambda value: f"{value:.2f}".rstrip("0").rstrip("."))
    cursor = run.x
    for index, name in enumerate(names):
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, run.baseline)))
        cursor += glyphs[name].width * scale
        if index + 1 < len(names):
            cursor += kerning.get((name, names[index + 1]), 0) * scale + run.tracking
    return pen.getCommands(), cursor


def _svg(label: str, height: int, symbol: str, runs: list[Run], extra: str = "", min_width: float = 0) -> str:
    paths, end = [], min_width
    for run in runs:
        data, run_end = _outline(run)
        paths.append(f'  <path d="{data}" fill="{run.fill}"/>\n')
        end = max(end, run_end)
    width = round(end + 2)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{label}">\n  <title>{label}</title>\n{symbol}{extra}{"".join(paths)}</svg>\n'
    )


def _mark_svg(label: str, view: int, symbol: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view} {view}" width="{view}" height="{view}" '
            f'role="img" aria-label="{label}">\n  <title>{label}</title>\n{symbol}</svg>\n')


# Northlake University -------------------------------------------------------------
NAVY, GOLD, SLATE, PAPER_INK, WHITE = "#14263F", "#C8A24A", "#59606B", "#E9E2CF", "#FFFFFF"
STAR = "M32 9 L35 18 L43.5 21 L35 24 L32 33 L29 24 L20.5 21 L29 18 Z"
LAKE = "M15 43 Q32 35.8 49 43 Q32 50.8 15 43 Z"


def _northlake_mark(reversed_: bool, waterline: str = NAVY) -> str:
    if reversed_:
        return (f'  <path d="{STAR}" fill="{GOLD}"/>\n  <path d="{LAKE}" fill="{WHITE}"/>\n'
                f'  <path d="M20.5 43 H43.5" stroke="{waterline}" stroke-width="1.5" stroke-linecap="round" fill="none"/>\n')
    return (f'  <circle cx="32" cy="32" r="31" fill="{NAVY}"/>\n  <path d="{STAR}" fill="{GOLD}"/>\n'
            f'  <path d="{LAKE}" fill="{GOLD}"/>\n'
            f'  <path d="M20.5 43 H43.5" stroke="{NAVY}" stroke-width="1.5" stroke-linecap="round" fill="none"/>\n')


def northlake(reversed_: bool) -> str:
    word, caption = (WHITE, GOLD) if reversed_ else (NAVY, SLATE)
    plex = (("wght", 500.0),)
    return _svg("Northlake University", 64, _northlake_mark(reversed_), [
        Run("Northlake", "northlake", "Spectral-SemiBold.woff2", 35, 76, 37, -0.3, word),
        Run("UNIVERSITY", "northlake", "IBMPlexSans-Variable.woff2", 10.5, 78, 55, 4.4, caption, plex),
    ])


def thermal(reversed_: bool) -> str:
    word, unit, rule = (WHITE, PAPER_INK, "#8C9AA1") if reversed_ else (NAVY, "#2F3E46", "#C9CFD2")
    runs = [
        Run("Northlake University", "northlake", "Spectral-SemiBold.woff2", 21, 76, 30, 0, word),
        Run("Central Plant Operations", "northlake", "IBMPlexSans-Variable.woff2", 13, 77, 55, 0.1, unit, (("wght", 500.0),)),
    ]
    end = max(_outline(run)[1] for run in runs)
    hairline = f'  <rect x="77" y="38" width="{end - 77:.1f}" height="1" fill="{rule}"/>\n'
    return _svg("Northlake University, Central Plant Operations", 64, _northlake_mark(reversed_, "#2F3E46" if reversed_ else NAVY), runs, hairline)


# Valley Electric District ------------------------------------------------------------
def _valley_symbol(reversed_: bool, y: float = 4) -> str:
    tile, bolt = ("#FFFFFF", "#1D5FAF") if reversed_ else ("#1D5FAF", "#FFFFFF")
    return (f'  <rect x="0" y="{y}" width="40" height="40" fill="{tile}"/>\n'
            f'  <rect x="0" y="{y + 32}" width="40" height="8" fill="#5E9E2F"/>\n'
            f'  <path d="M24 {y + 3} L12 {y + 22} H19.5 L16 {y + 37} L29 {y + 17} H21.5 Z" fill="{bolt}"/>\n')


def valley(reversed_: bool) -> str:
    word, sub = ("#FFFFFF", "#CFE3F7") if reversed_ else ("#13202E", "#1D5FAF")
    return _svg("Valley Electric District", 48, _valley_symbol(reversed_), [
        Run("Valley Electric", "valley-electric", "PublicSans-Variable.woff2", 21, 52, 26, -0.4, word, (("wght", 800.0),)),
        Run("DISTRICT", "valley-electric", "PublicSans-Variable.woff2", 10.5, 53, 42, 3, sub, (("wght", 600.0),)),
    ])


# River City Utilities ----------------------------------------------------------------
def _river_symbol(reversed_: bool, y: float = 4) -> str:
    tile, wave = ("#FFFFFF", "#0E6F7A") if reversed_ else ("#0E6F7A", "#FFFFFF")
    waves = "".join(f'  <path d="M6 {y + offset} q3.5 -4 7 0 t7 0 t7 0 t7 0" stroke="{wave}" stroke-width="3" fill="none"/>\n'
                    for offset in (12, 21, 30))
    return f'  <rect x="0" y="{y}" width="40" height="40" fill="{tile}"/>\n{waves}'


def river(reversed_: bool) -> str:
    word, sub = ("#FFFFFF", "#BDE7EC") if reversed_ else ("#0A555E", "#0E6F7A")
    return _svg("River City Utilities", 48, _river_symbol(reversed_), [
        Run("RIVER CITY", "river-city", "BarlowSemiCondensed-Bold.woff2", 23, 52, 25, 0.6, word),
        Run("UTILITIES", "river-city", "Barlow-Medium.woff2", 11.5, 53, 41, 3.6, sub),
    ])


# Sierra Gas Utility ------------------------------------------------------------------
def _sierra_symbol(base: str) -> str:
    return ('  <path d="M20 3 C26 11 32 16 32 26 A12 12 0 0 1 8 26 C8 19 12 15 15 9 C16 15 18 18 20 19 C22 14 22 9 20 3 Z" fill="#B5441B"/>\n'
            '  <path d="M20 21 C24 25 26.5 28 26.5 31.5 A6.5 6.5 0 0 1 13.5 31.5 C13.5 28 16.5 25 20 21 Z" fill="#F08A3E"/>\n'
            f'  <rect x="6" y="42" width="28" height="3" fill="{base}"/>\n')


def sierra(reversed_: bool) -> str:
    word, sub, base = ("#FFFFFF", "#F08A3E", "#FFFFFF") if reversed_ else ("#2B2F33", "#B5441B", "#2B2F33")
    return _svg("Sierra Gas Utility", 48, _sierra_symbol(base), [
        Run("Sierra Gas", "sierra-gas", "LibreFranklin-Variable.woff2", 23, 44, 27, -0.4, word, (("wght", 800.0),)),
        Run("UTILITY", "sierra-gas", "LibreFranklin-Variable.woff2", 10, 45, 43, 3, sub, (("wght", 600.0),)),
    ])


# Helios Onsite Solar -----------------------------------------------------------------
def _helios_symbol(bar: str) -> str:
    return ('  <path d="M6 30 A14 14 0 0 1 34 30 Z" fill="#FFB21A"/>\n'
            f'  <rect x="4" y="33" width="32" height="3" fill="{bar}"/>\n  <rect x="9" y="39" width="22" height="3" fill="{bar}"/>\n')


def helios(reversed_: bool) -> str:
    bar, word, sub = ("#FFFFFF", "#FFFFFF", "#FFE3A6") if reversed_ else ("#16181D", "#16181D", "#5D6470")
    return _svg("Helios Onsite Solar", 48, _helios_symbol(bar), [
        Run("helios", "helios", "Manrope-Variable.woff2", 28, 45, 30, -1.1, word, (("wght", 800.0),)),
        Run("onsite solar", "helios", "Manrope-Variable.woff2", 10.5, 46, 44, 0.3, sub, (("wght", 600.0),)),
    ])


# Ridgeline Wind ----------------------------------------------------------------------
def _ridgeline_symbol(turbine: str) -> str:
    return ('  <path d="M1 46 L11 39 L18 42 L28 33 L39 40" stroke="#7CC4E4" stroke-width="2.5" fill="none"/>\n'
            f'  <path d="M20 16 L20 42" stroke="{turbine}" stroke-width="2.4"/>\n'
            f'  <path d="M20 14 L20 1.5 M20 14 L30.8 20.2 M20 14 L9.2 20.2" stroke="{turbine}" stroke-width="2.4"/>\n'
            f'  <circle cx="20" cy="14" r="2.8" fill="{turbine}"/>\n')


def ridgeline(reversed_: bool) -> str:
    turbine, word, sub = ("#FFFFFF", "#FFFFFF", "#CFE4DA") if reversed_ else ("#1F5E4B", "#164637", "#1F5E4B")
    return _svg("Ridgeline Wind", 50, _ridgeline_symbol(turbine), [
        Run("RIDGELINE", "ridgeline-wind", "Archivo-Variable.woff2", 20, 50, 27, 1, word, (("wdth", 125.0), ("wght", 800.0))),
        Run("WIND", "ridgeline-wind", "Archivo-Variable.woff2", 11, 51, 43, 4.2, sub, (("wdth", 125.0), ("wght", 500.0))),
    ])


LOCKUPS = {
    "northlake": (northlake, _mark_svg("Northlake University", 64, _northlake_mark(False))),
    "thermal-plant": (thermal, _mark_svg("Northlake University", 64, _northlake_mark(False))),
    "valley-electric": (valley, _mark_svg("Valley Electric District", 40, _valley_symbol(False, 0))),
    "river-city": (river, _mark_svg("River City Utilities", 40, _river_symbol(False, 0))),
    "sierra-gas": (sierra, _mark_svg("Sierra Gas Utility", 48, _sierra_symbol("#2B2F33"))),
    "helios": (helios, _mark_svg("Helios Onsite Solar", 44, _helios_symbol("#16181D"))),
    "ridgeline-wind": (ridgeline, _mark_svg("Ridgeline Wind", 48, _ridgeline_symbol("#1F5E4B"))),
}


def main() -> None:
    for brand, (lockup, mark) in LOCKUPS.items():
        folder = BRANDS / brand
        for name, content in (("logo.svg", lockup(False)), ("logo-reversed.svg", lockup(True)), ("mark.svg", mark)):
            (folder / name).write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {(folder / name).relative_to(BRANDS.parent).as_posix()}")


if __name__ == "__main__":
    main()
