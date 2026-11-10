"""Cumulative register evidence calculated from the shared measurement timeline.

Known reads constrain the timeline; this module never rescales usage or invents a
negative opening read to make incompatible facts fit. Electric TOU dials remain
separate registers. All caches belong to one model and have fixed size bounds.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal


class RegisterConstraintError(ValueError):
    pass


def _date(value):
    return value if type(value) is date else date.fromisoformat(str(value)[:10])


def _cache(model):
    cache = getattr(model, "_source_register_cache", None)
    if cache is None:
        cache = {"days": OrderedDict(), "readings": OrderedDict(), "specs": OrderedDict()}
        model._source_register_cache = cache
    return cache


def clear_register_cache(model):
    """Call after deliberately recalibrating a model's unanchored measurements."""
    if hasattr(model, "_source_register_cache"):
        del model._source_register_cache


def _remember(cache, key, value, limit):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)
    return value


def _daily(model, meter_id, metric, day):
    key = (meter_id, metric, day)
    cache = _cache(model)["days"]
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    from .model import utc_boundary
    step = 15 if metric.endswith("kwh") or metric == "reactive_kvarh" else 60
    start, stop = utc_boundary(day), utc_boundary(day + timedelta(days=1))
    totals = {None: Decimal(0), "peak": Decimal(0), "part_peak": Decimal(0), "off_peak": Decimal(0)}
    stamp = start + timedelta(minutes=step)
    while stamp <= stop:
        value = model.meter_value(meter_id, metric, stamp, step)
        totals[None] += value
        if metric == "electric_kwh":
            totals[model.tou(stamp)] += value
        stamp += timedelta(minutes=step)
    return _remember(cache, key, totals, 512)


def _integral(model, meter_id, metric, group, start, stop):
    total = Decimal(0)
    day = start
    while day < stop:
        total += _daily(model, meter_id, metric, day)[group]
        day += timedelta(days=1)
    return total


def _specifications(model, meter_id, metric):
    key = (meter_id, metric)
    cache = _cache(model)["specs"]
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    meter = model.meters[meter_id]
    anchors = [(group, _date(start), values) for (owner, kind, group, start), values in model.register_anchors.items()
               if owner == meter_id and kind == metric]
    relevant_roles = {"billing_usage", "manual_register_reading", "handheld_register_reading", "manual_usage_delta", "handheld_usage_delta"}
    appropriate = any(channel.get("intervalMinutes") is None and channel.get("role") in relevant_roles
                      or "register" in channel.get("role", "") for channel in meter.get("channels", []))
    if not anchors and not appropriate:
        return _remember(cache, key, [], 256)
    if metric not in ("electric_kwh", "water_kgal", "gas_ccf", "steam_klb"):
        return _remember(cache, key, [], 256)
    groups = ("peak", "part_peak", "off_peak") if metric == "electric_kwh" else (None,)
    result = []
    for group in groups:
        points = {}
        multiplier = None
        for candidate, start, (previous, scale, end, present) in anchors:
            if candidate != group:
                continue
            scale = Decimal(str(scale))
            if multiplier is not None and multiplier != scale:
                raise RegisterConstraintError(f"{meter_id}/{metric}/{group}: changing register multipliers require an explicit instrument segment")
            multiplier = scale
            for boundary, reading in ((start, previous), (_date(end) + timedelta(days=1), present)):
                value = Decimal(str(reading))
                if boundary in points and points[boundary] != value:
                    raise RegisterConstraintError(f"{meter_id}/{metric}/{group}: incompatible reads at {boundary}")
                points[boundary] = value
        if multiplier is None:
            # Use another known dial's instrument multiplier, never scale demand.
            multiplier = Decimal(str(anchors[0][2][1])) if anchors else Decimal(str(meter.get("multiplier", 1)))
        if multiplier <= 0:
            raise RegisterConstraintError(f"{meter_id}: register multiplier must be positive")
        factor = Decimal("1.027") if metric == "gas_ccf" else Decimal(1)
        result.append({"group": group, "points": points, "multiplier": multiplier, "factor": factor})
    return _remember(cache, key, result, 256)


def _reading(model, meter_id, metric, spec, boundary):
    group, multiplier = spec["group"], spec["multiplier"]
    cache = _cache(model)["readings"]
    key = (meter_id, metric, group, boundary)
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    if boundary in spec["points"]:
        return _remember(cache, key, spec["points"][boundary], 2048)
    candidates = dict(spec["points"])
    candidates.update({item[3]: value for item, value in cache.items() if item[:3] == key[:3]})
    if not candidates:
        meter = model.meters[meter_id]
        account = model.accounts.get(model.meter_accounts.get(meter_id), {})
        opening = max((_date(value) for value in (meter.get("effectiveStart"), account.get("effectiveStart")) if value), default=date(2024, 1, 1))
        if opening == date(2024, 1, 1):
            opening = date(2023, 12, 1)
        candidates[opening] = Decimal(str(model.assumptions["profiles"]["unanchored_register_origin"]))
    reference = min(candidates, key=lambda day: abs((day - boundary).days))
    if reference <= boundary:
        value = candidates[reference] + _integral(model, meter_id, metric, group, reference, boundary) / multiplier
    else:
        value = candidates[reference] - _integral(model, meter_id, metric, group, boundary, reference) / multiplier
    if value < 0:
        raise RegisterConstraintError(f"{meter_id}/{metric}/{group}: timeline implies negative read {value} at {boundary} from known {candidates[reference]} at {reference}; calibrate unanchored pre-anchor usage")
    return _remember(cache, key, value, 2048)


def enrich_meter(model, meter_id, metric, start_date, end_date, total):
    """Return register fields, or ``register_channels`` for separate electric dials.

    ``total`` is the caller's independently accumulated canonical usage in this
    period. Gas uses raw CCF, with factor 1.027 reported separately; values are not
    converted twice. Dates are inclusive, readings are taken at local boundaries.
    """
    start, end = _date(start_date), _date(end_date)
    if end < start:
        raise ValueError("Register period ends before it starts")
    specs = _specifications(model, meter_id, metric)
    if not specs:
        return {}
    meter = model.meters[meter_id]
    opening = meter.get("effectiveStart")
    closing = meter.get("effectiveEnd")
    read_start = max(start, _date(opening)) if opening and _date(opening) > date(2024, 1, 1) else start
    read_end = min(end, _date(closing)) if closing else end
    if read_start > read_end:
        return {}
    rows = []
    sum_usage = Decimal(0)
    labels = {"peak": "On-peak register", "part_peak": "Part-peak register", "off_peak": "Off-peak register"}
    unit = {"electric_kwh": "kWh", "water_kgal": "kgal", "gas_ccf": "ccf", "steam_klb": "klb"}[metric]
    for spec in specs:
        previous = _reading(model, meter_id, metric, spec, read_start)
        present = _reading(model, meter_id, metric, spec, read_end + timedelta(days=1))
        measured = _integral(model, meter_id, metric, spec["group"], read_start, read_end + timedelta(days=1))
        implied = (present - previous) * spec["multiplier"]
        if abs(implied - measured) > Decimal("0.000001"):
            raise RegisterConstraintError(f"{meter_id}/{metric}/{spec['group']}: anchored read delta {implied} differs from canonical usage {measured} in {read_start}..{read_end}")
        sum_usage += measured
        rows.append({"channel": labels.get(spec["group"], f"Delivered ({unit})"), "previous": previous, "present": present,
                     "multiplier": spec["multiplier"], "factor": spec["factor"], "register_unit": unit, "unit": unit,
                     "quantity": measured, "readPeriod": {"start": read_start, "end": read_end}})
    if abs(sum_usage - Decimal(str(total))) > Decimal("0.000001"):
        raise RegisterConstraintError(f"{meter_id}/{metric}: register usage {sum_usage} differs from caller's canonical total {total}")
    if metric == "electric_kwh":
        return {"register_channels": rows}
    row = rows[0]
    return {key: row[key] for key in ("previous", "present", "multiplier", "factor", "register_unit", "readPeriod")}
