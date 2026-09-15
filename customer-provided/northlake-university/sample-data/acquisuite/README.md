# Student Center AcquiSuite handover

Provided by Northlake Facilities Operations. Packet 0.3. All readings are synthetic.

The Student Center electric meter is **SYN-VED-M-0040004**, on Valley Electric
account **SYN-VED-A-0010004**. Its logger serial is **ASQVED01** and its device
identifier is **STUDENT**. Files use the name `ASQVED01_STUDENT.log`.

## File specification

There is **no header row**. Each line contains these comma-separated fields:

| Position | Measurement | Unit | Meaning |
| --- | --- | --- | --- |
| 0 | Timestamp | UTC | Start of the 15-minute interval, enclosed in single quotes |
| 1 | Delivered energy | kWh | Energy used during this interval; not a cumulative register |
| 2 | Average demand | kW | Average power during the same interval |

The complete sample represents January 15, 2024 in Sacramento, from **00:00 to
23:45 PST**. UTC timestamps run from **2024-01-15 08:00:00** through
**2024-01-16 07:45:00**. No DST transition occurs in this sample.

The values describe a simplified operating day: 40 kW overnight, 80 kW during
morning opening, 120 kW during the working day, 100 kW in the evening, and 60 kW
late at night. Every interval's kWh equals its average kW multiplied by 0.25 hours.

## Supplied deliveries

| Folder | Rows | Energy | Peak demand | Purpose |
| --- | ---: | ---: | ---: | --- |
| `complete/` | 96 | 2,020 kWh | 120 kW | One complete day; also use the same file again for replay testing |
| `gap/` | 88 | 1,780 kWh | 120 kW | Eight missing intervals, from 12:00 through 13:45 PST |
| `backfill/` | 8 | 240 kWh | 120 kW | Only the missing intervals |

`expected-results.json` includes file hashes and expected counts. There are two
measurements per row, so the complete file supplies 192 point readings. Adding
the backfill to the gap must recover the complete day's 96 timestamps per point
and 2,020 kWh. Replaying the complete file must not increase unique timestamps
or energy totals.

Deliver **one case at a time**. The complete run and the gap/backfill run start
from separate copies of the same configured, empty baseline. These three folders
are alternative deliveries, not three independent meters or days.

The file has been generated and checked against its expected values. Installed
gateway execution, data storage, reports and replay behavior still require the
implementation team's acceptance run. The accompanying
[UI checklist](../../../../eem/northlake-onboarding-ui-checklist.md) describes that run.
