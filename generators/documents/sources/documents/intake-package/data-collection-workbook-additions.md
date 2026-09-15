---
department: Facilities Operations
---

# Data Collection Workbook — Later-Phase Requirements

Provided by: Northlake Facilities & Finance. Synthetic/illustrative. These
requirements are already represented in the Data Collection Workbook. Packet
0.3 gives the workbook 26 tabs: 21 tabs generated from the inventory (including
Hierarchy, Service Profiles, Meters, Units and Submeters, Measured Points,
related measurements, rollup members, weather assignments, rate schedules and
components, and source mappings) and the 5 later-phase tabs below. Contacts and
Departments & Responsibilities contain the complete implementation directory and
department ownership. Hierarchy records each company's sites and buildings; a
building appears once, in the company that owns its site, and Meters supplies
each meter's full parent path.

This document retains the later-phase requirement tables. Current structured
inventory and tariff values are generated from the
[versioned sources](../../generators/README.md); installed setup and acceptance
are recorded separately.

## Rate schedules

The Rate Schedules and Rate Components tabs are generated from our five
providers' tariffs (14 base schedules); the rate tariff sheets carry the detail.
Analysis-only rates we'd like added: a real-time/index electric option and a
large-demand ratchet rate.

## Tab: Chart of Accounts

| GL account | Type | Description | Default Fund | Default Dept |
| --- | --- | --- | --- | --- |
| 5100-ELEC | Expense | Electricity | 110 Operating | Facilities |
| 5110-GAS | Expense | Natural gas | 110 Operating | Facilities |
| 5120-WATER | Expense | Water/sewer/stormwater | 110 Operating | Facilities |
| 5130-THERMAL | Expense | Chilled water/steam | 700 Plant | Facilities |
| 5140-SOLAR | Expense | Solar PPA | 110 Operating | Facilities |
| 2000-AP | Liability | AP control | — | — |

Coding segments: Fund, Department, Program, Activity/Project, Object.

## Tab: Users & Access

| Name | Title | Property | Role | Status |
| --- | --- | --- | --- | --- |
| Samantha Ireland | Director of Campus Operations | University | Company admin / reports | Active |
| Jordan Hale | Facilities Systems Manager | University | Hierarchy/meter setup | Active |
| Priya Nandakumar | Energy Finance Lead | University | Utility & rate setup; import | Active |
| Nora Chen | Bill Import Specialist | University + Cedar Row | Bill import (cross-property) | Active |
| Iris Morales | Bill Entry Clerk | University | Bill entry (no approval) | Active |
| Leo Martinez | Sustainability Analyst | University | Sustainability reports | Active |
| Emerson Fox | Campus Data Administrator | University | Data/DB admin | Active |
| Quinn Roberts | Internal Audit Reviewer | All | Read-only audit (cross) | Active |
| Keiko Tan | Thermal Allocation Accountant | University + Plant | Allocation rates | Active |
| Dana Okafor | Science Center Coordinator | University | Reports — Science Center only | Active |
| Casey Holt | Former Bill Entry Clerk | University | (disabled — no login) | Disabled |
| Maya Chen | Property Manager | Cedar Row | Company admin / reports | Active |
| Marcus Reed | Accounts Coordinator | Cedar Row | Bill entry | Active |
| Valerie Kim | Housing Operations Analyst | Cedar Row | Hierarchy / reports | Active |
| Devon Brooks | Thermal Plant Manager | Plant | Company admin / operator | Active |
| Riley Santos | Thermal Plant Operator | Plant | Plant operator / reports | Active |
| Avery Singh | EEM Database Administrator | Support | System DB admin | Active |
| Morgan Patel | Implementation Consultant | Support | App setup | Active |
| Taylor Bennett | Support Analyst | Support | Read-only support | Active |

Plus ≈120 building representatives as **report-delivery recipients** (groups).

## Tab: Tenants & Leases

Cedar Row is part of this packet; Town Center is a later implementation phase.

| Property | Building | Tenant / space | Approx. size | Split method | Master meter |
| --- | --- | --- | --- | --- | --- |
| Town Center | Market Hall | Anchor Store | — | Fixed + common | Mall-Main |
| Town Center | Market Hall | Food Court | — | 15% | Mall-Main |
| Town Center | Market Hall | In-line Shop 1–4 | by sq ft | Building area | Mall-Main |
| Town Center | Tower | Floor 1–4 | — | Sub-metered | Tower-Main |
| Town Center | Tower | Landlord/house | — | Remainder | Tower-Main |
| Town Center | Campus Annex | Bldg A/B/C | — | Usage + coincident demand | Annex-Main |
| Town Center | Substation | Substation 1/2 | — | % of usage | Substation-Master |
| Town Center | — | Property Total | — | Aggregation of all | — |
| Cedar Row | A | 60 apartments | — | By apartment electric and water submeter; sewer capped at winter average; house submeters as overhead | Cedar Row A Electric Master; Cedar Row A Water Master |
| Cedar Row | B | 64 apartments | — | Same as A | Cedar Row B Electric Master; Cedar Row B Water Master |

## Tab: Sustainability

| Property | ENERGY STAR function | Score? | GHG scope sources |
| --- | --- | --- | --- |
| Main Campus (parent) | College/University | Metrics only | Scope 1 gas, Scope 2 electric, Scope 3 water; allocated plant steam and chilled water |
| Admin Hall | Office | Metrics only | as above |
| Science Center | Laboratory | Metrics only | as above |
| Library | Library | Metrics only | as above |
| Student Center | Food Service | Metrics only | as above |
| Lakeview Residence Hall | Residence Hall/Dormitory | Yes | as above |
| Recreation and Aquatics Center | Fitness Center/Health Club/Gym | Metrics only | as above |
| Parking Structure | Parking | Metrics only | Scope 2 electric |
| Cedar Row | Multifamily Housing | Yes | Scope 1 gas, Scope 2 electric, Scope 3 water |
| Central Plant | Other - Utility | Metrics only | Scope 1 boiler gas, Scope 2 electric, Scope 3 makeup water |

Solar = market-based Scope 2 reduction; Northlake retains RECs.

## Tab: Projects

| Project | Category | Capital | Incentive | M&V baseline |
| --- | --- | --- | --- | --- |
| Library LED Retrofit | Lighting | $120k | $25k | Library lighting kWh |
| Central Plant Chiller Upgrade | HVAC | $640k | $80k | plant kWh per CHW ton-hour |
| Cedar Row Solar Expansion | Renewable | $410k | ITC | solar generation |
| Admin Hall Recommissioning | Controls | $55k | $10k | gas + electric |
