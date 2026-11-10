---
title: Stage 9. Operations
subtitle: Projects, alarms, audit and activity, tasks and workflows, saved reports, delivery, handheld and importers
status: Ready to enter
---

# Stage 9. Operations

Stage 9 is the operational layer on top of everything Stages 1-8 built: a
capital project portfolio, point alarms with real thresholds, the audit and
activity trail that using the product produces on its own, the schedules and
custom workflows that keep the whole install running unattended, a saved
report library with delivery to more than a hundred people, and the
handheld and file-import paths that round out data entry. When this stage's
checks are green, every one of the product's 115 reports has rendered
non-empty at least once.

## Before you start

- Stages 1-8 are green. This stage schedules the tasks several earlier stages
  depend on (Process HDD/CDD, Weather Normalization Sync, Energy Star) as well
  as its own.
- Stages 2-7 are being authored in parallel, so meters and points are named by
  their Stage 2/3 scenario id, not an installed MeterID/PtID, the same
  convention Stage 8 uses.
- Several screens in this stage turned out narrower than the original design
  note assumed once checked against the installed product; each place that
  happened is called out where it matters, not saved for the end.
- The Ridgeline Wind additions need Stage 1's Ridgeline users and groups,
  Stage 2's Ridgeline site, meters, points and farm aggregates, and Stage 3's
  SCADA data. Without the data they enter but render empty.

## Step 1. Projects

**Where:** Web, Project Tracking Editor (routed from
`#/reporting/ProjectTrackingConfiguration`).

**Enter:** [01-projects.yaml](01-projects.yaml), 5 projects (the fifth is
Ridgeline's WTG-07 Gearbox Replacement, see the Ridgeline Wind section).

**Order inside the screen:** Name, Hierarchy node, Currency, Project Type
(carries its Project Category), Start/End Date, Primary and Secondary
Activity Type, Tracking Number, Operating/Capital Cost, Incentives, then add
Events — a monthly value series per Event Type (Implementation Costs, Cost
Savings, Use Savings, Renewable Energy).

**Correction:** there is no five-phase activity workflow (Design →
Procurement → Install → Commissioning → M&V) on this screen. A project
carries two Activity Types, both drawn from a small Funding Source lookup
(Local Funding, Project 2100, Utility Rebates); M&V is represented by adding
a Cost Savings or Use Savings event for the months after installation, not by
a phase field.

**Record:** the Project ID after save.

**Check:** `projects_with_finance`.

## Step 2. Alarms

**Where:** Database Administrator, Nodes > point > Point Alarm Definition.

**Enter:** [02-alarms.yaml](02-alarms.yaml), 15 points: the four campus and
Cedar Row alarms, ten Ridgeline Turbine State alarms and the met mast's
high-wind alarm. Two more records are goals and enter nothing.

**Order inside the screen:** Activation, Priority, Notify User, Notify Group,
Alarm Type, Deadband, then the threshold values (High Alarm, High Warning,
Normal, Low Warning, Low Alarm) for an analog point, or the four state
colors/text for a digital one.

**Correction:** Alarm Type is a single system value; every alarm in this
stage uses it; what distinguishes a "high-demand" alarm from a "data-gap"
alarm is its threshold values and Priority, not a type selection. The
data-gap alarm also moved from Science Center to Student Center's electric
interval — the source model's actual missing-interval scenario targets
Student Center, not Science Center.

**Record:** nothing new.

**Check:** `alarm_definitions`, `alarms_lifecycle` (the second is empty until
the alarm evaluation task has run against live point data) and
`ridgeline_wtg07_fault`, which shows WTG-07's change-of-state rows.

## Step 3. Audit and activity trail

**Where:** nowhere new — this is produced by using the product.

**Enter:** [03-audit-and-activity.yaml](03-audit-and-activity.yaml), a list
of actions to perform, not fields to fill.

**What's already on:** the 12 fields `rp_Audit` tracks (bill amount and
dates, bill-item amount and quantity, billing account number/description/
provider, meter code and billing-account link) are enabled by default;
editing any of them writes a row immediately. Signing in and opening reports
is all `rp_ActivityTracker` needs.

**The two regression cases:** casey.holt (Inactive since Stage 1) must fail
to sign in and must leave no login row at all — the case is proven by
absence, not by a special failure row. quinn.roberts (the cross-company
auditor) signs in once and opens a report scoped to each of the other two
companies. Ridgeline adds a third case: Elena and Kai, university researchers
who read the plant's wind site, sign in and run reports, and Activity Tracker
counts them under Northlake University, not under the plant.

**Record:** nothing.

**Check:** `audit_trail`, `activity_trail`.

## Step 4. Tasks and workflows

**Where:** Web, Task Manager (`#/tasks/manager`) for schedules; Configuration
Tool, Workflow Designer for the two custom workflows and the one custom task.

**Enter:** [04-tasks-and-workflows.yaml](04-tasks-and-workflows.yaml).

**Order:** schedule the 12 existing standard tasks first (Daily
Administration, Process HDD/CDD Calculations, Run DataGap Calculations, Run
Bill Validation, Late Bills, Populate Warehouse, Run Bill Importer, Alarm
Mail Service, Gateway Status, the two Energy Star tasks, Weather
Normalization Sync — all existing rows, nothing to create). Then, in
Configuration Tool, author the two custom workflows on the flow canvas: bill
download → import → validate → notify finance, and gateway read → interval
publish → weather regression → alert, each composing existing workflow
components rather than writing new ones. Finally create the one custom task,
Nightly Campus Load Summary, on the existing SQLEmailer workflow.

**Record:** the Task Item IDs and the new Workflow IDs.

**Check:** `task_schedules`, `task_history` (empty until the tasks have run).

## Step 5. Saved reports and dashboards

**Where:** Web, the Save-as-Favorite drawer on any report, and
`#/MyFavoriteReports/Index` for dashboards.

**Enter:** [05-saved-reports-and-dashboards.yaml](05-saved-reports-and-dashboards.yaml),
18 saved reports, 3 dashboards, 2 proposed custom views and 1 goal that enters
nothing. Fourteen of the saved reports and one dashboard are Ridgeline's.

**What "custom report" means here:** there is no screen to register a new,
SQL-backed report type. The two items the business calls custom reports are
entered as named, parameter-locked Favorites of an existing report — a
campus-vs-Cedar-Row EUI comparison saved from Benchmark Ranking, and a
quarterly ENERGY STAR portfolio view saved from ES Rating History — created
from that report's own Save-as-Favorite drawer.

**Record:** nothing new beyond the saved report/dashboard names.

**Check:** `saved_reports_and_dashboards` and `ridgeline_saved_reports_and_shares`.

## Step 6. Report delivery

**Where:** Web, the MFRDelivery modal (Reports, Recipients, Groups, Schedule
tabs), opened from a saved report.

**Enter:** [06-report-delivery.yaml](06-report-delivery.yaml), 12 new
distribution-only groups (120 users, generated by the rule in the file, not
enumerated), one finance distribution group, and 4 deliveries (the fourth is
Ridgeline's monthly performance report to Mateo Alvarez and Elena Vasquez).

**Scale decision:** reaching 100+ recipients by adding 120 individual people
to a delivery would be unmanageable; this stage instead creates one Group per
building/property, used purely as a distribution list (a Group needs no
permission grants to be a valid delivery recipient), and assigns the Monthly
Building Energy delivery to all 12. That is the same mechanism Stage 1 used
for permission groups, reused for a different purpose.

**External email recipients:** confirmed still blocked. The persisted
recipient table has an Email column, but the delivery picker only ever
offers system Users and Groups — the two external addresses on the Weekly
Cost Rollup delivery are recorded as intent, not entered.

**Record:** the Group IDs and MFR Delivery IDs.

**Check:** `mfr_delivery_100plus`, `mfr_external_email_finding`.

## Step 7. Handheld readings and importers

**Where:** Northlake Handheld Meter Setup and Export, the planned handheld simulator,
Task Manager, point-history/report screens, and My Imports.

**Enter:** [07-handheld-and-importers.yaml](07-handheld-and-importers.yaml).

**Reuse Stage 3:** [05-handheld-routes.yaml](../stage-3-gateways-and-data/05-handheld-routes.yaml)
owns the 192 permanent meters and their 204 registers, their read types and exact fields. Do not create them
again here. The [handheld environment design](../stage-3-gateways-and-data/handheld-test-environment.md)
defines an optional service alongside the source bundle, its separate session state, actual route-file
input and native Neptune/MVRS return files. The testing-environment session owns that implementation;
installed Northlake round-trip acceptance remains a separate check.

**Order:** verify Stage 3 configuration, export the real route file, import it with the current
environment binding manifest into the simulator, select a reader/route, record reads or explicit
skips and visit notes, review/finalize, then explicitly deliver one return format to the intended
Input folder. Run the existing disabled schedule and inspect the actual register/usage values and
appropriate MVRS logs. Resume, unchanged re-finalization, replay, a late actual and a correction
must preserve earlier evidence. Simulator preparation/delivery status is not Northlake import success.

First prove the two master routes with controlled whole-unit values. Retained monthly history and
the apartment water round wait for the raw-scale, gas-conversion, export-width and water-conservation
gate in the design. Imported history then supports supplier-bill comparison and Cedar Row allocation.
The two generic My Imports exercises remain separate from the native handheld collector path.

**GreenButton and EnergyAI:** both confirmed to have no entry UI in this
install (below).

**Record:** export/return hashes, binding/source version, reader, submission revision, delivery receipt,
task run ID, actual register/usage values, applicable logs and correction/replay outcome.

**Check:** the full Stage 3 HMR configuration checker, then `hmr_route_handoff`, `hmr_history`,
`hmr_mvrs_events`, `hmr_duplicate_events`, and `greenbutton_and_energyai_findings` here.

## Ridgeline Wind

The Thermal Plant bought Ridgeline Wind on 2024-07-01: ten 660 kW turbines in
the Montezuma Hills that also serve as the Wind Energy Research Lab. The one
event in its data that Stage 9 leans on is WTG-07's gearbox outage, 2025-02-11
to 2025-04-22: state Fault, zero energy, possible power still reported. That is
lost production, not missing data.

| Piece | Step | Status |
| --- | --- | --- |
| WTG-07 Gearbox Replacement, $310,000 | 1 | Enter. Renewable Energy, type Wind: there is no Generation category. |
| Ten Turbine State alarms | 2 | Enter, in the plant's black, green, red and orange. |
| Met mast high-wind alarm | 2 | Enter. The thresholds are assumed. |
| Researchers' sign-ins and report runs | 3 | Perform, then read Activity Tracker. |
| Farm generated against possible, WTG-07 generated against possible, Gateway Status | 5 | Enter. The two trends are Multi-Point Trend. |
| Ten power curves | 5 | Enter as plain scatter plots. The curve fit is goal 43. |
| Ridgeline Operations dashboard | 5 | Enter. Needs the allow_dashboards function. |
| Monthly performance report to Mateo and Elena | 6 | Enter. Needs a system administrator as its author. |
| Alarm on a performance ratio below a threshold | 2 | Goal 41. Nothing entered. |
| Expected against actual, the Radar scorecard | 5 | Goal 47. Nothing entered. |

**Goals, not features.** Three pieces cannot be entered because the product
cannot do them yet. The stage records them as goals and does not work around
them.

- **Goal 41, calculated points.** An alarm on a turbine's performance
  (generated energy over possible energy, below a threshold) needs a
  performance-ratio point that EEM cannot calculate, and so does a check for a
  stuck anemometer. Until then Ridgeline's alarms watch raw values: a turbine's
  state and the met mast's wind speed.
- **Goal 43, the power-curve fit.** The ten power curves are plain scatter
  plots, and the plot fits only a straight line, y = mx + b, through what is an
  S-shaped curve. A binned or polynomial fit, to compare turbine with turbine
  or with the manufacturer's curve, waits.
- **Goal 47, expected against actual.** The Radar chart's actual-against-target
  scorecard is the one target visual EEM has, and no shipped report feeds it.
  The report it needs returns one row per turbine, generated energy as the
  actual and possible energy as the reference, both as a percent of rated
  energy because the Radar scale is fixed at 0 to 100 percent. The scorecard
  then paints orange any turbine below 80 percent of possible, which is WTG-07
  from 2025-02-11 to 2025-04-22. Until that report exists the farm trend draws
  the same two quantities, summed over the farm, as two lines in kW.

**What the researchers can open.** Elena and Kai (eem_ridgeline_research) can
run every Use Analysis report on the Ridgeline Wind Site and open Points List
and Point Data Map, and they open Elena's shared power curves from My Favorite
Reports. They cannot open Gateway Status, Task Log, a bill report or the
plant's dashboard. A shared dashboard holds only its owner's own saved reports,
and an ordinary user shares only within their own company, so the plant's
dashboard and the researchers' power curves each reach their own people.
Dashboards also need the allow_dashboards function, which no Stage 1 group
grants yet: a Stage 1 follow-up.

**Read before entering.** Three things were read from the code and not yet run
on Ridgeline data. They are the first things to check once Stage 3's data
lands.

- A digital alarm records every change of state and scales its severity by
  Priority times the state's distance from a Normal State that no screen sets.
  Turbine State therefore alarms on Fault (red, 2 times Priority) but cannot
  alarm on Fault alone: Running counts as 1 times Priority and Curtailed as 3.
  `ridgeline_wtg07_fault` shows what WTG-07 actually leaves.
- The scatter plot reads a power or speed point as value times interval over
  60, so on 10-minute data wind speed and power may plot at one sixth of the
  reading with no unit on the axes. The shape and the fit are unchanged. Run the
  first curve against the point's own values.
- The Project Tracking editor takes 1 to 12 months from a start month, with
  every monthly series inside them, so WTG-07's window is February to December
  2025. The four earlier projects' savings run past their own end months and
  need the same reconciliation when they are entered.

## Stage 9 is done when

- Project, Alarm, Audit, ActivityTracker, TaskLog and GatewayStatus all
  render non-empty.
- HMR routes reuse Stage 3 configuration; the native returned files have verified register/usage
  history and appropriate MVRS event evidence. The two My Imports templates are checked separately.
- The Monthly Building Energy delivery fans out to 100 or more recipients
  through its 12 groups.
- Ridgeline: WTG-07's Fault shows in `ridgeline_wtg07_fault`, the power curves
  and the dashboard open for the people they were shared with, and the monthly
  performance delivery reaches Mateo and Elena. Goals 41, 43 and 47 stay goals.
- Every one of the 115 reports in the [report coverage matrix]
  (../report-coverage-matrix.pdf) has rendered non-empty at least once across
  Stages 1-9.

Run `checks.sql` beside this chapter against the instance database to see
each of these as a result set.

## Findings

- **Custom report registration has no UI.** Verified: `ReportMenuItemDTOController.Save`
  (`api/ReportMenuItem/Save`) can re-file an *existing* report into a
  different menu location, but nothing in the web frontend or Configuration
  Tool calls it, and it creates no new report logic. A genuinely new,
  SQL-backed report has no path through the product.
- **MFR external-email recipients: confirmed, and more precisely than the
  design note guessed.** The persisted `MFRDeliveryRecipient_TBL` table
  already has an `Email` column; the picker's own DTO
  (`MFRDeliveryRecipientsDTO`) and its drawer UI never expose a field that
  writes to it. Reaching 100+ recipients through Groups works today and does
  not need this fixed.
- **EnergyAI enrollment has no UI.** `EnergyAI_Loads`, `_WeatherSites`,
  `_TuningPeriod` and `_BaselinePeriod` exist only as tables; nothing in the
  web frontend or Configuration Tool writes them.
  `EEMSuite.Tasks.EnergyAIClient` only runs for an already-enrolled load.
  `rp_EnergyAIInsights` stays empty for Northlake.
- **GreenButton (ESPI XML) import has no UI.** `GreenButtonController`
  exposes only `[HttpGet]` endpoints; there is no upload path.
- **Project Tracking's activity model is a funding-source lookup, not a
  construction-phase workflow** (Step 1's correction) — a real gap between
  the original design note and the installed screen, not a missing feature;
  recorded here so it is not rediscovered.
- **Point Alarm Definition's Alarm Type is a single system value**, not a
  per-scenario choice (Step 2's correction).
- **Ridgeline's goals 41, 43 and 47** (calculated points, the power-curve fit,
  and a report for the Radar scorecard) are goals in the register. This stage
  enters nothing for them.
- **A digital alarm cannot single out a state** (finding 55, to verify). Normal
  State has no field on the Point Alarm Definition screen, so a four-state
  turbine point cannot alarm on Fault alone.
- **The scatter plot may scale power and speed points** (finding 56, to
  verify). It reads them as value times interval over 60 and labels no unit, so
  a 10-minute power curve may plot at one sixth of its reading.
- **Project Tracking takes at most 12 monthly columns from the start month**
  (finding 57), so savings after the first year cannot be recorded against the
  project.
- **Digital Summary totals only states 0, 1 and 2** (finding 58), so Turbine
  State's fourth state, Curtailed, is never summarised.

All are recorded in [product findings](../product-findings.pdf).
