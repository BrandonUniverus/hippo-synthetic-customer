-- Stage 6 checks. Read-only. Every check ends in a Result column (PASS, FAIL, or PENDING/BLOCKED where something outside this
-- recipe has to exist first). Run, in one session so the bill totals feed is available to the export checks:
--   sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i ../stage-5-bills/expected-bill-totals.sql -i checks.sql
-- (expected-bill-totals.sql is optional; it is written by the command in stage-5-bills/03-bills.yaml expected_totals_feed.)
-- 2026-11-10: rewritten. The account list reads dbo.BillingAccount_TBL (the BillingAccount view is scoped to the signed-in user).
SET NOCOUNT ON;
SELECT ba.BA_BillingAccountID AS AccountID, ba.BA_BillingAccountNumber AS AccountNumber, ba.CompanyID, ba.BillType_Code AS EntryType,
       ba.Type_Code AS ServiceType, ba.Status_Code AS AccountStatus, ba.BA_DefApAcctID AS LiabilityId, ba.BA_DefExpAcctID AS ExpenseId
  INTO #Acct FROM dbo.BillingAccount_TBL ba;
GO

PRINT '== gl_chart: 16 accounts, Northlake University 6, Cedar Row Apartments 5, Northlake Thermal Plant 5; Type_Code 1 Expenses and 2 Liabilities only ==';
SELECT c.CompanyName, COUNT(*) AS Accounts,
       CASE c.CompanyName WHEN 'Northlake University' THEN 6 WHEN 'Cedar Row Apartments' THEN 5 WHEN 'Northlake Thermal Plant' THEN 5 END AS Expected,
       CASE WHEN COUNT(*) = CASE c.CompanyName WHEN 'Northlake University' THEN 6 WHEN 'Cedar Row Apartments' THEN 5 WHEN 'Northlake Thermal Plant' THEN 5 END
             AND SUM(CASE WHEN g.Type_Code IN (1, 2) THEN 0 ELSE 1 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.GLAccount g JOIN dbo.Company_TBL c ON c.CompanyID = g.CompanyID
 WHERE c.CompanyName IN ('Northlake University', 'Cedar Row Apartments', 'Northlake Thermal Plant')
 GROUP BY c.CompanyName;
SELECT COUNT(*) AS Accounts, 16 AS Expected, CASE WHEN COUNT(*) = 16 THEN 'PASS' ELSE 'FAIL' END AS Result FROM dbo.GLAccount;
GO
PRINT '== account_defaults: all 51 billing accounts carry the expected Bill Service Type, Bill Entry Type, Liability Account (2000-AP) and Default Expense Account (by provider), and both GL accounts belong to the account''s own company. Failing accounts are listed ==';
WITH expected AS (
    SELECT a.AccountNumber, a.EntryType, a.ServiceType, a.CompanyID, lia.GL_AccountCode AS Liability, lia.CompanyID AS LiabilityCompany, ex.GL_AccountCode AS Expense, ex.CompanyID AS ExpenseCompany,
           CASE WHEN a.AccountNumber = 'SYN-RCU-A-0030004' THEN 0
                WHEN a.AccountNumber LIKE 'SYN-HOS-P-%' OR a.AccountNumber LIKE 'SYN-RWL-G-%' THEN 2 ELSE 1 END AS WantService,
           CASE WHEN a.AccountNumber LIKE 'SYN-VED-A-%' OR a.AccountNumber LIKE 'SYN-RCU-A-%' THEN 1
                WHEN a.AccountNumber LIKE 'SYN-SGU-A-%' OR a.AccountNumber LIKE 'SYN-HOS-P-%' THEN 0
                WHEN a.AccountNumber LIKE 'SYN-NTP-C-%' THEN 3 WHEN a.AccountNumber LIKE 'SYN-RWL-G-%' THEN 2 END AS WantEntry,
           CASE WHEN a.AccountNumber LIKE 'SYN-VED-A-%' THEN '5100-ELEC' WHEN a.AccountNumber LIKE 'SYN-SGU-A-%' THEN '5110-GAS'
                WHEN a.AccountNumber LIKE 'SYN-RCU-A-%' THEN '5120-WATER' WHEN a.AccountNumber LIKE 'SYN-NTP-C-%' THEN '5130-THERMAL'
                WHEN a.AccountNumber LIKE 'SYN-HOS-P-%' THEN '5140-SOLAR' WHEN a.AccountNumber LIKE 'SYN-RWL-G-%' THEN '5150-WIND' END AS WantExpense
      FROM #Acct a LEFT JOIN dbo.GLAccount lia ON lia.GL_AccountID = a.LiabilityId LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = a.ExpenseId),
judged AS (
    SELECT e.*, CASE WHEN e.ServiceType = e.WantService AND e.EntryType = e.WantEntry AND e.Liability = '2000-AP' AND e.Expense = e.WantExpense
                      AND e.LiabilityCompany = e.CompanyID AND e.ExpenseCompany = e.CompanyID THEN 'PASS' ELSE 'FAIL' END AS Result FROM expected e)
SELECT COUNT(*) AS Accounts, 51 AS Expected, SUM(CASE WHEN Result = 'PASS' THEN 1 ELSE 0 END) AS Pass, SUM(CASE WHEN Result = 'FAIL' THEN 1 ELSE 0 END) AS Fail,
       CASE WHEN COUNT(*) = 51 AND SUM(CASE WHEN Result = 'FAIL' THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result FROM judged;
-- (the failing rows themselves)
WITH expected AS (
    SELECT a.AccountNumber, a.EntryType, a.ServiceType, a.CompanyID, lia.GL_AccountCode AS Liability, lia.CompanyID AS LiabilityCompany, ex.GL_AccountCode AS Expense, ex.CompanyID AS ExpenseCompany,
           CASE WHEN a.AccountNumber = 'SYN-RCU-A-0030004' THEN 0 WHEN a.AccountNumber LIKE 'SYN-HOS-P-%' OR a.AccountNumber LIKE 'SYN-RWL-G-%' THEN 2 ELSE 1 END AS WantService,
           CASE WHEN a.AccountNumber LIKE 'SYN-VED-A-%' OR a.AccountNumber LIKE 'SYN-RCU-A-%' THEN 1 WHEN a.AccountNumber LIKE 'SYN-SGU-A-%' OR a.AccountNumber LIKE 'SYN-HOS-P-%' THEN 0
                WHEN a.AccountNumber LIKE 'SYN-NTP-C-%' THEN 3 WHEN a.AccountNumber LIKE 'SYN-RWL-G-%' THEN 2 END AS WantEntry,
           CASE WHEN a.AccountNumber LIKE 'SYN-VED-A-%' THEN '5100-ELEC' WHEN a.AccountNumber LIKE 'SYN-SGU-A-%' THEN '5110-GAS' WHEN a.AccountNumber LIKE 'SYN-RCU-A-%' THEN '5120-WATER'
                WHEN a.AccountNumber LIKE 'SYN-NTP-C-%' THEN '5130-THERMAL' WHEN a.AccountNumber LIKE 'SYN-HOS-P-%' THEN '5140-SOLAR' WHEN a.AccountNumber LIKE 'SYN-RWL-G-%' THEN '5150-WIND' END AS WantExpense
      FROM #Acct a LEFT JOIN dbo.GLAccount lia ON lia.GL_AccountID = a.LiabilityId LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = a.ExpenseId)
SELECT AccountNumber, ServiceType, WantService, EntryType, WantEntry, Liability, Expense, WantExpense, 'FAIL' AS Result
  FROM expected
 WHERE NOT (ServiceType = WantService AND EntryType = WantEntry AND Liability = '2000-AP' AND Expense = WantExpense AND LiabilityCompany = CompanyID AND ExpenseCompany = CompanyID)
    OR ServiceType IS NULL OR Liability IS NULL OR Expense IS NULL
 ORDER BY AccountNumber;
GO
PRINT '== account_type_counts: Bill Service Type 0 No AP Upload 1 / 1 AP Upload Only 46 / 2 Bill Payment 4 (3 Helios + Ridgeline); Bill Entry Type 0 Bill Entry 13 / 1 Bill Importer 31 / 2 Bill Generation 1 / 3 Bill Allocation 6 ==';
SELECT x.Dimension, x.Code, x.Expected, ISNULL(c.Actual, 0) AS Actual, CASE WHEN ISNULL(c.Actual, 0) = x.Expected THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM (VALUES ('Bill Service Type', 0, 1), ('Bill Service Type', 1, 46), ('Bill Service Type', 2, 4),
               ('Bill Entry Type', 0, 13), ('Bill Entry Type', 1, 31), ('Bill Entry Type', 2, 1), ('Bill Entry Type', 3, 6)) x(Dimension, Code, Expected)
  LEFT JOIN (SELECT 'Bill Service Type' AS Dimension, ServiceType AS Code, COUNT(*) AS Actual FROM #Acct GROUP BY ServiceType
             UNION ALL SELECT 'Bill Entry Type', EntryType, COUNT(*) FROM #Acct GROUP BY EntryType) c ON c.Dimension = x.Dimension AND c.Code = x.Code
 ORDER BY x.Dimension, x.Code;
GO
PRINT '== per_line_coding: every line of the SGU Student Center estimate and correction is coded 5110-GAS, every line of the Helios Science Center Feb-25 bill 5140-SOLAR (BillItem.BI_EXpAcctID itself, not the account default); the three Ridgeline bills'' lines are coded 5100-ELEC once re-imported ==';
SELECT a.AccountNumber, CONVERT(date, bl.BL_PeriodStart) AS PeriodStart, bl.BL_Amount, COUNT(*) AS Lines, SUM(CASE WHEN ex.GL_AccountCode IS NULL THEN 1 ELSE 0 END) AS LinesWithoutOwnCode,
       SUM(CASE WHEN ex.GL_AccountCode IS NOT NULL AND ex.GL_AccountCode <> w.WantCode THEN 1 ELSE 0 END) AS LinesWithAnotherCode,
       CASE WHEN SUM(CASE WHEN ex.GL_AccountCode = w.WantCode THEN 1 ELSE 0 END) = COUNT(*) THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
  JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
  LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = bi.BI_EXpAcctID
  JOIN (VALUES ('SYN-SGU-A-0020004', CONVERT(date, '2024-10-15'), '5110-GAS'), ('SYN-HOS-P-0000001', CONVERT(date, '2025-02-01'), '5140-SOLAR'),
               ('SYN-VED-A-0010014', CONVERT(date, '2024-07-01'), '5100-ELEC'), ('SYN-VED-A-0010014', CONVERT(date, '2025-01-05'), '5100-ELEC'),
               ('SYN-VED-A-0010013', CONVERT(date, '2024-08-05'), '5100-ELEC')) w(AccountNumber, PeriodStart, WantCode)
    ON w.AccountNumber = a.AccountNumber AND w.PeriodStart = CONVERT(date, bl.BL_PeriodStart)
 WHERE bl.DeleteInd = 0
 GROUP BY a.AccountNumber, bl.BL_BillID, bl.BL_PeriodStart, bl.BL_Amount, w.WantCode
 ORDER BY a.AccountNumber, bl.BL_PeriodStart;
GO
PRINT '== export_formats_registered: BLOCKED while ExportSetup is empty (the format rows and builders cannot be created on any screen, 04-ap-export-formats.yaml); PASS when nl_ap_invoice (APINV, csv, NLAP_, status 3) and nl_gl_journal (GLJNL, csv, NLGL_, status 7) exist with an active PermissionCatalog EX row each ==';
SELECT (SELECT COUNT(*) FROM dbo.ExportSetup) AS ExportSetupRows, (SELECT COUNT(*) FROM dbo.PermissionCatalog WHERE TypeKey = 'EX') AS CatalogRows,
       (SELECT COUNT(*) FROM dbo.ExportSetup WHERE ExportName = 'nl_ap_invoice' AND ExportLogType = 'APINV' AND RTRIM(FileType) = 'csv' AND BatchPrefix = 'NLAP_' AND StatusCode = 3) AS ApFormatOk,
       (SELECT COUNT(*) FROM dbo.ExportSetup WHERE ExportName = 'nl_gl_journal' AND ExportLogType = 'GLJNL' AND RTRIM(FileType) = 'csv' AND BatchPrefix = 'NLGL_' AND StatusCode = 7) AS GlFormatOk,
       (SELECT COUNT(*) FROM dbo.PermissionCatalog WHERE TypeKey = 'EX' AND IsActive = 1 AND PermissionKey IN ('nl_ap_invoice', 'nl_gl_journal')) AS CatalogOk,
       CASE WHEN (SELECT COUNT(*) FROM dbo.ExportSetup) = 0 THEN 'BLOCKED (no format can be created on a screen)'
            WHEN (SELECT COUNT(*) FROM dbo.ExportSetup WHERE ExportName = 'nl_ap_invoice' AND ExportLogType = 'APINV' AND RTRIM(FileType) = 'csv' AND BatchPrefix = 'NLAP_' AND StatusCode = 3) = 1
             AND (SELECT COUNT(*) FROM dbo.ExportSetup WHERE ExportName = 'nl_gl_journal' AND ExportLogType = 'GLJNL' AND RTRIM(FileType) = 'csv' AND BatchPrefix = 'NLGL_' AND StatusCode = 7) = 1
             AND (SELECT COUNT(*) FROM dbo.PermissionCatalog WHERE TypeKey = 'EX' AND IsActive = 1 AND PermissionKey IN ('nl_ap_invoice', 'nl_gl_journal')) = 2 THEN 'PASS'
            ELSE 'FAIL' END AS Result;
GO
PRINT '== ap_export_run: the 2024-09 AP run (04-ap-export-formats.yaml ap_export_run). PENDING until a nl_ap_invoice file exists. Then: the exported set equals the eligible set computed from the tables (fiscal 2024-09, QC-approved at some time, Bill Type 0, AP Upload Only or Bill Payment, not Bill Generation, no validation row), one ExportFile named NLAP_<14 digits>.csv, ExportLog rows and amounts match, every bill has its StatusHistory 3 row, and the file has detail rows + 2 lines and a trailer carrying the count and the control total ==';
DECLARE @pat nvarchar(100) = N'NLAP[_]' + REPLICATE(N'[0-9]', 14) + N'.csv';
IF NOT EXISTS (SELECT 1 FROM dbo.ExportLog WHERE ExportType = 'APINV')
    SELECT 'PENDING (no AP file has been created)' AS Result
ELSE
BEGIN
    SELECT b.BL_BillID, b.BL_Amount INTO #ApEligible
      FROM dbo.Bill b JOIN #Acct a ON a.AccountID = b.BA_BillingAccountID
     WHERE b.DeleteInd = 0 AND b.BL_FiscalYear = 2024 AND b.BL_FiscalPeriodNo = 9 AND b.BillType = 0
       AND a.ServiceType IN (1, 2) AND a.EntryType <> 2 AND a.AccountStatus = 1
       AND EXISTS (SELECT 1 FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.SH_TableRowID = b.BL_BillID AND h.Status_Code = 2)
       AND NOT EXISTS (SELECT 1 FROM dbo.BillValidation_Tbl t WHERE t.BillID = b.BL_BillID);
    SELECT (SELECT COUNT(*) FROM #ApEligible) AS EligibleBills, (SELECT COUNT(*) FROM dbo.ExportLog WHERE ExportType = 'APINV') AS ExportLogRows,
           (SELECT COUNT(*) FROM dbo.ExportLog l JOIN #ApEligible e ON e.BL_BillID = l.BillID WHERE l.ExportType = 'APINV') AS ExportedAndEligible,
           (SELECT SUM(ExportAmount) FROM dbo.ExportLog WHERE ExportType = 'APINV') AS ExportedAmount, (SELECT SUM(BL_Amount) FROM #ApEligible) AS EligibleAmount,
           (SELECT COUNT(*) FROM dbo.ExportFile WHERE ExportShortName LIKE @pat) AS FilesNamedLikeThePattern,
           (SELECT COUNT(DISTINCT ExportFileID) FROM dbo.ExportLog WHERE ExportType = 'APINV') AS FilesLogged,
           CASE WHEN (SELECT COUNT(*) FROM #ApEligible) = (SELECT COUNT(*) FROM dbo.ExportLog WHERE ExportType = 'APINV')
                 AND (SELECT COUNT(*) FROM dbo.ExportLog l JOIN #ApEligible e ON e.BL_BillID = l.BillID WHERE l.ExportType = 'APINV') = (SELECT COUNT(*) FROM #ApEligible)
                 AND ABS(ISNULL((SELECT SUM(ExportAmount) FROM dbo.ExportLog WHERE ExportType = 'APINV'), 0) - ISNULL((SELECT SUM(BL_Amount) FROM #ApEligible), 0)) < 0.01
                 AND (SELECT COUNT(DISTINCT ExportFileID) FROM dbo.ExportLog WHERE ExportType = 'APINV') = 1
                 AND (SELECT COUNT(*) FROM dbo.ExportFile WHERE ExportShortName LIKE @pat) = 1 THEN 'PASS' ELSE 'FAIL' END AS Result;
    SELECT COUNT(*) AS ExportedBills, SUM(ISNULL(sh.Has, 0)) AS WithStatusHistory3,
           SUM(CASE WHEN b.Status_Code = 3 THEN 1 ELSE 0 END) AS AtStatusCode3,
           CASE WHEN COUNT(*) = SUM(ISNULL(sh.Has, 0))
                 AND COUNT(*) = SUM(CASE WHEN b.Status_Code = 3 THEN 1 ELSE 0 END) THEN 'PASS' ELSE 'FAIL' END AS Result
      FROM dbo.ExportLog l JOIN dbo.Bill b ON b.BL_BillID = l.BillID
      OUTER APPLY (SELECT TOP 1 1 AS Has FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.SH_TableRowID = l.BillID AND h.Status_Code = 3) sh
     WHERE l.ExportType = 'APINV';
    SELECT f.ExportShortName, LEN(f.ExportData) - LEN(REPLACE(f.ExportData, CHAR(10), N'')) AS Lines,
           (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID) + 2 AS ExpectedLinesIfOneRowPerBill,
           CHARINDEX(N'T,' + CONVERT(nvarchar(20), (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID)) + N',' +
                     CONVERT(nvarchar(30), CONVERT(decimal(18, 2), (SELECT SUM(l.ExportAmount) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID))), f.ExportData) AS TrailerAt,
           CASE WHEN LEN(f.ExportData) - LEN(REPLACE(f.ExportData, CHAR(10), N'')) = (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID) + 2
                 AND CHARINDEX(N'T,' + CONVERT(nvarchar(20), (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID)) + N',' +
                     CONVERT(nvarchar(30), CONVERT(decimal(18, 2), (SELECT SUM(l.ExportAmount) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID))), f.ExportData) > 0 THEN 'PASS' ELSE 'FAIL' END AS Result
      FROM dbo.ExportFile f WHERE f.ExportFileID IN (SELECT ExportFileID FROM dbo.ExportLog WHERE ExportType = 'APINV');
    SELECT a.AccountNumber, COUNT(*) AS RowsInTheFile, 'FAIL (must never be exported)' AS Result
      FROM dbo.ExportLog l JOIN dbo.Bill b ON b.BL_BillID = l.BillID JOIN #Acct a ON a.AccountID = b.BA_BillingAccountID
     WHERE l.ExportType = 'APINV' AND (a.ServiceType = 0 OR a.EntryType = 2 OR b.BillType <> 0) GROUP BY a.AccountNumber;
    IF OBJECT_ID('tempdb..#ExpectedTotals') IS NOT NULL
        SELECT (SELECT SUM(x.Expected) FROM #ExpectedTotals x JOIN #Acct a ON a.AccountNumber = x.AccountNumber
                  JOIN dbo.Bill b ON b.BA_BillingAccountID = a.AccountID AND CONVERT(date, b.BL_PeriodStart) = x.PeriodStart AND b.DeleteInd = 0
                  JOIN dbo.ExportLog l ON l.BillID = b.BL_BillID AND l.ExportType = 'APINV') AS ControlTotalFromTheFeed,
               (SELECT SUM(ExportAmount) FROM dbo.ExportLog WHERE ExportType = 'APINV') AS ExportedAmount,
               CASE WHEN ABS(ISNULL((SELECT SUM(x.Expected) FROM #ExpectedTotals x JOIN #Acct a ON a.AccountNumber = x.AccountNumber
                  JOIN dbo.Bill b ON b.BA_BillingAccountID = a.AccountID AND CONVERT(date, b.BL_PeriodStart) = x.PeriodStart AND b.DeleteInd = 0
                  JOIN dbo.ExportLog l ON l.BillID = b.BL_BillID AND l.ExportType = 'APINV'), 0) - ISNULL((SELECT SUM(ExportAmount) FROM dbo.ExportLog WHERE ExportType = 'APINV'), 0)) < 0.01 THEN 'PASS' ELSE 'FAIL' END AS Result;
END
GO
PRINT '== gl_export_run: the 2024-09 GL journal. PENDING until a nl_gl_journal file exists. Then: one GLJNL ExportLog row per eligible bill (the AP rules except that Bill Generation is admitted), one file named NLGL_<14 digits>.csv, 2 lines per bill (one debit, one credit) plus header and trailer, and the debits equal the credits equal the bills'' total ==';
DECLARE @glpat nvarchar(100) = N'NLGL[_]' + REPLICATE(N'[0-9]', 14) + N'.csv';
IF NOT EXISTS (SELECT 1 FROM dbo.ExportLog WHERE ExportType = 'GLJNL')
    SELECT 'PENDING (no GL file has been created)' AS Result
ELSE
BEGIN
    SELECT b.BL_BillID, b.BL_Amount INTO #GlEligible
      FROM dbo.Bill b JOIN #Acct a ON a.AccountID = b.BA_BillingAccountID
     WHERE b.DeleteInd = 0 AND b.BL_FiscalYear = 2024 AND b.BL_FiscalPeriodNo = 9 AND b.BillType = 0 AND a.ServiceType IN (1, 2) AND a.AccountStatus = 1
       AND EXISTS (SELECT 1 FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.SH_TableRowID = b.BL_BillID AND h.Status_Code = 2)
       AND NOT EXISTS (SELECT 1 FROM dbo.BillValidation_Tbl t WHERE t.BillID = b.BL_BillID);
    SELECT (SELECT COUNT(*) FROM #GlEligible) AS EligibleBills, (SELECT COUNT(*) FROM dbo.ExportLog WHERE ExportType = 'GLJNL') AS ExportLogRows,
           (SELECT SUM(ExportAmount) FROM dbo.ExportLog WHERE ExportType = 'GLJNL') AS ExportedAmount, (SELECT SUM(BL_Amount) FROM #GlEligible) AS EligibleAmount,
           (SELECT COUNT(*) FROM dbo.ExportFile WHERE ExportShortName LIKE @glpat) AS FilesNamedLikeThePattern,
           CASE WHEN (SELECT COUNT(*) FROM #GlEligible) = (SELECT COUNT(*) FROM dbo.ExportLog WHERE ExportType = 'GLJNL')
                 AND ABS(ISNULL((SELECT SUM(ExportAmount) FROM dbo.ExportLog WHERE ExportType = 'GLJNL'), 0) - ISNULL((SELECT SUM(BL_Amount) FROM #GlEligible), 0)) < 0.01
                 AND (SELECT COUNT(DISTINCT ExportFileID) FROM dbo.ExportLog WHERE ExportType = 'GLJNL') = 1
                 AND (SELECT COUNT(*) FROM dbo.ExportFile WHERE ExportShortName LIKE @glpat) = 1 THEN 'PASS' ELSE 'FAIL' END AS Result;
    SELECT f.ExportShortName, LEN(f.ExportData) - LEN(REPLACE(f.ExportData, CHAR(10), N'')) AS Lines,
           (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID) * 2 + 2 AS ExpectedLinesWithOneExpenseAccountPerBill,
           CASE WHEN LEN(f.ExportData) - LEN(REPLACE(f.ExportData, CHAR(10), N'')) = (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID) * 2 + 2 THEN 'PASS' ELSE 'FAIL' END AS Result
      FROM dbo.ExportFile f WHERE f.ExportFileID IN (SELECT ExportFileID FROM dbo.ExportLog WHERE ExportType = 'GLJNL');
END
GO
PRINT '== export_revert: no orphans after any revert: no ExportLog row without its ExportFile, no ExportFile without an ExportLog row, no StatusHistory 3 or 7 row on a bill without its ExportLog row, no bill at Status_Code 3 or 7 without that StatusHistory row. Trivially PASS while nothing has been exported ==';
SELECT (SELECT COUNT(*) FROM dbo.ExportLog l WHERE NOT EXISTS (SELECT 1 FROM dbo.ExportFile f WHERE f.ExportFileID = l.ExportFileID)) AS LogWithoutFile,
       (SELECT COUNT(*) FROM dbo.ExportFile f WHERE NOT EXISTS (SELECT 1 FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID)) AS FileWithoutLog,
       (SELECT COUNT(*) FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.Status_Code = 3
          AND NOT EXISTS (SELECT 1 FROM dbo.ExportLog l WHERE l.BillID = h.SH_TableRowID AND l.ExportType = 'APINV')) AS Status3WithoutLog,
       (SELECT COUNT(*) FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.Status_Code = 7
          AND NOT EXISTS (SELECT 1 FROM dbo.ExportLog l WHERE l.BillID = h.SH_TableRowID AND l.ExportType = 'GLJNL')) AS Status7WithoutLog,
       (SELECT COUNT(*) FROM dbo.Bill b WHERE b.DeleteInd = 0 AND b.Status_Code IN (3, 7)
          AND NOT EXISTS (SELECT 1 FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.SH_TableRowID = b.BL_BillID AND h.Status_Code = b.Status_Code)) AS StatusCodeWithoutHistory,
       CASE WHEN (SELECT COUNT(*) FROM dbo.ExportLog l WHERE NOT EXISTS (SELECT 1 FROM dbo.ExportFile f WHERE f.ExportFileID = l.ExportFileID)) = 0
             AND (SELECT COUNT(*) FROM dbo.ExportFile f WHERE NOT EXISTS (SELECT 1 FROM dbo.ExportLog l WHERE l.ExportFileID = f.ExportFileID)) = 0
             AND (SELECT COUNT(*) FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.Status_Code = 3 AND NOT EXISTS (SELECT 1 FROM dbo.ExportLog l WHERE l.BillID = h.SH_TableRowID AND l.ExportType = 'APINV')) = 0
             AND (SELECT COUNT(*) FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.Status_Code = 7 AND NOT EXISTS (SELECT 1 FROM dbo.ExportLog l WHERE l.BillID = h.SH_TableRowID AND l.ExportType = 'GLJNL')) = 0
             AND (SELECT COUNT(*) FROM dbo.Bill b WHERE b.DeleteInd = 0 AND b.Status_Code IN (3, 7)
                   AND NOT EXISTS (SELECT 1 FROM dbo.StatusHistory h WHERE h.Table_Code = 'BL' AND h.SH_TableRowID = b.BL_BillID AND h.Status_Code = b.Status_Code)) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result;
GO
PRINT '== blocked_by_validation: IsError = 1 in BillValidation_Tbl means a CHECK COULD NOT RUN (BillValidation_Run.sql writes it only when an evaluator threw or a test has no check in this release); a finding is a row with IsError = 0. (1) no check may have failed to run; (2) no bill with a finding may be at Status_Code 2 or beyond (the job takes it back to 1; a manual Validate does not, so the AP builder must also leave it out); (3) the SGU Student Center pair (estimate and correction) has its findings and was exported by no one ==';
SELECT COUNT(*) AS ChecksThatCouldNotRun, CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result FROM dbo.BillValidation_Tbl WHERE IsError = 1;
SELECT COUNT(DISTINCT t.BillID) AS BillsWithAFinding,
       SUM(CASE WHEN b.Status_Code >= 2 THEN 1 ELSE 0 END) AS FindingRowsOnBillsAtStatus2OrMore,
       CASE WHEN SUM(CASE WHEN b.Status_Code >= 2 THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.BillValidation_Tbl t JOIN dbo.Bill b ON b.BL_BillID = t.BillID WHERE t.IsError = 0 AND b.DeleteInd = 0;
SELECT a.AccountNumber, CONVERT(date, b.BL_PeriodStart) AS PeriodStart, b.BL_Amount, b.BillType, b.Status_Code,
       STRING_AGG(CONVERT(varchar(4), t.BillTestID), ',') WITHIN GROUP (ORDER BY t.BillTestID) AS Findings,
       (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.BillID = b.BL_BillID) AS ExportLogRows,
       CASE WHEN b.BL_Amount = 935.90 AND ',' + STRING_AGG(CONVERT(varchar(4), t.BillTestID), ',') + ',' LIKE '%,3,%' AND ',' + STRING_AGG(CONVERT(varchar(4), t.BillTestID), ',') + ',' LIKE '%,15,%'
             AND (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.BillID = b.BL_BillID) = 0 THEN 'PASS (estimate: tests 3 and 15)'
            WHEN b.BL_Amount = 885.32 AND ',' + STRING_AGG(CONVERT(varchar(4), t.BillTestID), ',') + ',' LIKE '%,15,%' AND ',' + STRING_AGG(CONVERT(varchar(4), t.BillTestID), ',') + ',' LIKE '%,47,%'
             AND (SELECT COUNT(*) FROM dbo.ExportLog l WHERE l.BillID = b.BL_BillID) = 0 THEN 'PASS (correction: tests 15 and 47)'
            ELSE 'FAIL' END AS Result
  FROM dbo.BillValidation_Tbl t JOIN dbo.Bill b ON b.BL_BillID = t.BillID JOIN #Acct a ON a.AccountID = b.BA_BillingAccountID
 WHERE t.IsError = 0 AND b.DeleteInd = 0 AND a.AccountNumber = 'SYN-SGU-A-0020004'
 GROUP BY a.AccountNumber, b.BL_BillID, b.BL_PeriodStart, b.BL_Amount, b.BillType, b.Status_Code;
GO
PRINT '== ridgeline_gl_only: SYN-RWL-G-0000001 is GL only. (1) No AP-type ExportLog row (APINV, AP, APDIS) names one of its bills; (2) once Stage 7 has generated its statements, each is coded to 5150-WIND and its lines equal its total (a generated bill keeps four decimals against cent-rounded lines, product finding 72, so the total is rounded), and the July 2024 statement is 129330.27 ==';
SELECT COUNT(*) AS ApRowsNamingTheStatement, CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.ExportLog el JOIN dbo.Bill bl ON bl.BL_BillID = el.BillID JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
 WHERE a.AccountNumber = 'SYN-RWL-G-0000001' AND el.ExportType LIKE 'AP%';
SELECT CONVERT(char(10), bl.BL_PeriodStart, 120) AS PeriodStart, ROUND(bl.BL_Amount, 2) AS BillAmount, ex.GL_AccountCode AS ExpenseAccount, SUM(bi.BI_Amount) AS CodedAmount,
       CASE WHEN ex.GL_AccountCode = '5150-WIND' AND ABS(ROUND(bl.BL_Amount, 2) - SUM(bi.BI_Amount)) <= 0.01
                 AND (CONVERT(char(10), bl.BL_PeriodStart, 120) <> '2024-07-01' OR ABS(ROUND(bl.BL_Amount, 2) - 129330.27) <= 0.01) THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
  LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = COALESCE(bi.BI_EXpAcctID, a.ExpenseId)
 WHERE a.AccountNumber = 'SYN-RWL-G-0000001' AND bl.DeleteInd = 0
 GROUP BY bl.BL_BillID, bl.BL_PeriodStart, ROUND(bl.BL_Amount, 2), ex.GL_AccountCode ORDER BY bl.BL_PeriodStart;
IF NOT EXISTS (SELECT 1 FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID WHERE a.AccountNumber = 'SYN-RWL-G-0000001' AND bl.DeleteInd = 0)
    SELECT 'PENDING (Stage 7 generates the statements)' AS Result;
GO
PRINT '== ridgeline_bct_coded_once: the first bill credit transfer (152792.65) is coded once. Three lines: SYN-VED-A-0010014 2024-07-01..2024-08-04 generation credit -152792.65 and transferred +152792.65 (net 0.00), SYN-VED-A-0010013 2024-08-05..2024-09-04 received -152792.65, each coded 5100-ELEC; NetCredit must be -152792.65 ==';
SELECT a.AccountNumber, CONVERT(char(10), bl.BL_PeriodStart, 120) AS PeriodStart, bi.BI_Seq, bi.BI_Amount, own.GL_AccountCode AS ExplicitCode, ex.GL_AccountCode AS EffectiveCode,
       CASE WHEN ex.GL_AccountCode = '5100-ELEC' THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.BillItem bi JOIN dbo.Bill bl ON bl.BL_BillID = bi.BL_BillID JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
  LEFT JOIN dbo.GLAccount own ON own.GL_AccountID = bi.BI_EXpAcctID
  LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = COALESCE(bi.BI_EXpAcctID, a.ExpenseId)
 WHERE a.AccountNumber IN ('SYN-VED-A-0010014', 'SYN-VED-A-0010013') AND ABS(bi.BI_Amount) = 152792.65 AND bi.DeleteInd = 0 AND bl.DeleteInd = 0
 ORDER BY bl.BL_PeriodStart, a.AccountNumber, bi.BI_Seq;
SELECT COUNT(*) AS Lines, SUM(bi.BI_Amount) AS NetCredit, -152792.65 AS Expected,
       CASE WHEN COUNT(*) = 3 AND ABS(SUM(bi.BI_Amount) + 152792.65) < 0.005 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.BillItem bi JOIN dbo.Bill bl ON bl.BL_BillID = bi.BL_BillID JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
 WHERE a.AccountNumber IN ('SYN-VED-A-0010014', 'SYN-VED-A-0010013') AND ABS(bi.BI_Amount) = 152792.65 AND bi.DeleteInd = 0 AND bl.DeleteInd = 0;
GO
PRINT '== accrual_pair: SysConstants MPA Accruals and MPA Reversals resolve to Commodity rows named Accruals and Reversals; the one open accrual is SGU Admin Hall''s 2026-01-15..2026-02-14 bill, Bill Type 2 (Accrual), 3400.00, one line on the Accruals commodity and no BillAccrualMap row; dbo.Accrual_Bill does not exist in this instance (the reversal is blocked, 06-accruals.yaml) ==';
SELECT sc.Item, sc.Value_I, cy.CY_CommodityName, cy.CompanyID,
       CASE WHEN cy.CY_CommodityID IS NOT NULL AND cy.CY_CommodityName = CASE sc.Item WHEN 'MPA Accruals' THEN 'Accruals' ELSE 'Reversals' END THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.SysConstants sc LEFT JOIN dbo.Commodity cy ON cy.CY_CommodityID = sc.Value_I WHERE sc.Item IN ('MPA Accruals', 'MPA Reversals');
SELECT a.AccountNumber, CONVERT(date, bl.BL_PeriodStart) AS PeriodStart, bl.BillType, bl.BL_Amount,
       (SELECT COUNT(*) FROM dbo.BillAccrualMap m WHERE m.BillID = bl.BL_BillID OR m.ReversalBillID = bl.BL_BillID) AS MapRows,
       (SELECT COUNT(*) FROM dbo.BillItem bi JOIN dbo.SysConstants sc ON sc.Item = 'MPA Accruals' AND sc.Value_I = bi.CY_CommodityID WHERE bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0) AS AccrualLines,
       CASE WHEN a.AccountNumber = 'SYN-SGU-A-0020001' AND CONVERT(date, bl.BL_PeriodStart) = '2026-01-15' AND bl.BillType = 2 AND bl.BL_Amount = 3400.00
             AND (SELECT COUNT(*) FROM dbo.BillAccrualMap m WHERE m.BillID = bl.BL_BillID OR m.ReversalBillID = bl.BL_BillID) = 0
             AND (SELECT COUNT(*) FROM dbo.BillItem bi JOIN dbo.SysConstants sc ON sc.Item = 'MPA Accruals' AND sc.Value_I = bi.CY_CommodityID WHERE bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0) = 1 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID WHERE bl.DeleteInd = 0 AND bl.BillType = 2;
SELECT (SELECT COUNT(*) FROM dbo.Bill WHERE BillType = 2 AND DeleteInd = 0) AS AccrualBills, 1 AS Expected,
       (SELECT COUNT(*) FROM sys.tables WHERE name = 'Accrual_Bill') AS AccrualBillTableExists, 0 AS ExpectedAccrualBillTable,
       (SELECT COUNT(*) FROM sys.tables WHERE name = 'BillAccrualMap') AS BillAccrualMapTableExists, 1 AS ExpectedBillAccrualMapTable,
       CASE WHEN (SELECT COUNT(*) FROM dbo.Bill WHERE BillType = 2 AND DeleteInd = 0) = 1 AND (SELECT COUNT(*) FROM sys.tables WHERE name = 'Accrual_Bill') = 0
             AND (SELECT COUNT(*) FROM sys.tables WHERE name = 'BillAccrualMap') = 1 THEN 'PASS' ELSE 'FAIL' END AS Result;
GO
DROP TABLE #Acct;
