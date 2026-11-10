# Stage 4 rates: coverage review

November 9, 2026. Review only: nothing in Stage 4 has been changed. Three helpers read the product's rate code,
the Stage 4 recipe and the import/export code. Claims marked (checked) were confirmed against the source or the
YAML afterwards; the rest are the helpers' reading.

## Where Stage 4 stands

- 25 rates, 83 charges, 118 price dates, 6 providers, 9 schedules, 77 assignment rows, 29 rate tests.
- Every charge type appears: Charge Period 45, Fixed By Period 18, Taxes 10, Bill Adj 4, RTP 2, and one each of
  Charge Period Fixed Value, Fixed By Day, Min Value and Max Value.
- 16 rates are the providers' own tariffs. 9 are "NL-" rates written to show a feature (ratchet, options, RTP,
  tiers, currency), some of them assigned to real university meters.

It is wide but thin: most hard features appear once, several cannot run as written, and nothing ever changes.

## Gaps: features the product has and Stage 4 never sets

| Feature | In Stage 4 today | Gap |
|---|---|---|
| Rate options and classes | 1 rate, 4 options, 5 added classes | 4 of the 5 classes have no charge; no meter is bound to an option, so defaults and overrides never price |
| Min and Max classes per option | not varied | "pick one of" versus "pick several" never tested |
| Significance | All Hour 75, On Peak 4, Off Peak 4 (checked) | Mid Peak, Super On Peak, Super Off Peak and Other never used; On Peak and Super On Peak are the two that skip holidays |
| Seasons | 5, all By Month Day (checked) | no By Day of Week season |
| Time of use | 5 weekday windows | no weekend window, no three-period day (on, mid, off) |
| Holidays | 1 set, 2024 and 2025 only | nothing after 2025; no second set; no holiday inside an on-peak window with a known result |
| Tiers | 4 charges | only one stepped (Charge Period Fixed Value) case |
| Ratchet | 1 | Test Rates cannot run a ratchet, so it needs generated bills with 12 months behind them; Previous % and Bill cycle are set but no engine procedure reads them (helper) |
| Load factor | 1 block | same: only provable with generated bills |
| Interval and aggregate rules | Summing nearly everywhere, Averaging once | Min and Max never used |
| Prorate by date off | never | a price change mid-period billed as two lines |
| User-defined charge (per-meter prices) | never | also no desktop screen for the prices (helper): likely a product finding |
| Excluded points | never | a meter with one point left out of its rate |
| Scripts | 4 scripts on 5 charges (1 pre, 4 post) | no script that adds or removes a line; nothing that shows the limit of what a script can do |
| RTP | 2 charges, 1 with price ranges | the price point is never created, so NL-RTP-Index cannot price |
| Commodity mapping | Ridgeline only | usage and charge commodities unmapped on the other 24 rates; Exclude never used |
| Currency | 1 Canadian rate | never assigned to a meter |
| Rate tests | 29 | 17 say "record from run" (checked); only the rest state a total worked out beforehand |
| Rate import and export | none | not in any stage |
| Changes over time | 13 charges have a second price date | no rate retired, no assignment ended, no schedule changed |

## Things in the recipe that are wrong today

- Stage 7 assigns "NL-MULTI-Commodity", which Stage 4 never creates (checked: 06-tenant-bill-generation.yaml).
- Every Stage 4 file names data/eem/northlake-rates-v1.yaml as its source; that file is gone.
- Never assigned to a meter in Stage 4: VED-TOU-PRI, SGU-GN-1, NL-OPTIONS-Phase, NL-MULTI-Currency.
- Stormwater is on 9 water meters here and 6 accounts in the scenario. The Central Plant makeup water meter has water
  only here, and water, sewer and stormwater in Stage 5.
- 06-rate-assignments.yaml mentions a second assignment row for the FY2025 change that does not exist.
- Findings 7, 66 and 69 are cited in stage text but are not rows in the findings register.

## What a rate change costs elsewhere

Rate values are typed by hand in four places that happen to agree: 05-rates.yaml, data/providers/*.yaml, the
tariff sheets, and data/bills/*.yaml (which Stage 5 repeats). Nothing computes one from another.

- services/sources/billing.py hard-codes each provider's charge components and the 1.5% and 5% percentages.
- generators/render_bills.py has a colour per provider and fails on an unknown one.
- Stages 5, 6, 8, 9 and 10 carry fixed dollar totals derived from the rates.
- The Docker sources keep their own time-of-use windows and holidays, which already differ from Stage 4's.

So a harder tariff on one of the real providers means new bills, new PDFs and new totals in five stages.

## Decision: both (Brandon, November 9, 2026)

The real providers go wide and reasonably deep. A separate provider carries the full, complicated engine.

### Tier 1. The real providers, entered the way their own tariffs read

The providers' tariff data (data/providers) is already richer than what Stage 4 types in, and the sample bills
already follow the tariff data. So the depth is mostly there to be entered, and it costs little downstream.

| Provider | What its tariff says | What Stage 4 enters today | Entering it properly exercises |
|---|---|---|---|
| Valley Electric, VED-TOU-GS and VED-TOU-PRI | three periods: peak, part-peak, off-peak; part-peak 8-12 and 18-22 in summer, 8-22 in winter | two periods; part-peak folded into off-peak, which over-prices the Central Plant test by $39,743.08 | Mid Peak, a three-period day, weekends as off-peak, holidays in a peak window |
| Valley Electric bills | a public purpose line and a utility users tax | on VED-TOU-PRI only | Bill Adj and Taxes with member charges on the everyday rate |
| Valley Electric, VED-GEN-IC | reactive power beyond 0.95 power factor, $0.0042 per kVArh | left out | a charge on a second quantity; a script or minimum if the engine needs one |
| Valley Electric, VED-AL-1 | $14.60 a fixture | one flat $613.20 | a per-meter quantity (user-defined charge), or a finding if no screen can enter it |
| River City, RCU-W-TIER, RCU-IRR, RCU-FIRE | meter charge by size: 1, 2, 3, 4 inch; fire line 4, 6, 8 inch | the 2-inch and 4-inch prices typed as the only charge | rate options with a default class, and meters bound to a different size |
| River City, RCU-SW-ERU | $11.20 an ERU | one flat $44.80 | same per-meter quantity case as lighting |
| Sierra Gas, SGU-GN-1 and SGU-GL-1 | seasonal commodity, transport, public purpose surcharge, utility users tax | the surcharge and tax are only on NL-GAS-FuelAdj; SGU-GN-1 is on no meter | the real gas rate on its nine meters |
| Helios, HOS-PPA-2024 | 2% a year escalator | two price dates, and 0.121 where the bills use 0.12138 | yearly price dates that agree with the bills |
| Thermal Plant | consumption, demand, a fixed O&M allocation | consumption and demand | a fixed charge beside usage on an internal rate |
| All six | | commodity mapping on Ridgeline only | usage and charge commodities on every rate |

Also in Tier 1: holidays through 2027; VED-TOU-PRI assigned to the Central Plant; every rate test given a total
worked out beforehand, taken from the provider's own sample bill where one exists. A generated bill that matches the
imported one to the cent is the strongest check Northlake can make.

### Tier 2. Northlake Rate Lab, a seventh provider

Its own lab meters, no imported bills, no PDFs. Proved by hand-computed rate tests and by generated bills.

- Every significance, including Super On Peak and Super Off Peak; a By Day of Week season; a second holiday set.
- Ratchet and load factor on a meter with a year of history, so generated bills show them.
- RTP with its price point created and a price range that actually clips.
- Min Value and Max Value that fire and that do not; Min and Max interval and aggregate rules.
- Prorate by date on and off across a price change.
- Options: one-of, several-of and none-of, with defaults, and meters overriding them.
- Per-meter prices, excluded points, a second currency on an assigned meter.
- Scripts: the simple "add 20% afterwards", one that adds a line, one that removes a line, and one that tries to
  be a whole rate, to find where a script stops being reasonable.
- Export and import of the whole provider.

### Open: the nine NL- rates

They sit under the real providers today, several on real university meters in place of the real tariff (the nine
gas meters carry NL-GAS-FuelAdj, not SGU-GN-1). With Tier 1 in place the real meters should carry the real tariffs,
and the NL- rates belong in the lab. That moves nine rates and their assignments, and touches Stage 7, which bills
tenants on NL-STEP-Demand and NL-RES-Tiered.

### Order

1. Tier 1, because Stage 4 is the next stage to be entered.
2. The Rate Lab.
3. The Stage 12 rate scenarios below.

## Rework progress (November 9, 2026)

Done, not committed:

- 01-holidays: 2024 to 2027.
- 03-time-of-use and 04-schedules: Valley Electric's three periods; eight schedules.
- 05-rates: the 16 real tariffs as their tariffs and bills read (60 charges, 111 price dates).
- 06-rate-assignments: 56 meters, 74 rows, every real meter on its provider's tariff.
- 08-rate-lab: the nine NL- rates and four scripts, moved unchanged as starting material. Not enterable.

Still to do: 07-rate-tests, checks.sql, the chapter and its PDF, the Rate Lab itself, Stage 7's references to moved
rates, the Stage 12 scenarios. Until then Stage 4 must not be entered: the tests, checks and chapter describe the
old rates.

Found on the way:

- Significance: On Peak and Super On Peak skip holidays; every other significance counts the whole holiday. A
  three-period tariff entered with Mid Peak bills holidays twice. Entered here as Super On Peak, On Peak and Off
  Peak. To be looked at with Brandon later.
- The provider's gas bills price a whole bill at the season of its end date; the engine prices each day.
- The water meters carry water, sewer and stormwater as three rows, and the engine prices one rate per meter.
- The old recipe's three new scripts use variables the engine does not supply.
- The Stage 4 folder is not tracked in git. Copies of the files as they were are in this session's scratchpad.

## Scenarios for Stage 12 (rates on a running system)

1. A price change from a date: add a price date; a bill across the date prorates. Repeat with prorate off.
2. Retire one charge and add another mid-year (end date on the old one).
3. Move a meter to a new rate on a date, with a bill that straddles it. The helper reads the engine as billing the
   whole bill on the newer rate; the scenario would settle it.
4. On-peak hours change from a date. Schedules have no dates, so an edit reprices the past. The honest route is a
   new time of use, schedule and charge. This is a product finding either way.
5. Add 2026 and 2027 holidays; add a holiday inside an on-peak window and check both kinds of charge.
6. Switch a meter's option class. The binding has no date, so history changes: finding.
7. Regenerate after a rate change. Nothing marks generated bills when a rate is edited (Auto Regen reacts to new
   interval data only), so the scenario is: change the price, regenerate by hand, compare.
8. Export the lab provider and import it back: nothing should change. Then import it into an empty database.
9. Try to delete a rate that is in use.

## Likely product findings (not yet recorded)

- Import and export: only rates, charges, providers and schedules carry a GUID (checked); classes, options, seasons,
  time of use and holiday sets match by name. There is no transaction, so a failed import is partial. A rate matched
  by name takes the file's GUID, which the save may reject. The preview shows every charge as "Update". It is tested
  only on mocks.
- Schedules, seasons and time of use are not dated.
- Option class bindings are not dated.
- A rate edit does not flag generated bills.
- Ratchet Previous % and Bill cycle, the Shared flag, and the Transmission, Distribution and Commodity toggles are
  stored and shown, but nothing in the engine SQL reads them.
- An assignment's End Date is accepted but not stored.
- Per-meter prices for user-defined charges have no screen.

## Not verified

- The helpers read code and YAML only. No database was queried and nothing was run.
- Whether Bill Adj and Taxes take a fraction or a percent.
- How a By Day of Week season behaves across a year end.
- Whether anything outside the SQL uses the "nothing reads them" fields.

The three working inventories (product features, recipe inventory, import/export and changes) are in this session's
scratchpad, not in the repository. They can be added beside this file.
