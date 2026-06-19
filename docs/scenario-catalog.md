# Scenario Catalog

Each scenario should describe behavior the system must handle. Source data is only useful when the expected downstream result is clear.

## V1 Scenarios

| Scenario | Purpose | Initial scope | Expected assertions |
| --- | --- | --- | --- |
| `baseline_monthly_bills` | Prove standard bill ingestion and rollups. | 24 months across electric, gas, water, sewer, and chilled water. | Bill totals match source model by account, building, site, and customer. |
| `electric_interval_15min` | Prove interval ingestion and time-series rollups. | Science Center electric channels through MV90/MDEF and Student Center electric channels through AcquiSuite. | Interval count, usage totals, peak demand, gateway point mappings, and local time handling match expected values. |
| `solar_generation_interval` | Prove generation interval ingestion and sign convention. | Helios PV generation/export channels through MV90/MV9. | Generated kWh, exported kWh, REC basis, and net-load reduction match expected values. |
| `chilled_water_hourly` | Prove non-electric interval shape. | Science Center chilled-water ton-hours and tons through BACnet present values. | Usage totals, demand, unit conversion, and BACnet point mappings match expected values. |
| `weather_gateway_noaa` | Prove NOAA current-observation ingestion. | KSAC temperature, humidity, and wind points. | NOAA station id, weather type mapping, local time, and record counts match expected values. |
| `weather_gateway_aeris` | Prove Aeris observation/forecast ingestion. | KSMF observed and forecast temperature points. | Request counts, state cursor, forecast gating, and point bindings match expected values. |
| `spinwave_gateway` | Prove Spinwave CSV ingestion. | Science Center wireless temperature and humidity sensors. | Folder/device/channel mappings and interval counts match expected values. |
| `fig_gateway_formats` | Prove FIG-family provider file ingestion. | One Cedar Row water alias emitted in FIG, SIEMANSREPORT, MEDIATOR, EATON, XML, FIXEDNETWORKS, and CMEP shapes. | Each format binds to the same source channel and produces equivalent values. |
| `modbus_gateway` | Prove Modbus TCP point reads. | Thermal plant chiller kW from a floating-point register. | Register type, address mapping, scaling, and timestamping match expected values. |
| `odbc_gateway` | Prove SQL historian query ingestion. | Library electric interval reads through an ODBC profile and query key. | Query token substitution, cursor state, and backfill windows match expected values. |
| `fake_gateway` | Prove deterministic generated gateway data. | One synthetic 15-minute kWh channel. | Seeded generation, state handling, and optional anomaly/replay shapes match expected values. |
| `handheld_gateway_uploads` | Prove handheld upload ingestion. | Neptune water and MVRS gas route uploads. | MetaWorldID binding, usage/register point mapping, constants, and read timestamps match expected values. |
| `hmr_events_publish` | Prove handheld event publishing. | MVRS event output file published to the HMR event broker shape. | Event count, idempotency scope, queue metadata, and gateway identity match expected values. |
| `meter_replacement` | Prove meter lifecycle handling. | One electric account changes meter IDs mid-stream. | Old and new meters map to the same building without double counting. |
| `estimated_bill_correction` | Prove corrected bill behavior. | One natural gas estimated bill followed by a correction. | Corrected bill supersedes or adjusts the estimate according to product rules. |
| `missing_interval_backfill` | Prove late-arriving interval data. | A gap in Student Center interval reads is backfilled later. | Gap detection, backfill ingestion, and final totals match expected values. |
| `duplicate_file_import` | Prove idempotency. | Re-import one generated provider file. | Second import does not duplicate usage, costs, meters, or bills. |
| `account_number_change` | Prove account continuity. | Water account changes account number at renewal. | New account identifier preserves site and building continuity where expected. |
| `provider_rate_change` | Prove rate-sensitive calculations. | Electric rate changes at the start of a fiscal year. | Bills after the change use the expected tariff metadata. |
| `negative_bad_units` | Prove validation failures are explicit. | One intentionally invalid provider file uses an unsupported unit. | Import fails with the expected validation error and does not partially load data. |

## Scenario Rules

- Positive scenarios should be valid and repeatable.
- Negative scenarios must be labeled and isolated from normal demo loads.
- Every scenario must define source rows, generated artifacts, and validation assertions.
- Scenario names should be stable because generated artifact names and test results may reference them.
