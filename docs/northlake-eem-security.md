# Northlake EEM Security Setup

This document defines the fake EEM users for Northlake Stage 1 setup. It is not
customer intake data. It is an EEM app setup target used to prove that a blank
seed database can be configured through the product before task setup or fake
data consumption begins.

The machine-readable version is
[`security/northlake-eem-security-v1.yaml`](../security/northlake-eem-security-v1.yaml).

## Scope

Stage 1 covers the blank pre-go-live system:

- Created companies plus the built-in system company context.
- Groups.
- Users.
- Permission intent.
- Company-scoped access.
- Disabled-user and read-only-user regression cases.

Stage 1 does not cover bills, interval archives, gateway execution, workflow
schedules, or task run history. Those belong to later stages.

## Model

The intended shape is:

```text
company -> group -> user
```

For implementation/support access, `CompanyID = -1` is the EEM system company.
That context already exists and should not be created as a Northlake customer
company.

Permissions are attached to groups through semantic permission profiles. The
manifest intentionally does not use exact EEM permission IDs yet. When we drive
the actual app, each semantic profile can be mapped to the concrete permission
rows, screens, or roles that EEM exposes.

No user receives direct permissions in the manifest. That keeps security checks
predictable: a user has access because they are in a group, and a group has
access because it carries one or more permission profiles.

## Company Contexts

| Company/context | Type | Create in DBAdmin? | Why it exists |
| --- | --- | --- |
| System (`CompanyID = -1`) | Built-in EEM system context | No | Owns DB/admin/setup, implementation, gateway-prep, and support read-only users. |
| Northlake University | Campus operations company | Yes | Owns the main campus setup, campus utility setup, broad reporting, and central finance roles. It does not duplicate Cedar Row hierarchy or meters. |
| Cedar Row Apartments | Operating company | Yes | Tests a smaller scoped company with its own admin, bill entry, bill import, reports, and audit access. |
| Northlake Thermal Plant | Internal service company | Yes | Tests internal service-provider behavior for chilled-water and steam allocations, including Library steam and central-plant controller points. |

## Permission Profiles

The manifest defines these profiles:

| Profile | Purpose |
| --- | --- |
| `company_admin` | Manage company settings, groups, users, and company-scoped security. |
| `system_db_admin` | Administer and verify the local/demo EEM database. |
| `company_data_admin` | Maintain company setup data without broad security administration. |
| `hierarchy_setup` | Configure sites, buildings, rollups, accounts, meters, and points. |
| `utility_setup` | Configure commodities, units, providers, utility accounts, and meters. |
| `rates_admin` | Configure tariffs, rate versions, charges, and allocation rates. |
| `bill_entry` | Manually create and edit unposted bills. |
| `bill_import` | Import bill files and review import batches. |
| `report_viewer` | View dashboards, reports, bills, hierarchy, and exports. |
| `sustainability_reporter` | View ENERGY STAR, emissions, solar, and renewable-attribute reporting. |
| `audit_readonly` | Read-only validation across setup, bills, reports, security, and audit history. |
| `plant_operator` | Maintain thermal plant meter metadata and view plant outputs. |
| `thermal_allocation_admin` | Manage internal chilled-water and steam allocation rules. |
| `gateway_task_config_viewer` | View task, gateway, workflow, and point setup without enabling or running anything. |
| `implementation_admin` | Partner setup role for app-driven validation in local/demo environments. |
| `support_readonly` | Partner support role for troubleshooting without changing data. |

## User Coverage

The first pass has 18 users:

| User | Primary company | Coverage |
| --- | --- | --- |
| Samantha Ireland | Northlake University | Customer executive admin and all-property reporting. |
| Jordan Hale | Northlake University | Facilities setup, utility setup, company admin, gateway/task config view. |
| Priya Nandakumar | Northlake University | Rates, utility setup, bill import, and thermal allocation finance. |
| Nora Chen | Northlake University | Shared bill import across Northlake and Cedar Row. |
| Iris Morales | Northlake University | Northlake manual bill entry. |
| Leo Martinez | Northlake University | Sustainability and cross-company reporting. |
| Emerson Fox | Northlake University | Campus data admin and hierarchy setup. |
| Maya Chen | Cedar Row Apartments | Cedar Row company admin, operations, and reports. |
| Marcus Reed | Cedar Row Apartments | Cedar Row manual bill entry. |
| Valerie Kim | Cedar Row Apartments | Housing operations and reports. |
| Devon Brooks | Northlake Thermal Plant | Thermal company admin, operator, and reports. |
| Riley Santos | Northlake Thermal Plant | Thermal plant operator and reports. |
| Keiko Tan | Northlake Thermal Plant | Thermal allocation and rate administration. |
| Quinn Roberts | Northlake University | Cross-company audit read-only. |
| Avery Singh | System (`CompanyID = -1`) | DB admin and implementation admin. |
| Morgan Patel | System (`CompanyID = -1`) | Implementation admin and Stage 2 gateway/task prep view. |
| Taylor Bennett | System (`CompanyID = -1`) | Support read-only. |
| Casey Holt | Northlake University | Disabled former bill-entry user. |

## Validation Cases

This security model is useful because it exercises several permission shapes:

- A campus operations company with broad setup and reporting roles.
- A separate operating company with scoped bill and report roles, without duplicating its hierarchy or meters in the campus company.
- An internal service company with plant operations and allocation setup.
- Built-in system-company DB/admin/support access.
- Shared bill import across companies.
- Cross-company audit read-only access.
- Disabled-user membership that must not allow login.
- Stage 1 gateway/task visibility without task execution.

The expected counts are 3 created companies, 1 built-in system company context,
26 groups, 18 users, 17 active users, and 1 disabled user.
