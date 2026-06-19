# Synthetic Source Model

The synthetic source database is the authoritative model for fake customer data. Ingestion files and integration payloads should be generated from this model rather than edited independently.

## Core Entities

| Entity | Purpose |
| --- | --- |
| `customer` | Synthetic customer identity and global settings. |
| `site` | Campus, apartment complex, or other customer location grouping. |
| `building` | Physical property with use type, size, address, and weather mapping. |
| `energy_star_property` | ENERGY STAR Portfolio Manager property mapping for a site or building (primary function, gross floor area, occupancy). |
| `property_use` | One ENERGY STAR property use on a property, such as Office or Multifamily Housing. |
| `property_use_detail` | One use detail value on a property use, such as Weekly Operating Hours or Number of Bedrooms. |
| `provider` | Utility provider identity, including its kind and billing model. |
| `provider_service` | One commodity a provider supplies (a provider can supply several). |
| `account` | Provider account assigned to a site or building. |
| `meter` | Physical or logical meter associated with an account. |
| `channel` | Measured stream on a meter, such as kWh, kW, therms, gallons, or chilled water tons. |
| `reference_channel` | Non-metered source stream used by gateway tests, such as weather, BMS sensors, or SQL historian aliases. |
| `gateway_profile` | One EEMSuite gateway component configuration to prove, such as AcquiSuite, MV90/MDEF, MV90/MV9, or BACnet. |
| `gateway_node` | Runtime gateway node/device context used by the EEMSuite gateway components. |
| `gateway_point` | Runtime point binding that maps an EEMSuite `PtID` to a synthetic source `channel`. |
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
- ENERGY STAR `primary_function` and property use `function` values must be exact `PrimaryFunctionType` enum values, and each use detail must be valid for that property type.
- Gateway points must target a real meter channel or reference channel and preserve the EEMSuite runtime keys consumed by their component.
- A channel may be bound to more than one gateway profile only when those profiles are documented as alternate proof paths, not loaded together into the same baseline.
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

energy_star_property(
  energy_star_property_id,
  site_id,                 -- set for campus_parent / multifamily_property roles
  building_id,             -- set for child_property / building_within_property roles
  role,                    -- campus_parent | child_property | multifamily_property | building_within_property
  primary_function,        -- exact ENERGY STAR PrimaryFunctionType value, e.g. College/University, Office
  gross_floor_area,
  gross_floor_area_units,  -- Square Feet | Square Meters
  year_built,
  occupancy_percentage,    -- rounded to ENERGY STAR 5% increments on export
  is_institutional,
  parent_site_id           -- campus/property this child rolls up to
)

property_use(
  property_use_id,
  energy_star_property_id,
  use_function,            -- ENERGY STAR property use type, e.g. Office, Laboratory, Multifamily Housing
  gross_floor_area_sqft
)

property_use_detail(
  property_use_detail_id,
  property_use_id,
  detail_name,             -- e.g. weeklyOperatingHours, totalNumberOfResidentialLivingUnits, residentPopulationType
  detail_value,
  detail_units,            -- where applicable, e.g. Square Feet
  temporary,               -- provisional flag (ENERGY STAR UseAttributeBase)
  current_as_of            -- date the value became current
)

provider(
  provider_id,
  display_name,
  identity_class,          -- everyday | unique
  provider_kind,           -- distribution_utility | municipal_multi_service | district_energy_plant | onsite_generation_ppa
  ownership,               -- public_municipal | investor_owned | internal_campus_owned | third_party_owned
  billing_model,           -- tariff_metered | bundled_municipal | internal_allocation | ppa_generation
  primary_category,        -- primary commodity, for back-compat rollups
  config_ref               -- providers/<provider_id>.yaml
)

provider_service(
  provider_service_id,
  provider_id,
  commodity,               -- electric | natural_gas | water | sewer | stormwater | chilled_water | steam | solar_generation
  role,                    -- consumption | generation | production | service_fee
  usage_unit,
  demand_unit,
  has_interval,
  interval_minutes
)

account(
  account_id,
  provider_id,
  site_id,
  building_id,
  synthetic_account_number,
  rate_schedule_id,
  effective_start,
  effective_end
)

meter(
  meter_id,
  account_id,
  building_id,
  synthetic_meter_number,
  meter_type,
  lifecycle_status,
  replaces_meter_id,
  effective_start,
  effective_end
)

channel(
  channel_id,
  meter_id,
  commodity,
  role,                    -- billing_usage | billing_demand | interval_usage | interval_demand | derived_billing_usage | flat_service_fee | interval_generation
  unit,
  direction,               -- delivered | generated | exported
  interval_minutes,
  point_type,              -- value written to gateway PointType where applicable
  derived_from_channel_id
)

reference_channel(
  reference_channel_id,
  source_kind,             -- weather_station | building_sensor | plant_controller | sql_historian | provider_file_alias | synthetic_gateway
  source_id,
  commodity,
  role,
  unit,
  interval_minutes,
  point_type
)

gateway_profile(
  gateway_profile_id,
  component_id,            -- AcquiSuiteGateway | MV90Gateway | BACnetGateway | ... | HmrEventsPublish
  executor_key,            -- gateway.acquisuite | gateway.mv90 | gateway.bacnet | ... | hmr.events.publish
  gateway_type,            -- ACQUISUITE | MDEF | MV9 | BACNET | ... | HMR_EVENTS
  gateway_id,
  gateway_name,
  gateway_guid,
  source_time_zone,
  gateway_time_zone_id
)

gateway_node(
  gateway_node_id,
  gateway_profile_id,
  gw_node_id,
  name,
  is_enabled,
  timestamp_type,
  vendor_values_json        -- component-specific keys, such as Serial Number or BBMD Address
)

gateway_point(
  gateway_point_id,
  gateway_node_id,
  source_channel_id,       -- channel_id or reference_channel_id
  pt_id,
  pt_type,
  time_zone_id,
  interval_minutes,
  description,
  vendor_values_json        -- component-specific keys, such as DeviceID, Row Number, RecorderID, Channel, ObjectID, Object Type
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
