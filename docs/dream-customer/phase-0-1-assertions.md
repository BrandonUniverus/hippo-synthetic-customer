# Phase 0/1 Assertions (regression checklist)

The known-value checks to run **once the Phase 0/1 specs are loaded** into
EEMSuite. These make Northlake a regression asset, not just a demo. Each maps to
an `expected_assertion` (`schemas/synthetic-source-model.md`). Exact numbers that
depend on generated bill/interval values are expressed as *relationships*
(reconciliations, counts, comparisons) that hold regardless of the generator's
seed; fixed counts are stated outright.

Sources: [bill-charge-line-spec](bill-charge-line-spec.md),
[phase1-substrate-extras](phase1-substrate-extras.md),
`eem/northlake-company-calendar-v1.yaml`, `eem/northlake-eem-permissions-v1.yaml`,
`security/northlake-eem-security-v1.yaml`.

## Phase 0 — foundation

| id | assertion | expected |
| --- | --- | --- |
| `substrate_loads` | A blank EEMSuite seed loads the substrate without error | hierarchy + users + units + calendar present |
| `calendar_count` | `CompanyCalendar` rows per company (CalendarTypeID 1) | 24 each (2024-01…2025-12) |
| `calendar_companies` | companies with a calendar | northlake_university, cedar_row_apartments, northlake_thermal_plant |
| `fiscal_gap_absent` | `CompanyCalendar` for 2026-01 | no row (import-rejection fixture) |
| `import_rejected_no_period` | a bill-import dated 2026-01 | rejected: "Fiscal Year/Period NOT found!" |
| `substrate_reports_render` | rp_BuildingList, rp_PointsList, rp_IndexList, rp_HierarchyDetailsEditor | non-empty |
| `approver_vs_viewer` | bill QC approval | AccessLevel-3 group can approve; bill_entry (2) and report_viewer (1) cannot |
| `node_scope_intra_company` | `nlu_science_center_scope` group visibility | Science Center nodes only |
| `cross_company_isolation` | Cedar Row groups | see only Cedar Row site/buildings |
| `disabled_user_no_auth` | casey.holt | in membership, cannot authenticate |
| `readonly_no_edit` | report_viewer / audit_readonly / support_readonly | no AuthLevel ≥2 on editable objects |
| `security_counts` | groups / users / active | 27 / 19 / 18 |

## Phase 1 — consumption & cost

| id | assertion | expected |
| --- | --- | --- |
| `bill_history_complete` | consecutive monthly bills per active account | ≥24 (2024-01…2025-12), minus deliberate fixtures |
| `charge_lines_sum_to_total` | per bill, non-informational lines | = `total_cost` (±$0.01) |
| `usage_lines_reconcile` | per commodity, consumption-line qty | = bill usage quantity |
| `tou_lines_sum_to_kwh` | VED TOU lines | sum to total kWh; winter bills carry no peak line |
| `tier_blocks_partition_usage` | RCU water tiers | partition total kgal at 50/200 bounds |
| `credit_is_negative` | HOS net_metering_credit / rec_transfer | < 0 / = 0 (informational) |
| `tax_on_subtotal` | utility_users_tax | = tax_rate × sum(preceding lines) |
| `rollup_site_eq_sum_buildings` | site cost/usage rollup | = Σ child building rollups |
| `rollup_customer_eq_sum_sites` | customer rollup | = Σ site rollups |
| `provider_rollup` | per-provider totals | = Σ that provider's account bills |
| `interval_counts` | 15-min channels over the span | full-period count (96/day) minus the deliberate `missing_interval_backfill` gap, restored after backfill |
| `peak_demand_matches` | VED demand line kW | = max 15-min kW in the period for interval buildings |
| `monthly_eui_by_building` | rp_MonthlyEUI | usage ÷ gross floor area, non-null for all 6 buildings |
| `aggregate_campus_kwh` | campus electric aggregate | = Σ member building interval kWh |
| `digital_on_hours` | rp_DigitalSummary | chiller/occupancy/exhaust on-hours per month, non-zero |
| `notes_images_present` | rp_NoteHistory / rp_ImageManagement | seeded notes + bill images returned |
| `late_bill_detected` | rp_LateBills | Sierra Gas Library late fixture present |
| `rate_change_boundary` | VED bills ≥ 2025-01 | use FY2025 rates (higher than 2024) |
| `meter_replacement_continuity` | Library electric across 2024-08-14/15 | no double-count; continuous reads |
| `estimated_then_corrected` | Sierra Gas Student Center | estimate superseded by actual; no double-count |
| `duplicate_import_no_double` | RCU Cedar Row A re-import | no service line double-counted |

## How to use

- Treat the **relationship** assertions (reconciliations, rollup equalities) as
  generator-independent invariants — they must hold for any seed.
- Treat the **fixed-count** assertions (calendar 24, security 27/19/18) as exact.
- As phases 2–6 land, extend this file (rate-engine determinant results, AP file
  contents, tenant allocation reconciliation, GHG totals, etc.).
