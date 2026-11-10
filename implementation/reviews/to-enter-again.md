# To enter again in stages already built (November 10, 2026)

The coverage fixes added records to stages that are already in the Northlake database. Enter them in this order.
Each line names the YAML file that holds the values. The stage checks will report these as missing until they are
entered.

## Stage 1. Foundation

1. **Utility Providers, bill cycles.** Add the 12 periods for 2026 to every cycle of the six providers (Ridgeline
   too). [02-utility-providers.yaml](../stage-1-foundation/02-utility-providers.yaml)
2. **Utility Providers, new provider.** Georgian Shore Hydro (Toronto, Ontario, Canada): all pages, one cycle with
   12 periods for 2026, associated company Northlake University, vendor number GSH-20001. Same file.
3. **Users.** Three non-human accounts under Northlake University, then their groups: `svc.report-delivery`
   (Service), `api.energy-dashboard` (API client), `task.gateway-poll` (Task).
   [05-users.yaml](../stage-1-foundation/05-users.yaml)

## Stage 2. Hierarchy

4. **Nodes.** Northlake Toronto Campus (site) and Toronto Research Hall (Eastern time, Canada, area in square
   metres), with a Node Contact on the campus. Lakeshore Boathouse: closed June 30, 2025, with two area rows.
   [02-sites-and-buildings.yaml](../stage-2-hierarchy/02-sites-and-buildings.yaml)
5. **Node Contact** on the Ridgeline Wind Site. Same file.
6. **Billing accounts.** SYN-GSH-A-0090001 (Canadian Dollar) and SYN-SGU-A-0020011 (the boathouse). The workbook
   carries the boathouse account's opening status only; add its closing status row by hand on the Status page.
   [01-billing-accounts.yaml](../stage-2-hierarchy/01-billing-accounts.yaml)
7. **Meter and point.** SYN-SGU-M-0050011, the boathouse gas meter (Open, then Removed July 15, 2025), and its
   register with Delta 1.037. [03-meters.yaml](../stage-2-hierarchy/03-meters.yaml),
   [04-points.yaml](../stage-2-hierarchy/04-points.yaml)
8. **Hierarchy filter.** Save the "Utility Meters" filter from the Nodes tree filter.
   [07-hierarchy-filters.yaml](../stage-2-hierarchy/07-hierarchy-filters.yaml)

## Stage 3. Gateways and data

All in Configuration Tool, Gateway Configuration. [02-gateways.yaml](../stage-3-gateways-and-data/02-gateways.yaml)

9. **Enable Data Gaps on:** NOAA-KSAC, NOAA-KSMF, NTP-BACNET-PLANT-HEADERS.
10. **Enable Late Intervals on**, with Next Batch Method set to the picker's daily entry: ASQ-VED-STUDENT,
    MV90-MDEF-VED-SCIENCE, FIG-CEDAR-ROW-A-UNITS. Write the method name you pick back into the YAML.
11. **Disable a node:** ASQ-VED-LAKEVIEW, node parameter IsEnabled 0.
12. **Disable a point:** node FIG-CAMPUS-SUBMETERS, point Lakeview Hall laundry, point parameter Disabled 1.

Not in this list: Stage 3 Step 5 (handheld) is unchanged apart from the High and Low warnings added yesterday, which
are already in the paste file.

## Still needed in built stages, not yet written

- Stage 3: a Town Center gateway node with 22 points, so Stage 7's tenant loads have a source.
- Stage 2: 248 billing accounts for the Cedar Row apartment submeters, which Stage 7's four Cedar Row allocation
  configurations need.
- Stage 1: a group holding the public dashboards permission, which Stage 9's public dashboard link needs.
