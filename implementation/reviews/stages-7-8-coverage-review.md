# Stages 7 and 8 coverage review (Northlake recipe vs the product)

Date: 2026-11-10. Read-only. Recipe: `C:\Hippo\Git\hippo-synthetic-customer\implementation\stage-7-allocation-and-tenants` and `stage-8-sustainability`. Product: `C:\Hippo\Git\univerus\energyhippo`.
Marking: READ = I saw it in code or YAML. INFERRED = my reading of how it behaves; nothing was run.
Paths without a drive letter are under the recipe `implementation\` folder, or the product `src\` / `Database\EEMSuite\` folders (web scripts are under `src/Web/EEMSuite.Web/frontend/src/scripts/hippo/`).

## 0. The short version

Both stages look wide on paper and are shallower than they read. Five findings matter most.

1. **Town Center has no data at all.** No interval data (Stage 3), no bills (Stage 5), nothing in Stages 1, 3, 5 or 6. `data/eem/northlake-town-center-v1.yaml`, named as a source in files 01, 02 and 05, does not exist (`data/eem` holds four other files). Methods 2, 3, 5, 7, the WUI runs and every "sums to parent" check have nothing to compute from. No expected dollar value exists anywhere for a Town Center tenant.
2. **Tenant bill generation cannot be entered as written.** The tenant meters are allocation-only: no provider, no measure type, and (except Anchor Store and Food Court) no points. The Tenant Rebill rate list is the meter's provider's rates filtered by its measure type, so nothing can be picked (Stage 7 section 7.1). A Bill Generation row on a meter with no points is refused. The three missing rates are not the real problem: no rate can be assigned to these meters at all.
3. **The reconciliation fixture cannot be built as written.** The Tenant Rebill scenario picker leaves out Bill Meter Reconciliation. The only way into that scenario is the Bill checkbox, which copies the same rate. A "deliberately different rate" under scenario 20 is unreachable on the desktop. The report also ties to a real master bill only on schedule BL (Bill); the recipe uses CC.
4. **Stage 8 GHG will double-count and has no expected value for any campus meter.** With eGRID enabled, the warehouse job auto-maps every unexcluded California electric meter: the 124 Cedar Row apartment submeters, the three Helios PV meters, and the Ridgeline Farm Transfer Meter (about 2.25 million kWh a month on its generated statement). Only the ten turbines are excluded. No check reads `WH_GHG_Tbl` for any non-Ridgeline meter.
5. **ENERGY STAR is entered at property level only.** The 13 properties get a Primary Use and Auto Update = false. The scenario YAML holds year built, occupancy, gross floor area, secondary uses and use details for all 13; none are entered. The Admin Hall "29% over the 25% cap" story cannot evaluate, and no energy meter is mapped to any property.

Checks depth: Stage 7 has 31 check blocks: 4 assert a known value in SQL, 4 prove existence only, 23 list rows beside a PRINT that states the expectation. Stage 8 has 16: 0 assert in SQL, 2 existence, 14 list beside a PRINT.

---

# STAGE 7: Allocation and tenants

## 1. What the stage sets up

| File | Screen | Records | What it exercises |
|---|---|---|---|
| 01-town-center-company | DB Admin company Definitions, Levels, Address, Contact, Bill Scenarios; Users and Groups | 1 company, 2 groups, 1 user | New company, 4 levels, alarm colours, scenarios Actual + Budget + Bill Meter Reconciliation |
| 02-town-center-hierarchy | DB Admin nodes, Add Billing Account | 1 site, 5 buildings, 22 meters, 17 points, 22 billing accounts (4 Importer, 18 Allocation), Area on 15 nodes | Tree, allocation-only meters, owned submeters, area, account types |
| 03-thermal-plant-allocation | Web #/reporting/BillAllocationConfiguration | 2 configs (CHW method 2 on 2 meters; steam method 1 on 6 meters, 30/12/18/20/10/10) | Plant invoice allocated to campus buildings; Combine Overhead on |
| 04-bill-allocation-configs | same | 8 configs, 48 detail rows, one per method 1-7 (method 1 twice) | All 7 methods; fixed amount; Overhead %; Combine Overhead off/on; windows FY2024, FY2025, FY2026 P1-6, open-ended |
| 05-wui-point-families | Web Master Point Configuration modal | 4 masters, 12 child points (3 + 2 + 6 + 1) | WUI methods 1 and 2, method 3 (ignored), fail reasons 1-5 |
| 06-tenant-bill-generation | DB Admin Tenant Rebill tab; Web allocation config | 4 Town Center tenant meters (Off, Manual, Auto, Auto w/ Regen); 4 Cedar Row masters (rate + Bill checked); 4 Cedar Row method 2 configs, 248 rows (60 + 60 + 64 + 64) | Four generation types; Cedar Row apartment allocation |
| 07-allocation-runs-and-reconciliation | Web Process Meter Allocations, Task Manager | 5 (one run for 2024-01..03, 2 task schedules, Anchor Store reconciliation, accruals "not entered") | WUI run, tasks 24 and 42, reconciliation |
| 08-ridgeline-transfer-generation | DB Admin Tenant Rebill; Task Manager; Generated Bills | 4 (billing meter, generation row, July 2024 acceptance, WTG-07 outage) | One Auto generation row, 18 periods, statement $129,330.27 |

READ: the counts agree with `checks.sql` (22 meters, 22 accounts, 12 PtAllocationConfig rows) and with the chapter ("8 configs"). Area sums also agree: Market Hall 28000 + 12000 + 2200 + 1800 + 2600 + 2000 + 35400 = 84000; Office Tower 4 x 22000 + 8000 = 96000; Annex 16000 + 18000 + 20000 = 54000.

## 2. Coverage gaps

### 2.1 Bill Allocation Configuration (files 03, 04, 06)
Product: `reports/billAllocationConfiguration.ts`, `billAllocationMeterDrawer.ts`, `billAllocationPreview.ts`, `Database/EEMSuite/Procs/BillAllocationConfig_Save.sql`, `Tables/BillAllocationConfig.sql`, `BillAllocationConfigDetail.sql`.

- **Overhead Amount never entered (READ).** The grid has Allocation %, Allocation Amount, Fixed, Overhead %, Overhead Amount (`billAllocationConfiguration.ts` 53-57, 849-893). Overhead % is 2 on every row of every config. Allocation Amount appears once (Anchor Store 2000, Fixed). A non-fixed Allocation Amount is never used.
- **Percent rules barely exercised (READ).** Only method 1 has typed percentages; the Balance to 100% button, the negative-percent and wrong-total warnings and `minimumAllocationPercent` are never provoked.
- **Edit of a config that has allocated bills (READ, line 355).** Saving prompts that all bills made under the previous rule will be removed. Nothing in the recipe changes a config after it has run.
- **Delete a config (READ, `onClickDelete`, `BillAllocationConfig_Delete.sql`).** Never used.
- **Disable flag (READ).** `BillAllocationConfig.Disable` and the `@Disable` parameter of the save proc; the recipe never sets it.
- **Windows.** Mall-Main has three method windows with no overlap case and nothing after 2026-06 (INFERRED hole). No end period other than 12 and open-ended.
- **Test allocation / tenant map preview** (`BillAlloc_TestAllocation.sql`, `billAllocationPreview.ts`): no step uses them. INFERRED.
- **Bulk load.** `BillAllocationConfig_BulkLoad.sql` takes XML; I found no caller under `src`. Cedar Row's 248 hand-entered rows are the case it exists for. INFERRED.
- **Method 6 Commodity "n/a (cost center)".** Whether Commodity is required for method 6 I did not open (INFERRED).
- **Cedar Row C missing (READ).** Stage 2 now has Cedar Row C: 48 apartment water submeters plus house and laundry, open 2025-09-01 (`stage-2-hierarchy/03-meters.yaml` 3058-3460). File 06 allocates only A and B. Common House is not allocated either.
- **Sewer cap at winter average** is "a rate-engine rule" and modelled nowhere (file 06 note). INFERRED that no Stage 4 charge implements it.

### 2.2 Tenant Rebill tab (files 06, 07, 08)
Product: `src/Apps/EEMSuite.Apps.DatabaseAdministrator/Views/Controls/TenantRebillView.xaml`, `ViewModels/Controls/TenantRebillViewModel.cs`, `src/Data/Dapper/Billing/TenantRebilling/DapperUtilityBillConfigurationRepository.cs`, `Procs/UtilityGenerationConfig_Save.sql`, `UtilityGenBillDates_Set.sql`, `UtilityRateMeterAssignment_Save.sql`.

- **Schedule is always CC (READ).** The procs know BL (Bill), BC (Bill Cycle), CC (Company Calendar), and MV and RC (`UtilityGenerationConfig_Save.sql`). Only CC is entered anywhere. BL is the one reconciliation needs (7.2).
- **Available % always 100, Offset always 0 (READ).** Ridgeline briefly 99. Offset is clamped at 0 on the desktop (finding 70), so there is no value to enter.
- **Point Assignment Excluded checkbox never set (READ).** Described in notes only.
- **Bill checkbox.** True only on the four Cedar Row masters, false elsewhere. See 6.3.
- **Fiscal Start/End.** 2024-1 to 9999 on all but Ridgeline (2024-7 to 2025-12) and Anchor recon (2024-12).
- **End Date on a rate row** is accepted by the screen but not stored; every row is null.
- **Data source (Interval/Bill).** The desktop always sends 0, which the proc turns into 1 Interval (`DapperUtilityBillConfigurationRepository.cs` 193; `UtilityGenerationConfig_Save.sql` 52-56). The Web Bill Generation Configuration report shows and saves it (`rp_BillGenerationConfig.sql` 93, 161-162; `sr_BillGenerationConfig_Save.sql` 22). Data source 2 (Bill) is never used. File 07's note that it "is not a distinct field on the screen" is wrong for the Web report. READ.
- **Web reports with no step:** Bill Generation Configuration, Generated Bills (Create button), Tenant Map, Tenant Bill Audit, Tenant Bill Allocation Map, Rate Allocation, WUI Point Use History, Tenant Bill Definition (`reports/tenantMap.ts`, `tenantBillAudit.ts`, `tenantBillAllocationMap.ts`). Only their catalog rows are checked.

### 2.3 WUI point families (file 05)
Product: `reports/WUIProcessMeterAllocations.ts`, `views/viewMasterPointConfiguration.ts`, `Procs/WUIPtAllocConfig_Save.sql`, `WUIPtAllocConfig_Validate.sql`, `WUIPtAllocationIndex_Save.sql`, `src/Web/EEMSuite.Web/Views/Custom/CustomWUIAdd.cshtml`, `Procs/rp_WUIPointUseHistory.sql`.

- **File 05's PRODUCT FINDING "no UI path for index values" is wrong (READ).** `rp_WUIPointUseHistory.sql` (add/edit actions, line ~167; `Migrations/v7.0.0.sql` 163184) opens the custom view `CustomWUIAdd`, which calls `WUIPtAllocationIndex_Save` (PtID, UnitID, Fiscal period YYYYMM, IndexValue). Units come from `WUIAllocationUnits_Get` (unit classes EnergyUseIndex and VolumeUseIndex).
- **No index value, unit or period is recorded (READ).** File 05 says indices are "# assumed" but none appears. A Weighted Use Index child with no index fails NoUseIndex, so the expected successes (Landlord/House, market children, Chain Leaf, No Rate, No Area) have no input.
- **Index change over time, index delete** (`WUIPtAllocationIndex_Delete.sql`): never.
- **Dates.** Every child starts 2024-01-01 with no End Date. No end-dated child, no child moved between masters. The validator rejects "ChildExistsUnderAnotherMasterWithOverlappingPeriod" (`WUIPtAllocConfig_Validate.sql` 33); never provoked. READ.
- **Fixture contradiction (READ).** All six fixture children hang on one WUI Fixture Meter. "No Area" needs the node's Area empty; "No Rate" and "Chain Leaf" need "a valid index and area". One node has one Area value. They need separate meters.
- **Fixture nodes are not in file 02 (READ).** WUI Fixture Meter, its six points, the master point, Chain Mid, Chain Leaf, and the four "Estimated kWh" points (Anchor Store, Food Court, Common Area, Landlord/House) are in no hierarchy file; file 02's check (">= 14" points) does not count them.
- **Fail reason 1 (InsufficientIntervalData)** depends on a Stage 3 gap that does not exist (no Town Center in Stage 3).
- **Method 3 and the catalogs.** The recipe flags `PtAllocationMethod` (2 rows) and `BillAllocationMethod` (1 row) on the installed DB. I found no seed for either in `Database/EEMSuite/Scripts` or `Migrations` (grep); consistent with the recipe.
- **Runs.** Only 2024-01..03. No re-run of a processed period after an index or area change. INFERRED.

### 2.4 Node screens used for Town Center (file 02)
Product: `Views/Nodes/Definitions/MeterDefinitionView.xaml`, `PointDefinitionView.xaml`, `Views/Controls/AreaView.xaml`.

- **Meter Definition fields never set:** Meter Multiplier, Provider Meter Number (READ). Bill Cycle is 1 on the four masters only.
- **Point Definition features never set:** baselines, point associations, delta multiplier, gateway binding, index type on accumulators (READ in `PointDefinitionView.xaml`). The method 5 kW point is a plain Analog.
- **Area has no history in the recipe.** A tenant resized over time is never entered (INFERRED that Area keeps history: the check reads `ValueHistory`). Units are SqFt only.
- **Allocation-only meters have no Measure Type and no Provider.** Blocks rates (7.1).
- **Wrong calendar note.** File 01 says saving "creates a 1990-2013 fiscal calendar". Stage 1 (`03-company-calendars.yaml`) says Company_Save generates periods through next year. Town Center is not in Stage 1's calendar file, so its 2024-2026 periods are never confirmed.
- **Valley Electric vendor numbers for Town Center** (VED-3005-TC to 3008-TC) are a Stage 1 editor step that no file records (file 01 says so).
- **Groups and users:** 2 groups, 1 user, "# assumed". No user tests Bill Entry or Bill Validation access.

### 2.5 Product features in this area with no recipe data
- **Tenant accruals** (rp_accruals, rp_mpaaccruals, rp_OpenAccruals not registered; `BillAccrualMap` has no writer). Recorded as a gap; fine.
- **A tenant-facing statement/invoice.** Nothing (Billing Charges report appears only for Ridgeline). INFERRED.
- **Budget scenario.** Added to the company and used on one rate row (Anchor Store). No Bill Generation row under Budget.
- **Allocation of Cedar Row Common House, carport, and the Helios PV credit.** Nothing. INFERRED.
- **Method 1 on non-electric masters** appears only in file 03.

## 3. Fields present but always empty, null or default

| Where | Field | Value |
|---|---|---|
| All `installed:` blocks | ids, recordedOn | null (expected until entered) |
| 03, 04, 06 | Overhead Amount; non-fixed Allocation Amount | never set |
| 04 methods 2-7 | Allocation % | 0 by design |
| 05 | End Date | blank on all 12 children |
| 05 | index value, unit, period | absent |
| 06 | Bill (EnableBillReconcilliation) | false on the 5 Town Center rows, true on the 4 Cedar Row masters |
| 06, 08 | Offset | 0 everywhere |
| 06, 07 | Available % | 100 (Ridgeline briefly 99) |
| 06, 07, 08 | Schedule | CC everywhere |
| 06 | Fiscal End | 9999 on 5 of 6 rows |
| 02 | Meter Multiplier, Provider Meter Number, Bill Cycle on non-masters | never set |
| 02 | Area on Substation Feed and Property Total | none |
| 01 | Alarm Settings | identical to the other companies |

## 4. Depth of checks.sql (31 blocks)

- **Asserts a known value in the query (4):** `tenant_bills_sum_to_parent` (Diff, expected 0); `ridgeline_generated_statements` (Diff to the line sum, and a second query that must be empty); `ridgeline_acceptance_2024_07` 1 of 2 (per-turbine literals and Diff); 2 of 2 (129,330.27). None is PASS/FAIL; the reader scans a Diff column.
- **Only proves existence or catalog (4):** Task_Tbl 24/42/47; `BillAllocationMap` count; `rp_BillReconciliation` exists; the 14 `GuiReports_Tbl` rows.
- **Lists rows beside a PRINT that states the expectation (23):** company row, levels, groups/users, nodes by level, accounts by type, floor areas (no values stated), configs by method, detail row counts, `BillAllocationMethod`, `PtAllocationMethod`, `PtAllocationConfig` by method, fail reasons, method-3 ignored, generation types, Anchor recon row, `PtAllocationProcessLog`, Property Total list, Anchor rates under Actual vs 20, billing meter, commodity mapping, generation config, generation log, outage months.
- **The Property Total check does not check (READ).** Its PRINT says it "equals the sum of every consumed child bill"; the query lists aggregate rows and amounts and never sums or compares.

What Stage 7 enters that no check covers:
- Any Cedar Row allocation config. The filter is `CompanyName IN ('Northlake Town Center', 'Northlake University')`; the chapter says it covers "Cedar Row's 4 configs". READ.
- Cedar Row Bill=true rows; Cedar Row recon scenario.
- Rate rows (Actual, Budget) on Anchor Store, Food Court, Shop 1, Shop 2 (only Anchor's pair is read).
- That Off and Manual generated nothing and Auto and Auto w/ Regen did.
- `generation_configs` PRINT expects Cedar Row rows; Cedar Row has no Bill Generation row (file 06 gives its masters Rate Configuration only). Town Center would show 5 rows (Off, Manual, Auto, Auto Regen, Manual recon), Cedar Row 0, Ridgeline 1. READ.
- Task schedules (daily 1:00 AM, every 5 minutes): only the catalog row.
- Overhead %, fixed flag and percent values on the 48 detail rows (beyond totals).
- Company scenarios Budget and Reconciliation.
- WUI fixture children by name/method; index values (none exist).
- Thermal allocation output. Stage 5 has known bills for the same six buildings (Science Center Jul-24 $35,873.48 = 180,860 ton-hours x 0.168 + 542 tons x 9.50 + 340.00; arithmetic checked). Nothing ties file 03 to them.

## 5. Known expected values for reports or outputs

- **Has known values:** Ridgeline July 2024. I rechecked: the ten turbines sum to 2,251,384; x 0.058 = 130,580.272; less 1,250.00 = 129,330.27; WTG-07 222,196 x 0.058 = 12,887.37. Outage months have a qualitative expectation only.
- **No known value:** every Town Center allocation method (no master bill; not even Anchor's fixed $2,000 + 2% overhead has a stated result), the four generation types, Cedar Row apartment shares (248 rows), the reconciliation variance ("nonzero"), WUI allocated use, the thermal allocation, Tenant Map, Tenant Bill Audit and Allocation Map.
- **Easy to give one:** Mall-Main FY2024 with a stated master bill M: Anchor 2,000 fixed + 2% overhead, Food Court 15%, shops 8% each, Common 53%; the sum to parent must be M.

## 6. Internal inconsistencies (READ unless marked)

6.1 `NL-STEP-Demand` and `NL-RES-Tiered` are in `stage-4-rates/08-rate-lab.yaml` (not enterable). `NL-MULTI-Commodity` exists nowhere.
6.2 File 06 assigns `NL-RES-Tiered` and `NL-MULTI-Commodity` to Cedar Row masters; Stage 4 `06-rate-assignments.yaml` assigns `VED-TOU-GS` (`ved_cedar_row_a_master`, line 128) and `RCU-W-TIER` + `RCU-S-VOL` (`rcu_cedar_row_a_water`, line 524) to the same meters from the same date. A meter prices on one rate at a time (Stage 4 finding 65). File 06's own note says the real rate is "already assigned by whichever stage enters Cedar Row's rates", then assigns a feature rate. (Same-node identity of `ved_cedar_row_a_master` and "Cedar Row A Electric Master": INFERRED yes.)
6.3 File 06 turns Bill on for Cedar Row masters, but Cedar Row's Used scenarios are Actual only (`stage-1-foundation/01-companies.yaml` 69-114). File 08 documents that the save fails without the Reconciliation scenario (`UtilityMeterRates.BillScenarioID` NOT NULL). Stage 4 sets Bill = true on real rows for companies that also have only Actual, the same defect from the other side.
6.4 File 06 says Cedar Row reconciliation is "file 07"; file 07 reconciles only Anchor Store.
6.5 File 05: "no UI path" for index values is wrong (2.3).
6.6 File 05 fixtures: No Area vs No Rate on one meter (2.3).
6.7 File 02 note "(file 03, method 6)" should be file 04. File 01 says Budget exists "so Step 4's multi-component rate can be assigned"; Step 4 has no rate.
6.8 File 03 uses Stage 2 keys "Science Center Chilled Water BTU Meter" and "... Steam Cost Center"; Stage 2 `03-meters.yaml` has "Science Center Chilled Water" and "Science Center Steam" (grep for the file 03 names finds nothing). The masters "Central Plant CHW Allocation" and "Central Plant Steam Allocation" are in no hierarchy, account or bill file. File 03 admits NLU would have 8 NTP accounts, not Stage 2's 6.
6.9 Stage 5 (`03-bills.yaml` line 198) enters the six NTP building bills by hand, monthly for 24 months, with exact values. File 03 generates the same cost by Bill Allocation. Stage 4 also assigns `NTP-ALLOC-CHW`/`-STEAM` to the six building meters (third route). File 03's steam split is fixed 30/12/18/20/10/10 and cannot reproduce Stage 5's per-building steam.
6.10 File 03 quotes rates "0.168, 9.50, 14.20". Stage 4 now also has a Fixed O&M Share per meter (340.00, 350.20 from 2026) and a 3% 2026 step. File 03 leaves both out; its windows run 2024 to open-ended across the step.
6.11 Roster vs file 04: the roster splits In-line Shops "by square footage" and Common Area as "the remaining balance". File 04 gives each shop 8% for FY2024 and FY2025 (areas 2200, 1800, 2600, 2000 are not equal) and types Common Area as 53.
6.12 Allocation-only meters have no points, yet file 06 puts Auto and Auto w/ Regen on In-line Shop 1 and 2 and file 07 puts reconciliation on Anchor Store. `UtilityGenerationConfig_Save.sql` 117-122 refuses an Interval-source row on a meter with no child points. File 05 adds Estimated kWh points to Anchor Store, Food Court, Common Area only; shops have none.
6.13 File 01 calendar note vs Stage 1 (2.4).
6.14 The chapter says `allocation_configs_by_method` covers Cedar Row's four configs; the SQL excludes Cedar Row.
6.15 Source files named but absent: `data/eem/northlake-town-center-v1.yaml`, `data/eem/northlake-rates-v1.yaml`.

## 7. Effects of today's Stage 4 rates rework, and what tenant billing needs

### 7.1 What tenant billing actually needs

Three mechanisms are mixed in Stage 7 and need different things.

| Mechanism | Rate on the tenant meter? | What it needs instead |
|---|---|---|
| Bill Allocation (files 03, 04, 06): split a real master bill in dollars | **No.** Method 1 splits dollars by percent/fixed amount; 2-7 split by interval, area or usage share. No rate is read. | A master bill (Stage 5 has none for Town Center); for 2, 3, 5, 7 interval data on the candidates |
| Tenant Bill Generation (file 06 Town Center rows, file 08): price interval data with a rate | **Yes.** | A meter with child points and data, a provider and measure type so the rate list offers something, a Bill Generation row |
| Reconciliation (file 07): compare a billed amount with a calculated one | Yes, on the Reconciliation scenario | A real bill on the meter for the period, schedule BL, a rate under scenario 20 |

The rate list is read, not guessed: `TenantRebillViewModel.cs` 510 offers rates where `MeasureTypeId == _meterMeasureTypeId`, taken from `GetUtilityRatesAsync(providerID)` (line 252); an empty list shows `ShowNoProviderRatesMessage` (512). The tenant meters in file 02 have a billing account only. READ. So no tenant rate can be assigned as the meters stand.

What it takes to make tenant generation real:
- Give the generating tenant meters Provider Valley Electric District, Measure Type Electricity and at least one point with data (Anchor Store and Food Court get points from file 05; shops and others need them).
- A tenant rate. Stage 4 assigns no rate to any Town Center meter today (no Town Center entry in `06-rate-assignments.yaml`). The simplest real answer is the same Valley Electric tariff the master is billed on (`VED-TOU-GS`), re-used. `NL-STEP-Demand` (Charge Types 210 and 600, Maximum Bill 25,000; `08-rate-lab.yaml` 486) exercises stepped demand and a bill cap, nothing tenant-specific; it can stay in the Rate Lab and be assigned to one Town Center tenant meter once the lab can be entered.
- **`NL-RES-Tiered` on Cedar Row masters is not needed.** Apartments are billed by allocating the master's real bill; the master keeps its real tariff. Drop both assignments.
- **`NL-MULTI-Commodity` is not needed.** Water, sewer and stormwater are Stage 4's real River City rates on the real meter. Drop both assignments.
- Cedar Row needs the Reconciliation scenario if Bill stays on; but Cedar Row's apartment-total-vs-master reconciliation is the Bill Allocation sum-to-parent check, which needs no scenario.

### 7.2 What the reconciliation report reads (changes the Anchor Store fixture)
- `rp_BillReconciliation.sql`: rows come from `UtilityBillGenLog` joined to rates of a scenario with ScenarioTypeId 20, with `MasterBillID` (the actual bill) compared to a calculated scenario bill. `UtilityGenBillDates_Set.sql` fills `MasterBillID` only for schedule **BL** (lines 51-69); CC and BC rows insert NULL (lines 79, 108). The recipe's Anchor Store row is CC. READ. INFERRED result: no actual bill to compare to.
- The Tenant Rebill scenario picker calls `UtilityBillScenario_Get @BillScenarioType = 6`, "All except Bill Recon" (`UtilityBillScenario_Get.sql` 103-108). Bill Meter Reconciliation cannot be selected. `UtilityRateMeterAssignment_Save.sql` (36-48) mirrors the row to the Reconciliation scenario with the same rate when Bill is checked. READ. A mismatched rate under scenario 20 is not enterable.
- Anchor Store's Actual generation is Off (file 06), so its Actual bill is an allocated bill (the $2,000 fixed). File 07's story ("the Actual bill's recovered amount for the same period" against a stepped demand rate) is not what the report would compare. INFERRED.

### 7.3 Per-place effects of the rework

| Place | What it names | Effect |
|---|---|---|
| 06 `tc_anchor_store_billgen` | `NL-STEP-Demand`, Actual and Budget; Assigned Rates | Rate now only in `08-rate-lab.yaml` (not enterable; its own test says "no meter exists yet"); meter has no provider so no rate is offered anyway |
| 06 Food Court, Shop 1, Shop 2 | `NL-STEP-Demand`, Manual / Auto / Auto w/ Regen | Same |
| 06 Cedar Row A and B electric masters | `NL-RES-Tiered` | Moved to Rate Lab; collides with `VED-TOU-GS` |
| 06 Cedar Row A and B water masters | `NL-MULTI-Commodity` | Never existed; collides with `RCU-W-TIER` + `RCU-S-VOL` |
| 07 `anchor_store_reconciliation` | `NL-STEP-Demand` in Rate Configuration and Bill Generation; fixture about "block boundaries shifted down one tier" | Rate gone from Stage 4; fixture unreachable (7.2) |
| 06 notes | "data/eem/northlake-rates-v1.yaml ... fires type 210 + 600" | Source file gone |
| 03 `ntp_alloc_chw`, `ntp_alloc_steam` | Per-unit rates from `NTP-ALLOC-*` | Rates remain, but Stage 4 added a per-meter Fixed O&M Share and a 3% 2026 step that file 03 omits (6.10) |
| 03 | Stage 4 now assigns `NTP-ALLOC-*` to the six `ntp_*` building meters | A third route to the same cost (6.9) |
| 04 | no rate | Not affected |
| 05 | "Fixture No Rate: no Bill Generation rate" | Not affected, but no Town Center rate exists to omit |
| 08 | `RWL-XFER-2024`, class All, commodity mapping | Not affected; Stage 4 keeps the 2024-07-01 assignment on the billing meter, Bill unchecked |
| Schedule renames (Summer Peak, Gas Winter ...) | | Stage 7 uses no Stage 4 schedule; "CC"/"BC" are bill-generation codes. Not affected |
| Anything that depends on bill generation | All of 06 and 07 | Nothing can generate until a Town Center rate exists on a provider-backed meter |
| Rate-derived dollar amounts | Ridgeline $129,330.27; thermal rates | Ridgeline unchanged |

## 8. Stage 12 scenarios worth adding (tenant and allocation)

1. **Tenant leaves, new tenant arrives mid-year** (replace In-line Shop 3). Breaks: editing a config with allocated bills removes them (READ, `billAllocationConfiguration.ts` 355); sum to parent for earlier periods; Property Total.
2. **Percent re-split** (Food Court 15% to 18%) as a new window versus an edit of the live config. Breaks: the edit wipes history; the new window may leave an overlap or gap.
3. **Master bill corrected after allocation.** Breaks: `BillAlloc_ProcessBills` has `@ForceAllocation` defaulting to N, so a corrected bill is probably not reprocessed (INFERRED); sums to parent drift.
4. **Floor submeter replaced or its data gaps** (Library swap pattern on Floor 2). Breaks: methods 2 and 3 take shares from interval consumption; a gap skews them; the Landlord/House remainder can go negative.
5. **Tenant area changes** (lease resized, with an effective date). Breaks: Building Areas (method 4) and WUI NoFloorArea read the Area tab; already-allocated periods.
6. **WUI index changed or deleted for a period.** Breaks: periods without an index fail reason 2; a processed period is not re-run.
7. **Delete the last method 1 config.** `BillAlloc_ProcessBills` returns at once if no method 1 config exists (READ), so methods 2-7 stop too. Silent.
8. **Rate edit on a tenant under Auto w/ Regen** (Stage 4 scenario 7). Breaks: regenerated bills against exported ones; an allocated and a generated bill on one Allocation-type account and period (INFERRED).
9. **New building joins a master mid-year** (Cedar Row C style: 48 submeters, no master or config in Stage 7 today). Breaks: config row only valid from a later period; shares before it.
10. **Company calendar extended or a fiscal year closed.** Breaks: Fiscal End 9999 vs the log; closed periods rejecting allocated bill writes (INFERRED).

---

# STAGE 8: Sustainability

## 1. What the stage sets up

| File | Screen | Records | What it exercises |
|---|---|---|---|
| 01-emission-factors | Web EmissionFactorSources, EmissionFactors | 4 (CAMX 3 gases x 2 dates; gas x 2 dates; water extension x 2 dates; Ridgeline avoided emissions "computed outside") | Dated factor rows on two system members |
| 02-meter-emission-assignments | Web MeterEmissionFactorAssignment | 34 assignments (16 electric, 10 gas, 8 water) + 10 Exclude | Assign by source/member/category; Exclude |
| 03-ghg-company-configuration | Web GHGCompanyConfiguration | 3 companies (NLU 6, Cedar Row 3, Thermal Plant 5), baseline 2024-2025 | Source enablement, baseline years, default category |
| 04-energy-star | Web ESPropertySetup, ESNewRatingRequest; Config Tool; Task Manager | 13 properties, 20 rating requests (8 + 8 + 2 + 1 + 1), CustomerServer left blank, 1 "not a property" note | Property mapping, request queueing |
| 05-weather-regression | Web custom views WeatherNormalization_* | 4 regressions + 1 "goal not built" | Degree-day fit |
| 06-benchmarks | none | 3 built-ins read, 1 finding, 1 exclusion | Reading the 9 system benchmarks |

READ: Step 2 counts add up to the checks (electric 15 + interconnection = 16, gas 10, water 8 = 34). Step 3's per-company counts agree (NLU 10/6/6, Cedar Row 4/3/2, plant 2/1/0).

## 2. Coverage gaps

### 2.1 Emission factors (file 01)
Product: `views/viewEmissionFactorSources.ts`, `viewEmissionFactors.ts`, `viewEmissionTypes.ts`, `Database/EEMSuite/Scripts/UpdateEmissionTypeGwpAR6.sql`.

- **Only history rows on two existing members (READ).** The screens have "Add emission factor source", "Add emission factor member", "Add emission type", "Add emission factor". None is used. A customer's own supplier-specific factor is the common real case.
- **Emission Types (GWP Factor) screen never touched (READ).** The recipe's CO2e figures rest on GWP 28 and 265. `UpdateEmissionTypeGwpAR6.sql` is a manual opt-in AR6 switch (CH4 29.8) that also changes historical CO2e. Not exercised or mentioned.
- **Source Meter Link Type and member link rules (State/Region, Provider, Country) never varied (READ).** Only eGRID by state/region is in play; `CreateDefaultEmissionMeterMap.sql` handles all three.
- **Source preference order** (`EmissionCompanyConfigDetails.SeqNo`) never exercised: one enabled source per measure type, so the preference loop has one pass (READ).
- **Fuel Oil #2 (INFERRED supported).** Stage 2 has three Fuel Oil #2 emergency generator meters (`03-meters.yaml` 3466-3488). Stage 8 assigns none and mentions none.
- **Water factor** is "# assumed" and not click-tested: commodity add, offered units unknown. It is filed under a member whose units (Tonne/MBtu) cannot hold kg/kgal.
- **Factor history only moves forward.** No end-dated row, no back-dated correction, no row before 2023.

### 2.2 Meter emission assignment (file 02)
Product: `views/viewMeterEmissionFactorAssignment.ts`, `Procs/CreateDefaultEmissionMeterMap.sql`, `EmissionMeterMap_Save.sql`.

- **Unassign and re-assign never used (READ).** The grid has Assign, Unassign, Exclude; the status switch has Assigned / Excluded / Unassigned. Only Assign and Exclude are recorded.
- **Effective date is cosmetic (READ).** Every assignment is stored from 1970-01-01. A mid-year factor change for a meter has no screen path.
- **Auto-assignment is the real behaviour and is half handled (READ).** `CreateDefaultEmissionMeterMap.sql` maps every non-excluded meter in the company whose measure type and region/provider match an enabled source. The recipe excludes only the ten turbines. Unassigned meters that would be picked up:
  - **124 Cedar Row apartment electric submeters** and the house submeters (Electricity, California). Stage 7 allocation writes bills to them; whether those carry kWh quantities I did not open (INFERRED yes), in which case Cedar Row Scope 2 counts master plus apartments. Step 2 says "Open: Exclude them in the same pass" and never does.
  - **The three Helios PV meters:** their PPA bills carry generated kWh (recipe's own note).
  - **The Ridgeline Farm Transfer Meter (SYN-RWL-M-0110000):** Electricity, California, Thermal Plant company. Stage 7 step 8 bills about 2.25 million kWh a month on it. Not in the exclusion list (step 2 predates the logical billing meter). `ridgeline_turbines_excluded` filters `'Ridgeline WTG-%'` so it would not show; `ridgeline_generation_not_in_ghg_history` filters `'Ridgeline%'` and would.
  - **Town Center's electric meters:** no GHG configuration for the company at all. If one is added, master plus tenant allocated bills double count.
  - Fuel Oil generators, steam, chilled water, and irrigation/fire/common-house water: skipped only if no enabled source matches (INFERRED for fuel oil).
- **Cedar Row water: A and B assigned, Common House not (READ),** while Common House gas is assigned.
- **Dangling cross-reference (READ).** Step 2 says "step 1's note explains the category catalog has no literal Scope 1/2/3". Step 1 has no such note.
- **Categories: only Stationary and Indirect used (READ).** I did not list the `EmissionCategory` rows (INFERRED more exist).

### 2.3 GHG company configuration (file 03)
Product: `views/viewGHGCompanyConfiguration.ts`, `Tables/EmissionCompanyConfig.sql`, `EmissionCompanyConfigDetails.sql`.

- **Baseline 2024-2025 on all three (READ).** No single-year baseline, no baseline that ends before the data, no case for Variance with no result in the base year.
- **Disable or re-enable a source** with assignments in place: never.
- **No Town Center configuration (READ).**
- **GHG reports** (`rp_GHGHistory.sql`, `rp_GHGVariance.sql`, `rp_GHGAudit.sql`, Bill and GHG Variance): never named as something to open and read, apart from Ridgeline's `WH_GHG_Tbl` queries. INFERRED.

### 2.4 ENERGY STAR (file 04)
Product: `views/viewESPropertySetup.ts`, `viewESPropertyEditor.ts`, `viewESPropertyUseDetailEditor.ts`, `viewESNewRatingRequest.ts`, `reports/esRatingRequestLog.ts`, `Procs/ESFacility_Save.sql`, `ESFacilityMeter_Save.sql`, `ESFacilityMeterClass_Save.sql`, `ESFacilitySpaceType_Save.sql`, `ESFacAttributeHistory_Save.sql`, `ESRequestAuto_Save.sql`.

- **Only Primary Use is entered (READ).** The editor has tabs for Property Uses (use type, description, primary, gross floor area with effective date, per-use attributes), Energy Data Sources (meters: commodity, energy from, meter type, class attributes, associated use, portfolio status, lifecycle, inactive date, include), Rating History (score, label, weather-normalised EUI and energy, source EUI, direct GHG, alerts) and property facts (address, year built, occupancy).
- **The data exists in `data/scenarios/demo-university-v1.yaml` from line 386 and is not carried (READ):** year built, occupancy, gross floor area, institutional flag, per-use details (weekly operating hours, enrollment, FTE workers, computers, grants, % cooled/heated, workers on main shift) for all 13 properties, including Admin Hall's two uses (Office 60,000 + Other - Education 25,000).
- **No energy meter is mapped to any property (READ).** The Central Plant error request is "an incomplete meter map on purpose", but the other 12 properties have no meter map either, so every request fails alike. No meter class type (Renewables), associated use, lifecycle or inactive date.
- **Auto Update false everywhere (READ).** `ESRequestAuto` and Task 20 never switched on.
- **Row actions** Request Rating, View, History, Clear: noted, not entered. Request Type Building only (ESRequestType 3).
- **Admin Hall eligibility** cannot evaluate without the uses.
- **Cedar Row C** opened 2025-09-01 (Stage 2); file says 13 properties and "3 buildings".
- **Scores are external** (recipe says so). Local output is the request log (pending/error rows) and no known row values exist.

### 2.5 Weather regression (file 05)
Product: `src/Web/EEMSuite.Web/Views/Custom/WeatherNormalization_SetPeriod.cshtml`, `_Run.cshtml`, `_MeterDetails.cshtml`, `Procs/FF_wncore.sql`, `FF_WeatherNormalization.sql`, `rp_WeatherRegression.sql`, `Scripts/DropLegacyProcs.sql`.

- **The steps do not match the screens (READ).** `_SetPeriod` has two inputs: Fiscal Year and Fiscal Period (the baseline end). `_Run` calls `FF_wnCore` with MetaWorldID, BaselineEndFiscalYear, BaselineEndFiscalPeriodNo. There is no "pick the point" and no "Weather Inputs: CDD only" choice; the engine fits HDD and CDD balance points itself.
- **It regresses a meter's bills, not interval points (READ).** `FF_wncore.sql` reads billed quantities in unit classes 3 and 7 over a 12-period baseline. So the Student Center 15-minute kW point and the hourly chilled-water ton-hours point are not inputs; a demand regression cannot be produced. What classes 3 and 7 are: INFERRED.
- **Baseline end period never chosen.** Not given in any record.
- **A bill scenario named "Weather Normalized" is required (READ, `FF_WeatherNormalization.sql`).** Companies are set up with Actual only. Without it the sync writes no normalised bills, so the claimed "weather-normalized column on ScatterPlot/UsageVariance" is not produced. SysConstants `WeatherNormalizationTolerance` and `wnAllBills` also drive it; neither is set.
- **The Ridgeline note relies on `FF_PopulateRegressions`,** which `DropLegacyProcs.sql` (403-415) drops (READ).
- **Station binding** is Stage 2/3; no meter is bound to a second station.
- **Fit expectations are ranges only** (R2 >= 0.8, 0.85, ~0.6) with no seeded relationship; no check asserts them.
- **Task 48** is verified as a row; no step schedules it.

### 2.6 Benchmarks (file 06)
Product: `Procs/rp_BenchMark.sql`, `rp_BenchmarkScene.sql`, `reports/benchmarkRanking*.ts`.

- **Nothing is entered; it is a reading list (READ).** Three of nine built-ins named; Demand per Area, CO2 per day, Load Factor, Average price, Spend per Day, Use per day have no peer set or expected ranking.
- **Expected values are qualitative** ("Science Center highest; Library/Admin Hall lowest").
- **Peer set stale:** "3 Cedar Row buildings" (Stage 2 has C). Town Center not considered.
- **CO2 per area depends on GHG data nobody checked** (see 2.2).

## 3. Fields present but always empty, null or default

| Where | Field | Value |
|---|---|---|
| All `installed:` blocks | ids | empty until entered |
| 02 | Effective Date | stored as 1970-01-01 whatever is typed |
| 02 | Emission Source Category | Indirect or Stationary only |
| 03 | Starting/Ending Year | 2024/2025 on all three |
| 04 | Auto Update | false on all 13 |
| 04 | Request Type | Building on all 20 |
| 04 | PMPropertyID, CustomerServer | 0 / blank (by design) |
| 05 | Weather Inputs | not a real field (2.5) |
| 06 | peerSet | one string for all |

## 4. Depth of checks.sql (16 blocks)

- **Asserts a known value in SQL: 0.** Expectations sit in PRINT text only (about 1,815 lb CO2 for Aug-24, 4,428 kWh, 1,512,400 kWh on the Central Plant Sep-24 bill, 420,108 kg).
- **Existence or catalog only (2):** `emission_sources_and_members`; `benchmark_definitions_builtin`.
- **Lists rows beside a PRINT stating the expectation (14):** factor history, company config, meter assignments (34), ES properties (13), ES requests, ES scores (0 rows), weather results (4), turbines excluded, interconnection assignment (3 rows), no Ridgeline GHG rows, interconnection energy quantity, BCT credit is money, avoided emissions basis, Ridgeline not benchmarked (0 rows).

What Stage 8 enters that no check covers:
- Factor values: 410 / 395 / 0.0531 / 0.0537 / 0.597 (the check lists rows for ids 175, 201, 227, 12 only; the water row is outside it).
- Any non-Ridgeline GHG History row; no GHG History, Variance or Audit render.
- The 10 gas and 8 water assignments by category (no group or count by category).
- Exclusion of Helios, submeters, the Farm Transfer Meter (nothing excludes them; nothing checks).
- Rating request status (pending, error).
- Weather: R2/CVRMSE listed, no threshold.
- Tasks 19, 20, 48, and the `CustomerServer` constant.

A defect in a check (READ): `meter_emission_assignments` has no company filter, so it lists every assignment in the database, not the 34 its PRINT expects.

## 5. Known expected values for reports or outputs

- **Known:** Ridgeline station service and avoided emissions. I rechecked: 4.428 MWh x 411.44 lb/MWh = 1,822 lb CO2e; 46.92 MWh x 396.386 = 18,598 lb; 2,251,384 x 0.1866 = 420,108 kg; CAMX CO2e 0.1866 and 0.1798 kg/kWh at GWP 28 and 265; 412,800 + 368,400 + 731,200 = 1,512,400 kWh; 3.2 x 0.1866 = 0.597.
- **Unknown:** every campus electric, gas and water GHG History value. Factors are known but no bill-driven total is stated for any meter, although Stage 5 has quantities for many bills. An expected value could be quantity x factor.
- **Unknown:** GHG Variance, ENERGY STAR scores (external), regression coefficients (ranges), benchmark rankings.

## 6. Internal inconsistencies

6.1 Step 2 cites a category-catalog explanation in step 1 that is not there.
6.2 The Farm Transfer Meter is not excluded (2.2), and step 3's count of "2 electric meters" for the plant omits it.
6.3 Step 5 describes picking a point and weather inputs; the screens take a baseline end and a meter. Its Ridgeline note relies on a dropped proc.
6.4 Step 3 and step 4 and step 6 say 13 properties, "3 Cedar Row buildings"; Stage 2 has Cedar Row C.
6.5 Water: the factor is under a member whose units cannot hold it, yet step 3 enables "Natural Gas, Potable Water" as if both were entered.
6.6 PRINT says about 1,815 lb CO2; step 2 says about 1,822 lb CO2e. Both right (CO2 alone vs CO2e); the check lists CO2, CH4, N2O as three rows. Minor.
6.7 `meter_emission_assignments` has no company filter (section 4).

## 7. Effects of today's Stage 4 rates rework on Stage 8

- **No rate, schedule or rate-derived amount is named in Stage 8's YAML.** Nothing breaks directly.
- **GHG reads billed quantities, not dollars.** Rate changes do not move Scope 2 unless a commodity mapping adds or drops a quantity line. Stage 4 has commodity mapping on Ridgeline only; a determinant with no mapping adds to the bill total and writes no line (Stage 7 file 08 note). When mappings are added to the 16 real tariffs, an unmapped energy determinant would vanish from GHG, ENERGY STAR and the weather regression. INFERRED risk.
- **Three-period Valley Electric bills** now carry three kWh lines a month; the sums by unit class add them. The new public-purpose 1.5% and users-tax 5% lines must carry no kWh quantity or usage inflates (the weather regression sums classes 3 and 7 over all items). INFERRED; worth confirming in Stage 4.
- **2026 3% step** moves dollars only (benchmark Spend per Area for 2026), not GHG.
- **Gas** is now the real `SGU-GN-1` on the nine gas meters; therm quantities are unchanged, so the Admin Hall gas regression is unaffected.
- **Water**: Stage 4 notes the engine prices one rate per meter, so a generated water bill might carry the water line only; imported bills are unaffected.

## 8. Stage 12 scenarios worth adding (sustainability)

1. **Annual emission-factor update** (a 2026 row on CAMX and gas). Breaks: months already computed; overlapping Effective From; save refuses zero.
2. **Run the AR6 GWP script** (`UpdateEmissionTypeGwpAR6.sql`). Breaks: every historical CO2e figure, the recipe's 0.1866 / 0.1798 and Ridgeline's avoided-emissions basis.
3. **Add a meter to a company with a source enabled** (EV charger, tenant space). Breaks: the hourly warehouse job auto-maps it at the default category; a generation or tenant meter is counted unless Excluded first.
4. **Meter swap on an assigned meter** (Library pattern). Breaks: both meters mapped; new meter unmapped between swap and job; GHG gap or duplicate in the swap month.
5. **A building changes use or area** (Admin Hall classroom wing crosses 25%). Breaks: ENERGY STAR eligibility, Gross Floor Area effective date, which requests are valid.
6. **New building opens mid-year** (Cedar Row C, 2025-09-01). Breaks: property floor area and mix, benchmark peer set, partial first-year Use per Area.
7. **Weather regression roll-forward** (baseline end moves a year, or the station changes). Breaks: old `FF_wnRegressionBestResults` rows; normalised bills stop matching; Weather Normalized scenario missing.
8. **Portfolio Manager account connected after months of local requests.** Breaks: pending and error requests submit; PMPropertyID 0 to real; duplicate properties.
9. **A bill corrected or re-imported after GHG ran.** Breaks: `WH_GHG_Tbl` refresh (`wh_GHGRefreshRequest`, `wh_GHGSyncBillId`); Variance and Audit disagree until the sync.
10. **A source disabled for a company that has assignments.** Breaks: orphaned `EmissionMeterMap` rows still computing, or silently dropped from history.

---

# Top gaps, in order

1. Town Center has no data and no source file (Stage 7).
2. Tenant meters have no provider, measure type or points, so no rate can be assigned and no generation row saved (7.1, 6.12).
3. Reconciliation: scenario 20 is not selectable on the desktop; the report needs schedule BL; the Anchor Store fixture is unreachable (7.2).
4. Cedar Row masters carry both a Stage 4 real tariff and a Stage 7 feature rate; Bill = true without the Reconciliation scenario (6.2, 6.3).
5. WUI index values have a screen the recipe says is missing, and none is entered; fixtures contradict each other (2.3).
6. GHG auto-assignment will map the Farm Transfer Meter, 124 Cedar Row submeters and Helios PV (Stage 8, 2.2).
7. No GHG, ENERGY STAR, regression or benchmark output has a known value; 0 of 16 Stage 8 checks assert one.
8. ENERGY STAR uses, floor area, year built, meters and Auto Update are never entered although the scenario YAML has them.
9. Weather regression steps do not match the screens (meter bills, FY/FP only, Weather Normalized scenario required; kW and hourly ton-hour inputs impossible).
10. NTP cost recovery has three sources (Stage 5 hand-entered bills, Stage 4 per-meter assignments, Stage 7 allocation) and Stage 7's nodes do not exist in Stage 2.

# Not checked

- I ran nothing (no builds, tests, database queries, generators). Everything is code and YAML reading.
- The chapter PDFs and `energystar-integration`: only the chapter markdown counts were skimmed.
- `data/providers/*.yaml`, `data/bills/*.yaml`, `data/scenarios/northlake-onboarding-v1.yaml`: not read in detail (only the ES block of `demo-university-v1.yaml`).
- Whether Stage 4's meter ids (`ved_cedar_row_a_master`, etc.) are the same nodes as Stage 2's "Cedar Row A Electric Master": assumed.
- Stage 3 was grepped for Town Center and Cedar Row apartment submeters, not read in full; the absence of Town Center data is a grep result.
- Not opened: the add-config dialog for method 6 commodity, `billAllocationMeterDrawer.ts`, `BillAlloc_ProcessBillItems.sql` (whether allocated child bills carry kWh), `rp_GHG*.sql`, `wh_GHGTableSync.sql`, `rp_BenchMark.sql`, the EmissionCategory seed, unit class ids 3 and 7, the full ES save procs.
- Whether `BillAlloc_ProcessBills` reprocesses a corrected master bill (only the `@ForceAllocation` parameter was read).
- Whether the Web Bill Generation Configuration report lets a user edit Data Source in its UI (the save proc takes it; the report shows it).
- Seed data for `BillAllocationMethod` 2-7 and `PtAllocationMethod` 3 was not found in the repo scripts I grepped.
