# User Access Request & Role Matrix

Provided by: Northlake University HR & IT, with department input. Synthetic/
illustrative. This lists who needs access to the new system and what each person
needs to do, in business terms. Please map these to the appropriate system roles
and confirm back.

## Access principles

- Access is by **role within a property**, granted through groups — not to
  individuals directly.
- **Separation of duties:** the person who *enters* a bill is not the person who
  *approves* it. Approvals require elevated authority.
- **Read-only** roles (reports, audit, support) must not be able to change data.
- One former employee (Casey Holt) is included intentionally as a **disabled**
  account that must not be able to sign in.
- One internal auditor (Quinn Roberts) needs **read-only visibility across all
  properties**.

## Core users (≈19)

| Name | Title | Property | Needs to… |
| --- | --- | --- | --- |
| Samantha Ireland | Director of Campus Operations | Northlake University | Administer the company; view all reports |
| Jordan Hale | Facilities Systems Manager | Northlake University | Set up hierarchy, meters; view config |
| Priya Nandakumar | Energy Finance Lead | Northlake University | Set up utilities & rates; import bills |
| Nora Chen | Utility Bill Import Specialist | Northlake University (+ Cedar Row) | Import bill files across properties |
| Iris Morales | Utility Bill Entry Clerk | Northlake University | Enter/correct bills (no approval) |
| Leo Martinez | Sustainability Analyst | Northlake University | View sustainability & usage reports |
| Emerson Fox | Campus Data Administrator | Northlake University | Manage company data; DB admin |
| Quinn Roberts | Internal Audit Reviewer | All properties | Read-only audit across companies |
| Keiko Tan | Thermal Allocation Accountant | Univ. + Thermal Plant | Manage allocation rates; view bills |
| Dana Okafor | Science Center Building Coordinator | Northlake University | View reports for **Science Center only** |
| Casey Holt | Former Bill Entry Clerk | Northlake University | **Disabled** — must not sign in |
| Maya Chen | Cedar Row Property Manager | Cedar Row | Administer Cedar Row; view reports |
| Marcus Reed | Accounts Coordinator | Cedar Row | Enter Cedar Row bills |
| Valerie Kim | Housing Operations Analyst | Cedar Row | Set up housing hierarchy; view reports |
| Devon Brooks | Thermal Plant Manager | Thermal Plant | Administer plant; operate; view reports |
| Riley Santos | Thermal Plant Operator | Thermal Plant | Operate plant meters; view reports |
| Avery Singh | EEM Database Administrator | Implementation/Support | System DB admin |
| Morgan Patel | Implementation Consultant | Implementation/Support | App setup validation |
| Taylor Bennett | Support Analyst | Implementation/Support | Read-only support |

Note: Dana Okafor demonstrates **building-level access** — she should see only
Science Center, not the rest of campus. Quinn Roberts demonstrates **cross-
property read-only** access.

## Scheduled-report recipients (≈120)

Beyond the core users, about **120 building representatives** across departments
should **receive scheduled reports** (a monthly building energy report) but do not
need to log in and configure anything. Please set these up as report-delivery
recipient **groups** (roughly a dozen groups of ~10) rather than individual
configuration. A roster will be provided; for now treat them as
report-recipient-only.

## Open items

- Confirm final group membership and any additional building coordinators.
- Confirm email aliases for delivery.
- Confirm the building-representative roster (the ~120 recipients).
