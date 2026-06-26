# Phase 2 — Rate Engine Spec

Author the Northlake rate library so it fires **all 9 EEMSuite determinant math
kinds** and every rate construct, lighting up the 9 Rate Analysis reports and
making the Phase 1 charge lines computable from usage.

> **Entry path** (see [entry-path-and-gaps.md](entry-path-and-gaps.md)): nearly all
> of this is **UI-DIRECT** in the **WPF Rate Modeler** (all 9 determinant types,
> blocks, TOU/season/holiday schedules, ratchets, load factor, scripts, effective
> dates, commodity maps, multi-currency) — or bulk via **Rate Import**. RTP price
> point values arrive via **DATA-PATH**. **Gaps:** per-meter rate-class/**option
> binding** (A4) and the non-`Unique` "All" class (A5) have no UI — schedule #9's
> options can be *defined* on a rate but not *bound* to a meter through the UI.

EEMSuite model (verified): a `UtilityRate` → `UtilityRateClass` → determinants
(`UtilityDeterminant` via `UtilityRateDeterminant`). **The determinant is the
charge.** Each determinant has a `DeterminantTypeID` (the math kind), a
`ScheduleID` (season + TOU + holiday bundle), `UtilityDeterminantBlock` rows
(tiers), `UtilityDeterminantDate` rows (effective dates + `RTP_PtID`), optional
`UtilityDeterminantRatchet` / `UtilityDeterminantScript` / `UtilityDeterminantMember`.
Rates attach to meters via `UtilityMeterRates`.

## The 9 determinant kinds (verified `UtilityDeterminantType`)

| Type | Name | Construct |
| --- | --- | --- |
| 100 | RTP | hourly index price × interval usage |
| 200 | Charge Period | energy/demand, tiered/blocked, TOU, seasonal |
| 210 | Charge Period Fixed Value | stepped (one rate for the whole qty by step) |
| 300 | Fixed By Day | Σ value × days |
| 400 | Fixed By Period | flat per period |
| 500 | Min Value | minimum-bill floor |
| 600 | Max Value | maximum-bill cap |
| 700 | Bill Adj | % rider/adjustment on referenced charges |
| 800 | Taxes | % tax on charges ≤ 800 (compounding) |

`significance` (TOU): 1 All Hour, 2 Mid Peak, 3 Off Peak, 4 On Peak, 6 Super Off
Peak, 7 Super On Peak. `UtilityIntervalRule`: 1 Averaging, 2 Summing, 3 Minimum,
4 Maximum (demand uses 4 Max).

## Source-model extension

`schemas/synthetic-source-model.md` `rate_schedule` gains determinant-level
children (load-ready to `Utility*` tables):

- `rate_determinant` (rate_schedule_id, determinant_type 100–800, commodity,
  is_demand, interval_rule, schedule_ref, unit, use_load_factor, pre/post_script_ref)
- `rate_block` (rate_determinant_id, block_no, block_size/upper_bound, block_value, lf_size)
- `rate_effective_date` (rate_determinant_id, effective_date, block_values, rtp_point_ref, use_price_ranges, high/low_range)
- `rate_schedule_calendar` (schedule_ref, season {start/end month-day}, tou {hours-of-week, significance}, holiday_set)
- `rate_ratchet` (rate_determinant_id, current_pct, previous_pct, ratchet_months, aggregation_rule)
- `rate_class_option` (rate_schedule_id, class_type, option_name)  — voltage/phase/tax-exempt/farm
- `rate_meter_assignment` (rate_schedule_id, meter_id, rate_class_option_id, bill_scenario, start_date)

## The 10 Northlake rate schedules

Designed so that, between them, every `UtilityRates_Run_NNN` proc and every
construct fires. "Extends" = enrich an existing provider rate; "new" = a new rate
object/option in the library.

### 1. `NL-RES-Tiered` — Cedar Row residential electric *(extends VED for Cedar Row)*
Determinants: **400** customer charge; **200** inclining-block energy (≥3 blocks:
0–500 / 500–1500 / 1500+ kWh); **500** minimum bill; **800** state + municipal
tax (two members). Fires 200(blocks), 400, 500, 800; tier clamping.

### 2. `NL-GS-TOU-Seasonal` — campus commercial electric (flagship) *(extends VED-TOU-GS)*
Determinants: **400** facility charge; **200** On-Peak energy (sig 4) + **200**
Off-Peak energy (sig 3) on TOU schedules; **200** summer demand + **200** winter
demand (`IsDemand=1`, IntervalRule 4) on seasonal schedules; a **holiday set**
mapping weekday holidays to off-peak; **700** % public-purpose rider; **200**
per-unit renewable rider; **800** utility-users tax. Fires TOU, seasons, holiday
calendar, both rider styles, demand, the full `significance` taxonomy. This is the
rate the Phase 1 VED charge lines decompose against.

### 3. `NL-LG-Ratchet` — Science Center large demand *(new VED large-GS option)*
Determinants: **200** demand with a **`rate_ratchet`** (80% / 11-month look-back);
**200** energy with **load factor** (`use_load_factor`, `lf_size`); **400** fixed.
Needs ≥12 months interval with a strong summer peak so the winter ratchet floor
binds. Fires the ratchet path (almost unseeded product-wide).

### 4. `NL-CONTRACT-2Part` — base/excess contract demand *(new, campus central plant electric)*
Determinants: **200** base contract demand + **200** excess demand (split by a
**pre/post `rate_determinant.script`**); base + excess energy; **400** fixed;
**800** tax. Fires determinant scripts + two-part contract demand.

### 5. `NL-RTP-Index` — real-time pricing *(new VED RTP option, Student Center)*
Determinants: **100** RTP referencing an **hourly price-signal point**
(`rtp_point_ref` → a new `reference_channel` carrying hourly $/kWh); a second
**100** with `use_price_ranges=1` + high/low band; **400** delivery charge.
**The only way to fire `UtilityRates_Run_100`.** Requires a new synthetic hourly
price channel (add to `scenarios/demo-university-v1.yaml` referenceChannels).

### 6. `NL-STEP-Demand` — stepped + capped *(new, Town Center anchor — see Phase 4)*
Determinants: **210** stepped demand (one rate by which step the kW lands in);
**600** maximum-bill cap on the subtotal. **The only way to fire 210 and 600**
(both zero-seeded product-wide).

### 7. `NL-GAS-FuelAdj` — gas with monthly fuel adjustment *(extends SGU-GN-1)*
Determinants: **300** fixed-by-day customer charge; **200** seasonal commodity
(winter/summer) + **200** transport with **unit conversion** (ccf→therm, factor
1.027); a **"Fuel Cost Adjustment" 200** with **monthly `rate_effective_date`
rows** (a new BlockValue per month → effective-dated proration within a bill
period); **800** tax. Fires 300, unit conversion, effective-dated proration.

### 8. `NL-MULTI-Commodity` — water/sewer/CHW/steam *(extends RCU + NTP)*
Determinants: water tiered (**200** blocks), sewer as **700** % of water,
chilled-water demand in **tons** (**200** `IsDemand`), steam in **klb** (**200**).
Uses `UtilityCommodityMap` for ENERGY STAR component mapping (`rp_RateComponentMap`).
Fires multiple MeasureTypes + unusual units (tons, klb).

### 9. `NL-OPTIONS-Phase` — rate-class options *(new VED variant)*
An "All" base class + selectable option classes: **Primary vs Secondary voltage**,
**Single/Three-phase**, **Tax-Exempt**, **Farm Discount** (`rate_class_option`).
Meters pick options via `rate_meter_assignment.rate_class_option_id`. Fires class
assignment + `rp_RateClassAssignment`.

### 10. `NL-MULTI-Currency` — cross-currency *(optional)*
A rate with `CurrencyID` = C$ billed against a US$ reporting unit profile. Fires
currency conversion. (Optional completeness; flag as synthetic.)

## Meter assignment

Each schedule attaches via `rate_meter_assignment` over ≥13 months:
- `NL-GS-TOU-Seasonal` → Admin Hall, Library electric (monthly TOU registers) +
  via interval for Science/Student is `NL-LG-Ratchet`/`NL-RTP-Index`.
- `NL-RES-Tiered` → Cedar Row A/B electric.
- `NL-LG-Ratchet` → Science Center electric. `NL-RTP-Index` → Student Center.
- `NL-CONTRACT-2Part` → central-plant electric. `NL-STEP-Demand` → Town Center anchor.
- `NL-GAS-FuelAdj` → all SGU meters. `NL-MULTI-Commodity` → RCU + NTP meters.
- `NL-OPTIONS-Phase` → an Admin Hall variant (Primary voltage, Tax-Exempt option).

## Unsupported constructs (synthetic stand-ins — document explicitly)

The engine cannot model these natively; represent and label as stand-ins:
- **Power factor** → precompute the adjustment quantity into a billing channel or
  a post-`script` (the VED `power_factor_adjustment` line).
- **Coincident peak / 4-CP** → script the determinant value or mark CP hours via
  an RTP-style point.
- **CPP / critical-peak events** → a TOU schedule hard-coding event hours, or RTP
  price spikes on event days.
- **Net-metering banking** → no cross-month credit balance; approximate with a
  per-month negative `credit` block (HOS `net_metering_credit`).

## expectedAssertions

- `every_run_proc_fires` — each `UtilityRates_Run_100..800` executes ≥ once across
  the library.
- `rtp_priced_from_point` — `NL-RTP-Index` bill = Σ(interval kWh × hourly price);
  the price-range variant caps at high/low.
- `stepped_and_cap` — `NL-STEP-Demand` picks one step rate; `600` caps the
  subtotal when it would exceed the cap.
- `ratchet_floor_binds` — a winter `NL-LG-Ratchet` billed demand = 80% of the
  prior summer peak when current demand is lower.
- `tiers_and_min_bill` — `NL-RES-Tiered` blocks clamp to usage; a low-usage month
  tops up to the `500` minimum.
- `tax_compounds_in_order` — two `800` taxes apply in determinant order over
  members.
- `rate_comparison_shadow_bills` — `rp_RateComparison` recomputes a meter on an
  alternate schedule and diffs vs the baseline scenario.
- `class_option_assignment` — `rp_RateClassAssignment` shows the Primary/Tax-Exempt
  options on the `NL-OPTIONS-Phase` meter.
