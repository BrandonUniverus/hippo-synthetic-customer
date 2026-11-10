-- Stage 7 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- Filters by name, not ID, since nothing in this stage exists yet when this file is written; every
-- result set is expected to be empty until Brandon has entered the corresponding step.
SET NOCOUNT ON;

PRINT '== town_center_company: 1 row; ArchiveInterval 60, TimeZoneID 33, DefaultCountry USA, address + contact present ==';
SELECT c.CompanyID, c.CompanyName, c.ArchiveInterval, c.TimeZoneID, c.DefaultCountry, a.AD_Address1, a.AD_PostalCode, ct.CT_FirstName + ' ' + ct.CT_LastName AS Contact, ct.CT_Email
FROM dbo.Company_TBL c LEFT JOIN dbo.Address a ON a.AD_AddressID = c.AD_AddressID LEFT JOIN dbo.Contact ct ON ct.CT_ContactID = c.CT_ContactID
WHERE c.CompanyName = 'Northlake Town Center';
GO
PRINT '== town_center_company: 4 levels, UDF labels Site Code/Building Code/Meter Tag/Source Channel ==';
SELECT ml.CompanyID, ml.LevelNbr, ml.Description, ml.MetaType, ml.UDFField, ml.Awesomefont
FROM dbo.MetaLevel_TBL ml JOIN dbo.Company_TBL c ON c.CompanyID = ml.CompanyID
WHERE c.CompanyName = 'Northlake Town Center' ORDER BY ml.LevelNbr;
GO
PRINT '== town_center_company: groups and users (tc_company_admins, tc_bill_entry, priya.nakamura) ==';
SELECT g.CompanyID, g.GroupID, g.Name FROM dbo.UserGroups g JOIN dbo.Company_TBL c ON c.CompanyID = g.CompanyID WHERE c.CompanyName = 'Northlake Town Center';
SELECT u.UserID, u.CompanyID, u.UserName, u.Email, u.PrincipalType FROM dbo.Users_TBL u JOIN dbo.Company_TBL c ON c.CompanyID = u.CompanyID WHERE c.CompanyName = 'Northlake Town Center';
GO

PRINT '== town_center_hierarchy: nodes by level; expect Property 1, Buildings 5, Meters 22, Points >= 14 ==';
SELECT mw.InternalLevelNbr, mw.MetaType, COUNT(*) AS Nodes
FROM dbo.MetaWorld_TBL mw JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0
GROUP BY mw.InternalLevelNbr, mw.MetaType ORDER BY mw.InternalLevelNbr;
GO
PRINT '== town_center_hierarchy: 22 billing accounts, 4 Importer (masters) + 18 Allocation (tenant spaces) ==';
SELECT ba.BillType_Code, COUNT(*) AS Accounts
FROM dbo.BillingAccount_TBL ba JOIN dbo.Company_TBL c ON c.CompanyID = ba.CompanyID
WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(ba.DeleteInd, 0) = 0
GROUP BY ba.BillType_Code ORDER BY ba.BillType_Code;
GO
PRINT '== town_center_hierarchy: floor area values (SqFt) on tenant-space nodes, method 4 and the WUI fixtures depend on these ==';
SELECT mw.Description AS Node, h.Value, u.UN_Units
FROM dbo.Value_TBL v JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = v.TableRowID
JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
LEFT JOIN dbo.ValueHistory h ON h.ValueID = v.ValueID LEFT JOIN dbo.Unit u ON u.UN_UnitID = v.UN_UnitID
WHERE c.CompanyName = 'Northlake Town Center' AND v.Table_Code = 'M2' ORDER BY mw.Description, h.AsOfDate;
GO

PRINT '== allocation_configs_by_method: one BillAllocationConfig per method 1-7 across Town Center + the Thermal Plant chilled-water/steam configs on Northlake University ==';
SELECT bam.Name AS Method, bac.BillAllocationConfigID, mw.Description AS Master, bac.FiscalYearStart, bac.FiscalPeriodStart, bac.FiscalYearEnd, bac.FiscalPeriodEnd, bac.CombineOverhead
FROM dbo.BillAllocationConfig bac JOIN dbo.BillAllocationMethod bam ON bam.BillAllocationMethodID = bac.BillAllocationMethodID
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
WHERE c.CompanyName IN ('Northlake Town Center', 'Northlake University') ORDER BY bam.BillAllocationMethodID, bac.FiscalYearStart;
GO
PRINT '== allocation_configs_by_method: BillAllocationConfigDetail row counts per config (method 1 configs need typed %/amount; methods 2,3,4,5,7 are computed by the engine and may be 0 until a run) ==';
SELECT bac.BillAllocationConfigID, mw.Description AS Master, bam.Name AS Method, COUNT(bacd.BillAllocationConfigDetailID) AS DetailRows,
       SUM(CASE WHEN bacd.IsAmountFixed = 1 THEN 1 ELSE 0 END) AS FixedRows, SUM(bacd.AllocationPercent) AS PercentTotal
FROM dbo.BillAllocationConfig bac JOIN dbo.BillAllocationMethod bam ON bam.BillAllocationMethodID = bac.BillAllocationMethodID
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
LEFT JOIN dbo.BillAllocationConfigDetail bacd ON bacd.BillAllocationConfigID = bac.BillAllocationConfigID
WHERE c.CompanyName IN ('Northlake Town Center', 'Northlake University')
GROUP BY bac.BillAllocationConfigID, mw.Description, bam.Name ORDER BY bac.BillAllocationConfigID;
GO
PRINT '== allocation_configs_by_method PRODUCT FINDING check: dbo.BillAllocationMethod should have 7 rows (1 today; see file 04 notes) ==';
SELECT BillAllocationMethodID, Name FROM dbo.BillAllocationMethod ORDER BY BillAllocationMethodID;
GO

PRINT '== wui_families_and_fail_reasons: PtAllocationConfig rows by method (1 Weighted Use Index, 2 Measured Use); expect wui_market_electric (3), wui_tower_electric (2), wui_fixtures (6), chain leaf (1) = 12 ==';
SELECT pam.Name AS Method, COUNT(*) AS ChildPoints
FROM dbo.PtAllocationConfig pac JOIN dbo.PtAllocationMethod pam ON pam.PtAllocationMethodID = pac.PtAllocationMethodID
JOIN dbo.PointDef_TBL p ON p.PtID = pac.MasterPtID WHERE p.CompanyID > 0
GROUP BY pam.Name ORDER BY pam.Name;
GO
PRINT '== wui_families_and_fail_reasons PRODUCT FINDING check: dbo.PtAllocationMethod should have 3 rows incl Percentage Based (2 today; see file 05 notes) ==';
SELECT PtAllocationMethodID, Name FROM dbo.PtAllocationMethod ORDER BY PtAllocationMethodID;
GO
PRINT '== wui_families_and_fail_reasons: each of fail reasons 1-5 produced at least once by the fixtures (file 05), after Process Meter Allocations has run (file 07) ==';
SELECT r.Name AS FailReason, COUNT(*) AS Occurrences
FROM dbo.tempFailedAllocPts f JOIN dbo.PtAllocFailReason r ON r.PtAllocFailReasonID = f.PtAllocFailReasonID
GROUP BY r.Name ORDER BY r.Name;
GO
PRINT '== wui_families_and_fail_reasons: method-3 (Percentage Based) child produces no success and no fail row (silently ignored, documented product gap) ==';
SELECT p.PtID, p.Description FROM dbo.PointDef_TBL p WHERE p.Description = 'Fixture Percentage Based'
  AND NOT EXISTS (SELECT 1 FROM dbo.tempSuccessAllocPts s WHERE s.PtID = p.PtID)
  AND NOT EXISTS (SELECT 1 FROM dbo.tempFailedAllocPts f WHERE f.PtID = p.PtID);
GO

PRINT '== generation_configs: dbo.UtilityMeterRatesBillGen rows by generation type; expect the 4 Town Center fixtures (Off/Manual/Auto/Auto Regen) plus Cedar Row + Anchor Store reconciliation rows plus one Auto row on the Ridgeline billing meter (Northlake Thermal Plant, step 8) ==';
SELECT bgt.Name AS GenerationType, COUNT(*) AS Meters
FROM dbo.UtilityMeterRatesBillGen umrbg JOIN dbo.BillGenerationType bgt ON bgt.BillGenerationTypeId = umrbg.BillGenStatusID
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = umrbg.MetaWorldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
WHERE c.CompanyName IN ('Northlake Town Center', 'Cedar Row Apartments', 'Northlake Thermal Plant') GROUP BY bgt.Name ORDER BY bgt.Name;
GO
PRINT '== generation_configs: Anchor Store carries a row under the Bill Meter Reconciliation scenario (ScenarioTypeID 20) ==';
SELECT mw.Description AS Meter, umrbg.BillScenarioID, st.Description AS Scenario, umrbg.FiscalStart, umrbg.FiscalEnd, umrbg.BillGenReconDataSourceID
FROM dbo.UtilityMeterRatesBillGen umrbg JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = umrbg.MetaWorldID
LEFT JOIN dbo.BillScenario bs ON bs.BillScenarioID = umrbg.BillScenarioID LEFT JOIN dbo.ScenarioType st ON st.ScenarioTypeID = bs.ScenarioTypeID
WHERE mw.Description = 'Anchor Store';
GO

PRINT '== allocation_runs: dbo.PtAllocationProcessLog rows for 2024-01 through 2024-03 (file 07 Process Meter Allocations) ==';
SELECT ProcessKey, StartTime, Status, PtsForDisaggregation, PtsDisaggregated, NewBills, FiscalYear, FiscalPeriod
FROM dbo.PtAllocationProcessLog WHERE FiscalYear = 2024 AND FiscalPeriod IN (1, 2, 3) ORDER BY StartTime;
GO
PRINT '== allocation_runs: Task_Tbl 24/42/47 confirmed present with the expected names (catalog check, not a run check) ==';
SELECT TaskID, Name, Description, MinIntervalSeconds, SystemOnly, CanSchedule FROM dbo.Task_Tbl WHERE TaskID IN (24, 42, 47) ORDER BY TaskID;
GO
PRINT '== allocation_runs: dbo.BillAllocationMap rows exist (Process Bill Allocation, Task_Tbl 24, has produced allocated bills) ==';
SELECT COUNT(*) AS AllocationMapRows FROM dbo.BillAllocationMap WHERE ISNULL(DeleteInd, 0) = 0;
GO

PRINT '== tenant_bills_sum_to_parent: for every master bill, allocated child amounts (incl. overhead) sum to the parent to the penny; Diff must be 0 for every row ==';
SELECT bam.MasterBillID, mb.BL_Amount AS ParentAmount, SUM(bamd.AllocatedAmount) AS SumAllocated, mb.BL_Amount - SUM(bamd.AllocatedAmount) AS Diff
FROM dbo.BillAllocationMap bam JOIN dbo.BillAllocationMapDetail bamd ON bamd.BillAllocationMapID = bam.BillAllocationMapID
JOIN dbo.Bill mb ON mb.BL_BillID = bam.MasterBillID
WHERE ISNULL(bam.DeleteInd, 0) = 0 GROUP BY bam.MasterBillID, mb.BL_Amount
ORDER BY bam.MasterBillID;
GO
PRINT '== tenant_bills_sum_to_parent: Property Total (method 6) equals the sum of every consumed child bill it aggregates ==';
SELECT agg.BillAllocationConfigID, mw.Description AS CostCenter, agg.FiscalYear, agg.FiscalPeriod, agg.BillID, bl.BL_Amount
FROM dbo.BillAllocationAggMap agg JOIN dbo.BillAllocationConfig bac ON bac.BillAllocationConfigID = agg.BillAllocationConfigID
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID LEFT JOIN dbo.Bill bl ON bl.BL_BillID = agg.BillID
WHERE mw.Description = 'Property Total' ORDER BY agg.FiscalYear, agg.FiscalPeriod;
GO

PRINT '== reconciliation_variance: rp_BillReconciliation is present and callable (existence check, not a data check) ==';
SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_NAME = 'rp_BillReconciliation';
GO
PRINT '== reconciliation_variance: Anchor Store''s rate assignment under Actual vs under Bill Meter Reconciliation (ScenarioTypeID 20); rp_BillReconciliation resolves these two BillScenarioIDs the same way (dbo.BillScenario WHERE ScenarioTypeId = -1 / 20) before comparing amounts, so both rows existing with different rates is what makes its variance nonzero ==';
SELECT mw.Description AS Meter, st.ScenarioTypeID, st.Description AS Scenario, umrbg.BillScenarioID, umrbg.FiscalStart, umrbg.FiscalEnd, umrbg.BillGenStatusID
FROM dbo.Meter m JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = m.MetaWorldID
JOIN dbo.UtilityMeterRatesBillGen umrbg ON umrbg.MetaWorldID = mw.MetaWorldID
JOIN dbo.BillScenario bs ON bs.BillScenarioId = umrbg.BillScenarioID
JOIN dbo.ScenarioType st ON st.ScenarioTypeID = bs.ScenarioTypeId
WHERE mw.Description = 'Anchor Store' AND st.ScenarioTypeID IN (-1, 20)
ORDER BY st.ScenarioTypeID;
GO
PRINT '== GuiReports_Tbl PRODUCT FINDING check: 11 of 14 Tenant Rebilling reports registered; rp_accruals/rp_mpaaccruals/rp_OpenAccruals missing (see file 07 notes) ==';
SELECT ObjectName, URI FROM dbo.GuiReports_Tbl
WHERE ObjectName IN ('rp_TenantMap','rp_BillAllocationConfiguration','rp_BillGenerationConfig','rp_BillReconciliation','rp_RateAllocation',
  'rp_TenantBillAllocationMap','rp_TenantBillAudit','rp_TenantBillDefinition','rp_WUIPointFamilyConfig','rp_WUIPointUseHistory',
  'rp_WUIProcessMeterAllocations','rp_accruals','rp_mpaaccruals','rp_OpenAccruals')
ORDER BY ObjectName;
GO

-- Step 8, Ridgeline Wind (added 2026-10-01). The last four read Stage 3's turbine data and the statements Run Bill Gen
-- writes, so they fill in last. Account SYN-RWL-G-0000001 has one generating meter, never one of the ten pad meters.
-- These read BillingAccount_TBL, not the BillingAccount view, which a sqlcmd session with no EEM user sees empty.
PRINT '== ridgeline_billing_meter: Ridgeline Farm Transfer Meter (Stage 2, SYN-RWL-M-0110000) is one Electricity meter on SYN-RWL-G-0000001, provider Ridgeline Wind, Bill Cycle 1; its one point is the farm aggregate Ridgeline Farm Generated kWh 10m with 10 Required members at multiplier 1 and a registered aggregate (AggregateID above 0, PRODUCT FINDING 14) ==';
SELECT mw.MetaWorldID, mw.Description AS Meter, m.SM_Code AS MeterNumber, ba.BA_BillingAccountNumber AS Account, up.Name AS Provider, m.BillCycle, ms.MT_MeasureName AS MeasureType
FROM dbo.MetaWorld_TBL mw JOIN dbo.Meter m ON m.MetaWorldID = mw.MetaWorldID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
LEFT JOIN dbo.UtilityProvider up ON up.ProviderID = ba.ProviderID
LEFT JOIN dbo.MeasureType ms ON ms.MT_MeasureTypeID = m.MT_MeasureTypeID
WHERE mw.Description = 'Ridgeline Farm Transfer Meter' AND ISNULL(mw.DeleteInd, 0) = 0;
SELECT p.Description AS AggregatePoint, a.ID AS AggregateID, a.Interval, COUNT(x.PtID) AS Members,
       SUM(CASE WHEN x.Required = 1 THEN 1 ELSE 0 END) AS RequiredMembers, MIN(x.Multiplier) AS MinMultiplier, MAX(x.Multiplier) AS MaxMultiplier
FROM dbo.MetaWorld_TBL mw JOIN dbo.MetaWorld_TBL pn ON pn.ParentID = mw.MetaWorldID
JOIN dbo.PointDef_TBL p ON p.PtID = pn.PtID
LEFT JOIN dbo.PointAggregates_TBL a ON a.AggregatePtID = p.PtID
LEFT JOIN dbo.PointAggregatePoints x ON x.AggregatePtID = p.PtID
WHERE mw.Description = 'Ridgeline Farm Transfer Meter'
GROUP BY p.Description, a.ID, a.Interval;
GO
PRINT '== ridgeline_commodity_mapping: both RWL-XFER-2024 determinants (Transfer energy 200, Research credit 400) have a UtilityCommodityMap row, because an unmapped one adds to the bill total and writes no line; the rate class is in force for a meter (ClassType 0, or at least one default option; Stage 4 owns both, step 8 depends on them) ==';
SELECT r.Name AS Rate, d.ChargeName, d.DeterminantTypeID, cu.CY_CommodityName AS UsageCommodity, cc.CY_CommodityName AS ChargeCommodity, cm.Exclude
FROM dbo.UtilityRate_Tbl r JOIN dbo.UtilityRateClass rc ON rc.UtilityRateID = r.UtilityRateID
JOIN dbo.UtilityRateDeterminant rd ON rd.RateClassID = rc.RateClassID
JOIN dbo.UtilityDeterminant d ON d.DeterminantID = rd.DeterminantID
LEFT JOIN dbo.UtilityCommodityMap cm ON cm.UtilityRateID = r.UtilityRateID AND cm.DeterminantID = d.DeterminantID
LEFT JOIN dbo.Commodity cu ON cu.CY_CommodityID = cm.DeterminantsCommodityID
LEFT JOIN dbo.Commodity cc ON cc.CY_CommodityID = cm.ChargesCommodityID
WHERE r.Name = 'RWL-XFER-2024' ORDER BY d.DeterminantTypeID;
SELECT rc.Description AS RateClass, rc.ClassType, SUM(CASE WHEN df.RateClassDefault = 1 THEN 1 ELSE 0 END) AS DefaultOptions
FROM dbo.UtilityRate_Tbl r JOIN dbo.UtilityRateClass rc ON rc.UtilityRateID = r.UtilityRateID
LEFT JOIN dbo.UtilityRateClassDefault df ON df.RateClassID = rc.RateClassID
WHERE r.Name = 'RWL-XFER-2024' GROUP BY rc.Description, rc.ClassType;
GO
PRINT '== ridgeline_generation_config: exactly one generation row on SYN-RWL-G-0000001, on the billing meter and on no pad meter: Actual, 202407 to 202512, schedule CC, Auto, Interval data (1), Available % 100 (99 only during the one-off March 2025 run), Offset 0, rate RWL-XFER-2024 from 2024-07-01; the second result set is every rate assignment on the account''s meters and must be that one row, on the billing meter (Stage 4 assigns it there only, Bill unchecked) ==';
SELECT mw.Description AS Meter, ba.BA_BillingAccountNumber AS Account, st.Description AS Scenario, g.FiscalStart, g.FiscalEnd, g.BillGenScheduleCode AS Schedule,
       bgt.Name AS GenerationType, g.BillGenReconDataSourceID AS DataSource, g.DataThreshold AS AvailablePct, g.OffsetDays,
       rt.Name AS Rate, CONVERT(char(10), mr.StartDate, 120) AS RateStart
FROM dbo.UtilityMeterRatesBillGen g
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = g.MetaWorldID
JOIN dbo.Meter m ON m.MetaWorldID = g.MetaWorldID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
JOIN dbo.BillScenario bs ON bs.BillScenarioID = g.BillScenarioID
JOIN dbo.ScenarioType st ON st.ScenarioTypeID = bs.ScenarioTypeID
LEFT JOIN dbo.BillGenerationType bgt ON bgt.BillGenerationTypeId = g.BillGenStatusID
LEFT JOIN dbo.UtilityMeterRates mr ON mr.MetaWorldID = g.MetaWorldID AND mr.BillScenarioID = g.BillScenarioID
LEFT JOIN dbo.UtilityRate_Tbl rt ON rt.UtilityRateID = mr.UtilityRateID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001';
SELECT mw.Description AS Meter, m.SM_Code AS MeterNumber, rt.Name AS Rate, CONVERT(char(10), mr.StartDate, 120) AS RateStart, st.Description AS Scenario
FROM dbo.UtilityMeterRates mr
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = mr.MetaWorldID
JOIN dbo.Meter m ON m.MetaWorldID = mr.MetaWorldID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
JOIN dbo.UtilityRate_Tbl rt ON rt.UtilityRateID = mr.UtilityRateID
JOIN dbo.BillScenario bs ON bs.BillScenarioID = mr.BillScenarioID
JOIN dbo.ScenarioType st ON st.ScenarioTypeID = bs.ScenarioTypeID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' ORDER BY m.SM_Code;
GO
PRINT '== ridgeline_generation_log: one log row per month 2024-07 to 2025-12 (18); Available should equal Expected (4464 in a 31-day month at 10 minutes) once Stage 3''s data (the rows stamped 2024-06-30 23:10 PST through 2026-01-01 00:00 PST, each an interval end) and the aggregate are in, and BillID is filled once Run Bill Gen has written the statement; a month under Available % waits with BillID null, which is March 2025 (4458 of 4464, Pacific time skips an hour) until its one-off Available % 99 run; July 2024 at 4458 means the feed started at the SCADA''s own July 1, and December 2025 at 4463 means it stopped before the row stamped 2026-01-01 00:00 (the 08 stamp note) ==';
SELECT l.FiscalCal, CONVERT(char(10), l.StartDate, 120) AS ServiceFrom, CONVERT(char(10), l.EndDate, 120) AS ServiceTo, l.AvailableIntervals, l.ExpectedIntervals,
       CAST(100.0 * l.AvailableIntervals / NULLIF(l.ExpectedIntervals, 0) AS decimal(6, 2)) AS PctAvailable, l.IsNewData, l.BillID
FROM dbo.UtilityBillGenLog l JOIN dbo.Meter m ON m.MetaWorldID = l.MetaWorldID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' ORDER BY l.FiscalCal;
GO
PRINT '== ridgeline_generated_statements: one bill per month on SYN-RWL-G-0000001 (the second result set must be empty), each with exactly 2 lines, the research credit -1250.00 once and no adjustment line, and the lines adding to ROUND(BL_Amount, 2) (Diff 0.00; BL_Amount itself keeps four decimals); the WTG-07 outage months 2025-02 to 2025-04 are included and lower ==';
SELECT bl.BL_FiscalYear * 100 + bl.BL_FiscalPeriodNo AS FiscalCal, bl.BL_BillID, CONVERT(char(10), bl.BL_PeriodStart, 120) AS PeriodStart, CONVERT(char(10), bl.BL_PeriodEnd, 120) AS PeriodEnd, bl.BL_Amount,
       COUNT(bi.BI_BillItemID) AS Lines, MAX(bi.BI_Quantity) AS TransferKwh,
       SUM(CASE WHEN bi.BI_Amount >= 0 THEN bi.BI_Amount ELSE 0 END) AS TransferAmount, SUM(CASE WHEN bi.BI_Amount < 0 THEN bi.BI_Amount ELSE 0 END) AS CreditAmount,
       ROUND(bl.BL_Amount, 2) - SUM(bi.BI_Amount) AS Diff
FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
LEFT JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND ISNULL(bi.DeleteInd, 0) = 0
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND ISNULL(bl.DeleteInd, 0) = 0
GROUP BY bl.BL_FiscalYear, bl.BL_FiscalPeriodNo, bl.BL_BillID, bl.BL_PeriodStart, bl.BL_PeriodEnd, bl.BL_Amount
ORDER BY FiscalCal;
SELECT bl.BL_FiscalYear * 100 + bl.BL_FiscalPeriodNo AS FiscalCal, COUNT(*) AS Bills
FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND ISNULL(bl.DeleteInd, 0) = 0
GROUP BY bl.BL_FiscalYear * 100 + bl.BL_FiscalPeriodNo HAVING COUNT(*) <> 1;
GO
PRINT '== ridgeline_acceptance_2024_07 (1 of 2): each turbine''s July 2024 Generated kWh 10m summed over the engine''s window (the stored Pacific LocalTimeStamp after 2024-07-01 00:00 and up to and including 2024-08-01 00:00) against the hand-made statement: Diff 0 on all ten and on the farm total 2251384, Intervals 4464 on each; a Diff here beside a clean Stage 3 ridgeline_period_totals is the interval-start versus interval-end stamp question in the 08 notes ==';
;WITH Expected(MeterNumber, ExpectedKwh) AS (
    SELECT v.MeterNumber, v.ExpectedKwh FROM (VALUES ('SYN-RWL-M-0110001', 238412), ('SYN-RWL-M-0110002', 233905), ('SYN-RWL-M-0110003', 229768), ('SYN-RWL-M-0110004', 226341),
        ('SYN-RWL-M-0110005', 224087), ('SYN-RWL-M-0110006', 225530), ('SYN-RWL-M-0110007', 222196), ('SYN-RWL-M-0110008', 219874),
        ('SYN-RWL-M-0110009', 217402), ('SYN-RWL-M-0110010', 213869)) v(MeterNumber, ExpectedKwh)
), Actual AS (
    SELECT e.MeterNumber, e.ExpectedKwh, SUM(a.Value) AS ActualKwh, COUNT(a.Value) AS Intervals
    FROM Expected e LEFT JOIN dbo.Meter m ON m.SM_Code = e.MeterNumber
    LEFT JOIN dbo.MetaWorld_TBL pn ON pn.ParentID = m.MetaWorldID
    LEFT JOIN dbo.PointDef_TBL p ON p.PtID = pn.PtID AND p.Description = 'Generated kWh 10m'
    LEFT JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.LocalTimeStamp > '2024-07-01' AND a.LocalTimeStamp <= '2024-08-01'
    GROUP BY e.MeterNumber, e.ExpectedKwh
)
SELECT MeterNumber, ExpectedKwh, ActualKwh, ActualKwh - ExpectedKwh AS Diff, Intervals FROM Actual
UNION ALL SELECT 'FARM TOTAL', SUM(ExpectedKwh), SUM(ActualKwh), SUM(ActualKwh) - SUM(ExpectedKwh), SUM(Intervals) FROM Actual
ORDER BY MeterNumber;
GO
PRINT '== ridgeline_acceptance_2024_07 (2 of 2): the generated July 2024 statement equals the hand-made one to the cent: Rounded 129330.27 (Diff 0.00), two lines, 130580.27 on 2251384 kWh and -1250.00 ==';
SELECT bl.BL_BillID, bl.BL_Amount, ROUND(bl.BL_Amount, 2) AS Rounded, 129330.27 AS HandMade, ROUND(bl.BL_Amount, 2) - 129330.27 AS Diff
FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND bl.BL_FiscalYear = 2024 AND bl.BL_FiscalPeriodNo = 7 AND ISNULL(bl.DeleteInd, 0) = 0;
SELECT bi.BI_Seq, c.CY_CommodityName AS Commodity, bi.BI_Quantity, bi.BI_Amount
FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND bl.BL_FiscalYear = 2024 AND bl.BL_FiscalPeriodNo = 7
  AND ISNULL(bl.DeleteInd, 0) = 0 AND ISNULL(bi.DeleteInd, 0) = 0
ORDER BY bi.BI_Amount DESC;
GO
PRINT '== ridgeline_outage_months: WTG-07 (SYN-RWL-M-0110007) Generated kWh 10m by month: zero from 2025-02-11 to 2025-04-22 with every interval still present (lost production, not missing data), so March reads 0 kWh with all its intervals; the Feb to Apr statements above are lower and keep the same two lines ==';
SELECT CONVERT(char(7), DATEADD(second, -1, a.LocalTimeStamp), 120) AS DataMonth, SUM(a.Value) AS Wtg07Kwh, COUNT(a.Value) AS Intervals, SUM(CASE WHEN a.Value = 0 THEN 1 ELSE 0 END) AS ZeroIntervals
FROM dbo.Meter m JOIN dbo.MetaWorld_TBL pn ON pn.ParentID = m.MetaWorldID
JOIN dbo.PointDef_TBL p ON p.PtID = pn.PtID AND p.Description = 'Generated kWh 10m'
JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.LocalTimeStamp > '2025-01-01' AND a.LocalTimeStamp <= '2025-06-01'
WHERE m.SM_Code = 'SYN-RWL-M-0110007'
GROUP BY CONVERT(char(7), DATEADD(second, -1, a.LocalTimeStamp), 120) ORDER BY DataMonth;
GO
