# Engagement Document Set

How to turn the internal specs/YAMLs into the documents a **real implementation
engagement** actually exchanges — so Northlake reads like a genuine customer, with
the paperwork a corporate onboarding would have.

**Packet 0.3 is available:** the [customer packet](../../documents/intake-package/)
now includes the corrected 26-tab workbook, complete facilities/meter register,
source measurement mapping and first AcquiSuite files. The matching
[UI implementation checklist](../northlake-onboarding-ui-checklist.pdf)
and [gateway coverage](../northlake-gateway-coverage.pdf) are our response.
The document catalog below describes the larger engagement; it is not a list
of new prerequisites before starting the first gateway.

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

This already matches the repo: `documents/` (side 1, with explicit
"customer language vs implementation language" rules) vs `data/eem/` + `implementation/` (side 2).
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
`generators/documents/README.md`.)

| Subsystem | Customer artifact | Author (Northlake) | Format | Status |
| --- | --- | --- | --- | --- |
| Org & scope | Discovery questionnaire (completed) + cover letter | Project sponsor | Word/PDF | new |
| Facilities/hierarchy | Facilities & Utility Overview | Facilities | PDF | ✅ have |
| Everything structured | **Data Collection Workbook** (inventory, rates, measurement relationships, source mapping, events and later requirements) | Facilities/Finance | Excel | Corrected, packet 0.3 |
| Utility accounts | Utility account inventory (tab) + sample bills | Finance | Excel + PDF | ✅ have |
| **Rates** | **Rate tariff sheets** per provider | Finance / utility | PDF | new |
| **AP/GL** | **Chart of Accounts + GL coding guide**; AP vendor setup | Finance/AP | PDF/Excel | new |
| **Users/security** | **Org chart + user access request / role matrix** | HR/IT | Excel/PDF | new |
| **Tenant rebilling** | **Tenant & lease roster** + allocation-method memo | Housing/Property Mgmt | Excel/PDF | new |
| Sustainability | Reporting requirements (ENERGY STAR, GHG scopes, targets) | Sustainability | PDF | partial (in overview) |
| Projects | Capital/energy project list | Facilities/Sustainability | Excel | new |
| Data feeds | Source-system inventory + delivery cadence + sample files | IT/Facilities | Excel/Markdown/files | Complete mapping; AcquiSuite samples supplied; other fixtures pending |

The Data Collection Workbook is the structured handover. Its 26 tabs are 21
generated tabs (Instructions, Hierarchy, Contacts, Departments &
Responsibilities, Known Events, Sites, Buildings, Service Profiles, Utility
Services, Rate Schedules, Rate Components, Accounts And Agreements, Meters,
Units and Submeters, Measured Points, Related Measurements, Rollup Members,
Weather Assignments, Open Items, Data Sources, Source Measurements) plus 5
retained later-phase tabs (Chart of Accounts, Users & Access, Tenants & Leases,
Sustainability, Projects). Contacts and Departments & Responsibilities provide
the complete implementation directory and department ownership. Hierarchy lists
the company, site and building nodes (every company uses the same four levels:
Site, Building, Meter, Point), with full meter parent paths on Meters; Service
Profiles and Units and Submeters are new in packet 0.3. Separate inventory,
source-system and tenant workbooks are retired. After
`python generators/northlake_packet.py`, `python generators/update_workbook.py`
rebuilds the generated tabs and leaves the later-phase tabs as they are. The
[generator ownership table](../../generators/README.md) identifies the versioned
source for each field so the workbooks and Markdown registers stay consistent.

---

## Side 2 — Solution & Integration Documents: what we produce

| Document | Purpose | Built from | Format | Status |
| --- | --- | --- | --- | --- |
| Statement of Work (SOW) | Scope, deliverables, phases, timeline, assumptions | roadmap.pdf | Word/PDF | derivable |
| Solution Design Document (SDD) | The EEM configuration design across all subsystems | subsystem-gap-analysis.pdf + phase specs | Word/PDF | derivable |
| Integration Specs / ICDs (one per feed) | Each interface: gateways, bill import, AP export, ENERGY STAR, EnergyAI | data/providers/ + gateway bindings + phase3/5/6 specs | Word/PDF | new |
| Data Mapping Specification | Customer workbook fields → EEM config fields | workbook + data/eem/ entry plans | Excel/Word | new |
| Configuration / Build Workbook | Step-by-step build (the "build book") | **data/eem/*.yaml entry plans** | Word/Excel | ✅ have (as YAML) |
| Architecture Decision Records | One per design decision | decisions made across this project | Markdown/PDF | new (list below) |
| Test / UAT Plan | Acceptance criteria + expected results | phase-0-1-assertions.pdf + each plan's expectedAssertions | Word/Excel | derivable |
| Gap & Risk Register (RAID) | Open product gaps + risks | product-gap-backlog.pdf | Excel/Word | ✅ have |
| Project / Implementation Plan | Schedule, milestones, RACI | roadmap.pdf | Word/MS-Project-ish | derivable |
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
9. **Source-model-first**; numeric tariffs single-sourced in `data/providers/`.
10. **Deterministic synthetic identities**; public context only.

---

## Repository structure

```
documents/                         # Side 1: Northlake's own files (PDF)
  intake-package/                  # transmittal, questionnaire, binder, workbook (26 tabs),
                                   # facilities and meter register, source-system inventory,
                                   # user access request, AcquiSuite sample delivery
  guides/                          # facilities & utility overview, GL coding guide,
                                   # sustainability requirements, tenant & lease roster
  rate-tariffs/<provider>.pdf
  utility-bills/<provider>/        # bills and allocation statements
  brand/                           # EEM portal brand kit
implementation/                    # Side 2: what we produce (PDF)
  dream-customer/                  # coverage plan, roadmap, phase specs
  briefs/                          # design briefs
  (planned) sow, solution-design-document, integration-specs/<feed>,
  data-mapping-specification, adr/NNNN-<decision>, test-uat-plan,
  gap-risk-register (from product-gap-backlog), implementation-plan
  (from roadmap), cutover-runbook
data/                              # the versioned YAML facts both sides are built from
generators/documents/sources/      # the Markdown behind every PDF above
```

Markdown stays the versionable source in `generators/documents/sources/`, and
`python generators/documents/build_documents.py` renders each file as a
Northlake PDF under `documents/` or `implementation/` for the "this is what they
sent / what we delivered" feel. `python generators/update_workbook.py` maintains
the one Excel workbook in `documents/intake-package/`. Skills available: `docx`,
`pdf`, `xlsx`, `pptx`, plus `engineering:architecture` for ADRs.

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
