# Bill Charge-Line Decomposition Spec (Phase 1)

How every Northlake monthly bill decomposes into `bill_charge_line` rows
(EEMSuite `BillItem`), so cost reports (`rp_CostBreakOut`, `rp_BillingCharges`,
`rp_RateComponentMap`) and GL coding (Phase 3) have itemized data, and every
bill's lines provably reconcile to its total.

**Scope boundary.** Phase 1 fixes the **line structure + reconciliation rules**
(below). Phase 2 (rate engine) supplies the **determinant rates** that make each
line computable from usage; until then, lines are reconciled against the known
bill total. The per-provider charge *codes* already live in each
`providers/<id>.yaml` `billCharges` block — this spec maps them to the
`bill_charge_line.charge_type` enum, the EEMSuite determinant kind, and the
decomposition arithmetic.

## charge_type → EEMSuite determinant kind

`bill_charge_line.charge_type` (from `schemas/synthetic-source-model.md`) maps to
the rate-engine determinant math kind (see
[subsystem-gap-analysis.md](subsystem-gap-analysis.md) §3):

| charge_type | EEMSuite determinant kind | Sign | Notes |
| --- | --- | --- | --- |
| `fixed` / `customer` | 400 Fixed by period (or 300 Fixed by day) | + | meter/facility/customer/base charge |
| `energy` | 200 Charge period (energy) | + | flat $/unit consumption |
| `tou` | 200 with a TOU schedule | + | one line per TOU period |
| `seasonal` | 200 with a season schedule | + | rate chosen by month |
| `tier` | 200 with multiple blocks | + | one line per block consumed |
| `demand` | 200 with `IsDemand=1` | + | billed on peak (max-interval) |
| `rider` / `surcharge` | 700 Bill adj (%) or 200 (per-unit) | + | program/public-purpose riders |
| `tax` | 800 Taxes (% on subtotal) | + | applied after all ≤800 charges |
| `credit` | 200 with negative block (or 700 neg %) | − | net-metering / generation credit |
| `adjustment` | 200 (precomputed) or post-script | ± | e.g. power-factor adjustment (synthetic stand-in — engine has no PF math) |
| `allocation` | 200 / 400 (internal) | + | internal cost-recovery line (district energy) |
| `generation` | 200 on a generation channel | + | PPA energy priced on kWh produced |
| `minimum` / `maximum` | 500 / 600 | ± | floor/cap (introduced in Phase 2) |
| `informational` | none (not a money line) | 0 | e.g. REC count; excluded from the bill total |

## Per-provider decomposition

Each row = one `bill_charge_line` on every monthly bill for that provider/rate.
`qty source` is what the line's quantity comes from; `rate source` points at the
`providers/<id>.yaml` rate component.

### Valley Electric District — `VED-TOU-GS` (electric)

| line | charge_type | commodity | qty source | rate source |
| --- | --- | --- | --- | --- |
| energy_peak | tou | electric | peak kWh | components.energy.peak |
| energy_part_peak | tou | electric | part-peak kWh | components.energy.part_peak |
| energy_off_peak | tou | electric | off-peak kWh | components.energy.off_peak |
| demand_charge | demand | electric | max 15-min kW | components.demand |
| facility_charge | fixed | electric | 1 / month | components.facilityCharge |
| power_factor_adjustment | adjustment | electric | precomputed | *(needs rate param — Phase 2; synthetic stand-in)* |
| public_purpose_program | rider | electric | % of energy or flat | *(needs rate param — Phase 2)* |
| utility_users_tax | tax | electric | % of pre-tax subtotal | *(needs rate param — Phase 2)* |

- **TOU split for interval-metered buildings** (Science Center, Student Center):
  peak/part/off kWh come from the 15-min interval data classified by the TOU
  calendar (summer has peak/part/off; winter has part/off only — see
  `seasons`).
- **TOU split for monthly-only buildings** (Admin Hall, Library, Cedar Row A/B):
  no interval data, so the bill carries TOU-split kWh from **per-TOU meter
  registers** (three register reads), not from interval data. (This is how real
  TOU meters bill non-interval accounts.) Winter bills omit the peak line.
- FY2025 bills (period ≥ 2025-01) use `VED-TOU-GS-FY25` rates (the
  `provider_rate_change` scenario); line structure is identical.

### Sierra Gas Utility — `SGU-GN-1` (natural gas)

| line | charge_type | commodity | qty source | rate source |
| --- | --- | --- | --- | --- |
| customer_charge | fixed | natural_gas | 1 / month | components.customerCharge |
| gas_commodity | seasonal | natural_gas | therms | components.commodity.winter/summer |
| gas_transport | energy | natural_gas | therms | components.transport |
| public_purpose_surcharge | rider | natural_gas | % or flat | *(Phase 2)* |
| utility_users_tax | tax | natural_gas | % of pre-tax subtotal | *(Phase 2)* |

- **Seasonal selection:** the `gas_commodity` rate is winter (Nov–Mar) or summer
  (Apr–Oct) by the bill's period month.
- **Estimated→corrected scenario:** the estimated bill carries the same line
  structure with estimated therms; the corrected actual bill supersedes it with
  the same lines at actual quantities.
- `ccf → therms` uses `thermFactor 1.027` (the `gas_commodity`/`gas_transport`
  quantity is therms).

### River City Utilities — `RCU-W-TIER` + `RCU-S-VOL` + `RCU-SW-ERU` (water/sewer/stormwater)

One account, one statement, three commodities:

| line | charge_type | commodity | qty source | rate source |
| --- | --- | --- | --- | --- |
| water_meter_charge | fixed | water | meter size (1/2/4 in) | RCU-W-TIER.meterCharge |
| water_tier1 | tier | water | kgal in 0–50 | RCU-W-TIER.tiers[0] |
| water_tier2 | tier | water | kgal in 50–200 | RCU-W-TIER.tiers[1] |
| water_tier3 | tier | water | kgal over 200 | RCU-W-TIER.tiers[2] |
| sewer_base | fixed | sewer | 1 / month | RCU-S-VOL.baseCharge |
| sewer_volume | energy | sewer | metered water kgal | RCU-S-VOL.volume |
| stormwater_eru | fixed | stormwater | ERU count | RCU-SW-ERU.eruCharge |

- **Tier blocks:** the three `water_tier*` lines partition the period's water kgal
  (each clamped to its block) and together equal total metered water. Buildings
  with no usage in a tier omit that line.
- **Derived sewer:** `sewer_volume` quantity = metered water kgal (apartments
  capped at a winter average per the provider note). Cedar Row accounts have no
  stormwater line.
- **Duplicate-import scenario:** re-importing the combined file must not
  duplicate any of these lines.

### Northlake Thermal Plant — `NTP-ALLOC-CHW` + `NTP-ALLOC-STEAM` (internal allocation)

Cost-center "bills" (account_kind = internal_cost_center), not utility bills:

| line | charge_type | commodity | qty source | rate source |
| --- | --- | --- | --- | --- |
| chilled_water_consumption | allocation | chilled_water | ton-hours | NTP-ALLOC-CHW.consumption |
| chilled_water_demand | demand | chilled_water | peak tons | NTP-ALLOC-CHW.demand |
| steam_consumption | allocation | steam | klb | NTP-ALLOC-STEAM.consumption |
| fixed_oandm_allocation | allocation | (plant) | fixed monthly share | *(annual plant O&M recovery; Phase 2 rate param)* |

- Only Science Center has both chilled-water lines (it has the ton-hour/tons
  sub-meter); Admin Hall / Library / Student Center carry steam_consumption only.
- These behave like bills for rollups (`baseline_monthly_bills` secondary).

### Helios Onsite Solar — `HOS-PPA-2024` (PPA invoice)

| line | charge_type | commodity | qty source | rate source | sign |
| --- | --- | --- | --- | --- | --- |
| ppa_energy | generation | solar_generation | generated kWh | components.ppaEnergy (escalating) | + |
| net_metering_credit | credit | solar_generation | exported kWh | components.netMeteringCredit | − |
| rec_transfer | informational | solar_generation | REC count | recOwnership | 0 |

- **Escalator:** `ppaEnergy` rate rises 2.0%/year (`annualEscalator`) — 2025
  bills use the escalated rate.
- **Net invoice:** total = `ppa_energy` − `net_metering_credit`. The
  `rec_transfer` line carries a REC count, **not money**, and is excluded from
  the total (informational).
- **Inverter-outage backfill:** generation gaps reduce `ppa_energy` qty until
  backfilled.

## Decomposition rules (cross-cutting)

1. **Reconciliation:** Σ(`bill_charge_line.amount` where charge_type ≠
   `informational`) = `bill.total_cost`, exactly, per bill.
2. **Quantity reconciliation:** per commodity, the consumption lines' quantities
   reconcile to the bill's `usage_quantity` (TOU lines sum to total kWh; tier
   lines sum to total kgal).
3. **Ordering:** taxes (`tax`, kind 800) apply to the sum of all preceding
   non-tax lines; if multiple taxes exist they compound in line order.
4. **Signs:** `credit` lines are negative; `informational` lines are zero.
5. **Line presence is conditional:** omit a line whose quantity is zero (e.g. a
   winter VED peak line, an empty water tier, a Cedar Row stormwater line).
6. **Estimated/corrected/duplicate** scenarios preserve the same line structure;
   corrections supersede, duplicates must not double lines.

## Worked examples (illustrative — exact rates finalized in Phase 2)

**VED Science Center, a summer month (interval-metered):**

| line | qty | rate | amount |
| --- | --- | --- | --- |
| energy_peak | 12,000 kWh | 0.241 | 2,892.00 |
| energy_part_peak | 18,000 kWh | 0.168 | 3,024.00 |
| energy_off_peak | 30,000 kWh | 0.112 | 3,360.00 |
| demand_charge | 220 kW | 18.40 | 4,048.00 |
| facility_charge | 1 | 64.00 | 64.00 |
| power_factor_adjustment | — | — | 85.00 |
| public_purpose_program | — | — | 120.00 |
| utility_users_tax | 5.0% × 13,593.00 | — | 679.65 |
| **total** | | | **14,272.65** |

energy lines sum to 60,000 kWh (= bill usage); lines sum to total. ✓

**RCU Admin Hall, 2-inch meter, 120 kgal water:**

| line | qty | rate | amount |
| --- | --- | --- | --- |
| water_meter_charge | 2in | 96.00 | 96.00 |
| water_tier1 | 50 kgal | 4.85 | 242.50 |
| water_tier2 | 70 kgal | 6.40 | 448.00 |
| water_tier3 | 0 kgal | 8.15 | (omitted) |
| sewer_base | 1 | 28.50 | 28.50 |
| sewer_volume | 120 kgal | 7.95 | 954.00 |
| stormwater_eru | 18 eru | 11.20 | 201.60 |
| **total** | | | **1,970.60** |

water tiers sum to 120 kgal (= metered water = sewer volume basis). ✓

## expectedAssertions

- `charge_lines_sum_to_total` — per bill, non-informational lines sum to
  `total_cost` (tolerance: 1 cent).
- `usage_lines_reconcile` — per commodity, consumption-line quantities sum to the
  bill's usage quantity.
- `tier_blocks_partition_usage` — RCU water tier lines partition total water kgal
  with correct block bounds (50 / 200).
- `tou_lines_sum_to_kwh` — VED TOU lines sum to total kWh; winter bills carry no
  peak line.
- `credit_is_negative` — HOS `net_metering_credit` amount < 0; `rec_transfer`
  amount = 0.
- `tax_on_subtotal` — `utility_users_tax` = tax_rate × (sum of preceding lines).
