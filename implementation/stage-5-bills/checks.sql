-- Stage 5 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
-- Added 2026-10-01 (Ridgeline Wind): generator_account_opened_mid_window, itemized_ridgeline_bills_match,
-- bct_credit_counted_once and ridgeline_transfer_not_entered_here are new; the PRINT texts of validation_rules_set,
-- imports_configured, bills_per_account, images_attached and notes_present carry the new counts.
SET NOCOUNT ON;

PRINT '== validation_rules_set: Global rows for tests 13/14/21/23/25/28/41/42, plus the five account overrides (ScopeType/TestSetID differ from Global once entered; the Ridgeline generator account SYN-VED-A-0010014 holds two of them, tests 21 and 25, both disabled) ==';
SELECT bv.BV_ScopeType, bv.BV_TestSetID, bv.BV_TestID, l.BV_ValidationLabel, bv.BV_IsDisabled, bv.BV_PercentQuantity, bv.BV_AbsQuantity, bv.MT_MeasureTypeID
FROM dbo.BillValidation bv LEFT JOIN dbo.BillValidationLabel l ON l.BV_TestID = bv.BV_TestID AND l.LangID = 1033
WHERE bv.BV_TestID IN (13,14,21,23,25,28,41,42)
ORDER BY bv.BV_ScopeType, bv.BV_TestSetID, bv.BV_TestID;
GO
PRINT '== imports_configured: one BillImportPro_Utility row per imported provider (VED, RCU), each with a mapped CompanyID, and >=1 BillImportPro_AccMeter row per account that provider bills (31 accounts: 14 Valley Electric, the Ridgeline generator account included, and 17 River City) ==';
SELECT u.BIPUtilityProviderID, u.ProviderName_BIF, u.CompanyName_BIF, u.CompanyID, u.AutoMap, COUNT(m.BIPAcctMeterID) AS MappedAccounts
FROM dbo.BillImportPro_Utility u LEFT JOIN dbo.BillImportPro_AccMeter m ON m.BIPUtilityProviderID = u.BIPUtilityProviderID
GROUP BY u.BIPUtilityProviderID, u.ProviderName_BIF, u.CompanyName_BIF, u.CompanyID, u.AutoMap
ORDER BY u.BIPUtilityProviderID;
GO
PRINT '== bills_per_account: 24 bills per account that existed in January 2024 (23 for SGU Library, the late_bill fixture; the Library meter exchange is one bill, Sep-24, with items on both meters); the Ridgeline generator account SYN-VED-A-0010014 has 17 (2024-07-01 to 2025-12-04, posting Aug-24 to Dec-25) and shows its previous number SYN-VED-A-0019014, SYN-RWL-G-0000001 has none until Stage 7 generates its statements, and the RCU Cedar Row A row shows both its previous and current account number ==';
SELECT ba.BA_BillingAccountNumber, ba.BA_PrevBillingAccNumber, COUNT(bl.BL_BillID) AS BillCount, MIN(bl.BL_PeriodStart) AS FirstPeriod, MAX(bl.BL_PeriodEnd) AS LastPeriod
FROM dbo.BillingAccount ba LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = ba.BA_BillingAccountID AND bl.DeleteInd = 0
GROUP BY ba.BA_BillingAccountNumber, ba.BA_PrevBillingAccNumber
ORDER BY ba.BA_BillingAccountNumber;
GO
PRINT '== charge_lines_sum_to_total: per bill, |sum(BI_Amount) - BL_Amount| <= 0.01 (second result set lists any bill that fails this) ==';
SELECT bl.BL_BillID, ba.BA_BillingAccountNumber, bl.BL_PeriodStart, bl.BL_Amount, SUM(bi.BI_Amount) AS LineItemTotal, bl.BL_Amount - SUM(bi.BI_Amount) AS Difference
FROM dbo.Bill bl JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
WHERE bl.DeleteInd = 0
GROUP BY bl.BL_BillID, ba.BA_BillingAccountNumber, bl.BL_PeriodStart, bl.BL_Amount
HAVING ABS(bl.BL_Amount - SUM(bi.BI_Amount)) > 0.01
ORDER BY ba.BA_BillingAccountNumber, bl.BL_PeriodStart;
GO
PRINT '== estimated_then_corrected: SGU Student Center''s Nov-24 period (2024-10-15 to 2024-11-14) shows two bills, the estimated one (935.90, its gas lines estimated) and the corrected one (885.32, refBillID naming the first if the editor offers the link) ==';
SELECT bl.BL_BillID, bl.BL_PeriodStart, bl.BL_PeriodEnd, bl.BL_Amount, bl.refBillID, bi.BI_Quantity, bi.BI_Amount
FROM dbo.Bill bl JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID
WHERE ba.BA_BillingAccountNumber = 'SYN-SGU-A-0020004' AND bl.BL_PeriodEnd = '2024-11-14'
ORDER BY bl.BL_BillID;
GO
PRINT '== meter_replacement_continuity: the Library''s Sep-24 bill (2024-08-05 to 2024-09-04, 5114.37) carries items on both meters, each with its own period: SYN-VED-M-0040003 (old) 2024-08-05 to 2024-08-14, 5160 kWh, and SYN-VED-M-0040103 (new) 2024-08-15 to 2024-09-04, 10800 kWh; the two periods meet with no gap and no overlap ==';
SELECT bl.BL_BillID, bl.BL_PeriodStart, bl.BL_PeriodEnd, bl.BL_Amount, mt.SM_Code AS Meter,
       MIN(bi.BI_PeriodStart) AS ItemStart, MAX(bi.BI_PeriodEnd) AS ItemEnd, SUM(CASE WHEN c.UN_UnitID IS NOT NULL AND u.UT_UnitClassID = 3 THEN bi.BI_Quantity ELSE 0 END) AS EnergyQuantity
FROM dbo.Bill bl JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
JOIN dbo.Meter mt ON mt.MetaWorldID = bi.MetaWorldID
LEFT JOIN dbo.Commodity c ON c.CY_CommodityID = bi.CY_CommodityID
LEFT JOIN dbo.Unit u ON u.UN_UnitID = c.UN_UnitID
WHERE ba.BA_BillingAccountNumber = 'SYN-VED-A-0010003' AND bl.BL_PeriodEnd = '2024-09-04' AND bl.DeleteInd = 0
GROUP BY bl.BL_BillID, bl.BL_PeriodStart, bl.BL_PeriodEnd, bl.BL_Amount, mt.SM_Code
ORDER BY ItemStart;
GO
PRINT '== late_bill_present: SGU Library has no bill for 2025-12 while its peers do (second result set is the account''s last bill date) ==';
SELECT ba.BA_BillingAccountNumber, MAX(bl.BL_PeriodEnd) AS LastBillPeriodEnd, DATEDIFF(day, MAX(bl.BL_PeriodEnd), GETDATE()) AS DaysSinceLastBill
FROM dbo.BillingAccount ba JOIN dbo.Bill bl ON bl.BA_BillingAccountID = ba.BA_BillingAccountID AND bl.DeleteInd = 0
WHERE ba.BA_BillingAccountNumber IN ('SYN-SGU-A-0020003','SYN-SGU-A-0020001','SYN-SGU-A-0020002')
GROUP BY ba.BA_BillingAccountNumber
ORDER BY ba.BA_BillingAccountNumber;
GO
PRINT '== generator_account_opened_mid_window: the Ridgeline generator account SYN-VED-A-0010014 has 17 bills (2024-07-01 to 2025-12-04, posting Aug-24 to Dec-25), the first running 35 days from the opening, none before the acquisition, and every total is positive: the export credit leaves each bill with its bct_credit_transferred line, so a total at or below zero means that line is missing ==';
SELECT ba.BA_BillingAccountNumber, ba.BA_PrevBillingAccNumber, COUNT(bl.BL_BillID) AS BillCount, MIN(bl.BL_PeriodStart) AS FirstPeriod, MAX(bl.BL_PeriodEnd) AS LastPeriod,
       MAX(CASE WHEN bl.BL_PeriodStart = '2024-07-01' THEN bl.BL_PeriodDays END) AS FirstBillDays,
       SUM(CASE WHEN bl.BL_PeriodStart < '2024-07-01' THEN 1 ELSE 0 END) AS BillsBeforeAcquisition,
       SUM(CASE WHEN bl.BL_Amount <= 0 THEN 1 ELSE 0 END) AS TotalsAtOrBelowZero, MIN(bl.BL_Amount) AS SmallestTotal, MAX(bl.BL_Amount) AS LargestTotal
FROM dbo.BillingAccount ba LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = ba.BA_BillingAccountID AND bl.DeleteInd = 0
WHERE ba.BA_BillingAccountNumber = 'SYN-VED-A-0010014'
GROUP BY ba.BA_BillingAccountNumber, ba.BA_PrevBillingAccNumber;
GO
PRINT '== itemized_ridgeline_bills_match: the three itemized Valley Electric bills carry the totals their PDFs print (generator 2024-07-01 to 2024-08-04 1077.45, generator 2025-01-05 to 2025-02-04 6753.10, Central Plant 2024-08-05 to 2024-09-04 151171.47); Difference is 0.00 on every row ==';
SELECT x.Account, x.PeriodStart, x.Expected, bl.BL_Amount, bl.BL_Amount - x.Expected AS Difference
FROM (VALUES ('SYN-VED-A-0010014', CONVERT(date, '2024-07-01'), CONVERT(money, 1077.45)),
             ('SYN-VED-A-0010014', CONVERT(date, '2025-01-05'), CONVERT(money, 6753.10)),
             ('SYN-VED-A-0010013', CONVERT(date, '2024-08-05'), CONVERT(money, 151171.47))) AS x(Account, PeriodStart, Expected)
LEFT JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountNumber = x.Account
LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = ba.BA_BillingAccountID AND bl.BL_PeriodStart = x.PeriodStart AND bl.DeleteInd = 0
ORDER BY x.Account, x.PeriodStart;
GO
PRINT '== bct_credit_counted_once: each generator bill''s credit (SYN-VED-A-0010014, its negative lines) reappears with the sign reversed on the Central Plant bill (SYN-VED-A-0010013) one billing cycle later, the bill that starts the day after the generator bill ends: 16 pairs with Difference 0.00 (the first, 152792.65, leaves the 2024-07-01 to 2024-08-04 bill and lands on the 2024-08-05 to 2024-09-04 bill), and the last generator bill (2025-11-05 to 2025-12-04) with no receiving bill, because its Central Plant bill would post to Jan-26, outside the calendar ==';
WITH credit AS (
    SELECT ba.BA_BillingAccountNumber AS Account, bl.BL_PeriodStart, bl.BL_PeriodEnd, -SUM(CASE WHEN bi.BI_Amount < 0 THEN bi.BI_Amount ELSE 0 END) AS CreditAmount
    FROM dbo.Bill bl JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
    JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID AND bi.DeleteInd = 0
    WHERE bl.DeleteInd = 0 AND ba.BA_BillingAccountNumber IN ('SYN-VED-A-0010014', 'SYN-VED-A-0010013')
    GROUP BY ba.BA_BillingAccountNumber, bl.BL_BillID, bl.BL_PeriodStart, bl.BL_PeriodEnd
)
SELECT g.BL_PeriodStart AS GeneratorPeriodStart, g.BL_PeriodEnd AS GeneratorPeriodEnd, g.CreditAmount AS LeftGeneratorBill, c.BL_PeriodStart AS ReceivedPeriodStart, c.CreditAmount AS LandedOnCentralPlantBill,
       g.CreditAmount - ISNULL(c.CreditAmount, 0) AS Difference
FROM credit g LEFT JOIN credit c ON c.Account = 'SYN-VED-A-0010013' AND c.BL_PeriodStart = DATEADD(day, 1, g.BL_PeriodEnd)
WHERE g.Account = 'SYN-VED-A-0010014'
ORDER BY g.BL_PeriodStart;
GO
PRINT '== ridgeline_transfer_not_entered_here: SYN-RWL-G-0000001 has no bills at the end of Stage 5 because EEM generates them in Stage 7; once generated it has 18 and its 2024-07 total equals the hand-made statement, 129330.27 ==';
SELECT ba.BA_BillingAccountNumber, COUNT(bl.BL_BillID) AS BillCount, MAX(CASE WHEN bl.BL_PeriodStart = '2024-07-01' THEN bl.BL_Amount END) AS July2024Total
FROM dbo.BillingAccount ba LEFT JOIN dbo.Bill bl ON bl.BA_BillingAccountID = ba.BA_BillingAccountID AND bl.DeleteInd = 0
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001'
GROUP BY ba.BA_BillingAccountNumber;
GO
PRINT '== fiscal_period_rejection_logged: the sample file keyed with its year transposed (fiscal 2052 for 2025) shows Fiscal Year NOT found! and Fiscal Period NOT found! verification rows and zero imported bills ==';
SELECT f.FileName, f.NumberOfBills, f.ImportedBills, f.ImportStatus, v.VerificationStatus, v.Note
FROM dbo.BillImportPro_File f LEFT JOIN dbo.BillImportPro_FileData d ON d.BIPFileID = f.BipFileID
LEFT JOIN dbo.BillImportPro_FileDataVerification v ON v.BIPFileDataID = d.BIPFileDataID
WHERE f.FileName LIKE '%fiscal-period-rejection%'
ORDER BY f.BipFileID;
GO
PRINT '== approvals_by_role: roughly a third of each account''s bills are Status_Code 2, and every Status_Code 2 row''s LastChangedBy is a company-admin user (see 05-approval.yaml) ==';
SELECT ba.BA_BillingAccountNumber, bl.Status_Code, COUNT(*) AS BillCount, MIN(bl.LastChangedBy) AS SampleLastChangedBy
FROM dbo.Bill bl JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
WHERE bl.DeleteInd = 0
GROUP BY ba.BA_BillingAccountNumber, bl.Status_Code
ORDER BY ba.BA_BillingAccountNumber, bl.Status_Code;
GO
PRINT '== images_attached: every provider but Ridgeline Wind has at least one bill with an attached image (Table_Code BL), 23 images in all; the 24th, the hand-made Ridgeline statement, attaches to the bill EEM generates in Stage 7 ==';
SELECT i.Table_Code, bl.BA_BillingAccountID, COUNT(*) AS ImageCount
FROM dbo.Images i JOIN dbo.Bill bl ON bl.BL_BillID = i.IM_TableRowID AND i.Table_Code = 'BL'
GROUP BY i.Table_Code, bl.BA_BillingAccountID
ORDER BY bl.BA_BillingAccountID;
GO
PRINT '== notes_present: the five seeded notes exist, one per table code target (METR x2, BL x1, BA x2, the second BA note on the Ridgeline generator account); Stage 2''s account notes share the table ==';
SELECT Table_Code, NT_TableRowID, Note FROM dbo.NoteHistory_Tbl WHERE Table_Code IN ('METR','BL','BA') ORDER BY Table_Code, NT_TableRowID;
GO
