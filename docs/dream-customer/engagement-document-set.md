# Engagement Document Set

How to turn the internal specs/YAMLs into the documents a **real implementation
engagement** actually exchanges — so Northlake reads like a genuine customer, with
the paperwork a corporate onboarding would have.

## The key idea: it's two "binders," not one document type

What you're describing ("integration docs? ADRs? system design docs?") isn't a
single artifact — it's a **document set** split across two sides:

1. **Customer Intake Package** — *what Northlake sends us.* Business facts in the
   customer's own language: facilities, utility accounts, tariffs, bills, org
   chart, GL chart, leases, sustainability goals, data feeds. The customer does
   **not** send EEM configuration — they send the *requirements and source data*.
2. **Solution & Integration Documents** — *what we produce in response.* The
   design and configuration: solution design, integration specs, decision
   records, build workbook, test plan, project plan.

Our YAMLs are mostly **side 2** (our design/config). The "like the customer sent
it" docs are **side 1** — the *business facts that justify* each YAML. Example:
the rates YAML (determinants) is our response to the customer's **rate tariff
sheets**; the security YAML is our response to their **org chart + access
request**; the tenant YAML is our response to their **lease roster**.

This already matches the repo: `customer-provided/` (side 1, with explicit
"customer language vs implementation language" rules) vs `eem/` + `docs/` (side 2).
We extend both.

## What each artifact is actually called

| You said… | Industry name | Side |
| --- | --- | --- |
| "like the customer sent it to us" | **Implementation Intake / Discovery Package** (incl. a **Data Collection Workbook**) | Customer |
| "integration docs" | **Integration Specification** / **Interface Control Document (ICD)** — one per data feed | Vendor |
| "system design docs" | **Solution Design Document (SDD)** (a.k.a. System Design Doc / Solution Blueprint) | Vendor |
| "ADRs" | **Architecture Decision Records** — one per discrete decision | Vendor |
| "plans" | **Statement of Work (SOW)** + **Project/Implementation Plan** | Vendor |

---

## Side 1 — Customer Intake Package: how Northlake tells us each thing

What a real customer hands over, by subsystem. Author = the customer department
that would own it. (Voice + allowed vocabulary per
`customer-provided/northlake-university/README.md`.)

| Subsystem | Customer artifact | Author (Northlake) | Format | Status |
| --- | --- | --- | --- | --- |
| Org & scope | Discovery questionnaire (completed) + cover letter | Project sponsor | Word/PDF | new |
| Facilities/hierarchy | Facilities & Utility Overview | Facilities | PDF | ✅ have |
| Everything structured | **Data Collection Workbook** (sites, buildings, accounts, meters, points, data sources, events, contacts) | Facilities/Finance | Excel | ✅ have (expand) |
| Utility accounts | Utility account inventory (tab) + sample bills | Finance | Excel + PDF | ✅ have |
| **Rates** | **Rate tariff sheets** per provider | Finance / utility | PDF | new |
| **AP/GL** | **Chart of Accounts + GL coding guide**; AP vendor setup | Finance/AP | PDF/Excel | new |
| **Users/security** | **Org chart + user access request / role matrix** | HR/IT | Excel/PDF | new |
| **Tenant rebilling** | **Tenant & lease roster** + allocation-method memo | Housing/Property Mgmt | Excel/PDF | new |
| Sustainability | Reporting requirements (ENERGY STAR, GHG scopes, targets) | Sustainability | PDF | partial (in overview) |
| Projects | Capital/energy project list | Facilities/Sustainability | Excel | new |
| Data feeds | Source-system inventory + delivery cadence + sample files | IT/Facilities | Excel/PDF | partial (in overview) |

The Data Collection Workbook is the spine: today's tabs (Organization Units,
Sites, Buildings, Utility Services, Accounts & Agreements, Meters, Measured
Points, Data Sources, Known Events, Contacts, Open Items) gain **Rate Schedules,
Chart of Accounts, Users & Access, Tenants & Leases, Sustainability, Projects**.

---

## Side 2 — Solution & Integration Documents: what we produce

| Document | Purpose | Built from | Format | Status |
| --- | --- | --- | --- | --- |
| Statement of Work (SOW) | Scope, deliverables, phases, timeline, assumptions | roadmap.md | Word/PDF | derivable |
| Solution Design Document (SDD) | The EEM configuration design across all subsystems | subsystem-gap-analysis.md + phase specs | Word/PDF | derivable |
| Integration Specs / ICDs (one per feed) | Each interface: gateways, bill import, AP export, ENERGY STAR, EnergyAI | providers/ + gateway bindings + phase3/5/6 specs | Word/PDF | new |
| Data Mapping Specification | Customer workbook fields → EEM config fields | workbook + eem/ entry plans | Excel/Word | new |
| Configuration / Build Workbook | Step-by-step build (the "build book") | **eem/*.yaml entry plans** | Word/Excel | ✅ have (as YAML) |
| Architecture Decision Records | One per design decision | decisions made across this project | Markdown/PDF | new (list below) |
| Test / UAT Plan | Acceptance criteria + expected results | phase-0-1-assertions.md + each plan's expectedAssertions | Word/Excel | derivable |
| Gap & Risk Register (RAID) | Open product gaps + risks | product-gap-backlog.md | Excel/Word | ✅ have |
| Project / Implementation Plan | Schedule, milestones, RACI | roadmap.md | Word/MS-Project-ish | derivable |
| Cutover / Go-Live Runbook | Load order + go-live steps | roadmap dependency order | Word | new |

### Candidate ADRs (decisions already made — ready to write up)

1. Model the central plant as **internal cost allocation**, not a utility account.
2. **Cedar Row** as a separate EEM company (security boundary).
3. Use the built-in **System company (CompanyID -1)** for implementation/support.
4. **Enter all data through the EEM UI / legitimate data paths — no direct DB seed.**
5. **Close UI gaps by building product features** (vs deferring).
6. Model rates at the **determinant level** to exercise all 9 determinant kinds.
7. **Connect a sandbox ENERGY STAR PM** account for scores (no hand-entry).
8. **Both Town Center + Cedar Row sub-metering** for tenant rebilling.
9. **Source-model-first**; numeric tariffs single-sourced in `providers/`.
10. **Deterministic synthetic identities**; public context only.

---

## Proposed repo structure

```
customer-provided/northlake-university/     # Side 1 (customer intake) — sources
  00-cover-letter.md
  01-discovery-questionnaire.md
  facilities-and-utility-overview.md        # have
  rate-tariff-sheets/<provider>.md
  chart-of-accounts-and-gl-guide.md
  user-access-request.md
  tenant-and-lease-roster.md
  sustainability-requirements.md
  source-system-inventory.md
  data-collection-workbook.xlsx             # have (expand)
engagement/                                  # Side 2 (vendor) — sources
  sow.md
  solution-design-document.md
  integration-specs/<feed>.md
  data-mapping-specification.md
  adr/NNNN-<decision>.md
  test-uat-plan.md
  gap-risk-register.md                      # from product-gap-backlog.md
  implementation-plan.md                    # from roadmap.md
  cutover-runbook.md
output/                                      # generated Word/PDF/Excel deliverables
```

Markdown stays the versionable source; **Word/PDF/Excel** are generated into
`output/` for the "this is what they sent / what we delivered" feel (the repo
already does md→PDF via `temp/customer-packet`). Skills available: `docx`, `pdf`,
`xlsx`, `pptx`, plus `engineering:architecture` for ADRs.

## Recommended sequencing

1. **Customer Intake Package** first — it's the most evocative "real customer"
   artifact and becomes the *input* the Side-2 docs respond to. Start with the
   workbook expansion + the new intake docs (rate tariff sheets, GL guide, access
   request, lease roster, sustainability requirements, source-system inventory),
   plus a cover letter + discovery questionnaire.
2. **Solution Design Document + ADRs** — the headline Side-2 docs that tie the
   intake to our config.
3. **Integration Specs / ICDs**, **Data Mapping**, **Test/UAT Plan**, **SOW /
   Plan**, **Runbook** — fill out the binder.

Everything is a reframing of work already done — no new design, just the corporate
packaging.
