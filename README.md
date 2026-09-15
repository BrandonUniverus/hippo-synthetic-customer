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
docs/
  vision.md                    Project principles and rollout plan.
  synthetic-customer-v1.md     First customer shape and data scope.
  northlake-inventory-standard.md  Adopted hierarchy and inventory rules (one building, once; one owner per fact).
  scenario-catalog.md          Behavioral scenarios this dataset should exercise.
  integration-coverage.md      Coverage matrix for gateways, reports, and integrations.
schemas/
  synthetic-source-model.md    Source database model and invariants.
providers/
  README.md                    Provider set overview (3 everyday + 2 unique).
  *.yaml                       Full configuration for each utility provider.
scenarios/
  demo-university-v1.yaml      Machine-readable scenario manifest.
security/
  northlake-eem-security-v1.yaml Stage 1 EEM company/context/group/user setup.
eem/
  northlake-eem-stage1-setup-v1.yaml DBAdmin-facing Stage 1 setup fields.
  northlake-eem-metaworld-stage1b-v1.yaml EEM mapping rules (measure types, point rules, weather, aggregates).
identity/
  README.md                    Runnable synthetic OIDC and SAML identity provider.
  compose.yml                  Pinned Keycloak, PostgreSQL, and HTTPS proxy stack.
generators/
  README.md                    Reproducible customer packet and first AcquiSuite sample.
```

## Current Status

Start with the [Northlake onboarding packet](customer-provided/northlake-university/README.md),
the [inventory standard](docs/northlake-inventory-standard.md) it follows, and the
[first UI implementation checklist](eem/northlake-onboarding-ui-checklist.md).
Use the single [Data Collection workbook](outputs/northlake-university/data-collection-workbook.xlsx)
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
available under `eem/` and `docs/dream-customer/` for incremental implementation.

The repository also contains a runnable [synthetic identity provider](identity/README.md).
It converts the Stage 1 security manifest into a resettable Keycloak realm with
real login and administration pages, persistent sessions and keys, configurable
OIDC/SAML registrations, two concurrent disposable lab realms, and end-to-end
protocol verification for both standards.

## Operating Rules

- Versioned source manifests own the customer facts; see [field ownership and generation](generators/README.md). Workbooks are generated views, not a second source of truth.
- Generated files are outputs, not hand-edited fixtures.
- Generation must be deterministic from checked-in manifests and seed values.
- Every scenario should define expected downstream assertions.
- Any intentionally invalid data must be labeled as a negative test scenario.
