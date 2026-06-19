# Synthetic Customer V1

## Customer

`DemoUniversityV1` represents a fictional higher-education customer with a nearby apartment complex. The geography is based around Sacramento, California so public weather station data and plausible utility territories can be used without tying the dataset to a real customer.

Working names:

- Customer: Northlake University.
- Campus site: Northlake Main Campus.
- Housing site: Cedar Row Apartments.

These names are fictional and can be changed before external demos.

## Geography

- Region: Sacramento, California.
- Primary weather station: KSAC, Sacramento Executive Airport.
- Secondary weather station: KSMF, Sacramento International Airport.
- Time zone: America/Los_Angeles.

## Utility Providers

V1 should include five provider categories:

| Provider category | Synthetic provider name | Data type |
| --- | --- | --- |
| Electric | Valley Electric District | Bills and interval reads |
| Natural gas | Sierra Gas Utility | Bills |
| Water | River City Water | Bills |
| Sewer | Capital Sewer District | Bills |
| Chilled water | Northlake Thermal Plant | Internal allocation and interval reads |

The provider names are fictional. Rate structures may be loosely based on public examples, but bills and meter data must be synthetic.

## Sites and Buildings

| Site | Building | Primary use | Approximate size | Data coverage |
| --- | --- | --- | --- | --- |
| Northlake Main Campus | Admin Hall | Office and classrooms | 85,000 sq ft | Electric, gas, water |
| Northlake Main Campus | Science Center | Lab and classrooms | 120,000 sq ft | Electric interval, gas, chilled water |
| Northlake Main Campus | Library | Library and study space | 70,000 sq ft | Electric, gas |
| Northlake Main Campus | Student Center | Food service and event space | 95,000 sq ft | Electric interval, gas, water, sewer |
| Cedar Row Apartments | Cedar Row A | Multifamily housing | 60 units | Electric common area, water, sewer |
| Cedar Row Apartments | Cedar Row B | Multifamily housing | 64 units | Electric common area, water, sewer |

## Data Span

Initial V1 span:

- Start date: 2024-01-01.
- End date: 2025-12-31.
- Monthly bills for all provider categories.
- 15-minute electric interval reads for Science Center and Student Center.
- Hourly chilled water interval reads for Science Center.

## Required Patterns

V1 should include normal data and deliberately odd but realistic events:

- Seasonal electric usage that correlates with weather.
- Lab building baseload higher than classroom buildings.
- Student Center demand spikes during event periods.
- Apartment water usage that scales with occupancy.
- One meter replacement.
- One estimated bill followed by a corrected bill.
- One duplicate import attempt.
- One missing interval block that is later backfilled.

## Success Criteria

The V1 customer is useful when it can:

- Load into a dev environment without production data.
- Produce repeatable rollups by customer, site, building, provider, account, and meter.
- Exercise at least one file-based ingestion path.
- Exercise at least one backfill path.
- Exercise at least one external integration export path.
- Produce known expected totals for reports and validation checks.
