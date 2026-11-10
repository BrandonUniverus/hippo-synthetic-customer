-- Stage 4 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
SET NOCOUNT ON;

PRINT '== holidays_exist: 1 new holiday set (Northlake Holidays) with 12 dates, plus the system No Holidays set (0 dates) ==';
SELECT h.HolidayID, h.Description, h.IsSystem, COUNT(hd.HolidayDateID) AS Dates
FROM dbo.UtilityHoliday h LEFT JOIN dbo.UtilityHolidayDate hd ON hd.HolidayID = h.HolidayID
GROUP BY h.HolidayID, h.Description, h.IsSystem ORDER BY h.HolidayID;
GO

PRINT '== seasons_and_tou_exist: 5 seasons (0 system + 4 real), 5 time-of-use defs (0 system + 4 real); SeasonID 1 / UtilityTOUID 1 renamed off "New Season"/"Peak Hours" ==';
SELECT SeasonID, Description, IsSystem FROM dbo.UtilitySeason ORDER BY SeasonID;
SELECT UtilityTOUID, HoursOfName, IsSystem FROM dbo.UtilityTOU ORDER BY UtilityTOUID;
GO

PRINT '== schedules_exist: 9 schedules total (0 system default + 1 renamed + 7 new), each resolving to a real Season/Holiday/TOU name ==';
SELECT s.ScheduleID, s.ScheduleName, se.Description AS Season, h.Description AS Holiday, t.HoursOfName AS TimeOfUse, s.IsSystem
FROM dbo.UtilitySchedule s
JOIN dbo.UtilitySeason se ON se.SeasonID = s.SeasonID
JOIN dbo.UtilityHoliday h ON h.HolidayID = s.HolidayID
JOIN dbo.UtilityTOU t ON t.UtilityTOUID = s.UtilityTOUID
ORDER BY s.ScheduleID;
GO

PRINT '== rates_by_provider: 16 rates across 6 providers (VED 5, SGU 2, RCU 5, NTP 2, HOS 1, RWL 1), the real tariffs of 05-rates.yaml (reworked 2026-11-09). The Rate Lab provider and its rates are added to this count when 08-rate-lab.yaml is ready ==';
SELECT r.ProviderID, up.Name AS Provider, COUNT(*) AS Rates
FROM dbo.UtilityRate r JOIN dbo.UtilityProvider up ON up.ProviderID = r.ProviderID
GROUP BY r.ProviderID, up.Name ORDER BY r.ProviderID;
SELECT r.UtilityRateID, up.Name AS Provider, r.Name AS RateName, r.CurrencyID, r.MeasureTypeID, r.Transmission, r.Distribution, r.Commodity
FROM dbo.UtilityRate r JOIN dbo.UtilityProvider up ON up.ProviderID = r.ProviderID ORDER BY r.ProviderID, r.Name;
GO

PRINT '== determinant_kinds_covered: the real tariffs use four kinds: 200 (29), 400 (21), 700 (4) and 800 (6), 60 charges. The other five kinds (100, 210, 300, 500, 600) belong to the Rate Lab and appear when it is entered ==';
SELECT d.DeterminantTypeID, dt.DeterminantTypeName, COUNT(*) AS Determinants
FROM dbo.UtilityDeterminant d JOIN dbo.UtilityDeterminantType dt ON dt.DeterminantTypeID = d.DeterminantTypeID
GROUP BY d.DeterminantTypeID, dt.DeterminantTypeName ORDER BY d.DeterminantTypeID;
GO

PRINT '== rate_classes: every rate has exactly one ClassType 0 class, the All that Add Rate creates, and every class added by hand is ClassType 1: 16 ClassType 0 rows and 9 ClassType 1 rows, the size classes of RCU-W-TIER (4), RCU-IRR (2) and RCU-FIRE (3); the second result set lists any rate without exactly one ClassType 0 class and must be empty; the third lists the nine size classes ==';
SELECT ClassType, COUNT(*) AS Classes FROM dbo.UtilityRateClass GROUP BY ClassType;
SELECT r.Name AS RateName, SUM(CASE WHEN rc.ClassType = 0 THEN 1 ELSE 0 END) AS AlwaysAppliedClasses
FROM dbo.UtilityRate r LEFT JOIN dbo.UtilityRateClass rc ON rc.UtilityRateID = r.UtilityRateID
GROUP BY r.Name HAVING SUM(CASE WHEN rc.ClassType = 0 THEN 1 ELSE 0 END) <> 1;
SELECT rc.RateClassID, rc.Description, rc.ClassType, r.Name AS RateName
FROM dbo.UtilityRateClass rc JOIN dbo.UtilityRate r ON r.UtilityRateID = rc.UtilityRateID
WHERE rc.ClassType = 1 ORDER BY r.Name, rc.RateClassID;
GO

PRINT '== effective_dates_cover_2024_2025: EffectiveDate spans 2024-01-01..2026-01-01, 111 rows; the second result set counts them by rate (VED-TOU-GS 23, VED-TOU-PRI 16, the three Ridgeline-era rates one per charge) ==';
SELECT MIN(dd.EffectiveDate) AS Earliest, MAX(dd.EffectiveDate) AS Latest, COUNT(*) AS TotalEffectiveDateRows FROM dbo.UtilityDeterminantDate dd;
SELECT rcd.RateName, COUNT(dd.DeterminantDateID) AS EffectiveDateRows
FROM dbo.UtilityRateClassDeterminants rcd
JOIN dbo.UtilityDeterminantDate dd ON dd.DeterminantID = rcd.DeterminantID
GROUP BY rcd.RateName ORDER BY rcd.RateName;
GO

PRINT '== user_defined_charges: 4 charges priced per meter: VED-AL-1 Fixture Charge, RCU-SW-ERU Stormwater ERU Charge, and Fixed O&M Share on NTP-ALLOC-CHW and on NTP-ALLOC-STEAM, or 0 if no screen could enter a per-meter price and they were entered flat (product finding) ==';
SELECT d.ChargeName, d.IsUserDefined FROM dbo.UtilityDeterminant d WHERE d.IsUserDefined = 1 ORDER BY d.ChargeName;
GO

PRINT '== determinant_blocks: one tiered charge, RCU-W-TIER Water Tiered Commodity, with 3 blocks on each of its 2 price dates ==';
SELECT d.ChargeName, dd.EffectiveDate, COUNT(db.DeterminantBlockID) AS Blocks
FROM dbo.UtilityDeterminantBlock db
JOIN dbo.UtilityDeterminantDate dd ON dd.DeterminantDateID = db.DeterminantDateID
JOIN dbo.UtilityDeterminant d ON d.DeterminantID = dd.DeterminantID
GROUP BY d.ChargeName, dd.EffectiveDate ORDER BY d.ChargeName;
GO

PRINT '== scripts_exist: 1 script, the pre-existing Round Bill Item Down 2 Decimals; no real tariff uses a script, so the second result set is empty until the Rate Lab is entered ==';
SELECT DeterminantScriptID, Description, ScriptType FROM dbo.UtilityDeterminantScript ORDER BY DeterminantScriptID;
SELECT d.ChargeName, ps.Description AS PreScript, po.Description AS PostScript
FROM dbo.UtilityDeterminant d
LEFT JOIN dbo.UtilityDeterminantScript ps ON ps.DeterminantScriptID = d.PreDeterminantScriptID
LEFT JOIN dbo.UtilityDeterminantScript po ON po.DeterminantScriptID = d.PostDeterminantScriptID
WHERE d.PreDeterminantScriptID IS NOT NULL OR d.PostDeterminantScriptID IS NOT NULL;
GO

PRINT '== meter_assignments: one row per rate assignment on a meter and bill scenario: 74 Rate Config rows on 56 meters in 06-rate-assignments.yaml, and each checked Bill box adds a Bill Reconciliation row ==';
SELECT mr.UtilityMeterRatesID, mw.Description AS Node, r.Name AS RateName, bs.ScenarioName, mr.StartDate
FROM dbo.UtilityMeterRates mr
JOIN dbo.UtilityRate r ON r.UtilityRateID = mr.UtilityRateID
LEFT JOIN dbo.MetaWorld_TBL mw ON mw.MetaWorldID = mr.MetaWorldID
LEFT JOIN dbo.BillScenario bs ON bs.BillScenarioId = mr.BillScenarioID
ORDER BY mw.Description, r.Name;
GO

-- Added 2026-10-01 (Ridgeline Wind): ridgeline_rates and ridgeline_assignments; rates_by_provider and meter_assignments above carry the new counts.
PRINT '== ridgeline_rates: VED-GEN-IC (4 determinants), VED-BCT (1) and RWL-XFER-2024 (2), plus the Public Purpose Program and Utility Users Tax lines added to VED-TOU-PRI; Generation Credit and Research Credit are negative, percentage values are decimal multipliers (0.05, 0.015) and no determinant is priced in a reactive unit (unit class 21 or 22); RWL-XFER-2024 has one class, the automatic All (ClassType 0), and no Rate Option, and both its determinants have a Commodity Mapping ==';
SELECT rcd.RateName, rcd.ChargeName, rcd.DeterminantTypeID, rcd.UN_Units, rcd.ScheduleName, dd.EffectiveDate, MIN(db.BlockValue) AS Value
FROM dbo.UtilityRateClassDeterminants rcd
LEFT JOIN dbo.UtilityDeterminantDate dd ON dd.DeterminantID = rcd.DeterminantID
LEFT JOIN dbo.UtilityDeterminantBlock db ON db.DeterminantDateID = dd.DeterminantDateID
WHERE rcd.RateName IN ('VED-GEN-IC', 'VED-BCT', 'RWL-XFER-2024')
   OR (rcd.RateName = 'VED-TOU-PRI' AND rcd.DeterminantTypeID IN (700, 800))
GROUP BY rcd.RateName, rcd.ChargeName, rcd.DeterminantTypeID, rcd.UN_Units, rcd.ScheduleName, dd.EffectiveDate
ORDER BY rcd.RateName, rcd.DeterminantTypeID, rcd.ChargeName;
SELECT COUNT(*) AS DeterminantsPricedInReactiveUnits
FROM dbo.UtilityDeterminant d JOIN dbo.Unit u ON u.UN_UnitID = d.UN_UnitID
WHERE u.UT_UnitClassID IN (21, 22);
SELECT r.Name AS RateName, rc.Description AS RateClass, rc.ClassType,
       (SELECT COUNT(*) FROM dbo.UtilityRateClassOption o WHERE o.UtilityRateID = r.UtilityRateID) AS RateOptions
FROM dbo.UtilityRate r
JOIN dbo.UtilityRateClass rc ON rc.UtilityRateID = r.UtilityRateID
WHERE r.Name = 'RWL-XFER-2024';
SELECT rcd.RateName, rcd.ChargeName, usageCommodity.CY_CommodityName AS UsageCommodity, chargeCommodity.CY_CommodityName AS ChargeCommodity, m.Exclude
FROM dbo.UtilityRateClassDeterminants rcd
LEFT JOIN dbo.UtilityCommodityMap m ON m.DeterminantID = rcd.DeterminantID
LEFT JOIN dbo.Commodity usageCommodity ON usageCommodity.CY_CommodityID = m.DeterminantsCommodityID
LEFT JOIN dbo.Commodity chargeCommodity ON chargeCommodity.CY_CommodityID = m.ChargesCommodityID
WHERE rcd.RateName = 'RWL-XFER-2024'
ORDER BY rcd.ChargeName;
GO

PRINT '== ridgeline_assignments: 4 Rate Config rows on 3 meters, all from 2024-07-01: SYN-VED-M-0040015 (VED-BCT and VED-GEN-IC), SYN-VED-M-0040014 (VED-BCT, added to its existing rate) and SYN-RWL-M-0110000, the Ridgeline Farm Transfer Meter (RWL-XFER-2024); the ten turbine pad meters SYN-RWL-M-0110001..0110010 have no row, because Bill Generation prices one meter at a time, and the Tenant Rebill grid keeps one rate at a time, so a meter with two rows on one date is a duplicate ==';
SELECT mt.SM_Code AS MeterNumber, r.Name AS RateName, bs.ScenarioName, mr.StartDate
FROM dbo.UtilityMeterRates mr
JOIN dbo.Meter mt ON mt.MetaWorldID = mr.MetaWorldID
JOIN dbo.UtilityRate r ON r.UtilityRateID = mr.UtilityRateID
LEFT JOIN dbo.BillScenario bs ON bs.BillScenarioId = mr.BillScenarioID
WHERE (mt.SM_Code LIKE 'SYN-RWL-M-%' OR mt.SM_Code IN ('SYN-VED-M-0040014', 'SYN-VED-M-0040015'))
  AND r.Name IN ('VED-GEN-IC', 'VED-BCT', 'RWL-XFER-2024')
ORDER BY mt.SM_Code, r.Name;
SELECT COUNT(*) AS TurbinePadMetersWithARateRow
FROM dbo.UtilityMeterRates mr
JOIN dbo.Meter mt ON mt.MetaWorldID = mr.MetaWorldID
WHERE mt.SM_Code LIKE 'SYN-RWL-M-%' AND mt.SM_Code <> 'SYN-RWL-M-0110000';
GO

PRINT '== rate_test_runs: NOT a database check. Test Rates scenarios save as JSON under %AppData%\EEMSuite\RateEngineTestingScenarios\ (RateTestScenarioFileStore, verified in source), one file per run. Verify by listing that folder and opening each run''s Results tab; there is no table to query. ==';
GO
