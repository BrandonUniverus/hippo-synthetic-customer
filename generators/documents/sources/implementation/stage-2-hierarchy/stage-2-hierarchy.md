---
title: Stage 2. Hierarchy
subtitle: Units, billing accounts, sites, meters, points, weather stations and aggregates
status: Ready to enter (revised 2026-10-01)
---

# Stage 2. Hierarchy

Stage 2 turns the three companies from Stage 1 into a working meter-to-point tree: the units
Northlake adds to the catalog, billing accounts for every utility and internal counterparty, the
sites and buildings that already exist on the instance plus the new Ridgeline Wind Site and Cedar
Row C, 391 meters, 475 points a person enters (including the three baseline point shells, the
Student Center activity index and the 73 points the handheld routes read), the weather-station
assignment every Sacramento-area building gets, and the eleven aggregates. EEM adds another 204 points of its own
behind these (usage points behind every register, HDD/CDD behind the three temperature indexes),
for 679 points in the finished tree. Cedar Row C, the emergency generators, the switchgear meter and
their points were added on November 7, 2026, for the Stage 3 handheld routes; the Stage 2 import
creates them beside what is already entered.

**Added 2026-11-10: variety.** Stage 2 was already entered, so this is extra work on the installed
instance, and nothing already entered changes. A Toronto site and building bring a second time zone
(Eastern), a second country (Canada), a first area in square metres, a Canadian dollar billing
account and a Node Contact; a closed Lakeshore Boathouse brings a closed building, a two-row area
history, a removed meter (Status Removed), an inactive billing account and a register with a Delta
Multiplier of 1.037; the Ridgeline Wind Site gains a Node Contact; and Step 7 saves one Hierarchy Filter.
Each step below says what these add.
Nothing in this stage loads a bill or an interval reading; that is Stage 3 onward. The baselines
themselves are configured in Stage 3, once their measured points have a gateway. See the
[inventory standard](northlake-inventory-standard.pdf) for how the physical estate was inventoried
before any of this was modeled.

**Added 2026-10-01: the Ridgeline Wind Site.** The Thermal Plant bought a ten-turbine wind company
on July 1, 2024, and it is now part of Northlake: one site with two outdoor nodes, two billing
accounts, 14 meters (one of them a logical billing meter), 72 points and four aggregates, plus four units. Each step below says what
Ridgeline adds. It brings what the campus could not: 10-minute data, a metric site, a four-state
digital point, knots, an Angle unit, air density, a 12,000 multiplier, a generator account that
started mid-window under a new number, and the only Bill Generation account.

The files are written the way the editors show their values: measure types by their EEM names
(Electricity, Potable Water), units as the Units list shows them ("KilowattHours - (kWh)"),
remit addresses as the one-line combo text. Northlake is also built to vary: every Bill Entry Type
but Other, all three Bill Service Types, both invoice templates, backdated account status, a
renumbered account and a transferred one, notes, geocoded addresses, keywords with inheritance and
a keyword type of Northlake's own, every archive interval, both degree-day unit systems, an
activity index, and units the catalog does not ship.

## Before you start

- Stage 1's checks are green apart from what the Stage 1 chapter lists as open. Still to fix there:
  the Helios provider address ("77 Solar Grove Courts"), the stray " Test" at the end of the
  Thermal Plant description, the four abbreviated or blank contact titles, and the Thermal Plant
  provider's Associated Companies (it has none for Northlake University or Cedar Row Apartments).
- Step 6's aggregates and members can be entered before the aggregate registration fix (product
  finding 14); only recalculating them waits for it.
- The sites and buildings this stage's Step 2 covers already exist on the installed instance
  (Database Administrator, Nodes shows them), except the three Ridgeline nodes, as do four billing
  accounts (SYN-VED-A-0010001 to 0010004), which Step 1 completes rather than re-enters.
- Stage 1's Ridgeline changes are in: the Thermal Plant's Level 2 reads Facilities, the Ridgeline
  Wind provider exists with its 18 bill-cycle periods, and the two Ridgeline groups and four users
  exist. Step 2 below grants the groups their Points.

## Step 0. Units

**Where:** Database Administrator, Units.

**Enter:** [00-units.yaml](00-units.yaml): seven new units (Miles, Miles per Hour, Watts per Square
Meter, Events, Equivalent Runoff Unit, Knots, and Power Factor for the switchgear's handheld
register, added November 7) and five seeded units extended to another measure
type (Kilometers per Hour, Meters per Second, Degrees and Kilogram per cubic meter to Weather, PSIG
to Pressure), with their conversions. Each new unit is defined against one reference unit
(1 mi = 1.609344 km) and the editor works out the reverse and the rest of the class; Knots is
defined against Meters per Second, so enter it after Meters per Second's association.

**Why:** Northlake deliberately carries units the catalog does not ship, so the unit system itself
is tested: a new base unit, a compound unit built from a numerator and a denominator, a
User-defined unit (a class takes no numerator or denominator unless it defines them), existing units
associated with another measure type, conversions by multiplier and by offset, a custom Activity
Level unit that drives an index, and a billing unit for a flat fee. Ridgeline adds a unit whose
source misnames it (EEM's NOAA gateway delivers knots for the field it calls wspdm, product finding
45), an Angle unit with no measure type, and two seeded units that share the label kg/m3: air
density takes Kilogram per cubic meter, not Kilograms per Gas cubic meter.

**Order inside the editor:** Add Unit, fill the row and save; then Add measure type for each
association, and in Conversions pick the Reference and enter Multiplier and Offset so that
Reference = this unit x Multiplier + Offset; save again. Miles before Miles per Hour, which uses
it as numerator. A unit class sets which numerator and denominator a unit may have, so a
User-defined unit such as Watts per Square Meter has neither.

**Record:** the Unit ID of each new unit.

**Check:** `00 Units`, `00 Unit measure types`, `00 Unit conversions`. PSIG is a protected
seeded unit, so its conversions stay as seeded (product finding 37).

## Step 1. Billing accounts

**Where:** Database Administrator, Nodes, the company node's Utility Accountant tab.

**Enter:** [01-billing-accounts.yaml](01-billing-accounts.yaml), 53 records.

**Order inside the editor:** select the company, click Add, set Currency Unit to US Dollar first (a
new account starts as Australian Dollar, the first currency by name; the Toronto account takes Canadian Dollar), fill the rest of Definitions and save;
Service Address, Account Address, Account Contact, Notes and Status unlock after the first save.
Status needs an administrator.

**What varies:** Bill Entry Type is Bill Importer for every Valley Electric and River City account
(31), Bill Entry for Sierra Gas and Helios and the Toronto account (15), Bill Allocation for the six Thermal Plant cost
centers, and Bill Generation for Ridgeline's transfer agreement. Bill Service Type is AP Upload
Only (48), No AP Upload for the Cedar Row control account, Bill Payment for the three Helios PPA
accounts and the Ridgeline transfer (a journal). The Thermal Plant cost centers and the Ridgeline
transfer use the Billing Charges Report template. Every account gets Active Billing Account as of
2024-01-01, which bill validation's account-opening test needs, except the two Ridgeline accounts,
which open on 2024-07-01. SYN-RCU-A-0030003 carries its pre-renewal number in Previous Account
Number, and the Ridgeline generator account SYN-VED-A-0010014 the seller's number; one account has
no contact; service addresses carry the building's coordinates; the Thermal Plant's mail stop goes
in Address 2. Two accounts were added on 2026-11-10: SYN-GSH-A-0090001 for the Toronto Research Hall,
the only Canadian dollar account (its provider is Georgian Shore Hydro, Stage 1), and SYN-SGU-A-0020011 for the
Lakeshore Boathouse, which opens 2024-01-01 and is closed on 2025-07-31. The import writes only the Active row, so enter
the closing Status row by hand on the Status page, after the import, with the entry the page lists for closing an account.

**Remember:** Bill Entry lists only Bill Entry accounts. The 31 importer, 6 allocation and 1
generation accounts never appear there; their bills arrive through Bill Importer (Stage 5),
allocation and generation (Stage 7).

**Not entered here:** GL Accounts and Bill Validation Tests belong to Stage 6.

**Record:** the Billing Account ID after each save.

**Check:** `01 Billing accounts`, `01 Service addresses`, `01 Account addresses`,
`01 Account contacts`, `01 Account remit`, `01 Account status`, `01 Account notes`.

## Step 2. Sites and buildings

**Where:** Database Administrator, Nodes.

**Enter:** [02-sites-and-buildings.yaml](02-sites-and-buildings.yaml), the 6 sites (the 4
company sites, the Weather Reference site and the Northlake Toronto Campus) and the 18 buildings.

**What each record holds:** every page the node editor shows for that node, in order: the Level
it is added at (the company's Stage 1 level, such as 2: Facilities), Definitions with the Site or
Building Code, Node Address, Area, Keywords, a building's Status and Notes. A null or empty page is
deliberate and stays empty; those are the empty states under test. Keywords are what is assigned
on that node: Department once on each site, which its buildings list under Inherited Keywords to
verify. Sites have no Status page; every building opens on 2024-01-01 (the Toronto Research Hall on 2026-01-01), the Ridgeline buildings on
the acquisition date, 2024-07-01. Northlake University codes its campus (NLU-MAIN, ADM, SCI and
so on); Cedar Row and the Thermal Plant leave the code empty.

**Added 2026-11-10:** the Northlake Toronto Campus and Toronto Research Hall (Eastern time, Country CANADA,
Region ON, the hall's Area in SqM, a Node Contact on the campus), the Lakeshore Boathouse (Status Open on 2024-01-01 and
Closed on 2025-06-30, Area 3,200 SqFt from 2024-01-01 and 2,400 SqFt from 2025-03-01), and a Node Contact for
Mateo Alvarez on the Ridgeline Wind Site. Node Contact is the page of that name on a node; it takes First Name, Last Name,
Title, Phone and Email, like an Account Contact. The Area page lists two units; the one that is not SqFt is square metres.
The checks cover the new nodes' time zone, address, area and status, but not Node Contact.

**Order inside the editor:** the original nodes, their Node Address, their Area history and their
Department keywords already exist. Open each one and check the values against the file, then add
what is new: the codes, each building's Status, the notes on Weather Reference, Campus Grounds and
Cedar Row Carport and Grounds, and Cedar Row A and Cedar Row B's Meter Type keyword Sub-Meter, which
their apartment and house submeters inherit. Then enter the three Ridgeline nodes: Ridgeline Wind
Site under the Thermal Plant with Department = Thermal Plant Operations, then Ridgeline Turbine
Field and Ridgeline Substation beneath it, each with its Node Address and coordinates, Status and
note, and no floor area.

**Then, back in Stage 1:** the Ridgeline Wind Site's node key now exists (0.5.40), so make the two
Points grants that name it (04-groups.yaml): ntp_wind_ops at level 2 and the shared
eem_ridgeline_research at level 1. The Stage 1 checker covers them. Check that Kai Nakamura sees
the Ridgeline site and nothing else.

**A loose end from before this stage:** two more Location nodes, Sacramento Executive Airport
(38) and Sacramento International Airport (39), already sit under Weather Reference, created
when the two reference stations were modeled as buildings instead of meters. Either delete them
or keep them as the KSAC and KSMF meters' parent in Step 3; both are legal placements and
neither one changes a check.

**Floor area:** every building holds its Area history, but the node's own Area column is empty on
all eleven, and four reports read that column (product finding 36). Record what the reports show
rather than re-entering areas.

**Record:** the node IDs of the three Ridgeline nodes; the others are already known (see
`installed:` in the file).

**Check:** `02 Sites and buildings`, `02 Node addresses`, `02 Department keywords`,
`02 Node keywords`, `02 Floor areas`, `02 Building status`, `02 Node notes`.

## Step 3. Meters

**Where:** Database Administrator, Nodes, Meter nodes under each building (and, for the two
weather stations, under Weather Reference).

**Enter:** [03-meters.yaml](03-meters.yaml), 391 records: 68 utility meters (on a billing
account), 320 owned meters with no billing account (including 248 apartment submeters at Cedar
Row A and B, Cedar Row C's 50 water submeters, three emergency generators, the Central Plant Main
Switchgear and the Ridgeline met mast), and the 3 weather-station meters (KSAC, KSMF and KSUU).

**Order inside the editor:** add the meter node under its building, then on its Definitions page
set Measure Type first (a new meter starts as Activity Level), then Meter Number, the Billing
Account (which brings the meter's Utility Provider and Bill Cycle choices with it) for the 68
meters that have one, then Provider Meter Number and Meter Multiplier. Save, then Keywords and
Status. Every meter opens on its in-service date: 2024-01-01 for most, 2024-07-01 for the thirteen
Ridgeline meters and 2024-08-15 for the Library replacement, whose predecessor closes as Closed - Ex
on 2024-08-14, and the Lakeshore Boathouse gas meter (added 2026-11-10) goes Open on 2024-01-01 and
Removed on 2025-07-15. A meter's Status page writes the SM history that bill validation reads (tests 41
and 42) and lists SM's statuses; saving the backdated Open row replaces the Open row Meter_Save
wrote on the day the meter was entered. Enter a sample by hand; the Stage 2 import sets the rest.

**The Ridgeline Farm Transfer Meter** is a logical billing meter on the Ridgeline transfer
agreement: no channels, no keywords, no provider meter number. Its only point is the farm's
generated-kWh aggregate (Step 6). EEM's Bill Generation prices the points under one meter and
writes one bill per meter and month, so the transfer statement is generated
on this meter in Stage 7; billing the ten pad meters would write ten statements a month, each with
the research credit.

**Before the Ridgeline meters:** on the Keywords page's catalog view, create the keyword type
Generation Source with the attributes Wind and Solar, and add 34.5 kV to Service Voltage (the seed
has 33.6 kV). Generation Source marks the turbines and the three Helios arrays so a report can
leave generation out of use until the product can tell them apart (product finding 44).

**What varies:** seven measure types (Electricity, Potable Water, Natural Gas, Steam, Chilled Water,
Weather and Sensor), multipliers of 40, 10, 3.0367 and 12,000, Meter Type on every utility meter and
owned submeter (inherited at Cedar Row), Service Voltage on the electric services, Service Pressure
on the plant boiler gas, System Component on plant, lighting, laundry and charging loads, Generation
Source on the generation meters, the Library's August 2024 meter exchange recorded as Open and
Closed status, and the Ridgeline meters opened on 2024-07-01. The turbines are Electricity meters on
the Ridgeline transfer agreement with their position tags RWL-WTG-01 to 10 as provider meter
numbers. The met mast carries the Weather measure type without being a station, so it will appear
in the Weather Stations picker (finding 18): never pick it.

**Record:** the Meter ID (MetaWorldID) after each save.

**Check:** `03 Meters`, `03 Meter keywords`, `03 Meter status`, `03 Meter integrity`.

## Step 4. Points

**Where:** Database Administrator, Nodes, Point nodes under each meter (one, the Student Center
Event Count, directly under its building).

**Enter:** [04-points.yaml](04-points.yaml), 475 records, 72 of them Ridgeline's and 73 the handheld routes' (registers on Cedar Row C, the irrigation meters, the generators and the switchgear, whose four demand reads are Analog points with no register). A new Accumulator takes only an Energy or Volume unit or one with a rate unit, so each generator's run hours (in Hour) are an Analog register with its own Analog usage point. Ridgeline has six on each
turbine (Generated kWh, Active Power kW and Possible kW, Nacelle Wind Speed, Rotor Speed and the
four-state Turbine State, all at 10 minutes), six on the met mast in metric units, three on the
interconnection meter (export, station service and reactive kVArh at 15 minutes) and three on KSUU
(temperature with a Degree Days index, wind in knots, dew point). The last two are daily registers
on the two meters whose multiplier would otherwise act on no data: Science Center Electric Lab
Wing (x40, its current-transformer ratio) and Central Plant Boiler Gas (x3.0367, the pressure
factor), the gas one in Hundreds of Cubic Feet - (ccf), the Volume unit, not the Energy unit with
the same label. The Lakeshore Boathouse gas meter's register (added 2026-11-10) reads hundreds of cubic feet and
reports therms, so its Delta Multiplier is 1.037; the Delta box on the Point Definitions page is visible only for
an Accumulator, and it is the one multiplier that is not 1. The workbook and the checks do not carry it, so type it.

A meter with no points is a bill-only utility meter: 37 of the 391 carry only monthly bills, which
reach them in Stage 5 through the billing account, so they need no point.

**Order inside the editor:** add the point, then set Reading Type, Measure Type, Units and Archive
Interval, and Index where the file names one. A new point starts as Analog, Activity Level, Percent,
60 minutes: change every field before the first save. On a new Accumulator (register) point, Units
is the usage unit its generated Delta will carry; EEM stores the register as Reading. Accumulator
and Degree Days points lock these fields after the first save.

**What varies:** all three Reading Types, all seven archive intervals (1, 5, 10, 15, 30, 60 and 1440
minutes), Degree Days in degrees Fahrenheit (KSAC) and degrees Centigrade (KSMF and KSUU), the
Activity Level index, Relative Humidity and Pressure points, the points whose units come from Step
0, and Rotor Speed as an Activity Level point because RPM is seeded under that measure type alone.

**EEM creates for you:** an AccumulatorDelta point behind every Accumulator point, and an HDD and a
CDD point behind each Degree Days index, in (F) or (C) units to match the temperature, for 204
points EEM generates on its own. Capture their IDs on the parent point's own `installed:` block
(`deltaPointId`, or `hddPointId`/`cddPointId`) rather than typing them in as separate records.

**Check:** `04 Points`, `04 Generated children`, `04 Point integrity`.

## Step 5. Weather stations

**Where:** Database Administrator, Nodes, the company node's Definitions tab, Weather Stations
page.

**Enter:** [05-weather-stations.yaml](05-weather-stations.yaml), one record per company: KSAC
Sacramento Executive Airport for the eight campus buildings and the Central Plant, KSMF Sacramento
International Airport for the four Cedar Row buildings, and KSUU Travis Air Force Base for
Ridgeline Turbine Field and Ridgeline Substation. The Ridgeline Met Mast sorts first in the combo
for the Ridgeline nodes because it stands on the site; it is not a station. The two buildings added on 2026-11-10 get none: the Toronto Research Hall is
outside the three stations' reach and the Lakeshore Boathouse is closed.

**Order inside the editor:** do this after Step 3, since the Station combo only lists meters
that already exist with the Weather measure type. It has to be repeated once per company; the
combo is not scoped to the company you are in, and it is sorted by distance, so KSMF has to be
picked deliberately for Cedar Row.

**Record:** nothing generated; save the tab as usual.

**Check:** `05 Weather stations`.

## Step 6. Aggregates

**Where:** two screens. Create Aggregate Point is a context-menu item on the Nodes tree (right
click the site or building the total belongs under); its members are added on the Aggregates
workspace, the navigation item after Nodes.

**Enter:** [06-aggregates.yaml](06-aggregates.yaml), 11 aggregate points: create each one with
the fields in `Create Aggregate Point`, then select it on the Aggregates workspace, open Add
Points, and add every row in `Members` with its Required and Multiplier. The four Ridgeline totals
are the farm's generated kWh, active kW and possible kW at 10 minutes (ten members each) and its
net export at 15 minutes (on the substation). Active and possible power sit on the site; the
generated kWh total sits under the Ridgeline Farm Transfer Meter, because it is what the generated
statement prices: right-click that meter, not the site, to create it. Generated against possible is
the expected-against-actual view the plant asked for; turning possible kW into expected kWh, or
either into a performance ratio, needs a calculated point (product finding 41).

**Recalculate waits for the fix:** an aggregate is registered (PointAggregates_TBL) once it has
members, but Database Administrator's Save writes only the members, so the aggregate stays
unregistered after they are saved: ID 0 in the workspace, no recalculation, no Aggregate page
(product finding 14). Enter the members all the same. They are stored against the aggregate's
point, and the registration call adds the row to an existing aggregate, so nothing entered now is
re-entered once the fix is in.

**Record:** the aggregate point's own ID and its aggregate ID.

**Check:** `06 Aggregates`, `06 Aggregate members`.

## Step 7. Hierarchy filters

**Where:** Database Administrator, Nodes, the tree's filter bar, manage filters (the Hierarchy Filters page).

**Enter:** [07-hierarchy-filters.yaml](07-hierarchy-filters.yaml), one filter (added 2026-11-10): Utility Meters,
the Northlake University meters whose Meter Type keyword is Utility Meter, usable by everyone in the company.

**Order inside the editor:** New filter, then Name, Where (the company, then what the filter returns: Meters),
What (add a Keyword criterion: Meter Type is one of Utility Meter) and Who (Everyone in my company, offered to
administrators). Save, then Count matches: compare the count with the Northlake University meters in
03-meters.yaml that carry Meter Type = Utility Meter.

**Record:** the filter's ID, if the page shows one. There is no check for it; the page's own count is the check.

## Entering by hand or by import

A draft My Import handler (Northlake Stage 2, in the EEMSuite repository under
`Database/EEMSuite/Schemas/Northlake/Stage2Import`) loads Steps 1, 3 and 4 in full from three
workbooks generated from these files by `generators/stage2_workbooks.py`: every account with its
coordinates, Address 2, contact cell, previous account number, Active status date and note; every
meter with its note, keywords and status history, after creating the two keyword values Stage 2 adds
to the catalog; and every point, the Student Center Event Count under its building included. Enter
10 to 20 records of each kind by hand first, to test the screens, then import the rest. The import is
a fix that can be run again at any time: it finds each record by its key (account number, meter number,
point description under its parent), creates what is missing, corrects whatever differs from the
workbook (a mistyped hand entry included) and leaves the rest alone, as well as anything the workbooks do
not list. It writes through the procedures the screens call, but emits no configuration audit. Steps 0,
2, 5 and 6 stay by hand. My Import removes every apostrophe and turns line breaks into spaces (finding
74), so the notes in these files use neither. After changing the YAML, regenerate the workbooks;
`--check` reports a stale one.

## Ownership

A building exists once, in the company that owns its site; nothing is duplicated across
companies. Northlake University owns every campus building and every meter that serves it,
including the chilled-water and steam meters whose provider is the Northlake Thermal Plant. The
Northlake Thermal Plant company holds its own Central Plant (the plant's utility services, its
production and deduct meters, and the provider record the university's thermal accounts bill
against) and the Ridgeline Wind Site. KSUU, like KSAC and KSMF, belongs to the university's
Weather Reference site; university researchers reach Ridgeline through a group grant, never a
copied node.

## Stage 2 is done when

- Seven new units exist with their measure types and conversions, and Kilometers per Hour, Meters
  per Second, Degrees, Kilogram per cubic meter and PSIG carry their new measure types.
- 53 billing accounts exist with their entry type, service type, template, addresses, contact
  (all but one), Active status from 2024-01-01 (2024-07-01 for the two Ridgeline accounts), and the
  renewal and transferred accounts' previous numbers and notes; one account is in Canadian
  dollars and one, the Lakeshore Boathouse's, is inactive from 2025-07-31.
- The 6 sites and 18 buildings carry an address with coordinates, a floor area where one applies,
  a Department keyword, and Cedar Row A, B and C the Meter Type keyword; the two Ridgeline groups hold
  their Points on the Ridgeline Wind Site; the Toronto nodes are in Eastern time and the hall's area is in square
  metres; the Lakeshore Boathouse is closed from 2025-06-30 and has two area rows; the Toronto Campus and the Ridgeline
  Wind Site each have a Node Contact.
- 391 meters exist, 68 of them on a billing account, with the right measure type, multiplier, bill
  cycle and keywords, the Library meters carry their exchange status and the Ridgeline meters open
  on 2024-07-01, and the Boathouse gas meter is Removed from 2025-07-15.
- 475 points a person enters exist, each register with a usage point behind it in the right unit and
  each temperature index with its HDD and CDD children in the right scale, for 679 points in total, the Boathouse register's usage point carrying a Delta Multiplier of 1.037.
- Campus and plant buildings resolve to KSAC, Cedar Row buildings to KSMF and the Ridgeline nodes to
  KSUU.
- 11 aggregate points exist with the right members, each registered for calculation.
- The Utility Meters hierarchy filter exists and counts what the file's meters say it should.

Run `checks.sql` beside this chapter to see each of these as a result set.

## Findings

- **A meter opens on the day it is entered** unless its Status page says otherwise. Meter_Save
  writes an Open row dated the day a meter is first saved into the SM history that bill validation
  reads. The node Status page has written that history since the finding 32 fix, so a backdated
  Open row replaces it; without one, tests 41 and 42 flag the meter's 2024-2025 bills.
- **Billing account columns with no field are blanked by every save:** payment terms, cycle day,
  current balance, the remit and bill-review contacts and the bank account (finding 34).
- **Floor area does not reach the node** (finding 36, to reproduce).
- **PSIG converts exactly like psi** in the seed; whether that is wrong depends on whether the seed
  means gauge or absolute pressure (finding 37, unconfirmed).
- **A register saved with Reading takes the legacy path** and gets an arbitrary Delta unit
  (finding 39; which supported path still reaches it is unconfirmed).
- **The Meter editor has two identifiers**, Meter Number and Provider Meter Number (the serial
  column), and no Sub-Account Number field (findings 16, 40).
- **An aggregate may stay unregistered after its members are saved** (finding 14, to reproduce),
  **the supplied baseline algorithms have no editor**, which using them does not need (finding 15),
  and **the Station combo lists any Weather meter** (finding 18), which the Ridgeline met mast now
  shows in practice.
- **Ridgeline's goals:** no calculated point can turn possible kW into expected kWh or a
  performance ratio (finding 41), and nothing marks generation as generation; the Generation Source
  keyword stands in (finding 44). The NOAA gateway's wspdm field delivers knots (finding 45).
- **My Import rewrites every cell:** it removes apostrophes and turns line breaks into spaces without
  a warning (finding 74), so the import workbooks' notes avoid both.

All are recorded in [product findings](../product-findings.pdf).
