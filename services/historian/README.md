# Northlake ODBC historian

Stage 3's ODBC gateway (`gw_odbc_library_historian`, node ODBC-LIBRARY-HISTORIAN)
reads the Library's half-hourly electric readings from a historian, through the
`SyntheticCustomerHistorian` profile. This folder is that historian: a container
that keeps a Microsoft Access database current. Each reading carries the vendor's
classification, code and metadata, which Energy Hippo's ODBC gateway can read
(`src/Domain/EEMSuite.Domain/Admin/Gateways/Types/OdbcGatewayType.cs`).

Access is deliberate. It is a file-based, non-SQL Server source with its own SQL
dialect, reached through the Access ODBC driver. That tests the ODBC path the way a
customer's historian export would, where a second SQL Server would not.

**Status (2026-11-07):** running. The `historian` container writes
`northlake-historian.accdb` and refreshes it a minute after each half hour.

Energy Hippo can read the file once the profile fix in the energyhippo working tree
is built (uncommitted). With the fix, ODBC profiles send their "Additional connection
parameters" to the driver, and that is where an Access profile names its file
(`DBQ`). Without it, no ODBC profile can open a file-based source:

- **Access:** the driver fails with `DATABASE` or `SERVER` (IM006) and needs `DBQ`.
- **Text:** with `DATABASE` it opens but can't find the file.

## Run it

```powershell
docker compose -f services/sources/compose.yml --profile historian up -d --build historian
```

The image derives from the source image, so the readings come from the published
release's model. It refuses to start when the image's source fingerprint differs from
the release in the `source-data` volume.

- **Where the file goes:** `services\sources\historian-output\northlake-historian.accdb` by default. To move it, set
  `NORTHLAKE_HISTORIAN_ROOT` to another folder, then run the same command again. The profile below assumes
  `C:\ProgramData\EEM Suite\NorthLake\Historian`. The Workers service's account must be able to read that folder.
- **Health:** `docker compose -f services/sources/compose.yml --profile historian ps historian` shows healthy while the
  file is less than 65 minutes old. The log has one `published` line per write, with the window, the row count, and
  how many rows were added or replaced.
- **Stop:** `docker compose -f services/sources/compose.yml --profile historian stop historian`. The file stays.

## How a write works

- **Window:** on first start, the whole history from `historyStartLocal` (1 January 2024). After that, each write
  covers the last `refreshHours` (48), ending at the last closed half hour, as an upsert. New readings appear, and a
  `PROV` code clears once the reading is a day old.
- **Staged swap:** the writer updates a copy of the database, and the copy then replaces the published file, so a
  reader never sees a half-written database. While Energy Hippo has the file open the swap still succeeds; if Windows
  refuses it, it is retried. No `.laccdb` lock file is left behind.
- **Writer:** `writer/HistorianWriter.java` uses Jackcess 5.0.4, which the Dockerfile pins by checksum, as it does
  both Java images.
- **File:** Access 2016 format, with table `SyntheticIntervalReadings`. Its primary key is `(Channel, UtcTimeStamp)`,
  plus an index on `(Channel, TimeStamp)`.

## The rows

One row per reading of the Library's electric service, every 30 minutes, from the
canonical source model (meter `library_historian_electric_interval`). So the values
agree with every other Northlake feed.

| Column | Holds |
| --- | --- |
| `Channel` | `ch_odbc_library_electric_kwh_30m` |
| `UtcTimeStamp` | The interval end in UTC; with Channel, the key |
| `TimeStamp` | The interval end as campus wall time (the node reads Local timestamps). The repeated autumn hour has two rows with one TimeStamp |
| `Value` | kWh for the half hour |
| `SourceClassification` | Actual, Estimated, Substituted or Unknown; empty for a plain reading |
| `SourceCode` | The vendor's code, up to 16 characters; empty for a plain reading |
| `Reader`, `Method` | Who or what produced a flagged reading, and how |
| `HistorianTag` | `LIB.ELEC.KWH.30M` on every row |

Flags follow the calendar in `historian.json`. A window marks the readings whose
half hour lies wholly inside it:

| When (campus time) | Classification and code | Reader, method | Why |
| --- | --- | --- | --- |
| 14 Aug 2024, 10:00-12:00 | Substituted, `SUB1` | facilities.energy, Manual | Valley Electric swapped the Library meter that day (the model's before and after meters) |
| 3 Jun 2025, 08:00-14:00 | Estimated, `EST1` | bms-historian, Interpolated | The historian lost its link to the meter |
| The last 24 hours | Actual, `PROV` | bms-historian, Raw | Unvalidated; the code clears once a reading is a day old |

What Energy Hippo does with them:

- **Estimated and Substituted** set the archive's estimated bit on every point.
- **Codes** are kept only on enrolled points.
- **Metadata** reaches the broker message but is not stored yet.
- **`PROV`** gives the same-value recode path. A reading arrives with `PROV`, then again a day later with no code. The
  query re-reads the last 48 hours for that reason, and an unchanged repeat is a duplicate.

Flags are exceptions. On 7 November 2026 the file held 49,974 rows, 64 of them flagged.

## Energy Hippo settings

Once the profile fix is built, enter these. They are also in `historian.json` under `eem`.

**Profile `SyntheticCustomerHistorian`**, in Profile Manager:

| Field | Value |
| --- | --- |
| Database type | ODBC |
| ODBC driver | `Microsoft Access Driver (*.mdb, *.accdb)`, 64-bit. It comes with 64-bit Office or the Access Database Engine |
| Additional connection parameters | `DBQ=C:\ProgramData\EEM Suite\NorthLake\Historian\northlake-historian.accdb;ReadOnly=1`, the file's path on the EEM host |
| Server, database, user, password | Empty |
| Windows authentication | Off. With it on, Test connection skips the check instead of opening the file |

The parameters box refuses keywords that the profile's own fields set, such as
`Driver`, `SERVER`, `DATABASE`, `UID`, `PWD` and `DSN`.

**Node ODBC-LIBRARY-HISTORIAN:**

- `SourceClassificationName` = `SourceClassification`
- `SourceCodeName` = `SourceCode`
- `MetadataColumns` = `Reader,Method,HistorianTag`

**Query**, the text stored under the node's `QueryKey`
(`SyntheticGatewayQueries:LibraryElectricInterval`). It is Access SQL: `TimeStamp`
and `Value` are reserved words, so they are bracketed.

```sql
SELECT [TimeStamp], [Value], SourceClassification, SourceCode, Reader, Method, HistorianTag FROM SyntheticIntervalReadings WHERE Channel = 'ch_odbc_library_electric_kwh_30m' AND [TimeStamp] > DateAdd('h', -48, CDate('|LastTimeStamp|')) ORDER BY UtcTimeStamp
```

The profile, node parameters and query are Stage 3 recipe values, which the Step 5
session owns.

## Tests

Twelve; no database and no Java:

```powershell
.\services\bacnet\.runtime\venv\Scripts\python.exe -B -m unittest services.historian.tests.test_rows services.historian.tests.test_service -v
```

## Rows for another store

`rows.py` writes the same rows without the container:

```powershell
.\services\bacnet\.runtime\venv\Scripts\python.exe -B -m services.historian.rows --start 2024-01-01T00:00:00-08:00 --end 2026-11-07T12:00:00-08:00 --format sql --output historian.sql
```

`--format csv` writes them with a header. `--now` sets the moment the last 24 hours
count back from; it defaults to `--end`. The SQL is plain INSERT batches that SQL
Server and PostgreSQL both accept, for loading an empty table. Any Python with the
source requirements works; the BACnet venv above already has them.

Table, SQL Server (PostgreSQL: `timestamp(0)` and `numeric(18, 6)`):

```sql
CREATE TABLE SyntheticIntervalReadings (
    Channel varchar(64) NOT NULL,
    UtcTimeStamp datetime2(0) NOT NULL,
    TimeStamp datetime2(0) NOT NULL,
    Value decimal(18, 6) NOT NULL,
    SourceClassification varchar(16) NULL,
    SourceCode varchar(16) NULL,
    Reader varchar(64) NULL,
    Method varchar(32) NULL,
    HistorianTag varchar(64) NOT NULL,
    CONSTRAINT PK_SyntheticIntervalReadings PRIMARY KEY (Channel, UtcTimeStamp)
);
CREATE INDEX IX_SyntheticIntervalReadings_TimeStamp ON SyntheticIntervalReadings (Channel, TimeStamp);
```

This folder is outside the source bundle's fingerprint (`services/sources/*.py` and
`*.json`), so changing it never needs a source release.
