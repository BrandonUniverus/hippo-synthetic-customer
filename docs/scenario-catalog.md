# Scenario Catalog

Each scenario should describe behavior the system must handle. Source data is only useful when the expected downstream result is clear.

## V1 Scenarios

| Scenario | Purpose | Initial scope | Expected assertions |
| --- | --- | --- | --- |
| `baseline_monthly_bills` | Prove standard bill ingestion and rollups. | 24 months across electric, gas, water, sewer, and chilled water. | Bill totals match source model by account, building, site, and customer. |
| `electric_interval_15min` | Prove interval ingestion and time-series rollups. | Two campus buildings with 15-minute electric channels. | Interval count, usage totals, peak demand, and local time handling match expected values. |
| `chilled_water_hourly` | Prove non-electric interval shape. | One hourly chilled water channel for Science Center. | Usage totals and unit conversion match expected values. |
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
