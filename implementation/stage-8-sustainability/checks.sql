-- Stage 8 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- Rewritten 2026-11-10. ASSERT blocks return Expected, Actual and a Result column (PASS or FAIL); LIST blocks have no
-- known value. Several blocks return FAIL or no rows until Stages 2 to 5 exist and the hourly warehouse job (task 23,
-- Stage 9) has run: GHG rows and the 132 automatic mappings appear only after it. Filters are by name, not ID.
-- The three companies below are Northlake University (6), Cedar Row Apartments (3) and Northlake Thermal Plant (5).
SET NOCOUNT ON;

PRINT '== ASSERT emission_sources_and_members: eGRID / CAMX (WECC California, member 67) and Non-electric commodities / Non-electric commodities (member 3) both present ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT 'members 67 and 3 present' AS Item, 2 AS Expected,
        (SELECT COUNT(*) FROM dbo.EmissionFactorSource s JOIN dbo.EmissionFactorSourceMember m ON m.EmissionFactorSourceID = s.EmissionFactorSourceID WHERE m.EmissionFactorSourceMemberID IN (67, 3)) AS Actual) x;
GO

PRINT '== ASSERT emission_factor_history_2024_2025: the dated rows of step 1, value against value (CAMX CO2 410 then 395, CH4 0.024 then 0.023, N2O 0.0029 then 0.0028 lbs/MWh; natural gas 0.0531 then 0.0537 tonne per MBtu) ==';
;WITH Expected(FactorId, StartDate, Value_) AS (SELECT v.FactorId, CONVERT(date, v.StartDate), v.Value_ FROM (VALUES
    (175, '2024-01-01', 410.0), (175, '2025-01-01', 395.0), (201, '2024-01-01', 0.024), (201, '2025-01-01', 0.023),
    (227, '2024-01-01', 0.0029), (227, '2025-01-01', 0.0028), (12, '2024-01-01', 0.0531), (12, '2025-01-01', 0.0537)) v(FactorId, StartDate, Value_))
SELECT e.FactorId, e.StartDate, e.Value_ AS Expected, h.EmissionFactor AS Actual, CASE WHEN ABS(ISNULL(h.EmissionFactor, -1) - e.Value_) < 0.0000001 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.EmissionFactorHistory h ON h.EmissionFactorID = e.FactorId AND CONVERT(date, h.StartDate) = e.StartDate ORDER BY e.FactorId, e.StartDate;
GO

PRINT '== ASSERT ghg_company_config: three companies, baseline 2024 to 2025, default category (Northlake University Indirect, Cedar Row Indirect, Thermal Plant Stationary), two enabled sources each ==';
;WITH Expected(CompanyName, Category, Sources) AS (SELECT v.CompanyName, v.Category, v.Sources FROM (VALUES ('Northlake University', 'Indirect', 2), ('Cedar Row Apartments', 'Indirect', 2), ('Northlake Thermal Plant', 'Stationary', 2)) v(CompanyName, Category, Sources))
SELECT e.CompanyName, e.Category AS ExpectedCategory, cat.Name AS ActualCategory, c.BaseStartYear, c.BaseEndYear, e.Sources AS ExpectedSources,
       (SELECT COUNT(*) FROM dbo.EmissionCompanyConfigDetails d WHERE d.CompanyID = c.CompanyID) AS ActualSources,
       CASE WHEN cat.Name = e.Category AND c.BaseStartYear = 2024 AND c.BaseEndYear = 2025 AND (SELECT COUNT(*) FROM dbo.EmissionCompanyConfigDetails d WHERE d.CompanyID = c.CompanyID) = e.Sources THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.Company_TBL co ON co.CompanyName = e.CompanyName LEFT JOIN dbo.EmissionCompanyConfig c ON c.CompanyID = co.CompanyID LEFT JOIN dbo.EmissionCategory cat ON cat.EmissionCategoryID = c.EmissionCategoryID;
GO

PRINT '== ASSERT meter_emission_assignments: each of the 34 meters assigned by hand has an EmissionMeterMap row in the category of step 2 (electric Indirect, gas Stationary, water Indirect) ==';
;WITH Expected(CompanyName, Meter, Category) AS (SELECT v.CompanyName, v.Meter, v.Category FROM (VALUES
        ('Northlake University', 'Admin Hall Electric Main', 'Indirect'),
        ('Northlake University', 'Science Center Electric Main', 'Indirect'),
        ('Northlake University', 'Science Center Electric Lab Wing', 'Indirect'),
        ('Northlake University', 'Library Electric Old Meter', 'Indirect'),
        ('Northlake University', 'Library Electric New Meter', 'Indirect'),
        ('Northlake University', 'Student Center Electric Main', 'Indirect'),
        ('Northlake University', 'Lakeview Hall Electric Main', 'Indirect'),
        ('Northlake University', 'Recreation Center Electric Main', 'Indirect'),
        ('Northlake University', 'Parking Structure Electric Main', 'Indirect'),
        ('Northlake University', 'Campus Grounds Area Lighting', 'Indirect'),
        ('Cedar Row Apartments', 'Cedar Row A Electric Master', 'Indirect'),
        ('Cedar Row Apartments', 'Cedar Row B Electric Master', 'Indirect'),
        ('Cedar Row Apartments', 'Common House Electric Main', 'Indirect'),
        ('Cedar Row Apartments', 'Cedar Row Parking Lighting', 'Indirect'),
        ('Northlake Thermal Plant', 'Central Plant Electric Service', 'Indirect'),
        ('Northlake University', 'Admin Hall Gas', 'Stationary'),
        ('Northlake University', 'Science Center Gas', 'Stationary'),
        ('Northlake University', 'Library Gas', 'Stationary'),
        ('Northlake University', 'Student Center Kitchen Gas', 'Stationary'),
        ('Northlake University', 'Lakeview Hall Gas', 'Stationary'),
        ('Northlake University', 'Recreation Center Pool Gas', 'Stationary'),
        ('Cedar Row Apartments', 'Cedar Row A Gas House', 'Stationary'),
        ('Cedar Row Apartments', 'Cedar Row B Gas House', 'Stationary'),
        ('Cedar Row Apartments', 'Common House Gas', 'Stationary'),
        ('Northlake Thermal Plant', 'Central Plant Boiler Gas', 'Stationary'),
        ('Northlake University', 'Admin Hall Domestic Water', 'Indirect'),
        ('Northlake University', 'Science Center Domestic Water', 'Indirect'),
        ('Northlake University', 'Library Domestic Water', 'Indirect'),
        ('Northlake University', 'Student Center Domestic Water', 'Indirect'),
        ('Northlake University', 'Lakeview Hall Domestic Water', 'Indirect'),
        ('Northlake University', 'Recreation Center Domestic Water', 'Indirect'),
        ('Cedar Row Apartments', 'Cedar Row A Water Master', 'Indirect'),
        ('Cedar Row Apartments', 'Cedar Row B Water Master', 'Indirect'),
        ('Northlake Thermal Plant', 'Ridgeline Interconnection Meter', 'Indirect')) v(CompanyName, Meter, Category))
SELECT e.CompanyName, e.Meter, e.Category AS Expected, cat.Name AS Actual, CASE WHEN cat.Name = e.Category THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e JOIN dbo.Company_TBL co ON co.CompanyName = e.CompanyName
LEFT JOIN dbo.MetaWorld_TBL mw ON mw.CompanyID = co.CompanyID AND mw.Description = e.Meter AND ISNULL(mw.DeleteInd, 0) = 0
LEFT JOIN dbo.EmissionMeterMap emm ON emm.MeterID = mw.MetaWorldID LEFT JOIN dbo.EmissionCategory cat ON cat.EmissionCategoryID = emm.EmissionCategoryID ORDER BY e.CompanyName, e.Meter;
GO
PRINT '== ASSERT meter_exclusions: the 14 excluded meters (ten Ridgeline turbines, three Helios arrays, the Ridgeline Farm Transfer Meter) are in EmissionDisabledMeters and have no mapping; the warehouse job maps every unexcluded California Electricity meter of a company with eGRID enabled, so an unexcluded generation meter is a defect ==';
;WITH Expected(CompanyName, Meter) AS (SELECT v.CompanyName, v.Meter FROM (VALUES
        ('Northlake Thermal Plant', 'Ridgeline WTG-01'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-02'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-03'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-04'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-05'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-06'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-07'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-08'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-09'),
        ('Northlake Thermal Plant', 'Ridgeline WTG-10'),
        ('Northlake University', 'Science Center PV Array'),
        ('Northlake University', 'Student Center PV Array'),
        ('Cedar Row Apartments', 'Cedar Row Solar Carport'),
        ('Northlake Thermal Plant', 'Ridgeline Farm Transfer Meter')) v(CompanyName, Meter))
SELECT e.CompanyName, e.Meter, 1 AS ExpectedExcluded, (SELECT COUNT(*) FROM dbo.EmissionDisabledMeters d WHERE d.MeterID = mw.MetaWorldID) AS ActualExcluded,
       0 AS ExpectedMappings, (SELECT COUNT(*) FROM dbo.EmissionMeterMap m WHERE m.MeterID = mw.MetaWorldID) AS ActualMappings,
       CASE WHEN (SELECT COUNT(*) FROM dbo.EmissionDisabledMeters d WHERE d.MeterID = mw.MetaWorldID) = 1 AND (SELECT COUNT(*) FROM dbo.EmissionMeterMap m WHERE m.MeterID = mw.MetaWorldID) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e JOIN dbo.Company_TBL co ON co.CompanyName = e.CompanyName LEFT JOIN dbo.MetaWorld_TBL mw ON mw.CompanyID = co.CompanyID AND mw.Description = e.Meter AND ISNULL(mw.DeleteInd, 0) = 0
ORDER BY e.CompanyName, e.Meter;
GO
PRINT '== ASSERT auto_assignment_totals: meters with an EmissionMeterMap row in the three companies are 34 before the warehouse job runs and 166 after (34 by hand + the 132 owned Electricity meters that have no billing account and no bill, step 2 notes); excluded meters in the three companies are 14 ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Actual IN (x.Expected, x.ExpectedAfterJob) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'mapped meters (34 before the job, 166 after)' AS Item, 34 AS Expected, 166 AS ExpectedAfterJob,
           (SELECT COUNT(DISTINCT emm.MeterID) FROM dbo.EmissionMeterMap emm JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = emm.MeterID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
              WHERE c.CompanyName IN ('Northlake University', 'Cedar Row Apartments', 'Northlake Thermal Plant')) AS Actual
    UNION ALL SELECT 'excluded meters', 14, 14,
           (SELECT COUNT(*) FROM dbo.EmissionDisabledMeters d JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = d.MeterID JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
              WHERE c.CompanyName IN ('Northlake University', 'Cedar Row Apartments', 'Northlake Thermal Plant'))
) x;
GO
PRINT '== ASSERT ghg_known_values (pounds in WH_GHG_Tbl, CO2 row): Central Plant Electric Service 2024-09, 1512400 kWh x 410 lbs/MWh = 620084.00; Ridgeline Interconnection Meter 2024-08, 4428 kWh = 1815.48 and 2025-02, 46920 kWh x 395 = 18533.40; no row at all for an excluded generation meter. Tolerance 1 lb. Rows exist only after the warehouse job and the bills (Stage 5) ==';
;WITH Expected(Meter, FiscalCal, Pounds) AS (SELECT v.Meter, v.FiscalCal, v.Pounds FROM (VALUES ('Central Plant Electric Service', 202409, 620084.00), ('Ridgeline Interconnection Meter', 202408, 1815.48), ('Ridgeline Interconnection Meter', 202502, 18533.40)) v(Meter, FiscalCal, Pounds))
SELECT e.Meter, e.FiscalCal, e.Pounds AS Expected, SUM(g.PeriodEmmission) AS Actual, CASE WHEN ABS(ISNULL(SUM(g.PeriodEmmission), -1) - e.Pounds) <= 1 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.MetaWorld_TBL mw ON mw.Description = e.Meter AND ISNULL(mw.DeleteInd, 0) = 0
LEFT JOIN dbo.WH_GHG_Tbl g ON g.MetaWorldID = mw.MetaWorldID AND g.FiscalCal = e.FiscalCal LEFT JOIN dbo.EmissionType et ON et.EmissionTypeID = g.EmissionTypeID AND et.Name = 'CO2'
WHERE et.EmissionTypeID IS NOT NULL OR g.MetaWorldID IS NULL GROUP BY e.Meter, e.FiscalCal, e.Pounds
UNION ALL
SELECT 'GHG rows for excluded generation meters (turbines, Helios arrays, Farm Transfer Meter)', NULL, 0, COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.WH_GHG_Tbl g JOIN dbo.EmissionDisabledMeters d ON d.MeterID = g.MetaWorldID;
GO

PRINT '== ASSERT es_properties: 13 properties with Year Built, Occupancy Percentage, Primary Use, number of property uses and number of included energy meters as entered in step 4 (Admin Hall 2 uses 85,000 sq ft; the Central Plant 0 meters on purpose) ==';
;WITH Expected(Property, YearBuilt, Occupancy, PrimaryUse, Uses, Meters) AS (SELECT v.Property, v.YearBuilt, v.Occupancy, v.PrimaryUse, v.Uses, v.Meters FROM (VALUES
        ('Northlake Main Campus', 1965, 90, 'College/University', 1, 0),
        ('Admin Hall', 1998, 95, 'Office', 2, 3),
        ('Science Center', 2008, 90, 'Laboratory', 2, 6),
        ('Library', 1992, 90, 'Library', 1, 4),
        ('Student Center', 2003, 85, 'Food Service', 2, 4),
        ('Lakeview Residence Hall', 2010, 95, 'Residence Hall/Dormitory', 1, 3),
        ('Recreation and Aquatics Center', 2015, 90, 'Fitness Center/Health Club/Gym', 2, 4),
        ('Parking Structure', 2019, 100, 'Parking', 1, 1),
        ('Cedar Row Apartments', 2012, 95, 'Multifamily Housing', 2, 0),
        ('Cedar Row A', 2012, 95, 'Multifamily Housing', 1, 2),
        ('Cedar Row B', 2014, 95, 'Multifamily Housing', 1, 2),
        ('Cedar Row Common House', 2013, 100, 'Other - Recreation', 1, 2),
        ('Central Plant', 1988, 100, 'Other - Utility', 1, 0)) v(Property, YearBuilt, Occupancy, PrimaryUse, Uses, Meters))
SELECT e.Property, e.YearBuilt AS ExpectedYear, f.YearBuilt AS ActualYear, e.Occupancy AS ExpectedOccupancy, f.OccupancyPercentage AS ActualOccupancy, e.PrimaryUse AS ExpectedUse, f.PrimaryFunction AS ActualUse,
       e.Uses AS ExpectedUses, (SELECT COUNT(*) FROM dbo.ESFacilitySpaceType st WHERE st.ESFacilityID = f.ESFacilityID) AS ActualUses,
       e.Meters AS ExpectedMeters, (SELECT COUNT(*) FROM dbo.ESFacilityMeter fm WHERE fm.ESFacilityID = f.ESFacilityID) AS ActualMeters,
       CASE WHEN f.YearBuilt = e.YearBuilt AND f.OccupancyPercentage = e.Occupancy AND f.PrimaryFunction = e.PrimaryUse AND (SELECT COUNT(*) FROM dbo.ESFacilitySpaceType st WHERE st.ESFacilityID = f.ESFacilityID) = e.Uses
             AND (SELECT COUNT(*) FROM dbo.ESFacilityMeter fm WHERE fm.ESFacilityID = f.ESFacilityID) = e.Meters THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e LEFT JOIN dbo.MetaWorld_TBL mw ON mw.Description = e.Property AND ISNULL(mw.DeleteInd, 0) = 0 LEFT JOIN dbo.ESFacility f ON f.ESFacilityID = mw.MetaWorldID ORDER BY e.Property;
GO
PRINT '== ASSERT es_requests: 20 requests: Lakeview Hall 8 and Cedar Row Apartments 8 (quarterly 2024 and 2025), Admin Hall 2, Science Center 1, Central Plant 1; 0 scores until Portfolio Manager is connected ==';
;WITH Expected(Property, Requests) AS (SELECT v.Property, v.Requests FROM (VALUES ('Lakeview Residence Hall', 8), ('Cedar Row Apartments', 8), ('Admin Hall', 2), ('Science Center', 1), ('Central Plant', 1)) v(Property, Requests))
SELECT e.Property, e.Requests AS Expected, (SELECT COUNT(*) FROM dbo.ESRequestFacility rf JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = rf.ESFacilityID WHERE mw.Description = e.Property) AS Actual,
       CASE WHEN (SELECT COUNT(*) FROM dbo.ESRequestFacility rf JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = rf.ESFacilityID WHERE mw.Description = e.Property) = e.Requests THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e
UNION ALL SELECT 'ESResponseFacility rows (scores)', 0, COUNT(*), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END FROM dbo.ESResponseFacility;
GO

PRINT '== ASSERT weather_regression: baseline end 2025 / 12 for Northlake University and four regressions (Science Center, Student Center and Lakeview Hall electric mains; Admin Hall gas) with Year Ending 2025/12, Data Count 12, Adjusted R2 at or above 0.5 (assumed), cooling factor above 0 on the electric meters and heating factor above 0 on the gas meter ==';
SELECT x.Item, x.Expected, x.Actual, CASE WHEN x.Expected = x.Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT 'wnDefaultFY for Northlake University' AS Item, 2025 AS Expected, (SELECT Value_I FROM dbo.SysConstants WHERE Item = 'wnDefaultFY_6') AS Actual
    UNION ALL SELECT 'wnDefaultFP for Northlake University', 12, (SELECT Value_I FROM dbo.SysConstants WHERE Item = 'wnDefaultFP_6')
    UNION ALL SELECT 'regressions with Year Ending 2025/12 and Data Count 12', 4,
           (SELECT COUNT(*) FROM dbo.FF_wnRegressionBestResults r JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = r.MeterID
              WHERE mw.Description IN ('Science Center Electric Main', 'Student Center Electric Main', 'Lakeview Hall Electric Main', 'Admin Hall Gas') AND r.FiscalYearEnd = 2025 AND r.FiscalPeriodEnd = 12 AND r.DataRowCount = 12)
    UNION ALL SELECT 'of them with Adjusted R2 at or above 0.5', 4,
           (SELECT COUNT(*) FROM dbo.FF_wnRegressionBestResults r JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = r.MeterID
              WHERE mw.Description IN ('Science Center Electric Main', 'Student Center Electric Main', 'Lakeview Hall Electric Main', 'Admin Hall Gas') AND r.AdjR2 >= 0.5)
    UNION ALL SELECT 'electric regressions with a cooling factor above 0 (Science Center, Student Center)', 2,
           (SELECT COUNT(*) FROM dbo.FF_wnRegressionBestResults r JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = r.MeterID WHERE mw.Description IN ('Science Center Electric Main', 'Student Center Electric Main') AND r.CDDFactor > 0)
    UNION ALL SELECT 'gas regression with a heating factor above 0 (Admin Hall)', 1,
           (SELECT COUNT(*) FROM dbo.FF_wnRegressionBestResults r JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = r.MeterID WHERE mw.Description = 'Admin Hall Gas' AND r.HDDFactor > 0)
) x;
GO

PRINT '== ASSERT benchmark_definitions_builtin: 9 system rows at CompanyID -1 (BenchmarksController is GET-only, product backlog item 7) ==';
SELECT 'system benchmark rows' AS Item, 9 AS Expected, COUNT(*) AS Actual, CASE WHEN COUNT(*) = 9 THEN 'PASS' ELSE 'FAIL' END AS Result FROM dbo.wh_Benchmark WHERE CompanyID = -1;
GO

PRINT '== ASSERT ridgeline_turbines_excluded: 10 rows, Ridgeline WTG-01 to WTG-10, each Excluded = 1 and Mappings = 0 (Excluded, not merely Unassigned: the warehouse job maps any unexcluded electric meter once the plant enables eGRID) ==';
SELECT mw.Description AS Meter, 1 AS ExpectedExcluded, CASE WHEN edm.MeterID IS NULL THEN 0 ELSE 1 END AS Excluded, (SELECT COUNT(*) FROM dbo.EmissionMeterMap emm WHERE emm.MeterID = mw.MetaWorldID) AS Mappings,
       CASE WHEN edm.MeterID IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dbo.EmissionMeterMap emm WHERE emm.MeterID = mw.MetaWorldID) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.MetaWorld_TBL mw LEFT JOIN dbo.EmissionDisabledMeters edm ON edm.MeterID = mw.MetaWorldID
WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline WTG-%' AND EXISTS (SELECT 1 FROM dbo.Meter me WHERE me.MetaWorldID = mw.MetaWorldID) ORDER BY mw.Description;
GO

PRINT '== ASSERT ridgeline_interconnection_assignment: 3 rows, the Ridgeline Interconnection Meter on eGRID / CAMX (WECC California), category Indirect, one each for CO2, CH4 and N2O ==';
SELECT 'interconnection factor rows (CO2, CH4, N2O)' AS Item, 3 AS Expected, COUNT(*) AS Actual, CASE WHEN COUNT(*) = 3 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.MetaWorld_TBL mw JOIN dbo.EmissionMeterMap emm ON emm.MeterID = mw.MetaWorldID JOIN dbo.EmissionCategory cat ON cat.EmissionCategoryID = emm.EmissionCategoryID AND cat.Name = 'Indirect'
JOIN dbo.EmissionFactorMeterMap efmm ON efmm.EmissionMeterMapID = emm.EmissionMeterMapID JOIN dbo.EmissionFactor ef ON ef.EmissionFactorID = efmm.EmissionFactorID
JOIN dbo.EmissionFactorSourceMember m ON m.EmissionFactorSourceMemberID = ef.EmissionFactorSourceMemberID AND m.EmissionFactorSourceMemberID = 67
WHERE mw.CompanyID = 5 AND mw.Description = 'Ridgeline Interconnection Meter';
GO

PRINT '== ASSERT ridgeline_energy_quantities: the energy-class quantity billed to the interconnection meter is station service only, 4428 kWh for 2024-08 and 46920 kWh for 2025-02 (a total near the export means the generation credit was keyed as energy); the Central Plant Electric Service bill posted to 2024-09 carries 1512400 kWh (412800 + 368400 + 731200), the 152792.65 BCT credit being money ==';
;WITH Expected(Meter, FY, FP, Kwh) AS (SELECT v.Meter, v.FY, v.FP, v.Kwh FROM (VALUES ('Ridgeline Interconnection Meter', 2024, 8, 4428.0), ('Ridgeline Interconnection Meter', 2025, 2, 46920.0), ('Central Plant Electric Service', 2024, 9, 1512400.0)) v(Meter, FY, FP, Kwh))
SELECT e.Meter, e.FY, e.FP, e.Kwh AS Expected,
       (SELECT SUM(bi.BI_Quantity) FROM dbo.BillItem bi JOIN dbo.Bill b ON b.BL_BillID = bi.BL_BillID JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID JOIN dbo.Unit u ON u.UN_UnitID = c.UN_UnitID AND u.UT_UnitClassID = 3
          JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bi.MetaWorldID WHERE mw.CompanyID = 5 AND mw.Description = e.Meter AND bi.BI_Exclude = 0 AND b.BL_FiscalYear = e.FY AND b.BL_FiscalPeriodNo = e.FP) AS Actual,
       CASE WHEN ISNULL((SELECT SUM(bi.BI_Quantity) FROM dbo.BillItem bi JOIN dbo.Bill b ON b.BL_BillID = bi.BL_BillID JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID JOIN dbo.Unit u ON u.UN_UnitID = c.UN_UnitID AND u.UT_UnitClassID = 3
          JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bi.MetaWorldID WHERE mw.CompanyID = 5 AND mw.Description = e.Meter AND bi.BI_Exclude = 0 AND b.BL_FiscalYear = e.FY AND b.BL_FiscalPeriodNo = e.FP), -1) = e.Kwh THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Expected e;
GO

PRINT '== ASSERT ridgeline_avoided_emissions_basis: not a GHG report; the ten Generated kWh 10m points summed over July 2024 (the stamps after 2024-07-01 00:00 up to and including 2024-08-01 00:00) are 2251384 kWh, x 0.1866 kgCO2e/kWh = 420108.3 kg (the hand-made statement is the acceptance sample) ==';
SELECT 'July 2024 generated kWh' AS Item, 2251384 AS Expected, SUM(a.Value) AS Actual, CASE WHEN ABS(SUM(a.Value) - 2251384) < 0.5 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.AnalogArchive_TBL a JOIN dbo.MetaWorld_TBL pt ON pt.PtID = a.PtID JOIN dbo.MetaWorld_TBL m ON m.MetaWorldID = pt.ParentID
WHERE m.CompanyID = 5 AND m.Description LIKE 'Ridgeline WTG-%' AND pt.Description = 'Generated kWh 10m' AND a.LocalTimeStamp > '2024-07-01' AND a.LocalTimeStamp <= '2024-08-01';
GO

PRINT '== ASSERT ridgeline_not_benchmarked_or_regressed: 0 rows; no ENERGY STAR property, no ENERGY STAR meter and no weather regression names a Ridgeline node ==';
SELECT 'Ridgeline nodes in ENERGY STAR or the regression' AS Item, 0 AS Expected, COUNT(*) AS Actual, CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (
    SELECT mw.Description FROM dbo.ESFacility f JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = f.ESFacilityID WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%'
    UNION ALL SELECT mw.Description FROM dbo.ESFacilityMeter fm JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = fm.ESMeterID WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%'
    UNION ALL SELECT mw.Description FROM dbo.FF_wnRegressionBestResults r JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = r.MeterID WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%'
) t;
GO
