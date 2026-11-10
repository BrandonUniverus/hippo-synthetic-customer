# Northlake source service

This independent Compose project generates fictional gateway deliveries, supplier
bills and tariffs from the Northlake source model. It serves provider pages and a
download catalog, and can deliberately deliver selected files into an application's
input directory. It never connects to EEMSuite SQL Server or starts an EEM task.
The identity and Mailpit services remain separate.

The producer includes a December 2023 Pacific-time lead-in for opening January
bills, then January 2024 onward, and catches up to the latest completed 15-minute
UTC boundary. It then publishes new completed windows as time advances.
History follows source effective dates, billing cycles and the versioned model;
it is not a copy of every point at every timestamp. Source-model assumptions and
format limitations are recorded by the model and artifact metadata.

## Configuration handoff and model choices

This release covers 215 direct file-backed inputs across seven profiles and 14
nodes: AcquiSuite, MDEF, MV9, Spinwave, generic FIG, FIXEDNETWORKS and Ridgeline
SCADA. The seven FIG encodings are also available as explicit compatibility
fixtures. The other 43 direct inputs and handheld route protocols remain outside
this release. No generated aggregate, delta or weather point is invented as an
additional input.

The published `contracts/source-model.json` contains the source-to-gateway
bindings, required consumer settings, exact MDEF/MV9 node deltas and relative
provider-page URLs. Before delivering their continuous files, set the listed
MDEF/MV9 nodes to `TimeStampType=Utc`; keep point time zones Pacific. FIG and
FIXEDNETWORKS use UTC; Ridgeline retains its fixed-PST source clock and existing
480-minute point offset. Existing stage files and installed nodes are not changed
by the producer. Map fictional provider website addresses to the published routes
through the normal configuration process when ready.

`assumptions.json` records the added synthetic rules. Winter supplier part-peak is
08:00-22:00 on weekdays: the original proposed four-hour window could not contain
the existing bills' energy at their stated peak demand. Stage 4's simplified
analysis schedules remain unchanged. The Central Plant has a declared 2,200 kW
nominal process-load profile because its existing source model identifies it as
the estate's largest electric service. Cedar apartment/house electric readings conserve
their master; conserved handheld water allocation is a separate implementation gate.
Existing July wind totals constrain turbine, possible and export
energy. Known water register readings bound preceding usage and retain a
documented positive opening balance.

The optional [handheld testing service](../handheld/README.md) now provides its own
state volume, browser round workflow and native Neptune/MVRS return-file codecs.
Its first two-route demonstration uses controlled whole-unit reads; installed
ingestion is separate acceptance and retained HMR history still requires the documented
raw-unit, precision, gas-conversion and water-conservation checks.

Historical tariffs and all 24 sample PDFs are preserved. Annual synthetic tariffs
from 2026 increase monetary charges by 3%, except existing Helios and Ridgeline
contract terms. Generated invoices use a separate `_generated_YYYY_MM` ID namespace
to avoid collisions with existing anchor IDs whose names use service-start months.
The full published window contains 50 supplier/internal-allocation account series;
Ridgeline's own statements remain separate Stage 7 references. Meter-specific
register evidence remains in PDFs/manifests; rich XML includes readings only where
they have an unambiguous bill-item association. Never repeat a complete water
register delta on every tier line.

The accompanying EnergyHippo source fixes preserve signed credits, later nonzero
charges after skipped zero items, decimal XML values and legacy scientific numeric
notation. Rebuild the normal importer/application before installed acceptance of
those changes; this bundle does not deploy EnergyHippo binaries.

## Start the service

From the repository root:

```powershell
docker compose -f services/sources/compose.yml build
docker compose -f services/sources/compose.yml up -d producer web
docker compose -f services/sources/compose.yml logs -f producer
```

Provider pages are at `http://localhost:18081/`. People use them through the
Northlake site at `https://localhost:8443/utilities/`, which shows them in
today's Northlake look; the copies here change with the next release (see the
identity README). The file catalog is
`http://localhost:18081/catalog.json`; `/health/live` checks the HTTP process and
`/health/ready` becomes available after initial history generation and publication.
The catalog and provider pages state their actual completed cutoff. Every download
uses `/releases/<release-id>/files/...`, and that release's manifest is at
`/releases/<release-id>/manifest.json`. `/catalog.json` is the current release view.
The manifest grows as new immutable files arrive; a changed source model gets a
different release URL, so an old cached download can never silently become new bytes.

The producer image contains code, source manifests, selected gateway mappings,
fonts and branding. It does not require a checkout on the destination server.
Generated files and SQLite progress live in the Compose `source-data` named volume.
Caddy mounts that volume read-only. No host directory is required for HTTP use.
Publish both the producer and web images under a versioned registry tag when moving
to another server; that server also needs the Compose configuration and its own
persistent volume. The local port binding is intentionally loopback; a hosted demo
must provide its normal reachable HTTPS route and use that URL in EEM configuration.
`NORTHLAKE_IMAGE_PREFIX` can supply a registry/namespace prefix including its trailing
slash, and `NORTHLAKE_IMAGE_TAG` selects the shared release tag. Both are optional;
the local defaults remain the two `hippo-northlake-sources*:local` images. Registry
publication and remote-host configuration are separate deployment actions.

## Fixed cutoffs and restart behavior

For a deterministic acceptance release, use a separate project/volume and an
explicit cutoff instead of starting the continuous producer:

```powershell
docker compose -p northlake-sources-acceptance -f services/sources/compose.yml run --rm producer init --through 2024-01-03T00:00:00Z
docker compose -p northlake-sources-acceptance -f services/sources/compose.yml up -d web
```

The default seed is `104729`. `--start` and `--through` require timestamps with a
UTC offset or `Z`. `run --through ...` also runs once and exits. Continuous `run`
polls every 60 seconds; it generates only new completed windows. Catch-up is
partitioned by day and generation streams files instead of holding all history in
memory. The initial bootstrap cutoff is persisted once. Every later window stays
15 minutes, including catch-up after downtime, so restarting does not change file
partitioning. Source fingerprints are checked before each chunk and again before
its progress is committed. A changed input stops further publication. An operating
system file lock allows only one producer per state directory and releases ownership
automatically when that process exits.

Every store records the model version, source fingerprint, seed and history start.
Changing these requires a **new state directory/volume**. It never overwrites an
old release with a changed model. A partial generation does not advance the
committed cutoff. Complete files left by a crash can be reclaimed only when their
hashes match the deterministic retry. Published paths reject different contents.
The producer does not deliver files automatically.

```powershell
docker compose -f services/sources/compose.yml run --rm producer status
docker compose -f services/sources/compose.yml run --rm producer verify
docker compose -f services/sources/compose.yml run --rm producer health
```

`verify` recalculates hashes for every catalogued file and fails for changed or
missing bytes. Status and verification are source-service evidence, not gateway,
Bill Importer or installed application acceptance.

`health` checks the producer's heartbeat, separately from stored-data readiness.
It fails when no active producer heartbeat exists, the heartbeat is older than
180 seconds, or an idle continuous producer is more than 30 minutes behind the
clock. Active bootstrap/catch-up reports its lag without claiming the historical
load is complete. Docker's producer healthcheck uses this command; Caddy's health
checks only that a completed published catalog is available. A successful one-shot
`init` leaves usable files and a `complete` producer status, not a live producer.

## Explicit file delivery

The delivery command accepts the same catalog from a local state directory or an
HTTP source service. Select a source, provider, kind, representation, day, month or
case. `--all` is required if no narrower selector is supplied. Inspect the catalog
for exact source IDs and dates before configuring the consuming task.

For a host-mounted input directory, set the parent directory as the mount root;
the input directory itself is a child. This keeps receipt state and partial files
outside the watched input folder:

```powershell
$env:NORTHLAKE_DELIVERY_ROOT = 'C:\Hippo\NorthlakeSourceDelivery'
docker compose -f services/sources/compose.yml --profile delivery run --rm deliver deliver --state /state --source gw_acquisuite_student_electric --day 2024-01-02 --destination /delivery-root/acquisuite
```

When `--source` is supplied, the command uses each gateway's `delivery_path` relative
to that input root, including required subfolders. Without `--source`, it preserves
the catalog directory tree. `--flat` explicitly flattens names and rejects
collisions. Use one gateway source per watched directory.

To pull over HTTP using only the container images and deployment Compose file,
use the delivery container. The `web` hostname is the source HTTP service on this
Compose network; replace the URL with the hosted source service when they run on
different servers. No Python installation or source checkout is needed on the
destination host:

```powershell
$env:NORTHLAKE_DELIVERY_ROOT = 'C:\Hippo\NorthlakeSourceDelivery'
docker compose -f services/sources/compose.yml --profile delivery run --rm deliver deliver --url http://web:8080 --source gw_acquisuite_student_electric --day 2024-01-02 --destination /delivery-root/acquisuite
```

The same command is also available from an installed Python environment with
`services/sources/requirements.txt`:

```powershell
python -m services.sources deliver --url http://localhost:18081 --source gw_acquisuite_student_electric --day 2024-01-02 --destination C:\Hippo\NorthlakeSourceDelivery\acquisuite
```

Every delivered file is verified against the catalog before an atomic move makes
it visible. A durable receipt ledger under the destination's sibling
`.northlake-deliveries` directory records delivery identity and outcome. **A file
consumed or deleted by EEM is not delivered again on the next run.** Deliberate
duplicate/replay acceptance requires `--replay`. Keep the receipt directory with
the delivery root when moving or restoring it.

An intent is persisted before copying. If a process stops and the destination is
absent with only a pending intent, the result is uncertain: the file might have
been consumed after publication. The command stops rather than assuming it should
send again. Reconcile the consuming gateway's results and use `--replay` only when
that replay is intended. A differing existing input file is never overwritten.

`--follow` opts into continuous delivery of the selected stream. It polls the
catalog every 60 seconds and uses the same ledger. It is separate from producer
startup and cannot be combined with `--replay`.

## Bills and nonordinary artifacts

The catalog keeps alternative representations available without automatically
sending all of them to an importer. Ordinary bill delivery is limited to the
supported native XML streams selected by the bill generator. Other provider CSV,
BIF, extraction JSON, PDF, tariff, schema and negative/acceptance files require
`--include-nonordinary` for CLI delivery (`--include-acceptance` is an alias).
They remain downloadable through the provider pages.

Use `--artifact` to choose one representation: `nativeXml`, `bif`, `providerCsv`,
`pdf`, `manifest`, `extractedJson`, `json` or `schema`, according to the catalog.
For example:

```powershell
python -m services.sources deliver --url http://localhost:18081 --provider valley_electric_district --month 2024-02 --artifact pdf --include-nonordinary --destination C:\Hippo\NorthlakeSourceDelivery\bill-pdfs
```

Day/month filters select `metadata.period_start`, not the wall-clock download date.
The generator's metadata also retains the complete period. Acceptance fixtures are
separate from ordinary history and require an explicit case/representation choice.
Generating or downloading a PDF does not create an EEM image record, stage an import
or link an image to a bill; those remain the normal application workflows.

## Provider pages and validation

The pages reuse `identity/branding/brand.css` and `site.css` without changing identity.
Provider colors follow the existing tariff sheets and bill generator. Pages are
static, with provider, billing-account, year and month navigation, and paginated in
sets of 100 files. Account pages contain only files tagged for that account; year
pages filter the source period's year. They need no
JavaScript framework or frontend package build; both the shared assets and page
templates are included in the producer image.

The focused tests use the repository's Python `unittest` runner:

```powershell
python -m unittest services.sources.tests.test_runtime services.sources.tests.test_delivery services.sources.tests.test_web -v
```

For all source-model, billing, format and runtime checks:

```powershell
python -B -m unittest discover -s services/sources/tests -v
```

The opt-in EnergyHippo bridges are `NorthlakeGeneratedFixtureTests` in the existing
gateway test project (`NORTHLAKE_FIXTURE_ROOT`) and
`NorthlakeGeneratedArtifactTests` in the domain BillImporter project
(`NORTHLAKE_BILL_FIXTURES`). They consume generated files through the real parsers;
they do not connect to the Northlake database. Use the repository's xUnit v3 runner
and task-owned artifact policy. The gateways' `write_fixture_manifest` function and
the billing tests' `write_parser_fixtures` function prepare their inputs.

The tests exercise immutable publication, interrupted generation, delivery receipts
after consumption, uncertain delivery recovery, exact source selection and working
pagination/download links. Container validation must also generate a bounded
release, verify it, fetch its catalog and a file, restart without changing the
cutoff/bytes, and exercise the actual provider pages through the bundled in-app
Browser. Full historical generation and installed EEM acceptance are separate
checks. Do not use this service to insert customer rows directly into SQL Server.
