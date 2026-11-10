# Handheld pilot verification — November 4, 2026

The optional service is implemented and was exercised at http://localhost:18082/.
This is source-side evidence. No installed Northlake import, schedule run, SQL
publication, HMR log persistence or rendered EEM report is claimed.

## Automated checks

| Check | Result | Boundary proved |
| --- | --- | --- |
| Python `unittest discover -s services/handheld/tests -v` | 9 passed | Export/binding contracts, producer interoperability, integer/width validation, native fields, skipped reads, DST/leap day, restart, edit conflicts, immutable retry, corrections, interrupted publication, receipts, HTTP API and shared/HTTP byte agreement |
| Scoped Jest with `services/handheld/jest.config.cjs` | 2 passed | Exact whole-register parsing, explicit offsets, skip payloads and matching enabled delivery target/environment/profile |
| JavaScript syntax checks | Both scripts passed | Unbundled frontend scripts parse |
| Gateway test project build | 0 warnings, 0 errors | Only `EEMSuite.Tests.Tasks.Gateways.csproj` and its dependencies built |
| `NorthlakeHandheldFixtureTests` | Passed; 10 native files | Real Neptune/MVRS collectors, opening/normal/skip/later/correction cases, Pacific conversion, meter matching, values, MVRS visit logs and archived bytes |
| Shared accumulator calculation in the same bridge | Passed | Empty opening history, seeded subsequent readings, both input orders, repeated intake and an in-place corrected reading; no doubled usage |
| Compose profile | Valid; built and started | Own state, read-only source mount, loopback port, no dependent-service recreation |

Jest used the existing EnergyHippo frontend installation; no new npm dependencies
were installed. Python ran in the existing pinned source image. The native bridge
uses test-owned IDs, temp workspaces and no database/broker. Its fixture generation
command and opt-in variable are in the runbook. The task's isolated .NET artifact
directory was removed after successful checks.

## Running-service and browser checks

The bundled in-app Browser exercised the actual container, using Northlake's
shared `brand.css`/`site.css` page chrome, controls and typography:

- Demonstration preflight and actual two-file chooser upload both worked.
- CRBMW saved a register of 1125 against its explicit 1000 opening, producing
  125 kgal usage. Its prepared Neptune file downloaded through the browser.
- The same saved round and identical download survived container recreation.
- SCGAS saved an explicit skipped visit with its reader and note, then a linked
  later actual of 1180, producing 180 therm usage. A linked correction of 1182
  produced 182 therm while preserving the original return.
- Finalization locked the form and exposed the native download and evidence
  manifest. The UI retained separate prepared, downloaded and delivered states.
- Shared-directory delivery and explicit replay into `/handheld/qa-gateway/Input`
  produced receipts visible in the UI. This is a fixture-only folder inside the
  handheld volume, not a Northlake gateway input.
- The Windows `Sync-HandheldReturn.ps1` helper downloaded into the task-owned
  `services/handheld/.runtime/http-workspace/Input` directory. No EEM input was used.
- The temporary fixture delivery target was disabled again after verification.
  The final browser showed delivery disabled.

The CRBMW browser download, Windows HTTP copy and catalog all had SHA-256
`7e5949daf0b5d65ffa2d1d7b42372d3045604cf018b945281b8ce51374927d25` (819 bytes).
The SCGAS actual return and shared copy had SHA-256
`b7349f134c85746d83bbbec6eca0e7e9b42fcd473ae764043b2f3ae6254eb578` (572 bytes).

The mounted source pin remained
`northlake-sources-v1-5a4452b39320-104729`, seed 104729, assumptions version 1.
The source producer/web and identity/Mailpit container IDs stayed unchanged.
No BACnet control command, installed settings change, EEM import or schedule
enablement was performed by this implementation.

## Review decisions and remaining acceptance

- SQL exports its numeric channel in a space-padded character field. The
  consumer normalizes that numeric value to `01`; route/cycle identities retain
  their defined padding and are checked against the manifest.
- Native formats cannot carry a DST fold/offset. Both repeated-hour instants
  fail explicitly rather than silently selecting one.
- Controlled openings stay separate from the exported previous reading and
  canonical physical truth. A read at the opening instant must equal that
  opening; a skipped-visit follow-up must be later than the skip.
- A correction creates a separate immutable artifact linked to the original.
  A follow-up records its relationship without declaring the skip superseded.
- An unused inherited image volume is covered by the handheld volume read-only,
  so further Compose recreations do not allocate anonymous `/state` volumes.

The implementation chat's read-only checks still found missing HMR/gateway IDs
for an installed pilot binding. Finish that setup, export a real route, use the
checked binding exporter, and perform the acceptance (no checkpoint or restore)
workflow. Full 204-register configuration (multi-register meters and demand reads included), retained higher-precision history,
conserved apartment water allocation, gas conversion and future VEE scenarios
remain explicit follow-ups. See the [runbook](README.md) and
[agreed stage handoff](../../implementation/stage-3-gateways-and-data/handheld-test-environment.md).
