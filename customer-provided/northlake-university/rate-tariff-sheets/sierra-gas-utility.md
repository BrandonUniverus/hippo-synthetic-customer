# Rate Tariff Sheet — Sierra Gas Utility (Natural Gas)

Provided by: Northlake University Finance. Synthetic/illustrative values for
setup. Provider: Sierra Gas Utility (SGU). Monthly bills only; no interval data.
Usage billed in therms, converted from metered ccf at a heating value of **1.027
therms per ccf**.

## Schedule: General Non-Residential Firm Service (SGU-GN-1)

**Effective Jan 1, 2024 – Dec 31, 2025**

| Charge | Basis | Rate |
| --- | --- | --- |
| Customer charge | per month (prorated by days) | $38.00 |
| Commodity — Winter | per therm (Nov–Mar) | $1.142 |
| Commodity — Summer | per therm (Apr–Oct) | $0.876 |
| Transport | per therm | $0.214 |
| Public purpose surcharge | rider | as applicable |
| Utility users tax | % of charges | as applicable |

**Notes for setup:**
- We expect a **monthly fuel cost adjustment** on this service — a per-therm
  amount that changes each month. Please model it so each month can carry its own
  adjustment value.
- Strong winter heating peak; near-flat summer base load.
- One billing period was issued as an **estimate** and later **corrected** with an
  actual read (Student Center) — please handle the correction without
  double-counting.
- A negative-test file for this service intentionally uses an unsupported unit
  (BTU/hr) and should be rejected, not loaded.
- Accounts on this schedule: Admin Hall, Science Center, Library, Student Center.
