# Entry-Path & Gap Register

**The rule that governs this whole project:** the synthetic customer is created by
**entering data through the EEM UI** (by hand, or by a system that drives the UI),
**not** by inserting into the database. Data may only arrive off-UI through
**legitimate product paths** — file / ODBC / handheld gateways, the bill importer,
external integrations — or as **side effects of using the app** (audit, status,
logs). A blueprint is only useful if it can be produced this way. Where the UI
*can't* create something the product otherwise supports, that is a **finding**:
either we missed a screen, or the product needs a feature added.

This register re-frames every phase around *how each thing actually gets in*, and
lists the gaps. It is grounded in a sweep of the EEM apps + web frontend (WPF
DBAdmin, ConfigurationTool, BillImporter; the Angular/Kendo web SPA; the Tasks
engine).

## Instance assumption

We target a **fully-provisioned EEM instance** (all product stored procs, lookup
catalogs, and report-menu registrations present — i.e. a real install, not a
from-git build). Several capabilities the sweep flagged as "ships only in the
`.bak`, not in git" (the `BillAllocationMethod`/`PtAllocationMethod` catalogs, the
`FF_wn*` regression procs, the reconciliation report registration) are therefore
**present** for us. Installing the product's own SQL objects is *standing up
EEMSuite*, not seeding customer data — it does not violate the rule. The true
gaps below are where **no UI/data-path exists for the customer data even in a full
instance.**

## Entry-method legend

- **UI-DIRECT** — a screen where you type it in.
- **UI-THEN-RUN** — configure in the UI, then run a task/job/process that produces
  the result (the result is computed, not typed).
- **DATA-PATH** — enters via a real ingestion path (file/ODBC/handheld/bill import).
- **EXTERNAL** — comes from an outside service/API (ENERGY STAR PM, EnergyAI).
- **SYSTEM-GENERATED** — appears as a side effect of using the app (audit, status,
  notes, logs).
- **GAP** — the product supports the end state but there is no UI/data-path to
  create it: *missed-screen* (backend exists, view missing) or *needs-feature*
  (no path at all).

---

## What IS hand-enterable (the good news)

Most of the plan is straightforwardly UI-creatable in a full instance:

| Phase | UI-enterable via | 
| --- | --- |
| 0 Foundation | Companies/Users/Groups (WPF), Company Calendar (web `#/CompanyCalendar`), permissions; node hierarchy (WPF Nodes) |
| 1 Cost core | Bill Entry (`#/BillEntry`), Bill Validation rules (WPF `BillValidationView`), notes/status (system), digital points via point definitions; interval/bill data via **DATA-PATH** (gateways/import) |
| 2 Rates | **WPF Rate Modeler** creates providers, rates, classes, determinants of **all 9 types** (100–800; 210/600 confirmed present in the `UtilityDeterminantType` lookup), blocks/tiers, TOU/season/holiday schedules, ratchets, load factor, pre/post scripts, effective dates, commodity maps, multi-currency; **Rate Import** file for bulk. RTP determinant references a price point (point created in Nodes; price values via DATA-PATH). |
| 3 AP/GL | Bill entry/import (UI+DATA-PATH), GL accounts (WPF `GLAccountsView`), account AP/expense account assignment (WPF), AP approval + **run** an *existing* export format (`#/reporting/APApprovalAndUpload`) |
| 4 Tenant | Bill allocation config (web `#/reporting/BillAllocationConfiguration`), WUI master-point config (web), bill generation config (WPF `TenantRebillView`), meter-allocation **run** (`#/reporting/ProcessMeterAllocations`) |
| 5 Sustainability | Emission sources/factors(+history values)/meter-assignment/company-config (web `#/EmissionFactorSources`, `#/EmissionFactors`, `#/MeterEmissionFactorAssignment`, `#/GHGCompanyConfiguration`); ENERGY STAR property setup + rating request (web, **local**, no PM account); weather regression **run** (web Custom views) |
| 6 Operations | Project Tracking (web editor), alarm thresholds (WPF `PointAlarmDefinitionView`), Task scheduler (web `#/tasks/manager`), Workflow author (WPF ConfigurationTool), MFR save/dashboard/delivery incl. **groups for 100+ recipients**, Handheld config + export, MyUpload/MyImport; audit/status/notes (system-generated) |

---

## The gaps (where the UI can't do it)

Grouped by disposition. **Impact** = which reports/goals are affected.

### A. Needs a product feature (no UI path even in a full instance)

| # | Gap | Why | Impact | Recommended disposition |
| --- | --- | --- | --- | --- |
| A1 | **AP/GL export FORMAT definition** | No create/edit-format UI anywhere; formats are dev-authored procs (`rp_FinancialInterfaceUpload`-style) + `Exports_Get` rows (the `CustomDevelopment\<customer>` model). Only **running** an existing format is UI. | Phase 3 "7 formats." Only the 2 built-ins (`export_ap`, `export_ap2`) are usable by hand. | Use the 2 built-ins for the synthetic customer; treat new formats as **dev work** (or a candidate product feature: a format-builder UI). Flag, don't fake. |
| A2 | **Accruals (create + reverse)** | No UI/API/service writes `Accrual_Bill`/`BillAccrualMap`; the `rp_OpenAccruals @Reverse` proc isn't wired to any screen. | Phase 3 accruals; Phase 4 tenant accruals; OpenAccruals/accruals/mpaaccruals reports. | **Needs-feature.** Cannot be hand-entered. Either commission an accrual-entry UI, or accept these reports stay empty. Decision needed. |
| A3 | **GL user-defined fields (5 segments) + values** | Domain model + API + WPF MVVM models exist, but **no XAML view is wired**. | Phase 3 GL UDV coding; `rp_GLAccountUDV`; GL-coded export segments. | **Missed-screen** — closest to "finish the view." Small dev. Until then, GL coding is base account only. |
| A4 | **Per-meter rate-class / rate-class-OPTION binding** | The meter↔rate assignment (`TenantRebillView`→`UtilityMeterRates`) has only RateId + dates; no RateClassId/OptionId field. | Phase 2 #9 (voltage/phase/tax-exempt/farm per meter); `rp_RateClassAssignment` depth. | **Needs-feature.** Options can be *defined* on a rate but not *bound* to a meter via UI (engine applies defaults). Model the rate with options; note the binding gap. |
| A5 | **Non-`Unique` rate classes** (e.g. the always-applied "All" class) | `RateClassType` hardcoded to `Unique` on create. | Phase 2 tax/min-bill scoping that relies on an "All" class. | **Needs-feature** (these are system-seeded classes). Use member-scoping where possible; flag. |
| A6 | **Benchmark definitions / EUI targets** | Benchmark UI is read-only end-to-end; no create screen. | Phase 5 benchmarks; `rp_BenchmarkRanking` custom defs. | **Needs-feature** or rely on built-in benchmark master data. Decision needed. |
| A7 | **MFR delivery external-email recipients** | Domain `Recipient` supports email, but the web picker exposes only users + groups. | Phase 6 external recipients. | **Missed-screen.** Reach 100+ via **groups** (fully supported); external email needs the field added. |
| A8 | **GreenButton (ESPI XML) import** | Read-only API only; legacy upload tasks skipped in 7.0; no import UI. | Phase 6 GreenButton intake. | **Out-of-scope / needs-feature.** Drop GreenButton from the synthetic scope, or flag for re-enable. |

### B. External dependency (legitimate, but needs an outside service)

| # | Item | Why | Impact | Disposition |
| --- | --- | --- | --- | --- |
| B1 | **ENERGY STAR scores** (`ESResponseFacility`) | Property setup + rating request are local UI, but **scores only arrive from the Portfolio Manager API** via the EnergyStar sync task. No hand-entry. | Phase 5 RatingHistory/Comparison/RequestLog score columns; PerformanceSnapshot ES score. | **Decision needed:** (i) connect a **real/sandbox PM account** + run the sync task (the legitimate path), (ii) accept ES *score* reports stay empty (property/request data still demos), or (iii) request a manual-score-entry feature. |
| B2 | **EnergyAI insights** | Only from the external EnergyAI cloud service (enroll → run → download). Even enrollment is DB-only (no UI). | Phase 6 `rp_EnergyAIInsights`. | **Decision needed:** connect the EnergyAI service, or accept this report stays empty. Lowest priority. |

### C. UI-THEN-RUN — produced by running the product (legit; requires the engine/jobs running)

These are *not* gaps — the data is computed by running EEM, which is exactly how a
real customer gets it. They require the **Tasks EngineWorker / SQL Agent jobs** to
be running in the target instance.

| Item | Configure in UI | Produced by |
| --- | --- | --- |
| Tenant bill **generation** | gen type/schedule (WPF `TenantRebillView`) + allocation config (web) | SQL Agent job `Job_BillAllocation` (no on-demand "Generate Bills" button — meter-allocation has one; full bill-gen is scheduled) |
| Alarm **events** | thresholds (WPF `PointAlarmDefinitionView`) + load point data | the alarm evaluation/notification task raises rows |
| Weather **regression** results | period/config (web Custom views) | running the `FF_wn*` regression proc |
| **AP interface files** | approve bills, pick existing format | running AP Upload (writes `ExportFile`) |
| **Task logs / gateway status** | create schedules / run-now (web `#/tasks/manager`) | the EngineWorker executing tasks → `WorkflowRun`/`TaskQuickRun` |

### D. DATA-PATH — via real ingestion (legit, the intended path)

Interval & meter data (gateways: AcquiSuite/MV90/BACnet/Modbus/ODBC/NOAA/Aeris/
Spinwave/FIG/Neptune/MVRS/Fake), monthly bills (Bill Importer BIF/CSV/Excel),
handheld routes (Neptune/MVRS upload → HMR), and the **RTP hourly price point's
values**. These are already the backbone of the existing dataset.

### E. SYSTEM-GENERATED — free by using the app

Audit, activity, status history, notes, workflow audit — populated by performing
the actions in the UI (bill entry/approval, edits, report runs, logins, including
the disabled-user failed-auth and cross-company auditor cases). On by default.

---

## Decisions (resolved 2026-06-26) — close the gaps

The owner chose to **close** the gaps rather than defer them, so the dream customer
exercises everything:

1. **ENERGY STAR scores (B1):** ✅ **connect a sandbox/real PM account** + run the
   sync task (the only legitimate way to populate scores).
2. **AP export formats (A1):** ✅ **commission dev** for the richer ERP builder
   procs (PeopleSoft AP voucher + GL journal, SAP FI, GL-UDF, AR).
3. **All other gaps (A2–A8, B2):** ✅ **build the features** (accruals, per-meter
   rate options, non-Unique class, benchmarks, GL-UDF view, MFR external email,
   EnergyAI, GreenButton).

These become a **product backlog for the EEMSuite repo** — specified with build
locations and effort in [`product-gap-backlog.md`](product-gap-backlog.md). The
classification still holds (A3/A7 missed-screens; A1/A2/A4/A5/A6/A8 needs-feature;
B1/B2 external) — it now drives *what to build/connect*, not *whether*. Everything
not in the gap list is hand-enterable (UI-DIRECT) or legitimately produced (RUN /
DATA-PATH / SYSTEM-GENERATED) and proceeds to materialize.
