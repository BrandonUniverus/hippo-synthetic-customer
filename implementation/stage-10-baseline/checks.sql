-- Stage 10 checks. Read-only. Run: sqlcmd -S localhost -E -d EEMSuite_Northlake -W -s "|" -i checks.sql
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;

PRINT '== backup_history: the Stage 10 final backup exists in msdb, type D (full), at C:\Hippo\Backups\ ==';
SELECT bs.database_name, bs.backup_start_date, bs.type, bs.is_copy_only, bmf.physical_device_name
FROM msdb.dbo.backupset bs JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id
WHERE bs.database_name = 'EEMSuite_Northlake' ORDER BY bs.backup_start_date DESC;
GO

PRINT '== row_counts_major_tables: every major table across Stages 1-9 has at least one row (0 is a real gap, not a formatting issue) ==';
SELECT 'Company_TBL' AS TableName, COUNT(*) AS Rows FROM dbo.Company_TBL WHERE CompanyID > 0
UNION ALL SELECT 'UtilityProvider', COUNT(*) FROM dbo.UtilityProvider
UNION ALL SELECT 'MetaWorld_TBL (nodes)', COUNT(*) FROM dbo.MetaWorld_TBL WHERE CompanyID > 0 AND ISNULL(DeleteInd,0)=0
UNION ALL SELECT 'Meter', COUNT(*) FROM dbo.Meter
UNION ALL SELECT 'PointDef_TBL', COUNT(*) FROM dbo.PointDef_TBL
UNION ALL SELECT 'BillingAccount', COUNT(*) FROM dbo.BillingAccount WHERE ISNULL(DeleteInd,0)=0
UNION ALL SELECT 'Bill', COUNT(*) FROM dbo.Bill
UNION ALL SELECT 'Users', COUNT(*) FROM dbo.Users
UNION ALL SELECT 'UserGroups', COUNT(*) FROM dbo.UserGroups
UNION ALL SELECT 'EmissionFactorHistory (2024/2025 rows)', COUNT(*) FROM dbo.EmissionFactorHistory WHERE StartDate >= '2024-01-01'
UNION ALL SELECT 'EmissionMeterMap', COUNT(*) FROM dbo.EmissionMeterMap
UNION ALL SELECT 'EmissionCompanyConfig', COUNT(*) FROM dbo.EmissionCompanyConfig
UNION ALL SELECT 'ESFacility', COUNT(*) FROM dbo.ESFacility
UNION ALL SELECT 'ESRequestFacility', COUNT(*) FROM dbo.ESRequestFacility
UNION ALL SELECT 'FF_wnRegressionBestResults', COUNT(*) FROM dbo.FF_wnRegressionBestResults
UNION ALL SELECT 'wh_Benchmark', COUNT(*) FROM dbo.wh_Benchmark
UNION ALL SELECT 'Project', COUNT(*) FROM dbo.Project
UNION ALL SELECT 'AlarmData_TBL', COUNT(*) FROM dbo.AlarmData_TBL
UNION ALL SELECT 'AuditLog', COUNT(*) FROM dbo.AuditLog
UNION ALL SELECT 'UserLogin_Tbl', COUNT(*) FROM dbo.UserLogin_Tbl
UNION ALL SELECT 'GuiReportActivityLog', COUNT(*) FROM dbo.GuiReportActivityLog
UNION ALL SELECT 'TaskItems', COUNT(*) FROM dbo.TaskItems
UNION ALL SELECT 'TaskLog', COUNT(*) FROM dbo.TaskLog
UNION ALL SELECT 'WorkflowRun', COUNT(*) FROM dbo.WorkflowRun
UNION ALL SELECT 'GUIMFRSavedReports', COUNT(*) FROM dbo.GUIMFRSavedReports
UNION ALL SELECT 'GUIMFRDashboards', COUNT(*) FROM dbo.GUIMFRDashboards
UNION ALL SELECT 'MFRDelivery_TBL', COUNT(*) FROM dbo.MFRDelivery_TBL
UNION ALL SELECT 'MFRDeliveryRecipient_TBL', COUNT(*) FROM dbo.MFRDeliveryRecipient_TBL
UNION ALL SELECT 'HMR_Meter', COUNT(*) FROM dbo.HMR_Meter
UNION ALL SELECT 'HMR_Reading', COUNT(*) FROM dbo.HMR_Reading
UNION ALL SELECT 'HMR_Log', COUNT(*) FROM dbo.HMR_Log
UNION ALL SELECT 'EnergyAI_Loads (expect 0, Findings)', COUNT(*) FROM dbo.EnergyAI_Loads
ORDER BY TableName;
GO

PRINT '== report_matrix_nonempty: proxy queries per report bucket, standing in for opening all 115 reports; every row here should be non-zero once Stages 1-9 are entered ==';
SELECT 'GHG (EmissionMeterMap assigned)' AS ReportBucket, COUNT(*) AS NonEmptyRows FROM dbo.EmissionMeterMap
UNION ALL SELECT 'ENERGY STAR (ESFacility mapped)', COUNT(*) FROM dbo.ESFacility
UNION ALL SELECT 'Weather regression (FF_wnRegressionBestResults)', COUNT(*) FROM dbo.FF_wnRegressionBestResults
UNION ALL SELECT 'Benchmarks (wh_Benchmark, built-in)', COUNT(*) FROM dbo.wh_Benchmark
UNION ALL SELECT 'Projects (Project)', COUNT(*) FROM dbo.Project
UNION ALL SELECT 'Alarms (AlarmData_TBL)', COUNT(*) FROM dbo.AlarmData_TBL
UNION ALL SELECT 'Audit (AuditLog)', COUNT(*) FROM dbo.AuditLog
UNION ALL SELECT 'Activity (UserLogin_Tbl + GuiReportActivityLog)', (SELECT COUNT(*) FROM dbo.UserLogin_Tbl) + (SELECT COUNT(*) FROM dbo.GuiReportActivityLog)
UNION ALL SELECT 'Tasks/Gateway (TaskLog + WorkflowRun)', (SELECT COUNT(*) FROM dbo.TaskLog) + (SELECT COUNT(*) FROM dbo.WorkflowRun)
UNION ALL SELECT 'MFR saved reports + dashboards', (SELECT COUNT(*) FROM dbo.GUIMFRSavedReports) + (SELECT COUNT(*) FROM dbo.GUIMFRDashboards)
UNION ALL SELECT 'MFR delivery recipients resolved', (SELECT COUNT(*) FROM dbo.MFRDeliveryRecipient_TBL)
UNION ALL SELECT 'HMR configuration (HMR_Reading)', COUNT(*) FROM dbo.HMR_Reading
UNION ALL SELECT 'HMR collected history (configured points)', COUNT(*) FROM dbo.AnalogArchive_TBL a
    WHERE EXISTS (SELECT 1 FROM dbo.HMR_Reading r WHERE a.PtID IN (r.Ptid_Reading,r.Ptid_Usage))
UNION ALL SELECT 'MyImports (MyImportExport_Tbl, verified table)', COUNT(*) FROM dbo.MyImportExport_Tbl
ORDER BY ReportBucket;
GO
