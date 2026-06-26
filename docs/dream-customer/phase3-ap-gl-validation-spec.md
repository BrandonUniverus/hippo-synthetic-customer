# Phase 3 — AP / GL, Validation & Accruals Spec

"Do actual billing" end to end and **produce real AP/GL interface files**. Lights
up AccountsPayableDetail, APApprovalAndUpload, GLAccountUDV, BillValidation(+Status),
OpenAccruals, and `my_exports`.

> **Entry path** (see [entry-path-and-gaps.md](entry-path-and-gaps.md)): bill entry,
> GL accounts, account AP/expense assignment, bill validation rules, and the AP
> **approval + upload run** are **UI-DIRECT/UI-THEN-RUN**. **Gaps:** there is **no
> UI to define a new AP/GL export format** (A1 — only the 2 built-ins `export_ap`/
> `export_ap2` are usable by hand; richer ERP formats are dev work); **accruals
> have no UI/API at all** (A2 — not hand-enterable); the **GL user-defined-fields
> view is not wired** (A3 — base-account coding only until finished). These are the
> phase's biggest reframes.

EEMSuite facts (verified): export eligibility gates on `BillingAccount.Type_Code`
(0 No Upload, 1 AP, 2 GL, 3 AP+GL) + active status. GL accounts in `GLaccount`
(`Type_Code` 0 Assets / 1 Expenses / 2 Liabilities) with 5 user-defined segments
(`GLAccountUDField`/`GLAccountUDValue`). Bill lines carry GL via
`BillItem.BI_EXpAcctID`. Export engine = `ExportSetup` (per-format Approval/
UploadFile/Batch procs) → `ExportFile`/`ExportLog`; `ExportType` rows APINV/APDIS.
47 `BillValidation` rules. Accruals = bills tagged commodity 2300 (Accruals) /
2301 (Reversals), paired in `Accrual_Bill`/`BillAccrualMap`.

## Source-model extension

Add: `gl_account` (company, type 0/1/2, code, description), `gl_ud_field`
(alias GLUDF1–5, name), `gl_ud_value` (gl_account, field, value), `ap_export_setup`
(name, format, file_type, status_code, builder_ref), `bill_validation_rule`
(test_id, measure_type, pct_threshold, abs_threshold, mode), `bill_validation_result`,
`accrual` (bill_ref, reversal_bill_ref, commodity 2300/2301). Bill charge lines
(Phase 1) gain `gl_account_code` population here.

## 1. GL chart of accounts

Per company, expense accounts by commodity + AP control:

| code | type | description |
| --- | --- | --- |
| 5100-ELEC | 1 Expenses | Electricity expense |
| 5110-GAS | 1 Expenses | Natural gas expense |
| 5120-WATER | 1 Expenses | Water/sewer/stormwater expense |
| 5130-THERMAL | 1 Expenses | Chilled water / steam allocation |
| 5140-SOLAR | 1 Expenses | Solar PPA expense |
| 2000-AP | 2 Liabilities | Accounts payable control |

**5 GL user-defined segments** (`GLAccountUDField`, aliases `GLUDF1–5` so the
Sacramento-County-style exporter resolves them) — realistic university dimensions:

| alias | segment |
| --- | --- |
| GLUDF1 | Fund (e.g. 110 Operating, 250 Auxiliary, 700 Plant) |
| GLUDF2 | Department (Facilities, Housing, Athletics, Labs) |
| GLUDF3 | Program (Instruction, Research, Residential, Admin) |
| GLUDF4 | Activity / Project |
| GLUDF5 | Object code |

`gl_ud_value` populates these per GL account with realistic + **partly-blank**
coverage (to exercise empty-segment formatting). Building→Fund/Department mapping:
campus buildings → Operating/Facilities; Cedar Row → Auxiliary/Housing; thermal
plant → Plant.

## 2. Bill GL coding & account Type_Code

- Each Phase-1 `bill_charge_line` gets `BI_EXpAcctID` = the commodity's expense
  account; `BillingAccount.BA_DefExpAcctID` / `BA_DefApAcctID` set as fallback.
- Account `Type_Code` mix: most accounts **1 (AP)**; the campus electric +
  thermal accounts **3 (AP+GL)** (to exercise GL journal export); **one** Cedar
  Row account **0 (No Upload)** as the negative control (never exports).

## 3. AP/GL interface formats (produce one of each)

`ap_export_setup` rows → seven formats (builder procs supplied at load):

| setup name | format | structure |
| --- | --- | --- |
| `export_ap` | fixed-width .txt | single record/line (built-in) |
| `export_ap2` | .csv | fixed-width-in-CSV at bill grain (built-in) |
| `nl_ap_gludf` | fixed-width header+detail | GL-UDF coded (Sacramento-County style — region matches Northlake) |
| `nl_ap_voucher` | fixed-width C/H/L/D | PeopleSoft AP voucher |
| `nl_gl_journal` | fixed-width H/L | PeopleSoft GL journal, balanced debit/credit pairs |
| `nl_sap_fi` | comma-delimited | SAP FI document |
| `nl_ar_interface` | fixed-width | AR (tenant rebilling, Phase 4) |

Each `ExportSetup` registers a `SiEAppObjects` `EX` object (`export_ap`/`export_ap2`
exist; the rest are new). A run writes one `ExportFile` + `ExportLog` rows and
advances bill status to G/L Upload. `SysConstants 'UploadDirAP'` + `AP_EMAILER_TASK`
required.

## 4. Bill validation

`bill_validation_rule` thresholds per measure type (modes 1 Bill Save + 2 Batch):

| rule family | example threshold |
| --- | --- |
| cost change % | 35% with $1000 floor |
| cost max | $1,000,000 |
| usage change % | 40% |
| usage floor | kWh 1000 / gas-water 100 |
| period length | 26–36 days |
| missing field / inactive account | presence checks |

Fixtures: bills that **pass**; bills that **trip** each family (a cost spike, a
short period, a usage zero); ≥1 **open `bill_validation_result` alert on an
unapproved bill that blocks AP export**; a `BillScenario 'Weather Normalized'`
for the two weather-normalized rules. Lights up `rp_BillValidation` (failures) +
`rp_BillValidationStatus` (config matrix).

## 5. Accruals

- Set `SysConstants 'MPA Accruals'.Value_I = 2300`, `'MPA Reversals'.Value_I = 2301`;
  ensure commodities 2300/2301 exist.
- **Open accrual:** a Valley Electric account whose current period has no actual
  bill yet, with a manual bill carrying a 2300 line (no `Accrual_Bill` row) →
  appears in `rp_OpenAccruals @Reverse=0`.
- **Trued-up pair:** run `@Reverse=1` (or seed the +/− pair + `Accrual_Bill` link)
  so accrual(+) and reversal(−) net to zero when the actual arrives.

## expectedAssertions

- `gl_coding_present` — every AP-eligible bill line resolves a GL account + UD
  segments; `rp_GLAccountUDV` returns the 5-segment grid.
- `type_code_gating` — the `Type_Code=0` account never appears in an export;
  `Type_Code` 1/3 accounts do.
- `one_file_per_format` — running each `ap_export_setup` produces one `ExportFile`
  traceable to its bills; the GL journal balances (Σ debits = Σ credits).
- `export_blocked_by_alert` — the bill with an open validation alert is excluded
  from approval/upload.
- `validation_pass_and_fail` — `rp_BillValidation` shows the deliberate failures;
  clean bills pass to Status 2.
- `open_accrual_then_reversal` — `rp_OpenAccruals` lists the open accrual; after
  reversal the pair nets to 0.
