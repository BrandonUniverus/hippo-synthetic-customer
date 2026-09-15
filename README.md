# Hippo Synthetic Customer

This repository defines a deterministic fake customer used to exercise Hippo ingestion, gateways, reports, and external integrations without relying on production customer data.

The first customer is intentionally small enough to reason about and broad enough to grow into full integration coverage:

- A fictional university campus.
- A fictional apartment complex.
- Multiple utility providers and meter/account patterns.
- Public weather station references.
- Synthetic bills, interval reads, account changes, and known data quality events.

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
data/                    Everything the synthetic customer is, as versioned YAML
  scenarios/             Campus inventory and onboarding packet decisions
  providers/             The five utility providers
  security/              People, companies, groups and permission profiles
  eem/                   How Northlake maps into EEM: setup and phase entry plans
documents/               Northlake University's own files, as PDFs
  intake-package/        What Northlake sent Energy Hippo: transmittal, questionnaire,
                         binder, data collection workbook, meter register, source-system
                         inventory, user access request, AcquiSuite sample delivery
  guides/                Facilities and utility overview, GL coding guide,
                         sustainability requirements, tenant and lease roster
  rate-tariffs/          One tariff sheet per provider
  utility-bills/         Bills and allocation statements, by provider
  brand/                 EEM portal brand kit: logos, email templates, animations
implementation/          Energy Hippo's plans, specs and checklists for Northlake, as PDFs
identity/                Northlake's identity provider: a runnable Keycloak lab
generators/              Code that builds the packet, workbook, binder and every PDF
  documents/sources/     The Markdown behind each PDF
```

## Rebuild

```powershell
python -m pip install -r generators/requirements.txt
python generators/northlake_packet.py
python generators/update_workbook.py
python generators/documents/build_documents.py
python generators/render_intake_package.py
```

In order: the register, source-system inventory and gateway coverage PDFs with the
AcquiSuite samples and the EEM mapping template; the workbook's generated tabs;
every other PDF from its Markdown source; the intake binder. Each step is
deterministic, so a repeat run with unchanged sources changes nothing. See
[generators](generators/README.md) and [documents](generators/documents/README.md).

## Current Status

Start with the [Northlake intake package](documents/intake-package/),
the [inventory standard](implementation/northlake-inventory-standard.pdf) it follows, and the
[first UI implementation checklist](implementation/northlake-onboarding-ui-checklist.pdf).
Use the single [Data Collection workbook](documents/intake-package/data-collection-workbook.xlsx)
for inventory, contacts, source systems and later-phase requirements. Contacts
and Departments & Responsibilities include the implementation people and
department owners for all three Northlake companies. Every company uses the same
Site, Building, Meter and Point levels; a building appears once, in the company
that owns its site, and holds every meter that serves it. Hierarchy lists the
company, site and building nodes, and Meters records each meter's full parent path.
Packet 0.3 renders one join of the scenario, provider and EEM mapping manifests:
3 companies, 13 buildings, 49 accounts, 322 meters (55 utility meters, 265 owned
submeters and sources, 2 weather stations) and 431 points, including one electric
and one water submeter for each of the 124 Cedar Row apartments. It supplies a
deterministic Student Center AcquiSuite normal-day, gap and backfill sample. The
gateway list covers 15 profiles / 21 format cases plus the handheld-event
publisher; only AcquiSuite has a generated intake sample so far.

UI setup, installed ingestion acceptance and baseline backup/restore are the
next steps. A source specification or generated sample is not an installed test
result. The broader rate, bill, AP/GL, tenant, security and reporting plans remain
available under `data/eem/` and `implementation/dream-customer/` for incremental implementation.

The repository also contains a runnable [synthetic identity provider](identity/README.md).
It converts the security manifest into a resettable Keycloak realm with
real login and administration pages, persistent sessions and keys, configurable
OIDC/SAML registrations, two concurrent disposable lab realms, and end-to-end
protocol verification for both standards.

## Operating Rules

- Versioned source manifests own the customer facts; see [field ownership and generation](generators/README.md). Workbooks are generated views, not a second source of truth.
- Documents are PDFs. Edit the Markdown source under `generators/documents/sources/` and rebuild; Markdown elsewhere is limited to READMEs and code documentation.
- Generated files are outputs, not hand-edited fixtures.
- Generation must be deterministic from checked-in manifests and seed values.
- Every scenario should define expected downstream assertions.
- Any intentionally invalid data must be labeled as a negative test scenario.
