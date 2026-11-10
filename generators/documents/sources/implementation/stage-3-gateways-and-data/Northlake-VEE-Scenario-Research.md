---
title: Northlake VEE scenario research
subtitle: Controlled meter faults, realistic operations, late readings and measurable correction outcomes
department: Energy Hippo implementation
document_type: Research and implementation proposal
document_label: Northlake | VEE scenario research
date: November 4, 2026
prepared_by: Energy Hippo implementation team
status: Research only; scenarios and product changes proposed, not enabled
audience: Northlake implementation and EnergyHippo engineering
---

# Northlake VEE scenario research

## Recommended direction

Add a versioned scenario layer to the existing Northlake source bundle. Keep the underlying physical truth, alter selected measurements or their delivery, then send those artifacts through the real collectors and intake. A separate scorer should compare VEE findings, estimates and approved changes with private expected outcomes.

Populate the system with both faulty measurements and unusual but valid operation. A real leak, heatwave or equipment outage can merit an operational alert while its readings remain correct. VEE must learn when to investigate, when to propose a replacement and when to leave the measurement intact. Random spikes alone cannot teach those distinctions.

The catalog retains its **28 scenario families** and first pack of **12 families with paired valid controls**. Archive/manual reviews added 18 extensions on November 2 and **10 more, S11-S20, on November 4**, for **28 detailed extensions** refining those families. Start with normalized interval consumption and supervised corrections; registers and broader workflows follow. No running feeds, source facts, database rows or schedules are changed.

## What Northlake already supplies

| Existing capability | What it gives the scenario work |
| --- | --- |
| [Source bundle](../../services/sources/README.md) | Deterministic seed 104729, native interval generation, source lifetimes, persisted cutoffs, immutable artifacts, HTTP/shared-directory delivery and real-parser bridges. |
| [AcquiSuite fixtures](../../documents/intake-package/sample-data/acquisuite/expected-results.json) | A complete day, eight withheld intervals and their exact backfill. Useful for transport/recovery acceptance; not a general scenario scheduler. Preserve their start-stamped edge case. |
| [Versioned assumptions](../../services/sources/assumptions.json) | Existing WTG-07 outage, Helios missing telemetry, register baselines, physical allocations and explicit seasonal assumptions. |
| [Canonical model](../../services/sources/model.py) and [physical relationships](../../services/sources/physical.py) | A basis for energy/register/parent-child truth and realistic operational changes. Published bill anchors remain acceptance constraints. |
| [VEE delivery research](../../../univerus/energyhippo/src/Documentation/Research/VEE-Customer-Delivery-Research-2026-10-31.md) | Confirmed first product scope: interval validation, gap estimates and approved corrections. Predictive mathematics stays reusable; VEE owns measurement policy and publication. |

<!-- pagebreak -->

## Scenario catalog A: delivery and time

All durations and error magnitudes below are proposed test parameters, not production thresholds. Expand each family across seasons, load levels and supported formats. Keep the cause, observable evidence and expected action separate.

| ID and family | Injection and Northlake example | Expected behavior and valid control |
| --- | --- | --- |
| D01. Isolated missing interval | Withhold one 15-minute Student Center reading, then several nonadjacent readings. Also omit one hourly Cedar reading. | Detect after the feed's deadline, not immediately at interval close. No zero substitution. Control: a reading arriving within its normal grace period. |
| D02. Block and node outage | Withhold 2 hours, a day and several days; cover midnight and a bill boundary. A whole AcquiSuite node can disappear while another continues. | One understandable outage episode with affected channels; distinguish source silence from producer failure. Control: an inactive meter has no expected readings. |
| D03. Partial device failure | Drop only kW while Student Center kWh continues, or one turbine channel while state/wind remain available. | Identify missing sibling evidence and limit the fault scope. Control: channels with genuinely different native cadences. |
| D04. Replay and overlap | Deliver the same bytes twice, equivalent rows in a differently named file, and overlapping chunks. Then introduce one conflicting value at the same timestamp. | Harmless duplicates do not change totals. Conflicting revisions require precedence/review. Control: adjacent nonoverlapping files. |
| D05. Late and out-of-order actuals | Release a withheld block after 2 hours or 2 days, reverse daily file order and release a revision after a month closes. | Reopen/reassess the affected window without duplicate readings or repeated unrelated alerts. Control: routine delivery jitter. |
| D06. Clock and stamp errors | Shift a stream by one interval or one hour; encode local time as UTC; introduce gradual clock drift. Reuse the legacy start/end AcquiSuite edge case separately. | Detect misalignment using cadence and related evidence; do not silently guess a correction. Control: Ridgeline's documented fixed-PST convention. |
| D07. Calendar boundaries | Test leap day, spring 23-hour and autumn 25-hour days; remove only the first or only the second occurrence of a repeated-hour interval. | Use physical UTC identity. A 15-minute Pacific day has 92, 96 or 100 intervals as applicable. Preserve both repeated instants. |
| D08. Contract and lifecycle faults | Wrong interval length, unit metadata, unknown channel, readings before acquisition/after retirement; truncated, malformed or non-finite records. | Parser/intake rejects unusable representation with evidence. VEE assesses resulting missing coverage separately. Control: valid new-meter and cadence-change boundaries. |

Use D08 as an explicit parser/intake suite. A rejected file is not a successful VEE anomaly detection. Existing encoders deliberately reject non-finite values and unordered rows, so malformed-byte cases need a separate post-encoding fixture step rather than weakened normal encoders.

<!-- pagebreak -->

## Scenario catalog B: measurements and real operations

| ID and family | Injection and Northlake example | Expected behavior and valid control |
| --- | --- | --- |
| M01. Spike or dropout | Alter one value or a short burst by 2x, 10x or 100x; include a near-threshold case and clipping at a device limit. | Distinguish physical impossibility from merely unusual demand. Control: a plausible equipment start or EV charging burst. |
| M02. Stuck value or repeated day | Freeze a sensor for 2 hours or 2 days; replay yesterday's shape with today's timestamps. Include coarse but legitimate quantization. | Detect loss of variation or suspicious repetition where the process should vary. Control: steady baseload and low-resolution meters. |
| M03. False zero versus real outage | Force reported zero while true load continues. Pair it with a genuine electrical outage and a nighttime solar zero. | Faulty zero can merit replacement. Real outage/nighttime zero must remain zero; operational alerts are separate. Do not infer outage solely from zero values. |
| M04. Scale, offset and multiplier | Miss or double a multiplier, confuse W/kW or Wh/kWh, add a constant bias, or apply a changed CT ratio on the wrong date. | Compare effective configuration and related totals. Control: a correctly applied multiplier change. Never multiply both source and consumer blindly. |
| M05. Gradual drift | Ramp a sensor bias from 0 to 5%, then to 15% across weeks, with varying noise. | Detect persistent divergence without learning the fault into the baseline. Control: genuine seasonal drift or changing occupancy. |
| M06. Swapped or misbound channels | Swap two plausible Cedar apartment streams or map one recorder's column to the wrong point. | Detect where independent relationships identify the error. If two streams are indistinguishable, label diagnosis inconclusive. Control: correlated genuine loads. |
| M07. Direction and quantity confusion | Reverse import/export, make an import-only register decrease, or submit kW as interval kWh. | Apply channel-specific sign and unit rules, including duration. Control: valid net export. Northlake's separate import/export channels retain their declared conventions. |
| M08. Register reset, rollover and replacement | Reset an accumulator, roll over a declared modulus, replace a meter at a known boundary, then omit that configuration in a faulty variant. | Split at effective boundaries; do not manufacture enormous negative/positive consumption. Recalculate both neighboring deltas. Control: correctly documented replacement. |
| M09. Balance disagreement | Make a Cedar child exceed its master's accounting envelope; alter generation/export/station service; disagree with a trusted register. | Compare aligned quantities, periods and loss allowances. Control: incomplete submeter coverage, legitimate losses and registers that arrive later. |
| M10. Valid operational anomaly | Add a water leak, after-hours HVAC load, exam-week occupancy, heatwave, EV installation or permanent process-load change. Reuse WTG-07's physical outage. | Retain valid measurements; optionally raise an operational finding. Relearning a new normal requires a policy decision. Control: return to normal and an announced shutdown. |

For a physical event, change the truth model first and recompute dependent registers, parents and bills. For a measurement fault, keep physical truth intact and corrupt only the declared measurement path. A provider bill produced from the same faulty meter is not an independent witness; record the shared lineage.

<!-- pagebreak -->

## Scenario catalog C: estimation, review and correction

| ID and family | Sequence to exercise | Expected behavior |
| --- | --- | --- |
| E01. Short versus long estimation | Remove one interval with valid neighbors; repeat over a load transition, overnight, a holiday and several days. | Short interpolation, comparable-day and predictive proposals have explicit eligibility. A method producing a number is not sufficient approval. |
| E02. Register-constrained gap | Provide trusted period consumption of 1,000 kWh, with 760 kWh already observed and gaps in several places. | Allocate only the remaining 240 kWh. Preserve accepted observations; satisfy capacity and nonnegative constraints. If observations exceed the trusted total, flag a conflict instead of forcing a negative fill. |
| E03. Cold start and poor peers | New acquisition, recent replacement, insufficient history or a candidate peer with incompatible occupancy/commodity. | Report insufficient support or use only an approved alternate. Control: a genuinely comparable peer with independently available evidence. |
| E04. No safe estimate | Long outage, missing register, simultaneous peer failure, unreliable weather, or a major operating change inside the gap. | Abstain or request review. Record the unresolved interval and reason. An honest abstention is a correct outcome. |
| E05. Contaminated history | Put known bad readings, previous estimates and reviewed-invalid periods into the history feed; then change a review decision. | Exclude or reinstate history according to versioned policy. Do not use the model's own estimates as independent measured training targets. |
| E06. Evidence from the future | Make a useful neighbor, register, bill or weather observation arrive after the evaluation time. | The first decision cannot use it. A later evaluation may improve. Offline retrospective interpolation and real-time estimation are separately scored. |
| E07. Actual after estimate | Deliver valid actuals after an approved estimate, including one numerically identical value and a partial block. | Replace only eligible estimates, preserve origin/revision history and retain unresolved portions. Equal value still requires a quality transition. |
| E08. Conflicting and protected edits | Send a lower-quality later read, a second correction and a late actual over an operator-protected edit. | Newer does not automatically win. Preserve protection and reasons; unlock/reprocess is an explicit action. |
| E09. Stale proposal and concurrent change | While a proposal awaits approval, deliver a new actual or change meter configuration/policy; approve the old proposal afterward. | Version checks reject or recompute the stale proposal. No overwrite of a newer accepted state. |
| E10. Recovery and dependent effects | Stop the scenario runner between releases; replay after restart; re-evaluate an approved correction affecting deltas, parent totals and bill periods. | No lost/duplicate actions, endless self-trigger loops or stale downstream results. Later hold-enforcement tests must prove the actual billing/export consumers. |

Initial expected dispositions should be **accept**, **flag for review**, **reject unusable input**, **propose estimate**, **abstain**, **supersede eligible estimate** or **retain protected value**. Ground truth identifies the actual cause; expected disposition also accounts for what evidence the system could know at that time.

<!-- pagebreak -->

## How to implement this in the source bundle

Use four distinct records per run: **physical truth**, **source observations**, **delivery events**, and **private expected outcomes**. A single boolean called `bad` cannot express a correct reading during an operational incident or a safe estimate awaiting approval.

| Extension point | Proposed implementation |
| --- | --- |
| [Model and relationships](../../services/sources/model.py) | Optional physical-event overlay before quantity/register/bill derivation. Reserve unanchored windows or a separate scenario branch of the model; never rewrite the 24 original PDFs or source facts. |
| [Gateway encoders](../../services/sources/gateways.py) | A measurement-view adapter supplies altered rows to existing format encoders. Generate parser expectations from observed bytes; score correctness against separate truth. Keep MDEF/MV9 chunks self-contained. |
| [Generation](../../services/sources/generation.py) | Add versioned scenario identity and an event calendar. Seed by run/scenario/channel/time; evaluate overlapping-event precedence explicitly and reject ambiguous combinations. |
| [Publication and delivery](../../services/sources/runtime.py) | Add a persistent release queue distinct from generation progress. A finished artifact can be withheld until `available_at`; never put future withheld artifacts in the consumer catalog. |
| [Delivery receipts](../../services/sources/delivery.py) | Reuse atomic publication and receipt semantics. A late correction is a new source revision/event with a distinct immutable artifact, not an overwrite. Explicit duplicate tests record their replay intent. |
| Scoring adapter, new work | Consume actual parsed/intake/VEE results through supported read paths and compare them with private truth. Do not mutate archives directly to manufacture a passing result. |

The current source fingerprint changes when generator code changes. Build a new version and use a separate scenario state volume; keep the existing accepted release and active source volume intact. Keep one active feed transport per target. Scenario and ordinary delivery must not both feed the same points/timestamps during an acceptance run.

The scenario manifest should record run/scenario version, baseline release/hash, seed, channel and meter-configuration identity, interval UTC boundaries, quantity/unit, physical effect, observed transformation, release times, source revision/quality, private truth and expected disposition. It should also record the evidence required for a decision and its availability time. Put truth and labels outside the HTTP root and outside the detector's feed.

Transport catalogs may expose counts and totals of the bytes actually delivered. They must not expose clean hidden totals, fault names, answer labels or future correction values. Use opaque artifact names for blind scoring. Direct access to the baseline catalog, bills or sibling channels must follow the same declared evidence policy.

Do not weaken ordinary file validation to create malformed cases. Use a separate explicitly selected byte-corruption fixture step. Native source quality flags can be emitted only where the format/parser supports them; otherwise mark the case as requiring an intake adapter. An invented CSV column is not proof of end-to-end provenance.

No new protocol container is needed for the first file-based pack. A later BACnet/Modbus simulator can use the same event/truth contract when those packages exist. Suggested future CLI verbs are `scenario build`, `scenario play` and `scenario score`; these commands do not exist today.

<!-- pagebreak -->

## A concrete pilot and an event timeline

Start with five file-source groups rather than corrupting the whole campus; add monthly register evidence as its contract becomes available. Exact point IDs are resolved from the installed configuration at acceptance time; scenario truth uses stable channel identities.

| Source group | Existing anchors for the pilot |
| --- | --- |
| Student Center and Lakeview, AcquiSuite | `ch_ved_student_center_kwh_15m`, `ch_ved_student_center_kw_15m`; matching Lakeview channels provide an unaffected neighboring node. |
| Central Plant, MDEF | `ch_ved_central_plant_kwh_15m` and `ch_ved_central_plant_kw_15m` exercise process load, capacity and quantity consistency. |
| Science solar, MV9 | `ch_hos_science_center_gen_kwh_15m`, export and irradiance channels exercise daylight, weather/context and the existing telemetry gap. |
| Cedar housing, FIXEDNETWORKS/FIG | Master and apartment/house channels exercise hourly delivery, incomplete evidence and allocation balance. Use the bindings in the published source contract. |
| Ridgeline, SCADA FIG | WTG-07's 10-minute kWh, kW, possible kW, wind, rotor and state channels distinguish outage from bad telemetry. Fixed-PST source handling stays intact. |
| Monthly/register evidence, later | Existing gas/water reads and meter-replacement facts support E02/M08 once the corresponding VEE ingestion contract is present. A PDF is not itself a structured interval input. |

Example new AcquiSuite scenario, on an unanchored date: retain the eight actual interval-end readings covering 12:00-14:00 Pacific in private truth and withhold them from delivery. Set the demonstration lateness grace to 30 minutes, explicitly as a test configuration. Other readings continue arriving.

| Decision time | Source event | Expected observation |
| --- | --- | --- |
| Before each interval's deadline | Eight rows remain withheld | No premature missing-data failure. Other channels/nodes remain available. |
| After the deadline | Missing block is now actionable | Open one gap episode with the eight physical UTC intervals as they become overdue. |
| At a configured evaluation time | Enough eligible evidence is available | Propose a fill, or abstain with a reason. Only a supervised action publishes the estimate. |
| Next day at 09:00 Pacific | Release the actual rows as a new immutable file | Re-evaluate eligible estimates, including a same-value quality transition. Retain the estimate history. |
| After correction | Explicitly replay that delivery | No duplicate energy, revisions or new unrelated incident. |

Measurement time and arrival time must stay separate. For a fast historical replay, both the source event player and VEE evaluator need a coordinated logical clock and as-of evidence. Accelerating source deliveries alone does not test real-time deadlines in an EEM process using wall time. If no evaluator clock is available, classify that run as batch retrospective acceptance and prove deadlines separately with a real-time run. Do not change the operating-system clock.

Keep the original January 2024 AcquiSuite fixtures as their own start-stamped acceptance case. The new VEE pilot should use the normal interval-end convention so its first lessons are about missing data and replacement, without the old timestamp mismatch masking the result.

<!-- pagebreak -->

## Teaching and scoring without leaking the answers

Use the clean, eligible measurement history to fit an expected-load model. Use labeled fault/control scenarios to tune rules, compare models and teach the review workflow. Supervised classification can be a later consumer of labels; it is not required before useful VEE. Keep VEE approvals outside the generic predictive engine.

Proposed split: 2024 for development/history, 2025 for calibration and 2026 for a locked chronological evaluation. A held-out 2026 episode may use earlier eligible observations that would genuinely have been available, but not its hidden truth or future corrections. Hold out some meters, event severities and event combinations as well; do not put variants of the same fault episode in both training and evaluation. December 2023 supports initial history, not a fabricated abundance of prior seasons.

Northlake already has built-in outages and estimates, so a year is not automatically clean training data. Eligibility is per interval and source revision, with reviewer exclusions retained. Passing validation also does not mean an exceptional operational period is representative training history.

| Measure | What to record |
| --- | --- |
| Detection quality | Precision/recall by fault family and severity, missed episodes, false findings per 1,000 meter-days and detection latency from the configured deadline. Score episode and interval coverage separately. |
| Correct discrimination | Whether valid outages, solar zeros, exports and real load changes were retained; operational alerts and data-quality faults have different labels. |
| Estimate quality | MAE and bias in native units, integrated energy error, peak-demand and TOU/bill impact, interval uncertainty coverage and abstention rate. Avoid percentage error divided by zero/near-zero load. |
| Physical consistency | Trusted-register residual, parent/child residual within declared coverage/losses, sign/capacity/cadence violations and unchanged accepted observations. |
| Workflow correctness | Actual replacing estimate, equal-value provenance changes, protected edits, stale proposals, revision history, replay/restart behavior and dependent recalculation. |
| Operational burden | Distinct cases per incident, repeated notifications, review effort and time unresolved. One bad recorder should not create hundreds of unconnected cases. |

For deterministic contracts, require exact expected counts, identifiers, precedence and no unauthorized replacement. For statistical detection and estimation, establish pilot-specific error/false-positive targets from calibration rather than declaring an unsupported universal pass percentage. Report failures and abstentions, not only successful repairs.

Run three distributions: a balanced teaching suite with every family and matched controls; a long mostly-normal soak with sparse faults; and an opt-in live demonstration with a small published-to-operators event calendar. An illustrative demo cadence is two to four incidents per week across the pilot cohort, with bounded durations and recovery events. That cadence is a presentation choice, not an assumed field failure rate.

Vary shapes and severity instead of always using round 10x faults. Include ambiguous cases whose correct result is review/abstention. Introduce compound events after single-fault behavior is understood. A baseline and scorer built from the same formulas can agree and still be unrealistic: retain independent arithmetic examples, real parser tests and a separate external-data evaluation.

Use reviewed [Building Data Genome 2 data](https://arxiv.org/abs/2006.02273) as an independent hourly challenge set; the [authors' repository](https://github.com/buds-lab/building-data-genome-project-2) provides source and prepared data. Hourly readings cannot establish quarter-hour peaks, and synthetic/cleaned labels do not prove customer accuracy.

<!-- pagebreak -->

## Implementation sequence and acceptance gates

| Step | Deliverable and completion evidence |
| --- | --- |
| 1. Scenario contracts | Versioned manifest, channel/UTC identities, private truth, expected dispositions and evidence-availability rules. Validate source lifetimes, units, overlaps and anchored-window protection before generation. |
| 2. First 12 families | D01, D02, D04, D05, D07, M01, M02, M03, M04, M10, E02 and E07, each with a valid control. Produce selected real gateway files, not only analytical CSV. E02 starts as a register/interval contract test; installed evidence ingestion and E07 provenance remain product gates. |
| 3. Replay and scoring | Persistent release queue, paired logical-clock/as-of execution, hashes and receipts, real-parser results and a repeatable score report. Prove restart, duplicate selection and delayed recovery across a checkpoint. |
| 4. VEE shadow pilot | Feed actual intake results to predictive/VEE evaluation. Establish false-positive and estimate-error performance. Preserve source evidence and history eligibility; no automatic replacement. |
| 5. Supervised corrections | Complete product provenance/version/protection integration and publish through the shared interval writer. Prove before/after history, equal-value actual replacement and downstream recalculation in installed Northlake. |
| 6. Broader coverage | Add the other 16 families, cumulative-register and compound failures, held-out real-data challenges and opt-in live incidents. Automatic replacement/holds need their own consumer-level acceptance. |

Source scenarios can be built before all VEE product work is ready. Parser success proves the transport representation; source truth proves expected values; a VEE score proves analytical behavior; installed reports and bill impacts prove the application result. Record those stages separately.

The existing product work remains necessary: durable source/revision evidence beyond intake retention; propagation of actual/estimated/invalid origin and quality; distinct repeated-hour UTC write targets; versioned history eligibility; review/protection and optimistic concurrency; and shared publication with dependent effects. A later actual with the same number must still change provenance. A gap filled by an estimate must not conceal a continuing source outage.

The November 4 source check still finds that `IntervalIntake_LoadCalculationChunk` omits `PtStatus` from calculation input and `IntervalIntake_PurgeCompleted` makes completed rows eligible for removal after one day and receipts after 30 days. The current Analysis calendar also has `PhysicalTargets`, which preserves both repeated-hour instants; its `SlotEndUtc` convenience helper selects the first occurrence. D07 must verify that the intended intake/VEE/write path retains physical UTC identity. These source helpers do not establish installed acceptance, and synthetic files alone cannot repair missing provenance.

The existing Helios gap runs from March 8, 2025 at 09:00 PST to March 9 at 16:30 PDT and includes the spring DST transition. Its 2,140 kWh estimated portion is useful evidence, not automatically available to a detector before the associated source/bill arrives. WTG-07's existing outage runs February 11 through April 22, 2025. Those are distinct missing-telemetry and physical-outage cases.

No system should be allowed to estimate the ground truth merely by reading this research document's expected constants. E02's 1,000/760/240 example is an independent contract test. Statistical challenge runs use different held-out values and private labels.

<!-- pagebreak -->

## Additional scenarios from the supplied design archive

The following eight extensions turn the supplied rule notes, approval examples and mockups into testable cases. They refine the original families rather than replace them. Register and workflow cases need corresponding product support; they are not all gateway-file mutations. Source keys are defined after the two extension tables.

| ID and source | Scenario to populate | Expected outcome and control |
| --- | --- | --- |
| L01. Historical comparison eligibility [F1, F2] | Use billing cycles of 26, 27 and 28 days. Select last year's comparison by the current period's midpoint; then make that comparison estimated, missing or too short and exercise fallback to the previous read. | Normalize by days and show the selected period/rejection reason. No eligible comparison means not assessed, not passed. Exercise a zero comparison denominator and exact low/high/high-high boundaries. Extends E03/E05. |
| L02. Physical meter moves and service events [F1, F2] | Move the same asset from one service point to another with PULL then SET; vary matching digits, explicit reset and first installation. Separately send RECONNECT with and without an earlier DISCONNECT. | Follow asset identity and effective installation history. Do not carry the previous customer's baseline forward blindly. A declared reset/new meter is a control; unexplained discontinuity needs review. Extends M08/D08. |
| L03. Correction across missing-read chains [F3] | Correct an old actual or missing register read, followed by zero, one or several missing placeholders and then a real reading. Approve adjacent historical reads in different orders. | Recalculate affected boundaries, starting digits and the next actual's consumption. Keep placeholders missing. Do not double-count the intervening period or silently approve a downstream unresolved exception. Extends E09/E10. |
| L04. Read value, differential and consumption [F3, F4] | Edit the final register, raw read differential or consumption with a non-unit multiplier. Try explicit zero, blank and unchanged values; try moving the read date onto an existing read or across a neighboring read. | Apply the multiplier once. Distinguish zero from absent input. Preserve chronology and reject/review ambiguous collisions. Save and revalidate edits before approval. Extends M04/M08/E09. |
| L05. Mixed bulk approval [F3, F6] | Select ordinary failed reads, missing reads with/without estimates, protected edits and unapproved read exceptions. Repeat the approval and let one selected record change concurrently. | Account for every selected item; do not silently skip or treat an unresolved missing read as verified. Define atomic versus per-item outcomes later. Preserve unselected records and record reasons for ineligible items. Extends E08/E09. |
| L06. Explicit estimation prohibitions [F5] | A missing read belongs to a must-read service, an off meter, or a meter at its consecutive-estimate limit. Repeat after eligibility is restored; include a configured billing-attempt limit. | A numerical estimate being available does not grant permission to use it. Record the eligibility reason and request recovery/review. Do not adopt the archive's suggested auto-approval after repeated bill attempts without a separate decision. Extends E04. |
| L07. Re-read and case ownership [F4, F6] | Request a re-read for a flagged meter, assign/reassign the case, then return the same value, a corrected value, no result or a canceled order. Refresh filters while the order is pending. | Pending investigation remains discoverable and unresolved. Link returned evidence to the original case; revalidate changed data. A same-value re-read can support verification but cannot bypass policy. Extends D05/E08. |
| L08. Approval after export [F3, F7] | Correct a historical read already sent to the billing/CIS consumer; include the next dependent read and retry after interruption. | Record which downstream revisions need recalculation/resubmission and prove exactly one accepted result per revision. The legacy `SentToCIS` behavior is a scenario reference, not a prescribed new EEM field or permission to rewrite posted bills. Extends E10. |

For L04, a simple independent example is opening register 1,000, closing register 1,050 and multiplier 4: consumption is 200. Changing the differential to 60 gives closing register 1,060 and consumption 240. Use these known values to catch confusing raw digits, read differences and already-scaled consumption.

<!-- pagebreak -->

## Additional scenarios from documented VEE methods

These ten extensions draw on the supplied California VEE attachment, the Oracle configuration manual and current Oracle documentation. Numeric examples in those sources are versioned reference cases, not adopted Northlake operating thresholds.

| ID and source | Scenario to populate | Expected outcome and control |
| --- | --- | --- |
| S01. Ranked spike boundary [C1 A3.4.4, F1, O2] | Compare highest and third-highest intervals, with tied peaks, a zero third peak, low pulse counts and incomplete edge days. Test the same observations split into different files. | Resolve minimum evidence and zero denominator explicitly. Preserve pulse/energy scaling. Distinguish a configured daily window from Oracle's whole-input mode; input file size must not accidentally choose the rule. Extends M01. |
| S02. Hardware flags and test load [C1 A3.4.1-2, F1] | Send plausible values carrying pulse-overflow or test-mode evidence. Pair deliberate meter testing with a meter accidentally left in test mode, and with an ordinary register rollover. | A normal-looking number can still be unusable. Separate test load from customer use and overflow from rollover. Verify flag propagation; where the parser lacks the flag, the case requires an adapter. Extends D08/M08. |
| S03. Reactive/active consistency [C1 A3.4.5, F1] | Supply reactive energy while corresponding active energy is zero; include one-to-many channel mappings, low pulse counts and mismatched periods. Compare reported power factor with aligned active/reactive energy evidence. | Aggregate related channels using matching periods, units and averaging bases. Preserve legitimate low-load or unusual reactive operation; missing sibling data is insufficient evidence, not zero. Extends D03/M09. |
| S04. Clock correction history [C1 A3.3.2] | Drift from a last-known-good clock check, reset the meter clock, then inspect all affected intervals. Vary collection-device error, communications latency and repeated monthly failures. | Retain the original timestamps and correction evidence; distinguish collector clock from meter clock. Test the historical source's correction bands without adopting them as defaults. An isolated timestamp shift is not enough to prove the affected period. Extends D06. |
| S05. Estimation endpoint and day selection [C1 A4.1-2, F1] | Put a power failure at an interpolation endpoint; vary a gap just below/at/above two hours. For longer gaps, vary holidays, observed holidays, partial days, equidistant candidates and estimated comparison days. | Select only eligible, already-available evidence. Record candidate rejection and tie-breaking. Flat continuation is a distinct method requiring permission; retrospective future-day selection cannot leak into live evaluation. Extends E01/E05/E06. |
| S06. TOU sum and season crossover [C1 B3.5/B4.3, O3] | Split a period across seasons, include an inactive TOU bucket or one unreported bucket, and compare with an independent total register. Cross a tariff-version boundary too. | Align season, unit, period and effective TOU mapping. Sum only compatible quantities; an intentionally unreported bucket requires a different check from a complete set. Preserve total energy after estimation. Extends M09/E02. |
**Historical defaults:** the attachment's pulse thresholds, clock bands, holiday choices, two-hour interpolation rule and estimation fallbacks describe that source. Northlake needs versioned, quantity-specific eligibility and limits. Do not copy its integer rounding or bill-attempt auto-approval into every meter type.

<!-- pagebreak -->

## Additional scenarios for representation and policy

| ID and source | Scenario to populate | Expected outcome and control |
| --- | --- | --- |
| S07. Dials, fixed zeros and demand decimals [C1 B3.8-10, F5] | Change a meter's digit count, lose leading zeros, violate a fixed-zero pattern or misread demand decimal places. Supply internal and external IDs that disagree. | Check the configured representation before interpreting the quantity. An on-site decimal/display check needs field evidence; do not claim it passed from a remote file lacking that information. Extends D08/M04. |
| S08. Rule context and effective dates [F2, F7, O1, O2] | Give a point a rule override, remove it to exercise a type/group fallback, then vary initial-load, manual-override and estimation roles. Deliver old-period readings after a threshold change. | Record the exact rule instance, role, version and eligibility. Copying group defaults must not change another group. Define whether an input spanning a rule change is split or uses a declared start-date policy. Extends E05/E09. |
| S09. Multiple findings and termination [F2, F6, C1 A2, O1, O2] | One read fails several rules at different severities. Vary informational, issue and terminating findings, missing prerequisites and a disabled rule. | Keep one reviewable measurement case with its distinct findings. Retain ran/passed/failed/ineligible/not-run states. Test continue-all and explicit termination policies separately; never turn a skipped check into a pass. Extends D08/E10. |
| S10. Estimate provenance and untouched endpoints [F1] | Reuse the workbook's interpolation examples: some rows are missing, while neighboring measured values remain present. Re-run estimation, then deliver actuals for only part of the gap. | Mark only genuinely substituted rows as estimates, retain actual endpoint provenance and prevent estimated history from becoming measured training data. The example worksheet has ambiguous status labels that are not an acceptance oracle. Extends E05/E07. |

<!-- pagebreak -->

## Further documented validation scenarios

The November 4 additions below are Northlake test designs derived from the cited methods. The manuals establish the rule concepts; the selected campus examples, fault magnitudes, controls and expected Northlake dispositions are proposals. IESO and AEMO settlement requirements do not become Northlake policy merely by appearing here.

| ID and source | Scenario to populate | Expected outcome and control |
| --- | --- | --- |
| S11. Main and check meter disagreement [I1 A.3, B, C.2] | Add a proposed independent Central Plant check-meter stream. Fail the main only, check only, then both. Add a shared sensing/configuration fault. Make one comparison hour incomplete or estimated. | Substitute only from eligible independent evidence. Disagreement alone cannot identify the faulty meter; shared-error agreement is not proof of accuracy. Both failed means no trusted substitute. Control: aligned, validated actuals. Extends D03/M09/E04. |
| S12. Energy and demand load factor [F5 A13:B20, C1 B4.2] | Supply credible-looking energy and maximum demand that cannot both be true. Vary the multiplier, elapsed hours, missing demand, a reset demand register and a billed demand ratchet. | Compare the same physical coverage and demand averaging basis. Apply scaling once. A sampled kW value or ratcheted billing demand is not the measured maximum. Low load factor may be valid; missing demand is insufficient evidence. Control: consistent energy and measured peak. Extends M04/M07/M09. |
| S13. Consecutive fault across file boundaries [O4, F1 Validation rows 22-24] | Split a continuous run of zeros or bad quality across two files, midnight and a producer restart. Repeat with one valid interval inside the run and with a water-flow run that never reaches zero. | Look back across accepted chunks; packaging must not reset the run. Define which conditions break continuity. Preserve real water consumption and classify a supported leak separately from a sensor fault. Control: valid steady baseload. Extends D02/M02/M10. |
| S14. Prolonged estimation despite complete coverage [O5, F5 A22:B22] | Fill a source outage with approved estimates so no numeric gaps remain. Evaluate just before, at and after a configured age limit. Then deliver one old actual, a current actual and an equal-value actual replacement in separate variants. | Track missing actual evidence independently of filled coverage. Approval does not turn an estimate into an actual. Record the latest qualifying measurement time, not upload time, and the rule's counter definition. Control: timely actuals. Extends E04/E07 and L06. |
| S15. Weather proxy day is numerically close but unsuitable [O6, F1 Validation rows 51/55] | Give the estimator a temperature-matched holiday, a normal teaching day and an exam day. Separately corrupt the weather unit, station association or coverage, and withhold weather until after the decision. | A temperature match alone does not establish comparable operation. Record candidate eligibility, weather version and as-of availability; reject unsupported inputs or abstain. Control: an eligible prior day with aligned weather and occupancy. Extends E03/E05/E06. |

For S12, a 24-hour period containing 2,400 kWh with a measured maximum of 80 kW has load factor **1.25** and is inconsistent under matching, complete demand coverage. A control with 1,800 kWh and a 100 kW maximum has load factor **0.75**. Repeat using actual elapsed hours over DST boundaries. C1 B4.2.3 permits average demand as a historical estimation fallback; that estimate must not be relabeled as an observed peak or used as independent proof that peak demand was correct.

<!-- pagebreak -->

## Further documented estimation and operational scenarios

| ID and source | Scenario to populate | Expected outcome and control |
| --- | --- | --- |
| S16. Reconciliation must preserve accepted actuals [O7] | Combine accepted intervals with estimates, then release a higher-quality scalar total. Compare an explicitly permitted all-interval adjustment with a condition-limited adjustment. Include zero estimated weight, incompatible totals and an operator-protected interval. | Identify exactly which intervals can change. Do not silently rescale actuals to make the sum pass. Reject or review an infeasible residual; any permitted fallback is a distinct recorded method. Control: a feasible residual allocated only to eligible estimates. Extends E02/E08. |
| S17. Profile unavailable inside a mixed-quality gap [O8] | Omit one interval of the reference profile. In the target window mix missing intervals, confirmed outage zeros and valid measured zeros. Run again when the profile arrives. | Fill only eligible missing targets with available profile evidence. Retain confirmed outage and measured zeros. An absent profile value leaves a specific unresolved interval, not a fabricated zero or a successful fill. Control: a complete eligible profile. Extends M03/E01/E04. |
| S18. Switching changes the measurement boundary [I1 1.4.5, 2.4] | Switch a modeled feeder mid-interval; separately bypass the meter's voltage sensing. Deliver the switch notice promptly and late. Include a switch with no metering effect. | Use effective topology and the affected interval scope. Distinguish real load transfer from metering error. A planned event is not blanket permission to accept bad readings; expire temporary exceptions. Control: correctly measured switching. Extends M09/M10/E06. |
| S19. Historical quality percentage boundary [O9] | Offer two otherwise comparable history windows with different shares of estimated, edited and non-normal data. Exercise just below, exactly at and just above the configured eligibility limit; then revise one historical quality decision. | Record the denominator, condition categories and limit. Do not compute eligibility from row count when native durations differ unless policy explicitly calls for it. Re-evaluate proposals that depend on changed history. Control: an eligible window with the same load shape. Extends E05/E09 and L01. |
| S20. Correcting a proven meter registration error [A1 3.3.14] | Under-register a selected unanchored period by 20%, then release calibration evidence defining the affected period and correction factor. Replay the correction; include already-corrected and out-of-period readings. | A proven multiplicative error permits a scoped correction, not a campus-wide multiplier change. Preserve raw values, evidence and revision links; apply once. For this example, 80 measured units become 100 using **1.25**, not 1.20. Control: an accurate meter. Extends M04/M05/E10. |

For S16, 800 kWh of accepted actuals plus two 100 kWh estimates can reconcile to a trusted 1,200 kWh total by changing the two estimates to 200 kWh each. Multiplying every interval by 1.2 would incorrectly change the accepted actuals to 960 kWh. Score the unchanged actuals as well as the final sum.

### What these additions require later

S12 and the numeric variants of S13 can use existing file encoders with altered observation views. S20 additionally needs a timed calibration-evidence event and revision sequence. Quality-dependent S13-S17/S19 need a proven parser/intake quality path or a separate supported adapter; a private label in the scorer cannot stand in for evidence delivered to VEE. S11 needs new check-channel bindings and declared measurement independence. S18 needs effective topology and switch-event evidence. None requires changing the existing bill anchors.

Keep these as planning candidates after the first pack. A useful next slice is **S12, S13, S14 and S16**: physical consistency, continuity across deliveries, persistent source failure and safe reconciliation. For each selected case, settle the policy and evidence contract before scheduling injections. Reuse the earlier truth/observation/delivery separation, and record both the individual findings and the allowed publication outcome.

<!-- pagebreak -->

## Interpreting the supplied sources

The archive contains historical product requirements and prototype SQL, not evidence of current Northlake implementation. The original 28 families and first 12-family pack remain unchanged; L01-L08 and S01-S20 are additional planning candidates. Raw source files were read only and were not imported into the repository or executed against a database. The November 4 review revisited the supplied rules, requirements, approval examples, configuration notes, workbook examples and relevant prototype branches. It added source-specific cases rather than adopting historical SQL behavior as the new implementation.

### Decisions and source discrepancies to retain

- **Rule execution:** the California attachment A2 says a failed check does not preclude the others. The local notes suggest stopping lower-priority checks, while Oracle distinguishes informational, issue and terminating exceptions. Preserve these as explicit policy variants for S09; choose the Northlake policy during implementation planning.
- **Minimum comparison duration:** one local note says greater than 27 days, another excludes durations below 27, and prototype notes use greater than 26. L01 must exercise 26/27/28 days; do not silently settle the boundary from conflicting drafts.
- **TOU arithmetic:** C1's printed page 28 (PDF page 32) sums 50 + 100 + 150 + 200 and applies plus/minus 2, but prints a lower bound of 488. The arithmetic lower bound is 498. Use independently calculated expectations for S06 and preserve this discrepancy in the source record.
- **Flags and approval:** F1's `Estimation Example` cells D39:G44 mix missing/measured inputs and resulting quality labels. F3 also leaves bulk approval of an unapproved read exception unresolved. These are questions for the new policy, not proof that missing data can be marked actual or every selected exception approved.

<!-- pagebreak -->

## Source key and precise locations

Supplied folder: `C:/Users/Admin/OneDrive - Univerus Software Inc/Desktop/code`. The Word files, workbook rules/comments and relevant PDF sections were reviewed; schedules and mockups supplied workflow context. Selected SQL branches were read to clarify older intent, not to validate or port the legacy system.

| Key | Source locations |
| --- | --- |
| F1 | `VEE Rules.docx`: High/Low Usage and Reconnect/Disconnect/Set/Pull sections. `VEE Rules.xlsx`: Validation A2:M55; Editing A1:D5; Estimation Examples and Estimation Example, especially D39:G44. |
| F2 | `VEE reqs.docx`: How to run it, Test execution, Estimation and configuration requirements. `System Configuration page.docx`: group selection, thresholds, units and change history. `notes sep 20.txt`: rule priority and comparison-period notes. |
| F3 | `VEE Approval Scenarios.docx`: the seven non-historic/historic/missing-read approval scenarios and follow-up questions. |
| F4 | `VEE Side Mockup V2.xlsx`: Sheet1 (2), A3:A13 and D17:K38, read value/differential/multiplier and service-order controls. |
| F5 | `Copy of Hilo Exceptions.xlsx`: Sheet1 A13:B43, especially consecutive estimates, must-read services, date order, fixed-zero digits and missing paired consumption. |
| F6 | `Copy of VEE Mockup Version 1.0.xlsx`: VEE Process V7:V16 and Sheet5 assignment/actions. `Book2.xlsx`: Sheet1 rule ordering. Both MDM Schedule - Plan workbooks: VEE/business-rule/estimation sections. |
| F7 | `code/VEEMeterRead_Approve.sql`: read-date guard, missing-chain recalculation and export flags. `code/VEERule_Copy.sql` and `VEERuleThreshold_update.sql`: group defaults and history. The accompanying dated SQL files are prototype context. |
| C1 | `VEE.pdf`, 56 PDF pages: Section A revision 2.0 and Section B revision 1.1. Section references in S01-S07 identify the methods; printed page 28 is PDF page 32. |
| O1 | `Oracle MDM Documentation.pdf`: Configuration Guide, release 2.0.1 SP8, October 2012. Chapter 7, printed 7-3 and 7-6/7-7 (PDF 115, 118/119): eligibility, roles, effective periods and severity. |
| O2/O3 | Oracle 2.5.4 online [VEE rules](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_Understanding_VEE_Rules.html), [spike check](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_IntervalSpikeCheck.html) and [sum check](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_SumCheck.html), checked November 2, 2026. O2 denotes rules/spikes; O3 denotes sum checks. |

<!-- pagebreak -->

## Sources for the November 4 additions

The online sources below were checked November 4, 2026. Oracle links deliberately identify release 2.5.4. The IESO download currently identifies itself as Issue 2.0 dated December 3, 2025; its older search-index description is not the version used here. AEMO's PDF cover identifies version 8.23, effective November 1, 2026, despite older title metadata. Page numbers below distinguish printed labels from PDF positions.

| Key | Source and relevant method |
| --- | --- |
| O4 | Oracle [Consecutive Interval Check](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_ConsecutiveIntervalCheck.html), overview and examples 4-6: value/condition combinations, continuous water flow and prior-measurement lookback. |
| O5 | Oracle [Prolonged Estimation Check](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_ProlongedEstimationCheck.html): qualifying condition range, most recent non-estimated measurement time and allowable estimation days. |
| O6 | Oracle [Interval Proxy Day Estimation](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_IntervalProxyDayEstimation.html): similar-temperature comparison periods. Occupancy and weather-quality challenges in S15 are Northlake adaptations. |
| O7 | Oracle [Interval Adjustment From Scalar](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_IntervalAdjustmentFromScalar.html): all-interval versus condition-limited adjustment and zero-total behavior. |
| O8 | Oracle [Interval Profile Estimation](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_IntervalProfileEstimation.html): missing targets, outage exclusions and absent reference-profile values. |
| O9 | Oracle [High/Low Check](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_HighLowCheck.html): historical windows and configurable shares of edited, estimated and non-normal history. |
| I1 | IESO [Metering Data Processing, Part 5.2](https://www.ieso.ca/-/media/Files/IESO/Document-Library/Renewed-Market-Rules-and-Manuals/market-manuals/settlements/ieso-se-meter-data-processing.pdf), Issue 2.0: A.3, B, C.2 and 1.4.5/2.4. Printed pages 26, 34-37, 12 and 22-24; PDF pages 34, 42-45, 20 and 30-32. |
| A1 | AEMO [Metrology Procedure Part B, v8.23](https://www.aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2026/august-2026-remp-expedited-consultation/final-stage/1-nov-2026/metrology-procedure-part-b-v823-clean.pdf?rev=309f0c4e25d948eea9db6bd7d554d306&sc_lang=en), section 3.3.14, printed/PDF page 15: correction of erroneous actual registration by scaling. |

## Research basis and scope

The scenario selection is a Northlake engineering proposal informed by these primary sources, accessed November 2, 2026:

- [Oracle: IMD validations](https://docs.oracle.com/en/industries/energy-water/advanced-meter/254/c2m-user-guides/Topics/D1_BG_About_IMD_Validations.html) documents missing/sibling data, spikes, cadence, multiplier, unit, sum and prolonged-estimation checks, including outage context for zeros. Those families informed D/M cases; its settings are not adopted as universal thresholds.
- [Oracle: IMD estimations](https://docs.oracle.com/en/industries/energy-water/advanced-meter/254/c2m-user-guides/Topics/D1_BG_About_IMD_Estimations.html) distinguishes scalar-constrained adjustments, historical interval estimates and creation of gap estimates. This supports separating estimation methods and their eligibility.
- [Oracle: final measurement replacement](https://docs.oracle.com/en/industries/energy-water/meter-data-management/254/mdm-user-guides/Topics/D1_AG_VEE_FinalMeasurementReplacement.html) distinguishes value-change criteria, quality priority and manual-edit protection. It informed E07-E09.
- [AEMO: Part B v8.23](https://www.aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2026/august-2026-remp-expedited-consultation/final-stage/1-nov-2026/metrology-procedure-part-b-v823-clean.pdf?rev=309f0c4e25d948eea9db6bd7d554d306&sc_lang=en), effective November 1, 2026, documents like-day, contextual adjustment, scaling and known-zero approaches. These reinforce evidence and method-specific eligibility; Northlake is not claiming Australian settlement compliance.
- [EnergyHippo VEE delivery research](../../../univerus/energyhippo/src/Documentation/Research/VEE-Customer-Delivery-Research-2026-10-31.md), [calculation input](../../../univerus/energyhippo/Database/EEMSuite/Procs/IntervalIntake_LoadCalculationChunk.sql), [retention](../../../univerus/energyhippo/Database/EEMSuite/Procs/IntervalIntake_PurgeCompleted.sql), [history eligibility](../../../univerus/energyhippo/src/Domain/Analysis/Observations/Models/Observation.cs) and [slot conversion](../../../univerus/energyhippo/src/Domain/Analysis/Calendar/Helpers/LocalTime.cs) establish the local integration boundaries. The two moved code references were refreshed November 4. These sources were read, not modified.

The initial research created this document and its Stage 3 index link. The supplied-archive follow-ups change only this document and its rendered PDF. No scenario runner, fault injection, data import, VEE implementation, application build or installed acceptance was performed as part of these research updates.
