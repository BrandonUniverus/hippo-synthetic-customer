-- Stage 12 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- One asserting check per verify item of the four scenarios (plus the step expectations the scenario states), each with
-- Expected, Actual and a PASS/FAIL Result, using only values the scenario files state. Run it after the scenario it belongs
-- to has been entered; before that the rows read missing / FAIL, which is the expected state, not a defect. Written against the
-- tables in Database\EEMSuite\Tables (Meter, MetaWorld_TBL, PointDef_TBL, AnalogArchive_TBL, HMR_Meter, HMR_Reading,
-- HMR_ReadType, StatusHistory, Global_Status_Code, BillingAccount_TBL, Bill, BillItem); not run.
-- Scenario 1 changes the Cedar Row A water route and scenario 4 adds two registers, so no check here counts registers
-- database-wide; Stage 3's handheld checker is the place for the 204 (and its expectation changes with these scenarios).
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;

IF OBJECT_ID('tempdb..#pt') IS NOT NULL DROP TABLE #pt;
-- Every point under the scenario meters, by meter number (Meter.SM_Code) and the point's own name.
SELECT m.SM_Code AS SmCode, m.MetaWorldID AS MeterNode, w.Description AS PointDescription, p.PtID
INTO #pt
FROM dbo.Meter m
JOIN dbo.MetaWorld_TBL w ON w.ParentID = m.MetaWorldID AND ISNULL(w.DeleteInd, 0) = 0
JOIN dbo.PointDef_TBL p ON p.MetaWorldID = w.MetaWorldID
WHERE m.SM_Code IN ('SYN-SUB-W-A214', 'SYN-SUB-W-A214R', 'SYN-SUB-E-CPSWGR', 'SYN-SUB-E-TCK1');
GO

PRINT '== s1_final_read: the old meter SYN-SUB-W-A214 holds Register Reading 1388 at 2024-10-15 07:00 UTC (midnight Pacific daylight time) ==';
SELECT 'old register 1388 at 2024-10-15 07:00 UTC' AS Item, '1388' AS Expected,
       ISNULL(CONVERT(varchar(30), (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.UTCTimeStamp = '2024-10-15 07:00')), 'missing') AS Actual,
       CASE WHEN (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.UTCTimeStamp = '2024-10-15 07:00') = 1388 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-W-A214' AND p.PointDescription = 'Register Reading';
GO

PRINT '== s1_old_meter_status: the old meter is Closed - Ex from 2024-10-15 and the new one Open from the same day (StatusHistory, Table_Code SM) ==';
SELECT x.SmCode AS Item, CONCAT(x.Status, ' as of ', x.AsOf) AS Expected,
       ISNULL((SELECT TOP (1) CONCAT(s.Status_Code_Description, ' as of ', CONVERT(varchar(10), h.AsOfDate, 120))
                 FROM dbo.StatusHistory h JOIN dbo.Global_Status_Code s ON s.Table_Code = N'SM' AND s.Status_Code = h.Status_Code
                WHERE h.Table_Code = N'SM' AND h.SH_TableRowID = m.MetaWorldID ORDER BY h.AsOfDate DESC, h.SH_ActionID DESC), 'missing') AS Actual,
       CASE WHEN EXISTS (SELECT 1 FROM dbo.StatusHistory h JOIN dbo.Global_Status_Code s ON s.Table_Code = N'SM' AND s.Status_Code = h.Status_Code
                          WHERE h.Table_Code = N'SM' AND h.SH_TableRowID = m.MetaWorldID AND s.Status_Code_Description = x.Status
                            AND CONVERT(date, h.AsOfDate) = CONVERT(date, x.AsOf)) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (VALUES ('SYN-SUB-W-A214', 'Closed - Ex', '2024-10-15'), ('SYN-SUB-W-A214R', 'Open', '2024-10-15')) AS x(SmCode, Status, AsOf)
LEFT JOIN dbo.Meter m ON m.SM_Code = x.SmCode;
GO

PRINT '== s1_new_register_first_read: the new register SYN-SUB-W-A214R holds 3 at 2024-10-15 07:00 UTC, with no usage beside it, and its Register Reading Delta exists ==';
SELECT 'new register 3 at 2024-10-15 07:00 UTC' AS Item, '3' AS Expected,
       ISNULL(CONVERT(varchar(30), (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.UTCTimeStamp = '2024-10-15 07:00')), 'missing') AS Actual,
       CASE WHEN (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.UTCTimeStamp = '2024-10-15 07:00') = 3 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-W-A214R' AND p.PointDescription = 'Register Reading'
UNION ALL
SELECT 'delta rows on the new register at 2024-10-15 07:00 UTC', '0',
       CONVERT(varchar(30), COUNT(a.PtID)), CASE WHEN COUNT(a.PtID) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-W-A214R' AND p.PointDescription = 'Register Reading Delta'
LEFT JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.UTCTimeStamp = '2024-10-15 07:00';
GO

PRINT '== s1_next_round: the November 1, 2024 read of 9 kgal on the new meter books usage 6 (9 - 3) on its Register Reading Delta at 2024-11-01 07:00 UTC, no rollover and no held reading ==';
SELECT 'new Delta at 2024-11-01 07:00 UTC' AS Item, '6' AS Expected,
       ISNULL(CONVERT(varchar(30), (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.UTCTimeStamp = '2024-11-01 07:00')), 'missing') AS Actual,
       CASE WHEN (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.UTCTimeStamp = '2024-11-01 07:00') = 6 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-W-A214R' AND p.PointDescription = 'Register Reading Delta';
GO

PRINT '== s1_unit_214_october: unit 214 from 2024-10-01 to 2024-11-01 = (1388 - the old meter''s October 1 read) + (9 - 3): the two meters'' Delta rows stamped after 2024-10-01 07:00 UTC up to and including 2024-11-01 07:00 UTC add up to that figure ==';
SELECT 'unit 214 October usage, kgal' AS Item,
       CONVERT(varchar(30), 1388 - o.OldOct1 + (9 - 3)) AS Expected,
       ISNULL(CONVERT(varchar(30), d.Usage), 'missing') AS Actual,
       CASE WHEN o.OldOct1 IS NOT NULL AND d.Usage = 1388 - o.OldOct1 + (9 - 3) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a JOIN #pt p ON p.PtID = a.PtID AND p.SmCode = 'SYN-SUB-W-A214' AND p.PointDescription = 'Register Reading'
               WHERE a.UTCTimeStamp = '2024-10-01 07:00') AS OldOct1) o
CROSS JOIN (SELECT SUM(a.Value) AS Usage FROM dbo.AnalogArchive_TBL a JOIN #pt p ON p.PtID = a.PtID AND p.SmCode IN ('SYN-SUB-W-A214', 'SYN-SUB-W-A214R') AND p.PointDescription = 'Register Reading Delta'
             WHERE a.UTCTimeStamp > '2024-10-01 07:00' AND a.UTCTimeStamp <= '2024-11-01 07:00') d;
GO

PRINT '== s1_route: CRAWTR still has 61 meters; the replacement SYN-SUB-W-A214R is on cycle 02, route CRAWTR at sequence 350 (the route file lists it) and the old meter SYN-SUB-W-A214 is not on the route ==';
SELECT 'meters on route CRAWTR' AS Item, '61' AS Expected, CONVERT(varchar(30), COUNT(*)) AS Actual, CASE WHEN COUNT(*) = 61 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.HMR_Meter WHERE RouteNumber = 'CRAWTR'
UNION ALL
SELECT 'SYN-SUB-W-A214R cycle / route / sequence', '02 / CRAWTR / 350',
       ISNULL(CONCAT(h.CycleID, ' / ', h.RouteNumber, ' / ', h.ReadSequence), 'missing'),
       CASE WHEN h.CycleID = '02' AND h.RouteNumber = 'CRAWTR' AND h.ReadSequence = 350 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN dbo.Meter m ON m.SM_Code = 'SYN-SUB-W-A214R' LEFT JOIN dbo.HMR_Meter h ON h.MetaWorldID = m.MetaWorldID
UNION ALL
SELECT 'old meter SYN-SUB-W-A214 on route CRAWTR', 'not on the route',
       CASE WHEN COUNT(h.HMR_MeterID) = 0 THEN 'not on the route' ELSE 'still on the route' END,
       CASE WHEN COUNT(h.HMR_MeterID) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.Meter m LEFT JOIN dbo.HMR_Meter h ON h.MetaWorldID = m.MetaWorldID AND h.RouteNumber = 'CRAWTR'
WHERE m.SM_Code = 'SYN-SUB-W-A214';
GO

PRINT '== s2_read_type: the read type Northlake Keyed Demand MW 10D3DC (10 dials, 3 decimals, code 14, direction L, demand read Y, truncation 0) ==';
SELECT 'Northlake Keyed Demand MW 10D3DC' AS Item, '10 / 3 / 14 / L / Y / 0' AS Expected,
       ISNULL(CONCAT(r.NumDials, ' / ', r.NumDecimals, ' / ', r.ReadTypeCode, ' / ', r.ReadDirection, ' / ', r.DemandRead, ' / ', r.TruncationFactor), 'missing') AS Actual,
       CASE WHEN r.NumDials = 10 AND r.NumDecimals = 3 AND r.ReadTypeCode = '14' AND r.ReadDirection = 'L' AND r.DemandRead = 'Y' AND r.TruncationFactor = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT 1 AS One) o LEFT JOIN dbo.HMR_ReadType r ON r.Description = 'Northlake Keyed Demand MW 10D3DC';
GO

PRINT '== s2_registers: on SYN-SUB-E-CPSWGR the KW register reads prompt MW (previous KW) and the KWP register MWP (previous KWP), both on the MW read type with constant 1000; the KVA register is unchanged (prompt KVA, constant 1); no KW or KWP prompt remains on the route file ==';
SELECT x.Prompt AS Item, CONCAT('previous ', ISNULL(x.PreviousPrompt, 'none'), ' | ', x.ReadType, ' | constant ', x.Constant) AS Expected,
       ISNULL(CONCAT('previous ', ISNULL(r.PreviousTextPrompt, 'none'), ' | ', rt.Description, ' | constant ', r.MeterConstant), 'missing') AS Actual,
       CASE WHEN r.HMR_ReadingID IS NOT NULL AND ISNULL(r.PreviousTextPrompt, '') = ISNULL(x.PreviousPrompt, '') AND rt.Description = x.ReadType AND r.MeterConstant = x.Constant THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (VALUES ('MW', 'KW', 'Northlake Keyed Demand MW 10D3DC', 1000.0),
             ('MWP', 'KWP', 'Northlake Keyed Demand MW 10D3DC', 1000.0),
             ('KVA', CONVERT(varchar(4), NULL), 'Northlake Keyed Demand 10D2DC', 1.0)) AS x(Prompt, PreviousPrompt, ReadType, Constant)
LEFT JOIN dbo.Meter m ON m.SM_Code = 'SYN-SUB-E-CPSWGR'
LEFT JOIN dbo.HMR_Meter h ON h.MetaWorldID = m.MetaWorldID
LEFT JOIN dbo.HMR_Reading r ON r.HMR_MeterID = h.HMR_MeterID AND r.TextPrompt = x.Prompt
LEFT JOIN dbo.HMR_ReadType rt ON rt.HMR_ReadTypeID = r.HMR_ReadTypeID
UNION ALL
SELECT 'registers still prompting KW or KWP', '0', CONVERT(varchar(30), COUNT(r.HMR_ReadingID)), CASE WHEN COUNT(r.HMR_ReadingID) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.Meter m JOIN dbo.HMR_Meter h ON h.MetaWorldID = m.MetaWorldID
JOIN dbo.HMR_Reading r ON r.HMR_MeterID = h.HMR_MeterID AND r.TextPrompt IN ('KW', 'KWP')
WHERE m.SM_Code = 'SYN-SUB-E-CPSWGR';
GO

PRINT '== s2_history: Max Demand kW reads 1294.6 (2025-02-28) then 1312 (2025-03-31 07:00 UTC) and On-Peak Max Demand kW 1281.15 then 1298 in one kW history, with no factor-of-1000 step between them; the report converts to MW by the unit system (1294.6 -> 1.2946, 1312 -> 1.312), nothing is stored in MW ==';
SELECT x.Item, CONVERT(varchar(30), x.Expected) AS Expected,
       ISNULL(CONVERT(varchar(30), v.Value), 'missing') AS Actual,
       CASE WHEN v.Value = x.Expected THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (VALUES ('Max Demand kW, 2025-02-28', 'Max Demand kW', CONVERT(datetime, '2025-02-28'), CONVERT(float, 1294.6)),
             ('Max Demand kW, 2025-03-31', 'Max Demand kW', CONVERT(datetime, '2025-03-31'), 1312.0),
             ('On-Peak Max Demand kW, 2025-02-28', 'On-Peak Max Demand kW', CONVERT(datetime, '2025-02-28'), 1281.15),
             ('On-Peak Max Demand kW, 2025-03-31', 'On-Peak Max Demand kW', CONVERT(datetime, '2025-03-31'), 1298.0)) AS x(Item, PointDescription, LocalDay, Expected)
OUTER APPLY (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a JOIN #pt p ON p.PtID = a.PtID AND p.SmCode = 'SYN-SUB-E-CPSWGR' AND p.PointDescription = x.PointDescription
              WHERE CONVERT(date, a.LocalTimeStamp) = CONVERT(date, x.LocalDay) ORDER BY a.UTCTimeStamp) v
UNION ALL
SELECT 'Max Demand kW at 2025-03-31 07:00 UTC', '1312', ISNULL(CONVERT(varchar(30), a.Value), 'missing'), CASE WHEN a.Value = 1312 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-E-CPSWGR' AND p.PointDescription = 'Max Demand kW'
LEFT JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.UTCTimeStamp = '2025-03-31 07:00'
UNION ALL
SELECT 'Max Demand kW 2025-03-31 read as MW (1312 / 1000)', '1.312', ISNULL(CONVERT(varchar(30), a.Value / 1000.0), 'missing'), CASE WHEN a.Value / 1000.0 = 1.312 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-E-CPSWGR' AND p.PointDescription = 'Max Demand kW'
LEFT JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID AND a.UTCTimeStamp = '2025-03-31 07:00'
UNION ALL
SELECT 'Max Demand kW 2025-02-28 read as MW (1294.6 / 1000)', '1.2946', ISNULL(CONVERT(varchar(30), a.Value / 1000.0), 'missing'), CASE WHEN ABS(a.Value / 1000.0 - 1.2946) < 0.0000001 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-E-CPSWGR' AND p.PointDescription = 'Max Demand kW'
OUTER APPLY (SELECT TOP (1) a2.Value FROM dbo.AnalogArchive_TBL a2 WHERE a2.PtID = p.PtID AND CONVERT(date, a2.LocalTimeStamp) = '2025-02-28' ORDER BY a2.UTCTimeStamp) a;
GO

PRINT '== s3_route_in_walking_order: every one of the 50 Cedar Row C meters in 03-cedar-row-c-walking-order.csv is on cycle 02, route CRCWTR, enabled, at the CSV sequence (house 10, laundry 20, unit 401 30, ..., unit 112 500) ==';
WITH Walk(SmCode, Seq) AS
(
    SELECT * FROM (VALUES
        ('SYN-SUB-W-CH', 10),
        ('SYN-SUB-W-CL', 20),
        ('SYN-SUB-W-C401', 30),
        ('SYN-SUB-W-C301', 40),
        ('SYN-SUB-W-C201', 50),
        ('SYN-SUB-W-C101', 60),
        ('SYN-SUB-W-C402', 70),
        ('SYN-SUB-W-C302', 80),
        ('SYN-SUB-W-C202', 90),
        ('SYN-SUB-W-C102', 100),
        ('SYN-SUB-W-C403', 110),
        ('SYN-SUB-W-C303', 120),
        ('SYN-SUB-W-C203', 130),
        ('SYN-SUB-W-C103', 140),
        ('SYN-SUB-W-C404', 150),
        ('SYN-SUB-W-C304', 160),
        ('SYN-SUB-W-C204', 170),
        ('SYN-SUB-W-C104', 180),
        ('SYN-SUB-W-C405', 190),
        ('SYN-SUB-W-C305', 200),
        ('SYN-SUB-W-C205', 210),
        ('SYN-SUB-W-C105', 220),
        ('SYN-SUB-W-C406', 230),
        ('SYN-SUB-W-C306', 240),
        ('SYN-SUB-W-C206', 250),
        ('SYN-SUB-W-C106', 260),
        ('SYN-SUB-W-C407', 270),
        ('SYN-SUB-W-C307', 280),
        ('SYN-SUB-W-C207', 290),
        ('SYN-SUB-W-C107', 300),
        ('SYN-SUB-W-C408', 310),
        ('SYN-SUB-W-C308', 320),
        ('SYN-SUB-W-C208', 330),
        ('SYN-SUB-W-C108', 340),
        ('SYN-SUB-W-C409', 350),
        ('SYN-SUB-W-C309', 360),
        ('SYN-SUB-W-C209', 370),
        ('SYN-SUB-W-C109', 380),
        ('SYN-SUB-W-C410', 390),
        ('SYN-SUB-W-C310', 400),
        ('SYN-SUB-W-C210', 410),
        ('SYN-SUB-W-C110', 420),
        ('SYN-SUB-W-C411', 430),
        ('SYN-SUB-W-C311', 440),
        ('SYN-SUB-W-C211', 450),
        ('SYN-SUB-W-C111', 460),
        ('SYN-SUB-W-C412', 470),
        ('SYN-SUB-W-C312', 480),
        ('SYN-SUB-W-C212', 490),
        ('SYN-SUB-W-C112', 500)
    ) AS v(SmCode, Seq)
)
SELECT w.SmCode AS Item, CONCAT('02 / CRCWTR / enabled / ', w.Seq) AS Expected,
       ISNULL(CONCAT(h.CycleID, ' / ', h.RouteNumber, ' / ', CASE WHEN h.active = 1 THEN 'enabled' ELSE 'disabled' END, ' / ', h.ReadSequence), 'missing') AS Actual,
       CASE WHEN h.CycleID = '02' AND h.RouteNumber = 'CRCWTR' AND h.active = 1 AND h.ReadSequence = w.Seq THEN 'PASS' ELSE 'FAIL' END AS Result
FROM Walk w
LEFT JOIN dbo.Meter m ON m.SM_Code = w.SmCode
LEFT JOIN dbo.HMR_Meter h ON h.MetaWorldID = m.MetaWorldID
UNION ALL
SELECT 'meters in the CSV on route CRCWTR cycle 02, enabled', '50', CONVERT(varchar(30), COUNT(*)), CASE WHEN COUNT(*) = 50 THEN 'PASS' ELSE 'FAIL' END
FROM Walk w JOIN dbo.Meter m ON m.SM_Code = w.SmCode JOIN dbo.HMR_Meter h ON h.MetaWorldID = m.MetaWorldID
WHERE h.CycleID = '02' AND h.RouteNumber = 'CRCWTR' AND h.active = 1;
GO

PRINT '== s3_no_cycle_20: there is no cycle 20 in the route file (unit 412 moved to cycle 02) ==';
SELECT 'meters on cycle 20' AS Item, '0' AS Expected, CONVERT(varchar(30), COUNT(*)) AS Actual, CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.HMR_Meter WHERE CycleID = '20';
GO

PRINT '== s3_meter_text: every Cedar Row C meter text reads the text 03-fix-cedar-row-c-route.yaml gives it ==';
SELECT 'Cedar Row C meters with the new meter text' AS Item, '50 of 50' AS Expected,
       CONCAT(SUM(CASE WHEN h.ReadingText = 'Cedar Row C water submeter. Confirm the unit on the meter before reading.' THEN 1 ELSE 0 END), ' of ', COUNT(*)) AS Actual,
       CASE WHEN COUNT(*) = 50 AND SUM(CASE WHEN h.ReadingText = 'Cedar Row C water submeter. Confirm the unit on the meter before reading.' THEN 1 ELSE 0 END) = 50 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.HMR_Meter h JOIN dbo.Meter m ON m.MetaWorldID = h.MetaWorldID
WHERE h.RouteNumber = 'CRCWTR';
GO

PRINT '== s3_nothing_else_changed: the 50 Cedar Row C meters on CRCWTR carry 50 registers (one each: the Stage 3 count of 204 less the other 154), each with a read type, a prompt and a usage point still set ==';
SELECT 'registers on route CRCWTR' AS Item, '50' AS Expected, CONVERT(varchar(30), COUNT(r.HMR_ReadingID)) AS Actual, CASE WHEN COUNT(r.HMR_ReadingID) = 50 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM dbo.HMR_Meter h JOIN dbo.HMR_Reading r ON r.HMR_MeterID = h.HMR_MeterID
WHERE h.RouteNumber = 'CRCWTR'
UNION ALL
SELECT 'registers on CRCWTR with no read type, prompt or usage point', '0', CONVERT(varchar(30), COUNT(r.HMR_ReadingID)), CASE WHEN COUNT(r.HMR_ReadingID) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.HMR_Meter h JOIN dbo.HMR_Reading r ON r.HMR_MeterID = h.HMR_MeterID
WHERE h.RouteNumber = 'CRCWTR' AND (r.HMR_ReadTypeID IS NULL OR r.TextPrompt IS NULL OR r.Ptid_Usage IS NULL);
GO

PRINT '== s4_bills: seven Meter Reads bills on account TC-MKT-KIOSK1 with the dates, kWh and totals 04-demand-read-after-energy.yaml states (May 05-01 to 05-30 628.72; June 05-31 to 06-30 464.28; July 07-01 to 07-31 793.08; August 08-01 to 08-29 764.56; September 08-30 to 09-30 684.72; October 10-01 to 10-31 417.16; November 11-01 to 11-28 576.04); each bill carries a line whose quantity is its kWh ==';
SELECT x.Period AS Item, CONCAT(x.PeriodStart, ' to ', x.PeriodEnd, ' | ', FORMAT(x.Total, 'N2'), ' | ', x.Kwh, ' kWh') AS Expected,
       CASE WHEN b.BL_BillID IS NULL THEN 'missing' ELSE CONCAT(CONVERT(varchar(10), b.BL_PeriodStart, 120), ' to ', CONVERT(varchar(10), b.BL_PeriodEnd, 120), ' | ', FORMAT(ROUND(b.BL_Amount, 2), 'N2'), ' | ',
            ISNULL((SELECT TOP (1) CONVERT(varchar(20), CONVERT(decimal(12, 0), bi.BI_Quantity)) FROM dbo.BillItem bi WHERE bi.BL_BillID = b.BL_BillID AND bi.DeleteInd = 0 AND bi.BI_Quantity = x.Kwh), 'no kWh line'), ' kWh') END AS Actual,
       CASE WHEN b.BL_BillID IS NOT NULL AND ROUND(b.BL_Amount, 2) = x.Total
             AND EXISTS (SELECT 1 FROM dbo.BillItem bi WHERE bi.BL_BillID = b.BL_BillID AND bi.DeleteInd = 0 AND bi.BI_Quantity = x.Kwh) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (VALUES ('2025-05', '2025-05-01', '2025-05-30', CONVERT(money, 628.72), 2560),
             ('2025-06', '2025-05-31', '2025-06-30', CONVERT(money, 464.28), 2890),
             ('2025-07', '2025-07-01', '2025-07-31', CONVERT(money, 793.08), 3320),
             ('2025-08', '2025-08-01', '2025-08-29', CONVERT(money, 764.56), 3220),
             ('2025-09', '2025-08-30', '2025-09-30', CONVERT(money, 684.72), 2870),
             ('2025-10', '2025-10-01', '2025-10-31', CONVERT(money, 417.16), 2580),
             ('2025-11', '2025-11-01', '2025-11-28', CONVERT(money, 576.04), 2340)) AS x(Period, PeriodStart, PeriodEnd, Total, Kwh)
LEFT JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountNumber = 'TC-MKT-KIOSK1'
LEFT JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND b.DeleteInd = 0 AND CONVERT(date, b.BL_PeriodStart) = CONVERT(date, x.PeriodStart) AND CONVERT(date, b.BL_PeriodEnd) = CONVERT(date, x.PeriodEnd)
UNION ALL
SELECT 'bills on TC-MKT-KIOSK1', '7', CONVERT(varchar(30), COUNT(b.BL_BillID)), CASE WHEN COUNT(b.BL_BillID) = 7 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.BillingAccount_TBL ba LEFT JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND b.DeleteInd = 0
WHERE ba.BA_BillingAccountNumber = 'TC-MKT-KIOSK1';
GO

PRINT '== s4_kwh_add_up: the seven bills'' kWh (2560 + 2890 + 3320 + 3220 + 2870 + 2580 + 2340) add up to the register''s movement 38200 - 18420 = 19780, and the Register Reading Delta rows add up to the same, so every kWh is billed once ==';
SELECT 'sum of the seven stated kWh' AS Item, '19780' AS Expected, CONVERT(varchar(30), 2560 + 2890 + 3320 + 3220 + 2870 + 2580 + 2340) AS Actual,
       CASE WHEN 2560 + 2890 + 3320 + 3220 + 2870 + 2580 + 2340 = 38200 - 18420 THEN 'PASS' ELSE 'FAIL' END AS Result
UNION ALL
SELECT 'sum of Register Reading Delta on SYN-SUB-E-TCK1', '19780', ISNULL(CONVERT(varchar(30), SUM(a.Value)), 'missing'), CASE WHEN SUM(a.Value) = 19780 THEN 'PASS' ELSE 'FAIL' END
FROM #pt p JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID
WHERE p.SmCode = 'SYN-SUB-E-TCK1' AND p.PointDescription = 'Register Reading Delta'
UNION ALL
SELECT 'last Register Reading value on SYN-SUB-E-TCK1', '38200',
       ISNULL(CONVERT(varchar(30), (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID ORDER BY a.UTCTimeStamp DESC)), 'missing'),
       CASE WHEN (SELECT TOP (1) a.Value FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID ORDER BY a.UTCTimeStamp DESC) = 38200 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-E-TCK1' AND p.PointDescription = 'Register Reading';
GO

PRINT '== s4_demand_values: Max Demand kW holds seven values: 14.50 May 30 10:04, 17.80 July 1 08:30, 16.40 July 31 10:04 (the setting off), then 16.90 August 29 10:00 and 15.10 September 30 10:00 (moved onto the energy read), 13.20 November 1 08:30 (kept) and 12.60 November 28 10:00 (same visit); local time stamps ==';
SELECT x.Item, CONCAT(FORMAT(x.Value, 'N2'), ' at ', x.At) AS Expected,
       ISNULL((SELECT TOP (1) CONCAT(FORMAT(a.Value, 'N2'), ' at ', CONVERT(varchar(16), a.LocalTimeStamp, 120)) FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.LocalTimeStamp = CONVERT(datetime, x.At)), 'missing') AS Actual,
       CASE WHEN EXISTS (SELECT 1 FROM dbo.AnalogArchive_TBL a WHERE a.PtID = p.PtID AND a.LocalTimeStamp = CONVERT(datetime, x.At) AND ROUND(a.Value, 2) = x.Value) THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (VALUES ('May', '2025-05-30 10:04', CONVERT(float, 14.50)), ('June read, keyed July 1', '2025-07-01 08:30', 17.80), ('July', '2025-07-31 10:04', 16.40),
             ('August, moved', '2025-08-29 10:00', 16.90), ('September, moved', '2025-09-30 10:00', 15.10),
             ('October read, keyed November 1', '2025-11-01 08:30', 13.20), ('November', '2025-11-28 10:00', 12.60)) AS x(Item, At, Value)
LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-E-TCK1' AND p.PointDescription = 'Max Demand kW'
UNION ALL
SELECT 'Max Demand kW values', '7', CONVERT(varchar(30), COUNT(a.PtID)), CASE WHEN COUNT(a.PtID) = 7 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o LEFT JOIN #pt p ON p.SmCode = 'SYN-SUB-E-TCK1' AND p.PointDescription = 'Max Demand kW'
LEFT JOIN dbo.AnalogArchive_TBL a ON a.PtID = p.PtID;
GO

IF OBJECT_ID('tempdb..#pt') IS NOT NULL DROP TABLE #pt;
GO
