# Northlake Facilities and Meter Register

Packet 0.2 | Issued 2026-09-14 | Fictional customer

This register replaces the smaller Draft 0.1 inventory. It describes the requested setup; installation and ingestion acceptance are pending.

## Customer decisions

- **Ownership:** Campus, Cedar Row and Thermal Plant retain separate EEM company boundaries.
- **Names and areas:** Use scenario building areas and Stage 1B display names; the older workbook values are superseded.
- **Student Center thermal service:** Steam only; chilled-water service is not part of the current inventory.
- **Weather:** Northlake University owns the shared KSAC and KSMF references. All listed locations use KSAC observations; KSMF is the secondary and forecast source.
- **Common House:** Create the location without inventing a new metered service.
- **Stormwater:** Campus municipal accounts include ERUs; Cedar Row accounts have water and sewer only.
- **Solar:** Northlake retains RECs under HOS-PPA-2024. Keep exported energy distinct from total generated energy.
- **Overlapping measurements:** Library historian values and meter readings represent the same service; do not add them together.
- **Rollup boundary:** Campus interval totals cover Science Center and Student Center only; they are not the entire campus utility total.
- **FIG variants:** Seven format cases reuse one destination measurement in separate restored runs. Never ingest all variants together as independent consumption.

## Organization Units

Company ownership and primary contact for each department; email and phone come from the Contacts register.

| Unit Name | Purpose / Responsibility | Primary Contact | Email | Phone | Review Status | Notes | Organization |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Campus Operations | Overall sponsorship, scope decisions and implementation priorities. | Samantha Ireland | samantha.ireland@northlake.example.edu | 916-555-0101 | Documented | Scope decisions, implementation priorities and escalation. | Northlake University |
| Facilities Operations | Campus utilities, BMS coordination, meter maintenance and vendor access. | Jordan Hale | facilities.ops@northlake.example.edu | 916-555-4100 | Documented | Facilities shared mailbox. | Northlake University |
| Housing Operations | Cedar Row operations, resident utility questions and common-area service. | Maya Chen | housing.ops@northlake.example.edu | 916-555-4200 | Documented | Housing shared mailbox; belongs to Cedar Row Apartments. | Cedar Row Apartments |
| Finance and Accounts Payable | Utility account ownership, invoice payment, account changes and bill processing. | Priya Nandakumar | ap@northlake.example.edu | 916-555-4300 | Documented | Finance and accounts payable shared mailbox. | Northlake University |
| Sustainability Office | Reporting, renewable energy accounting, emissions factors and performance tracking. | Leo Martinez | sustainability@northlake.example.edu | 916-555-4400 | Documented | Sustainability shared mailbox. | Northlake University |
| Thermal Plant Operations | Plant operations, steam and chilled-water service, allocation statements and controller sources. | Devon Brooks | devon.brooks@northlake.example.edu | 916-555-0104 | Documented | Internal thermal-service counterparty and plant escalation contact. | Northlake Thermal Plant |

## Contacts

Company contacts and utility representatives. All details are fictional; shared contact mailboxes can differ from user login email.

| Organization | Contact Name | Role | Email | Phone | Applies To | Review Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Northlake University | Samantha Ireland | Director of Campus Operations | samantha.ireland@northlake.example.edu | 916-555-0101 | Overall sponsorship | Documented | Scope decisions, implementation priorities and escalation. |
| Northlake University | Jordan Hale | Facilities Systems Manager | facilities.ops@northlake.example.edu | 916-555-4100 | Meters, buildings and source systems | Documented | Facilities shared mailbox. |
| Northlake University | Priya Nandakumar | Energy Finance Lead | ap@northlake.example.edu | 916-555-4300 | Billing accounts, invoices and account changes | Documented | Finance and accounts payable shared mailbox. |
| Northlake University | Iris Morales | Utility Bill Entry Clerk | iris.morales@northlake.example.edu | 916-555-0102 | Bill entry and corrections | Documented | Utility bill processing contact. |
| Northlake University | Nora Chen | Utility Bill Import Specialist | nora.chen@northlake.example.edu | 916-555-0103 | Bill imports for Northlake University and Cedar Row | Documented | Cross-property billing contact. |
| Northlake University | Leo Martinez | Sustainability Analyst | sustainability@northlake.example.edu | 916-555-4400 | Solar, weather and sustainability reporting | Documented | Sustainability shared mailbox. |
| Cedar Row Apartments | Maya Chen | Cedar Row Property Manager | housing.ops@northlake.example.edu | 916-555-4200 | Cedar Row operations and resident utility questions | Documented | Housing shared mailbox; belongs to Cedar Row Apartments. |
| Northlake Thermal Plant | Devon Brooks | Thermal Plant Manager | devon.brooks@northlake.example.edu | 916-555-0104 | Thermal plant operations, steam and chilled-water allocations | Documented | Internal thermal-service counterparty and plant escalation contact. |
| Valley Electric District | Owen Blake | Electric account representative | owen.blake@valleyelectric.example | 916-555-6100 | Electric bills and interval files | Documented |  |
| Sierra Gas Utility | Marisol Vega | Gas account representative | marisol.vega@sierragas.example | 916-555-6150 | Gas bills and route files | Documented |  |
| River City Utilities | Dana Perez | Municipal utility representative | dana.perez@rivercity.example | 916-555-6200 | Water, sewer and stormwater bills | Documented |  |
| Helios Onsite Solar | Simone Hart | Solar PPA representative | simone.hart@helios.example | 916-555-6300 | PPA statements and generation data | Documented |  |

## Buildings

Six benchmarked buildings plus the central plant and Common House supporting locations.

| Building Name | Site Name | Building Type | Primary Owner | Service Address | Gross Area | Area Unit | Occupancy / Use Notes | Review Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Admin Hall | Northlake Main Campus | office classroom | Facilities Operations | 100 Synthetic Campus Drive | 85000 | sq ft | office classroom | Documented | Included in the existing benchmarking boundary. |
| Applied Science Center | Northlake Main Campus | lab classroom | Facilities Operations | 120 Synthetic Campus Drive | 120000 | sq ft | lab classroom | Documented | Included in the existing benchmarking boundary. |
| Main Library | Northlake Main Campus | library | Facilities Operations | 140 Synthetic Campus Drive | 70000 | sq ft | library | Documented | Included in the existing benchmarking boundary. |
| Student Center | Northlake Main Campus | food service event | Facilities Operations | 160 Synthetic Campus Drive | 95000 | sq ft | food service event | Documented | Included in the existing benchmarking boundary. |
| Cedar Row A | Cedar Row Apartments | multifamily housing | Housing Operations | 400 Synthetic Grove Avenue | 58000 | sq ft | 60 apartments | Documented | Included in the existing benchmarking boundary. |
| Cedar Row B | Cedar Row Apartments | multifamily housing | Housing Operations | 420 Synthetic Grove Avenue | 62000 | sq ft | 64 apartments | Documented | Included in the existing benchmarking boundary. |
| Northlake Central Plant | Northlake Main Campus | Supporting facility | Northlake Thermal Plant | 4122 Plant Service Road | 58400 | sq ft | Plant controller location; excluded from the existing 370000 sq ft academic benchmarking boundary. | Documented | See scope note; no automatic change to ENERGY STAR properties. |
| Cedar Row Common House | Cedar Row Apartments | Supporting facility | Housing Operations | 1304 Cedar Row Lane | 18400 | sq ft | Location only in this release; no separate account or meter. Excluded from the existing 120000 sq ft residential benchmarking boundary. | Documented | See scope note; no automatic change to ENERGY STAR properties. |

## Accounts And Agreements

One row per source account, PPA agreement or internal cost center; several services may share an account.

| Account / Agreement Name | Provider / Counterparty | Service Category | Account Number | Site / Building Scope | Cost Center | Start Date | End Date | Billing Contact | Review Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Admin Hall / VED | Valley Electric District | external Utility Accounts | SYN-VED-A-0010001 | Northlake University / Admin Hall |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | VED-TOU-GS |
| Applied Science Center / VED | Valley Electric District | external Utility Accounts | SYN-VED-A-0010002 | Northlake University / Applied Science Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | VED-TOU-GS |
| Main Library / VED | Valley Electric District | external Utility Accounts | SYN-VED-A-0010003 | Northlake University / Main Library |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | VED-TOU-GS |
| Student Center / VED | Valley Electric District | external Utility Accounts | SYN-VED-A-0010004 | Northlake University / Student Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | VED-TOU-GS |
| Cedar Row A / VED | Valley Electric District | external Utility Accounts | SYN-VED-A-0010005 | Cedar Row Apartments / Cedar Row A |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | VED-TOU-GS |
| Cedar Row B / VED | Valley Electric District | external Utility Accounts | SYN-VED-A-0010006 | Cedar Row Apartments / Cedar Row B |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | VED-TOU-GS |
| Admin Hall / SGU | Sierra Gas Utility | external Utility Accounts | SYN-SGU-A-0020001 | Northlake University / Admin Hall |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | SGU-GN-1 |
| Applied Science Center / SGU | Sierra Gas Utility | external Utility Accounts | SYN-SGU-A-0020002 | Northlake University / Applied Science Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | SGU-GN-1 |
| Main Library / SGU | Sierra Gas Utility | external Utility Accounts | SYN-SGU-A-0020003 | Northlake University / Main Library |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | SGU-GN-1 |
| Student Center / SGU | Sierra Gas Utility | external Utility Accounts | SYN-SGU-A-0020004 | Northlake University / Student Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | SGU-GN-1 |
| Admin Hall / RCU | River City Utilities | external Utility Accounts | SYN-RCU-A-0030001 | Northlake University / Admin Hall |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | RCU-W-TIER, RCU-S-VOL, RCU-SW-ERU |
| Student Center / RCU | River City Utilities | external Utility Accounts | SYN-RCU-A-0030002 | Northlake University / Student Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | RCU-W-TIER, RCU-S-VOL, RCU-SW-ERU |
| Cedar Row A / RCU | River City Utilities | external Utility Accounts | SYN-RCU-A-0030003 | Cedar Row Apartments / Cedar Row A |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | RCU-W-TIER, RCU-S-VOL |
| Cedar Row B / RCU | River City Utilities | external Utility Accounts | SYN-RCU-A-0030004 | Cedar Row Apartments / Cedar Row B |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | RCU-W-TIER, RCU-S-VOL |
| Applied Science Center / NTP | Northlake Thermal Plant | internal Cost Centers | SYN-NTP-C-0000001 | Northlake Thermal Plant / Applied Science Center | SYN-NTP-C-0000001 | 2024-01-01 | Active | Finance and Accounts Payable | Documented | NTP-ALLOC-CHW, NTP-ALLOC-STEAM |
| Admin Hall / NTP | Northlake Thermal Plant | internal Cost Centers | SYN-NTP-C-0000002 | Northlake Thermal Plant / Admin Hall | SYN-NTP-C-0000002 | 2024-01-01 | Active | Finance and Accounts Payable | Documented | NTP-ALLOC-STEAM |
| Main Library / NTP | Northlake Thermal Plant | internal Cost Centers | SYN-NTP-C-0000003 | Northlake Thermal Plant / Main Library | SYN-NTP-C-0000003 | 2024-01-01 | Active | Finance and Accounts Payable | Documented | NTP-ALLOC-STEAM |
| Student Center / NTP | Northlake Thermal Plant | internal Cost Centers | SYN-NTP-C-0000004 | Northlake Thermal Plant / Student Center | SYN-NTP-C-0000004 | 2024-01-01 | Active | Finance and Accounts Payable | Documented | NTP-ALLOC-STEAM |
| Applied Science Center / HOS | Helios Onsite Solar | ppa Agreements | SYN-HOS-P-0000001 | Northlake University / Applied Science Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | HOS-PPA-2024 |
| Student Center / HOS | Helios Onsite Solar | ppa Agreements | SYN-HOS-P-0000002 | Northlake University / Student Center |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | HOS-PPA-2024 |
| Cedar Row A / HOS | Helios Onsite Solar | ppa Agreements | SYN-HOS-P-0000003 | Cedar Row Apartments / Cedar Row A |  | 2024-01-01 | Active | Finance and Accounts Payable | Documented | HOS-PPA-2024 |

## Meters

Physical meters, logical measurement groups and weather references; every planned gateway measurement has a destination.

| Meter Name | Meter Number / Tag | Service Category | Site Name | Building Name | Provider / Counterparty | Installation Location | Ownership | Read Method | Review Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Admin Hall Electric Main | SYN-VED-M-0040001 | Electric | Northlake Main Campus | Admin Hall | Valley Electric District | Admin Hall | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-VED-A-0010001. |
| Admin Hall Gas Meter | SYN-SGU-M-0050001 | Natural Gas | Northlake Main Campus | Admin Hall | Sierra Gas Utility | Admin Hall | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-SGU-A-0020001. |
| Admin Hall Municipal Water | SYN-RCU-M-0060001 | Water | Northlake Main Campus | Admin Hall | River City Utilities | Admin Hall | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-RCU-A-0030001. |
| Applied Science Electric Interval | SYN-VED-M-0040002 | Electric | Northlake Main Campus | Applied Science Center | Valley Electric District | Applied Science Center | Northlake University | Valley Electric meter-data service | Documented | Company: Northlake University. Account: SYN-VED-A-0010002. |
| Applied Science Gas Meter | SYN-SGU-M-0050002 | Natural Gas | Northlake Main Campus | Applied Science Center | Sierra Gas Utility | Applied Science Center | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-SGU-A-0020002. |
| Applied Science PV Array | SYN-HOS-M-0080001 | Solar Generation | Northlake Main Campus | Applied Science Center | Helios Onsite Solar | Applied Science Center | Northlake University | Helios solar meter-data service | Documented | Company: Northlake University. Account: SYN-HOS-P-0000001. |
| Applied Science Environmental Sensors | SCIENCE-CENTER-ENVIRONMENTAL-SENSORS | Weather | Northlake Main Campus | Applied Science Center | Northlake / reference source | Applied Science Center | Northlake University | Applied Science laboratory sensors | Documented | Company: Northlake University. Account: No billing account. |
| Main Library Electric Old Meter | SYN-VED-M-0040003 | Electric | Northlake Main Campus | Main Library | Valley Electric District | Main Library | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-VED-A-0010003. Service dates: 2024-01-01 through 2024-08-14. |
| Main Library Electric New Meter | SYN-VED-M-0040103 | Electric | Northlake Main Campus | Main Library | Valley Electric District | Main Library | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-VED-A-0010003. Service dates: 2024-08-15 through active. Replaces ved_library_main_before_replacement; keep histories separate. |
| Main Library Gas Meter | SYN-SGU-M-0050003 | Natural Gas | Northlake Main Campus | Main Library | Sierra Gas Utility | Main Library | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-SGU-A-0020003. |
| Main Library Electric Historian | LIBRARY-HISTORIAN-ELECTRIC-INTERVAL | Electric | Northlake Main Campus | Main Library | Northlake / reference source | Main Library | Northlake University | Main Library historian | Documented | Company: Northlake University. Account: No billing account. |
| Student Center Electric Interval | SYN-VED-M-0040004 | Electric | Northlake Main Campus | Student Center | Valley Electric District | Student Center | Northlake University | Student Center AcquiSuite logger | Documented | Company: Northlake University. Account: SYN-VED-A-0010004. |
| Student Center Gas Meter | SYN-SGU-M-0050004 | Natural Gas | Northlake Main Campus | Student Center | Sierra Gas Utility | Student Center | Northlake University | Student Center gas route | Documented | Company: Northlake University. Account: SYN-SGU-A-0020004. |
| Student Center Municipal Water | SYN-RCU-M-0060002 | Water | Northlake Main Campus | Student Center | River City Utilities | Student Center | Northlake University | Bill / allocation statement | Documented | Company: Northlake University. Account: SYN-RCU-A-0030002. |
| Student Center PV Array | SYN-HOS-M-0080002 | Solar Generation | Northlake Main Campus | Student Center | Helios Onsite Solar | Student Center | Northlake University | Helios solar meter-data service | Documented | Company: Northlake University. Account: SYN-HOS-P-0000002. |
| Student Center Fake Gateway Smoke | FAKE-GATEWAY-SMOKE-METER | Electric | Northlake Main Campus | Student Center | Northlake / reference source | Student Center | Northlake University | Student Center commissioning test signal | Documented | Company: Northlake University. Account: No billing account. |
| Cedar Row A Common Electric | SYN-VED-M-0040005 | Electric | Cedar Row Apartments | Cedar Row A | Valley Electric District | Cedar Row A | Cedar Row Apartments | Bill / allocation statement | Documented | Company: Cedar Row Apartments. Account: SYN-VED-A-0010005. |
| Cedar Row A Municipal Water | SYN-RCU-M-0060003 | Water | Cedar Row Apartments | Cedar Row A | River City Utilities | Cedar Row A | Cedar Row Apartments | Cedar Row A water export | Documented | Company: Cedar Row Apartments. Account: SYN-RCU-A-0030003. |
| Cedar Row A Solar Carport | SYN-HOS-M-0080003 | Solar Generation | Cedar Row Apartments | Cedar Row A | Helios Onsite Solar | Cedar Row A | Cedar Row Apartments | Helios solar meter-data service | Documented | Company: Cedar Row Apartments. Account: SYN-HOS-P-0000003. |
| Cedar Row B Common Electric | SYN-VED-M-0040006 | Electric | Cedar Row Apartments | Cedar Row B | Valley Electric District | Cedar Row B | Cedar Row Apartments | Bill / allocation statement | Documented | Company: Cedar Row Apartments. Account: SYN-VED-A-0010006. |
| Cedar Row B Municipal Water | SYN-RCU-M-0060004 | Water | Cedar Row Apartments | Cedar Row B | River City Utilities | Cedar Row B | Cedar Row Apartments | Cedar Row B water route | Documented | Company: Cedar Row Apartments. Account: SYN-RCU-A-0030004. |
| Applied Science Chilled Water BTU Meter | SYN-NTP-M-0070001 | Chilled Water | Northlake Main Campus | Chilled Water / Applied Science Center | Northlake Thermal Plant | Chilled Water / Applied Science Center | Northlake Thermal Plant | Central plant building automation | Documented | Company: Northlake Thermal Plant. Account: SYN-NTP-C-0000001. |
| Applied Science Steam Allocation | SYN-NTP-M-0070101 | Steam | Northlake Main Campus | Steam / Applied Science Center | Northlake Thermal Plant | Steam / Applied Science Center | Northlake Thermal Plant | Bill / allocation statement | Documented | Company: Northlake Thermal Plant. Account: SYN-NTP-C-0000001. |
| Admin Hall Steam Allocation | SYN-NTP-M-0070002 | Steam | Northlake Main Campus | Steam / Admin Hall | Northlake Thermal Plant | Steam / Admin Hall | Northlake Thermal Plant | Bill / allocation statement | Documented | Company: Northlake Thermal Plant. Account: SYN-NTP-C-0000002. |
| Main Library Steam Allocation | SYN-NTP-M-0070003 | Steam | Northlake Main Campus | Steam / Main Library | Northlake Thermal Plant | Steam / Main Library | Northlake Thermal Plant | Bill / allocation statement | Documented | Company: Northlake Thermal Plant. Account: SYN-NTP-C-0000003. |
| Student Center Steam Allocation | SYN-NTP-M-0070004 | Steam | Northlake Main Campus | Steam / Student Center | Northlake Thermal Plant | Steam / Student Center | Northlake Thermal Plant | Bill / allocation statement | Documented | Company: Northlake Thermal Plant. Account: SYN-NTP-C-0000004. |
| Central Plant Chiller Controller | NTP-MODBUS-CHILLER-CONTROLLER | Electric | Northlake Main Campus | Plant Electric / Northlake Central Plant | Northlake / reference source | Plant Electric / Northlake Central Plant | Northlake Thermal Plant | Central plant chiller controller | Documented | Company: Northlake Thermal Plant. Account: No billing account. |
| KSAC Sacramento Executive Airport | KSAC | Weather | Reference stations | Sacramento Weather Reference | Northlake / reference source | Sacramento Weather Reference | Northlake University | KSAC weather observations | Documented | Company: Northlake University. Account: No billing account. |
| KSMF Sacramento International Airport | KSMF | Weather | Reference stations | Sacramento Weather Reference | Northlake / reference source | Sacramento Weather Reference | Northlake University | KSMF observations and forecast | Documented | Company: Northlake University. Account: No billing account. |

## Measured Points

Measured and explicitly specified point definitions. Related outputs and rollup members are listed on their own tabs.

| Point Name | Meter Name | Measurement | Direction / Role | Units | Interval / Frequency | Use In Reporting | Review Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Delivered kWh | Admin Hall Electric Main | billing usage | Analog | kWh | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Billing Demand kW | Admin Hall Electric Main | billing demand | Analog | kW | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Gas Therms | Admin Hall Gas Meter | billing usage | Analog | therms | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Potable Water | Admin Hall Municipal Water | billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Derived Sewer Volume | Admin Hall Municipal Water | derived billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Stormwater ERUs | Admin Hall Municipal Water | flat service fee | Analog | eru | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Delivered kWh 15m | Applied Science Electric Interval | interval usage | Analog | kWh | 15 minutes | Yes | Documented | Source: Valley Electric meter-data service |
| Billing Demand kW 15m | Applied Science Electric Interval | interval demand | Analog | kW | 15 minutes | Yes | Documented | Source: Valley Electric meter-data service |
| Gas Therms | Applied Science Gas Meter | billing usage | Analog | therms | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| PV Generated kWh 15m | Applied Science PV Array | interval generation | Analog | kWh | 15 minutes | Yes | Documented | Source: Helios solar meter-data service |
| PV Exported kWh 15m | Applied Science PV Array | interval export | Analog | kWh | 15 minutes | Yes | Documented | Source: Helios solar meter-data service |
| PV Generated kW 15m | Applied Science PV Array | interval generation demand | Analog | kW | 15 minutes | Yes | Documented | From bill, related-point calculation or a later input path. |
| Lab Air Temperature | Applied Science Environmental Sensors | sensor observation | Analog | degF | 15 minutes | Yes | Documented | Source: Applied Science laboratory sensors |
| Lab Relative Humidity | Applied Science Environmental Sensors | sensor observation | Analog | pct | 15 minutes | Yes | Documented | Source: Applied Science laboratory sensors |
| Delivered kWh Old Meter | Main Library Electric Old Meter | billing usage | Analog | kWh | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Delivered kWh New Meter | Main Library Electric New Meter | billing usage | Analog | kWh | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Gas Therms | Main Library Gas Meter | billing usage | Analog | therms | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Historian Delivered kWh 15m | Main Library Electric Historian | interval usage | Analog | kWh | 15 minutes | Yes | Documented | Source: Main Library historian |
| Delivered kWh 15m | Student Center Electric Interval | interval usage | Analog | kWh | 15 minutes | Yes | Documented | Source: Student Center AcquiSuite logger |
| Demand kW 15m | Student Center Electric Interval | interval demand | Analog | kW | 15 minutes | Yes | Documented | Source: Student Center AcquiSuite logger |
| Gas Therms Usage | Student Center Gas Meter | handheld usage delta | AccumulatorDelta | therms | Monthly route / actual reading dates | Yes | Documented | Source: Student Center gas route |
| Gas Register Reading | Student Center Gas Meter | handheld register reading | Accumulator | Reading | Monthly route / actual reading dates | Yes | Documented | From bill, related-point calculation or a later input path. |
| Potable Water | Student Center Municipal Water | billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Derived Sewer Volume | Student Center Municipal Water | derived billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Stormwater ERUs | Student Center Municipal Water | flat service fee | Analog | eru | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| PV Generated kWh 15m | Student Center PV Array | interval generation | Analog | kWh | 15 minutes | Yes | Documented | Source: Helios solar meter-data service |
| PV Exported kWh 15m | Student Center PV Array | interval export | Analog | kWh | 15 minutes | Yes | Documented | From bill, related-point calculation or a later input path. |
| PV Generated kW 15m | Student Center PV Array | interval generation demand | Analog | kW | 15 minutes | Yes | Documented | From bill, related-point calculation or a later input path. |
| Fake Gateway Smoke kWh 15m | Student Center Fake Gateway Smoke | generated smoke test | Analog | kWh | 15 minutes | Exclude test signal | Documented | Source: Student Center commissioning test signal |
| Common Area kWh | Cedar Row A Common Electric | billing usage | Analog | kWh | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Potable Water | Cedar Row A Municipal Water | billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Derived Sewer Volume | Cedar Row A Municipal Water | derived billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| FIG Water Interval | Cedar Row A Municipal Water | interval usage | Analog | kgal | 60 minutes | Yes | Documented | Source: Cedar Row A water export |
| PV Generated kWh 15m | Cedar Row A Solar Carport | interval generation | Analog | kWh | 15 minutes | Yes | Documented | Source: Helios solar meter-data service |
| PV Exported kWh 15m | Cedar Row A Solar Carport | interval export | Analog | kWh | 15 minutes | Yes | Documented | From bill, related-point calculation or a later input path. |
| Common Area kWh | Cedar Row B Common Electric | billing usage | Analog | kWh | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Potable Water Usage | Cedar Row B Municipal Water | handheld usage delta | AccumulatorDelta | kgal | Monthly route / actual reading dates | Yes | Documented | Source: Cedar Row B water route |
| Water Register Reading | Cedar Row B Municipal Water | handheld register reading | Accumulator | Reading | Monthly route / actual reading dates | Yes | Documented | From bill, related-point calculation or a later input path. |
| Derived Sewer Volume | Cedar Row B Municipal Water | derived billing usage | Analog | kgal | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Chilled Water Ton-Hours | Applied Science Chilled Water BTU Meter | interval usage | Analog | ton_hours | 60 minutes | Yes | Documented | Source: Central plant building automation |
| Chilled Water Tons | Applied Science Chilled Water BTU Meter | interval demand | Analog | tons | 60 minutes | Yes | Documented | Source: Central plant building automation |
| Steam klb | Applied Science Steam Allocation | monthly allocation | Analog | klb | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Steam klb | Admin Hall Steam Allocation | monthly allocation | Analog | klb | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Steam klb | Main Library Steam Allocation | monthly allocation | Analog | klb | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Steam klb | Student Center Steam Allocation | monthly allocation | Analog | klb | Monthly / actual bill period | Yes | Documented | From bill, related-point calculation or a later input path. |
| Chiller Demand kW 5m | Central Plant Chiller Controller | equipment demand | Analog | kW | 5 minutes | Yes | Documented | Source: Central plant chiller controller |
| Chiller Enable Status | Central Plant Chiller Controller | equipment status | Digital | state | 5 minutes | Yes | Documented | From bill, related-point calculation or a later input path. |
| KSAC Outside Air Temperature | KSAC Sacramento Executive Airport | weather | Analog | degF | 60 minutes | Yes | Documented | Source: KSAC weather observations |
| KSAC Relative Humidity | KSAC Sacramento Executive Airport | weather | Analog | pct | 60 minutes | Yes | Documented | Source: KSAC weather observations |
| KSAC Wind Speed | KSAC Sacramento Executive Airport | weather | Analog | mph | 60 minutes | Yes | Documented | Source: KSAC weather observations |
| KSMF Outside Air Temperature | KSMF Sacramento International Airport | weather | Analog | degF | 60 minutes | Yes | Documented | Source: KSMF observations and forecast |
| KSMF Forecast Temperature | KSMF Sacramento International Airport | weather | Analog | degF | 60 minutes | Yes | Documented | Source: KSMF observations and forecast |

## Related Measurements

Business relationships to create through the product's supported point/index settings.

| Source Meter | Source Measurement | Related Meter | Related Measurement | Relationship | Frequency | Requirement |
| --- | --- | --- | --- | --- | --- | --- |
| Student Center Gas Meter | Gas Register Reading | Student Center Gas Meter | Gas Therms Usage | Usage from register difference | Actual reading dates | Multiplier 1 for the initial case; capture the automatically created usage-point ID. Do not create an unrelated second usage point. |
| Cedar Row B Municipal Water | Water Register Reading | Cedar Row B Municipal Water | Potable Water Usage | Usage from register difference | Actual reading dates | Multiplier 1 for the initial case; capture the automatically created usage-point ID. Do not create an unrelated second usage point. |
| KSAC Sacramento Executive Airport | KSAC Outside Air Temperature | KSAC Sacramento Executive Airport | HDD_F_daily | Heating degree days | Daily | Create through the temperature index setting; verify base and calculation method in the UI. |
| KSAC Sacramento Executive Airport | KSAC Outside Air Temperature | KSAC Sacramento Executive Airport | CDD_F_daily | Cooling degree days | Daily | Create through the temperature index setting; verify base and calculation method in the UI. |
| KSMF Sacramento International Airport | KSMF Outside Air Temperature | KSMF Sacramento International Airport | HDD_F_daily | Heating degree days | Daily | Create through the temperature index setting; verify base and calculation method in the UI. |
| KSMF Sacramento International Airport | KSMF Outside Air Temperature | KSMF Sacramento International Airport | CDD_F_daily | Cooling degree days | Daily | Create through the temperature index setting; verify base and calculation method in the UI. |
| Applied Science Electric Interval | Delivered kWh 15m | Applied Science Electric Interval | Applied Science Electric kWh Baseline | Measured versus baseline | 15 minutes | Baseline definition only; calculation and expected values are a later acceptance step. |
| Student Center Electric Interval | Demand kW 15m | Student Center Electric Interval | Student Center Demand kW Baseline | Measured versus baseline | 15 minutes | Baseline definition only; calculation and expected values are a later acceptance step. |
| Applied Science Chilled Water BTU Meter | Chilled Water Ton-Hours | Applied Science Chilled Water BTU Meter | Applied Science Chilled Water Ton-Hours Baseline | Measured versus baseline | 60 minutes | Baseline definition only; calculation and expected values are a later acceptance step. |

## Rollup Members

One row per member. Never add monthly bills to their interval representation or include the commissioning test signal.

| Requested Total | Member Meter | Member Measurement | Multiplier | Availability | Unit | Interval Minutes | Boundary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Campus Interval Electric kWh Total | Applied Science Electric Interval | Delivered kWh 15m | 1 | Required | kWh | 15 | Science + Student only |
| Campus Interval Electric kWh Total | Student Center Electric Interval | Delivered kWh 15m | 1 | Required | kWh | 15 | Science + Student only |
| Campus Coincident Electric kW | Applied Science Electric Interval | Billing Demand kW 15m | 1 | Required | kW | 15 | Science + Student only |
| Campus Coincident Electric kW | Student Center Electric Interval | Demand kW 15m | 1 | Required | kW | 15 | Science + Student only |
| Campus PV Generated kWh | Applied Science PV Array | PV Generated kWh 15m | 1 | Required | kWh | 15 | Science + Student only |
| Campus PV Generated kWh | Student Center PV Array | PV Generated kWh 15m | 1 | Required | kWh | 15 | Science + Student only |
| Applied Science Net Electric kWh | Applied Science Electric Interval | Delivered kWh 15m | 1 | Required | kWh | 15 | Delivered minus generated; an analysis series, not a supplier bill total |
| Applied Science Net Electric kWh | Applied Science PV Array | PV Generated kWh 15m | -1 | Optional | kWh | 15 | Delivered minus generated; an analysis series, not a supplier bill total |

## Weather Assignments

Shared station ownership avoids duplicating weather measurements under every building.

| Organization | Location | Reference Station |
| --- | --- | --- |
| Northlake University | Admin Hall | KSAC |
| Northlake University | Applied Science Center | KSAC |
| Northlake University | Main Library | KSAC |
| Northlake University | Student Center | KSAC |
| Cedar Row Apartments | Cedar Row A | KSAC |
| Cedar Row Apartments | Cedar Row B | KSAC |
| Cedar Row Apartments | Cedar Row Common House | KSAC |
| Northlake Thermal Plant | Applied Science Center | KSAC |
| Northlake Thermal Plant | Admin Hall | KSAC |
| Northlake Thermal Plant | Main Library | KSAC |
| Northlake Thermal Plant | Student Center | KSAC |
| Northlake Thermal Plant | Northlake Central Plant | KSAC |
