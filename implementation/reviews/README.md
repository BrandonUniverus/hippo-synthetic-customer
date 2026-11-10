# Northlake coverage reviews, November 10, 2026

Five helpers read every stage's YAML, checks and chapter beside the product code it feeds. They read only: no
database was queried and nothing was run. Each item in the stage files is marked READ or INFERRED. Treat a claim
about the product as a lead to confirm, not a fact.

| Review | Stages |
|---|---|
| [stages-1-2-coverage-review.md](stages-1-2-coverage-review.md) | Foundation, hierarchy |
| [stage-3-coverage-review.md](stage-3-coverage-review.md) | Gateways and data |
| [../stage-4-rates/stage-4-coverage-review.md](../stage-4-rates/stage-4-coverage-review.md) | Rates (reworked November 9) |
| [stages-5-6-coverage-review.md](stages-5-6-coverage-review.md) | Bills, financial |
| [stages-7-8-coverage-review.md](stages-7-8-coverage-review.md) | Allocation and tenants, sustainability |
| [stages-9-12-coverage-review.md](stages-9-12-coverage-review.md) | Operations, baseline, third party, scenarios |

## The pattern across every stage

Many rows, few different values. The recipe enters a lot (390 meters, about 1,190 bills, 204 handheld registers) but
most fields hold one value everywhere, and whole editor pages are never opened. The High and Low warning miss in
Stage 3 was one case of something every stage has.

## How deep the checks are

| Stage | Checks | Assert a known value | List rows beside a stated expectation | Other |
|---|---|---|---|---|
| 1 | 699 expected rows | 696 | 0 | 3 existence |
| 2 | 2,522 expected rows | about 2,498 | 0 | 24 |
| 3 | 21 sections | 9 (one cannot fail) | 11 | 1 existence |
| 4 | 14 sections | 0 | 14 | the 26 rate tests carry the values |
| 5 | 15 | 3 | 10 | 2 existence |
| 6 | 8 | 0 | 8 | |
| 7 | 31 | 4 | 23 | 4 existence |
| 8 | 16 | 0 | 14 | 2 existence |
| 9 | 17 | 1 | 12 | 3 do not run |
| 10 | 3 | 0 | 1 | 2 do not compile |
| 11, 12 | none | | | |

Stages 1 and 2 are generated from the YAML and compare every value. From Stage 3 on, most checks print rows for a
person to compare by eye.

## Most serious, by stage

**Stages 1 and 2**
- Provider bill cycles stop at December 2025, so a 2026 bill has no period and Stage 4's new 2026 prices never post.
- Time zone, country and currency never vary. The fiscal year is always a 12-period calendar year.
- All 23 users are people with one sign-in policy; no task, API or service principal exists.
- No closed building, inactive account or removed meter. Node Contact and Hierarchy Filters are never entered.

**Stage 3**
- Data-gap and late-interval flags are off on all 26 nodes, so Stage 9's data-gap task has nothing to process.
- 28 of 34 acceptance cases have no sample file and 25 have no check.
- No node or point is ever disabled. Only 2 of 9 baseline algorithms are used.
- Radio (ERT) handheld reads, BACnet write-back and several collectors have no data.
- The Central Plant main meter has no interval sample, so its tariff has nothing to price.

**Stages 5 and 6**
- Only 8 of 47 bill validation tests are set. About 98% of bills have no known total.
- No AP or GL export format runs, so no export file, log or revert is covered.
- Bill Type is never set, though it drives estimated bills and accruals.
- The recipe disagrees with itself on who enters Cedar Row, Thermal Plant and Helios bills.
- One Stage 6 check reads the wrong flag (it selects checks that failed to run, not open alerts).
- Imported and generated bills use different commodity names, so they will not line up line by line.

**Stages 7 and 8**
- Town Center has no interval data, no bills and no source file, so nothing can allocate and no tenant value is known.
- Tenant meters have no provider, measure type or points, so no rate can be assigned to them. This matters more
  than the three rates Stage 4 moved.
- The Anchor Store reconciliation cannot be reached from the screens as written.
- ENERGY STAR enters only primary use for 13 properties. The weather regression steps do not match the screens.
- Greenhouse gas auto-assignment will count the Cedar Row submeters, Helios and the Ridgeline transfer meter.

**Stages 9 to 12**
- The product moved on: the audit log, task history and built-in task catalog were reworked. Stage 9's 12 standard
  schedules cannot be entered as written, and five checks in Stages 9 and 10 do not compile.
- One alarm names a point that Stage 2 never creates.
- Seven of nine import methods are unused, including Meter Swap, the product's own meter replacement path, which
  Stage 12's replacement scenario does not use.
- Stage 11 has no recipe files. Stage 12 has no checks.
- The report coverage matrix has no expected-value column and is stale.

## What the Stage 4 rework touched elsewhere

- Stage 7 still assigns NL-STEP-Demand, NL-RES-Tiered and NL-MULTI-Commodity. The helper's reading: the two Cedar
  Row ones are not needed and collide with the real tariffs, so drop them; the Town Center ones need tenant rates of
  their own.
- Stage 5 cites VED-TOU-GS-FY25 as a rate; it is now a price date on VED-TOU-GS.
- Stage 12 scenario 4 names NL-STEP-Demand in two lines of explanation.
- Stage 2's Equivalent Runoff Unit is no longer used by anything.
- Stage 7's thermal plant allocation omits the fixed share and the 2026 step that Stage 4 now carries.
- Stages 3, 6, 8, 9 and 10 name no changed rate or schedule. The Ridgeline totals ($129,330.27 and the others) are
  unaffected.

## Not done

Nothing here has been fixed. These files are not committed.
