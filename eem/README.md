# EEM Setup Manifests

This folder translates the customer/source manifests into EEM application setup
targets.

- `northlake-eem-stage1-setup-v1.yaml` is the DBAdmin-driven Stage 1 setup
  plan for companies, definitions, contacts, levels, groups, and users.
- `northlake-eem-metaworld-stage1b-v1.yaml` is the DBAdmin-driven Stage 1B
  setup target for hierarchy completion, utility setup, billing account shells,
  meter nodes, point nodes, weather station assignments, aggregates, and
  baseline shells.
- `northlake-rates-v1.yaml` is the Phase 2 **Rate Modeler entry plan**: the rate
  library to build by hand in the WPF Rate Modeler (shared TOU/season/holiday
  schedules + scripts, then ~10 rate schedules at determinant level firing all 9
  determinant kinds), with meter assignments and Track-B dependency flags. Numeric
  tariffs stay sourced from `providers/`.
- The remaining **Track A materialize** entry plans (what to enter, on which
  screen, with values) — one per phase, all referencing
  `docs/dream-customer/` specs and flagging Track-B gaps:
  - `northlake-bill-entry-v1.yaml` — Phase 1: bills + charge lines, status history,
    digital points, notes/images (Bill Entry / Bill Importer).
  - `northlake-ap-gl-v1.yaml` — Phase 3: GL chart, account upload flags, validation
    rules, AP approval/upload run (2 built-in formats).
  - `northlake-town-center-v1.yaml` — Phase 4: new mixed-use company/site + Cedar
    Row sub-metering, all 7 allocation methods, WUI families, bill-gen, reconciliation.
  - `northlake-sustainability-v1.yaml` — Phase 5: GHG config, ENERGY STAR setup +
    requests (scores via sandbox PM), weather regression run.
  - `northlake-operations-v1.yaml` — Phase 6: projects, alarms, tasks/workflows, MFR
    delivery to 100+ (via groups), handheld, importers.
- `northlake-eem-permissions-v1.yaml` is the Phase 0 (foundation) concrete
  permission-grant spec: it realizes the 16 semantic permission profiles from
  `security/northlake-eem-security-v1.yaml` against the real EEMSuite permission
  surfaces (`Permissions_TBL`+`SiEAppObjects`, `MetaWorldPermissions_TBL` for
  node scope, `GuiPermissions` for reports), with a building-subset node-scope
  fixture and AccessLevel-3 approver vs AccessLevel-1 viewer cases.
- `northlake-company-calendar-v1.yaml` is the Phase 0 (foundation) fiscal
  calendar (EEMSuite `CompanyCalendar`) for every company across the V1 data
  span, including the deliberate `fiscal_period_not_found` import-rejection
  fixture. Required before bills load. See `docs/dream-customer/`.
- Bill records, interval archive rows, gateway runtime objects, workflows, and
  task schedules belong to later stage manifests.

The source customer workbook is still customer-facing. These files are
EEM-facing and can include EEM concepts such as `CompanyID = -1`, archive
interval, alarm default colors, and DBAdmin section names.
