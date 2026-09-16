"""Render Markdown as a Northlake University PDF.

Northlake's documents are PDFs. This is the EEMSuite stakeholder renderer from
the eemsuite-pdf skill, re-branded for the fictional Northlake University: the
same Markdown subset and page geometry, with the Northlake palette
(identity/branding/brand.css), Open Sans, the north-star mark, a navy masthead
on the first page, a bookmark for every section and landscape pages for
sections that hold wide tables.

    python -m generators.documents.render_northlake_pdf input.md output.pdf
    python -m generators.documents.render_northlake_pdf input.md output.pdf --department "Facilities Operations"

Front matter (``---`` key: value lines) sets the title, subtitle, department,
document_type, date, prepared_by, audience and status. The same source and
metadata always produce identical bytes.
"""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# A fixed creation date and document id: re-rendering an unchanged source
# writes identical bytes, so Git only ever shows real document changes.
rl_config.invariant = 1

NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#C9A227")
SLATE = colors.HexColor("#5B6573")
INK = colors.HexColor("#2B3340")
LINE = colors.HexColor("#D6DDE7")
TINT = colors.HexColor("#EDF1F6")
GOLD_TINT = colors.HexColor("#FAF5E5")
CANVAS = colors.HexColor("#F5F6F8")
WHITE = colors.white
ON_NAVY = colors.Color(1, 1, 1, alpha=0.78)

PORTRAIT = LETTER
LANDSCAPE = landscape(LETTER)
SIDE_MARGIN = 61.2
TOP_MARGIN = 64.0
FIRST_TOP_MARGIN = 96.0
BOTTOM_MARGIN = 52.0
MASTHEAD_HEIGHT = 62.0
PORTRAIT_WIDTH = PORTRAIT[0] - 2 * SIDE_MARGIN
LANDSCAPE_WIDTH = LANDSCAPE[0] - 2 * SIDE_MARGIN
WIDE_TABLE_COLUMNS = 8
CELL_PAD_X = 5.0
CELL_PAD_Y = 4.0

FONT_DIR = Path(__file__).resolve().parent / "fonts"
REGULAR = "OpenSans"
SEMIBOLD = "OpenSans-Semibold"
BOLD = "OpenSans-Bold"
EXTRABOLD = "OpenSans-ExtraBold"
MONO = "NorthlakeMono"
SYMBOLS = "NorthlakeSymbols"
FONT_FILES = {
    REGULAR: "OpenSans-Regular.ttf",
    SEMIBOLD: "OpenSans-Semibold.ttf",
    BOLD: "OpenSans-Bold.ttf",
    EXTRABOLD: "OpenSans-ExtraBold.ttf",
    MONO: "DroidSansMono.ttf",
    SYMBOLS: "NotoSansSymbols-Subset.ttf",
}

# Status emoji have no place in print: they become coloured symbols.
STATUS_GLYPHS = {
    "\N{LARGE GREEN CIRCLE}": ("\N{BLACK CIRCLE}", "#286244"),
    "\N{LARGE YELLOW CIRCLE}": ("\N{BLACK CIRCLE}", "#C9A227"),
    "\N{LARGE RED CIRCLE}": ("\N{BLACK CIRCLE}", "#A52A32"),
    "\N{WHITE HEAVY CHECK MARK}": ("\N{CHECK MARK}", "#286244"),
    "\N{HEAVY CHECK MARK}": ("\N{CHECK MARK}", "#286244"),
    "\N{CROSS MARK}": ("\N{BALLOT X}", "#A52A32"),
    "\N{WARNING SIGN}": ("\N{WARNING SIGN}", "#806414"),
}
SUBSCRIPTS = {chr(0x2080 + digit): str(digit) for digit in range(10)}
INVISIBLE = {"\N{VARIATION SELECTOR-16}", "\N{ZERO WIDTH JOINER}"}
# Droid Sans Mono has no box drawing; code-block trees stay aligned in ASCII.
CODE_BOX_DRAWING = str.maketrans({
    "\N{BOX DRAWINGS LIGHT HORIZONTAL}": "-",
    "\N{BOX DRAWINGS LIGHT VERTICAL}": "|",
    "\N{BOX DRAWINGS LIGHT VERTICAL AND RIGHT}": "|",
    "\N{BOX DRAWINGS LIGHT VERTICAL AND LEFT}": "|",
    "\N{BOX DRAWINGS LIGHT UP AND RIGHT}": "`",
    "\N{BOX DRAWINGS LIGHT DOWN AND RIGHT}": "+",
    "\N{BOX DRAWINGS LIGHT DOWN AND LEFT}": "+",
    "\N{BOX DRAWINGS LIGHT UP AND LEFT}": "+",
    "\N{BOX DRAWINGS LIGHT DOWN AND HORIZONTAL}": "+",
    "\N{BOX DRAWINGS LIGHT UP AND HORIZONTAL}": "+",
    "\N{BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL}": "+",
})

LinkResolver = Callable[[str], "str | None"]


# --------------------------------------------------------------------------
# fonts and glyphs
# --------------------------------------------------------------------------

_glyphs: dict[str, frozenset[int]] = {}


def register_fonts() -> None:
    if _glyphs:
        return
    for name, file_name in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file_name)))
        _glyphs[name] = frozenset(pdfmetrics.getFont(name).face.charToGlyph)
    # The brand kit has no italic Open Sans: emphasis is set in Semibold.
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD, italic=SEMIBOLD, boldItalic=EXTRABOLD)
    pdfmetrics.registerFontFamily(SEMIBOLD, normal=SEMIBOLD, bold=EXTRABOLD, italic=SEMIBOLD, boldItalic=EXTRABOLD)
    pdfmetrics.registerFontFamily(BOLD, normal=BOLD, bold=EXTRABOLD, italic=BOLD, boldItalic=EXTRABOLD)
    for name in (EXTRABOLD, MONO, SYMBOLS):
        pdfmetrics.registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)


def glyph_markup(character: str, text_font: str, keep: Callable[[str], str]) -> str:
    """Return the character, or a placeholder for markup that sets it in another font."""
    if character in INVISIBLE:
        return ""
    if ord(character) < 128 or ord(character) in _glyphs[text_font]:
        return character
    if character in STATUS_GLYPHS:
        glyph, colour = STATUS_GLYPHS[character]
        return keep(f'<font name="{SYMBOLS}" color="{colour}">{glyph}</font>')
    if character in SUBSCRIPTS:
        return keep(f"<sub>{SUBSCRIPTS[character]}</sub>")
    if ord(character) in _glyphs[SYMBOLS]:
        return keep(f'<font name="{SYMBOLS}">{html.escape(character)}</font>')
    raise ValueError(f"No Northlake print font has U+{ord(character):04X} {character!r}")


# --------------------------------------------------------------------------
# inline markup
# --------------------------------------------------------------------------

TOKEN = re.compile("\x00(\\d+)\x00")


def inline_markup(value: str, resolve_link: LinkResolver | None = None, text_font: str = REGULAR,
                  anchors: frozenset[str] = frozenset()) -> str:
    """Convert inline Markdown to ReportLab paragraph markup.

    ``#heading`` links jump to a heading in this document; links to another PDF open
    it (a PDF remote go-to); other relative links become relative URIs.
    """
    tokens: list[str] = []

    def keep(markup: str) -> str:
        tokens.append(markup)
        return f"\x00{len(tokens) - 1}\x00"

    def code_span(match: re.Match[str]) -> str:
        code = "".join(glyph_markup(ch, MONO, keep) if ord(ch) >= 128 else html.escape(ch) for ch in match.group(1))
        return keep(f'<font name="{MONO}" size="-0.8" color="#1F3A5F">{code}</font>')

    def emphasis(value: str) -> str:
        value = "".join(glyph_markup(ch, text_font, keep) for ch in value)
        value = html.escape(value, quote=False)
        value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
        value = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"<b>\1</b>", value)
        value = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", value)
        value = re.sub(r"(?<![\w_])_(?!\s)([^_]+?)(?<!\s)_(?![\w_])", r"<i>\1</i>", value)
        return re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", value)

    def link(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2).strip()
        if re.match(r"^(https?|mailto):", target):
            href = target
        elif target.startswith("#"):
            href = target if target[1:] in anchors else None
        else:
            href = resolve_link(target) if resolve_link else None
            if href and href.partition("#")[0].lower().endswith(".pdf"):
                href = "pdf:" + href.partition("#")[0]
        inner = emphasis(label)
        if not href:
            return keep(inner)
        return keep(f'<link href="{html.escape(href, quote=True)}" color="#1F3A5F"><u>{inner}</u></link>')

    value = re.sub(r"`([^`]+)`", code_span, value)
    value = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, value)
    value = emphasis(value)
    while TOKEN.search(value):
        value = TOKEN.sub(lambda match: tokens[int(match.group(1))], value)
    return value


def plain_text(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return re.sub(r"[`*_~]", "", value)


def slug(text: str) -> str:
    """The anchor GitHub gives a heading: lower case, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", plain_text(text).strip().lower()).replace(" ", "-")


# --------------------------------------------------------------------------
# block parsing
# --------------------------------------------------------------------------


@dataclass
class Block:
    kind: str  # heading, paragraph, list, table, quote, code, rule, pagebreak
    text: str = ""
    level: int = 0
    rows: list[list[str]] = field(default_factory=list)
    align: list[str] = field(default_factory=list)
    items: list[ListEntry] = field(default_factory=list)
    ordered: bool = False
    start: int = 1
    lines: list[str] = field(default_factory=list)
    anchor: str = ""


@dataclass
class ListEntry:
    text: str
    children: Block | None = None


LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
RULE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")


def split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [cell.strip().replace("\\|", "|") for cell in cells]


def is_separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def starts_block(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    return (
        not stripped
        or stripped.startswith(("```", "~~~", ">", "<!--", "#"))
        or bool(RULE.match(stripped))
        or bool(LIST_MARKER.match(lines[index]))
        or (stripped.startswith("|") and index + 1 < len(lines) and is_separator(lines[index + 1]))
    )


def parse_list(lines: list[str], index: int) -> tuple[Block, int]:
    first = LIST_MARKER.match(lines[index])
    base_indent = len(first.group(1).expandtabs(4))
    ordered = first.group(2)[0].isdigit()
    block = Block("list", ordered=ordered, start=int(first.group(2)[:-1]) if ordered else 1)
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            following = next((i for i in range(index + 1, len(lines)) if lines[i].strip()), None)
            match = LIST_MARKER.match(lines[following]) if following is not None else None
            if match and len(match.group(1).expandtabs(4)) >= base_indent:
                index = following
                continue
            break
        match = LIST_MARKER.match(line)
        if match:
            indent = len(match.group(1).expandtabs(4))
            if indent < base_indent:
                break
            if indent > base_indent and block.items:
                child, index = parse_list(lines, index)
                block.items[-1].children = child
                continue
            if match.group(2)[0].isdigit() != ordered:
                break
            block.items.append(ListEntry(match.group(3).strip()))
            index += 1
            continue
        if block.items and (line.startswith(" ") or not starts_block(lines, index)):
            block.items[-1].text += " " + line.strip()
            index += 1
            continue
        break
    return block, index


def parse_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
        elif stripped == "<!-- pagebreak -->":
            blocks.append(Block("pagebreak"))
            index += 1
        elif stripped.startswith("<!--"):
            while index < len(lines) and "-->" not in lines[index]:
                index += 1
            index += 1
        elif stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith(fence):
                code.append(lines[index].rstrip())
                index += 1
            if index >= len(lines):
                raise ValueError("Code fence has no closing fence")
            blocks.append(Block("code", lines=code))
            index += 1
        elif heading := re.match(r"^(#{1,6})\s+(.+?)\s*#*$", stripped):
            blocks.append(Block("heading", text=heading.group(2), level=len(heading.group(1))))
            index += 1
        elif RULE.match(stripped):
            blocks.append(Block("rule"))
            index += 1
        elif stripped.startswith("|") and index + 1 < len(lines) and is_separator(lines[index + 1]):
            rows = [split_row(line)]
            align = []
            for cell in split_row(lines[index + 1]):
                align.append("center" if cell.startswith(":") and cell.endswith(":") else "right" if cell.endswith(":") else "left")
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_row(lines[index]))
                index += 1
            width = len(rows[0])
            rows = [(row + [""] * width)[:width] for row in rows]
            blocks.append(Block("table", rows=rows, align=(align + ["left"] * width)[:width]))
        elif stripped.startswith(">"):
            paragraphs: list[str] = [""]
            while index < len(lines) and lines[index].strip().startswith(">"):
                content = lines[index].strip()[1:].strip()
                if content:
                    paragraphs[-1] = (paragraphs[-1] + " " + content).strip()
                elif paragraphs[-1]:
                    paragraphs.append("")
                index += 1
            blocks.append(Block("quote", lines=[p for p in paragraphs if p]))
        elif LIST_MARKER.match(line):
            block, index = parse_list(lines, index)
            blocks.append(block)
        else:
            paragraph = [line]
            index += 1
            while index < len(lines) and not starts_block(lines, index):
                paragraph.append(lines[index])
                index += 1
            # Hard breaks: two trailing spaces, a trailing backslash, or a run of
            # "**Label:** value" field lines such as a letter's To/From/Date/Re.
            fields = len(paragraph) > 1 and all(re.match(r"^\*\*[^*]+:\*\*", part.strip()) for part in paragraph)
            text = ""
            for position, part in enumerate(paragraph):
                if position:
                    previous = paragraph[position - 1]
                    text += "\n" if fields or previous.endswith("  ") or previous.rstrip().endswith("\\") else " "
                text += part.strip().removesuffix("\\").rstrip()
            blocks.append(Block("paragraph", text=text))
    return blocks


# --------------------------------------------------------------------------
# styles and flowables
# --------------------------------------------------------------------------


def build_styles() -> dict[str, ParagraphStyle]:
    body = ParagraphStyle("NLBody", fontName=REGULAR, fontSize=9.5, leading=14, textColor=INK, spaceAfter=6)
    styles = {
        "title": ParagraphStyle("NLTitle", fontName=BOLD, fontSize=21, leading=25.5, textColor=NAVY, spaceAfter=3),
        "subtitle": ParagraphStyle("NLSubtitle", fontName=REGULAR, fontSize=11.5, leading=15.5, textColor=SLATE, spaceAfter=10),
        "h1": ParagraphStyle("NLH1", fontName=BOLD, fontSize=16, leading=20, textColor=NAVY, spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("NLH2", fontName=BOLD, fontSize=13, leading=16.5, textColor=NAVY, spaceBefore=16, spaceAfter=3),
        "h3": ParagraphStyle("NLH3", fontName=SEMIBOLD, fontSize=10.8, leading=14, textColor=NAVY, spaceBefore=11, spaceAfter=3),
        "h4": ParagraphStyle("NLH4", fontName=BOLD, fontSize=9.5, leading=12.5, textColor=INK, spaceBefore=8, spaceAfter=2),
        "body": body,
        "list": ParagraphStyle("NLList", parent=body, spaceAfter=0),
        "meta_label": ParagraphStyle("NLMetaLabel", fontName=SEMIBOLD, fontSize=7.4, leading=11.5, textColor=SLATE),
        "meta_value": ParagraphStyle("NLMetaValue", fontName=REGULAR, fontSize=8.8, leading=11.5, textColor=INK),
        "callout": ParagraphStyle("NLCallout", parent=body, fontSize=9.3, leading=13.6, spaceAfter=0),
        "code": ParagraphStyle("NLCode", fontName=MONO, fontSize=7.6, leading=10.2, textColor=INK),
    }
    for size in (8.2, 7.4, 7.0):
        for align_name, alignment in (("left", TA_LEFT), ("right", TA_RIGHT), ("center", TA_CENTER)):
            styles[f"th-{size}-{align_name}"] = ParagraphStyle(
                f"NLTableHead{size}{align_name}", fontName=SEMIBOLD, fontSize=size, leading=size * 1.3,
                textColor=WHITE, alignment=alignment, embeddedHyphenation=1)
            styles[f"td-{size}-{align_name}"] = ParagraphStyle(
                f"NLTableBody{size}{align_name}", fontName=REGULAR, fontSize=size, leading=size * 1.3,
                textColor=INK, alignment=alignment, embeddedHyphenation=1)
    return styles


class HeadingParagraph(Paragraph):
    """A heading: a link destination, and for levels 1 to 3 an entry in the PDF bookmarks."""

    def __init__(self, text: str, style: ParagraphStyle, anchor: str, outline_level: int | None) -> None:
        super().__init__(text, style)
        self.anchor = anchor
        self.outline_level = outline_level


def table_font_size(block: Block) -> float:
    columns = len(block.rows[0])
    return 7.0 if columns >= 12 else 7.4 if columns >= 10 else 8.2


def table_padding(block: Block) -> float:
    return 3.5 if len(block.rows[0]) >= 10 else CELL_PAD_X


def column_widths(block: Block, available: float) -> list[float]:
    size = table_font_size(block)
    count = len(block.rows[0])
    longest = [0.0] * count
    word = [0.0] * count
    # Like a browser's automatic table layout: every column is at least as wide
    # as its longest word (capped, so one long identifier cannot starve the
    # rest) and the remaining width goes to the columns that wrap the most.
    pad = 2 * table_padding(block) + 1
    cap = max(available / count * 1.5, 60.0)
    for row_index, row in enumerate(block.rows):
        font = SEMIBOLD if row_index == 0 else REGULAR
        for column, cell in enumerate(row):
            text = plain_text(cell)
            longest[column] = max(longest[column], stringWidth(text, font, size))
            for token in text.split():
                width = stringWidth(token, font, size)
                # Only a word too wide for its column breaks, and then after an
                # embedded hyphen (embeddedHyphenation); identifiers stay whole.
                if width > cap:
                    width = max(stringWidth(part, font, size) for part in re.split(r"(?<=-)", token))
                word[column] = max(word[column], width)
    minimum = [min(value, cap) + pad for value in word]
    natural = [value + pad for value in longest]
    if sum(natural) <= available:
        spare = available - sum(natural)
        return [value + spare * value / sum(natural) for value in natural]
    if sum(minimum) >= available:
        return [value * available / sum(minimum) for value in minimum]
    spare = available - sum(minimum)
    wants = [max(0.0, n - m) for n, m in zip(natural, minimum)]
    return [m + spare * w / sum(wants) for m, w in zip(minimum, wants)]


def is_wide(block: Block) -> bool:
    """A table goes on landscape pages when it has many columns or its rows would wrap deeply in portrait."""
    if block.kind != "table":
        return False
    if len(block.rows[0]) >= WIDE_TABLE_COLUMNS:
        return True
    if len(block.rows) < 4 or len(block.rows[0]) < 5:
        return False
    size = table_font_size(block)
    widths = column_widths(block, PORTRAIT_WIDTH)
    depth = 0.0
    for row in block.rows[1:]:
        depth += max(-(-(stringWidth(plain_text(cell), REGULAR, size) + 2) // max(1.0, width - 2 * CELL_PAD_X))
                     for cell, width in zip(row, widths))
    return depth / (len(block.rows) - 1) > 2.4


class Story:
    def __init__(self, styles: dict[str, ParagraphStyle], resolve_link: LinkResolver | None, anchors: frozenset[str]) -> None:
        self.styles = styles
        self.resolve_link = resolve_link
        self.anchors = anchors
        self.flowables: list = []
        self.width = PORTRAIT_WIDTH

    def markup(self, text: str, font: str = REGULAR) -> str:
        return inline_markup(text, self.resolve_link, font, self.anchors)

    def add(self, block: Block) -> None:
        getattr(self, f"add_{block.kind}")(block)

    def add_heading(self, block: Block) -> None:
        level = min(block.level, 4)
        style = self.styles[f"h{level}"]
        text = self.markup(block.text, style.fontName)
        # Start a new page rather than strand a heading at the foot of one. A
        # conditional break leaves no gap when a long table follows the heading.
        self.flowables.append(CondPageBreak({1: 150, 2: 130, 3: 96}.get(level, 72)))
        self.flowables.append(HeadingParagraph(text, style, block.anchor, max(0, level - 2) if level <= 3 else None))
        if level <= 2:
            self.flowables.append(HRFlowable(width=26, thickness=2, color=GOLD, hAlign="LEFT", spaceBefore=1, spaceAfter=7))

    def add_paragraph(self, block: Block) -> None:
        text = "<br/>".join(self.markup(part) for part in block.text.split("\n"))
        self.flowables.append(Paragraph(text, self.styles["body"]))

    def add_rule(self, block: Block) -> None:
        self.flowables.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=4, spaceAfter=10))

    def add_pagebreak(self, block: Block) -> None:
        self.flowables.append(PageBreak())

    def list_flowable(self, block: Block, depth: int) -> ListFlowable:
        items = []
        for entry in block.items:
            content = [Paragraph(self.markup(entry.text), self.styles["list"])]
            if entry.children is not None:
                content.append(self.list_flowable(entry.children, depth + 1))
            items.append(ListItem(content, leftIndent=14, spaceBefore=1.5))
        options = {
            "leftIndent": 14,
            "bulletFontName": BOLD if block.ordered else REGULAR,
            "bulletFontSize": 8.6 if block.ordered else 9,
            "bulletColor": NAVY if depth == 0 else SLATE,
            "spaceAfter": 6 if depth == 0 else 0,
        }
        if block.ordered:
            return ListFlowable(items, bulletType="1", start=str(block.start), bulletFormat="%s.", **options)
        return ListFlowable(items, bulletType="bullet", start="\N{BULLET}" if depth == 0 else "\N{EN DASH}", **options)

    def add_list(self, block: Block) -> None:
        self.flowables.append(self.list_flowable(block, 0))

    def add_table(self, block: Block) -> None:
        size = table_font_size(block)
        # A blank header row (a two-column key/value list) prints without the navy band.
        header = any(cell.strip() for cell in block.rows[0])
        rows = block.rows if header else block.rows[1:]
        cells = []
        for row_index, row in enumerate(rows):
            kind = "th" if header and row_index == 0 else "td"
            font = SEMIBOLD if kind == "th" else REGULAR
            cells.append([
                Paragraph(self.markup(value, font), self.styles[f"{kind}-{size}-{block.align[column]}"])
                for column, value in enumerate(row)
            ])
        table = Table(cells, colWidths=column_widths(block, self.width), repeatRows=1 if header else 0, splitByRow=1, hAlign="LEFT")
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY if header else WHITE),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
            ("LINEBEFORE", (1, 1 if header else 0), (-1, -1), 0.5, LINE),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), table_padding(block)),
            ("RIGHTPADDING", (0, 0), (-1, -1), table_padding(block)),
            ("TOPPADDING", (0, 0), (-1, -1), CELL_PAD_Y),
            ("BOTTOMPADDING", (0, 0), (-1, -1), CELL_PAD_Y + 1),
        ]
        commands.extend(("BACKGROUND", (0, row), (-1, row), TINT) for row in range(2 if header else 1, len(cells), 2))
        table.setStyle(TableStyle(commands))
        self.flowables.extend([table, Spacer(1, 10)])

    def add_quote(self, block: Block) -> None:
        following = ParagraphStyle("NLCalloutNext", parent=self.styles["callout"], spaceBefore=5)
        paragraphs = [Paragraph(self.markup(text), self.styles["callout"] if index == 0 else following)
                      for index, text in enumerate(block.lines)]
        table = Table([[paragraphs]], colWidths=[self.width], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GOLD_TINT),
            ("LINEBEFORE", (0, 0), (0, -1), 3, GOLD),
            ("LEFTPADDING", (0, 0), (-1, -1), 11),
            ("RIGHTPADDING", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        self.flowables.extend([table, Spacer(1, 10)])

    def add_code(self, block: Block) -> None:
        style = self.styles["code"]
        per_line = int((self.width - 20) / stringWidth("M", MONO, style.fontSize))
        lines: list[str] = []
        for raw in block.lines or [""]:
            text = raw.expandtabs(4).translate(CODE_BOX_DRAWING)
            while len(text) > per_line:
                lines.append(text[:per_line])
                text = "  " + text[per_line:]
            lines.append(text)
        rows = []
        for text in lines:
            tokens: list[str] = []

            def keep(markup: str) -> str:
                tokens.append(markup)
                return f"\x00{len(tokens) - 1}\x00"

            # Keep runs of spaces (no-break spaces) before glyph markup goes back in.
            body = html.escape("".join(glyph_markup(ch, MONO, keep) for ch in text), quote=False).replace(" ", "\N{NO-BREAK SPACE}")
            body = TOKEN.sub(lambda match: tokens[int(match.group(1))], body) or "\N{NO-BREAK SPACE}"
            rows.append([Paragraph(body, style)])
        table = Table(rows, colWidths=[self.width], hAlign="LEFT", splitByRow=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CANVAS),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        ]))
        if len(rows) > 40:
            self.flowables.extend([table, Spacer(1, 10)])
            return
        # A short block moves to the next page whole, taking a heading directly above it along.
        kept = [table, Spacer(1, 10)]
        while self.flowables and isinstance(self.flowables[-1], (HeadingParagraph, HRFlowable)):
            kept.insert(0, self.flowables.pop())
            if isinstance(kept[0], HeadingParagraph):
                break
        self.flowables.append(KeepTogether(kept))


# --------------------------------------------------------------------------
# page furniture
# --------------------------------------------------------------------------


def _cubic_from_quadratic(p0, q, p2):
    return (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]),
            p2[0] + 2 / 3 * (q[0] - p2[0]), p2[1] + 2 / 3 * (q[1] - p2[1]), p2[0], p2[1])


def draw_mark(canvas, x: float, y: float, size: float, reversed_colours: bool) -> None:
    """The Northlake north-star mark (identity/branding/northlake-mark*.svg) in a size x size box."""
    scale = size / 64.0

    def point(px: float, py: float) -> tuple[float, float]:
        return x + px * scale, y + (64 - py) * scale

    canvas.saveState()
    if not reversed_colours:
        canvas.setFillColor(NAVY)
        canvas.circle(*point(32, 32), 31 * scale, stroke=0, fill=1)
    star = canvas.beginPath()
    corners = [(32, 9), (35, 18), (43.5, 21), (35, 24), (32, 33), (29, 24), (20.5, 21), (29, 18)]
    star.moveTo(*point(*corners[0]))
    for corner in corners[1:]:
        star.lineTo(*point(*corner))
    star.close()
    canvas.setFillColor(GOLD)
    canvas.drawPath(star, stroke=0, fill=1)
    lake = canvas.beginPath()
    start, top, right, bottom = point(15, 43), point(32, 35.8), point(49, 43), point(32, 50.8)
    lake.moveTo(*start)
    lake.curveTo(*_cubic_from_quadratic(start, top, right))
    lake.curveTo(*_cubic_from_quadratic(right, bottom, start))
    lake.close()
    canvas.setFillColor(WHITE if reversed_colours else GOLD)
    canvas.drawPath(lake, stroke=0, fill=1)
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(1.5 * scale)
    canvas.setLineCap(1)
    canvas.line(*point(20.5, 43), *point(43.5, 43))
    canvas.restoreState()


def spaced_text(canvas, x: float, y: float, text: str, font: str, size: float, spacing: float, right: bool = False) -> None:
    # Character spacing is PDF text state and outlives the text object: restore it.
    width = stringWidth(text, font, size) + spacing * (len(text) - 1)
    canvas.saveState()
    text_object = canvas.beginText(x - width if right else x, y)
    text_object.setFont(font, size)
    text_object.setCharSpace(spacing)
    text_object.textOut(text)
    canvas.drawText(text_object)
    canvas.restoreState()


def fit_text(text: str, font: str, size: float, maximum: float) -> str:
    if stringWidth(text, font, size) <= maximum:
        return text
    while text and stringWidth(text + "...", font, size) > maximum:
        text = text[:-1]
    return text.rstrip() + "..."


@dataclass
class PageFurniture:
    metadata: dict[str, str]

    def footer(self, canvas, doc) -> None:
        width, _ = canvas._pagesize
        prepared_by = self.metadata["prepared_by"]
        date = self.metadata.get("date", "")
        left = f"{prepared_by}  \N{MIDDLE DOT}  {date}" if date else prepared_by
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(SIDE_MARGIN, 40, width - SIDE_MARGIN, 40)
        canvas.setFillColor(SLATE)
        canvas.setFont(REGULAR, 7.4)
        canvas.drawString(SIDE_MARGIN, 27, fit_text(left, REGULAR, 7.4, width - 2 * SIDE_MARGIN - 70))
        canvas.drawRightString(width - SIDE_MARGIN, 27, f"Page {doc.page}")

    def first_page(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.showOutline()
        width, height = canvas._pagesize
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - MASTHEAD_HEIGHT, width, MASTHEAD_HEIGHT, stroke=0, fill=1)
        canvas.setFillColor(GOLD)
        canvas.rect(0, height - MASTHEAD_HEIGHT - 3, width, 3, stroke=0, fill=1)
        middle = height - MASTHEAD_HEIGHT / 2
        draw_mark(canvas, SIDE_MARGIN - 4, middle - 19, 38, reversed_colours=True)
        canvas.setFillColor(WHITE)
        spaced_text(canvas, SIDE_MARGIN + 38, middle + 0.5, "Northlake", EXTRABOLD, 18, -0.18)
        canvas.setFillColor(GOLD)
        spaced_text(canvas, SIDE_MARGIN + 39, middle - 10.5, "UNIVERSITY", SEMIBOLD, 6.6, 2.25)
        department = self.metadata.get("department")
        if department:
            canvas.setFillColor(WHITE)
            spaced_text(canvas, width - SIDE_MARGIN, middle + 1, department.upper(), SEMIBOLD, 7.4, 1.1, right=True)
        document_type = self.metadata.get("document_type")
        if document_type:
            canvas.setFillColor(ON_NAVY)
            canvas.setFont(REGULAR, 7.6)
            canvas.drawRightString(width - SIDE_MARGIN, middle - 10.5, document_type)
        self.footer(canvas, doc)
        canvas.restoreState()

    def later_page(self, canvas, doc) -> None:
        canvas.saveState()
        width, height = canvas._pagesize
        baseline = height - 30
        draw_mark(canvas, SIDE_MARGIN, baseline - 4, 14, reversed_colours=False)
        canvas.setFillColor(NAVY)
        spaced_text(canvas, SIDE_MARGIN + 20, baseline, "NORTHLAKE UNIVERSITY", BOLD, 7.4, 1.05)
        canvas.setFillColor(SLATE)
        canvas.setFont(REGULAR, 7.6)
        label = self.metadata.get("document_label") or self.metadata["title"]
        canvas.drawRightString(width - SIDE_MARGIN, baseline, fit_text(label, REGULAR, 7.6, width / 2 - SIDE_MARGIN))
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1.5)
        canvas.line(SIDE_MARGIN, height - 40, width - SIDE_MARGIN, height - 40)
        self.footer(canvas, doc)
        canvas.restoreState()


class NorthlakeDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs) -> None:
        super().__init__(filename, **kwargs)
        self._outline_level = -1

    def afterFlowable(self, flowable) -> None:  # noqa: N802 - ReportLab hook
        if not isinstance(flowable, HeadingParagraph):
            return
        self.canv.bookmarkPage(flowable.anchor)
        if flowable.outline_level is None:
            return
        level = min(flowable.outline_level, self._outline_level + 1)
        self._outline_level = level
        self.canv.addOutlineEntry(flowable.getPlainText(), flowable.anchor, level=level, closed=level > 0)


# --------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------


def parse_front_matter(text: str) -> tuple[dict[str, str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as error:
        raise ValueError("Front matter starts with --- but has no closing ---") from error
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Invalid front-matter line: {line}")
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")
    return metadata, lines[end + 1 :]


def title_block(metadata: dict[str, str], styles: dict[str, ParagraphStyle]) -> list:
    story: list = [Paragraph(inline_markup(metadata["title"], None, BOLD), styles["title"])]
    if metadata.get("subtitle"):
        story.append(Paragraph(inline_markup(metadata["subtitle"]), styles["subtitle"]))
    fields = [("Date", "date"), ("Prepared by", "prepared_by"), ("Audience", "audience"), ("Status", "status"),
              ("From", "from"), ("To", "to"), ("Re", "re")]
    rows = [[Paragraph(label.upper(), styles["meta_label"]), Paragraph(inline_markup(metadata[key]), styles["meta_value"])]
            for label, key in fields if metadata.get(key)]
    if rows:
        table = Table(rows, colWidths=[78, PORTRAIT_WIDTH - 78], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story.extend([Spacer(1, 4), table])
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=10, spaceAfter=12))
    return story


def render_markdown(
    text: str,
    output: Path | BinaryIO,
    metadata: dict[str, str] | None = None,
    defaults: dict[str, str] | None = None,
    resolve_link: LinkResolver | None = None,
) -> dict[str, int]:
    """Render Markdown to a PDF file or binary stream and return page, section and table counts.

    Metadata precedence: ``defaults`` < the source's front matter < ``metadata``.
    """
    register_fonts()
    front, lines = parse_front_matter(text)
    meta = {**(defaults or {}), **front, **{key: value for key, value in (metadata or {}).items() if value}}
    blocks = parse_blocks(lines)
    first_heading = next((block for block in blocks if block.kind == "heading" and block.level == 1), None)
    if "title" not in meta:
        if first_heading is None:
            raise ValueError("A document needs a title: front matter or a level-1 heading")
        meta["title"] = plain_text(first_heading.text).strip()
    if first_heading is not None and plain_text(first_heading.text).strip() == meta["title"]:
        blocks.remove(first_heading)
    meta.setdefault("prepared_by", "Northlake University")

    # Each heading is a link destination named like GitHub's anchor, made unique.
    anchors: set[str] = set()
    for block in blocks:
        if block.kind == "heading":
            base = slug(block.text) or "section"
            anchor, number = base, 1
            while anchor in anchors:
                anchor, number = f"{base}-{number}", number + 1
            block.anchor = anchor
            anchors.add(anchor)

    styles = build_styles()
    story = Story(styles, resolve_link, frozenset(anchors))
    story.flowables.extend(title_block(meta, styles))

    # Sections start at level-1 and level-2 headings. A section holding a wide
    # table is set on landscape pages; orientation changes on a new page.
    sections: list[list[Block]] = [[]]
    for block in blocks:
        if block.kind == "heading" and block.level <= 2 and sections[-1]:
            sections.append([])
        sections[-1].append(block)
    orientation = "portrait"

    def turn(wanted: str) -> None:
        nonlocal orientation
        if wanted != orientation:
            story.flowables.extend([NextPageTemplate(wanted), PageBreak()])
            orientation = wanted
            story.width = LANDSCAPE_WIDTH if wanted == "landscape" else PORTRAIT_WIDTH

    for number, section in enumerate(sections):
        wide = [is_wide(block) for block in section]
        if not any(wide):
            turn("portrait")
        elif number == 0:
            # The introduction under the title stays on the first page.
            lead = wide.index(True)
            for block in section[:lead]:
                story.add(block)
            section = section[lead:]
            turn("landscape")
        else:
            turn("landscape")
        for block in section:
            story.add(block)

    if isinstance(output, Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        target = str(output)
    else:
        target = output
    furniture = PageFurniture(meta)
    document = NorthlakeDocTemplate(
        target,
        pagesize=PORTRAIT,
        title=meta["title"],
        author=meta["prepared_by"],
        subject=meta.get("subtitle") or meta.get("department") or meta["title"],
        creator="Northlake University",
    )

    def frame(page: tuple[float, float], top: float, name: str) -> Frame:
        return Frame(SIDE_MARGIN, BOTTOM_MARGIN, page[0] - 2 * SIDE_MARGIN, page[1] - top - BOTTOM_MARGIN,
                     leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id=name)

    document.addPageTemplates([
        PageTemplate(id="first", frames=[frame(PORTRAIT, FIRST_TOP_MARGIN, "first")], onPage=furniture.first_page,
                     pagesize=PORTRAIT, autoNextPageTemplate="portrait"),
        PageTemplate(id="portrait", frames=[frame(PORTRAIT, TOP_MARGIN, "portrait")], onPage=furniture.later_page,
                     pagesize=PORTRAIT),
        PageTemplate(id="landscape", frames=[frame(LANDSCAPE, TOP_MARGIN, "landscape")], onPage=furniture.later_page,
                     pagesize=LANDSCAPE),
    ])
    document.build(story.flowables)
    return {
        "pages": document.page,
        "sections": sum(1 for block in blocks if block.kind == "heading" and block.level == 2),
        "tables": sum(1 for block in blocks if block.kind == "table"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Markdown as a Northlake University PDF.")
    parser.add_argument("input", type=Path, help="Markdown source file")
    parser.add_argument("output", type=Path, help="Destination PDF file")
    options = ("title", "subtitle", "document_label", "document_type", "department", "date", "prepared_by", "audience", "status")
    for option in options:
        parser.add_argument("--" + option.replace("_", "-"))
    args = parser.parse_args()
    counts = render_markdown(args.input.read_text(encoding="utf-8"), args.output.resolve(),
                             {option: getattr(args, option) for option in options})
    print(f"[OK] Rendered {args.output.resolve()}")
    print(f"Pages: {counts['pages']} | Sections: {counts['sections']} | Tables: {counts['tables']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
