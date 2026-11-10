---
title: Product Findings
subtitle: Open issues and customer requirements
document_type: Open findings register
status: 59 open items; source review October 4, 2026; findings 78 and 79 added and finding 19 updated November 5, 2026
---

# Product Findings

Northlake is created through the EEM applications and supported product data
paths: configured tasks, file and bill importers, external services and the
records produced by normal use. Direct insertion of customer data is not a
substitute for those workflows.

This register contains 59 open defects, investigations and customer
requirements. Finding numbers are retained so stage references remain stable;
gaps in the numbering are intentional.

The findings are based on the October 4, 2026 source review at EnergyHippo
commit 8241fa2309ee5c3d69bfb98beb59a127d9225b40. Application reproduction,
installed-build checks and factory-database verification remain necessary
where indicated. An open item calls for the stated next action, not automatic
implementation of a new feature.

## How data legitimately gets in

| Method | Meaning |
| --- | --- |
| Direct | A screen or editable report where the user enters and saves data |
| Configure then run | Configure a workflow, task or integration through supported product tools, then run it |
| Data path | A supported file, ODBC, handheld or bill-import path |
| External | A connected service such as ENERGY STAR Portfolio Manager or EnergyAI |
| Produced by use | Audit records, status history, notes and logs created through application use |
| Customer integration | Developer-authored reports, calculations or export formats deployed through the product's extension mechanisms |

Workflow Designer, Gateway Types, Report Configuration and editable reports are
legitimate configuration paths. Customer-specific development should remain
distinct from factory defaults and from repairs to existing supported behavior.

## Findings register

| # | Finding | Kind | Stage met | Effort | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Read-only task configuration visibility is a requested permission capability; the reported single-level Task Manager grants need an installed access check before changing the catalog or editor. | enhancement | 1 | TBD | Requirement to confirm |
| 4 | AP and GL formats are developer-authored integrations registered in ExportSetup. The application lists configured exports and runs the selected format; manual execution is not limited in code to export_ap and export_ap2. | customer integration | 6 | per format | Use configured export path |
| 5 | Accrual reversal has an existing web form: CustomReverseBill calls rp_OpenAccruals with Reverse=1. Confirm its legacy schema, constants and report registration separately from the required accrual-creation workflow. | integration verification | 6, 7 | TBD | Existing reversal path; verify setup |
| 6 | GL user-defined field models and save operations exist, but no current desktop view using them was identified. Confirm the required account-level fields before adding an editor; per-billing-account coding is a separate request (51). | enhancement | 6 | TBD | Editor requirement to confirm |
| 8 | Add Rate creates the always-applied All class; added classes are Unique options. Their types are not clearly distinguished in the Rate Modeler. The capability exists; clearer labeling is a usability request. | usability | 4 | S | Confirm labeling improvement |
| 9 | The benchmark catalog is read-only in the reviewed API. Its definitions describe calculation/report metadata; custom benchmark definitions, peer sets and EUI targets are different requirements, not just one missing edit screen. | enhancement | 8 | TBD | Define required benchmark behavior |
| 10 | Report delivery supports users and groups in its picker. The model and persistence also support email recipients, but the current picker does not expose ad hoc addresses. | enhancement | 9 | S | Optional recipient editor |
| 12 | EnergyAI has an external enrollment/feed/results workflow. A self-service enrollment screen was not identified; confirm the supported integration setup and customer requirement before adding one. | external integration | 9 | TBD | Optional integration verification |
| 13 | The current GreenButton API exposes reads. Legacy download, file handoff and downstream import are separate paths; verify the supported 7.0 import workflow before choosing migration or new development. | integration verification | 9 | TBD | Optional; importer path unverified |
| 14 | Database Administrator saves aggregate members without calling the registration operation. A memberless point is not expected to have a registration row; the suspected defect is remaining unregistered after members are saved. | defect candidate | 2 | S | Reproduce save-members then calculate |
| 15 | Baseline algorithms are registered calculation implementations selected by the Point editor. No algorithm-definition editor was identified; using the supplied algorithms does not require one. | configuration / enhancement | 2 | TBD | Use supplied algorithms; define any extension |
| 16 | The Meter editor has Meter Number and Provider Meter Number fields; Provider Meter Number maps to SM_SerialNumber. If Northlake needs an internal identifier, provider badge and manufacturer serial independently, define those three meanings before adding a field. | data-model requirement | 2 | TBD | Clarify required identifiers |
| 18 | Weather-station selection includes Weather measure-type meters, including an indoor sensor if configured that way. A narrower station-role filter may help, but the required eligibility rule must be defined first. | configuration / usability | 2 | TBD | Confirm station eligibility |
| 19 | Handheld reading paths require HMR_ReadType catalog rows, and the shipped product has no catalog editor. The new Handheld Read Types page (with Handheld Meter Setup, not yet installed on Northlake) is that editor; the Northlake-only catalog script Stage 3 used before was retired and its three rows deleted on November 5. Factory seeding remains unverified. | addressed in development | 3 | S | Verify after the page ships: Northlake's three formats saved through it; check factory defaults separately |
| 21 | Gateway Types in Configuration Tool creates vendors and node/point parameter definitions. Verify missing packaged labels as presets; Neptune and MVRS use handheld-specific configuration rather than the assumed generic vendor-parameter path. | configuration / presets | 3 | TBD | Use existing editor; verify defaults |
| 24 | Project Tracking records project costs, activities and monthly savings/renewables. Ordered Design, Procurement, Installation and M&V phases would extend its purpose into a project workflow system. | enhancement | 9 | TBD | Optional workflow requirement |
| 25 | The earlier review reported an empty export catalog. Verify the factory backup and installed ExportSetup/permissions before calling this a missing product seed; customer export formats are configured integrations. | installation verification | 6 | TBD | Factory contents unverified |
| 26 | The legacy accrual report/reversal references Accrual_Bill and MPA constants, while core source also has BillAccrualMap. Verify the intended accrual workflow and installed schema before adding a legacy table. | integration verification | 6, 7 | TBD | Schema and workflow to confirm |
| 27 | Reported allocation-method counts need comparison with the shipped factory backup. Some methods in upgraded databases are MPA-specific; all seven demo methods are not automatically required product defaults. | installation verification | 7 | TBD | Separate core and customer methods |
| 28 | Reported absent accrual report registrations need an installed catalog check. MPA-specific and legacy variants should not automatically become factory reports for every customer. | configuration / scope | 7 | TBD | Confirm applicable reports |
| 32 | Meter_Save creates SM status history, while the node Status page uses M2. Bill validation reads SM; reproduce how historical in-service and closing dates can be maintained through the installed application. | defect candidate | 2, 5 | TBD | Verify historical-meter workflow |
| 34 | Account saves explicitly pass NULL for unexposed payment terms, cycle day, balance, remit/review contacts and bank account, and the procedure assigns those values. Preserve existing values independently of whether new editor fields are wanted. | defect | 2 | TBD | Source-supported; reproduce data preservation |
| 36 | The earlier Northlake observation found empty node Area values despite area history. Value_Save explicitly updates the current node area; reproduce the full area-save and later node-save sequence to identify any overwrite. | defect candidate | 2 | TBD | Reproduce exact save sequence |
| 37 | Equal PSIG and psi scale factors alone do not prove an absolute-pressure conversion defect. Verify the factory rows and whether the destination preserves gauge reference or explicitly requires absolute pressure. | unit-semantics verification | 2 | TBD | Pressure reference unconfirmed |
| 39 | Point_Save retains a legacy Reading-unit branch with an Electricity-specific fallback. Current new-accumulator UI selects a consumption unit; verify which supported edit/import path can still reach the legacy branch. | defect candidate | 2 | TBD | Confirm reachable input path |
| 40 | The Meter editor does not expose SM_SubAcctNum, although the model and save parameter retain it. Confirm that a separate sub-account field is required for this customer. | enhancement | 2 | S | Field requirement to confirm |
| 41 | General formula-derived points for turbine output, capacity factor or performance ratio would add an analytical capability. Existing aggregate calculation performs weighted sums; storing Formula does not establish support for arbitrary evaluation. | feature goal | 2, 3, 9 | L | Optional analytical scope |
| 42 | The normal weather-regression runner does not enable its partial third-variable hook. General wind, occupancy or activity regression is a separate analytical requirement from the current weather-normalization workflow. | feature goal | 8 | TBD | Optional analytical scope |
| 43 | The scatter plot implements linear regression. Binned turbine power curves or polynomial fits are additional analyses, not failures of the existing linear tool. | feature goal | 3, 9 | TBD | Optional analytical scope |
| 44 | A generation/consumption role could improve report selection. Electricity remains the correct physical measure type; prove any incorrect total with a named report, selected points, aggregation signs and an explicit accounting boundary. | reporting requirement | 2, 8 | TBD | Define boundary and reproduce total |
| 45 | NOAA maps the legacy name wspdm to wind_kt and preserves knots. A knots-configured point is correct; misleading field metadata can cause a km/h setup error. Wind direction is a separate field request. | usability / metadata | 3 | S | Clarify source units |
| 47 | The desired per-turbine actual/possible view needs a dataset and report composition. Radar minimum, maximum and unit are configurable; 0 to 100% is only the default, not a fixed limit. | customer report | 9 | per report | Use Report Configuration and chart settings |
| 48 | The reported zone 23 pairing of a fixed-GMT label/calendar with GMT Standard Time would make gateway and SQL conversions disagree. Verify the actual factory/installed row and WorkTimezone data before confirming the seed defect. | defect candidate | 3 | TBD | Verify zone and calendar evidence |
| 49 | FIG treats every non-utc Timestamp Type as local, so the shared converter's standard-time mode cannot be selected. Exposing that mode is a narrow capability request for standard-time sources. | enhancement | 3 | S | Source-supported limitation |
| 50 | The cited AP inclusion rule belongs to an MPA-specific integration. Define Northlake's GL-only routing in its financial integration before deciding whether a new core bill-service type is needed. | customer integration | 6 | TBD | Define export routing |
| 51 | GL user-defined values are attached to GL accounts. Different Department/Program segments for the same code per billing account would change that model; it is separate from exposing existing account-level fields (6). | data-model requirement | 6 | TBD | Optional accounting extension |
| 52 | A bill item derives its unit from its commodity. Mapping an unconverted MWh quantity to a kWh commodity is an input-mapping error; verify conversion and validation requirements before proposing a per-item unit field. | configuration / validation | 5 | TBD | Correct mapping; assess import validation |
| 53 | Bill lines support signed quantities and exclusions, but no explicit generation role was established. Define the report and export/consumption semantics before concluding that generation must either inflate use or disappear. | reporting requirement | 5 | TBD | Assess with 44 and customer bill mapping |
| 54 | The bill-validation quantity threshold is a tinyint, limited to 0 through 255. Supporting a larger percentage is an explicit limit-extension request. | enhancement | 5 | S | Optional; low priority |
| 55 | The digital alarm model loads/saves NormalState, but no current view binding was found; alarm resolution also hard-codes state 1. A policy with several acceptable states and only Fault alarming needs more than exposing one normal-state field. | defect candidate / enhancement | 9 | TBD | Separate state inconsistency from alarm policy |
| 56 | The scatter plot uses SumUsageValue, which integrates non-usage values by interval/60; ten-minute power values can therefore plot at one sixth of their reading. Statistics include units, but axis unit titles are absent. | defect candidate | 9 | S | Reproduce numeric and axis behavior |
| 57 | Project Tracking's editor limits its monthly grid to 12 months, while savings persistence supports additional month dates. Confirm the intended project horizon before extending the editor. | editor enhancement | 9 | TBD | Confirm project editing horizon |
| 58 | The point editor supports states 0 through 3, while Digital Summary totals only states 0, 1 and 2. A legitimately configured fourth state is omitted. | defect | 9 | S | Source-supported; reproduce fourth state |
| 59 | GHG inventory, avoided emissions, market-based instruments and valid zero factors are separate requirements. Avoided emissions should be reported separately from inventory totals; positive-only storage and rejected zero factors need their own assessment. | accounting / enhancement | 8 | TBD | Split requirements before design |
| 60 | Automatic GHG mapping matches eligible, unassigned, unexcluded meters to configured sources and has an Exclude action. It has no generation-role safeguard; the assigned category comes from configuration, not a hard-coded Scope 2 rule. | configuration / safeguard | 8 | TBD | Review mapping and accounting boundary |
| 61 | ENERGY STAR mapping sets Energy Exported Off Site to zero for onsite solar/wind consumption entries. This misrepresents a meter that actually exports; entirely onsite-consumed generation is unaffected. | defect | 8 | TBD | Source-supported; verify exporting meter |
| 62 | Rate point selection is scoped by scenario and unit/measure type. Per-determinant selection of delivered versus received channels on the same meter is an additional rate-model requirement. | enhancement | 4, 5 | TBD | Confirm tariff and channel model |
| 63 | UtilityChargeUnits excludes reactive-energy/power classes 21 and 22. Supporting those charge units is a rate-model extension; the broader claim about all power-factor/allowance arithmetic still needs tracing. | enhancement | 4 | TBD | Confirm required reactive tariff |
| 64 | Transferring a selected credit between accounts with a cycle lag is a customer tariff/allocation requirement. Assess existing allocation and integration paths before defining new core behavior. | customer requirement | 4, 7 | TBD | Confirm credit-transfer contract |
| 65 | Rate assignments form a timeline with one selected rate. A base tariff and rider may be modeled as determinants in one rate; independently reusable, concurrent rider objects would be an additional capability. | configuration / enhancement | 4 | TBD | Evaluate combined-rate model first |
| 67 | Tax/adjustment code calculates from BlockValue but constructs its percentage label from BlockSize. The previously asserted 0.05% output is not established by that code alone; reproduce the configured example. | defect candidate | 4 | TBD | Verify exact label and calculation |
| 70 | Define the required issue date, invoice number and preparer identity for generated bills, then assess what the existing bill and document model can provide. | customer requirement | 7 | TBD | Define invoice requirements |
| 71 | Commodity-mapping inner joins can discard a calculated determinant before a later missing-mapping check, while the header total still includes its amount. Reproduce the resulting header-versus-lines mismatch. | defect | 7 | TBD | Source-supported consistency issue |
| 72 | Generated bills round line amounts separately from the header; day-count and availability calculations also need checks for period boundaries, multiple points and daylight saving. Treat these as separate reproducible cases, not a universal DST failure. | defect candidates | 7 | TBD | Split rounding, days and availability cases |
| 73 | A start-stamped interval-total file can shift results if treated as end-stamped. Establish each supported source format's timestamp contract first; polls, registers and weather observations do not justify one blanket interval shift. | source-contract verification | 3 | TBD | Verify real input convention and fixture |
| 74 | The Excel reader unconditionally deletes apostrophes and flattens newlines before handlers see cells. O'Brien becomes OBrien; preserving literal cell content is a concrete data-integrity issue. | defect | 2 | S | Source-supported; reproduce text preservation |
| 77 | BulkPointDef_Get requires Bulk Data Entry at level 3. Verify that the permission catalog, group editor and runtime agree on the intended levels and honor the saved grant. | defect candidate | 1 | TBD | Open: permission consistency |
| 78 | Configuration Tool's Add Gateway always assigns a gateway type and the picker cannot clear it, but the Neptune and MVRS components never read one. Massport's live MVRS gateway has no type and no nodes, which the 7.0 editor cannot recreate, and no handheld type ships. Northlake uses an empty Handheld Meter Reading Gateway type. | configuration / presets | 3 | S | Use an empty type; decide on a packaged default |
| 79 | The web schedule form's parameter grid saves a Boolean only as true or false: an unticked box is stored as false, so a schedule cannot leave a Boolean blank to inherit its configuration default. Every saved MVRS schedule pins UseReadingTimeStamp, which should follow MVRSGateway:UseReadingTimeStamp (false by default). | defect | 3 | S | Store blank for an untouched Boolean |

## How to read the register

**Defect** means current source supports a concrete integrity or behavior
problem; its status records any required reproduction. **Defect candidate**
means the symptom, reachable input or deployment needs confirmation.
**Configuration** and **integration verification** call for checking the
supported setup. **Enhancement**, **feature goal** and **customer requirement**
mean additional behavior requires a scope decision.

Estimates are provisional. S means an apparently small change; L indicates a
larger feature. Per-format/report estimates depend on the selected deliverable.
TBD means the requirement or repair needs definition before it can be estimated.

## Review detail and next actions

### Configuration and integration checks

**Rate labels and target reports (8, 47).** Confirm clearer labeling for All
and Unique rate classes. Define the per-turbine actual/possible dataset and
report composition, using Report Configuration and the configurable Radar
minimum, maximum and unit settings.

**Gateway defaults (21, 78).** Confirm which packaged parameter labels are
missing and define them through Gateway Types. Neptune/MVRS use the handheld
configuration path; assess their setup through that path. Their gateways still
need a type to be saved in Configuration Tool. Decide whether to ship an empty
handheld type or let handheld gateways save without one, as Massport's does.

**Schedule Booleans (79).** The web schedule form stores every parameter, and
its Boolean checkbox returns only true or false, so a Boolean whose task default
is blank is pinned when the schedule is saved. MVRS UseReadingTimeStamp should
defer to MVRSGateway:UseReadingTimeStamp; Northlake's MVRS schedule stores
false, which matches today's default, but a later change to that default would
not reach the schedule.

**Accrual lifecycle (5, 26).** Verify the installed reversal form, permissions
and data prerequisites, then establish the complete accrual-creation and
reversal workflow. The legacy path references Accrual_Bill and MPA constants,
while the core also has BillAccrualMap. Identify the supported schema before
proposing another table or screen.

**Generated invoice requirements (70).** Define invoice numbering, issue
dates and preparer identity, then assess the existing bill and document
model against those requirements.

### Configuration, factory data and customer-specific development

**Financial interfaces (4, 25, 27, 28, 50, 51).** The AP application enumerates
configured exports and runs the selected format; execution is not hard-coded
to only export_ap and export_ap2. Northlake's PeopleSoft, SAP, GL and tenant
interfaces require defined customer contracts. An MPA-specific AP routing rule
does not establish a universal new bill-service type. Likewise, MPA allocation
methods and report variants are not automatically core factory defaults.

The product ships a factory database backup. Absence of a text seed script, or
a difference from an upgraded demonstration database, is not enough to prove
that a fresh supported install lacks a required row. Verify the actual factory
and installed catalogs for 19 and 25-28, then distinguish missing required
product defaults from customer setup. Do not seed every historical method,
report or legacy table merely to make the catalogs match.

**Fields and calculation definitions (6, 9, 15, 16, 18, 40).** Existing GL
user-defined fields are account-scoped; adding an editor is separate from
introducing different values for the same GL code per billing account.
Benchmark rows describe calculation/report metadata and are not by themselves
a complete peer-set or EUI-target model. Baseline algorithm rows register
implementations; selecting supplied algorithms does not require a general
algorithm-authoring screen. The Meter editor already has Meter Number and
Provider Meter Number, with the latter mapped to the serial column. Define
whether a third independent identity and a separate sub-account are needed.
Define weather-station eligibility before prescribing a site-name filter or
new station flag.

**Bill quantities and generation (52, 53, 62-65).** Bill quantities derive
their units from commodities. Convert source quantities before mapping MWh to
a kWh commodity, or use the appropriate commodity; evaluate clearer import
validation separately from a per-item unit proposal. Signed quantities and
line exclusions exist, but any generation-role requirement needs an explicit
reporting contract. A base tariff and rider may be represented by determinants
within one rate. Independently
reusable concurrent riders, channel-specific determinants, reactive charge
units and cross-account credit transfers are separate tariff capabilities to
assess, not failures established by the original configuration assumptions.

### Genuine integrity issues and bounded reproductions

**Account and import data (34, 74).** The account repository explicitly passes
nulls for unexposed fields and the save procedure assigns them. Reproduce an
ordinary edit preserving pre-existing payment terms, balance, contacts and
bank data; field preservation does not depend on adding UI for every column.
The Excel reader deletes apostrophes and flattens newlines before handlers see
the values. Reproduce with a literal name such as O'Brien and a multiline note.
These are concrete data-integrity concerns, not new customer features.

**Aggregate registration (14).** A new memberless aggregate point is not
expected to have the registration row: SaveAggregate requires members. The
reviewed desktop member-save path calls PointAggregatePoint_Save without the
registration operation, so the case to reproduce is an aggregate that remains
unregistered after members have been saved. The earlier register records ID 0,
Last calc: never, error 51081 and missing job selection as symptoms. Verify
save-members, reload and calculate as one sequence. A repair should register
the existing point when required, retaining its saved members; do not rebuild
the aggregate or create premature memberless registrations.

**Historical meter dates and area (32, 36).** The SM/M2 status-history mismatch
has source support. Reproduce entry and backdating of a meter's in-service and
closed dates, then exercise the relevant historical-bill validation. For area,
Value_Save already updates MetaWorld_TBL.Area from history; reproduce a later
node save before concluding that area history is never synchronized.

**Digital states and scatter values (55, 56, 58).** The fourth configured
digital state is absent from Digital Summary calculations. Separately, check
normal-state editing and notification's state-1 resolution rule. One normal
state cannot express three acceptable states and only Fault alarming; that
policy is a larger requirement. Scatter uses SumUsageValue after interval/60
integration for non-usage classes. Check a known ten-minute power/speed pair
and its plotted units. The statistics grid does include units; the earlier
blanket statement that no units are labeled was too broad.

**Generated bills and exports (61, 67, 71, 72).** ENERGY STAR's unconditional
zero export value is wrong when an onsite solar/wind meter actually exports.
Use an exporting example, not an entirely onsite-consumed one. Missing
commodity mapping can remove a calculated line while leaving its value in
the header; reproduce that mismatch before selecting the validation repair.
Test line/header rounding, period day counts and availability denominators as
separate cases, including multiple points and daylight saving. The tax label
uses BlockSize while calculation uses BlockValue; verify the actual configured
label rather than asserting a particular 0.05% output from the multiplier alone.

### Remaining code-path checks

The legacy Reading branch in 39 needs a reachable supported edit/import case,
because current new accumulators select consumption units. For 77, verify
BulkPointDef_Get's level-3 requirement against the intended permission
catalog and check that the group editor and runtime honor the same contract.

### Clock and source-unit contracts

NOAA's wspdm mapping supplies knots. Keep a correctly configured knots point;
clarify the metadata rather than changing valid data to match an assumed name.
FIG's unexposed standard-time mode is the issue in 49. Verify the reported
zone-23 row and SQL calendar before confirming 48. For 37, establish gauge versus absolute
pressure semantics before adding any atmospheric offset.

For 73, the earlier synthetic example reported 95 readings/2,010 kWh within a
day from a 96-reading/2,020 kWh start-stamped file. That is evidence about the
fixture's convention. Verify the actual supported AcquiSuite file contract
and period boundary before attributing it to a gateway defect. Poll timestamps,
register readings, observations and interval totals are not interchangeable.
GatewayServices.FromSourceAsync currently receives a timestamp, mode and zone,
not a node and interval. Do not prescribe a universal interval shift there
without establishing the semantics and required inputs for each affected path.

### Sustainability boundaries and optional analytical scope

Generated electricity remains Electricity as a physical measure type. For 44,
53 and 60, specify the report, selected points, signs, exclusions and accounting
boundary before asserting an incorrect consumption or emissions total.
Automatic GHG assignment already honors explicit exclusions and uses the
configured category; Scope 2 is not hard-coded in that assignment procedure.
A generation-role safeguard may improve setup but does not replace defining
the accounting policy.

GHG inventory totals and avoided-emissions estimates are different outputs.
GHG Protocol requires avoided emissions from project-based analysis to be
disclosed separately from Scope 2 inventory totals, rather than deducted from
the company's footprint. See [Inventory and Project Accounting: A Comparative
Review](https://ghgprotocol.org/blog/inventory-and-project-accounting).
Split 59 into separate avoided-emissions reporting, market-based/REC treatment,
valid zero-factor support and correct energy-flow inclusion. Positive-only
inventory results alone do not establish an accounting defect.

Formula points (41), general driver regression (42), turbine power curves (43)
and ordered project phases (24) are optional additional capabilities. Current
Project Tracking records savings and renewables, not a general project
workflow. Its 12-month editor horizon (57) is separate from storage, which can
hold additional month dates. EnergyAI setup (12) and GreenButton migration
(13) remain integration questions to resolve through their supported paths.

## Verification and delivery order

1. Reproduce the integrity cases in 34 and 74, aggregate registration after
   member save (14), meter-history behavior (32), digital reporting (58),
   scatter values (56), exporting ENERGY STAR meters (61), the schedule form's
   Boolean save (79), bill consistency (71) and the separate bookkeeping cases
   in 72. Resolve 77's permission
   mismatch against the intended catalog contract.
2. Check factory/installed catalogs for 19 and 25-28, gateway defaults (21, 78),
   accrual setup (5), and the unit/clock contracts for 37, 45, 48, 49 and 73.
   Add only demonstrated missing defaults or required customer setup.
3. Define and estimate the selected enhancements, invoice requirements and
   customer reports. Keep analytical, project-workflow and accounting-model
   extensions separate from defects, and reuse current configuration and
   extension mechanisms first.

## Evidence pointers

These links point to the reviewed source files in the sibling EnergyHippo
checkout. They document the implementation evidence, not installed availability.

- 5/26: [CustomReverseBill.cshtml](../../univerus/energyhippo/src/Web/EEMSuite.Web/Views/Custom/CustomReverseBill.cshtml), [rp_OpenAccruals.sql](../../univerus/energyhippo/Database/EEMSuite/Procs/rp_OpenAccruals.sql).
- 21: [VendorManagementViewModel.cs](../../univerus/energyhippo/src/Apps/EEMSuite.Apps.ConfigurationTool/ViewModels/Vendors/VendorManagementViewModel.cs).
- 78: [GatewayConfigurationViewModel.cs](../../univerus/energyhippo/src/Apps/EEMSuite.Apps.ConfigurationTool/ViewModels/GatewayConfigurationViewModel.cs), [GatewayModel.cs](../../univerus/energyhippo/src/Apps/EEMSuite.Apps.ConfigurationTool/Models/Gateways/GatewayModel.cs), [HMR_PointNode_Get.sql](../../univerus/energyhippo/Database/EEMSuite/Procs/HMR_PointNode_Get.sql).
- 79: [dynamicFieldEditor.ts](../../univerus/energyhippo/src/Web/EEMSuite.Web/frontend/src/scripts/hippo/components/dynamicFieldEditor.ts), [mvrs-gateway.json](../../univerus/energyhippo/src/Tasks/EEMSuite.Tasks.Components/BuiltInWorkflows/mvrs-gateway.json).
- 47: [chartPresentationSettings.ts](../../univerus/energyhippo/src/Web/EEMSuite.Web/frontend/src/scripts/hippo/reporting/chartPresentationSettings.ts).
- 34/74: [DapperBillingAccountsRepository.cs](../../univerus/energyhippo/src/Data/Dapper/Billing/BillingAccounts/DapperBillingAccountsRepository.cs), [uaBillingAccount_Save.sql](../../univerus/energyhippo/Database/EEMSuite/Procs/uaBillingAccount_Save.sql), [EEMClosedExcel.cs](../../univerus/energyhippo/src/Domain/Shared/Excel/EEMClosedExcel.cs).
- 58/61/71: [rp_digitalPoints.sql](../../univerus/energyhippo/Database/EEMSuite/Procs/rp_digitalPoints.sql), [MeterConsumptionMapping.cs](../../univerus/energyhippo/src/Tasks/EEMSuite.Tasks.EnergyStar/Mapping/MeterConsumptionMapping.cs), [UtilityBillLineItems_Get.sql](../../univerus/energyhippo/Database/EEMSuite/Procs/UtilityBillLineItems_Get.sql), [UtilityGenBill_Create.sql](../../univerus/energyhippo/Database/EEMSuite/Procs/UtilityGenBill_Create.sql).
