---
title: Stage 6. Financial
subtitle: GL chart, account GL/AP defaults, export formats, approval and upload, accruals
status: Ready to enter
---

# Stage 6. Financial

Stage 6 gives every Northlake bill a GL account to land on and exercises the AP
approval-and-upload path Bill Administrators actually use. Most of it is
straightforward: a GL chart per company, and a Liability/Expense account plus a
Bill Service Type on every billing account from Stage 5. Three pieces are not
straightforward, and this chapter says so plainly rather than working around it
with SQL: the GL user-defined-fields view is not wired, no AP export format is
registered in this installed instance (not even the two the Phase 3 plan called
"built-in"), and the accrual reversal has neither a caller nor, in this
instance, the table it would write to. Each is entered as far as the product
lets it go and then stated as a Finding.

**Added 2026-10-01: Ridgeline Wind.** The Thermal Plant bought a ten-turbine
wind company on July 1, 2024, and Stage 6 gains two entries and one rule
because of it. The entries are 5150-WIND, Ridgeline wind energy transfer, in
the Thermal Plant's GL chart (Step 1), and the GL defaults of the two Ridgeline
billing accounts (Step 3). The rule belongs to the export steps (4 and 5):
Ridgeline's monthly transfer statement is GL only, a journal between the plant
and its own wind company with no payment leaving the plant, so it must never
reach an AP file. The Valley Electric generator account pays only its own small
charges and is an ordinary AP account. Its export credit moves to the Central
Plant's account under the bill credit transfer, and the credit is coded once,
on the Central Plant bill where it lands. Step 2 gains the new code's target
values; Step 6 is unchanged.

## Before you start

- Stage 5's bills, and the GL account codes Stage 5 assumed (5100-ELEC through
  2000-AP), are in place.
- The three Ridgeline bills Step 5 uses are in place: the generated July 2024
  transfer statement, the generator's first bill (July 1 to August 4, 2024) and
  the Central Plant's September 2024 bill (August 5 to September 4).
- Read the Findings before Steps 4 and 6 - both describe exactly what is and is
  not possible to enter today, so you do not spend time looking for a screen
  that is not there.

## Step 1. GL Accounts

**Where:** Database Administrator, Nodes, the company node's GL Accounts tab.

**Enter:** [01-gl-accounts.yaml](01-gl-accounts.yaml), sixteen accounts across
three companies.

**Order inside the editor:** pick Account Type from the chip dropdown (Assets,
Expenses, Liabilities), type the Account Code and Description, and Add. GL
accounts are per company - the same code (5100-ELEC) is entered separately in
every company that needs it. Northlake University gets all five expense codes
plus 2000-AP; Cedar Row Apartments gets four (no Thermal Plant allocation);
Northlake Thermal Plant gets its own three utility codes, 5150-WIND for the
Ridgeline Wind transfer, and 2000-AP - it never bills itself the allocation or
the solar accounts. Ridgeline bills no other company, so 5150-WIND is entered
in the plant's chart only.

**Record:** nothing generated.

**Check:** `gl_chart`.

## Step 2. GL user-defined fields

**Where:** target only - see Findings.

**Enter:** [02-gl-fields.yaml](02-gl-fields.yaml) states the five segments
(Fund, Department, Program, Activity/Project, Object) and their values per GL
account, ready for the day the view exists. The Thermal Plant's list now
includes 5150-WIND and a Ridgeline generator override.

**Record:** nothing; nothing can be typed in today.

**Check:** none (the underlying columns exist but are unreachable from any
screen).

## Step 3. Account GL defaults

**Where:** Database Administrator, Utility Accountant tab, each billing
account's Definitions page, Associated G/L Accounts section.

**Enter:** [03-account-gl-defaults.yaml](03-account-gl-defaults.yaml), Bill
Service Type, Bill Entry Type, Liability Account and Default Expense Account
for all 51 billing accounts.

**Order inside the editor:** these four fields sit below the account's own
identity fields on the same Definitions page Stage 2 already opened to create
the account - there is no separate screen. Liability Account is 2000-AP
everywhere, including the two negative-control accounts. Default Expense
Account follows the provider (Valley Electric to 5100-ELEC, and so on). Bill
Service Type is three real values (No AP Upload, AP Upload Only, Bill Payment -
see Findings), not the four the AP/GL plan assumed; River City's Cedar Row B is
the No AP Upload control, and the Thermal Plant's six allocations use Bill
Payment instead of AP Upload Only, since they settle between Northlake
companies rather than through a real vendor invoice. The two Ridgeline accounts
join the Thermal Plant company: the Valley Electric generator account takes the
ordinary Valley Electric defaults, and the transfer account, the one GL-only
account, takes Bill Payment with Bill Generation as its Bill Entry Type and
5150-WIND as its Default Expense Account.

**Record:** nothing generated.

**Check:** `account_defaults` (51 rows).

## Step 4. AP/GL export formats

**Where:** target only for every format - see Findings.

**Enter:** [04-ap-export-formats.yaml](04-ap-export-formats.yaml) states all
seven formats the Phase 3 plan named, and why none can run today. It also
states the one routing rule Ridgeline adds: the GL-only transfer statement
belongs to the GL journal and to no file of vendor invoices.

**Record:** nothing; there is nothing to pick on the Preview/Create Interface
File screen in this instance.

**Check:** `export_formats_registered`, `ap_files_generated` (both expected
empty; that emptiness is the check).

## Step 5. AP approval and upload

**Where:** Web SPA, `#/reporting/APApprovalAndUpload`.

**Enter:** [05-ap-approval-and-upload.yaml](05-ap-approval-and-upload.yaml).

**Order:** filter to a company and period, and select the QC-Approved,
AP-eligible bills - everything up to picking a format still works and is worth
proving. The blocked-by-validation fixture (Recreation and Aquatics Center,
December 2024) shows a bill whose cost jumped 41% staying out of the queue
until its validation alert clears, even after Stage 5 marked it QC Approval.
Two Ridgeline fixtures prove the routing. The generated July 2024 transfer
statement (GL only) stays out of the queue even after QC Approval, so no AP file
can name it. The generator's first bill (July 1 to August 4, 2024) is an
ordinary AP bill for its own charges ($1,077.45), and the bill credit transfer
is coded once, on the Central Plant's September 2024 bill. Stop before "Create
Interface File" - the format list is empty (Step 4).

**Record:** nothing generated.

**Check:** `blocked_by_validation`, `ridgeline_gl_only` (its first result set
expected empty), `ridgeline_bct_coded_once`.

## Step 6. Accruals

**Where:** Configuration Tool's System Constants (Add Constant), Database
Administrator's Commodities (Add Commodity), then `#/BillEntry` for the accrual
bill itself. See Findings - the reversal half cannot be entered at all.

**Enter:** [06-accruals.yaml](06-accruals.yaml).

**Order:** create the Accruals and Reversals commodities for Northlake
University first, then point two new System Constants ("MPA Accruals", "MPA
Reversals" - the names are inherited from the proc that reads them, not
anything Northlake-specific) at their commodity IDs. Then enter the open
accrual as an ordinary manual bill on the Accruals commodity, for a period
Valley Electric has not yet billed Admin Hall.

**Record:** the two new CY_CommodityIDs, into the System Constants above.

**Check:** `accrual_pair` (the open half only; the reversal half has no
check because it cannot exist).

## Stage 6 is done when

- One runnable AP format file exists per format that is actually registered in
  this instance - today that is none, and the chapter says so rather than
  showing a file that was never produced.
- Validation passes and failures are both visible: clean bills reach the AP
  approval queue, and the deliberate failure stays out of it until resolved.
- The accrual pair is visible exactly as far as the product allows: the open
  accrual bill exists and appears wherever an open accrual would show up; the
  reversal does not exist, and nothing pretends otherwise.
- Ridgeline's routing holds: the GL-only transfer statement appears in no AP
  queue and no AP file, the generator's bill is an ordinary AP bill, and the
  bill credit transfer is coded once, on the Central Plant bill.

Run `checks.sql` beside this chapter against the instance database to see each
of these as a result set - several are expected to come back empty, and that
emptiness is what the check is proving.

## Findings

- **The GL user-defined-fields view is not wired.** Confirmed exactly as
  product-gap-backlog.md item 3 describes: `Models/Companies/
  GLUserDefinedModel.cs` and the full API round-trip
  (`SaveGLAccountFieldAsync`/`SaveGLAccountFieldValueAsync` on
  `IGLAccountsDTORepository`/`IGLAccountsDTOService`, wired through
  `GLAccountsDTOController`) exist end to end, but no `.xaml` file in the
  repository references any of them. `GLAccountUDField` itself has no
  `CompanyID` column - the five segment aliases are one global set, not
  per-company, which the target file above already assumes. This is the
  smallest of the three gaps (a view, not a feature) and unblocks the
  `nl_ap_gludf` export format once built.
- **No AP export format is registered in this installed instance - not even
  the two the Phase 3 plan called built-in.** `ExportSetup` has zero rows, and
  `PermissionCatalog` has zero `TypeKey='EX'` rows, in `EEMSuite_Northlake`
  (both verified by direct query). `Exports_Get` inner-joins the two, so the
  AP Approval & Upload format picker has nothing to show regardless of which
  format a user is permitted to run. The `EEMSuite` upgraded-demo database, by
  contrast, has both catalog rows and both `ExportSetup` rows for `export_ap`/
  `export_ap2`, pointing at `HIPPODemo`-schema builder procs
  (`HIPPODemo.EEM_AP_BillsForApproval_Get`, etc.). That confirms the two
  "built-in" formats are themselves a demo customer's own customization, not
  core, always-present product objects - Northlake's install never received
  the equivalent. Recommend either loading a Northlake-specific pair of
  `PermissionCatalog`/`ExportSetup` rows (reusing the demo's proc shapes) or
  building the five richer formats product-gap-backlog.md item 2 already
  scopes, and registering all seven the same way.
- **Accruals are blocked twice over, not once.** Product-gap-backlog.md item 4
  already says no UI or API calls `rp_OpenAccruals` with `@Reverse=1`. Reading
  the proc (`Database/EEMSuite/Procs/rp_OpenAccruals.sql`) shows it is worse
  than unwired: its first executable statement deletes stale rows from
  `dbo.Accrual_Bill` unconditionally, before it even checks `@Reverse`, and
  `EEMSuite_Northlake` has no `dbo.Accrual_Bill` table at all (verified against
  `sys.tables`; only `dbo.BillAccrualMap` exists here). The `EEMSuite`
  upgraded-demo database has both tables. Calling `rp_OpenAccruals` against
  Northlake today - with either value of `@Reverse` - fails immediately with
  "Invalid object name 'Accrual_Bill'". The open accrual itself is unaffected
  (it is an ordinary manual bill, entered in Step 6); only the reversal path is
  affected, and it needs the missing table restored before the missing caller
  is even worth building.
- **Bill Service Type cannot say GL only.** Ridgeline's transfer statement is
  GL only, and EEM's three Bill Service Type values have no such option; Bill
  Payment is only the nearest. The Massport AP approval builder
  (`MPA.MPA_FI_AP_BillsForApproval_Get`) admits `Type_Code in (1, 2)` and reads
  2 as both AP and BI, so a Northlake builder that followed it would put a Bill
  Payment account, the transfer statement included, in the AP file. Northlake's
  AP builders therefore need an exclusion of their own, and the target file
  assumes one keyed on Bill Entry Type (Bill Generation). Closing it for real
  needs GL-only and AP-and-GL values in the lookup, honored by every builder.

None of the above blocks entering what this stage can enter - the GL chart,
the account defaults, and the open accrual all go in normally. They are
recorded so the AP export and accrual features start from an accurate account
of what is actually installed, not what the Phase 3 plan assumed.
