---
title: Stage 5. Bills
subtitle: Bill validation rules, imported and manual bills, images, notes and approval
status: Ready to enter (revised 2026-10-01)
---

# Stage 5. Bills

Stage 5 puts two years of real utility bills into Northlake: one monthly bill per
account from January 2024 through December 2025, decomposed into the charge
lines each provider actually bills, plus the fixtures that make Bill Processing
and Bill Tracking reports worth looking at - a meter swap mid-bill, an estimate
that gets corrected, a file imported twice on purpose, an account that goes
quiet, a rate that changes at a year boundary, and a file that a bad fiscal date
bounces. Bill Validation rules go in first so the deliberate failures actually
fire when the bills that should trip them are saved. Stage 2's hierarchy and
Stage 4's rates are prerequisites; nothing here needs Stage 3's interval data,
though the interval-metered buildings' demand lines read better once it exists.

**Added 2026-10-01: Ridgeline Wind.** The Thermal Plant's wind company brings two
accounts, and this stage enters only one of them. Valley Electric's generator
account at the Ridgeline substation (SYN-VED-A-0010014) is imported like every
other Valley Electric account, but it opened with the acquisition. Valley
Electric reads on the 5th, so its first bill runs 35 days, from the July 1
opening to August 4, and its series is 17 bills (August 2024 to December 2025),
not 24. It keeps none of its export credit: the credit leaves each generator
bill as a transfer line and lands, sign reversed, on the Central Plant's bill one
cycle later (the first bill's credit on the September 2024 bill), so the
generator pays a small residue and the credit is counted once. Ridgeline's
own transfer agreement (SYN-RWL-G-0000001) takes no bill in this stage: EEM
generates its monthly statement in Stage 7, and the hand-made July 2024
statement is the figure the first generated one must match to the cent. Three
itemized Valley Electric statements and that hand-made one are in
`documents/utility-bills`; each step below says what they change.

## Before you start

- Stage 1's companies, providers, calendars, groups and users are in place; Stage
  2's billing accounts and meters exist with their synthetic account and meter
  numbers recorded, the Ridgeline generator account and its interconnection meter
  included; Stage 4's VED-TOU-GS-FY25 rate is loaded, and so are the generator
  rates VED-GEN-IC and VED-BCT.
- Accounts and meters are referenced here by synthetic number, not by database
  ID - look each one up in Stage 2's records before opening it.
- Before Step 5, confirm the approver holds the Bill Validation function: that
  is what the product checks when a bill is validated, and Stage 1 grants it
  through EEM Company Setup (see Findings).

## Step 1. Bill Validation rules

**Where:** Database Administrator, Nodes, the company node's Bill Validation
tab.

**Enter:** [01-bill-validation-rules.yaml](01-bill-validation-rules.yaml), six
records: the Global defaults and five account-level overrides.

**Order inside the editor:** pick "Validation for" (Global Defaults, or a
company), then "Settings for" if you picked a company (its own defaults, its
groups, one group, or one billing account). The Bill Save tab holds the tests
Northlake uses; Batch Test is untouched. Test Name, Commodity, the paired
description and Unit are locked from the product's own catalog - only State,
Percent and Amount are yours to set, and only on the row for the scope you are
actually on.

**The five overrides** each open one billing account directly through "Settings
for > Account": Science Center's cost-change threshold is raised to 60% (lab
loads swing further than the 35% campus default), Student Center's usage-change
test is turned off (the estimate-then-correction fixture is a deliberate swing),
Cedar Row A's minimum-period-length test is turned off (the July 2024 renewal
produces one short period), the Thermal Plant's Science Center allocation gets
its own $250,000 cost ceiling instead of the $1,000,000 global one, and, added
for Ridgeline, the Valley Electric generator account has both of its tests
against the previous bill (cost change and usage change) turned off. Its bill
is the small residue left after the export credit leaves ($1,077.45 on the first
bill, $6,753.10 on the calm bill for January 5 to February 4, 2025) and its only
usage, station service, follows the wind (4,428 kWh, then 46,920 kWh). The
percent column holds at most 255, so raising the threshold could not cover a
swing that size.

**Record:** nothing generated; the scope and test you picked are the record.

**Check:** `validation_rules_set`.

## Step 2. Bill Importer sources

**Where:** the Bill Importer app, then Web SPA, `#/BillImporter`.

**Enter:** [02-bill-importer-sources.yaml](02-bill-importer-sources.yaml), two
provider sources and two hand-built sample files.

**Order:** in the Bill Importer app, point it at the provider's sample CSV and
let it write a `.bif` file; there is no screen to add a new provider to the
app - a provider is a `Schemas/<code>.xml` file plus a code in
`appsettings.json`'s utility list, both already installed alongside the app for
VED and RCU. Then, in the Web SPA, open Files and upload the `.bif`, open
Mappings and set the Account Mapping and Commodity Mapping once per provider,
then Workspace to review and import.

**The two fixture files** skip the WPF step entirely: they are flat BIF text
typed by hand in the same column layout the app itself produces, uploaded
straight to the Files tab. One declares a Sierra Gas Student Center line in
`BTU/hr`, a unit its commodity does not accept. The other is Admin Hall's
January 2025 Valley Electric bill keyed with its year transposed, 2052 for
2025, a fiscal period no Northlake calendar has (they run to 2026 or 2027, and
EEM keeps extending them) - the Workspace shows the product's own messages,
"Fiscal Year NOT found!" and "Fiscal Period NOT found!", and imports nothing.

**Added for Ridgeline: seven charge codes, not a source.** Valley Electric's
generator account and the credit lines on the Central Plant's bills arrive in
the same Valley Electric file, so Step 2 only gains mappings: a fixed charge,
station service energy, reactive energy, the generation credit, the credit
transferred out, the credit received and the BCT fee. VED.xml gets a BillItem
block for each. The statement prints the export register in MWh (2,496.612)
beside kWh (2,496,612), and the interval channels are kWh. A bill item has no
unit of its own, so a quantity takes the unit of the commodity it maps to, and
the export is carried as dollars only. Ridgeline Wind itself has no source:
nobody sends it a bill.

**Record:** nothing generated by this step; Step 3's bills carry the IDs.

**Check:** `imports_configured`, `fiscal_period_rejection_logged`.

## Step 3. Bills

**Where:** Web SPA, `#/BillEntry`, Add Bill, `#/BillEntry/Editor/Details` for
every manually-entered account; the imported series from Step 2 for Valley
Electric and River City.

**Enter:** [03-bills.yaml](03-bills.yaml), a monthly series rule per provider
group covering the 50 billing accounts that take bills in this stage, six named
fixtures, and the Ridgeline records described below.

**Every bill follows its provider's read cycle** and posts to the month it ends
in: Valley Electric reads on the 5th (a bill runs from the 5th to the 4th),
Sierra Gas and River City's Cedar Row cycle on the 15th, and River City's campus
cycle, the Thermal Plant and Helios close with the calendar month. The sample
bills under `documents/utility-bills/` are exact and itemized, generated from
`data/bills/` on those cycles and at the tariffs; the fixtures quote them.

**Order inside the editor:** period start/end/days, fiscal year/period,
received/issue/due dates and invoice number first, then the Bill Items grid -
one line per charge from the bill-charge-line spec, in the order the provider
bills them, taxes last. A line whose quantity is zero for that period (a winter
peak line, an empty water tier, Cedar Row's stormwater line) is left out
entirely rather than entered as zero. A bill becomes read-only once it is
exported, so enter and check it before that point.

**The six fixtures:**

- **Meter replacement** - the Library's meter was exchanged on August 15, 2024,
  inside its September 2024 cycle (August 5 to September 4). It is one bill
  ($5,114.37) whose items carry each meter's own read period, August 5 to 14 on
  the old meter and August 15 to September 4 on the new one, so the cycle is
  billed once, not twice.
- **Estimated then corrected** - Sierra Gas Student Center's November 2024 bill
  (October 15 to November 14) is entered once with its gas lines flagged
  Estimate ($935.90), and a second time with the actual read after the December
  read ($885.32).
- **Duplicate import** - River City's Main Campus file delivered on September 4,
  2024 (the campus accounts' August bills) is imported twice on purpose (Step
  2), as River City sent it; each account's water, sewer and stormwater lines
  must still show once.
- **Account number change** - Cedar Row A's River City account was renumbered at
  the July 2024 lease renewal; its September 2024 bill (August 15 to September
  14, $1,984.50) is under the new number, and Stage 2's Previous Account Number
  links the old one.
- **Late bill** - Sierra Gas Library stops after its November 2025 bill; with
  no December bill and its usual entry lag past, it is overdue.
- **Rate change boundary** - Valley Electric's FY2025 rates start with service
  on January 1, 2025, which falls inside Student Center's January 2025 bill
  (December 5 to January 4). That bill is priced in two parts: energy by the
  date it was used, demand and the facility charge prorated by days ($8,469.10).
  The bills either side are wholly at one rate.

**Ridgeline (added 2026-10-01):**

- **Generator series** - SYN-VED-A-0010014 gets 17 bills, posting August 2024
  through December 2025 and imported with the other Valley Electric accounts. A
  bill runs from the 5th to the 4th and posts to the month it ends in, so the
  first runs July 1 to August 4 (35 days) and the last November 5 to December 4,
  2025. Each has a customer charge, station service energy, reactive power
  beyond the 0.95 power-factor allowance (left out when zero), the generation
  credit, the same credit transferred out, and 5% tax on the three charges. The
  credit and its transfer cancel, so the bill is a small positive residue. No
  bill exists before July 1, 2024, and the account has no FY2025 rate step.
- **Credit transfer** - from the September 2024 bill, the Central Plant's bills
  carry the VED-BCT lines: the credit received, equal to the transfer out on the
  previous generator bill, and a $12.50 fee that starts with the first credit
  (an assumption; the rider is effective July 1, 2024, but the September bill is
  the first one printed). That is 16 credits. The credit is counted once: it
  leaves one bill and lands on the other. The last generator bill's credit (the
  one for November 5 to December 4, 2025) has no bill to land on inside the
  window (it would post to January 2026, after the last bill this packet
  covers), so it stays in transit. The credit and the fee are not taxable, which is the one
  place a tax line is not a percent of every line before it.
- **Itemized bills** - like every sample bill, three Ridgeline statements are
  exact, down to the cent: the generator's first bill (July 1 to August 4, 2024,
  $1,077.45), its calm bill for January 5 to February 4, 2025 ($6,753.10;
  station service more than ten times the first bill's, no reactive charge) and
  the Central Plant's first credit (August 5 to September 4, 2024, $151,171.47).
  Each is entered three days after its period ends, after its invoice date.
  Enter them first; their PDFs attach in Step 4.
- **Ridgeline's own statement** is not entered. EEM generates it in Stage 7; the
  hand-made July 2024 statement (2,251,384 kWh at $0.058 less the $1,250.00
  research credit, $129,330.27) is kept in `03-bills.yaml` as the acceptance
  reference.

**Record:** nothing new beyond the bills themselves; Stage 6 refers back to
these accounts by synthetic number.

**Check:** `bills_per_account`, `charge_lines_sum_to_total`,
`estimated_then_corrected`, `meter_replacement_continuity`, `late_bill_present`,
`generator_account_opened_mid_window`, `itemized_ridgeline_bills_match`,
`bct_credit_counted_once`, `ridgeline_transfer_not_entered_here`.

## Step 4. Bill images and notes

**Where:** the Bill Entry editor's image pane for bill images; the web Note
History screen for a meter note; the Utility Accountant tab's Notes page for a
billing-account note.

**Enter:** [04-bill-images-and-notes.yaml](04-bill-images-and-notes.yaml),
twenty-four bill images and five notes.

**Order:** attach each sample PDF to the bill it illustrates - the provider's
standard sample to a typical month, the scenario samples to the matching
fixture bill. Meter Definition has no Notes page of its own, so the Library
meter's replacement note and the Science Center meter's power-factor note both
go through Note History with Table Code METR and that meter's ID. Ridgeline
adds three Valley Electric statements (the generator's first bill and its calm
bill ending February 4, 2025, the Central Plant's first credit), a note on the
generator account (transferred at the acquisition, the seller's number
SYN-VED-A-0019014) and the hand-made July 2024 Ridgeline statement. Nobody
enters that bill, so its PDF waits for the statement EEM generates in Stage 7
and is the one image not attached here.

**Record:** nothing generated.

**Check:** `images_attached`, `notes_present`.

## Step 5. Approval

**Where:** the bill's status chip and status history in `#/BillEntry`; the
Validate action on Bill Validation.

**Enter:** [05-approval.yaml](05-approval.yaml).

**Order:** every bill already carries a Status_Code 1 (Bill Entry) history row
from being saved. Open roughly a third of each account's bills, spread across
the two years, and click Validate to advance them to Status_Code 2 (QC
Approval). Then, as the fixture in Step 5's second record, sign in as a
bill-entry-only user and confirm she cannot do the same.

**Record:** nothing generated; the status change is the record.

**Check:** `approvals_by_role`.

## Stage 5 is done when

- Bill Processing and Bill Tracking's core reports render with the phase-0-1
  relationships holding on every bill: charge lines sum to the bill total,
  Valley Electric's TOU lines sum to total kWh, River City's tiers partition
  total kgal, Helios's credit line is negative, Sierra Gas and Valley Electric's
  tax lines are a percent of the subtotal before them (the Central Plant's, from
  the September 2024 bill, leave the VED-BCT credit and fee out of that
  subtotal), and site/building rollups equal the sum of their bills.
- Ten Bill Validation test rows exist at Global scope and five account-level
  overrides exist, exactly where the AP/GL plan calls for them; the fifth, on
  the Ridgeline generator account, switches off both change tests.
- Two Bill Importer sources are configured and the fiscal-period and bad-data
  samples are rejected with the product's own messages, not silently dropped.
- Every account that existed in January 2024 has at least 23 monthly bills for
  2024-2025, the Ridgeline generator account has 17 (August 2024 to December
  2025), the six named fixtures behave as described, twenty-three bill images
  and five notes are attached (a twenty-fourth image joins Ridgeline's generated
  statement in Stage 7), and roughly a third of each account's bills have been
  advanced to QC Approval.
- Each generator credit has left its bill and landed once, sign reversed, on the
  Central Plant's next one: 16 matched pairs, with the last generator bill's
  (December 2025) still in transit, and Ridgeline's own account has no bill
  until Stage 7.

Run `checks.sql` beside this chapter against the instance database to see each
of these as a result set.

## Findings

- **Approval is the Bill Validation function, not Bill Administration.** The
  API endpoint that advances a bill to QC Approval -
  `BillEditController.ValidateBill`/`ValidateBills`
  (`src/Web/EEMSuite.Web.Endpoints/Controllers/BillEditController.cs`) - is
  gated by `[EEMPermission(Function, "Bill Validation")]`, and the permission
  catalog marks "Bill Administration" as a legacy, unmapped entry. Stage 1 now
  grants Bill Validation at level 1 through the shared EEM Company Setup group
  (eem_company_setup) and gives bill-entry groups none, so the approver-versus-
  entry test in Step 5 runs against the function the product checks. Product
  finding 2 records the model change (closed by design).
- **The Bill Importer app has no "add provider" screen.** A provider is a
  `Schemas/<code>.xml` file (documented inline in `Schemas/CRC.xml`) plus a code
  in `appsettings.json`'s `BillImporter:Utilities` list
  (`BillImporterMainWindowViewModel._TryLoadProvider`), both installed
  alongside the app rather than entered on any screen. Treated here as a
  one-time customization step, not a gap - see [product findings](../product-findings.pdf)
  if a same-instance "add a provider" screen is wanted later.
- **Bill Service Type is three values, not four.** The Phase 3 AP/GL plan
  described a four-way flag (No Upload / AP / GL / AP and GL). The field it
  actually maps to, `Global_Type_Code` where `Table_Code='BA'`, has three rows
  in this installed instance: 0 No AP Upload, 1 AP Upload Only, 2 Bill Payment
  (verified by direct query). There is no GL-only or AP-and-GL value; GL coding
  (the Liability Account and Default Expense Account fields) is present on
  every billing account regardless of its upload flag. Stage 6 reconciles the
  AP/GL plan's rules against the real three values.
- **A bill item has no unit of its own (Ridgeline).** The flat BIF item the Bill
  Importer reads is Meter, Descriptor, Estimate, Quantity and Amount, and the
  bill item it creates stores a commodity, a quantity and an amount, so a
  quantity takes the unit of the commodity it maps to. Valley Electric's
  generator statement prints the export in MWh beside kWh; a figure mapped to a
  commodity of the other unit is stored a thousand times off, and nothing flags
  it. Northlake carries the export as dollars only, so nothing here depends on it.
- **A bill line cannot say it is generation (Ridgeline).** The generation credit
  has an export quantity and a negative amount, but no commodity marks energy as
  exported rather than used (product finding 44 for meters and points; bills
  have the same gap). Mapped to a kWh commodity it adds the export to the
  building's use; mapped to Misc Chgs/Credits it keeps the dollars and drops the
  kWh from the bill. Northlake takes the second, and the export stays in the
  received interval channel.

None of the above blocks entering this stage's bills - they are recorded so
Stage 6 and any later permission cleanup start from what is actually installed.
