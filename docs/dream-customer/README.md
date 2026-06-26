# Northlake: The Dream Synthetic Customer

> **Goal (north star).** Turn Northlake into a complete, deterministic synthetic
> customer that exercises **every part of EEMSuite** — every report, every rate
> construct, the full AP/GL financial interface, tenant rebilling with every
> allocation and reconciliation method, GHG, ENERGY STAR, baselines/regression,
> projects, alarms, tasks/workflows, importers, and scheduled report delivery to
> 100+ users — so that loading Northlake into a blank EEMSuite seed proves the
> product end to end and produces known, repeatable expected results.

This folder is the plan for that goal. It is grounded in a full sweep of the
production code at `energyhippo/EEMSuite`, the live `EEMSuite` database, and the
current synthetic dataset in this repo (see the dated discovery in the session
that created these docs).

| Doc | What it is |
| --- | --- |
| `README.md` (this file) | Goal, current state, coverage scorecard, roadmap summary, open decisions |
| [`subsystem-gap-analysis.md`](subsystem-gap-analysis.md) | Per-subsystem: what EEMSuite supports, what Northlake has, the gap, what to add |
| [`report-coverage-matrix.md`](report-coverage-matrix.md) | All 115 EEMSuite reports → data bucket → covered/partial/missing → phase |
| [`roadmap.md`](roadmap.md) | Phased plan with deliverables and acceptance criteria |
| [`bill-charge-line-spec.md`](bill-charge-line-spec.md) | Phase 1: how each provider's bills decompose into reconciling charge lines (→ EEMSuite `BillItem`) |
| [`phase1-substrate-extras.md`](phase1-substrate-extras.md) | Phase 1: bill status history, digital/status points, notes & images |
| [`phase-0-1-assertions.md`](phase-0-1-assertions.md) | Phase 0/1 known-value regression checklist (verify once loaded) |
| [`phase2-rate-engine-spec.md`](phase2-rate-engine-spec.md) | Phase 2: 10 rate schedules firing all 9 determinant kinds |
| [`phase3-ap-gl-validation-spec.md`](phase3-ap-gl-validation-spec.md) | Phase 3: GL coding, 7 AP/GL/AR export formats, validation, accruals |
| [`phase4-tenant-rebilling-spec.md`](phase4-tenant-rebilling-spec.md) | Phase 4: Town Center + sub-metered Cedar Row; every allocation/WUI/reconciliation path |
| [`phase5-sustainability-analytics-spec.md`](phase5-sustainability-analytics-spec.md) | Phase 5: GHG, ENERGY STAR ratings, weather regression, benchmarks |
| [`phase6-operations-engagement-spec.md`](phase6-operations-engagement-spec.md) | Phase 6: projects, alarms, audit, tasks/workflows, MFR delivery to 100+, EnergyAI, HMR, importers |
| [`entry-path-and-gaps.md`](entry-path-and-gaps.md) | **How each thing is created via the EEM UI** (not DB), and the register of UI gaps + decisions |
| [`product-gap-backlog.md`](product-gap-backlog.md) | EEMSuite **product features to build/connect** to close the UI gaps (cross-repo work) |

## Design principles

1. **Coverage is the product.** A subsystem is "done" only when a real EEMSuite
   report or output renders non-empty from Northlake data with a *known expected
   value* we can assert against.
2. **Speak the customer's language, not EEM's.** Source data and customer-facing
   artifacts use real facilities/utility vocabulary (a university, a town center,
   a housing community). EEM-specific jargon is confined to the `eem/` setup
   translation layer. (Per the project owner: "it should fit what it does.")
3. **Deterministic & synthetic.** Same commit + seed ⇒ same customer. Identities
   are fictional; only public context (weather stations, geography, utility
   territory shapes) is reused.
4. **New themed customers are allowed** where a subsystem needs a different
   shape than a campus. A mixed-use **Northlake Town Center** (retail + office +
   residential tower) is the natural vehicle for tenant rebilling; a larger
   multi-company **Northlake Portfolio** is the vehicle for security/permission
   scale and 100+ user report delivery.
5. **Model first, generate second.** Grow the synthetic *source model* to the
   detail each subsystem needs (charge lines, rate determinants, allocation
   configs, GL coding) and generate EEMSuite-ready artifacts from it, rather than
   hand-seeding the EEMSuite tables. This preserves determinism and traceability.
6. **Created through the UI, not the database.** The end state can be stated as
   "this is what must exist," but it must be reachable by **entering data through
   the EEM UI** (or a UI-driving system), or via a legitimate product data path
   (file/ODBC/handheld gateway, bill importer, external integration), or as a
   side effect of using the app. Direct DB seeding of customer data is off-limits.
   Where the UI can't create something the product supports, that is a **finding**
   — a missed screen or a feature to add. See
   [`entry-path-and-gaps.md`](entry-path-and-gaps.md) for the per-subsystem entry
   paths and the gap register.

## The scale of the target

- **115 reports** across 18 functional modules. **92 are MFR-deliverable**
  (can be scheduled/emailed). **94 are data-backed**; 21 are config/editor
  screens.
- The reports collapse to **~28 data-capability buckets**. Everything rests on a
  **substrate** every report needs: a populated hierarchy (`MetaWorld`), security
  (users permissioned to nodes), units/measure-types, a fiscal calendar, and
  meters tied to billing accounts. *Without the substrate loaded, every report
  is empty regardless of how rich the rest of the data is.*
- EEMSuite supports **37 measure types**, **9 rate-determinant math kinds**,
  **7 bill-allocation methods + 3 point-allocation methods**, **7+ AP/GL export
  file formats**, and **6 task types**. Northlake today touches a fraction of each.

## Where Northlake stands today (current state)

The current dataset (`scenarios/demo-university-v1.yaml` + `providers/` +
`security/` + `eem/`) is a strong **Stage-1 design**: 2 sites / 6 buildings,
5 providers, 25 accounts, ~38 meters, ~65 channels, 13 gateways, 9 rate
schedules (as metadata), 3 EEM companies, 19 users, 27 groups, 4 aggregates,
3 baseline shells, 2 weather stations, and 19 scenario events. It is excellent
for **ingestion, gateways, interval/bill data, and ENERGY STAR property
mapping**.

It is **not yet** a loaded, report-exercising customer: there is no built
generate→load pipeline populating an EEMSuite DB, and entire subsystems
(tenant rebilling, AP/GL, GHG, rating responses, regression results, projects,
alarms, audit, MFR delivery, EnergyAI) have **no data at all**.

## Coverage scorecard

Status = how close the *current Northlake data design* is to exercising the
subsystem's reports/outputs. (Detail and "what to add" in
[`subsystem-gap-analysis.md`](subsystem-gap-analysis.md).)

| Subsystem | EEMSuite reports/outputs | Status |
| --- | --- | --- |
| Hierarchy / security / units substrate | (all reports depend on it) | 🟡 Designed, not loaded |
| Monthly bills + charges | Bill Processing/Tracking (~20) | 🟡 Bills modeled; **no charge-line breakdown** |
| Interval / time-series use | Use Analysis (15) | 🟢 Strong (electric, solar, CHW) |
| Aggregates & peak/demand | AggregateDemand, AggregatePeakLoad | 🟢 4 aggregates defined |
| Rate engine | Rate Analysis (9) | 🟡 TOU/tiered/seasonal/PPA only; **missing RTP, stepped, max-bill, ratchet, load-factor, %-riders, taxes, min-bill, class options, scripts, multi-currency** |
| AP / GL / financial interface | AP Detail, AP Approval/Upload, GLAccountUDV | 🔴 **Missing** (no GL accounts, no UDF coding, no export formats/runs) |
| Tenant rebilling & allocation | Tenant Rebilling (14) | 🔴 **Missing** (no multi-tenant property, no allocation/WUI configs, no generated bills, no reconciliation) |
| Accruals (open / MPA) | OpenAccruals, accruals, mpaaccruals | 🔴 Missing |
| Bill validation | BillValidation, BillValidationStatus | 🔴 Missing (deferred in Stage 1) |
| GHG / emissions | GHG History/Variance/Audit (3) | 🔴 Missing (factors named in providers, **not configured**) |
| ENERGY STAR ratings | RatingComparison/History/RequestLog (3) | 🟡 Property mapping done; **no rating responses/scores** |
| Weather regression / normalization | WeatherRegression, RegressionSummary | 🟡 HDD/CDD + baseline shells; **no stored regression results** |
| Benchmarks / EUI | BenchmarkRanking, MonthlyEUI, PerformanceSnapshot | 🟡 Have floor areas; **no peer set / EUI config** |
| Project tracking | Project Detail/Summary/Finance (4) | 🔴 Missing |
| Alarms | AlarmDataMap | 🔴 Missing |
| Audit / activity logs | Audit, ActivityTracker | 🔴 Missing |
| Tasks / job scheduler / workflows | TaskLog, GatewayStatus, job_scheduler | 🟡 Gateways designed; **no task run history / workflows** |
| MFR saved reports & delivery | (92 deliverable reports) | 🔴 Missing (no saved reports, dashboards, deliveries, recipients) |
| Importers (Bill Importer, GreenButton, MyUpload/MyImport) | bill_importer, my_imports, my_exports | 🟡 Handheld/gateway files designed; **no bill-importer/GreenButton/upload configs** |
| HMR (handheld) | HMRConfiguration, hmr_export | 🟡 Upload files designed; **HMR meter/route config TBD** |
| EnergyAI | EnergyAIInsights | 🔴 Missing |
| Commodities / unique units | (cross-cutting) | 🟢 Good (unique units present: ton-hours, klb, ERU) — can extend |

🟢 covered/strong · 🟡 partial · 🔴 missing

## Roadmap at a glance

Detail + acceptance criteria in [`roadmap.md`](roadmap.md).

> **Status (2026-06-26):** all phase specs (0–6) are authored **and re-framed for
> UI entry** ([entry-path-and-gaps.md](entry-path-and-gaps.md)), and **all Track A
> phases are materialized** as UI-entry plans in `eem/` (`northlake-rates-v1`,
> `-bill-entry-v1`, `-ap-gl-v1`, `-town-center-v1`, `-sustainability-v1`,
> `-operations-v1`, plus the Phase 0 `-company-calendar-v1` / `-eem-permissions-v1`).
> Each names the screen, the values, and flags any **Track B** gap. Remaining work:
> (1) enter the Track A plans into a full EEM instance + run the assertions; (2) the
> **Track B product features** in [product-gap-backlog.md](product-gap-backlog.md)
> (owner chose to build/connect all of them). The synthetic-data design side is
> complete.

| Phase | Theme | Unlocks |
| --- | --- | --- |
| **0** | **Foundation & load pipeline** | Substrate loads into a blank EEMSuite seed; substrate reports return data |
| **1** | **Consumption & cost core** (bills w/ charge lines, intervals, units) | Use Analysis (15) + Bill Processing/Tracking core |
| **2** | **Rate engine completeness** (10 schedules → all 9 determinant kinds) | Rate Analysis (9) |
| **3** | **AP / GL & financial interface** (GL coding, 7 export formats, validation, accruals) | AP + accrual + validation reports; real AP interface files |
| **4** | **Tenant rebilling** (mixed-use property; all allocation + WUI + reconciliation) | Tenant Rebilling (14) |
| **5** | **Sustainability & analytics** (GHG, ENERGY STAR ratings, regression, benchmarks) | GHG (3) + ES Rating (3) + regression + benchmark |
| **6** | **Operations & engagement** (projects, alarms, audit, tasks, MFR delivery to 100+, EnergyAI, importers) | Remaining System Manager / Project / My Reports + scheduled delivery |

## Decisions (resolved 2026-06-25)

1. **Sequencing.** ✅ Start with **Foundation (0) + Consumption & cost core (1)**.
   Subsystem order after that to be picked when we get there.
2. **Output approach.** ✅ **Specs / manifests only** — this repo authors the data
   *designs* (YAML/markdown specs in the repo style, EEMSuite-aware). Loading into
   EEMSuite is handled externally by the owner's tooling. *No generate→load
   pipeline is built here.* "Status: not loaded" in the scorecard means the spec is
   authored and ready to load, not that a loader exists.
3. **Tenant-rebilling vehicle.** ✅ **Both** — a new mixed-use **Northlake Town
   Center** (commercial allocation) *and* sub-metered **Cedar Row** (residential
   allocation). Built in Phase 4.

### Still open (decide when the phase arrives)

- **Scale targets.** How many companies/users for permission + 100+ MFR delivery
  testing (Phase 6). Default plan: one portfolio company with ~120 users reached
  via group recipients, plus a few individual/external recipients.
- **Unsupported rate constructs.** Default: document power factor, coincident
  peak/4-CP, CPP events, and net-metering banking as *synthetic stand-ins* (the
  engine can't model them natively).
