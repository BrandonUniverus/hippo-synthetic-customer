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
- Address coordinates are synthetic Sacramento-area values for weather and
  mapping setup; see
  [docs/northlake-address-coordinates.md](northlake-address-coordinates.md).

## Utility Providers

V1 includes five fully-configured providers, deliberately split into three
everyday utilities and two unique provider identities. Each provider's complete
definition (services, units, channels, rate schedules, charges, file formats,
environmental attributes, and scenario hooks) lives in `providers/<id>.yaml`,
indexed by `providers/README.md`.

| # | Synthetic provider | Class | Supplies | Data type |
| --- | --- | --- | --- | --- |
| 1 | Valley Electric District | everyday | Electric | Monthly bills, 15-minute interval reads, billing demand |
| 2 | Sierra Gas Utility | everyday | Natural gas | Monthly bills only |
| 3 | River City Utilities | everyday | Water + sewer + stormwater | One bundled monthly bill with several service lines |
| 4 | Northlake Thermal Plant | unique | Chilled water + steam | Internal cost allocation and hourly chilled-water interval reads |
| 5 | Helios Onsite Solar | unique | Solar generation | Generation interval reads, PPA invoice, REC / avoided-CO2e statement |

The three everyday utilities cover what almost every customer has: a data-rich
electric distribution utility, a deliberately simple gas utility, and a municipal
biller that bundles multiple services on one account. The two unique identities
exist to stress data shapes ordinary meters never produce — internal
district-energy allocation, and behind-the-meter solar generation with
environmental attributes.

River City Utilities consolidates what were previously two separate stubs
(`River City Water` and `Capital Sewer District`) into one realistic municipal
multi-service biller.

The provider names are fictional. Rate structures may be loosely based on public
examples, but bills and meter data must be synthetic.

## Stage 1 EEM Security Setup

The fake EEM users, companies, groups, and permission intent live in
[`security/northlake-eem-security-v1.yaml`](../security/northlake-eem-security-v1.yaml),
with the companion note in
[`docs/northlake-eem-security.md`](northlake-eem-security.md).

The DBAdmin-facing setup translation lives in
[`eem/northlake-eem-stage1-setup-v1.yaml`](../eem/northlake-eem-stage1-setup-v1.yaml).
It defines the company form fields, address/contact values, hierarchy levels
including DBAdmin FontAwesome icon classes, deferred DBAdmin sections, and the
decision to use the built-in system company `CompanyID = -1` for
implementation/support users instead of creating an implementation-support
company.

The follow-on MetaWorld setup translation lives in
[`eem/northlake-eem-metaworld-stage1b-v1.yaml`](../eem/northlake-eem-metaworld-stage1b-v1.yaml).
It maps the source inventory into EEM utility setup, billing account shells,
meter nodes, point nodes, weather station assignments, aggregate points, and
baseline shells.

This is app setup data, not customer-provided bill or archive source data. It is
used to prove that a blank EEMSuite seed can be configured through the actual
apps before bill records, interval archives, gateway execution, workflows, or
scheduled task execution are introduced.

For Stage 1, EEM companies are treated as data and security boundaries. Cedar
Row assets belong to the Cedar Row company only; Northlake users who need Cedar
Row visibility receive it through Cedar Row group membership rather than copied
hierarchy or duplicate meters.

## Sites and Buildings

| Site | Building | Primary use | Approximate size | Data coverage |
| --- | --- | --- | --- | --- |
| Northlake Main Campus | Admin Hall | Office and classrooms | 85,000 sq ft | Electric, gas, water + sewer + stormwater, steam |
| Northlake Main Campus | Science Center | Lab and classrooms | 120,000 sq ft | Electric interval, gas, chilled water + steam, solar |
| Northlake Main Campus | Library | Library and study space | 70,000 sq ft | Electric, gas, steam |
| Northlake Main Campus | Student Center | Food service and event space | 95,000 sq ft | Electric interval, gas, water + sewer + stormwater, steam, solar |
| Cedar Row Apartments | Cedar Row A | Multifamily housing | 60 units | Electric common area, water + sewer, solar |
| Cedar Row Apartments | Cedar Row B | Multifamily housing | 64 units | Electric common area, water + sewer |

Water, sewer, and stormwater are all billed by River City Utilities on one
account per building. Steam and chilled water are allocated by the Northlake
Thermal Plant. Solar generation is supplied by Helios Onsite Solar and nets
against Valley Electric consumption on shared buildings.

## ENERGY STAR Property Mapping

Each site and building also carries an ENERGY STAR Portfolio Manager property
mapping so the dataset is ready for the EEMSuite ENERGY STAR integration. The
manifest's `energyStarProperties` section assigns an exact PM `primaryFunction`
and one or more property uses (with use details) to every site and building.

| Property | ENERGY STAR primary function | Property uses |
| --- | --- | --- |
| Northlake Main Campus (campus parent) | College/University | College/University |
| Admin Hall | Office | Office + Other - Education |
| Science Center | Laboratory | Laboratory + Other - Education |
| Library | Library | Library |
| Student Center | Food Service | Food Service + Other - Entertainment/Public Assembly |
| Cedar Row Apartments (multifamily property) | Multifamily Housing | Multifamily Housing |
| Cedar Row A / B | Multifamily Housing | Multifamily Housing |

The campus is modeled as a College/University parent with child building
properties; Cedar Row is modeled as one multifamily property with two physical
buildings, with resident population `Dedicated Student`. See
[docs/energystar-integration.md](energystar-integration.md) for the full field
mapping, use-detail lists, enum values, and integration hooks.

## Data Span

Initial V1 span:

- Start date: 2024-01-01.
- End date: 2025-12-31.
- Monthly bills (and the thermal plant's monthly allocation) for all provider categories.
- 15-minute electric interval reads for Science Center and Student Center.
- 15-minute solar generation interval reads for Science Center, Student Center, and Cedar Row A.
- Hourly chilled water interval reads for Science Center.

## Meter And Point Inventory

`scenarios/demo-university-v1.yaml` now defines the V1 source inventory at the
account, meter, and channel level:

- 21 provider accounts/cost centers/PPA agreements.
- 23 physical or logical meters, including the Library electric replacement pair.
- 49 source channels covering utility meters, billing demand, interval usage, derived municipal services, generation/export, weather, BMS sensors, SQL historian aliases, and gateway smoke-test streams.
- 23 EEMSuite gateway runtime points bound back to source channel ids.
- 14 gateway profiles: 12 gateway collectors, both MV90 formats, and HMR event publishing.

The inventory deliberately includes both ordinary and awkward shapes:

| Provider | Meter shape | Channels |
| --- | --- | --- |
| Valley Electric District | Monthly electric meters plus interval demand meters | kWh billing usage, kW billing demand, 15-minute kWh, 15-minute kW |
| Sierra Gas Utility | Monthly gas meters | therms, with ccf as delivered volume metadata |
| River City Utilities | One physical water meter per account | water kgal, derived sewer kgal, flat stormwater ERU where applicable |
| Northlake Thermal Plant | Chilled-water BTU meter plus steam allocation meters | hourly ton-hours, hourly tons, monthly steam klb |
| Helios Onsite Solar | PV production/export meters | generated kWh, exported kWh, generated kW |
| Reference channels | Weather stations, BMS sensors, plant controllers, SQL historians, provider file aliases | temperature, humidity, wind, equipment kW, generic file/historian interval values |

## Gateway Proof Points

The gateway bindings in the scenario manifest are written against the current
EEMSuite gateway component contract in
`EEMSuite/src/Tasks/EEMSuite.Tasks.Gateways`:

| Gateway profile | EEMSuite component | Source provider | Points proved |
| --- | --- | --- | --- |
| `gw_acquisuite_student_electric` | `AcquiSuiteGateway` (`ACQUISUITE`) | Valley Electric District | Student Center 15-minute kWh and kW, using `Serial Number`, `DeviceID`, and `Row Number` bindings |
| `gw_noaa_ksac_observations` | `NOAAGateway` (`NOAA`) | KSAC weather station | NOAA station observations with `WeatherType`, `StationID`, and `WeatherTypeName` mappings |
| `gw_aeris_ksmf_weather` | `AerisWeatherGateway` (`AERISWEATHER`) | KSMF weather station | Aeris observations, forecasts, state-file behavior, and weather metric names |
| `gw_mv90_valley_mdef` | `MV90Gateway` (`MDEF`) | Valley Electric District | Science Center 15-minute kWh and kW, using `RecorderID` and `Channel` bindings |
| `gw_mv90_helios_mv9` | `MV90Gateway` (`MV9`) | Helios Onsite Solar | Solar generation/export interval points, including positive-generation sign convention |
| `gw_bacnet_thermal_plant` | `BACnetGateway` (`BACNET`) | Northlake Thermal Plant | Chilled-water ton-hours and tons from BACnet present values |
| `gw_spinwave_science_lab` | `SpinwaveGateway` (`SPINWAVE`) | Science Center sensors | Spinwave folder, device address, and channel-number file mapping |
| `gw_fig_multi_format` | `FIGGateway` (`FIG`) | River City Utilities alias data | FIG, SIEMANSREPORT, MEDIATOR, EATON, XML, FIXEDNETWORKS, and CMEP format variants |
| `gw_modbus_thermal_plant` | `ModbusGateway` (`MODBUS`) | Northlake Thermal Plant controller | Modbus TCP node settings and floating-point register decoding |
| `gw_odbc_library_historian` | `ODBCGateway` (`ODBC`) | Synthetic SQL historian | Profile/query-key lookup, token substitution, timestamp cursor state, and backfill behavior |
| `gw_fake_smoke` | `FakeGateway` (`FAKE`) | Synthetic generated channel | Deterministic generated interval data, generation modes, and state handling |
| `gw_neptune_river_city_water` | `NeptuneGateway` (`NEPTUNE`) | River City Utilities | Neptune handheld water upload parsing, usage point, and register-reading point mapping |
| `gw_mvrs_sierra_gas` | `MVRSGateway` (`MVRS`) | Sierra Gas Utility | MVRS handheld gas upload parsing, usage/register points, read-code events, and HMR event file output |
| `hmr_events_publish` | `HmrEventsPublish` (`HMR_EVENTS`) | MVRS/Neptune outputs | HMR event JSONL publishing, idempotency scope, queue naming, and gateway identity metadata |

The source model treats channels as the business facts and gateway points as
collector bindings. Generated AcquiSuite logs, MDEF/MV9 files, BACnet runtime
JSON, handheld upload files, HMR event payloads, BIF files, and assertions should
all trace back to the same source channel ids.

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
- Exercise every gateway component in `EEMSuite.Tasks.Gateways`.
- Exercise at least one backfill path.
- Exercise at least one external integration export path.
- Produce known expected totals for reports and validation checks.
