# Report Coverage Matrix (all 115 reports)

Every report in EEMSuite (`dbo.GuiReports_Tbl` ⋈ `dbo.GuiReportTypes`), mapped to
its data-capability bucket, its **current** coverage by Northlake, and the
**phase** that closes the gap. See [`roadmap.md`](roadmap.md) for phases and
[`subsystem-gap-analysis.md`](subsystem-gap-analysis.md) for the buckets.

**Status (current):** 🟢 data design already covers it (once loaded) · 🟡 partial
(needs additions, e.g. charge lines / digital points / benchmark config) · 🔴 no
data today.

`MFR` = report can be saved & scheduled for delivery (`AllowMFR=1`); 92 of 115.

---

### Bill Management (5)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| bill_entry | bill entry screen | 🟡 | 1 |
| bill_importer | importer screen | 🔴 | 6 |
| cst_smartgrid | custom grid | 🟡 | 1 |
| rp_BillEntryList | bills + accounts | 🟡 | 1 |
| scriptstring_dashboard | custom embed | 🟡 | 1 |

### Bill Processing (12)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_AccountDetail | account metadata | 🟢 | 1 |
| rp_AccountHistory | monthly bills | 🟢 | 1 |
| rp_AccountSummary | account metadata | 🟢 | 1 |
| rp_FiscalPeriodBills | monthly bills | 🟢 | 1 |
| rp_billdatagaps | bill data gaps | 🟢 | 1 |
| rp_DailyProcessingSummary | bills + status history | 🟡 | 1 |
| rp_LateBills | bills + status history | 🟡 | 1 |
| rp_AccountsPayableDetail | AP / financial interface | 🔴 | 3 |
| rp_APApprovalAndUpload | AP approval + upload | 🔴 | 3 |
| rp_BillValidation | bill validation | 🔴 | 3 |
| rp_OpenAccruals | accruals | 🔴 | 3 |

### Bill Tracking (9)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_BillHistory | monthly bills | 🟢 | 1 |
| rp_BillVariance | monthly bills | 🟢 | 1 |
| rp_BillVarianceAnalysis | monthly bills | 🟢 | 1 |
| rp_BillVarianceDetail | monthly bills | 🟢 | 1 |
| rp_BillVarianceRanking | monthly bills | 🟢 | 1 |
| rp_FacilityAccountDetail | bills + account | 🟢 | 1 |
| rp_CostBreakOut | bills (charge lines) | 🟡 | 1 |
| rp_BenchmarkRanking | benchmarks | 🟡 | 5 |
| rp_PerformanceSnapshot | bills + benchmark | 🟡 | 5 |

### Use Analysis (15)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_TimeInterval | interval | 🟢 | 1 |
| rp_24HourLineChart | interval | 🟢 | 1 |
| rp_MultiPointTrend | interval | 🟢 | 1 |
| rp_HeatMap | interval | 🟢 | 1 |
| rp_LoadDurationCurve | interval | 🟢 | 1 |
| rp_Histogram | interval | 🟢 | 1 |
| rp_ScatterPlot | interval (+ regression) | 🟢 | 1 |
| rp_Summary | interval | 🟢 | 1 |
| rp_AverageHourlyProfile | interval | 🟢 | 1 |
| rp_DataViewExport | interval | 🟢 | 1 |
| rp_MonthlyEUI | interval + area | 🟢 | 1 |
| rp_UsageVariance | interval (+ weather) | 🟢 | 1 |
| rp_AggregateDemand | aggregate demand | 🟢 | 1 |
| rp_AggregatePeakLoad | aggregate demand | 🟢 | 1 |
| rp_DigitalSummary | digital interval | 🟡 | 1 |

### Rate Analysis (9)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_RateSummary | rate components | 🟡 | 2 |
| rp_RateMeterInformation | rate + meter assignment | 🟡 | 2 |
| rp_RateMeterAssignment | rate + meter assignment | 🟡 | 2 |
| rp_CostSummary | rate calc | 🟡 | 2 |
| rp_BillingCharges | rate execution (calc) | 🔴 | 2 |
| rp_RateAllocation | rate calc | 🔴 | 2 |
| rp_RateClassAssignment | rate class options | 🔴 | 2 |
| rp_RateComparison | shadow billing | 🔴 | 2 |
| rp_RatePointAssignment | rate + point | 🔴 | 2 |

### Tenant Rebilling (14)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_BillAllocationConfiguration | bill allocation | 🔴 | 4 |
| rp_TenantBillAllocationMap | bill allocation | 🔴 | 4 |
| rp_TenantBillDefinition | bill allocation | 🔴 | 4 |
| rp_TenantBillAudit | bill allocation | 🔴 | 4 |
| rp_BillGenerationConfig | bill generation | 🔴 | 4 |
| rp_GeneratedBills | bill generation | 🔴 | 4 |
| rp_BillMaintenance | bill generation | 🔴 | 4 |
| rp_BillReconciliation | reconciliation | 🔴 | 4 |
| rp_RateComponentMap | commodity map | 🔴 | 4 |
| rp_WUIPointFamilyConfig | WUI point allocation | 🔴 | 4 |
| rp_WUIPointUseHistory | WUI point allocation | 🔴 | 4 |
| rp_WUIProcessMeterAllocations | WUI point allocation | 🔴 | 4 |
| rp_accruals | accruals | 🔴 | 4 |
| rp_mpaaccruals | accruals | 🔴 | 4 |

### Energy Star Rating (5)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| facility_setup | ES facility setup screen | 🟡 | 5 |
| new_rating_request | ES request screen | 🔴 | 5 |
| rp_ESRatingComparison | ES rating responses | 🔴 | 5 |
| rp_ESRatingHistory | ES rating responses | 🔴 | 5 |
| rp_ESRatingRequestLog | ES rating responses | 🔴 | 5 |

### Green House Gas (3)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_GHGHistory | GHG emissions | 🔴 | 5 |
| rp_GHGVariance | GHG emissions | 🔴 | 5 |
| rp_GHGAudit | GHG emissions | 🔴 | 5 |

### Project Tracking (5)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_ProjectDetail | project financials | 🔴 | 6 |
| rp_ProjectSummary | project financials | 🔴 | 6 |
| rp_ProjectFinance | project financials | 🔴 | 6 |
| rp_ProjectTrackingConfiguration | project config | 🔴 | 6 |
| rp_ApplyRateSchedule | rate history + project | 🔴 | 6 |

### System Manager (27)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_BuildingList | hierarchy + premise | 🟢 | 0 |
| rp_PointsList | points inventory | 🟢 | 0 |
| rp_PointDataMap | points inventory | 🟢 | 1 |
| rp_IndexList | index points | 🟢 | 1 |
| rp_HierarchyDetailsEditor | hierarchy editor | 🟢 | 0 |
| Data_Validation | bill/interval cross-check | 🟡 | 1 |
| rp_NoteHistory | notes | 🟡 | 1 |
| rp_ImageManagement | images | 🟡 | 1 |
| rp_GLAccountUDV | AP / GL | 🔴 | 3 |
| my_exports | export log | 🔴 | 3 |
| rp_BillValidationStatus | bill validation | 🔴 | 3 |
| rp_TenantMap | tenant allocation | 🔴 | 4 |
| rp_weatherregression | weather regression | 🔴 | 5 |
| emission_company_config | GHG config screen | 🔴 | 5 |
| emission_factor | GHG config screen | 🔴 | 5 |
| emission_meter_assign | GHG config screen | 🔴 | 5 |
| emission_source | GHG config screen | 🔴 | 5 |
| emission_type | GHG config screen | 🔴 | 5 |
| rp_GatewayStatus | gateway / live status | 🟡 | 6 |
| rp_TaskLog | task logs | 🔴 | 6 |
| rp_Audit | audit logs | 🔴 | 6 |
| rp_ActivityTracker | activity logs | 🔴 | 6 |
| rp_AlarmDataMap | alarms | 🔴 | 6 |
| log_analysis | log screen | 🟡 | 6 |
| my_imports | import log | 🔴 | 6 |

### My Reports (5)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| rp_monthlyutilitydistributionreport | monthly bills | 🟢 | 1 |
| rp_meterevents | meter events | 🟡 | 1 |
| rp_cngtestreportcgr | bills (custom CNG) | 🟡 | 1 |
| rp_RegressionSummaryReport2 | weather regression | 🔴 | 5 |
| rp_EnergyAIInsights | EnergyAI insights | 🔴 | 6 |

### System Administration (8)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| admin_reportconfig | config screen | 🟢 | 0 |
| admin_reportxmlconfig | language/config screen | 🟢 | 0 |
| company_calendar | calendar screen | 🟢 | 0 |
| user_editor | user screen | 🟢 | 0 |
| rp_AnonymizeData | admin tool | 🟢 | 0 |
| rp_HMRConfiguration | HMR | 🟡 | 6 |
| hmr_export | HMR | 🟡 | 6 |
| job_scheduler | tasks dashboard | 🟡 | 6 |

### Modules (1)

| Report | Bucket | Status | Phase |
| --- | --- | --- | --- |
| laco_dash_trending | custom dashboard (interval) | 🟡 | 6 |

---

## Tally by phase

| Phase | Reports closed (cumulative new coverage) |
| --- | --- |
| 0 Foundation | 8 substrate/config screens render |
| 1 Consumption & cost | ~35 (Use Analysis 15, Bill Processing/Tracking core, inventory, distribution) |
| 2 Rate engine | 9 Rate Analysis |
| 3 AP / GL & validation | 7 (AP, GL UDV, validation, open accruals, export log) |
| 4 Tenant rebilling | 15 (Tenant Rebilling 14 + TenantMap) |
| 5 Sustainability & analytics | 14 (GHG 3, ES Rating 5, regression 2, benchmark 2, emission config screens) |
| 6 Operations & engagement | remainder (projects 5, alarms, audit/activity, tasks/gateway/log, HMR, EnergyAI, importers, custom dashboards) + MFR delivery layer over all 92 deliverable reports |

> The phase a report is listed under is where its *data* first becomes non-empty.
> Many reports also gain depth in later phases (e.g. ScatterPlot/UsageVariance get
> weather-normalization in Phase 5; bills get GL coding in Phase 3).
