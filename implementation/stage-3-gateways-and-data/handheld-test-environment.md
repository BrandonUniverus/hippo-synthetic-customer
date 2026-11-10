# Northlake handheld testing environment

Status: first two-route source-side pilot implemented and verified, November 4, 2026.
See the [handheld service runbook](../../services/handheld/README.md) for startup, file
contracts, delivery and verification. Installed Northlake ingestion remains pending acceptance.

The Northlake impl and Northlake testing environment chats agreed this plan at the user's request.
The first deliverable is a small, usable handheld demonstration that exchanges actual files with
Northlake. Existing source generation, identity services, and acquisition schedules keep their
current state while it is built.

## End-to-end flow

1. Configure the real meters and reading channels using [Stage 3 Step 5](05-handheld-routes.yaml).
2. Export the actual route file from Northlake and capture its hash.
3. Import that file and a checked environment binding manifest into the handheld simulator.
4. Pick a fictional reader, open a route, record a reading or explicit skip, and add a visit note.
5. Review and finalize an immutable Neptune or MVRS return file.
6. Download it or explicitly deliver it into the selected gateway's RootDirectory/Input.
7. Run the existing disabled schedule through Northlake and verify its stored readings and logs.

The simulator's file-preparation and delivery states are separate from Northlake's import result.
Northlake's Configuration Tool, web application, workers, collectors, broker and storage remain the
system under test. The simulator has no SQL connection, EEM credentials or direct point-write API.

## Packaging and ownership

- Add an optional `handheld` profile to the existing `northlake-sources` Compose project.
- Put the service in `services/handheld`, initially at `http://localhost:18082/`.
- Mount its own `handheld-state` named volume for SQLite sessions, source exports and finalized files.
- Mount existing `source-data` read-only. The simulator must not modify the producer's ledger,
  immutable release history, generation fingerprint or public catalog.
- Pin each session to a source release/model hash, seed and assumptions version; a later producer
  release must not silently change a saved route or in-progress round.
- Reuse Northlake's existing branding and small Python web-service conventions. A future proxy
  path can consolidate URLs; it is not needed for the first demonstration.
- The fictional reader picker records field activity. It does not authenticate as an EEM user.
- The testing-environment chat owns service/UI, codecs, session state, delivery integration and
  focused collector-contract tests when implementation begins.
- The implementation chat owns Stage 3/9 recipes and checks, environment identity mapping, actual
  catalog/configuration entry, and installed read/log/report/billing verification.

The optional handheld container is now available at port 18082 with its own state volume.
Implementation adds headless collector tests without changing production EnergyHippo code.

## First vertical slice

Use the existing CRBMW water-master route with Neptune and SCGAS gas-master route with MVRS.
Keep their existing whole-unit fixture configuration: integer kgal or therm register readings,
NumDecimals 0 and MeterConstant 1. These values are controlled demonstration inputs, not a
representation of the canonical retained source history.

Prove opening registers, a normal read, an explicit skip followed by a later actual, a visit note,
interrupted-session recovery, unchanged re-finalization, explicit delivery and explicit replay.
First validate the real export parser and return encoders headlessly, including the actual EEM
collector contract; then build and verify the browser flow. Verify the complete ingestion path as
well as collector output because the accumulator calculator also produces the related delta.

Use [the existing acceptance cases](04-acceptance-runs.yaml). Stage 3 takes no checkpoint after
its entry backup (decided November 5, 2026), so the first two-master pilot runs on the live
Northlake database and its readings stay in the two masters' history. Only those two routes need
be configured for the pilot; the full 204-register check remains incomplete until the other routes
are entered. The simulator handles one register per meter today: the switchgear (ten registers, four
demand reads) and the generators (two each) need multi-register support before their routes join a round. Any later restore is an operator action coordinated with other Northlake work, never
an automatic simulator action. Keep every acquisition schedule disabled.

The 126-submeter round, direct demand, rollover/reset and estimate workflows are subsequent
slices. The first UI does not need Massport's custom reports, estimate approvals or LOTO screens.

## File and binding contracts

Northlake's outbound HMR export is an MVRS-shaped, fixed-width 126-character record stream,
including when a selected route's return will be collected by Neptune. It is device configuration,
not a return file that can be copied straight into Input.

Parse that common export once, then encode distinct return formats accepted by the current
Neptune and MVRS collectors. Validate record lengths/counts, required fields, bounded numeric
values, ASCII/encoding requirements, leading zeros, route membership and CRLF output. Reject
overflow; do not silently truncate an identity, value or note. Compatibility means tested against
the current parsers, not certification against an external handheld vendor.

The export does not contain the complete stable source-model mapping. Require a companion
manifest generated through read-only Northlake verification with:

- Environment identifier and checked database name.
- Physical meter MetaWorldID and exact Text Prompt.
- Stable model meter/channel key, meter number and company.
- Register PtID, usage PtID, applicable HMR IDs, read-type fields and raw/display/usage units.
- Canonical gateway profile key, resolved GatewayId, return format and permitted delivery target.
- Route, cycle, sequence, multiplier and source-model/release identity.

Show mismatches before starting a round. IDs must come from the current environment. The current
collectors load all HMR channels regardless of GatewayId, so neither gateway selection nor a
folder name establishes route isolation; validate the exact returned meter/prompt set.

The implementation-side producer is `generators/handheld_bindings.py`. It reads Northlake through
integrated SQL authentication, checks the two selected routes, hashes an actual exported file,
and emits the agreed `northlake-handheld-bindings-v1` JSON. It reads source identity and the
assumptions version from the live release catalog and its hash-verified source-model artifact.
It never fills missing installed IDs or writes database configuration.

After saving the two pilot routes and their gateway headers, use an actual exported file and
explicit controlled opening values, for example from the repository root:

```powershell
python -m generators.handheld_bindings --export "C:\Temp\Northlake-routes.txt" --output "C:\Temp\Northlake-pilot.bindings.json" --opening-water 12000 --opening-gas 1000 --opening-at "2024-01-01T00:00:00-08:00"
```

The example paths are operator-selected files. Add `--route CRBMW` or `--route SCGAS` for a single
route. The default checks both. The producer intentionally fails until HMR/gateway setup is real;
the simulator must also check the export hash, route entries and pinned source identity.

For MVRS v1, use MTM for visit notes, after the applicable RDG record so the current reader and
timestamp apply. MTS changes persistent meter instructions through HMR_SpecialText_Save and must
be a separate, deliberate exercise. A skipped RDG still needs valid numeric/date placeholders.
Neptune's ORDST note is retained in simulator/source evidence; it is not an HMR log in Northlake.

## Session and delivery behavior

Persist original export bytes/hash, environment manifest/hash, route assignment, reader,
draft reads/skips/notes, timestamps and attempts. Use revision checks for edits. Finalization
freezes a submission: an unchanged repeat returns the same bytes/hash; a correction creates a
linked new revision. Preserve the prior attempt rather than overwriting its history.

Use separate states for draft, prepared, downloaded and delivered. Mark an import verified only
when the actual Northlake readings/logs have been checked; file download, successful delivery,
a task-success flag, and persistence are distinct observations.

Keep finalized files and their manifest in the handheld volume. Reuse the existing explicit
delivery helper and receipt conventions for a selected target, with temporary-file rename into
the Windows-visible Input directory. No continuous delivery or automatic redelivery initially.
A download alone is not a delivery receipt.

Deliver only one codec/target for an observation in retained history. Comparing both codecs is
a controlled restored-run exercise. The helper must not remove files from Input or manage
Northlake's Working, Archive or Error folders.

## Retained-history gate

Retained history is not enabled by the first two-route demonstration. The existing source model
stores higher-precision physical truth than the native register contracts can reproduce losslessly
under the current configuration.

The testing-environment chat checked 34 issuable periods per master through November 4, 2026.
For each master, 33 periods had a boundary reading still fractional after multiplication by 1000.
The checked water register reached 6861.784394 kgal. Gas evidence is raw CCF with a separate 1.027
heat-content factor and reached 477698.080938 CCF.

The current collectors use ten-character integer return registers. HMR_HDLData rounds the meter
constant to four decimal places before writing a six-character field. Therefore micro-kgal
scaling rounds its 0.000001 constant to zero, and micro-CCF absolute counters exceed the return
width. NumDecimals is applied to direct demand, not register-difference calculations. The
IntervalBatchCalculator also independently writes the generated delta using PointDef.DeltaMultiplier.

Before retaining monthly history or expanding to the apartment water routes:

1. Choose and version the observed meter resolution separately from canonical physical truth,
   including raw units, displayed units, multiplier and explicit reconciliation tolerances.
   A realistic quantized observation model may be used; no silent rounding, rebasing, bill-anchor
   changes or claim of lossless delivery is allowed.
2. Align and test both HMR MeterConstant and PointDef.DeltaMultiplier, including opening values,
   ordering, chunk boundaries, replay and correction of a previously accepted reading.
3. Apply CCF-to-therm conversion exactly once for gas. Do not label raw supplier CCF as therms.
4. Implement and prove conserved water allocation and rounding across the 124 apartments and two
   house meters. Current physical.py conserves electric groups; water conservation is follow-up.
5. Reconcile the observed monthly history against the preserved bill anchors and declared
   tolerances. The source model's higher-precision truth remains intact for scoring.

If exact current canonical readings must survive the native export/return contracts, that needs
a separately authorized product-contract change. It is not part of this Northlake-only first slice.

## Stage handoff

Stage 3 owns identities, types, route/channel setup, disabled schedules and controlled acceptance.
[Stage 9 Step 7](../stage-9-operations/07-handheld-and-importers.yaml) reuses that configuration for
ongoing export, reader rounds, delivery, exceptions, replay and correction review.

Stage 9 must not recreate the HMR assignments or use its former placeholder prompts/read types.
It records evidence of actual point history and appropriate MVRS logs. Generic My Imports exercises
remain separate from the native handheld round. Retained submeter consumption then feeds Stage 7's
allocation/reconciliation and Stage 5's supplier-bill comparison.
