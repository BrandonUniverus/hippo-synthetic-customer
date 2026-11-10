# Northlake weather catch-up: Stage 2 to Stage 3

These are setup artifacts for `BVirtualPC / EEMSuite_Northlake`. They do not install or change the EEM product.

[Northlake VEE scenario research](Northlake-VEE-Scenario-Research.pdf) proposes controlled faults, valid operational events, late readings and correction scoring for the source bundle. This is research for future implementation; it does not enable fault injection or change the setup checkpoint below.

**Live audit, November 4, 2026:** Stage 1 passes all 1,222 expected records, including 716 permissions, 91 groups, 67 memberships and 23 users. Stage 2 passes all 2,210 expected records with 552 points. Run these UTF-8 SQL files with `sqlcmd -f 65001` (or open them as UTF-8 in SSMS); reading the degree-symbol unit names as an ANSI code page produces four false Stage 2 mismatches.

The November 4 gateway check confirms all 258 direct point-to-gateway bindings match the current recipe with zero blocking issues. This includes the ten corrected BACnet device IDs and all three nodes' blank BBMD fields, saved through Configuration Tool. **TimeStampType is now UTC** on **MV90-MDEF-VED-SCIENCE (5), MV90-MDEF-VED-RECREATION (6), MV90-MDEF-VED-PLANT (7), MV90-MV9-HELIOS (9), and MV90-MDEF-VED-RIDGELINE (8)**, saved through Configuration Tool and verified in the database. This matches the source service's MDEF/MV9 timestamps; point time zones remain Pacific. The shared FIG task default uses `TimeStampType=utc`.

The earlier November 4 check confirmed an empty interval archive and the Stage 3 entry backup. Stage 3 takes no second, configured-empty backup (decided November 5): Northlake is backed up later, once it works end to end, and the Step 4 acceptance runs use an order that needs no restore. All **eleven reusable task definitions** are now saved, including Neptune 1067 and MVRS 1068. Thirteen intended disabled schedules are configured; the three handheld schedules remain pending their Step 5 gateways. The four duplicate per-profile tasks and their old schedules were removed through Configuration Tool after confirmation. The live workflow/task checker passes all configured tasks, defaults and schedules, reporting only six expected prerequisite rows: the three missing handheld gateways and their three schedules. The custom Fake Gateway workflow remains 28, version 1. No collection or task run was started during this setup. Stored-configuration checks do not prove successful ingestion.

The weather target is four observations and six forecasts at each of KSAC, KSMF and KSUU. Observations cover temperature, dew point, relative humidity and wind speed. Forecasts add wind direction and precipitation probability. Probability is a percentage, not a rainfall-amount point. The existing KSMF temperature forecast remains Fahrenheit; KSMF observed temperature remains Celsius.

## 1. Import the Stage 2 point definitions

Use the existing Stage 2 My Imports points import with [04-points.xlsx](../stage-2-hierarchy/04-points.xlsx), sheet **Points**. It has **401 data rows** and the same ten columns as before. Import the complete sheet using the existing exact-match/update process; do not create a second copy of existing points.

The completed catch-up created **21 points** (17 forecasts and four observations) and corrected four existing measurement types:

- KSAC, KSMF and KSUU Wind Speed: **Wind Speed**.
- KSUU Dew Point: **Dew Point**.

The four new observations are KSAC Dew Point, KSMF Dew Point, KSMF Relative Humidity and KSUU Relative Humidity. Keep existing point names, identities, units, bindings and data. Only the three observed temperature points have a Degree Days index. Forecasts do not have an index.

The workbook contains point definitions only. There are no forecast-association columns or association import rows, and no new My Imports procedure is required.

Run [Stage 2 checks.sql](../stage-2-hierarchy/checks.sql) against **EEMSuite_Northlake**. The expected point counts are 401 entered, 140 generated (134 accumulator deltas and six HDD/CDD) and 11 aggregates: **552 total**. Resolve point-definition failures before the gateway changes. The existing 15 building-to-weather-station assignments remain in place.

## 2. Update the Weather Gateway type and nodes through the app

In the gateway YAML, each point's **Description** is now its exact Stage 2 point description. **Company** and **Meter** identify where to find it in the picker; these are lookup details, not gateway parameters. For example, select **KSAC Dew Point** under **KSAC Sacramento Executive Airport** (meter number **KSAC**) in **Northlake University**, then enter its **Point Parameters**. The channel key is the source-model identifier, not a point name to search for.

The same lookup fields are provided for all gateways. Apartment and turbine templates use an exact point description plus a **Meter pattern** for each unit/turbine. The three handheld gateways have no nodes and no points: their 192 meters and 204 registers, each register with its **Reading Point** (the register) and **Consumption Point** (its Delta, or a demand point), are listed in [05-handheld-routes.yaml](05-handheld-routes.yaml) and entered in Step 5. Stage 2 does not specify separate report names; no point or report name needs to be changed for this guide.

For NOAA, **Gateway binding** is the gateway/node to attach that existing point to. **Point Parameters** contains the literal settings the collector reads. These are values to enter, not descriptions of the point's measurement type.

For **KSAC Dew Point**, the complete connection is:

| Where to set it | Field | Value to enter/select |
|---|---|---|
| Gateway Configuration | Gateway | Northlake NOAA Weather |
| Gateway Configuration | Node | NOAA-KSAC |
| Node parameters | IsEnabled | 1 (Enabled) |
| Node parameters | WeatherKind | Observation |
| Node parameters | StationID | KSAC |
| Node parameters | GhcnStationID | USW00023232 (for history) |
| Points on that node | Existing point | KSAC Dew Point, on meter KSAC Sacramento Executive Airport |
| Point parameters | IsEnabled | 1 (Enabled) |
| Point parameters | Measurement | DewPoint |
| Point parameters | OutputUnit | Fahrenheit |

Select the gateway and node, add/select the existing point under that node, enter those point parameters, and save. The collector uses `StationID=KSAC` to request station observations; `Measurement=DewPoint` selects the response's dew-point reading and `OutputUnit=Fahrenheit` requests conversion to the point's unit. Temperature instead uses `Measurement=Temperature`; humidity uses `RelativeHumidity`; wind uses `WindSpeed`. The other exact station/point settings are alongside each point in the YAML. If the newer Weather Provider field appears, select **NWS**, the default for these US stations.

The collectors now require **separate gateway types**. Follow the `type_noaa` and `type_aeris` definitions in [02-gateways.yaml](02-gateways.yaml). The gateway name identifies an instance; the gateway type defines the fields shown on its nodes and points.

| Gateway instance | Assigned gateway type |
|---|---|
| Northlake NOAA Weather | NOAA / ECCC Weather Gateway |
| Northlake Aeris Weather, while it still exists | Aeris Weather Gateway |

First, create or select **NOAA / ECCC Weather Gateway** in Gateway Types. Give it the following fields and the exact predefined values listed in the YAML:

| Level | Column | Label | Type |
|---|---:|---|---|
| Node | 1 | IsEnabled | Boolean |
| Node | 2 | WeatherKind | String |
| Node | 3 | StationID | String |
| Node | 4 | GhcnStationID | String |
| Node | 5 | WeatherProvider | String |
| Node | 6 | EcccStationID | String |
| Node | 7 | EcccForecastLocationID | String |
| Point | 1 | IsEnabled | Boolean |
| Point | 2 | Measurement | String |
| Point | 3 | OutputUnit | String |

Assign **Northlake NOAA Weather** to this type before changing the former shared type. The installed editor locks a gateway type while nodes or points remain. The approved November 1 rebuild temporarily unassigned seven point links, deleted old nodes 13/14, switched the type, and recreated all six NOAA nodes. The underlying points and readings were preserved. On all six NOAA nodes, select `WeatherProvider=NWS`; leave the two ECCC identifiers blank. NOAA points must show `Measurement` and `OutputUnit`, not `WeatherTypeName`.

Then rename the former shared **Weather Gateway** type to **Aeris Weather Gateway**, or select the existing type with that name. Preserve or restore the following Aeris fields; if the earlier instructions led you to replace them with NOAA fields, restore the Aeris layout after moving NOAA to its own type:

| Level | Column | Label | Type |
|---|---:|---|---|
| Node | 1 | IsEnabled | Boolean |
| Node | 2 | WeatherType | String |
| Node | 3 | StationID | String |
| Node | 4 | BackFillDays | Integer |
| Point | 1 | IsEnabled | Boolean |
| Point | 2 | WeatherTypeName | String |
| Point | 3 | PointType | String |

The **Northlake Aeris Weather** profile now has no points and uses this Aeris type. Its two empty nodes remain as a transition record. The obsolete `history` predefined choice was removed after confirmation; only `observation` and `forecast` remain. Retain the separate Aeris type afterward; do not reuse it for NOAA. The old ambiguous type name **Weather Gateway** no longer remains.

Run the `gateway_types`, `gateway_type_assignments` and `gateway_types_retired` sections of [checks.sql](checks.sql) after the type split. Each should return no discrepancy rows. The assignment check requires NOAA's own type and checks the Aeris profile's type only while that profile exists.

Gateway 7 is now **Northlake NOAA Weather**. These are the saved nodes:

| Node | Installed ID | WeatherKind | StationID | GhcnStationID | Points |
|---|---|---|---|---|---:|
| NOAA-KSAC | 27 | Observation | KSAC | USW00023232 | 4 |
| NOAA-KSUU | 28 | Observation | KSUU | USW00023202 | 4 |
| NOAA-KSMF | 29 | Observation | KSMF | USW00093225 | 4 |
| NOAA-KSMF-FORECAST | 30 | Forecast | KSMF | blank | 6 |
| NOAA-KSAC-FORECAST | 31 | Forecast | KSAC | blank | 6 |
| NOAA-KSUU-FORECAST | 32 | Forecast | KSUU | blank | 6 |

Set **IsEnabled = 1** explicitly on these nodes. Keep **Next Batch Method = Disabled** and late intervals off. Data gaps are on for NOAA-KSAC and NOAA-KSMF (added 2026-11-10, see the node flag notes in 02-gateways.yaml) and off on the other four. These flags configure the nodes; the workflow tasks must remain disabled until Step 4. The binding script requires the gateway type, node names and required node values to match before it can apply.

## 3. Connect the weather points

To configure through the app, follow each point's **Gateway binding** and enter its **Point Parameters**, then save. All 30 NOAA points list their destination and explicit enable flag. That completes the binding without running a bulk assignment script.

The SQL path below is an alternative to manual configuration. The current installation is already configured: leave `@Apply = 0`; no assignment write is needed. Historical parameter snapshots live separately in [02-weather-binding-migration.yaml](02-weather-binding-migration.yaml); they are inputs to the migration safeguard, not current values to enter in the editor. Points already configured correctly through the app appear as **ALREADY CORRECT**.

Open [02-gateway-point-assignments.sql](02-gateway-point-assignments.sql) in SSMS on **BVirtualPC / EEMSuite_Northlake**. For this catch-up, set its three declarations to:

```sql
DECLARE @Apply bit = 0;
DECLARE @ProfileKey nvarchar(128) = N'gw_noaa_ksac_observations';
DECLARE @AllowLegacyWeatherMigration bit = 1;
```

Run the whole file. The current weather preview is **30 ALREADY CORRECT with zero blocking issues**. Before the November 1 catch-up it was nine READY TO MIGRATE and 21 READY TO ASSIGN. Partially completed work can instead appear as ALREADY CORRECT. The migration recognizes only the nine exact old weather gateway/node/parameter snapshots in the separate migration file, including the three KSMF points previously under **Northlake Aeris Weather**. Unexpected values remain blockers.

After reviewing the resolved points, old and new parameters and zero blockers, change only `@Apply` to `1` and run the whole file again. It uses `GwPtParam_Save` inside a checked transaction. It does not create points or associations. It verifies the saved bindings and preserves other point-definition fields and aggregate memberships.

Then set `@Apply = 0`, `@ProfileKey = NULL` and `@AllowLegacyWeatherMigration = 0`, and run it again. The full result should be **258 ALREADY CORRECT, zero blockers**. Leave the saved script in preview mode.

The empty **Northlake Aeris Weather** profile and its old nodes may be retired through the app after deletion confirmation; their removal is optional for this transition checkpoint. Do not delete or recreate its former points, especially KSMF Forecast Temperature. The target has 12 acquisition profiles with 26 typed nodes, plus the three handheld gateways that Step 5 creates on the parameterless Handheld Meter Reading Gateway type, with no nodes.

## 4. Later in Stage 3 Step 6: create the 12 forecast associations through the app

Follow `weatherAssociations` in [06-baselines.yaml](06-baselines.yaml). Open each **observed** point in DBAdmin, choose **Relationships > Associations**, select **Weather forecast**, choose the matching forecast, and save.

| Station | Observed point | Forecast point |
|---|---|---|
| KSAC | KSAC Outside Air Temperature | KSAC Forecast Temperature |
| KSAC | KSAC Dew Point | KSAC Forecast Dew Point |
| KSAC | KSAC Relative Humidity | KSAC Forecast Relative Humidity |
| KSAC | KSAC Wind Speed | KSAC Forecast Wind Speed |
| KSMF | KSMF Outside Air Temperature | KSMF Forecast Temperature |
| KSMF | KSMF Dew Point | KSMF Forecast Dew Point |
| KSMF | KSMF Relative Humidity | KSMF Forecast Relative Humidity |
| KSMF | KSMF Wind Speed | KSMF Forecast Wind Speed |
| KSUU | KSUU Outside Air Temperature | KSUU Forecast Temperature |
| KSUU | KSUU Dew Point | KSUU Forecast Dew Point |
| KSUU | KSUU Relative Humidity | KSUU Forecast Relative Humidity |
| KSUU | KSUU Wind Speed | KSUU Forecast Wind Speed |

These are `ReasonType = V`, `RelationshipKind = Association`. Both endpoints stay independent gateway points. The six wind-direction and precipitation-probability forecasts stay unpaired because the collector has no matching observation inputs.

Run [06-weather-associations-check.sql](06-weather-associations-check.sql): expect **12 rows, all Configured**. This checker is read-only. Also run the gateway-type and gateway-binding sections of [Stage 3 checks.sql](checks.sql). Workflow, schedule, baseline, backup and ingestion sections describe later Stage 3 work and need not pass before those steps are completed.

## 5. Stage 3 Step 3 workflows and tasks

Use [03-workflows-and-tasks.yaml](03-workflows-and-tasks.yaml) as the entry guide. Its `tasks` section defines **one reusable task per workflow**; its `schedules` section supplies the configured gateway, root directory, format or operation, timing and source ID for each use of that task. Task defaults are starting values, not fixed collector configuration.

1. In **Configuration Tool > Tasks > Northlake Gateways**, create the reusable task, choose the current workflow version, and enter `Default parameters`. Leave GatewayId, RootDirectory and other schedule-specific defaults blank. Keep all parameter fields visible, the minimum interval at 300 seconds, Can schedule enabled and Single schedule only disabled.
2. Keep or add one execution target for **BVirtualPC** (machine 2), with Run as profile blank to inherit the Workers service account. The installed target editor exposes Machine and Run as, not a gateway selector. The collector selects its gateway from the effective schedule parameter; legacy gateway metadata on an existing target does not need to be cleared.
3. In **Web > Tasks > Library**, select that task and add each named schedule. Enter its `Parameters` as schedule overrides, selecting GatewayId by the supplied gateway name. Choose a current/future start in Pacific and leave it disabled until Step 4.

**Required is a run-time requirement.** It does not require a value in the task-default row. A required GatewayId, Format, Operation or LocalIpAddress can be blank in Configuration Tool and supplied by the schedule. The checker validates stored task defaults separately from effective scheduled inputs; it also requires the explicit gateway/root selections and any other overrides listed in each schedule. It never substitutes one schedule's values for another's.

Configure each file schedule with **RootDirectory only** for its workspace location. The shared FileWorkspace code resolves omitted or blank folder overrides to `RootDirectory\Input`, `Working`, `Archive`, `Error` and `Output`; a relative override is resolved under the root and an absolute override can point elsewhere. The workflow still needs its other non-folder inputs, such as format and timestamp interpretation. Keep the optional folder overrides blank unless a specific external location is required. FIG can also inherit InputDirectory, ArchiveDirectory and ErrorDirectory from component configuration; leave those defaults unset for the same root-only layout.

Northlake keeps an explicit RootDirectory for predictable delivery and checkpoint locations. A blank root does not always fail: installed gateways derive `InstanceDataPath\TaskData\<family>\<GatewayId>`, and the installed standalone FileWorkspace component derives `InstanceDataPath\TaskData\FileWorkspace\<TaskId>`. Outside that context an InputDirectory can supply the fallback workspace; otherwise execution requires a root. The core FileWorkspace path resolver itself rejects a blank root.

**Live consolidation completed, November 4:** all eleven reusable task definitions and thirteen currently possible disabled schedules are saved. The four obsolete task/schedule pairs are removed. Schedule IDs below are `TaskSchedules.TaskScheduleId`; item IDs are `TaskItems.TaskItemID`.

| Reusable task | Saved task ID | Saved schedules and remaining prerequisites |
|---|---|---|
| Northlake AcquiSuite Gateway | 1054 | Campus Loggers: schedule 15, item 3 |
| Northlake MV90 Gateway | 1055 | VED MDEF: 16 / item 4; Helios MV9: 28 / item 16 |
| Northlake NOAA Gateway | 1057 | Current Weather: 18 / item 6; Archive Reconciliation: 29 / item 17 |
| Northlake Spinwave Gateway | 1059 | Science Center: 20 / item 8 |
| Northlake FIG Gateway | 1060 | FIG File Imports: 21 / item 9; Fixed Network: 30 / item 18; Ridgeline SCADA: 31 / item 19 |
| Northlake Modbus Gateway | 1063 | Thermal Plant: 24 / item 12 |
| Northlake ODBC Gateway | 1064 | Library Historian: 25 / item 13 |
| Northlake Fake Gateway | 1065 | Smoke: 26 / item 14 |
| Northlake BACnet Gateway | 1066 | Thermal Plant: 27 / item 15 |
| Northlake Neptune Gateway | 1067, created with blank gateway/root defaults | Neptune Water Upload: 36 / item 24 (gateway 16); Cedar Row Submeter Water Route: 38 / item 26 (gateway 18) |
| Northlake MVRS Gateway | 1068, created with blank gateway/root defaults | MVRS Gas Upload: 37 / item 25 (gateway 17) |

The retained tasks now use their reusable names and default parameters. The named disabled schedules are saved on the appropriate reusable task with the complete overrides from YAML. Keep the existing BVirtualPC execution target and inherited service account. Do not recreate a target just to clear hidden legacy gateway metadata: gateway components load the runtime from the effective scheduled GatewayId. The checker validates the target's task ownership, machine and account separately from that scheduled gateway selection.

Duplicate tasks **1056, 1058, 1061 and 1062** and old schedules **17, 19, 22 and 23** are removed. Their replacement schedules are **28, 29, 30 and 31**, respectively. Redundant InputDirectory, ArchiveDirectory and ErrorDirectory values are cleared from Spinwave and the three FIG schedules and from the retained task defaults; WorkingDirectory is blank. Each schedule keeps its explicit RootDirectory. All schedules remain disabled, with their existing Pacific timing. The checker resolves them by exact schedule name and verifies the reusable task binding.

The final target is **11 tasks and 16 schedules**. `MvrsGateway` already chains `MVRSGateway → IntervalDataPublish → HmrEventsPublish`; do not add another HMR publisher. For the seven generic FIG acceptance formats, use a run override or a temporary disabled schedule of the same FIG task; do not change shared task defaults. The Fake workflow includes its exact parameter definitions, values and six connections. Its inclusive range is **2024-01-01 08:00Z through 2024-01-02 07:45Z**, exactly 96 quarter-hours on January 1 Pacific.

The installed web date/time editor interprets timezone-free defaults from Configuration Tool as local time. Saving the unadjusted NOAA history start shifted it from 08:00Z to 16:00Z. The saved schedule overrides are corrected and verified: NOAA `HistoryStartUtc=2024-01-01T08:00:00.0000000Z`; Fake `StartTimestamp=2024-01-01T08:00:00.0000000Z` and `EndTimestamp=2024-01-02T07:45:00.0000000Z`. In the Pacific web editor these show January 1, 2024 at **12:00 AM**, **12:00 AM**, and **11:45 PM**, respectively. Check the stored UTC values again after editing those date fields; leave the YAML's UTC boundaries unchanged.

The Fake workflow saved with zero validation errors. Its initial warning reported that the Fake collector was disabled by `GatewayRuntime:ObjectEnablement`. The user has now saved **Profile Manager > Local Configuration > BVIRTUALPC > Gateway Runtime > GatewayRuntime > Object Enablement**, and a November 4 read-back of the Northlake local configuration confirms that every collector required by the recipe is enabled, including BACnet and Fake. The saved map also enables Web and omits the recipe's disabled entries. Profile Manager requires administrator privileges, so the user made this save manually; the current Computer Use helper cannot send input to its elevated window. The editor's validation warning has not been refreshed since the save. Collector enablement and schedule activation are separate settings; keep all Northlake schedules disabled.

NOAA uses one reusable task with two schedules on gateway 7. **Current Weather** supplies `Operation=Current` every 900 seconds. **Archive Reconciliation** supplies `Operation=History` and `HistoryStartUtc=2024-01-01T08:00:00Z`, inherits `ArchiveDelayDays=3`, and uses Cron `0 0 3 * * ?` for 03:00 Pacific. Both stay disabled until their acceptance prerequisites are met.

The three handheld gateways (16, 17 and 18) and their schedules (36, 37 and 38) were saved on November 5. The companion BACnet source is now running on **BVirtualPC Ethernet 3, 172.21.29.4**. A probe using the real collector client discovered all three devices and successfully read all ten configured objects; it did not execute an EEM workflow or publish readings. [The BACnet source bindings](../../services/bacnet/bindings.json) define the device/object mapping.

| BACnet setting | Correct local value |
|---|---|
| Schedule LocalIpAddress | `172.21.29.4`; recheck if the host network changes |
| Default UdpPort | `47808` for local discovery |
| Science device ID | `530101`, replacing `5301001` on both points |
| Recreation device ID | `530102`, replacing `5301002` on both points |
| Plant device ID | `530103`, replacing `5301003` on all six points |
| All three nodes' BBMD Address and BBMD UDP Port | Blank; local discovery does not use a BBMD |

The original device IDs exceeded the BACnet device-instance range. The emulator advertises unicast endpoints on ports 47820, 47821 and 47822; leave the discovery port at 47808. All object IDs, object types, existing points and readings stay unchanged. The corrected device IDs and blank BBMD fields are saved on live gateway 6 and match the YAML and generated checks. Task **1066** uses the latest `BacnetGateway` workflow and a BVirtualPC target. Its hourly schedule **27** (task item **15**) is disabled and supplies gateway 6 and the verified local interface. The reusable task's gateway, root and interface defaults are blank. The main HTTP source service does not provide the Modbus, ODBC or handheld endpoints.

Use the [BACnet startup and verification runbook](../../services/bacnet/README.md) to restart or check the source. The verified local deployment runs natively on Windows so BACnet broadcasts share the Workers network; the container package targets Linux host networking. The source supplies the last completed hour's energy/volume and quarter-hour pressure. The collector stamps these scalar values at polling time, and the hourly task does not create a complete 15-minute pressure history. Verify those timing and sampling boundaries during acceptance before using the values for reconciliation.

For the source service at `http://localhost:18081`, use `/catalog.json` to find the current release and its `contracts/source-model.json`. Its 215 file inputs require the five MV90 node changes above and effective `TimeStampType=utc` on all three FIG schedules, including generic FIG and FIXEDNETWORKS; the shared FIG task supplies that default. No delivery or collection was started by this setup; preserve the source subfolders such as Spinwave's `SCIENCE` when delivering after the checkpoint.

Run the batch between `BEGIN WORKFLOW CHECKS` and `END WORKFLOW CHECKS` in [checks.sql](checks.sql), or run the full checker and assess each section separately. It checks current workflow components/connections, eleven reusable tasks and their stored defaults, sixteen named schedules and their effective parameters, machine-only execution targets, explicit schedule overrides and obsolete duplicate tasks. Its `@RequireDisabledSchedules = 1` default expects every schedule disabled until Step 4. Blank required task defaults are allowed; a missing required schedule input is reported.

## Repository validation and regeneration

The SQL data blocks and workbook rows are derived from the YAML. From this repository root, check them without connecting to a database:

```powershell
python -B -m generators.stage_check_data --check
python -B -m generators.gateway_assignments --check
python -B -m generators.weather_associations --check
python -B -m generators.stage2_workbooks --check
python -B -m unittest generators.tests.test_stage2_hierarchy generators.tests.test_gateway_assignments generators.tests.test_weather_associations generators.tests.test_stage3_workflows
```

If the recipe is edited later, regenerate the SQL with the same first three commands without `--check`. `python -B -m generators.stage2_workbooks` regenerates all three Stage 2 workbooks; the points import itself still uses only `04-points.xlsx`.

## Demo source services and container research

[ADR-002c: Northlake demo service bundle](../stage-11-third-party/ADR-002c-Northlake-Demo-Service-Bundle-Research.pdf) inventories the source files and services needed for these acceptance runs, then follows their dependencies into bills, document parsing, My Imports/Exports, operations, provider pages and the Northlake API/Power BI site. It is research only, with an incremental backlog and explicit deployment/state requirements. The [editable source](../../generators/documents/sources/implementation/stage-11-third-party/ADR-002c-Northlake-Demo-Service-Bundle-Research.md) lives with the other document sources.

The research identifies corrections to address when implementing the affected cases: MV9 is binary in the current parser, Web gateway coverage is missing from the acceptance inventory, and HMR configuration and provider bill schemas remain prerequisites. It does not mark any acceptance run complete or change the existing recipes.

To run the stored-configuration checks from the repository root without a code-page mismatch:

```powershell
sqlcmd -S BVirtualPC -d EEMSuite_Northlake -E -C -I -b -f 65001 -i implementation/stage-1-foundation/checks.sql
sqlcmd -S BVirtualPC -d EEMSuite_Northlake -E -C -I -b -f 65001 -i implementation/stage-2-hierarchy/checks.sql
sqlcmd -S BVirtualPC -d EEMSuite_Northlake -E -C -I -b -f 65001 -i implementation/stage-3-gateways-and-data/checks.sql
```


## Handheld setup and acceptance

The [agreed handheld testing environment](handheld-test-environment.md) defines a separate optional
service in the existing source bundle. Its first browser demonstration will load the real route
export, record reads/skips, and return native files to the current collectors. Its implementation
is owned by the testing-environment session; installed Northlake round-trip acceptance is separate.
Stage 9 now [operates the saved configuration](../stage-9-operations/07-handheld-and-importers.yaml)
instead of recreating it. Retained high-precision history and the water-submeter population have
explicit conversion/conservation prerequisites; the first demo uses controlled whole-unit values.
The read-only `python -m generators.handheld_bindings` command produces the agreed companion JSON
after the pilot assignments and actual export exist. See the environment plan for its invocation.
It verifies the live source release and refuses unresolved HMR or gateway IDs.

On November 5 the three read types a SQL script had inserted were deleted, so
Northlake again has zero read types, meter assignments and reading-channel
assignments (still true November 7, after the upgrade that brought the new page).
Step 5 is entered on the web's **Handheld Meter Setup** page (System Manager), which
takes over the HMR Configuration menu entry before this step.
The [route recipe](05-handheld-routes.yaml) defines 192 meters and 204 registers on
ten routes. The five of November 5 are the two utility masters, the 126 Cedar Row A
and B submeters and the four sewer-credit deduct meters. The five added November 7
are there to learn the handheld settings: **CRCWTR** (Cedar Row C's 50 meters, keyed
badly by its installer and kept that way until the Stage 12 fix), **IRRIG** (four
irrigation meters in ccf), **CHECK** (two registers that need a meter constant, x40
and x3.0367), **SWGR** (one switchgear meter with ten registers, four of them demand
reads) and **GEN** (three generators, run hours and diesel gallons). The meters and
their points come from Stage 2 (Cedar Row C, the generators and the switchgear were
added there on November 7), so Stage 2's import runs first.

1. In **Configuration Tool**, add the parameterless **Handheld Meter Reading
   Gateway** type on Gateway Types, then the three handheld gateways in
   `02-gateways.yaml` with that type and no nodes. Configuration Tool requires a
   type; Neptune and MVRS never read it. Then complete the three disabled handheld
   schedules on the existing Neptune/MVRS tasks.
2. On **Handheld Meter Setup**, **More** > **Read types**: add the nine read types in
   the recipe and save them together.
3. Choose Northlake University, Cedar Row Apartments and Northlake Thermal Plant and
   show all meters. **More** > **Paste from Excel**: open
   [05-handheld-meters.csv](05-handheld-meters.csv) in a text editor (Excel drops
   the leading zeros of the cycles and tamper code), copy all of it, paste it and
   save. It has one row per register (204); rows of one meter are told apart by
   their prompt, and the four demand reads leave Reading Point empty.
4. Starting readings, Cedar Row C first: choose only Cedar Row C, set the date to
   September 1, 2025 and paste the 50 lines of
   [05-handheld-starting-readings-2025-09-01.txt](05-handheld-starting-readings-2025-09-01.txt);
   save. Then choose the three companies, set January 1, 2024 and paste the 150 lines
   of [05-handheld-starting-readings-2024-01-01.txt](05-handheld-starting-readings-2024-01-01.txt).
   Each file is in the grid's order, so it lines up only when the grid lists exactly
   50, then 150, registers with no starting reading.
5. Run the `handheld_configuration` section of [checks.sql](checks.sql). It checks
   nine full read-type definitions and 204 exact register mappings, reports
   unexpected assignments and registers, and lists the resolved meter and point IDs
   for file generation. All 213 expected checks must pass before the Step 4 handheld
   pack. Cedar Row C's mistakes are expected; do not correct them.
6. Complete Step 6, then run the `handheldAcceptance` pack in
   [04-acceptance-runs.yaml](04-acceptance-runs.yaml) on the live database (Stage 3
   takes no configured-empty backup). The pack checks the masters' starting readings,
   then covers outbound export, normal/zero consumption, database/file previous values,
   replay, skipped and late reads, log/text evidence, the submeter batch and
   invalid-input cases; their probe readings stay in the meters' history. Its uploads
   still need generating from the saved Northlake meter IDs.

The direct-demand, multiplier and rollover cases change settings temporarily and leave
synthetic values, so they wait until a backup exists to restore afterward; otherwise
those controlled test values and the temporary assignment would become production-style
source history.
Massport's custom estimate-approval/LOTO screens and real radio-device provisioning
are outside this basic HMR pack. Ordinary skip logging is included.

Regenerate and validate the embedded expectations and the paste file with:

```powershell
python -m generators.stage_check_data
python -m generators.stage_check_data --check
python -m unittest generators.tests.test_handheld_routes generators.tests.test_stage3_workflows
```

This revision specifies and checks the setup; it does not establish completed
handheld imports, exported device files or live UI acceptance.


## Step 5 entry verification - November 4, 2026

A fresh read-only check of `BVirtualPC / EEMSuite_Northlake` passes Stage 1
(1,222 expected/actual records) and Stage 2 (2,210). The direct gateway preview
reports 258 already-correct bindings and zero blocking issues. All required
node settings, including the five UTC settings, match the recipe. The 11
workflows and 11 reusable tasks match; the 13 existing schedules match and
remain disabled. The six remaining workflow-checker rows are the three Step 5
handheld gateway headers and their three schedules.

The task-group expectation now uses the user's saved name **Northlake Gateways**
(group 3). The earlier EEM Gateways label caused eleven false discrepancies.
The saved runtime file enables all required kinds, but `AerisWeather` is true
where the recipe requests false; change that flag through Profile Manager.
Workers, the source producer/web and the handheld service are running. The
interval archive is still empty. The entry backup is recorded; no configured-empty
backup will be taken (decided November 5). Old failed/incomplete task-run history is
not evidence of current acquisition acceptance.

Step 5's read-type catalog, HMR meter assignments and HMR reading assignments were
still empty then. The three read types a script inserted afterwards were deleted on
November 5; Step 5 now starts on the Handheld Read Types page (step 2 above), then
pastes [05-handheld-meters.csv](05-handheld-meters.csv) on Handheld Meter Setup.

**Gateway headers resolved, November 5.** The three handheld gateways use one new
parameterless type, **Handheld Meter Reading Gateway**, and have no nodes.
Configuration Tool cannot save a gateway without a type (Add Gateway assigns one
and the picker cannot clear it), but Neptune and MVRS never read the type:
`HMR_PointNode_Get` takes only the gateway name and GUID and returns one synthetic
node. Only aggregation selects gateways by type name, so no other type would break
at runtime; a dedicated empty type avoids mislabeling them. Massport's live MVRS
gateway has no type and no nodes, a shape the 7.0 editor cannot create (product
finding 78). Until the three exist, `gateway_type_assignments` lists them as
missing gateways. The real gateway IDs must exist before schedule/binding-manifest
completion or native return-file acceptance. Do not use a fixture-only manifest
as an installed Northlake binding.

A November 5 read-only recheck found Step 5 unchanged: no read types, meter or
channel assignments, or handheld gateways. Step 6 has 1 of the 12 weather
associations (KSAC Dew Point) and none of the 3 baselines. All 13 Northlake
schedules remain disabled and the interval archive is empty.
