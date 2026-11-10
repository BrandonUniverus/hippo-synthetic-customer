# Northlake coverage review: Stage 1 (foundation) and Stage 2 (hierarchy)

Read-only review, 2026-11-10. Recipe: `C:\Hippo\Git\hippo-synthetic-customer\implementation\stage-1-foundation` and `stage-2-hierarchy`.
Product: `C:\Hippo\Git\univerus\energyhippo`. Nothing was edited, built, run or queried.

Marks: **READ** = seen in code or in the YAML/SQL. **INFERRED** = deduced, or a search came back empty.
`DBAdmin/` means `src/Apps/EEMSuite.Apps.DatabaseAdministrator/`.

## 0. Headline

- Stage 1 and 2 enter many rows (Stage 1: 3 companies, 6 providers, 23 users, 29 group definitions. Stage 2: 51 accounts, 390 meters, 474 points) but almost every field has one value across all records.
- Examples of one value everywhere: time zone Pacific on every company, node, point and user; currency US Dollar on 51 of 51 accounts; principal type Human and policy LocalAndFederated on 23 of 23 users; building status Open on 16 of 16; unit conversion offset 0 on 4 of 4.
- Whole editor pages are never touched: Node Contact, Hierarchy Filters, Delta Multiplier, API keys / customer logos, non-calendar fiscal years.
- The two checks.sql files are the strong part: every field the YAML sets is compared to a known expected value. The weak part is fields the YAML never sets.

---

## STAGE 1 FOUNDATION

### 1.1 What the stage sets up

| File | Screen | Records | What it exercises |
|---|---|---|---|
| 01-companies.yaml | DB Admin > Nodes > company node > Definitions (Definitions, Levels, Company Address, Company Contact, Bill Scenarios) | 3 (Northlake University id 6, Cedar Row id 3, Thermal Plant id 5) | Name, archive interval 60, Pacific, USA, 9 alarm texts/colours + 4 digital state colours, 4 hierarchy levels each (description, UDF name, icon), address with lat/long, one contact, Bill Scenario Actual |
| 02-utility-providers.yaml | DB Admin > Utility Providers | 6 providers (Helios, Thermal Plant, Ridgeline Wind, River City, Sierra Gas, Valley Electric); 7 cycle groupings and 162 periods; 14 vendor associations; 6 remit addresses; 23 note lines | Definitions + icon, address, contact, remit address, bill cycles (Ridgeline 18 periods, the rest 24), associated companies with vendor number and alias, Notes page |
| 03-company-calendars.yaml | Web > Administration > Company Calendar | 3 companies x 24 periods = 72 | Verifies 2024 and 2025 monthly periods, calendar quarters, "Mon-YYYY" names |
| 04-groups.yaml | DB Admin > Users & Groups > Groups | 29 definitions (21 shared masters in Common + 8 local) = 91 group rows with 62 shared copies; 255 permission rows | Shared masters and copies, Points by company root and by node (Science Center 0.6.22.24, Ridgeline 0.5.40), levels 1/2/3, report categories All vs listed, user modules, admin modules, functions, one Task Manager `*`, library rates `*`, one detached copy (Make Local) |
| 05-users.yaml | DB Admin > Users & Groups > Users | 23 users (12 NLU, 5 Thermal Plant, 3 Cedar Row, 3 Common); 5 IsAdmin; 1 Inactive (casey.holt); 67 memberships | IsAdmin, Inactive, cross-company Points through home-company membership |
| checks.sql | read-only | 699 expected rows, 18 families (1.4) | |

Counts agree between the YAMLs and the chapter (29 groups, 91 rows, 23 users, 5 admins, 18 non-admins). I also checked: every group a user belongs to exists, and `groupMemberships` matches the per-user lists (67 both ways).

### 1.2 Coverage gaps

**Companies** (`DBAdmin/ViewModels/Companies/Definitions/*`, `Database/EEMSuite/Tables/Company_TBL.sql`)

| # | Gap | Mark |
|---|---|---|
| C1 | All three companies use the product defaults for every alarm text and colour (the 27 alarm rows equal the `Company_TBL` column defaults exactly). No company customises them. `Definitions/DefaultsViewModel.cs` | READ |
| C2 | Archive interval 60 for all three. The editor offers a list (`CompanySectionViewModel`, `GetArchiveIntervalsAsync`); no other value used. | READ |
| C3 | One time zone (Pacific) and one country (USA) on every company, address, provider, user and node. No zone offsets, no "Propagate Time Zone" (`NodeDefinitionsViewModel._propagateTimeZoneCommand`), no non-US address/region (`RE_RegionCode` char(5), only "CA" sent). | READ |
| C4 | Hierarchy Levels: every company has exactly 4 levels (Site, Location, Meter, Point). The editor lets a company add further levels (`Models/Companies/HierarchyLevelModel.cs`: CanDelete, CanMove, Insert). No Floor/Room/Zone level. The level **Purpose** field (`Views/Companies/Definitions/CompanyLevelsView.xaml` line 220) is never filled. | READ |
| C5 | Fiscal settings never varied. The desktop Calendar section exposes Fiscal Year Begin, Fiscal Year Type (1-255 periods), Fiscal Format, Generate Calendar (only when type = 12) and Copy Calendar (`Views/Companies/CompanyFiscalSettingsView.xaml`, `CompanyCalendarSectionViewModel.cs`, `Company.IsValidFiscalSettings`). Every company runs a calendar year, 12 periods. No July-start year, no 13-period year, no custom format. | READ |
| C6 | Web Company Calendar: Period/Start/End/Quarter/Name grid read back only. Quarters are calendar quarters. Copy Calendar, Add/Delete period and the gap/overlap validators (`Web/EEMSuite.Web/frontend/src/scripts/hippo/views/viewCompanyCalendar.ts`, msgGap*, msgOverlap*) are not exercised on purpose. "Calendar Type: Standard (calendar year)" is not an editor field; it maps to `CompanyCalendar.CalendarTypeID`. | READ |
| C7 | Bill Scenarios: **Actual** only on all three. The scenario types also include Budget and Weather Normalized (`Migrations/v7.0.0.sql` ~29930, `BillScenarioViewModel.AvailableScenarios`). Stage 7 uses Budget in the Town Center company only. | READ |
| C8 | `Company_TBL` columns with no recipe data: ContractStart/End, FYAbbrMask, Auto_Expand_Level, CT_ContactID_AcctMgr. A search of `src` finds no UI for ContractStart, FYAbbrMask or AcctMgr (probably unused columns); Auto_Expand_Level appears only in the repository/model. | INFERRED |
| C9 | Company Address has no Address 2. One contact per company. | READ |

**Utility providers** (`DBAdmin/ViewModels/UtilityProviderViewModel.cs`, `BillCycleViewModel.cs`, `AssociatedCompaniesViewModel.cs`; `Tables/UtilityProvider.sql`, `BillCycle.sql`, `CompanyProvider.sql`)

| # | Gap | Mark |
|---|---|---|
| P1 | Every provider has exactly one remit address. The Stage 2 per-account Remit combo is only ever a one-item list; choosing between addresses is untested. | READ |
| P2 | Every bill cycle is monthly, contiguous, 28-31 days, period/year = posting month. Missing: bi-monthly or 4-4-5 cycles, a gap, an overlap, a mid-history change of cycle number. Cycle numbers used: 1, plus River City 2. The Generate Periods drawer (`BillCycleGeneratePeriodsDrawerViewModel.cs`) and Excel import/export (`BillCycleViewModel.cs`) are not used. I checked all 7 groupings: days = end - start + 1, no gaps, no sequence breaks. | READ |
| P3 | Provider cycle periods stop at **2025-12** (Ridgeline from 2024-07). The checker looks at 2024 and 2025 only. See 1.7. | READ |
| P4 | `UtilityProvider.TimeZoneID` exists; the provider editor has no time zone control, so it is never set. | INFERRED |
| P5 | Associated Companies: every row has a vendor number and an alias; no blank ones. The Thermal Plant is associated with Cedar Row (NTP-INTERNAL-CR) but Cedar Row has no Thermal Plant account (the only association with no account; harmless). | READ |
| P6 | Website blank only for the Thermal Plant; Address 2 only for the Thermal Plant; one contact per provider. Provider Notes are filled but checked by nothing (1.4). | READ |

**Groups and permissions** (`DBAdmin/ViewModels/UsersAndGroups/*`; `Database/EEMSuite/Scripts/Register*Permission*.sql`; `src/Domain/EEMSuite.Domain/Admin/Users/Models/EEMApplicationPermissionKeys.cs`)

| # | Gap | Mark |
|---|---|---|
| G1 | Permission keys that exist and are granted to no group: `sql_execute`, `budget_maker`, `scim_provisioning_administration`, `identity_privacy_restricted_data_view`, `system_configuration`, `report_library`, the Analysis module set (`analysis`: Setup, Configurations, Results, Review, Approve, Edit Readings), and the admin tab key `BillValidationTab`. A grep of `implementation/stage-*/` finds none of the first six. | READ (register scripts); recipe grep INFERRED complete |
| G2 | Permission type **MI (My Import Methods)** is listed in `permissionTypes` and granted nowhere. Task Manager (TS) is granted once (`*`, level 3). | READ |
| G3 | Levels: Report Groups only 1 (67 grants). Library Rates only 1 and 3, never 2. Functions only 3 (the YAML notes Bulk Data Entry works only at 3). Admin Modules cover 1, 2, 3. The level-behaviour cases are "Pending application execution". | READ |
| G4 | Sharing life-cycle half covered. Make Local is done once (Cedar Row eem_reports). **Delete a copy to opt out** (`Tables/UserGroupSharedOptOut.sql`) and **Restore shared group** (`RestoreSharedGroupViewModel.cs`) have no record. | READ |
| G5 | Access Management extras with no recipe data: API keys (`ApiKeyViewModel.cs`), customer logos (`CustomerLogosViewModel.cs`), change password (`ChangePasswordViewModel.cs`). A grep of `stage-*/*.yaml` for "API Key" and "Customer Logo" finds nothing. | READ / INFERRED |
| G6 | Node-scoped Points exist for two nodes only (Science Center, Ridgeline Wind Site). None for a Meter or Point node, none for a node later moved or deleted. | READ |

**Users** (`DBAdmin/ViewModels/UsersAndGroups/AddUserViewModel.cs`, `Tables/Users_TBL.sql`, `UserPrincipalType.cs`, `UserSecurityState.cs`)

| # | Gap | Mark |
|---|---|---|
| U1 | **All 23 users are Human with LocalAndFederated.** The product defines principal types Human, Task, ApiClient, Service and policies LocalAndFederated, ExternalOnly, WorkloadOnly. No service account, API client, task principal, external-only or workload-only user. The note "WorkloadOnly is for service principals only" has no record. | READ |
| U2 | All users: Pacific zone, no notes, no contact, default language, default AutoNotify. `Users_TBL` has LanguageTypeID, AutoNotify, Notes, CT_ContactID, lock-out and invalid-login columns. I did not find a user-editor language control. | INFERRED |
| U3 | States beyond active: only Inactive (casey.holt). Not exercised: locked out, expired password, invitation required/accepted (`InvitationsEnabled` in `AddUserViewModel`), user moved to another company. | READ / INFERRED |

**Product features in this area with no recipe data at all**
- Hierarchy Filters (`DBAdmin/ViewModels/Nodes/HierarchyFilterManagerViewModel.cs`): no stage YAML mentions them. The reconciliation doc lists hierarchy filters as a reference table for groups.
- Non-US company, second currency.
- GL Accounts and Bill Validation tabs are Stage 6 by design.

### 1.3 Fields in the YAML that are always empty, null or default

- 01-companies: no Address 2, no level Purpose; alarm/digital colours identical on all three and equal to the table defaults.
- 02-providers: `Website:` null (Thermal Plant); `installed.remitAddressIds` blank on all.
- 04-groups: Report Group level always 1; `MetaCompanyID: null` only on the three system groups.
- 05-users: Principal Type, Authentication Policy and Time Zone single-valued on 23 of 23; Inactive false on 22 of 23.

### 1.4 Depth of checks.sql (Stage 1)

Generated from the YAML (`python -m generators.stage_check_data`). It compares an expected-value JSON with a live read and reports missing, extra, duplicate and wrong-value rows. There are **no PRINT-only checks** and no "list rows beside a PRINT" checks.

| Family | Expected rows | Kind |
|---|---|---|
| 01 Companies / addresses / contacts | 3 + 3 + 3 | known values |
| 01 Hierarchy levels | 12 | known values |
| 01 Alarm settings | 27 | known values |
| 01 Bill scenarios | 3 | **existence only** (`Present:true`) |
| 02 Providers / addresses / contacts / remit | 6 + 6 + 6 + 6 | known values |
| 02 Bill cycles | 162 | known values (2024-2025 only) |
| 02 Vendor associations | 14 | known values |
| 03 Company calendars | 72 | known values (2024-2025 only) |
| 04 Groups | 29 (+ copies derived in SQL) | known values |
| 04 Permissions | 255 (+ copies) | known values |
| 04 Scoped hierarchy | 2 | known values |
| 05 Users | 23 | known values (company, display name, email, type, policy, zone, inactive, IsAdmin) |
| 05 Memberships | 67 | known values |
| **Total** | **699 rows, 18 families** | 696 value assertions, 3 existence-only |

**Entered by Stage 1 but covered by no check:** provider Notes (23 lines, no family exists); level Purpose (never set); calendar and cycle rows outside 2024-2025; group Purpose text. Nothing proves login or that a level 1 or 2 grant blocks an action (header says "stored settings, not UI permission enforcement"). Stage 1's checker depends on Stage 2: the Ridgeline Points grants name node key `0.5.40`, which exists only after Stage 2 step 2.

### 1.5 Known VALUES a report or output must show

Stage 1 records none. The verification cases state expected effective scopes in words (Nora reads Northlake and Cedar Row; Quinn reads all three), but no value a report must render. `report-coverage-matrix.md` lists rp_BuildingList, rp_PointsList and rp_HierarchyDetailsEditor as Phase 0 (Stages 1 and 2), with no value attached. Records with no rendered expectation: all 6 providers, 3 calendars, 29 groups, 23 users.

### 1.6 Internal inconsistencies (Stage 1)

1. `04-groups-reconciliation.md` is a 2026-09-23 snapshot and is stale: 26 definitions, 20 masters, 6 local groups, 86 rows, "all 19 IsAdmin values", "other 16 planned users". The YAML has 29, 21, 8, 91, 23 users.
2. `01-companies.yaml` says saving a company creates "a 1990-2013 fiscal calendar"; `03-company-calendars.yaml` says the installed calendars run to 2026 or 2027 because Company_Save generates through next year.
3. `02-sites-and-buildings.yaml` (Stage 2) tells you to grant the Ridgeline scopes "waiting in Stage 1 (04-groups.yaml laterPermissions)". `laterPermissions` is `[]`; the grants are already in eem_ridgeline_research and ntp_wind_ops.
4. The Ridgeline Points grants hard-code node key `0.5.40` (04-groups; checks.sql lines 463, 625, 634) but the Ridgeline Wind Site has `installed.nodeId: null`, and Cedar Row C also has `nodeId: null` and is a later addition. If Cedar Row C is saved before the Ridgeline site, it takes the next node id and the Ridgeline site is not `.40`; the grants and the `04 Scoped hierarchy` check then fail. The key depends on entry order. INFERRED (database assigns the id).

### 1.7 Effects of the Stage 4 rates rework on Stage 1

- No Stage 1 file names an NL- rate, a renamed schedule or a rate-derived dollar amount (grep clean). Nothing breaks.
- Library Rates grants are category `*` (implementation admins and eem_rate_allocations level 3, others level 1), so the 16 real tariffs and the Rate Lab rates are covered. The "Library-rate levels" case needs one real rate; the 16 tariffs now qualify. Rate Lab rates are not enterable, so cannot serve the level-2 test.
- **Provider bill cycles end 2025-12.** Stage 4 now prices 2026-01-01 steps (3% for Valley Electric, Sierra Gas, River City, Thermal Plant). A 2026 bill has no period on any provider cycle (company calendars already reach 2026/2027). Also `checks.sql` filters cycles to 2024-2025.
- Valley Electric runs the 5th to the 4th; Sierra Gas and River City cycle 2 run the 15th to the 14th. The 2025-01-01 and 2026-01-01 price dates fall inside a period for these providers, so the first bill after each step straddles the change. Stage 4's own list (coverage review, line 146) still has "a bill that straddles it" as to-do. Stage 1 cycles are what make it happen.
- Provider descriptions remain accurate: Valley Electric "time-of-use charges and billing demand", Sierra Gas "monthly therms", Helios "per kWh generated, no demand charge".

### 1.8 Stage 12 scenarios for the Stage 1 area

1. **Year roll-over**: add next year's periods to every provider Bill Cycle and the Company Calendar. Could break: "Fiscal Year/Period NOT found" rejection; 2026 price steps never priced; Ridgeline's 18-period cycle versus 24.
2. **A provider changes its read date** (River City moves from the 15th to the 1st): new cycle number, meters moved to it. Could break: overlapping or missing days, a meter pointing to a cycle number the provider lacks, bill validation period-length tests.
3. **Employee leaves or changes role**: set a user Inactive, move memberships, toggle IsAdmin. Could break: alarm Notify User, report recipients, task owners, last company administrator removed.
4. **Edit a Common shared master** (add and remove a grant). Could break: copies out of sync, the Make-Local copy (Cedar Row) drifting, forbidden AR rows in shared groups.
5. **Customer adopts a July-1 or 13-period fiscal year**: change Fiscal Year Begin/Type, regenerate, copy. Could break: bills already posted to calendar periods, fiscal-year reports, quarters.
6. **New company after go-live** (acquisition): 21 shared copies with no members, default alarm colours, Actual scenario only. Could break: missing vendor associations, no calendar for first bills.
7. **A node-scoped group's node is re-parented or deleted** (Ridgeline Wind Site). The grant stores a MetaKey path. Could break: silent loss of scope, or scope to a dead path.
8. **Service account or API client created and rotated** (needs a non-Human principal). Could break: authentication-policy rules, API key display/copy, admin-role check.
9. **Provider adds or changes a remit address**. Could break: bill export remit line, account combo showing an address no longer on the provider.

---

## STAGE 2 HIERARCHY

### 2.1 What the stage sets up

| File | Screen | Records | What it exercises |
|---|---|---|---|
| 00-units.yaml | DB Admin > Units | 15 (5 new: Miles, W/m2, Events, ERU, Power Factor; 10 existing seeded units extended) | Class, label, measure-type associations (19 rows), 4 conversions (all offset 0) |
| 01-billing-accounts.yaml (+ .xlsx) | Nodes > company > Utility Accountant | 51 (32 NLU, 14 Cedar Row, 5 Thermal Plant) | Definitions, service/account address, account contact, status, 7 notes |
| 02-sites-and-buildings.yaml | Nodes (Site, Location) | 23: 5 sites, 16 buildings, 2 legacy airport nodes | Time zone, site/building code, address with lat/long, Area history, Keywords (Department, Meter Type), Notes, Status |
| 03-meters.yaml (+ .xlsx) | Nodes > Meter | 390 (67 on accounts, 320 owned, 3 weather stations) | Meter number, provider meter number, measure type (8 kinds), multiplier (4 non-blank), account, provider, bill cycle, keywords (77 meters), status, 8 notes |
| 04-points.yaml (+ .xlsx) | Nodes > Point | 474 (+203 generated children = 677) | Analog 266, Accumulator 197, Digital 11; 17 measure types; 31 units; intervals 1, 10, 15, 30, 60, 1440; Degree Days 3, Activity Level 1 |
| 05-weather-stations.yaml | Company > Definitions > Weather Stations | 3 companies, 16 assignments | KSAC 9 buildings, KSMF 5, KSUU 2 |
| 06-aggregates.yaml | Nodes (Create Aggregate Point) + Aggregates workspace | 11 aggregates, 172 members | Multiplier +1/-1, Required true/false |
| checks.sql | read-only | 2,522 rows, 28 families | |

Cross-reference test (I loaded the YAMLs): every meter's building exists; every account on a meter exists and its provider and company match the meter; every bill cycle on a meter exists on the provider; every point's meter exists; every aggregate member resolves to a point (172); every weather location is a building; all 56 Stage 4 assignment meters exist in 03-meters. No broken reference found.

### 2.2 Coverage gaps

**Units** (`DBAdmin/ViewModels/Units/*`)

| # | Gap | Mark |
|---|---|---|
| N1 | The 00-units header promises "conversions by multiplier and by offset" and a "compound unit built from a numerator and a denominator". All 4 offsets are 0. The only compound unit (mph) is an existing seeded unit; no new compound unit is created. | READ |
| N2 | Rate Unit, Numerator Unit and Denominator Unit are described but no new record sets any of them. | READ |
| N3 | Equivalent Runoff Unit (the "billing unit for a flat fee") is now named by nothing in Stage 4 or Stage 5 (2.7). | READ |
| N4 | The area control offers two units (ids 112 and 113, `DBAdmin/Services/AreaUnitLookup.cs`); only SqFt is used. | READ |
| N5 | Seeded measure types: I could not enumerate the seed. Meters use Electricity, Potable Water, Natural Gas, Steam, Weather, Chilled Water, Fuel Oil #2, Sensor. Product text (`Migrations/v7.0.0.sql` ~210671) also names Hot Water, Fuel Oil #6, Diesel, LPG with no recipe meter. | INFERRED |

**Billing accounts** (`DBAdmin/ViewModels/Companies/BillAccountViewModel.cs`, `Models/Companies/BillAccountModel.cs`)

| # | Gap | Mark |
|---|---|---|
| A1 | Currency Unit US Dollar on 51 of 51. The editor starts at Australian Dollar and has a currency list. No non-USD account. | READ |
| A2 | Status: every account has one row, Active Billing Account, dated 2024-01-01 (49) or 2024-07-01 (2). No inactive or closed account, no status history longer than one. | READ |
| A3 | Bill Service Type uses all 3 values; Bill Entry Type 4 of 5 ("Other" unused, documented); invoice template 2 of 2. | READ |
| A4 | Liability and Default Expense account at defaults (Stage 6). Payment terms, cycle day, balance, remit contact, bill-review contact and bank account have columns and no field (PRODUCT FINDING 34, in the YAML). | READ |
| A5 | Account Address lat/long on 1 of 51; Previous Account Number on 2; Notes on 7; Account Contact missing on 1 (documented). | READ |

**Sites and buildings** (`DBAdmin/ViewModels/Nodes/NodeDefinitionsViewModel.cs`, `Controls/AreaViewModel.cs`, `KeywordsViewModel.cs`)

| # | Gap | Mark |
|---|---|---|
| S1 | **Node Contact page is never filled** for any site or building. The editor registers it (`NodeDefinitionsViewModel.cs`, `_contactPage`); no site record has a contact key. | READ |
| S2 | Time Zone Pacific on all 21 nodes; the editor offers all zones and Propagate Time Zone. | READ |
| S3 | Status: 16 of 16 buildings Open; no closure or change over time. | READ |
| S4 | Area: one history row per building (dated 2026-09-15 for 11, 2025-09-01 for Cedar Row C); SqFt only. No area change over time. `MetaWorld_TBL.Area` is empty (PRODUCT FINDING 36). | READ |
| S5 | Keywords: two types on nodes (Department on 4 sites, Meter Type on 3 buildings). Notes on 6 of 23 nodes. | READ |
| S6 | Hierarchy Filters, node copy (`NodeCopyOptionsDrawerViewModel.cs`), node move and the Bulk tabs (`BulkNodeWorkspaceViewModel.cs`, `BulkAreaViewModel.cs`, `BulkKeywordsViewModel.cs`, `BulkIntervalDataViewModel.cs`) are not part of any hand-entry step. The bulk tabs may be used by the workbook import. | INFERRED |

**Meters** (`DBAdmin/ViewModels/Nodes/Definitions/MeterDefinitionViewModel.cs`)

| # | Gap | Mark |
|---|---|---|
| M1 | The editor's seven fields (meter number, provider meter number, measure type, multiplier, account, provider, bill cycle) are all set somewhere. Multiplier is blank on 386 of 390 (values 40, 10, 3.0367, 12000). Provider Meter Number blank on 335. | READ |
| M2 | Meter statuses used: Open and Closed - Ex (one meter). MPA help text names Obsolete and Removed as further statuses (`Database/EEMSuite/Schemas/MPA/Scripts/MPA.HelpGuides.sql:254`); unused. | READ |
| M3 | No meter changes provider, account or cycle over time; only the Library replacement has a second status row. | READ |
| M4 | Rate assignment is the meter's Tenant Rebill page and is Stage 4 (`06-rate-assignments.yaml`), not a Stage 2 gap. | READ |

**Points** (`DBAdmin/ViewModels/Nodes/Definitions/PointDefinitionViewModel.cs`, `PointAlarmDefinitionViewModel.cs`, `DBAdmin/Views/Nodes/Definitions/PointDefinitionView.xaml`)

| # | Gap | Mark |
|---|---|---|
| T1 | Stage 2 sets 6 point fields (Description, Reading Type, Measure Type, Unit, Index, Archive Interval). The editor also has **Delta Multiplier** for registers (`PointDefinitionView.xaml:331`; always 1, Stage 3 only tests changing it), **Associations** (Stage 3, weather forecast only), Baseline (Stage 3), Gateway (Stage 3) and the **Point Alarm page** (Stage 9). | READ |
| T2 | Point Alarm fields (Stage 9, `02-alarms.yaml`): 15 alarms; Activation always Normal; Alarm Type always default; High Alarm on 3, High Warning on 3, Low Alarm 1, Low Warning 1, Deadband 4. Handheld register High/Low Warning went into Stage 3 on 2026-11-09. Of 474 Stage 2 points, none carries alarm limits at entry. | READ |
| T3 | Index: Degree Days on 3 and Activity Level on 1 of 474. | READ |
| T4 | Natural Gas has 2 points and Steam 2, against 10 gas and 7 steam meters. Gas and steam consumption is mostly bill facts, not points. 37 meters have no point. | READ |
| T5 | Only 1 point sits directly under a building (Student Center Event Count). | READ |

**Weather stations** (`DBAdmin/ViewModels/Companies/Definitions/WeatherStationViewModel.cs`)

| # | Gap | Mark |
|---|---|---|
| W1 | One station per node, never changed. No Delete Associations (`WeatherStationMap_Del`) case. | READ |

**Aggregates** (`DBAdmin/ViewModels/Commodity/Aggregates/AggregateDetailViewModel.cs`, `Models/Controls/AggregatePointModel.cs`, `Tables/PointAggregates_TBL.sql`, `PointAggregatePoints.sql`)

| # | Gap | Mark |
|---|---|---|
| X1 | Member Multiplier only +1 (170) and -1 (2). `PointAggregatePoints.Multiplier` is real; no fractional or loss-factor weight. | READ |
| X2 | Measure types: Electricity 10, Chilled Water 1. No water, gas, steam or weather aggregate. Intervals 10, 15, 60 only. | READ |
| X3 | `PointAggregates_TBL` has `Formula` and `DayBeginsAtLocalHour`. The model and repository carry `DayBeginsAtLocalHour`; I found no desktop control for either. | INFERRED |
| X4 | Recalculate fails for every aggregate (PRODUCT FINDING 14, documented). | READ |

### 2.3 Fields in the YAML that are always empty, null or default (Stage 2)

- 00-units: every `Offset: 0`; `installed.unitId` blank.
- 01-accounts: Currency US Dollar 51/51; Status Active Billing Account 51/51; address lat/long 1 of 51.
- 02-sites: `Area: null` on 9; Time Zone identical on 21; Site Code null on 4 of 5 sites; Building Code null on 8 of 16.
- 03-meters: Multiplier blank 386/390; Provider Meter Number blank 335; Billing Account, Provider, Bill Cycle blank on 323.
- 04-points: Index blank on 470 of 474.
- 06-aggregates: Multiplier 1 or -1.

### 2.4 Depth of checks.sql (Stage 2)

Same generator and style: no PRINT-only checks.

| Family | Rows | Kind |
|---|---|---|
| 00 Units / measure types / conversions | 5 / 19 / 4 | known values (units compare label and class only) |
| 01 Billing accounts | 51 | known values |
| 01 Service addresses / account addresses / remit / contacts | 51 x 4 | known values |
| 01 Account status | 51 | known values (first-active date, current status) |
| 01 Account notes | 7 | **existence only** |
| 02 Sites and buildings / node addresses | 21 / 21 | known values |
| 02 Floor areas | 12 | known values (area, unit; no date) |
| 02 Building status | 16 | known values |
| 02 Department keywords / node keywords | 20 / 3 | known values |
| 02 Node notes | 6 | **existence only** |
| 03 Meters | 390 | known values (14 fields) |
| 03 Meter keywords / status | 415 / 391 | known values |
| 03 Meter notes | 8 | **existence only** |
| 03 Meter integrity | 1 | zero-count assertions |
| 04 Points | 474 | known values (9 fields) |
| 04 Generated children | 203 | known values |
| 04 Point integrity | 1 | zero-count assertions |
| 05 Weather stations | 16 | known values |
| 06 Aggregates / members | 11 / 172 | known values |
| **Total** | **2,522 rows, 28 families** | 2,498 value assertions, 21 note-existence rows, 2 integrity rows, 1 other |

**Entered by Stage 2 but covered by no check:** unit numerator/denominator/rate unit (the YAML sets them for mph; the check compares label and class); floor-area as-of dates and node/meter status as-of dates (account first-active is checked) (INFERRED from the field lists); note text (presence only); the `.xlsx` workbooks. The checks.sql header counts are stale (2.6).

### 2.5 Known VALUES a report or output must show

Mostly none. The only recorded report-linked value is the 11 building floor areas, and the YAML says the report column (`MetaWorld_TBL.Area`, read by rp_BuildingList, rp_BenchMark, rp_IndexList, rp_ProjectSummary) is empty on every building (finding 36), so what the report should show is "record what it shows", not a known value. Aggregate outputs have none (finding 14). Meter multipliers (40, 10, 3.0367, 12000) are inputs with a computable effect, but no output value is recorded in Stage 2. Records with no known value: all 51 accounts, 386 of 390 meters, all 11 aggregates, 16 weather assignments, all 15 units.

### 2.6 Internal inconsistencies (Stage 2)

1. `checks.sql` header: "336 meters", "397 entered points", "15 buildings", "15 weather assignments", "4 custom units", "537 ordinary points (548 once complete)". YAML and chapter: 390, 474, 16, 16, 5, 677. (336 = 390 minus the 54 handheld meters.)
2. Chapter `stage-2-hierarchy.md` line 26 says "plus four units"; `00-units.yaml` has five new units.
3. `03-meters.yaml` notes say "3 weather-station meters" in the first note and "The 2 weather-station meters (KSAC, KSMF)" later. KSUU came with Ridgeline. Weather measure type count is 4 (three stations + met mast).
4. `00-units.yaml` header promises an offset conversion and a new compound unit; neither exists (N1).
5. `02-sites-and-buildings.yaml` says "The 11 buildings with a floor area"; 12 area rows exist (11 + Cedar Row C).
6. See 1.6 items 3 and 4 (`laterPermissions` and `0.5.40`).

### 2.7 Effects of today's Stage 4 rates rework

1. **Equivalent Runoff Unit** (`00-units.yaml`, `equivalent_runoff_unit`, 1 ERU = 2,500 sq ft). Its note says "used by Stage 4 rates and Stage 5 bill lines". After the rework stormwater is a User Defined per-meter price (for example 18 ERUs), and no stage YAML names the unit (grep of `stage-*/`: only stage-2 files). It and its conversion check are orphaned. READ.
2. **Per-meter quantities** (48 and 20 fixtures, ERU counts, plant fixed share by floor area) and River City meter/line size (2-, 3-, 4-inch; 4-, 6-, 8-inch) exist only on the Stage 4 Tenant Rebill pages. Stage 2 meters carry no fixture count, ERU count or size. No Stage 2 source or keyword for them. INFERRED.
3. **Fixed O&M Share by floor area** (Thermal Plant) depends on the building floor area, held in Stage 2 Area history, while `MetaWorld_TBL.Area` is empty (finding 36). Which area the engine reads is not visible from Stage 2.
4. **Bill cycles**: meters carry only a cycle number. The 5th and 15th cycles straddle the 2025-01-01 and 2026-01-01 price steps; provider cycles stop at 2025-12 (1.7).
5. **Billing Charges Report template**: the six Thermal Plant cost centers and Ridgeline's transfer account use it "because their charges come from the plant's allocation rate schedules". After the rework those are NTP-ALLOC-CHW, NTP-ALLOC-STEAM and RWL-XFER-2024. The sentence still holds.
6. **Meter references**: all 56 Stage 4 assignment meters exist in 03-meters. 11 account-bearing meters have no rate: the ten Ridgeline pad meters (rate on the transfer meter) and the replaced Library meter. Both documented.
7. The 16 tariffs by provider: Valley Electric 5, River City 5, Sierra Gas 2, Thermal Plant 2, Helios 1, Ridgeline 1. Each provider has at least one meter in 03-meters. No dangling provider.
8. `northlake-inventory-standard.md` line 36 mentions `VED-TOU-GS-FY25` (drift table); the reworked rates hold `VED-TOU-GS` only. Cosmetic. Schedules renamed: no Stage 1 or 2 file names one.

### 2.8 Stage 12 scenarios for the Stage 2 area

1. **Building sold, closed or demolished**: set the building Closed with a date, close its meters and account. Could break: building lists, bill tracking for an open account, aggregates that hold its meters as Required members, weather assignment.
2. **Floor area changes after a renovation** (new Area row, or SqFt to SqM). Could break: EUI and benchmark by date, the plant's fixed share by area, `MetaWorld_TBL.Area` overwritten by a Definitions save (finding 36).
3. **A meter moves to a different account or provider** (customer switches supplier; River City renumbering like Cedar Row A). Could break: stored cycle number versus new provider's cycles, rate assignment on the old provider, account-opening validation.
4. **Weather station reassigned** (KSAC outage; campus to KSMF). Could break: HDD(F)/CDD(F) versus (C) children, baselines, weather regression, forecast associations.
5. **Move a building to another site or company**. Could break: node-scoped Points keys, inherited Department keyword, account company versus building company.
6. **Meter multiplier changes after a CT/PT upgrade** (Lab Wing 40 to 80). Could break: whether history is rescaled, aggregates holding that point, bills already posted.
7. **Wrong point type found after data exists** (a register locks after first save: delete and re-enter). Could break: lost history, generated Delta child, aggregate membership, alarms.
8. **60 new submeters added to an aggregate** (Cedar Row template). Could break: eligibility (same unit, interval, zone), Recalculate failing (finding 14), partial member data.
9. **Customer adds a Floor/Room level after go-live**. Could break: existing nodes at fixed levels, icons and UDF names, group scopes by MetaKey.
10. **A unit conversion is corrected** (ERU size, PSIG gauge factor, finding 37) after readings exist. Could break: stored versus displayed values, report unit preferences.

---

## What I could not check

- The exact user-editor field list (language, notes, contact): inferred from `Users_TBL.sql` and an empty search of `src`.
- Seeded MeasureType, Unit and Status code lists: not enumerated (they live in migrations); gaps N5 and M2 rest on text in help guides and migrations.
- The web provider and calendar pages beyond `viewCompanyCalendar.ts`.
- `.xlsx` workbooks, PDFs, and the Northlake import path (`Database/EEMSuite/Schemas/Northlake/Stage2Import`): not opened.
- Whether the installed Northlake database matches the YAML (no database access allowed).
