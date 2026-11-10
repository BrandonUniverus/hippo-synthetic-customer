---
title: Stage 12. Scenarios
subtitle: Things that happen once the system is running, starting with the handheld routes
status: Four handheld scenarios written; enter after Stage 9's first rounds (scenario 4 also after Stage 7)
---

# Stage 12. Scenarios

Stages 1 to 11 build Northlake and show that it works. Stage 12 is what happens next, while it is running: a
meter fails and is replaced, a display changes units, a route that was set up badly has to be fixed. Each
scenario starts from a working configuration, makes one real-world change through the product, and checks
that nothing in the history breaks. Scenarios run after Stage 9's first handheld rounds, because they change
configuration those rounds depend on.

The first four are handheld scenarios. They use the routes Stage 3 sets up
([05-handheld-routes.yaml](../stage-3-gateways-and-data/05-handheld-routes.yaml)) and the Handheld Meter Setup
page. Scenario 4 also bills a Town Center tenant, so it needs Stage 7. Later scenarios (the VEE catalog's register reset, rollover and replacement case, M08 in the
[VEE scenario research](../stage-3-gateways-and-data/Northlake-VEE-Scenario-Research.pdf), p3) join this stage
when their parts exist.

## Scenario 1. Replace a handheld meter

**Enter:** [01-handheld-meter-replacement.yaml](01-handheld-meter-replacement.yaml).

**What happens:** Cedar Row A unit 214's water meter stops registering, and maintenance sets a new meter on
October 15, 2024.

**What to do:** keep the old meter and its history, record its final read (1388 kgal) and close it
(Closed - Ex). Add the new meter as a new meter node with its own register point, and put it in the old one's
place on route CRAWTR (sequence 350). Give it its own starting reading, 3 kgal on October 15.

**Why not reuse the old register:** EEM has no replacement action for a handheld meter. A lower register on
the same point is a rollover, or a reading held as implausible. A new meter keeps both histories true, and the
unit's usage is the two meters together.

**Check:** the November read books 6 kgal on the new meter (9 - 3), with no rollover and no held reading, and
the route file lists the replacement at sequence 350.

## Scenario 2. A register moves from kW to MW

**Enter:** [02-switchgear-kw-to-mw.yaml](02-switchgear-kw-to-mw.yaml).

**What happens:** after a second chiller train, the Central Plant switchgear meter's demand displays are
reprogrammed on March 1, 2025 to show megawatts with three decimals.

**What to do:** keep the kW points. Add the read type Northlake Keyed Demand MW 10D3DC. On the KW and KWP
registers, change the prompt to MW and MWP, the read type to the MW one and the meter constant to 1000.

**Why:** moving the registers to new MW points would split every history, report, goal and alarm at the change.
The constant keeps one unit in the history. The renamed prompts keep their previous prompt, so a round already on
the handheld in kW still lands.

**Check:** February's kW read (1294.60) and March's MW read (1.312, stored 1312) sit in one kW history with no
factor-of-1000 step.

## Scenario 3. Fix a badly built route with bulk edit

**Enter:** [03-fix-cedar-row-c-route.yaml](03-fix-cedar-row-c-route.yaml) and
[03-cedar-row-c-walking-order.csv](03-cedar-row-c-walking-order.csv).

**What happens:** the reader reports the problems with Cedar Row C as its installer keyed it (Stage 3 Step 5):

- the route zig-zags between the two meter banks;
- unit 412 never reaches the handheld, because it is on cycle 20;
- the laundry meter is missing, because it is disabled;
- every meter text says Cedar Row B.

**What to do:** on Handheld Meter Setup:

- set unit 412's cycle to 02;
- enable the laundry meter;
- bulk edit all 50 meter texts in one step;
- paste the two-column walking order (Meter # and Sequence), so the route starts in the laundry room and walks
  each bank stack by stack.

**Check:** cycle 02 CRCWTR has all 50 meters, enabled, at 10 to 500 in walking order. The route file has no cycle
20. Nothing else changed: read types, prompts, points and history stay as they were.

The two meter batches stay as they are: ccf upstairs and gallons downstairs are the meters on the wall, and the
unit system converts them when a report sums the building.

## Scenario 4. A tenant's demand is read the day after its energy

**Enter:** [04-demand-read-after-energy.yaml](04-demand-read-after-energy.yaml).

**What happens:** Town Center bills a coffee kiosk in Market Hall from its own electric meter, read by hand each
month: the kWh dial and the maximum demand display. Some months the reader keys the demand the next morning.

**What to do:** add the kiosk meter (Market Hall Kiosk K1) with a Register Reading accumulator and a Max Demand kW
point. Give it a billing account and a flat tenant rate (TC-TENANT-GS). Bill it by Meter Reads (MV), Auto w/ Auto
Regen. Put it on route TCTEN with a KWH register and a KW demand register, then return seven monthly rounds:

- May: both registers on the same visit.
- June: the demand read the next morning.
- July: both on the same visit.
- Turn on Use Reading TimeStamp on the Northlake MVRS Gas Upload schedule.
- August: the demand read the next morning again.
- September: the demand read the next morning and returned in its own upload.
- October: the demand returned before its energy read.
- November: both on the same visit. Then turn the setting off again.

**Why it happens:** a Meter Reads bill takes its dates from the energy registers only, from the day after the
previous energy read through this one's date. A demand keyed on a later day belongs to the next bill. That bill
bills the higher of two demands, and this one has none. Use Reading TimeStamp moves a meter's values onto its
energy read's time. A demand returned on its own moves only when that energy read is newer than the meter's last
demand. September's round needs the gateway fix of November 9, 2026.

**Check:** seven bills. June has no demand and July bills June's 17.80 kW. August and September keep their own
demand. October has none (its demand came back first) and November bills it. The kWh add up to the register's
19,780.

## Stage 12 is done when

- The replacement meter for Cedar Row A unit 214 is on CRAWTR at sequence 350 with its own starting reading,
  the old meter is Closed - Ex with its history intact, and the first read after the swap books no rollover.
- The switchgear's KW and KWP registers read MW with constant 1000, and their kW points show one continuous
  history across March 1, 2025.
- Cedar Row C's route is in walking order on cycle 02 with all 50 meters enabled and the right meter text.
- Market Hall Kiosk K1 has seven Meter Reads bills from May to November 2025 with the totals in scenario 4's verify
  list, and the Northlake MVRS Gas Upload schedule's Use Reading TimeStamp is back to what Stage 3 expects.

Run `checks.sql` beside this chapter against the instance database after the scenarios. It has one asserting
check for each verify item (13 in all) and for the step expectations the scenario files state, each with Expected,
Actual and PASS or FAIL, using only the values the YAML gives: scenario 1's 1388, 3 and 6 kgal, its route (CRAWTR,
61 meters, sequence 350) and statuses; scenario 2's read type, prompts, constants and the 1294.60 and 1312 reads;
scenario 3's 50 meters in walking order (the CSV is embedded in the check), the missing cycle 20 and the meter text;
scenario 4's seven bills, 19,780 kWh and seven demand values. Before a scenario is entered its rows read missing and
FAIL, which is the expected state.
