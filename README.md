# Hippo Synthetic Customer

This repository defines a deterministic fake customer used to exercise Hippo ingestion, gateways, reports, and external integrations without relying on production customer data.

The first customer is intentionally small enough to reason about and broad enough to grow into full integration coverage:

- A fictional university campus.
- A fictional apartment complex.
- Multiple utility providers and meter/account patterns.
- Public weather station references.
- Synthetic bills, interval reads, account changes, and known data quality events.

To start the Docker services and the Northlake site, follow the step-by-step [runbook](RUNBOOK.md).

## Goals

- Generate repeatable source data for demos and devserver validation.
- Produce ingestion artifacts such as MDEF, BIF, backfill inputs, and provider-like files from one source model.
- Validate downstream behavior with explicit assertions, not visual inspection alone.
- Keep all generated data fictional, deterministic, and safe to share internally.

## Non-goals

- Do not mirror a real customer's private usage, account, meter, or billing data.
- Do not create one-off fixtures that cannot be regenerated.
- Do not make production code depend on this repository.

## Repository Layout

```text
data/                    The customer source model, as versioned YAML
  scenarios/             Campus inventory and onboarding packet decisions
  providers/             The six utility providers
  bills/                 The itemized bills, as data (rendered to documents/utility-bills/)
  security/              People, companies, groups and permission profiles
  eem/                   The mapping rules the generators use (not the implementation)
documents/               Northlake University's own files, as PDFs
  intake-package/        What Northlake sent Energy Hippo: transmittal, questionnaire,
                         binder, data collection workbook, meter register, source-system
                         inventory, user access request, AcquiSuite sample delivery
  guides/                Facilities and utility overview, GL coding guide,
                         sustainability requirements, tenant and lease roster
  rate-tariffs/          One tariff sheet per provider
  utility-bills/         Bills and allocation statements, by provider
  brand/                 EEM portal brand kit: logos, email templates, animations
implementation/          The build of Northlake in EEMSuite: guide, roadmap, findings, briefs,
                         then one folder per stage with its chapter PDF, one YAML per EEM
                         editor in entry order, and a read-only checks.sql
identity/                Northlake's identity provider: a runnable Keycloak lab
generators/              Code that builds the packet, workbook, binder and every PDF
  documents/sources/     The Markdown behind each PDF
```

## Rebuild

```powershell
python -m pip install -r generators/requirements.txt
python generators/northlake_packet.py
python generators/update_workbook.py
python generators/render_bills.py
python generators/documents/build_documents.py
python generators/render_intake_package.py
```

In order: the register and source-system inventory PDFs with the AcquiSuite
samples; the workbook's generated tabs; the itemized bills from
`data/bills/`; every other PDF from its Markdown source; the intake binder.
Each step is
deterministic, so a repeat run with unchanged sources changes nothing. See
[generators](generators/README.md) and [documents](generators/documents/README.md).

## Current Status

Start with the [implementation guide](implementation/northlake-implementation-guide.pdf).
It explains the ten build stages and the eleventh, research-only stage for third-party services, how a stage folder is used (chapter, YAML per
editor, checks), and the rules: everything enters through the EEM applications
or a real data path, a missing screen is a product finding, and the build is
done once and kept as a database backup. The [roadmap](implementation/roadmap.pdf)
says what each stage unlocks; the
[report coverage matrix](implementation/report-coverage-matrix.pdf) maps all
115 reports to their stage; [product findings](implementation/product-findings.pdf)
is the backlog of gaps the build has met.

The customer packet under [documents/](documents/) is what Northlake sent
(packet 0.4, October 1, 2026): 3 companies, 15 buildings, 6 providers, 51
accounts, 336 meters and 506 points, including an electric and a water
submeter for each of the 124 Cedar Row apartments and the Ridgeline Wind Site
the Thermal Plant bought in July 2024 (ten turbines, a met mast, a Valley
Electric generator account whose export credit lands on the Central Plant's
bill, and a transfer statement EEM generates), a Student Center AcquiSuite
sample with normal-day, gap and backfill deliveries, tariff sheets, bills and a
brand kit. It is generated from the source model in `data/` and is not edited
to match the implementation.

The November 4, 2026 live check against **BVirtualPC / EEMSuite_Northlake** confirms
Stage 2 is complete: **2,210 expected records match**, with 51 billing accounts,
5 sites, 15 buildings, 336 meters and **552 points** (401 entered, 140 generated,
11 aggregates). The 21 additional weather points and four observation measurement
type corrections are installed.

Stage 1 passes its full stored-configuration check: **1,222 expected records match,
with zero failures or warnings**, including 716 permission rows, 91 groups,
67 memberships and 23 users. The **G:15 / audit_explorer level-1** grant is present
on the shared `eem_audit_readonly` master and all three company copies. Its checker
reflects the upgrade's System Health/GHG module grants and the replacement Audit
Explorer report. This verifies stored configuration; user login and UI permission
enforcement remain separate application checks.

Stage 3 **Step 2: Gateway Types and Gateways** has **258 of 258 direct bindings
ALREADY CORRECT**, with zero binding blockers. This includes the ten corrected
BACnet device IDs and all three nodes' blank BBMD fields, saved through
Configuration Tool and verified against the updated recipe. The saved bindings include all 30 NOAA weather
points, saved through Configuration Tool. Gateway 7 uses its own **NOAA / ECCC
Weather Gateway** type, with six nodes and explicit Measurement/OutputUnit mappings.
Aeris has its separate **Aeris Weather Gateway** type and optional PointType field.
The empty Aeris profile and two empty nodes are retained as a transition record.
The obsolete Aeris WeatherType choice, `history` / "NOAA current observations", was
removed after confirmation. All gateway-type comparisons now pass.

The five MDEF/MV9 nodes use **UTC**, and AcquiSuite's task default has
**MaxParallelism=2**. On November 4, all **11 reusable task definitions** were saved
through Configuration Tool, including Neptune **1067** and MVRS **1068**. Gateway
IDs, root directories, formats and NOAA operations now belong on schedules;
task defaults stay blank for those inputs, including required inputs.
The shared MV90, NOAA and FIG tasks have replacement schedules **28–31** for
Helios MV9, NOAA history, Fixed Network and Ridgeline. Their four old per-profile
tasks (1056, 1058, 1061 and 1062) and schedules (17, 19, 22 and 23) were removed
through Configuration Tool after confirmation. All **13 intended schedules currently
possible** are saved and disabled; the three handheld schedules still need their
Step 5 gateways. Spinwave and FIG workspace overrides have been cleared, leaving
each schedule's explicit RootDirectory. The live workflow/task checker passes
all configured task and schedule checks and reports only the three handheld
gateway/schedule prerequisites: three missing gateways and three missing schedules.
NOAA/Fake UTC date overrides are verified in SQL. The BACnet source passed its
earlier protocol probe on Ethernet 3 (`172.21.29.4`). Task **1066** uses the latest
`BacnetGateway` workflow; its hourly schedule **27** (item **15**) is disabled and
supplies the local interface. The reusable task's interface default is blank.
The local object-enablement setting now enables every collector required by the
recipe, including BACnet and Fake; the Profile Manager save also enables Web.
No acquisition task was run during this setup.

Follow the [Stage 2/3 weather run order](implementation/stage-3-gateways-and-data/README.md)
for the saved node IDs, verification and remaining work. The
[binding script](implementation/stage-3-gateways-and-data/02-gateway-point-assignments.sql)
is left in read-only preview mode; it does not need to be applied again.
My Imports contains point definitions only. The 12 forecast associations remain
application work in Step 6, after workflows/tasks and the intervening setup steps.

The 204 Neptune/MVRS registers (192 meters) belong to Step 5's handheld route configuration,
which reads `HMR_Reading`; they are excluded from direct point assignments.
The three handheld gateways are created in Step 5 on one parameterless type,
Handheld Meter Reading Gateway, with no nodes: Configuration Tool requires a type,
but Neptune and MVRS never read it, and the HMR reader returns its own synthetic node.
Explicitly choose Enabled for every IsEnabled parameter the component reads:
the installed editor saved an untouched None as 0 on the first new node, which
was corrected before continuing.
The Stage 3 entry checkpoint was taken on October 5, 2026, and it is the only Stage 3
backup: there is no configured-empty backup (decided November 5); Northlake is backed up
later, once it works end to end. The November 4 check confirms the interval archive is
still empty. The handheld schedules and routes, the baselines and the weather
associations remain before the acceptance runs, which use an order that needs no
restore. Baseline configuration is
part of Stage 3 because its measured points must first be bound to gateways.
Stages 4 to 10 are authored and waiting to be entered.

The repository also contains a runnable [synthetic identity provider](identity/README.md):
the security manifest as a resettable Keycloak realm with real login and
administration pages, configurable OIDC/SAML registrations and end-to-end
protocol verification for both standards.

## Operating Rules

- Versioned source manifests own the customer facts; see [field ownership and generation](generators/README.md). Workbooks are generated views, not a second source of truth.
- Documents are PDFs. Edit the Markdown source under `generators/documents/sources/` and rebuild; Markdown elsewhere is limited to READMEs and code documentation.
- Generated files are outputs, not hand-edited fixtures.
- Generation must be deterministic from checked-in manifests and seed values.
- Every scenario should define expected downstream assertions.
- Any intentionally invalid data must be labeled as a negative test scenario.
