---
title: Stage 10. Baseline
subtitle: The final backup and its restore verification
status: Ready to enter
---

# Stage 10. Baseline

Stage 10 closes the implementation out. Everything from Stage 1's companies
through Stage 9's report delivery has been entered through the applications,
every stage's checks are green, and now the whole thing is captured in one
backup that can be trusted: restored anywhere, it reproduces Northlake
exactly, not "approximately." This stage takes that backup, proves it by
restoring it somewhere disposable and reading real values back out, and then
promotes it to be the reference database everyone restores from afterward.

## Before you start

- Stages 1-9 are green: every checks.sql in every stage folder has been run
  and matches its expected result.
- This stage is SQL Server work, not an EEM editor. Run its commands with
  sqlcmd or SQL Server Management Studio as a sysadmin, the same way Stage 3's
  entry backup was taken.
- A database backup only ever captures the database. It does not capture the
  application version, the repo state, or anything held outside SQL Server
  (gateway folders, ConfigFiles runtime settings, external service
  credentials). Step 1 records all of that beside the .bak file.

## Step 1. Final backup

**Where:** SQL Server, `BACKUP DATABASE`.

**Enter:** [01-backup.yaml](01-backup.yaml).

**Order:** confirm every stage's checks are green, then take one full backup
of `EEMSuite_Northlake` to `C:\Hippo\Backups\`, named
`EEMSuite_Northlake.stage10-final.<yyyyMMdd>.bak` — the same folder and dot-
separated naming the existing pre-upgrade backup already uses there, distinct
from Stage 3's entry backup in the instance's own default backup path.
Run `RESTORE VERIFYONLY` against it immediately.

**Keep beside it, since none of it is in the database:** the application
version (7.0.0.4005) and the repo commit the install was built from; the
gateway input/working/backup/error folders and
`GatewayOutput` state files under
`C:\ProgramData\EEM Suite\NorthLake`; and any externally-held settings —
ConfigFiles runtime configuration, the ENERGY STAR `CustomerServer` constant
and Portfolio Manager credentials once connected, SMTP/mail relay settings.

**Record:** the backup file path and the date taken.

**Check:** `backup_history`.

## Step 2. Restore verification

**Where:** SQL Server, `RESTORE DATABASE`, then the web site and Database
Administrator pointed at the restored copy.

**Enter:** [02-restore-verification.yaml](02-restore-verification.yaml).

**Order:** restore the Step 1 backup into a disposable database
(`EEMSuite_NorthlakeVerify`) on the same server, never over the real
`EEMSuite_Northlake`. Point gateway profiles at scratch folders instead of
the real ProgramData paths, and leave the ENERGY STAR and mail settings
unset, since this is a read/render check, not a live-processing rehearsal.
Then open the report checklist in the file — one representative report per
stage — and confirm each shows the value it should.

**Once every row in the checklist matches:** the Step 1 backup is promoted.
It replaces the 2026-09-14 pre-upgrade snapshot as Northlake's reference
database, the file every future restore starts from. Drop
`EEMSuite_NorthlakeVerify` and its scratch folders; the real instance was
never touched.

**Check:** `row_counts_major_tables`, `report_matrix_nonempty`.

## Stage 10 is done when

- The Step 1 backup exists in `msdb` backup history as a full backup at
  `C:\Hippo\Backups\`, and `RESTORE VERIFYONLY` passed.
- Every table in `row_counts_major_tables` that a prior stage populates shows
  a non-zero count.
- Every report bucket in `report_matrix_nonempty` is non-zero, standing in
  for the full [report coverage matrix](../report-coverage-matrix.pdf)'s 115
  reports all having rendered at least once.
- The restore-verification checklist opened cleanly in a disposable database
  and every value matched.
- The backup is promoted as Northlake's reference database.

Run `checks.sql` beside this chapter against the instance database to see
each of these as a result set.

## Findings

None new in this stage. It inherits every finding recorded in Stages 8 and 9
(ENERGY STAR scores are external, benchmark and MFR external-email UI gaps,
EnergyAI and GreenButton have no entry path, custom report registration has
no UI) — see [product findings](../product-findings.pdf) for the full list.
Nothing in Stage 10 works around any of them with SQL; the restore
verification checklist expects those reports to show exactly the partial
state those findings describe (property metrics without a score, a
delivery reaching people only through groups, and so on), not a hidden
seed of the missing data.
