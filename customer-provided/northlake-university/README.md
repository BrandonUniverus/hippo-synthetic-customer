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

**Start here:** [Facilities and Meter Register](facilities-and-meter-register.md)
and [Data Collection](../../outputs/northlake-university/data-collection-workbook.xlsx),
the single customer workbook. Use **Contacts** for people, email and phone, and
**Departments & Responsibilities** for department ownership and primary contacts.
**Hierarchy** lists every company's site and building nodes (all three companies
use the Site, Building, Meter and Point levels); a building appears once, in the
company that owns its site. **Service Profiles**
records how each building is heated, cooled and otherwise served; **Units and
Submeters** lists one row per Cedar Row apartment with its electric and water
submeter. **Meters** gives each meter's full parent path. Responsible
departments on Sites and Buildings identify the team responsible for a property,
not its parent in the EEM tree. Packet **0.3** corrects and regenerates the
inventory: 3 operating companies, 13 buildings, 322 meters (including an
electric and a water submeter in each of the 124 Cedar Row apartments) and 431
measured points. The [Student Center AcquiSuite handover](sample-data/acquisuite/README.md)
supplies the first source files and expected values. Installed acceptance is
still pending; follow the [UI checklist](../../eem/northlake-onboarding-ui-checklist.md).

- `00-cover-letter.md` — transmittal letter from Northlake, with enclosures + contacts.
- `01-discovery-questionnaire.md` — completed discovery questionnaire (goals, scope, systems, success criteria).
- `northlake-facilities-and-utility-overview.md` — narrative facilities & utility overview.
- `rate-tariff-sheets/` — one tariff sheet per provider (Valley Electric, Sierra Gas, River City, Northlake Thermal, Helios Solar).
- `chart-of-accounts-and-gl-guide.md` — Finance: GL chart, coding segments, AP/ERP export targets.
- `user-access-request.md` — HR/IT: who needs access and to what (role matrix, separation of duties, the ~120 report recipients).
- `tenant-and-lease-roster.md` — Property Mgmt/Housing: Cedar Row apartment submeters, Town Center (later phase) and how costs are split.
- `sustainability-requirements.md` — Sustainability: ENERGY STAR, GHG scopes, targets, REC handling.
- `source-system-inventory.md` — IT/Facilities: data feeds, formats, cadence, owners.
- `facilities-and-meter-register.md` — complete building/account/meter/point inventory, related measurements, rollup members and weather assignments.
- `sample-data/acquisuite/` — one deterministic day, a missing-block delivery, its backfill and expected results.
- `data-collection-workbook-additions.md` — retained later-phase workbook requirements (rates, GL, users, tenants, sustainability and projects).

EEM application branding (customer-provided customization for the EEM portal):

- `eem-application-branding.md` — login page customization (`CustomLoginInfo`: logos, kicker/title, bullets, colors, "Need help?" contacts, CTA), logo/image asset specs, and transactional-email branding (colors, logo, footer, contacts).
- `eem-branding-design-brief.md` — prompt for Claude to generate the logo assets + filled login config + branded email templates (keeping all `{{tokens}}`).
- `eem-animation-design-brief.md` — prompt for Claude to generate two per-customer CSS+SVG animations (login-hero entrance + loading spinner) themed via the app's CSS custom properties (Northlake POC).

See `docs/dream-customer/engagement-document-set.md` for how this intake package
relates to the vendor-produced solution/integration documents.

## Generated Customer-Facing Artifacts

Generated files are built from these sources and written outside this directory:

- `output/pdf/northlake-facilities-overview-redone.pdf`
- `outputs/northlake-university/data-collection-workbook.xlsx` — the single implementation intake workbook, including contacts, source systems and tenants/leases.
- `output/intake/Northlake Intake Package.html` — the combined intake binder of every document above, rendered by `python generators/render_intake_package.py`.

The [versioned source manifests](../../generators/README.md) own the structured
facts, including the complete contact and department registers. The duplicate
inventory, source-system and tenant workbooks are retired; maintain the one
Data Collection workbook.
The older PDF overview and illustrated bills remain Draft 0.1 examples; the
current register supersedes conflicting inventory values. Bill examples still
need reconciliation before financial acceptance.

The workbook has 26 tabs: 21 generated tabs (Instructions, Hierarchy, Contacts,
Departments & Responsibilities, Known Events, Sites, Buildings, Service
Profiles, Utility Services, Rate Schedules, Rate Components, Accounts And
Agreements, Meters, Units and Submeters, Measured Points, Related Measurements,
Rollup Members, Weather Assignments, Open Items, Data Sources, Source
Measurements) plus 5 retained later-phase tabs (Chart of Accounts, Users &
Access, Tenants & Leases, Sustainability, Projects). Service Profiles and Units
and Submeters are new in packet 0.3. After `python generators/northlake_packet.py`,
rebuild the generated tabs with `python generators/update_workbook.py`; the
later-phase tabs are left as they are. Known Events and Open Items distinguish
supplied samples from later scenarios whose fixtures or product acceptance are
pending.

Contacts includes all eight implementation contacts named in the cover letter
and four external utility representatives. Cedar Row and Thermal Plant contacts
are assigned to their own companies. The contact register describes who to
reach; Users & Access remains the separate list of login and permission needs.

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
