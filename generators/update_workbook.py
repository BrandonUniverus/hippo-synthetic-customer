"""Update the customer Data Collection workbook from the packet tables.

Only the generated worksheets change. The later-phase tabs (Chart of Accounts,
Users & Access, Tenants & Leases, Sustainability, Projects) are preserved as
they are, and a repeat run with unchanged sources leaves the file untouched.
Pass --output to write elsewhere, for example while Excel holds the workbook.
"""

import argparse
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation, DataValidationList
from openpyxl.worksheet.table import Table, TableStyleInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generators.northlake_packet import ROOT, build_packet  # noqa: E402

TARGET = ROOT / "outputs/northlake-university/data-collection-workbook.xlsx"
STATUS_CHOICES = '"Documented,Pending,Planned,Sample supplied,Confirmed,UI acceptance pending,Ongoing"'
LEGACY_STATUS_CHOICES = '"Draft,Needs review,Confirmed,Not applicable"'
LEGACY_SHEETS = ["Organization Units"]
TITLE_FILL, DESCRIPTION_FILL, HEADER_FILL, BAND_FILL, TEXT = "244539", "EAF1ED", "3C6B5C", "EEF6F0", "203A31"
DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIDTH_RULES = [
    (r"^Parent Path$", 54),
    (r"^Node Name$|^Parent Node$|^Department$|^Responsible Department$", 27.5),
    (r"^Level$|^EEM Type$", 16),
    (r"^Unit$|^Units$|^Floor$|Area Unit|Multiplier|^Rate$|Gross Area|Interval Minutes", 12.5),
    (r"Notes|Requirement|Convention|Channel / Source|Occupancy|Boundary|What Northlake|Purpose", 41),
    (r"Meter|Measurement|Source|Device / Station|Account / Agreement|Requested Total|Email|Point$", 37.5),
    (r"Provider|Counterparty|Scope|Location|Property|Service Name|Organization|^Company$|^Building$", 27.5),
    (r"Date|Effective", 19),
]


def column_width(header):
    return next((width for pattern, width in WIDTH_RULES if re.search(pattern, header)), 22)


def cell_value(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str) and DATE_TEXT.match(value):
        return datetime.fromisoformat(value)
    return None if value == "" or value is None else value


def desired_values(definition):
    return [list(definition["headers"])] + [[cell_value(v) for v in row] for row in definition["rows"]]


def values_of(ws):
    return [[cell.value for cell in row] for row in ws.iter_rows()]


def table_name(sheet_name):
    return re.sub(r"[^A-Za-z0-9]", "", sheet_name) + "Table"


def is_current(ws, name, definition):
    columns, last_row = len(definition["headers"]), len(definition["rows"]) + 4
    if ws.max_row != last_row or ws.max_column != columns:
        return False
    if ws["A1"].value != name or ws["A2"].value != definition["description"]:
        return False
    if {table.ref for table in ws.tables.values()} != {f"A4:{get_column_letter(columns)}{last_row}"}:
        return False
    current = [[ws.cell(row=r, column=c).value for c in range(1, columns + 1)] for r in range(4, last_row + 1)]
    return current == desired_values(definition)


def text_of(value):
    return value.strftime("%m/%d/%Y") if isinstance(value, datetime) else "" if value is None else str(value)


def write_sheet(ws, name, definition, table_style):
    headers, description = definition["headers"], definition["description"]
    rows = desired_values(definition)[1:]
    columns, last_row = len(headers), len(rows) + 4
    end = get_column_letter(columns)
    widths = [column_width(header) for header in headers]

    for merged in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(merged))
    for existing in list(ws.tables):
        del ws.tables[existing]
    kept_validations = [dv for dv in ws.data_validations.dataValidation if dv.formula1 not in {STATUS_CHOICES, LEGACY_STATUS_CHOICES}]
    ws.data_validations = DataValidationList()
    if ws.max_row:
        ws.delete_rows(1, ws.max_row)
    for index in [r for r in ws.row_dimensions if r > last_row]:
        del ws.row_dimensions[index]

    ws["A1"] = name
    ws["A2"] = description
    for column, header in enumerate(headers, 1):
        ws.cell(row=4, column=column, value=header)
    for index, row in enumerate(rows, 5):
        for column, value in enumerate(row, 1):
            ws.cell(row=index, column=column, value=value)

    thin = Side(style="thin", color="C9D6CF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    body_font = Font(name="Arial", size=10, color=TEXT)
    for row in ws.iter_rows(min_row=1, max_row=last_row, max_col=columns):
        for cell in row:
            cell.font = body_font
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    for cell in ws.iter_rows(min_row=1, max_row=1, max_col=columns).__next__():
        cell.fill = PatternFill("solid", fgColor=TITLE_FILL)
        cell.font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
    for cell in ws.iter_rows(min_row=2, max_row=2, max_col=columns).__next__():
        cell.fill = PatternFill("solid", fgColor=DESCRIPTION_FILL)
    for cell in ws.iter_rows(min_row=4, max_row=4, max_col=columns).__next__():
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = border
    for index, row in enumerate(ws.iter_rows(min_row=5, max_row=last_row, max_col=columns)):
        fill = PatternFill("solid", fgColor=BAND_FILL) if index % 2 == 0 else PatternFill(fill_type=None)
        for cell in row:
            cell.fill = fill
            cell.border = border
    for column, header in enumerate(headers, 1):
        letter = get_column_letter(column)
        ws.column_dimensions[letter].width = widths[column - 1]
        body = [row[column - 1] for row in rows]
        number_format = None
        if re.search("Date", header):
            number_format = "mm/dd/yyyy"
        elif header == "Rate":
            number_format = "0.000"
        elif re.search("Gross Area|Multiplier|Interval Minutes", header):
            number_format = "#,##0" if all(isinstance(v, int) or v is None for v in body) else "#,##0.00"
        if number_format:
            for index in range(5, last_row + 1):
                ws.cell(row=index, column=column).number_format = number_format
        if re.search(r"Review Status|^Status$", header):
            validation = DataValidation(type="list", formula1=STATUS_CHOICES, allow_blank=True)
            validation.add(f"{letter}5:{letter}{max(100, last_row)}")
            ws.add_data_validation(validation)
    for validation in kept_validations:
        ws.add_data_validation(validation)

    ws.merge_cells(f"A1:{end}1")
    ws.merge_cells(f"A2:{end}2")
    total_width = sum(widths)
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = max(33, 13 * math.ceil(len(description) / max(20, total_width * 1.1)) + 12)
    ws.row_dimensions[4].height = 33
    for index, row in enumerate(rows, 5):
        lines = max([1] + [math.ceil(len(text_of(value)) / max(8, widths[column] - 2)) for column, value in enumerate(row)])
        ws.row_dimensions[index].height = max(27, 13 * lines + 8)
    ws.freeze_panes = ("C5" if name == "Hierarchy" else "B5") if len(rows) > 8 else None
    ws.sheet_view.showGridLines = False
    table = Table(displayName=table_name(name), ref=f"A4:{end}{last_row}")
    table.tableStyleInfo = TableStyleInfo(name=table_style or "TableStyleMedium4", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    ws.add_table(table)


def insertion_index(wb, generated, name):
    """Place a new generated sheet after the nearest earlier generated sheet that already exists."""
    names = list(generated)
    for earlier in reversed(names[: names.index(name)]):
        if earlier in wb.sheetnames:
            return wb.sheetnames.index(earlier) + 1
    return len(wb.sheetnames)


def verify(path, generated, snapshot):
    wb = openpyxl.load_workbook(path)
    for name, definition in generated.items():
        assert is_current(wb[name], name, definition), f"Saved table values differ: {name}"
    for name, values in snapshot.items():
        assert name in wb.sheetnames and values_of(wb[name]) == values, f"Unrelated sheet changed: {name}"
    assert wb.sheetnames[:2] == ["Instructions", "Hierarchy"], "Hierarchy must follow Instructions"
    return wb.sheetnames


def update_workbook(target=TARGET, output=None, packet=None):
    target, output = Path(target), Path(output or target)
    packet = packet or build_packet()
    generated = packet["sheets"]
    wb = openpyxl.load_workbook(target)
    snapshot = {ws.title: values_of(ws) for ws in wb.worksheets if ws.title not in generated and ws.title not in LEGACY_SHEETS}
    changed = []
    for name, definition in generated.items():
        if name in wb.sheetnames:
            ws = wb[name]
            if is_current(ws, name, definition):
                continue
            style = next((table.tableStyleInfo.name for table in ws.tables.values() if table.tableStyleInfo), None)
        else:
            ws = wb.create_sheet(name, insertion_index(wb, generated, name))
            style = None
        write_sheet(ws, name, definition, style)
        changed.append(name)
    for name in LEGACY_SHEETS:
        if name in wb.sheetnames:
            wb.remove(wb[name])
            changed.append(f"{name} (removed)")
    if wb.sheetnames.index("Hierarchy") != 1:
        wb.move_sheet(wb["Hierarchy"], offset=1 - wb.sheetnames.index("Hierarchy"))
        changed.append("sheet order")
    if not changed and output == target:
        print(f"{target.name}: all generated tables are current; no file changes.")
        return changed
    wb.save(output)
    order = verify(output, generated, snapshot)
    print(f"{output.name}: updated {len(changed)} sheets ({', '.join(changed)}); {len(snapshot)} other sheets preserved; {len(order)} sheets total; reopened successfully.")
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write the updated workbook to this path instead of updating it in place")
    update_workbook(output=parser.parse_args().output)
