"""Render Northlake's bills from every file under data/bills/.

Run: python generators/render_bills.py            writes the PDFs under documents/utility-bills/
     python generators/render_bills.py --check    fails if a checked-in bill is stale

Every bill is checked before it is drawn: quantity x rate rounds to the amount, a
percentage line matches its base, the lines sum to the total, and a credit transferred
out of one account arrives, with the opposite sign, on the bill it names. Every bill under
documents/utility-bills/ comes from here; none is a hand-made image.
"""
from __future__ import annotations

import argparse
import io
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Importing the document renderer also sets reportlab's invariant mode: identical bytes per run.
from generators.documents.render_northlake_pdf import BOLD, INK, LINE, REGULAR, SEMIBOLD, SLATE, register_fonts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path("data/bills")
SCENARIO = Path("data/scenarios/demo-university-v1.yaml")
CENT = Decimal("0.01")
LINE_KEYS = {"code", "description", "quantity", "unit", "rate", "amount", "percent", "percentOf", "transfer", "estimate"}
MARGIN = 46.0
BAND_HEIGHT = 84.0
# Provider id -> (band colour, tint), the intake binder's tariff-sheet palette.
PALETTE = {
    "valley_electric_district": ("#1C5FB0", "#E8F1FA"),
    "sierra_gas_utility": ("#C9551F", "#F7ECE3"),
    "river_city_utilities": ("#0E7C86", "#E4F2F2"),
    "northlake_thermal_plant": ("#37474F", "#ECEFF1"),
    "helios_onsite_solar": ("#F5A524", "#FEF4E2"),
    "ridgeline_wind": ("#2E6E5A", "#E6F0EC"),
}


def read_yaml(root, path):
    return yaml.safe_load((root / path).read_text(encoding="utf-8"))


def load_bills(root=ROOT):
    """(bill, source file) for every bill under data/bills/, file by file in name order."""
    return [(bill, path.relative_to(root)) for path in sorted((root / SOURCE_DIR).glob("*.yaml"))
            for bill in yaml.safe_load(path.read_text(encoding="utf-8"))["bills"]]


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def check_bills(bills):
    """Every arithmetic and cross-bill fact the PDFs show, asserted from the source alone."""
    by_id = {bill["id"]: bill for bill in bills}
    assert len(by_id) == len(bills), "A bill id is listed twice"
    for bill in bills:
        amounts = {}                     # charge code -> the sum of its lines so far (a code repeats across a rate change)
        for line in bill["lines"]:
            # An unquoted comma in a flow mapping silently splits a description into a stray key.
            assert set(line) <= LINE_KEYS, f"{bill['id']}: unknown line keys {sorted(set(line) - LINE_KEYS)}; quote a description that has a comma"
            amount = money(line["amount"])
            if "rate" in line:
                expected = money(Decimal(str(line["quantity"])) * Decimal(str(line["rate"])))
                assert expected == amount, f"{bill['id']}: {line['description']} is {amount}; quantity x rate is {expected}"
            if "percent" in line:
                assert line["code"] not in line["percentOf"] and all(code in amounts for code in line["percentOf"]), f"{bill['id']}: {line['description']} names a line that is not above it"
                expected = money(sum(amounts[code] for code in line["percentOf"]) * Decimal(str(line["percent"])) / 100)
                assert expected == amount, f"{bill['id']}: {line['description']} is {amount}; {line['percent']}% of its base is {expected}"
            amounts[line["code"]] = amounts.get(line["code"], Decimal(0)) + amount
        assert sum(amounts.values()) == money(bill["total"]), f"{bill['id']}: lines sum to {sum(amounts.values())}, total is {bill['total']}"
        if bill.get("supersedes"):
            assert by_id[bill["supersedes"]]["period"] == bill["period"], f"{bill['id']}: a corrected bill covers the period of the bill it supersedes"
        for line in bill["lines"]:
            target = (line.get("transfer") or {}).get("appearsOn")
            if target:
                arrivals = [other for other in by_id[target]["lines"] if (other.get("transfer") or {}).get("leftOn") == bill["id"]]
                assert len(arrivals) == 1, f"{bill['id']}: the transferred credit does not arrive once on {target}"
                assert money(arrivals[0]["amount"]) == -money(line["amount"]), f"{bill['id']}: the credit changes amount on its way to {target}"
    return by_id


def address_text(address):
    return f"{address['line1']}, {address['city']}, {address['state']} {address['postalCode']}"


def day(value):
    return f"{value:%B} {value.day}, {value.year}" if isinstance(value, date) else "None"


def currency(value) -> str:
    amount = money(value)
    return f"{'−' if amount < 0 else ''}${abs(amount):,.2f}"


def read_period_text(meter):
    period = meter.get("readPeriod")
    return f"{period['start']:%m/%d} to {period['end']:%m/%d}" if period else ""


def reads_text(meter):
    if "present" not in meter:
        return ""
    return f"{meter['previous']:,} to {meter['present']:,}" + (f" {meter['readType']}" if meter.get("readType") else "")


# Meter summary columns: header, the meter key that adds the column when any meter on the bill has it
# (None: always shown), relative width, and the cell text.
METER_COLUMNS = [
    ("Meter", None, 0.17, lambda meter: meter["meterNumber"]),
    ("Badge / tag", "badge", 0.17, lambda meter: meter.get("badge", "")),
    ("Multiplier", "multiplier", 0.08, lambda meter: f"{meter['multiplier']:,}" if "multiplier" in meter else ""),
    ("Channel", None, 0.22, lambda meter: meter["channel"]),
    ("Read period", "readPeriod", 0.12, read_period_text),
    ("Reads", "present", 0.17, reads_text),
    ("Factor", "factor", 0.06, lambda meter: f"{meter['factor']}" if "factor" in meter else ""),
    ("Quantity", None, 0.1, lambda meter: f"{meter['quantity']:,}" + (f" ({meter['statedAs']})" if meter.get("statedAs") else "")),
    ("Unit", None, 0.06, lambda meter: meter["unit"]),
]


def rate_text(line, amounts):
    if "percent" in line:
        return f"{line['percent']}% of {currency(sum(amounts[code] for code in line['percentOf']))}"
    if "rate" not in line:
        return "transfer" if line.get("transfer") else ""
    rate = Decimal(str(line["rate"]))
    places = max(2, -rate.normalize().as_tuple().exponent)
    return f"{'−' if rate < 0 else ''}${abs(rate):,.{places}f}/{line['unit']}"


def styles():
    base = dict(fontName=REGULAR, fontSize=8.6, leading=11.2, textColor=INK)
    return {
        "body": ParagraphStyle("body", **base),
        "label": ParagraphStyle("label", **{**base, "fontName": SEMIBOLD, "textColor": SLATE, "fontSize": 7.4, "leading": 9.4}),
        "heading": ParagraphStyle("heading", **{**base, "fontName": BOLD, "fontSize": 10.4, "leading": 13, "spaceBefore": 10, "spaceAfter": 4}),
        "right": ParagraphStyle("right", **{**base, "alignment": TA_RIGHT}),
        "due": ParagraphStyle("due", **{**base, "fontName": BOLD, "fontSize": 17, "leading": 21, "alignment": TA_RIGHT}),
    }


def grid(rows, widths, tint, numeric_from, total_row=False):
    table = Table(rows, colWidths=widths, repeatRows=1)
    commands = [
        ("FONT", (0, 0), (-1, 0), SEMIBOLD, 7.6),
        ("FONT", (0, 1), (-1, -1), REGULAR, 8.2),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(tint)),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("ALIGN", (numeric_from, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if total_row:
        commands += [("FONT", (0, -1), (-1, -1), BOLD, 9), ("LINEABOVE", (0, -1), (-1, -1), 1, INK)]
    table.setStyle(TableStyle(commands))
    return table


def bill_story(bill, provider, scenario, wrap_meter_cells=False):
    s = styles()
    band, tint = PALETTE[provider["id"]]
    accounts = {account["id"]: account for account in scenario["accounts"]}
    buildings = {building["id"]: building for site in scenario["sites"] for building in site["buildings"]}
    account = accounts[bill["accountId"]]
    assert account["syntheticAccountNumber"] == bill["accountNumber"], f"{bill['id']}: account number differs from the scenario"
    building = buildings[account["buildingId"]]
    width = LETTER[0] - 2 * MARGIN
    journal = bill["dueDate"] is None

    facts = [
        ("Customer", bill["customer"]),
        ("Account number", bill["accountNumber"]),
        ("Service location", f"{building['displayName']}, {address_text(building['address'])}"),
        ("Rate schedules", ", ".join(bill["rateSchedules"])),
        ("Statement date", day(bill["billDate"])),
        ("Service period", f"{day(bill['period']['start'])} to {day(bill['period']['end'])}"),
    ]
    if bill.get("preparedBy"):
        facts.append(("Prepared by", bill["preparedBy"]))
    left = Table([[Paragraph(label, s["label"]), Paragraph(value, s["body"])] for label, value in facts], colWidths=[92, width * 0.62 - 92])
    left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    due_label = "Transfer total (journal, no payment)" if journal else f"Amount due by {day(bill['dueDate'])}"
    right = Table([[Paragraph(due_label, ParagraphStyle("dl", parent=s["label"], alignment=TA_RIGHT))], [Paragraph(currency(bill["total"]), s["due"])]], colWidths=[width * 0.38])
    right.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(tint)), ("LINEABOVE", (0, 0), (-1, 0), 2, colors.HexColor(band)), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    header = Table([[left, right]], colWidths=[width * 0.62, width * 0.38])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story = [header, Spacer(1, 10)]

    notice = Table([[Paragraph(bill["notice"].strip(), s["body"])]], colWidths=[width])
    notice.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(tint)), ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(band)), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(notice)

    story.append(Paragraph("Meter summary", s["heading"]))
    columns = [column for column in METER_COLUMNS if column[1] is None or any(column[1] in meter for meter in bill["meters"])]
    if wrap_meter_cells:
        columns = [column for column in columns if column[0] not in ("Multiplier", "Factor")
                   or any(Decimal(str(meter.get(column[1], 1))) != 1 for meter in bill["meters"])]
        weights = {"Meter": 0.22, "Badge / tag": 0.16, "Multiplier": 0.07, "Channel": 0.18,
                   "Read period": 0.11, "Reads": 0.28, "Factor": 0.08, "Quantity": 0.17, "Unit": 0.07}
        columns = [(label, key, weights[label], formatter) for label, key, _, formatter in columns]
    weight = sum(column[2] for column in columns)
    meter_rows = [[column[0] for column in columns]] + [[column[3](meter) for column in columns] for meter in bill["meters"]]
    numeric_from = next(index for index, column in enumerate(columns) if column[0] in ("Reads", "Factor", "Quantity"))
    if wrap_meter_cells:
        labels = {"electric_kwh": "Electricity", "gas_ccf": "Gas volume", "gas_therms": "Gas energy", "water_kgal": "Water",
                  "chilled_water_ton_hours": "Chilled water", "steam_klb": "Steam", "generated_kwh": "Generation",
                  "exported_kwh": "Export", "received_kwh": "Export received", "delivered_kwh": "Station service", "reactive_kvarh": "Reactive energy"}
        meter_rows = [[Paragraph("Mult." if column[0] == "Multiplier" else escape(column[0]), s["label"]) for column in columns]]
        for meter in bill["meters"]:
            row = []
            numbers = {key: f"{Decimal(str(meter[key])).normalize():,f}" for key in ("previous", "present", "quantity") if key in meter}
            for index, column in enumerate(columns):
                text = escape(str(column[3](meter)))
                if column[0] == "Reads" and "present" in meter:
                    text = escape(numbers["previous"]) + "<br/>to " + escape(numbers["present"])
                    if meter.get("readType"):
                        text += "<br/>" + escape(meter["readType"])
                elif column[0] == "Channel":
                    text = escape(labels.get(meter["channel"], meter["channel"]))
                elif column[0] == "Read period" and meter.get("readPeriod"):
                    text = f"{meter['readPeriod']['start']:%m/%d}<br/>to {meter['readPeriod']['end']:%m/%d}"
                elif column[0] == "Quantity":
                    text = escape(numbers["quantity"])
                    if meter.get("statedAs"):
                        text += "<br/>" + escape(meter["statedAs"])
                row.append(Paragraph(text, s["right"] if index >= numeric_from else s["body"]))
            meter_rows.append(row)
    story.append(grid(meter_rows, [width * column[2] / weight for column in columns], tint, numeric_from))

    if not wrap_meter_cells:
        story.append(Paragraph("Charge detail", s["heading"]))
    amounts = {}
    for line in bill["lines"]:
        amounts[line["code"]] = amounts.get(line["code"], Decimal(0)) + money(line["amount"])
    charge_rows = [["Charge", "Quantity", "Rate", "Amount"]]
    for line in bill["lines"]:
        quantity = f"{line['quantity']:,} {line['unit']}" if "quantity" in line else ""
        if wrap_meter_cells:
            quantity = Paragraph(escape(quantity), s["right"])
        description = line["description"] + (" (estimated)" if line.get("estimate") else "")
        charge_rows.append([Paragraph(description, s["body"]), quantity, Paragraph(rate_text(line, amounts), s["right"]), currency(line["amount"])])
    charge_rows.append(["Total" if journal else "Total amount due", "", "", currency(bill["total"])])
    charge_table = grid(charge_rows, [width * f for f in (0.47, 0.17, 0.2, 0.16)], tint, 1, total_row=True)
    story.append(KeepTogether([Paragraph("Charge detail", s["heading"]), charge_table] if wrap_meter_cells else charge_table))

    if bill.get("informational"):
        story.append(Paragraph("Operating summary (informational, not charged)", s["heading"]))
        info_rows = [["Measure", "Value"]] + [[item["label"], f"{item['value']:,} {item['unit']}".replace(" %", "%")] for item in bill["informational"]]
        story.append(grid(info_rows, [width * 0.74, width * 0.26], tint, 1))
    return story


def render_bill(bill, provider, scenario, source, output, wrap_meter_cells=False):
    register_fonts()
    band, _ = PALETTE[provider["id"]]
    billing = provider["billing"]

    def page(canvas, doc):
        width, height = LETTER
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(band))
        canvas.rect(0, height - BAND_HEIGHT, width, BAND_HEIGHT, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(BOLD, 19)
        canvas.drawString(MARGIN, height - 38, provider["displayName"])
        canvas.setFont(REGULAR, 8)
        canvas.drawString(MARGIN, height - 54, f"Remit to: {address_text(billing['remitAddress'])}")
        canvas.drawString(MARGIN, height - 66, f"Office: {address_text(billing['businessAddress'])}   {provider.get('website', '')}")
        canvas.setFont(SEMIBOLD, 11.5)
        canvas.drawRightString(width - MARGIN, height - 38, bill["title"])
        canvas.setFont(REGULAR, 8)
        canvas.drawRightString(width - MARGIN, height - 54, f"Account {bill['accountNumber']}")
        canvas.drawRightString(width - MARGIN, height - 66, f"Period {bill['period']['start']:%m/%d/%Y} to {bill['period']['end']:%m/%d/%Y}")
        canvas.setFillColor(SLATE)
        canvas.setFont(REGULAR, 6.8)
        canvas.drawString(MARGIN, 30, "Northlake synthetic customer. Every name, number and value is fictional.")
        canvas.drawString(MARGIN, 21, f"Source: {source.as_posix()} ({bill['id']})")
        canvas.drawRightString(width - MARGIN, 30, f"Page {doc.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(output, pagesize=LETTER, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=BAND_HEIGHT + 22, bottomMargin=46,
                                 title=f"{provider['displayName']} {bill['title']} {bill['accountNumber']} {bill['period']['start']:%Y-%m}",
                                 author=provider["displayName"], subject="Northlake synthetic customer bill", creator="generators/render_bills.py")
    document.build(bill_story(bill, provider, scenario, wrap_meter_cells=wrap_meter_cells), onFirstPage=page, onLaterPages=page)


def rendered_bills(root=ROOT, only=None):
    bills = [(bill, source) for bill, source in load_bills(root) if only is None or source == Path(only)]
    scenario = read_yaml(root, SCENARIO)
    providers = {p["id"]: p for p in (yaml.safe_load(f.read_text(encoding="utf-8")) for f in sorted((root / "data/providers").glob("*.yaml")))}
    check_bills([bill for bill, _ in bills])
    result = {}
    for bill, source in bills:
        assert bill["file"] not in result, f"{bill['id']}: another bill already renders {bill['file']}"
        buffer = io.BytesIO()
        render_bill(bill, providers[bill["providerId"]], scenario, source, buffer)
        result[bill["file"]] = buffer.getvalue()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if a checked-in bill differs from its source")
    parser.add_argument("--only", help="Check and render only the bills of one source file, e.g. data/bills/sierra-gas-utility-v1.yaml")
    args = parser.parse_args()
    stale = []
    for path, content in rendered_bills(only=args.only).items():
        target = ROOT / path
        if not target.exists() or target.read_bytes() != content:
            stale.append(path)
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    if args.check and stale:
        parser.exit(1, "Stale bills; run python generators/render_bills.py:\n" + "\n".join(stale) + "\n")
    print("Bills match their source." if args.check else "Rendered bills: " + (", ".join(stale) or "already current"))


if __name__ == "__main__":
    main()
