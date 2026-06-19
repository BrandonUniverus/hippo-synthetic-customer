# Synthetic Source Model

The synthetic source database is the authoritative model for fake customer data. Ingestion files and integration payloads should be generated from this model rather than edited independently.

## Core Entities

| Entity | Purpose |
| --- | --- |
| `customer` | Synthetic customer identity and global settings. |
| `site` | Campus, apartment complex, or other customer location grouping. |
| `building` | Physical property with use type, size, address, and weather mapping. |
| `provider` | Utility provider or internal provider category. |
| `account` | Provider account assigned to a site or building. |
| `meter` | Physical or logical meter associated with an account. |
| `channel` | Measured stream on a meter, such as kWh, kW, therms, gallons, or chilled water tons. |
| `bill` | Billing period, usage, cost, demand, and charge details. |
| `interval_reading` | Time-series reading for one channel. |
| `rate_schedule` | Synthetic tariff metadata used to explain bills and rate changes. |
| `scenario_event` | A deliberate event such as a meter replacement, estimated bill, correction, duplicate file, or missing interval block. |
| `artifact_run` | A record of generated files and payloads for a scenario/version. |
| `expected_assertion` | Expected downstream result used by validation checks. |

## Required Invariants

- Every generated customer, site, building, account, meter, and channel must have a stable synthetic identifier.
- Source identifiers must not look like real customer account or meter numbers unless clearly prefixed as synthetic.
- Timestamps must declare their time zone behavior.
- Bills must preserve billing period boundaries and provider units.
- Interval data must preserve source interval length and unit.
- Scenario events must identify the data they affect.
- Assertions must be traceable to scenario names and source identifiers.

## Suggested Tables

The first implementation does not need to use these exact names, but it should preserve these concepts.

```text
customer(
  customer_id,
  display_name,
  seed,
  time_zone
)

site(
  site_id,
  customer_id,
  display_name,
  site_type,
  region
)

building(
  building_id,
  site_id,
  display_name,
  use_type,
  gross_floor_area_sqft,
  address_line1,
  city,
  state,
  postal_code,
  primary_weather_station
)

provider(
  provider_id,
  display_name,
  provider_category
)

account(
  account_id,
  provider_id,
  site_id,
  building_id,
  synthetic_account_number,
  effective_start,
  effective_end
)

meter(
  meter_id,
  account_id,
  building_id,
  synthetic_meter_number,
  meter_type,
  effective_start,
  effective_end
)

channel(
  channel_id,
  meter_id,
  commodity,
  unit,
  interval_minutes
)

bill(
  bill_id,
  account_id,
  meter_id,
  billing_start,
  billing_end,
  statement_date,
  usage_quantity,
  usage_unit,
  demand_quantity,
  demand_unit,
  total_cost,
  currency,
  bill_status
)

interval_reading(
  channel_id,
  reading_start,
  reading_end,
  quantity,
  unit,
  quality_code
)

scenario_event(
  scenario_event_id,
  scenario_name,
  event_type,
  effective_start,
  effective_end,
  affected_source_id,
  description
)

expected_assertion(
  assertion_id,
  scenario_name,
  assertion_type,
  target_source_id,
  expected_value,
  tolerance,
  unit
)
```

## Artifact Generation

Generated artifacts should include enough metadata to trace back to:

- Repository commit.
- Scenario manifest version.
- Generator version.
- Source database version.
- Scenario names included in the run.

Generated artifacts should be written under `artifacts/` or `out/`, which are intentionally ignored by git.
