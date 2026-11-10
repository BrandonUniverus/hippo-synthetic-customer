---
title: Northlake Roadmap
subtitle: What each stage builds, what it unlocks, and where coverage stands
document_type: Implementation plan
---

# Northlake Roadmap

The goal is a complete, deterministic synthetic customer that exercises every
part of EEMSuite: every report, every rate construct, the AP and GL interface,
tenant rebilling with every allocation and reconciliation method, GHG, ENERGY
STAR, baselines and regression, projects, alarms, tasks and workflows,
importers, and scheduled report delivery to more than a hundred users. Loading
Northlake into a blank EEMSuite proves the product end to end and produces
known, repeatable expected results. It is also the demonstration customer, so
everything it contains has to look and read like a real university.

The build is one pass through ten stages, plus an eleventh for the services
outside the database. Each stage is a folder beside this document with a
chapter, the YAML files for its editors and a check script. The
[implementation guide](northlake-implementation-guide.pdf) says how to work a
stage. This document says why the stages are ordered as they are, which
reports each one lights up, and how much of the product is covered so far.

## The scale of the target

- 115 reports across 18 functional modules. 92 can be scheduled and emailed.
  94 are data-backed; 21 are configuration or editor screens. The full list,
  with the data each needs and the stage that provides it, is the
  [report coverage matrix](report-coverage-matrix.pdf).
- The reports collapse to about 28 data capabilities. Every one of them rests
  on the same substrate: a populated hierarchy, users permissioned to nodes,
  units and measure types, a fiscal calendar, and meters tied to billing
  accounts. Without the substrate every report is empty regardless of how rich
  the rest of the data is. That is why Stages 1 and 2 come first and are
  entered completely before any data arrives.
- EEMSuite supports 37 measure types, 9 rate determinant kinds, 7 bill
  allocation methods plus 3 point allocation methods, 7 or more AP and GL
  export formats, and 6 task types. Northlake is designed to touch every one
  of them.

## Stages

| Stage | Builds | Unlocks |
| --- | --- | --- |
| [1 Foundation](stage-1-foundation/stage-1-foundation.pdf) | Companies, levels, defaults, utility providers with real bill cycles and vendor numbers, fiscal calendars, groups with permissions, users | Every editor that follows; the permission and calendar fixtures |
| [2 Hierarchy](stage-2-hierarchy/stage-2-hierarchy.pdf) | Billing accounts; sites, buildings, meters and points for the whole estate; weather stations with degree days; station assignments; aggregates; baseline shells | rp_BuildingList, rp_PointsList, rp_IndexList, rp_HierarchyDetailsEditor and every configuration screen |
| [3 Gateways and data](stage-3-gateways-and-data/stage-3-gateways-and-data.pdf) | Every gateway format with its workflow and task; the AcquiSuite acceptance; handheld routes; baselines | The 15 Use Analysis reports; aggregate demand and peak load; Gateway Status and Task Log |
| [4 Rates](stage-4-rates/stage-4-rates.pdf) | Holidays, seasons, time of use, schedules; rate schedules firing all 9 determinant kinds; meter assignments; rate tests | The 9 Rate Analysis reports; rp_RateComparison shadow billing |
| [5 Bills](stage-5-bills/stage-5-bills.pdf) | Validation rules; Bill Importer sources; 24 months of bills with charge lines; images and notes; status history and approval | Bill Processing and Bill Tracking, about 20 reports; Bill Validation and Late Bills |
| [6 Financial](stage-6-financial/stage-6-financial.pdf) | GL chart and fields; account GL defaults; AP and GL export formats; approval and upload runs; accruals | AP Detail, AP Approval and Upload, GL user-defined values, Open Accruals |
| [7 Allocation and tenants](stage-7-allocation-and-tenants/stage-7-allocation-and-tenants.pdf) | The Northlake Town Center company; thermal plant cost allocation; every bill allocation method; weighted use families; tenant bill generation; reconciliation | The 14 Tenant Rebilling reports and rp_TenantMap |
| [8 Sustainability](stage-8-sustainability/stage-8-sustainability.pdf) | Emission factors and meter assignments; GHG configuration; ENERGY STAR properties and requests through a sandbox account; weather regression; benchmarks | GHG History, Variance and Audit; ENERGY STAR Rating Comparison, History and Request Log; regression and benchmark reports |
| [9 Operations](stage-9-operations/stage-9-operations.pdf) | Projects; alarms; audit and activity; task schedules and custom workflows plus a custom task; saved reports, dashboards, custom reports and views; delivery to 100+ users; handheld; importers; EnergyAI | Project, Alarm, Audit, Activity Tracker, Task Log, HMR, My Imports; every one of the 115 reports rendered at least once |
| [10 Baseline](stage-10-baseline/stage-10-baseline.pdf) | The full backup, a restore into a clean instance, and the verification pass | The reference database that testing and demonstrations restore from then on |
| [11 Third-party integrations](stage-11-third-party/stage-11-third-party.pdf) | Research so far. The identity bundle (Keycloak realm for OIDC and SAML), SCIM provisioning, RabbitMQ, a mail sink, ENERGY STAR and EnergyAI accounts, API service principals, and the host-name convention that makes them portable | Third-party sign-in, provisioning, brokered publishing, delivered mail and API calls on any server that restores the baseline |

## Why this order

Providers come before billing accounts because an account picks its remit
address and its meters pick a bill cycle. The calendar comes before bills
because a bill posts to a fiscal period. Rates come before bills because the
rate tests and the shadow-billing report compare against entered bills, and
because the bill importer's validation can reference expected cost. Gateways
come before rates because interval data is what most determinants consume.
The Town Center company is a separate stage because tenant rebilling needs
shapes a campus does not have. Sustainability and operations come last because
they read everything that came before.

Stage 3 takes one backup, before its gateway entry, as the way back if that goes
wrong. It takes no configured-empty backup (decided November 5, 2026): Northlake is
backed up once it works end to end, and the AcquiSuite cases run in an order that
needs no restore.

## Coverage scorecard

Design coverage, as of packet 0.4 (which adds the Ridgeline Wind Site). Green
means the customer data and the entry plan exist; it does not mean the installed
instance has been accepted. The stage checks and the report matrix are what turn
a row green for real.

| Subsystem | Reports and outputs | Status | Stage |
| --- | --- | --- | --- |
| Hierarchy, security, units substrate | everything depends on it | 🟡 Designed and partly entered | 1, 2 |
| Monthly bills with charge lines | Bill Processing and Tracking, about 20 | 🟡 Bills modeled, charge lines specified; four itemized bills rendered from source | 5 |
| Interval and time series use | Use Analysis, 15 | 🟢 Strong for electric, solar, chilled water and 10-minute wind | 3 |
| Aggregates, peak and demand | Aggregate Demand, Aggregate Peak Load | 🟢 11 aggregates defined | 2, 3 |
| Generated bills | Bill Generation | 🟡 Ridgeline transfer statement specified; acceptance sample supplied | 7 |
| Wind performance (expected against actual) | Radar scorecard, Scatter Plot | 🔴 Goals 41, 43, 47: calculated points, a power-curve fit and a report for the Radar | 2, 9 |
| Rate engine | Rate Analysis, 9 | 🟡 Provider tariffs modeled; the dream schedules specified | 4 |
| AP, GL and financial interface | AP Detail, AP Approval and Upload, GL user-defined values | 🔴 Chart specified, nothing entered; 2 of 7 formats runnable today | 6 |
| Tenant rebilling and allocation | Tenant Rebilling, 14 | 🔴 Town Center specified, nothing entered | 7 |
| Accruals | Open Accruals, accruals, MPA accruals | 🔴 No entry screen exists | 6, 7 |
| Bill validation | Bill Validation, Bill Validation Status | 🟡 Rules specified | 5 |
| GHG and emissions | GHG History, Variance, Audit | 🔴 Factors named in providers, not configured | 8 |
| ENERGY STAR ratings | Rating Comparison, History, Request Log | 🟡 Properties mapped; scores need a Portfolio Manager account | 8 |
| Weather regression and normalization | Weather Regression, Regression Summary | 🟡 Degree days and baseline shells specified | 2, 8 |
| Benchmarks and EUI | Benchmark Ranking, Monthly EUI, Performance Snapshot | 🟡 Floor areas entered; no peer set yet | 8 |
| Project tracking | Project Detail, Summary, Finance | 🔴 Specified only | 9 |
| Alarms | Alarm Data Map | 🔴 Specified only | 9 |
| Audit and activity | Audit, Activity Tracker | 🔴 Produced by use | 9 |
| Tasks, scheduler, workflows | Task Log, Gateway Status, job scheduler | 🟡 Built-in workflows seeded; Northlake tasks not scheduled | 3, 9 |
| Saved reports and delivery | 92 deliverable reports | 🔴 No saved reports or deliveries | 9 |
| Importers | Bill Importer, My Imports, My Exports | 🟡 Formats specified; no importer configuration | 5, 9 |
| Handheld | HMR setup, route export, native return and operational review | 🟡 Stage 3/9 recipes aligned; simulator design agreed, implementation and retained-history precision pending | 3, 9 |
| EnergyAI | EnergyAI Insights | 🔴 External service and enrollment screen needed | 9 |
| Commodities and unique units | cross-cutting | 🟢 Ton-hours, klb and ERU present | 2 |

🟢 covered · 🟡 partial · 🔴 missing

## Decisions already taken

- Tenant rebilling uses both a new mixed-use Northlake Town Center for
  commercial allocation and the sub-metered Cedar Row Apartments for
  residential allocation.
- ENERGY STAR scores come from a sandbox or real Portfolio Manager account
  through the sync task; they are never typed in.
- Where the product supports something no screen can create, the gap is
  closed by building the feature, not by seeding data. The list is
  [product findings](product-findings.pdf).
- Unsupported rate constructs (power factor, coincident peak, critical peak
  pricing, net-metering banking) are modeled as documented synthetic
  stand-ins with pre and post scripts.
- Northlake is built once. The result of Stage 10 is restored from then on;
  the YAML exists so the build can be repeated if the product changes enough
  to require it.

## Still open

- Stage 11's host-name convention: whether every Northlake server serves the
  site and the identity bundle under the same names, which decides whether
  the identity rows can live in the baseline.

- Scale for delivery testing: how many users the 100+ recipient test needs
  and whether they come from a portfolio company or from groups over the
  existing three. Stage 9 proposes a default.
- Which custom task, custom reports and views Northlake carries. Stage 9
  proposes them; the owner decides.
