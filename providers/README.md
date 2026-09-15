# Utility Providers

This directory fully configures the utility providers for the synthetic
customer. Each provider has a machine-readable definition (`<id>.yaml`) plus the
narrative below describing its identity, what it does, and what it supplies. The
scenario manifest (`scenarios/demo-university-v1.yaml`) indexes these files
through a `configRef`, and the source model (`schemas/synthetic-source-model.md`)
holds the matching `provider` and `provider_service` concepts.

The set is deliberately split **3 + 2**:

- **3 everyday utilities** — the providers almost every customer has. One is
  data-rich (electric), one is deliberately simple (gas), and one bundles
  several services on a single account (municipal water/sewer/stormwater).
- **2 unique provider identities** — deliberately *not* everyday utilities. They
  exist to stress data shapes that ordinary meters never produce: internal
  district-energy cost allocation, and behind-the-meter solar generation with
  environmental attributes.

## The five providers

| # | Provider | Class | Kind | Supplies | Data products |
| - | -------- | ----- | ---- | -------- | ------------- |
| 1 | [Valley Electric District](valley-electric-district.yaml) | everyday | distribution utility | electric | monthly bills · 15-min interval · billing demand · unmetered area lighting |
| 2 | [Sierra Gas Utility](sierra-gas-utility.yaml) | everyday | distribution utility | natural gas | monthly bills only |
| 3 | [River City Utilities](river-city-utilities.yaml) | everyday | municipal multi-service | water + sewer + stormwater, irrigation, fire service | one bundled bill, several service lines · separate irrigation and fire-service accounts |
| 4 | [Northlake Thermal Plant](northlake-thermal-plant.yaml) | **unique** | district energy plant | chilled water + steam | internal cost allocation + hourly chilled-water interval |
| 5 | [Helios Onsite Solar](helios-onsite-solar.yaml) | **unique** | onsite generation (PPA) | solar generation | generation interval · PPA invoice · REC/CO2e statement |

---

### 1. Valley Electric District — everyday, single commodity, data-rich

A municipal electric distribution district. It is a *single* commodity but the
most data-rich everyday provider, so it carries most of the interval coverage.
Every metered account produces a monthly time-of-use bill with energy, billing
demand, and a facility charge; the interval-metered buildings (Science Center,
Student Center, Lakeview Residence Hall, Recreation and Aquatics Center, Central
Plant) also produce 15-minute kWh and kW channels, while Admin Hall, Library,
Parking Structure, Cedar Row A, Cedar Row B and Cedar Row Common House are
monthly only. Cedar Row A and Cedar Row B are each billed on one master meter;
the district never bills a resident. Demand is billed on the highest 15-minute
kW, power factor can trigger a reactive-power adjustment, and a fiscal-year
tariff step drives the `provider_rate_change` scenario. This provider also hosts
the `meter_replacement` and `missing_interval_backfill` scenarios.

Rate schedules: `VED-TOU-GS` (Time-of-Use General Service, 2024) and
`VED-TOU-GS-FY25` (its 2025 rate change) cover general service. `VED-TOU-PRI`
(Time-of-Use Primary Service) bills the Central Plant on the same seasons at
$0.214 / $0.149 / $0.098 per kWh peak / part-peak / off-peak, $21.90 per kW of
demand and a $410.00 monthly facility charge. `VED-AL-1` (Unmetered Area
Lighting) bills Campus Grounds and Cedar Row Carport and Grounds a flat $14.60
per fixture per month, with no metered usage.

### 2. Sierra Gas Utility — everyday, single commodity, simplest

The simplest everyday provider on purpose: one commodity, monthly bills only, no
interval data. Gas is billed in therms (derived from metered ccf via a heating
value), with strong winter heating seasonality. Buildings bill on `SGU-GN-1`
(General Non-Residential Firm Service); the Central Plant's boiler gas bills on
`SGU-GL-1` (Large Volume Firm Service): a $245.00 monthly customer charge,
$0.982 per therm in winter (November–March) and $0.741 per therm in summer
(April–October) for the commodity, and $0.163 per therm transport. It hosts the
`estimated_bill_correction` scenario (an estimate later superseded by an actual
read) and is the home of the `negative_bad_units` negative test (a file that
declares an unsupported usage unit so ingestion must fail cleanly).

### 3. River City Utilities — everyday, multi-service

The "does multiple things" everyday provider. A single municipal account and a
single monthly statement carry **three** services: potable water, sanitary
sewer, and stormwater. Only water is metered — sewer volume is derived from
metered water, and stormwater is a flat fee based on impervious area (ERUs). This
provider consolidates what were previously two separate stubs (`River City
Water` and `Capital Sewer District`) into one realistic municipal biller. It
hosts `account_number_change` (the account number changes at renewal while site
and building continuity is preserved) and `duplicate_file_import` (re-importing
the bundled file must not double-count any of the three services).

Two schedules bill outside that bundle, on their own accounts. `RCU-IRR`
(Irrigation Water, seasonal, no sewer) charges $5.30 per kgal plus a $96.00
(2-inch) or $168.00 (3-inch) monthly meter charge, for the three Campus Grounds
irrigation meters and Cedar Row Landscape Irrigation. `RCU-FIRE` (Private Fire
Service Line) is a flat $38.00, $62.00 or $95.00 monthly charge for a 4-, 6- or
8-inch line with no metered usage, for Admin Hall, Science Center, Lakeview
Residence Hall, Cedar Row A and Cedar Row B. Campus building water accounts
include stormwater ERUs; irrigation, fire-service, Central Plant and Cedar Row
accounts have no stormwater charge.

### 4. Northlake Thermal Plant — unique: campus district energy

**Not an external utility.** A university-owned central plant, set up as its own
EEM company whose only building is the Central Plant (4122 Plant Service Road).
It *produces* chilled water (cooling) and steam (heating) and *allocates* its
operating cost to the university buildings it serves: chilled water to Science
Center and the Recreation and Aquatics Center; steam to Science Center, Admin
Hall, Library, Student Center, Lakeview Residence Hall and the Recreation and
Aquatics Center. The chilled-water and steam meters at those buildings belong to
the university, with this plant as provider. There is no external account number
and no tariff — buildings receive an internal cost allocation based on
sub-metered consumption, keyed to a cost center rather than a utility account.
It exercises three things ordinary
utilities don't: internal allocation in place of a tariff bill, an hourly (not
15-minute) interval, and a non-electric energy commodity measured in ton-hours
and klb. The plant is itself a Valley Electric customer (`VED-TOU-PRI`), a
Sierra Gas customer (`SGU-GL-1`) and a River City customer (makeup water), which
links Scope 1 (boiler gas) and Scope 2 (chiller electric) emissions to delivered
thermal energy. Its own production meters (chilled-water supply, steam
production, condensate return) make production minus delivered, the
distribution loss, reportable. It is the home of `chilled_water_hourly`.

### 5. Helios Onsite Solar — unique: behind-the-meter generation PPA

A third-party developer that owns rooftop PV at Science Center and Student Center
and the solar carport at Cedar Row Carport and Grounds (plus a small battery),
and sells the output under a Power Purchase Agreement. It inverts the everyday
model in three ways: the channels are **generation/export**, not
consumption (positive-generation, reducing net load); the invoice is priced per
kWh *generated* with an annual escalator, not against a tariff and with no demand
charge; and it supplies **environmental attributes** — Renewable Energy
Certificates and avoided CO2e — that no metered utility produces. Generation nets
against Valley Electric load on shared buildings, so it pairs with
`electric_interval_15min`, and an inverter outage makes it a candidate for
`missing_interval_backfill`.

---

## Shared conventions

**Identifiers.** Provider ids are snake_case. Every synthetic account, cost
center, PPA, and meter number is prefixed `SYN-<CODE>-<TYPE>-#######` so it can
never be mistaken for a real account:

| Code | Provider | Account/agreement letter |
| ---- | -------- | ------------------------ |
| VED | Valley Electric District | `A` (utility account) |
| SGU | Sierra Gas Utility | `A` (utility account) |
| RCU | River City Utilities | `A` (utility account) |
| NTP | Northlake Thermal Plant | `C` (internal cost center) |
| HOS | Helios Onsite Solar | `P` (PPA agreement) |

Provider meters are always `SYN-<CODE>-M-#######`. Owned meters have no provider
account: apartment and house submeters use `SYN-SUB-…`, sewer-deduct submeters
`SYN-DED-…`, and the plant's production meters `SYN-NTP-P-…`.

**Units glossary.**

| Commodity | Usage unit | Demand unit | Interval | Notes |
| --------- | ---------- | ----------- | -------- | ----- |
| electric | kWh | kW | 15 min | Demand = max 15-min kW |
| natural gas | therms | — | none | Derived from ccf × heating value |
| water | kgal | — | none | Thousand gallons |
| sewer | kgal | — | none | Derived from metered water |
| stormwater | eru | — | none | Flat area-based fee, no usage |
| chilled water | ton_hours | tons | 60 min | Cooling energy / instantaneous |
| steam | klb | — | none | Thousand pounds (≈ mmbtu) |
| solar generation | kWh | kW | 15 min | Positive-generation sign |

**File formats → artifact types.** Each provider declares the provider-like
files it supplies and the Hippo artifact each maps to:

- Billing / allocation / PPA invoice extracts → **BIF**.
- Interval extracts (electric, chilled water, solar) → **MDEF**.
- REC / avoided-emissions statement → **integration payload**.

**Source-model mapping.** Each provider file populates one `provider` row and one
`provider_service` row per entry under `supplies:`. `accountModel` →
`account`, `meterModel` → `meter`, `channels` → `channel`, `rateSchedules` →
`rate_schedule`, and `scenarioHooks` link back to `scenario_event` /
`expected_assertion`. The scenario manifest owns the concrete account, meter,
channel, and gateway point inventory; `gatewayBindings` maps those channels to
the EEMSuite gateway runtime keys for the full gateway matrix, including
AcquiSuite, NOAA, Aeris Weather, MV90/MDEF, MV90/MV9, BACnet, Spinwave, FIG,
Modbus, ODBC, Fake, Neptune, MVRS, and HMR event publishing.

## Extending the set (more unique identities)

If you need additional unique providers later, follow the same file shape. Good
candidates that break the everyday mold in different ways:

- **EV charging network** — session-based records (one row per charge session),
  not fixed intervals; tests an entirely different time grain.
- **Waste & recycling hauler** — tons hauled and a diversion percentage, with no
  energy unit at all; tests ESG/sustainability rollups.
- **Reclaimed (purple-pipe) water** — a separate non-potable water commodity.
- **District steam-only or hydrogen supply** — additional thermal/fuel commodities.
