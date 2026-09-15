# Northlake first implementation: Student Center electricity

Status: **packet and source samples prepared; UI setup and installed acceptance not run**.

Use the [customer packet](../documents/intake-package/),
[Stage 1B definitions](../data/eem/northlake-eem-metaworld-stage1b-v1.yaml), and
[gateway coverage](northlake-gateway-coverage.pdf). This checklist starts a real
implementation and records its evidence. It is not a database seed or an import
of EEM internal tables.

## 1. Record the starting instance

- Record application/build version, database name, instance name and packet version.
- Confirm the supported product installation, setup login and intended worker are available.
- Keep the current setup account for this milestone. User/permission scenarios follow later.
- Copy `northlake-instance-mapping.template.csv` to the run's evidence directory.
  The generated template is overwritten when the packet is regenerated; never
  enter actual IDs or acceptance results into the template itself.
- Capture the actual company, hierarchy, point-type, unit and timezone choices
  from the UI. Numeric IDs in older scenario YAML are illustrative and must not
  be inserted into EEMSuite or assumed to match the installed instance.

## 2. Enter the customer foundation

Use Database Administrator's company and Nodes screens. Create only missing
objects after checking the existing hierarchy.

Every company uses the same levels, listed below. A building exists once, in
the company that owns its site. The Northlake Thermal Plant company contains
only the Central Plant; chilled-water and steam meters at served buildings are
created under those buildings in Northlake University.

| Object | Intended value |
| --- | --- |
| Company | Northlake University |
| Hierarchy levels | Site, Building, Meter, Point |
| Hierarchy | System / Northlake University / Northlake Main Campus / Student Center |
| Building area | 95,000 sq ft; address 160 Synthetic Campus Drive, Sacramento |
| Timezone | Sacramento / America/Los_Angeles equivalent in the installed lookup |
| Provider | Valley Electric District |
| Billing account | SYN-VED-A-0010004 |
| Contractual tariff reference | VED-TOU-GS for 2024; VED-TOU-GS-FY25 for 2025 |
| Meter | Student Center Electric Main; SYN-VED-M-0040004 |
| Energy point | Delivered kWh 15m; Analog; kWh; 15 minutes |
| Demand point | Demand kW 15m; Analog; kW; 15 minutes |

Create data/providers/accounts through their normal UI. Full determinant construction
in Rate Modeler and bill calculations are later acceptance work; they are not
required for raw interval ingestion. Company calendars are required before the
later bill import milestone.

Record generated IDs and screenshots/exports after saving. Check that the point
list contains both measurements under the correct meter. A missing required UI
path is a product finding; do not fill the gap with SQL.

## 3. Configure the AcquiSuite source

Use the Gateway Configuration workspace in ConfigurationTool or the gateway
workspace opened from Database Administrator. Point identities are created in
Nodes; the gateway screen associates those points with a logger/device.

| Setting | Value |
| --- | --- |
| Customer data source | Campus AcquiSuite loggers |
| Gateway type | ACQUISUITE |
| Gateway name | Northlake Student Center AcquiSuite |
| Gateway node | ASQ-VED-STUDENT |
| Node Serial Number | ASQVED01 |
| DeviceID on both points | STUDENT |
| Energy Row Number | 1 |
| Demand Row Number | 2 |
| RowOffset | 0 |
| Input pattern | `*.log` |
| Input / working / backup / error locations | Separate writable directories belonging to this test instance |

Use actual point and node IDs captured from the UI. Enable the relevant gateway
object through normal instance configuration and create the supported workflow
and task/schedule through the UI. Ensure the workflow includes interval
publication and that the appropriate worker is processing it. The sample is
historical, so confirm the normal backfill path is active. A gateway producing
an intermediate file or a successful task log alone does not prove stored data.

The format is grounded in `AcquiSuiteGatewayComponent`: filename tokens match
serial/device, column zero is UTC, the configured row number plus RowOffset
selects the value column, and the installed timezone determines local time.
No header line is permitted; an unparseable timestamp ends that file's read loop.

## 4. Execute and accept

Take a configured checkpoint before introducing interval data. Use disposable
restores of that checkpoint for independent cases. Copy a source sample into the
configured input directory through the normal file-delivery path, then run the
task from the UI. Retain the original packet files outside the watched folder.

| Case | Input / action | Required visible result |
| --- | --- | --- |
| Normal day | Deliver `complete/ASQVED01_STUDENT.log` | 96 readings per point, correct local/UTC times, 2,020 kWh, 120 kW peak |
| Replay | Deliver that same complete file again | Still 96 unique timestamps per point and 2,020 kWh; capture the actual duplicate/replay treatment |
| Missing block | Fresh configured checkpoint; deliver the gap file | 88 readings per point, 1,780 kWh, missing 12:00–13:45 PST |
| Backfill | Deliver the backfill file after the gap | 96 readings per point, gap closed, 2,020 kWh and 120 kW peak |

Use the point/history and applicable interval/report UI for the January 15 local
day. Sum **kWh**, and take the maximum of **kW**. Do not sum demand or infer
success from the task log. Record actual results, times, point IDs and evidence
in the run record. Report partial success at the failed boundary if collection,
publication, storage or rendering does not complete.

## 5. Extend the same implementation

1. Add Science Center Electric Main (MV90 MDEF) under
   System / Northlake University / Northlake Main Campus / Science Center with
   its two points, Delivered kWh 15m and Demand kW 15m.
2. Configure and calculate the campus aggregates Campus Interval Electric kWh
   Total and Campus Coincident Electric kW directly under Northlake Main Campus.
   They cover the four interval-metered campus buildings, so Science Center
   Electric Main, Student Center Electric Main, Lakeview Hall Electric Main and
   Recreation Center Electric Main must all exist with their points first.
   Coincident demand is the maximum of the interval-by-interval sum, not the
   sum of separate meter peaks.
3. Add the KSAC Sacramento Executive Airport station meter under
   System / Northlake University / Weather Reference and its HDD/CDD
   relationships through the index UI, confirming base temperature, method and
   station assignments (KSAC for every building in all three companies).
4. Add the Student Center Kitchen Gas MVRS and Cedar Row B Water Master Neptune
   register/usage pairs (Register Reading with Route Usage Therms, and Register
   Reading with Route Usage kgal). Create the accumulator through the UI and
   capture its related usage point rather than creating a disconnected
   duplicate. Replace all placeholder handheld IDs, including meter and
   register IDs.
5. Work through the remaining gateway format cases in the coverage list. Use
   separate restores for alternative formats that share a measurement.

Rate modeling, bills, AP/GL, user permissions, tenants and broader reporting
continue through the existing phase plans after the measurement foundation.
The chiller status point, activity index, baselines and other feeds remain
explicitly pending until their own input paths and results have been exercised.

## 6. Promote a restore baseline

Save the database backup only after the applicable acceptance checks pass.
Keep the application version, packet/source revision, fixture hashes, actual-ID
mapping, instance configuration and observed results beside it. Gateway file
directories and external services are not reproduced by a database backup alone.

Restore once into a disposable test instance, reconnect its intended sources and
verify the same saved data through the UI before calling it the Northlake
baseline. Keep the configured-empty checkpoint as well as the accepted-data
checkpoint so replay and backfill tests can start cleanly.
