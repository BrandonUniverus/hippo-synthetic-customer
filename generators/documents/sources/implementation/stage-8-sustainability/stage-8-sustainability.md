---
title: Stage 8. Sustainability
subtitle: GHG emissions, ENERGY STAR, weather regression and benchmarks
status: Ready to enter
---

# Stage 8. Sustainability

Stage 8 turns the usage and bill data Stages 1-7 already built into the
sustainability story: greenhouse-gas emissions computed from that usage, ENERGY
STAR property setup and rating requests, a weather-normalized read on four
metered points, and the built-in benchmarks that rank buildings against each
other. Every emission factor source and the nine benchmark definitions already
ship with the product; this stage's job is dating factor values, wiring meters
to them, and configuring the two screens (ENERGY STAR, weather regression) that
turn existing data into a new report. The Thermal Plant's Ridgeline Wind farm
adds one more job: keeping its generation out of the emissions it would
otherwise be counted in (see Ridgeline Wind below).

## Before you start

- Stages 1-7 are green: companies, the hierarchy, meters and points, bills and
  rates all exist. Stage 8 does not create a single meter; it only assigns
  emission factors to ones that already exist.
- Stages 2-7 are being authored in parallel with this one, so this chapter and
  its files name meters and points by their Stage 2/3 scenario id (the id in
  `data/scenarios/demo-university-v1.yaml`), not by an installed MeterID.
  Look each one up by its display name once those stages record real IDs.
- EmissionFactorSource, EmissionFactorSourceMember, EmissionType and
  EmissionCategory are system lookups, not blank tables: two sources and their
  members already exist with real published history. Step 1 opens and extends
  them; it does not create new ones.

## Step 1. Emission factor sources and factors

**Where:** Web, Emission Factor Sources (`#/EmissionFactorSources`) and
Emission Factors (`#/EmissionFactors`).

**Enter:** [01-emission-factors.yaml](01-emission-factors.yaml).

**Order inside the screens:** open Emission Factor Sources first only to
confirm eGRID (source 4) and Non-electric commodities (source 3) are already
present with their members CAMX (WECC California) and "Non-electric
commodities" — nothing to save there. Then go to Emission Factors, find each
member/emission-type row, open its History editor and add a 2024-01-01 row and
a 2025-01-01 row so every factor has two different values across the reporting
window.

**Why two sources are enough:** eGRID covers every electric meter (Scope 2 in
customer language) and Non-electric commodities covers natural gas (Scope 1)
and, once its Commodities list is extended to Potable Water, the water/sewer
embedded-energy figure (an approximation of Scope 3). The file explains why
chilled water/steam delivered by the Central Plant and Helios's solar
generation get no factor of their own, and why Ridgeline's wind generation,
which is reported as avoided emissions, gets none either.

**Record:** nothing new is created; note the effective-dated values you enter.

**Check:** `emission_sources_and_members`, `emission_factor_history_2024_2025`.

## Step 2. Meter emission factor assignment

**Where:** Web, Meter Emission Factor Assignment (`#/MeterEmissionFactorAssignment`).

**Enter:** [02-meter-emission-assignments.yaml](02-meter-emission-assignments.yaml),
34 meters across the three companies to assign, and 14 meters to exclude: the 10
Ridgeline turbine meters, the three Helios PV arrays and the Ridgeline Farm
Transfer Meter.

**Order inside the screen:** pick a company node on the hierarchy tree and Show
meters, choose the Emission Factor Source, Emission Factor Member and Emission
Source Category once under Assignment defaults, then Assign each meter listed and
Save. The Unassigned status shows what is left on that node. On the Thermal Plant
node, Exclude Ridgeline WTG-01 to WTG-10 and the Ridgeline Farm Transfer Meter first
and do not use Assign all (Ridgeline Wind, below); Exclude the Science Center PV
Array, the Student Center PV Array and the Cedar Row Solar Carport on their nodes.
Exclude is one click per row; the screen has no bulk Exclude.

**Auto-assignment, confirmed in the product.** Enabling a source in step 3 lets the
warehouse job (`CreateDefaultEmissionMeterMap`) map every Meter of the company whose
measure type and region match, at the company's default category, unless it is
Excluded: no bill, billing account or submeter check. GHG History then adds only what is
billed to a mapped meter. So the exclusions are the meters that carry billed kWh and
must not count: generation (the Helios arrays' PPA bills, the Ridgeline statement).
The 132 owned electric meters left to map themselves (124 Cedar Row apartments, 2 house
meters, 6 others) have no billing account, so no bill and no quantity, and add nothing;
they are not excluded (132 clicks for no change).

**Expected totals once the warehouse job has run:** 166 meters mapped in the three
companies (34 by hand and 132 automatic), 14 excluded and unmapped, no GHG row for an
excluded meter, Central Plant Electric Service 2024-09 620,084.00 lb CO2 (1,512,400 kWh x
410 lbs/MWh), Ridgeline Interconnection Meter 1,815.48 lb for 2024-08 and 18,533.40 lb
for 2025-02.

**Record:** nothing new; the assignment itself is the record.

**Check:** `meter_emission_assignments`, `meter_exclusions`, `auto_assignment_totals` and
`ghg_known_values`; for Ridgeline, `ridgeline_turbines_excluded` and
`ridgeline_interconnection_assignment`.

## Step 3. GHG company configuration

**Where:** Web, GHG Company Configuration (`#/GHGCompanyConfiguration`).

**Enter:** [03-ghg-company-configuration.yaml](03-ghg-company-configuration.yaml),
one record per company.

**Order inside the screen:** pick the company, set Starting Year 2024 and
Ending Year 2025, pick a Default Emission Source Category, then enable every
source that company has an assigned meter for from step 2. Do this after step
2: the enabled sources are also the company's automatic assignment list, so the
warehouse job maps any meter that step 2 left unassigned and unexcluded and that
a source matches.

**Record:** nothing new.

**Check:** `ghg_company_config` (baseline years, default category and two enabled sources per company).

## Step 4. ENERGY STAR property setup, rating requests, Portfolio Manager connection

**Where:** Web, ENERGY STAR Property Setup (`#/ESPropertySetup`) and New Rating
Request (`#/ESNewRatingRequest`); Configuration Tool, System Constants; Web,
Task Manager (`#/tasks/manager`) for the sync task.

**Enter:** [04-energy-star.yaml](04-energy-star.yaml), the 13 properties from
`data/scenarios/demo-university-v1.yaml` and their rating requests. See
[ENERGY STAR integration](energystar-integration.pdf) for the full property
mapping this step is entering.

**Order inside the screens:** open each of the 13 properties with Edit Property on
Property Setup (Stage 2 already created the nodes) and fill the editor: Details
(address, year built, occupancy percentage, Auto Update off), Property Uses (type,
description, Primary, gross floor area and its effective date, then Edit Details for
the use's own values: operating hours, workers, computers, enrollment, unit counts
and so on) and Energy Data Sources (Include each building's utility bill meters, never
the interval points beside them; the two PV arrays as Renewable, Electric on Site
Solar). Save, then queue rating requests on New Rating Request for 2024-2025. Both
screens are fully local and save without a Portfolio Manager account.

**What the earlier step entered, and what this one adds.** Only Primary Use and Auto
Update were entered; the year built, occupancy, floor areas, secondary uses, use
details and meters were in the scenario file and were not carried, so Admin Hall's
29% classroom wing could not evaluate and every request failed alike. The file now
carries all of it for the 13 properties (31 meters included; the campus and the Cedar
Row property are parents and carry none, and the Central Plant carries none on purpose
so its 2025 request fails the meter check). The effective dates (2023-01-01) are
assumed.

**Scores are external:** ENERGY STAR 1-100 scores only arrive from the
Portfolio Manager API, never by hand entry. Obtaining a sandbox account and
setting the `CustomerServer` System Constant is Brandon's own action item
(product backlog item 1); until then, property and request data still render,
only the score columns stay empty. Lakeview Residence Hall and Cedar Row
Apartments are the two properties expected to score once connected; every
other property, including Admin Hall, gets metrics only.

**Record:** nothing new.

**Check:** `es_properties` (year built, occupancy, use, number of uses and meters per property), `es_requests` (20 requests, 0 scores).

## Step 5. Weather regression

**Where:** Web, the Weather Regression report (`rp_WeatherRegression`), with its
popups WeatherNormalization_SetPeriod, _Run and _MeterDetails.

**Enter:** [05-weather-regression.yaml](05-weather-regression.yaml), four
meters.

**What the screens are.** The report lists the company's meters with their weather
station and latest fit (Adjusted R2, Data Count, Balance_CDD, Balance_HDD, the
factors, the T tests and CVRMSE). A button in its notes band sets the baseline END
(a popup with two inputs, Fiscal Year and Fiscal Period); each meter row has
Normalize or Re-Normalize and Meter Details. There is no step that picks a point
and no choice of weather inputs: the engine fits the heating and cooling balance
points itself. The earlier text of this step described both and did not match.

**What it regresses.** The meter's billed energy or volume (bill items of unit
classes 3 and 7) per bill period, over the 12 fiscal periods ending at the baseline
end, against the station's degree days. It does not read interval points, so the
Student Center demand and the plant's hourly ton-hours cannot be inputs; the file
uses three electric mains and one gas meter instead.

**Order:** set the baseline end to Fiscal Year 2025, Fiscal Period 12; Normalize
Science Center Electric Main, Student Center Electric Main, Lakeview Hall Electric Main
and Admin Hall Gas; read each row. Expected: Year Ending 2025/12, Data Count 12, a
cooling factor above 0 on the electric meters and a heating factor above 0 on the gas
meter, Adjusted R2 at or above 0.5 (the ranges in the file are assumed: the
synthetic bills were not generated from a known coefficient). Normalized bills need a
bill scenario named Weather Normalized, which no Northlake company has, so none are
produced.

**Record:** nothing; the result is computed.

**Check:** `weather_regression`.

## Step 6. Benchmarks

**Where:** nothing to enter. `BenchmarkRanking`, `MonthlyEUI` and
`PerformanceSnapshot` already read nine built-in benchmark definitions
(`wh_Benchmark`, company -1) including Use per area, Spend per area and CO2
per area — exactly the EUI, cost-intensity and GHG-intensity benchmarks this
stage needs. Run those three reports over the campus and Cedar Row buildings
once steps 1-5 are in; nothing is created here.

**Check:** `benchmark_definitions_builtin` (9 system rows).

## Ridgeline Wind

*Added 2026-10-01 (Ridgeline Wind).* The Thermal Plant bought Ridgeline Wind on
2024-07-01: ten 660 kW turbines near Rio Vista, one Valley Electric
interconnection, and a monthly transfer statement that EEM generates. The
Sustainability Office keeps the renewable energy certificates (one per MWh) and
wants the generation reported as avoided emissions at the grid factor, the
eGRID CAMX CO2e of the year that step 1 enters (0.1866 kgCO2e/kWh for 2024,
0.1798 for 2025), with the interconnection's station service counted as
ordinary Scope 2. It wants the turbine meters' generation counted, not the Valley
Electric bill credit, which is money and whose export is measured at the
substation, 1.9 percent below what the turbines made.

EEM's GHG screens can report the station service and nothing else of that. They
multiply the energy billed to a mapped meter by a factor and keep only positive
results; nothing marks a meter as generation (product finding 44), and no REC,
market-based or avoided-emissions input exists. A turbine with a factor would
add its output to Scope 2, about 420 t CO2e for July 2024 on the step 1 factor
rows, against 0.7 t of station service. So the stage keeps the generation out
and reports it beside the GHG screens:

- **Exclude the ten turbines (step 2).** On Meter Emission Factor Assignment,
  choose Exclude on Ridgeline WTG-01 to WTG-10; each shows as Not Calculated.
  Leaving them Unassigned is not enough: the sources enabled in step 3 are an
  automatic assignment list, and the warehouse job gives every unassigned,
  unexcluded electric meter in California a CAMX mapping at the company's
  default category. Exclude is the one state it skips. Exclude the ten before
  step 3 saves the Thermal Plant's configuration, and never use Assign all on a
  node that holds them: from Unassigned it maps them, from Excluded it clears
  the exclusions.
- **Assign the interconnection meter (step 2).** CAMX, Indirect, like every
  other electric meter. It counts station service only, so the Valley Electric
  bill must not carry the export kWh as an energy quantity on that meter
  (Stage 5): GHG History adds every energy quantity billed to a meter. The same
  holds for the credit that lands on the Central Plant's September 2024 bill
  (August 5 to September 4) under VED-BCT: it is money and adds no kWh.
- **Report avoided emissions from the turbine data.** Monthly generated kWh of
  the ten pad meters times the grid factor of the year, with the RECs at one per
  generated MWh. July 2024 is 2,251,384 kWh, or 420.11 t CO2e avoided at 0.1866;
  the hand-made July statement fixes the kWh. EEM supplies the kWh and does not
  multiply. Helios's statements print its own estimate (0.209 kgCO2e/kWh), which
  is Helios's figure, not Northlake's.
- **Enter nothing else.** Ridgeline is not an ENERGY STAR property (its two
  Facilities nodes show as unconfigured rows on Property Setup; leave them), is
  not in the benchmark peer set (no floor area), and has no weather regression
  (step 5 records output against wind speed as a goal, finding 42).

**Check:** `ridgeline_turbines_excluded`, `ridgeline_interconnection_assignment`,
`ghg_known_values`, `ridgeline_energy_quantities`,
`ridgeline_avoided_emissions_basis`, `ridgeline_not_benchmarked_or_regressed`.

## Stage 8 is done when

- eGRID's CAMX member and Non-electric commodities' gas factor each carry a
  2024 and a different 2025 value.
- All 34 electric, gas and water meters across the three companies carry an
  emission factor assignment, the 14 generation meters (ten turbines, three Helios
  arrays, the Ridgeline Farm Transfer Meter) are Excluded, and each company's GHG
  configuration covers 2024-2025. After the warehouse job 166 meters are mapped
  and the CO2 rows of Central Plant Electric Service 2024-09 (620,084.00 lb) and the
  Ridgeline Interconnection Meter (1,815.48 lb for 2024-08, 18,533.40 lb for 2025-02) are
  as expected.
- GHG History, GHG Variance and GHG Audit render computed emissions from that
  assignment, with Ridgeline in them as station service only, and Variance is
  non-zero between 2024 and 2025.
- Ridgeline's avoided emissions are computed from the turbine meters' generated
  kWh at the grid factor of the year (420.11 t CO2e for July 2024), and Ridgeline
  is in no ENERGY STAR, benchmark or weather-regression result.
- All 13 ENERGY STAR properties carry their year built, occupancy, uses with floor
  areas and details and their energy meters, and their rating requests are queued;
  once a sandbox Portfolio Manager account is connected, Lakeview Residence
  Hall and Cedar Row Apartments show a quarterly 1-100 score and the rest show
  metrics only.
- The baseline end is 2025/12 and the four weather regressions show Data Count 12 and an
  Adjusted R2 of at least 0.5 on the Weather Regression report.
- BenchmarkRanking, MonthlyEUI and PerformanceSnapshot render a ranking across
  the campus and Cedar Row buildings using the built-in benchmarks.

Run `checks.sql` beside this chapter against the instance database to see each
of these as a result set.

## Findings

- **GHG auto-assignment maps every unexcluded California Electricity meter of a configured
  company**, whatever it is (generation, submeter, tenant), at the company's default
  category (`CreateDefaultEmissionMeterMap`). Only billed quantities reach GHG History, so
  a generation meter with a bill must be Excluded; a meter with no bill is harmless. The
  Exclude action is one click per row, with no bulk form.
- **The weather regression reads billed quantities over 12 fiscal periods, not interval
  points.** A demand or an hourly point cannot be regressed. The report's lower date
  bound is `(FY-1)+FP`, a typo for `(FY-1)*100+FP`, so its Normalize gate counts every
  bill up to the baseline.
- **The ENERGY STAR editor needs far more than a primary use:** address, year built,
  occupancy, uses with floor areas and details, and the included meters. Without them every
  request is refused alike. Some use-detail labels (total units, bedrooms, the chilled-water
  attribute) were not found in the seed and are marked in the file.

- **ENERGY STAR scores are external.** `ESResponseFacility` only ever
  populates from the Portfolio Manager API via the EnergyStar sync task
  (Task 19, `EEMSuite.Tasks.EnergyStar`). Verified: `EnergyStarController.
  IsConfiguredForRequests` gates `#/ESNewRatingRequest` submission on the
  `CustomerServer` System Constant. This is product backlog item 1, not a gap
  introduced by this stage.
- **Company-specific benchmark definitions have no create screen.** Verified:
  `BenchmarksController.cs` exposes only `GetBenchmarks` and
  `GetBenchmarkControls`, both `[HttpGet]`; nothing in the Benchmarks stack
  writes `wh_Benchmark`. The nine built-in, company -1 definitions (step 6)
  cover this stage's needs, so this finding only blocks a customer wanting its
  *own* named benchmark or a saved target value. Product backlog item 7.
- **The Non-electric commodities source is CO2-only.** Verified:
  `EmissionFactorSourceEmissionType` associates source 3 with Emission Type
  CO2 only, so natural gas and water emissions in this stage are entered as a
  single already-GWP-inclusive CO2 figure rather than split across CO2/CH4/N2O
  the way eGRID's electric factor is. Not a blocking gap — the customer's
  source values were already expressed as CO2-equivalent — but worth knowing
  before comparing a GHG Audit line to a raw EPA table.
- **Extending a source to a new commodity is unverified end to end.** Adding
  Potable Water as a commodity on the existing Non-electric commodities source
  (step 1) was reasoned from the screen's code, not click-tested; confirm the
  Unit options it offers before entering the water/sewer embedded-energy
  values.
- **GHG company configuration has no Scope 1/2/3 toggle and no target field.**
  Its Starting and Ending Year are the baseline GHG Variance compares against,
  not a reporting range.
- **GHG has no generation or avoided-emissions concept.** Verified:
  `wh_GHGTableSync` multiplies each mapped meter's billed energy by its factor
  and keeps only positive results, `wh_GetGHGData` sums them, the Emission
  Factors save refuses a factor of zero or less, and no REC or market-based
  input exists. Generation can be excluded (step 2) but not reported as avoided
  emissions or as a market-based Scope 2 reduction, so Ridgeline's figure, like
  Helios's, is computed outside the GHG screens. Product finding 59, which
  extends 44.
- **Unassigned is not excluded (finding 60).** Verified: enabling a source on GHG Company
  Configuration turns on automatic assignment, and the warehouse job
  (`CreateDefaultEmissionMeterMap`) maps every unassigned, unexcluded meter
  whose commodity and address match, at the company's default category, with no
  regard for Meter Type or generation. Only Exclude stops it, for the Ridgeline
  turbines and for any other meter that must stay out of GHG History.
- **Weather regression is driven by temperature alone (goal 42).** Verified: the
  engine regresses a meter's bills on HDD and CDD from one temperature point.
  `FF_wnCore` has a third-variable slot that the runner never fills and
  normalization never uses, so output against wind speed stays a goal and no
  Ridgeline regression is run.

Findings 9, 11, 42, 44, 59 and 60 in [product findings](../product-findings.pdf)
carry the benchmark, ENERGY STAR score, regression-driver, generation-role,
avoided-emissions and automatic-assignment gaps; finding 61 records that the
ENERGY STAR sync reports no export from an on-site array. The other items here
are notes from entering this stage.
