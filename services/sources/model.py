"""One physical timeline for file feeds, meter registers and supplier quantities.

Unanchored readings are synthetic assumptions. Anchored periods allocate their
known energy among real UTC intervals, with explicit capacity checks. The same
allocated values are read by both the bill generator and gateway encoders.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

UTC = timezone.utc
PACIFIC = ZoneInfo("America/Los_Angeles")
PRECISION = Decimal("0.000001")


def as_date(value):
    return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])


def utc_boundary(value):
    return datetime.combine(as_date(value), time(), PACIFIC).astimezone(UTC)


def decimal(value):
    return Decimal(str(value))


def holiday_dates(year):
    """The six holidays already selected by Northlake, extended by calendar rule."""
    may_end = date(year, 5, 31)
    memorial = may_end - timedelta(days=may_end.weekday())
    september = date(year, 9, 1)
    labor = september + timedelta(days=(-september.weekday()) % 7)
    november = date(year, 11, 1)
    thanksgiving = november + timedelta(days=(3 - november.weekday()) % 7 + 21)
    return frozenset((date(year, 1, 1), memorial, date(year, 7, 4), labor, thanksgiving, date(year, 12, 25)))


class SourceModel:
    def __init__(self, source_root, seed=104729, assumptions=None):
        self.root = Path(source_root)
        self.seed = seed
        self.assumptions = assumptions or json.loads(Path(__file__).with_name("assumptions.json").read_text(encoding="utf-8"))
        self.scenario = yaml.safe_load((self.root / "data/scenarios/demo-university-v1.yaml").read_text(encoding="utf-8"))
        self.accounts = {a["id"]: a for a in self.scenario["accounts"]}
        self.providers = {p["id"]: p for p in (yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((self.root / "data/providers").glob("*.yaml")))}
        self.buildings = {b["id"]: {**b, "companyId": s["ownerCompanyId"]} for s in self.scenario["sites"] for b in s.get("buildings", [])}
        from generators.northlake_packet import expand_owned_meters
        owned = list(expand_owned_meters(self.scenario, self.buildings))
        self.meters = {}
        self.meter_accounts = {}
        self.channels = {}
        for account in self.accounts.values():
            for meter in account.get("meters", []):
                self.meters[meter["id"]] = {**meter, "buildingId": account["buildingId"]}
                self.meter_accounts[meter["id"]] = account["id"]
        self.meters.update({m["id"]: m for m in owned})
        self.meter_numbers = {m["syntheticMeterNumber"]: key for key, m in self.meters.items() if "syntheticMeterNumber" in m}
        for meter_id, meter in self.meters.items():
            for channel in meter.get("channels", []):
                self.channels[channel["id"]] = {**channel, "meter": meter_id}
        self.wind_meters = tuple(m for m in self.meters if any(c.get("unit") == "kWh" and c.get("intervalMinutes") == 10 for c in self.meters[m].get("channels", [])))
        from .gateways import gateway_bindings
        self.bindings = gateway_bindings(self.root)
        for binding in self.bindings:
            binding["units"] = self.channels.get(binding["channel"], {}).get("unit", binding.get("units", ""))
        self.gateway_bindings = self.bindings
        from generators.render_bills import load_bills, check_bills
        self.anchor_bills = [b for b, _ in load_bills(self.root)]
        check_bills(self.anchor_bills)
        self.constraints = {}
        self.peaks = {}
        self.register_anchors = {}
        self._build_constraints()
        from .physical import configure
        configure(self)
        # The small absolute water registers bound how much unobserved usage can
        # precede the first known read. Keep a documented opening balance instead
        # of back-integrating an impossible negative register.
        first_reads = {}
        for (meter_id, metric, group, start), values in self.register_anchors.items():
            if metric == "water_kgal" and (meter_id not in first_reads or start < first_reads[meter_id][0]):
                first_reads[meter_id] = (start, values)
        for meter_id, (end_date, (previous, multiplier, _, _)) in first_reads.items():
            start_date = date(2023, 12, 1)
            stamp, stop = utc_boundary(start_date) + timedelta(hours=1), utc_boundary(end_date)
            prior = Decimal(0)
            while stamp <= stop:
                prior += self.meter_value(meter_id, "water_kgal", stamp, 60)
                stamp += timedelta(hours=1)
            if prior > previous * multiplier:
                target = previous * multiplier * (1 - decimal(self.assumptions["profiles"]["anchored_register_origin_fraction"]))
                self.constraints.setdefault((meter_id, "water_kgal"), []).append({"start": start_date, "end": end_date - timedelta(days=1), "target": target, "group": None, "condition": None, "bill_id": f"synthetic-opening-register:{meter_id}"})

    def tou(self, end):
        local = (end - timedelta(microseconds=1)).astimezone(PACIFIC)
        if local.weekday() >= 5 or local.date() in holiday_dates(local.year):
            return "off_peak"
        rules = self.assumptions["tou"]
        hour = local.hour + local.minute / 60
        if local.month in rules["summer_months"]:
            if any(a <= hour < b for a, b in rules["summer_peak"]):
                return "peak"
            if any(a <= hour < b for a, b in rules["summer_part_peak"]):
                return "part_peak"
        elif any(a <= hour < b for a, b in rules["winter_part_peak"]):
            return "part_peak"
        return "off_peak"

    def _build_constraints(self):
        superseded = {b["supersedes"] for b in self.anchor_bills if b.get("supersedes")}
        for bill in self.anchor_bills:
            if bill["id"] in superseded:
                continue
            for item in bill["meters"]:
                meter_id = self.meter_numbers.get(item["meterNumber"])
                if meter_id is None:
                    raise ValueError(f"{bill['id']}: unknown meter {item['meterNumber']}")
                start, end = (as_date(bill["period"][k]) for k in ("start", "end"))
                if item.get("readPeriod") and item.get("readType") != "estimated":
                    start, end = (as_date(item["readPeriod"][k]) for k in ("start", "end"))
                label, unit = item.get("channel", "").lower(), item.get("unit", "").lower()
                group = None
                if unit == "kw" or unit == "ton":
                    metric = "electric_kwh" if unit == "kw" else "chilled_water_ton_hours"
                    self.peaks.setdefault((meter_id, metric), []).append((start, end, decimal(item["quantity"])))
                    continue
                if unit == "kwh":
                    if "received" in label or "export" in label:
                        metric = "received_kwh" if bill["accountId"] == "ved_ridgeline_generator" else "exported_kwh"
                    elif "generation" in label or "generated" in label:
                        metric = "generated_kwh"
                    elif "station service" in label:
                        metric = "delivered_kwh"
                    else:
                        metric = "electric_kwh"
                        if "part-peak" in label:
                            group = "part_peak"
                        elif "off-peak" in label:
                            group = "off_peak"
                        elif "on-peak" in label:
                            group = "peak"
                else:
                    metric = {"kvarh": "reactive_kvarh", "kgal": "water_kgal", "therms": "gas_ccf", "ton-hr": "chilled_water_ton_hours", "klb": "steam_klb"}.get(unit)
                if metric is None:
                    continue
                condition = None
                if bill["id"] == "hos_science_center_2025_03" and metric in ("generated_kwh", "exported_kwh"):
                    condition = "gap" if item.get("readType") == "estimated" else "outside_gap"
                target = decimal(item["present"]) - decimal(item["previous"]) if metric == "gas_ccf" and "present" in item else decimal(item["quantity"])
                constraint = {"start": start, "end": end, "target": target, "group": group, "condition": condition, "bill_id": bill["id"]}
                self.constraints.setdefault((meter_id, metric), []).append(constraint)
                if "previous" in item and item.get("readType") != "estimated":
                    self.register_anchors[(meter_id, metric, group, start)] = (decimal(item["previous"]), decimal(item.get("multiplier", 1)), end, decimal(item["present"]))
        # VED's Central Plant sample states total metered energy and separate TOU
        # charge quantities. The latter are the more precise interval constraints.
        for bill in self.anchor_bills:
            if bill["accountId"] != "ved_central_plant":
                continue
            meter_id = self.accounts[bill["accountId"]]["meters"][0]["id"]
            self.constraints[(meter_id, "electric_kwh")] = [
                {"start": as_date(bill["period"]["start"]), "end": as_date(bill["period"]["end"]), "target": decimal(line["quantity"]), "group": line["code"].removeprefix("energy_"), "condition": None, "bill_id": bill["id"]}
                for line in bill["lines"] if line["code"].startswith("energy_")]
        # A zero/omitted thermal commodity on an anchored allocation is meaningful.
        # Do not fabricate steam on the summer cooling-only Science statement.
        for bill in self.anchor_bills:
            if bill["providerId"] != "northlake_thermal_plant":
                continue
            present = {item["meterNumber"] for item in bill["meters"]}
            for meter in self.accounts[bill["accountId"]]["meters"]:
                if meter["syntheticMeterNumber"] in present:
                    continue
                units = {c.get("unit", "").lower() for c in meter.get("channels", [])}
                metric = "steam_klb" if "klb" in units else "chilled_water_ton_hours"
                self.constraints.setdefault((meter["id"], metric), []).append({"start": as_date(bill["period"]["start"]), "end": as_date(bill["period"]["end"]), "target": Decimal(0), "group": None, "condition": None, "bill_id": bill["id"]})

    def _gap(self, end):
        events = self.assumptions["events"]
        return datetime.fromisoformat(events["helios_gap_start"]).astimezone(UTC) < end <= datetime.fromisoformat(events["helios_gap_end"]).astimezone(UTC)

    def _matches(self, constraint, end):
        return (constraint["group"] is None or self.tou(end) == constraint["group"]) and (constraint["condition"] is None or self._gap(end) == (constraint["condition"] == "gap"))

    def _lifetime(self, meter_id):
        meter = self.meters[meter_id]
        account = self.accounts.get(self.meter_accounts.get(meter_id), {})
        starts = [as_date(v) for v in (meter.get("effectiveStart"), account.get("effectiveStart")) if v]
        if "rwl" in meter_id or "ridgeline" in meter_id:
            starts.append(date(2024, 7, 1))
        # Only the existing January 2024 estate receives the approved lead-in.
        start = max(starts, default=date(2024, 1, 1))
        if start == date(2024, 1, 1):
            start = date(2023, 12, 1)
        stop = meter.get("effectiveEnd") or account.get("effectiveEnd")
        return start, as_date(stop) if stop else None

    def active(self, meter_id, end):
        start, stop = self._lifetime(meter_id)
        return end > utc_boundary(start) and (not stop or end <= utc_boundary(stop + timedelta(days=1)))

    def _outage(self, meter_id, end):
        events = self.assumptions["events"]
        return ("07" in meter_id and ("rwl" in meter_id or "ridgeline" in meter_id)
                and utc_boundary(events["wtg07_outage_start"]) < end <= utc_boundary(events["wtg07_outage_end_exclusive"]))

    @lru_cache(maxsize=1024)
    def _phase(self, key):
        return int.from_bytes(hashlib.sha256(f"{self.seed}:{key}".encode()).digest()[:4], "big") / 2**32

    def _raw_wind(self, meter_id, end, step):
        if not self.active(meter_id, end) or self._outage(meter_id, end):
            return 0.0
        return self.assumptions["profiles"]["wind_turbine_mean_kw"] * (1 + 0.35 * math.sin(end.timestamp() / 86400 * 0.5)) * (0.8 + self._phase(meter_id) * 0.4) * step / 60

    @lru_cache(maxsize=8)
    def _wind_period_scale(self, index):
        received = self.constraints[("ved_ridgeline_interconnection", "received_kwh")][index]
        start, stop = utc_boundary(received["start"]), utc_boundary(received["end"] + timedelta(days=1))
        known = Decimal(0)
        free_weight = 0.0
        for meter_id in self.wind_meters:
            fixed = self.constraints.get((meter_id, "generated_kwh"), [])
            for constraint in fixed:
                if received["start"] <= constraint["start"] and constraint["end"] <= received["end"]:
                    known += constraint["target"]
                elif constraint["start"] <= received["end"] and constraint["end"] >= received["start"]:
                    raise ValueError("Partially overlapping wind constraints need an explicit segment allocation")
            stamp = start + timedelta(minutes=10)
            while stamp <= stop:
                day = (stamp - timedelta(microseconds=1)).astimezone(PACIFIC).date()
                if not any(c["start"] <= day <= c["end"] for c in fixed):
                    free_weight += self._raw_wind(meter_id, stamp, 10)
                stamp += timedelta(minutes=10)
        required = received["target"] / decimal(self.assumptions["profiles"]["wind_export_fraction"]) - known
        if not free_weight and received["target"] <= known:
            # Fully anchored turbine periods determine their own loss fraction.
            return 1.0
        if required < 0 or (required and not free_weight):
            raise ValueError(f"{received['bill_id']}: wind generation cannot reconcile with export and known turbine energy")
        return float(required) / free_weight if free_weight else 1.0

    def _base(self, meter_id, metric, end, step):
        if not self.active(meter_id, end) or (metric == "generated_kwh" and self._outage(meter_id, end)):
            return 0.0
        meter = self.meters[meter_id]
        building = self.buildings.get(meter.get("buildingId"), {})
        area = float(building.get("grossFloorAreaSqft", 60000)) / 100000
        local = (end - timedelta(seconds=1)).astimezone(PACIFIC)
        hour = local.hour + local.minute / 60
        phase = self._phase(meter_id)
        daily = 0.65 + 0.55 * max(0.0, math.sin(math.pi * (hour - 5) / 16))
        weekday = 0.84 if local.weekday() >= 5 else 1.0
        seasonal = math.cos(2 * math.pi * (local.timetuple().tm_yday - 200) / 365.2425)
        variation = 0.94 + 0.12 * (0.5 + 0.5 * math.sin(end.timestamp() / 86400 * 0.77 + phase * 9))
        hours = step / 60
        profiles = self.assumptions["profiles"]
        if metric == "electric_kwh":
            # Split independent services of one building rather than duplicating it.
            account = self.accounts.get(self.meter_accounts.get(meter_id), {})
            simultaneous = sum(1 for m in account.get("meters", []) if self.active(m["id"], end)) or 1
            nominal_kw = profiles["electric_kw_by_building"].get(meter.get("buildingId"), area * 100000 * profiles["electric_kw_per_sqft"])
            return nominal_kw * daily * weekday * (1 + 0.2 * seasonal) * variation * hours / simultaneous
        if metric == "generated_kwh":
            if "rwl" in meter_id or "ridgeline" in meter_id:
                local_day = (end - timedelta(microseconds=1)).astimezone(PACIFIC).date()
                scale = next((self._wind_period_scale(i) for i, c in enumerate(self.constraints.get(("ved_ridgeline_interconnection", "received_kwh"), [])) if c["start"] <= local_day <= c["end"]), 1.0)
                return self._raw_wind(meter_id, end, step) * scale
            account_id = self.meter_accounts.get(meter_id)
            capacity = profiles["solar_capacity_kw"].get(account_id, profiles["solar_capacity_kw_default"])
            return capacity * profiles["solar_output_factor"] * max(0, math.sin(math.pi * (hour - 6) / 12)) * (1 + 0.22 * seasonal) * variation * hours
        if metric == "exported_kwh":
            return self._base(meter_id, "generated_kwh", end, step) * profiles["solar_export_fraction"]
        if metric == "received_kwh":
            return self.wind_energy(end, step) * profiles["wind_export_fraction"]
        if metric == "delivered_kwh":
            return (8 + 30 * max(0, -seasonal)) * hours * variation
        if metric == "reactive_kvarh":
            return self._base(meter_id, "received_kwh", end, step) * 0.34
        bases = {"water_kgal": profiles["water_kgal_per_hour_per_100000_sqft"], "gas_ccf": profiles["gas_therms_per_hour_per_100000_sqft"] / 1.027, "chilled_water_ton_hours": profiles["chilled_water_tons_per_100000_sqft"], "steam_klb": profiles["steam_klb_per_hour_per_100000_sqft"]}
        amount = bases[metric] * area * daily * weekday * variation * hours
        if metric in ("gas_ccf", "steam_klb"):
            amount *= 1 - 0.5 * seasonal
        elif metric == "chilled_water_ton_hours":
            amount *= 1 + 0.6 * seasonal
        return amount

    @lru_cache(maxsize=160)
    def _allocated(self, meter_id, metric, constraint_index, step):
        c = self.constraints[(meter_id, metric)][constraint_index]
        start, end = utc_boundary(c["start"]), utc_boundary(c["end"] + timedelta(days=1))
        count = int((end - start).total_seconds() // (step * 60))
        stamps = [start + timedelta(minutes=step * (i + 1)) for i in range(count)]
        selected = [i for i, stamp in enumerate(stamps) if self.active(meter_id, stamp) and self._matches(c, stamp)]
        weights = [max(0.0, self._base(meter_id, metric, stamps[i], step)) for i in selected]
        target = float(c["target"])
        cap = next((float(v) * step / 60 for a, b, v in self.peaks.get((meter_id, metric), []) if a <= c["start"] and b >= c["end"]), math.inf)
        if target > cap * len(selected) + 0.000001 or (target and not sum(weights)):
            raise ValueError(f"{c['bill_id']} / {meter_id} / {metric} / {c['group']}: {target} cannot fit {len(selected)} intervals capped at {cap}")
        remaining, free = target, set(range(len(selected)))
        allocated = [0.0] * len(selected)
        # Retain an exact observed peak once in the largest-energy TOU bucket.
        peers = self.constraints[(meter_id, metric)]
        peak_bucket = max((p for p in peers if p["start"] == c["start"] and p["end"] == c["end"]), key=lambda p: p["target"])
        if math.isfinite(cap) and c == peak_bucket and target >= cap and free:
            index = max(free, key=lambda i: weights[i])
            allocated[index] = cap
            free.remove(index)
            remaining -= cap
        while free:
            total_weight = sum(weights[i] for i in free)
            if not total_weight:
                if remaining > 0.000001:
                    raise ValueError(f"{c['bill_id']}: no physical intervals for remaining {remaining}")
                break
            capped = [i for i in free if remaining * weights[i] / total_weight > cap]
            if not capped:
                for i in free:
                    allocated[i] = remaining * weights[i] / total_weight
                break
            for i in capped:
                allocated[i] = cap
                remaining -= cap
                free.remove(i)
        values = [decimal(v).quantize(PRECISION, rounding=ROUND_HALF_UP) for v in allocated]
        if values:
            residual = c["target"] - sum(values)
            index = next((i for i in reversed(range(len(values))) if (not residual or values[i] > 0) and values[i] + residual >= 0 and (not math.isfinite(cap) or values[i] + residual <= decimal(cap))), None)
            if index is None:
                raise ValueError(f"{c['bill_id']}: rounding cannot preserve constrained total")
            values[index] += residual
        result = {int(stamps[i].timestamp()): v for i, v in zip(selected, values)}
        return result

    def meter_value(self, meter_id, metric, end, step=15):
        if not self.active(meter_id, end):
            return Decimal(0)
        local_day = (end - timedelta(microseconds=1)).astimezone(PACIFIC).date()
        candidates = self.constraints.get((meter_id, metric), [])
        covered = False
        for i, c in enumerate(candidates):
            if c["start"] <= local_day <= c["end"]:
                covered = True
                if self._matches(c, end):
                    return self._allocated(meter_id, metric, i, step).get(int(end.timestamp()), Decimal(0))
        if covered:
            return Decimal(0)
        return decimal(self._base(meter_id, metric, end, step)).quantize(PRECISION, rounding=ROUND_HALF_UP)

    def wind_energy(self, end, step=15):
        # A five-minute integration grid reconciles native ten-minute turbines
        # with the fifteen-minute interconnection without shifting timestamps.
        total = Decimal(0)
        for minute in range(0, step, 5):
            stamp = end - timedelta(minutes=minute)
            ceiling = math.ceil(stamp.timestamp() / 600) * 600
            ten_end = datetime.fromtimestamp(ceiling, UTC)
            total += sum((self.meter_value(m, "generated_kwh", ten_end, 10) for m in self.wind_meters), Decimal(0)) / 2
        return float(total)

    def _binding_value(self, binding, end):
        key = binding["channel"]
        channel = self.channels.get(key, {})
        meter_id = channel.get("meter", binding.get("meter"))
        if meter_id not in self.meters:
            raise ValueError(f"Unknown channel/meter: {key}/{meter_id}")
        if not self.active(meter_id, end):
            return None
        from .physical import reading_override
        override = reading_override(self, binding, end)
        if override is not NotImplemented:
            return override
        step = binding["interval_minutes"]
        unit = channel.get("unit", binding.get("units", "")).lower()
        unit = {"w_per_m2": "w/m2", "m_per_s": "m/s", "kpa": "kpa", "kgm3": "kgm3"}.get(unit, unit)
        role = channel.get("role", "")
        lower = key.lower()
        if "turbine_state" in lower or unit in ("state", "status") or binding.get("reading_type") == "Digital":
            return 2 if self._outage(meter_id, end) else 1
        if meter_id in self.wind_meters:
            if unit == "kwh":
                return self.meter_value(meter_id, "generated_kwh", end, step)
            if unit == "kw":
                actual = self.meter_value(meter_id, "generated_kwh", end, step) * 60 / step
                if "possible" in lower:
                    possible = decimal(self.assumptions["profiles"]["wind_turbine_mean_kw"] * (1 + 0.35 * math.sin(end.timestamp() / 86400 * 0.5)))
                    return max(possible, actual * Decimal("1.05")).quantize(PRECISION)
                return actual
        if unit == "kwh":
            metric = "electric_kwh"
            if "hos" in lower:
                metric = "exported_kwh" if "export" in lower else "generated_kwh"
                if "science" in lower and self._gap(end):
                    return None
            elif "received" in lower or "export" in lower:
                metric = "received_kwh"
            elif self.meter_accounts.get(meter_id) == "ved_ridgeline_generator":
                metric = "delivered_kwh"
            return self.meter_value(meter_id, metric, end, step)
        if unit == "kw":
            return self.meter_value(meter_id, "electric_kwh", end, step) * 60 / step
        if unit == "kvarh":
            return self.meter_value(meter_id, "reactive_kvarh", end, step)
        if unit in ("kgal", "gal", "gallons"):
            value = self.meter_value(meter_id, "water_kgal", end, step)
            return value * 1000 if unit != "kgal" else value
        local = end.astimezone(PACIFIC)
        wave = math.sin(2 * math.pi * (local.hour + local.minute / 60) / 24)
        defaults = {"degf": 72 + 3 * wave, "degc": 18 + 7 * wave, "pct": 48 + 8 * wave, "%": 48 + 8 * wave,
                    "w/m2": max(0, 800 * math.sin(math.pi * (local.hour - 6) / 12)), "w/m²": max(0, 800 * math.sin(math.pi * (local.hour - 6) / 12)),
                    "m/s": 7 + 3 * wave, "mph": 15 + 6 * wave, "knots": 12 + 4 * wave, "deg": (180 + 45 * wave) % 360,
                    "degrees": (180 + 45 * wave) % 360, "rpm": 12 + 3 * wave, "hpa": 1010 + 8 * wave,
                    "kpa": 101 + 0.8 * wave, "kgm3": 1.225 - 0.02 * wave}
        if unit not in defaults:
            raise ValueError(f"No synthetic physical profile for {key} unit={unit!r} role={role}")
        return decimal(defaults[unit]).quantize(PRECISION)

    def readings(self, binding, start, end):
        seconds = binding["interval_minutes"] * 60
        timestamp = (math.floor(start.timestamp() / seconds) + 1) * seconds
        while timestamp <= end.timestamp():
            stamp = datetime.fromtimestamp(timestamp, UTC)
            value = self._binding_value(binding, stamp)
            if value is not None:
                yield {"timestamp_utc": stamp, "value": value}
            timestamp += seconds

    @lru_cache(maxsize=256)
    def period_metrics(self, account_id, start_date, end_date):
        start_date, end_date = as_date(start_date), as_date(end_date)
        account = self.accounts[account_id]
        result = {k: Decimal(0) for k in ("electric_peak_kw", "delivered_kwh", "received_kwh", "reactive_kvarh", "gas_ccf", "gas_therms", "water_kgal", "chilled_water_ton_hours", "chilled_water_peak_tons", "steam_klb", "generated_kwh", "exported_kwh")}
        result["electric_tou_kwh"] = {k: Decimal(0) for k in ("peak", "part_peak", "off_peak")}
        result["meters"] = []
        provider = account["providerId"]
        metrics = {"valley_electric_district": ["electric_kwh"], "sierra_gas_utility": ["gas_ccf"], "river_city_utilities": ["water_kgal"], "helios_onsite_solar": ["generated_kwh", "exported_kwh"], "northlake_thermal_plant": ["chilled_water_ton_hours", "steam_klb"], "ridgeline_wind": ["generated_kwh"]}[provider]
        if account_id == "ved_ridgeline_generator":
            metrics = ["received_kwh", "delivered_kwh", "reactive_kvarh"]
        start, end = utc_boundary(start_date), utc_boundary(end_date + timedelta(days=1))
        for meter in account.get("meters", []):
            if not meter.get("channels"):
                continue
            meter_id = meter["id"]
            opened, closed = self._lifetime(meter_id)
            if opened > end_date or (closed and closed < start_date):
                continue
            for metric in metrics:
                # Plant meters measure one physical commodity, not both.
                if provider == "northlake_thermal_plant":
                    units = {c.get("unit", "").lower() for c in meter.get("channels", [])}
                    if metric == "steam_klb" and "klb" not in units:
                        continue
                    if metric == "chilled_water_ton_hours" and not units.intersection({"ton-hr", "ton-hour", "tonh", "ton_hr", "ton_hours"}):
                        continue
                step = 10 if provider == "ridgeline_wind" else 15 if metric in ("electric_kwh", "generated_kwh", "exported_kwh", "received_kwh", "delivered_kwh", "reactive_kvarh") else 60
                total, peak = Decimal(0), Decimal(0)
                stamp = start + timedelta(minutes=step)
                while stamp <= end:
                    value = self.meter_value(meter_id, metric, stamp, step)
                    total += value
                    peak = max(peak, value * 60 / step)
                    if metric == "electric_kwh":
                        result["electric_tou_kwh"][self.tou(stamp)] += value
                    stamp += timedelta(minutes=step)
                if metric == "electric_kwh":
                    result["electric_peak_kw"] += peak
                else:
                    result[metric] += total
                if metric == "chilled_water_ton_hours":
                    result["chilled_water_peak_tons"] += peak
                unit = {"electric_kwh": "kWh", "generated_kwh": "kWh", "exported_kwh": "kWh", "received_kwh": "kWh", "delivered_kwh": "kWh", "reactive_kvarh": "kVArh", "gas_ccf": "ccf", "water_kgal": "kgal", "chilled_water_ton_hours": "ton-hr", "steam_klb": "klb"}[metric]
                meter_row = {"meterNumber": meter.get("syntheticMeterNumber", meter_id), "channel": metric, "quantity": total, "unit": unit, "readPeriod": {"start": start_date, "end": end_date}, "peak": peak}
                from .registers import enrich_meter
                registers = enrich_meter(self, meter_id, metric, start_date, end_date, total)
                channels = registers.pop("register_channels", [])
                if channels:
                    result["meters"].extend({**meter_row, **register} for register in channels)
                else:
                    result["meters"].append({**meter_row, **registers})
        result["gas_therms"] = (result["gas_ccf"] * Decimal("1.027")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        # A changed meter is one service; simultaneous services have additive demand.
        if account_id == "ved_library":
            result["electric_peak_kw"] = max((m["peak"] for m in result["meters"]), default=Decimal(0))
        return result

    def validate_anchors(self):
        """Resolve every allocation, surfacing impossible source constraints early."""
        counts = 0
        for (meter_id, metric), constraints in self.constraints.items():
            step = 10 if ("rwl" in meter_id or "ridgeline" in meter_id) and metric == "generated_kwh" else 15 if metric.endswith("kwh") or metric == "reactive_kvarh" else 60
            for index, constraint in enumerate(constraints):
                actual = sum(self._allocated(meter_id, metric, index, step).values(), Decimal(0))
                if actual != constraint["target"]:
                    raise ValueError(f"{constraint['bill_id']}: allocated {actual}, expected {constraint['target']}")
                counts += 1
        return {"bills": len(self.anchor_bills), "constraints": counts, "file_points": len(self.bindings)}
