-- Stage 8 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- Meters/points are not installed yet as of this stage's authoring (Stages 2-7 are running in parallel); several
-- checks below return 0 rows until then. That is expected, not a failure -- rerun after Stage 3's meters land.
-- Added 2026-10-01 (Ridgeline Wind): the seven ridgeline_* checks at the end. They return 0 rows until the Ridgeline meters,
-- points and bills exist (Stages 2, 3 and 5), and they take the Northlake Thermal Plant to be CompanyID 5.
SET NOCOUNT ON;

PRINT '== emission_sources_and_members: eGRID/CAMX (WECC California) and Non-electric commodities/Non-electric commodities, both existing system rows ==';
SELECT s.EmissionFactorSourceID, s.Description AS Source, m.EmissionFactorSourceMemberID, m.Description AS Member
FROM dbo.EmissionFactorSource s JOIN dbo.EmissionFactorSourceMember m ON m.EmissionFactorSourceID = s.EmissionFactorSourceID
WHERE m.EmissionFactorSourceMemberID IN (67, 3) ORDER BY s.EmissionFactorSourceID;
GO

PRINT '== emission_factor_history_2024_2025: 4 rows (CO2/CH4/N2O for CAMX electric, CO2 for gas), each with a 2024-01-01 and 2025-01-01 dated row ==';
SELECT ef.EmissionFactorID, et.Name AS EmissionType, m.Description AS Member, h.StartDate, h.EndDate, h.EmissionFactor
FROM dbo.EmissionFactor ef JOIN dbo.EmissionFactorSourceMember m ON m.EmissionFactorSourceMemberID = ef.EmissionFactorSourceMemberID
JOIN dbo.EmissionType et ON et.EmissionTypeID = ef.EmissionTypeID
JOIN dbo.EmissionFactorHistory h ON h.EmissionFactorID = ef.EmissionFactorID
WHERE ef.EmissionFactorID IN (175, 201, 227, 12) AND h.StartDate >= '2024-01-01'
ORDER BY ef.EmissionFactorID, h.StartDate;
GO

PRINT '== ghg_company_config: 3 rows, CompanyID 6/3/5, BaseStartYear 2024, BaseEndYear 2025 ==';
SELECT CompanyID, EmissionCategoryID, BaseStartYear, BaseEndYear FROM dbo.EmissionCompanyConfig
WHERE CompanyID IN (6, 3, 5) ORDER BY CompanyID;
GO

PRINT '== meter_emission_assignments: 34 assigned meters (16 electric -> CAMX, Indirect, the Ridgeline Interconnection Meter among them; 10 gas -> Non-electric commodities, Stationary; 8 water -> Non-electric commodities, Indirect), one row per attached factor so each electric meter shows three; the 10 Ridgeline turbines are Excluded and not listed here (see ridgeline_turbines_excluded); 0 rows until the meters exist ==';
SELECT mw.CompanyID, c.CompanyName, mw.Description AS Meter, emm.EmissionCategoryID, cat.Name AS Category, efmm.EmissionFactorID
FROM dbo.EmissionMeterMap emm
JOIN dbo.Meter me ON me.MetaWorldID = emm.MeterID
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = emm.MeterID
JOIN dbo.Company_TBL c ON c.CompanyID = mw.CompanyID
JOIN dbo.EmissionCategory cat ON cat.EmissionCategoryID = emm.EmissionCategoryID
LEFT JOIN dbo.EmissionFactorMeterMap efmm ON efmm.EmissionMeterMapID = emm.EmissionMeterMapID
ORDER BY mw.CompanyID, mw.Description;
GO

PRINT '== es_properties: 13 rows (ESFacility), PMPropertyID 0 until Portfolio Manager is connected ==';
SELECT ESFacilityID, PrimaryFunction, YearBuilt, OccupancyPercentage, PMPropertyID, IsReqdDataAvl
FROM dbo.ESFacility ORDER BY ESFacilityID;
GO

PRINT '== es_rating_requests: quarterly requests for Lakeview Hall and Cedar Row Apartments, single requests for Admin Hall/Science Center/Central Plant ==';
SELECT rf.ESRequestFacilityID, rf.ESFacilityID, rf.RatingYear, rf.RatingMonth, r.ESRequestID, r.ESUserRequestID
FROM dbo.ESRequestFacility rf
JOIN dbo.ESRequest r ON r.ESRequestID = rf.ESRequestID
ORDER BY rf.ESFacilityID, rf.RatingYear, rf.RatingMonth;
GO

PRINT '== es_scores_pending_external: 0 rows expected until a sandbox/real Portfolio Manager account is connected and the sync task runs (product backlog item 1) ==';
SELECT ESRequestFacilityID, Rating, RatingYear, RatingMonth, totalGHGEmissions FROM dbo.ESResponseFacility ORDER BY ESRequestFacilityID;
GO

PRINT '== weather_regression_results: 4 rows (Science Center electric, Student Center demand, Admin Hall gas, NTP chilled water), R2 and CVRMSE populated ==';
SELECT FF_wnRegressionBestResultsID, MeterID, FiscalYearEnd, HDDFactor, CDDFactor, R2, CVRMSE
FROM dbo.FF_wnRegressionBestResults ORDER BY MeterID, FiscalYearEnd;
GO

PRINT '== benchmark_definitions_builtin: 9 system rows at CompanyID -1, including Use per area / Spend per area / CO2 per area; BenchmarksController is GET-only so no company-specific row can be added (product backlog item 7) ==';
SELECT BenchmarkID, CompanyID, Description, ObjectName FROM dbo.wh_Benchmark ORDER BY BenchmarkID;
GO

PRINT '== ridgeline_turbines_excluded: 10 rows, Ridgeline WTG-01 to WTG-10, each Excluded = 1 and Mappings = 0 (Excluded on Meter Emission Factor Assignment, not merely Unassigned: the warehouse job maps any unexcluded electric meter once the plant enables eGRID) ==';
SELECT mw.Description AS Meter,
       CASE WHEN edm.MeterID IS NULL THEN 0 ELSE 1 END AS Excluded,
       (SELECT COUNT(*) FROM dbo.EmissionMeterMap emm WHERE emm.MeterID = mw.MetaWorldID) AS Mappings
FROM dbo.MetaWorld_TBL mw
LEFT JOIN dbo.EmissionDisabledMeters edm ON edm.MeterID = mw.MetaWorldID
WHERE mw.CompanyID = 5 AND mw.InternalLevelNbr = 4 AND mw.Description LIKE 'Ridgeline WTG-%'
ORDER BY mw.Description;
GO

PRINT '== ridgeline_interconnection_assignment: 3 rows, the Ridgeline Interconnection Meter on eGRID / CAMX (WECC California), category Indirect, one row each for CO2, CH4 and N2O ==';
SELECT mw.Description AS Meter, cat.Name AS Category, s.Description AS Source, m.Description AS Member, et.Name AS EmissionType
FROM dbo.MetaWorld_TBL mw
JOIN dbo.EmissionMeterMap emm ON emm.MeterID = mw.MetaWorldID
JOIN dbo.EmissionCategory cat ON cat.EmissionCategoryID = emm.EmissionCategoryID
JOIN dbo.EmissionFactorMeterMap efmm ON efmm.EmissionMeterMapID = emm.EmissionMeterMapID
JOIN dbo.EmissionFactor ef ON ef.EmissionFactorID = efmm.EmissionFactorID
JOIN dbo.EmissionFactorSourceMember m ON m.EmissionFactorSourceMemberID = ef.EmissionFactorSourceMemberID
JOIN dbo.EmissionFactorSource s ON s.EmissionFactorSourceID = m.EmissionFactorSourceID
JOIN dbo.EmissionType et ON et.EmissionTypeID = ef.EmissionTypeID
WHERE mw.CompanyID = 5 AND mw.Description = 'Ridgeline Interconnection Meter'
ORDER BY et.EmissionTypeID;
GO

PRINT '== ridgeline_generation_not_in_ghg_history: WH_GHG_Tbl (pounds; what GHG History, Variance and Audit read) has rows for the Ridgeline Interconnection Meter only and none for a Ridgeline WTG meter; the first row is 2024-08 (the first generator bill, 2024-07-01 to 2024-08-04), station service, 4,428 kWh, about 1,815 lb CO2 on the 2024 CAMX row (410 lbs/MWh, assumed in step 1) ==';
SELECT mw.Description AS Meter, g.FiscalCal, et.Name AS EmissionType, g.PeriodEmmission AS Pounds
FROM dbo.WH_GHG_Tbl g
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = g.MetaWorldID
JOIN dbo.EmissionType et ON et.EmissionTypeID = g.EmissionTypeID
WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%'
ORDER BY mw.Description, g.FiscalCal, g.EmissionTypeID;
GO

PRINT '== ridgeline_interconnection_energy_quantity: the energy-class quantity billed to the interconnection meter is station service only, 4428 kWh for 2024-08 (the bill 2024-07-01 to 2024-08-04) and 46920 kWh for 2025-02 (the bill 2025-01-05 to 2025-02-04); a total near the export (about 2.5 million kWh for 2024-08) means the generation credit was entered as energy and GHG History is counting the export as Scope 2 ==';
SELECT b.BL_FiscalYear, b.BL_FiscalPeriodNo, SUM(bi.BI_Quantity) AS EnergyQuantity, u.UN_Units AS Unit
FROM dbo.BillItem bi
JOIN dbo.Bill b ON b.BL_BillID = bi.BL_BillID
JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID
JOIN dbo.Unit u ON u.UN_UnitID = c.UN_UnitID AND u.UT_UnitClassID = 3
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bi.MetaWorldID
WHERE mw.CompanyID = 5 AND mw.Description = 'Ridgeline Interconnection Meter' AND bi.BI_Exclude = 0
GROUP BY b.BL_FiscalYear, b.BL_FiscalPeriodNo, u.UN_Units
ORDER BY b.BL_FiscalYear, b.BL_FiscalPeriodNo;
GO

PRINT '== ridgeline_bct_credit_is_money: the Central Plant Electric Service bill for 2024-08-05 to 2024-09-04 (posted to 2024-09; Valley Electric reads on the 5th) carries 1512400 kWh of energy (412800 + 368400 + 731200); the 152792.65 bill credit received under VED-BCT is money and adds or removes no kWh, so the Central Plant Scope 2 and its ENERGY STAR electricity stay what the meter recorded ==';
SELECT b.BL_FiscalYear, b.BL_FiscalPeriodNo, SUM(bi.BI_Quantity) AS EnergyQuantity, u.UN_Units AS Unit
FROM dbo.BillItem bi
JOIN dbo.Bill b ON b.BL_BillID = bi.BL_BillID
JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID
JOIN dbo.Unit u ON u.UN_UnitID = c.UN_UnitID AND u.UT_UnitClassID = 3
JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = bi.MetaWorldID
WHERE mw.CompanyID = 5 AND mw.Description = 'Central Plant Electric Service' AND bi.BI_Exclude = 0
  AND b.BL_FiscalYear = 2024 AND b.BL_FiscalPeriodNo = 9
GROUP BY b.BL_FiscalYear, b.BL_FiscalPeriodNo, u.UN_Units;
GO

PRINT '== ridgeline_avoided_emissions_basis: not a GHG report; monthly kWh of the ten Generated kWh 10m points and the avoided kg CO2e at the grid factor of the year (eGRID CAMX CO2e, 0.1866 kgCO2e/kWh in 2024 and 0.1798 in 2025); months are cut like the rate engine, the stamps after the first midnight up to and including the next; July 2024 is 2,251,384 kWh and about 420,108 kg (the hand-made statement is the acceptance sample) ==';
SELECT YEAR(DATEADD(MINUTE, -1, a.LocalTimeStamp)) AS Y, MONTH(DATEADD(MINUTE, -1, a.LocalTimeStamp)) AS M,
       SUM(a.Value) AS GeneratedKwh,
       SUM(a.Value) * CASE WHEN YEAR(DATEADD(MINUTE, -1, a.LocalTimeStamp)) = 2024 THEN 0.1866 ELSE 0.1798 END AS AvoidedKgCO2e
FROM dbo.AnalogArchive_TBL a
JOIN dbo.MetaWorld_TBL pt ON pt.PtID = a.PtID
JOIN dbo.MetaWorld_TBL m ON m.MetaWorldID = pt.ParentID
WHERE m.CompanyID = 5 AND m.Description LIKE 'Ridgeline WTG-%' AND pt.Description = 'Generated kWh 10m'
GROUP BY YEAR(DATEADD(MINUTE, -1, a.LocalTimeStamp)), MONTH(DATEADD(MINUTE, -1, a.LocalTimeStamp))
ORDER BY Y, M;
GO

PRINT '== ridgeline_not_benchmarked_or_regressed: 0 rows; no ENERGY STAR property, no ENERGY STAR meter and no weather regression names a Ridgeline node ==';
SELECT 'ESFacility' AS Source, mw.Description
FROM dbo.ESFacility f JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = f.ESFacilityID
WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%'
UNION ALL
SELECT 'ESFacilityMeter', mw.Description
FROM dbo.ESFacilityMeter fm JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = fm.ESMeterID
WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%'
UNION ALL
SELECT 'FF_wnRegressionBestResults', mw.Description
FROM dbo.FF_wnRegressionBestResults r JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = r.MeterID
WHERE mw.CompanyID = 5 AND mw.Description LIKE 'Ridgeline%';
GO
