---
department: Facilities Operations
---

# Northlake University Facilities And Utility Overview

Prepared by: Northlake University Facilities, Housing, Sustainability, and Finance  
Packet version: 0.4

Coverage period requested: January 1, 2024 through December 31, 2025

## Purpose

Northlake University is providing this packet to describe how the university
organizes properties, utility services, meters, measured points, billing
relationships, and operational data sources. The packet is intended to support a
new facilities and utility data setup without assuming any vendor-specific
database or software model.

## Organization

Northlake University operates a main academic campus, a nearby residential
apartment property, and a central thermal plant. Each is run as its own
operating unit with its own staff, accounts, and reports. Facilities Operations
manages campus utilities, building automation systems, and meter maintenance.
Housing Operations manages Cedar Row Apartments. Thermal Plant Operations runs
the central plant and supplies chilled water and steam to the campus buildings.
Since July 2024 the plant also owns Ridgeline Wind, a ten-turbine wind site run
by its own small team, which the Mechanical Engineering department's Wind
Energy Research Lab uses for research. Finance owns external utility account
payment and internal cost allocation. Sustainability uses the same data for
reporting, performance tracking, and renewable energy accounting.

Primary groups:

- Facilities Operations
- Housing Operations
- Thermal Plant Operations
- Ridgeline Wind Operations
- Wind Energy Research Lab
- Science Operations
- Dining And Events
- Library Administration
- Finance And Accounts Payable
- Sustainability Office

## Sites

Northlake Main Campus is the primary academic site. It contains administrative,
classroom, laboratory, library, dining, event, residential, recreation, parking,
and grounds assets, with solar arrays on two roofs.

Cedar Row Apartments is a nearby student housing site with two apartment
buildings, a common house, and a carport with a solar array and parking lighting.
The property buys electricity and water on one master meter per building and
owns the submeters in every apartment; the utility never bills a resident.

Northlake Central Plant is the site of the central thermal plant that produces
chilled water and steam for the campus.

Ridgeline Wind Site, in the Montezuma Hills near Rio Vista, about fifty miles
southwest of campus, belongs to the thermal plant. The plant bought it on July
1, 2024 with university capital funding. It has ten 660 kW turbines (6.6 MW), a
50 m met mast and a collector substation where Valley Electric meters the
connection.

The three airport weather stations we rely on are not properties; they are
listed alongside the sites so that every building can name its primary station.
KSAC and KSMF are the Sacramento airports; KSUU (Travis Air Force Base) is the
nearest station to Ridgeline.

## Buildings And Properties

Admin Hall (85,000 sq ft) is an office and classroom building. Science Center
(120,000 sq ft) is the largest laboratory and classroom building and has the
highest base load. Library (70,000 sq ft) is a library and study-space building;
its electric meter was replaced in August 2024. Student Center (95,000 sq ft)
includes dining, a commercial kitchen, event, and student support areas.
Lakeview Residence Hall (110,000 sq ft, 300 beds) is the campus residence hall.
The Recreation and Aquatics Center (65,000 sq ft) holds the campus pool. The
Parking Structure (180,000 sq ft of parking) carries an electric-vehicle charger
bank. Campus Grounds is not a building; it is the outdoor service area for
irrigation and area lighting.

Cedar Row A (60 apartments on three floors) and Cedar Row B (64 apartments on
four floors) are multifamily housing buildings. The Cedar Row Common House
(18,400 sq ft) holds leasing, a community room, laundry, and the pool. The
Cedar Row Carport and Grounds is the outdoor service area for the solar carport,
parking lighting, and landscape irrigation.

The Central Plant (58,400 sq ft) is the only building at the plant site.

Ridgeline Turbine Field is not a building: it is the ridge that holds the ten
turbines and the met mast. Ridgeline Substation is the fenced substation and
control house at the point of interconnection; it holds the SCADA server and
the research lab's field office, and has no benchmarked floor area.

Every building appears once, under the site and operating unit that owns it, and
lists every meter that serves it whatever the provider or commodity. Each is
identified by its common name, service address, primary use, approximate size,
responsible department, operating contact, and primary weather station.

## Utility Services

Valley Electric District supplies external electric service. It bills monthly
energy, time-of-use charges, and billing demand. Science Center, Student Center,
Lakeview Residence Hall, the Recreation and Aquatics Center, and the Central
Plant also have interval demand data. Campus Grounds and the Cedar Row carport
take unmetered area-lighting service at a flat monthly charge. At the Ridgeline
substation Valley Electric meters both directions at 34.5 kV under its
generator interconnection schedule: it charges station service, credits the
farm's export, and moves that credit to the Central Plant's account under its
bill credit transfer rider.

Sierra Gas Utility supplies natural gas service. It bills monthly therms and is
used for heating, domestic hot water, pool heating, food-service loads, and the
plant boilers.

River City Utilities provides bundled municipal water, sewer, and stormwater
service. Potable water is metered. Sewer is billed from water volume. Stormwater
is an area-based service fee where applicable. Irrigation and fire-service
connections are billed on their own schedules; fire service has no metered
usage. Kitchen, pool-fill, and cooling-tower deduct meters are read by hand each
month so that water that never reaches the sewer can be credited.

Northlake Thermal Plant is the university's central plant, run as its own
operating unit. It buys electricity, gas, and makeup water at the plant, meters
what it produces (chilled water, steam, and condensate return, hourly), and
allocates chilled water and steam costs to the served buildings through internal
cost centers. The meters that measure what each building receives belong to that
building, not to the plant, so production and delivery can be compared.

Helios Onsite Solar owns and operates photovoltaic arrays under a power purchase
agreement at Science Center, Student Center, and the Cedar Row carport. It
provides generation, exported energy, monthly invoices, renewable energy
certificates, and avoided-emissions information.

Ridgeline Wind is the plant's own wind company. The plant buys everything the
turbines make at an internal transfer price, less a monthly credit for the
research lab's use of the site. Nobody sends that bill: we want the system to
generate the monthly statement from the ten turbine meters. Each turbine's
SCADA also reports power, the controller's possible power at the measured
wind, nacelle wind, rotor speed and run state every ten minutes, and the met
mast reports the free-stream wind in metric units.

## Accounts, Agreements, And Cost Centers

External utility accounts are maintained by Finance. Internal plant allocations
use cost centers rather than utility accounts. Solar service uses PPA agreement
ids. Ridgeline's output is bought under one transfer agreement whose statement
is generated, never received. Submeters that Northlake owns, including every Cedar Row apartment meter,
have no account of their own; their usage is recovered from the master meter's
bill. Account and agreement identifiers in this packet are synthetic and should
not be confused with real account numbers.

Required account details:

- Provider or internal service owner
- Service address or served property
- Account, cost center, or agreement id
- Effective start and end dates
- Billing contact
- Operating contact
- Rate schedule or agreement type

## Meters And Measured Points

Meters represent physical or logical measurement devices. Measured points
describe the streams exposed by those meters or data sources. A meter that only
has monthly bills carries no measured point; its usage stays on the utility
account. Every Cedar Row apartment has an owned electric submeter (hourly kWh
over the fixed network) and an owned water submeter (monthly handheld route:
register reading and usage); house submeters cover corridors, laundry, and
lighting.

Examples:

- Electric delivered kWh and demand kW
- Apartment submeter kWh
- Natural gas therms
- Potable water kgal, water register readings and route usage
- Chilled water ton-hours and tons
- Steam production klb and lb/h, condensate return kgal
- Solar generated kWh
- Solar exported kWh
- Electric-vehicle charger kWh
- Chiller controller kW and status
- Outdoor air temperature
- Indoor air temperature
- Relative humidity
- Turbine generated kWh, active power and possible power, every ten minutes
- Turbine nacelle wind (m/s), rotor speed (RPM) and run state
- Met mast wind speed (m/s), wind direction (degrees), air temperature,
  pressure (kPa), air density (kg/m3) and humidity
- Interconnection export, station service and reactive energy (kVArh)
- Airport wind speed in knots

## Data Sources

Northlake receives data from several source systems and vendors. These should be
documented as customer systems, not as implementation-specific import paths.

Known source categories:

- Utility billing files
- Electric interval files from meter data services
- AcquiSuite electric data logs
- MV90 electric and solar files
- BACnet central plant points
- Modbus plant controller points
- Spinwave wireless sensor files
- FIG-family provider files
- Fixed-network electric submeter files (apartments, house meters, laundry, and chargers)
- SQL historian extracts
- NOAA public weather station observations
- Aeris weather observations and forecasts
- Neptune handheld water route uploads, including the apartment submeter route
- MVRS handheld gas route uploads
- Handheld meter reading event files
- Ridgeline turbine SCADA and met mast files (ten-minute, Pacific Standard Time
  all year)

## Known Events

Known events should be documented before data loading so they can be handled
intentionally:

- Library electric meter replacement during August 2024
- Student Center gas estimated bill followed by a corrected bill
- Student Center electric missing interval block requiring backfill
- River City Utilities duplicate bundled billing file
- Cedar Row A municipal account number change at renewal
- Valley Electric District rate schedule change beginning January 2025
- One negative-test utility file with unsupported units, excluded from normal loads
- Ridgeline acquisition on July 1, 2024: its accounts and meters start that day,
  and Valley Electric's generator account moved to the plant under a new number
- The first bill credit transfer, on the Central Plant's September 2024 bill
  (August 5 to September 4), for the generator account's first bill (July 1 to
  August 4)
- Ridgeline WTG-07 gearbox outage, February 11 to April 22, 2025

## Current Decisions And Open Items

Since packet 0.3 we use one inventory standard: a building appears once, under the
operating unit that owns its site, and holds every meter that serves it; the
thermal plant is its own operating unit and a provider to the campus; Cedar Row
is master-metered with an owned submeter in every apartment; meters that only
have bills carry no measured points; and buildings keep the names we use every
day. The Facilities and Meter Register and Source System Inventory record the
building areas, source owners, and delivery cadence. Cedar Row has water and
sewer without stormwater. Student Center receives steam without chilled water.
KSAC supplies the shared observation reference for the campus and plant
buildings, Cedar Row benchmarks on KSMF, which is also the forecast source, and
the Ridgeline site uses KSUU. Northlake retains the solar RECs.

Packet 0.4 adds the Ridgeline Wind Site as a second site of the thermal plant.
The plant buys its output at a transfer price, the system generates that
statement, Valley Electric's export credit lands on the Central Plant's bill,
and university researchers read the site without seeing anything else of the
plant or any bill. We retain Ridgeline's RECs as well.

The remaining work is to confirm installed configuration through the UI,
supply and test the other data feeds (including the fixed-network submeter file
and the apartment water route), decide how the manual deduct-meter readings are
entered, and supply the Ridgeline SCADA sample files. Every sample bill is now
itemized on its provider's own read cycle and priced at the tariff. Rate calculations, permissions, bill
validations and reporting have their own later acceptance steps. The workbook's
Open Items tab records these boundaries.

## Appendix: Provided Inventory Workbook

The accompanying workbook includes these core inventory tabs, plus the expanded
relationship, source mapping, rate and later-phase requirements tabs:

- Hierarchy
- Departments & Responsibilities
- Sites
- Buildings
- Service Profiles
- Utility Services
- Accounts And Agreements
- Meters
- Units and Submeters
- Measured Points
- Data Sources
- Known Events
- Contacts
- Open Items

The current [Facilities and Meter Register](../intake-package/facilities-and-meter-register.pdf)
and generated Data Collection Workbook provide the expanded inventory, including
relationships, rollups, weather assignments and source measurement mappings.
Their structured facts come from the [versioned source manifests](../../generators/README.md).
They supersede conflicting inventory values in older workbooks and the Draft
0.1 PDF overview. Fixture availability and installed acceptance remain separate
from whether a requirement has been documented.
