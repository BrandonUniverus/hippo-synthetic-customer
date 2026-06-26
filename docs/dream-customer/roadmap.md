# Roadmap

Phased plan to make Northlake the dream synthetic customer. Each phase lists the
**deliverables** (what we add to the source model + generated artifacts) and the
**acceptance criteria** (the EEMSuite reports/outputs that must render non-empty
with a *known expected value*).

Phases are dependency-ordered. Within a phase, work is independent and can be
parallelized. Phase 0 is a hard prerequisite for everything.

---

## Phase 0 — Foundation specs  *(enabling)*

**Why first.** Every report rests on a loaded substrate (hierarchy + permissioned
users + units + fiscal calendar + meters↔accounts). Per the owner's output
decision, this repo authors the *specs* for that substrate; loading into EEMSuite
is handled externally. So Phase 0 is "complete the foundation specs," not "build a
loader."

**Deliverables (specs / manifests)**
- Source-model extensions (`schemas/synthetic-source-model.md`) for the substrate
  gaps: bill **charge lines**, **company calendar**, **concrete permission grants**,
  **digital/status points**, **notes/images**.
- A concrete permission-grant spec mapping the 16 semantic permission profiles to
  real EEMSuite `Permissions_TBL` types (`$/A/D/EX/F/MI/MU/TS`) + `SiEAppObjects` +
  `AccessLevel`, including node-scoped `D` grants and an AccessLevel-3 approver vs.
  an AccessLevel-1 viewer.
- A 2024–2025 monthly `CompanyCalendar` spec per company, with 1–2 months
  deliberately omitted for the import-rejection scenario.

**Acceptance (verified once the owner loads the specs)**
- Substrate reports render: `rp_BuildingList`, `rp_PointsList`,
  `rp_HierarchyDetailsEditor`, `rp_IndexList`, and the config screens.
- A non-admin user sees only their permitted nodes; an AccessLevel-1 user cannot
  perform an AccessLevel-3 action.

---

## Phase 1 — Consumption & cost core

**Goal.** Light up everything that runs on bills + intervals + units — the bulk
of day-to-day reporting.

**Deliverables**
- Extend the `bill` model with **charge-line items** (`BillItem`: commodity,
  quantity, unit, amount, GL placeholder) so bills decompose into energy/demand/
  fixed/tax components, routed into the "Actual" `BillScenario`.
- Ensure ≥13 consecutive monthly bills per account; populate `StatusHistory`
  (entry dates, ≥2 distinct entry users) so late/daily-processing logic works.
- Load the existing interval/aggregate data; add a few **digital/status points**
  (chiller enable, occupancy) for `DigitalSummary`.
- Add notes + a couple of images on meters/bills for `NoteHistory`/`ImageManagement`.

**Acceptance**
- All 15 Use Analysis reports render with known totals (interval count, peak
  demand, EUI).
- Bill Processing/Tracking core renders: AccountDetail/Summary/History,
  BillHistory, BillVariance(+Analysis/Detail/Ranking), CostBreakOut,
  FacilityAccountDetail, FiscalPeriodBills, LateBills, DailyProcessingSummary,
  BillDataGaps, MonthlyUtilityDistribution.
- Known expected rollups by customer/site/building/provider/account/meter.

---

## Phase 2 — Rate engine completeness

**Goal.** Exercise all **9 determinant math kinds** and every rate construct.

**Deliverables.** Grow the rate model to determinants/blocks/schedules and author
~10 rate schedules, assigned to meters (`UtilityMeterRates`) over ≥13 months:

1. **Residential inclining-block** (Cedar Row) — tiered energy (200), fixed (400),
   minimum bill (500), state + municipal taxes (800).
2. **Commercial TOU + seasonal demand** (campus, flagship) — On/Off-peak energy,
   summer/winter demand, **holiday calendar**, a % rider (700) + per-unit rider
   (200), taxes (800).
3. **Large-demand ratchet** (Science Center / chiller) — ratchet demand + load
   factor; needs a strong summer peak so the winter floor binds.
4. **Base/excess contract demand** — two-part demand with pre/post **determinant
   scripts**.
5. **RTP / index** — type **100** referencing an hourly **price-signal point**
   (the only way to fire RTP), plus a price-range-capped variant.
6. **Stepped + max-bill** — types **210** and **600** (both unexercised anywhere).
7. **Gas with monthly fuel adjustment** — fixed-by-day (300), volumetric energy
   with **unit conversion**, monthly effective-dated fuel-adjustment blocks.
8. **Multi-commodity** water/sewer/CHW/steam — multiple measure types + unusual
   units (tons, klb) + `UtilityCommodityMap` for component mapping.
9. **Rate-class options** — voltage/phase/tax-exempt/farm selectable classes.
10. **Multi-currency** (optional) — a C$/£ rate against a US$ reporting profile.

Document **unsupported constructs** (power factor, coincident-peak/4-CP, CPP,
net-metering banking) as explicit synthetic stand-ins.

**Acceptance**
- All 9 Rate Analysis reports render; `rp_RateComparison` shadow-bills; every
  `UtilityRates_Run_NNN` proc fires at least once; RTP/stepped/max-bill/ratchet
  each have a verifying scenario with a known computed total.

---

## Phase 3 — AP / GL & financial interface

**Goal.** "Do actual billing" end to end and **produce real AP interface files.**

**Deliverables**
- A chart of GL expense/AP accounts per company + the 5 user-defined GL segments
  (`GLAccountUDField/Value`) with realistic + partly-blank coverage.
- GL-code the bill lines (`BillItem.BI_EXpAcctID`) and account defaults; set
  account `Type_Code` mix (1 AP / 2 GL / 3 both / 0 no-upload negative control).
- `ExportSetup` rows + builder procs to **generate one file of each of the 7
  formats**: fixed-width AP (`export_ap`), CSV AP (`export_ap2`), GL-UDF
  header+detail (Sacramento County style), multi-record AP voucher + GL journal
  (PeopleSoft/Massport style), SAP FI CSV (Clark County style), AR interface.
- Bill validation thresholds + bills that pass and trip each rule family; ≥1 open
  alert that **blocks** AP export.
- Accruals: set the 2300/2301 commodities; one open accrual + one trued-up
  accrual↔reversal pair.

**Acceptance**
- `rp_AccountsPayableDetail`, `rp_APApprovalAndUpload`, `rp_GLAccountUDV`,
  `my_exports` render.
- One example file of **each** AP/GL/AR format generated and traceable to bills.
- `rp_BillValidation` / `rp_BillValidationStatus` show passes + failures;
  `rp_OpenAccruals` shows the open accrual and its reversal.

---

## Phase 4 — Tenant rebilling

**Goal.** Exercise **every** allocation + reconciliation path. Vehicle (owner
decision): **both** a new mixed-use **Northlake Town Center** (commercial
allocation) *and* sub-metered **Cedar Row** (residential allocation).

**Deliverables**
- A multi-tenant structure (anchor retail + in-line shops + office tower + food
  court + common area + a cost center) with the meters/sub-meters each method
  needs.
- A bill-allocation config per method: Fixed Amount & %, Fully Submetered,
  Partially Submetered, Building Areas, Coincident Demand, Metered Substations,
  and **Bill Aggregation** (children→cost center). Overhead in both combined and
  separate modes.
- WUI **point families**: Weighted Use Index + Measured Use, with deliberate
  fail-reason cases (no index, no area, partial data, broken chain, no rate); note
  the unimplemented "Percentage Based" method.
- Generated tenant bills under all 4 generation types; a reconciliation scenario
  (interval-source and bill-source) with a deliberate nonzero variance; tenant
  accruals.

**Acceptance**
- All 14 Tenant Rebilling reports + `rp_TenantMap` render.
- Each allocation method has a config that produces tenant bills summing back to
  the parent (penny-true-up); `rp_BillReconciliation` shows known over/under
  variance.

---

## Phase 5 — Sustainability & analytics

**Goal.** GHG, ENERGY STAR ratings, weather regression, benchmarks.

**Deliverables**
- **GHG**: emission factor source (eGRID region + EPA stationary combustion),
  factor members with effective dates, meter→category mapping (electric Scope 2,
  gas/steam Scope 1), per-company scope config.
- **ENERGY STAR ratings**: seed `ESResponseFacility` scores + request/log rows
  for the 8 mapped properties across several periods.
- **Weather regression**: produce/seed `FF_wnRegressionBestResults` for metered
  buildings from existing interval + weather data (realistic R²/CV-RMSE).
- **Benchmarks**: EUI + cost-intensity benchmark definitions over the building
  peer set.

**Acceptance**
- GHG History/Variance/Audit render with computed emissions; ES Rating
  Comparison/History/RequestLog render with scores; `rp_weatherregression` /
  `rp_RegressionSummaryReport2` render fitted models; `rp_BenchmarkRanking` /
  `rp_MonthlyEUI` / `rp_PerformanceSnapshot` rank the peer set.

---

## Phase 6 — Operations & engagement

**Goal.** The operational layer + scheduled delivery to **100+ users**.

**Deliverables**
- **Project tracking**: a portfolio (LED retrofit, chiller upgrade, solar
  expansion) with activities, financial events, and M&V linkage to baselines.
- **Alarms**: alarm-enabled points with raised/ack/resolved rows across the span.
- **Audit / activity**: enable audit; generate a user action + data-change trail.
- **Tasks / workflows**: schedules for gateways + bill import + delivery; a couple
  of multi-step workflows; `TaskLog` run history; `GatewayStatus` live feed.
- **MFR delivery**: a saved-report + dashboard library; delivery schedules whose
  group-based recipient lists resolve to **100+ users** (needs the scale
  decision), plus individual + external recipients; the delivery task.
- **EnergyAI**: pre-generated insight rows for a couple of load points.
- **HMR**: explicit meter/route/read-type config tied to the handheld uploads.
- **Importers**: bill-importer source + mappings + sample BIF/CSV/Excel (incl. the
  bad-data validation sample), a GreenButton ESPI XML feed, a MyUpload/MyImport
  template.

**Acceptance**
- Project, Alarm, Audit, ActivityTracker, TaskLog, GatewayStatus, EnergyAIInsights,
  HMRConfiguration, bill_importer, my_imports render.
- A scheduled MFR delivery fans out to 100+ recipients (verifiable via the
  delivery task log) across PDF/Excel.
- Every one of the 115 reports has at least one scenario that renders it non-empty.

---

## Cross-cutting: assertions

Per the project quality bar, each phase also adds **`expected_assertion`** entries
so downstream results are validated automatically (known totals, counts, variances,
file checksums), keeping the dream customer a *regression* asset, not just a demo.
