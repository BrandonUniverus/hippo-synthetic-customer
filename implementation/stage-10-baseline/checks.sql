-- Stage 10 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- Run it against the restored copy (EEMSuite_NorthlakeVerify) as well as the original: the values must be identical.
-- Every check returns Expected, Actual and a PASS/FAIL Result. Rewritten 2026-11-10: the earlier row counts named retired
-- tables (AuditLog, TaskLog, WorkflowRun) and asserted nothing; these assert the values 02-restore-verification.yaml and
-- Stages 1 to 9 already state. Written against the tables in Database\EEMSuite\Tables; not run.
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;

PRINT '== backup_history: the Stage 10 final backup is in msdb as a full backup (type D), not copy-only, in C:\Hippo\Backups\ and named EEMSuite_Northlake.stage10-final.<yyyyMMdd>.bak; run on the original instance only (the restored copy has the history of the instance it was restored on) ==';
SELECT 'stage10-final full backups of EEMSuite_Northlake' AS Item, '1 or more' AS Expected, CONVERT(varchar(30), COUNT(*)) AS Actual,
       CASE WHEN COUNT(*) >= 1 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM msdb.dbo.backupset bs JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id
WHERE bs.database_name = 'EEMSuite_Northlake' AND bs.type = 'D' AND bs.is_copy_only = 0
  AND bmf.physical_device_name LIKE 'C:\Hippo\Backups\EEMSuite_Northlake.stage10-final.%.bak';
GO

PRINT '== baseline_counts: the counts of what Stages 1 to 9 enter, from their YAML and checks: 3 named companies (6 Northlake University, 3 Cedar Row Apartments, 5 Northlake Thermal Plant; Stage 7 adds Northlake Town Center as a fourth), 6 utility providers, 13 ENERGY STAR properties, 4 weather regressions, 3 GHG company configurations (companies 6, 3, 5, base years 2024 to 2025), 5 projects, 15 alarm points, 23 saved-report rows, 3 dashboards, 5 deliveries, 20 delivery recipient rows, 0 EnergyAI loads ==';
SELECT x.Item, CONVERT(varchar(30), x.Expected) AS Expected, CONVERT(varchar(30), v.Actual) AS Actual, CASE WHEN v.Actual = x.Expected THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (VALUES ('Company_TBL: Northlake University 6, Cedar Row Apartments 3, Northlake Thermal Plant 5', 3),
             ('UtilityProvider', 6), ('ESFacility', 13), ('FF_wnRegressionBestResults', 4), ('EmissionCompanyConfig (6, 3, 5; 2024-2025)', 3),
             ('Project', 5), ('alarm points (a notify user or group on the point)', 15), ('GUIMFRSavedReports_TBL', 23), ('GUIMFRDashboards', 3),
             ('MFRDelivery_TBL', 5), ('MFRDeliveryRecipient_TBL', 20), ('EnergyAI_Loads', 0)) AS x(Item, Expected)
CROSS APPLY (SELECT CASE x.Item
    WHEN 'Company_TBL: Northlake University 6, Cedar Row Apartments 3, Northlake Thermal Plant 5'
         THEN (SELECT COUNT(*) FROM dbo.Company_TBL WHERE (CompanyID = 6 AND CompanyName = 'Northlake University') OR (CompanyID = 3 AND CompanyName = 'Cedar Row Apartments') OR (CompanyID = 5 AND CompanyName = 'Northlake Thermal Plant'))
    WHEN 'UtilityProvider' THEN (SELECT COUNT(*) FROM dbo.UtilityProvider)
    WHEN 'ESFacility' THEN (SELECT COUNT(*) FROM dbo.ESFacility)
    WHEN 'FF_wnRegressionBestResults' THEN (SELECT COUNT(*) FROM dbo.FF_wnRegressionBestResults)
    WHEN 'EmissionCompanyConfig (6, 3, 5; 2024-2025)' THEN (SELECT COUNT(*) FROM dbo.EmissionCompanyConfig WHERE CompanyID IN (6, 3, 5) AND BaseStartYear = 2024 AND BaseEndYear = 2025)
    WHEN 'Project' THEN (SELECT COUNT(*) FROM dbo.Project)
    WHEN 'alarm points (a notify user or group on the point)' THEN (SELECT COUNT(*) FROM dbo.PointDef_TBL p JOIN dbo.MetaWorld_TBL w ON w.MetaWorldID = p.MetaWorldID WHERE w.PrimaryUserID IS NOT NULL OR w.NotifyGroupID IS NOT NULL)
    WHEN 'GUIMFRSavedReports_TBL' THEN (SELECT COUNT(*) FROM dbo.GUIMFRSavedReports_TBL)
    WHEN 'GUIMFRDashboards' THEN (SELECT COUNT(*) FROM dbo.GUIMFRDashboards)
    WHEN 'MFRDelivery_TBL' THEN (SELECT COUNT(*) FROM dbo.MFRDelivery_TBL)
    WHEN 'MFRDeliveryRecipient_TBL' THEN (SELECT COUNT(*) FROM dbo.MFRDeliveryRecipient_TBL)
    WHEN 'EnergyAI_Loads' THEN (SELECT COUNT(*) FROM dbo.EnergyAI_Loads)
    END AS Actual) v;
GO

PRINT '== ridgeline_bill_values: the values the restore checklist names for Bill Tracking: the generated July 2024 Ridgeline transfer statement 129330.27; the generator account''s first bill (2024-07-01 to 2024-08-04) 1077.45; the -152792.65 credit on the Central Plant''s bill 2024-08-05 to 2024-09-04 (posted September 2024), on that one Central Plant bill and on no bill outside the two Valley Electric accounts ==';
SELECT 'Ridgeline July 2024 statement, SYN-RWL-G-0000001' AS Item, '129330.27' AS Expected,
       ISNULL(CONVERT(varchar(30), ROUND(b.BL_Amount, 2)), 'missing') AS Actual, CASE WHEN ROUND(b.BL_Amount, 2) = 129330.27 THEN 'PASS' ELSE 'FAIL' END AS Result
FROM (SELECT 1 AS One) o
LEFT JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001'
LEFT JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND b.BL_FiscalYear = 2024 AND b.BL_FiscalPeriodNo = 7 AND b.DeleteInd = 0
UNION ALL
SELECT 'generator account first bill, SYN-VED-A-0010014 from 2024-07-01', '1077.45',
       ISNULL(CONVERT(varchar(30), ROUND(b.BL_Amount, 2)), 'missing'), CASE WHEN ROUND(b.BL_Amount, 2) = 1077.45 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o
LEFT JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountNumber = 'SYN-VED-A-0010014'
LEFT JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND CONVERT(date, b.BL_PeriodStart) = '2024-07-01' AND b.DeleteInd = 0
UNION ALL
SELECT 'credit lines on the Central Plant bill from 2024-08-05, SYN-VED-A-0010013', '-152792.65',
       ISNULL(CONVERT(varchar(30), c.Credit), 'missing'), CASE WHEN c.Credit = -152792.65 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT 1 AS One) o
OUTER APPLY (SELECT SUM(bi.BI_Amount) AS Credit
               FROM dbo.BillingAccount_TBL ba
               JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND CONVERT(date, b.BL_PeriodStart) = '2024-08-05' AND b.DeleteInd = 0
               JOIN dbo.BillItem bi ON bi.BL_BillID = b.BL_BillID AND bi.DeleteInd = 0 AND bi.BI_Amount < 0
              WHERE ba.BA_BillingAccountNumber = 'SYN-VED-A-0010013') c
UNION ALL
SELECT 'Central Plant bills carrying a -152792.65 credit', '1', CONVERT(varchar(30), COUNT(*)), CASE WHEN COUNT(*) = 1 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT b.BL_BillID
        FROM dbo.BillingAccount_TBL ba JOIN dbo.Bill b ON b.BA_BillingAccountID = ba.BA_BillingAccountID AND b.DeleteInd = 0
        JOIN dbo.BillItem bi ON bi.BL_BillID = b.BL_BillID AND bi.DeleteInd = 0 AND bi.BI_Amount < 0
       WHERE ba.BA_BillingAccountNumber = 'SYN-VED-A-0010013'
       GROUP BY b.BL_BillID HAVING SUM(bi.BI_Amount) = -152792.65) one
UNION ALL
SELECT 'bills outside those two accounts carrying a -152792.65 credit', '0', CONVERT(varchar(30), COUNT(*)), CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
FROM (SELECT b.BL_BillID
        FROM dbo.Bill b JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = b.BA_BillingAccountID AND b.DeleteInd = 0
        JOIN dbo.BillItem bi ON bi.BL_BillID = b.BL_BillID AND bi.DeleteInd = 0 AND bi.BI_Amount < 0
       WHERE ba.BA_BillingAccountNumber NOT IN ('SYN-VED-A-0010013', 'SYN-VED-A-0010014')
       GROUP BY b.BL_BillID HAVING SUM(bi.BI_Amount) = -152792.65) other;
GO

PRINT '== activity_and_audit_survive_restore: what Stage 9 steps 2 and 3 expect from the report checklist: casey.holt 0 sign-ins, runs and page opens; elena.vasquez and kai.nakamura with report runs; 4 or more AuditEntry rows by jordan.hale (the bill, account and two meter edits); WTG-07''s Fault alarm row of 2025-02-11 with severity 3 ==';
SELECT 'casey.holt sign-ins + runs + opens' AS Item, '0' AS Expected,
       CONVERT(varchar(30), (SELECT COUNT(*) FROM dbo.UserLogin_Tbl l WHERE l.UserID = 'casey.holt') + (SELECT COUNT(*) FROM dbo.GuiReportActivityLog g WHERE g.UserID = 'casey.holt') + (SELECT COUNT(*) FROM dbo.GuiPageActivityLog g WHERE g.UserID = 'casey.holt')) AS Actual,
       CASE WHEN (SELECT COUNT(*) FROM dbo.UserLogin_Tbl l WHERE l.UserID = 'casey.holt') + (SELECT COUNT(*) FROM dbo.GuiReportActivityLog g WHERE g.UserID = 'casey.holt') + (SELECT COUNT(*) FROM dbo.GuiPageActivityLog g WHERE g.UserID = 'casey.holt') = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
UNION ALL
SELECT CONCAT('report runs by ', x.UserName), '1 or more', CONVERT(varchar(30), COUNT(g.GuiReportActivityLogID)), CASE WHEN COUNT(g.GuiReportActivityLogID) >= 1 THEN 'PASS' ELSE 'FAIL' END
FROM (VALUES ('elena.vasquez'), ('kai.nakamura')) AS x(UserName)
LEFT JOIN dbo.GuiReportActivityLog g ON g.UserID = x.UserName
GROUP BY x.UserName
UNION ALL
SELECT 'AuditEntry rows by jordan.hale (Action Update)', '4 or more', CONVERT(varchar(30), COUNT(*)), CASE WHEN COUNT(*) >= 4 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.AuditEntry WHERE ActorId = N'jordan.hale' AND Action = N'Update'
UNION ALL
SELECT 'WTG-07 Fault alarm row on 2025-02-11 (Value 2, Severity 3)', '1 or more', CONVERT(varchar(30), COUNT(*)), CASE WHEN COUNT(*) >= 1 THEN 'PASS' ELSE 'FAIL' END
FROM dbo.AlarmData_TBL a JOIN dbo.PointDef_TBL p ON p.PtID = a.PtID JOIN dbo.MetaWorld_TBL w ON w.MetaWorldID = p.MetaWorldID
JOIN dbo.Meter mt ON mt.MetaWorldID = w.ParentID AND mt.SM_Code = 'SYN-RWL-M-0110007'
WHERE a.Value = 2 AND a.SeverityNbr = 3 AND a.PtLocalTimeStamp >= '2025-02-11' AND a.PtLocalTimeStamp < '2025-02-12';
GO

PRINT '== checklist_not_scripted (nothing to run; read these in the restored copy, each must match 02-restore-verification.yaml): report-checklist lines that need an open report and a person, with no query that stands for them: rp_MonthlyEUI / BenchmarkRanking (the 12-building peer set ranked, Science Center highest), GHGHistory (computed emissions per company), GHGVariance (2024 against 2025 differs), WeatherRegression R-squared ranges (Stage 8 step 5), ESRatingHistory (13 properties, scores for Lakeview Hall and Cedar Row Apartments once Portfolio Manager is connected), the Facility Operations / Executive Overview / Ridgeline Operations tiles rendering, and the Task Log and Gateway Status run history ==';
