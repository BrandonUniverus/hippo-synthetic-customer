# Northlake inventory and hierarchy standard

Status: adopted 2026-09-14 and implemented in packet 0.3. Section 3 is the
standing rule set for `scenarios/`, `eem/`, the generators and the workbook;
section 5 records the decisions taken and section 6 what changed. Section 1
keeps the review findings that led here.

## 1. Why this exists

Before packet 0.3 the packet described the same physical estate three different ways:

- `scenarios/demo-university-v1.yaml` lists the physical facts: 2 sites, 6
  buildings, 21 accounts, 23 meters, 38 channels plus 11 reference channels.
- `eem/northlake-eem-stage1-setup-v1.yaml` and
  `eem/northlake-eem-metaworld-stage1b-v1.yaml` re-list buildings, meters and
  points per EEM company with their own level names ("Portfolio", "Service
  Area", "Served Building") and their own display names, and count 29 meters and
  52 points.
- The generated register and Data Collection workbook render the EEM view, so
  the customer-facing documents inherit EEM mapping decisions. The intake
  overview and cover letter still describe the plant as a university-owned
  central plant on the campus.

The symptoms raised in review, with their causes:

| Symptom | Cause |
| --- | --- |
| "Applied Science Center" appears three times in the Hierarchy tab (under the university, and under the plant as "Chilled Water / Applied Science Center" and "Steam / Applied Science Center"). Admin Hall, Main Library and Student Center appear twice. | The thermal plant company was given its own copy of every building it serves, split by commodity, instead of the building holding its own thermal meters. |
| The plant is "part of the university" in the intake but a separate company with a duplicate campus in the EEM manifests. | The plant's role as a **provider** (it bills chilled water and steam) was mixed with its role as a **company** (it owns a plant). |
| Cedar Row is two buildings with one "common electric" meter each, while the Tenants and Leases tab promises 60 + 64 unit submeters that exist nowhere. | Unit metering was deferred to the Phase 4 tenant spec and never entered the inventory. |
| Admin Hall shows 3 meters in one company and a 4th (steam) in another. | Same duplication. The building's real service list was never written down. |
| Every bill-only meter carries "monthly" points with no interval or source. | Bill usage lives on the billing account in EEM, not on points. |
| "Science Center" and "Library" in the scenario, providers and `docs/synthetic-customer-v1.md`; "Applied Science Center" and "Main Library" everywhere EEM-facing. | Two files own the name. |
| The Cedar Row A FIG water interval is a reference channel in the scenario and a third point on the water meter in Stage 1B. | Same fact declared twice. |
| A fourth company, Northlake Town Center, exists in `eem/northlake-town-center-v1.yaml`, the cover letter and the Tenants and Leases tab, but not in the scenario, Stage 1, the security manifest or the hierarchy. | Phase 4 content leaked into the current packet. |
| 12 university groups in the security manifest, 11 in Stage 1; Stage 1B lists `VED-TOU-GS` only while the register lists `VED-TOU-GS-FY25` too. | Drift between re-listed copies. |

## 2. What EEM actually requires

Verified in `C:\Hippo\Git\univerus\energyhippo` (EEM Suite 7.0).

### 2.1 Node types and storage

`HierarchyNodeTypes` (`src/Domain/EEMSuite.Domain/Organizations/Hierarchy/Models/HierarchyNodes/HierarchyNodeTypes.cs`):
Company -1, UserDefined 0, Site 1, Location 2, Meter 4, Point 5. Every node of
every type is one `MetaWorld_TBL` row (`CompanyID`, `ParentID`, `LevelNbr`,
`InternalLevelNbr`, `MetaType`, `Description`, `Area`, `AD_AddressID`,
`ProviderID`, `RatescheduleId`). A building is a Location node plus a `Premise`
row (`PM_Number` is the building code), an `Address` with coordinates and an
`Area`; that is exactly what `rp_BuildingList` reports. A meter adds a `Meter`
row (`MT_MeasureTypeID`, `BA_BillingAccountID`, `SM_SerialNumber`,
`SM_Multiplier`, `BillCycle`). A point adds `PointDef_TBL` (`UN_UnitID`,
`Interval`, `PtType`, `MT_MeasureTypeID`, gateway binding).

### 2.2 Levels

`MetaLevel_TBL` holds a company's levels as one ordered list. `HierarchyList`
and `MetaLevel_SaveList` enforce the list itself: only UserDefined may repeat,
and Location, Meter and Point are pinned, in that order, at the bottom, with
Site and UserDefined levels above them.

Placement is scope-based, not depth-based. `HierarchyNode.CanAddNode` allows a
node under any node of broader scope and refuses "an object with the same or
lesser scope"; `MetaWorld_Save` records the resulting tree depth in `LevelNbr`
and takes the node's `MetaType` from its own internal type. So a point can sit
directly under a company or a site, a meter directly under a site, and levels
may be skipped. The Site → Building → Meter → Point shape in section 3 is a
convention chosen for consistency and for reports that expect it
(`rp_BuildingList` reads Location nodes with premises and addresses), not an
EEM restriction. Nodes never move between companies.

### 2.3 Where facts live

- Commodity is `MT_MeasureTypeID` on the meter and on each point. Unit and
  interval are on the point.
- Bills attach to a meter through `BA_BillingAccountID` (provider, account
  number, bill cycle); bill usage and cost are bill data, not point archives.
- Points hold interval or register archives. A meter "is made up of 0 or more
  points", so a bill-only meter can have none.
- Weather stations are meters with measure type 28 (Weather) and an address;
  `WeatherStationMap_tbl` assigns one station per node and children inherit it.
  A temperature point with the degree-day index type spawns HDD and CDD related
  points (`PtRelatedData_TBL` reasons H and C); baselines use reason B.
- Aggregates are points registered in `PointAggregates_TBL` with members in
  `PointAggregatePoints` (multiplier, required); members share unit and interval.
- Companies are flat (no parent company) and are the security boundary. A group
  in one company can be granted reach into another company's subtree
  (`Permissions_TBL.MetaCompanyID` + `MetaKey`), so shared visibility never needs
  copied nodes.
- EEM has no "organization unit" concept. Departments and responsibilities are a
  contact register in the workbook, not hierarchy.

## 3. The standard

R1. **One company per operating unit that owns meters and pays bills.** An EEM
company is an operating and security boundary, not a legal entity. Cedar Row and
the plant are both university-owned and both get their own company because each
has its own staff, accounts and reports. Three companies stay: Northlake
University, Cedar Row Apartments, Northlake Thermal Plant. Northlake Town Center
joins later under the same rules (Phase 4), not before.

R2. **Every company defines the same four levels:** Site → Building → Meter →
Point. No Portfolio or Service Area levels. A Site is a grouping (campus,
property, plant, reference stations) and may hold a single Building. Physical
meters always sit under their Building and their points under the meter; the
two places where a level is skipped on purpose are R7 and R8.

R3. **A physical building is one Building node, in one company, once.** It never
appears in another company and is never split by commodity. A non-building
service area (grounds, a carport, a substation yard) is also a Building node;
its name says what it is.

R4. **A building holds every meter that serves it,** whatever the commodity or
provider: electric, gas, water, fire service, chilled water, steam, solar,
submeters, sensors. Commodity is never part of a building name.

R5. **A meter is one device (or one logical source) on one account, and its
points are the channels that device produces.** Bill-only meters have no points.
Interval electric meters carry kWh and kW. Handheld-read meters carry a register
point and its usage-delta point. Submeters carry one point.

R6. **Meter replacements are two meter nodes under the same building** with
effective dates (the Library pattern stays).

R7. **Rollups are aggregate points placed directly under the node they
summarise.** Campus totals sit under the campus Site, a building's net electric
under that Building. No logical rollup meters. This is how the campus aggregates
are already placed and it is a supported EEM shape (2.2).

R8. **Weather is a Site of its own** in the university company:
`Weather Reference` → `KSAC`, `KSMF` (station Meters directly under the Site,
as today) → observation, forecast and degree-day points.

R9. **The thermal plant is a provider to the university and a company for
itself.** University buildings own the chilled-water and steam meters that
measure what they receive; those meters carry provider Northlake Thermal Plant,
an allocation rate schedule and an internal cost-center billing account in the
university company. The plant company owns the plant: its utility services,
production meters and controllers. Nothing about a served building is stored in
the plant company.

R10. **Cedar Row is master-metered with owned submeters.** The property pays the
utility on one master meter per commodity per building; every apartment has its
own electric and water submeter (one point each); house meters cover corridors,
laundry, pool and lighting. Phase 4 tenant rebilling maps units to those
submeter points. The utility bills no resident.

R11. **One name.** Buildings keep the names the customer uses (`Science Center`,
`Library`); the EEM-side aliases (`Applied Science Center`, `Main Library`)
disappear. Building = common name. Meter =
`<Building> <Commodity> <Qualifier>` (`Admin Hall Electric Main`,
`Cedar Row A Unit 214 Electric`, `Central Plant Chilled Water Supply`). Point =
channel (`kWh`, `kW`, `therms`, `kgal`, `ton-hours`, `klb`, `Register Reading`).
Tags stay synthetic (`SYN-VED-M-…`).

R12. **One owner per fact.** `scenarios/demo-university-v1.yaml` owns the
physical inventory: sites, buildings with a service profile (heating, cooling,
hot water, kitchen and process loads), accounts, meters, channels, and the
company that owns each site. `eem/` files own only the mapping: level names,
measure and point types, gateway profile per channel, rollups, weather
assignments, groups. They reference scenario ids and never re-list buildings,
meters or points. The register and workbook are rendered from the join, so the
counts can only ever be one set of numbers.

## 4. Target inventory

Per building. "Bill" is a provider account with monthly bills; "sub" is an owned
submeter with readings; "logical" is a data source with no device.

### 4.1 Northlake University

Site **Northlake Main Campus**

| Building | Profile | Meters |
| --- | --- | --- |
| Admin Hall | 85,000 sq ft office and classrooms. Steam heat from the plant, rooftop DX cooling, gas domestic hot water. | Electric Main (VED, bill, billing demand) · Gas (SGU, bill) · Domestic Water (RCU, bill: water, sewer, stormwater) · Fire Service (RCU, bill, flat charge, no usage) · Steam (NTP condensate meter, cost center) |
| Science Center | 120,000 sq ft labs and classrooms. Chilled water and steam from the plant, gas for lab and kitchenette loads, PV array. | Electric Main (VED, bill, 15-min via MV90 MDEF) · Electric Lab Wing (VED, second service, bill) · Gas (SGU, bill) · Domestic Water (RCU, bill) · Fire Service (RCU) · Chilled Water (NTP BTU meter, hourly BACnet, cost center) · Steam (NTP, cost center) · PV Array (Helios, PPA, 15-min) · Lab Environmental Sensors (logical, Spinwave) · Rollup: Net Electric (aggregate) |
| Library | 70,000 sq ft. Steam heat, DX cooling, gas hot water. Electric meter replaced August 2024. | Electric Old Meter (VED, to 2024-08-14) · Electric New Meter (VED, from 2024-08-15) · Gas (SGU) · Domestic Water (RCU) · Steam (NTP) · Electric Historian (logical, ODBC) |
| Student Center | 95,000 sq ft dining and events. Steam heat, DX cooling, large kitchen gas load, PV array. | Electric Main (VED, 15-min via AcquiSuite) · Kitchen Gas (SGU, MVRS handheld route: register + usage) · Domestic Water (RCU, bill) · Kitchen Sewer-Deduct Water (sub, usage subtracted from sewer) · Steam (NTP) · PV Array (Helios) · Fake Gateway Smoke (logical) |
| Lakeview Residence Hall (new) | 110,000 sq ft, 300 beds. Steam heat, DX cooling, gas hot water and laundry. | Electric Main (VED, 15-min) · Gas (SGU) · Domestic Water (RCU) · Fire Service (RCU) · Steam (NTP) · Laundry Electric (sub) |
| Recreation and Aquatics Center (new) | 65,000 sq ft with pool. Chilled water and steam from the plant, gas pool heating. | Electric Main (VED, 15-min) · Pool Gas (SGU) · Domestic Water (RCU) · Pool Fill Water (sub, sewer deduct) · Chilled Water (NTP BTU) · Steam (NTP) |
| Campus Grounds (new, not a building) | Irrigated fields and quads. | Irrigation Water North, South, Athletics (RCU irrigation rate, seasonal, bill) · Area Lighting (VED unmetered flat service, bill, no usage) |
| Parking Structure (new) | 4 levels, EV charger bank. | Electric Main (VED, bill) · EV Chargers (sub, hourly via the fixed network) |

Campus aggregate points (interval electric kWh and kW, PV generation and
delivered chilled-water ton-hours) sit directly under the Site.

Site **Weather Reference** → KSAC (NOAA) and KSMF (Aeris) station meters with
temperature, humidity, wind and forecast points plus HDD and CDD related points;
stations assigned to every Building in all three companies.

As built: 8 buildings, 47 meters (including the two weather station meters),
35 points, 24 provider accounts, 6 cost centers and 2 PPA agreements.

### 4.2 Cedar Row Apartments

Site **Cedar Row Apartments**

| Building | Profile | Meters |
| --- | --- | --- |
| Cedar Row A | 60 apartments, 3 storeys, central gas hot water, electric cooling in units. | Electric Master (VED, monthly bill with billing demand) · Electric House (sub: corridors, laundry) · Unit Electric ×60 (sub, AMR fixed network, one kWh point each) · Water Master (RCU, bill: water and sewer; hourly FIG export at A, Neptune route at B) · Water House (sub) · Unit Water ×60 (sub, Neptune monthly route: register + usage) · Gas House (SGU, bill, hot-water boilers) · Fire Service (RCU) |
| Cedar Row B | 64 apartments, same profile; the water route already exists. | As A with ×64 |
| Common House | 18,400 sq ft leasing office, community room, laundry, pool. | Electric (VED, bill) · Gas (SGU, pool and hot water) · Domestic Water (RCU) · Pool Fill Water (sub, sewer deduct) |
| Carport and Grounds (not a building) | Solar carport, parking lighting, landscape. | PV Carport (Helios, PPA, 15-min) · Parking Lighting (VED unmetered flat) · Irrigation Water (RCU) |

As built: 4 buildings, 267 meters, 385 points, 13 provider accounts and one PPA.
This is the wall of meters, and it is what Phase 4 needs: master → unit
submeters with house overhead. Apartment numbers are floor × 100 + position
(A: 101–120, 201–220, 301–320; B: four floors of 16).

### 4.3 Northlake Thermal Plant

Site **Northlake Central Plant** → Building **Central Plant** (58,400 sq ft)

| Meter | Kind |
| --- | --- |
| Plant Electric Service | VED, bill, primary-metered, 15-min via MV90 MDEF |
| Boiler Gas | SGU, bill, monthly |
| Makeup Water | RCU, bill |
| Cooling Tower Deduct | sub, sewer deduct |
| Chilled Water Supply | production BTU meter, hourly BACnet (ton-hours, tons) |
| Steam Production | boiler output, hourly (klb, lb/h) |
| Condensate Return | hourly (kgal) |
| Chiller Controller | logical, Modbus 5-min (kW, enable status) |
| Plant Efficiency | aggregate point (kW per ton) under the Site, later |

As built: 8 meters, 11 points and 3 provider accounts. The plant company holds
no campus building. The served-building thermal meters moved under their
buildings in the university company and keep provider Northlake Thermal Plant,
their `SYN-NTP-C-…` cost centers and their bill images. Production minus
delivered is the distribution loss, which is now reportable.

## 5. Decisions (taken 2026-09-14)

1. **Plant as a company.** Yes. The company owns meters and points of its own
   (production, consumption and the chiller controller), so "how much did we
   produce versus how much did we use to produce it" is an interval question
   inside one company, and the provider relationship between two companies is
   exercised.
2. **Cedar Row metering model.** Master-metered with owned submeters. The
   property is the utility's customer and rebills residents; this is also the
   test bed for bill allocation.
3. **Campus expansion.** Accepted now: Lakeview Residence Hall, the Recreation
   and Aquatics Center, the Parking Structure and Campus Grounds.
4. **Portfolio and Service Area levels.** Dropped. Department views come from
   reports and group scope, not levels.
5. **Bill-only meters get no points.** Adopted.
6. **Names.** The customer's names stay (`Science Center`, `Library`), as a
   real customer would use them; every document and manifest uses the same name.
7. **Northlake Town Center** stays out of this packet and arrives with Phase 4
   under the same standard.

## 6. What changed (packet 0.3)

1. `scenarios/demo-university-v1.yaml`: `companies`; `ownerCompanyId` per site;
   a `serviceProfile` and `unitNumbering` per building; the new buildings and
   grounds nodes; the missing water, fire-service, second-service, deduct and
   irrigation meters; the served-building thermal meters under their buildings
   with `providerId: northlake_thermal_plant`; `ownedMeters` with per-apartment
   templates (`{unit}`); per-apartment gateway `pointTemplates`; the FIG
   interval as a channel of the water meter, not a reference channel.
2. `eem/northlake-eem-stage1-setup-v1.yaml`: one level list for all companies;
   `hierarchySitesFromScenario` per company; the Weather Reference site; the
   12th university group.
3. `eem/northlake-eem-metaworld-stage1b-v1.yaml`: mapping rules only
   (`measureTypes`, `pointRules`, `billingAccountKinds`, weather assignments,
   aggregates with a per-apartment `memberTemplate`, baselines); no re-listed
   buildings, meters or points; rate schedule lists match `providers/`.
4. `providers/*.yaml`: `VED-TOU-PRI`, `VED-AL-1`, `SGU-GL-1`, `RCU-IRR` and
   `RCU-FIRE`; the plant's served buildings extended to Lakeview Residence Hall
   and the Recreation and Aquatics Center.
5. `scenarios/northlake-onboarding-v1.yaml`: packet 0.3; support locations
   removed; decisions and deferred items updated; the two submeter sources added.
6. `generators/northlake_packet.py` and `generators/update_workbook.py`: the
   register, workbook, coverage and mapping template are rendered from the
   scenario join with one set of counts; Service Profiles and Units and
   Submeters tabs added; the Codex-only `build_workbook.mjs` retired.
7. `security/northlake-eem-security-v1.yaml` and
   `eem/northlake-eem-permissions-v1.yaml`: no new companies; each company's
   scope lists exactly the sites and buildings it owns (the plant company holds
   only the Central Plant), which the generator now asserts; the Science Center
   scoped group and its node scope are unchanged.
8. Docs: `docs/synthetic-customer-v1.md`, the intake overview and cover letter,
   the ENERGY STAR mapping, `docs/dream-customer/phase4-tenant-rebilling-spec.md`,
   the UI checklist and the gateway coverage.
9. Bill images: the four thermal allocation statements stay valid (same cost
   centers, addressed to the university). New accounts get statements when
   Phase 3 bill generation exists, not hand-drawn PDFs.

## 7. Real-world references used

- University metering programmes meter electricity, steam or condensate, chilled
  water, hot water, potable water and gas per building at revenue grade, with
  well over a thousand meters on a large campus (Cornell Facilities and Campus
  Services, "Energy Metering"; UVA Building Performance Energy and Water Tracker,
  "How we meter").
- BTU meters at each served building (flow plus supply and return temperature)
  are the standard way central plants allocate chilled water and heating energy
  (LEEDuser, Cadillac Meter, MEP Academy).
- Multifamily properties are either master-metered (one meter per building or
  property; the owner pays and recovers costs by submeter or ratio billing) or
  direct-metered (the utility meters each apartment). Submetered properties use
  15 to 40 percent less water than allocation-billed ones, which is why owners
  install per-unit meters (submeter.com, Conservice, housingfinance.com).
