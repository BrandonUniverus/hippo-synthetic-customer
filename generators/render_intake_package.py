"""Render the Northlake intake package binder from the customer document sources.

The binder packages every document listed in the intake package design brief
(generators/documents/sources/implementation/briefs/intake-package-design-brief.md)
into one self-contained HTML page: a cover, a table of contents and one section per
document. It formats and never rewrites: each section is rendered from the current
Markdown source, the register and source-system inventory come straight from the
packet, and the packet version and issue date come from
data/scenarios/northlake-onboarding-v1.yaml. Regenerate after any source change;
--check exits with status 1 when the binder is stale. Print the page from a browser
for the paper binder.
"""

import argparse
import base64
import html
import re
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generators.northlake_packet import build_packet, register_markdown, source_inventory_markdown  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SOURCES = Path("generators/documents/sources/documents")
ONBOARDING = Path("data/scenarios/northlake-onboarding-v1.yaml")
TARGET = Path("documents/intake-package/Northlake Intake Package.html")
FONTS = Path(__file__).resolve().parent / "fonts"
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.S)

# Binder source name -> where its Markdown lives under SOURCES; the register and
# source-system inventory have no Markdown source and are built from the packet.
SOURCE_FOLDERS = {
    "northlake-facilities-and-utility-overview.md": "guides",
    "chart-of-accounts-and-gl-guide.md": "guides",
    "sustainability-requirements.md": "guides",
    "tenant-and-lease-roster.md": "guides",
}
GENERATED_SOURCES = {"facilities-and-meter-register.md": register_markdown, "source-system-inventory.md": source_inventory_markdown}

# Source stem -> (palette, band colour, band ink, icon). Order is the binder order.
TARIFF_SHEETS = {
    "valley-electric-district": ("ved", "#1C5FB0", "#FFFFFF", "bolt"),
    "sierra-gas-utility": ("sgu", "#C9551F", "#FFFFFF", "flame"),
    "river-city-utilities": ("rcu", "#0E7C86", "#FFFFFF", "drop"),
    "northlake-thermal-plant": ("ntp", "#37474F", "#FFFFFF", "thermal"),
    "helios-onsite-solar": ("hos", "#F5A524", "#2B2742", "sun"),
}

# Owner teams follow the cover letter's "What's enclosed" table.
SECTIONS = [
    {"key": "transmittal", "owner": "Campus Operations", "layout": "letter", "sources": ["00-cover-letter.md"]},
    {"key": "questionnaire", "owner": "Campus Operations", "layout": "questionnaire", "sources": ["01-discovery-questionnaire.md"]},
    {"key": "overview", "owner": "Facilities", "layout": "document", "sources": ["northlake-facilities-and-utility-overview.md"]},
    {"key": "register", "owner": "Facilities / Finance", "layout": "document", "wide": True, "sources": ["facilities-and-meter-register.md"]},
    {"key": "tariffs", "owner": "Finance", "layout": "tariffs", "title": "Rate Tariff Sheets", "sources": [f"rate-tariff-sheets/{stem}.md" for stem in TARIFF_SHEETS]},
    {"key": "gl-guide", "owner": "Finance / AP", "layout": "document", "sources": ["chart-of-accounts-and-gl-guide.md"]},
    {"key": "user-access", "owner": "HR / IT", "layout": "document", "sources": ["user-access-request.md"]},
    {"key": "tenants", "owner": "Housing / Property Mgmt", "layout": "document", "sources": ["tenant-and-lease-roster.md"]},
    {"key": "sustainability", "owner": "Sustainability Office", "layout": "document", "sources": ["sustainability-requirements.md"]},
    {"key": "sources", "owner": "IT / Facilities", "layout": "document", "wide": True, "sources": ["source-system-inventory.md"]},
    {"key": "workbook", "owner": "Facilities / Finance", "layout": "workbook", "sources": ["data-collection-workbook-additions.md"]},
]

FONT_FACES = [
    ("Spectral", "normal", "600", "Spectral-SemiBold-latin.woff2"),
    ("IBM Plex Sans", "normal", "100 700", "IBMPlexSans-Variable-latin.woff2"),
    ("IBM Plex Sans", "italic", "400", "IBMPlexSans-Italic-latin.woff2"),
    ("IBM Plex Mono", "normal", "500", "IBMPlexMono-Medium-latin.woff2"),
    ("IBM Plex Mono", "normal", "600", "IBMPlexMono-SemiBold-latin.woff2"),
]

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RULE = re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
LIST_ITEM = re.compile(r"^ {0,3}(?P<marker>[-*+]|\d{1,9}[.)])\s+(?P<text>.*)$")
TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
EMPHASIS = re.compile(r"(?<![*\w])\*(?=\S)([^*]+?)(?<=\S)\*(?![*\w])")
NUMBER = re.compile(r"^[-\u2212]?\$?\d[\d,]*(?:\.\d+)?%?$")
MEMO_LINE = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s+(?P<value>.+)$")
QUESTION = re.compile(r"^\*\*(?P<number>\d+(?:\.\d+)+)\s+(?P<question>.+?)\*\*\s*(?P<answer>.*)$", re.S)
NUMBERED_HEADING = re.compile(r"^(?P<number>\d+)\.\s+(?P<text>.+)$")
BOLD_ONLY = re.compile(r"^\*\*(?P<text>[^*]+)\*\*$")
SHEET_TITLE = re.compile(r"^(?P<kind>.+?) \u2014 (?P<provider>.+?) \((?P<scope>.+)\)$")
SCHEDULE_CODE = re.compile(r"\((?P<code>[A-Z0-9][A-Z0-9-]+)\)\s*$")
HARD_BREAK = "\u2028"

MARK = ('<path d="M32 11 L35.5 20.5 L45 24 L35.5 27.5 L32 37 L28.5 27.5 L19 24 L28.5 20.5 Z" fill="#C8A24A"/>'
        '<rect x="14" y="41.5" width="36" height="2.6" fill="#C8A24A"/>'
        '<rect x="19" y="46.5" width="26" height="2.2" fill="#C8A24A" opacity="0.82"/>')
ICONS = {
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "flame": '<path d="M12 2c1 4 6 6 6 12a6 6 0 0 1-12 0c0-3 2-5 3-7 0 2 1 3 2 3 0-3 0-6 1-8z"/>',
    "drop": '<path d="M12 2.5S5.5 10 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10 12 2.5 12 2.5z"/>',
    "thermal": '<path d="M10 3a2 2 0 0 1 4 0v10.3a4.5 4.5 0 1 1-4 0z"/>',
    "sun": '<circle cx="12" cy="12" r="4.2"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1M4.6 19.4l2.1-2.1M17.3 6.7l2.1-2.1"/>',
}


def read_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def read_source(name, root=ROOT, packet=None):
    """The Markdown for one binder source, without its PDF front matter."""
    if name in GENERATED_SOURCES:
        return GENERATED_SOURCES[name](packet or build_packet(root))
    if name.startswith("rate-tariff-sheets/"):
        path = SOURCES / "rate-tariffs" / Path(name).name
    else:
        path = SOURCES / SOURCE_FOLDERS.get(name, "intake-package") / name
    return FRONT_MATTER.sub("", read_text(root / path), count=1)


def is_table_start(lines, index):
    return lines[index].lstrip().startswith("|") and index + 1 < len(lines) and TABLE_DELIMITER.match(lines[index + 1]) is not None


def starts_block(lines, index):
    line = lines[index]
    return bool(HEADING.match(line) or RULE.match(line) or LIST_ITEM.match(line) or is_table_start(lines, index))


def split_row(line):
    row = line.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") else row
    return [cell.strip() for cell in row.split("|")]


def parse_blocks(markdown):
    """Split Markdown into headings, paragraphs, lists, tables and rules (the subset the sources use)."""
    lines = markdown.split("\n")
    blocks = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
        elif match := HEADING.match(line):
            blocks.append({"kind": "heading", "level": len(match[1]), "text": match[2]})
            index += 1
        elif RULE.match(line):
            blocks.append({"kind": "rule"})
            index += 1
        elif is_table_start(lines, index):
            header = split_row(line)
            index += 2
            rows = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                rows.append(split_row(lines[index]))
                index += 1
            blocks.append({"kind": "table", "header": header, "rows": rows})
        elif LIST_ITEM.match(line):
            ordered = LIST_ITEM.match(line)["marker"][0].isdigit()
            start = int(LIST_ITEM.match(line)["marker"][:-1]) if ordered else 1
            items = []
            while index < len(lines):
                item = LIST_ITEM.match(lines[index])
                if item and item["marker"][0].isdigit() == ordered:
                    parts = [item["text"]]
                    index += 1
                    while index < len(lines) and lines[index].strip() and not starts_block(lines, index):
                        parts.append(lines[index].strip())
                        index += 1
                    items.append(" ".join(parts))
                    continue
                following = index
                while following < len(lines) and not lines[following].strip():
                    following += 1
                if following > index and following < len(lines) and (next_item := LIST_ITEM.match(lines[following])) and next_item["marker"][0].isdigit() == ordered:
                    index = following
                    continue
                break
            blocks.append({"kind": "list", "ordered": ordered, "start": start, "items": items})
        else:
            parts = []
            while index < len(lines) and lines[index].strip() and (not parts or not starts_block(lines, index)):
                parts.append(lines[index])
                index += 1
            text = "".join(part.strip() + (HARD_BREAK if part.endswith("  ") else " ") for part in parts).strip(" " + HARD_BREAK)
            blocks.append({"kind": "paragraph", "text": text, "lines": [part.strip() for part in parts]})
    return blocks


def inline(text, links):
    """Render inline Markdown: code spans, links, strong and emphasis."""
    rendered = []
    for piece in re.split(r"(`[^`]+`)", text):
        if len(piece) > 1 and piece.startswith("`") and piece.endswith("`"):
            rendered.append(f"<code>{html.escape(piece[1:-1])}</code>")
            continue
        escaped = html.escape(piece, quote=False)
        escaped = LINK.sub(lambda match: link(match, links), escaped)
        escaped = STRONG.sub(r"<strong>\1</strong>", escaped)
        escaped = EMPHASIS.sub(r"<em>\1</em>", escaped)
        rendered.append(escaped)
    return "".join(rendered).replace(HARD_BREAK, "<br>")


def link(match, links):
    label, target = match[1], html.unescape(match[2])
    if target.startswith(("http://", "https://", "mailto:")):
        return f'<a href="{html.escape(target)}">{label}</a>'
    # Sources link to each other's PDFs; inside the binder those become section anchors.
    stem = Path(target.partition("#")[0]).stem
    if stem in links:
        return f'<a href="#{links[stem]}">{label}</a>'
    return label


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-")


def render_table(block, links, context=None):
    """Right-align mostly numeric columns and set figures in mono; register-style tables keep a column-based minimum width."""
    header, rows = block["header"], block["rows"]
    numeric = []
    for column in range(len(header)):
        values = [row[column].replace("*", "") for row in rows if column < len(row) and row[column].strip()]
        numeric.append(bool(values) and sum(1 for value in values if NUMBER.match(value)) / len(values) >= 0.6)

    def cell_class(column, cell):
        names = (["num"] if column < len(numeric) and numeric[column] else []) + (["fig"] if NUMBER.match(cell.replace("*", "")) else [])
        return f' class="{" ".join(names)}"' if names else ""

    wide = len(header) >= 8 or bool(context and context.get("wide"))
    table_attributes = f' class="t wide" style="--cols:{len(header)}"' if wide else ' class="t"'
    head_classes = [' class="num"' if flag else "" for flag in numeric]
    head = "".join(f"<th{head_classes[i]}>{inline(cell, links)}</th>" for i, cell in enumerate(header))
    body = "\n".join("<tr>" + "".join(f"<td{cell_class(i, cell)}>{inline(cell, links)}</td>" for i, cell in enumerate(row)) + "</tr>" for row in rows)
    return f'<div class="tw"><table{table_attributes}>\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}\n</tbody>\n</table></div>'


def render_list(block, links):
    tag = "ol" if block["ordered"] else "ul"
    start = f' start="{block["start"]}"' if block["ordered"] and block["start"] != 1 else ""
    items = "\n".join(f"<li>{inline(item, links)}</li>" for item in block["items"])
    return f'<{tag} class="b"{start}>\n{items}\n</{tag}>'


def render_block(block, links, context):
    kind = block["kind"]
    if kind == "heading":
        tag = "h2" if block["level"] <= 2 else "h3"
        text = inline(block["text"], links)
        return f'<{tag} class="h" id="{unique_id(context, text)}">{text}</{tag}>'
    if kind == "paragraph":
        return f"<p>{inline(block['text'], links)}</p>"
    if kind == "list":
        return render_list(block, links)
    if kind == "table":
        return render_table(block, links, context)
    return '<hr class="rule">'


def unique_id(context, text):
    base = f"{context['prefix']}-{slug(text)}"
    context[base] = context.get(base, 0) + 1
    return base if context[base] == 1 else f"{base}-{context[base]}"


def split_title(blocks):
    """Return the first H1 text and the remaining blocks."""
    for position, block in enumerate(blocks):
        if block["kind"] == "heading" and block["level"] == 1:
            return block["text"], blocks[:position] + blocks[position + 1:]
    return "", blocks


def render_document(blocks, links, context):
    parts = []
    for block in blocks:
        if block["kind"] == "paragraph" and re.match(r"^Packet [\d.]+ \|", block["text"]):
            parts.append(f'<p class="meta">{inline(block["text"], links)}</p>')
        else:
            parts.append(render_block(block, links, context))
    return "\n".join(parts)


def render_letter(blocks, links, context):
    """Memo header lines become a memo grid; the closing italic name and title become the signature."""
    parts = []
    for position, block in enumerate(blocks):
        lines = block.get("lines", [])
        entries = [MEMO_LINE.match(line) for line in lines]
        if block["kind"] == "paragraph" and entries and all(entries):
            memo = "\n".join(f'<div class="ml">{inline(entry["label"], links)}</div><div class="mv">{inline(entry["value"], links)}</div>' for entry in entries)
            parts.append(f'<div class="memo">\n{memo}\n</div>')
        elif block["kind"] == "paragraph" and position == len(blocks) - 1 and re.match(r"^\*[^*]+\*$", lines[0]):
            signature = HARD_BREAK.join(lines)
            parts.append(f'<p class="sig">{inline(signature, links)}</p>')
        else:
            parts.append(render_block(block, links, context))
    return "\n".join(parts)


def render_questionnaire(blocks, links, context):
    parts = []
    group_open = False
    for block in blocks:
        if block["kind"] == "heading" and block["level"] == 2:
            if group_open:
                parts.append("</div>")
            numbered = NUMBERED_HEADING.match(block["text"])
            text = f'<span class="hn">{numbered["number"]}</span>{inline(numbered["text"], links)}' if numbered else inline(block["text"], links)
            parts.append(f'<h2 class="h" id="{unique_id(context, text)}">{text}</h2>\n<div class="grp">')
            group_open = True
        elif block["kind"] == "paragraph" and (question := QUESTION.match(block["text"])):
            parts.append(f'<p class="q"><span class="qn">{question["number"]}</span>{inline(question["question"], links)}</p>')
            if question["answer"].strip():
                parts.append(f'<p class="a">{inline(question["answer"].strip(), links)}</p>')
        elif block["kind"] == "paragraph" and not group_open:
            parts.append(f'<p class="intro">{inline(block["text"], links)}</p>')
        else:
            parts.append(render_block(block, links, context))
    if group_open:
        parts.append("</div>")
    return "\n".join(parts)


def render_tariff_sheet(stem, markdown, links, context):
    palette, band, ink, icon = TARIFF_SHEETS[stem]
    title, blocks = split_title(parse_blocks(markdown))
    heading = SHEET_TITLE.match(title)
    kind, provider, scope = (heading["kind"], heading["provider"], heading["scope"]) if heading else ("", title, "")
    codes = [match["code"] for block in blocks if block["kind"] == "heading" and (match := SCHEDULE_CODE.search(block["text"]))]
    icon_svg = f'<svg viewBox="0 0 24 24" width="26" height="26" fill="{ink}" stroke="{ink}" stroke-width="{1.6 if icon == "sun" else 0}" stroke-linecap="round" aria-hidden="true">{ICONS[icon]}</svg>'
    parts = [
        f'<div class="sheet sheet-{palette}" id="sheet-{stem}">',
        f'<div class="sheet-band" style="background:{band};color:{ink}">',
        f'<div class="pm">{icon_svg}</div>',
        f'<div><div class="pk">{inline(kind, links)}</div><div class="pn">{inline(provider, links)}</div><div class="ps">{inline(scope, links)}</div></div>',
        f'<div class="pe">{"<br>".join(html.escape(code) for code in codes)}</div>',
        "</div>",
    ]
    position = 0
    while position < len(blocks):
        block = blocks[position]
        text = block.get("text", "")
        bold = BOLD_ONLY.match(text) if block["kind"] == "paragraph" else None
        if bold and text.startswith("**Effective"):
            parts.append(f'<div class="eff-row"><span class="eff">{inline(bold["text"], links)}</span></div>')
        elif bold and bold["text"].endswith(":") and position + 1 < len(blocks) and blocks[position + 1]["kind"] == "list":
            parts.append(f'<div class="note"><div class="nh">{inline(bold["text"][:-1], links)}</div>\n{render_list(blocks[position + 1], links)}\n</div>')
            position += 1
        elif block["kind"] == "paragraph" and text.startswith("Provided by:"):
            parts.append(f'<p class="provided">{inline(text, links)}</p>')
        else:
            parts.append(render_block(block, links, context))
        position += 1
    parts.append("</div>")
    return "\n".join(parts)


def render_workbook(blocks, links, context):
    parts = []
    for block in blocks:
        tab = re.match(r"^Tab:\s*(.+)$", block.get("text", "")) if block["kind"] == "heading" else None
        if tab:
            text = inline(tab[1], links)
            parts.append(f'<h2 class="h" id="{unique_id(context, text)}"><span class="tab-tag">Tab</span>{text}</h2>')
        else:
            parts.append(render_block(block, links, context))
    return "\n".join(parts)


def draft_chip(version):
    return f'<span class="draft-chip">Synthetic<br>Packet {html.escape(version)}</span>'


EM_DASH = chr(0x2014)
ORGANIZATION_TITLE = re.compile(f"^(?P<organization>Northlake University) {EM_DASH} (?P<title>.+)$")
ORGANIZATION_PREFIX = re.compile(f"^Northlake(?: University)?(?: {EM_DASH})? ")


def title_html(title, links):
    """Set the organisation of an organisation-prefixed title as a small line above the document name."""
    match = ORGANIZATION_TITLE.match(title)
    if match is None:
        return inline(title, links)
    return f'<span class="sec-org">{inline(match["organization"], links)}</span>{inline(match["title"], links)}'


def contents_label(title):
    """The binder is Northlake's own, so contents entries drop the repeated organisation prefix."""
    return ORGANIZATION_PREFIX.sub("", title, count=1)


def render_section(number, section, documents, links, version):
    context = {"prefix": section["key"], "wide": section.get("wide", False)}
    if section["layout"] == "tariffs":
        title = section["title"]
        body = "\n".join(render_tariff_sheet(Path(source).stem, documents[source], links, context) for source in section["sources"])
    else:
        title, blocks = split_title(parse_blocks(documents[section["sources"][0]]))
        renderer = {"letter": render_letter, "questionnaire": render_questionnaire, "workbook": render_workbook}.get(section["layout"], render_document)
        body = renderer(blocks, links, context)
    letterhead = LETTERHEAD if section["layout"] == "letter" else ""
    wide = " wide-section" if section.get("wide") else ""
    head = (f'<div class="sec-head"><div><p class="eyebrow">Section {number:02d} \u00b7 {html.escape(section["owner"])}</p>'
            f'<h1 class="sec-title">{title_html(title, links)}</h1></div>{draft_chip(version)}</div>')
    return f'<section class="section pad{wide}" id="section-{section["key"]}">\n{letterhead}{head}\n{body}\n</section>', title


LETTERHEAD = (
    '<div class="letterhead"><div class="lh-brand">'
    f'<svg width="46" height="46" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="31" fill="#14263F"/>{MARK}</svg>'
    '<div><div class="lh-wm">Northlake</div><div class="lh-sub">UNIVERSITY</div></div></div>'
    '<div class="lh-office"><div class="lh-o1">Office of Campus Operations</div><div class="lh-o2">Facilities \u00b7 Housing \u00b7 Sustainability \u00b7 Finance</div></div></div>\n'
)


def font_css():
    faces = []
    for family, style, weight, filename in FONT_FACES:
        data = base64.b64encode((FONTS / filename).read_bytes()).decode("ascii")
        faces.append(f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    return "\n".join(faces)


def render_package(root=ROOT):
    onboarding = yaml.safe_load(read_text(root / ONBOARDING))
    version = str(onboarding["packetVersion"])
    issued = date.fromisoformat(str(onboarding["issuedOn"]))
    issued_text = f"{issued:%B} {issued.day}, {issued.year}"
    packet = build_packet(root)
    documents = {source: read_source(source, root, packet) for section in SECTIONS for source in section["sources"]}
    coverage = re.search(r"\*\*Planned coverage period:\*\*\s*(.+)", documents["00-cover-letter.md"])
    if coverage is None:
        raise ValueError("00-cover-letter.md must state the planned coverage period")
    links = {}
    for section in SECTIONS:
        for source in section["sources"]:
            links[Path(source).stem] = f"sheet-{Path(source).stem}" if section["layout"] == "tariffs" else f"section-{section['key']}"

    sections, contents = [], []
    for number, section in enumerate(SECTIONS, start=1):
        markup, title = render_section(number, section, documents, links, version)
        sections.append(markup)
        label = f"{title} ({len(section['sources'])} providers)" if section["layout"] == "tariffs" else contents_label(title)
        contents.append(f'<a class="toc-row" href="#section-{section["key"]}"><span class="toc-n">{number:02d}</span><span class="toc-t">{inline(label, links)}</span><span class="toc-o">{html.escape(section["owner"])}</span></a>')

    escaped_version = html.escape(version)
    cover = f"""<div class="cover" id="cover">
<svg class="ghost" viewBox="0 0 64 64" aria-hidden="true">{MARK}</svg>
<div class="brand"><svg width="52" height="52" viewBox="0 0 64 64" aria-hidden="true">{MARK}</svg><div><div class="wm">Northlake</div><div class="wm-sub">UNIVERSITY</div></div></div>
<div class="cover-title">
<p class="kicker">Facilities \u00b7 Housing \u00b7 Sustainability \u00b7 Finance</p>
<h1>Onboarding Data Package</h1>
<p class="blurb">Facilities, utility, billing, cost-allocation, and reporting source material assembled by our Facilities, Housing, Finance, and Sustainability teams for the new energy &amp; utility management system setup.</p>
</div>
<div class="cover-foot">
<div class="facts">
<div><div class="fact-k">Coverage period</div><div class="fact-v">{inline(coverage[1].strip(), links)}</div></div>
<div><div class="fact-k">Version</div><div class="fact-v">Packet {escaped_version}</div></div>
<div><div class="fact-k">Issued</div><div class="fact-v">{issued_text}</div></div>
<div><div class="fact-k">Prepared by</div><div class="fact-v">Campus Operations, Northlake University</div></div>
</div>
<p class="synthetic">SYNTHETIC, FICTIONAL DATA \u2014 PREPARED FOR IMPLEMENTATION SETUP.</p>
</div>
</div>"""
    toc = f"""<section class="toc pad" id="contents">
<p class="eyebrow">Contents</p>
<h1 class="sec-title toc-title">What's enclosed</h1>
<p class="toc-intro">This binder compiles the source material our teams assembled to describe how the university is organized and how we want our utility data, billing, cost allocation, and reporting handled. Everything is written in our own operational terms; please map it into your system during the design phase and confirm back to us.</p>
{chr(10).join(contents)}
</section>"""
    end = f"""<section class="pad end-pad"><div class="end">
<p class="end-k">End of package</p>
<p>This binder compiles packet {escaped_version} of the Northlake University onboarding data package, issued {issued_text}. All identifiers, names, and figures are synthetic and fictional, prepared for implementation setup. Please confirm the open items with the area contacts listed in the transmittal letter.</p>
</div></section>"""
    css = STYLES.replace("__VERSION__", version.replace('"', ""))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Northlake University \u2014 Onboarding Data Package \u2014 Packet {escaped_version}</title>
<style>
{font_css()}
{css}
</style>
</head>
<body>
<div class="binder">
<div class="paper">
{cover}
{toc}
{chr(10).join(sections)}
{end}
</div>
</div>
</body>
</html>
"""


STYLES = """:root{--nu-primary:#14263F;--nu-secondary:#C8A24A;--nu-tint:#EEF1F5;--cool-200:#DCE3EB;--warm-50:#FAF8F2;--warm-200:#E9E3D4;
--ved-primary:#1C5FB0;--ved-tint:#E8F1FA;--ved-ink:#11457F;--sgu-primary:#C9551F;--sgu-tint:#F7ECE3;--sgu-ink:#A8420F;
--rcu-primary:#0E7C86;--rcu-tint:#E4F2F2;--rcu-ink:#0A5860;--ntp-primary:#37474F;--ntp-tint:#ECEFF1;--ntp-ink:#2B373D;
--hos-primary:#F5A524;--hos-tint:#FEF4E2;--hos-ink:#8A5305;
--font-nu:'Spectral',Georgia,'Times New Roman',serif;--font-ui:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;--font-mono:'IBM Plex Mono',ui-monospace,'SFMono-Regular',Menlo,monospace}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--warm-200);color:#2E3942;font-family:var(--font-ui);font-size:15px;line-height:1.62;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.binder{padding:40px 20px 90px}
.paper{max-width:8.5in;margin:0 auto;background:#fff;box-shadow:0 8px 34px rgba(20,38,63,.16);overflow:hidden}
.pad{padding-left:.82in;padding-right:.82in}
.section{padding-top:50px;padding-bottom:26px}
p{margin:0 0 12px}
strong{color:#1B2B40;font-weight:600}
a{color:#1F4F7A;text-underline-offset:2px}
code{font:500 .9em var(--font-mono);background:#F4F0E6;padding:0 4px}
.eyebrow{font:600 11px/1.3 var(--font-ui);text-transform:uppercase;letter-spacing:.15em;color:#7A6E57;margin:0}
.cover{position:relative;background:var(--nu-primary);color:#fff;min-height:10.6in;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;gap:48px;padding:.95in .85in .78in}
.cover::before{content:"";position:absolute;top:0;left:0;bottom:0;width:7px;background:linear-gradient(#C8A24A,#9C7A22)}
.cover .ghost{position:absolute;top:-70px;right:-90px;width:460px;height:460px;opacity:.06}
.brand{position:relative;display:flex;align-items:center;gap:15px}
.wm{font:600 25px/1 var(--font-nu);letter-spacing:-.01em;color:#fff}
.wm-sub{font:600 10.5px/1 var(--font-ui);letter-spacing:.42em;color:#C8A24A;margin-top:5px}
.cover-title,.cover-foot{position:relative}
.kicker{font:600 12px/1.4 var(--font-ui);text-transform:uppercase;letter-spacing:.22em;color:#C8A24A;margin:0 0 22px}
.cover h1{font:600 60px/1.04 var(--font-nu);letter-spacing:-.02em;color:#fff;margin:0 0 22px;max-width:9.5in}
.blurb{font:400 17px/1.6 var(--font-ui);color:#AEBBCB;margin:0;max-width:6.2in}
.facts{display:flex;flex-wrap:wrap;gap:18px 48px;border-top:1px solid rgba(200,162,74,.28);padding-top:22px;margin-bottom:20px}
.fact-k{font:600 9.5px/1 var(--font-ui);text-transform:uppercase;letter-spacing:.13em;color:#C8A24A;margin-bottom:7px}
.fact-v{font:500 14px/1.3 var(--font-ui);color:#E7ECF2}
.synthetic{font:500 11px/1.4 var(--font-mono);letter-spacing:.04em;color:#6E7E92;margin:0}
.toc{padding-top:56px;padding-bottom:44px}
.toc-title{font-size:34px;margin-bottom:14px}
.toc-intro{color:#5E5849;max-width:66ch;margin-bottom:22px}
.toc-row{display:flex;align-items:baseline;gap:14px;padding:13px 2px;border-bottom:1px solid var(--cool-200);text-decoration:none}
.toc-row:hover .toc-t{text-decoration:underline}
.toc-n{font:600 13px/1 var(--font-mono);color:#A8853A;width:26px;flex:none}
.toc-t{font:600 15.5px/1.3 var(--font-ui);color:var(--nu-primary)}
.toc-o{margin-left:auto;font:600 10.5px/1.3 var(--font-ui);text-transform:uppercase;letter-spacing:.08em;color:#8A7E66;white-space:nowrap;padding-left:14px}
.sec-head{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;border-bottom:2px solid var(--nu-primary);padding-bottom:15px;margin-bottom:26px;position:relative}
.sec-head::after{content:"";position:absolute;left:0;bottom:-2px;width:96px;height:2px;background:var(--nu-secondary)}
.sec-title{font:600 31px/1.1 var(--font-nu);color:var(--nu-primary);letter-spacing:-.015em;margin:9px 0 6px}
.sec-org{display:block;font:600 15px/1.3 var(--font-nu);color:#7A6E57;letter-spacing:0;margin:0 0 3px}
.draft-chip{font:600 9.5px/1.1 var(--font-ui);letter-spacing:.1em;text-transform:uppercase;color:#9C7A22;border:1px solid #DCC992;background:#FBF6E6;padding:7px 10px;white-space:nowrap;text-align:center}
.letterhead{display:flex;justify-content:space-between;align-items:flex-end;gap:18px;border-bottom:2px solid var(--nu-primary);padding-bottom:15px;margin-bottom:30px;position:relative}
.letterhead::after{content:"";position:absolute;left:0;bottom:-2px;width:96px;height:2px;background:var(--nu-secondary)}
.lh-brand{display:flex;align-items:center;gap:13px}
.lh-wm{font:600 22px/1 var(--font-nu);color:var(--nu-primary);letter-spacing:-.01em}
.lh-sub{font:600 9px/1 var(--font-ui);letter-spacing:.4em;color:#9C7A22;margin-top:5px}
.lh-office{text-align:right}
.lh-o1{font:600 10px/1.3 var(--font-ui);text-transform:uppercase;letter-spacing:.12em;color:var(--nu-primary)}
.lh-o2{font:400 11px/1.4 var(--font-ui);color:#7A6E57;margin-top:3px}
h2.h{font:600 19px/1.25 var(--font-nu);color:var(--nu-primary);margin:30px 0 7px;letter-spacing:-.01em}
h3.h{font:600 12.5px/1.3 var(--font-ui);color:#1B2B40;text-transform:uppercase;letter-spacing:.07em;margin:22px 0 9px}
.meta{font:500 11.5px/1.5 var(--font-mono);letter-spacing:.03em;color:#7A6E57;margin:-8px 0 16px}
.intro{color:#5E5849}
ul.b,ol.b{margin:6px 0 16px;padding-left:20px}
ul.b li,ol.b li{margin:0 0 6px;padding-left:3px}
hr.rule{border:0;border-top:1px solid var(--cool-200);margin:24px 0}
.tw{overflow-x:auto;margin:14px 0 22px}
table.t{width:100%;border-collapse:collapse;font-size:13px}
table.t th{background:var(--nu-tint);color:var(--nu-primary);font:600 10.5px/1.25 var(--font-ui);letter-spacing:.05em;text-transform:uppercase;text-align:left;padding:9px 11px;border-bottom:2px solid var(--nu-primary);vertical-align:bottom}
table.t td{padding:8px 11px;border-bottom:1px solid var(--cool-200);vertical-align:top;color:#34404D}
table.t tbody tr:nth-child(even){background:var(--warm-50)}
table.t td.num,table.t th.num{text-align:right;white-space:nowrap}
table.t td.fig{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
table.t.wide{min-width:max(100%,calc(var(--cols) * 150px));font-size:11.5px}
table.t.wide th{font-size:9.5px;padding:7px 8px}
table.t.wide td{padding:6px 8px}
.memo{display:grid;grid-template-columns:max-content 1fr;gap:9px 18px;background:var(--warm-50);border:1px solid var(--warm-200);padding:18px 20px;margin:0 0 26px;font-size:13.5px}
.ml{font:600 10px/1.9 var(--font-mono);text-transform:uppercase;letter-spacing:.08em;color:#9C7A22}
.mv{color:#2E3942}
.sig{margin-top:24px;color:#34404D}
.sig em{font:italic 400 17px/1.5 var(--font-ui);color:var(--nu-primary)}
.grp{border-left:2px solid var(--warm-200);padding-left:20px;margin:8px 0 26px}
.hn{font:600 14px/1 var(--font-mono);color:#A8853A;margin-right:10px}
.q{font:600 14.5px/1.45 var(--font-ui);color:var(--nu-primary);margin:18px 0 5px}
.qn{color:#A8853A;font-family:var(--font-mono);font-size:12.5px;font-weight:600;margin-right:8px}
.a{margin:0 0 4px;color:#34404D}
.sheet{margin-bottom:10px}
.sheet+.sheet{margin-top:40px}
.sheet-band{display:flex;align-items:center;gap:15px;padding:15px 18px;margin-bottom:4px}
.sheet-band .pm{flex:none;width:48px;height:48px;background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center}
.sheet-band .pk{font:600 10px/1.3 var(--font-ui);text-transform:uppercase;letter-spacing:.12em;opacity:.86}
.sheet-band .pn{font:600 19px/1.15 var(--font-ui);margin-top:3px}
.sheet-band .ps{font:600 10.5px/1.3 var(--font-ui);opacity:.86;text-transform:uppercase;letter-spacing:.1em;margin-top:4px}
.sheet-band .pe{margin-left:auto;text-align:right;font:600 10.5px/1.5 var(--font-mono);opacity:.95}
.provided{font-size:12px;color:#8A7E66;font-style:italic;margin:10px 0 12px}
.eff-row{margin:16px 0 2px}
.eff{display:inline-block;font:600 10px/1.2 var(--font-ui);text-transform:uppercase;letter-spacing:.09em;padding:6px 11px}
.note{border-left:3px solid var(--nu-secondary);background:var(--warm-50);padding:12px 16px;margin:16px 0 18px;font-size:13.5px;color:#4A4636}
.note .nh{font:600 10.5px/1 var(--font-ui);text-transform:uppercase;letter-spacing:.1em;color:#9C7A22;margin:0 0 7px}
.note ul.b{margin:6px 0 0;padding-left:18px}
.sheet-ved .eff{background:var(--ved-tint);color:var(--ved-ink)}
.sheet-sgu .eff{background:var(--sgu-tint);color:var(--sgu-ink)}
.sheet-rcu .eff{background:var(--rcu-tint);color:var(--rcu-ink)}
.sheet-ntp .eff{background:var(--ntp-tint);color:var(--ntp-ink)}
.sheet-hos .eff{background:var(--hos-tint);color:var(--hos-ink)}
.sheet-ved table.t th{background:var(--ved-tint);color:var(--ved-ink);border-bottom-color:var(--ved-primary)}
.sheet-sgu table.t th{background:var(--sgu-tint);color:var(--sgu-ink);border-bottom-color:var(--sgu-primary)}
.sheet-rcu table.t th{background:var(--rcu-tint);color:var(--rcu-ink);border-bottom-color:var(--rcu-primary)}
.sheet-ntp table.t th{background:var(--ntp-tint);color:var(--ntp-ink);border-bottom-color:var(--ntp-primary)}
.sheet-hos table.t th{background:var(--hos-tint);color:var(--hos-ink);border-bottom-color:var(--hos-primary)}
.tab-tag{display:inline-block;font:600 9.5px/1 var(--font-mono);color:#fff;background:var(--nu-primary);padding:4px 7px;vertical-align:middle;margin:-3px 9px 0 0;letter-spacing:.06em;text-transform:uppercase}
.end-pad{padding-bottom:56px}
.end{margin-top:16px;padding-top:20px;border-top:2px solid var(--nu-primary);position:relative;color:#5E5849;max-width:100%}
.end::before{content:"";position:absolute;top:-2px;left:0;width:96px;height:2px;background:var(--nu-secondary)}
.end-k{font:600 11px/1.5 var(--font-ui);text-transform:uppercase;letter-spacing:.12em;color:#9C7A22;margin:0 0 6px}
@media (max-width:680px){
.binder{padding:0}
.pad{padding-left:20px;padding-right:20px}
.cover{min-height:0;padding:48px 24px 40px}
.cover h1{font-size:40px}
.sec-head,.letterhead{flex-direction:column;align-items:flex-start}
.lh-office{text-align:left}
.toc-row{flex-wrap:wrap;row-gap:4px}
.toc-o{flex-basis:100%;margin-left:40px;padding-left:0}
}
@page{size:Letter;margin:.82in .7in .72in;
@top-left{content:"NORTHLAKE UNIVERSITY";font-family:'IBM Plex Sans',sans-serif;font-size:7.5pt;letter-spacing:.16em;color:#9AA6B2}
@top-right{content:"Onboarding Data Package \\00B7 Packet __VERSION__";font-family:'IBM Plex Sans',sans-serif;font-size:7.5pt;color:#9AA6B2}
@bottom-left{content:"Synthetic, fictional data \\2014 prepared for implementation setup.";font-family:'IBM Plex Sans',sans-serif;font-size:7pt;color:#B2BAC3}
@bottom-right{content:"Page " counter(page) " of " counter(pages);font-family:'IBM Plex Mono',monospace;font-size:7.5pt;color:#9AA6B2}}
@page:first{margin:0;@top-left{content:none}@top-right{content:none}@bottom-left{content:none}@bottom-right{content:none}}
@page wide{size:Letter landscape;margin:.6in .55in .62in}
@media print{
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{background:#fff;font-size:10.4pt}
.binder{padding:0}
.paper{max-width:none;margin:0;box-shadow:none;overflow:visible}
.pad{padding-left:0;padding-right:0}
.section{break-before:page;padding-top:4px;padding-bottom:0}
.wide-section{page:wide}
.cover{break-after:page;height:100vh;min-height:0}
.toc-row{color:inherit}
h1,h2,h3,.sec-head,.letterhead{break-after:avoid}
tr,.note,.sheet-band,.memo,.eff-row{break-inside:avoid}
.sheet+.sheet{break-before:page;margin-top:0}
.tw{overflow:visible}
table.t{font-size:9.2pt}
table.t.wide{min-width:0;font-size:7pt}
table.t.wide th{font-size:6.4pt;padding:5px 5px}
table.t.wide td{padding:4px 5px}
thead{display:table-header-group}
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit with status 1 when the binder does not match the current sources")
    args = parser.parse_args()
    content = render_package()
    target = ROOT / TARGET
    version = yaml.safe_load(read_text(ROOT / ONBOARDING))["packetVersion"]
    if args.check:
        current = read_text(target) if target.exists() else ""
        if current != content:
            print(f"{TARGET.as_posix()} is stale; run python generators/render_intake_package.py")
            return 1
        print(f"{TARGET.as_posix()} matches packet {version}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.as_posix()} for packet {version} ({len(content.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
