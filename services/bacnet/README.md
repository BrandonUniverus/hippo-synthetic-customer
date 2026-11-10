# Northlake BACnet source

This package serves the ten thermal points on Northlake gateway 6, nodes 10-12.
It provides three discoverable, read-only BACnet/IP devices. The Python producer
uses the existing Northlake canonical model; the protocol host uses BACnet 4.0.0,
the same client library as EnergyHippo. No database or broker is required.

Every object also reports its status (see "Status flags"), so the source is ready
for EnergyHippo to read `Status_Flags` beside Present_Value. Two devices answer
ReadPropertyMultiple and the third rejects it, so both the multiple-read path and
the one-read-per-property fallback can be tested.

The local Windows deployment uses **Ethernet 3, 172.21.29.4/20**, with discovery
on **UDP 47808** and device replies on **UDP 47820-47822**. This is the Workers
host's LAN adapter, not its VPN or WSL adapter. Recheck the address after a
network change. The subnet broadcast is 172.21.31.255.

## Required Northlake bindings

Use `LocalIpAddress=172.21.29.4` and `UdpPort=47808` for the BACnet task.
Clear the fictional `10.53.0.10` **BBMD Address** on all three nodes; clear the
BBMD port override where supported. This deployment uses local WhoIs/IAm
discovery and does not need a BBMD.

The original device instances exceed BACnet's 22-bit instance range. Apply these
three node changes through the normal Northlake configuration workflow:

| Node | Original instance | Source device instance | Unicast endpoint |
| --- | ---: | ---: | --- |
| 10, Science Center | 5301001 | **530101** | 172.21.29.4:47820 |
| 11, Recreation Center | 5301002 | **530102** | 172.21.29.4:47821 |
| 12, Plant Headers | 5301003 | **530103** | 172.21.29.4:47822 |

All point property reads use **85, Present_Value**, with no array index.
Existing object types, object instances and point identities stay as follows.
The full stable channel names are in [bindings.json](bindings.json).

| Node | PtID | Object type | Object instance | Quantity |
| --- | ---: | --- | ---: | --- |
| 10 | 34 | 2, Analog Value | 1001 | Science chilled-water ton-hours |
| 10 | 35 | 2, Analog Value | 1002 | Science chilled-water tons |
| 11 | 37 | 2, Analog Value | 1001 | Recreation chilled-water ton-hours |
| 11 | 38 | 2, Analog Value | 1002 | Recreation chilled-water tons |
| 12 | 448 | 2, Analog Value | 2001 | Plant chilled-water ton-hours |
| 12 | 449 | 2, Analog Value | 2002 | Plant chilled-water tons |
| 12 | 450 | 2, Analog Value | 2003 | Plant steam klb |
| 12 | 451 | 2, Analog Value | 2004 | Plant steam lb/hour |
| 12 | 452 | 0, Analog Input | 3001 | Steam header psig |
| 12 | 453 | 2, Analog Value | 2005 | Condensate kgal |

The package never writes installed bindings, enables a schedule or runs an EEM
acquisition. The implementation chat owns the Stage 3 binding edits and installed
acceptance.

## Windows startup and diagnostics

Use PowerShell 7, Python 3.13 and the .NET 10 SDK for setup. Run from the repository
root. Setup prepares `.runtime/venv`, publishes the server and, when an EnergyHippo
checkout is available, publishes the verification client. Normal startup needs
the .NET runtime and the Northlake checkout but not the EnergyHippo checkout.

```powershell
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Setup
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Start -LocalIpAddress 172.21.29.4
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Status
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Verify
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Stop
```

For a differently located product checkout, supply `-EnergyHippoRoot` to Setup.
Use `-ArtifactsPath` to direct disposable build output to a task-owned directory.
The published executables remain under `.runtime/server` and `.runtime/probe`.
Start is idempotent for a healthy instance on the same IP; incomplete or differently
bound instances require an explicit Stop. Stop validates PID, executable path and
creation time before stopping the owned process trees. It retains source state.

No Windows service or scheduled startup is installed. After a reboot, run Start.
Logs are `.runtime/producer.log`, `producer.err.log`, `server.log` and
`server.err.log`; a new start replaces those session logs. Durable source identity
and current values are under `.runtime/state`. `processes.json` records process
ownership. Status returns a nonzero exit code for stopped or stale processes.
If source facts, bindings or model identity change, the producer refuses to reuse
incompatible state. Stop the source and preserve the old state directory before
initializing a new one after review; it does not silently migrate its identity.

The running producer also stops itself when a file in the source fingerprint
changes: the generators, the source service, provider or bill data. Status then
reports it unhealthy. That is how the source went down on 2026-11-04, and it stayed
down until 2026-11-07. To restart, rename `.runtime/state` (the 11/04 state is kept as
`.runtime/state-v1-before-status-20261107`), then run Start.

The producer refreshes every 30 seconds, and the server emits health every 10
seconds. Present-value reads reject snapshots older than 120 seconds, more than
30 seconds in the future, from a different bindings hash, or with incorrect
native interval ends. Unknown objects and scalar array indexes return explicit
protocol errors. Writes are denied.

## Quantities and timestamp acceptance

Energy and volume are **last completed hour consumption**, not cumulative
registers. The paired rate is that hour's average, so ton-hours and tons have the
same numeric value for a one-hour interval. Pressure is sampled at the last
completed quarter hour. `values.json` records each source interval end in UTC.
Values derive from seed 104729 and the canonical model's anchored meter quantities.

Explicit synthetic operating assumptions in `bindings.json` are 5% chilled-water
distribution loss, 8% steam distribution loss, 75% condensate return, condensate
density 8.34 lb/gallon, and steam pressure 85 psig with a smooth +/-3 psig variation.
Plant steam sums the six modeled building deliveries before the loss adjustment.
These are new operational assumptions, not additional customer-provided facts.

**Installed timestamp acceptance remains necessary.** The current EEM collector
timestamps Present_Value at polling time, truncated to a minute. It does not
receive the source interval end through this scalar BACnet property. A poll just
after an hour boundary may also precede the producer's next refresh. Therefore
verify scheduling, archived timestamps and downstream interval treatment before
using these energy values for hourly reconciliation. An hourly task samples the
pressure only hourly; it does not create a complete 15-minute pressure history.

The source exposes Present_Value, the status properties below, object
identity/name/type, and the device's object list and Protocol_Services_Supported. It
is not a general building controller: no control writes, COV subscriptions,
trend-log history or BACnet conformance certification is claimed.

## Status flags

Each object answers `Status_Flags`, `Event_State`, `Out_Of_Service` and
`Reliability`. The producer writes them beside each value in `values.json`, so a
value and its status always change together. They follow BACnet's rules:

- **In alarm** whenever Event_State is not normal.
- **Fault** whenever Reliability is not no-fault-detected.
- **Overridden** and **out of service** come from the calendar below.

Status_Flags is a four-bit string in BACnet order: in alarm, fault, overridden, out
of service. So `0010` means overridden.

The calendar is `statusScenarios` in `bindings.json`, in campus (Pacific) time:

| Scenario | When | Objects | Status |
| --- | --- | --- | --- |
| `science-chiller-override` | Tuesdays 02:00-04:00 | Science chilled-water ton-hours and tons | Overridden |
| `recreation-flow-sensor-swap` | Wednesdays 10:00-11:00 | Recreation chilled-water ton-hours and tons | Out of service |
| `steam-header-transmitter-fault` | The 1st of each month, 06:00-07:00 | Steam header psig | Fault, Reliability no-sensor |

An interval is in a window when it lies wholly inside it. During a window each
listed object keeps reporting the value of the interval that ended when the window
opened (`hold`): an overridden, out-of-service or failed input no longer follows the
sensor. The steam header also has `highLimit` 87.9 psig. Above it, Event_State is
high-limit and the object is in alarm. With the modelled pressure this happens for
about half a day roughly once a week.

Devices 530101 and 530102 answer ReadPropertyMultiple. Their
Protocol_Services_Supported says so, and ALL and REQUIRED expand to the properties
above. Device 530103 rejects the service with UNRECOGNIZED_SERVICE, as a device
without it does.

EnergyHippo's collector reads only Present_Value today, so the status changes nothing
in EnergyHippo yet. Changing the calendar changes `bindings.json`, and with it the
source identity, so start on a new state directory (below).

## Container package

```powershell
docker compose -f services/bacnet/compose.yml build
```

On a native Linux deployment, set `NORTHLAKE_BACNET_IP` to an assigned LAN IPv4
address on that host before `docker compose ... up -d`. The server requires an
explicit address: automatic selection is ambiguous when several interfaces exist.
Use `docker compose -f services/bacnet/compose.yml ps` to inspect its health.

The images are `hippo-northlake-bacnet-values:local` and
`hippo-northlake-bacnet:local`. The values image extends the existing
`hippo-northlake-sources:local` image; build or load that image first. Optional
variables are `NORTHLAKE_SOURCE_IMAGE`, `NORTHLAKE_IMAGE_PREFIX` and
`NORTHLAKE_IMAGE_TAG`. This is its own `northlake-bacnet` Compose project and named
state volume. Existing source, identity and Mailpit deployments are independent.

Compose uses **native Linux host networking** so the source can participate in the
BACnet broadcast domain. A conventional published UDP port alone does not establish
WhoIs reachability across Docker Desktop's VM boundary. The supported local Windows
handoff is the native runner above. Linux deployment needs its own broadcast and
firewall acceptance on the target host; a successful image build is not that proof.

On November 4, 2026, a Docker Desktop host-network check bound the source to
192.168.65.3 and reported fresh values on all three devices. The Windows client
bound to 172.21.29.4 timed out in WhoIs, and the container recorded zero discoveries.
The same client successfully discovers the native Windows source. No Docker
Desktop network settings were changed during this check.

## Verification and acceptance boundary

```powershell
.\services\bacnet\.runtime\venv\Scripts\python.exe -B -m unittest services.bacnet.tests.test_producer -v
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Verify
.\services\bacnet\verify\Verify-FailureModes.ps1 -LocalIpAddress 172.21.29.4
```

The ten Python tests cover:

- canonical model integration;
- independently calculated loss and volume conversions;
- deterministic polling and repeated-hour UTC identity;
- invalid clock and configuration rejection;
- the status calendar: a window holds its opening value, keeps campus clock time across daylight saving, sets the
  out-of-service and fault flags, raises the high limit, and rejects invalid calendars.

The opt-in probe source-links EnergyHippo's unmodified `BacnetClient.cs`. It
discovers each device and compares all ten values to the snapshot after conversion
to BACnet REAL. It also checks write denial, unknown objects and invalid array
indexes by their returned protocol error codes.

It then reads the four status properties of every object, and ReadPropertyMultiple
(or its reject) from every device, with the BACnet library directly. The collector
doesn't read these yet.

Failure-mode verification creates a separate local source on UDP 47908/47920-47922.

- It serves a snapshot with one object overridden, one out of service, one in fault and one above its limit, and the
  probe reads each status back over the wire.
- It then tests stale, future, wrong-configuration and wrong-interval snapshots.

It stops that test process in `finally`, and does not alter the live source or EEM configuration.

On November 7 all ten Python tests passed. The live source answered all ten values
through the collector client and all ten objects' status properties. ReadPropertyMultiple
worked on 530101 and 530102, and 530103 rejected it. The isolated check served the four
non-normal statuses as `0010`, `0001`, `1100` and `1000`, and rejected all four bad
snapshots. Both .NET builds had zero warnings.

This establishes the real collector **client boundary** on the Windows Workers
host, without a database or broker. It does not run the complete collector task or
prove ingestion, archived timestamps, billing reconciliation or rendered EEM results.
Those remain Stage 3 acceptance steps after the binding delta is applied.

Local verification on November 4 passed all five Python cases, all ten real-client
reads, all three protocol-error checks per device, and all four snapshot-rejection
cases across the three isolated devices. Both scoped .NET builds completed with
zero warnings and errors. Controlled Stop/Start preserved identity and successful
reads; repeated Start retained the existing process ownership. The container and
native producer generated identical values at the fixed 2026-11-04T16:00:00Z clock.
Their source hashes identify different source-package revisions, so their state
directories are not interchangeable. Runtime evidence is in
`.runtime/verification.jsonl`, `.runtime/failure-verification.log` and
`.runtime/network-check/result.json`.
