# Northlake University — Implementation Discovery Questionnaire (Completed)

Prepared by: Campus Operations, with Facilities, Finance, Housing, and
Sustainability. Packet version: Draft 0.1.

This is our response to your standard discovery questionnaire. Answers reflect
how we operate today and what we want the new system to do.

## 1. Organization & goals

**1.1 Describe your organization.**
Northlake University is a mid-size university operating a main academic campus, a
student housing property (Cedar Row Apartments), and a mixed-use property
(Northlake Town Center). Facilities Operations manages campus utilities, building
automation, and meters. Housing Operations manages Cedar Row. Finance owns
external utility payment and internal cost allocation. The Sustainability Office
owns reporting.

**1.2 What are your top goals for this system?**
1. One source of truth for all utility usage and cost across properties.
2. Accurate monthly bill processing, validation, and payment/AP export.
3. Internal cost allocation for our central thermal plant.
4. Tenant sub-metering and rebilling at Town Center and Cedar Row.
5. Sustainability reporting: ENERGY STAR scores and greenhouse-gas emissions.
6. Scheduled reports delivered automatically to building and finance staff.

**1.3 What does success look like in 12 months?**
Every property's bills load and reconcile automatically; Finance exports approved
costs to our ERP; tenants are billed accurately; we submit ENERGY STAR scores and
report emissions by scope; and ~120 staff receive the reports they need without
asking us to run them.

## 2. Scope

**2.1 Properties in scope.** Northlake Main Campus (4 buildings + central plant +
solar), Cedar Row Apartments (2 buildings + common area + carport), Northlake
Town Center (retail + office tower + annex + infrastructure).

**2.2 Commodities.** Electricity, natural gas, water, sewer, stormwater, chilled
water, steam, and onsite solar generation.

**2.3 In scope now vs later.** Town Center tenant rebilling and EnergyAI insights
are desired but we understand they may follow once the core is live.

## 3. Utilities & billing

**3.1 Who are your providers?** Valley Electric District (electric), Sierra Gas
Utility (gas), River City Utilities (bundled water/sewer/stormwater), Northlake
Thermal Plant (internal chilled water + steam), Helios Onsite Solar (PPA).

**3.2 How do bills arrive today?** A mix of vendor billing files and PDF
statements. Electric and water can be delivered as files; gas and the solar PPA
are entered from statements. Tariff sheets and samples are enclosed.

**3.3 Do you have time-of-use / demand / tiered rates?** Yes — TOU and billing
demand on electric, tiered water, seasonal gas, internal allocation rates, and a
PPA. See the rate tariff sheets. We also want to model a real-time-pricing option
and a large-demand ratchet rate for analysis.

**3.4 How are utility costs coded for accounting?** By GL account plus our five
coding segments (Fund, Department, Program, Activity, Object). See the GL guide.
We export approved costs to our ERP for payment.

## 4. Metering & data

**4.1 What meter/interval data do you have?** 15-minute electric interval at
Science Center and Student Center; 15-minute solar generation/export; hourly
chilled-water; monthly reads elsewhere. Water/gas include handheld route reads.

**4.2 What source systems feed data?** Utility billing files, meter-data-service
interval files, AcquiSuite and MV90 files, central-plant BACnet and Modbus
points, wireless sensor files, a SQL historian, NOAA and Aeris weather, and
handheld route uploads. See the Source System Inventory.

**4.3 Weather.** We use Sacramento-area public stations (KSAC primary, KSMF
secondary). We are still confirming the preferred station per property.

## 5. Users & access

**5.1 How many users?** ~19 core operational users across the three properties
plus implementation/support, and a broader audience of ~120 building
representatives who should receive scheduled reports.

**5.2 How do you think about roles?** Company administrators, facilities/utility
setup, rates, bill entry, bill import, report viewers, sustainability reporters,
auditors, plant operators, and a thermal allocation accountant. See the User
Access Request. We require approval authority separation (the person who enters a
bill is not the person who approves it).

## 6. Reporting

**6.1 What reports matter most?** Cost and usage by property/building, bill
variance, fiscal-period processing, rate analysis, tenant bills, ENERGY STAR
ratings, and greenhouse-gas reports.

**6.2 Delivery.** Monthly building energy report to building representatives;
weekly cost rollup to Finance; daily operations report to operations staff. We'd
like these emailed automatically.

## 7. Current pain points

- Utility data lives in spreadsheets and vendor portals; no single rollup.
- Manual bill entry is slow and error-prone; no validation.
- Thermal plant cost allocation is a manual monthly exercise.
- No tenant rebilling system for Town Center; done by hand.
- Sustainability reporting is assembled manually each year.

## 8. Known events & data-quality notes

We have documented intentional events (meter replacement, estimated→corrected
bill, account-number change, rate change, a duplicate billing file, and a missing
interval block) in the overview and workbook so they can be handled deliberately.

## 9. Key contacts

See the cover letter contact table. Project sponsor: Samantha Ireland.
