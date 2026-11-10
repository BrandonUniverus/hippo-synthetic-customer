---
title: Stage 7. Allocation and tenants
subtitle: Northlake Town Center, Cedar Row sub-metering, WUI point families, reconciliation and Ridgeline Wind's generated statement
status: Ready to enter
---

# Stage 7. Allocation and tenants

Stage 7 builds the new mixed-use Northlake Town Center company and its hierarchy, then exercises
every Bill Allocation method, every WUI point-allocation method and every bill generation type the
product has, plus the Thermal Plant's internal cost recovery and Cedar Row's residential
sub-metering. It is the tenant-rebilling stage: two related but different features share the name
"Tenant Rebilling" in the product — Bill Allocation (splitting a parent bill's dollar cost across
tenants) and WUI point allocation (splitting a master point's measured use across sub-points) — and
this stage uses both, on top of Bill Generation (rate times meter use), which the earlier rate and
meter stages already stood up.

**What the product actually does (read in its source, 2026-11-10).** Only two of the seven Bill
Allocation methods compute anything: method 1 (Fixed Amount and %) and method 6 (Bill Aggregation).
Methods 2, 3, 4, 5 and 7 can be configured but have no calculator, so a master bill under them produces
no allocated bill (Step 4). Bill Allocation, Bill Generation and WUI each need their meters to have a
Measure Type and a billing account with a provider, which the earlier hierarchy did not give them (Steps 2
and 6). Town Center now has its own rates (Step 9) and a small scripted data set with every expected
value (Step 10).

**Added 2026-10-01: Ridgeline Wind.** The Thermal Plant bought a ten-turbine wind company on July 1,
2024, and Stage 7 gains Step 8 and one more Run Now in Step 7. Ridgeline is Bill Generation the other
way round from the tenants: no tenant and no allocation, one account (SYN-RWL-G-0000001) whose
monthly internal transfer statement EEM writes itself, priced at $0.058 a kWh on the ten turbines
less a $1,250.00 monthly research credit. EEM generates a bill per meter, not per account (finding
66), so Stage 2 carries one logical billing meter whose one point is the farm aggregate of the ten
turbines, and this step generates from it. The first statement, July 2024, must equal the hand-made
one to the cent, $129,330.27. Steps 1 through 6 take nothing from Ridgeline.

## Before you start

- Stages 1 through 6 are green. This stage adds a new company and hierarchy of its own (Town Center)
  and adds records to Northlake University and Cedar Row Apartments, both of which must already exist
  (companies 6 and 3).
- **Order of work.** Steps 1 and 2, then Step 9 (the two tenant rates, which Step 6 picks from), then
  Stage 3's Town Center data (Step 10 lists the 22 points and their constants), then the master bills of
  Step 10 on Bill Entry Web, then Steps 3 to 8.
- Two catalog gaps must be closed before typing this stage, and neither is customer data: `dbo.
  BillAllocationMethod` may have only method 1 on this instance (methods 2-7 are present in the reference
  EEMSuite database; the product has no seed for them) and `dbo.PtAllocationMethod` has only 2 of its 3 rows
  (Percentage Based is missing). Install both, the same way earlier stages treated other ".bak, not
  in git" catalogs as product install data. Step 4 and Step 5 name the exact rows.
- Enter everything through the applications. If a screen cannot take a value this stage needs, stop
  and record it under Findings at the end of this chapter and in
  [product findings](../product-findings.pdf). Do not fill the gap with SQL.
- Step 8 also needs Ridgeline Wind in place: its Stage 2 account, meters (the billing meter included) and
  farm aggregate, Stage 3's 10-minute turbine data and aggregation, and Stage 4's rate RWL-XFER-2024 with
  its determinants under the class All, their commodity mapping and its assignment. The step lists the
  order.

## Step 1. Northlake Town Center company

**Where:** Database Administrator, Nodes (the company node's Definitions tab); Users & Groups.

**Enter:** [01-town-center-company.yaml](01-town-center-company.yaml).

**Order inside the editor:** same as Stage 1 step 1 — Definitions first, save, then Levels, Company
Address, Company Contact and Bill Scenarios. Then create the two groups and the one user under Users
& Groups.

**EEM creates for you:** the Actual bill scenario and the company calendar through next year (fiscal year equals calendar year, so period 1 of 2024 is January 2024).

**Bill Scenarios:** add Budget and Bill Meter Reconciliation to Used, alongside Actual. Budget holds
Anchor Store's second rate row (Step 6); Bill Meter Reconciliation is what the Bill checkbox on that
row copies the rate to (Step 7). The Tenant Rebill scenario picker never lists it.

**A loose end for Stage 1's screen, not this one:** once Town Center is saved, go back to Utility
Providers > Valley Electric District > Associated Companies and give Town Center a vendor number.

**Record:** the Company ID, and the Group ID/User ID (already the keys you typed).

**Check:** `town_center_company`.

## Step 2. Town Center hierarchy

**Where:** Database Administrator, Nodes (Property, then Buildings, then Meters, then Points); the
Add Billing Account dialog, opened from a meter.

**Enter:** [02-town-center-hierarchy.yaml](02-town-center-hierarchy.yaml).

**Order inside the tree:** the Property node, save; the five Buildings (Market Hall, Office Tower,
Campus Annex, Substation Feed, Property Total), save each; then every Meter under its building —
save a Billing Account first through Add Billing Account so the meter has one to attach to. Points
last.

**What every meter needs, and why.** Each of the 22 meters has Measure Type Electricity and a billing
account whose Utility Provider is Valley Electric District (US Dollar). The Add Billing Account dialog
will not save an account without a provider, and the meter's provider is copied from its account.
Without them the Tenant Rebill rate list is empty (it lists the meter provider's rates of the meter's
measure type), a rate of another measure type is refused, and the Add Allocated Meters picker rejects the
meter (different measure type, no account or a different currency). The four masters are Bill Entry
accounts (their bills are keyed in Step 10); the four tenants that Step 6 generates for are Bill
Generation accounts; the rest are Bill Allocation accounts.

**Points (26 in all):** the measured kWh and kW points that Stage 3 loads (Step 10 lists them) and four
Estimated kWh points under Shop 3, Shop 4, Common Area and Landlord/House that Weighted Use Index writes
into. Floor area (Area tab, SqFt) goes on every tenant space the Building Areas method and the WUI
families read.

**Record:** the MetaWorldID, MeterID and BillingAccountID for every row.

**Check:** `town_center_hierarchy` (level counts, account types, provider and measure type on every
meter, and each floor area against its expected value).

## Step 3. Thermal Plant chilled water and steam cost recovery

**Where:** Web, Bill Allocation Configuration (`#/reporting/BillAllocationConfiguration`).

**Enter:** [03-thermal-plant-allocation.yaml](03-thermal-plant-allocation.yaml).

**Order inside the screen:** same as Step 4 below — pick the master meter, commodity, method and
effective period, save, then add candidates.

**Read this file's notes before typing it.** It makes an explicit, flagged assumption about how
Northlake Thermal Plant's internal cost recovery reaches Northlake University's buildings, because
Stage 2 (written in parallel) had not landed a node shape to build against. Confirm the two master
accounts and the six served-building accounts agree with whatever Stage 2 actually created before
treating this step as final.

**Record:** the BillAllocationConfigID for both configs.

**Check:** `allocation_configs` (this step's two rows are included in that check: 2 and 6 detail rows).

## Step 4. Bill Allocation Configuration, one config per method

**Where:** Web, Bill Allocation Configuration (`#/reporting/BillAllocationConfiguration`).

**Enter:** [04-bill-allocation-configs.yaml](04-bill-allocation-configs.yaml), 8 configs covering
methods 1 through 7.

**Order inside the screen:** Master Meter, Commodity, Method and Effective From first, save; then
Add Allocated Meters through the Eligible Meters picker; then Combine Overhead; then Balance to
100% if a method 1 config's percentages do not already total 100.

**Which methods compute.** Only method 1 and method 6. The bill-allocation procedures go on only when
the master meter has a method 1 config for the bill's period and then split by the typed Allocation %
and Allocation Amount; they never branch on the method. Methods 2, 3, 4, 5 and 7 have no calculator
(ADR-015), so those five configs can be entered and a master bill under them gets no allocated bill.
The earlier text of this step said the engine would compute the shares from consumption, area or usage
when Process Meter Allocations runs. It does not: Process Meter Allocations is the WUI run of Step 5.

**What you type.** Method 1: Allocation %, Allocation Amount with Fixed, and Overhead % on every row.
Overhead is added on top of each tenant's share, not carved out of it. Method 6 runs backwards: its
master, Property Total, is the receiver and every row feeds it, and each row is typed Allocation % 100
(a method 6 row left at 0 aggregates nothing). Methods 2, 3, 4, 5 and 7: add the candidates and leave
their percentages at 0.

**Known values.** With the master bills of Step 10 (Mall-Main 30,000.00 in 2024-01 and 2025-01): Anchor
Store 2,040.00, Food Court 4,284.00, each of Shops 1 to 4 2,284.80, Common Area 15,136.80, which is
30,000.00 of shares plus 600.00 of overhead; Property Total 30,600.00 in both periods. For the other
five masters the check asserts the opposite: the bill exists and nothing was allocated.

**Record:** the BillAllocationConfigID for every config.

**Check:** `allocation_configs`, then after Step 7 `method_1_allocation`, `tenant_bills_sum_to_parent`,
`methods_2_3_4_5_7_not_computed_today` and `method_6_property_total`.

## Step 5. WUI point families and fail-reason fixtures

**Where:** Web, Point Family Configuration (`#/reporting/PointFamilyConfiguration`) — a row's action
opens the Master Point Configuration modal.

**Enter:** [05-wui-point-families.yaml](05-wui-point-families.yaml): two real point families
(wui_market_electric, wui_tower_electric) and a set of deliberately broken fixtures covering all 5
`PtAllocFailReason` values plus the unimplemented Percentage Based method. The fixture nodes are in no
hierarchy file yet, and No Area and No Rate need separate meters (a known problem in the file's notes).

**Order inside the modal:** pick or confirm the master point, then Add Child Points with each
child's Allocation Method and Start Date.

**Before this step:** install the missing `PtAllocationMethod` row (3, Percentage Based) — without
it the last fixture cannot even be selected.

**Index values have a screen.** The Web report WUI Point Use History lists every Weighted Use Index
child; its create action opens a small view with three inputs (Unit, Fiscal Start, Index Value), which
calls `WUIPtAllocationIndex_Save`. Enter 0.40, 0.50, 0.15 and 0.90 kWh per SqFt per day for the four
Estimated kWh children, fiscal start 2024-01 (the file has them). The expected allocated use for
2024-01 is in Step 10: Shop 3 26,318.37, Shop 4 25,306.12, Common Area 134,375.51 and Landlord/House
230,640 kWh.

**Record:** nothing new; the modal has no separate ID beyond the point IDs already recorded when the
points were created.

**Check:** `wui_families`, `wui_index_values` and, after Step 7, `wui_allocated_use_2024_01`.

## Step 6. Tenant bill generation types and Cedar Row residential allocation

**Where:** Database Administrator, Nodes (a meter node's Tenant Rebill tab); Web, Bill Allocation
Configuration.

**Enter:** [06-tenant-bill-generation.yaml](06-tenant-bill-generation.yaml): 4 Tenant Rebill entries
(the 4 generation types, on Anchor Store, Food Court, In-line Shop 1 and In-line Shop 2) and 4 Bill
Allocation Configuration configs for Cedar Row.

**Order inside the Tenant Rebill tab:** pick the Bill Scenario at the top, add a Rate Configuration
row and save, then switch to Bill Generation and add its row (Assigned Rates, Fiscal Start/End,
Schedule, Status, Available %, Offset). A company administrator enters the Bill Generation row.

**Rates.** The tab offers the meter provider's rates of the meter's measure type, so the rates of
Step 9 appear because Step 2 gave the tenants a provider and a measure type. Anchor Store takes
TC-STEP-DEMAND (Actual and Budget, from 2024-01-01); Food Court, Shop 1 and Shop 2 take TC-FLAT-GS from
2026-01-01. The earlier NL-STEP-Demand, NL-RES-Tiered and NL-MULTI-Commodity are gone (the first two
moved to Stage 4's Rate Lab, the last never existed).

**The four generation types**, each over the single period 2026-01 so generated bills never double the
allocated bills of 2024 and 2025: Anchor Store Off (Bill ticked, which creates the reconciliation of
Step 7), Food Court Manual, Shop 1 Auto, Shop 2 Auto w/ Auto Regen. A generation row needs the meter to
have child points; Step 10 gives them their data.

**Cedar Row.** The four masters keep the real tariffs Stage 4 assigns and take no rate here. The four
configs (method 2, one per building per commodity, 248 apartment rows) are not enterable as written
and compute nothing: the apartment submeters have no billing account (Stage 2), which the eligible-meter
picker requires, and method 2 has no calculator. They are kept for the day both are fixed.

**Record:** nothing new on the Tenant Rebill tab; the 4 Cedar Row BillAllocationConfigIDs.

**Check:** `generation_configs`, `rate_assignments`, `allocation_configs`, and after Step 7
`generated_tenant_bills_2026_01`.

## Step 7. Allocation runs, scheduled tasks and reconciliation

**Where:** Web, Process Meter Allocations (`#/reporting/ProcessMeterAllocations`); Web, Task Manager
(`#/tasks/manager`); the Bill Reconciliation report.

**Enter:** [07-allocation-runs-and-reconciliation.yaml](07-allocation-runs-and-reconciliation.yaml).

**Order:** run Process Meter Allocations for 2024-01 through 2024-03 first (it needs Step 5's
families and indices and Stage 3's data). Key the master bills of Step 10, then schedule and Run Now
Task_Tbl 24 (Process Bill Allocation, which also aggregates Property Total), and only then 42 (Run Bill
Gen) from Task Manager. Task_Tbl 47 (Run WUI Process) is system-only. Run Now on Run Bill Gen once more
after Step 8, once Ridgeline's data is in.

**Reconciliation is the Bill checkbox, nothing else.** The Tenant Rebill scenario picker leaves out
Bill Meter Reconciliation, and a mismatched rate under it cannot be typed. Ticking Bill on Anchor
Store's Actual rate row copies the same rate to that scenario and creates its Bill Generation row
(schedule BL, Auto w/ Auto Regen, Interval). Schedule BL is the only one that records the real bill the
report compares with. So the variance comes from the actual bill, not a second rate: Anchor Store's
allocated bills are 2,040.00; its own interval data priced at TC-STEP-DEMAND is 15,000.00 (capped);
variance -12,960.00 in 2024-01 and 2025-01.

**Tenant accruals have no entry path at all** — no UI, API or scheduled task writes
`BillAccrualMap`. This step does not attempt one; see Findings.

**Record:** nothing generated; this step produces data, not IDs.

**Check:** `allocation_runs`, `tenant_bills_sum_to_parent`, `reconciliation_anchor_store`.

## Step 8. Ridgeline Wind transfer statement

**Where:** Database Administrator, Nodes (a meter node's Tenant Rebill tab); Web, Generated Bills
(`#/reporting/GeneratedBills`) to watch it.

**Enter:** [08-ridgeline-transfer-generation.yaml](08-ridgeline-transfer-generation.yaml): the Bill Generation
row for Stage 2's billing meter, with the acceptance case, the WTG-07 outage months and the run order.

**Bill Generation with no tenant.** The Thermal Plant buys its own wind farm's output at a transfer
price and nobody sends a bill: EEM writes the monthly statement for account SYN-RWL-G-0000001 from
the ten turbines' Generated kWh 10m points and rate RWL-XFER-2024 ($0.058 a kWh and a $1,250.00
monthly research credit). The first statement, July 2024, must equal Ridgeline accounting's hand-made
one to the cent: 2,251,384 kWh, $130,580.27 of energy, less the credit, $129,330.27.

**Why a billing meter and not ten turbine meters.** Generation prices the points under one meter node
and writes one bill per meter per month (finding 66). On the ten turbine meters it would write ten
bills a month, each repeating the credit. So Stage 2 carries a billing meter, Ridgeline Farm Transfer
Meter (SYN-RWL-M-0110000), under Ridgeline Turbine Field, whose one point is the farm aggregate
Ridgeline Farm Generated kWh 10m, the way EEM's own demo database bills from aggregates, and this step
generates from it. The turbine meters keep their account and get neither a rate nor a generation row.

**Order inside the tab:** the meter must already have its aggregate (the Bill Generation row cannot be
saved on a meter with no point), and Stage 4 has assigned RWL-XFER-2024 to it with Bill unchecked. This
step adds only the Bill Generation row: Company Calendar, Auto, 2024-07 to 2025-12, Available % 100,
Offset 0. A company administrator enters it, because the save refuses anyone else.

**Run order:** Stage 3's turbine data and aggregation, Stage 4's rate (determinants under All,
commodity mapping, assignment), then this step. The Billing Charges report on the billing meter previews July
before any bill is written; then Run Now on Run Bill Gen (Step 7) writes one bill per complete month.
A month below Available % waits; it is not an error. Two months are short for clock reasons. The
engine cuts months on the points' stored Pacific time while the SCADA clock stays on PST (finding 46),
so July 2024 starts an hour before the SCADA's own July: Stage 3's feed must begin with the row stamped
2024-06-30 23:10 PST (the ten minutes from Pacific midnight) or July is an hour short, waits, and the
acceptance case cannot pass. March 2025 holds 4,458 of 4,464 whatever the feed, because Pacific time
skips an hour on 2025-03-09: set Available % to 99, Run Now once, and set it back to 100 (assumed; a
manual Create needs Bill Entry Web, which no Thermal Plant user holds). The engine reads a stamp as the
end of its interval, so a month takes stamps after 00:00 on the 1st up to and including 00:00 on the
next 1st. The SCADA file is written with interval-end stamps and Stage 3 cuts its sums the same way, so
a feed through the row stamped 2026-01-01 00:00 PST is exactly July 2024 to December 2025.

**What to expect:** 18 statements, 2024-07 to 2025-12, each with the transfer-energy line and the
credit once. WTG-07's gearbox outage (2025-02-11 to 2025-04-22) makes February to April lower with no
adjustment line: the turbine keeps reporting zero energy, so it is lost production, not missing data.
The statement is dated its period end, not 2024-08-02, and has no invoice number, due date or the
four informational rows of the hand-made one; its two lines and total must match.

**Record:** nothing new; the billing meter's IDs are Stage 2's.

**Check:** `ridgeline_setup` (asserts the billing meter, mapping, generation row, 18 log rows and statements, July 2024), `ridgeline_billing_meter`, `ridgeline_commodity_mapping`, `ridgeline_generation_config`,
`ridgeline_generation_log`, `ridgeline_generated_statements`, `ridgeline_acceptance_2024_07`,
`ridgeline_outage_months`.

## Step 9. Town Center tenant rates

**Where:** Database Administrator, RateModeler > Rate Edit, under Valley Electric District. Enter this
step before Step 6.

**Enter:** [09-town-center-tenant-rates.yaml](09-town-center-tenant-rates.yaml): TC-FLAT-GS (customer
charge 45.00 and energy 0.14 a kWh) and TC-STEP-DEMAND (a stepped demand charge of Charge Type 210 with
blocks 100/150/rest at 1,500.00, 3,200.00 and 6,800.00, energy 0.142 a kWh and a Maximum Bill of type
600 at 15,000.00). Every charge has a commodity mapping, because an unmapped charge adds to the bill
total and writes no line.

**Expected bills** (constant loads, 744-hour January): Food Court 6,294.60, Shop 1 878.28, Shop 2 669.96
on TC-FLAT-GS; Anchor Store 15,000.00 on TC-STEP-DEMAND (demand 3,200.00 from the 100 to 250 kW block,
energy 12,677.76, Maximum Bill line -877.76). A 28-day month stays under the cap (14,650.88).

**Record:** the rate IDs.

**Check:** `tenant_rates`. Stage 4's `rates_by_provider` reads two more Valley Electric rates once this
step is done.

## Step 10. Town Center data, master bills and expected values

**Where:** Web, Bill Entry (the master bills); Stage 3 (the interval data).

**Enter:** [10-town-center-data-and-bills.yaml](10-town-center-data-and-bills.yaml).

**Why it exists.** Town Center had no interval data, no bills and no source file, so no case had a value
to compare with. This file is the smallest set that gives each one: 22 points with a constant hourly
value from 2024-01-01 to 2026-02-01 (so every January is value times 744), seven master bills (Mall-Main
2024-01, 2025-01 and 2026-01 at 30,000.00; Tower-Main 2024-01 and 2025-01 at 35,712.00; Annex-Main
26,784.00; Substation-Master 44,640.00), and a table of what each case must produce, scripted so every
column adds to its master.

**Outside this stage:** Stage 3 must load the 22 points (a file gateway node as for the Cedar Row
submeters). Until it does, no tenant bill generates, the WUI run has nothing to allocate and the
reconciliation has nothing to calculate; method 1 and method 6 allocation does not need it.

**Reference only:** for methods 2, 3, 4, 5 and 7 the file keeps what a plain reading of each method would
allocate, marked not expected today.

**Check:** `master_bills`, `method_1_allocation`, `method_6_property_total`, `wui_allocated_use_2024_01`.

## Stage 7 is done when

- Northlake Town Center exists with its levels, address, contact, two groups and one user, five
  buildings, 22 Electricity meters with Valley Electric District accounts, 26 points and the area values
  the Building Areas method and the WUI families need.
- TC-FLAT-GS and TC-STEP-DEMAND exist with a commodity mapping on every charge.
- Method 1 allocates Mall-Main's two bills to the seven tenants to the cent (30,000.00 of shares plus
  600.00 of overhead each period), Property Total holds 30,600.00 for 2024-01 and 2025-01, and
  the five masters on methods 2, 3, 4, 5 and 7 have a bill and no allocated bill (a product gap).
- The Weighted Use Index and Measured Use families allocate the use of file 10 (Shop 3 26,318.37, Shop 4
  25,306.12, Common Area 134,375.51, Landlord/House 230,640 kWh for 2024-01), and each of `PtAllocFailReason`
  1 through 5 has been produced by its fixture at least once; the Percentage Based fixture produces
  neither a success nor a failure row.
- All 4 bill generation types behave as configured for 2026-01 (Shop 1 878.28, Shop 2 669.96, nothing
  for Off and Manual), and the 3 Task_Tbl tasks this stage depends on are present and, for 24 and 42,
  scheduled.
- The Bill Reconciliation report shows Anchor Store billed 2,040.00 against calculated 15,000.00 in
  2024-01 and 2025-01 (variance -12,960.00), and every other Tenant Rebilling report this instance's
  catalog carries renders without error.
- Ridgeline's account SYN-RWL-G-0000001 holds 18 generated statements, one a month from July 2024 to
  December 2025, each with the transfer-energy line and the research credit once. July 2024 reads
  $129,330.27 and its per-turbine sums match the hand-made statement
  (`ridgeline_acceptance_2024_07`, Diff 0), and February to April 2025 are lower with no adjustment
  line.
- Cedar Row's four configs are entered only once Stage 2 gives the apartment submeters billing accounts
  (`allocation_configs` shows them as FAIL until then, which is correct).

Run `checks.sql` beside this chapter against the instance database to see each of these as a result
set.

## Findings

Product gaps and open questions found while building this stage, in addition to what earlier stages
already logged in [product findings](../product-findings.pdf):

- **Two catalog gaps, not customer data.** This instance's `BillAllocationMethod` table carries only
  method 1 (of 7) and `PtAllocationMethod` carries only 2 (of 3, missing Percentage Based). Both are
  confirmed present with the expected names, descriptions and procs in the reference EEMSuite
  database, and both fit the precedent already established for other install-time catalogs: standing
  them up is finishing the install, not seeding this customer's data. Neither can be typed around
  from a screen.
- **Not fixed here:** the WUI fixture nodes are in no hierarchy file and `No Area` / `No Rate` need
  separate meters; the Thermal Plant masters of Step 3 and the node names it uses are not in Stage 2.
- **Three Tenant Rebilling reports are not registered on this instance.** `dbo.GuiReports_Tbl` has 11
  of the 14 rows the reference database carries for this feature; missing are `rp_accruals`,
  `rp_mpaaccruals` and `rp_OpenAccruals`, all three accrual reports. They will not appear on the
  Reporting menu, with data or without, until their catalog rows are installed — consistent with the
  gap below.
- **Bill Allocation methods 2, 3, 4, 5 and 7 have no calculator.** `BillAlloc_ProcessBillItems` goes on
  only when the master meter has a method 1 config for the period, and `BillAlloc_ProcessAllocatedItems`
  splits by the typed percent and amount whatever the method. The configs save and nothing is allocated
  (ADR-015 records the same). Only methods 1 and 6 produce values.
- **Overhead % is added to the allocation, not carved out of it**, so a config with Overhead % above 0
  bills the tenants 2% more than the master in all. The earlier sum-to-parent check could not reach zero.
- **The Add Billing Account dialog requires a provider**, so an allocation-only or tenant account cannot
  be provider-less, and a meter's provider is copied from its account. The Tenant Rebill rate list and
  the allocation candidate picker both depend on a measure type and an account the original tenant meters
  lacked.
- **The reconciliation scenario is reachable only through the Bill checkbox** (the picker excludes it),
  which copies the same rate. A reconciliation between two rates cannot be entered on the desktop.
- **Cedar Row's apartment submeters cannot be allocation candidates** (no billing account), and method 2
  would compute nothing if they could.
- **Tenant accruals (product-gap-backlog #4, "Accruals create/reverse feature") have no entry path.**
  No screen, API or scheduled task writes `dbo.BillAccrualMap`; `rp_OpenAccruals @Reverse` exists as
  a proc but nothing calls it from the UI. This blocks Phase 4's tenant accrual case entirely, not
  just this stage's demo of it.
- **Percentage Based (`PtAllocationMethod` 3) is unimplemented in the engine, confirmed again here.**
  Once its catalog row is installed it can be selected on the Master Point Configuration modal, but a
  child configured with it produces no allocated use and no `PtAllocFailReason` row — it is silently
  ignored. This matches the Phase 4 spec's documented expectation exactly.
- **Index values have a screen, though not the modal.** WUI Point Use History (`rp_WUIPointUseHistory`)
  opens `CustomWUIAdd`, which calls `WUIPtAllocationIndex_Save`. The earlier finding that no screen
  writes `PtAllocationIndex` was wrong; the screen is a custom view, outside the C# search.
- **Per-meter rate-class/option binding (product-gap-backlog #5, "Per-meter rate-class / option
  binding") still has no field on the Tenant Rebill tab's Rate Configuration grid.** Not exercised by
  this stage directly, but every tenant meter here is exactly the kind of assignment that gap
  affects; carried forward from the backlog being dissolved into this chapter set.
- **The Thermal Plant's cost-recovery mechanism (Step 3) is this chapter's own assumption, not a
  confirmed product fact**, because it depends on how Stage 2 shapes Northlake University's served
  buildings, and Stage 2 was still being written in parallel. Confirm the master/served-building
  structure once Stage 2 lands, and adjust Step 3 if it does not match.
- **Bill Generation cannot bill a sum across meters (finding 66, Ridgeline).** `UtilityRates_GetPoints`
  reads only the points under the one meter node, and `UtilityGenBill_Create` writes one bill per
  meter and month. The ten turbine meters would give ten bills a month, each repeating the monthly
  credit (July 2024's lines would add to $118,080.28, not $129,330.27; even the ten energy lines alone
  add to $130,580.28, a cent over the farm line). The workaround is the one EEM's demo database uses:
  a logical billing meter whose one point is an aggregate, which Stage 2 now carries (Ridgeline Farm
  Transfer Meter, with the farm aggregate under it). `ridgeline_generated_statements` confirms it: one
  bill a month on the account.
- **A determinant under an added rate class may price nothing on a generated bill (finding 69; read
  from the code, not yet seen on a run).** `UtilityRate_Exec` takes a rate class only if it is the
  All type, or its rate option is the default, or the meter is bound to it. Add Rate creates the
  class All with that type, but every class added after it is Unique and no screen binds a meter to
  one (findings 7 and 8), so a determinant under an added class prices only as its option's default.
  Rate tests pass regardless, because they name the classes. RWL-XFER-2024 keeps both determinants
  under All.
- **Offset cannot hold a statement back, and a generated bill carries no issue date (finding 70).** A
  period is listed once its end is before today plus Offset, so a positive Offset brings a month
  forward, and the desktop clamps Offset at 0. A generated bill is dated its period end, has no
  invoice number or due date, and is written by the task's login. The two-day entry lag and the
  keiko.tan entry user planned for Ridgeline therefore have no setting.
- **An unmapped determinant drops its line, and generated-bill bookkeeping is loose (findings 71 and
  72).** A determinant with no commodity mapping stays in the bill total and writes no line, so the
  lines stop adding to the total (`ridgeline_commodity_mapping` and `ridgeline_generated_statements`
  catch it). The bill total keeps four decimals while each line rounds to the cent (July 2024:
  129,330.2720 against lines adding to 129,330.27), so compare `ROUND(BL_Amount, 2)`; the day count is
  end minus start (30 for July); and the availability test counts every non-excluded point's rows
  against one point's expected intervals and counts a daylight-saving gap as missing data.

If a screen refuses any other value while entering this stage, add it here with the screen, the
field and what happened.
