# Northlake University Customer-Provided Packet

This directory contains customer-owned onboarding material for the fictional
Northlake University account. The packet is intentionally written as if it came
from Northlake Facilities, Housing, Sustainability, and Finance teams before any
implementation-specific system mapping.

## Files — Implementation Intake Package

Written in customer voice (per the language rules below). These are the markdown
sources; polished Word/PDF/Excel are generated from them. They translate the
internal specs (`eem/`, `providers/`, `security/`, `docs/dream-customer/`) back
into the business facts a real customer would actually send.

- `00-cover-letter.md` — transmittal letter from Northlake, with enclosures + contacts.
- `01-discovery-questionnaire.md` — completed discovery questionnaire (goals, scope, systems, success criteria).
- `northlake-facilities-and-utility-overview.md` — narrative facilities & utility overview.
- `rate-tariff-sheets/` — one tariff sheet per provider (Valley Electric, Sierra Gas, River City, Northlake Thermal, Helios Solar).
- `chart-of-accounts-and-gl-guide.md` — Finance: GL chart, coding segments, AP/ERP export targets.
- `user-access-request.md` — HR/IT: who needs access and to what (role matrix, separation of duties, the ~120 report recipients).
- `tenant-and-lease-roster.md` — Property Mgmt/Housing: Town Center + Cedar Row sub-metering and how costs are split.
- `sustainability-requirements.md` — Sustainability: ENERGY STAR, GHG scopes, targets, REC handling.
- `source-system-inventory.md` — IT/Facilities: data feeds, formats, cadence, owners.
- `data-collection-workbook-additions.md` — new workbook tabs (Rate Schedules, Chart of Accounts, Users & Access, Tenants & Leases, Sustainability, Projects).

EEM application branding (customer-provided customization for the EEM portal):

- `eem-application-branding.md` — login page customization (`CustomLoginInfo`: logos, kicker/title, bullets, colors, "Need help?" contacts, CTA), logo/image asset specs, and transactional-email branding (colors, logo, footer, contacts).
- `eem-branding-design-brief.md` — prompt for Claude to generate the logo assets + filled login config + branded email templates (keeping all `{{tokens}}`).
- `eem-animation-design-brief.md` — prompt for Claude to generate two per-customer CSS+SVG animations (login-hero entrance + loading spinner) themed via the app's CSS custom properties (Northlake POC).

See `docs/dream-customer/engagement-document-set.md` for how this intake package
relates to the vendor-produced solution/integration documents.

## Generated Customer-Facing Artifacts

Generated files are built from these sources and written outside this directory:

- `output/pdf/northlake-facilities-overview-redone.pdf`
- `outputs/northlake-university/northlake-organization-inventory.xlsx`
- `outputs/northlake-university/northlake-organization-inventory-filled.xlsx`

The filled workbook is the synthetic seed source of truth. It uses fictional but
complete addresses, contacts, account numbers, meter tags, source paths, and
event dates. Open items represent intentional data-quality or implementation
scenarios rather than missing seed structure.

## Customer Language Rules

Use customer and facilities language:

- property
- site
- building
- department
- cost center
- utility account
- service agreement
- meter
- measured point
- data source
- billing contact

Avoid implementation-specific language:

- seed table
- internal point id
- gateway runtime
- import component
- database schema
