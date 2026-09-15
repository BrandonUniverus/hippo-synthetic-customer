# Integration Coverage

This matrix tracks what the synthetic customer must eventually prove. It starts as a planning document and should become more concrete as generators and validations are added.

Packet 0.3 supplies the first deterministic AcquiSuite deliveries and the
[gateway/format acceptance list](../eem/northlake-gateway-coverage.md).
All installed UI setup and ingestion acceptance remain **Not run**. Local
generator checks establish file contents, not downstream EEMSuite behavior.

| Area | Data needed | V1 target | Status |
| --- | --- | --- | --- |
| Monthly bill ingestion | Accounts, meters, bills, charges, units, provider metadata | Electric, unmetered lighting, gas, water, sewer, stormwater, irrigation, fire service, chilled water, steam, solar PPA | Planned |
| Interval ingestion | Channels, readings, units, timestamps, time zone rules | Electric and solar 15-minute; chilled water, Central Plant production and electric submeters hourly | Planned |
| AcquiSuite gateway | Runtime nodes/points, serial/device/row mappings, AcquiSuite log files | Student Center and Lakeview Residence Hall electric 15-minute kWh and kW; complete, gap and backfill deliveries for Student Center | Generated; installed acceptance pending |
| NOAA gateway | Runtime station nodes/points, NOAA XML observations, weather type mappings | KSAC temperature, humidity, and wind observations | Planned |
| Aeris Weather gateway | Runtime station nodes/points, Aeris credentials, forecast/history state | KSMF observed and forecast temperature | Planned |
| MV90 MDEF gateway | Runtime nodes/points, recorder/channel mappings, `.mde` files | Science Center, Recreation and Aquatics Center and Central Plant electric 15-minute kWh and kW | Planned |
| MV90 MV9 gateway | Runtime nodes/points, recorder/channel mappings, `.mv9` files | Helios solar generation and export intervals | Planned |
| BACnet gateway | Runtime nodes/points, device/object mappings, present-value reads | Science Center and Recreation and Aquatics Center chilled-water ton-hours and tons; Central Plant chilled-water supply, steam production and condensate return | Planned |
| Spinwave gateway | Runtime folder/device/channel mappings and CSV files | Science Center wireless temperature and humidity sensors | Planned |
| FIG gateway | Point aliases and FIG-family provider file variants | FIG, SIEMANSREPORT, MEDIATOR, EATON, XML, FIXEDNETWORKS, and CMEP aliases for the Cedar Row A water master; a fixed-network submeter file for every Cedar Row apartment and house electric submeter, the Lakeview Residence Hall laundry and the Parking Structure EV chargers | Planned |
| Modbus gateway | Runtime node TCP settings and register metadata | Thermal plant chiller kW via floating-point holding register | Planned |
| ODBC gateway | Source profile, query key, timestamp cursor, token substitution | Library electric interval reads from synthetic SQL historian | Planned |
| Fake gateway | Generation parameters, state file, optional replay/anomaly settings | Deterministic synthetic interval smoke channel | Planned |
| Neptune gateway | Handheld upload file, MetaWorldID, usage/register point mappings | Cedar Row B water master route upload; Cedar Row apartment and house water submeter route upload | Planned |
| MVRS gateway | Handheld upload file, MetaWorldID, usage/register points, event output | Student Center gas route upload plus HMR event records | Planned |
| HMR events publish | HMR event JSONL, gateway identity, queue/idempotency metadata | MVRS/Neptune event payload publishing | Planned |
| Onsite generation and attributes | Generation channels, PPA invoice, RECs, avoided CO2e | Helios Onsite Solar generation, net metering, REC statement | Planned |
| Backfill processes | Date ranges, channel mappings, missing data windows | One missing interval block and one corrected bill | Planned |
| MDEF generation | Meter definitions, channels, unit metadata, account mappings | Science Center electric interval meter plus provider interval definitions | Planned |
| BIF generation | Billing account, meter, usage, cost, and charge details | Monthly bills for all provider categories | Planned |
| Reports | Customer, site, building, meter, provider, bill, and interval rollups | Basic rollups and known totals | Planned |
| EnergyAI | Building metadata, weather context, interval series, monthly summaries | One campus interval use case | Planned |
| ENERGY STAR | Property `primaryFunction`, gross floor area, occupancy, year built, and per-use `useDetails`; monthly meter data | Campus parent (College/University) with child building properties, a multifamily property with its buildings, and a standalone Central Plant property — 13 properties mapped in `energyStarProperties` (see `docs/energystar-integration.md`) | Planned (property mapping defined) |
| Weather mapping | Station identifiers, local time zone, fallback station | KSAC primary and KSMF secondary | Planned |
| Data quality checks | Missing intervals, duplicates, invalid units, corrected bills | Positive and negative scenario assertions | Planned |

## Coverage Tracking

Use the `Status` column conservatively:

- `Planned`: scenario is described but no generator or validation exists.
- `Generated`: source data and artifacts can be generated.
- `Load-tested`: artifacts have been loaded into a dev environment.
- `Asserted`: automated validation verifies expected results.

## Adding New Coverage

When adding a gateway or integration:

1. Document the minimum required source data.
2. Add or update a scenario in `docs/scenario-catalog.md`.
3. Add fields to the source model only when they represent durable domain data.
4. Generate artifacts from the source model.
5. Add assertions that prove the downstream behavior.
