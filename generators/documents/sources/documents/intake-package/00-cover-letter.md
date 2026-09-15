---
department: Campus Operations
prepared_by: Samantha Ireland, Director of Campus Operations
---

# Northlake University — Onboarding Data Transmittal

**To:** Energy & Utility Management Implementation Team
**From:** Samantha Ireland, Director of Campus Operations, Northlake University
**Date:** September 14, 2026 — onboarding packet 0.3
**Re:** Facilities, utility, and reporting data package for new energy management system setup
**Planned coverage period:** January 1, 2024 – December 31, 2025
**First interval delivery:** January 15, 2024 — Student Center electricity

---

Thank you for partnering with us on standing up our new energy and utility
management system. This package contains the source material our Facilities,
Housing, Finance, and Sustainability teams have assembled to describe how the
university is organized and how we want our utility data, billing, cost
allocation, and reporting handled.

We have written everything in our own operational terms — properties, sites,
buildings, departments, cost centers, utility accounts, service agreements,
meters, and measured points. We have intentionally **not** assumed any
particular software model; please map our information into your system as part
of the design phase and confirm the mapping back to us.

## What's enclosed

| # | Document | Owner team | Purpose |
| --- | --- | --- | --- |
| 1 | Facilities & Utility Overview | Facilities | Narrative of how we're organized |
| 2 | Discovery Questionnaire (completed) | Campus Operations | Goals, scope, systems, success criteria |
| 3 | Data Collection Workbook (26 tabs) + Facilities and Meter Register | Facilities / Finance | Current hierarchy, inventory, building service profiles, apartment submeters, measurement relationships, rollups and source mapping |
| 4 | Rate Tariff Sheets (5 providers) | Finance | Our utility rate schedules (14 across the five providers) |
| 5 | Chart of Accounts & GL Coding Guide | Finance / AP | How we want utility costs coded |
| 6 | User Access Request | HR / IT | Who needs access and to what |
| 7 | Tenant & Lease Roster | Housing / Property Mgmt | Sub-metered/allocated tenant spaces |
| 8 | Sustainability Reporting Requirements | Sustainability Office | ENERGY STAR, emissions, targets |
| 9 | Source System Inventory | IT / Facilities | Data feeds, formats, delivery cadence |
| 10 | Student Center AcquiSuite delivery files | Facilities | Complete day, missing block and replacement readings with expected totals |
| — | Illustrated utility bills, thermal allocations, solar invoices | Finance | Earlier examples; values require reconciliation before billing acceptance |

## How we're organized (quick orientation)

- **Northlake Main Campus** — academic campus: Admin Hall, Science Center,
  Library, Student Center, Lakeview Residence Hall, the Recreation and Aquatics
  Center, the Parking Structure and Campus Grounds, with onsite solar.
- **Northlake Thermal Plant** — our central plant (chilled water and steam), run
  as its own operating company with its own contact. It buys its own
  electricity, gas and water and allocates its cost to the campus buildings it
  serves.
- **Cedar Row Apartments** — nearby student housing (Cedar Row A and B, 124
  apartments), the Common House, and a solar carport with grounds. Each building
  is master-metered and we own an electric and a water submeter in every
  apartment; the utility never bills a resident.
- **Northlake Town Center** — a later implementation phase for our mixed-use property (retail, an office
  tower, a campus annex, and shared infrastructure) where we sub-meter and
  rebill tenants.

## Primary contacts

| Area | Contact | Role |
| --- | --- | --- |
| Overall / sponsor | Samantha Ireland | Director of Campus Operations |
| Facilities & meters | Jordan Hale | Facilities Systems Manager |
| Utility finance & rates | Priya Nandakumar | Energy Finance Lead |
| Bill processing | Iris Morales / Nora Chen | Bill Entry / Bill Import |
| Housing | Maya Chen | Cedar Row Property Manager |
| Thermal plant (its own operating company) | Devon Brooks | Thermal Plant Manager |
| Sustainability | Leo Martinez | Sustainability Analyst |

The **Contacts** tab in the Data Collection Workbook contains the full directory
with email addresses, phone numbers, company ownership and utility-provider
representatives. **Departments & Responsibilities** identifies each department's
organization and primary contact. **Hierarchy** lists, for each of our three
operating companies, its sites and buildings; a building appears once, under the
company that owns its site, and **Meters** and **Measured Points** list what sits
beneath it. **Units and
Submeters** lists every Cedar Row apartment with its electric and water
submeter. Source-system and tenant/lease inventories are tabs in that same workbook.

## A few things to know up front

- Identifiers in this package (account numbers, meter tags, addresses) are our
  internal references and may need normalizing on your side.
- We have flagged **known events** (a meter replacement, an estimated-then-
  corrected bill, an account-number change, a rate change, etc.) so they can be
  handled intentionally during loading rather than treated as errors.
- Several items are still marked **open** for our teams to confirm; see the Open
  Items list in the overview and workbook.
- Start with Student Center electricity, then expand across the supplied
  inventory. Other source-format samples and the full historical dataset will
  follow; a documented feed does not mean its files have been delivered yet.

We look forward to the design review. Please direct questions to me or the area
contacts above.

*Samantha Ireland*
Director of Campus Operations, Northlake University
