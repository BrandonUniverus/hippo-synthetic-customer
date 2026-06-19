# Integration Coverage

This matrix tracks what the synthetic customer must eventually prove. It starts as a planning document and should become more concrete as generators and validations are added.

| Area | Data needed | V1 target | Status |
| --- | --- | --- | --- |
| Monthly bill ingestion | Accounts, meters, bills, charges, units, provider metadata | Electric, gas, water, sewer, chilled water | Planned |
| Interval ingestion | Channels, readings, units, timestamps, time zone rules | Electric 15-minute and chilled water hourly | Planned |
| Backfill processes | Date ranges, channel mappings, missing data windows | One missing interval block and one corrected bill | Planned |
| MDEF generation | Meter definitions, channels, unit metadata, account mappings | Science Center and Student Center electric interval meters | Planned |
| BIF generation | Billing account, meter, usage, cost, and charge details | Monthly bills for all provider categories | Planned |
| Reports | Customer, site, building, meter, provider, bill, and interval rollups | Basic rollups and known totals | Planned |
| EnergyAI | Building metadata, weather context, interval series, monthly summaries | One campus interval use case | Planned |
| ENERGY STAR | Property metadata, gross floor area, use type, monthly meter data | Campus and apartment properties | Planned |
| Weather mapping | Station identifiers, local time zone, fallback station | KSAC primary and KSMF secondary | Planned |
| Data quality checks | Missing intervals, duplicates, invalid units, corrected bills | Positive and negative scenario assertions | Planned |

## Coverage Tracking

Use the `Status` column conservatively:

- `Planned`: scenario is described but no generator or validation exists.
- `Generated`: source data and artifacts can be generated.
- `Load-tested`: artifacts have been loaded into a dev environment.
- `Asserted`: automated validation verifies expected results.

## Adding New Coverage

When adding a gateway or integration:

1. Document the minimum required source data.
2. Add or update a scenario in `docs/scenario-catalog.md`.
3. Add fields to the source model only when they represent durable domain data.
4. Generate artifacts from the source model.
5. Add assertions that prove the downstream behavior.
