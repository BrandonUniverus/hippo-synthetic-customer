# Subsystem Gap Analysis

For each EEMSuite subsystem: **what the product supports**, **what Northlake has
today**, **the gap**, and **what to add**. Grounded in `energyhippo/EEMSuite`
code, the live `EEMSuite` DB, and the current dataset in this repo.

Legend: 🟢 covered · 🟡 partial · 🔴 missing.

---

## 0. Foundation: hierarchy, security, units, calendar  🟡

**What EEMSuite needs.** Almost every one of the 94 data-backed reports starts
from a spine: the org tree (`MetaWorld_TBL` / `MetaLevel_TBL`), security
(`ValidUser`, `Users_Tbl`, `UserGroup*`, `MetaWorldPermissions_TBL`,
`Permissions_TBL`, `SiEAppObjects`), units (`Unit`, `UnitProfile`, `MeasureType`,
`UnitConversion`), a fiscal calendar (`CompanyCalendar`), and meters tied to
billing accounts (`Meter`, `BillingAccount_Tbl`, `UtilityProvider`). **If the
substrate is not loaded with a permissioned user, every report returns empty.**

Permission model: access is gated three ways — (a) **which hierarchy nodes** a
user sees (`MetaWorldPermissions_TBL`, type `D` Points permissions, recursive
down the tree), (b) **which screens/reports** (`SiEAppObjects` + `Permissions_TBL`
types `$/A/D/EX/F/MI/MU/TS`), and (c) **authority level** (`AccessLevel` 1 read /
2 edit / 3 approve — e.g. bill QC approval requires ≥3).

**Northlake today.** Strong *design*: 3 EEM companies, hierarchy levels per
company, 19 users, 27 groups, 16 permission profiles, disabled-user case. Units
include the unusual ones (ton-hours, klb, ERU). All in YAML, **not loaded**, and
no built pipeline to load it.

**Gap.** (1) No generate→load pipeline that populates an EEMSuite DB. (2)
Permission *profiles* are semantic intent, not yet mapped to concrete
`Permissions_TBL`/`SiEAppObjects` grants. (3) `CompanyCalendar` periods not
materialized.

**What to add.** A Phase-0 loader; concrete permission grants per group (incl.
node-scoped `D` grants proving a Finance user sees only some buildings, and an
AccessLevel-3 approver vs. a viewer); a 2024–2025 monthly `CompanyCalendar` with
**1–2 months deliberately omitted** to exercise the "fiscal period not found"
import rejection.

---

## 1. Monthly bills + charges  🟡

**What EEMSuite needs.** `Bill` + `BillItem` (line items) routed into a
`BillScenario` ("Actual"), ≥13 consecutive months per account so variance and
year-over-year tests bind. Reports: AccountHistory, BillHistory, CostBreakOut,
BillVariance(+Analysis/Detail/Ranking), FacilityAccountDetail, PerformanceSnapshot,
FiscalPeriodBills, MonthlyUtilityDistribution, etc.

**Northlake today.** Bills are modeled at the account level (24 months, all
providers) with usage/demand/total — good coverage of *bill-level* facts and the
estimated→corrected, meter-replacement, account-renewal, duplicate-import, and
rate-change scenarios.

**Gap.** The `bill` source entity has `usage/demand/total_cost` but **no
charge-line breakdown** (`BillItem`s). CostBreakOut, BillingCharges, RateComponent
mapping, and GL coding all need itemized lines (energy vs demand vs fixed vs tax).

**What to add.** Extend the `bill` model with charge lines (commodity, determinant
linkage, quantity, unit, amount, GL account) so each bill decomposes into the same
components the rate engine would produce.

---

## 2. Interval / time-series use  🟢

**What EEMSuite needs.** Points (`PointDef_TBL`) with rows in `AnalogArchive_TBL`
(PtID × UTCTimeStamp × Interval, Value/Min/Max/Avg) and `DigitalArchive_TBL` for
status points. Drives all 15 Use Analysis reports (TimeInterval, 24HourLineChart,
MultiPointTrend, HeatMap, LoadDurationCurve, Histogram, ScatterPlot, Summary,
AverageHourlyProfile, DigitalSummary, DataViewExport, MonthlyEUI, UsageVariance,
AggregateDemand, AggregatePeakLoad).

**Northlake today.** Strong: 15-min electric (Science Center, Student Center) and
solar (3 arrays), hourly chilled water, 5-min chiller kW, weather/sensor series.

**Gap.** Few **digital/status** points (DigitalSummary stays thin); interval
coverage is concentrated on a few meters.

**What to add.** A handful of digital points (e.g. chiller enable/occupancy
status) with `DigitalArchive` data; optionally widen interval coverage so
load-duration/heat-map reports have variety. (Mostly already covered.)

---

## 3. Rate engine  🟡 → the biggest "supported but unexercised" gap

**What EEMSuite supports.** A rate = `UtilityRate` → rate classes
(`UtilityRateClass`) → determinants (`UtilityDeterminant`). **The determinant is
the charge.** There are exactly **9 math kinds** (each a `UtilityRates_Run_NNN`
proc):

| Type | Kind | Northlake has it? |
| --- | --- | --- |
| 100 | RTP / real-time index pricing (hourly price point) | 🔴 no |
| 200 | Charge period: energy/demand, **tiered/block** | 🟡 energy/demand/tiers described |
| 210 | Stepped fixed-value | 🔴 no |
| 300 | Fixed by day | 🟡 (water meter charge) |
| 400 | Fixed by period (customer/facility charge) | 🟡 (facility charge) |
| 500 | Minimum bill | 🔴 no |
| 600 | Maximum bill / cap | 🔴 no |
| 700 | Bill adjustment (% rider) | 🔴 not at determinant level |
| 800 | Taxes (% on subtotal, compounding) | 🔴 not at determinant level |

Plus cross-cutting constructs: **time-of-use** (one determinant per period via
schedules), **seasonal** (summer/winter via `UtilitySeason`), **holiday calendars**,
**ratchet demand** (`UtilityDeterminantRatchet`), **load factor**, **rate-class
options** (voltage/phase/tax-exempt/farm), **pre/post determinant scripts**,
**effective-dated proration / escalation**, **unit conversion**, **multi-currency**,
and **net-metering credits** (modeled as negative blocks). The engine does **not**
natively support: power-factor math, coincident-peak/4-CP, CPP event pricing,
or net-metering banking — those must be approximated.

In the live demo DB, types **100 (RTP), 210 (stepped), 600 (max-bill)** have
**zero** determinants, and **ratchets** have only 1 row — so these are the
constructs least proven anywhere.

**Northlake today.** Rate *metadata* for TOU energy, demand, facility/customer
charge, tiered water, seasonal gas, volumetric sewer, flat-per-ERU stormwater,
PPA energy, internal allocation, and a FY2025 rate change. Described at bill
level, not modeled to the determinant/block/schedule level the engine consumes.
The `rate_schedule` source entity has no field block yet.

**Gap.** No determinant-level model; the exotic kinds (RTP, stepped, max-bill,
ratchet, load-factor, %-rider, tax, min-bill, class options, scripts,
multi-currency) are entirely absent.

**What to add.** Grow the rate model to determinants/blocks/schedules and author
**~10 rate schedules** that, between them, fire all 9 `Run_NNN` procs and every
construct — e.g. residential inclining-block (200/400/500/800), commercial
TOU+seasonal demand with holidays + riders (the flagship), large-demand ratchet
+ load factor, base/excess contract demand with scripts, **RTP index** (the only
way to fire type 100; needs an hourly price point), **stepped + max-bill** (types
210/600), gas with monthly fuel-adjustment proration (300 + effective dating),
multi-commodity water/sewer/CHW/steam, and a rate-class-options demo. Each rate
must be **assigned to meters** (`UtilityMeterRates`) with ≥13 months of usage so
ratchets/seasons/proration bind. (Full list in `roadmap.md` Phase 2.)

---

## 4. AP / GL / financial interface  🔴

**What EEMSuite supports.** A config-driven export engine. `ExportSetup` names
per-format procs (Approval/UploadFile/Batch); the file layout lives in the
"UploadFile" builder proc. Export eligibility gates on
`BillingAccount.Type_Code` (0 none / 1 AP / 2 GL / 3 both) and active status.
GL coding: `GLaccount` + 5 user-defined segments (`GLAccountUDField/Value`),
attached to bills via `BillItem.BI_EXpAcctID` (and account defaults). **7+
distinct real export file formats** exist in the codebase:

1. Single-record fixed-width AP (`export_ap`, .txt)
2. Fixed-width-in-CSV AP (`export_ap2`, .csv)
3. Header+detail fixed-width AP with GL-UDF coding (Sacramento County — region
   matches Northlake)
4. Multi-record (C/H/L/D) fixed-width AP voucher (Massport / PeopleSoft)
5. Multi-record (H/L) fixed-width GL journal with balanced debit/credit pairs
   (Massport / PeopleSoft)
6. Comma-delimited SAP FI document (Clark County)
7. AR interface (Massport)

Reports: AccountsPayableDetail, APApprovalAndUpload (Financial Interface
Approval), GLAccountUDV. Bill lifecycle states tracked in `StatusHistory`
(Received → Bill Entry → QC Approval → Payment Approval → … → G/L Upload).

**Northlake today.** Nothing — GL coding was explicitly deferred in Stage 1.

**Gap.** No GL accounts, no UDF segments, no `ExportSetup` rows, no export runs,
no bill GL coding, no approval/upload flow.

**What to add.** A chart of expense/AP GL accounts per company; the 5 UD segments
(Order/FTC/Cost Center/Fund Center/Fund or similar) with realistic + partly-blank
coverage; bill `BI_EXpAcctID` coding; `ExportSetup` rows + builder procs so we can
**generate one file of each of the 7 formats**; mixed `Type_Code` accounts (incl.
a `0`/no-upload negative control); approved-vs-blocked bills (one blocked by an
open validation alert). This directly answers "create actual AP interface files."

---

## 5. Tenant rebilling & allocation  🔴

**What EEMSuite supports.** Two top-level modes — **Bill Generation** (rate ×
meter use → recalculated tenant bill) and **Bill Allocation** (split a parent
bill's cost to tenants) — plus a lower-level **WUI point allocation** engine
(disaggregate a master point's use to sub-points). **7 bill-allocation methods**
(verified): Fixed Amount & %, Fully Submetered, Partially Submetered, Building
Areas, Partially Submetered w/ Coincident Demand, **Bill Aggregation** (children→
parent), Metered Substations. **3 point-allocation methods**: Weighted Use Index,
Measured Use, and **Percentage Based (catalog only — unimplemented; document as a
known gap)**. Bill generation has 4 generation types (Off/Manual/Auto/Auto-Regen)
and 5 schedule bases. Reconciliation has two flavors: penny-true-up inside
allocation, and `rp_BillReconciliation` (Billed vs Calculated variance, source =
interval or bill data). 14 reports depend on this subsystem.

> Note: most allocation "methods" share one SQL engine — the UI precomputes the
> per-tenant percentages and writes them as method-1 fixed/percent rows. So to
> exercise each method we supply the right precomputed shares + method id.

**Northlake today.** Nothing usable — Cedar Row is modeled at common-area level
only; there are no tenants, no sub-meters per unit, no allocation configs.

**Gap.** Entire subsystem absent.

**What to add.** A **mixed-use multi-tenant property** (proposed: *Northlake Town
Center* — anchor retail + in-line shops + an office tower + a food court, or
sub-metered Cedar Row units) structured to hit **every** method: fixed/%, fully
& partially submetered, building-areas, coincident-demand, metered substations,
and bill aggregation up to a cost center. Plus **WUI point families** (index +
measured, with deliberate fail-reason cases), **generated tenant bills** under
all 4 generation types, a **reconciliation** scenario with nonzero variance, and
**tenant accruals**. This is also where the owner's "shopping mall / housing
community" customers fit.

---

## 6. Accruals  🔴

**What EEMSuite supports.** An accrual is a `Bill`+`BillItem` tagged with the
special "Accruals" commodity (2300); its reversal carries "Reversals" (2301),
paired in `Accrual_Bill`/`BillAccrualMap`. `rp_OpenAccruals` lists
expected-but-unpaired accruals and can generate the negative reversal. "MPA" =
**Massport** (a customer), an allocation/estimation generator — not "multi-point
aggregate."

**Northlake today.** None.

**What to add.** Set the accrual/reversal commodity sys-constants; create an open
accrual (a period missing its actual bill, with a 2300 line) and a trued-up
accrual↔reversal pair; optionally an estimation generator run.

---

## 7. Bill validation  🔴

**What EEMSuite supports.** 47 QC rules (`uaQC<n>_*` procs) configured via
`BillValidation` (per-account or global thresholds by measure type: % change,
absolute floors/caps, period length). Modes: Bill Save (interactive) and Batch
Test (job → report). A bill passes QC (status → 2) only with zero failures.
~30 of 47 rules early-return when there's no prior bill, so ≥2–3 chronological
bills per account are required; two rules need a "Weather Normalized" scenario.

**Northlake today.** Deferred in Stage 1.

**What to add.** Validation thresholds per measure type; bills that deliberately
pass and trip each rule family (cost/usage variance, period length, missing
fields, inactive account); ≥1 open alert that blocks AP export; a "Weather
Normalized" scenario for the weather-normalized rules.

---

## 8. GHG / emissions  🔴

**What EEMSuite supports.** `EmissionFactor`(+History) by emission type
(CO₂/CH₄/N₂O/SF₆/HFCs… with GWP), `EmissionCategory` (scopes: indirect /
stationary combustion / mobile / fugitive / process / de-minimis),
`EmissionFactorSource`(+Member) (e.g. eGRID, EPA), mapped to meters
(`EmissionMeterMap` / `EmissionFactorMeterMap`) and enabled per company
(`EmissionCompanyConfig`). GHG = usage × factor. Reports: GHGHistory, GHGVariance,
GHGAudit.

**Northlake today.** Provider YAMLs *mention* eGRID/EPA factors, but nothing is
configured in the EEMSuite emissions tables; meters aren't mapped to factors.

**What to add.** An emission factor source (eGRID region for Sacramento + EPA
stationary combustion for gas), factor members with effective dates, meter→
category mapping (electric = indirect/Scope 2; gas/steam = stationary
combustion/Scope 1), and per-company scope config. Then GHG reports compute from
the existing usage.

---

## 9. ENERGY STAR ratings  🟡

**What EEMSuite supports.** `ESFacility` (PrimaryFunction, GFA, occupancy,
PMPropertyID) + rating **requests** (`ESRequest`) and **responses/scores**
(`ESResponseFacility`). Reports: RatingComparison, RatingHistory, RequestLog.
Scores normally come from the Portfolio Manager API.

**Northlake today.** Excellent property mapping (8 properties, exact
PrimaryFunction enums, use details) — but **no rating requests or responses**, so
the rating reports are empty.

**What to add.** Seed `ESResponseFacility` scores (and request/log rows) directly
for the mapped properties across several periods, so RatingHistory/Comparison
populate without a live PM call.

---

## 10. Weather regression / normalization  🟡

**What EEMSuite supports.** Regression of use vs HDD/CDD (+ optional 3rd
variable) stored in `FF_wnRegressionResults` / `FF_wnRegressionBestResults`
(intercept, HDD/CDD factors, R², CV-RMSE, t-stats), produced by a regression
**task** — not by raw data load. Drives WeatherRegression, RegressionSummary, and
the weather-normalized variants of ScatterPlot/UsageVariance.

**Northlake today.** HDD/CDD related points + 3 baseline shells exist; **no
stored regression results**.

**What to add.** Run/seed regression results for the metered buildings (using the
existing interval + weather data) so the regression and weather-normalized
reports return models with realistic fit stats.

---

## 11. Benchmarks / EUI  🟡

**What EEMSuite supports.** `wh_BenchMark` + EUI normalization (use ÷ floor area),
peer sets, performance snapshot; relates to ENERGY STAR score. Reports:
BenchmarkRanking, MonthlyEUI, PerformanceSnapshot.

**Northlake today.** Floor areas exist (so EUI is computable); no benchmark
definition or peer grouping.

**What to add.** Benchmark definitions (EUI, cost intensity), and enough
comparable buildings/periods that ranking is meaningful (the campus buildings +
town-center + Cedar Row give a peer set).

---

## 12. Project tracking  🔴

**What EEMSuite supports.** `Project` (type/category, capital/operating cost,
incentives) → `Activity` (design/install/M&V) → `Event` (milestones), tied to
hierarchy; M&V activities relate baselines to post-project use. Reports:
ProjectDetail, ProjectSummary, ProjectFinance.

**Northlake today.** None.

**What to add.** A small project portfolio (e.g. LED retrofit, chiller upgrade,
solar expansion) with activities, financial events, and M&V linkage to the
baselines — realistic for a campus sustainability program.

---

## 13. Alarms  🔴

**What EEMSuite supports.** `AlarmData_TBL` raised on points, with
`PriorityLevels` (informational → emergency) and alarm types. Report:
AlarmDataMap.

**Northlake today.** None.

**What to add.** Alarm-enabled points (e.g. demand threshold, chiller fault,
data-gap) with raised + acknowledged + resolved alarm rows across the data span.

---

## 14. Audit / activity logs  🔴

**What EEMSuite supports.** `AuditLog`/`AuditConfig` (data-change audit, must be
enabled) and user-activity tracking. Reports: Audit, ActivityTracker.

**Northlake today.** None.

**What to add.** Enable audit; generate a realistic trail of user actions and data
edits across the 18+ users (and the disabled-user negative case).

---

## 15. Tasks / job scheduler / workflows  🟡

**What EEMSuite supports.** A task engine with **6 task types** (System, Standard
Alerts, EEM Gateways, Report Tasks, MFR Reports, Bill Importer) plus a
component-based **workflow** engine (gateways, REST, SQL, file transfer, email,
run-process, control-flow nodes), scheduled by interval/cron. `TaskLog` records
runs. Reports: TaskLog, GatewayStatus, job_scheduler dashboard.

**Northlake today.** 13 gateway *profiles* are designed, but there is no task run
history, no schedules, no workflows.

**What to add.** Task schedules for the gateways + bill import + report delivery;
a couple of multi-step workflows (e.g. download → bill-import → validate → notify;
gateway → interval publish → regression → alert); and `TaskLog` history so
TaskLog/GatewayStatus report real runs.

---

## 16. MFR saved reports & delivery (100+ users)  🔴

**What EEMSuite supports.** Users save parameterized reports
(`GUIMFRSavedReports_TBL` + parameters), build dashboards
(`GUIMFRDashboardReports`), and schedule recurring **delivery**
(`MFRDelivery_TBL` → `MFRDeliveryReport_TBL` + `MFRDeliveryRecipient_TBL`) to
individuals, **groups**, or external emails, rendered as PDF/Excel by a delivery
task. **92 of 115 reports are MFR-deliverable.**

**Northlake today.** None.

**What to add.** A library of saved reports + dashboards; delivery schedules whose
recipient lists resolve to **100+ users** (the owner's explicit target) — most
efficiently via **group** recipients in a large portfolio company, plus a few
individual and external recipients; the delivery task to execute them. This needs
the **scale** decision (how many users/companies).

---

## 17. Importers / file intake  🟡

**What EEMSuite supports.** Bill Importer (BIF + CSV/fixed-width/Excel, with
source/utility/account/commodity mapping + validation), GreenButton/ESPI XML
interval import, MyImportExport templates, and MyUpload (JSON/CSV) handlers.
Reports: bill_importer, my_imports, my_exports.

**Northlake today.** Handheld (Neptune/MVRS) and gateway files are designed;
**no bill-importer source mappings, no GreenButton XML, no MyUpload/MyImport
configs**.

**What to add.** A bill-importer source + mapping + sample BIF/CSV/Excel files
(incl. the shipped bad-data validation sample), a GreenButton ESPI XML feed for
one meter, and a MyUpload/MyImport template — so each intake path is exercised
alongside the gateways.

---

## 18. HMR (handheld meter reading)  🟡

**What EEMSuite supports.** `HMR_Meter` (route/cycle/sequence), `HMR_ReadType`
(dials/decimals/direction/demand), `HMR_Reading`. Reports: HMRConfiguration,
hmr_export.

**Northlake today.** Neptune (water) + MVRS (gas) upload files are designed.

**What to add.** Explicit HMR meter/route/read-type config so HMRConfiguration
renders and route uploads tie to HMR readings.

---

## 19. EnergyAI  🔴

**What EEMSuite supports.** Enroll a load point + baseline period; push
consumption + weather to the EnergyAI service; store returned insights in
`EnergyAI_Insights`. Report: EnergyAIInsights.

**Northlake today.** None.

**What to add.** Pre-generated insight rows for a couple of well-instrumented
load points (anomalies, forecasts) so the report renders without a live service.

---

## 20. Commodities & unique units  🟢 (extensible)

**What EEMSuite supports.** 37 measure types (electricity, gas, steam, chilled
water, potable/sewer water, fuel oils, propane, diesel, kerosene, LPG, hot water,
coal, gasoline, recycling, solid waste, NGL, ethane, oil, produced water, plus
money/weather/activity/digital/sensor/emission). Rich unit model with conversions,
compound/rate units, dynamic (time-based) conversions, multi-currency, and unit
profiles per user.

**Northlake today.** Uses ~9 commodities with appropriate units including the
unusual ones (ton-hours, klb steam, ERU). Good.

**What to add (optional breadth).** A fuel-oil or propane backup-boiler meter, a
diesel generator, and a multi-currency rate would extend unit coverage; a custom
user-defined measure type proves the "unique units" path.
