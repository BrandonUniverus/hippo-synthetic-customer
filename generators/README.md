# Generators

Generator code will live here once the source model is finalized.

> The generation core + file/DB/API **intake emulators** are Layer 1–2 of the
> **Synthetic Meter System** — see
> [`docs/synthetic-meter-system-plan.md`](../docs/synthetic-meter-system-plan.md)
> for the full plan (fake meters emitting into every gateway's real intake path,
> plus a web control plane to turn meters on/off and drive scenarios).

The generators should transform checked-in manifests and synthetic source database rows into ingestion-ready artifacts. They should not contain hidden random data or hand-maintained customer facts.

## Expected Command Shape

The exact implementation language is still open. The command interface should eventually support flows like:

```powershell
generate-source --scenario scenarios/demo-university-v1.yaml --output out/source
generate-artifacts --scenario scenarios/demo-university-v1.yaml --source out/source --output artifacts/demo-university-v1
validate-artifacts --scenario scenarios/demo-university-v1.yaml --artifacts artifacts/demo-university-v1
```

## Generator Requirements

- Deterministic output from manifest and seed.
- Stable synthetic identifiers.
- No production customer data.
- Clear artifact traceability.
- Positive and negative scenarios separated.
- Validation output that can run in CI or a devserver smoke test.

## Artifact Types

Initial artifact targets:

- MDEF files.
- BIF files.
- Backfill inputs.
- Provider-like billing files.
- Provider-like interval files.
- Integration export payloads.

Generated artifacts should stay out of git unless a small golden fixture is intentionally checked in for tests.
