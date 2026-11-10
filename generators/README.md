# Northlake packet and first meter sample

The first generator builds the facilities/meter register, the customer source
mapping and three AcquiSuite deliveries. It never opens a database or configures an EEM instance. Every other
Northlake document is rendered from its Markdown source; see
[`documents/README.md`](documents/README.md).

## Sources and ownership

| Source | Owns |
| --- | --- |
| `data/scenarios/demo-university-v1.yaml` | The physical inventory: companies, sites and the company that owns each, buildings with service profiles and apartment counts, accounts, utility meters and their channels, owned submeters and sources (with per-apartment templates), and gateway-side bindings |
| `data/providers/*.yaml` | Numeric base tariffs, identifier formats and provider facts: remit and business addresses, website and icon, bill cycles, and each company's vendor number |
| `data/eem/northlake-eem-stage1-setup-v1.yaml` | The level names shared by every company (Site, Building, Meter, Point), the scenario sites each company creates, the Weather Reference site and security groups |
| `data/eem/northlake-eem-metaworld-stage1b-v1.yaml` | EEM mapping only: measure types, which channel roles become points and how they are named, which points EEM creates itself, the archive intervals and index the editor allows, meter multipliers and bill-cycle rules, rate schedule and billing account kinds, weather stations and assignments, aggregates and baselines |
| `data/scenarios/northlake-onboarding-v1.yaml` | Packet decisions, contact responsibilities and department ownership, source descriptions, known events and first sample contract |
| `data/security/northlake-eem-security-v1.yaml` | Existing fictional people's names, titles, personal email and company ownership, reused for Northlake contacts |
| `data/eem/northlake-bill-entry-v1.yaml` | How each provider's bills arrive (import, manual, allocation, generation), which sets every account's Bill Entry Type |
| `data/eem/northlake-ap-gl-v1.yaml` | The GL chart, each account's AP upload flag and default GL accounts, and the bill validation tests set at account scope |
| `data/bills/*.yaml` | Every sample bill, one file per provider plus the Ridgeline-era set (every line, quantity, rate and total), which `render_bills.py` draws |

These files own different fields and never re-list each other's facts; the
rules are in [`implementation/stage-2-hierarchy/northlake-inventory-standard.pdf`](../implementation/stage-2-hierarchy/northlake-inventory-standard.pdf).
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

Python 3.11+ with the dependencies in `requirements.txt`:

```powershell
python -m pip install -r generators/requirements.txt
python generators/northlake_packet.py --check
python -m unittest generators.tests.test_northlake_packet -v
python generators/northlake_packet.py
python generators/update_workbook.py
```

The fourth command writes the register and source-system inventory PDFs to
`documents/intake-package/`, the AcquiSuite samples beside them, the gateway
coverage, billing account setup and meter and point setup PDFs to
`implementation/`, and the EEM mapping template to `data/eem/`. That template is
the full object sheet: a row per meter and point with the editor values each one
needs and blank columns for the installed IDs. Provider addresses and the Stage 1B billing account
rules resolve per account: service address from the building, remit address and
representative from the provider, and entry type, upload flag, invoice template
and GL defaults from the phase plans.
Pass `--dump-json <path>` to also write the joined packet for inspection. PDFs
and samples have fixed bytes; there is no random or current-time input.

## Update the workbook

`update_workbook.py` rewrites the generated worksheets of the only customer
workbook, `documents/intake-package/data-collection-workbook.xlsx`, with
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

## Render the bills

`render_bills.py` draws every bill in `data/bills/` into
`documents/utility-bills/<provider>/` as one-page PDFs with a text layer: the
provider's band, the account facts, a meter summary (with register reads, read
periods and the gas therm factor where a bill has them) and the charge detail.
Before drawing anything it checks the source: quantity x rate rounds to each
amount, a percentage line matches its base, the lines sum to the total, a
corrected bill covers the period of the bill it supersedes, and a credit
transferred out of one account arrives, with the opposite sign, on the bill it
names. A description with a comma must be quoted in its flow mapping; an
unknown line key fails the check rather than silently splitting the text.
`generators/tests/test_render_bills.py` adds what the customer's documents
require: every rate is the tariff's own, every period is one of its provider's
Stage 1 bill-cycle periods, every bill is dated no later than Stage 5 enters it,
and every meter, badge and multiplier is Stage 2's. While one provider's file is
being written, `--only data/bills/<file>.yaml` renders just that file and
`BILLS_ONLY=data/bills/<file>.yaml` limits the tests to it.

```powershell
python generators/render_bills.py
python generators/render_bills.py --check
python -m unittest generators.tests.test_render_bills -v
```

The test also ties every rate on a bill to the provider file's own schedule.

## Render the intake binder

`render_intake_package.py` packages the customer documents listed in the
[intake package design brief](../implementation/briefs/intake-package-design-brief.pdf)
into `documents/intake-package/Northlake Intake Package.html`: one self-contained page with
a cover, contents and a section per document, including the register and source
inventory. It formats and never rewrites: sections come from the Markdown in
`generators/documents/sources/documents/` and from the packet, the packet version and issue
date come from `data/scenarios/northlake-onboarding-v1.yaml`, and the fonts are
embedded from `generators/fonts`. Run it after changing a source:

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
BACnet/Modbus sources are specified per format in the
[Stage 3 chapter](../implementation/stage-3-gateways-and-data/stage-3-gateways-and-data.pdf).
Add one real intake format and its independently checked expected results at a
time. Do not bypass the gateway or bill importer by inserting EEM customer data.

Generated samples do not establish installed acceptance. The
[implementation guide](../implementation/northlake-implementation-guide.pdf)
and its stage chapters are how the customer is created through the UI, how
ingestion is exercised, and how the final restore baseline is promoted.
