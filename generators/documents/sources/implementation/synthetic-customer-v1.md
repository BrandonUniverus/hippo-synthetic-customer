# Synthetic Customer V1

## Customer

`DemoUniversityV1` represents a fictional higher-education customer with a nearby apartment complex and a central thermal plant. The geography is based around Sacramento, California so public weather station data and plausible utility territories can be used without tying the dataset to a real customer.

Working names:

- Customer: Northlake University.
- EEM companies: Northlake University, Cedar Row Apartments, Northlake Thermal Plant.
- Campus site: Northlake Main Campus.
- Housing site: Cedar Row Apartments.
- Plant site: Northlake Central Plant.
- Weather site: Weather Reference (KSAC and KSMF station meters, under Northlake University).

These names are fictional and can be changed before external demos.

## Geography

- Region: Sacramento, California.
- Primary weather station: KSAC, Sacramento Executive Airport.
- Secondary weather station: KSMF, Sacramento International Airport.
- Time zone: America/Los_Angeles.
- Address coordinates are synthetic Sacramento-area values for weather and
  mapping setup; see
  [implementation/northlake-address-coordinates.pdf](northlake-address-coordinates.pdf).

## Utility Providers

V1 includes five fully-configured providers, deliberately split into three
everyday utilities and two unique provider identities. Each provider's complete
definition (services, units, channels, rate schedules, charges, file formats,
environmental attributes, and scenario hooks) lives in `data/providers/<id>.yaml`,
indexed by `data/providers/README.md`.

| # | Synthetic provider | Class | Supplies | Data type |
| --- | --- | --- | --- | --- |
| 1 | Valley Electric District | everyday | Electric | Monthly bills, 15-minute interval reads, billing demand, unmetered area lighting |
| 2 | Sierra Gas Utility | everyday | Natural gas | Monthly bills only |
| 3 | River City Utilities | everyday | Water + sewer + stormwater, irrigation, fire service | One bundled monthly bill with several service lines; separate irrigation and fire-service accounts |
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
[`data/security/northlake-eem-security-v1.yaml`](../data/security/northlake-eem-security-v1.yaml),
with the companion note in
[`implementation/northlake-eem-security.pdf`](northlake-eem-security.pdf).

The DBAdmin-facing setup translation lives in
[`data/eem/northlake-eem-stage1-setup-v1.yaml`](../data/eem/northlake-eem-stage1-setup-v1.yaml).
It defines the company form fields, address/contact values, the hierarchy levels
every company shares (Site, Building, Meter, Point) including DBAdmin
FontAwesome icon classes, deferred DBAdmin sections, and the
decision to use the built-in system company `CompanyID = -1` for
implementation/support users instead of creating an implementation-support
company.

The follow-on MetaWorld setup translation lives in
[`data/eem/northlake-eem-metaworld-stage1b-v1.yaml`](../data/eem/northlake-eem-metaworld-stage1b-v1.yaml).
It holds only the rules that map the scenario inventory into EEM utility setup,
billing account shells, meter nodes, point nodes, weather station assignments,
aggregate points, and baseline shells; it never re-lists buildings, meters or
points.

This is app setup data, not customer-provided bill or archive source data. It is
used to prove that a blank EEMSuite seed can be configured through the actual
apps before bill records, interval archives, gateway execution, workflows, or
scheduled task execution are introduced.

For Stage 1, EEM companies are treated as data and security boundaries. Cedar
Row assets belong to the Cedar Row company only; Northlake users who need Cedar
Row visibility receive it through Cedar Row group membership rather than copied
hierarchy or duplicate meters. The Northlake Thermal Plant company contains only
the Central Plant; the chilled-water and steam meters at the buildings it serves
belong to those university buildings, with the plant as provider.

## Sites and Buildings

| Site | Building | Primary use | Approximate size | Data coverage |
| --- | --- | --- | --- | --- |
| Northlake Main Campus | Admin Hall | Office and classrooms | 85,000 sq ft | Electric, gas, water + sewer + stormwater, fire service, steam |
| Northlake Main Campus | Science Center | Lab and classrooms | 120,000 sq ft | Electric interval plus a second lab-wing service, gas, water + sewer + stormwater, fire service, chilled water + steam, solar, lab sensors |
| Northlake Main Campus | Library | Library and study space | 70,000 sq ft | Electric (meter replacement, historian mirror), gas, water + sewer + stormwater, steam |
| Northlake Main Campus | Student Center | Food service and event space | 95,000 sq ft | Electric interval, kitchen gas route, water + sewer + stormwater with a kitchen sewer deduct, steam, solar |
| Northlake Main Campus | Lakeview Residence Hall | Residence hall | 110,000 sq ft, 300 beds | Electric interval, laundry submeter, gas, water + sewer + stormwater, fire service, steam |
| Northlake Main Campus | Recreation and Aquatics Center | Recreation and pool | 65,000 sq ft | Electric interval, pool gas, water + sewer + stormwater with a pool-fill deduct, chilled water + steam |
| Northlake Main Campus | Parking Structure | Parking, EV charger bank | 180,000 sq ft parking area | Electric, EV charger submeter |
| Northlake Main Campus | Campus Grounds | Outdoor service area | No floor area | Irrigation water (three meters), unmetered area lighting |
| Cedar Row Apartments | Cedar Row A | Multifamily housing | 58,000 sq ft, 60 apartments | Electric master, water + sewer master, house gas, fire service; electric and water house submeters plus an electric and a water submeter per apartment |
| Cedar Row Apartments | Cedar Row B | Multifamily housing | 62,000 sq ft, 64 apartments | As Cedar Row A, for 64 apartments |
| Cedar Row Apartments | Cedar Row Common House | Leasing, community room, laundry, pool | 18,400 sq ft | Electric, gas, water + sewer with a pool-fill deduct |
| Cedar Row Apartments | Cedar Row Carport and Grounds | Outdoor service area | No floor area | Solar carport, unmetered parking lighting, irrigation water |
| Northlake Central Plant | Central Plant | District energy plant | 58,400 sq ft | Electric interval (primary service), boiler gas, makeup water + sewer with a cooling-tower deduct, chilled-water, steam and condensate production, chiller controller |

Water, sewer, and stormwater are billed by River City Utilities on one bundled
account per building; irrigation and fire service are separate accounts, and
irrigation, fire-service, Central Plant and Cedar Row accounts have no
stormwater charge. Steam and chilled water are allocated by the Northlake
Thermal Plant to the university buildings it serves. Solar generation is
supplied by Helios Onsite Solar and nets against Valley Electric consumption on
shared buildings. Cedar Row A and Cedar Row B are master-metered: the utilities
bill the property on one electric master and one water master per building,
never a resident, and every apartment has an owned electric submeter and water
submeter.

## ENERGY STAR Property Mapping

The campus and Cedar Row sites and every building except the two grounds nodes
also carry an ENERGY STAR Portfolio Manager property mapping so the dataset is
ready for the EEMSuite ENERGY STAR integration. The manifest's
`energyStarProperties` section (13 entries) assigns an exact PM
`primaryFunction` and one or more property uses (with use details) to each of
them.

| Property | ENERGY STAR primary function | Property uses |
| --- | --- | --- |
| Northlake Main Campus (campus parent) | College/University | College/University |
| Admin Hall | Office | Office + Other - Education |
| Science Center | Laboratory | Laboratory + Other - Education |
| Library | Library | Library |
| Student Center | Food Service | Food Service + Other - Entertainment/Public Assembly |
| Lakeview Residence Hall | Residence Hall/Dormitory | Residence Hall/Dormitory |
| Recreation and Aquatics Center | Fitness Center/Health Club/Gym | Fitness Center/Health Club/Gym + Swimming Pool |
| Parking Structure | Parking | Parking |
| Cedar Row Apartments (multifamily property) | Multifamily Housing | Multifamily Housing + Other - Recreation |
| Cedar Row A / B | Multifamily Housing | Multifamily Housing |
| Cedar Row Common House | Other - Recreation | Other - Recreation |
| Central Plant (standalone property) | Other - Utility | Other - Utility |

The campus is modeled as a College/University parent (545,000 sq ft, parking
excluded) with child building properties; Cedar Row is modeled as one
multifamily property (124 units, resident population `Dedicated Student`) with
three physical buildings: Cedar Row A, Cedar Row B and Cedar Row Common House.
The Central Plant is a standalone property outside the campus boundary. See
[implementation/energystar-integration.pdf](energystar-integration.pdf) for the full field
mapping, use-detail lists, enum values, and integration hooks.

## Data Span

Initial V1 span:

- Start date: 2024-01-01.
- End date: 2025-12-31.
- Monthly bills (and the thermal plant's monthly allocation) for all provider categories.
- 15-minute electric interval reads for Science Center, Student Center, Lakeview Residence Hall, Recreation and Aquatics Center, and Central Plant.
- 15-minute solar generation interval reads for Science Center, Student Center, and the Cedar Row carport (Cedar Row Carport and Grounds).
- Hourly chilled water interval reads for Science Center and Recreation and Aquatics Center, and hourly Central Plant production (chilled water, steam, condensate).
- Hourly fixed-network submeter reads for every Cedar Row apartment and house electric submeter, the Lakeview Residence Hall laundry and the Parking Structure EV chargers.
- Monthly route reads for every Cedar Row apartment and house water submeter.

## Meter And Point Inventory

`data/scenarios/demo-university-v1.yaml` now defines the V1 source inventory at the
account, meter, and channel level. The counts below come from one join of the
manifests (packet 0.3):

- 3 companies, 3 sites plus the Weather Reference site, and 13 buildings.
- 49 accounts: 40 external utility accounts, 6 internal cost centers and 3 PPA agreements.
- 322 meters: 55 utility meters (including the Library electric replacement pair), 265 owned meters (248 apartment submeters for 124 apartments plus 17 house, deduct, production, sensor, logical-source and controller meters) and 2 weather station meters.
- 431 points. Bill-only meters have no points; bill usage stays on the billing account.
- 139 related measurements (132 register/usage pairs, 4 degree-day, 3 baseline) and 7 aggregate points.
- EEMSuite gateway runtime points bound back to source channel ids, with per-apartment point templates for the two submeter profiles.
- 15 gateway profiles covering 21 format cases, plus the HMR handheld-event publisher.

Regenerate the register and packet with `python generators/northlake_packet.py`
(check first with `--check`), then update the Data Collection workbook with
`python generators/update_workbook.py`.

The inventory deliberately includes both ordinary and awkward shapes:

| Provider | Meter shape | Channels |
| --- | --- | --- |
| Valley Electric District | Monthly electric meters plus interval demand meters, and unmetered area-lighting services | kWh billing usage, kW billing demand, 15-minute kWh, 15-minute kW, flat fixture charge with no usage |
| Sierra Gas Utility | Monthly gas meters | therms, with ccf as delivered volume metadata |
| River City Utilities | Water meters on bundled accounts, irrigation meters (three on the Campus Grounds account) and flat-rate fire service lines | water kgal, derived sewer kgal, flat stormwater ERU where applicable, irrigation kgal, flat fire-service charge |
| Northlake Thermal Plant | Chilled-water BTU meters at two served buildings plus steam meters at six, all under university buildings | hourly ton-hours, hourly tons, monthly steam klb |
| Helios Onsite Solar | PV production/export meters | generated kWh, exported kWh, generated kW |
| Owned meters (no provider) | Apartment and house submeters, sewer-deduct submeters, Central Plant production meters, lab sensors, the Library historian, the chiller controller, the smoke-test source | hourly submeter kWh, route register and usage kgal, manual deduct readings, hourly ton-hours, klb and kgal production, 5-minute chiller kW and status, sensor and historian interval values |
| Reference channels | KSAC and KSMF weather stations | temperature, humidity, wind, forecast temperature |

## Gateway Proof Points

The gateway bindings in the scenario manifest are written against the current
EEMSuite gateway component contract in
`EEMSuite/src/Tasks/EEMSuite.Tasks.Gateways`:

| Gateway profile | EEMSuite component | Source provider | Points proved |
| --- | --- | --- | --- |
| `gw_acquisuite_student_electric` | `AcquiSuiteGateway` (`ACQUISUITE`) | Valley Electric District | Student Center and Lakeview Residence Hall 15-minute kWh and kW, using `Serial Number`, `DeviceID`, and `Row Number` bindings |
| `gw_noaa_ksac_observations` | `NOAAGateway` (`NOAA`) | KSAC weather station | NOAA station observations with `WeatherType`, `StationID`, and `WeatherTypeName` mappings |
| `gw_aeris_ksmf_weather` | `AerisWeatherGateway` (`AERISWEATHER`) | KSMF weather station | Aeris observations, forecasts, state-file behavior, and weather metric names |
| `gw_mv90_valley_mdef` | `MV90Gateway` (`MDEF`) | Valley Electric District | Science Center, Recreation and Aquatics Center and Central Plant 15-minute kWh and kW, using `RecorderID` and `Channel` bindings |
| `gw_mv90_helios_mv9` | `MV90Gateway` (`MV9`) | Helios Onsite Solar | Solar generation/export interval points, including positive-generation sign convention |
| `gw_bacnet_thermal_plant` | `BACnetGateway` (`BACNET`) | Northlake Thermal Plant | Chilled-water ton-hours and tons at Science Center and Recreation and Aquatics Center, plus Central Plant chilled-water supply, steam production and condensate return, from BACnet present values |
| `gw_spinwave_science_lab` | `SpinwaveGateway` (`SPINWAVE`) | Science Center sensors | Spinwave folder, device address, and channel-number file mapping |
| `gw_fig_multi_format` | `FIGGateway` (`FIG`) | River City Utilities alias data | FIG, SIEMANSREPORT, MEDIATOR, EATON, XML, FIXEDNETWORKS, and CMEP format variants |
| `gw_modbus_thermal_plant` | `ModbusGateway` (`MODBUS`) | Northlake Thermal Plant controller | Modbus TCP node settings and floating-point register decoding |
| `gw_odbc_library_historian` | `ODBCGateway` (`ODBC`) | Synthetic SQL historian | Profile/query-key lookup, token substitution, timestamp cursor state, and backfill behavior |
| `gw_fake_smoke` | `FakeGateway` (`FAKE`) | Synthetic generated channel | Deterministic generated interval data, generation modes, and state handling |
| `gw_neptune_river_city_water` | `NeptuneGateway` (`NEPTUNE`) | River City Utilities | Neptune handheld water upload parsing, usage point, and register-reading point mapping |
| `gw_mvrs_sierra_gas` | `MVRSGateway` (`MVRS`) | Sierra Gas Utility | MVRS handheld gas upload parsing, usage/register points, read-code events, and HMR event file output |
| `gw_fig_fixed_network_submeters` | `FIGGateway` (`FIXEDNETWORKS`) | Fixed-network electric submeters | Hourly kWh for every Cedar Row apartment and house electric submeter, the Lakeview Residence Hall laundry and the Parking Structure EV chargers, using per-apartment point templates |
| `gw_neptune_cedar_row_submeters` | `NeptuneGateway` (`NEPTUNE`) | Cedar Row apartment water submeter route | Monthly register and usage points for every Cedar Row apartment and house water submeter |
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
