# Source System Inventory (Data Feeds)

Provided by: Northlake University IT & Facilities. Synthetic/illustrative. This
lists the systems and vendors that produce our utility and operational data, so
you can plan how each feed is collected. We've described these as **our** systems,
not as your import mechanics.

| Source system / vendor | Provides | Format | Cadence | Owner | Property |
| --- | --- | --- | --- | --- | --- |
| Valley Electric billing files | Monthly electric bills | CSV/billing file | Monthly | Finance | All electric |
| River City billing files | Bundled water/sewer/stormwater bills | CSV/billing file | Monthly | Finance | Campus + Cedar Row |
| Sierra Gas statements | Gas bills (therms) | PDF statement | Monthly | Finance | Campus |
| Helios PPA invoices + REC statement | Solar generation invoice, RECs, avoided CO2e | PDF/CSV | Monthly | Finance/Sustainability | Science, Student, Cedar Row A |
| Meter-data service (MV90) | Electric & solar interval files | MV90 files | Daily/Monthly | Facilities | Science Center, solar arrays |
| AcquiSuite logger | Student Center electric 15-min interval | AcquiSuite log | Continuous | Facilities | Student Center |
| Central plant BACnet | Chilled-water ton-hours & tons | BACnet present values | Hourly | Thermal Plant | Science Center |
| Plant Modbus controller | Chiller power (kW) | Modbus register | 5-min | Thermal Plant | Thermal Plant |
| Wireless sensors (Spinwave) | Lab temperature/humidity | Sensor CSV | 15-min | Facilities | Science Center |
| FIG-family provider files | Cedar Row water reads | FIG family formats | Monthly | Facilities | Cedar Row A |
| SQL historian extract | Library electric interval | Database extract | 15-min | IT | Library |
| NOAA weather (KSAC) | Outdoor temp, humidity, wind | Public observations | Hourly | Facilities | Sacramento area |
| Aeris weather (KSMF) | Observed + forecast temperature | Weather service | Hourly | Facilities | Sacramento area |
| Neptune handheld | Cedar Row B water route reads | Handheld upload | Monthly | Facilities | Cedar Row B |
| MVRS handheld | Student Center gas route reads | Handheld upload | Monthly | Facilities | Student Center |
| Handheld reading events | Route read events | Event file | Monthly | Facilities | Cedar Row, Student Center |

## Notes

- Some feeds are **files we send you**; some are **systems you connect to**
  (BACnet, Modbus, the SQL historian, weather services). Please confirm which
  collection method you'll use for each.
- We can also provide **interval data via a standard interval feed** (e.g. a
  GreenButton-style export) for one building if that's easier — to discuss.
- **Open:** confirm the delivery owner, cadence, and destination for each feed,
  and the weather station preference per property (KSAC vs KSMF).
