"""Invoices and import artifacts derived from the shared Northlake measurement model."""
from __future__ import annotations

import calendar
import copy
import csv
import io
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from .tariffs import annual_factor, decimal, json_bytes, money, tariff_for, tariff_rate


def billing_periods(account, as_of, since_date=None):
    """Completed issued supplier cycles. December 2023 is explicit supporting history."""
    provider = account["providerId"]
    cedar = account.get("siteId") == "cedar_row_apartments"
    read_day = 5 if provider == "valley_electric_district" else 15 if provider == "sierra_gas_utility" or (provider == "river_city_utilities" and cedar) else 1
    lag = {"valley_electric_district": 2, "river_city_utilities": 3, "sierra_gas_utility": 4,
           "northlake_thermal_plant": 4, "helios_onsite_solar": 4, "ridgeline_wind": 0}[provider]
    if cedar:
        lag = 4
    opening = account.get("effectiveStart", date(2024, 1, 1))
    result = []
    for year in range(2024, as_of.year + 1):
        for month in range(1, 13):
            if read_day == 1:
                start = date(year, month, 1)
                end = date(year, month, calendar.monthrange(year, month)[1])
            else:
                end = date(year, month, read_day - 1)
                previous = date(year, month, 1) - timedelta(days=1)
                start = date(previous.year, previous.month, read_day)
            if opening > date(2024, 1, 1):
                if end < opening:
                    continue
                # The first generator bill deliberately spans July 1 through August 4.
                if account["id"] == "ved_ridgeline_generator" and (year, month) == (2024, 7):
                    continue
                if account["id"] == "ved_ridgeline_generator" and (year, month) == (2024, 8):
                    start = opening
                else:
                    start = max(start, opening)
            issued = end + timedelta(days=lag)
            if issued > as_of or (since_date and issued < since_date):
                continue
            if account["id"] == "sgu_library" and (year, month) == (2025, 12):
                continue
            result.append({"start": start, "end": end, "fiscal_year": year, "fiscal_period": month, "issued_on": issued})
    return result


def _charge(code, quantity, rate, unit, **extra):
    quantity, rate = decimal(quantity), decimal(rate)
    return {"code": code, "description": code.replace("_", " "), "quantity": quantity,
            "unit": unit, "rate": rate, "amount": money(quantity * rate), **extra}


def _percent(code, lines, percentage):
    return {"code": code, "description": code.replace("_", " "),
            "amount": money(sum((decimal(line["amount"]) for line in lines), Decimal(0)) * decimal(percentage) / 100)}


def _generated_bill(model, account, period, anchors):
    start, end = period["start"], period["end"]
    provider = model.providers[account["providerId"]]
    metrics = model.period_metrics(account["id"], start, end)
    if not isinstance(metrics, dict):
        raise ValueError(f"{account['id']}: period_metrics must return the shared measurement dictionary")
    schedules = account.get("rateScheduleIds", [account.get("rateScheduleId")])
    schedules = [item for item in schedules if item]
    rate = lambda schedule, component, year=end.year: tariff_rate(provider, schedule, component, max(2024, year))
    value = lambda key: decimal(metrics[key])
    lines = []
    family = account["providerId"]
    if family == "valley_electric_district":
        if "VED-AL-1" in schedules:
            lines.append(_charge("area_lighting", sum(meter.get("fixtureCount", 0) for meter in account["meters"]), rate("VED-AL-1", "fixtureCharge"), "fixtures"))
            lines.append(_percent("utility_users_tax", lines, 5))
        elif "VED-GEN-IC" in schedules:
            lines.append(_charge("generator_customer_charge", 1, rate("VED-GEN-IC", "customerCharge"), "month"))
            lines.append(_charge("station_service_energy", value("delivered_kwh"), rate("VED-GEN-IC", "stationServiceEnergy"), "kWh"))
            allowance = (value("received_kwh") * Decimal("0.3286841")).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            reactive = max(Decimal(0), value("reactive_kvarh") - allowance)
            if reactive:
                lines.append(_charge("reactive_power_charge", reactive, rate("VED-GEN-IC", "reactivePower"), "kVArh"))
            credit = _charge("generation_credit", value("received_kwh"), rate("VED-GEN-IC", "generationCredit"), "kWh")
            lines.extend([credit, {"code": "bct_credit_transferred", "description": "Generation credit transferred to Central Plant", "amount": -credit["amount"]}])
            lines.append(_percent("utility_users_tax", lines, 5))
        else:
            schedule = "VED-TOU-PRI" if "VED-TOU-PRI" in schedules else "VED-TOU-GS"
            cursor = start
            while cursor <= end:
                boundary = min(end, date(cursor.year, 12, 31))
                part = metrics if (cursor, boundary) == (start, end) else model.period_metrics(account["id"], cursor, boundary)
                fraction = Decimal((boundary - cursor).days + 1) / Decimal((end - start).days + 1)
                for bucket in ("peak", "part_peak", "off_peak"):
                    quantity = decimal(part["electric_tou_kwh"][bucket])
                    if quantity:
                        lines.append(_charge(f"energy_{bucket}", quantity, rate(schedule, f"energy.{bucket}", cursor.year), "kWh",
                                             itemPeriod={"start": cursor, "end": boundary}))
                demand = (value("electric_peak_kw") * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                lines.append(_charge("demand_charge", demand, rate(schedule, "demand", cursor.year), "kW", itemPeriod={"start": cursor, "end": boundary}))
                lines.append(_charge("facility_charge", fraction.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP), rate(schedule, "facilityCharge", cursor.year), "month",
                                     itemPeriod={"start": cursor, "end": boundary}))
                cursor = boundary + timedelta(days=1)
            lines.append(_percent("public_purpose_program", [line for line in lines if line["code"].startswith("energy_")], Decimal("1.5")))
            taxable = list(lines)
            if account["id"] == "ved_central_plant" and end >= date(2024, 9, 4):
                generator = model.accounts["ved_ridgeline_generator"]
                previous = next((candidate for candidate in reversed(billing_periods(generator, end)) if candidate["end"] < start), None)
                if previous:
                    key = (generator["id"], previous["start"], previous["end"])
                    upstream = anchors[key][0] if key in anchors else _generated_bill(model, generator, previous, anchors)
                    transfer = next(line for line in upstream["lines"] if line["code"] == "bct_credit_transferred")
                    lines.extend([{"code": "bct_credit_received", "description": "Previous generator invoice credit", "amount": -decimal(transfer["amount"])},
                                  _charge("bct_administrative_fee", 1, rate("VED-BCT", "administrativeFee"), "month")])
            lines.append(_percent("utility_users_tax", taxable, 5))
    elif family == "sierra_gas_utility":
        schedule = "SGU-GL-1" if "SGU-GL-1" in schedules else "SGU-GN-1"
        season = "winter" if end.month in (11, 12, 1, 2, 3) else "summer"
        lines = [_charge("customer_charge", 1, rate(schedule, "customerCharge"), "month"),
                 _charge("gas_commodity", value("gas_therms"), rate(schedule, f"commodity.{season}"), "therms"),
                 _charge("gas_transport", value("gas_therms"), rate(schedule, "transport"), "therms")]
        lines.append(_percent("public_purpose_surcharge", lines[1:], Decimal("1.5")))
        lines.append(_percent("utility_users_tax", lines, 5))
    elif family == "river_city_utilities":
        if "RCU-FIRE" in schedules:
            for meter in account["meters"]:
                lines.append(_charge("fire_service", 1, rate("RCU-FIRE", f"lineCharge.{meter['meterSize']}"), "month", meterNumber=meter["syntheticMeterNumber"]))
        elif "RCU-IRR" in schedules:
            for meter in account["meters"]:
                lines.append(_charge("irrigation_meter_charge", 1, rate("RCU-IRR", f"meterCharge.{meter['meterSize']}"), "month", meterNumber=meter["syntheticMeterNumber"]))
            if value("water_kgal"):
                lines.append(_charge("irrigation_volume", value("water_kgal"), rate("RCU-IRR", "volume"), "kgal"))
        else:
            meter = account["meters"][0]
            quantity = value("water_kgal")
            lines.append(_charge("water_meter_charge", 1, rate("RCU-W-TIER", f"meterCharge.{meter['meterSize']}"), "month"))
            for index, capacity in enumerate((Decimal(50), Decimal(150), quantity)):
                portion = min(quantity, capacity)
                if portion:
                    lines.append(_charge(f"water_tier{index + 1}", portion, rate("RCU-W-TIER", f"tiers.{index}"), "kgal"))
                quantity -= portion
            if "RCU-S-VOL" in schedules:
                lines.extend([_charge("sewer_base", 1, rate("RCU-S-VOL", "baseCharge"), "month"),
                              _charge("sewer_volume", value("water_kgal"), rate("RCU-S-VOL", "volume"), "kgal")])
            if "RCU-SW-ERU" in schedules:
                lines.append(_charge("stormwater_eru", meter.get("eruCount", 0), rate("RCU-SW-ERU", "eruCharge"), "ERU"))
    elif family == "northlake_thermal_plant":
        if "NTP-ALLOC-CHW" in schedules:
            lines.extend([_charge("chilled_water_consumption", value("chilled_water_ton_hours"), rate("NTP-ALLOC-CHW", "consumption"), "ton-hr"),
                          _charge("chilled_water_demand", value("chilled_water_peak_tons"), rate("NTP-ALLOC-CHW", "demand"), "ton")])
        if "NTP-ALLOC-STEAM" in schedules and value("steam_klb"):
            lines.append(_charge("steam_consumption", value("steam_klb"), rate("NTP-ALLOC-STEAM", "consumption"), "klb"))
        building = next(building for site in model.scenario["sites"] for building in site["buildings"] if building["id"] == account["buildingId"])
        base_om = getattr(model, "assumptions", {}).get("profiles", {}).get("fixed_plant_om_per_120000_sqft", 340)
        fixed = (decimal(base_om) * decimal(building.get("grossFloorAreaSqft", 120000)) / Decimal(120000) / 10).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 10
        lines.append({"code": "fixed_oandm_allocation", "description": "Fixed plant operations and maintenance share", "amount": money(fixed * annual_factor(family, "fixed_oandm", end.year))})
    elif family == "helios_onsite_solar":
        lines = [_charge("ppa_energy", value("generated_kwh"), rate("HOS-PPA-2024", "ppaEnergy"), "kWh"),
                 _charge("net_metering_credit", value("exported_kwh"), -abs(rate("HOS-PPA-2024", "netMeteringCredit")), "kWh"),
                 {"code": "rec_transfer", "description": "REC transfer (informational)", "quantity": (value("generated_kwh") / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP), "unit": "RECs", "amount": Decimal(0)}]
    elif family == "ridgeline_wind":
        lines = [_charge("transfer_energy", value("generated_kwh"), rate("RWL-XFER-2024", "transferEnergy"), "kWh"),
                 _charge("research_credit", 1, rate("RWL-XFER-2024", "researchCredit"), "month")]
    else:
        raise ValueError(f"Unsupported provider {family}")
    companies = {company["id"]: company["displayName"] for company in model.scenario["companies"]}
    site = next(site for site in model.scenario["sites"] if site["id"] == account["siteId"])
    number = account["syntheticAccountNumber"]
    if account["id"] == "rcu_cedar_row_a" and end < date(2024, 7, 1):
        number = "SYN-RCU-A-0030103"
    # Anchor IDs describe source documents, sometimes by service-start month.
    # A separate namespace prevents an ordinary fiscal-month invoice colliding
    # with a later anchor (notably the Ridgeline Jan-2025/FEB posting sample).
    bill_id = f"{account['id']}_generated_{period['fiscal_year']}_{period['fiscal_period']:02d}"
    rate_years = sorted({max(2024, start.year), end.year}) if family == "valley_electric_district" and "VED-GEN-IC" not in schedules else [end.year]
    published_schedules = list(dict.fromkeys(tariff_for(provider, schedule, year)["id"] for year in rate_years for schedule in schedules))
    bill = {"id": bill_id, "file": f"bills/{family}/{account['id']}/{bill_id}.pdf", "providerId": family,
            "accountId": account["id"], "accountNumber": number, "customer": companies[site["ownerCompanyId"]],
            "invoiceNumber": f"SYN-{provider['shortName']}-{account['id']}-{period['fiscal_year']}{period['fiscal_period']:02d}-01",
            "title": "Synthetic utility statement", "rateSchedules": published_schedules,
            "tariffFiles": [f"tariffs/{family}/{year}.pdf" for year in rate_years], "billDate": period["issued_on"],
            "dueDate": None if family in ("northlake_thermal_plant", "ridgeline_wind") else period["issued_on"] + timedelta(days=30),
            "period": {"start": start, "end": end}, "meters": copy.deepcopy(metrics["meters"]),
            "lines": lines, "total": sum((money(line["amount"]) for line in lines), Decimal(0)),
            "notice": "Fictional invoice derived from the shared Northlake measurement model. Historical anchors are retained separately; all additional load profiles and post-2025 rates are declared synthetic assumptions.",
            "fiscalYear": period["fiscal_year"], "fiscalPeriod": period["fiscal_period"]}
    bill["notice"] = f"Invoice {bill['invoiceNumber']}. " + bill["notice"]
    return bill


def invoices(model, as_of_date, since_date=None):
    """Yield all source invoice versions once; Stage 7 statements remain references."""
    if not hasattr(model, "_source_invoice_anchors"):
        from generators.render_bills import check_bills, load_bills
        source_bills = getattr(model, "anchor_bills", None)
        if source_bills is None:
            source_bills = [bill for bill, _ in load_bills(model.root)]
        check_bills(source_bills)
        anchors = {}
        for bill in source_bills:
            anchors.setdefault((bill["accountId"], bill["period"]["start"], bill["period"]["end"]), []).append(bill)
        model._source_invoice_anchors = (source_bills, anchors)
    source_bills, anchors = model._source_invoice_anchors
    emitted = set()
    for account in model.accounts.values():
        for period in billing_periods(account, as_of_date, since_date):
            key = (account["id"], period["start"], period["end"])
            if key in anchors:
                for anchor in anchors[key]:
                    if anchor["billDate"] > as_of_date or (since_date and anchor["billDate"] < since_date):
                        continue
                    bill = copy.deepcopy(anchor)
                    bill.update(fiscalYear=period["fiscal_year"], fiscalPeriod=period["fiscal_period"], anchor=True)
                    emitted.add(bill["id"])
                    yield bill
            else:
                yield _generated_bill(model, account, period, anchors)
    # Anchor issue dates may differ from synthetic defaults or be a later corrected version.
    for anchor in source_bills:
        if anchor["id"] not in emitted and anchor["billDate"] <= as_of_date and (not since_date or anchor["billDate"] >= since_date):
            bill = copy.deepcopy(anchor)
            bill.update(fiscalYear=anchor["period"]["end"].year, fiscalPeriod=anchor["period"]["end"].month, anchor=True)
            yield bill


def import_items(bill, account):
    """Keep printed lines separate from richer meter-specific importer items."""
    result = []
    meters = bill.get("meters", [])
    for line in bill["lines"]:
        if line["code"] == "rec_transfer":
            continue  # Informational certificates are not a commodity purchase.
        quantity = decimal(line.get("quantity", 0))
        if line["code"] in ("generation_credit", "bct_credit_transferred", "bct_credit_received"):
            quantity = Decimal(0)  # Established Northlake dollars-only export policy.
        item = {"meter": line.get("meterNumber") or (account["meters"][0]["syntheticMeterNumber"] if len(account["meters"]) == 1 else bill["accountNumber"]),
                "code": line["code"], "quantity": quantity, "amount": money(line["amount"]),
                "unit": line.get("unit", ""), "estimate": bool(line.get("estimate")),
                "start": line.get("itemPeriod", bill["period"])["start"], "end": line.get("itemPeriod", bill["period"])["end"]}
        if bill["providerId"] == "northlake_thermal_plant":
            suffix = "steam" if line["code"].startswith("steam_") else "chilled_water"
            match = next((meter for meter in account["meters"] if suffix in meter["id"]), None)
            if match:
                item["meter"] = match["syntheticMeterNumber"]
        # Printed VED energy can aggregate two physical services or an exchanged meter.
        matched = []
        if bill.get("anchor") and line["code"].startswith("energy_") and len({meter["meterNumber"] for meter in meters}) > 1:
            bucket = line["code"].removeprefix("energy_")
            for meter in meters:
                channel = meter.get("channel", "").lower()
                if ((bucket == "peak" and "on-peak" in channel) or (bucket == "part_peak" and "part-peak" in channel)
                        or (bucket == "off_peak" and "off-peak" in channel)):
                    matched.append(meter)
        if matched:
            if sum((decimal(meter["quantity"]) for meter in matched), Decimal(0)) != quantity:
                raise ValueError(f"{bill['id']}: physical meter quantities do not reconcile to {line['code']}")
            remaining = item["amount"]
            for index, meter in enumerate(matched):
                part = dict(item, meter=meter["meterNumber"], quantity=decimal(meter["quantity"]))
                part["amount"] = remaining if index == len(matched) - 1 else money(part["quantity"] * decimal(line["rate"]))
                remaining -= part["amount"]
                part.update(start=meter.get("readPeriod", bill["period"])["start"], end=meter.get("readPeriod", bill["period"])["end"])
                if "previous" in meter:
                    part.update(previous=decimal(meter["previous"]), current=decimal(meter["present"]), multiplier=decimal(meter.get("multiplier", 1)))
                result.append(part)
        else:
            if bill["id"] == "ved_library_2024_09":
                item["meter"] = "SYN-VED-M-0040103"
            result.append(item)
    if sum((item["amount"] for item in result), Decimal(0)) != money(bill["total"]):
        raise ValueError(f"{bill['id']}: importer item amounts do not match the statement")
    return result


def _bill_xml(bill, items):
    root = ET.Element("Bills")
    node = ET.SubElement(root, "Bill")
    fields = {"UniqueID": 1, "BillType": 0, "Provider": bill["providerCode"], "Scenario": "Actual", "CompanyName": bill["customer"],
              "InvoiceNumber": bill.get("invoiceNumber", ""), "FiscalYear": bill["fiscalYear"], "FiscalPeriod": bill["fiscalPeriod"],
              "InvoiceDate": bill["billDate"], "PeriodStart": bill["period"]["start"], "PeriodEnd": bill["period"]["end"],
              "DueDate": bill.get("dueDate"), "Account": bill["accountNumber"], "Location": bill.get("location", ""),
              "Amount": money(bill["total"]), "PreviousBalance": 0, "BillImportStatus": 0}
    for key, value in fields.items():
        if value is not None and value != "":
            ET.SubElement(node, key).text = str(value)
    rows = ET.SubElement(node, "BillItems")
    for item in items:
        row = ET.SubElement(rows, "BillItem")
        fields = {"Meter": item["meter"], "Description": item["code"], "Quantity": item["quantity"], "Amount": item["amount"],
                  "Multiplier": item.get("multiplier"), "PreviousReading": item.get("previous"), "CurrentReading": item.get("current"),
                  "BIStartDate": item["start"], "BIEndDate": item["end"]}
        for key, value in fields.items():
            if value is not None:
                ET.SubElement(row, key).text = str(value)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _bif(bill, items):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["//Provider", "Scenario", "CustomerName", "InvoiceNumber", "FiscalYear", "FiscalPeriod", "InvoiceDate", "PeriodStart", "PeriodEnd", "DueDate",
                     "Account", "Location", "Currency", "Amount", "PrevBalance", "EarMark", "Notes"] +
                    [field for index in range(1, len(items) + 1) for field in (f"Meter{index}", f"Descriptor{index}", f"Estimate{index}", f"Quantity{index}", f"Amount{index}")])
    row = [bill["providerCode"], "Actual", bill["customer"], bill.get("invoiceNumber", ""), bill["fiscalYear"], bill["fiscalPeriod"], bill["billDate"],
           bill["period"]["start"], bill["period"]["end"], bill.get("dueDate") or "", bill["accountNumber"], bill.get("location", ""), "$", money(bill["total"]), 0, "Y", ""]
    for item in items:
        # Estimate is source evidence only; the existing product ignores the flat flag.
        row.extend([item["meter"], item["code"], "Y" if item["estimate"] else "N", item["quantity"], item["amount"]])
    writer.writerow(row)
    return output.getvalue().encode("utf-8")


CSV_FIELDS = ["source_bill_id", "company_name", "invoice_number", "fiscal_year", "fiscal_period", "invoice_date", "period_start", "period_end",
              "due_date", "account_number", "location", "total_amount", "previous_balance"]
SLOTS = 16


def _provider_csv(bill, items):
    if len(items) > SLOTS:
        raise ValueError(f"{bill['id']}: {len(items)} items exceed the declared provider CSV slots ({SLOTS})")
    fields = CSV_FIELDS + [f"line_{index:02d}_{key}" for index in range(1, SLOTS + 1) for key in ("meter", "code", "quantity", "amount")]
    row = [bill["id"], bill["customer"], bill.get("invoiceNumber", ""), bill["fiscalYear"], bill["fiscalPeriod"], bill["billDate"],
           bill["period"]["start"], bill["period"]["end"], bill.get("dueDate") or "", bill["accountNumber"], bill.get("location", ""), money(bill["total"]), 0]
    for index in range(SLOTS):
        row.extend([items[index][key] for key in ("meter", "code", "quantity", "amount")] if index < len(items) else ["", "", "", ""])
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(fields)
    writer.writerow(row)
    # Delimited._CreateTable currently treats a final empty physical line as a row.
    return output.getvalue().rstrip("\n").encode("utf-8")


def provider_schema(code):
    root = ET.Element("Providers", ext=f"*{code}*.csv", extname="CSV Files", multiselect="false", interfacename="Delimited",
                      delimiter=",", fiscalyearoffset="0", fiscalmonthoffset="0", providercolumn="", startatrow="1")
    fields = {"Provider": f"[F]{code}", "Scenario": "[F]Actual", "CustomerName": "[C]company_name", "InvoiceNumber": "[C]invoice_number",
              "FiscalYear": "[C]fiscal_year", "FiscalPeriod": "[C]fiscal_period", "InvoiceDate": "[C]invoice_date", "PeriodStart": "[C]period_start",
              "PeriodEnd": "[C]period_end", "DueDate": "[C]due_date", "Account": "[C]account_number", "Location": "[C]location", "Currency": "[F]$",
              "Amount": "[C]total_amount", "PrevBalance": "[C]previous_balance", "EarMark": "[F]Y", "Notes": "", "Image": ""}
    for key, value in fields.items():
        attributes = {"dateformat": "yyyy-MM-dd", "daysoffset": "0", "customdate": ""} if key in ("InvoiceDate", "PeriodStart", "PeriodEnd", "DueDate") else {"gui": "false"} if key in ("FiscalYear", "FiscalPeriod") else {}
        ET.SubElement(root, key, **attributes).text = value
    ET.SubElement(root, "ColumnList", RequiredColumns="false")
    for index in range(1, SLOTS + 1):
        item = ET.SubElement(root, "BillItem", SaveAllValues="true")
        for name, column in (("Meter", "meter"), ("Description", "code"), ("Quantity", "quantity"), ("Amount", "amount")):
            ET.SubElement(item, name).text = f"[C]line_{index:02d}_{column}"
        ET.SubElement(item, "Estimate").text = "[F]N"
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def generate_billing_artifacts(model, as_of_date, since_date=None):
    """Stream one invoice at a time, with identical bytes for file and HTTP delivery."""
    from generators.render_bills import render_bill, rendered_bills
    for code, provider in (("VED", "valley_electric_district"), ("RCU", "river_city_utilities")):
        yield {"path": f"schemas/{code}.xml", "content": provider_schema(code), "media_type": "application/xml",
               "metadata": {"kind": "schema", "provider": provider, "source": code, "artifact": "schema", "ordinary_delivery": False}}
    for bill in invoices(model, as_of_date, since_date):
        account = model.accounts[bill["accountId"]]
        provider = model.providers[bill["providerId"]]
        bill["providerCode"] = provider["shortName"]
        # Comma-free stable location also survives the existing unquoted WPF BIF writer.
        bill["location"] = account["buildingId"]
        items = import_items(bill, account)
        reference = bill["providerId"] == "ridgeline_wind"
        metadata = {"kind": "reference" if reference else "bill", "provider": bill["providerId"], "source": bill["accountId"],
                    "account": bill["accountId"], "bill_id": bill["id"], "period_start": str(bill["period"]["start"]),
                    "period_end": str(bill["period"]["end"]), "issued_on": str(bill["billDate"]), "revision": 2 if bill.get("supersedes") else 1,
                    "case": "estimated" if any(line.get("estimate") for line in bill["lines"]) else "correction" if bill.get("supersedes") else "normal",
                    "ordinary_delivery": bill["providerId"] in ("valley_electric_district", "river_city_utilities"),
                    "anchor": bool(bill.get("anchor")), "total": str(money(bill["total"]))}
        stem = ("references" if reference else "bills") + f"/{bill['providerId']}/{bill['accountId']}/{bill['id']}"
        if bill.get("anchor"):
            if not hasattr(model, "_source_anchor_pdfs"):
                model._source_anchor_pdfs = rendered_bills(model.root)
            pdf = model._source_anchor_pdfs[bill["file"]]
        else:
            output = io.BytesIO()
            scenario = model.scenario
            if account["syntheticAccountNumber"] != bill["accountNumber"]:
                scenario = copy.deepcopy(scenario)
                next(item for item in scenario["accounts"] if item["id"] == account["id"])["syntheticAccountNumber"] = bill["accountNumber"]
            render_bill(bill, provider, scenario, Path("services/sources/model.py"), output, wrap_meter_cells=True)
            pdf = output.getvalue()
        yield {"path": stem + ".pdf", "content": pdf, "media_type": "application/pdf", "metadata": dict(metadata, artifact="pdf", ordinary_delivery=False)}
        evidence = {"bill": bill, "items": items, "pdf": stem + ".pdf", "sourceEvidenceOnly": ["estimate", "supersedes"],
                    "formatLimits": {"bif": ["item periods", "readings", "estimate persistence", "image location"],
                                     "uploadJsonSave": ["item periods", "readings", "estimate persistence"], "nativeXml": ["estimate persistence", "image location"]}}
        yield {"path": stem + ".manifest.json", "content": json_bytes(evidence), "media_type": "application/json", "metadata": dict(metadata, artifact="manifest", ordinary_delivery=False)}
        if reference:
            continue
        yield {"path": stem + ".bif", "content": _bif(bill, items), "media_type": "text/csv", "metadata": dict(metadata, artifact="bif", ordinary_delivery=False)}
        yield {"path": stem + ".xml", "content": _bill_xml(bill, items), "media_type": "application/xml", "metadata": dict(metadata, artifact="nativeXml")}
        if bill["providerId"] in ("valley_electric_district", "river_city_utilities"):
            yield {"path": stem + f".{provider['shortName']}.csv", "content": _provider_csv(bill, items), "media_type": "text/csv", "metadata": dict(metadata, artifact="providerCsv", ordinary_delivery=False)}
        grouped = {}
        for item in items:
            grouped.setdefault(item["meter"], []).append({"Description": item["code"], "Quantity": str(item["quantity"]), "Charge": str(item["amount"]), "UnitOfMeasure": item["unit"]})
        data = {"Customer": bill["customer"], "Documents": [{"DocId": 1, "Extraction": {
            "AccountInfo": {"Vendor": provider["shortName"], "AccountNumber": bill["accountNumber"], "InvoiceNumber": bill.get("invoiceNumber", ""),
                            "StartDate": str(bill["period"]["start"]), "EndDate": str(bill["period"]["end"]), "StatementDate": str(bill["billDate"]),
                            "DueDate": str(bill["dueDate"]) if bill.get("dueDate") else None, "TotalCharges": str(money(bill["total"])), "ServiceAddress": bill["location"]},
            "MeterLineItems": [{"MeterNumber": meter, "LineItems": rows} for meter, rows in grouped.items()]}}]}
        yield {"path": stem + ".extracted.json", "content": json_bytes(data), "media_type": "application/json", "metadata": dict(metadata, artifact="extractedJson", ordinary_delivery=False)}
