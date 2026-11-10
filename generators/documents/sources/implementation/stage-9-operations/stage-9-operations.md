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
checks are green, every one of the product's 119 reports has rendered
non-empty at least once.

## Before you start

- Stages 1-8 are green. This stage switches on the built-in maintenance several earlier
  stages depend on (degree-day calculations, weather normalization, bill generation and
  allocation) as well as scheduling its own tasks.
- Rewritten 2026-11-10 against the product as it stands: the audit log (AuditLog,
  AuditConfig, rp_Audit) was replaced by AuditEntry and Audit Explorer, task history
  (TaskLog, WorkflowRun) by TaskRun, and the built-in task catalog was restructured
  (Revision 4), so steps 2, 3 and 4 and their checks changed, and every check now
  asserts a value (Expected, Actual, PASS or FAIL).
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
high-wind alarm. Two more records are goals and enter nothing, and one records
that Alarm Mail Notification belongs to the product.

**Order inside the screen:** Activation (Normal, Disabled, Suspended),
Priority, Notify User, Notify Group, Alarm Type, Deadband, then for an analog
point the ladder High Alarm, High Warning, Normal, Low Warning and Low Alarm, or
for a digital point the Severity reference state and the four state
colors/text.

**What the screen requires.** An enabled analog alarm needs all four thresholds,
strictly ordered (Low Alarm < Low Warning < High Warning < High Alarm); the
earlier records that left the low side blank could not have been saved, so every
analog alarm now carries all four. Only a Disabled alarm is exempt. Normal is a
band with a colour and no value. Disabled records nothing; Suspended still records
every alarm and stops only the mail.

**Coverage.** Across the 15 alarms the stage now enters Disabled (the data-gap
alarm), Suspended (WTG-07), the Severity reference state (Running on all ten
turbines, clear on the chiller), Priority 1 and 5, and Low Warning and Low Alarm
on the three enabled analog alarms. Two options in the view model have no control
on the screen and are not entered: Log State Change and any alarm on an
accumulator point (finding candidates).

**Correction:** Alarm Type is a single system value; every alarm in this
stage uses it; what distinguishes a "high-demand" alarm from a "data-gap"
alarm is its threshold values and Priority, not a type selection. A threshold
alarm cannot see missing intervals at all (an AlarmData row comes only from a
value crossing a threshold or a digital state changing), so the "data-gap"
alarm on Student Center's electric interval is kept as a Disabled record and the
gaps themselves are found by the Data gap monitoring maintenance entry (step 4).
The Cedar Row water alarm now sits on the hourly point Stage 2 creates for that
meter, so its thresholds are per hour, not per month.

**Record:** nothing new.

**Check:** `alarm_definitions` (each of the 15 against its Activation,
Priority, thresholds, Deadband, Severity reference state and notify user and
group) and `ridgeline_wtg07_fault`, which asserts WTG-07's Fault row of
2025-02-11 at severity 3 and its return to Running.

## Step 3. Audit and activity trail

**Where:** nowhere new — this is produced by using the product.

**Enter:** [03-audit-and-activity.yaml](03-audit-and-activity.yaml), a list
of actions to perform, not fields to fill.

**What's already on:** the application audit trail is `AuditEntry`, written by
the services that save business data and selected by the ApplicationAudit
configuration, which defaults to enabled with every entity when nothing is
configured. The earlier design (12 tracked columns in `AuditConfig`, rows in
`AuditLog`, the `rp_Audit` report) was retired. Editing a bill, a billing account
or a meter in the apps writes an entry at once (direct SQL does not), and Audit
Explorer, under System Health, reads them for a system administrator by date
range, user, record type, action, company and source. Signing in, opening pages
and running reports is all `rp_ActivityTracker` needs; it now lists report runs,
page opens and sign-ins together.

**The regression cases:** casey.holt (Inactive since Stage 1) must fail
to sign in and must leave no login row at all — the case is proven by
absence, not by a special failure row. quinn.roberts (the cross-company
auditor) signs in once and opens a report scoped to each of the other two
companies. Ridgeline adds a third case: Elena and Kai, university researchers
who read the plant's wind site, sign in and run reports, and Activity Tracker
counts them under Northlake University, not under the plant. A system
administrator then reads the four edits in Audit Explorer.

**Record:** nothing.

**Check:** `audit_trail` (the bill, billing account and two meter entries by
jordan.hale, none by casey.holt), `activity_trail`.

## Step 4. Tasks and workflows

**Where:** Web, Task Dashboard > Tasks (`#/tasks/manager` redirects there) for
schedules; Configuration Tool > Maintenance for the built-in maintenance
procedures; Configuration Tool > Tasks and Workflow Designer for the custom task
and the two custom workflows.

**Enter:** [04-tasks-and-workflows.yaml](04-tasks-and-workflows.yaml).

**What changed.** The built-in task catalog (`BuiltInTaskCatalog`, Revision 4)
no longer holds the twelve standard tasks the stage used to schedule. Alarm Mail
Notification is SystemOnly (the product runs it), Late Bills, Gateway Status,
Daily Administration and the two Energy Star tasks are gone, and five tasks
(Process HDD/CDD, Run DataGap, Run Bill Validation, Populate Warehouse, Weather
Normalization Sync) became entries of the SystemOnly Maintenance SQL task, 13 in
all, each with its own schedule on the Maintenance page. Two built-in tasks are
still scheduled by a customer: BIP Automated Import and Password Expiration
Notification.

**Order:** schedule those two on the Task Library (BIP Automated Import
left Enabled off, because Stage 5 imports by hand); switch on 12 of the 13
maintenance entries on the Maintenance page (BIP automated import stays off, the
Task Library schedule carries it); author the two custom workflows in Workflow
Designer, make a task for each in the Task Editor and schedule it; finally make
the custom task Nightly Campus Load Summary on the existing SQLEmailer workflow,
with two schedules. Across the six schedules the stage enters an interval, two
presets, a custom cron, a one-shot and a disabled schedule.

**Record:** the Task Item IDs, the Maintenance Task IDs and the new Workflow IDs.

**Check:** `task_schedules` (the six schedules by Description, Active and
ScheduleKind, the custom task, the two workflows and the 13 maintenance entries),
`task_history` (every run is a `TaskRun` row; `TaskLog` and `WorkflowRun` are
retired).

## Step 5. Saved reports and dashboards

**Where:** Web, the Save-as-Favorite drawer on any report, and
`#/MyFavoriteReports/Index` for dashboards.

**Enter:** [05-saved-reports-and-dashboards.yaml](05-saved-reports-and-dashboards.yaml),
23 saved-report rows (21 saved reports and 2 proposed custom views), 3
dashboards and 1 goal that enters nothing. Fourteen of the saved reports and one
dashboard are Ridgeline's. Facility Operations and Executive Overview now list
saved reports their owners actually have (three each); the earlier tile lists named
reports no record created.

**Dashboard options entered:** Columns, per-tile Refresh rate, Open report (same
window, new window, none), Zoom mode on the chart tiles, the public link and Show
data as, Set as my homepage and the shared report controls. The public link needs the
Public Dashboards function, which Stage 1 does not yet grant to any group.

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
enumerated), one finance distribution group, and 5 deliveries (the fourth is
Ridgeline's monthly performance report to Mateo Alvarez and Elena Vasquez; the
fifth is a one-shot, Run immediately). Every delivery now carries its Delivery
description, Email subject, Delivery status, PDF orientation and Time zone; one
is Off, one has a start and an end date, one is Portrait, and the Output card's
Impersonate reports (administrators only) stays off.

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

**Check:** `mfr_delivery_100plus` (each delivery's subject, orientation, format, status, schedule kind and resolved recipients: 120, 4, 2, 2 and 1), `mfr_external_email_finding`.

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
The generic My Imports exercises remain separate from the native handheld collector path.

**My Imports:** the product names nine import methods, but only Loss Factor Import ships with a handler, so the stage adds one
Loss Factor upload (Account Number, Loss Factor, Notes) to the two templates it had. Meter Swap, Create Hierarchy, Hospitality,
SWG, CRC and Boulder City are permission entries with no definition or handler and cannot be entered; Stage 12 scenario 1 is
unchanged because no working Meter Swap import was found.

**GreenButton and EnergyAI:** both confirmed to have no entry UI in this
install (below).

**Record:** export/return hashes, binding/source version, reader, submission revision, delivery receipt,
task run ID, actual register/usage values, applicable logs and correction/replay outcome.

**Check:** the full Stage 3 HMR configuration checker, then `hmr_route_handoff`, `hmr_history`,
`hmr_mvrs_events`, `hmr_duplicate_events`, `myimports_installed` and `greenbutton_and_energyai_findings` here.

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
Dashboards also need the allow_dashboards function, which Stage 1 grants through
four groups.

**Read before entering.** Three things were read from the code and not yet run
on Ridgeline data. They are the first things to check once Stage 3's data
lands.

- A digital alarm records every change of state and scales its severity by
  Priority times the state's distance from the Severity reference state, which
  the screen has had a picker for since 2026-10-05 (the stage sets it to Running).
  Turbine State then alarms on Fault (red, 1 times Priority) but cannot alarm on
  Fault alone: Stopped scores 1 times Priority and Curtailed 2. WTG-07 is Suspended,
  so its Fault is recorded but not mailed. `ridgeline_wtg07_fault` asserts what it leaves.
- The scatter plot reads a power or speed point as value times interval over
  60, so on 10-minute data wind speed and power may plot at one sixth of the
  reading with no unit on the axes. The shape and the fit are unchanged. Run the
  first curve against the point's own values.
- The Project Tracking editor takes 1 to 12 months from a start month, with
  every monthly series inside them, so WTG-07's window is February to December
  2025. The four earlier projects' savings run past their own end months and
  need the same reconciliation when they are entered.

## Stage 9 is done when

- Project, Alarm, Audit Explorer, ActivityTracker, TaskLog and GatewayStatus all
  render non-empty, and every row of this stage's checks is PASS.
- HMR routes reuse Stage 3 configuration; the native returned files have verified register/usage
  history and appropriate MVRS event evidence. The two My Imports templates are checked separately.
- The Monthly Building Energy delivery fans out to 100 or more recipients
  through its 12 groups.
- Ridgeline: WTG-07's Fault shows in `ridgeline_wtg07_fault`, the power curves
  and the dashboard open for the people they were shared with, and the monthly
  performance delivery reaches Mateo and Elena. Goals 41, 43 and 47 stay goals.
- Every one of the 119 reports in the [report coverage matrix]
  (../report-coverage-matrix.pdf) has rendered non-empty at least once across
  Stages 1-9, and the matrix records the value each stage expects of it.

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
- **A digital alarm cannot single out a state** (finding 55, reworded). The
  Severity reference state picker exists (it moves the zero point of the severity),
  but severity is a distance from it, so a four-state turbine point still cannot
  alarm on Fault alone.
- **Log State Change and accumulator alarms have no control.** The Point Alarm
  Definition view model carries both, the view binds neither.
- **A point alarm cannot detect a data gap.** Only the Data gap monitoring
  maintenance entry does; the earlier "data-gap alarm" was a threshold alarm on the
  point.
- **My Imports lists six methods nothing implements** (Meter Swap, Create
  Hierarchy, Hospitality, SWG, CRC, Boulder City): permission entries without a
  definition or handler.
- **BIP Automated Import exists twice**, as a built-in task and as a maintenance
  entry running the same procedure.
- **The scatter plot may scale power and speed points** (finding 56, to
  verify). It reads them as value times interval over 60 and labels no unit, so
  a 10-minute power curve may plot at one sixth of its reading.
- **Project Tracking takes at most 12 monthly columns from the start month**
  (finding 57), so savings after the first year cannot be recorded against the
  project.
- **Digital Summary totals only states 0, 1 and 2** (finding 58), so Turbine
  State's fourth state, Curtailed, is never summarised.

All are recorded in [product findings](../product-findings.pdf).
