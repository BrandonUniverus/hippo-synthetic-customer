# Phase 4 — Tenant Rebilling Spec

Exercise **every** allocation and reconciliation path. Vehicle (owner decision):
**both** a new mixed-use **Northlake Town Center** (commercial allocation) and
**sub-metered Cedar Row** (residential allocation). Lights up all 14 Tenant
Rebilling reports + `rp_TenantMap`.

> **Entry path** (see [entry-path-and-gaps.md](entry-path-and-gaps.md)): bill
> allocation config (web), WUI master-point config (web), and bill-generation config
> (WPF `TenantRebillView`) are **UI-DIRECT**; meter allocation has an on-demand
> **run** button. **Note:** full tenant-**bill generation** runs via a scheduled
> SQL Agent job (`Job_BillAllocation`), not an on-demand button (**UI-THEN-RUN**,
> engine must be running). **Gap:** tenant **accruals** have no UI (A2). The 7
> allocation methods are selectable; the engine branches only for method 1 (%/amt)
> and 6 (aggregation) — others are method-1 rows with precomputed shares.

EEMSuite facts (verified): two modes — **Bill Allocation** (split a parent bill's
cost to tenants) and **Bill Generation** (rate × meter use → tenant bill) — plus
the lower-level **WUI point allocation** (split a master point's use to
sub-points). **7 bill-allocation methods**, **3 point-allocation methods**
(Percentage-Based is catalog-only/unimplemented), 4 bill-generation types
(Off/Manual/Auto/Auto-Regen), reconciliation via penny-true-up + `rp_BillReconciliation`
(source = interval or bill data). Most allocation "methods" share one engine — the
percentages are precomputed and stored as method-1 detail rows.

## Source-model extension

Add: `tenant_space` (building, name, floor_area, occupancy), `bill_allocation_config`
(master_meter, method 1–7, fiscal_window, combine_overhead), `bill_allocation_detail`
(config, tenant_space, percent, fixed_amount, is_amount_fixed, overhead_pct/amt,
seq), `bill_allocation_map` (master_bill, allocated_bill), `bill_aggregation_map`,
`pt_allocation_config` (master_pt, alloc_pt, method 1–3, effective), `pt_allocation_index`
(child, index_value, unit, effective), `bill_gen_config` (meter, scenario,
gen_status 1–4, schedule_code, recon_source 1/2). New EEM company **Northlake Town
Center** + site/buildings/tenants extend `security/` + `scenarios/` manifests.

## A. Northlake Town Center (commercial)

New mixed-use site under a new EEM company `northlake_town_center` (companyType
`commercial_multi_tenant`). Buildings + masters + tenants:

| building | master meter | tenants (sub-meters / spaces) |
| --- | --- | --- |
| Market Hall (retail) | `tc_market_main` electric | Anchor Store, 4 in-line shops, Food Court, Common Area |
| Tower (office) | `tc_tower_main` electric | Floors 1–4 (sub-metered), Landlord/house meter |
| Campus Annex (demand) | `tc_annex_main` demand-metered | Bldg A, B, C (usage + coincident demand) |
| Substation feed | `tc_substation_master` | Substation 1, Substation 2 |
| — (cost center) | `tc_property_total` | rolls up all tenant bills |

### Allocation method coverage (one config each → every method)

| # | method | config |
| --- | --- | --- |
| 1 | Fixed Amount & % | Market Hall → Anchor fixed $2,000; Food Court 15%; in-line shops remaining % — with **overhead** in both combined (`combine_overhead=1`) and separate modes |
| 2 | Fully Submetered | Tower → 4 floors, each a sub-meter (consumption share) |
| 3 | Partially Submetered | Tower variant → 3 submetered floors + landlord/house meter for the remainder |
| 4 | Building Areas | Market Hall in-line shops → share by `tenant_space.floor_area` |
| 5 | Partially Submetered w/ Coincident Demand | Campus Annex → Bldg A/B/C by usage + coincident peak |
| 6 | Bill Aggregation | `tc_property_total` ← sum of all tenant bills (children→parent, `bill_aggregation_map`) |
| 7 | Metered Substations | Substation feed → Substation 1/2 by % of usage |

## B. Cedar Row sub-metering (residential)

Extend the existing Cedar Row A/B (today common-area only) with **unit-level
sub-meters**:
- Cedar Row A: 60 unit electric + water sub-meters; Cedar Row B: 64.
- Common-area master allocated to units by **method 2 (fully submetered)** for
  electric and **method 4 (building areas/occupancy)** for the winter-capped
  water, with **overhead** for common-area lighting.
- Residential angle complements the commercial Town Center, covering the same
  methods on a housing community.

## C. WUI point families (master point → sub-points)

Separate from bill allocation; needs interval + index + area + a generation rate.

| family | method | setup |
| --- | --- | --- |
| `wui_market_electric` | 1 Weighted Use Index | master electric point + 3 child points each with `pt_allocation_index` (kWh/sqft-day) + area + `bill_gen_config` rate |
| `wui_tower_electric` | 2 Measured Use + residual | master + one **measured** child (own interval, subtracted) + one WUI child (gets residual) |

**Deliberate fail-reason fixtures** (`PtAllocFailReason`): a child with **no
index** (reason 2); one with **no area** (reason 3); a master/child with
**partial interval** (reason 1); a 3-level chain where the mid master fails so the
leaf inherits **reason 4**; a valid child with **no rate** (reason 5). Plus a
**method-3 (Percentage Based)** child to demonstrate it is **silently ignored**
(documented product gap).

## D. Bill generation

Assign a multi-component rate (Phase 2 determinants + `UtilityCommodityMap` to ≥2
charge commodities) to a tenant meter under both an **Actual (-1)** and a
**non-actual** scenario. Replicate `bill_gen_config` four times with
`gen_status` = **1 Off / 2 Manual / 3 Auto / 4 Auto-Regen**; schedule code **CC**
(Company Calendar). Seed ≥3 periods of interval data so the generator produces
`UtilityBillGenLog` + child bills. Lights up GeneratedBills, BillGenerationConfig,
BillMaintenance, RateComponentMap.

## E. Reconciliation

Give one Town Center meter a **Bill Meter Reconciliation** scenario
(`ScenarioTypeId 20`): `recon_source=1 (interval)` on some meters, `=2 (bill)` on
others. Build a **deliberate rate/usage mismatch** on one meter so
`rp_BillReconciliation` shows nonzero amount/quantity variance (over/under
recovery). The allocation path's penny-true-up still makes child bills sum to the
parent.

## F. Tenant accruals

A tenant account missing its current-period bill, with a manual 2300-tagged bill
(open accrual) + a trued-up accrual↔reversal pair — feeding `rp_accruals` /
`rp_mpaaccruals` in the tenant context.

## expectedAssertions

- `every_alloc_method_configured` — one `bill_allocation_config` per method 1–7
  exists and produces tenant bills.
- `children_sum_to_parent` — for each allocation, Σ child bill amounts = parent
  bill amount (penny-true-up), incl. overhead lines.
- `aggregation_rolls_up` — `tc_property_total` bill = Σ consumed child bills
  (`bill_aggregation_map`).
- `wui_split_sums_to_master` — WUI family child allocated use = master residual,
  proportional to index × area × days.
- `wui_fail_reasons` — each of fail reasons 1–5 is produced by its fixture; the
  method-3 child yields no output and no failure.
- `bill_gen_types` — Off/Manual/Auto/Auto-Regen behave per type; Auto creates
  missing-period bills, Auto-Regen regenerates on new data.
- `reconciliation_variance` — `rp_BillReconciliation` shows the deliberate nonzero
  variance with interval vs bill source.
- `tenant_accrual_lifecycle` — open tenant accrual listed, then trued up to zero.
