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
  scenario-catalog.md          Behavioral scenarios this dataset should exercise.
  integration-coverage.md      Coverage matrix for gateways, reports, and integrations.
schemas/
  synthetic-source-model.md    Source database model and invariants.
scenarios/
  demo-university-v1.yaml      Machine-readable scenario manifest.
generators/
  README.md                    Generator expectations and future command shape.
```

## Current Status

This repo currently contains the starting contract for the synthetic customer. The next step is to choose the first generator implementation and create the synthetic source database schema from `schemas/synthetic-source-model.md`.

## Operating Rules

- The synthetic source model is the source of truth.
- Generated files are outputs, not hand-edited fixtures.
- Generation must be deterministic from checked-in manifests and seed values.
- Every scenario should define expected downstream assertions.
- Any intentionally invalid data must be labeled as a negative test scenario.
