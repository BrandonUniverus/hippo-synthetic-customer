# Northlake handheld rounds

Implemented source-side pilot, November 4, 2026. Open it in the Northlake site at
**https://localhost:8443/meter-reading/**, or directly at http://localhost:18082/.
Its pages use relative URLs so both addresses work.
This optional service prepares real Neptune and MVRS return files from checked
EEM route exports. Installed Northlake ingestion, log persistence and billing
verification remain separate acceptance steps.

## Start and resume

From the repository root, with the existing source image available:

```powershell
docker compose -f services/sources/compose.yml --profile handheld build handheld
docker compose -f services/sources/compose.yml --profile handheld up -d --no-deps handheld
docker compose -f services/sources/compose.yml exec handheld python -m services.handheld status
```

Only `handheld` is built/recreated. The producer, source web service, BACnet,
identity and Mailpit keep their current deployment. Do not rebuild the producer
to start this pilot: the current source checkout may have a different fingerprint
from its retained release. The handheld image derives from the existing source
image, reusing its pinned Python dependencies. Its Dockerfile-specific allowlist
adds `services/handheld` plus the Northlake look: `identity/branding` and
`brands/northlake` (without the PDF-only TTF files), copied over the source
image's older branding. Rebuild only the handheld after editing them.

The Compose profile binds `127.0.0.1:18082` (override `NORTHLAKE_HANDHELD_PORT`).
`handheld-state:/handheld` holds SQLite rounds, original export/manifest BLOBs,
attempt history and immutable returns. `source-data:/source:ro` supplies the
published source identity and model assumptions. The service verifies the
source-model hash against the read-only source catalog; it never imports the
current generator to infer the mounted release's identity.
The base image's unused `/state` path also mounts handheld-state read-only,
avoiding a new anonymous volume at every container recreation.

`GET /health/ready` reports a readable, consistent mounted source contract.
`GET /api/status` also lists the fictional readers and configured target names.
Use `docker compose ... logs handheld` for request/error diagnostics.

## Supported round

| Route | Master | Return | Controlled units |
| --- | --- | --- | --- |
| CRBMW | Cedar Row B water | Neptune | Whole kgal |
| SCGAS | Student Center gas | MVRS | Whole therm |

Both use NumDecimals 0, MeterConstant 1 and PointDef.DeltaMultiplier 1. They are
controlled observations, **not the higher-precision retained source history**.
The 126 apartment/house channels, direct demand, estimation, rollover/reset and
retained gas conversion remain follow-ups in the
[agreed design](../../implementation/stage-3-gateways-and-data/handheld-test-environment.md).

1. Configure the two-route pilot through the Stage 3 recipe. There is no pilot
   checkpoint: Stage 3 takes none after its entry backup, so pilot readings stay in
   Northlake. Leave acquisition schedules disabled.
2. Export the actual HMR route file through EEM. The simulator does not execute
   `HMR_HDLData`, which itself has a cycle-99 deactivation side effect.
3. Produce a companion manifest with the implementation-owned read-only
   [binding exporter](../../generators/handheld_bindings.py). It fails on missing
   installed HMR/gateway IDs. Supply explicit controlled openings and their time.
4. Select both original files in the UI, choose **Check files**, select a checked
   route and start a round. Alternatively, **Use demonstration files** loads
   clearly marked synthetic IDs that cannot represent installed Northlake.
5. Select a fictional reader, record the register or an explicit skip, and save
   a visit note. On the MVRS route also choose the read and audit codes, or the
   skip code (see "File contract"). Save persists immediately; reopening/restarting
   resumes it.
6. Review the saved values and finalize. Finalization freezes the bytes and their
   evidence manifest. An unchanged retry returns the same artifact. A correction
   is a separate linked round. A skip can produce a later follow-up without
   advancing its known opening. After an actual import, export fresh checked
   bindings for the next ordinary round.
7. Download or explicitly deliver the native file. Run the installed disabled
   schedule manually and verify actual register, delta and appropriate logs in
   Northlake. A successful download or delivery is not an import result.

The local UI has no authentication and stays bound to loopback. Reader names are
fictional activity attribution, not EEM identities. It has no SQL client, EEM
credentials, schedule controls or direct point-write API.

## File contract

The common outbound format is EEM's 126-character `FHD/CHD/RHD/CUS/MTR/RDG/...`
stream, even for Neptune returns. Import checks the UTF-8/ASCII content, exact
widths, envelopes, route/meter counts, physical meter/prompt uniqueness, serial
prefix, route/cycle/sequence, channel and keyed read-type configuration. Route
leading zeros are preserved; SQL's space-padded numeric channel becomes `01`.
Unknown or malformed record ordering fails preflight.

The companion JSON schema is `northlake-handheld-bindings-v1`, purpose
`controlled-pilot`. Required top-level fields are `environment_id`, `database`,
`verified_at`, `export_sha256`, `source` and `channels`. `source` contains exactly
`release_id`, `model_version`, `source_hash`, `seed`, `assumptions_version`.
`model_version` maps to source catalog `identity.version`; assumptions come from
that release's immutable `contracts/source-model.json`, not the current checkout.

Each channel requires:

- `channel_key`, `reading_channel_key`, `company`, `meter_number`, `meter_description`.
- Positive `meter_id` (physical MetaWorldID), `reading_pt_id`, `usage_pt_id`,
  `hmr_meter_id`, `hmr_reading_id`, `gateway_id` from the checked environment.
- `cycle`, `route`, `sequence`, `text_prompt`, two-digit `channel`.
- `read_type`: `key`, `num_dials`, `num_decimals`, `read_type_code`,
  `read_direction`, `demand_read`, `truncation_factor`.
- String `meter_constant` and `delta_multiplier`, `raw_unit: "Reading"`,
  `display_unit` and `usage_unit` (`kgal` or `therm`).
- `gateway_profile`, `return_format` (`neptune` or `mvrs`), `delivery_target`.
- `opening`: integer `value`, offset-bearing `observed_at`,
  `basis: "controlled-pilot"`, and explicit `reason`.

The controlled opening override and original exported previous reading are both
shown. No missing opening is inferred from a zero or 1901 database timestamp.
Every round retains both original byte hashes, its source pin and binding values.
The implementation-owned manifest builder is exercised by a consumer contract
test using synthetic rows; that test makes no database query.

MVRS readings carry the RDG record's codes:

- **Read code:** N for a normal read, or O or C.
- **Audit code:** 0 for none, or 1 to 9.
- **Skip code:** 01 to 09, on a skip.

Energy Hippo records a read code other than N, a nonzero audit code and every skip
code as an HMR log event. Once its vendor-flag change lands, it also keeps the read
and audit codes on the reading. Itron publishes no meanings for these codes, so none
are claimed here. A round saved without codes encodes as N, 0 and 01, the bytes it
had before codes existed. Neptune returns carry no codes; their RDGDT and ORDST
fields wait for Neptune's record specification.

Native returns use CRLF and printable ASCII. Overflow fails rather than truncating.
MVRS visit notes use `MTM`, after `RDG`, with a 40-character limit. `MTS` is never
emitted: it would change persistent meter instructions. Skips have valid numeric
and date placeholders but emit no accepted reading. Neptune notes use `ORDST`
(128 characters) and remain file/evidence data; the collector does not publish an
HMR note log for them. Both formats carry Pacific wall time without an offset,
so both instants in the repeated autumn hour are rejected. UTC/offset input at
other times is normalized to Pacific before encoding.

Required pilot collector settings: `UseSqlValues=false`,
`UseReadingTimeStamp=false`, `IgnoreDays=0` (legacy `MVRSIgnoreDays=0`),
`AllowNoData=true` for skip-only returns. Destination points remain Pacific;
headless fixtures use built-in TimeZoneID 33 and archive interval 1440. Verify
the actual installed timezone/configuration independently. Deliver one codec per
observation/target; comparing both is a controlled restored-run exercise.

## Explicit delivery

No target is configured or enabled by default. Copy `targets.example.json` to an
operator-owned configuration and set the exact checked environment/profile.
Only enable the intended target. There is no continuous delivery loop.

For a Windows gateway workspace, create/identify its root and invoke:

```powershell
.\services\handheld\Sync-HandheldReturn.ps1 `
  -Round '<finalized round ID>' -Target 'crbmw-pilot' `
  -TargetsFile 'C:\Hippo\Northlake\handheld-targets.json' `
  -GatewayRoot 'C:\Hippo\Northlake\Neptune'
```

The target's `destination` is `/delivery-root/Input` inside this helper. The
script mounts the entire selected gateway root so its sibling
`.northlake-deliveries/delivery.sqlite3` and JSON receipts persist. It downloads
over HTTP using the same delivery engine as the source bundle, checks size/hash,
and renames a staged file into Input. `-Url` defaults to
`http://host.docker.internal:18082` for Docker Desktop; use the actual hosted URL
when deployed. No Python installation or repository checkout is needed on that
host once the image and script are present. The helper verifies the round's exact
target/environment/profile before delivering it.

For an enabled server-side target, explicitly bind the Windows gateway root into
the handheld container using an operator Compose override and put its target
configuration at `/handheld/targets.json` (or `NORTHLAKE_HANDHELD_TARGETS`). The
UI's delivery button or this command then uses shared-directory delivery:

```powershell
docker compose -f services/sources/compose.yml exec handheld python -m services.handheld deliver `
  --round '<round ID>' --target crbmw-pilot --targets /handheld/targets.json
```

Use one delivery mode per target. If both modes are tested, point them at the
same physical root and receipt ledger. Removing a claimed Input file does not
trigger redelivery. `-Replay`/`--replay` is an explicit operator decision after
reconciling EEM. An interrupted pending transfer with no visible target reports
an uncertain outcome. Different existing bytes are never overwritten. The
helper never manages Working, Archive or Error. Fixture-only IDs require a
`fixture_only: true` target and must only use a test-owned output directory.

The UI records its own deliveries. A Windows HTTP helper keeps its authoritative
receipt on Windows and does not push a delivery claim back to the UI. HTTP
downloads can show `downloaded`; neither path can show `import verified`.

## Persistence, recovery and artifacts

`handheld.sqlite3` contains revisions and all attempts. Save conflicts return
HTTP 409. Finalization stages files and verifies bytes before committing the
artifact in SQLite. HTTP catalogs only expose committed returns; a crash-created
orphan or `.partial` is ineligible. Retrying an interrupted finalization produces
the same content. A changed-source manifest cannot start a round against the
wrong mounted release; saved rounds continue using their original pin.

`/catalog.json` lists finalized returns only. Immutable URLs are
`/releases/handheld-<round>/files/<route>-<round>.imp`; the companion
`/releases/handheld-<round>/manifest.json` freezes the original preparation
evidence. Preserve the entire handheld volume and Windows receipt directories
together, and with any later Northlake backup. Back up the SQLite database coherently (SQLite backup
API or stop **only** handheld while copying its volume); copying a live DB file
without its WAL is insufficient. Do not delete receipts to force a replay.

## Verification and remaining acceptance

Python tests use `unittest`; no database or broker is needed:

```powershell
docker run --rm --entrypoint python --mount "type=bind,source=$((Get-Location).Path),target=/work,readonly" `
  -w /work hippo-northlake-sources:local -B -m unittest discover -s services/handheld/tests -v
```

The interchange test requires the current checkout's implementation-owned
`generators/handheld_bindings.py`. The image reuses its existing pinned `tzdata`;
bare Windows Python needs the repository's source requirements installed.
UI logic uses scoped Jest (`jest.config.cjs`); run Jest from `services/handheld`.
`node --check web/app.js` and `node --check web/model.js` validate the unbundled
scripts; the Docker image build packages the frontend directly, with no separate
frontend compilation step.

Generate ten native fixtures with `python -m services.handheld fixtures --output
<directory>`. Set `NORTHLAKE_HANDHELD_FIXTURE_ROOT` to that directory and run
`EEMSuite.Tests.Tasks.Gateways.exe --filter-class
EEMSuite.Tests.Tasks.Gateways.NorthlakeHandheldFixtureTests` after a scoped build.
This exercises real collectors, Pacific conversion, opening/normal/skip/later/
corrected values, MVRS notes, archived bytes and the accumulator calculation with
both input orders and replay. Focused Python tests cover binding interoperability,
conflicts, restart, linked corrections, crash publication, delivery uncertainty,
HTTP/shared byte agreement, leap day and both autumn DST instants.

Installed acceptance still needs the actual export/binding, disabled schedule
manual run, and stored register/delta and log checks. There is no checkpoint to
restore afterward; the readings stay in Northlake.
Headless collector/calculator proof is not proof of SQL publication, installed
gateway settings, HMR log persistence or rendered reports/bills.
