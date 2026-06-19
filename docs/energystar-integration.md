# ENERGY STAR Portfolio Manager Integration

This document explains how the synthetic customer maps to ENERGY STAR Portfolio
Manager (PM) so that a future integration run is mostly configuration, not
modeling. The synthetic data is intentionally shaped to match the PM model that
the EEMSuite EnergyStar integration already generates and consumes.

## Where this is grounded

- **EEMSuite integration model** (the XSD-generated C# the integration uses):
  `energyhippo/EEMSuite/src/Integrations/EEMSuite.Integrations.EnergyStar/Models/Generated`
  — `PropertyType`, `PrimaryFunctionType`, `GrossFloorAreaType`, `OccupancyType`,
  and the use-detail value types.
- **EEMSuite mapping code**:
  `energyhippo/EEMSuite/src/Tasks/EEMSuite.Tasks.EnergyStar/Mapping/PropertyMapping.cs`
  — maps an EEM facility row to a PM `PropertyType`.
- **ENERGY STAR public reference**: "U.S. Property Types, Definitions, and Use
  Details" (Oct 2024), and the PM web services property API. Links in
  [Sources](#sources).

## The PM property model

A PM **Property** is one benchmarked building or campus. It carries:

| PM field | Source | Notes |
| --- | --- | --- |
| `name` | building/site display name | 1–80 chars |
| `primaryFunction` | `PrimaryFunctionType` enum | Must be an exact enum value or it cannot be parsed |
| `grossFloorArea` | `GrossFloorAreaType` | `value` + `units` (`Square Feet` / `Square Meters`) |
| `yearBuilt` | int | |
| `occupancyPercentage` | `OccupancyType` | Discrete 5% increments (0, 5, …, 100) |
| `isInstitutionalProperty` | bool | True for campus buildings |
| `address` | `AddressType` | |

A Property then has one or more **Property Uses** (e.g. Office, Library,
Multifamily Housing). Each Property Use carries **Use Details** — the
characteristics PM uses for metrics. A single building can hold several uses
(e.g. an office building with a classroom wing).

### Use-detail wrapper

Every use detail derives from `UseAttributeBase`, so each value can carry:

- `value` (the measurement), and `units` where applicable.
- `currentAsOf` (date the value became current).
- `temporary` (flag for provisional values).
- `default` (read-only; PM marks values it defaulted).

Value carriers in the generated model: `UseIntegerType` (int ≥ 0),
`UseDecimalType` (decimal ≥ 0), `UseStringType`, `UseYesNoType` (Yes/No),
`GrossFloorAreaType`, plus typed enums such as `ResidentPopulationType`,
`OnsiteLaundryType`, and `AnnualResearchExpenditureType`.

Key enum/unit values used by this dataset:

- `GrossFloorAreaUnitsType`: `Square Feet`, `Square Meters`.
- `ResidentPopulationType`: `No specific resident population`, `Dedicated
  Student`, `Dedicated Military`, `Dedicated Senior/Independent Living`,
  `Dedicated Special Accessibility Needs`, `Other dedicated housing`.
- `OccupancyType`: 0, 5, 10, … 100. `PercentHeated` / `PercentCooled`: 0, 10, … 100.

## Two grouping models in this dataset

PM supports more than one way to group buildings; the synthetic customer
exercises both deliberately:

1. **Campus** — `Northlake Main Campus` is a `College/University` **campus
   parent**. Each academic building (Admin Hall, Science Center, Library,
   Student Center) is its own **child property** with its own `primaryFunction`
   and uses, rolling up to the campus.
2. **Multifamily property** — `Cedar Row Apartments` is one PM-benchmarked
   `Multifamily Housing` **property**; Cedar Row A and B are its physical
   **buildings within the property**.

This is captured in `scenarios/demo-university-v1.yaml` under
`energyStarProperties`, keyed by `siteId` / `buildingId` with a `role`
(`campus_parent`, `child_property`, `multifamily_property`,
`building_within_property`).

## Synthetic building → PM mapping

| Building | `primaryFunction` | Property uses |
| --- | --- | --- |
| Northlake Main Campus (site) | `College/University` | College/University (Enrollment, FTE Workers, Grant Dollars) |
| Admin Hall | `Office` | Office + `Other - Education` (classroom wing) |
| Science Center | `Laboratory` | Laboratory + `Other - Education` |
| Library | `Library` | Library |
| Student Center | `Food Service` | Food Service + `Other - Entertainment/Public Assembly` |
| Cedar Row Apartments (site) | `Multifamily Housing` | Multifamily Housing (124 units, `Dedicated Student`) |
| Cedar Row A / B | `Multifamily Housing` | Multifamily Housing (per-building) |

Every `primaryFunction` and `function` string above is a verbatim
`PrimaryFunctionType` enum value, so `ResolvePrimaryFunction` parses it instead
of falling back to `Other`.

## Use details by property type

Required vs optional per the ENERGY STAR reference (Oct 2024). Optional details
do not affect metrics but are still accepted.

| Property type | Scored | Required use details | Optional use details |
| --- | --- | --- | --- |
| College/University | No | Gross Floor Area | Weekly Operating Hours, Enrollment, Number of FTE Workers, Number of Computers, Grant Dollars |
| Office | Yes | Gross Floor Area (≥1,000), Weekly Operating Hours (≥30), Number of Workers on Main Shift (≥1), Number of Computers (≥1), Percent That Can Be Cooled, Occupancy (≥55% to certify) | Percent That Can Be Heated |
| Laboratory | No | Gross Floor Area | Weekly Operating Hours, Number of Workers on Main Shift, Number of Computers |
| Library | No | Gross Floor Area | Weekly Operating Hours, Number of Workers on Main Shift, Number of Computers, Percent That Can Be Heated, Percent That Can Be Cooled |
| Food Service | No | Gross Floor Area | Weekly Operating Hours, Number of Workers on Main Shift, Number of Computers |
| Multifamily Housing | Yes | Gross Floor Area, Total Residential Living Units (≥20), Low-/Mid-/High-rise unit counts, Number of Bedrooms, Occupancy (≥80% to certify) | Resident Population Type, Government Subsidized Housing, Laundry Hookups (in-unit / common), Percent Heated, Percent Cooled |
| Residence Hall/Dormitory | Yes | Gross Floor Area (≥5,000), Number of Rooms (≥5), Percent Heated, Percent Cooled | Computer Lab, Dining Hall |
| Other - Education | No | Gross Floor Area | Weekly Operating Hours, Number of Workers on Main Shift, Number of Computers |
| Other - Entertainment/Public Assembly | No | Gross Floor Area | Weekly Operating Hours, Number of Workers on Main Shift, Number of Computers |

`Residence Hall/Dormitory` is documented but not currently assigned — Cedar Row
is modeled as `Multifamily Housing` with `Dedicated Student` population because
it is an apartment complex, not a dorm. If a true campus dormitory is added
later, map it to `Residence Hall/Dormitory` to exercise the Number of Rooms /
Computer Lab / Dining Hall details.

## Manifest field names → PM use-detail names

The `useDetails` keys in the manifest map to PM use details as follows:

| Manifest key | PM use detail |
| --- | --- |
| `weeklyOperatingHours` | Weekly Operating Hours |
| `numberOfWorkersOnMainShift` | Number of Workers on Main Shift |
| `numberOfComputers` | Number of Computers |
| `percentThatCanBeCooled` / `percentThatCanBeHeated` | Percent That Can Be Cooled / Heated |
| `enrollment` | Enrollment |
| `numberOfFTEWorkers` | Number of Full Time Equivalent (FTE) Workers |
| `grantDollars` | Grant Dollars |
| `totalNumberOfResidentialLivingUnits` | Total Number of Residential Living Units |
| `residentialLivingUnitsLowRise` / `MidRise` / `HighRise` | Residential Living Units in a Low-/Mid-/High-rise Setting |
| `numberOfBedrooms` | Number of Bedrooms |
| `residentPopulationType` | Resident Population Type |
| `governmentSubsidizedHousing` | Government Subsidized Housing |
| `numberOfLaundryHookupsInAllUnits` / `InCommonAreas` | Number of Laundry Hookups in All Units / Common Area(s) |

## Integration hooks (already present in EEMSuite)

- `PropertyMapping.ResolvePrimaryFunction(string)` parses the function string by
  its XML enum value and falls back to `PrimaryFunctionType.Other` (a safe,
  unscored default) on no match — so an exact string matters.
- `PropertyMapping.ResolveOccupancy(int)` clamps 0–100 and rounds to PM's 5%
  scale. The synthetic `occupancyPercentage` values are already multiples of 5.
- Building mapping sets `grossFloorArea.units` by country (US → `Square Feet`).
- Property uses are serialized via `PropertyUseRequest` + `PropertyUseXmlBuilder`
  and read back via `PropertyUseDocument` / `PropertyUseDetailEntry`.

## Not yet covered (follow-on work)

- **Meter association + consumption upload**: pushing monthly usage to PM uses
  `meter.xsd`, `association.xsd`, and `meterConsumption`. The synthetic meters
  and bills already exist (see the manifest `accounts` and provider configs);
  the PM side still needs meter→property association and consumption payloads.
- **Metrics read-back**: validating PM-returned metrics (Site/Source EUI,
  ENERGY STAR score) against expected synthetic values.
- A **negative scenario**: a building whose `primaryFunction` is an unknown
  string, to prove the `Other` fallback path.

## Sources

- [List of Portfolio Manager Property Types, Definitions, and Use Details — ENERGY STAR](https://www.energystar.gov/buildings/tools-and-resources/list-portfolio-manager-property-types-definitions-and-use-details)
- [U.S. Property Types, Definitions, and Use Details (Oct 2024, PDF)](https://www.energystar.gov/sites/default/files/2024-11/US_PropertyTypesUseDetails_Definitions_Oct2024_508.pdf)
- [Portfolio Manager web services — Property API](https://portfoliomanager.energystar.gov/webservices/home/api/property)
