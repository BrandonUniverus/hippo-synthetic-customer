# Coverage review: Stages 9, 10, 11, 12 and the report coverage matrix

Date of review: 2026-11-10. Read-only. Recipe: `C:\Hippo\Git\hippo-synthetic-customer`. Product: `C:\Hippo\Git\univerus\energyhippo` (branch feature/Northlake_NewStage3, working tree as found).
Tags: **READ** = I saw it in product code or the recipe file. **INFERRED** = reasoned from what I saw, not confirmed. Recipe paths are relative to `implementation/` unless they start with `generators/`.

## 0. The findings that matter most

1. **The recipe has fallen behind the product in three places, and the checks no longer run.** The product dropped `AuditLog`/`AuditConfig` (replaced by `AuditEntry`; report `rp_Audit` retired by `Database/EEMSuite/Scripts/RetireAuditReport.sql`; the new report is Audit Explorer `rp_AuditExplorer`), dropped `TaskLog` and `WorkflowRun` (`Scripts/RetireTaskLogs.sql`; history is now `TaskRun`/`EEMLogEvent`), and restructured the task catalog (`src/Domain/Services/EEMSuite.Domain.Services/Admin/Tasks/BuiltInTaskCatalog.cs`, Revision 4). Stage 9 step 3 (audit), step 4 (12 "existing standard schedules") and both `checks.sql` files still describe the old product. READ.
2. **Stage 9 step 4's 12 standard schedules cannot be entered as written.** Alarm Mail is now `SystemOnly` (not customer-schedulable); Late Bills, Gateway Status, Daily Administration, Energy Star and Energy Star Automation are not in the built-in catalog; five others (HDD/CDD, DataGap, Bill Validation, Populate Warehouse, Weather Normalization) became "Maintenance SQL" built-ins with their own schedules. The recipe's own ADR (`generators/documents/sources/implementation/stage-11-third-party/ADR-002c-Northlake-Demo-Service-Bundle-Research.md` line 273) already says Daily Administration (17) "is absent". READ.
3. **Stage 10's two main checks fail outright.** `row_counts_major_tables` (32 UNION rows) and `report_matrix_nonempty` (14 rows) both name `AuditLog`, `TaskLog`, `WorkflowRun`. One missing table fails the whole statement. The restore checklist also expects `rp_Audit` and an app version `7.0.0.4005` (the tree builds 7.1). READ / INFERRED.
4. **Fields the recipe never touches in the editors it names** (section 2): MFR delivery Subject, orientation, one-shot, end date, time zone, inactive; dashboard columns, public user, refresh rate, click target, zoom, shared filters; project notes, Operating Cost (0 on all five), fuel and heating events; alarm Disabled/Suspended, Log State Change, Low Warning/Low Alarm on every analog alarm, accumulator alarms; task schedule parameters, one-shot, end date, inactive; seven of the product's My Imports methods.
5. **The alarm Normal State finding is stale.** The recipe (and chapter finding 55) say no screen sets Normal State. The screen now has a Severity reference state picker (`PointAlarmDefinitionViewModel.NormalStateOptions` / `SelectedSeverityReferenceState`, committed 2026-10-05, after the recipe note of 2026-10-01). So the turbine alarm can single out Fault, and the recipe never sets the picker. READ.

## 1. What each stage sets up

### Stage 9 (implementation/stage-9-operations)

| File | Screen | Records | Exercises |
|---|---|---|---|
| 01-projects.yaml | Web, Project Tracking Editor | 5 projects, 14 event series | Library LED, Central Plant chiller, Cedar Row solar, Admin Hall recommissioning, WTG-07 gearbox. Capital cost, incentives, funding-source activity types, Implementation Costs / Use Savings / Cost Savings / Renewable Energy events |
| 02-alarms.yaml | DBA, Nodes > point > Point Alarm Definition; Web tasks | 18 records: 15 alarms (4 analog, 11 digital), 2 goals, 1 task schedule | Priority, notify user and group, Deadband, High Alarm/Warning thresholds, four state colours and text, Alarm Mail schedule |
| 03-audit-and-activity.yaml | system-generated | 5 actions | 3 field edits (bill amount, account description, meter code), normal logins, one disabled-user refusal (casey.holt), quinn.roberts cross-company views, two Ridgeline researchers |
| 04-tasks-and-workflows.yaml | Web tasks/manager; Config Tool Workflow Designer | 15 records: 12 schedules, 2 custom workflows, 1 custom task | Interval and cron schedules, two multi-step workflows, one SQLEmailer task |
| 05-saved-reports-and-dashboards.yaml | Web, Save-as-Favorite, MyFavoriteReports | 24 records: 20 saved reports (4 campus, 2 "custom", 4 Ridgeline, 10 power curves), 3 dashboards, 1 goal | Favorites, dashboards, sharing to a group, Dashboardable flag |
| 06-report-delivery.yaml | DBA Users & Groups; Web MFRDelivery | 17 records: 13 groups (+120 users by rule, not listed), 4 deliveries | 100+ recipient fan-out through groups, cron and interval schedules, PDF / PDF+Excel |
| 07-handheld-and-importers.yaml | Web handheld pages, simulator, MyImports | 10 records: 8 handheld operations, 2 My Imports templates | Operates Stage 3's 192 meters / 204 registers (the 11 route rows embedded in checks.sql sum to 192 and 204, READ) |

### Stage 10 (stage-10-baseline)

| File | Screen | Records | Exercises |
|---|---|---|---|
| 01-backup.yaml | SQL Server BACKUP | 1 backup + 3 "keep beside" notes | Full backup, CHECKSUM, VERIFYONLY |
| 02-restore-verification.yaml | RESTORE into EEMSuite_NorthlakeVerify | 1 record, 16 report-checklist lines | Restore, re-point gateways, read values |

### Stage 11 (stage-11-third-party)

No YAML, no checks.sql. One research chapter (OIDC/SAML identity, SCIM, RabbitMQ, SMTP, ENERGY STAR, EnergyAI, public API) and ADR-002c, which is really Stage 3 source-bundle research. The chapter proposes eight files (`01-services-bundle.yaml` to `08-acceptance.yaml`); none exist.

### Stage 12 (stage-12-scenarios)

| File | Screen | Records | Exercises |
|---|---|---|---|
| 01-handheld-meter-replacement.yaml | DBA Nodes; Handheld Meter Setup; Task Manager | 6 steps | Cedar Row A unit 214 water meter replaced 2024-10-15: close old, new meter, route swap, starting reading |
| 02-switchgear-kw-to-mw.yaml | Handheld Meter Setup (read types, registers) | 1 read type, 2 registers changed, 4 steps | Prompt rename, constant 1 to 1000, in-flight kW file |
| 03-fix-cedar-row-c-route.yaml + .csv | Handheld Meter Setup bulk edit, paste | 50-row CSV, 4 findings, 6 steps | Cycle, enabled, bulk meter text, paste order |
| 04-demand-read-after-energy.yaml | DBA Nodes; RateModeler; Handheld; Task Dashboard; Generated Bills | 6 setup records, 7 rounds, 7 expected bills | Meter Reads bill dates, demand a day late, Use Reading TimeStamp |

## 2. Coverage gaps (product editor against recipe)

### Stage 9 step 1, Projects
Editor: `src/Web/EEMSuite.Web/frontend/src/scripts/hippo/views/viewProjectTrackingEditor.ts`, `src/Web/EEMSuite.Web.Endpoints/Models/ProjectTrackingEditorModels.cs`, table `Database/EEMSuite/Tables/Project.sql`.

- Project Notes drawer (`NoteHistory`, entity "PT", `hasNotes`): no project gets a note. READ.
- Copy mode (`mode === "copy"`): never used. READ.
- Operating Cost is 0 on all 5 projects. Incentives 0 on WTG-07. READ (yaml).
- Project categories used: Conservation (3), Renewable Energy (2). Never Cost Avoidance, Water Conservation, Water Cost Avoidance. A water-excluding variant exists (`Procs/gc_ProjectTrackingCategoriesNoWater_Get.sql`) that the recipe never meets. READ.
- Activity types used: Utility Rebates, Local Funding, No Cogen. Never Project 2100, any real Cogen fuel. READ.
- Renewable events: the drawer also takes fuel input and heating output (`addRenewableRows`, line 951; `HeatingUnit` in the context model). The recipe enters only generation, with no fuel or heating. READ.
- Status (`StatusId`, table `Status`): never set; the save request does not carry it. READ.
- Project types: 5 lookup rows used (Lighting, Central Plant, Solar PV, Continuous Commissioning, Wind). The rest unused. INFERRED (lookup not listed).
- Feature with no data: `rp_ApplyRateSchedule` (matrix: rate history + project) appears in no stage file; nothing links a project to a rate change. READ.

### Stage 9 step 2, Alarms
Editor: `src/Apps/EEMSuite.Apps.DatabaseAdministrator/ViewModels/Nodes/Definitions/PointAlarmDefinitionViewModel.cs`, `Views/Nodes/Definitions/PointAlarmDefinitionView.xaml`; behaviour in `Database/EEMSuite/Procs/PointData_UpdateAlarms.sql`, `AlarmNotification.sql`.

- Activation: only "Normal". Options also Disabled (1) and Suspended (2) (`ActivationModes`). READ.
- Log State Change (`LogStateChangeOptions` Disabled/Enabled): never set. READ.
- Severity reference state (Normal State picker): never set, and the recipe says it does not exist. READ (stale, section 0).
- The 3 analog alarms with thresholds set High Alarm / High Warning only. None uses Low Warning or Low Alarm, none uses both sides. READ.
- Accumulator alarms: the view model has an accumulator branch (`IsAccumulator`, line 818); none entered. READ.
- Alarm Testing command (`OpenAlarmTestingCommand`): never run. READ.
- Deadband takes only 0, 1, 2, 5. Priorities used: 2, 3, 4; never 1 Informational or 5 Emergency. READ.
- Digital alarms: all ten turbines identical; the chiller alarm gives State 0 and State 1 the same green (#008040). READ.
- Notify: always user plus group. No alarm with only one of them, or neither. READ.
- Alarm lifecycle (acknowledge, resolve): `AlarmData_TBL` has Ack/Resolved columns; I found no acknowledge control in the web front end scripts. The recipe never acks or resolves, and never sets `ResolveNormalAlarms`. INFERRED for the UI, READ for column and constant.
- **Dangling point:** `ch_rcu_cedar_row_a_water_kgal_monthly` (the Cedar Row water alarm) does not exist in `stage-2-hierarchy/04-points.yaml`. Nearest is `ch_fig_cedar_row_a_water_kgal_60m` (hourly), so thresholds written per month (650/850/950) would not fit. READ.

### Stage 9 step 3, Audit and activity
Product: `Database/EEMSuite/Tables/AuditEntry.sql`, `Procs/rp_AuditExplorer.sql`, `AuditEntry_PurgeExpired.sql`, `Procs/rp_ActivityTracker.sql`, `Tables/GuiPageActivityLog.sql`.

- The recipe's audit design (12 `AuditConfig` rows, `AuditLog`, `rp_Audit`) is gone. Audit Explorer reads `AuditEntry` with its own facets (`gc_AuditActions_Get`, `gc_AuditEntityTypes_Get`, `gc_AuditSources_Get`, `gc_AuditCompanies_Get`). The recipe tests none of: record history (`AuditEntry_GetRecordHistory`), operation view (`AuditEntry_GetOperation`), audit retention (`AUDIT_RETENTION` maintenance entry), entity types other than bill, account and meter. READ.
- Activity Tracker now reads three sources: report runs, **page opens** (`GuiPageActivityLog`), sign-ins, with a Kinds facet. The recipe exercises report runs and sign-ins only. READ.
- Sign-ins are all local successes. Failed password (as opposed to Inactive), federated sign-in, MFA: untouched. INFERRED.
- The Inactive-user case proves itself by absence only (recipe says so). READ.

### Stage 9 step 4, Tasks and workflows
Product: `BuiltInTaskCatalog.cs`, `Database/EEMSuite/Tables/TaskItems.sql`, `TaskSchedules.sql`, `TaskRun.sql`, `frontend/.../views/taskDashboard/taskLibraryView.ts`, `src/Tasks/*`.

- Catalog (section 0). Plainly schedulable built-ins: `BIP_AUTOMATED_IMPORT` (Run Bill Importer), `PASSWORD_EXPIRATION_NOTIFICATION`. `ALARM_MAIL_NOTIFICATION` is SystemOnly. `MAINTENANCE_SQL` carries 12 entries (CALENDAR_EXTENSION, BILL_SYNC, WAREHOUSE_UPKEEP, LOG_RETENTION, AUDIT_RETENTION, BILL_VALIDATION, BILL_GENERATION, BILL_ALLOCATION, DEGREE_DAYS, DATA_GAPS, WEATHER_NORMALIZATION, BASELINE_FILL). The recipe schedules none of these through their own screen. READ.
- Schedule fields: only Interval and Cron used. One-shot (`ScheduleKind 0`), End date (`EndUtc`), time zone, Active off, per-schedule parameter overrides (the page shows default parameters per task, "each free to set its own"), machine choice: none set. READ.
- Workflow components never composed: RestRequest, FileTransfer, RunProcess, EventBus, Documents, BillImage, IntervalData, Sql, EnergyAIClient, EnergyStar, Analysis (`src/Tasks/EEMSuite.Tasks.*`). The two custom workflows use gateway, BillImporter, SQLEmailer and weather sync only. READ.
- No task is made to fail, time out or overlap; no dedup or retry test (`DedupWindowSeconds`). INFERRED.
- Recipe task ids (Daily Administration 17, Run Bill Importer 43, Weather Normalization Sync 48) are history. The file says "Task_Tbl (41 rows)", yet ids 43 and 48 exceed 41. READ.

### Stage 9 step 5, Saved reports and dashboards
Product: tables `GUIMFRSavedReports_TBL`, `GUIMFRDashboards`, `GUIMFRDashboardReports`, `GUIMFRDashboardSettings`, `GUIMFRDashboardControlBindings`, `GUIMFRSavedModules_tbl`, `GuiMFRPermissions_TBL`; `frontend/.../views/viewDashboardConfiguration.ts`, `viewDashboardEditor.ts`, `dashboardReportSettings.ts`.

- Dashboard options never set: Columns (default 2), per-tile Refresh rate (default 15), Click-to-open target (`_blank`/`_self`/none), Zoom mode, shared filter controls (`GUIMFRDashboardControlBindings`), dashboard Report Settings (`GUIMFRDashboardSettings`, applied for every viewer), the public (TV) session user (`publicUserId`). Executive Overview is "Public: true" with no public user. READ.
- User-created saved modules (`GUIMFRSavedModules_tbl`): only built-in module names used. INFERRED.
- Sharing: only "to a group of own company". Share to a company or user, unshare, re-share, owner edits after sharing, a favorite deleted while on a dashboard: none. INFERRED.
- **Tile mismatch:** Facility Operations tiles ("Gateway Status, Alarm Data Map, Task Log") have no saved-report records; Executive Overview tiles ("GHG History, Benchmark Ranking (Use per area)") match no saved title ("Executive Sustainability Summary", "Northlake Campus vs. Cedar Row EUI Comparison"). `Daily Operations` is "TaskLog + GatewayStatus" but a saved report snapshots one report. `Weekly Cost Rollup` names no real report ("cost/spend report (rp_ variant ...)"). The 4 campus saved reports, 2 custom ones and 4 deliveries state no owner. READ.
- New report scenes in the product (`rp_BenchmarkScene`, `rp_BillScene`, `rp_SpendScene`, from `Scripts/Add*SceneReport.sql`) are saved or dashboarded nowhere. READ.

### Stage 9 step 6, Delivery
Editor: `frontend/.../views/viewMFRDelivery.ts`; tables `MFRDelivery_TBL`, `MFRDeliveryRecipient_TBL`, `MFRDeliveryReport_TBL`.

- Never set: **Description** (required by the editor; the recipe's delivery records carry none), **Subject** (required, default "MFR Delivery"), **PDF orientation** (Portrait never), Active off, Start date, End date, time zone, one-shot, more than one report per delivery (each has one), Excel-only. READ.
- `RecipientKind` has three kinds in the table (1 user, 2 group, 3 email). The picker DTO (`MFRDeliveryRecipientsDTO`: UserId, DisplayName, CompanyID) still has no email entry, so the blocked external addresses stand. READ.
- `ImpersonateReports` is not on the editor (service saves false, `MFRDeliveryService.cs:106`). **INFERRED risk:** the 120 `bldgrep` users sit in groups with zero grants, so each recipient renders as himself with no right to run Monthly Building Energy, and 40 of them (Cedar Row 30, Central Plant 10) are in other companies than "Northlake Main Campus buildings". The check counts resolved recipients, not delivered reports. I did not find the render code that decides what happens to an unauthorised recipient.
- Weekly Cost Rollup lists samantha.ireland and morgan.patel individually and again inside NLU Finance Distribution; no dedupe expectation. READ.
- Author of the three non-Ridgeline deliveries not stated; cross-company groups need a system administrator author. READ.
- Delivery run history, overrun stop (`MFRDelivery_StopOverrun`, `StoppedForOverrun`), `NextRunTimeUtc` advance: not exercised. READ.

### Stage 9 step 7, Handheld and importers
Product: `Tables/HMR_Reading.sql`, `HMR_Meter.sql`, `Procs/HandheldMeterReading_Save.sql`, `HMR_HDLData.sql`; My Imports permission rows in `Scripts/SeedLanguageData.sql` (~line 15985).

- High/Low warning (`HMR_Reading.High1/Low1`, `int`), Tamper code, ERTID, Bill code: Stage 3's route file now covers them, but none of the Stage 12 registers set or move them (scenario 1 new register, scenario 2 constant change, scenario 4 kiosk registers). READ. `High1/Low1` are integers and go to the handheld file (`HMR_HDLData.sql` lines 243-266), so a three-decimal MW display cannot carry a fractional warning. INFERRED.
- My Imports: the product has Interval Data, Meter Readings, Loss Factor Import, Meter Swap, Create Hierarchy, Hospitality, SWG, CRC, Boulder City, plus exports Facility Detail and Facility Area (permission catalog, READ). The recipe uses 2. **Meter Swap is the product's own meter-replacement import and Stage 12 scenario 1 never uses it.** Loss Factor Import is installed in Northlake (ADR-002c line 102) and unused. The same line says the MeterReadings template Stage 9 uses "is not installed in Northlake". READ.
- Not tested: a bad upload (wrong column, duplicate rows, negative usage), upload overlapping existing readings, upload by a user without the MI permission, skipped read versus zero read. INFERRED.
- EnergyAI: SQL-only enrolment (`Procs/EnergyAI_LoadSetup.sql`, READ); checks verify only `EnergyAI_Loads` and `EnergyAI_Insights` are empty. Six other EnergyAI tables are not checked. GreenButton is GET-only (`GreenButtonController`: `ById`, `All`, READ).

### Stage 10

- Not tested: a backup that includes Stage 12 changes (the baseline closes before Stage 12 runs, so either Stage 12 never lands in the baseline or the baseline is not final), restore to a different SQL Server version, restore under another database name with the app config re-pointed. INFERRED.
- "Kept beside" lists app version 7.0.0.4005, now stale (tree builds 7.1.0.x, `bin/Release/v7.1.0.20`). No SQL logins or users are mentioned (not in a database backup). INFERRED.
- Checklist lines with no stated value: GHGHistory ("computed emissions per company"), GHGVariance ("non-zero"), rp_TaskLog / rp_GatewayStatus ("run history"), rp_ActivityTracker ("counts"). READ.

### Stage 11
Everything is a gap: no data, no check for identity providers, SCIM, RabbitMQ, SMTP, ENERGY STAR sandbox, EnergyAI, service principals. The chapter says so. I did not open the product surfaces; the SCIM controller and constants files exist (`ScimProvisioningAdministrationController.cs`, `Web/API/Scim/Infrastructure/ScimProtocolConstants.cs`). The "37 event types, 24 publishable" claim is unverified (`Scripts/SeedEventBusEventTypes.sql` has an `AllowsApiPublish` column).

### Stage 12

- Scenario 1: does not use Meter Swap; does not set High/Low warning or tamper code on the new register. Not tested: a replacement with a different multiplier, dial width or unit, or the new meter taking over a billing account. READ / INFERRED.
- Scenario 2: warnings not converted; no reverse change (MW back to kW); no bill reading the demand. READ.
- Scenario 3: cycle, enabled, text, sequence only. Not: moving a meter to another route, deleting a route, duplicate sequence, unknown meter number in the paste, Cancel before Save. READ.
- Scenario 4: exact and thorough on dates but one flat rate and one meter. Not: ratchet or minimum demand, a missing energy read, a corrected demand, `Auto` versus `Auto w/ Auto Regen`, an exported bill then regenerated. READ.

## 3. Fields present in the YAML but empty, null or default

- 01-projects.yaml: `installed.projectId` blank on all 5 (expected). `Operating Cost: 0` on all 5. `Incentives: 0` on WTG-07. Secondary Activity Type blank on WTG-07. The file says the four earlier records were "not re-checked ... reconcile them when this step is entered" (a Secondary of Local Funding is not offered, Cedar Row solar gets the fuel list, series run past end months). READ.
- 02-alarms.yaml: Low Warning / Low Alarm blank on all analog alarms. `Normal` blank on the met mast. `Deadband: 0` and no thresholds on the data-gap alarm. `installed.pointAlarmId` blank (expected). Two goal records enter nothing. READ.
- 04: every `installed` id blank (expected). The two custom workflows give `Steps` only as prose; no node or parameter values. READ.
- 05: `Params` are prose, not machine-checkable. `Owner` absent on 10 records. READ.
- 06: Format and Schedule set; no Description, Subject, orientation. External recipients never entered (blocked, intentional). READ.
- 07: `installed.myImportExportId` blank. Handheld records carry `Expected` text only. READ.
- 10/01-backup.yaml: `backupFile`, `takenOn` blank (expected). `repoCommit` is a description, not a value. READ.
- 12/04: `installed.metaWorldId: null`. READ.

## 4. Depth of checks.sql

### Stage 9 `checks.sql` (195 lines, 17 labelled checks, about 22 result sets)

| Class | Count | Checks |
|---|---|---|
| Asserts an expected value (PASS/FAIL) | 1 | `hmr_route_handoff` (11 route rows; 192 meters, 204 channels) |
| Zero rows expected, nothing flags a miss | 3 | `mfr_external_email_finding`, `hmr_duplicate_events`, `greenbutton_and_energyai_findings` (two counts) |
| Computes a status word, existence only | 1 | `hmr_history` |
| Lists rows beside a PRINT that states the expectation | 12 | `projects_with_finance` (5), `alarm_definitions` (15), `alarms_lifecycle` (none stated), `ridgeline_wtg07_fault`, `audit_trail` (3), `activity_trail` (casey 0), `task_schedules` (15), `task_history`, `saved_reports_and_dashboards` (18/3/2), `ridgeline_saved_reports_and_shares`, `mfr_delivery_100plus` (>=100, 2), `hmr_mvrs_events` |

Defects:

- `audit_trail` queries `dbo.AuditLog` and `dbo.AuditConfig`; `task_history` queries `dbo.TaskLog` and `dbo.WorkflowRun`. None exist. These two fail to compile. READ.
- `mfr_delivery_100plus` compares `r.RecipientKind = 'Group'` but `RecipientKind` is `tinyint`; it raises a conversion error. READ.
- `alarm_definitions` selects any point with `DisableAlarms = 0` that has a notify user or group. `DisableAlarms` defaults to 0, so it cannot isolate the 15. READ.
- `activity_trail` crosses logins with report views and counts distinct timestamps (two views in one second collapse); it cannot show "none of them a bill report" and ignores page opens. READ.
- `task_schedules` lists every `TaskItems` row (Stage 3 included) with no expected name or count.
- No check at all for: the two custom workflows in `Workflow`/`WorkflowVersion`, the custom task's SQL, project event values (`Event` table), alarm colours and text, Notify user and group per point, the 120 users and their group memberships (counted only indirectly), dashboard tile membership of Facility Operations and Executive Overview, My Imports (`MyImportExport_Tbl` appears only in Stage 10), the Weekly Cost Rollup and Daily Operations deliveries, Cedar Row C or any HMR correction.
- The `hmr_*` checks prove configuration and that history exists; none compares a returned value to a known one.

### Stage 10 `checks.sql` (3 checks, 0 asserted)

- `backup_history`: lists backups; does not check type D, folder, or `is_copy_only = 0`.
- `row_counts_major_tables`: 32 rows, expectation "at least one" (and `EnergyAI_Loads` 0 in the label). Fails to compile (AuditLog, TaskLog, WorkflowRun).
- `report_matrix_nonempty`: 14 proxy counts standing in for 115 reports. Same compile failure.
- The 16 restore-checklist lines are read by eye; none is scripted. `RESTORE VERIFYONLY` result is not checked.

### Stage 11, Stage 12
No `checks.sql`. Stage 12's chapter says each verify list is the check "until the first run is recorded". The verify lists have 3, 3, 4 and 3 bullets.

## 5. Known expected values

Stage 9:

| Record | Known value | Where |
|---|---|---|
| Projects | Capital and incentive dollars (120000/25000, 640000/80000, 410000/123000, 55000/10000, 310000/0); event values are prose with no numbers | 01 |
| Alarms | Thresholds 850/750, 950/850, 25/20 m/s; WTG-07 Fault window 2025-02-11 to 2025-04-22 (no severity numbers) | 02 |
| Audit | 3 AuditLog rows; casey 0 | 03 |
| Delivery | 120 recipients, 2 for Ridgeline | 06 |
| HMR | 192 / 204 | 07, checks |

No known value: Cost Savings and Use Savings series, all saved reports and dashboards (nothing says what a tile shows), Weekly Cost Rollup, Daily Operations, Executive Sustainability Summary, the custom task's email output, both workflows, the two My Imports uploads ("a week of rows", "a month of readings", no rows given), the handheld round values, the power curves (no expected slope or point count).

Stage 10: exact dollars for the Ridgeline Bill Tracking row only ($129,330.27, $1,077.45, -$152,792.65). Counts for providers, companies, properties, alarms, projects. Everything else is words.

Stage 12: scenarios 1 to 3 have exact numbers (1388, 3, 6 kgal; 1294.60 and 1312; 50 meters, sequences 10 to 500). Scenario 4 has seven exact bills; I recomputed all seven and the 19,780 kWh sum and they agree (for example May 25.00 + 2560 x 0.152 + 14.50 x 14.80 = 628.72). READ.

## 6. Internal inconsistencies

1. Alarm point `ch_rcu_cedar_row_a_water_kgal_monthly` does not exist in Stage 2. READ.
2. The chapter (stage-9-operations.md, Ridgeline section) says allow_dashboards has no Stage 1 grant ("a Stage 1 follow-up"). The YAML says three groups grant it, and `stage-1-foundation/04-groups.yaml` grants it at Level 3 in at least four groups (lines 385, 490, 777, 833). The YAML also says "level 1". READ.
3. The Stage 9 chapter says all 115 reports render non-empty across Stages 1-9, and also says `rp_EnergyAIInsights` stays empty. The matrix puts it in Phase 6. `laco_dash_trending`, `log_analysis` and `rp_ApplyRateSchedule` appear in no stage file (grep: matrix and Stage 1 permission lists only); `laco_dash_trending` is not found in the product. READ.
4. Chapter finding 55 and the alarm YAML note say Normal State has no screen field; the screen has it. READ.
5. Matrix headings disagree with rows: Bill Processing says 12, lists 11; System Manager says 27, lists 25; the headings sum to 118, the rows to 115. The tally says Phase 5 closes 14 reports but its own parts add to 17 and the rows list 17 (14 red, 3 yellow). READ.
6. Matrix claims "92 of 115" are MFR-deliverable. Not verified.
7. Stage 10 says "run history for the 12 scheduled tasks"; Stage 9 step 4 has 12 + 2 + 1 = 15, and the check text says 15. READ.
8. Stage 10 checklist lists `rp_Audit` (retired). `rp_TaskLog` is still the report name but its backing tables changed. READ.
9. Alarm Mail is scheduled twice (`alarm_mail_task` in 02, `sched_alarm_mail_service` in 04). The notes say deliberate, but the check's count of 15 then double-counts or must be reconciled. READ.
10. Step 5 tile names do not match saved titles (section 2). READ.
11. Step 6 header says "13 new Database Administrator groups"; the screen named is Users & Groups. Weekly Cost Rollup repeats two people. READ.
12. Stage 9 07 says "Task Manager"; the route `#/tasks/manager` redirects into the Task Dashboard's Tasks view (`routing.ts` line 965), which is what Stage 12 scenario 4 calls it. Minor. READ.
13. Stage 12 scenario 4 names `NL-STEP-Demand` twice (lines 51 and 84). That rate was moved to `08-rate-lab.yaml` (section 7). READ.
14. Stage 10 says app version 7.0.0.4005; recent commits describe 7.1. INFERRED.
15. The Stage 11 chapter (2026-10-01) says a services bundle is only a proposal; ADR-002c (2026-11-01) reports one implemented (`services/sources`). They overlap and do not cross-reference. READ.

## 7. Effects of today's Stage 4 rates rework on these stages

I searched every file in these stages for rates, schedules and rate-derived dollars (grep for "NL-", "VED", "SGU", "Summer Peak", "Winter Part", "rate").

- **Stage 12 scenario 4** (`04-demand-read-after-energy.yaml`): lines 51 and 84 name `NL-STEP-Demand` ("bills demand as a block amount", "under Valley Electric District (as NL-STEP-Demand is)"). That rate now lives in `08-rate-lab.yaml`, not enterable. The explanation can stay but should name a real rate or a general statement. The scenario depends on no Stage 4 rate otherwise: `TC-TENANT-GS` is created in the scenario with the system schedule "Annual All Hrs", which still exists (`04-schedules.yaml` line 16). Dollar figures are self-contained and unaffected. Stage 7's `06-tenant-bill-generation.yaml` line 21 and 32 still say tenant rates "need a home" and call NL-STEP-Demand "purpose-built for a Town Center anchor"; scenario 4 sits on that Stage 7 gap.
- **Stage 9 projects**: Cost Savings are defined as savings x "the Library's VED rate" (Library LED), "plant electric savings x VED rate" (chiller), "both savings streams x their rates" (Admin Hall). Library now sits on `VED-TOU-GS` (three time-of-use periods, 1.5% public purpose, 5% tax) and the plant on `VED-TOU-PRI`, so there is no single "VED rate". No dollar figure is written, so nothing breaks, but those series cannot be entered until a method is named (average $/kWh from Stage 5 bills, or the peak/part-peak/off-peak split). Admin Hall gas is `SGU-GN-1` (winter and summer commodity). Cedar Row solar has no rate.
- **WTG-07 project**: "$0.058/kWh, the RWL-XFER-2024 transfer price". `RWL-XFER-2024` still exists (`05-rates.yaml` line 1440) at $0.058; Ridgeline does not escalate. Unaffected.
- **Stage 10 restore checklist**: the Ridgeline Bill Tracking values ($129,330.27, $1,077.45, -$152,792.65) still trace to `07-rate-tests.yaml` (lines 467-473, 556, 573) and `05-rates.yaml` (`VED-GEN-IC`, `VED-BCT`, `RWL-XFER-2024` kept). Unaffected. Provider list (six) still matches. No line names a rate, TOU schedule or feature rate.
- **Stage 9 workflow 1**: notifies "NLU Rates Admins" (`nlu_rates_admins` exists, `04-groups.yaml` line 166). No rate dependency.
- **Bill generation dependence**: scenario 4 depends on Run Bill Gen (Stage 7 step 7); in the product that is now the `BILL_GENERATION` maintenance entry (section 2). Not a rates-rework effect.
- **Delivery "Weekly Cost Rollup"**: will show real-tariff dollars; no expected number is recorded, so no check fails, and none can notice a change.
- **Renamed schedules** (Summer Peak ... Gas Summer): no file in these stages names a time-of-use schedule. Unaffected.

## 8. Running-system scenarios worth adding to Stage 12

1. **Mid-period rate change:** edit an effective date on `VED-TOU-GS` after bills exist. Could break: Auto Regen regenerating exported or approved bills, AP export totals, Stage 10 expected dollars.
2. **Owner of saved reports and deliveries leaves:** deactivate a delivery author (`OwnerUserID`) and the Ridgeline sysadmin author. Could break: cron deliveries stop silently, shared favorites vanish, dashboard tiles go empty.
3. **Gateway device replaced or address changed:** data-gap alarm fires, backfill arrives late, late data marks bills for regeneration. Could break: alarm storm, bills regenerated twice.
4. **Billing account renumbered by the provider:** change the account number. Could break: Bill Importer matching, duplicate account, orphaned bills (and audit rows now in `AuditEntry`).
5. **New building and tenant move-in or move-out mid-month:** add node, meter, points, Bldg Rep group, alarm, GHG map, ENERGY STAR property, benchmark peer set. Could break: empty rows in reports, allocation split on the move date.
6. **Restore to another server:** restore the Stage 10 backup, then check `MachineID` on each `TaskItems` row, SMTP, callbacks (Stage 11). Could break: schedules target a machine that no longer exists, mail goes nowhere, SCIM credential expired.
7. **Daylight-saving and time-zone change:** MFR delivery `TimeZoneID` with cron at 07:00 across the change; a user's time zone changes. Could break: delivery runs twice or not at all.
8. **Year rollover:** calendar extension (`CALENDAR_EXTENSION`), Helios 2% escalator and 3% price step taking effect. Could break: bill generation for a period with no calendar row, wrong price dates.
9. **SMTP password or provider change:** rotate credentials with alarm mail and the 120-recipient delivery running. Could break: queued mail leases, dead letters, alarms recorded as sent but not delivered.
10. **A task is made to fail:** stop a gateway share, break a SQL emailer query, let a task overrun; watch the Task Dashboard and `MFRDelivery_StopOverrun`. Could break: silent stop, retry storm, overlapping runs.

## 9. Report coverage matrix (`generators/documents/sources/implementation/report-coverage-matrix.md`)

My counts from the table rows: 115 reports. Status: green 36, yellow 26, red 53. By phase: 0 = 8, 1 = 41 (28 green, 13 yellow), 2 = 9, 3 = 7, 4 = 15, 5 = 17, 6 = 18.

- **Stage feeding them:** all 115 carry a phase, so 115 of 115 have a feeding stage in the recipe's own scheme ("the phase where its data first becomes non-empty"). The Stage 9 set (phase 6) is 18: `bill_importer`, `rp_ProjectDetail`, `rp_ProjectSummary`, `rp_ProjectFinance`, `rp_ProjectTrackingConfiguration`, `rp_ApplyRateSchedule`, `rp_GatewayStatus`, `rp_TaskLog`, `rp_Audit`, `rp_ActivityTracker`, `rp_AlarmDataMap`, `log_analysis`, `my_imports`, `rp_EnergyAIInsights`, `rp_HMRConfiguration`, `hmr_export`, `job_scheduler`, `laco_dash_trending`.
- **Known expected value recorded in the matrix itself:** 0 of 115. It has no value column.
- **Known value found in Stages 9, 10, 12:** about 10 reports have a number or ordering written somewhere: `rp_ProjectDetail`, `rp_ProjectSummary`, `rp_ProjectFinance` (capital and incentive only), `rp_AlarmDataMap` (count 15), `rp_ActivityTracker` (casey 0), `rp_HMRConfiguration` and `hmr_export` (192/204), `rp_GeneratedBills` (7 exact bills), the Ridgeline Bill Tracking report (3 exact dollars; report not named, INFERRED `rp_BillHistory`), `rp_BenchmarkRanking` (Science Center highest, from Stage 8). Exact dollars rather than counts: 5 (`rp_GeneratedBills`, the Ridgeline bill report, the three project reports on cost). I did not read Stages 1 to 8, so I cannot count the rest of the 115.
- **Stage 9's 18 with no known value:** at least 11: `bill_importer`, `rp_ProjectTrackingConfiguration`, `rp_ApplyRateSchedule`, `rp_GatewayStatus`, `rp_TaskLog`, `log_analysis`, `my_imports`, `rp_EnergyAIInsights` (known empty), `job_scheduler`, `laco_dash_trending` (no product object found), `rp_Audit` (retired).
- **Out of date against the product:** `rp_Audit` retired (replaced by `rp_AuditExplorer`); `rp_BenchmarkScene`, `rp_BillScene`, `rp_SpendScene`, `rp_IntervalIntakeFlow` are registered by `Scripts/Add*Report.sql` and absent from the matrix. At least 5 reports unlisted, so 115 is no longer the count. INFERRED (I did not query `GuiReports_Tbl`).
- **Stage 10's 14 proxy buckets** are table counts, not reports; they do not map one-to-one to the 53 red reports and cannot fail on a wrong value.

## 10. What I could not check

- No database was queried. Installed lookup counts (AlarmType rows, ProjectType rows, Task_Tbl rows, `GuiReports_Tbl`, the 92 MFR-eligible reports) are unverified.
- I ran no SQL. The compile failures come from reading object lists in `Database/EEMSuite/Tables`, `Views`, `Scripts`. A table could in principle be created elsewhere; I found only retire scripts and old migrations for `TaskLog`, `WorkflowRun`, `AuditLog`.
- I did not open the Stage 11 product surfaces (Security Administration, SCIM console), the Workflow Designer, or the handheld simulator. The Keycloak lab, 37 event types and 24 publishable are unchecked.
- I read Stage 3, 4, 7 files only where these stages point at them (route counts, rate names, `tc_market_hall`, schedule names).
- Alarm acknowledge/resolve: I found no web control but did not read the Alarm Data Map front end in full.
- Render behaviour for a delivery recipient without access: not found in code.
- I read the markdown sources, not the PDFs.
