# Stages 5 and 6 coverage review (bills, financial)

Review date 2026-11-10. Read-only. Recipe: `C:\Hippo\Git\hippo-synthetic-customer\implementation\stage-5-bills` and `stage-6-financial`. Product: `C:\Hippo\Git\univerus\energyhippo`.
Marks: **READ** = I saw it in product code or the recipe. **INFERRED** = reasoned from code I saw, not confirmed on screen or in a database.
Product paths are relative to the product repo root.

## 0. Read these first

1. **Four source documents the recipe leans on are not in the repo.** Both stages cite `generators/documents/sources/implementation/dream-customer/{phase3-ap-gl-validation-spec,phase1-substrate-extras,bill-charge-line-spec,product-gap-backlog}.md`. They exist nowhere in the recipe repo (READ: file check and a repo-wide name search). Entry lags, "one in three approved", reconciliation rules and the Track B backlog cannot be traced.
2. **The recipe contradicts itself on how each account's bills are entered** (Stage 5 section 6, items 1 to 3; Stage 6 section 6, item 1). That decides which screen a bill goes through, and one version makes a whole series impossible.
3. **The Stage 6 "open alert" check reads the wrong flag** (Stage 6 section 6, item 3). It selects `IsError = 1`, which in the product means "the check failed to run".
4. **Known-value coverage is thin:** about 24 of roughly 1,190 bills have a known total.

---

# STAGE 5. Bills

## 1. What Stage 5 sets up

| File | Screen | Records | Exercises |
|---|---|---|---|
| `01-bill-validation-rules.yaml` | Database Administrator, Nodes > company > Bill Validation, tab Bill Save | Global block of 10 test rows (tests 13, 14, 21, 23, 25, 28 x3 commodities, 41, 42) and 5 account overrides = 6 rows (the Ridgeline generator holds two) | Global and Account scope, Enabled/Disabled, Percent, Amount |
| `02-bill-importer-sources.yaml` | WPF Bill Importer (schema + `appsettings.json`), then web `#/BillImporter` Files, Mappings, Workspace | 2 sources (VED, RCU) and 2 one-row hand-made BIF files | Account mapping, commodity mapping (13 VED codes, 3 RCU), upload, Workspace review, fiscal-period rejection, duplicate-file import, account renumber |
| `03-bills.yaml` | `#/BillEntry` editor and the imported series | 8 series records (VED 13 accounts, VED generator, Central Plant credit series, SGU 10, RCU 17, NTP 6, HOS 3, RWL generated in Stage 7) and 9 fixtures. Count: 49 accounts x 24, minus 1 (SGU Library), plus 17 generator bills = 1,192, plus the corrected SGU bill = 1,193 | Charge lines per provider, TOU split, tiers, credits, tax on subtotal, meter swap, estimate then correction, late bill, mid-bill rate step, account opened mid-window, bill credit transfer |
| `04-bill-images-and-notes.yaml` | Bill Entry image pane, web Note History, Utility Accountant billing-account Notes | 24 PDFs (23 attached here, 1 in Stage 7) and 5 notes (2 METR, 1 BL, 2 BA) | Image attach, notes on 3 table codes |
| `05-approval.yaml` | Bill Entry status chip, Validate action | "About one in three" bills per account to Status 2; one negative test (iris.morales cannot validate) | Status 1 to 2, the Bill Validation function gate |

## 2. Coverage gaps

### 2a. Bill Validation (`01-bill-validation-rules.yaml`)
Editor: `src/Apps/EEMSuite.Apps.DatabaseAdministrator/ViewModels/Companies/BillValidationViewModel.cs`, `Models/Companies/BillValidationTestModel.cs`, `Views/Companies/BillValidationView.xaml`. Engine: `Database/EEMSuite/Procs/BillValidation_Run.sql` plus 38 `BillValidation_Calc*.sql`. Scope table: `Database/EEMSuite/Tables/BillValidation.sql`.

- **8 of the 47 tests are set; 39 are never enabled.** READ: `BillValidation_ResolveTests.sql` says "No row at any scope means the test is off". Not set (engine file in brackets):
  - 1, 2: previous balance, late payment fees.
  - 3: estimated bill (`CalcEstimatedBill`, fires on `BillType = 1`). The recipe's own estimated bill never trips it.
  - 4: bill total reconciliation.
  - 5, 6: billing before account opening / after closure. Stage 2 backdates the Active status because "bill validation's account-opening test reads the earliest Active date" (`implementation/stage-2-hierarchy/01-billing-accounts.yaml` lines 56-57), yet Stage 5 never turns test 5 on.
  - 7, 8, 9: period end after invoice date, due before invoice date, reversed period.
  - 10, 11, 12: overlap, gap, period length change.
  - 15: duplicate bills in fiscal period (the estimate and corrected pair is a natural trigger). 16, 17: missing fiscal periods, insufficient accounting overlap.
  - 18, 19, 20: same total, zero usage, same usage as the preceding bill.
  - 22, 24, 26, 27, 29, 30, 31: historical highs, minimum cost, usage maximum, demand highs and limits.
  - 32, 33, 34, 40: average price increase and maximum, line item count, variable average price.
  - 35 to 38: prior-year and baseline cost and usage change. 39: bill resaved after allowed days. 43 to 46: daily and weather usage change. 47: invoice issued after allowed delay.
  - 99: accrual bill without a mapping (`BillValidation_CalcUnmappedAccruals.sql`). It is not in the recipe's "47-row catalog" at all.
- **Scopes never used:** Company defaults (scope 1) and Validation Groups (scope 2). The editor has Manage Groups with member editing (`BillValidationViewModel.cs`, regions Groups and `GroupMembers`; endpoints `SaveBillValidationGroup`, `SaveBillValidationGroupMembers` in `src/Web/EEMSuite.Web.Endpoints/Controllers/BillEditController.cs`). READ.
- **Mode 2 (Batch Test tab) is never used.** The recipe says "Northlake uses Bill Save only"; `data/eem/northlake-ap-gl-v1.yaml` says "modes 1 Bill Save + 2 Batch Test". READ.
- **States:** all 10 Global rows are Enabled. Global Off, company Inherit/Disabled never appear. READ.
- **Unit looks editable** (`BillValidationTestModel.SelectedUnit`, `CanEditUnit`); the recipe calls unit locked. INFERRED (XAML cell template not opened).
- **Account override rows carry the whole configuration.** READ: `BillValidation_ResolveTests.sql` "The winning row supplies the whole configuration (on/off and thresholds together)". The Science Center test-21 override sets Percent 60 and no Amount, while the Global row has a $1,000 floor. It probably runs with no floor.
- **Weather-normalized scenario for tests 45 and 46** is named in `data/eem/northlake-ap-gl-v1.yaml` fixtures and appears in no stage; Stage 1 uses only "Actual". READ.
- **Deliberate failure fixtures:** the plan promises "bills that deliberately trip each family (cost spike, short period, usage zero)". Stage 5 has none; the only intended alert bill is the Stage 6 Recreation Center illustration. READ.

### 2b. Bill Importer (`02-bill-importer-sources.yaml`)
Web: `src/Web/EEMSuite.Web/frontend/src/scripts/hippo/views/billImporter/*`. Tables: `Database/EEMSuite/Tables/BillImportPro_*.sql`. Validation: `Database/EEMSuite/Procs/BillImportPro_FileData_Validate.sql`.

- **Utility mapping options never set** (`billImporterUtilityMappingForm.ts`, `BillImportPro_Utility`): Import mode (Automatic/Manual), Conflict mode (Interactive/Skip/Duplicate/Replace), Overwrite criteria (Fiscal Year and Period / Start and End Date / Invoice Date / Bill Amount), AutoMap, SingleMeterToAccountMap. READ. The duplicate-file fixture depends on Conflict mode and the recipe never says which mode is set.
- **Commodity mapping columns never set** (`BillImportPro_Commodity`): Exclude, Ignore, IsActive, SourceMeasureTypeID, per-commodity expense account `BI_EXpAcctID`. READ.
- **Commodity rules never used** (`BillImportPro_Commodity_Rules`, `billImporterCommodityRuleDrawer.ts`): Contains, Starts With, Ends With, Custom, Regex. READ.
- **Meter-level mapping:** `BillImportPro_AccMeter` has `Meter_BIF NOT NULL` and `MetaWorldID`; the recipe maps account numbers only. "Meter NOT mapped!" (`FileData_Validate.sql` line 365) is never produced. READ.
- **Item fields the product reads that the recipe's BIF never carries:** Multiplier, PrevReading, CurReading, item start and end dates (`BillImportPro_FileDataItem.sql`; validated at `FileData_Validate.sql` 263-271). Relevant to the Library meter swap and the Ridgeline meter (multiplier 12,000). READ.
- **The CSV the importer converts has no charge-line columns.** `data/providers/valley-electric-district.yaml` fileFormats.billing key columns: `synthetic_account_number, billing_start, billing_end, total_kwh, billing_demand_kw, total_cost, bill_status`. The recipe's schema needs one source column per charge (energy_peak, demand_charge ...) and never lists them. INFERRED (key columns may not be the full list).
- **Workspace features unused:** Remove Import dialog, History explorer/inspector, Workspace notes, line item drawer, mapping-fix flow, source viewer and comparison (`billImporterRemoveImportDialog.ts`, `billImporterHistory*.ts`, `billImporterWorkspaceNotes.ts`, `billImporterWorkspaceSourceViewer.ts`). READ.
- **Rejections the validate proc can raise** (READ): Utility NOT mapped, Billing account NOT mapped, Meter NOT mapped, Commodity NOT mapped, Scenario NOT found, Fiscal Year/Period NOT found, Missing/Non NUMERIC/MONEY/DATE, invoice number too long. File data statuses also include "Previous bill found" and "Previous bill has been exported" (`Migrations/v6.1.0.sql` ~862). The recipe triggers one (fiscal) plus a "bad unit" case that cannot fire (item 5 in section 6).
- **Automatic import:** `BillImportPro_Source.TaskItemID` and status "Pending automatic import process" imply an automatic import task; none is set up in any stage. READ (table, status text); the wiring is INFERRED.
- **Estimate flag is dropped:** the BIF carries `Estimate`, but `BillImportPro_FileDataItem` and `BillItem` have no estimate column. READ.

### 2c. Bills (`03-bills.yaml`)
Editor: `src/Web/EEMSuite.Web/Views/Kendo/BillEntryEditorDetails.cshtml`, `.../views/billEntry/billEntryTablessEditor.ts`, `billEntryItemsGrid.ts`, `billEntryLineItemDrawer.ts`. Tables `Bill.sql`, `BillItem.sql`, `BillItemTemplate.sql`.

- **Bill Type is never set.** The editor has a Bill Type combobox (`GetBillTypes` reads `Global_Type_Code` where `Table_Code='BL'`). Engine: `BillType = 1` is an estimated bill (`BillValidation_CalcEstimatedBill.sql`), `BillType = 2` is an accrual (`BillValidation_CalcUnmappedAccruals.sql`). The estimated fixture and the accrual fixture both need it. READ.
- **"Mark the Bill Items grid Estimate checkbox"** (estimated fixture) names a control that does not exist. The grid columns are meter, commodity type, commodity, unit, quantity, cost, exclude, periods, readings, expense account, provider meter number, actions (`billEntryItemsGrid.ts` 351-461); no "estimate" appears anywhere under `views/billEntry`. READ.
- **Header fields never set:** Invoice Number (no fixture gives one), Received Date (the recipe's "Entered On" is not a field; Received Date is the closest), Previous Balance, Payment Received, Pay Amount. Pay Amount only shows on accounts with Bill Service Type 2 Bill Payment (`src/Data/Dapper/Billing/Bills/DapperBillEditingDTORepository.cs` 74-82). READ.
- **Line fields never set:** per-line Expense Account (`BI_EXpAcctID`; the plan says "set BI_EXpAcctID per charge line by commodity"), Exclude (the `rec_transfer` "Informational" line has no such field; Exclude is nearest), Provider Meter Number. Readings and item periods appear on two fixtures only. READ.
- **"Rate" and "Percent" in the recipe are not fields.** `BillItem` stores commodity, quantity, amount, reads, periods. Rates and percents are check arithmetic only; they are exercised only by comparison with Stage 4 generated bills. READ.
- **Account-level features never set:** Bill Item Templates (`BillItemTemplate`, `GetTemplateChanged`, "NotifyTemplateChange"), Extended Items (`BA_ExtendItems`), Payment Term (`BA_PaymentTerm`). READ.
- **Bill Scenarios:** the editor supports non-Actual bills (`isScenarioActual` hides Received/Issue/Due/Previous Balance/Payment fields; `billEntryScenarioPage.test.ts`). Only Actual exists. READ.
- **Other paths unused:** "Bill Updated" status row on edit (`Migrations/v6.2.0.sql` 36083), bulk delete (`Procs/BulkBill_Del.sql`), delete lock after export (`Procs/rp_BillEntryGrid.sql` `@DisableExportDelete`), staged-image flow, source comparison (`BillEntrySourceComparison*`), line reorder drawer. READ.
- **No stated 2025 summer peak bill for Valley Electric.** VED-TOU-GS peak steps to 0.258 on 2025-01-01 (`implementation/stage-4-rates/05-rates.yaml`); every worked example is 2024 summer or 2025 winter. READ.

### 2d. Images and notes (`04-bill-images-and-notes.yaml`)
One PDF per bill, always PDF; never a second image on a bill, never an image Label (`Images_tbl.Label`, `Seq`), never a PNG/JPG, never deleted or replaced (`ClearImageByImageId`, `ClearImagesByBillId`). One note per target, never edited. READ.

### 2e. Approval (`05-approval.yaml`)
Single Validate only; bulk `ValidateBills` (`BillEditController.cs` line 119) never used. "Roughly one in three" with no list of which bills, so no expected count. No edit-after-approve, no bill approved while an alert is open. READ.

### 2f. Product features in this area with no recipe data
Bill Scenarios other than Actual; Validation Groups and Batch mode; Bill Item Templates; accruals as Bill Type 2 with `BillAccrualMap`; Bill Importer automatic mode and tasks; Commodity Rules; image Label and multiple images; source comparison; payment fields (previous balance, payment received, pay amount, late fees); non-USD bills. READ unless noted above.

## 3. Fields present in the YAML but always empty, null or default
- Every record carries `installed: {}` (placeholder).
- BIF rows: `Scenario` always Actual, `Currency` USD, `PrevBalance` 0, `EarMark` Y, `Estimate` N, one meter per row.
- Tests 41 and 42 have neither Percent nor Amount.
- Bill fixtures: no invoice numbers; only Entered On, Invoice Date, Due Date on the 9 fixtures; the other ~1,180 bills specify only series and period.
- Images: no label, none doubled. Notes: plain text, none updated.

## 4. Depth of `checks.sql` (15 checks)
- **Assert a known value in the query: 3.** `charge_lines_sum_to_total` (returns only failing bills), `itemized_ridgeline_bills_match` (literal expected totals and a Difference), `bct_credit_counted_once` (Difference column).
- **List rows next to a PRINT that states the expectation: 10.** `validation_rules_set`, `imports_configured`, `bills_per_account`, `estimated_then_corrected`, `meter_replacement_continuity`, `late_bill_present`, `generator_account_opened_mid_window`, `ridgeline_transfer_not_entered_here`, `fiscal_period_rejection_logged`, `approvals_by_role` (selects `MIN(LastChangedBy)`, which cannot show every approver was an admin).
- **Existence only: 2.** `images_attached` (counts per account; "23" not asserted), `notes_present`.
- **Entered but not covered by any check:**
  - The bad-data BIF (no check, and the expected rejection cannot occur).
  - The duplicate file import (the headline fixture; reading Admin Hall's lines once is the obvious check).
  - Account renumber continuity (only the previous-number column is listed).
  - The rate-step bill Student Center Jan-25 = 8,469.10 (a PDF exists; no check).
  - Totals of the other ~17 PDF-backed bills (only 3 asserted).
  - Meter swap: the check lists quantity but asserts neither 5,160 nor 10,800.
  - Site/building rollups ("equal the sum of their bills" is in the chapter's done-when).
  - The negative approval test (iris.morales refused).
  - Total bill count; validation behaviour (no check that any alert fired or that the 5 overrides beat Global).
- **Scoped view:** 10 references to `dbo.BillingAccount`, a view that joins `Company` (`Database/EEMSuite/Views/BillingAccount.sql`). Stage 6's own checks say this view returns no rows to a plain session and use `BillingAccount_TBL`; Stage 5 never does. INFERRED for the scoping.
- `late_bill_present` uses `GETDATE()`, so no fixed value can be expected.

## 5. Known expected VALUES that a report must show
Totals stated in the YAML: VED 7 (Science Center Aug-24 15,087.59; Admin Hall Apr-24 6,888.42; Library Sep-24 5,114.37; Student Center Jan-25 8,469.10; generator 1,077.45 and 6,753.10; Central Plant Sep-24 151,171.47), SGU 4 (1,483.85; 13,070.88; 935.90; 885.32), RCU 4 (3,762.60; 8,479.40; 1,984.50; 2,128.00), NTP 4 (35,873.48; 22,760.92; 8,561.20; 6,120.40), Helios 1 (4,474.43), RWL 129,330.27 (Stage 7). Three more Helios PDFs carry totals only in the PDF. I re-added the itemized fixtures and they reconcile (Library, Student Center rate step, both generator bills, Central Plant Sep-24, both SGU gas bills, SGU Admin Hall, RCU Admin Hall and Cedar Row A, NTP Science Center, Helios, and the ten RWL turbine sums to 2,251,384).
**No known value: about 1,170 bills, 98%.** The text says "assumed until Stage 3/4's interval and meter-read data exists". Reports with no stated expected figure: `rp_AccountHistory`, `rp_FiscalPeriodBills`, `rp_DailyProcessingSummary` (the approved count is "roughly a third"), `rp_LateBills`, `rp_BillValidation`, `rp_BillValidationStatus`, `rp_BillReconciliation`.

## 6. Internal inconsistencies
1. **Who enters Cedar Row's Valley Electric and River City bills.** Stage 5 `02` and `03` say they import (31 importer accounts: 14 VED + 17 RCU, user nora.chen, Cedar Row included); Stage 2 agrees (31 Bill Importer accounts). Stage 6 `03` sets the 4 Cedar Row VED and 6 Cedar Row RCU accounts to Bill Entry, leaving 21 importer accounts. `05-approval.yaml` says marcus.reed enters every Cedar Row bill. `03-bills.yaml` notes say "the Cedar Row company scope beating the provider default" and then "import in every company, Cedar Row included".
2. **The six Thermal Plant allocation accounts.** Stage 5 `03` enters SYN-NTP-C-0000001 to 0000006 as manual monthly bills by keiko.tan. Stage 2 and Stage 6 set their Bill Entry Type to Bill Allocation, and Stage 2 states "Bill Entry lists only Bill Entry accounts (BillType_Code 0) ... the 31 Bill Importer, 6 Bill Allocation and 1 Bill Generation accounts never appear there" (`01-billing-accounts.yaml` lines 50-52). They cannot be entered in Bill Entry; the 4 NTP PDFs have nowhere to attach until bills exist.
3. **VED fixtures are written as hand-entered but sit on Bill Importer accounts:** Library meter swap, Student Center rate step, both generator bills, Central Plant credit bill. The `02` BIF has no columns for item periods or reads (section 2b).
4. **The NTP Science Center validation override is entered under the wrong company.** `01-bill-validation-rules.yaml` says "Validation for: Northlake Thermal Plant" for SYN-NTP-C-0000001; Stage 2 and Stage 6 put all six NTP accounts in Northlake University.
5. **The bad-data sample cannot fail as described.** It is an SGU row, but only VED and RCU have a `BillImportPro_Utility` row, so the first rejection is "Utility NOT mapped!". It adds a `Unit1` column the chapter says does not exist ("a bill item has no unit of its own"), and `FileData_Validate.sql` has no unit check. READ.
6. **Stale Stage 4 names.** `03-bills.yaml` (lines 351-352) and the chapter's "Before you start" cite `VED-TOU-GS-FY25` as a loaded rate. Stage 4 has no such rate (the step is a second price date on VED-TOU-GS; one note mentions the name at `05-rates.yaml` line 245). "(it does not yet)" about winter pricing is also out of date.
7. **Stale rate notes.** `03-bills.yaml` says the riders "have no rate parameter in the Phase 1 model" and fixed O&M is "a bare amount". Stage 4 now has Public Purpose Program 0.015 and Utility Users Tax 0.05 as Bill Adj/Taxes charges and Fixed O&M Share as a User Defined per-meter price.
8. **Counts.** Checks and chapter say 24 bills per account (23 for SGU Library); the estimate and corrected fixture gives SGU Student Center 25.
9. **Unfinished instruction.** The estimated fixture asks the operator to "record which" of a supersedes link or an independent second bill was used. The `Bill` table has `refBillID`; I found no field for it under `views/billEntry` (INFERRED). The check cannot know what to expect.
10. **Four cited source documents are missing** (section 0).

## 7. Effects of today's Stage 4 rework on Stage 5
- **No `NL-` rate is named in Stage 5 or 6** (grep, READ). The nine moved rates break nothing here.
- **No renamed TOU schedule is named in Stage 5 or 6** (grep for Summer Peak, Winter Part-Peak, Annual All Hrs: none). "Rate schedule" in Stage 5 means the tariff name. All 14 rate names Stage 5 uses exist in `05-rates.yaml` except `VED-TOU-GS-FY25`.
- **`VED-TOU-GS-FY25` does not exist** (item 6).
- **VED-TOU-PRI has no 2025 price date** (2024-01-01 and 2026-01-01 only), but `03-bills.yaml` says "Every VED account's Jan-25 bill straddles the step the same way". A generated Central Plant 2025 bill stays at 2024 prices. READ.
- **Commodity names differ between Stage 4 rates and the Stage 5 importer.** Stage 4 maps energy to On Pk kWh / Part Pk kWh / Off Pk kWh, demand to Non-TOU kW Billed, riders and taxes to Elec Misc Chgs/Credits (`05-rates.yaml`). `02-bill-importer-sources.yaml` maps the same charges to "Electric, TOU", "Electric, Demand", "Electric, Fixed", "Electric, Rider", "Electric, Tax", "Electric, Adjustment". A generated and an imported bill for one account carry different commodities, so line-by-line reconciliation (`rp_BillReconciliation`) cannot line up. READ both.
- **Bills the engine will price differently** (from `stage-4-rates/stage-4-coverage-review.md`, relayed from its helpers, not rechecked by me):
  - Gas season: the engine prices each day at its season; the provider prices a whole bill at the season of its end date. SGU Admin Hall Apr-25 (2025-03-15 to 04-14, 1,483.85) and the Student Center estimate and corrected pair (2024-10-15 to 11-14; 935.90, 885.32) straddle the winter boundary.
  - On Peak and Super On Peak skip holidays; other significances do not. VED bills with a holiday in the period can differ.
  - Per-meter prices (lighting fixtures, stormwater ERUs, Fixed O&M) have no desktop screen. RCU Admin Hall 18 ERU = 201.60 and the NTP fixed shares 340 / 240 / 270 cannot be reproduced until that is solved. Stage 5 gives only three of six NTP shares.
  - Water meters carry water, sewer and stormwater as three rows; the engine prices one rate per meter.
- **Ridgeline lines the engine cannot produce** (notes on VED-GEN-IC and VED-BCT in `05-rates.yaml`): reactive charge (161.07), `bct_credit_transferred` (+152,792.65), `bct_credit_received` (-152,792.65), the 12.50 fee. A generated generator bill would be 285.00 + 580.07 - 152,792.65 + tax, a credit balance, not 1,077.45. The three itemized PDFs are valid as import acceptance, not as rate tests.
- **Good news:** Helios 0.12138 on 2025 bills now matches (was 0.121); net metering -0.092 has one date, matching "does not escalate"; RCU/SGU/NTP have no 2025 step, matching 2024-priced sample bills dated 2025; the 2026 3% step falls after the last Stage 5 bill (Dec-25).
- I did not check whether Stage 5's totals appear in `07-rate-tests.yaml` (not yet reworked).

## 8. Stage 12 scenarios for the bill area
1. **The utility reissues a bill after approval:** edit amounts on a QC-approved bill (writes "Bill Updated"), re-validate. Could break: status regression, queue admission (the v7.0.0 queue SQL treats Bill Updated as an edit marker, not progress past validation), stale alerts until the job reruns.
2. **A bill is exported, then rebilled for the same period** with a new invoice number and a credit. Could break: test 15, rollups double count, exported bill cannot be deleted (`rp_BillEntryGrid.sql` `@DisableExportDelete`).
3. **The utility adds a new charge code** to the VED or RCU file. Could break: "Commodity NOT mapped!" holds the whole bill; rule vs mapping row; bills stuck at status 3 or 8.
4. **A fiscal calendar runs out in January** (calendars end 2026/2027): import January bills. Could break: "Fiscal Year NOT found!" on every bill.
5. **An account closes and is replaced** (second renumber, final bill, first bill same month, Active/Closed dates). Could break: tests 5 and 6, importer account mapping repoint (`BillImportPro_AccMeter`), previous-number search.
6. **A validation threshold changes on a live company** (Global 35% to 25%, or an account moves into a new Validation Group). Could break: old results persist until rerun; precedence picks an unexpected row.
7. **An estimate is replaced by the real bill** with Bill Type Estimated and test 3 on. Could break: duplicate-period alert, rollup counts both, no `refBillID` link.
8. **An approver leaves** (group membership or function revoked). Could break: bills sit at status 1; the function, not the group name, is what the product checks.
9. **An imported bill is removed and re-imported** (Workspace Remove Import vs `beBill_Del.sql`). Could break: file status stuck at "Imported", "Previous bill found".
10. **A partial payment and a late fee appear** (previous balance, payment received, tests 1 and 2 on). Could break: these fields have never held data in Northlake; test 4 reconciliation.

---

# STAGE 6. Financial

## 1. What Stage 6 sets up

| File | Screen | Records | Exercises |
|---|---|---|---|
| `01-gl-accounts.yaml` | Database Administrator, Nodes > company > GL Accounts | 16 accounts: NLU 6, Cedar Row 5, Thermal Plant 5 (codes 5100-ELEC, 5110-GAS, 5120-WATER, 5130-THERMAL, 5140-SOLAR, 5150-WIND, 2000-AP) | Account Type Expenses and Liabilities, per-company codes |
| `02-gl-fields.yaml` | **No screen** (view not wired) | 5 segment definitions, 3 company value sets | Target only |
| `03-account-gl-defaults.yaml` | Utility Accountant > Billing Account > Definitions | 51 accounts in 6 provider records | Bill Service Type (3 values), Bill Entry Type (4 of 5), Liability Account, Default Expense Account |
| `04-ap-export-formats.yaml` | `#/reporting/APApprovalAndUpload` format picker | 7 formats + a routing rule; **none runnable** | Nothing today |
| `05-ap-approval-and-upload.yaml` | Same page | 4 examples; only the queue and the validation block are usable | Queue admission rules, Ridgeline routing |
| `06-accruals.yaml` | Config Tool System Constants, Commodities, Bill Entry | 2 constants, 2 commodities, 1 open accrual bill (3,400.00) | Open accrual; reversal blocked |

## 2. Coverage gaps
- **No export format runs.** `ExportSetup` and `PermissionCatalog TypeKey='EX'` are empty in Northlake (the recipe's own finding). The product ships only Massport examples (`Database/EEMSuite/Schemas/MPA/Procs/MPA.MPA_FI_AP_*`, `MPA_FI_GL_*`, `MPA_FI_AR_*`, `MPA.MPA_RevertExports`, `MPA.MPA_FI_UploadLog_Write`, `MPA.gc_ExportFiles_Get_{AP,GL,BI,ACR}`). `Database/EEMSuite/Schemas/Northlake/` holds only the Stage 2 import, branding and address functions. So Stage 6 exercises none of: preview, create file, ExportFile/ExportLog rows, bill advanced to uploaded, re-run of an exported bill, export revert, upload log, and the GL, BI (AR) and ACR (accrual) export types. READ.
- **AP approval page controls never exercised** (`src/Web/EEMSuite.Web/frontend/src/scripts/hippo/reports/apApprovalAndUpload.ts`, `Views/Reporting/APApprovalAndUpload.cshtml`): per-bill Approve checkbox and Check All, Header Date, Batch Number, totals grid, Preview vs Create, provider filter (`@utilityProviderIds` in `Procs/rp_FinancialInterfaceApproval.sql`), the `|Other|` parameter, the confirm text ("status ... changed to uploaded"), the "export already exists" message, delivery queued (task history). READ.
- **GL accounts:** Account Type Assets (0) never used; deleting an in-use account (`Procs/uaGLAccountIsUsed_Check.sql`, `uaGLAccount_Delete.sql`) never tried; GL account favorites (`GLAccountFavoriteListSource.cs`). READ.
- **GL user-defined fields:** `GLAccountUDField` has ApplicationAlias, UDFieldName and **UDFieldDefault**; the recipe omits the default. READ: `Database/EEMSuite/Tables/GLAccountUDField.sql`. `rp_GLAccountUDV` has no data.
- **Per-line expense account** (`BillItem.BI_EXpAcctID`), per-commodity importer expense account (`BillImportPro_Commodity.BI_EXpAcctID`) and `BillItemTemplate.BT_ExpAcctID` are never set, so every line lands in the account default. A mixed-coded bill (tax or credit lines to their own accounts) is the most common real GL case. The `ridgeline_bct_coded_once` check coalesces to the default, so it can only ever show 5100-ELEC. READ.
- **Account settings:** Bill Service Type 0, 1, 2 all used. Bill Entry Type 0, 1, 2, 3 used; 10 (Other) is not. READ.
- **Accruals:** the recipe uses two SysConstants (2300 and 2301, "MPA Accruals/Reversals") plus commodity lines. The product also has accrual bills as Bill Type 2 mapped in `BillAccrualMap` with validation test 99 (`BillValidation_CalcUnmappedAccruals.sql`, `Schemas/MPA/Procs/MPA.MPA_Open_AFB_Sav.sql`, `MPA.uaQC99_MPA_Accruals.sql`). Stage 6 uses only the older mechanism, and the open accrual fixture does not set Bill Type 2. `Procs/rp_Accrual.sql` hard-codes fiscal periods 2019-1 to 2019-3 and hierarchy -3 inside the proc (lines 29-31), so it cannot be exercised as written. READ.
- **`Procs/rp_OpenAccruals.sql`** deletes from `Accrual_Bill`, and no `Accrual_Bill` table is under `Database/EEMSuite/Tables` (READ), matching the recipe. The Reverse button calls a customer-named popup `CustomReverseBill` (READ).
- **Reports with no data:** `rp_AccountsPayableDetail`, `rp_APApprovalAndUpload`, `rp_GLAccountUDV`, export log reports (red in `generators/documents/sources/implementation/report-coverage-matrix.md`).

## 3. Fields present in the YAML but always empty, null or default
- Activity / Project is blank on 13 of 16 GL value rows (set only on 5130-THERMAL, and 5140-SOLAR at NLU and Cedar Row); Object is blank on all 16; Program is blank on the 2000-AP rows. Intentional per the guide, but Object never holds a value.
- Every Liability Account is 2000-AP; every Default Expense Account is the provider's, with no exceptions on any account.
- GL account descriptions repeat across the 3 companies.
- Accrual fixture: one amount (3,400.00, "assumed"), one account, no note, no reversal.
- Approval queue: Header Date and Batch Number never given.

## 4. Depth of `checks.sql` (8 checks)
- **Assert a known value in the query: 0.**
- **List rows next to a PRINT that states the expectation: 8.** `gl_chart` (16), `account_defaults` (51), `export_formats_registered` (expected empty), `ap_files_generated` (expected empty), `blocked_by_validation`, `ridgeline_gl_only` (first set expected empty; second shows BillAmount beside CodedAmount without a Difference), `ridgeline_bct_coded_once` (PRINT says NetCredit must be -152792.65; the SELECT does not compare), `accrual_pair`.
- **Existence only: 0.** Three "pass" by returning nothing (`export_formats_registered`, `ap_files_generated`, `ridgeline_gl_only` first set), and the first two pass in a broken install too.
- **Not covered:** GL UDF tables (`GLAccountUDField`, `GLAccountUDValue` never queried); Bill Service Type counts; the Recreation Center alert example; the No AP Upload control account (only inside the 51-row dump); the open accrual's amount; a per-company chart count.

## 5. Known expected VALUES
Known: 16 accounts; 51 default rows; the three Ridgeline bills (1,077.45; 151,171.47; 6,753.10) and the RWL statement (129,330.27); net credit -152,792.65. Nothing else in Stage 6 has an output value: no file contents, no journal total, no accrual figure beyond the illustrative 3,400.00, no queue count, no GL UDF render. No value for: every format in `04`, `rp_AccountsPayableDetail`, `rp_GLAccountUDV`, `rp_OpenAccruals`, and the Recreation Center alert (5,800.00 and 8,200.00, "assumed, illustrative").

## 6. Internal inconsistencies
1. **Stage 6 `03` contradicts Stage 2 on three settings** (Stage 2 counted by awk over `01-billing-accounts.yaml`). Thermal Plant allocation accounts (6): Stage 2 AP Upload Only, Stage 6 Bill Payment. Helios accounts (3): Stage 2 Bill Payment, Stage 6 AP Upload Only. Cedar Row VED (4) and RCU (6): Stage 2 Bill Importer, Stage 6 Bill Entry. The plan (`data/eem/northlake-ap-gl-v1.yaml`) agrees with Stage 2. `checks.sql` `account_defaults` says to match `03-account-gl-defaults.yaml`, so it checks the Stage 6 version.
2. **Pay Amount cannot be exercised in the Stage 6 version.** It shows only on Bill Payment accounts; Stage 6 makes only NTP and RWL Bill Payment, neither enterable in Bill Entry. In Stage 2's version Helios (manual, Bill Payment) would show it. READ.
3. **`blocked_by_validation` reads the wrong flag.** It selects `BillValidation_Tbl WHERE IsError = 1` as "open alerts". `Procs/BillValidation_Run.sql` (lines 67, 269-281) sets `IsError` only when a check could not run; a failed test is a row with `IsError = 0`. The check returns nothing while real alerts exist, which looks like a pass. READ.
4. **GL UDF "overrides" cannot be stored as written.** `GLAccountUDValue` is keyed by GL account and field only (`Database/EEMSuite/Tables/GLAccountUDValue.sql`). "Science Center override: 5100-ELEC and 5130-THERMAL use Department Labs / Program Research" and "Ridgeline generator override" on SYN-VED-A-0010014's 5100-ELEC lines cannot be held per building or per billing account. They would need separate GL accounts. READ.
5. **The alert example does not agree with the series.** Recreation Center SYN-VED-A-0010008 has Nov-24 5,800.00 and Dec-24 8,200.00 in Stage 6 `05`, while Stage 5 lists the account in the monthly series with quantities assumed. A seasonal building may also trip tests 21 and 25 in other months. INFERRED.
6. **Accrual table claim:** the recipe says "grep confirmed" that `CustomReverseBill` is absent from the repo; I did not re-run that grep.
7. **Four cited source documents are missing** (section 0).

## 7. Effects of today's Stage 4 rework on Stage 6
- Stage 6 names no rate and no rate schedule and no `NL-` rate (grep, READ).
- **Dollar amounts that depend on Stage 4:** 129,330.27 (RWL-XFER-2024: 0.058 per kWh and the -1,250.00 Research Credit are both present in Stage 4 and match); 1,077.45, 151,171.47 and 6,753.10 (VED-GEN-IC, VED-TOU-PRI, VED-BCT; the credit, transfer, reactive charge and fee are not engine-computable, see Stage 5 section 7); the illustrative 5,800.00 and 8,200.00.
- The Ridgeline GL-only journal (129,330.27 against 2000-AP) needs the generated statement, which depends on Stage 4's RWL rate and the meter assignment (Stage 7).
- The 3,400.00 accrual estimate is tied to no rate; Admin Hall's real April 2024 bill is 6,888.42. A computed estimate would come from VED-TOU-GS on Stage 3 data.
- `ridgeline_gl_only` rounds `BL_Amount` to 2 places because generated bills keep 4 decimals (product finding 72); the rework leaves this unchanged.

## 8. Stage 12 scenarios for the financial area
1. **A new GL account is added mid-year and an account's default expense account changes.** Could break: old lines keep the old code (per-line vs default), mixed coding in a period, an in-use account cannot be deleted.
2. **An AP export is created, found wrong, reverted and re-run.** Could break: ExportLog/ExportFile rows, bill status back to QC Approval, batch numbers (the product's model is `MPA.MPA_RevertExports`).
3. **A bill is approved with an alert open, then corrected.** Could break: the bill leaves and rejoins the queue; "Bill Updated" vs queue admission.
4. **A vendor account moves from AP Upload Only to No AP Upload or Bill Payment with approved bills pending.** Could break: bills vanish from the queue; Pay Amount appears.
5. **An accrual is booked and the real bill arrives** (Bill Type 2 and/or Accruals commodity). Could break: no screen creates the reversal (recipe finding), test 99, a double-counted period.
6. **A GL segment value changes after an export, or a sixth segment is needed.** Could break: only 5 segments exist (`GLAccountUDField` is install-wide); the next file differs from the last.
7. **The finance export format changes** (a new column in the voucher). Could break: the ExportSetup row's builder proc, preview vs create, old files cannot be regenerated identically.
8. **A company is added with its own chart.** Could break: `GLAccount` has a unique index on `(CompanyID, GL_AccountCode)`; an account cannot take another company's codes.
9. **A second GL-only account appears.** Could break: GL-only routing is by Bill Entry Type only (`04-ap-export-formats.yaml`), so a manually entered GL-only account would reach AP files.
10. **Two exports in one day reuse a header date or batch number.** Could break: duplicate batches; the "export already exists" idempotency (`apApprovalAndUpload.ts`).

---

## What I could not check
- No database was queried (rules). The installed 47-row test catalog, the `BL` rows of `Global_Status_Code` and `Global_Type_Code`, and which validation tests are on by default in `EEMSuite_Northlake` are unverified; the recipe says it verified the catalog, and I only read the table definition.
- I did not open the XAML to confirm which Bill Validation cells are editable (Unit, colour, icon) or the Definitions page beyond its bindings.
- I did not read Stage 4 `06-rate-assignments` and `07-rate-tests`, nor Stage 3 or 7 files, beyond the lines cited.
- The four missing source documents could not be read, so claims sourced to them (entry lags, one-third approval, reconciliation rules, backlog items) are unverified.
- Whether Bill Entry can enter a bill on a Bill Importer or Bill Allocation account by some other path: Stage 2 says no; I read `rp_BillEntryGrid` and `GetBillInfo` only partly.
- The chapter PDFs and the bill PDFs under `documents/utility-bills/` were not opened; I used the source Markdown and YAML. I did not check that the PDFs match the Markdown.
- Whether the editor exposes a `refBillID` (supersedes) link: not found under `views/billEntry`, not proven absent from the Razor view.
- The Northlake AP queue SQL does not exist, so queue behaviour comes from the recipe, `rp_FinancialInterfaceApproval.sql` and the MPA examples.
