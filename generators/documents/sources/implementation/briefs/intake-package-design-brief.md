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
small "Synthetic — Packet 0.3" marker on each document.

## Source files

All under: `documents/intake-package/`

- `00-cover-letter.md` — transmittal letter
- `01-discovery-questionnaire.md` — completed discovery questionnaire
- `northlake-facilities-and-utility-overview.md` — facilities & utility overview
- `facilities-and-meter-register.md` — building, account, meter and measured-point register (the same inventory as the workbook)
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
- `data-collection-workbook-additions.md` — later-phase requirements already included in the workbook

Existing workbook to extend (do not recreate from scratch):
`documents/intake-package/data-collection-workbook.xlsx`

This is the single customer workbook. Preserve its existing tabs and reuse the
source-system and tenant/lease tabs; do not generate separate inventory workbooks.

## Produce

| # | Document | From | Format |
| --- | --- | --- | --- |
| 1 | Cover / transmittal letter | 00-cover-letter.md | PDF (on letterhead) |
| 2 | Discovery Questionnaire | 01-discovery-questionnaire.md | PDF |
| 3 | Facilities & Utility Overview | northlake-facilities-and-utility-overview.md | PDF (cover page + TOC) |
| 4 | Rate Tariff Sheets (5) | rate-tariff-sheets/*.md | one PDF each, utility-rate-sheet style |
| 5 | Chart of Accounts & GL Coding Guide | chart-of-accounts-and-gl-guide.md | PDF |
| 6 | User Access Request & Role Matrix | user-access-request.md | PDF |
| 7 | Tenant & Lease Roster | tenant-and-lease-roster.md | Tenants & Leases tab in Data Collection (+ optional PDF summary) |
| 8 | Sustainability Reporting Requirements | sustainability-requirements.md | PDF |
| 9 | Source System Inventory | source-system-inventory.md | Data Sources and Source Measurements tabs in Data Collection (+ optional PDF) |
| 10 | Data Collection Workbook | the existing .xlsx and its versioned sources | One Excel workbook with 26 tabs (21 generated plus 5 retained later-phase tabs), including Hierarchy, Contacts, Departments & Responsibilities, Service Profiles and Units and Submeters |
| 11 | Combined Intake Package | all of the above | one bundled PDF "binder" with a cover page + table of contents |

## Brand & styling

- **Identity:** Northlake University — collegiate, professional. Palette: deep
  navy primary, slate gray, a warm gold accent. A simple "NORTHLAKE UNIVERSITY"
  wordmark with a small lake/leaf mark is fine (placeholder logo OK).
- **Letterhead / header:** university wordmark + "Facilities · Housing ·
  Sustainability · Finance," with a header on each page: *Northlake University —
  <Document Title> — Packet 0.3*.
- **Footer:** page X of Y + "Synthetic, fictional data — prepared for
  implementation setup."
- **Cover pages** on the overview and the combined binder (title, "Onboarding Data
  Package," coverage period Jan 1 2024 – Dec 31 2025, Packet 0.3).
- **Tariff sheets:** style like real utility rate sheets — provider name as the
  issuer, effective-date banners, clean rate tables — presented as enclosures
  Finance compiled.
- **Tables:** consistent styling, zebra rows, bold headers; keep all tables from
  the Markdown.
- **Voice:** customer/operational language (property, site, building, cost center,
  utility account, meter, measured point). Don't add software/implementation
  jargon.

## Output

Write the rendered files to `documents/intake-package/`, named clearly (e.g.
`01-northlake-cover-letter.pdf`, `northlake-intake-package.pdf`); the workbook
stays at `documents/intake-package/data-collection-workbook.xlsx`. Preserve
all content from the sources; you are formatting and packaging, not rewriting.

---
