# Northlake packet and first meter sample

The first generator builds the facilities/meter register, customer source
mapping, gateway coverage, a blank UI-ID capture template, and three AcquiSuite
deliveries. It never opens a database or configures an EEM instance.

## Sources and ownership

| Source | Owns |
| --- | --- |
| `scenarios/demo-university-v1.yaml` | Physical sites, source account/meter identifiers, channels and gateway-side bindings |
| `providers/*.yaml` | Numeric base tariffs and provider facts |
| `eem/northlake-eem-metaworld-stage1b-v1.yaml` | Company ownership, EEM display names, point definitions, relationships, weather assignments and aggregates |
| `scenarios/northlake-onboarding-v1.yaml` | Packet decisions, contact responsibilities and department ownership, supporting locations, source descriptions, known events and first sample contract |
| `security/northlake-eem-security-v1.yaml` | Existing fictional people's names, titles, personal email and company ownership, reused for Northlake contacts |

These files own different fields. They are not independent copies of the same
inventory. Account and channel joins are validated before generation. Change
the owning source and regenerate; do not hand-edit a generated workbook or
register. Contact department mailboxes and phone numbers come from onboarding;
they can differ from personal login email. Organization Units takes its primary
contact details from that same contact register. Later-phase workbook tabs are
preserved by the updater.

## Generate and validate

Python 3.11+ with the dependency in `requirements.txt`:

```powershell
python -m pip install -r generators/requirements.txt
python generators/northlake_packet.py --check
python -m unittest discover -s generators/tests -v
python generators/northlake_packet.py
```

The last command writes customer Markdown/sample files, the EEM mapping template
and coverage, plus `out/northlake-onboarding/packet.json` for workbook rendering.
The JSON intermediate is disposable and ignored by Git. Samples have fixed
bytes and checksums; there is no random or current-time input.

## Update the workbook

`build_workbook.mjs` uses the supported `@oai/artifact-tool` JavaScript runtime.
Use the workspace dependency runtime supplied by Codex; do not modify its
dependency directory. If the package is not on the script's normal module path,
set `NORTHLAKE_ARTIFACT_RUNTIME` to a directory whose `node_modules` contains it
(a temporary junction to the supplied dependency directory is sufficient).

```powershell
# After generating packet.json, using the supplied Node executable:
node generators/build_workbook.mjs
```

The only customer workbook is
`outputs/northlake-university/data-collection-workbook.xlsx`. It contains the
inventory, contacts, source systems and tenant/lease requirements. The duplicate
organization, source-system and tenant workbooks are retired. The updater
changes only tables whose source data changed; a repeat run with unchanged
sources leaves the workbook untouched.

Set `NORTHLAKE_PREVIEW_DIR` to a temporary directory to render changed
worksheets for visual review. The updater reopens its export, compares every
generated table value, and compares values/formulas on unaffected sheets. Preview images and
tool inspection sidecars are not customer deliverables.

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
