# Chart of Accounts & GL Coding Guide

Provided by: Northlake University Finance & Accounts Payable. Synthetic/
illustrative values. This describes how we want utility and energy costs coded so
approved costs can be exported to our financial system for payment.

## Financial system

Northlake Finance runs a PeopleSoft-based financials/ERP. We need approved utility
costs delivered to it as:

1. An **AP voucher** interface (for payment), and
2. A **GL journal** interface (for internal cost distribution, including the
   thermal plant allocations).

We currently produce these from spreadsheets by hand; automating them is a
priority. Please confirm the file layout your system can produce against our ERP's
import format during the design phase.

## Chart of accounts (expense + control)

| GL account | Type | Description |
| --- | --- | --- |
| 5100-ELEC | Expense | Electricity expense |
| 5110-GAS | Expense | Natural gas expense |
| 5120-WATER | Expense | Water / sewer / stormwater expense |
| 5130-THERMAL | Expense | Chilled water / steam (internal allocation) |
| 5140-SOLAR | Expense | Solar PPA expense |
| 2000-AP | Liability | Accounts payable control |

## Cost-coding segments

Every cost line is coded with our **five segments** in addition to the GL account:

| Segment | Examples |
| --- | --- |
| Fund | 110 Operating, 250 Auxiliary, 700 Plant |
| Department | Facilities, Housing, Athletics, Labs |
| Program | Instruction, Research, Residential, Administration |
| Activity / Project | (project or activity code, where applicable) |
| Object | (object code) |

## How costs map to coding

| Property / source | GL account | Fund | Department |
| --- | --- | --- | --- |
| Main Campus buildings (electric/gas/water) | by commodity | 110 Operating | Facilities |
| Science Center labs | by commodity | 110 Operating | Labs |
| Cedar Row Apartments | by commodity | 250 Auxiliary | Housing |
| Thermal plant allocations | 5130-THERMAL | 700 Plant | Facilities |
| Solar PPA | 5140-SOLAR | 110 Operating | Facilities |

Some segment values are intentionally left blank on certain accounts (e.g.
Activity/Project) — that is expected, not an error.

## AP setup

- Each utility account should be flagged for the right interface: most are **AP
  upload**; campus electric and thermal accounts are **both AP and GL**; one Cedar
  Row account is intentionally **no upload** (kept off the interface as a control).
- A bill should not be exported until it is **approved** (see access request — the
  person who enters a bill is not the person who approves it), and a bill with an
  open validation alert must be **held** from export.

## Open items

- Confirm the exact ERP import layout for the AP voucher and GL journal.
- Confirm object codes per commodity.
- Confirm whether the solar PPA posts to AP or is handled as a separate agreement.
