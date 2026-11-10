---
title: Stage 1. Foundation
subtitle: Companies, utility providers, fiscal calendars, groups and users
status: Ready to enter
---

# Stage 1. Foundation

Stage 1 creates everything the rest of Northlake hangs from: the three companies
with their levels and defaults, the seven utility providers with real bill cycles
and vendor numbers, the fiscal calendars that bills post to, and the groups and
users that decide who sees what. Nothing in this stage needs a meter, a bill or a
file. When its checks are green, Stage 2 can build the hierarchy.

**Added 2026-10-01: Ridgeline Wind.** Stage 1 was already entered when the
Thermal Plant's wind company joined Northlake. On the installed instance that
means four changes, each described in its step below: rename the plant's Level
2 to Facilities, add the Ridgeline Wind provider, add two groups, and add four
users. Two Points grants name the Ridgeline Wind Site node, so they are made
once Stage 2 has created it.

**Added 2026-11-10: fuller coverage.** Stage 1 was entered before this round, so
everything below is extra work on the installed instance, and nothing already
entered changes. Every provider's bill cycles now run to December 2026, so a 2026
bill has a period (add the twelve 2026 periods to each installed cycle). A
seventh provider, Georgian Shore Hydro, is Ontario's electric utility for the
Stage 2 Toronto Research Hall: Northlake's one Canadian address and the first
provider with a second country. Three workload accounts join the users: a Service,
an API client and a Task principal.

Every step below names the app and the screen, links the YAML file that holds
the values for that screen, and says which IDs to write back into the file after
saving. The file's section keys are the editor's own page names, so the file
reads top to bottom the way the editor does.

## Before you start

- The installed NorthLake instance is running: Database Administrator opens and
  signs in with the setup account, the web site answers at
  `https://localdev.energyhippo.com/Hippo`, and the Workers service reports
  ready. No other application or database access is used in this stage.
- Enter everything through the applications. If a screen cannot take a value
  this stage needs, stop and record it under Findings at the end of this chapter
  and in [product findings](../product-findings.pdf). Do not fill the gap with
  SQL.
- Keep the YAML files open beside the editor. After each save, write the
  generated ID into the record's `installed:` block. Those IDs are how later
  stages refer to what you created.

## Step 1. Companies

**Where:** Database Administrator, Nodes. A company is the top node of the
tree; selecting it opens the company editor, whose Definitions tab holds the
pages Bill Scenarios, Company Address, Company Contact, Definitions, Levels
and Weather Stations.

**Enter:** [01-companies.yaml](01-companies.yaml), one record per company.

**Order inside the editor:** Definitions first. Fill Company Name, Archive
Interval, Time Zone, Country and the alarm colour defaults on that page and
save; the other pages unlock after the first save. Then Levels, then Company
Address, then Company Contact. Leave Bill Scenarios as the editor created it.
Weather Stations is Stage 2, and the editor's other tabs (Utility Accountant,
GL Accounts, Bill Validation) belong to later stages.

**EEM creates for you:** the Actual bill scenario and a fiscal calendar from
1990 to 2013. Leave both in place.

**Levels:** the four base types are fixed by the product: Site, Location, Meter
and Point. The descriptions are the words each company uses for them, and every
company carries the same four User Defined Field labels. Icons are Font Awesome
6 class names. The Thermal Plant's Level 2 is Facilities: it holds the Central
Plant, Ridgeline Turbine Field and Ridgeline Substation, none of which is a
building the plant serves, so the earlier Served Buildings label is renamed on
the installed company.

**Record:** the Company ID shown after the first save.

**Check:** `companies_defined`, `levels_match`.

## Step 2. Utility providers

**Where:** Database Administrator, Utility Providers.

**Enter:** [02-utility-providers.yaml](02-utility-providers.yaml), one record per
provider.

**Order inside the editor:** Definitions first (Name, Description, Website,
Icon) and save. Then Provider Address, Provider Contact and Remit Addresses.
Then Bill Cycles: add one cycle grouping per Cycle number and its 36 periods,
2024-01 through 2026-12. A period runs from one meter read to the day before
the next, and its Period and Year are the month the bill posts to. The page
can import the periods from an Excel sheet if typing 36 rows per cycle is slow.
Then Associated Companies, which needs the Step 1 companies to exist: this is
where each company's vendor number for the provider goes. Notes last.

**Why the cycles matter now:** a meter stores only its provider's cycle number,
so the Meter editor in Stage 2 cannot pick a cycle that does not exist yet.

**The Northlake Thermal Plant** is an internal counterparty and a provider at
the same time. It has no website, the plant manager is its contact, and its
addresses are campus mail stops.

**Ridgeline Wind** is the plant's own wind company, bought on July 1, 2024. It
is the second internal provider: its site manager, Mateo Alvarez, is the
contact, the remit address is a campus mail stop, and the only associated
company is the Thermal Plant (vendor RWL-INTERNAL). Its one bill cycle starts
with the acquisition, so it has 30 periods, July 2024 to December 2026. Nobody
sends its bill: EEM generates the monthly transfer statement in Stage 7.

**Georgian Shore Hydro** (added 2026-11-10) is the Canadian provider: a business
address and remit address in Toronto, Ontario (Country CANADA, Region ON), a
commercial accounts contact, one bill cycle of 12 calendar-month periods starting
January 2026 (the Toronto Research Hall opens that month), and Northlake University
as its only associated company (vendor GSH-20001).

**Record:** the Provider ID, and the ID of each remit address once saved.

**Check:** `providers_defined`, `provider_remit`, `provider_bill_cycles`,
`provider_vendor_numbers`.

## Step 3. Company calendars

**Where:** Web, Administration, Company Calendar (`#/CompanyCalendar`).

**Enter:** [03-company-calendars.yaml](03-company-calendars.yaml), 24 periods for
each of the three companies.

**Order inside the page:** pick the company, then add the 2024 and 2025 periods
with their start date, end date, quarter and period name. Fiscal year equals
calendar year for every Northlake company. Do not add 2026: Stage 5 imports a
bill dated January 2026 on purpose to show the fiscal period rejection.

**Record:** nothing; the calendar has no generated IDs.

**Check:** `calendars_2024_2025`.

## Step 4. Groups and permissions

**Where:** Database Administrator, Users & Groups, Groups.

**Enter:** [04-groups.yaml](04-groups.yaml), 29 groups: 21 shared masters under
the Common (System) company and eight local groups across the three Northlake
companies, one of them Cedar Row's copy of eem_reports made local. EEMSuite adds
a copy of each shared master to every company, 91 group rows in all.

**Order inside the editor:** create the group with its Group ID, Name and
Company, save, then open its permission tree and grant what the record lists,
section by section: Admin tabs, Functions, Task Manager, My Import, Library
Rates, Points with its node scope, and Reports by module. Levels are Read,
Modify and Insert/Delete, and every function is entered at Insert/Delete (see
Findings). The permissions in the file are already resolved from the security
profiles, so there is nothing to interpret; enter them as written.

**All means the category, not each item.** A report category marked All, and
a Task Manager or Library Rates grant with Key `*`, is made by setting the level
on the category itself. That saves one wildcard grant, which also covers the
reports, task groups and rates added later, such as the Scene reports. Ticking
every report instead saves one grant per report and misses the next one.

**One copy is made local on purpose.** Open Cedar Row's copy of EEM Billing
and Usage Reports (eem_reports), use Make Local and save. Then rename it CRA EEM
Billing and Usage Reports and add the Tenant Rebilling module, Tenant Rebilling
Reports (All) and all library rates at Read.
Cedar Row's housing staff check the Stage 7 residential tenant bills, and those
reports show only the rates a user holds. The copy keeps its grants and its
members, and the Northlake and Thermal Plant copies stay shared. This is the
Make Local test: a later change to the Common master reaches the two shared
copies and not Cedar Row's.

**Two fixtures to get exactly right:** NLU Bill Entry holds the Bill Entry
Web and bill images functions and nothing on the Admin tabs, while the three
company admin groups hold the Bill Validation function. The web bill editor
gates validation and approval on Bill Validation, so that difference is what
the Stage 5 approval test checks. NLU Science Center Scoped Reports grants the Science
Center building only, not the company root; that is the intra-company scope
test.

**The two Ridgeline groups add the cases that were missing.** Ridgeline Wind
Operations (ntp_wind_ops, local to the Thermal Plant) is node scope at Modify:
its operators change Ridgeline meters and points and never see the Central
Plant. EEM Ridgeline Wind Research (eem_ridgeline_research) is a shared master
whose Points name a node inside another company: university researchers, who
belong to the Northlake University copy, read the plant's Ridgeline site and
nothing else, with no bill reports. Create both with their report grants; their
Points grants (Ridgeline Wind Site, key 0.5.40, at level 2 and level 1) are made
once Stage 2 has saved that node. Do not add any company-root Points to either
group: it would hide whether the site scope works.

**Record:** nothing new; the Group ID you type is the key.

**Check:** `groups_created`, `grants_sentinels`, `node_scope_fixture`,
`report_grants`.

## Step 5. Users

**Where:** Database Administrator, Users & Groups, Users.

**Enter:** [05-users.yaml](05-users.yaml), 26 accounts: 23 people and, added
2026-11-10, three workload accounts (a Service, an API client and a Task
principal). Of the people, the last four are the Ridgeline staff (Mateo Alvarez,
Renee Castillo) and the wind researchers (Elena Vasquez, Kai Nakamura); until
Stage 2 grants their groups' Points they can sign in but see no nodes.

**Order inside the editor:** add the user with User Name, Display Name, Email,
Company, Principal Type Human and the default authentication policy, save,
then assign the Groups the record lists. The three workload accounts differ:
choose their Principal Type (Service, ApiClient or Task) in the Add user drawer,
which then offers only the WorkloadOnly policy and lets the password pair stay
empty; an API client gets its key from Assign/rotate workload credential on its
page, and that key is not written down. The three people with
energyhippo.example.com addresses belong to the Common (System) company. Create
casey.holt like everyone else and then set Inactive: that user stays a member
of NLU Bill Entry and must not be able to sign in.

**Record:** the User ID after save.

**Check:** `users_created`, `memberships`.

## Stage 1 is done when

- Three companies exist with a 60-minute archive interval, Pacific time,
  United States, a street address with coordinates, and a named contact.
- Each company has the same four base levels with the User Defined Field labels
  Site Code, Building Code, Meter Tag and Source Channel; the Thermal Plant's
  Level 2 reads Facilities.
- Seven providers exist with a website (except the Thermal Plant), an icon, a
  business address, a contact, one remit address, and 36 periods for every bill
  cycle from January 2024 to December 2026 (Ridgeline Wind: 30, from July 2024;
  Georgian Shore Hydro: 12, all 2026).
- Fifteen company-to-provider vendor numbers exist.
- Every company's fiscal calendar has 24 periods for 2024 and 2025 and none for
  2026.
- 29 groups (91 rows with the shared copies) and 26 users exist (three of them
  workload accounts), one user
  inactive, every active user in at least one group, Cedar Row's eem_reports is
  local with its own grants, and the two permission fixtures hold. Every All is
  a single category grant, and both Ridgeline groups scope the Ridgeline Wind
  Site. The two bill-import task groups wait for Stage 5, and the two gateway
  task viewers for a read-only Task Manager grant (finding 1).

Run `checks.sql` beside this chapter against the instance database to see each
of these as a result set.

## Findings

Three things the 7.0 permission model changed, found while resolving the
groups file against the installed permission catalog:

- **Task Manager items have one level.** The catalog grants EEM Gateways,
  Report Tasks, Standard Alerts, System Tasks and Bill Importer Tasks as
  all-or-nothing, so a "view task configuration only" group cannot be
  expressed. The viewer groups in this stage get the Gateway Status and Task
  Log reports instead. If read-only task visibility matters to a customer, it
  is a product feature to add.
- **Approval is a function, not a level, and the function is Bill
  Validation.** The web bill editor gates ValidateBill and ValidateBills on the
  Bill Validation function; nothing in 7.0 reads Bill Administration, which the
  catalog still lists as a legacy key. Approver versus entry clerk is therefore
  "holds Bill Validation" versus "holds Bill Entry Web and bill images", and
  the Stage 5 approval test is written against that.
- **Functions are entered at Insert/Delete.** Bulk Data Entry works only at
  Insert/Delete although the catalog lists it at Read only, and until
  2026-10-02 every upgrade raised a function granted at Read or Modify to
  Insert/Delete (finding 77; the backfill now runs once). Bill Validation and
  Bulk Data Entry were entered at Read and the 2026-09-29 upgrade raised them,
  so every function in this stage is entered at Insert/Delete.

All three are recorded in [product findings](../product-findings.pdf). If a page
refuses any other value in this stage, add it here with the screen, the field
and what happened.
