# Phase 1 Substrate Extras

Three small but report-blocking additions that finish Phase 1: **bill status
history**, a few **digital/status points**, and sample **notes & images**. These
are additions to `scenarios/demo-university-v1.yaml` (channels/points) and the
`eem/` setup (status history, notes, images), authored here as load-ready spec.

---

## 1. Bill status history (`StatusHistory`)

**Why.** `rp_LateBills`, `rp_DailyProcessingSummary`, and `rp_FiscalPeriodBills`
derive entry dates and processing users from `StatusHistory` (Table_Code `BL`).
Without it those reports are empty and "late" can't be computed.

**Rule.** Every loaded bill gets at least a Status_Code `1` (Bill Entry) history
row:

| field | value |
| --- | --- |
| Table_Code | `BL` |
| Status_Code | `1` (Bill Entry); `2` (QC Approval) for the approved subset |
| SH_TableRowID | the bill id |
| AsOfDate | `billing_end` + entry lag (see below) |
| LastChangedBy | the entry/import user |

**Entry lag + users (deterministic):**

| Provider | Entry path | LastChangedBy | Entry lag after period end |
| --- | --- | --- | --- |
| Valley Electric | import | nora.chen | 3 days |
| Sierra Gas | manual entry | iris.morales | 5 days |
| River City | import | nora.chen | 4 days |
| Northlake Thermal | manual (allocation) | keiko.tan | 6 days |
| Helios Solar | manual entry | iris.morales | 7 days |
| Cedar Row (VED/RCU/HOS) | manual entry | marcus.reed | 5 days |

This yields ≥2 distinct entry users overall (requirement) and realistic
per-provider lags so `rp_LateBills` (default 5-day overdue) flags the slow ones.

**Late-bill fixture.** Stop one account's series one period early (no current
bill) so its projected next-entry date is >5 days overdue → it appears in
`rp_LateBills`. Use **Sierra Gas – Library** (low-traffic) for the deliberate
late account; document it as a scenario event `late_bill_fixture`.

**Approved subset.** Mark ~1/3 of bills Status_Code `2` (QC Approval) by an
AccessLevel-3 user (per `eem/northlake-eem-permissions-v1.yaml`) so AP-export
eligibility (Phase 3) and `rp_DailyProcessingSummary` approval counts are
non-trivial.

---

## 2. Digital / status points

**Why.** `rp_DigitalSummary` and the digital side of the interval engine
(`DigitalArchive_TBL`) need points whose `point_type` is `Digital` with an
enumerated `state_set` (see `digital_reading` in
`schemas/synthetic-source-model.md`). Northlake is currently all analog.

Add these reference channels / points (IDs follow existing manifest conventions):

| channel id | source | commodity | point_type | state_set | interval | maps to |
| --- | --- | --- | --- | --- | --- | --- |
| `ch_modbus_ntp_chiller_enable_status` | thermal plant chiller controller (existing modbus meter) | control | Digital | `chiller_run` {0 off, 1 on} | 15 min | DigitalArchive_TBL |
| `ch_student_center_occupancy_status` | Student Center BMS | control | Digital | `occupancy` {0 unoccupied, 1 occupied} | 15 min | DigitalArchive_TBL |
| `ch_science_center_lab_exhaust_status` | Science Center BMS | control | Digital | `exhaust_mode` {0 normal, 1 high} | 15 min | DigitalArchive_TBL |

**Reading shape (`digital_reading`).** `state_value` is from the set (never a
measured quantity). Deterministic patterns:
- chiller_run: on during cooling season daytime, off overnight/winter.
- occupancy: occupied Mon–Sat building hours, unoccupied otherwise; extra
  occupied blocks on Student Center event days.
- exhaust_mode: mostly normal, high during weekday lab hours.

These also give `rp_DigitalSummary` runtime/duty-cycle results with known totals
(e.g. chiller on-hours per month).

---

## 3. Notes & images

**Why.** `rp_NoteHistory` and `rp_ImageManagement` need `NoteHistory_Tbl` /
`Images` rows attached to entities. Bill images also support the bill-image
viewer used across bill reports.

**Notes** (`note` entity → `NoteHistory_Tbl`):

| target | table code | note |
| --- | --- | --- |
| Library electric meter (replacement) | METR | "Meter replaced 2024-08-14; new synthetic serial issued, same account; reads continuous." |
| Sierra Gas Student Center estimated bill | BL | "Estimated read this cycle; corrected actual issued next cycle (estimated_bill_correction)." |
| Cedar Row A RCU account (renewal) | BA | "Account number changed at 2025 renewal; site/building continuity preserved across all three services." |
| Valley Electric Science Center | METR | "Lab load drives summer peak; power-factor adjustment expected on heavy months." |

**Images** (`image` entity → `Images`):

| target | table code | image_kind | file_ref |
| --- | --- | --- | --- |
| Each provider's sample bills | BL | bill_image | the generated PDFs under `output/pdf/<provider>/...` |
| Library replacement meter | METR | meter_photo | synthetic placeholder photo |

The bill-image links reuse the already-generated synthetic PDFs, so the
bill-image path is exercised with real artifacts.

---

## expectedAssertions

- `every_bill_has_entry_history` — each loaded bill has a Status_Code 1
  `StatusHistory` row with a valid `AsOfDate` and `LastChangedBy`.
- `distinct_entry_users` — ≥2 distinct `LastChangedBy` across bill entry.
- `late_bill_detected` — the Sierra Gas Library late fixture appears in
  `rp_LateBills`.
- `digital_points_present` — ≥3 Digital points with `DigitalArchive` data;
  `rp_DigitalSummary` returns on-hours per month per point.
- `notes_and_images_attached` — `rp_NoteHistory` and `rp_ImageManagement` return
  the seeded notes and bill images.
