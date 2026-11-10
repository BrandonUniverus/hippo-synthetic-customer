"""Physical relationships declared by Northlake's source meters and statements.

This module supplies dependent readings; it does not write files or database rows.
Every energy comparison uses the same UTC interval ends as the upstream model.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from zoneinfo import ZoneInfo

UTC = timezone.utc
PACIFIC = ZoneInfo("America/Los_Angeles")
PRECISION = Decimal("0.000001")


def _boundary(day):
    return datetime.combine(day, time(), PACIFIC).astimezone(UTC)


def _information(bill, word):
    matches = [Decimal(str(item["value"])) for item in bill.get("informational", [])
               if word in item["label"].lower() and item.get("unit", "").lower() == "kwh"]
    if len(matches) != 1:
        raise ValueError(f"{bill['id']}: expected one {word} energy source fact")
    return matches[0]


def configure(model):
    """Called once after invoice constraints, before any readings are evaluated."""
    bills = {bill["id"]: bill for bill in model.anchor_bills}
    statement = bills["rwl_transfer_2024_07"]
    first_bill = bills["ved_ridgeline_generator_2024_07"]
    start, stop = statement["period"]["start"], statement["period"]["end"]
    if (start, stop) != (date(2024, 7, 1), date(2024, 7, 31)):
        raise ValueError("The Ridgeline calendar-July source checkpoint changed")
    meter_id = model.meter_numbers[first_bill["meters"][0]["meterNumber"]]
    july_targets = {
        "received_kwh": _information(statement, "export"),
        # Stage 3, 04-acceptance-runs.yaml, mdef_ridgeline_interconnection:
        # July station service is 3,876; Aug 1-4 is the first bill's remainder.
        "delivered_kwh": Decimal("3876"),
    }
    for metric, july_target in july_targets.items():
        key = (meter_id, metric)
        original = [constraint for constraint in model.constraints[key] if constraint["bill_id"] == first_bill["id"]]
        total = sum((constraint["target"] for constraint in original), Decimal(0))
        if not original or original[0]["start"] != start or max(c["end"] for c in original) <= stop:
            raise ValueError(f"{metric}: first generator bill must contain July and its following days")
        if not Decimal(0) <= july_target <= total:
            raise ValueError(f"{metric}: calendar July cannot exceed the complete source bill")
        following_end = max(c["end"] for c in original)
        remaining = [constraint for constraint in model.constraints[key] if constraint["bill_id"] != first_bill["id"]]
        model.constraints[key] = sorted(remaining + [
            {"start": start, "end": stop, "target": july_target, "group": None, "condition": None, "bill_id": first_bill["id"]},
            {"start": stop + timedelta(days=1), "end": following_end, "target": total - july_target,
             "group": None, "condition": None, "bill_id": first_bill["id"]},
        ], key=lambda constraint: constraint["start"])

    groups = {}
    meter_to_master = {}
    for binding in model.bindings:
        if binding["profile"] != "gw_fig_fixed_network_submeters":
            continue
        meter = model.channels[binding["channel"]]["meter"]
        parent = model.meters[meter]["behindMeterId"]
        if parent not in model.meters:
            raise ValueError(f"{meter}: unknown master meter {parent}")
        meter_to_master[meter] = parent
        groups.setdefault(parent, []).append(meter)
    profiles = model.assumptions["profiles"]
    unit_share = Decimal(str(profiles["apartment_electric_share"]))
    if not Decimal(0) <= unit_share <= 1:
        raise ValueError("Apartment energy share must be between zero and one")
    single_shares = {meter: Decimal(str(value)) for meter, value in profiles.get("electric_submeter_shares", {}).items()}
    for parent, members in groups.items():
        units = [meter for meter in members if model.meters[meter].get("kind") == "unit_submeter"]
        if units:
            houses = [meter for meter in members if model.meters[meter].get("kind") == "house_submeter"]
            if len(houses) != 1:
                raise ValueError(f"{parent}: a complete apartment group needs one house meter")
        elif any(meter not in single_shares for meter in members) or sum((single_shares[meter] for meter in members), Decimal(0)) > 1:
            raise ValueError(f"{parent}: declare non-overlapping electric_submeter_shares")
    if any(not Decimal(0) <= share <= 1 for share in single_shares.values()):
        raise ValueError("Electric submeter shares must be between zero and one")
    model._physical = {"possible_start": start, "possible_end": stop,
                       "possible_kwh": _information(statement, "possible"), "possible_values": None,
                       "submeter_groups": {parent: tuple(sorted(members)) for parent, members in groups.items()},
                       "meter_to_master": meter_to_master, "unit_share": unit_share, "single_shares": single_shares}


@lru_cache(maxsize=1024)
def _submeter_values(model, master, end, interval):
    if interval % 15:
        raise ValueError("Electric submeter intervals must contain complete fifteen-minute master intervals")
    # A 60-minute reallocation of an anchored master is not necessarily its four
    # actual 15-minute readings. Sum the same source intervals used by billing.
    total = sum((model.meter_value(master, "electric_kwh", end - timedelta(minutes=minute), 15)
                 for minute in range(0, interval, 15)), Decimal(0))
    members = model._physical["submeter_groups"][master]
    units = [meter for meter in members if model.meters[meter].get("kind") == "unit_submeter"]
    if not units:
        return {meter: (total * model._physical["single_shares"][meter]).quantize(PRECISION, rounding=ROUND_HALF_UP)
                for meter in members}
    target = (total * model._physical["unit_share"]).quantize(PRECISION, rounding=ROUND_HALF_UP)
    weights = {meter: Decimal(str(0.8 + model._phase(meter) * 0.4)) for meter in units}
    weight_sum = sum(weights.values(), Decimal(0))
    result = {meter: (target * weight / weight_sum).quantize(PRECISION, rounding=ROUND_HALF_UP) for meter, weight in weights.items()}
    result[units[-1]] += target - sum(result.values(), Decimal(0))
    house = next(meter for meter in members if model.meters[meter].get("kind") == "house_submeter")
    result[house] = total - target
    if any(value < 0 for value in result.values()) or sum(result.values(), Decimal(0)) != total:
        raise ValueError(f"{master}: dependent readings do not conserve master energy")
    return result


def _possible_values(model):
    state = model._physical
    if state["possible_values"] is not None:
        return state["possible_values"]
    start = _boundary(state["possible_start"])
    stop = _boundary(state["possible_end"] + timedelta(days=1))
    values = []
    actual_total = Decimal(0)
    for meter in sorted(model.wind_meters):
        end = start + timedelta(minutes=10)
        while end <= stop:
            actual_kw = model.meter_value(meter, "generated_kwh", end, 10) * 6
            actual_total += actual_kw
            values.append((meter, int(end.timestamp()), actual_kw))
            end += timedelta(minutes=10)
    target = state["possible_kwh"] * 6
    if actual_total <= 0 or target < actual_total:
        raise ValueError("Ridgeline possible-energy source fact cannot be below actual generated energy")
    result = {(meter, timestamp): (actual * target / actual_total).quantize(PRECISION, rounding=ROUND_HALF_UP)
              for meter, timestamp, actual in values}
    residual = target - sum(result.values(), Decimal(0))
    for meter, timestamp, actual in reversed(values):
        if result[(meter, timestamp)] + residual >= actual:
            result[(meter, timestamp)] += residual
            break
    else:
        raise ValueError("Possible-energy rounding cannot preserve its source total")
    if any(result[(meter, timestamp)] < actual for meter, timestamp, actual in values):
        raise ValueError("Possible power cannot be below actual power")
    state["possible_values"] = result
    return result


def reading_override(model, binding, end):
    """Return a dependent value, or NotImplemented for the ordinary source model."""
    channel = model.channels[binding["channel"]]
    meter = channel["meter"]
    if not model.active(meter, end):
        return NotImplemented
    state = model._physical
    if binding["profile"] == "gw_fig_fixed_network_submeters":
        return _submeter_values(model, state["meter_to_master"][meter], end, binding["interval_minutes"])[meter]
    day = (end - timedelta(microseconds=1)).astimezone(PACIFIC).date()
    if meter in model.wind_meters and "possible_kw" in binding["channel"] and state["possible_start"] <= day <= state["possible_end"]:
        if binding["interval_minutes"] != 10:
            raise ValueError("Ridgeline possible-energy checkpoint requires ten-minute source intervals")
        return _possible_values(model)[(meter, int(end.timestamp()))]
    return NotImplemented
