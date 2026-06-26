# Phase 5 — Sustainability & Analytics Spec

GHG emissions, ENERGY STAR ratings, weather regression, and benchmarks — the
reporting that needs config + a processing/calc result rather than raw load.
Lights up GHG History/Variance/Audit (3), ES Rating Comparison/History/RequestLog
(3), WeatherRegression + RegressionSummary, and BenchmarkRanking/MonthlyEUI/
PerformanceSnapshot.

> **Entry path** (see [entry-path-and-gaps.md](entry-path-and-gaps.md)): GHG
> sources/factors/meter-assignment/company-config and ENERGY STAR property setup +
> rating request are **UI-DIRECT** (ES is fully local — no PM account needed to set
> up). Weather regression is **UI-THEN-RUN**. **Critical gap:** ENERGY STAR
> **scores** (`ESResponseFacility`) are **EXTERNAL** — they only arrive from the
> Portfolio Manager API via the sync task; they **cannot be hand-entered** (B1), so
> score-dependent reports need a sandbox/real PM account or stay empty. **Benchmark
> definitions** have no create UI (A6). GHG company config lacks Scope 1/2/3 toggles
> (content gap).

## Source-model extension

Add: `emission_factor_source` (ref to EEM source), `emission_factor` (source,
measure_type, emission_type, value, unit, effective_date), `emission_meter_map`
(meter, category, start/end), `emission_company_config` (company, scopes, year);
`es_rating_response` (es_property, period, score, eligible, metrics);
`weather_regression_result` (meter/point, period, weather_pt, intercept, hdd_factor,
cdd_factor, r2, cvrmse); `benchmark_definition` (company, name, formula, unit).

## 1. GHG / emissions

EEMSuite (verified): `EmissionType` (18; CO₂=GWP 1, CH₄=28, N₂O=265…),
`EmissionCategory` (1 Indirect, 2 Stationary, 3 Mobile, 4 Fugitive, 5 Process,
6 De Minimis), `EmissionFactorSource` (incl. **4 eGRID**, **3 Non-electric
commodities**, **10 Steam Plant**, 1 US EIA). GHG = usage × factor × GWP.

**Factor sources → Northlake commodities:**

| commodity | EmissionFactorSource | category (scope) | factor (reuse provider values) |
| --- | --- | --- | --- |
| electric (VED) | 4 eGRID (CAMX) | 1 Indirect (Scope 2) | 0.231 kgCO₂e/kWh (+ CH₄, N₂O) |
| natural gas (SGU) | 3 Non-electric commodities | 2 Stationary (Scope 1) | 5.31 kgCO₂e/therm |
| chilled water / steam (NTP) | 10 Steam Plant | 2 Stationary (Scope 1, plant) | from plant gas/electric input factors |
| water/sewer (RCU) | 3 Non-electric | 1 Indirect (Scope 3) | 3.2 kWh/kgal embedded → grid factor |
| solar (HOS) | — | Scope 2 reduction | avoided 0.231 kgCO₂e/kWh (market-based, RECs retained) |

Add `emission_factor` rows (with `EmissionFactorHistory` effective dates for a
2024→2025 factor change), `emission_meter_map` (each meter → its category), and
`emission_company_config` (Scopes 1+2+3 enabled, reporting years 2024–2025).
GHG reports then compute from the existing usage.

## 2. ENERGY STAR ratings

Property mapping already exists (8 properties, exact PrimaryFunction). Add
**rating requests + responses (scores)** — normally from the PM API; seed
`es_rating_response` directly:

- **Quarterly** scores 2024–2025 for **eligible** property types: campus
  (College/University), Office (Admin Hall), Library, Food Service (Student
  Center), Residence-Hall/Multifamily (Cedar Row) — ENERGY STAR 1–100 scores
  (e.g. 72 → 78 trend showing improvement).
- **Ineligible** types (Laboratory / Science Center) get **metrics but no 1–100
  score** (`eligible=false`) — realistic, and exercises the no-score path.
- A few requests with error/pending status for `rp_ESRatingRequestLog`.

## 3. Weather regression / normalization

Produce `weather_regression_result` (→ `FF_wnRegressionBestResults`) for the
metered buildings from existing interval + HDD/CDD (KSAC), model
`Use = intercept + HDD·f_h + CDD·f_c`:

| meter/point | weather inputs | expect |
| --- | --- | --- |
| Science Center electric kWh | HDD + CDD | cooling-driven, R² ≥ 0.8 |
| Student Center demand kW | CDD | event/occupancy noise, R² ~0.6 |
| Admin Hall gas therms | HDD | heating-driven, R² ≥ 0.85 |
| NTP chilled-water ton-hours | CDD | strong cooling fit |

This also fills the 3 baseline **shells** (Phase 0/1) with computed values and
enables the weather-normalized variants of ScatterPlot/UsageVariance.

## 4. Benchmarks / EUI

`benchmark_definition` rows (floor areas already exist):

| benchmark | formula | unit |
| --- | --- | --- |
| Site EUI | annual kBtu ÷ gross floor area | kBtu/sqft |
| Cost intensity | annual cost ÷ gross floor area | $/sqft |
| GHG intensity | annual kgCO₂e ÷ gross floor area | kgCO₂e/sqft |

Peer set = the 6 campus/Cedar Row buildings + Town Center buildings, so
`rp_BenchmarkRanking` ranks meaningfully and `rp_PerformanceSnapshot` /
`rp_MonthlyEUI` populate. Labs (high EUI) vs library/office (low) gives spread.

## expectedAssertions

- `ghg_computed` — GHG History = Σ(usage × factor × GWP) per scope; electric =
  Scope 2, gas/steam = Scope 1, water = Scope 3; solar shows avoided emissions.
- `ghg_factor_change` — a 2025 factor differs from 2024 (GHGVariance non-zero).
- `es_scores_present` — eligible properties have quarterly 1–100 scores
  (RatingHistory trend); labs show metrics with no score; RequestLog shows a
  pending/error request.
- `regression_fit` — each `weather_regression_result` has R² and CV-RMSE in plausible
  ranges; baselines now have computed values.
- `weather_normalized_use` — UsageVariance weather-normalized column differs from
  raw and is flatter year-over-year.
- `benchmark_ranking` — buildings rank by EUI with labs highest; EUI = use ÷ area
  matches Phase 1 `rp_MonthlyEUI`.
