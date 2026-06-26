# Phase 6 — Operations & Engagement Spec

The operational layer plus scheduled report delivery to **100+ users**. Closes the
remaining reports: Project (4), Alarm, Audit, ActivityTracker, TaskLog,
GatewayStatus, EnergyAIInsights, HMRConfiguration, bill_importer/my_imports — and
adds the MFR delivery layer over all 92 deliverable reports.

> **Entry path** (see [entry-path-and-gaps.md](entry-path-and-gaps.md)): project
> tracking, alarm **thresholds** (WPF), task **schedules** (web), workflow authoring
> (WPF ConfigurationTool), MFR save/dashboard/delivery, and handheld config are
> **UI-DIRECT**. Audit/activity/status/notes are **SYSTEM-GENERATED** (free by using
> the app). Alarm **events**, **task-log** history, and AP/regression results are
> **UI-THEN-RUN** (the Tasks EngineWorker / jobs must be running). **Gaps:**
> **EnergyAI** insights are **EXTERNAL**-only (B2); **GreenButton** import has no UI
> (A8); MFR **external-email** recipients are a missed screen — reach **100+ via
> groups** (A7). Project types/categories/activities are reference data (no create
> UI).

## Source-model extension

Add: `project` (type, category, status, capital/operating/incentive cost),
`project_activity` (type, dates, hierarchy), `project_event` (type, milestone);
`alarm_point` (point, alarm_type, priority, thresholds), `alarm_event`
(point, ts, value, priority, ack, resolved); `audit_event` (user, action,
table, ts); `task_schedule` (task, kind, cron/interval, next_run),
`task_log_entry`, `workflow` (nodes); `mfr_saved_report`, `mfr_dashboard`,
`mfr_delivery` (schedule, formats), `mfr_delivery_recipient` (kind, user/group/email);
`energyai_insight`; `hmr_meter`/`hmr_read_type`/`hmr_reading`; `import_source`/
`import_mapping`.

## A. Project tracking

A campus sustainability portfolio (`Project` → `Activity` → `Event`, verified
tables exist):

| project | category | capital | incentive | M&V |
| --- | --- | --- | --- | --- |
| Library LED Retrofit | Lighting | $120k | $25k rebate | baseline `bl_nlu_*` → post lighting kWh |
| Science Center Chiller Upgrade | HVAC | $640k | $80k | CHW ton-hour baseline |
| Cedar Row Solar Expansion | Renewable | $410k | ITC | solar generation vs prior |
| Admin Hall Recommissioning | Controls | $55k | $10k | gas + electric baseline |

Each with activities (Design → Procurement → Install → Commissioning → **M&V**)
and financial events (cost, savings) tied to hierarchy nodes. Lights up
ProjectDetail/Summary/Finance + `rp_ApplyRateSchedule`.

## B. Alarms

Alarm-enabled points with `PriorityLevels` (1 Informational … 5 Emergency):

| point | alarm | priority | raised |
| --- | --- | --- | --- |
| Student Center demand kW | high-demand threshold | 4 Critical | summer event spikes |
| Chiller enable (digital) | chiller-fault | 3 Important | occasional |
| Science Center interval | data-gap | 2 Warning | the `missing_interval_backfill` window |
| Cedar Row water kgal | high-usage | 2 Warning | occupancy spikes |

Each with raised → acknowledged → resolved `alarm_event` rows across the span →
`rp_AlarmDataMap`.

## C. Audit & activity logs

Enable audit; generate a realistic trail across the 19 users: bill entry/approval,
rate edits, hierarchy changes, report runs, logins — including the **disabled user
(casey.holt) failed-auth** attempt and the **cross-company auditor (quinn.roberts)**
views. Lights up `rp_Audit` + `rp_ActivityTracker`.

## D. Tasks / workflows

`task_schedule` + `task_log_entry` (TaskType: 3 EEM Gateways, 6 Bill Importer,
4 Report, 5 MFR, 2 Standard Alerts, 1 System):

- Schedules for the 13 gateway profiles, the bill importer, and report/MFR
  delivery (interval + cron).
- `TaskLog` run history across 2024–2025 (successes + a few failures) →
  `rp_TaskLog`, `rp_GatewayStatus`.
- Two **workflows**: (1) download → bill-import → validate → notify finance;
  (2) gateway read → interval publish → weather regression → alert.

## E. MFR saved reports & delivery (100+ users)

**Scale default (owner decision still open):** a **Monthly Building Energy
Report** delivered to a **building-representative roster of ~120 users**, reached
via **group** recipients (most efficient). Roster defined by a deterministic
generation rule (120 users across ~12 building-rep groups, ~10 each), not
enumerated.

- `mfr_saved_report` library: Monthly Building Energy, Weekly Cost Rollup,
  Executive Sustainability Summary, Daily Operations — each with saved parameters.
- `mfr_dashboard`: Facility Operations, Executive Overview.
- `mfr_delivery` schedules: Monthly (cron `0 7 1 * *`) → the 120-user building-rep
  groups (PDF); Weekly (cron) → finance group + 2 external emails (PDF+Excel);
  Daily (interval) → ops individuals. Recipients via `mfr_delivery_recipient`
  (kind group/user/email). Executed by the MFR Reports task.

## F. EnergyAI

Pre-generated `energyai_insight` rows for two well-instrumented load points
(Science Center electric, Student Center electric): anomaly detections (e.g.
weekend baseload spike), forecast vs actual, and savings opportunities, with
energy/demand/cost metrics → `rp_EnergyAIInsights`.

## G. HMR (handheld meter reading)

Explicit `hmr_meter` route/cycle/sequence + `hmr_read_type` (dials/decimals/
direction/demand) tied to the existing **Neptune (Cedar Row B water)** and
**MVRS (Student Center gas)** handheld uploads, with `hmr_reading` rows →
`rp_HMRConfiguration`, `hmr_export`.

## H. Importers / file intake

- **Bill Importer**: an `import_source` + `import_mapping` (provider/account/
  commodity) + sample **BIF/CSV/Excel** bill files, including the shipped
  **bad-data validation sample** and the **2026-01 fiscal-gap** rejection file
  (Phase 0 fixture) → `bill_importer`, `my_imports`.
- **GreenButton**: one ESPI XML interval feed for a metered building.
- **MyUpload/MyImport**: a JSON upload handler + a `myimport_intervaldata` /
  `myimport_MeterReadings` template run.

## expectedAssertions

- `projects_with_finance` — Project Detail/Summary/Finance render with capital/
  incentive/savings; M&V activities link to baselines.
- `alarms_lifecycle` — `rp_AlarmDataMap` shows raised→ack→resolved across
  priorities; the data-gap alarm aligns with the backfill window.
- `audit_trail` — `rp_Audit`/`rp_ActivityTracker` show edits + the disabled-user
  failed auth + cross-company auditor views.
- `task_history` — `rp_TaskLog`/`rp_GatewayStatus` show scheduled runs incl.
  failures; workflows complete.
- `mfr_delivery_100plus` — the Monthly delivery fans out to ≥100 recipients
  (verifiable via the delivery task log) in PDF.
- `energyai_insights_present` — `rp_EnergyAIInsights` returns insights with metrics.
- `hmr_config_renders` — `rp_HMRConfiguration` shows the Neptune/MVRS routes with
  read types.
- `importers_ingest` — sample BIF/CSV/Excel + GreenButton + MyUpload all ingest;
  the bad-data and 2026-01 files are rejected with the expected messages.
- `every_report_nonempty` — with all phases loaded, each of the 115 reports has at
  least one scenario that renders it non-empty.
