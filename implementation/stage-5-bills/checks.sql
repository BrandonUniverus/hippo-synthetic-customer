-- Stage 5 checks. Read-only. Every check ends in a Result column (PASS or FAIL, or PENDING where a later stage supplies the data).
-- Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i expected-bill-totals.sql -i checks.sql
-- (expected-bill-totals.sql is written by the command in 03-bills.yaml expected_totals_feed and creates the temp table
-- #ExpectedTotals; both files must run in ONE sqlcmd session. Without it only the 24 sample-PDF totals are asserted.)
-- 2026-11-10: rewritten. Every check asserts a value; the account list reads dbo.BillingAccount_TBL (the BillingAccount view is
-- scoped to the signed-in user and returns no rows to a plain session); the Thermal Plant cost centers and Ridgeline's statement
-- are expected at 0 bills here and PENDING until Stage 7.
SET NOCOUNT ON;
SELECT ba.BA_BillingAccountID AS AccountID, ba.BA_BillingAccountNumber AS AccountNumber, ba.BA_PrevBillingAccNumber AS PrevNumber,
       ba.CompanyID, ba.BillType_Code AS EntryType, ba.Type_Code AS ServiceType
  INTO #Acct FROM dbo.BillingAccount_TBL ba;
GO

PRINT '== validation_rules_set 1 of 4: every test that Northlake exercises or enables (42 of the 48; 01-bill-validation-rules.yaml test_catalog) has a row, not disabled, on the Bill Save tab at some scope ==';
SELECT COUNT(*) AS ExpectedTests,
       SUM(CASE WHEN c.BV_TestID IS NOT NULL THEN 1 ELSE 0 END) AS ConfiguredTests,
       ISNULL(STRING_AGG(CASE WHEN c.BV_TestID IS NULL THEN CONVERT(varchar(3), e.TestID) END, ','), '') AS MissingTests,
       CASE WHEN SUM(CASE WHEN c.BV_TestID IS NULL THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM (VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11),(12),(13),(14),(15),(16),(17),(18),(19),(20),(21),(22),(23),(24),(25),(26),(27),(28),
               (30),(31),(32),(33),(34),(35),(36),(39),(40),(41),(42),(43),(47),(99)) e(TestID)
  LEFT JOIN (SELECT DISTINCT BV_TestID FROM dbo.BillValidation WHERE BV_IsDisabled = 0 AND BVT_ID = 1) c ON c.BV_TestID = e.TestID;
GO
PRINT '== validation_rules_set 2 of 4: rows per scope and tab (scope 0 Global, 1 Company, 2 Group, 3 Account; tab 1 Bill Save, 2 Batch Test) ==';
SELECT s.ScopeType, s.Mode, s.Expected, COUNT(v.BV_TestID) AS Actual,
       CASE WHEN COUNT(v.BV_TestID) = s.Expected THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM (VALUES (0,1,12),(0,2,12),(1,1,11),(1,2,11),(2,1,21),(2,2,0),(3,1,14),(3,2,14)) s(ScopeType, Mode, Expected)
  LEFT JOIN dbo.BillValidation v ON v.BV_ScopeType = s.ScopeType AND v.BVT_ID = s.Mode
 GROUP BY s.ScopeType, s.Mode, s.Expected
 ORDER BY s.ScopeType, s.Mode;
GO
PRINT '== validation_rules_set 3 of 4: the account rows carry their values (a disabled row only needs to be disabled; an enabled row needs its Percent and Amount) ==';
SELECT x.Account, x.TestID, x.Disabled AS ExpectedDisabled, x.Pct AS ExpectedPercent, x.Amt AS ExpectedAmount,
       v.BV_IsDisabled AS ActualDisabled, v.BV_PercentQuantity AS ActualPercent, v.BV_AbsQuantity AS ActualAmount,
       CASE WHEN v.BV_TestID IS NULL THEN 'FAIL'
            WHEN x.Disabled = 1 AND v.BV_IsDisabled = 1 THEN 'PASS'
            WHEN x.Disabled = 0 AND v.BV_IsDisabled = 0 AND ISNULL(v.BV_PercentQuantity, -1) = ISNULL(x.Pct, -1)
                 AND ABS(ISNULL(v.BV_AbsQuantity, -1) - ISNULL(x.Amt, -1)) < 0.0001 THEN 'PASS'
            ELSE 'FAIL' END AS Result
  FROM (VALUES ('SYN-VED-A-0010002', 21, 0, 60,   1000.0),
               ('SYN-SGU-A-0020004', 25, 1, NULL, NULL),
               ('SYN-RCU-A-0030003', 14, 1, NULL, NULL),
               ('SYN-NTP-C-0000001', 23, 0, NULL, 250000.0),
               ('SYN-VED-A-0010014', 21, 1, NULL, NULL),
               ('SYN-VED-A-0010014', 25, 1, NULL, NULL),
               ('SYN-VED-A-0010001', 27, 0, NULL, 25000.0),
               ('SYN-VED-A-0010001', 30, 0, NULL, 120.0),
               ('SYN-VED-A-0010001', 31, 0, NULL, 100.0),
               ('SYN-VED-A-0010001', 33, 0, NULL, 0.13),
               ('SYN-VED-A-0010003', 27, 0, NULL, 25000.0),
               ('SYN-VED-A-0010003', 30, 0, NULL, 130.0),
               ('SYN-VED-A-0010003', 31, 0, NULL, 130.0),
               ('SYN-VED-A-0010003', 33, 0, NULL, 0.2)) x(Account, TestID, Disabled, Pct, Amt)
  JOIN #Acct a ON a.AccountNumber = x.Account
  LEFT JOIN dbo.BillValidation v ON v.BV_ScopeType = 3 AND v.BV_TestSetID = a.AccountID AND v.BV_TestID = x.TestID AND v.BVT_ID = 1
 ORDER BY x.Account, x.TestID;
GO
PRINT '== validation_rules_set 4 of 4: the Validation Bay group exists, holds SYN-SGU-A-0020005 and carries its 21 Bill Save rows ==';
SELECT (SELECT COUNT(*) FROM dbo.BillValidationGroup WHERE GroupName = N'Validation Bay') AS Groups,
       (SELECT COUNT(*) FROM dbo.BillValidationGroupMember m JOIN dbo.BillValidationGroup g ON g.GroupID = m.GroupID
          JOIN #Acct a ON a.AccountID = m.BA_BillingAccountID WHERE g.GroupName = N'Validation Bay' AND a.AccountNumber = 'SYN-SGU-A-0020005') AS BayMember,
       (SELECT COUNT(*) FROM dbo.BillValidation v JOIN dbo.BillValidationGroup g ON g.GroupID = v.BV_TestSetID
         WHERE v.BV_ScopeType = 2 AND v.BVT_ID = 1 AND g.GroupName = N'Validation Bay') AS GroupRows,
       CASE WHEN (SELECT COUNT(*) FROM dbo.BillValidationGroup WHERE GroupName = N'Validation Bay') = 1
             AND (SELECT COUNT(*) FROM dbo.BillValidationGroupMember m JOIN dbo.BillValidationGroup g ON g.GroupID = m.GroupID
                    JOIN #Acct a ON a.AccountID = m.BA_BillingAccountID WHERE g.GroupName = N'Validation Bay' AND a.AccountNumber = 'SYN-SGU-A-0020005') = 1
             AND (SELECT COUNT(*) FROM dbo.BillValidation v JOIN dbo.BillValidationGroup g ON g.GroupID = v.BV_TestSetID
                   WHERE v.BV_ScopeType = 2 AND v.BVT_ID = 1 AND g.GroupName = N'Validation Bay') = 21 THEN 'PASS' ELSE 'FAIL' END AS Result;
GO
PRINT '== validation_findings_expected: after the validation job has run, the planned findings are in BillValidation_Tbl (IsError = 0) and the planned non-findings are not. ShouldReport 1 = the test must list the bill, 0 = it must not (01-bill-validation-rules.yaml test_catalog). The SGU Admin Hall accrual row (test 99) needs Stage 6 ==';
SELECT x.Account, x.PeriodEnd, x.TestID, x.ShouldReport, r.Reported,
       CASE WHEN x.TestID = 99 AND r.HasAccrual = 0 THEN 'PENDING (Stage 6)'
            WHEN x.ShouldReport = r.Reported THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM (VALUES ('SYN-VED-A-0010003', CONVERT(date, '2024-09-04'), 41, 1),
               ('SYN-VED-A-0010003', CONVERT(date, '2024-09-04'), 31, 1),
               ('SYN-VED-A-0010003', CONVERT(date, '2024-09-04'), 27, 0),
               ('SYN-VED-A-0010003', CONVERT(date, '2024-09-04'), 30, 0),
               ('SYN-VED-A-0010003', CONVERT(date, '2024-09-04'), 33, 0),
               ('SYN-VED-A-0010001', CONVERT(date, '2024-04-04'), 27, 1),
               ('SYN-VED-A-0010001', CONVERT(date, '2024-04-04'), 30, 1),
               ('SYN-VED-A-0010001', CONVERT(date, '2024-04-04'), 33, 1),
               ('SYN-VED-A-0010001', CONVERT(date, '2024-04-04'), 31, 0),
               ('SYN-SGU-A-0020004', CONVERT(date, '2024-11-14'), 3, 1),
               ('SYN-SGU-A-0020004', CONVERT(date, '2024-11-14'), 15, 1),
               ('SYN-SGU-A-0020004', CONVERT(date, '2024-11-14'), 47, 1),
               ('SYN-SGU-A-0020004', CONVERT(date, '2024-11-14'), 25, 0),
               ('SYN-SGU-A-0020001', CONVERT(date, '2024-01-14'), 5, 1),
               ('SYN-SGU-A-0020001', CONVERT(date, '2024-02-14'), 5, 0),
               ('SYN-HOS-P-0000002', CONVERT(date, '2025-02-28'), 1, 1),
               ('SYN-HOS-P-0000001', CONVERT(date, '2025-02-28'), 1, 0),
               ('SYN-HOS-P-0000001', CONVERT(date, '2025-03-31'), 3, 1),
               ('SYN-SGU-A-0020001', CONVERT(date, '2026-02-14'), 99, 1)) x(Account, PeriodEnd, TestID, ShouldReport)
  JOIN #Acct a ON a.AccountNumber = x.Account
  OUTER APPLY (SELECT CASE WHEN EXISTS (SELECT 1 FROM dbo.Bill b JOIN dbo.BillValidation_Tbl t ON t.BillID = b.BL_BillID
                                         WHERE b.BA_BillingAccountID = a.AccountID AND b.DeleteInd = 0 AND CONVERT(date, b.BL_PeriodEnd) = x.PeriodEnd
                                           AND t.BillTestID = x.TestID AND t.IsError = 0) THEN 1 ELSE 0 END AS Reported,
                      CASE WHEN EXISTS (SELECT 1 FROM dbo.Bill b2 WHERE b2.BA_BillingAccountID = a.AccountID AND b2.BillType = 2 AND b2.DeleteInd = 0) THEN 1 ELSE 0 END AS HasAccrual) r
 ORDER BY x.Account, x.PeriodEnd, x.TestID;
GO
PRINT '== imports_configured: BillImportPro_Utility rows exist for Valley Electric and River City, and exactly the 31 importer accounts (14 Valley Electric including the Ridgeline generator, 17 River City) are mapped. BillImportPro_Utility is keyed by provider and company text, so up to six rows (two providers x three companies) is normal ==';
SELECT COUNT(DISTINCT u.BIPUtilityProviderID) AS UtilityRows, COUNT(DISTINCT m.BillingAccountID) AS MappedAccounts, 31 AS ExpectedAccounts,
       CASE WHEN COUNT(DISTINCT u.BIPUtilityProviderID) BETWEEN 2 AND 6 AND COUNT(DISTINCT m.BillingAccountID) = 31 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.BillImportPro_Utility u LEFT JOIN dbo.BillImportPro_AccMeter m ON m.BIPUtilityProviderID = u.BIPUtilityProviderID;
SELECT u.BIPUtilityProviderID, u.ProviderName_BIF, u.CompanyName_BIF, u.CompanyID, u.AutoMap, COUNT(m.BIPAcctMeterID) AS MappedRows
  FROM dbo.BillImportPro_Utility u LEFT JOIN dbo.BillImportPro_AccMeter m ON m.BIPUtilityProviderID = u.BIPUtilityProviderID
 GROUP BY u.BIPUtilityProviderID, u.ProviderName_BIF, u.CompanyName_BIF, u.CompanyID, u.AutoMap
 ORDER BY u.BIPUtilityProviderID;
GO
PRINT '== bills_per_account: 24 bills per account, except the Ridgeline generator 17, SGU Library 23 (the late_bill fixture), SGU Student Center 25 (estimate and correction), the six Thermal Plant cost centers 0 until Stage 7 (then 24) and SYN-RWL-G-0000001 0 until Stage 7 (then 18). Total 1049 after Stage 5, 1211 after Stage 7 ==';
WITH expected AS (
    SELECT a.AccountID, a.AccountNumber, a.PrevNumber,
           CASE a.AccountNumber WHEN 'SYN-VED-A-0010014' THEN 17 WHEN 'SYN-SGU-A-0020003' THEN 23 WHEN 'SYN-SGU-A-0020004' THEN 25
                                WHEN 'SYN-RWL-G-0000001' THEN 18 ELSE 24 END AS Expected,
           CASE WHEN a.AccountNumber LIKE 'SYN-NTP-C-%' OR a.AccountNumber = 'SYN-RWL-G-0000001' THEN 1 ELSE 0 END AS LaterStage
      FROM #Acct a),
actual AS (SELECT BA_BillingAccountID AS AccountID, COUNT(*) AS Bills, MIN(BL_PeriodStart) AS FirstStart, MAX(BL_PeriodEnd) AS LastEnd
             FROM dbo.Bill WHERE DeleteInd = 0 GROUP BY BA_BillingAccountID)
SELECT e.AccountNumber, e.PrevNumber, e.Expected, ISNULL(x.Bills, 0) AS Actual, CONVERT(date, x.FirstStart) AS FirstPeriodStart, CONVERT(date, x.LastEnd) AS LastPeriodEnd,
       CASE WHEN ISNULL(x.Bills, 0) = e.Expected THEN 'PASS'
            WHEN e.LaterStage = 1 AND ISNULL(x.Bills, 0) = 0 THEN 'PENDING (Stage 7)'
            ELSE 'FAIL' END AS Result
  FROM expected e LEFT JOIN actual x ON x.AccountID = e.AccountID
 ORDER BY e.AccountNumber;
SELECT COUNT(*) AS BillsEntered, CASE WHEN COUNT(*) IN (1049, 1211) THEN 'PASS' ELSE 'FAIL' END AS Result FROM dbo.Bill WHERE DeleteInd = 0;
GO
PRINT '== charge_lines_sum_to_total: for every bill, Total Due = sum of line items + previous balance - payment received, within 0.01 (second result set lists the bills that fail) ==';
SELECT COUNT(*) AS BillsChecked, SUM(CASE WHEN ABS(t.BL_Amount - (t.Lines + t.Past - t.Pmt)) > 0.01 THEN 1 ELSE 0 END) AS Failing,
       CASE WHEN SUM(CASE WHEN ABS(t.BL_Amount - (t.Lines + t.Past - t.Pmt)) > 0.01 THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM (SELECT bl.BL_BillID, bl.BL_Amount, ISNULL(bl.BL_PastAmount, 0) AS Past, ISNULL(bl.BL_PmtRecdAmount, 0) AS Pmt, SUM(bi.BI_Amount) AS Lines
          FROM dbo.Bill bl JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
         WHERE bl.DeleteInd = 0 GROUP BY bl.BL_BillID, bl.BL_Amount, bl.BL_PastAmount, bl.BL_PmtRecdAmount) t;
SELECT TOP 50 a.AccountNumber, CONVERT(date, bl.BL_PeriodStart) AS PeriodStart, bl.BL_Amount, SUM(bi.BI_Amount) AS LineItemTotal, 'FAIL' AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
 WHERE bl.DeleteInd = 0
 GROUP BY a.AccountNumber, bl.BL_BillID, bl.BL_PeriodStart, bl.BL_Amount, bl.BL_PastAmount, bl.BL_PmtRecdAmount
HAVING ABS(bl.BL_Amount - (SUM(bi.BI_Amount) + ISNULL(bl.BL_PastAmount, 0) - ISNULL(bl.BL_PmtRecdAmount, 0))) > 0.01
 ORDER BY a.AccountNumber, bl.BL_PeriodStart;
GO
PRINT '== bill_totals_expected_vs_actual (the 24 sample-PDF totals, 03-bills.yaml sample_bill_totals): the bill for that account and period has the printed Total Due (HOS Student Center Feb-25 = 2629.00 + 1310.55 - 500.00 = 3439.55). The Thermal Plant and Ridgeline rows are PENDING until Stage 7 ==';
SELECT x.Bill, x.Account, x.PeriodStart, x.Expected + x.Delta AS ExpectedTotalDue, a.Bills AS BillsFound, a.ActualMin AS ActualTotalDue, x.Stage,
       CASE WHEN a.Bills = 0 AND x.Stage = 7 THEN 'PENDING (Stage 7)'
            WHEN a.Bills = 0 THEN 'FAIL (no bill)'
            WHEN a.MatchCount >= 1 THEN 'PASS' ELSE 'FAIL' END AS Result
  INTO #AnchorResult
  FROM (VALUES
    ('ved_admin_hall_2024_04',            'SYN-VED-A-0010001', CONVERT(date, '2024-03-05'),   6888.42, 0.00, 5),
    ('ved_science_center_2024_08',        'SYN-VED-A-0010002', CONVERT(date, '2024-07-05'),  15087.59, 0.00, 5),
    ('ved_library_2024_09',               'SYN-VED-A-0010003', CONVERT(date, '2024-08-05'),   5114.37, 0.00, 5),
    ('ved_student_center_2025_01',        'SYN-VED-A-0010004', CONVERT(date, '2024-12-05'),   8469.10, 0.00, 5),
    ('ved_central_plant_2024_09',         'SYN-VED-A-0010013', CONVERT(date, '2024-08-05'), 151171.47, 0.00, 5),
    ('ved_ridgeline_generator_2024_07',   'SYN-VED-A-0010014', CONVERT(date, '2024-07-01'),   1077.45, 0.00, 5),
    ('ved_ridgeline_generator_2025_01',   'SYN-VED-A-0010014', CONVERT(date, '2025-01-05'),   6753.10, 0.00, 5),
    ('sgu_admin_hall_2025_04',            'SYN-SGU-A-0020001', CONVERT(date, '2025-03-15'),   1483.85, 0.00, 5),
    ('sgu_science_center_2025_01',        'SYN-SGU-A-0020002', CONVERT(date, '2024-12-15'),  13070.88, 0.00, 5),
    ('sgu_student_2024_11_estimated',     'SYN-SGU-A-0020004', CONVERT(date, '2024-10-15'),    935.90, 0.00, 5),
    ('sgu_student_2024_11_corrected',     'SYN-SGU-A-0020004', CONVERT(date, '2024-10-15'),    885.32, 0.00, 5),
    ('rcu_admin_hall_2025_02',            'SYN-RCU-A-0030001', CONVERT(date, '2025-02-01'),   3762.60, 0.00, 5),
    ('rcu_student_center_2025_02',        'SYN-RCU-A-0030002', CONVERT(date, '2025-02-01'),   8479.40, 0.00, 5),
    ('rcu_cedar_row_a_2024_09',           'SYN-RCU-A-0030003', CONVERT(date, '2024-08-15'),   1984.50, 0.00, 5),
    ('rcu_cedar_row_b_2025_02',           'SYN-RCU-A-0030004', CONVERT(date, '2025-01-15'),   2128.00, 0.00, 5),
    ('hos_science_center_2025_02',        'SYN-HOS-P-0000001', CONVERT(date, '2025-02-01'),   4474.43, 0.00, 5),
    ('hos_science_center_2025_03',        'SYN-HOS-P-0000001', CONVERT(date, '2025-03-01'),   4347.52, 0.00, 5),
    ('hos_student_center_2025_02',        'SYN-HOS-P-0000002', CONVERT(date, '2025-02-01'),   2629.00, 810.55, 5),
    ('hos_cedar_row_carport_2025_02',     'SYN-HOS-P-0000003', CONVERT(date, '2025-02-01'),   1997.11, 0.00, 5),
    ('ntp_science_center_2024_07',        'SYN-NTP-C-0000001', CONVERT(date, '2024-07-01'),  35873.48, 0.00, 7),
    ('ntp_science_center_2025_03',        'SYN-NTP-C-0000001', CONVERT(date, '2025-03-01'),  22760.92, 0.00, 7),
    ('ntp_admin_hall_2025_01',            'SYN-NTP-C-0000002', CONVERT(date, '2025-01-01'),   8561.20, 0.00, 7),
    ('ntp_student_center_2024_11',        'SYN-NTP-C-0000004', CONVERT(date, '2024-11-01'),   6120.40, 0.00, 7),
    ('rwl_transfer_2024_07',              'SYN-RWL-G-0000001', CONVERT(date, '2024-07-01'), 129330.27, 0.00, 7)) x(Bill, Account, PeriodStart, Expected, Delta, Stage)
  JOIN #Acct acc ON acc.AccountNumber = x.Account
  OUTER APPLY (SELECT COUNT(*) AS Bills, MIN(q.BL_Amount) AS ActualMin, ISNULL(SUM(q.IsMatch), 0) AS MatchCount
                 FROM (SELECT b.BL_Amount, CASE WHEN ABS(b.BL_Amount - (x.Expected + x.Delta)) <= 0.01 THEN 1 ELSE 0 END AS IsMatch
                         FROM dbo.Bill b WHERE b.BA_BillingAccountID = acc.AccountID AND CONVERT(date, b.BL_PeriodStart) = x.PeriodStart AND b.DeleteInd = 0) q) a;
SELECT Result, COUNT(*) AS Bills FROM #AnchorResult GROUP BY Result ORDER BY Result;
SELECT * FROM #AnchorResult WHERE Result <> 'PASS' ORDER BY Bill;
GO
PRINT '== bill_totals_expected_vs_actual (the feed, every bill): #ExpectedTotals from expected-bill-totals.sql against the bills entered; the Thermal Plant rows are PENDING until Stage 7. Nothing below runs when the feed was not loaded ==';
IF OBJECT_ID('tempdb..#ExpectedTotals') IS NULL
    PRINT 'feed not loaded: run expected-bill-totals.sql first, in the same sqlcmd session (03-bills.yaml expected_totals_feed)'
ELSE
BEGIN
    SELECT e.AccountNumber, e.PeriodStart, e.Expected + ISNULL(adj.Delta, 0) AS ExpectedTotalDue, a.Bills AS BillsFound, a.ActualMin AS ActualTotalDue, e.ProviderId,
           CASE WHEN a.Bills = 0 AND e.ProviderId = 'northlake_thermal_plant' THEN 'PENDING (Stage 7)'
                WHEN a.Bills = 0 THEN 'FAIL (no bill)'
                WHEN a.MatchCount >= 1 THEN 'PASS' ELSE 'FAIL' END AS Result
      INTO #FeedResult
      FROM #ExpectedTotals e
      JOIN #Acct acc ON acc.AccountNumber = e.AccountNumber
      LEFT JOIN (VALUES ('SYN-HOS-P-0000002', CONVERT(date, '2025-02-01'), CONVERT(money, 810.55))) adj(AccountNumber, PeriodStart, Delta)
             ON adj.AccountNumber = e.AccountNumber AND adj.PeriodStart = e.PeriodStart
      OUTER APPLY (SELECT COUNT(*) AS Bills, MIN(b.BL_Amount) AS ActualMin,
                          SUM(CASE WHEN ABS(b.BL_Amount - (e.Expected + ISNULL(adj.Delta, 0))) <= 0.01 THEN 1 ELSE 0 END) AS MatchCount
                     FROM dbo.Bill b WHERE b.BA_BillingAccountID = acc.AccountID AND CONVERT(date, b.BL_PeriodStart) = e.PeriodStart AND b.DeleteInd = 0) a;
    SELECT (SELECT COUNT(*) FROM #ExpectedTotals) AS ExpectedRows, (SELECT COUNT(*) FROM #FeedResult) AS RowsMatchedToAnAccount,
           SUM(CASE WHEN Result = 'PASS' THEN 1 ELSE 0 END) AS Pass, SUM(CASE WHEN Result LIKE 'PENDING%' THEN 1 ELSE 0 END) AS Pending,
           SUM(CASE WHEN Result LIKE 'FAIL%' THEN 1 ELSE 0 END) AS Fail,
           CASE WHEN (SELECT COUNT(*) FROM #ExpectedTotals) = (SELECT COUNT(*) FROM #FeedResult) AND SUM(CASE WHEN Result LIKE 'FAIL%' THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
      FROM #FeedResult;
    SELECT TOP 100 * FROM #FeedResult WHERE Result LIKE 'FAIL%' ORDER BY AccountNumber, PeriodStart;
END
GO
PRINT '== bill_type_set: Bill Type Estimated (1) on exactly the SGU Student Center estimate and the Helios Science Center Mar-25 backfill bill, no Accrual (2) yet (Stage 6 enters the one accrual) ==';
SELECT a.AccountNumber, CONVERT(date, bl.BL_PeriodStart) AS PeriodStart, bl.BL_Amount, bl.BillType,
       CASE WHEN (a.AccountNumber = 'SYN-SGU-A-0020004' AND bl.BL_Amount = 935.90 AND bl.BillType = 1)
              OR (a.AccountNumber = 'SYN-HOS-P-0000001' AND CONVERT(date, bl.BL_PeriodStart) = '2025-03-01' AND bl.BillType = 1) THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
 WHERE bl.DeleteInd = 0 AND bl.BillType <> 0
 ORDER BY a.AccountNumber, bl.BL_PeriodStart;
SELECT SUM(CASE WHEN BillType = 1 THEN 1 ELSE 0 END) AS EstimatedBills, 2 AS ExpectedEstimated, SUM(CASE WHEN BillType = 2 THEN 1 ELSE 0 END) AS AccrualBills,
       CASE WHEN SUM(CASE WHEN BillType = 1 THEN 1 ELSE 0 END) = 2 AND SUM(CASE WHEN BillType NOT IN (0, 1, 2) THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill WHERE DeleteInd = 0;
GO
PRINT '== estimated_then_corrected: SGU Student Center has two bills for 2024-10-15 to 2024-11-14, the estimate (935.90, Bill Type 1) and the correction (885.32, Bill Type 0); there is no refBillID link to expect (nothing in the product writes it) ==';
SELECT bl.BL_BillID, bl.BL_Amount, bl.BillType, bl.refBillID, bl.BL_InvoiceNumber,
       CASE WHEN bl.BL_Amount = 935.90 AND bl.BillType = 1 THEN 'PASS (estimate)'
            WHEN bl.BL_Amount = 885.32 AND bl.BillType = 0 THEN 'PASS (correction)' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
 WHERE a.AccountNumber = 'SYN-SGU-A-0020004' AND CONVERT(date, bl.BL_PeriodEnd) = '2024-11-14' AND bl.DeleteInd = 0
 ORDER BY bl.BL_BillID;
GO
PRINT '== meter_replacement_continuity: the Library''s Sep-24 bill (2024-08-05 to 2024-09-04, 5114.37) carries items on both meters, each with its own period and energy: SYN-VED-M-0040003 (old) 2024-08-05 to 2024-08-14, 5160 kWh, and SYN-VED-M-0040103 (new) 2024-08-15 to 2024-09-04, 10800 kWh; the periods meet with no gap and no overlap ==';
SELECT mt.SM_Code AS Meter, CONVERT(date, MIN(bi.BI_PeriodStart)) AS ItemStart, CONVERT(date, MAX(bi.BI_PeriodEnd)) AS ItemEnd,
       SUM(CASE WHEN u.UT_UnitClassID = 3 THEN bi.BI_Quantity ELSE 0 END) AS EnergyQuantity,
       CASE mt.SM_Code WHEN 'SYN-VED-M-0040003' THEN 5160 WHEN 'SYN-VED-M-0040103' THEN 10800 END AS ExpectedEnergy,
       CASE WHEN mt.SM_Code = 'SYN-VED-M-0040003' AND SUM(CASE WHEN u.UT_UnitClassID = 3 THEN bi.BI_Quantity ELSE 0 END) = 5160
                 AND CONVERT(date, MIN(bi.BI_PeriodStart)) = '2024-08-05' AND CONVERT(date, MAX(bi.BI_PeriodEnd)) = '2024-08-14' THEN 'PASS'
            WHEN mt.SM_Code = 'SYN-VED-M-0040103' AND SUM(CASE WHEN u.UT_UnitClassID = 3 THEN bi.BI_Quantity ELSE 0 END) = 10800
                 AND CONVERT(date, MIN(bi.BI_PeriodStart)) = '2024-08-15' AND CONVERT(date, MAX(bi.BI_PeriodEnd)) = '2024-09-04' THEN 'PASS'
            ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
  JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
  JOIN dbo.Meter mt ON mt.MetaWorldID = bi.MetaWorldID
  LEFT JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID
  LEFT JOIN dbo.Unit u ON u.UN_UnitID = c.UN_UnitID
 WHERE a.AccountNumber = 'SYN-VED-A-0010003' AND CONVERT(date, bl.BL_PeriodEnd) = '2024-09-04' AND bl.DeleteInd = 0
 GROUP BY mt.SM_Code
 ORDER BY ItemStart;
GO
PRINT '== late_bill_present: SGU Library''s last bill ends 2025-11-14 while its peers end 2025-12-14 (fixed dates, not GETDATE(): rp_LateBills compares with the as-of date) ==';
SELECT a.AccountNumber, CONVERT(date, MAX(bl.BL_PeriodEnd)) AS LastBillPeriodEnd,
       CASE a.AccountNumber WHEN 'SYN-SGU-A-0020003' THEN '2025-11-14' ELSE '2025-12-14' END AS Expected,
       CASE WHEN CONVERT(varchar(10), MAX(bl.BL_PeriodEnd), 23) = (CASE a.AccountNumber WHEN 'SYN-SGU-A-0020003' THEN '2025-11-14' ELSE '2025-12-14' END) THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM #Acct a JOIN dbo.Bill bl ON bl.BA_BillingAccountID = a.AccountID AND bl.DeleteInd = 0
 WHERE a.AccountNumber IN ('SYN-SGU-A-0020003', 'SYN-SGU-A-0020001', 'SYN-SGU-A-0020002')
 GROUP BY a.AccountNumber ORDER BY a.AccountNumber;
GO
PRINT '== generator_account_opened_mid_window: SYN-VED-A-0010014 has 17 bills from 2024-07-01 to 2025-12-04, the first running 35 days, none before the acquisition, every total above zero, and the seller''s number SYN-VED-A-0019014 as its previous number ==';
SELECT a.AccountNumber, a.PrevNumber, COUNT(bl.BL_BillID) AS BillCount, CONVERT(date, MIN(bl.BL_PeriodStart)) AS FirstPeriod, CONVERT(date, MAX(bl.BL_PeriodEnd)) AS LastPeriod,
       MAX(CASE WHEN CONVERT(date, bl.BL_PeriodStart) = '2024-07-01' THEN bl.BL_PeriodDays END) AS FirstBillDays,
       SUM(CASE WHEN bl.BL_PeriodStart < '2024-07-01' THEN 1 ELSE 0 END) AS BillsBeforeAcquisition,
       SUM(CASE WHEN bl.BL_Amount <= 0 THEN 1 ELSE 0 END) AS TotalsAtOrBelowZero,
       CASE WHEN COUNT(bl.BL_BillID) = 17 AND CONVERT(date, MIN(bl.BL_PeriodStart)) = '2024-07-01' AND CONVERT(date, MAX(bl.BL_PeriodEnd)) = '2025-12-04'
                 AND MAX(CASE WHEN CONVERT(date, bl.BL_PeriodStart) = '2024-07-01' THEN bl.BL_PeriodDays END) = 35
                 AND SUM(CASE WHEN bl.BL_PeriodStart < '2024-07-01' THEN 1 ELSE 0 END) = 0 AND SUM(CASE WHEN bl.BL_Amount <= 0 THEN 1 ELSE 0 END) = 0
                 AND a.PrevNumber = 'SYN-VED-A-0019014' THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM #Acct a LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = a.AccountID AND bl.DeleteInd = 0
 WHERE a.AccountNumber = 'SYN-VED-A-0010014'
 GROUP BY a.AccountNumber, a.PrevNumber;
GO
PRINT '== bct_credit_counted_once: each generator bill''s credit (SYN-VED-A-0010014, its negative lines) reappears with the sign reversed on the Central Plant bill (SYN-VED-A-0010013) that starts the day after the generator bill ends: 16 pairs, Difference 0.00 on every one (the first, 152792.65, leaves the 2024-07-01 to 2024-08-04 bill and lands on the 2024-08-05 to 2024-09-04 bill); the last generator bill (2025-11-05 to 2025-12-04) has no receiving bill ==';
WITH credit AS (
    SELECT a.AccountNumber AS Account, bl.BL_PeriodStart, bl.BL_PeriodEnd, -SUM(CASE WHEN bi.BI_Amount < 0 THEN bi.BI_Amount ELSE 0 END) AS CreditAmount
      FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
      JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
     WHERE bl.DeleteInd = 0 AND a.AccountNumber IN ('SYN-VED-A-0010014', 'SYN-VED-A-0010013')
     GROUP BY a.AccountNumber, bl.BL_BillID, bl.BL_PeriodStart, bl.BL_PeriodEnd),
pairs AS (
    SELECT g.BL_PeriodStart AS GeneratorPeriodStart, g.BL_PeriodEnd AS GeneratorPeriodEnd, g.CreditAmount AS LeftGeneratorBill,
           c.BL_PeriodStart AS ReceivedPeriodStart, c.CreditAmount AS LandedOnCentralPlantBill, g.CreditAmount - ISNULL(c.CreditAmount, 0) AS Difference
      FROM credit g LEFT JOIN credit c ON c.Account = 'SYN-VED-A-0010013' AND CONVERT(date, c.BL_PeriodStart) = DATEADD(day, 1, CONVERT(date, g.BL_PeriodEnd))
     WHERE g.Account = 'SYN-VED-A-0010014')
SELECT COUNT(*) AS GeneratorBills, SUM(CASE WHEN ReceivedPeriodStart IS NOT NULL THEN 1 ELSE 0 END) AS PairsLanded,
       SUM(CASE WHEN ReceivedPeriodStart IS NOT NULL AND ABS(Difference) > 0.005 THEN 1 ELSE 0 END) AS PairsWithDifference,
       CASE WHEN COUNT(*) = 17 AND SUM(CASE WHEN ReceivedPeriodStart IS NOT NULL THEN 1 ELSE 0 END) = 16
                 AND SUM(CASE WHEN ReceivedPeriodStart IS NOT NULL AND ABS(Difference) > 0.005 THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM pairs;
GO
PRINT '== ridgeline_transfer_not_entered_here: SYN-RWL-G-0000001 has no bills at the end of Stage 5 (EEM generates them in Stage 7); once generated it has 18 and its 2024-07 total is 129330.27 ==';
SELECT a.AccountNumber, COUNT(bl.BL_BillID) AS BillCount, MAX(CASE WHEN CONVERT(date, bl.BL_PeriodStart) = '2024-07-01' THEN bl.BL_Amount END) AS July2024Total,
       CASE WHEN COUNT(bl.BL_BillID) = 0 THEN 'PASS (none yet)'
            WHEN COUNT(bl.BL_BillID) = 18 AND ABS(ISNULL(MAX(CASE WHEN CONVERT(date, bl.BL_PeriodStart) = '2024-07-01' THEN bl.BL_Amount END), 0) - 129330.27) <= 0.01 THEN 'PASS (Stage 7 done)'
            ELSE 'FAIL' END AS Result
  FROM #Acct a LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = a.AccountID AND bl.DeleteInd = 0
 WHERE a.AccountNumber = 'SYN-RWL-G-0000001'
 GROUP BY a.AccountNumber;
GO
PRINT '== thermal_plant_not_entered_here: the six Bill Allocation cost centers (SYN-NTP-C-0000001 to 0000006) are Bill Allocation accounts and hold no bill from Stage 5 (0), or 24 each once Stage 7 has allocated ==';
SELECT a.AccountNumber, a.EntryType, COUNT(bl.BL_BillID) AS BillCount,
       CASE WHEN a.EntryType <> 3 THEN 'FAIL (not Bill Allocation)' WHEN COUNT(bl.BL_BillID) IN (0, 24) THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM #Acct a LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = a.AccountID AND bl.DeleteInd = 0
 WHERE a.AccountNumber LIKE 'SYN-NTP-C-%'
 GROUP BY a.AccountNumber, a.EntryType ORDER BY a.AccountNumber;
GO
PRINT '== fiscal_period_rejection_logged: the sample file keyed with its year transposed (fiscal 2052 for 2025) was uploaded, imported no bill and has verification rows (the Fiscal Year and Fiscal Period checks, two rows at least) ==';
SELECT f.FileName, f.NumberOfBills, f.ImportedBills, COUNT(v.BillImportPro_FileDataVerificationID) AS VerificationRows,
       CASE WHEN f.ImportedBills = 0 AND COUNT(v.BillImportPro_FileDataVerificationID) >= 2 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.BillImportPro_File f LEFT JOIN dbo.BillImportPro_FileData d ON d.BipFileID = f.BipFileID
  LEFT JOIN dbo.BillImportPro_FileDataVerification v ON v.BIPFileDataID = d.BIPFileDataID
 WHERE f.FileName LIKE '%fiscal-period-rejection%'
 GROUP BY f.BipFileID, f.FileName, f.NumberOfBills, f.ImportedBills;
GO
PRINT '== duplicate_file_import: River City Admin Hall (SYN-RCU-A-0030001) has ONE bill for August 2024 after the campus file was imported twice ==';
SELECT a.AccountNumber, COUNT(bl.BL_BillID) AS AugustBills, CASE WHEN COUNT(bl.BL_BillID) = 1 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM #Acct a LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = a.AccountID AND bl.DeleteInd = 0 AND CONVERT(date, bl.BL_PeriodStart) = '2024-08-01'
 WHERE a.AccountNumber = 'SYN-RCU-A-0030001' GROUP BY a.AccountNumber;
GO
PRINT '== account_number_change: Cedar Row A (SYN-RCU-A-0030003) keeps SYN-RCU-A-0030103 as its previous number and has one 2024-08-15 to 2024-09-14 bill of 1984.50 under the new number ==';
SELECT a.AccountNumber, a.PrevNumber, COUNT(bl.BL_BillID) AS Bills, MAX(bl.BL_Amount) AS Total,
       CASE WHEN a.PrevNumber = 'SYN-RCU-A-0030103' AND COUNT(bl.BL_BillID) = 1 AND MAX(bl.BL_Amount) = 1984.50 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM #Acct a LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = a.AccountID AND bl.DeleteInd = 0 AND CONVERT(date, bl.BL_PeriodStart) = '2024-08-15'
 WHERE a.AccountNumber = 'SYN-RCU-A-0030003' GROUP BY a.AccountNumber, a.PrevNumber;
GO
PRINT '== rate_step_bill: the Student Center Jan-25 bill (2024-12-05 to 2025-01-04) has 4 lines for service from 2025-01-01 (energy_part_peak, energy_off_peak, demand_charge, facility_charge at the 2025 prices) and 4 for the days before ==';
SELECT SUM(CASE WHEN CONVERT(date, bi.BI_PeriodStart) = '2025-01-01' THEN 1 ELSE 0 END) AS LinesFrom2025_01_01,
       SUM(CASE WHEN CONVERT(date, bi.BI_PeriodEnd) = '2024-12-31' THEN 1 ELSE 0 END) AS LinesTo2024_12_31,
       CASE WHEN SUM(CASE WHEN CONVERT(date, bi.BI_PeriodStart) = '2025-01-01' THEN 1 ELSE 0 END) = 4
             AND SUM(CASE WHEN CONVERT(date, bi.BI_PeriodEnd) = '2024-12-31' THEN 1 ELSE 0 END) = 4 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
 WHERE a.AccountNumber = 'SYN-VED-A-0010004' AND CONVERT(date, bl.BL_PeriodStart) = '2024-12-05' AND bl.DeleteInd = 0;
GO
PRINT '== header_fields_set: every Bill Entry account bill (Sierra Gas and Helios, EntryType 0) has an Invoice Number and a Received Date, and the Helios Student Center Feb-25 bill carries Previous Balance 1310.55, Payment Received 500.00 and Pay Amount 3439.55 ==';
SELECT COUNT(*) AS BillEntryBills, SUM(CASE WHEN ISNULL(bl.BL_InvoiceNumber, '') = '' THEN 1 ELSE 0 END) AS WithoutInvoiceNumber,
       SUM(CASE WHEN bl.BL_ReceivedDate IS NULL THEN 1 ELSE 0 END) AS WithoutReceivedDate,
       CASE WHEN SUM(CASE WHEN ISNULL(bl.BL_InvoiceNumber, '') = '' THEN 1 ELSE 0 END) = 0 AND SUM(CASE WHEN bl.BL_ReceivedDate IS NULL THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID WHERE a.EntryType = 0 AND bl.DeleteInd = 0;
SELECT a.AccountNumber, bl.BL_PastAmount, bl.BL_PmtRecdAmount, bl.BL_PayAmount, bl.BL_Amount,
       CASE WHEN bl.BL_PastAmount = 1310.55 AND bl.BL_PmtRecdAmount = 500.00 AND bl.BL_PayAmount = 3439.55 AND bl.BL_Amount = 3439.55 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
 WHERE a.AccountNumber = 'SYN-HOS-P-0000002' AND CONVERT(date, bl.BL_PeriodStart) = '2025-02-01' AND bl.DeleteInd = 0;
GO
PRINT '== line_fields_set: every Helios bill''s rec_transfer line is Exclude (one excluded line per Helios bill) and every meter on a billed account has a Provider Meter Number (Meter.SM_SerialNumber) ==';
SELECT (SELECT COUNT(*) FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID WHERE a.AccountNumber LIKE 'SYN-HOS-P-%' AND bl.DeleteInd = 0) AS HeliosBills,
       (SELECT COUNT(*) FROM dbo.BillItem bi JOIN dbo.Bill bl ON bl.BL_BillID = bi.BL_BillID JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
         WHERE a.AccountNumber LIKE 'SYN-HOS-P-%' AND bl.DeleteInd = 0 AND bi.DeleteInd = 0 AND bi.BI_Exclude = 1) AS ExcludedLines,
       (SELECT COUNT(*) FROM dbo.Meter m JOIN #Acct a ON a.AccountID = m.BA_BillingAccountID WHERE ISNULL(m.SM_SerialNumber, '') = '') AS MetersWithoutProviderNumber,
       CASE WHEN (SELECT COUNT(*) FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID WHERE a.AccountNumber LIKE 'SYN-HOS-P-%' AND bl.DeleteInd = 0)
               = (SELECT COUNT(*) FROM dbo.BillItem bi JOIN dbo.Bill bl ON bl.BL_BillID = bi.BL_BillID JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
                   WHERE a.AccountNumber LIKE 'SYN-HOS-P-%' AND bl.DeleteInd = 0 AND bi.DeleteInd = 0 AND bi.BI_Exclude = 1)
             AND (SELECT COUNT(*) FROM dbo.Meter m JOIN #Acct a ON a.AccountID = m.BA_BillingAccountID WHERE ISNULL(m.SM_SerialNumber, '') = '') = 0 THEN 'PASS' ELSE 'FAIL' END AS Result;
GO
PRINT '== entered_by: the user who saved or imported each bill (StatusHistory BL 1) is nora.chen for Valley Electric and River City in every company, iris.morales for Sierra Gas and Helios outside Cedar Row, marcus.reed for Cedar Row''s Sierra Gas and Helios accounts. Result counts bills whose user is NOT the expected one ==';
WITH first_status AS (SELECT sh.SH_TableRowID AS BillID, MIN(sh.LastChangedBy) AS EnteredBy FROM dbo.StatusHistory sh WHERE sh.Table_Code = 'BL' AND sh.Status_Code = 1 GROUP BY sh.SH_TableRowID),
bills AS (
    SELECT a.AccountNumber, bl.BL_BillID, f.EnteredBy,
           CASE WHEN a.AccountNumber LIKE 'SYN-VED-A-%' OR a.AccountNumber LIKE 'SYN-RCU-A-%' THEN 'nora.chen'
                WHEN a.AccountNumber IN ('SYN-SGU-A-0020007', 'SYN-SGU-A-0020008', 'SYN-SGU-A-0020009', 'SYN-HOS-P-0000003') THEN 'marcus.reed'
                WHEN a.AccountNumber LIKE 'SYN-SGU-A-%' OR a.AccountNumber LIKE 'SYN-HOS-P-%' THEN 'iris.morales' END AS ExpectedUser
      FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID LEFT JOIN first_status f ON f.BillID = bl.BL_BillID WHERE bl.DeleteInd = 0)
SELECT ExpectedUser, COUNT(*) AS Bills, SUM(CASE WHEN EnteredBy LIKE '%' + ExpectedUser + '%' THEN 0 ELSE 1 END) AS WrongUser,
       CASE WHEN SUM(CASE WHEN EnteredBy LIKE '%' + ExpectedUser + '%' THEN 0 ELSE 1 END) = 0 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM bills WHERE ExpectedUser IS NOT NULL GROUP BY ExpectedUser ORDER BY ExpectedUser;
GO
PRINT '== approvals_by_role: after the validation job has run, no bill with a finding in BillValidation_Tbl is at Status_Code 2, no QC Approval row was written by iris.morales (a bill-entry-only user), and the SGU Student Center estimate is back at Status_Code 1 ==';
SELECT (SELECT COUNT(*) FROM dbo.Bill bl WHERE bl.DeleteInd = 0 AND bl.Status_Code = 2 AND EXISTS (SELECT 1 FROM dbo.BillValidation_Tbl t WHERE t.BillID = bl.BL_BillID AND t.IsError = 0)) AS ApprovedWithAFinding,
       (SELECT COUNT(*) FROM dbo.StatusHistory sh WHERE sh.Table_Code = 'BL' AND sh.Status_Code = 2 AND sh.LastChangedBy LIKE '%iris.morales%') AS QcRowsByIris,
       (SELECT COUNT(*) FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
         WHERE a.AccountNumber = 'SYN-SGU-A-0020004' AND bl.BL_Amount = 935.90 AND bl.DeleteInd = 0 AND ISNULL(bl.Status_Code, 1) = 1) AS EstimateBackAtStatus1,
       CASE WHEN (SELECT COUNT(*) FROM dbo.Bill bl WHERE bl.DeleteInd = 0 AND bl.Status_Code = 2 AND EXISTS (SELECT 1 FROM dbo.BillValidation_Tbl t WHERE t.BillID = bl.BL_BillID AND t.IsError = 0)) = 0
             AND (SELECT COUNT(*) FROM dbo.StatusHistory sh WHERE sh.Table_Code = 'BL' AND sh.Status_Code = 2 AND sh.LastChangedBy LIKE '%iris.morales%') = 0
             AND (SELECT COUNT(*) FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
                   WHERE a.AccountNumber = 'SYN-SGU-A-0020004' AND bl.BL_Amount = 935.90 AND bl.DeleteInd = 0 AND ISNULL(bl.Status_Code, 1) = 1) = 1 THEN 'PASS' ELSE 'FAIL' END AS Result;
SELECT sh.LastChangedBy, COUNT(*) AS QcApprovalRows FROM dbo.StatusHistory sh WHERE sh.Table_Code = 'BL' AND sh.Status_Code = 2 GROUP BY sh.LastChangedBy ORDER BY COUNT(*) DESC;
GO
PRINT '== images_attached: 19 of the 24 sample PDFs are attached to bills in this stage (7 Valley Electric, 4 Sierra Gas, 4 River City, 4 Helios); the 4 Thermal Plant ones and the Ridgeline statement wait for Stage 7 (24 in all) ==';
SELECT COUNT(DISTINCT i.IM_TableRowID) AS BillsWithAnImage, 19 AS ExpectedAfterStage5, 24 AS ExpectedAfterStage7,
       CASE WHEN COUNT(DISTINCT i.IM_TableRowID) IN (19, 24) THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Images_tbl i JOIN dbo.Bill bl ON bl.BL_BillID = i.IM_TableRowID WHERE i.Table_Code = 'BL' AND bl.DeleteInd = 0;
GO
PRINT '== notes_present: the five seeded notes exist (METR 2, BL 1, BA 2: the second BA note on the Ridgeline generator account); Stage 2''s account notes share the table, so BA may be higher ==';
SELECT Table_Code, COUNT(*) AS Notes,
       CASE Table_Code WHEN 'METR' THEN 2 WHEN 'BL' THEN 1 WHEN 'BA' THEN 2 END AS AtLeast,
       CASE WHEN COUNT(*) >= CASE Table_Code WHEN 'METR' THEN 2 WHEN 'BL' THEN 1 WHEN 'BA' THEN 2 END THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.NoteHistory_Tbl WHERE Table_Code IN ('METR', 'BL', 'BA') GROUP BY Table_Code ORDER BY Table_Code;
GO
PRINT '== validation_fixture_bay_clean: after F01 to F20 are read and deleted, Lakeview Hall gas (SYN-SGU-A-0020005) has no live bill dated 2026 or later, and still its 24 bills ==';
SELECT SUM(CASE WHEN bl.BL_PeriodStart >= '2026-01-01' THEN 1 ELSE 0 END) AS LiveFixtureBills, COUNT(*) AS LiveBills,
       CASE WHEN SUM(CASE WHEN bl.BL_PeriodStart >= '2026-01-01' THEN 1 ELSE 0 END) = 0 AND COUNT(*) = 24 THEN 'PASS' ELSE 'FAIL' END AS Result
  FROM dbo.Bill bl JOIN #Acct a ON a.AccountID = bl.BA_BillingAccountID
 WHERE a.AccountNumber = 'SYN-SGU-A-0020005' AND bl.DeleteInd = 0;
GO
DROP TABLE #Acct;
