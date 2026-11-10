-- Stage 6 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
SET NOCOUNT ON;

PRINT '== gl_chart: 16 rows across 3 companies (NLU 6, Cedar Row 5, Thermal Plant 5, including 5150-WIND, Ridgeline wind energy transfer); Type_Code 1 Expenses / 2 Liabilities ==';
SELECT c.CompanyID, c.CompanyName, g.Type_Code, g.GL_AccountCode, g.GL_Description
FROM dbo.GLAccount g JOIN dbo.Company_TBL c ON c.CompanyID = g.CompanyID
ORDER BY c.CompanyID, g.Type_Code, g.GL_AccountCode;
GO
PRINT '== account_defaults: 51 rows, one per billing account, each with BA_DefApAcctID = the company''s 2000-AP row and a
       BA_DefExpAcctID by provider; Type_Code/BillType_Code match 03-account-gl-defaults.yaml. The Ridgeline pair
       reads SYN-VED-A-0010014 1|1|2000-AP|5100-ELEC and SYN-RWL-G-0000001 2|2|2000-AP|5150-WIND ==';
SELECT ba.BA_BillingAccountNumber, ba.Type_Code AS BillServiceTypeCode, ba.BillType_Code AS BillEntryTypeCode,
       ap.GL_AccountCode AS LiabilityAccount, ex.GL_AccountCode AS DefaultExpenseAccount
FROM dbo.BillingAccount ba
LEFT JOIN dbo.GLAccount ap ON ap.GL_AccountID = ba.BA_DefApAcctID
LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = ba.BA_DefExpAcctID
ORDER BY ba.BA_BillingAccountNumber;
GO
PRINT '== export_formats_registered: expected empty today, both result sets (Stage 6 Finding) - neither
       ExportSetup nor PermissionCatalog TypeKey=EX has rows for export_ap/export_ap2/nl_* in this instance ==';
SELECT ExportName, FileType, StatusCode FROM dbo.ExportSetup ORDER BY ExportName;
SELECT PermissionKey, DescriptionFallback FROM dbo.PermissionCatalog WHERE TypeKey = 'EX' ORDER BY PermissionKey;
GO
PRINT '== ap_files_generated: expected empty today - no ExportSetup row exists to run, so no ExportFile/ExportLog
       rows can exist yet (Stage 6 Finding, 04-ap-export-formats.yaml) ==';
SELECT ExportFileID, ExportDate, ExportFile, ExportShortName FROM dbo.ExportFile ORDER BY ExportFileID;
SELECT ExportLogID, ExportType, BillID, ExportAmount FROM dbo.ExportLog ORDER BY ExportLogID;
GO
PRINT '== blocked_by_validation: bills with an open (unresolved) BillValidation_Tbl alert, and whether each one
       has already been advanced past Status_Code 2 despite the alert (it should not have been) ==';
SELECT bv.BillID, ba.BA_BillingAccountNumber, bl.Status_Code, bv.BillTestID, bv.ShortDesc, bv.BillMessage, bv.IsError
FROM dbo.BillValidation_Tbl bv
JOIN dbo.Bill bl ON bl.BL_BillID = bv.BillID
JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
WHERE bv.IsError = 1
ORDER BY ba.BA_BillingAccountNumber, bv.BillID;
GO
PRINT '== ridgeline_gl_only: SYN-RWL-G-0000001 is GL only (Ridgeline Wind addition), so the first result set must be
       empty - no AP-type ExportLog row (AP, APINV, APDIS) may name one of its bills, today or after Track B; the
       second shows each generated statement coded to 5150-WIND and equal to its bill total (July 2024: 129330.27).
       A generated bill keeps its total to four decimals against cent-rounded lines (product finding 72), so the
       total is compared rounded. The Ridgeline checks read BillingAccount_TBL: the BillingAccount view is scoped
       to the signed-in user and returns no rows to a plain sqlcmd session ==';
SELECT el.ExportLogID, el.ExportType, el.BillID, el.ExportAmount
FROM dbo.ExportLog el
JOIN dbo.Bill bl ON bl.BL_BillID = el.BillID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001' AND el.ExportType LIKE 'AP%'
ORDER BY el.ExportLogID;
SELECT bl.BL_BillID, CONVERT(char(10), bl.BL_PeriodStart, 120) AS PeriodStart, ROUND(bl.BL_Amount, 2) AS BillAmount,
       ex.GL_AccountCode AS ExpenseAccount, SUM(bi.BI_Amount) AS CodedAmount
FROM dbo.Bill bl
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID
LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = COALESCE(bi.BI_EXpAcctID, ba.BA_DefExpAcctID)
WHERE ba.BA_BillingAccountNumber = 'SYN-RWL-G-0000001'
GROUP BY bl.BL_BillID, bl.BL_PeriodStart, ROUND(bl.BL_Amount, 2), ex.GL_AccountCode
ORDER BY bl.BL_PeriodStart;
GO
PRINT '== ridgeline_bct_coded_once: the first bill credit transfer (152792.65) is coded once, where it lands. Three
       lines expected: SYN-VED-A-0010014 first bill (2024-07-01..2024-08-04) generation credit -152792.65 and
       transferred +152792.65 (net 0.00), SYN-VED-A-0010013 September 2024 bill (2024-08-05..2024-09-04) received
       -152792.65 coded 5100-ELEC; NetCredit must be -152792.65 ==';
SELECT ba.BA_BillingAccountNumber, bl.BL_BillID, CONVERT(char(10), bl.BL_PeriodStart, 120) AS PeriodStart,
       bi.BI_Seq, bi.BI_Amount, ex.GL_AccountCode AS ExpenseAccount
FROM dbo.BillItem bi
JOIN dbo.Bill bl ON bl.BL_BillID = bi.BL_BillID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
LEFT JOIN dbo.GLAccount ex ON ex.GL_AccountID = COALESCE(bi.BI_EXpAcctID, ba.BA_DefExpAcctID)
WHERE ba.BA_BillingAccountNumber IN ('SYN-VED-A-0010014', 'SYN-VED-A-0010013') AND ABS(bi.BI_Amount) = 152792.65
ORDER BY bl.BL_PeriodStart, ba.BA_BillingAccountNumber, bi.BI_Seq;
SELECT SUM(bi.BI_Amount) AS NetCredit
FROM dbo.BillItem bi
JOIN dbo.Bill bl ON bl.BL_BillID = bi.BL_BillID
JOIN dbo.BillingAccount_TBL ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
WHERE ba.BA_BillingAccountNumber IN ('SYN-VED-A-0010014', 'SYN-VED-A-0010013') AND ABS(bi.BI_Amount) = 152792.65;
GO
PRINT '== accrual_pair: SysConstants MPA Accruals/Reversals resolve to real Commodity rows; dbo.Accrual_Bill does
       NOT exist in this instance (Stage 6 Finding - second result set proves it, third confirms BillAccrualMap
       does exist); open-accrual bill line on the Accruals commodity, no reversal pair possible yet ==';
SELECT sc.Item, sc.Value_I, cy.CY_CommodityName, cy.CompanyID
FROM dbo.SysConstants sc LEFT JOIN dbo.Commodity cy ON cy.CY_CommodityID = sc.Value_I
WHERE sc.Item IN ('MPA Accruals','MPA Reversals');
SELECT COUNT(*) AS AccrualBillTableExists FROM sys.tables WHERE name = 'Accrual_Bill';
SELECT COUNT(*) AS BillAccrualMapTableExists FROM sys.tables WHERE name = 'BillAccrualMap';
SELECT bl.BL_BillID, ba.BA_BillingAccountNumber, bi.CY_CommodityID, bi.BI_Amount
FROM dbo.Bill bl
JOIN dbo.BillingAccount ba ON ba.BA_BillingAccountID = bl.BA_BillingAccountID
JOIN dbo.BillItem bi ON bi.BL_BillID = bl.BL_BillID
JOIN dbo.SysConstants sc ON sc.Item = 'MPA Accruals' AND sc.Value_I = bi.CY_CommodityID
ORDER BY bl.BL_BillID;
GO
