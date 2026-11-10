# Report Coverage Matrix (all 119 reports)

Every report in EEMSuite, mapped to its data-capability bucket, its **current**
coverage by Northlake, the **phase** that closes the gap and the **expected
value** a stage already records for it. Phases map onto the build stages in the
[roadmap](roadmap.pdf): Phase 0 is Stages 1 and 2, Phase 1 is Stages 3 and 5,
Phase 2 is Stage 4, Phase 3 is Stage 6, Phase 4 is Stage 7, Phase 5 is Stage 8
and Phase 6 is Stage 9. Where a screen cannot create the data a report needs,
the gap is in [product findings](product-findings.pdf).

**Reconciled 2026-11-10** against the product source (branch
feature/Northlake_NewStage3), not a database: the report manifest in
`Database\EEMSuite\Scripts\SeedReportTags.sql` (92 data reports), the
`Add*Report.sql` registration scripts, `AddSystemHealthModule.sql` (which put
nine pages in a new System Health module, eight of them moved out of System Manager
and System Administration, and moved the five GHG setup pages beside the GHG reports) and
`RetireAuditReport.sql`. Changes since the 115-row list: **rp_Audit retired**
(replaced by Audit Explorer, `audit_explorer`, procedure `rp_AuditExplorer`);
**five reports added** (`audit_explorer`, `rp_IntervalIntakeFlow`,
`rp_BenchmarkScene`, `rp_BillScene`, `rp_SpendScene`); the section headings now
add up to the rows. Seven earlier rows are in no Database script and appear only
in front-end language and overview resources (`cst_smartgrid`, `Data_Validation`,
`emission_company_config`, `emission_meter_assign`, `laco_dash_trending`,
`rp_RegressionSummaryReport2`, `admin_reportconfig`): they are kept, and each is
a candidate for removal once someone confirms it in a live `GuiReports_Tbl`.

**Status (current):** 🟢 data design already covers it (once loaded) · 🟡 partial
(needs additions, e.g. charge lines / digital points / benchmark config) · 🔴 no
data today.

**Expected value** is the value a stage's YAML or checks already state for that
report, with the stage that states it; `none yet` means no stage records a value
for it (47 of 119 have one). Many are counts or qualitative shapes, not
dollars; the stage's `checks.sql` is where each is asserted.

`MFR` = report can be saved and scheduled for delivery (`AllowMFR`, default 1).
The earlier count of 92 was not re-verified; Stage 9 delivers 5.

---

### Bill Management (5)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| bill_entry | bill entry screen | 🟡 | 1 | none yet |
| bill_importer | importer screen | 🔴 | 6 | none yet |
| cst_smartgrid | custom grid | 🟡 | 1 | none yet |
| rp_BillEntryList | bills + accounts | 🟡 | 1 | none yet |
| scriptstring_dashboard | custom embed | 🟡 | 1 | none yet |

### Bill Processing (12)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_AccountDetail | account metadata | 🟢 | 1 | none yet |
| rp_AccountHistory | monthly bills | 🟢 | 1 | Ridgeline generator account SYN-VED-A-0010014: 17 bills, the first 2024-07-01 to 2024-08-04 at 1,077.45 (Stage 5) |
| rp_AccountSummary | account metadata | 🟢 | 1 | none yet |
| rp_FiscalPeriodBills | monthly bills | 🟢 | 1 | 24 bills per account that existed in January 2024, 23 for the Library gas account (Stage 5) |
| rp_billdatagaps | bill data gaps | 🟢 | 1 | none yet |
| rp_DailyProcessingSummary | bills + status history | 🟡 | 1 | none yet |
| rp_LateBills | bills + status history | 🟡 | 1 | one late bill, the Library gas fixture (Stage 5) |
| rp_AccountsPayableDetail | AP / financial interface | 🔴 | 3 | none yet |
| rp_APApprovalAndUpload | AP approval + upload | 🔴 | 3 | empty today: no export format can be registered (Stage 6 finding) |
| rp_BillValidation | bill validation | 🔴 | 3 | none yet (Stage 5 enters 8 global tests and 5 account overrides, no results) |
| rp_OpenAccruals | accruals | 🔴 | 3 | none yet |
| rp_BillScene | bills (scene) | 🟡 | 1 | none yet |

### Bill Tracking (11)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_BillHistory | monthly bills | 🟢 | 1 | generator 2024-07-01 to 2024-08-04 1,077.45; Central Plant 2024-08-05 to 2024-09-04 151,171.47; generator 2025-01-05 to 2025-02-04 6,753.10 (Stage 5); Ridgeline July 2024 statement 129,330.27 (Stage 7) |
| rp_BillVariance | monthly bills | 🟢 | 1 | none yet |
| rp_BillVarianceAnalysis | monthly bills | 🟢 | 1 | none yet |
| rp_BillVarianceDetail | monthly bills | 🟢 | 1 | none yet |
| rp_BillVarianceRanking | monthly bills | 🟢 | 1 | none yet |
| rp_FacilityAccountDetail | bills + account | 🟢 | 1 | none yet |
| rp_CostBreakOut | bills (charge lines) | 🟡 | 1 | none yet |
| rp_BenchmarkRanking | benchmarks | 🟡 | 5 | the 12-building peer set ranked, Science Center (lab) highest (Stage 8, Stage 10) |
| rp_PerformanceSnapshot | bills + benchmark | 🟡 | 5 | none yet |
| rp_BenchmarkScene | benchmarks (scene) | 🟡 | 5 | the same ranking as rp_BenchmarkRanking |
| rp_SpendScene | bills by commodity (scene) | 🟡 | 1 | none yet |

### Use Analysis (15)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_TimeInterval | interval | 🟢 | 1 | one AcquiSuite day: 96 rows per Student Center point, kWh sums 2,020, kW peaks at 120 (Stage 3) |
| rp_24HourLineChart | interval | 🟢 | 1 | none yet |
| rp_MultiPointTrend | interval | 🟢 | 1 | WTG-07 generated energy zero from 2025-02-11 to 2025-04-22 (Stage 9, qualitative) |
| rp_HeatMap | interval | 🟢 | 1 | none yet |
| rp_LoadDurationCurve | interval | 🟢 | 1 | none yet |
| rp_Histogram | interval | 🟢 | 1 | none yet |
| rp_ScatterPlot | interval (+ regression) | 🟢 | 1 | ten Ridgeline power curves; WTG-07 stacked on zero power 2025-02-11 to 2025-04-22 (Stage 9, qualitative) |
| rp_Summary | interval | 🟢 | 1 | none yet |
| rp_AverageHourlyProfile | interval | 🟢 | 1 | none yet |
| rp_DataViewExport | interval | 🟢 | 1 | none yet |
| rp_MonthlyEUI | interval + area | 🟢 | 1 | Science Center highest (Stage 10) |
| rp_UsageVariance | interval (+ weather) | 🟢 | 1 | none yet |
| rp_AggregateDemand | aggregate demand | 🟢 | 1 | Ridgeline aggregates with 10, 10, 10 and 2 required members (Stage 3) |
| rp_AggregatePeakLoad | aggregate demand | 🟢 | 1 | none yet |
| rp_DigitalSummary | digital interval | 🟡 | 1 | none yet |

### Rate Analysis (9)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_RateSummary | rate components | 🟡 | 2 | 16 rates across 6 providers: VED 5, SGU 2, RCU 5, NTP 2, HOS 1, RWL 1 (Stage 4) |
| rp_RateMeterInformation | rate + meter assignment | 🟡 | 2 | none yet |
| rp_RateMeterAssignment | rate + meter assignment | 🟡 | 2 | 74 Rate Config rows on 56 meters (Stage 4) |
| rp_CostSummary | rate calc | 🟡 | 2 | none yet |
| rp_BillingCharges | rate execution (calc) | 🔴 | 2 | none yet |
| rp_RateAllocation | rate calc | 🔴 | 2 | none yet |
| rp_RateClassAssignment | rate class options | 🔴 | 2 | 16 ClassType 0 rows and 9 ClassType 1 rows (Stage 4) |
| rp_RateComparison | shadow billing | 🔴 | 2 | none yet |
| rp_RatePointAssignment | rate + point | 🔴 | 2 | none yet |

### Tenant Rebilling (14)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_BillAllocationConfiguration | bill allocation | 🔴 | 4 | Town Center 8 configurations, Cedar Row 4, Thermal Plant recovery 2 (Stage 7) |
| rp_TenantBillAllocationMap | bill allocation | 🔴 | 4 | Mall-Main allocated amounts add to the master bill, overhead 2% (600.00 of 30,000.00) (Stage 7) |
| rp_TenantBillDefinition | bill allocation | 🔴 | 4 | none yet |
| rp_TenantBillAudit | bill allocation | 🔴 | 4 | none yet |
| rp_BillGenerationConfig | bill generation | 🔴 | 4 | Town Center Off 1, Manual 1, Auto 1, Auto w/ Auto Regen 2; Thermal Plant Auto 1 (Stage 7) |
| rp_GeneratedBills | bill generation | 🔴 | 4 | Shop 1 878.28 and Shop 2 669.96 (2026-01); Ridgeline July 2024 129,330.27 (Stage 7); kiosk K1 seven bills 628.72, 464.28, 793.08, 764.56, 684.72, 417.16, 576.04 (Stage 12) |
| rp_BillMaintenance | bill generation | 🔴 | 4 | none yet |
| rp_BillReconciliation | reconciliation | 🔴 | 4 | Anchor Store billed 2,040.00 in 2024-01 and 2025-01 (Stage 7) |
| rp_RateComponentMap | commodity map | 🔴 | 4 | none yet |
| rp_WUIPointFamilyConfig | WUI point allocation | 🔴 | 4 | 12 child points: Weighted Use Index 9, Measured Use 2, Percentage Based 1 (Stage 7) |
| rp_WUIPointUseHistory | WUI point allocation | 🔴 | 4 | index Shop 3 0.40, Shop 4 0.50, Common Area 0.15, Landlord/House 0.90 (Stage 7) |
| rp_WUIProcessMeterAllocations | WUI point allocation | 🔴 | 4 | 2024-01 Shop 3 26,318.37, Shop 4 25,306.12, Common Area 134,375.51, Landlord/House 230,640 kWh (Stage 7) |
| rp_accruals | accruals | 🔴 | 4 | none yet |
| rp_mpaaccruals | accruals | 🔴 | 4 | none yet |

### Energy Star Rating (5)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| facility_setup | ES facility setup screen | 🟡 | 5 | 13 properties (Stage 8) |
| new_rating_request | ES request screen | 🔴 | 5 | quarterly requests for Lakeview Hall and Cedar Row Apartments, single requests for Admin Hall, Science Center, Central Plant (Stage 8) |
| rp_ESRatingComparison | ES rating responses | 🔴 | 5 | none yet; scores arrive only once Portfolio Manager is connected (Stage 8) |
| rp_ESRatingHistory | ES rating responses | 🔴 | 5 | 13 properties; Lakeview Hall and Cedar Row Apartments carry a score once Portfolio Manager is connected (Stage 10) |
| rp_ESRatingRequestLog | ES rating responses | 🔴 | 5 | none yet |

### Green House Gas (8)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_GHGHistory | GHG emissions | 🔴 | 5 | 34 assigned meters (16 electric, 10 gas, 8 water); Ridgeline Interconnection Meter 2024-08, 4,428 kWh (Stage 8) |
| rp_GHGVariance | GHG emissions | 🔴 | 5 | 2024 against 2025 differs: four factors each with 2024-01-01 and 2025-01-01 dated rows (Stage 8) |
| rp_GHGAudit | GHG emissions | 🔴 | 5 | none yet |
| emission_company_config | GHG config screen | 🔴 | 5 | 3 rows, companies 6, 3 and 5, base years 2024 to 2025 (Stage 8) |
| emission_factor | GHG config screen | 🔴 | 5 | 4 factors, each with a 2024-01-01 and a 2025-01-01 row (Stage 8) |
| emission_meter_assign | GHG config screen | 🔴 | 5 | 34 assigned meters; the 10 Ridgeline turbines Excluded (Stage 8) |
| emission_source | GHG config screen | 🔴 | 5 | eGRID / CAMX and Non-electric commodities (Stage 8) |
| emission_type | GHG config screen | 🔴 | 5 | none yet |

### Project Tracking (5)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_ProjectDetail | project financials | 🔴 | 6 | 5 projects, capital cost / incentives 120,000 / 25,000; 640,000 / 80,000; 410,000 / 123,000; 55,000 / 10,000; 310,000 / 0 (Stage 9) |
| rp_ProjectSummary | project financials | 🔴 | 6 | the same 5 projects (Stage 9) |
| rp_ProjectFinance | project financials | 🔴 | 6 | the same capital cost and incentive dollars (Stage 9); event values none yet |
| rp_ProjectTrackingConfiguration | project config | 🔴 | 6 | none yet |
| rp_ApplyRateSchedule | rate history + project | 🔴 | 6 | none yet: no stage links a project to a rate change |

### System Manager (12)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_BuildingList | hierarchy + premise | 🟢 | 0 | none yet |
| rp_PointsList | points inventory | 🟢 | 0 | none yet |
| rp_IndexList | index points | 🟢 | 1 | none yet |
| rp_HierarchyDetailsEditor | hierarchy editor | 🟢 | 0 | none yet |
| Data_Validation | bill/interval cross-check | 🟡 | 1 | none yet |
| rp_ImageManagement | images | 🟡 | 1 | none yet |
| rp_GLAccountUDV | AP / GL | 🔴 | 3 | none yet |
| my_exports | export log | 🔴 | 3 | none yet |
| rp_BillValidationStatus | bill validation | 🔴 | 3 | none yet |
| rp_TenantMap | tenant allocation | 🔴 | 4 | none yet |
| rp_weatherregression | weather regression | 🔴 | 5 | 4 regressions: Science Center electric, Student Center demand, Admin Hall gas, Central Plant chilled water (Stage 8) |
| my_imports | import log | 🔴 | 6 | Loss Factor Import definition with handler MyImportToLossFactors_Save; the six unimplemented methods absent (Stage 9 step 7) |

### System Health (10)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_PointDataMap | points inventory | 🟢 | 1 | none yet; 258 direct points and Ridgeline's 73 are bound (Stage 3) |
| rp_NoteHistory | notes | 🟡 | 1 | none yet |
| rp_GatewayStatus | gateway / live status | 🟡 | 6 | 12 acquisition gateways, 26 nodes, 258 direct points (Stage 3) |
| rp_TaskLog | task logs | 🔴 | 6 | 1 or more finished TaskRun rows once the enabled schedules have run (Stage 9 step 4) |
| rp_ActivityTracker | activity logs | 🔴 | 6 | 8 users with 1 or more sign-in; casey.holt 0; elena.vasquez and kai.nakamura on Ridgeline reports only (Stage 9 step 3) |
| rp_AlarmDataMap | alarms | 🔴 | 6 | 15 alarm definitions (1 Disabled, WTG-07 Suspended); WTG-07 Fault 2025-02-11, severity 3 (Stage 9 step 2) |
| log_analysis | log screen | 🟡 | 6 | none yet |
| job_scheduler | tasks dashboard | 🟡 | 6 | 6 Task Library schedules and 13 maintenance entries, 12 enabled (Stage 9 step 4) |
| audit_explorer | audit entries | 🔴 | 6 | 4 entries by jordan.hale: Bill 1 or more, BillingAccount 1 or more, Meter 2 or more; none by casey.holt (Stage 9 step 3) |
| rp_IntervalIntakeFlow | interval intake runs | 🟡 | 1 | none yet |

System Health is the module `AddSystemHealthModule.sql` creates for the pages that watch the
system run and look back: audit, data feeds and alarms, jobs and logs. Its pages were System Manager
(and, for Job Scheduler, System Administration) pages in the earlier list.

### My Reports (5)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| rp_monthlyutilitydistributionreport | monthly bills | 🟢 | 1 | none yet |
| rp_meterevents | meter events | 🟡 | 1 | none yet |
| rp_cngtestreportcgr | bills (custom CNG) | 🟡 | 1 | none yet |
| rp_RegressionSummaryReport2 | weather regression | 🔴 | 5 | 4 regressions as rp_weatherregression (Stage 8) |
| rp_EnergyAIInsights | EnergyAI insights | 🔴 | 6 | 0 rows: no enrolment screen (Stage 9 finding) |

### System Administration (7)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| admin_reportconfig | config screen | 🟢 | 0 | none yet |
| admin_reportxmlconfig | language/config screen | 🟢 | 0 | none yet |
| company_calendar | calendar screen | 🟢 | 0 | none yet |
| user_editor | user screen | 🟢 | 0 | none yet |
| rp_AnonymizeData | admin tool | 🟢 | 0 | none yet |
| rp_HMRConfiguration | HMR | 🟡 | 6 | 192 meters, 204 registers on 11 routes (Stage 3, Stage 9 step 7) |
| hmr_export | HMR | 🟡 | 6 | the same 192 meters and 204 registers (Stage 9 step 7) |

HMR configuration is entered once in Stage 3. Stage 9 reuses it for the reader round, native-file
return, stored-history and exception-review exercises described in the handheld environment plan.
The legacy phase number above is a report-category mapping, not a second setup instruction.

### Modules (1)

| Report | Bucket | Status | Phase | Expected value |
| --- | --- | --- | --- | --- |
| laco_dash_trending | custom dashboard (interval) | 🟡 | 6 | none yet |

---

## Tally by phase

| Phase | Reports in it | What it closes |
| --- | --- | --- |
| 0 Foundation | 8 | substrate and configuration screens render |
| 1 Consumption and cost | 44 | consumption and cost: Use Analysis, Bill Processing and Tracking core, inventory, distribution, scenes |
| 2 Rate engine | 9 | Rate Analysis |
| 3 AP / GL and validation | 7 | AP / GL and validation |
| 4 Tenant rebilling | 15 | tenant rebilling |
| 5 Sustainability and analytics | 18 | sustainability and analytics: GHG, ES Rating, regression, benchmarks, emission setup screens |
| 6 Operations and engagement | 18 | operations and engagement: projects, alarms, audit and activity, tasks, gateway and log pages, HMR, EnergyAI, importers, custom dashboards, plus the MFR delivery layer |
| Total | 119 | 36 🟢, 30 🟡, 53 🔴 |

> The phase a report is listed under is where its *data* first becomes non-empty.
> Many reports also gain depth in later phases (e.g. ScatterPlot/UsageVariance get
> weather-normalization in Phase 5; bills get GL coding in Phase 3).
