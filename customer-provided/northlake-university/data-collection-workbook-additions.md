# Data Collection Workbook — New Tabs

Provided by: Northlake Facilities & Finance. Synthetic/illustrative. These are the
**additional tabs** to fold into the existing Data Collection Workbook (which
already has Organization Units, Sites, Buildings, Utility Services, Accounts &
Agreements, Meters, Measured Points, Data Sources, Known Events, Contacts, Open
Items). Presented as tables for the design team to render into the workbook.

## Tab: Rate Schedules

| Provider | Schedule | Type | Effective | Key charges |
| --- | --- | --- | --- | --- |
| Valley Electric | VED-TOU-GS | TOU + demand | 2024 | On/Part/Off energy, demand, facility |
| Valley Electric | VED-TOU-GS-FY25 | TOU + demand | 2025 | rate-change step |
| Sierra Gas | SGU-GN-1 | Seasonal | 2024–2025 | customer, winter/summer commodity, transport |
| River City | RCU-W-TIER | Tiered water | 2024–2025 | meter charge by size, 3 usage tiers |
| River City | RCU-S-VOL | Volumetric sewer | 2024–2025 | base + per-kgal on water |
| River City | RCU-SW-ERU | Flat stormwater | 2024–2025 | per ERU |
| Northlake Thermal | NTP-ALLOC-CHW | Internal allocation | 2024–2025 | per ton-hour + peak ton demand |
| Northlake Thermal | NTP-ALLOC-STEAM | Internal allocation | 2024–2025 | per klb |
| Helios Solar | HOS-PPA-2024 | PPA | 2024–2025 | per kWh generated, escalator, export credit |

(Detail in the rate tariff sheets. Analysis-only rates we'd like added: a
real-time/index electric option and a large-demand ratchet rate.)

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
| Cedar Row | A | 60 units | — | Sub-metered + occupancy | common-area |
| Cedar Row | B | 64 units | — | Sub-metered + occupancy | common-area |

## Tab: Sustainability

| Property | ENERGY STAR function | Score? | GHG scope sources |
| --- | --- | --- | --- |
| Main Campus (parent) | College/University | Yes | Scope 1 gas/plant, Scope 2 electric, Scope 3 water |
| Admin Hall | Office | Yes | as above |
| Science Center | Laboratory | Metrics only | as above |
| Library | Library | Yes | as above |
| Student Center | Food Service | Yes | as above |
| Cedar Row | Multifamily Housing | Yes | Scope 2 electric, Scope 3 water |

Solar = market-based Scope 2 reduction; Northlake retains RECs.

## Tab: Projects

| Project | Category | Capital | Incentive | M&V baseline |
| --- | --- | --- | --- | --- |
| Library LED Retrofit | Lighting | $120k | $25k | Library lighting kWh |
| Science Center Chiller Upgrade | HVAC | $640k | $80k | CHW ton-hours |
| Cedar Row Solar Expansion | Renewable | $410k | ITC | solar generation |
| Admin Hall Recommissioning | Controls | $55k | $10k | gas + electric |
