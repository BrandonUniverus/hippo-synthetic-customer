# Northlake group reconciliation before remaining user entry

Read-only snapshot: `EEMSuite_Northlake` on server `.`, 2026-09-23T21:43:34.1241176 UTC (2026-09-23 Pacific). The database was not changed. This checklist compares live effective grants with [04-groups.yaml](04-groups.yaml); it is not a manual application test.

The target is 20 shared Common masters (11 capability/system groups and nine company Points groups), plus six local groups. A shared Points copy keeps its target company and node path. All user memberships remain in the home company.

Of the 26 definitions, 16 already exist: **9 need a correction and 7 already match**. Create ten Common masters and retire ten old local groups. Their automatic copies bring the target to 86 recipe-owned group rows. The six existing default/bootstrap rows are separate.

## 1. Correct the existing groups

Keep `eem_system_db_admins`, `eem_implementation_admins`, and `eem_support_readonly` **Shared=true**. The previous instruction to turn sharing off is obsolete. Edit each Common master once; its attached copies synchronize.

| Company | Group | Required correction |
|---|---|---|
| Common | `eem_system_db_admins` | Add `A / AccessManagementTab` at 3. Add `A / CommodityTab` at 3. Add `A / UnitsTab` at 3. Add `F / Bulk Data Entry` at 1. Add `F / ImpersonateUser` at 3. Add `F / System Administration` at 3. Add Points / all companies (`MetaCompanyID=NULL`, key `*`) at 3. |
| Common | `eem_implementation_admins` | Add Points / all companies (`MetaCompanyID=NULL`, key `*`) at 3. Remove unlisted `G:21 / alarms` at 1. Remove unlisted `G:21 / baseline_perf` at 1. Remove unlisted `G:21 / billmeter_rec` at 1. Remove unlisted `G:21 / utility_accountant` at 1. |
| Common | `eem_support_readonly` | Add Points / all companies (`MetaCompanyID=NULL`, key `*`) at 1. |
| Common | `eem_company_setup` | Set `F / Bill Validation` from 3 to 1. Remove unlisted `configuration / migrations` at 3. |
| Common | `eem_reports` | Set Name to **EEM Billing and Usage Reports**. |
| Northlake University | `nlu_database_admins` | Set `F / Bulk Data Entry` from 3 to 1. |
| Northlake University | `nlu_facilities_setup` | Set `A / CommodityTab` from 3 to 1. Set `A / UnitsTab` from 3 to 1. |
| Cedar Row Apartments | `cra_housing_ops` | Remove unlisted Points / Cedar Row Apartments (`MetaCompanyID=3`, key `*`) at 2. |
| Northlake Thermal Plant | `ntp_plant_ops` | Add `G:17 / All` at level 1 (15 current reports). Add `G:21 / use_analysis` at 1. |

Already matching definitions: `eem_bill_entry`, `eem_bill_import`, `eem_sustainability_reports`, `eem_audit_readonly`, `eem_gateway_reports`, `nlu_utility_setup`, `nlu_science_center_scope`.

The live catalog has replaced `UsersTab` and `GroupsTab` with `AccessManagementTab`. The YAML now uses that key; the existing company-setup and audit copies already contain it. Avery additionally needs its explicit level-3 grant in `eem_system_db_admins` to manage access.

## 2. Create the ten missing Common masters

Create these under Common/System with **Shared=true**. The new IDs avoid collisions with the existing local Points groups. Save and verify the new copies before removing any old groups.

| Group | Grant |
|---|---|
| `eem_rate_allocations` | Use the exact rate/schedule/allocation module and report grants in 04-groups.yaml. Library-rate keys remain deferred to Stage 4. |
| `eem_nlu_points_read` | Points target **Northlake University**, `MetaCompanyID=6`, key `*`, level **1**. |
| `eem_nlu_points_modify` | Points target **Northlake University**, `MetaCompanyID=6`, key `*`, level **2**. |
| `eem_nlu_points_admin` | Points target **Northlake University**, `MetaCompanyID=6`, key `*`, level **3**. |
| `eem_cra_points_read` | Points target **Cedar Row Apartments**, `MetaCompanyID=3`, key `*`, level **1**. |
| `eem_cra_points_modify` | Points target **Cedar Row Apartments**, `MetaCompanyID=3`, key `*`, level **2**. |
| `eem_cra_points_admin` | Points target **Cedar Row Apartments**, `MetaCompanyID=3`, key `*`, level **3**. |
| `eem_ntp_points_read` | Points target **Northlake Thermal Plant**, `MetaCompanyID=5`, key `*`, level **1**. |
| `eem_ntp_points_modify` | Points target **Northlake Thermal Plant**, `MetaCompanyID=5`, key `*`, level **2**. |
| `eem_ntp_points_admin` | Points target **Northlake Thermal Plant**, `MetaCompanyID=5`, key `*`, level **3**. |

`eem_nlu_points_modify` is currently unassigned; it completes the three-level set. Every company receives the nine scope copies, but copies have no members until explicitly assigned. A Northlake copy of `eem_cra_points_read` still grants Cedar Row (3), not Northlake (6).

## 3. Move the existing memberships, then retire ten local groups

Samantha, Jordan and Priya already exist. Samantha and Jordan are administrators and currently belong to Northlake `nlu_points_admin`; Priya is a non-administrator with no ordinary group memberships. The other 16 planned users are absent.

For **Samantha and Jordan**, add Northlake `eem_nlu_points_admin`, save/reload and verify the level-3 Northlake scope, then remove their old `nlu_points_admin` membership. Keep their other memberships and protected administrator assignment. Finish Priya and the remaining user entries from [05-users.yaml](05-users.yaml) after the groups are reconciled.

| Company | Retire this local group | Replacement shared group | Current members |
|---|---|---|---|
| Northlake University | `nlu_points_read` | `eem_nlu_points_read` | None |
| Northlake University | `nlu_points_admin` | `eem_nlu_points_admin` | `jordan.hale`, `samantha.ireland` |
| Cedar Row Apartments | `cra_points_read` | `eem_cra_points_read` | None |
| Cedar Row Apartments | `cra_points_modify` | `eem_cra_points_modify` | None |
| Cedar Row Apartments | `cra_points_admin` | `eem_cra_points_admin` | None |
| Northlake Thermal Plant | `ntp_points_read` | `eem_ntp_points_read` | None |
| Northlake Thermal Plant | `ntp_points_modify` | `eem_ntp_points_modify` | None |
| Northlake Thermal Plant | `ntp_points_admin` | `eem_ntp_points_admin` | None |
| Northlake University | `nlu_rates_admins` | `eem_rate_allocations` | None |
| Northlake Thermal Plant | `ntp_rates_allocations` | `eem_rate_allocations` | None |

These ten rows are local (`Shared=false`) and non-protected. The snapshot found no saved-report, rate-scenario, hierarchy-filter, report-recipient, notification, custom-link, keyword, node-notification, SCIM-link, federated-link or federated-snapshot references for them. The two memberships above are the only current dependencies found. Recheck immediately before deletion if another task or operator has changed the database.

The former `nlu_cra_points_read`, `nlu_ntp_points_read`, `nlu_ntp_points_modify`, and `ntp_nlu_points_read` groups do not exist in the live database; they have been removed from the recipe and need no deletion.

## 4. Keep these groups and verify before starting the remaining users

- Keep the six local duties/scope groups: `nlu_database_admins`, `nlu_facilities_setup`, `nlu_utility_setup`, `nlu_science_center_scope`, `cra_housing_ops`, and `ntp_plant_ops`. Science Center already has the correct path `0.6.22.24`, target company 6, level 1.
- Keep `all rights` in Common, the three `Public` groups, and the protected System/Company Administrators groups. Common `all rights` currently serves `SiE_Setup` and `Worker`.
- Keep all planned shared copies. Deleting a company copy opts it out of synchronization; deleting a Common shared master deletes its attached shared copies. Neither is part of this local-group retirement list.
- All 30 existing shared company copies match their current masters, and there are no shared-copy opt-outs in this snapshot. After corrections, compare each attached copy again, including `MetaCompanyID`, node key and level.
- Run the read-only `checks.sql`. `groups_missing_or_wrong_sharing`, `shared_grants_match`, `shared_forbidden_grants`, `point_scope_mismatches`, `unexpected_points`, and `replaced_groups_still_present` should return no discrepancy rows after the group work. The full user count is a later step.
- Keep future gateway/task and library-rate permissions deferred at the end of 04-groups.yaml; their concrete keys do not exist yet.

Access Management requires both an administrator role and its explicit permission. Quinn remains `IsAdmin=false`: the audit group grants reports and setup reads, but its AccessManagementTab level-1 row alone does not let Quinn inspect that editor. No administrator elevation has been added to bypass this rule.

Validation: duplicate-key-aware YAML parsing; all group and user references; all 19 IsAdmin values; all nine target/level combinations; current active catalog keys; preserved planned per-user Points scopes and capability grants after mapping the retired Users/Groups keys, with Avery's required Access Management grant added explicitly. Runtime save/reload and action enforcement remain to be exercised after applying the checklist.
