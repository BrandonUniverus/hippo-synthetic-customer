"""Render the Stage 2 import workbooks from the Stage 2 YAML.

The three workbooks beside the YAML are the input of the My Import handler (EEMSuite repository,
Database/EEMSuite/Schemas/Northlake/Stage2Import), and between them they carry every Stage 2 field of every
billing account, meter and point:

  01-billing-accounts.xlsx  BillingAccounts (definitions, both addresses with coordinates, the contact, the
                            first Active date and the account note)
  03-meters.xlsx            Meters (with the node note), Keywords (the keyword values the meters use, so the
                            catalog entries Stage 2 adds are created explicitly), MeterKeywords, MeterStatus
  04-points.xlsx            Points, the one placed under a building included

They are a generated view of the YAML in that handler's column contract, never a second source of truth.
The handler matches names exactly, so values are projected into what it compares: a remit address without the
country the combo appends, a date as ISO text (My Import passes a date cell on as an Excel serial number).
A unit stays the Units list entry "Name - (abbreviation)", as the YAML writes it, because the abbreviation
alone can name two units of one measure type (Natural Gas lists a Volume and an Energy ccf).
My Import also removes every apostrophe from a cell, so a value with one is refused here.

Run: python -m generators.stage2_workbooks            (writes the three workbooks)
     python -m generators.stage2_workbooks --check    (exit 1 when a workbook is stale)
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "implementation" / "stage-2-hierarchy"
COMPANY_ORDER = {"Northlake University": 0, "Cedar Row Apartments": 1, "Northlake Thermal Plant": 2}
HEADERS = {
    "BillingAccounts": ["Company", "AccountNumber", "PreviousAccountNumber", "Description", "CurrencyUnit", "UtilityProvider",
                        "BillServiceType", "BillEntryType", "BillInvoiceTemplate", "RemitAddress", "ServiceAddress",
                        "ServiceCity", "ServiceRegion", "ServicePostalCode", "ServiceCountry", "ServiceLatitude",
                        "ServiceLongitude", "AccountAddress", "AccountAddress2", "AccountCity", "AccountRegion",
                        "AccountPostalCode", "AccountCountry", "ContactFirstName", "ContactLastName", "ContactTitle",
                        "ContactPhone", "ContactCell", "ContactEmail", "ActiveAsOf", "Note"],
    "Meters": ["Company", "MeterNumber", "Description", "Site", "Building", "AccountNumber", "MeasureType",
               "ProviderMeterNumber", "MeterMultiplier", "UtilityProvider", "BillCycle", "Note"],
    "Keywords": ["KeywordType", "KeywordValue"],
    "MeterKeywords": ["Company", "MeterNumber", "KeywordType", "KeywordValue"],
    "MeterStatus": ["Company", "MeterNumber", "Status", "AsOfDate"],
    "Points": ["Company", "MeterNumber", "Site", "Building", "Description", "ReadingType", "MeasureType", "Unit",
               "ArchiveInterval", "Index"],
}
WORKBOOKS = {
    "01-billing-accounts.xlsx": ["BillingAccounts"],
    "03-meters.xlsx": ["Meters", "Keywords", "MeterKeywords", "MeterStatus"],
    "04-points.xlsx": ["Points"],
}


def load(name):
    return yaml.safe_load((STAGE / name).read_text(encoding="utf-8"))["records"]


def blank(value):
    return None if value in ("", None) else value


def text(value):
    """A number or date written as the text the handler parses (no Excel number format, no date serial)."""
    return None if value in ("", None) else str(value)


def units_list_entry(unit):
    if not re.fullmatch(r".+ - \(.+\)", unit):
        raise ValueError(f"Unit is not a Units list entry: {unit!r}")
    return unit


def account_rows(accounts):
    rows = []
    for record in sorted(accounts, key=lambda r: (COMPANY_ORDER[r["Company"]], r["Definitions"]["Account Number"])):
        definition, service, account = record["Definitions"], record["Service Address"], record["Account Address"]
        contact = record.get("Account Contact") or {}
        notes = record.get("Notes") or []
        if len(notes) > 1:
            raise ValueError(f"{record['key']}: the workbook carries one account note; the recipe has {len(notes)}")
        if [entry["Status"] for entry in record["Status"]] != ["Active Billing Account"]:
            raise ValueError(f"{record['key']}: the workbook carries one Active status row; the recipe has {record['Status']}")
        rows.append([record["Company"], definition["Account Number"], blank(definition.get("Previous Account Number")),
                     definition["Description"], definition["Currency Unit"], definition["Utility Provider"],
                     definition["Bill Service Type"], definition["Bill Entry Type"], definition["Bill Invoice Template"],
                     re.sub(r", USA$", "", definition["Remit Address"]), service["Address"], service["City"], service["Region"],
                     service["Postal Code"], service["Country"], text(service.get("Latitude")), text(service.get("Longitude")),
                     account["Address"], blank(account.get("Address 2")), account["City"], account["Region"],
                     account["Postal Code"], account["Country"], blank(contact.get("First Name")), blank(contact.get("Last Name")),
                     blank(contact.get("Title")), blank(contact.get("Phone")), blank(contact.get("Cell")),
                     blank(contact.get("Email")), text(record["Status"][0]["As of Date"]), notes[0]["Note"] if notes else None])
    return rows


def meter_place(record, places):
    place = places[record["Building"]]
    site, building = (place["Parent"], record["Building"]) if "Parent" in place else (record["Building"], None)
    return place["Company"], site, building


def meter_rows(meters, accounts, places):
    account_numbers = {r["Definitions"]["Account Number"] for r in accounts}
    rows = []
    for record in meters:
        definition = record["Meter Definition"]
        if definition["Billing Account"] and definition["Billing Account"] not in account_numbers:
            raise ValueError(f"Meter {definition['Meter Number']}: no billing account {definition['Billing Account']}")
        company, site, building = meter_place(record, places)
        rows.append([company, definition["Meter Number"], definition["Description"], site, building,
                     blank(definition["Billing Account"]), definition["Measure Type"],
                     blank(definition["Provider Meter Number"]), blank(definition["Meter Multiplier"]),
                     blank(definition["Utility Provider"]), blank(definition["Bill Cycle"]), blank(record.get("Notes"))])
    return sorted(rows, key=lambda row: (COMPANY_ORDER[row[0]], row[4] or "", row[1]))


def keyword_rows(meters):
    return [list(pair) for pair in sorted({(keyword["Type"], keyword["Attribute"]) for record in meters for keyword in record.get("Keywords") or []})]


def meter_keyword_rows(meters, places):
    rows = []
    for record in meters:
        company = meter_place(record, places)[0]
        types = [keyword["Type"] for keyword in record.get("Keywords") or []]
        if len(types) != len(set(types)):
            raise ValueError(f"{record['key']}: a keyword type is listed twice")
        rows += [[company, record["Meter Definition"]["Meter Number"], keyword["Type"], keyword["Attribute"]]
                 for keyword in record.get("Keywords") or []]
    return sorted(rows, key=lambda row: (COMPANY_ORDER[row[0]], row[1], row[2]))


def meter_status_rows(meters, places):
    rows = []
    for record in meters:
        company = meter_place(record, places)[0]
        history = sorted(record.get("Status") or [], key=lambda entry: entry["As of Date"])
        rows += [[company, record["Meter Definition"]["Meter Number"], entry["Status"], text(entry["As of Date"])] for entry in history]
    return sorted(rows, key=lambda row: (COMPANY_ORDER[row[0]], row[1], row[3]))


def point_rows(points, meters, places):
    rows = []
    for record in points:
        definition = record["Point Definition"]
        if "Meter" in record:
            meter = meters[record["Meter"]["Meter Number"]]
            if meter["Meter Definition"]["Description"] != record["Meter"]["Description"]:
                raise ValueError(f"Point {record['key']}: meter {record['Meter']} does not match 03-meters.yaml")
            company, number, site, building = places[meter["Building"]]["Company"], meter["Meter Definition"]["Meter Number"], None, None
        else:  # placed directly under a building (the Student Center activity index)
            place = places[record["Parent"]]
            company, number = place["Company"], None
            site, building = (place["Parent"], record["Parent"]) if "Parent" in place else (record["Parent"], None)
        rows.append([company, number, site, building, definition["Description"], definition["Reading Type"],
                     definition["Measure Type"], units_list_entry(definition["Unit"]), blank(definition["Archive Interval"]),
                     blank(definition["Index"])])
    return sorted(rows, key=lambda row: (COMPANY_ORDER[row[0]], row[1] or "", row[3] or "", row[4]))


def render(sheets):
    book = openpyxl.Workbook()
    book.remove(book.active)
    for sheet, rows in sheets.items():
        worksheet = book.create_sheet(sheet)
        worksheet.append(HEADERS[sheet])
        for row in rows:
            if any(isinstance(value, str) and "'" in value for value in row):
                raise ValueError(f"{sheet}: My Import removes apostrophes, so this row would not import as written: {row}")
            worksheet.append(row)
    book.properties.creator = "generators/stage2_workbooks.py"
    return book


def cells(path_or_book):
    book = path_or_book if isinstance(path_or_book, openpyxl.Workbook) else openpyxl.load_workbook(path_or_book, data_only=True)
    return [(sheet.title, [list(row) for row in sheet.iter_rows(values_only=True)]) for sheet in book.worksheets]


def workbooks():
    accounts, meters_list, points = load("01-billing-accounts.yaml"), load("03-meters.yaml"), load("04-points.yaml")
    places = {r["Definitions"]["Description"]: r for r in load("02-sites-and-buildings.yaml")}
    meters = {r["Meter Definition"]["Meter Number"]: r for r in meters_list}
    rows = {
        "BillingAccounts": account_rows(accounts),
        "Meters": meter_rows(meters_list, accounts, places),
        "Keywords": keyword_rows(meters_list),
        "MeterKeywords": meter_keyword_rows(meters_list, places),
        "MeterStatus": meter_status_rows(meters_list, places),
        "Points": point_rows(points, meters, places),
    }
    return {name: render({sheet: rows[sheet] for sheet in sheets}) for name, sheets in WORKBOOKS.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    targets = workbooks()
    stale = [name for name, book in targets.items()
             if not (STAGE / name).exists() or cells(STAGE / name) != cells(io.BytesIO(_bytes(book)))]
    if args.check:
        if stale:
            parser.exit(1, "Stale Stage 2 workbooks; run python -m generators.stage2_workbooks:\n" + "\n".join(stale) + "\n")
        print("Stage 2 workbooks match the YAML.")
        return
    for name in stale:
        targets[name].save(STAGE / name)
    print("Wrote: " + (", ".join(stale) or "nothing; already current"))


def _bytes(book):
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


if __name__ == "__main__":
    sys.exit(main())
