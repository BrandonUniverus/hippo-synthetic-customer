# Stage 3 coverage review: gateways, tasks, acceptance, handheld, baselines

Read-only review, 2026-11-10. Recipe: C:\Hippo\Git\hippo-synthetic-customer\implementation\stage-3-gateways-and-data (written R: below). Product: C:\Hippo\Git\univerus\energyhippo (written P: below).
Marking: READ = seen in code or YAML. INFERRED = reasoned from what I saw. Handheld High/Low warnings are skipped as agreed.

## 1. What the stage sets up

| File | Screen (app) | Records | Exercises |
|---|---|---|---|
| 01-checkpoint.yaml | BACKUP DATABASE (sqlcmd/SSMS) | 1 backup | COPY_ONLY full backup before entry. |
| 02-gateways.yaml gatewayTypes | Gateway Types (Config Tool) | 11 types (AcquiSuite, BACnet, Modbus, Spinwave, FIG, MDEF, ODBC, NOAA/ECCC, Aeris, Fake, Handheld); 11 `otherGatewayTypes` rows (2 kept, 9 deleted or renamed) | Node and point parameter definitions, the four value types, predefined values. |
| 02-gateways.yaml records | Gateway Configuration (Config Tool) | 15 gateways (12 acquisition, 3 handheld), 26 nodes, 258 point bindings | Description, type, node, up to 15 node and point parameter columns. |
| 02-gateway-point-assignments.sql | SSMS preview/apply script | 258 expected bindings | Exact per-point parameter check in preview mode. |
| 02-weather-binding-migration.yaml | none (migration safeguard) | 9 legacy snapshots | Not an entry file. |
| 03-workflows-and-tasks.yaml | Config Tool > Tasks; Web > Tasks > Library; Workflow Designer (Fake only) | 11 tasks (10 built-in workflows plus the custom Fake workflow), 16 schedules (14 Interval, 1 Cron, 1 Runs once), 1 execution target (BVirtualPC) | Task defaults and schedule overrides. All schedules disabled. |
| 04-acceptance-runs.yaml | Web Task Manager Run now; Reports | 34 `records` (4 AcquiSuite plus 30 format cases) and 19 `handheldAcceptance` cases | File delivery and read-back. Only the 4 AcquiSuite files exist; 28 records say "Sample file exists: false". |
| 05-handheld-routes.yaml, .csv, 2 .txt | Web Handheld Read Types, Handheld Meter Setup | 9 read types, 192 meters, 204 registers, 10 routes, 200 starting readings (150 + 50) | Cycle/route/sequence, prompt, constant, channel, accumulator/analog/demand registers, starting readings. |
| 06-baselines.yaml | DB Admin > point Definitions | 3 baselines, 12 weather forecast associations | Two baseline algorithms; Association relationship (ReasonType V). |
| checks.sql, 06-weather-associations-check.sql | SSMS | 21 sections plus 1 query | See section 4. |

## 2. Coverage gaps

### 2a. Gateway Configuration (Config Tool)
Product editor: P:src/Apps/EEMSuite.Apps.ConfigurationTool/Views/Gateway/ (GatewayPaneView, NodePaneView, PointPaneView, GatewayParameterFieldsControl) and ViewModels/GatewayConfigurationViewModel.cs. Save: P:src/Data/Dapper/Admin/Gateway/DapperGatewayConfigurationRepository.cs. Table: P:Database/EEMSuite/Tables/GwNodes.sql.

| Gap | Where | Mark |
|---|---|---|
| **No node or point is ever disabled.** IsEnabled is 1 on every node and point; FIG/MDEF "Disabled" is 0 on every point. No `IsEnabled: 0` or `Disabled: 1` anywhere in 02-gateways.yaml. Components report "Skipped Point Count" and skip disabled nodes; nothing tests it. | R:02-gateways.yaml; P:src/Domain/EEMSuite.Domain/Manifests/Components/*GatewayManifest.cs (GatewayOutputKeys.SkippedPointCount) | READ |
| **Node flags Enable Data Gaps and Enable Late Intervals are false on every node.** `hmDataGap_Exec` only processes nodes with EnableDataGaps=1, and Stage 9 schedules "Run DataGap Calculations" (task 28), so that task has nothing to do. `hmDataLate_Report` and `rp_GatewayStatus` also read the flags. README says "late intervals off and data gaps off" on purpose, but it removes the feature. | P:Database/EEMSuite/Procs/hmDataGap_Exec.sql lines 44 and 52; hmDataLate_Report.sql; rp_GatewayStatus.sql; R:02-gateways.yaml lines 384-385; R:../stage-9-operations/04-tasks-and-workflows.yaml (sched_run_datagap) | READ |
| **Next Batch Method is "Disabled" on every node.** The editor offers a list (`BatchMethods`) backed by `hmNextBatchMethod`; one other value would prove the picker saves. | P:Views/Gateway/NodePaneView.xaml line 50; Tables/hmNextBatchMethod.sql | READ |
| **BACnet: only Object Type 0 (1 point) and 2 (9 points).** Types 1, 3, 4, 5 never used. Array Index, Comment, Property, Network Type never set. | R:02 type_bacnet; P:src/Tasks/EEMSuite.Tasks.Gateways/Bacnet/BACnetGatewayComponent.cs | READ |
| **BACnet control (write-back) commands have no data.** `GatewayControlCommandRepository` reads `ControlCommandLog_TBL` rows with Status=1 for the gateway's points and writes them; the recipe has no controllable point and no command row. | P:src/Tasks/EEMSuite.Tasks.Gateways/Bacnet/GatewayControlCommandRepository.cs | READ |
| **Modbus: one node, one point, one Register Type** ("Floating Point MSR First", address 40001). The type offers 9 register types and the 1xxxx/3xxxx/4xxxx address ranges. Multiplier 1 and Additive Constant 0, so scaling is never exercised. | R:02-gateways.yaml lines 187 and 1066 | READ |
| **FIG: Multiplier is 1 on all 195 FIG points; OffsetTimeMinutes is 0 except Ridgeline's 66 (480).** Timestamp Type is always utc; the component default (Local) is never used. | R:02-gateways.yaml; P:src/Tasks/EEMSuite.Tasks.Gateways/Fig/FIGGatewayComponent.cs line 88 | READ |
| **FIG: the seven-format cases use one point** (Cedar Row A Water Master). IgnoreCodes, EstimatedCodes, SubstitutedCodes, NormalCodes (status-code handling) are blank everywhere. | R:03 task_fig; P:Manifests/Components/FIGGatewayManifest.cs | READ |
| **MV90:** RejectStatusCodes blank; node TimeStampType only UTC (Local, STANDARD, ticks never used). | R:03 task_mv90; R:02 type_mdef | READ |
| **AcquiSuite:** Row Offset 0 only; no zipped delivery (MaxZipFiles 0, ZipFilePattern set, but no case). The Lakeview Hall node (ASQ-VED-LAKEVIEW, 2 points) has no acceptance case and no check; every AcquiSuite check hard-codes ASQ-VED-STUDENT. | R:04-acceptance-runs.yaml; R:checks.sql lines 377, 388, 399 | READ |
| **Spinwave:** one node, one folder (SCIENCE), one device, two points, channels 1 and 2 only. | R:02 gw_spinwave_science_lab | READ |
| **ODBC:** one node, one point, one query. Point parameters ODBC PtID, Multiplier, IgnoreRollovers, RolloverValue are "not read" and blank; the point has no parameters at all; task Delimiter and CommandTimeoutSeconds unset; TimeStampType Local only. | R:02 type_odbc, gw_odbc_library_historian; P:Manifests/Components/ODBCGatewayManifest.cs | READ |
| **Fake:** one point, GenerationMode sine only. constant, random, ramp, IntervalMinutes, DefaultBackfillMinutes, ReplayTimeShift and AnomalyProfileJson (spikes, gaps) never set. | P:src/Tasks/EEMSuite.Tasks.Gateways/Fake/FakeGatewayComponent.cs lines 72-82 and 156; FakeGatewayManifest.cs | READ |
| **NOAA:** WeatherProvider is NWS on all six nodes. The ECCC path (EcccStationID, EcccForecastLocationID, Canadian stations) has no data. Operation only Current and History; HistoryEndUtc blank. | P:src/Tasks/EEMSuite.Tasks.Gateways/Noaa/EcccWeatherClient.cs; R:02 type_noaa | READ |
| **Aeris Weather collector has no points** (empty transition profile; kind disabled in Gateway Runtime). BaseUrl, ClientId, ClientSecret, MaxPollsPerDay, ForecastHours, HistoryDaysBack never entered. | P:Manifests/Components/AerisWeatherGatewayManifest.cs | READ |
| **Web gateway component has no recipe data** (BaseUrl, RemoteUserId, SessionId, BackfillDays). GraphQl, Opc, WeatherUnderground, DataBridge kinds are set false and untested. README already notes "Web gateway coverage is missing". | P:src/Tasks/EEMSuite.Tasks.Gateways/Web/WebGatewayComponent.cs; R:README.md | READ |
| **Editor operations with no recipe use:** node copy (`GwNode_Copy`), bulk edit beyond the FIG bulk-select note (GatewayBulkEditFullScreenView, BulkEditDialog), point finder (GatewayPointFinderView), gateway deletion with points (GatewayDeletionDialog), moving a point between nodes. | P:Views/Gateway/*; Procs/GwNode_Copy.sql | READ (editors); INFERRED (no recipe use) |

Gateway header has only Description and Type and the recipe sets both: no gap there (P:GatewayPaneView.xaml, READ).

### 2b. Gateway Types (Config Tool)
Only the four value types are used; the one range value is Modbus Register Address `[00001..49999]`. Delimiter and display order have no entry fields (README, READ). No recipe step edits a type that is in use (rename, reorder, delete a parameter) apart from the one-off Weather type split. INFERRED.

### 2c. Tasks and schedules (Config Tool Tasks, Web Task Library)
Product: P:src/Apps/EEMSuite.Apps.ConfigurationTool/Views/Tasks/TaskPaneView.xaml and ViewModels/TaskEditorViewModel.cs; web P:src/Web/EEMSuite.Web/frontend/src/scripts/hippo/views/taskDashboard/ (taskScheduleForm.ts, taskLibraryView.ts, taskRunNow.ts, taskScheduleFit.ts); domain P:src/Domain/EEMSuite.Domain/Admin/Tasks/Models/ (ScheduleKind, ScheduleDescriptor, TaskExecutionTarget).

| Gap | Mark |
|---|---|
| Every task: group "Northlake Gateways", workflow version **Latest** (never pinned), MinInterval 300, Can schedule true, **Single schedule only false**. Task Description and TaskCode (TaskPaneView lines 95-105) are never set. | READ |
| **One execution target: BVirtualPC, Run-as blank.** No second machine, no Run-as profile, no multi-machine execution mode. | READ |
| **All 16 schedules are disabled and none has an end date.** `ScheduleDescriptor.EndUtc` exists and the form saves it; the recipe never sets it. Nothing fires on a clock, so firing, overlap and missed runs are never observed. Acceptance uses Run now only. | READ |
| Schedule kinds: Cron is used once (`0 0 3 * * ?`), always TimeZoneId 33; no other zone, no weekly or monthly cron. Runs once is used once (Fake). | READ |
| Intervals: 300, 600, 900, 3600, 86400 only. The 300-second floor's rejection path is not tried. | READ |
| Task copy, move between groups, add group, Repair built-ins (TaskEditorView) have no recipe use. Task Dashboard day/period/history/lane board and Schedule Fit (quiet-time picking) are not specified beyond "Run now". | READ (screens); INFERRED (no use) |
| Workflow Designer: only the two-node Fake workflow is authored; run history (WorkflowRunHistoryViewModel) and the power editor are not exercised. | READ |
| Task parameters never changed from defaults: BACnet LocalDeviceId 0, LocalDeviceName blank, NetworkNumber 0, timeouts 7000, MaxReadErrors 3; Modbus timeouts 5/1 s; NOAA RequestTimeoutSeconds 120; MVRS IgnoreDays 0, AdjustReadOrder false, UseSqlValues false; Neptune CreateSummary false. | READ |
| Folder overrides (Input, Working, Archive, Error, Output) are blank on every task and schedule by design; an absolute external path is never exercised. | READ |

### 2d. Handheld (Web Handheld Read Types, Handheld Meter Setup)
Product: P:src/Web/EEMSuite.Web/frontend/src/scripts/hippo/views/handheldMeterSetup/ (handheldReadTypesPanel.ts, handheldSetupPaste.ts); tables P:Database/EEMSuite/Tables/HMR_ReadType.sql, HMR_Reading.sql, HMR_Meter.sql; proc P:Database/EEMSuite/Procs/HMR_HDLData.sql.

| Gap | Mark |
|---|---|
| **Read Direction is L on all 9 read types.** The page offers L and R (`READ_DIRECTIONS = ["L","R"]`). | READ |
| **ERT Type is blank on all 9 read types and ERT ID is blank on all 204 registers.** `HMR_HDLData` emits 'K' (keyed) when ERTType is null and 'R' (radio) otherwise, so the radio branch of the route export is untested. All nine read type names say "Keyed". | READ (P:Procs/HMR_HDLData.sql line 242) |
| **Truncation Factor is 0 on all 9 read types.** | READ |
| **Tamper Code is "00" on all 204 rows; Bill Code is "-" on all 204.** | READ (05-handheld-meters.csv) |
| Meter Constant is 1 on 202 of 204 rows (40 and 3.0367 on the two CHECK registers). No constant below 1. | READ |
| Only 1 of 192 meters is disabled (Cedar Row C laundry). | READ |
| MVRS `UseReadingTimeStamp`, `UseSqlValues`, `AdjustReadOrder` and Neptune `CreateSummary` are false in the saved schedules; only the `database_previous` case flips UseSqlValues temporarily. | READ |
| Changing or re-dating a starting reading after usage exists is not specified. | INFERRED |

### 2e. Baselines and weather associations (DB Admin)
Product: P:src/Apps/EEMSuite.Apps.DatabaseAdministrator/Views/Nodes/Definitions/PointDefinitionView.xaml lines 411-455; P:Database/EEMSuite/Scripts/SeedBaselineAlgorithms.sql; Procs/BaselinePoints_Lookup.sql.

| Gap | Mark |
|---|---|
| **2 of the 9 seeded algorithms are used** (Rolling Day Type Forecast, Average of Top 5 Days). Unused: Average of 3 Days in 7, Yesterday, Last 5 Days, Last 10 Days, Other Baseline, Other Forecast, EnergyAI Baseline. | READ |
| **Display baseline is ticked on all 3.** The unticked state and the Clear baseline button are never used. | READ |
| Per-algorithm BaselineParameters (DaysBack, EquateWeekendDays, HighUsagePercent and others; defaults at calc 0) are never edited. | READ |
| No baseline can produce a known value: Student Center demand has one loaded day (2024-01-15) and "Average of Top 5 Days" needs five; the Science Center points depend on MDEF and BACnet files that do not exist. | INFERRED |
| Weather associations: 12 links, ReasonType V only; no negative case (wrong measure type), no association reason other than Weather forecast. | READ |
| No baseline on a gas, water or aggregate point, although `BaselinePoints_Lookup` accepts a registered aggregate. | READ |

### 2f. Product features in this area with no recipe data at all
- Web, GraphQl, Opc, WeatherUnderground, DataBridge collectors (READ, R:03 gatewayEnablement).
- BACnet writes (control commands), Aeris collection, ECCC weather.
- Radio (ERT) handheld reads; Read Direction R.
- Late intervals and data gaps (node flags, Data Gap and Late reports).
- Task end dates, Single schedule only, pinned workflow version, multi-machine targets, Run-as profile.
- Gateway Status report (`rp_GatewayStatus`): no Stage 3 check names it.
- Zipped input for AcquiSuite, FIG and Spinwave.

## 3. Fields present in the YAML but always empty, null or default
READ.
- 02-gateways.yaml: `Next Batch Method: Disabled` on all 26 nodes; `Enable Late Intervals: false` and `Enable Data Gaps: false` (written out on 2 AcquiSuite nodes, stated false everywhere in README); BACnet node `BBMD Address` and `BBMD UDP Port` blank on all 3 nodes; FIG `Multiplier: 1` on all 195 FIG points; FIG `OffsetTimeMinutes: 0` on 129 of 195 (non-zero only on Ridgeline's 66); Modbus `Additive Constant: 0`; the ODBC point has no parameters; NOAA ECCC identifiers blank on all 6 nodes; the Aeris profile's two nodes are empty.
- 03-workflows-and-tasks.yaml: `GatewayId: null` and `RootDirectory: null` on all 11 tasks (by design); `Run as profile: null` throughout; `RejectStatusCodes`, `IgnoreCodes`, `HistoryEndUtc`, `SummaryOutputPath`, `EventsOutputPath`, `UseReadingTimeStamp`, `LocalDeviceName` all `''`; BACnet LocalDeviceId 0 and NetworkNumber 0; MaxZipFiles 0 on four tasks; BatchKind Auto, BatchSize 20000, BackfillCutoffDays 1 on every task.
- 03 schedules: `Enabled: false` on all 16; no end date; Time zone ID 33 on all 16.
- 04-acceptance-runs.yaml: every `installed:` block (`runOn`, `workflowRunId`, `observed`) is empty on all 34 records; `Sample file exists: false` on 28.
- 05: ERTType blank 9 of 9; ReadDirection L 9 of 9; TruncationFactor 0 9 of 9; Tamper "00" 204 of 204; Bill Code "-" 204 of 204; Constant 1 on 202 of 204.
- 06: `installed.pointId` blank on all 3 baselines; Display baseline true on 3 of 3.
- 01-checkpoint.yaml: file-name template still carries `<yyyyMMdd>` beside the installed 20261005 record.

## 4. Depth of checks.sql
checks.sql has 21 `PRINT '==` sections. Beside it: 06-weather-associations-check.sql (one query, 12 rows) and the 258-binding preview in 02-gateway-point-assignments.sql.

| Class | Count | Sections |
|---|---|---|
| Asserts a known expected value (returns only discrepancy rows, or PASS/FAIL per item) | 9 | gateway_types, gateway_type_assignments, gateway_node_parameters, gateway_types_retired, gateway_types_unlisted, workflows_and_tasks (28 issue inserts: workflows, components, tasks, defaults, schedules, targets, disabled state), ridgeline_scada_day_short_points, replay_no_duplicates (cannot fail, see below), handheld_configuration (213 PASS/FAIL: 9 read types plus 204 registers) |
| Lists rows beside a PRINT that states the expectation (a person compares) | 11 | acquisuite_complete_day, gap_then_backfill, ridgeline_scada_day, ridgeline_wtg07_outage, ksuu_wind_knots, ridgeline_mdef_channels, ridgeline_aggregates, ridgeline_period_totals, baselines, gateway_points_bound, ridgeline_nodes_bound |
| Existence only | 1 | task_runs (lists TaskRun rows with Succeeded and ErrorCount; no expected count) |

Notes, all READ:
- `replay_no_duplicates` cannot fail. It looks for points where COUNT(*) <> COUNT(DISTINCT UTCTimeStamp), but (PtID, UTCTimeStamp) is the archive's primary key (R:checks.sql lines 382-390; 04's own note says so). It proves nothing about a replay.
- `gateway_points_bound` and `ridgeline_nodes_bound` list counts; the expected numbers (258 points, 26 nodes, 73 Ridgeline points) are only in the PRINT text.
- Point-level parameters (DeviceID, ObjectID, Register Type, Point Alias, Row Number, Multiplier, OffsetTimeMinutes) are not asserted in checks.sql at all. Only the separate assignments script asserts them.
- `baselines` does not assert the algorithm name or that Display equals 1; it lists them.
- 25 of 34 acceptance records have no `Check:` and no SQL section: mdef_valley_electric, mv9_helios_generation, bacnet_thermal_plant, noaa_ksac, noaa_observation_history, noaa_ksmf, spinwave_science_lab, the seven fig_cedar_row_water_* cases, modbus_chiller, odbc_library_historian, fake_smoke, neptune_cedar_row_b_water, mvrs_student_center_gas, fixed_network_submeters, neptune_cedar_row_submeters, neptune_cedar_row_c, neptune_irrigation, mvrs_facilities_rounds, hmr_events_publish. Nine records have one (the four AcquiSuite and five Ridgeline).
- No check reads HMR starting readings, handheld acceptance results, HMR log events, the Fake gateway's 96 readings, ODBC cursor state, or any named task's last run.

What the stage enters that no check covers: the Lakeview Hall AcquiSuite node; Fake data; NOAA current and history data; every FIG format; Spinwave; Modbus; ODBC; BACnet readings; fixed-network submeter data; schedule start times (kind, interval and cron are asserted, start is not); starting readings; baseline algorithm identity; HMR event publishing; the 126-meter submeter batch.

## 5. Known expected VALUES
The recipe's rule is "covered means a known value renders".

Has known values (READ, R:04-acceptance-runs.yaml):
- acquisuite_gap (88 per point, 176 stored, 1,780 kWh, 120 kW, gap 12:00-13:45), acquisuite_backfill (96, 2,020, 120), acquisuite_complete_day (96 on the file's day; 95 and 2,010 on EEM's day), acquisuite_replay (unchanged).
- ridgeline_scada_july_day (144 per point, 9,504 stored, first and last UTC stamps, stored local stamps), ridgeline_wtg07_outage (10,224 per point, state 2, zero kWh), mdef_ridgeline_interconnection (2,496,612 / 4,428 / 858,948 and 418,836 / 46,920 / 131,664), ridgeline_aggregates (144 and 96 rows; July tie-out 2,251,384).
- Handheld cases carry expected usage (for example 2,429.36 for the CHECK gas meter, line 761).

Counts only, no values: mdef_valley_electric (96, 92, 100 per day), spinwave_science_lab (144 per day), all seven FIG formats ("24 values", no list), fixed_network_submeters (24 per day; sum below the master), fake_smoke (96 readings between 12 and 36, no sum), neptune_cedar_row_submeters (usage equals read difference).

No expected value at all: mv9_helios_generation (shape words), bacnet_thermal_plant (poll-time readings; history sums 180,860 and 58,640 ton-hours are quoted but nothing loads them, see section 6), noaa_ksac, noaa_ksmf, noaa_observation_history (live public data cannot have a fixed value; a recorded fixture would), noaa_ksuu_wind_knots (order of magnitude), modbus_chiller, odbc_library_historian, hmr_events_publish, the 3 baselines, the 12 weather associations (structure only).

## 6. Internal inconsistencies (all READ)
1. 04 `mdef_ridgeline_interconnection` (line 546) and the node note in 02-gateways.yaml (line 502) say the Ridgeline MDEF node is "TimeStampType local". The saved node parameter is UTC (02, checks.sql gateway_node_parameters, README).
2. 02-gateways.yaml notes say Ridgeline adds "72 points in all" and NOAA-KSUU has "3 points". The node has 4 (a Dew Point was added) and `ridgeline_nodes_bound` says 73. The chapter repeats "Ridgeline's 72 points" (chapter line 397).
3. Chapter intro says "sixteen gateway profiles" and "two handheld upload formats / the two handheld gateways"; later it says "All 15 gateway profiles". YAML has 15, with three handheld gateways.
4. Chapter says "The remaining 26 format cases"; 04 has 34 records, 4 of them AcquiSuite, so 30 remain.
5. Chapter finding 21 says NOAA and Aeris Weather have "no matching row in GWVendor", and chapter line ~45 says "Weather Gateway, which NOAA and Aeris Weather share". 02 shows both types created separately (type 100094, 100092).
6. 03 notes say the handheld gateway IDs "remain unresolved until Step 5"; the same file's schedules use GatewayId 16, 17, 18 and the README says they were saved November 5.
7. 03 `sourceService.Required node changes` still shows "Verified current value: Local (2026-11-03)" for all five MDEF/MV9 nodes; they are UTC now.
8. 04 `ridgeline_scada_july_day` "Before the run" cites a check named `vendor_setup`; checks.sql has no such section (it is `gateway_types`).
9. `task_fake` default `AllowSyntheticData: false`, custom workflow default `true`, schedule sets true. Harmless, but the default contradicts the workflow.
10. 04 `bacnet_thermal_plant` says 2024-2025 history "comes through a file path, not the poll" and must reproduce the Thermal Plant bills, but no gateway, format, task or case loads that file. The expected sums have no path in.
11. 02-gateways.yaml tells the reader to select IsEnabled = 1 on nodes and points "wherever the component reads that parameter", but most records omit it (BACnet nodes; AcquiSuite, BACnet, Spinwave, Modbus, Fake points). The generator adds it (the SQL data carries "1"), so what a person reads differs from what is checked.
12. 02-gateways.yaml header says "15 acquisition profiles"; README and chapter say 12 acquisition plus 3 handheld.
13. Stage 4 `07-rate-tests.yaml` line 577 depends on 4,464 ten-minute July rows on Ridgeline Farm Generated kWh 10m; Stage 3 only specifies one SCADA day, and all sample files are "false".
No dangling gateway, schedule or task key: every `gw_`, `schedule_` and `task_` key used in 04 exists in 02/03 (script check). Channel keys in 04 missing from 02 (`ch_rcu_*`, `ch_sgu_*`, `ch_rwl_wtg0N_*`) are in 05 or are pattern expansions.

## 7. Effects of today's Stage 4 rates rework on this stage
Stage 3 names no rate, no rate schedule and no dollar amount (searched all Stage 3 files for NL-, VED-, SGU-, tariff, dollar signs: only quantities and `ved_ridgeline_generator_*` bill ids). The Stage 4 schedule renames do not touch Stage 3, whose "schedules" are task schedules. The effects are indirect, through data Stage 3 must supply:
1. **Valley Electric three-period TOU (VED-TOU-GS, VED-TOU-PRI)** prices interval kWh/kW from Stage 3's MDEF and AcquiSuite points (Science, Recreation, Student Center, Lakeview, Central Plant). With part-peak windows 8-12 and 18-22, the AcquiSuite interval-start stamp (95 vs 96 rows, PRODUCT FINDING 73) moves energy across a period boundary, and the MDEF node UTC/Local contradiction (section 6 item 1) would too. INFERRED.
2. **Central Plant main meter now on VED-TOU-PRI** (READ, 06-rate-assignments.yaml line 177): its MDEF points `ch_ved_central_plant_kwh_15m` and `kw_15m` have no sample file, so that tariff has no Stage 3 interval data.
3. **Stage 4 rate test waits on Stage 3 data** (READ, 07-rate-tests.yaml line 577): needs July Ridgeline Farm Generated kWh 10m for the month; Stage 3 specifies one day.
4. **Helios 2% escalator and 2026 price step**: the 5 Helios MV9 points have no file, and the history windows quoted stop at 2025 or 2026-01-01, so a 2026 step has no interval data. INFERRED.
5. **Valley Electric bill cycle on the 5th** is already baked into Stage 3's Ridgeline sums (2024-07-01 to 2024-08-04); any bill-period change in the rework must still match them. READ.
6. **Per-meter prices (lighting, ERUs, thermal plant fixed share)**: no Stage 3 dependency except the Thermal Plant BACnet history (section 6 item 10).
7. **River City meter and line size options; water meters with three rows**: the water masters, deduct meters and Cedar Row water submeters are Stage 3 handheld (Neptune) and FIG sources; their usage must exist for the water rates. The 4 DEDUCT meters feed a sewer credit. INFERRED.
8. **SGU-GN-1 now on nine gas meters** (READ, 06-rate-assignments.yaml lines 211-283): the Student Center Kitchen Gas (MVRS SCGAS) and Central Plant Boiler Gas (CHECK, constant 3.0367) meters are Stage 3's. The gas rate prices by the season of the bill's end date (coverage review), so the February 2024 probe readings land in one season. INFERRED.
9. **SWGR route registers are named On-Peak, Mid-Peak, Off-Peak kWh** (05-handheld-routes.yaml ~line 597); Valley Electric now reads Peak, Part-Peak, Off-Peak. Naming only; no rate reads the SWGR registers. INFERRED.
10. **Rate Lab ratchet** needs 12 months of interval data with a summer peak; 08-rate-lab.yaml line 359 says to "flag this to whoever builds Stage 3's interval generator". Stage 3 has no lab-meter gateway or history. READ.
11. **Stage 7 tenant bills** on NL-RES-Tiered and NL-STEP-Demand (moved to the Rate Lab) use the Cedar Row submeters Stage 3 feeds (FIXEDNETWORKS electric 124, Neptune water 126). No Stage 3 file changes. INFERRED from the Stage 4 coverage review.

## 8. Running-system scenarios worth adding to Stage 12
Stage 12 has four scenarios, all handheld (01-handheld-meter-replacement, 02-switchgear-kw-to-mw, 03-fix-cedar-row-c-route, 04-demand-read-after-energy). Nothing for gateways, tasks or baselines.
1. AcquiSuite logger replaced (new serial): edit node Serial Number; breaks: files with the new serial go unmatched into Error (serial is case-sensitive), a gap in the data.
2. Source changes timestamp convention or zone after history is loaded: edit MDEF/FIG TimeStampType or OffsetTimeMinutes; breaks: reloads overwrite rows in place (key PtID + UTCTimeStamp), shifting history with no error.
3. Daylight-saving crossing on live schedules: 2025-03-09 (92 intervals) and 2025-11-02 (100) through MDEF, Spinwave, ODBC (Local) and the NOAA 03:00 cron; breaks: missing or doubled interval, cron skipped or doubled.
4. New meter appears in an existing FIG/fixed-network file before it is bound: breaks: Unknown Alias warning and lost rows until the archived zip is replayed.
5. Late file for a closed month with EnableLateIntervals on: breaks: Late Intervals report, bill validation re-run, baseline recompute.
6. Device renumbered or moved (BACnet device id, Modbus IP/unit, BBMD added for a remote subnet): breaks: failed node count, MaxReadErrors, partial polls leaving gaps.
7. Operations edit a live schedule (interval 900 to 300, new cron, end date, second machine, Run-as profile) then re-enable: breaks: overlapping runs, run on the wrong machine, a schedule that never fires after its end.
8. NOAA station change or provider switch to ECCC: breaks: history reconciliation overwrites the old station's rows under the same point; forecast association left pointing at the old forecast.
9. Retire a gateway or move points between nodes (delete the Aeris profile, copy node, bulk edit 60 points): breaks: points on no node, tasks that name a deleted GatewayId.
10. Change a baseline algorithm or replace its measured meter after history exists: breaks: stale generated baseline rows; Baseline For list silently empty when the new measured point has no gateway.

## 9. What I could not check
- No database was queried and nothing was built or run. Installed state (task IDs, node IDs, saved values) is as the recipe and README claim.
- I did not open all 19 handheld acceptance cases or the 05 route records line by line, and did not recompute Cedar Row C or switchgear arithmetic.
- I did not read the bodies of the BACnet, Modbus, Spinwave, Neptune, MVRS, MV90, ODBC and Web components. Those gaps come from manifest parameter keys, the gateway type YAML and spot reads; "the component supports X" is READ only where a file and line are named, otherwise INFERRED.
- The web schedule form (taskScheduleForm.ts, 760 lines) and taskLibraryView.ts (1,119 lines) were skimmed for fields, not read in full; fields may exist that I did not see.
- I did not verify AcquiSuite sample file contents or sha256 values, the Ridgeline sums, or the VEE scenario research PDF.
- The generated JSON blocks inside checks.sql (about 16K, 62K and 163K characters) were sampled, not diffed against the YAML.
- Stage 7 impact of the moved NL- rates is taken from the Stage 4 coverage review, not re-read in Stage 7.
