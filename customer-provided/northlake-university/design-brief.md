# Design Brief — Render the Northlake Intake Package

Paste the block below into Claude (with document-generation / design capability),
attaching or pointing it at the Markdown sources listed. It turns the package into
polished, corporate-looking deliverables. Reusable: edit the "Produce" list to
choose which documents to render.

---

You are producing a polished **customer onboarding / implementation intake
package** for an energy-and-utility management software engagement. The customer
is **Northlake University** (fictional). I'll give you Markdown source files;
render them as professional documents that look like Northlake's Facilities,
Finance, Housing, and Sustainability teams assembled and sent them to their
software vendor.

**Important:** the content is **synthetic/fictional**. Use the values exactly as
written — do not invent real companies, people, addresses, or numbers. Keep a
small "Synthetic — Draft 0.1" marker on each document.

## Source files

All under: `customer-provided/northlake-university/`

- `00-cover-letter.md` — transmittal letter
- `01-discovery-questionnaire.md` — completed discovery questionnaire
- `northlake-facilities-and-utility-overview.md` — facilities & utility overview
- `rate-tariff-sheets/valley-electric-district.md`
- `rate-tariff-sheets/sierra-gas-utility.md`
- `rate-tariff-sheets/river-city-utilities.md`
- `rate-tariff-sheets/northlake-thermal-plant.md`
- `rate-tariff-sheets/helios-onsite-solar.md`
- `chart-of-accounts-and-gl-guide.md`
- `user-access-request.md`
- `tenant-and-lease-roster.md`
- `sustainability-requirements.md`
- `source-system-inventory.md`
- `data-collection-workbook-additions.md` — new tabs to add to the workbook

Existing workbook to extend (do not recreate from scratch):
`outputs/northlake-university/northlake-organization-inventory-filled.xlsx`

## Produce

| # | Document | From | Format |
| --- | --- | --- | --- |
| 1 | Cover / transmittal letter | 00-cover-letter.md | PDF (on letterhead) |
| 2 | Discovery Questionnaire | 01-discovery-questionnaire.md | PDF |
| 3 | Facilities & Utility Overview | northlake-facilities-and-utility-overview.md | PDF (cover page + TOC) |
| 4 | Rate Tariff Sheets (5) | rate-tariff-sheets/*.md | one PDF each, utility-rate-sheet style |
| 5 | Chart of Accounts & GL Coding Guide | chart-of-accounts-and-gl-guide.md | PDF |
| 6 | User Access Request & Role Matrix | user-access-request.md | PDF |
| 7 | Tenant & Lease Roster | tenant-and-lease-roster.md | Excel (+ 1-page PDF summary) |
| 8 | Sustainability Reporting Requirements | sustainability-requirements.md | PDF |
| 9 | Source System Inventory | source-system-inventory.md | Excel (+ PDF) |
| 10 | Data Collection Workbook | the existing .xlsx + data-collection-workbook-additions.md | Excel — add tabs: Rate Schedules, Chart of Accounts, Users & Access, Tenants & Leases, Sustainability, Projects |
| 11 | Combined Intake Package | all of the above | one bundled PDF "binder" with a cover page + table of contents |

## Brand & styling

- **Identity:** Northlake University — collegiate, professional. Palette: deep
  navy primary, slate gray, a warm gold accent. A simple "NORTHLAKE UNIVERSITY"
  wordmark with a small lake/leaf mark is fine (placeholder logo OK).
- **Letterhead / header:** university wordmark + "Facilities · Housing ·
  Sustainability · Finance," with a header on each page: *Northlake University —
  <Document Title> — Draft 0.1*.
- **Footer:** page X of Y + "Synthetic, fictional data — prepared for
  implementation setup."
- **Cover pages** on the overview and the combined binder (title, "Onboarding Data
  Package," coverage period Jan 1 2024 – Dec 31 2025, Draft 0.1).
- **Tariff sheets:** style like real utility rate sheets — provider name as the
  issuer, effective-date banners, clean rate tables — presented as enclosures
  Finance compiled.
- **Tables:** consistent styling, zebra rows, bold headers; keep all tables from
  the Markdown.
- **Voice:** customer/operational language (property, site, building, cost center,
  utility account, meter, measured point). Don't add software/implementation
  jargon.

## Output

Write the rendered files to an `output/` folder, named clearly (e.g.
`01-northlake-cover-letter.pdf`, `data-collection-workbook.xlsx`,
`northlake-intake-package.pdf`). Preserve all content from the sources; you are
formatting and packaging, not rewriting.

---
