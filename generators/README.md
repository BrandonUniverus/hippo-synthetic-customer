# Northlake packet and first meter sample

The first generator builds the facilities/meter register, customer source
mapping, gateway coverage, a blank UI-ID capture template, and three AcquiSuite
deliveries. It never opens a database or configures an EEM instance.

## Sources and ownership

| Source | Owns |
| --- | --- |
| `scenarios/demo-university-v1.yaml` | The physical inventory: companies, sites and the company that owns each, buildings with service profiles and apartment counts, accounts, utility meters and their channels, owned submeters and sources (with per-apartment templates), and gateway-side bindings |
| `providers/*.yaml` | Numeric base tariffs, identifier formats and provider facts |
| `eem/northlake-eem-stage1-setup-v1.yaml` | The level names shared by every company (Site, Building, Meter, Point), the scenario sites each company creates, the Weather Reference site and security groups |
| `eem/northlake-eem-metaworld-stage1b-v1.yaml` | EEM mapping only: measure types, which channel roles become points and how they are named, rate schedule and billing account kinds, weather stations and assignments, aggregates and baselines |
| `scenarios/northlake-onboarding-v1.yaml` | Packet decisions, contact responsibilities and department ownership, source descriptions, known events and first sample contract |
| `security/northlake-eem-security-v1.yaml` | Existing fictional people's names, titles, personal email and company ownership, reused for Northlake contacts |

These files own different fields and never re-list each other's facts; the
rules are in [`docs/northlake-inventory-standard.md`](../docs/northlake-inventory-standard.md).
The generator joins them: it expands the per-apartment submeter and gateway
templates (one electric and one water submeter for each of the 124 Cedar Row
apartments), builds the hierarchy from the scenario sites and buildings under
the company that owns each site, and asserts the join before writing anything
(account and meter numbers match the provider identifier formats, every meter
parent is a hierarchy node in the same company, gateway node and point ids are
unique, aggregate members share unit and interval, Stage 1 site ownership
matches the scenario). Change the owning source and regenerate; do not hand-edit
a generated workbook or register. Contact department mailboxes and phone numbers
come from onboarding; they can differ from personal login email. Departments &
Responsibilities takes its primary contact details from that same contact
register. Departments describe responsibility; the Hierarchy tab defines the
actual EEM nodes. Later-phase workbook tabs are preserved by the updater.

## Generate and validate

Python 3.11+ with the dependency in `requirements.txt`:

```powershell
python -m pip install -r generators/requirements.txt
python generators/northlake_packet.py --check
python -m unittest generators.tests.test_northlake_packet -v
python generators/northlake_packet.py
python generators/update_workbook.py
```

The third command writes customer Markdown/sample files, the EEM mapping template
and coverage, plus `out/northlake-onboarding/packet.json` for inspection. The
JSON intermediate is disposable and ignored by Git. Samples have fixed bytes and
checksums; there is no random or current-time input.

## Update the workbook

`update_workbook.py` rewrites the generated worksheets of the only customer
workbook, `outputs/northlake-university/data-collection-workbook.xlsx`, with
openpyxl. It rebuilds each generated tab (title, description, table, status
validation lists, widths, freeze panes) and leaves the later-phase tabs
(Chart of Accounts, Users & Access, Tenants & Leases, Sustainability, Projects)
exactly as they are. Hierarchy sits immediately after Instructions and covers
company, site and building nodes; Meters supplies their meter children using
full Parent Path values; Units and Submeters lists one row per apartment; and
Measured Points identifies each point's parent meter. The updater changes only
tables whose source data changed, so a repeat run with unchanged sources leaves
the workbook untouched, and it reopens its output to compare every generated
table value and every preserved sheet before reporting success.

Excel locks the workbook while it is open. Close it first, or pass
`--output <path>` to write the updated copy elsewhere and copy it over later.

## Render the intake binder

`render_intake_package.py` packages the customer Markdown documents listed in
[`design-brief.md`](../customer-provided/northlake-university/design-brief.md)
into `output/intake/Northlake Intake Package.html`: one self-contained page with
a cover, contents and a section per document, including the register and source
inventory. It formats and never rewrites; the packet version and issue date come
from `scenarios/northlake-onboarding-v1.yaml`, and the fonts are embedded from
`generators/fonts`. Run it after regenerating the Markdown:

```powershell
python generators/render_intake_package.py
python generators/render_intake_package.py --check
python -m unittest generators.tests.test_render_intake_package -v
```

`--check` exits with status 1 when the checked-in binder no longer matches its
sources. The test also proves every source word and table row reaches the page.
Print the page from a browser for a paper binder; the register and source
inventory print on landscape pages.

## Remaining source emulators

AcquiSuite is the first file emitter. MV90 MDEF/MV9, FIG variants, Spinwave,
Neptune, MVRS, bill import, the ODBC historian, weather fixtures, and live
BACnet/Modbus sources remain planned in
[`docs/synthetic-meter-system-plan.md`](../docs/synthetic-meter-system-plan.md).
Add one real intake format and its independently checked expected results at a
time. Do not bypass the gateway or bill importer by inserting EEM customer data.

Generated samples do not establish installed acceptance. Use
[`eem/northlake-onboarding-ui-checklist.md`](../eem/northlake-onboarding-ui-checklist.md)
to create the customer through the UI, exercise ingestion, record actual IDs
and results, and promote a tested restore baseline.
