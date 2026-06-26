# Product Gap-Closure Backlog

The UI entry-path review ([entry-path-and-gaps.md](entry-path-and-gaps.md)) found
places where EEMSuite supports a capability but has **no UI/data path to create
the data**. Per owner decision (2026-06-26), we **close these gaps** rather than
defer them — so the dream customer truly exercises everything via the UI. That
makes this a **product backlog for the `energyhippo/EEMSuite` repo** (a sibling
repo); this doc specifies each item with the build location the code sweeps found.

> **Cross-repo:** these features are built in `C:\Hippo\Git\univerus\energyhippo\EEMSuite`
> (and its `Database\EEMSuite`), not in this synthetic-customer repo. Once built,
> the corresponding synthetic data becomes UI-enterable and moves into the
> materialize phase here.

Effort: **S** ≈ hours–1 day · **M** ≈ a few days · **L** ≈ 1–2+ weeks.

## How to use this document

This is the **canonical, standalone reference** for the EEMSuite product features
to build/connect so the synthetic customer can exercise everything through the UI.
Each item below is self-contained — actionable cold in a future session (including
one opened directly in the `energyhippo/EEMSuite` repo). When you pick one up:
update its row in the **status tracker**, open the cited files, and implement.
Discovered while building the Northlake dream customer; these are genuine product
gaps, useful beyond this dataset.

## Status tracker

| # | Item | Type | Effort | Status |
| --- | --- | --- | --- | --- |
| 1 | Connect ENERGY STAR PM (sandbox) | external/ops | S–M | Not started |
| 2 | AP/GL export builder procs (richer ERP formats) | dev (procs) | M–L | Not started |
| 3 | GL user-defined-fields view | missed-screen | S | Not started |
| 4 | Accruals create/reverse feature | needs-feature | L | Not started |
| 5 | Per-meter rate-class/option binding | needs-feature | M | Not started |
| 6 | Non-`Unique` rate classes | needs-feature | S–M | Not started |
| 7 | Benchmark definition UI | needs-feature | M | Not started |
| 8 | MFR external-email recipients | missed-screen | S | Not started |
| 9 | EnergyAI enrollment + connection | needs-feature + external | L | Not started |
| 10 | GreenButton (ESPI XML) import | re-enable/build | M–L | Not started |

(Detail for each item is in the matching numbered section below. The cited code
paths are the build locations the entry-path sweeps found; verify against current
code before implementing — the codebase moves.)

## Decisions applied

- **ENERGY STAR scores** → connect a **sandbox/real Portfolio Manager account** + run the sync task (B1).
- **AP export formats** → **commission dev** for the richer ERP builder procs (A1).
- **All other gaps** → **build the features** (A2–A8, B2).

---

## 1. Connect ENERGY STAR Portfolio Manager (B1)  — config/ops, effort S–M

**Goal:** populate `ESResponseFacility` scores so Rating History/Comparison,
RequestLog, and PerformanceSnapshot's ES score work.
**Not product dev** — integration/ops:
1. Obtain an ENERGY STAR PM **sandbox** account + register the test properties
   (the `#/ESPropertySetup` data already maps them; PMPropertyID is 0 until linked).
2. Set the `CustomerServer` (and PM credential) system constants so
   `#/ESNewRatingRequest` submits and the **EnergyStar sync task** can call PM.
3. Run `EEMSuite.Tasks.EnergyStar` (`RatingSyncService`) to pull `score` metrics →
   `SaveResponseAsync` writes `ESResponseFacility`.
**Unblocks:** Phase 5 ENERGY STAR rating reports.
**Note:** scores then reflect PM's model on the synthetic usage — document them as
PM-derived, not hand-set.

## 2. AP/GL export builder procs — richer ERP formats (A1)  — effort M (per format), L (all)

**Goal:** more than the 2 built-in formats are runnable from the AP Approval &
Upload screen.
**Build (Database repo, `CustomDevelopment\Northlake\` pattern):** author the
`*_UploadFile_Get` / `*_BillsForApproval_Get` builder procs + register each via an
`ExportSetup`/`Exports_Get` row and a `SiEAppObjects` `EX` object. Layouts are
already specified in [phase3](phase3-ap-gl-validation-spec.md) (from the AP code
sweep):
- `nl_ap_gludf` — fixed-width header+detail with GL-UDF segments (Sacramento style)
- `nl_ap_voucher` — PeopleSoft AP voucher (C/H/L/D records)
- `nl_gl_journal` — PeopleSoft GL journal (H/L, balanced debit/credit)
- `nl_sap_fi` — SAP FI comma-delimited
- `nl_ar_interface` — AR interface (tenant rebilling)
**Depends on:** GL-UDF data (item 3) for the GL-coded formats.
**Unblocks:** Phase 3 "one file of each format"; AccountsPayableDetail depth.
**No format-builder UI is built** (out of scope) — formats remain dev-authored;
this is the accepted model.

## 3. GL user-defined-fields view (A3)  — effort S (missed-screen)

**Goal:** enter the 5 GL segments (Fund/Dept/Program/Activity/Object) + values.
**Build (DBAdmin WPF):** wire a XAML view to the existing
`Models/Companies/GLUserDefinedModel.cs` + `GLAccountUDFValueModel.cs` and the
existing API (`GLAccountsDTOController.SaveGLAccountFieldAsync` /
`SaveGLAccountFieldValueAsync`). Backend already complete — just the view.
**Unblocks:** `rp_GLAccountUDV`; GL-coded export segments (item 2).

## 4. Accruals create/reverse feature (A2)  — effort L (needs-feature)

**Goal:** create an accrual and reverse it through the UI.
**Build (Domain + Data + Web API + frontend):** a service + endpoints + screen to
(a) create an accrual bill tagged commodity 2300, (b) call the existing
`rp_OpenAccruals @Reverse` to produce the 2301 reversal + `BillAccrualMap` pairing.
Today no UI/API/service exists; the proc does.
**Unblocks:** OpenAccruals/accruals/mpaaccruals (Phase 3 + Phase 4 tenant accruals).

## 5. Per-meter rate-class / option binding (A4)  — effort M (needs-feature)

**Goal:** bind a meter to a specific rate class **option** (voltage/phase/
tax-exempt/farm).
**Build (Rate/TenantRebill UI + model):** add `RateClassId`/`RateClassOptionId` to
the meter↔rate assignment (`UtilityRateConfig` → `UtilityMeterRates`) and expose a
picker in `TenantRebillView`; ensure the engine honors the bound option (today it
applies class defaults).
**Unblocks:** Phase 2 schedule #9; `rp_RateClassAssignment` depth.

## 6. Non-`Unique` rate classes (A5)  — effort S–M (needs-feature)

**Goal:** create the always-applied "All" class (for tax/min-bill scoping).
**Build (Rate Modeler):** allow selecting `RateClassType` on create (today
hardcoded to `Unique` in `RateModelerAddItemDrawerViewModel`); verify engine
handling of the "All" class.
**Unblocks:** cleaner Phase 2 tax/min-bill scoping.

## 7. Benchmark definition UI (A6)  — effort M (needs-feature)

**Goal:** define benchmarks/EUI targets (today benchmark UI is read-only).
**Build (Web):** a create/edit screen over `wh_Benchmark` (+ EUI/target/baseline
fields) and a save endpoint (`BenchmarkController` is GET-only today).
**Unblocks:** Phase 5 custom benchmarks; BenchmarkRanking definitions.

## 8. MFR external-email recipients (A7)  — effort S (missed-screen)

**Goal:** add ad-hoc external email recipients to an MFR delivery.
**Build (Web MFR delivery picker):** expose the already-modeled `Recipient.Email`
field in `MFRDelivery` UI (domain supports it; picker only offers users/groups).
**Unblocks:** Phase 6 external delivery. (100+ recipients already work via groups.)

## 9. EnergyAI enrollment + connection (B2)  — effort L (needs-feature + external)

**Goal:** produce `EnergyAI_Insights` for the report.
**Build + connect:** (a) an **enrollment UI** over `EnergyAI_Loads`/`_WeatherSites`/
`_TuningPeriod`/`_BaselinePeriod` (today DB-only, no screen); (b) connect the
external EnergyAI service + run `EEMSuite.Tasks.EnergyAIClient` (upload → download).
**Unblocks:** Phase 6 `rp_EnergyAIInsights`. Lowest priority.

## 10. GreenButton (ESPI XML) import (A8)  — effort M–L (re-enable/build)

**Goal:** ingest GreenButton interval XML.
**Build:** re-enable the legacy GreenButton upload path (tasks marked
`TargetKind: Skip` in workers; read-only API only today) or build a small import
UI/task over the existing `GreenButtonConverterService`.
**Unblocks:** Phase 6 GreenButton intake. Optional/low priority.

---

## Suggested build order

1. **GL-UDF view (3, S)** + **MFR external-email (8, S)** — quick missed-screens.
2. **AP builder procs (2, M)** + **ENERGY STAR sandbox connect (1, S–M)** — high report value.
3. **Per-meter rate option (5) + non-Unique class (6)** — completes the rate story.
4. **Benchmark UI (7)** — analytics.
5. **Accruals (4, L)** — larger feature.
6. **EnergyAI (9, L)** + **GreenButton (10)** — lowest priority / optional.

## What this does NOT change

Everything classified UI-DIRECT / UI-THEN-RUN / DATA-PATH / SYSTEM-GENERATED in
the register is unaffected and proceeds to materialize as planned. This backlog
only covers the gap items.
