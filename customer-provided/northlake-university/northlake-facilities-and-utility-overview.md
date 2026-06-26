# Northlake University Facilities And Utility Overview

Prepared by: Northlake University Facilities, Housing, Sustainability, and Finance  
Packet version: Draft 0.1  
Coverage period requested: January 1, 2024 through December 31, 2025

## Purpose

Northlake University is providing this packet to describe how the university
organizes properties, utility services, meters, measured points, billing
relationships, and operational data sources. The packet is intended to support a
new facilities and utility data setup without assuming any vendor-specific
database or software model.

## Organization

Northlake University operates a main academic campus and a nearby residential
apartment property. Facilities Operations manages campus utilities, building
automation systems, and meter maintenance. Housing Operations manages Cedar Row
Apartments. Finance owns external utility account payment and internal cost
allocation. Sustainability uses the same data for reporting, performance
tracking, and renewable energy accounting.

Primary groups:

- Facilities Operations
- Housing Operations
- Science Operations
- Dining And Events
- Library Administration
- Finance And Accounts Payable
- Sustainability Office

## Sites

Northlake Main Campus is the primary academic site. It contains administrative,
classroom, laboratory, library, dining, event, central plant, and solar
generation assets.

Cedar Row Apartments is a nearby student housing site with two residential
buildings, common-area electric service, municipal water and sewer service, and
one solar carport array.

## Buildings And Properties

Admin Hall is an office and classroom building. Science Center is the largest
laboratory and classroom building and has the highest base load. Library is a
library and study-space building. Student Center includes dining, commercial
kitchen, event, and student support areas. Cedar Row A and Cedar Row B are
multifamily housing buildings.

Each building should be identified by its common name, service address, primary
use, approximate size, responsible department, operating contact, and primary
weather station.

## Utility Services

Valley Electric District supplies external electric service. It bills monthly
energy, time-of-use charges, and billing demand. Science Center and Student
Center also have interval demand data.

Sierra Gas Utility supplies natural gas service. It bills monthly therms and is
used for heating and food-service loads.

River City Utilities provides bundled municipal water, sewer, and stormwater
service. Potable water is metered. Sewer is billed from water volume. Stormwater
is an area-based service fee where applicable.

Northlake Thermal Plant is a university-owned central plant. It allocates
chilled water and steam costs to served buildings using internal cost centers
and submetered consumption.

Helios Onsite Solar owns and operates photovoltaic arrays under a power purchase
agreement. It provides generation, exported energy, monthly invoices, renewable
energy certificates, and avoided-emissions information.

## Accounts, Agreements, And Cost Centers

External utility accounts are maintained by Finance. Internal plant allocations
use cost centers rather than utility accounts. Solar service uses PPA agreement
ids. Account and agreement identifiers in this packet are synthetic and should
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
describe the streams exposed by those meters or data sources.

Examples:

- Electric delivered kWh
- Electric billing demand kW
- Natural gas therms
- Potable water kgal
- Derived sewer kgal
- Stormwater ERUs
- Chilled water ton-hours
- Chilled water tons
- Steam klb
- Solar generated kWh
- Solar exported kWh
- Outdoor air temperature
- Indoor air temperature
- Relative humidity

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
- SQL historian extracts
- NOAA public weather station observations
- Aeris weather observations and forecasts
- Neptune handheld water route uploads
- MVRS handheld gas route uploads
- Handheld meter reading event files

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

## Open Items For Northlake

- Confirm final building ownership and operating contacts.
- Confirm billing contact names and email aliases.
- Confirm whether stormwater applies to Cedar Row buildings.
- Confirm central plant allocation rules for steam-only buildings.
- Confirm whether weather station KSAC or KSMF is preferred for each property.
- Confirm which solar attributes are retained by Northlake under the PPA.
- Confirm data source owners and delivery cadence for each source system.

## Appendix: Provided Inventory Workbook

The accompanying workbook contains the initial structured inventory tabs:

- Organization Units
- Sites
- Buildings
- Utility Services
- Accounts And Agreements
- Meters
- Measured Points
- Data Sources
- Known Events
- Contacts
- Open Items

The filled workbook is the synthetic seed source of truth for this customer
packet. It uses fictional but complete customer-facing values and should remain
understandable to Facilities, Housing, Finance, Sustainability, and vendor
contacts. Open items represent intentional data-quality or implementation
scenarios rather than missing seed structure.
