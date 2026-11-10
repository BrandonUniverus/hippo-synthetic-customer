# EEM mapping rules (generator inputs)

The files here are not the implementation. They are the rules the generators
use to turn the customer source model (`data/scenarios`, `data/providers`,
`data/security`) into the customer's own documents under `documents/` and, once,
into the Stage 2 editor files. The implementation itself lives in
`implementation/stage-N-*/` as one YAML file per EEM editor; start with
`implementation/northlake-implementation-guide.pdf`.

| File | Used by | Owns |
| --- | --- | --- |
| `northlake-eem-stage1-setup-v1.yaml` | `generators/northlake_packet.py` | Company defaults (archive interval, time zone, country, alarm colours), the scenario sites each company creates, the Weather Reference site |
| `northlake-eem-metaworld-stage1b-v1.yaml` | `generators/northlake_packet.py`, `generators/stage2_hierarchy.py` | EEM mapping only: measure types by commodity, which channel roles become points and how they are named, which points EEM creates itself, archive intervals and the degree-day index, meter multipliers and bill-cycle rules, billing account kinds, weather stations, aggregates and baselines |
| `northlake-bill-entry-v1.yaml` | `generators/northlake_packet.py` | How each provider's bills arrive (import, manual, allocation, generation), which sets every account's Bill Entry Type |
| `northlake-ap-gl-v1.yaml` | `generators/northlake_packet.py` | The GL chart, each account's AP upload flag and default GL accounts, and the bill validation tests set at account scope |

The generators assert the join between these files and the source model before
writing anything (identifier formats, one building per company, aggregate
members sharing unit and interval, security scope matching ownership). Change
the owning file and regenerate.

Everything that used to be an "entry plan" here (rates, calendars, permissions,
tenant rebilling, sustainability, operations) has been rewritten into the stage
folders in the editors' own shape and removed from this directory.
