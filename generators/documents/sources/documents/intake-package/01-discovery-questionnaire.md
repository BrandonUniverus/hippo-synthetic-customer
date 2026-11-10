---
department: Campus Operations
---

# Northlake University — Implementation Discovery Questionnaire (Completed)

Prepared by: Campus Operations, with Facilities, Finance, Housing, and
Sustainability. Packet version: 0.4.

This is our response to your standard discovery questionnaire. Answers reflect
how we operate today and what we want the new system to do.

## 1. Organization & goals

**1.1 Describe your organization.**
Northlake University is a mid-size university operating a main academic campus, a
student housing property (Cedar Row Apartments), a central thermal plant run as
its own operating company (Northlake Thermal Plant), and — in a later phase — a
mixed-use property (Northlake Town Center). Facilities Operations manages campus
utilities, building automation, and meters. Housing Operations manages Cedar Row.
The thermal plant has its own manager and operator, and since July 2024 it also
owns Ridgeline Wind, a ten-turbine wind site with its own site manager, which
doubles as the Mechanical Engineering department's Wind Energy Research Lab.
Finance owns external utility payment and internal cost allocation. The
Sustainability Office owns reporting.

**1.2 What are your top goals for this system?**
1. One source of truth for all utility usage and cost across properties.
2. Accurate monthly bill processing, validation, and payment/AP export.
3. Internal cost allocation for our central thermal plant.
4. Resident rebilling from our Cedar Row apartment submeters, and later tenant
   rebilling at Town Center.
5. Sustainability reporting: ENERGY STAR scores and greenhouse-gas emissions.
6. Scheduled reports delivered automatically to building and finance staff.
7. Wind performance: what each Ridgeline turbine made against what the wind
   made possible, and the energy the farm should have produced over any period.

**1.3 What does success look like in 12 months?**
Every property's bills load and reconcile automatically; Finance exports approved
costs to our ERP; tenants are billed accurately; we submit ENERGY STAR scores and
report emissions by scope; and ~120 staff receive the reports they need without
asking us to run them.

## 2. Scope

**2.1 Properties in scope.** Northlake Main Campus (seven buildings: Admin Hall,
Science Center, Library, Student Center, Lakeview Residence Hall, the Recreation
and Aquatics Center and the Parking Structure, plus Campus Grounds and onsite
solar),
Northlake Thermal Plant (the Central Plant, its own operating company, and the
Ridgeline Wind Site it bought on July 1, 2024: a turbine field and a substation
near Rio Vista), Cedar Row Apartments (Cedar Row A and B with 124 apartments,
the Common House, and the carport and grounds). Northlake Town Center (retail +
office tower + annex + infrastructure) is a later phase.

**2.2 Commodities.** Electricity, natural gas, water, sewer, stormwater, chilled
water, steam, onsite solar generation and off-site wind generation.

**2.3 In scope now vs later.** Town Center tenant rebilling and EnergyAI insights
are desired but we understand they may follow once the core is live.

## 3. Utilities & billing

**3.1 Who are your providers?** Valley Electric District (electric), Sierra Gas
Utility (gas), River City Utilities (bundled water/sewer/stormwater), Northlake
Thermal Plant (internal chilled water + steam), Helios Onsite Solar (PPA), and
Ridgeline Wind (the plant's own wind company, sold to the plant at an internal
transfer price).

**3.2 How do bills arrive today?** A mix of vendor billing files and PDF
statements. Electric and water can be delivered as files; gas and the solar PPA
are entered from statements. Ridgeline's monthly transfer statement is built by
hand today; we want the system to generate it from the turbine meters. Tariff
sheets and samples are enclosed.

**3.3 Do you have time-of-use / demand / tiered rates?** Yes — TOU and billing
demand on electric, tiered water, seasonal gas, internal allocation rates, a
PPA, a generator interconnection schedule whose export credit Valley Electric
moves to the Central Plant's bill, and Ridgeline's internal transfer price. See
the rate tariff sheets. We also want to model a real-time-pricing option and a
large-demand ratchet rate for analysis.

**3.4 How are utility costs coded for accounting?** By GL account plus our five
coding segments (Fund, Department, Program, Activity, Object). See the GL guide.
We export approved costs to our ERP for payment.

## 4. Metering & data

**4.1 What meter/interval data do you have?** 15-minute electric interval at
Science Center, Student Center, Lakeview Residence Hall, the Recreation and
Aquatics Center and the Central Plant; 15-minute solar generation/export; hourly
chilled-water and plant production; hourly electric and monthly water submeter
reads for every Cedar Row apartment; monthly reads elsewhere. Water/gas include
handheld route reads. At Ridgeline: 10-minute turbine SCADA (energy, power, the
controller's possible power, nacelle wind, rotor speed and run state) for each
of ten turbines, a 10-minute met mast in metric units, and Valley Electric's
15-minute interconnection meter in both directions with reactive energy.

**4.2 What source systems feed data?** Utility billing files, meter-data-service
interval files, AcquiSuite and MV90 files, central-plant BACnet and Modbus
points, wireless sensor files, fixed-network submeter files, a SQL historian,
NOAA and Aeris weather, handheld route uploads, and Ridgeline's SCADA file
export, whose clock stays on Pacific Standard Time all year. See the Source
System Inventory.

**4.3 Weather.** We use public airport stations: KSAC (Sacramento Executive
Airport) is the primary station for the campus and Central Plant buildings;
Cedar Row benchmarks on KSMF (Sacramento International Airport), which is also
our forecast source; and the Ridgeline site uses KSUU (Travis Air Force Base),
whose wind is reported in knots, as the long-term reference for its own met
mast. We want heating and cooling degree days derived from temperature.

## 5. Users & access

**5.1 How many users?** ~23 core operational users across the three properties
plus implementation/support, and a broader audience of ~120 building
representatives who should receive scheduled reports.

**5.2 How do you think about roles?** Company administrators, facilities/utility
setup, rates, bill entry, bill import, report viewers, sustainability reporters,
auditors, plant operators, a thermal allocation accountant, wind operations
limited to the Ridgeline site, and university researchers who may read the
Ridgeline site and nothing else of the plant. See the User Access Request. We
require approval authority separation (the person who enters a bill is not the
person who approves it).

## 6. Reporting

**6.1 What reports matter most?** Cost and usage by property/building, bill
variance, fiscal-period processing, rate analysis, tenant bills, ENERGY STAR
ratings, greenhouse-gas reports, and wind generation against the energy the
wind made possible, per turbine and for the farm.

**6.2 Delivery.** Monthly building energy report to building representatives;
weekly cost rollup to Finance; daily operations report to operations staff. We'd
like these emailed automatically.

## 7. Current pain points

- Utility data lives in spreadsheets and vendor portals; no single rollup.
- Manual bill entry is slow and error-prone; no validation.
- Thermal plant cost allocation is a manual monthly exercise.
- No tenant rebilling system for Town Center; done by hand.
- Sustainability reporting is assembled manually each year.
- Ridgeline's transfer statement and turbine performance are worked out by hand
  from SCADA exports, and the researchers ask us for files.

## 8. Known events & data-quality notes

We have documented intentional events (meter replacement, estimated→corrected
bill, account-number change, rate change, a duplicate billing file, a missing
interval block, the Ridgeline acquisition and its generator account transfer,
the first bill credit transfer, and a turbine gearbox outage) in the overview
and workbook so they can be handled deliberately.

## 9. Key contacts

See the cover letter contact table. Project sponsor: Samantha Ireland.
