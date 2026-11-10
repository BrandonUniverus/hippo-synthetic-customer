-- Stage 7 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- Rewritten 2026-11-10. A block that says ASSERT returns Expected, Actual and a Result column (PASS or FAIL) for every
-- value the recipe knows; the expected values come from files 09 and 10, which scripts computed. A block that says
-- LIST has no known value and only shows rows. Filters are by name (Town Center, Cedar Row, Thermal Plant), never by ID.
-- Order of entry: steps 1, 2, 9 (rates), Stage 3's Town Center data, the master bills of file 10, then 3 to 8.
SET NOCOUNT ON;

PRINT '== ASSERT town_center_company: one company, archive interval 60, time zone 33, country USA, 4 levels, 2 groups, 1 user ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'company rows' AS Item, 1 AS Expected, (SELECT COUNT(*) FROM dbo.Company_TBL WHERE CompanyName = 'Northlake Town Center') AS Actual
    UNION ALL SELECT 'ArchiveInterval', 60, (SELECT MAX(ArchiveInterval) FROM dbo.Company_TBL WHERE CompanyName = 'Northlake Town Center')
    UNION ALL SELECT 'TimeZoneID', 33, (SELECT MAX(TimeZoneID) FROM dbo.Company_TBL WHERE CompanyName = 'Northlake Town Center')
    UNION ALL SELECT 'levels', 4, (SELECT COUNT(*) FROM dbo.MetaLevel_TBL ml JOIN dbo.Company_TBL c ON c.CompanyID = ml.CompanyID WHERE c.CompanyName = 'Northlake Town Center')
    UNION ALL SELECT 'groups', 2, (SELECT COUNT(*) FROM dbo.UserGroups g JOIN dbo.Company_TBL c ON c.CompanyID = g.CompanyID WHERE c.CompanyName = 'Northlake Town Center')
    UNION ALL SELECT 'users', 1, (SELECT COUNT(*) FROM dbo.Users_TBL u JOIN dbo.Company_TBL c ON c.CompanyID = u.CompanyID WHERE c.CompanyName = 'Northlake Town Center')
    UNION ALL SELECT 'bill scenarios (Actual, Budget, Bill Meter Reconciliation)', 3, (SELECT COUNT(*) FROM dbo.BillScenario bs JOIN dbo.Company_TBL c ON c.CompanyID = bs.CompanyID WHERE c.CompanyName = 'Northlake Town Center')
) x;
GO

PRINT '== ASSERT town_center_hierarchy: nodes by level (Property 1, Buildings 5, Meters 22, Points 26) and 22 accounts: 4 Bill Entry, 4 Bill Generation, 14 Bill Allocation, all Valley Electric District, all US Dollar; all 22 meters Electricity ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'level 1 nodes' AS Item, 1 AS Expected, (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0 AND mw.InternalLevelNbr = 1) AS Actual
    UNION ALL SELECT 'level 2 nodes', 5, (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0 AND mw.InternalLevelNbr = 2)
    UNION ALL SELECT 'level 3 nodes (meters)', 22, (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0 AND mw.InternalLevelNbr = 3)
    UNION ALL SELECT 'level 4 nodes (points)', 26, (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0 AND mw.InternalLevelNbr = 4)
    UNION ALL SELECT 'accounts, Bill Entry (BillType_Code 0)', 4, (SELECT COUNT(*) FROM dbo.BillingAccount_TBL ba JOIN dbo.Company_TBL c ON c.CompanyID = ba.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(ba.DeleteInd, 0) = 0 AND ba.BillType_Code = 0)
    UNION ALL SELECT 'accounts, Bill Generation (2)', 4, (SELECT COUNT(*) FROM dbo.BillingAccount_TBL ba JOIN dbo.Company_TBL c ON c.CompanyID = ba.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(ba.DeleteInd, 0) = 0 AND ba.BillType_Code = 2)
    UNION ALL SELECT 'accounts, Bill Allocation (3)', 14, (SELECT COUNT(*) FROM dbo.BillingAccount_TBL ba JOIN dbo.Company_TBL c ON c.CompanyID = ba.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(ba.DeleteInd, 0) = 0 AND ba.BillType_Code = 3)
    UNION ALL SELECT 'accounts with a provider', 22, (SELECT COUNT(*) FROM dbo.BillingAccount_TBL ba JOIN dbo.Company_TBL c ON c.CompanyID = ba.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(ba.DeleteInd, 0) = 0 AND ba.ProviderID IS NOT NULL)
    UNION ALL SELECT 'meters carrying that provider (copied from the account)', 22, (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Meter m ON m.MetaWorldID = mw.MetaWorldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0 AND mw.ProviderID IS NOT NULL)
    UNION ALL SELECT 'meters with Measure Type Electricity', 22, (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Meter m ON m.MetaWorldID = mw.MetaWorldID JOIN dbo.MeasureType mt ON mt.MT_MeasureTypeID = m.MT_MeasureTypeID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID WHERE c.CompanyName = 'Northlake Town Center' AND ISNULL(mw.DeleteInd, 0) = 0 AND mt.MT_MeasureName = 'Electricity')
) x;
GO
PRINT '== ASSERT town_center_hierarchy: floor area (SqFt) of the 15 area nodes: expected value against the latest Area entry ==';
;WITH Expected(Node, Area) AS (
    SELECT v.Node, v.Area FROM (VALUES ('Market Hall', 84000), ('Office Tower', 96000), ('Campus Annex', 54000), ('Anchor Store', 28000), ('Food Court', 12000),
        ('In-line Shop 1', 2200), ('In-line Shop 2', 1800), ('In-line Shop 3', 2600), ('In-line Shop 4', 2000), ('Common Area', 35400),
        ('Floor 1', 22000), ('Floor 2', 22000), ('Floor 3', 22000), ('Floor 4', 22000), ('Landlord/House', 8000), ('Bldg A', 16000), ('Bldg B', 18000), ('Bldg C', 20000)) v(Node, Area)
), Actual AS (
    SELECT mw.Description AS Node, (SELECT TOP 1 h.Value FROM dbo.ValueHistory h WHERE h.ValueID = v.ValueID ORDER BY h.AsOfDate DESC) AS Area
    FROM dbo.Value_TBL v JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = v.TableRowID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
    WHERE c.CompanyName = 'Northlake Town Center' AND v.Table_Code = 'M2'
)
SELECT e.Node, e.Area AS Expected, a.Area AS Actual, CASE WHEN a.Area = e.Area THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN Actual a ON a.Node = e.Node ORDER BY e.Node;
GO

PRINT '== ASSERT tenant_rates: TC-FLAT-GS (2 charges) and TC-STEP-DEMAND (3 charges, types 400/200 and 210/200/600), both under Valley Electric District, every charge with a commodity mapping (an unmapped charge adds to the total and writes no line) ==';
SELECT x.Rate, x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT r.Name AS Rate, 'charges' AS Item, CASE r.Name WHEN 'TC-FLAT-GS' THEN 2 ELSE 3 END AS Expected,
           (SELECT COUNT(*) FROM dbo.UtilityRateClass rc JOIN dbo.UtilityRateDeterminant rd ON rd.RateClassID = rc.RateClassID WHERE rc.UtilityRateID = r.UtilityRateID) AS Actual
    FROM dbo.UtilityRate_Tbl r WHERE r.Name IN ('TC-FLAT-GS', 'TC-STEP-DEMAND')
    UNION ALL
    SELECT r.Name, 'charges with a commodity mapping', CASE r.Name WHEN 'TC-FLAT-GS' THEN 2 ELSE 3 END,
           (SELECT COUNT(*) FROM dbo.UtilityRateClass rc JOIN dbo.UtilityRateDeterminant rd ON rd.RateClassID = rc.RateClassID
              JOIN dbo.UtilityCommodityMap cm ON cm.UtilityRateID = r.UtilityRateID AND cm.DeterminantID = rd.DeterminantID
              WHERE rc.UtilityRateID = r.UtilityRateID AND (cm.ChargesCommodityID IS NOT NULL OR cm.DeterminantsCommodityID IS NOT NULL))
    FROM dbo.UtilityRate_Tbl r WHERE r.Name IN ('TC-FLAT-GS', 'TC-STEP-DEMAND')
    UNION ALL
    SELECT r.Name, 'charge type 210 and 600 present (1 each)', CASE r.Name WHEN 'TC-STEP-DEMAND' THEN 2 ELSE 0 END,
           (SELECT COUNT(*) FROM dbo.UtilityRateClass rc JOIN dbo.UtilityRateDeterminant rd ON rd.RateClassID = rc.RateClassID JOIN dbo.UtilityDeterminant d ON d.DeterminantID = rd.DeterminantID
              WHERE rc.UtilityRateID = r.UtilityRateID AND d.DeterminantTypeID IN (210, 600))
    FROM dbo.UtilityRate_Tbl r WHERE r.Name IN ('TC-FLAT-GS', 'TC-STEP-DEMAND')
    UNION ALL
    SELECT r.Name, 'filed under Valley Electric District', 1, (SELECT COUNT(*) FROM dbo.UtilityProvider up WHERE up.ProviderID = r.ProviderID AND up.Name = 'Valley Electric District')
    FROM dbo.UtilityRate_Tbl r WHERE r.Name IN ('TC-FLAT-GS', 'TC-STEP-DEMAND')
) x ORDER BY x.Rate, x.Item;
GO

PRINT '== ASSERT allocation_configs: configs and detail rows per master; Town Center 8 (methods 1 x2, 2, 3, 4, 5, 6, 7), the Thermal Plant recovery on Northlake University 2, Cedar Row 4 (the 248 rows need Stage 2 to give the apartment submeters billing accounts, file 06 notes); typed values on the method 1 and 6 rows ==';
;WITH Expected(CompanyName, Master, MethodId, StartYear, DetailRows) AS (
    SELECT v.CompanyName, v.Master, v.MethodId, v.StartYear, v.DetailRows FROM (VALUES
        ('Northlake Town Center', 'Mall-Main', 1, 2024, 7), ('Northlake Town Center', 'Mall-Main', 1, 2025, 7), ('Northlake Town Center', 'Tower-Main', 2, 2024, 4),
        ('Northlake Town Center', 'Tower-Main', 3, 2025, 4), ('Northlake Town Center', 'Mall-Main', 4, 2026, 4), ('Northlake Town Center', 'Annex-Main', 5, 2024, 3),
        ('Northlake Town Center', 'Property Total', 6, 2024, 17), ('Northlake Town Center', 'Substation-Master', 7, 2024, 2),
        ('Northlake University', 'Central Plant CHW Allocation', 2, 2024, 2), ('Northlake University', 'Central Plant Steam Allocation', 1, 2024, 6),
        ('Cedar Row Apartments', 'Cedar Row A Electric Master', 2, 2024, 60), ('Cedar Row Apartments', 'Cedar Row A Water Master', 2, 2024, 60),
        ('Cedar Row Apartments', 'Cedar Row B Electric Master', 2, 2024, 64), ('Cedar Row Apartments', 'Cedar Row B Water Master', 2, 2024, 64)) v(CompanyName, Master, MethodId, StartYear, DetailRows)
), Actual AS (
    SELECT c.CompanyName, mw.Description AS Master, bac.BillAllocationMethodID AS MethodId, bac.FiscalYearStart AS StartYear, COUNT(d.BillAllocationConfigDetailID) AS DetailRows
    FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
    LEFT JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID
    WHERE c.CompanyName IN ('Northlake Town Center', 'Northlake University', 'Cedar Row Apartments')
    GROUP BY c.CompanyName, mw.Description, bac.BillAllocationMethodID, bac.FiscalYearStart
)
SELECT e.CompanyName, e.Master, e.MethodId, e.StartYear, e.DetailRows AS Expected, a.DetailRows AS Actual, CASE WHEN a.DetailRows = e.DetailRows THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN Actual a ON a.CompanyName = e.CompanyName AND a.Master = e.Master AND a.MethodId = e.MethodId AND a.StartYear = e.StartYear
ORDER BY e.CompanyName, e.Master, e.StartYear;
GO
PRINT '== ASSERT allocation_configs: typed values. Mall-Main method 1: percents total 100 per config, Anchor Store one fixed 2000 row, Overhead % 2 on all 7 rows; Property Total: 17 rows at 100%; Cedar Row apartment rows Overhead % 2 (blank until the Stage 2 accounts exist) ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'Mall-Main method 1 configs with percents totalling 100 (non-fixed rows)' AS Item, 2 AS Expected,
           (SELECT COUNT(*) FROM (SELECT bac.BillAllocationConfigID FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID
                JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID
                WHERE mw.Description = 'Mall-Main' AND bac.BillAllocationMethodID = 1 AND d.IsAmountFixed = 0 GROUP BY bac.BillAllocationConfigID HAVING SUM(d.AllocationPercent) = 100) t) AS Actual
    UNION ALL SELECT 'Mall-Main method 1 rows fixed at 2000 (Anchor Store)', 2,
           (SELECT COUNT(*) FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID
                JOIN dbo.MetaWorld_TBL tn ON tn.MetaWorldID = d.MetaworldID
                WHERE mw.Description = 'Mall-Main' AND bac.BillAllocationMethodID = 1 AND d.IsAmountFixed = 1 AND d.AllocationAmount = 2000 AND tn.Description = 'Anchor Store')
    UNION ALL SELECT 'Mall-Main method 1 rows with Overhead % 2', 14,
           (SELECT COUNT(*) FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID
                WHERE mw.Description = 'Mall-Main' AND bac.BillAllocationMethodID = 1 AND d.OverheadPercent = 2)
    UNION ALL SELECT 'Mall-Main FY2024 Combine Overhead off and FY2025 on (both configs match)', 2,
           (SELECT COUNT(*) FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID
                WHERE mw.Description = 'Mall-Main' AND bac.BillAllocationMethodID = 1 AND ((bac.FiscalYearStart = 2024 AND bac.CombineOverhead = 0) OR (bac.FiscalYearStart = 2025 AND bac.CombineOverhead = 1)) HAVING COUNT(*) = 2)
    UNION ALL SELECT 'Property Total rows at Allocation % 100', 17,
           (SELECT COUNT(*) FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID
                WHERE mw.Description = 'Property Total' AND bac.BillAllocationMethodID = 6 AND d.AllocationPercent = 100)
    UNION ALL SELECT 'Cedar Row apartment rows with Overhead % 2 (248 once Stage 2 gives the submeters accounts)', 248,
           (SELECT COUNT(*) FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
                JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID WHERE c.CompanyName = 'Cedar Row Apartments' AND d.OverheadPercent = 2)
    UNION ALL SELECT 'Northlake University steam recovery percents total 100', 100,
           (SELECT CAST(SUM(d.AllocationPercent) AS int) FROM dbo.BillAllocationConfig bac JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bac.MetaworldID JOIN dbo.BillAllocationConfigDetail d ON d.BillAllocationConfigID = bac.BillAllocationConfigID
                WHERE mw.Description = 'Central Plant Steam Allocation')
    UNION ALL SELECT 'BillAllocationMethod rows installed (methods 1-7)', 7, (SELECT COUNT(*) FROM dbo.BillAllocationMethod)
) x;
GO

PRINT '== ASSERT wui_families: child points by method (Weighted Use Index 9, Measured Use 2, Percentage Based 1 = 12 rows; installed catalog 3 rows) ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'Weighted Use Index children' AS Item, 9 AS Expected, (SELECT COUNT(*) FROM dbo.PtAllocationConfig pac JOIN dbo.PtAllocationMethod pam ON pam.PtAllocationMethodID = pac.PtAllocationMethodID WHERE pam.Name = 'Weighted Use Index') AS Actual
    UNION ALL SELECT 'Measured Use children', 2, (SELECT COUNT(*) FROM dbo.PtAllocationConfig pac JOIN dbo.PtAllocationMethod pam ON pam.PtAllocationMethodID = pac.PtAllocationMethodID WHERE pam.Name = 'Measured Use')
    UNION ALL SELECT 'Percentage Based children', 1, (SELECT COUNT(*) FROM dbo.PtAllocationConfig pac JOIN dbo.PtAllocationMethod pam ON pam.PtAllocationMethodID = pac.PtAllocationMethodID WHERE pam.Name = 'Percentage Based')
    UNION ALL SELECT 'PtAllocationMethod rows installed', 3, (SELECT COUNT(*) FROM dbo.PtAllocationMethod)
    UNION ALL SELECT 'distinct fail reasons produced by the fixtures (1 to 5)', 5, (SELECT COUNT(DISTINCT f.PtAllocFailReasonID) FROM dbo.tempFailedAllocPts f WHERE f.PtAllocFailReasonID BETWEEN 1 AND 5)
    UNION ALL SELECT 'Percentage Based fixture in neither success nor failure table', 1,
           (SELECT COUNT(*) FROM dbo.PointDef_TBL p WHERE p.Description = 'Fixture Percentage Based' AND NOT EXISTS (SELECT 1 FROM dbo.tempSuccessAllocPts s WHERE s.PtID = p.PtID) AND NOT EXISTS (SELECT 1 FROM dbo.tempFailedAllocPts f WHERE f.PtID = p.PtID))
) x;
GO
PRINT '== ASSERT wui_index_values: the index entered on WUI Point Use History for each child (Shop 3 0.40, Shop 4 0.50, Common Area 0.15, Landlord/House 0.90), effective 2024-01-01 ==';
;WITH Expected(Point, IndexValue) AS (SELECT v.Point, v.IndexValue FROM (VALUES ('In-line Shop 3 Estimated kWh', 0.40), ('In-line Shop 4 Estimated kWh', 0.50), ('Common Area Estimated kWh', 0.15), ('Landlord/House Estimated kWh', 0.90)) v(Point, IndexValue))
SELECT e.Point, e.IndexValue AS Expected, pai.IndexValue AS Actual, CASE WHEN pai.IndexValue = e.IndexValue AND pai.EffectiveDate = '2024-01-01' THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.PointDef_TBL p ON p.Description = e.Point LEFT JOIN dbo.PtAllocationIndex pai ON pai.AllocPtID = p.PtID;
GO
PRINT '== ASSERT wui_allocated_use_2024_01: after Process Meter Allocations for 2024-01 the child points hold, for the stamps after 2024-01-01 00:00 up to and including 2024-02-01 00:00, the use of file 10 (within 0.05 kWh): Shop 3 26318.37, Shop 4 25306.12, Common Area 134375.51, Landlord/House 230640 ==';
;WITH Expected(Point, Kwh) AS (SELECT v.Point, v.Kwh FROM (VALUES ('In-line Shop 3 Estimated kWh', 26318.37), ('In-line Shop 4 Estimated kWh', 25306.12), ('Common Area Estimated kWh', 134375.51), ('Landlord/House Estimated kWh', 230640.00)) v(Point, Kwh)),
Actual AS (SELECT p.Description AS Point, SUM(a.Value) AS Kwh, COUNT(a.Value) AS Intervals FROM dbo.PointDef_TBL p JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.LocalTimeStamp > '2024-01-01' AND a.LocalTimeStamp <= '2024-02-01' GROUP BY p.Description)
SELECT e.Point, e.Kwh AS Expected, a.Kwh AS Actual, a.Intervals, CASE WHEN ABS(ISNULL(a.Kwh, -1) - e.Kwh) <= 0.05 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN Actual a ON a.Point = e.Point;
GO

PRINT '== ASSERT generation_configs: Bill Generation rows by company and type. Town Center: Off 1 (Anchor Store), Manual 1 (Food Court), Auto 1 (Shop 1), Auto w/ Auto Regen 2 (Shop 2 and the reconciliation row Anchor Store gets from its Bill checkbox); Cedar Row 0; Thermal Plant Auto 1 (the Ridgeline billing meter) ==';
;WITH Expected(CompanyName, TypeName, Rows_) AS (SELECT v.CompanyName, v.TypeName, v.Rows_ FROM (VALUES
    ('Northlake Town Center', 'Off', 1), ('Northlake Town Center', 'Manual', 1), ('Northlake Town Center', 'Auto', 1), ('Northlake Town Center', 'Auto w/ Auto Regen', 2),
    ('Cedar Row Apartments', 'Off', 0), ('Northlake Thermal Plant', 'Auto', 1)) v(CompanyName, TypeName, Rows_)),
Actual AS (SELECT c.CompanyName, bgt.Name AS TypeName, COUNT(*) AS Rows_ FROM dbo.UtilityMeterRatesBillGen g JOIN dbo.BillGenerationType bgt ON bgt.BillGenerationTypeId = g.BillGenStatusID
    JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = g.MetaWorldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID GROUP BY c.CompanyName, bgt.Name)
SELECT e.CompanyName, e.TypeName, e.Rows_ AS Expected, ISNULL(a.Rows_, 0) AS Actual, CASE WHEN ISNULL(a.Rows_, 0) = e.Rows_ THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN Actual a ON a.CompanyName = e.CompanyName AND a.TypeName = e.TypeName ORDER BY e.CompanyName, e.TypeName;
GO
PRINT '== ASSERT rate_assignments: Anchor Store TC-STEP-DEMAND under Actual, Budget and Bill Meter Reconciliation from 2024-01-01; Food Court, Shop 1, Shop 2 TC-FLAT-GS under Actual from 2026-01-01; no NL- feature rate on any Cedar Row or Town Center meter ==';
;WITH Expected(Meter, ScenarioTypeId, RateName, StartDate) AS (SELECT v.Meter, v.ScenarioTypeId, v.RateName, CONVERT(date, v.StartDate) FROM (VALUES
    ('Anchor Store', -1, 'TC-STEP-DEMAND', '2024-01-01'), ('Anchor Store', 20, 'TC-STEP-DEMAND', '2024-01-01'), ('Food Court', -1, 'TC-FLAT-GS', '2026-01-01'),
    ('In-line Shop 1', -1, 'TC-FLAT-GS', '2026-01-01'), ('In-line Shop 2', -1, 'TC-FLAT-GS', '2026-01-01')) v(Meter, ScenarioTypeId, RateName, StartDate)),
Actual AS (SELECT mw.Description AS Meter, bs.ScenarioTypeId, r.Name AS RateName, CONVERT(date, mr.StartDate) AS StartDate FROM dbo.UtilityMeterRates mr JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = mr.MetaWorldID
    JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID JOIN dbo.BillScenario bs ON bs.BillScenarioId = mr.BillScenarioID JOIN dbo.UtilityRate_Tbl r ON r.UtilityRateID = mr.UtilityRateID WHERE c.CompanyName = 'Northlake Town Center')
SELECT e.Meter, e.ScenarioTypeId, e.RateName AS Expected, a.RateName AS Actual, CASE WHEN a.RateName = e.RateName AND a.StartDate = e.StartDate THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN Actual a ON a.Meter = e.Meter AND a.ScenarioTypeId = e.ScenarioTypeId
UNION ALL
SELECT 'NL- rates on Town Center and Cedar Row meters', NULL, '0', CAST(COUNT(*) AS nvarchar(20)), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.UtilityMeterRates mr JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = mr.MetaWorldID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID JOIN dbo.UtilityRate_Tbl r ON r.UtilityRateID = mr.UtilityRateID
WHERE c.CompanyName IN ('Northlake Town Center', 'Cedar Row Apartments') AND r.Name LIKE 'NL-%';
GO

PRINT '== ASSERT master_bills: the seven bills of file 10 keyed on Bill Entry Web, amount to the cent ==';
;WITH Expected(Invoice, Amount) AS (SELECT v.Invoice, v.Amount FROM (VALUES ('TC-MM-2024-01', 30000.00), ('TC-MM-2025-01', 30000.00), ('TC-MM-2026-01', 30000.00), ('TC-TM-2024-01', 35712.00), ('TC-TM-2025-01', 35712.00), ('TC-AM-2024-01', 26784.00), ('TC-SM-2024-01', 44640.00)) v(Invoice, Amount))
SELECT e.Invoice, e.Amount AS Expected, b.BL_Amount AS Actual, CASE WHEN b.BL_Amount = e.Amount THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.Bill b ON b.BL_InvoiceNumber = e.Invoice AND ISNULL(b.DeleteInd, 0) = 0 ORDER BY e.Invoice;
GO
PRINT '== ASSERT method_1_allocation: after Task 24 Run Now, each Mall-Main tenant bill for 2024-01 (separate overhead) and 2025-01 (overhead combined): allocated amount without overhead, overhead (2%) and the bill total; Anchor Store 2000.00 + 40.00, Food Court 4200.00 + 84.00, Shops 2240.00 + 44.80, Common Area 14840.00 + 296.80. The map keeps the overhead as its own detail rows in both periods; only the bill layout differs (a separate line in 2024-01, folded into the lines in 2025-01) ==';
;WITH Expected(Invoice, Account, BaseAmt, OhAmt, BillTotal) AS (SELECT v.Invoice, v.Account, v.BaseAmt, v.OhAmt, v.BillTotal FROM (VALUES
    ('TC-MM-2024-01', 'TC-MKT-ANCHOR', 2000.00, 40.00, 2040.00), ('TC-MM-2024-01', 'TC-MKT-FOODCOURT', 4200.00, 84.00, 4284.00), ('TC-MM-2024-01', 'TC-MKT-SHOP1', 2240.00, 44.80, 2284.80),
    ('TC-MM-2024-01', 'TC-MKT-SHOP2', 2240.00, 44.80, 2284.80), ('TC-MM-2024-01', 'TC-MKT-SHOP3', 2240.00, 44.80, 2284.80), ('TC-MM-2024-01', 'TC-MKT-SHOP4', 2240.00, 44.80, 2284.80),
    ('TC-MM-2024-01', 'TC-MKT-COMMON', 14840.00, 296.80, 15136.80),
    ('TC-MM-2025-01', 'TC-MKT-ANCHOR', 2000.00, 40.00, 2040.00), ('TC-MM-2025-01', 'TC-MKT-FOODCOURT', 4200.00, 84.00, 4284.00), ('TC-MM-2025-01', 'TC-MKT-SHOP1', 2240.00, 44.80, 2284.80),
    ('TC-MM-2025-01', 'TC-MKT-SHOP2', 2240.00, 44.80, 2284.80), ('TC-MM-2025-01', 'TC-MKT-SHOP3', 2240.00, 44.80, 2284.80), ('TC-MM-2025-01', 'TC-MKT-SHOP4', 2240.00, 44.80, 2284.80),
    ('TC-MM-2025-01', 'TC-MKT-COMMON', 14840.00, 296.80, 15136.80)) v(Invoice, Account, BaseAmt, OhAmt, BillTotal)),
Actual AS (
    SELECT mb.BL_InvoiceNumber AS Invoice, ba.BA_BillingAccountNumber AS Account, b.BL_Amount AS BillTotal,
           SUM(CASE WHEN d.IsOverhead = 0 THEN d.AllocatedAmount ELSE 0 END) AS BaseAmt, SUM(CASE WHEN d.IsOverhead = 1 THEN d.AllocatedAmount ELSE 0 END) AS OhAmt
    FROM dbo.BillAllocationMap m JOIN dbo.Bill mb ON mb.BL_BillID = m.MasterBillID JOIN dbo.Bill b ON b.BL_BillID = m.AllocatedBillID
    JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = b.BA_BillingAccountID JOIN dbo.BillAllocationMapDetail d ON d.BillAllocationMapID = m.BillAllocationMapID
    WHERE ISNULL(m.DeleteInd, 0) = 0 AND mb.BL_InvoiceNumber IN ('TC-MM-2024-01', 'TC-MM-2025-01') GROUP BY mb.BL_InvoiceNumber, ba.BA_BillingAccountNumber, b.BL_Amount)
SELECT e.Invoice, e.Account, e.BaseAmt AS ExpectedBase, a.BaseAmt AS ActualBase, e.OhAmt AS ExpectedOverhead, a.OhAmt AS ActualOverhead, e.BillTotal AS ExpectedBill, a.BillTotal AS ActualBill,
       CASE WHEN a.BaseAmt = e.BaseAmt AND a.OhAmt = e.OhAmt AND a.BillTotal = e.BillTotal THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN Actual a ON a.Invoice = e.Invoice AND a.Account = e.Account ORDER BY e.Invoice, e.Account;
GO
PRINT '== ASSERT tenant_bills_sum_to_parent: for each Mall-Main master bill the allocated amounts WITHOUT overhead add up to the master (Diff 0.00) and the overhead is exactly 2% of it (600.00 of 30000.00). Overhead is added on top of the shares, so the old check, which added it in, could never reach Diff 0 ==';
SELECT mb.BL_InvoiceNumber AS Invoice, mb.BL_Amount AS Master, SUM(CASE WHEN d.IsOverhead = 0 THEN d.AllocatedAmount ELSE 0 END) AS SumAllocated,
       mb.BL_Amount - SUM(CASE WHEN d.IsOverhead = 0 THEN d.AllocatedAmount ELSE 0 END) AS Diff, SUM(CASE WHEN d.IsOverhead = 1 THEN d.AllocatedAmount ELSE 0 END) AS Overhead,
       CASE WHEN mb.BL_Amount = SUM(CASE WHEN d.IsOverhead = 0 THEN d.AllocatedAmount ELSE 0 END) AND SUM(CASE WHEN d.IsOverhead = 1 THEN d.AllocatedAmount ELSE 0 END) = ROUND(mb.BL_Amount * 0.02, 2) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.BillAllocationMap m JOIN dbo.Bill mb ON mb.BL_BillID = m.MasterBillID JOIN dbo.BillAllocationMapDetail d ON d.BillAllocationMapID = m.BillAllocationMapID
WHERE ISNULL(m.DeleteInd, 0) = 0 AND mb.BL_InvoiceNumber IN ('TC-MM-2024-01', 'TC-MM-2025-01') GROUP BY mb.BL_InvoiceNumber, mb.BL_Amount ORDER BY mb.BL_InvoiceNumber;
GO
PRINT '== ASSERT methods_2_3_4_5_7_not_computed_today: the master bill exists and NO allocated bill was made for it (the stock engine has no calculator for these methods, file 04). If a row reads FAIL with Actual above 0, a calculator has shipped: compare with the reference table in file 10 and change the expectation ==';
;WITH Expected(Invoice, Method_) AS (SELECT v.Invoice, v.Method_ FROM (VALUES ('TC-TM-2024-01', 2), ('TC-TM-2025-01', 3), ('TC-MM-2026-01', 4), ('TC-AM-2024-01', 5), ('TC-SM-2024-01', 7)) v(Invoice, Method_))
SELECT e.Invoice, e.Method_ AS Method, 0 AS Expected, (SELECT COUNT(*) FROM dbo.BillAllocationMap m JOIN dbo.Bill b ON b.BL_BillID = m.MasterBillID WHERE b.BL_InvoiceNumber = e.Invoice AND ISNULL(m.DeleteInd, 0) = 0) AS Actual,
       (SELECT COUNT(*) FROM dbo.Bill b WHERE b.BL_InvoiceNumber = e.Invoice) AS MasterBillExists,
       CASE WHEN (SELECT COUNT(*) FROM dbo.BillAllocationMap m JOIN dbo.Bill b ON b.BL_BillID = m.MasterBillID WHERE b.BL_InvoiceNumber = e.Invoice AND ISNULL(m.DeleteInd, 0) = 0) = 0
             AND (SELECT COUNT(*) FROM dbo.Bill b WHERE b.BL_InvoiceNumber = e.Invoice) = 1 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e;
GO
PRINT '== ASSERT method_6_property_total: the Property Total account holds one aggregate bill per period with a feeder bill: 2024-01 30600.00 and 2025-01 30600.00 (the seven Mall-Main tenant bills), 2026-01 1548.24 (the generated bills of Shop 1 878.28 and Shop 2 669.96; 7842.84 if Food Court''s Manual bill has been created, 6294.60 more) ==';
;WITH Expected(FY, FP, Amount) AS (SELECT v.FY, v.FP, v.Amount FROM (VALUES (2024, 1, 30600.00), (2025, 1, 30600.00), (2026, 1, 1548.24)) v(FY, FP, Amount))
SELECT e.FY, e.FP, e.Amount AS Expected, (SELECT SUM(b.BL_Amount) FROM dbo.Bill b JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = b.BA_BillingAccountID WHERE ba.BA_BillingAccountNumber = 'TC-PROPERTY-TOTAL' AND b.BL_FiscalYear = e.FY AND b.BL_FiscalPeriodNo = e.FP AND ISNULL(b.DeleteInd, 0) = 0) AS Actual,
       CASE WHEN (SELECT SUM(b.BL_Amount) FROM dbo.Bill b JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = b.BA_BillingAccountID WHERE ba.BA_BillingAccountNumber = 'TC-PROPERTY-TOTAL' AND b.BL_FiscalYear = e.FY AND b.BL_FiscalPeriodNo = e.FP AND ISNULL(b.DeleteInd, 0) = 0) = e.Amount THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e ORDER BY e.FY;
GO
PRINT '== ASSERT generated_tenant_bills_2026_01: after Run Bill Gen Run Now. Anchor Store (Off): no bill. Food Court (Manual): no bill until Create is pressed, 6294.60 after. Shop 1 (Auto) 878.28 and Shop 2 (Auto w/ Auto Regen) 669.96, each with a 45.00 customer line and an energy line (kWh 5952 and 4464) ==';
;WITH Expected(Account, Amount, Kwh) AS (SELECT v.Account, v.Amount, v.Kwh FROM (VALUES ('TC-MKT-SHOP1', 878.28, 5952), ('TC-MKT-SHOP2', 669.96, 4464)) v(Account, Amount, Kwh))
SELECT e.Account, e.Amount AS ExpectedBill, b.BL_Amount AS ActualBill, e.Kwh AS ExpectedKwh, (SELECT MAX(bi.BI_Quantity) FROM dbo.BillItem bi WHERE bi.BL_BillID = b.BL_BillID AND ISNULL(bi.DeleteInd, 0) = 0) AS ActualKwh,
       (SELECT COUNT(*) FROM dbo.BillItem bi WHERE bi.BL_BillID = b.BL_BillID AND ISNULL(bi.DeleteInd, 0) = 0) AS Lines,
       CASE WHEN ROUND(b.BL_Amount, 2) = e.Amount THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountNumber = e.Account
LEFT JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND b.BL_FiscalYear = 2026 AND b.BL_FiscalPeriodNo = 1 AND ISNULL(b.DeleteInd, 0) = 0
UNION ALL
SELECT ba.BA_BillingAccountNumber, NULL, NULL, NULL, NULL, COUNT(b.BL_BillID),
       CASE WHEN ba.BA_BillingAccountNumber = 'TC-MKT-ANCHOR' AND COUNT(b.BL_BillID) = 0 THEN 'PASS'
            WHEN ba.BA_BillingAccountNumber = 'TC-MKT-FOODCOURT' AND (COUNT(b.BL_BillID) = 0 OR (COUNT(b.BL_BillID) = 1 AND MAX(ROUND(b.BL_Amount, 2)) = 6294.60)) THEN 'PASS' ELSE 'FAIL' END
FROM dbo.BillingAccount_TBL ba LEFT JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND b.BL_FiscalYear = 2026 AND b.BL_FiscalPeriodNo = 1 AND ISNULL(b.DeleteInd, 0) = 0
WHERE ba.BA_BillingAccountNumber IN ('TC-MKT-ANCHOR', 'TC-MKT-FOODCOURT') GROUP BY ba.BA_BillingAccountNumber;
GO
PRINT '== ASSERT reconciliation_anchor_store: the Bill checkbox created the Bill Meter Reconciliation row (schedule BL, status 4, Interval, 202401 to 999901) and, after Run Bill Gen, the log has one row per allocated Anchor Store bill (2024-01 and 2025-01), each with MasterBillID set. Billed is 2040.00 in both; the Calculated amount (15000.00, variance -12960.00) is read on the Bill Reconciliation report, Fiscal Year 2024 / Period 1 and 2025 / 1 ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'reconciliation Bill Generation rows on Anchor Store (BL, status 4, source 1, 202401, 999901)' AS Item, 1 AS Expected,
           (SELECT COUNT(*) FROM dbo.UtilityMeterRatesBillGen g JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = g.MetaWorldID JOIN dbo.BillScenario bs ON bs.BillScenarioId = g.BillScenarioID
              WHERE mw.Description = 'Anchor Store' AND bs.ScenarioTypeId = 20 AND g.BillGenScheduleCode = 'BL' AND g.BillGenStatusID = 4 AND g.BillGenReconDataSourceID = 1 AND g.FiscalStart = 202401 AND g.FiscalEnd = 999901) AS Actual
    UNION ALL SELECT 'log rows with a MasterBillID (one per allocated Anchor Store bill)', 2,
           (SELECT COUNT(*) FROM dbo.UtilityBillGenLog l JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = l.MetaWorldID JOIN dbo.BillScenario bs ON bs.BillScenarioId = l.BillScenarioID
              WHERE mw.Description = 'Anchor Store' AND bs.ScenarioTypeId = 20 AND l.MasterBillID IS NOT NULL)
    UNION ALL SELECT 'Billed (the 2024-01 allocated bill on Anchor Store''s account)', 204000,
           (SELECT CAST(ROUND(b.BL_Amount * 100, 0) AS int) FROM dbo.Bill b JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = b.BA_BillingAccountID WHERE ba.BA_BillingAccountNumber = 'TC-MKT-ANCHOR' AND b.BL_FiscalYear = 2024 AND b.BL_FiscalPeriodNo = 1 AND ISNULL(b.DeleteInd, 0) = 0)
) x;
GO

PRINT '== LIST allocation_runs: dbo.PtAllocationProcessLog rows for 2024-01 through 2024-03 (file 07); no known count ==';
SELECT ProcessKey, StartTime, Status, PtsForDisaggregation, PtsDisaggregated, NewBills, FiscalYear, FiscalPeriod
FROM dbo.PtAllocationProcessLog WHERE FiscalYear = 2024 AND FiscalPeriod IN (1, 2, 3) ORDER BY StartTime;
GO
PRINT '== ASSERT task_catalog: Task_Tbl 24, 42 and 47 present; Tenant Rebilling catalog 11 of 14 reports registered (accrual reports missing, a product finding) ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'Task_Tbl 24, 42, 47' AS Item, 3 AS Expected, (SELECT COUNT(*) FROM dbo.Task_Tbl WHERE TaskID IN (24, 42, 47)) AS Actual
    UNION ALL SELECT 'rp_BillReconciliation present', 1, (SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_NAME = 'rp_BillReconciliation')
    UNION ALL SELECT 'Tenant Rebilling reports in GuiReports_Tbl', 11, (SELECT COUNT(*) FROM dbo.GuiReports_Tbl WHERE ObjectName IN ('rp_TenantMap','rp_BillAllocationConfiguration','rp_BillGenerationConfig','rp_BillReconciliation','rp_RateAllocation','rp_TenantBillAllocationMap','rp_TenantBillAudit','rp_TenantBillDefinition','rp_WUIPointFamilyConfig','rp_WUIPointUseHistory','rp_WUIProcessMeterAllocations'))
    UNION ALL SELECT 'accrual reports registered (product finding: 0)', 0, (SELECT COUNT(*) FROM dbo.GuiReports_Tbl WHERE ObjectName IN ('rp_accruals','rp_mpaaccruals','rp_OpenAccruals'))
) x;
GO

-- Step 8, Ridgeline Wind (added 2026-10-01). The last four read Stage 3's turbine data and the statements Run Bill Gen
-- writes, so they fill in last. Account SYN-RWL-G-0000001 has one generating meter, never one of the ten pad meters.
-- These read BillingAccount_TBL, not the BillingAccount view, which a sqlcmd session with no EEM user sees empty.
PRINT '== ASSERT ridgeline_setup: the billing meter is one Electricity meter on SYN-RWL-G-0000001, provider Ridgeline Wind, Bill Cycle 1, with 10 Required aggregate members; both RWL-XFER-2024 determinants are mapped; exactly one generation row (CC, Auto, 202407 to 202512, Interval, Available % 100, Offset 0, RWL-XFER-2024 from 2024-07-01) ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'billing meter rows (Ridgeline Farm Transfer Meter, Electricity, Ridgeline Wind, cycle 1)' AS Item, 1 AS Expected,
           (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.Meter m ON m.MetaWorldID = mw.MetaWorldID JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
              JOIN dbo.UtilityProvider up ON up.ProviderID = ba.ProviderID JOIN dbo.MeasureType ms ON ms.MT_MeasureTypeID = m.MT_MeasureTypeID
              WHERE mw.Description = 'Ridgeline Farm Transfer Meter' AND ISNULL(mw.DeleteInd, 0) = 0 AND ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND up.Name = 'Ridgeline Wind' AND m.BillCycle = 1 AND ms.MT_MeasureName = 'Electricity') AS Actual
    UNION ALL SELECT 'Required aggregate members at multiplier 1', 10,
           (SELECT COUNT(*) FROM dbo.MetaWorld_TBL mw JOIN dbo.MetaWorld_TBL pn ON pn.ParentID = mw.MetaWorldID JOIN dbo.PointAggregatePoints x ON x.AggregatePtID = pn.PtID
              WHERE mw.Description = 'Ridgeline Farm Transfer Meter' AND x.Required = 1 AND x.Multiplier = 1)
    UNION ALL SELECT 'RWL-XFER-2024 determinants with a commodity mapping', 2,
           (SELECT COUNT(*) FROM dbo.UtilityRate_Tbl r JOIN dbo.UtilityRateClass rc ON rc.UtilityRateID = r.UtilityRateID JOIN dbo.UtilityRateDeterminant rd ON rd.RateClassID = rc.RateClassID
              JOIN dbo.UtilityCommodityMap cm ON cm.UtilityRateID = r.UtilityRateID AND cm.DeterminantID = rd.DeterminantID WHERE r.Name = 'RWL-XFER-2024' AND cm.ChargesCommodityID IS NOT NULL)
    UNION ALL SELECT 'generation rows on SYN-RWL-G-0000001 (CC, status 3, 202407 to 202512, Interval, 100, offset 0)', 1,
           (SELECT COUNT(*) FROM dbo.UtilityMeterRatesBillGen g JOIN dbo.Meter m ON m.MetaWorldID = g.MetaWorldID JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
              WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND g.BillGenScheduleCode = 'CC' AND g.BillGenStatusID = 3 AND g.FiscalStart = 202407 AND g.FiscalEnd = 202512 AND g.BillGenReconDataSourceID = 1 AND g.DataThreshold IN (100, 99) AND g.OffsetDays = 0)
    UNION ALL SELECT 'generation log rows (18 months)', 18,
           (SELECT COUNT(*) FROM dbo.UtilityBillGenLog l JOIN dbo.Meter m ON m.MetaWorldID = l.MetaWorldID JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001')
    UNION ALL SELECT 'generated statements, one per month (18 bills)', 18,
           (SELECT COUNT(*) FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND ISNULL(bl.DeleteInd, 0) = 0)
    UNION ALL SELECT 'generated statements whose two lines do not add to the rounded total', 0,
           (SELECT COUNT(*) FROM (SELECT bl.BL_BillID FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID LEFT JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND ISNULL(bi.DeleteInd, 0) = 0
              WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND ISNULL(bl.DeleteInd, 0) = 0 GROUP BY bl.BL_BillID, bl.BL_Amount HAVING COUNT(bi.BI_BillItemID) <> 2 OR ROUND(bl.BL_Amount, 2) <> SUM(bi.BI_Amount)) t)
    UNION ALL SELECT 'July 2024 statement, cents (129330.27)', 12933027,
           (SELECT CAST(ROUND(ROUND(bl.BL_Amount, 2) * 100, 0) AS int) FROM dbo.Bill bl JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND bl.BL_FiscalYear = 2024 AND bl.BL_FiscalPeriodNo = 7 AND ISNULL(bl.DeleteInd, 0) = 0)
) x;
GO
PRINT '== LIST ridgeline_billing_meter: Ridgeline Farm Transfer Meter (Stage 2, SYN-RWL-M-0110000) is one Electricity meter on SYN-RWL-G-0000001, provider Ridgeline Wind, Bill Cycle 1; its one point is the farm aggregate Ridgeline Farm Generated kWh 10m with 10 Required members at multiplier 1 and a registered aggregate (AggregateID above 0, PRODUCT FINDING 14) ==';
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
PRINT '== LIST ridgeline_commodity_mapping: both RWL-XFER-2024 determinants (Transfer energy 200, Research credit 400) have a UtilityCommodityMap row, because an unmapped one adds to the bill total and writes no line; the rate class is in force for a meter (ClassType 0, or at least one default option; Stage 4 owns both, step 8 depends on them) ==';
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
PRINT '== LIST ridgeline_generation_config: exactly one generation row on SYN-RWL-G-0000001, on the billing meter and on no pad meter: Actual, 202407 to 202512, schedule CC, Auto, Interval data (1), Available % 100 (99 only during the one-off March 2025 run), Offset 0, rate RWL-XFER-2024 from 2024-07-01; the second result set is every rate assignment on the account''s meters and must be that one row, on the billing meter (Stage 4 assigns it there only, Bill unchecked) ==';
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
PRINT '== LIST ridgeline_generation_log: one log row per month 2024-07 to 2025-12 (18); Available should equal Expected (4464 in a 31-day month at 10 minutes) once Stage 3''s data (the rows stamped 2024-06-30 23:10 PST through 2026-01-01 00:00 PST, each an interval end) and the aggregate are in, and BillID is filled once Run Bill Gen has written the statement; a month under Available % waits with BillID null, which is March 2025 (4458 of 4464, Pacific time skips an hour) until its one-off Available % 99 run; July 2024 at 4458 means the feed started at the SCADA''s own July 1, and December 2025 at 4463 means it stopped before the row stamped 2026-01-01 00:00 (the 08 stamp note) ==';
SELECT l.FiscalCal, CONVERT(char(10), l.StartDate, 120) AS ServiceFrom, CONVERT(char(10), l.EndDate, 120) AS ServiceTo, l.AvailableIntervals, l.ExpectedIntervals,
       CAST(100.0 * l.AvailableIntervals / NULLIF(l.ExpectedIntervals, 0) AS decimal(6, 2)) AS PctAvailable, l.IsNewData, l.BillID
FROM dbo.UtilityBillGenLog l JOIN dbo.Meter m ON m.MetaWorldID = l.MetaWorldID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = m.BA_BillingAccountID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' ORDER BY l.FiscalCal;
GO
PRINT '== LIST ridgeline_generated_statements: one bill per month on SYN-RWL-G-0000001 (the second result set must be empty), each with exactly 2 lines, the research credit -1250.00 once and no adjustment line, and the lines adding to ROUND(BL_Amount, 2) (Diff 0.00; BL_Amount itself keeps four decimals); the WTG-07 outage months 2025-02 to 2025-04 are included and lower ==';
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
PRINT '== ASSERT ridgeline_acceptance_2024_07 (1 of 2): each turbine''s July 2024 Generated kWh 10m summed over the engine''s window (the stored Pacific LocalTimeStamp after 2024-07-01 00:00 and up to and including 2024-08-01 00:00) against the hand-made statement: Diff 0 on all ten and on the farm total 2251384, Intervals 4464 on each; a Diff here beside a clean Stage 3 ridgeline_period_totals is the interval-start versus interval-end stamp question in the 08 notes ==';
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
PRINT '== ASSERT ridgeline_acceptance_2024_07 (2 of 2): the generated July 2024 statement equals the hand-made one to the cent: Rounded 129330.27 (Diff 0.00), two lines, 130580.27 on 2251384 kWh and -1250.00 ==';
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
PRINT '== LIST ridgeline_outage_months: WTG-07 (SYN-RWL-M-0110007) Generated kWh 10m by month: zero from 2025-02-11 to 2025-04-22 with every interval still present (lost production, not missing data), so March reads 0 kWh with all its intervals; the Feb to Apr statements above are lower and keep the same two lines ==';
SELECT CONVERT(char(7), DATEADD(second, -1, a.LocalTimeStamp), 120) AS DataMonth, SUM(a.Value) AS Wtg07Kwh, COUNT(a.Value) AS Intervals, SUM(CASE WHEN a.Value = 0 THEN 1 ELSE 0 END) AS ZeroIntervals
FROM dbo.Meter m JOIN dbo.MetaWorld_TBL pn ON pn.ParentID = m.MetaWorldID
JOIN dbo.PointDef_TBL p ON p.PtID = pn.PtID AND p.Description = 'Generated kWh 10m'
JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.LocalTimeStamp > '2025-01-01' AND a.LocalTimeStamp <= '2025-06-01'
WHERE m.SM_Code = 'SYN-RWL-M-0110007'
GROUP BY CONVERT(char(7), DATEADD(second, -1, a.LocalTimeStamp), 120) ORDER BY DataMonth;
GO
