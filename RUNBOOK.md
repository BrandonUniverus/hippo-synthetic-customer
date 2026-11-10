# Northlake runbook

Bring the Northlake environment up on one Windows machine and check it. Run
every command from the repository root in PowerShell 7 unless a step says
otherwise. The service READMEs keep the detail:
[identity](identity/README.md), [sources](services/sources/README.md),
[handheld](services/handheld/README.md), [historian](services/historian/README.md),
[BACnet](services/bacnet/README.md).

| Piece | Runs as | Address | State kept in |
| --- | --- | --- | --- |
| Identity: Keycloak, PostgreSQL, Caddy, configuration, customer site | Docker project `hippo-synthetic-identity` | `https://localhost:8443`, `https://customer.localtest.me:8443` | Volumes `postgres-data`, `caddy-data`, `caddy-config`; ignored `identity/.env` and `identity/.runtime/` |
| Northlake site and brand gallery | Served by the identity Caddy | `https://localhost:8443/`, `https://localhost:8443/brands/`; utility pages at `/utilities/`, meter reading at `/meter-reading/` | The repository (`identity/portal`, `brands`, `documents`) |
| Source bundle: producer and web | Docker project `northlake-sources` | `http://localhost:18081` (in the site at `/utilities/`) | Volume `source-data` |
| Handheld simulator | Same project, profile `handheld` | `http://localhost:18082` (in the site at `/meter-reading/`) | Volume `handheld-state` |
| ODBC historian | Same project, profile `historian` | An Access file, `services/sources/historian-output/northlake-historian.accdb` unless `NORTHLAKE_HISTORIAN_ROOT` moves it | That file |
| Mailpit | Docker, from the energyhippo repository's local services | UI `http://localhost:8587`, SMTP `localhost:1587` | Volume `mailpit_data` |
| BACnet source | Native Windows processes | `172.21.29.4`, UDP 47808 and 47820-47822 | `services/bacnet/.runtime/` |
| Energy Hippo, Northlake instance | Installed (IIS) | `https://northlake.energyhippo.com/Hippo` | Database `EEMSuite_Northlake` |

## 1. Install once

1. Install Docker Desktop for Windows (WSL 2 engine), PowerShell 7, Python 3.13
   and, for BACnet setup only, the .NET 10 SDK.
2. Check that both answer:

   ```powershell
   docker version
   docker compose version
   ```

3. Install the identity scripts' Python packages:

   ```powershell
   python -m pip install -r .\identity\requirements.txt
   ```

## 2. Identity stack and the Northlake site

1. Start it. The first run creates `identity/.env` with random secrets,
   generates the realm, starts five containers and runs the OIDC and SAML
   verifier:

   ```powershell
   pwsh .\identity\scripts\Start-Identity.ps1
   ```

2. Trust its certificate once. Run it again from an elevated shell with
   `-StoreLocation LocalMachine` so Energy Hippo under IIS trusts it too:

   ```powershell
   pwsh .\identity\scripts\Trust-IdentityCertificate.ps1
   ```

3. Check: `https://localhost:8443/` opens the Northlake site without a
   certificate warning, and `Get-IdentityStatus.ps1` reports healthy:

   ```powershell
   pwsh .\identity\scripts\Get-IdentityStatus.ps1
   ```

4. Point it at the Northlake instance (once). Each page below keeps its own
   settings, and the OIDC and SAML pages hold the lists the clients get. Each
   apply regenerates the realm: users and their password stay, current Keycloak
   sessions end and the realm signing key changes. So do this before step 2.5;
   after any later apply, refresh the provider's metadata in Energy Hippo and
   approve it if asked.
   - `https://localhost:8443/configure`: set the Energy Hippo application home URL
     to `https://northlake.energyhippo.com/Hippo/`, then **Apply and reset realm**.
   - `/configure/oidc`: add the redirect URI
     `https://northlake.energyhippo.com/Hippo/signin-oidc` (and
     `.../signin-oidc/<provider key>` for a provider with its own callback) and
     the post-logout URI `https://northlake.energyhippo.com/Hippo/signout-callback-oidc`,
     then **Apply and verify**.
   - `/configure/saml`: put `https://northlake.energyhippo.com/Hippo/saml/northlake-saml-standard/acs`
     first in the ACS URLs and `.../logout` first in the logout URLs, then
     **Apply and verify**. Keycloak sends IdP-initiated sign-ins and logout
     responses to the first of each.
5. Add the Northlake provider in Energy Hippo (once, as an Energy Hippo
   administrator, in **Manage access**, `#/SecurityAdministration`). Copy the
   values from the **Ready-to-copy EEM values** card on `/configure/saml`.
   1. **Identity realms**, **Add realm**: enabled, discovery **Local provider
      chooser**, **Default login realm** on.
   2. **SAML 2.0 providers**, **Add SAML provider** in that realm: key
      `northlake-saml-standard`, service-provider entity ID
      `urn:energyhippo:eemsuite-web:saml:standard`, validation profile Standard,
      persistent NameID, single logout on, and the card's claims and
      authentication context. How Energy Hippo matches a Northlake user to its
      own user is Energy Hippo's choice.
   3. Its **Metadata source**: **Remote entity metadata**, expected entity ID
      `https://localhost:8443/realms/northlake`, address
      `https://localhost:8443/realms/northlake/protocol/saml/descriptor`,
      **Require signed metadata** off (Keycloak does not sign it; HTTPS trust
      comes from step 2.2), allowed single sign-on destination
      `https://localhost:8443/realms/northlake/protocol/saml`. Then **Approve
      pending metadata**.
   4. **Rotate credential** once: Energy Hippo needs a current service-provider
      credential before it enables a SAML provider.
   5. **Enable** the provider, and turn on `ExternalAuth.EnableThirdPartyLogins`.
6. Set the Northlake site's links in the ignored `identity/.env`, then recreate
   Caddy (step 2.8):
   - `NORTHLAKE_EEM_PROVIDER_KEY`: the Northlake provider's key in Energy Hippo
     (default `northlake-saml-standard`; use the OIDC provider's key to test OIDC);
   - `NORTHLAKE_PUBLIC_DASHBOARD_ID`: a dashboard made public in Energy Hippo, or
     leave it empty to hide the dashboard links;
   - `NORTHLAKE_SOURCES_URL`: the utility pages (default `/utilities`, the source
     bundle served through the site);
   - `NORTHLAKE_SOURCES_UPSTREAM` and `NORTHLAKE_HANDHELD_UPSTREAM`: where Caddy
     finds the bundle and the handheld (default `host.docker.internal:18081` and
     `:18082`).
7. Check a shortcut. **Open Energy Hippo** on the site points at
   `https://northlake.energyhippo.com/Hippo/Account/ExternalAutoLogin?provider=northlake-saml-standard&returnRoute=%23%2FHome`.
   Clicking it shows the Northlake sign-in (or nothing, with a Northlake session)
   and then the Energy Hippo home page.
8. After editing `identity/Caddyfile`, `identity/compose.yml` or the `.env`
   values Caddy reads, recreate Caddy through the identity scripts so the saved
   `/configure` settings still apply:

   ```powershell
   . .\identity\scripts\Identity.Common.ps1
   Invoke-IdentityCompose up --detach --no-deps --force-recreate caddy
   ```

   After editing the configuration pages or the customer lab, rebuild those two
   images the same way: `Invoke-IdentityCompose up --detach --no-deps --build configuration customer-site` (use `--detach`, not `-d`: PowerShell binds `-d` to `-Debug` and compose then stays attached; `--no-deps` leaves Keycloak running).
   Brand and theme edits (`brands/`, `identity/branding/`, `identity/themes/`,
   `identity/portal/`) are live on refresh; bump `assetVersion` in
   `identity/themes/northlake/login/theme.properties` after a sign-in CSS change.
9. Day to day, these keep every user, key and session:

   ```powershell
   pwsh .\identity\scripts\Stop-Identity.ps1
   pwsh .\identity\scripts\Start-Identity.ps1
   ```

## 3. Source bundle

1. After a reboot the producer and web come back by themselves
   (`restart: unless-stopped`). After a `stop`, bring them back without
   recreating anything:

   ```powershell
   docker compose -f services/sources/compose.yml start producer web
   ```

2. First time only, when the containers do not exist yet:

   ```powershell
   docker compose -f services/sources/compose.yml up -d producer web
   ```

3. Check: `docker compose -f services/sources/compose.yml ps` shows both
   healthy, `http://localhost:18081/health/ready` answers, and
   `http://localhost:18081/catalog.json` names the running release.
4. Deeper checks when needed:

   ```powershell
   docker compose -f services/sources/compose.yml run --rm producer status
   docker compose -f services/sources/compose.yml run --rm producer verify
   ```

> **Never add `--build` here and never run `build` for the producer.** Its
> `source_fingerprint` covers the generators, bills, provider data and the
> bill and PDF renderers. A rebuilt producer whose fingerprint differs stops
> publishing on the existing volume: a rebuild is a new release with a new
> state volume, and the handheld then needs a new pin. The site already shows
> the bundle's pages in today's Northlake look at `/utilities/`; restyling the
> bundle's own copies, the bills and Northlake's PDFs waits for that release.

## 4. Handheld simulator

1. Start the existing container, or create it the first time:

   ```powershell
   docker compose -f services/sources/compose.yml --profile handheld start handheld
   docker compose -f services/sources/compose.yml --profile handheld up -d --no-deps handheld
   ```

2. Check: `https://localhost:8443/meter-reading/` (or `http://localhost:18082/`)
   opens, and status reports the source release:

   ```powershell
   docker compose -f services/sources/compose.yml exec handheld python -m services.handheld status
   ```

3. After editing `services/handheld`, `identity/branding` or `brands/northlake`,
   rebuild only the handheld. Its rounds stay in its volume:

   ```powershell
   docker compose -f services/sources/compose.yml --profile handheld up -d --build --no-deps handheld
   ```

## 5. ODBC historian

An Access database of the Library's half-hourly readings, which the Stage 3 ODBC
gateway reads. [Its README](services/historian/README.md) has the detail.

1. Start the existing container, or create it the first time. Its image derives
   from the source image, so create it after the source bundle:

   ```powershell
   docker compose -f services/sources/compose.yml --profile historian start historian
   docker compose -f services/sources/compose.yml --profile historian up -d --build --no-deps historian
   ```

2. The file lands in `services\sources\historian-output`. To put it where the
   Workers service can read it, set `NORTHLAKE_HISTORIAN_ROOT` (for example
   `C:\ProgramData\EEM Suite\NorthLake\Historian`) and run the `up` line again.
3. Check: `docker compose -f services/sources/compose.yml --profile historian ps historian`
   shows it healthy (the file is under 65 minutes old), and its log ends with a
   `published` line.
4. Energy Hippo reads the file through the Access ODBC driver, but only with the
   profile fix built (ODBC profiles send their additional connection parameters).
   The profile's values are in the settings table at the end.

## 6. Mailpit

```powershell
docker compose -f C:\Hippo\Git\univerus\energyhippo\BuildScripts\Local\Docker\local-services-docker-compose.yml up -d mailpit
```

Check: `http://localhost:8587` shows the inbox. SMTP is `localhost:1587` with
STARTTLS; the user and development password are in that compose file.

## 7. BACnet source (native, not Docker)

Docker Desktop cannot carry BACnet broadcast, so this one runs natively.

1. Once:

   ```powershell
   .\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Setup
   ```

2. After every reboot:

   ```powershell
   .\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Start -LocalIpAddress 172.21.29.4
   ```

3. Check: `-Action Status` exits 0 and `-Action Verify` reads all ten values and
   their status properties.
4. If the network changed, confirm the address first, then Stop and Start with
   the new one and update the Energy Hippo schedule:

   ```powershell
   Get-NetIPAddress -InterfaceAlias 'Ethernet 3' -AddressFamily IPv4
   ```

5. The producer stops itself when a file in the source fingerprint changes (the
   generators, the source service, provider or bill data), and Status then reports
   it unhealthy. A changed `services/bacnet/bindings.json` also needs a fresh start.
   Either way, rename `services/bacnet/.runtime/state` to keep it, then Start again.

## 8. Deliver source files to a gateway

Each Stage 3 schedule reads `<RootDirectory>\Input`, with RootDirectory
`C:\ProgramData\EEM Suite\NorthLake\Gateways\<profile>`. Mount the root and
deliver into `Input`, so the receipt ledger sits beside it. For example, one day
of Student Center AcquiSuite files:

```powershell
$env:NORTHLAKE_DELIVERY_ROOT = 'C:\ProgramData\EEM Suite\NorthLake\Gateways\AcquiSuite'
docker compose -f services/sources/compose.yml --profile delivery run --rm deliver deliver --state /state --source gw_acquisuite_student_electric --day 2024-01-02 --destination /delivery-root/Input
```

A file Energy Hippo consumed is never delivered again; a replay needs
`--replay`. Not yet run against the ProgramData folders on this machine.

## 9. Health check

| Check | Expect |
| --- | --- |
| `docker ps` | Five identity containers, producer, web, handheld and historian healthy, Mailpit |
| `https://localhost:8443/` | The Northlake site, no certificate warning |
| `https://localhost:8443/brands/` | The seven brand systems |
| `https://localhost:8443/utilities/providers/valley-electric-district/` | A utility page in the Northlake look |
| `https://localhost:8443/meter-reading/` | Meter reading, "Source ready" with the running release |
| `http://localhost:18081/health/ready` | 200 |
| `http://localhost:18082/health/ready` | 200 |
| `http://localhost:8587` | Mailpit inbox |
| `Run-NorthlakeBacnet.ps1 -Action Status` | Exit code 0 |
| `https://northlake.energyhippo.com/Hippo` | Energy Hippo sign-in, Northlake provider listed |

## 10. Stop (state is kept)

```powershell
pwsh .\identity\scripts\Stop-Identity.ps1
docker compose -f services/sources/compose.yml --profile handheld --profile historian stop
.\services\bacnet\Run-NorthlakeBacnet.ps1 -Action Stop
docker compose -f C:\Hippo\Git\univerus\energyhippo\BuildScripts\Local\Docker\local-services-docker-compose.yml stop mailpit
```

Never use `down -v`: it deletes the volumes that hold users, keys, generated
history and handheld rounds.

## 11. Restore the portable seed database (ADR-002c, package P8)

Placeholder. P8 is the portable release rehearsal: a pinned Compose bundle, a
populated database and content package, and a restore runbook. This step will
restore `EEMSuite_Northlake` and its companion content, then start the stacks
above against their matching volumes. To be written when P8 exists.

## Energy Hippo settings and what they point at

What each setting should be. Check the Northlake instance itself; this runbook
does not read its database.

| Energy Hippo setting (where) | Points at | Value |
| --- | --- | --- |
| Third-Party Identity, OIDC provider (Security Administration) | Keycloak | Discovery `https://localhost:8443/realms/northlake/.well-known/openid-configuration`; client `eemsuite-web`; secret from `Get-IdentityStatus.ps1 -ShowSecrets` |
| Manage access, identity realm and SAML provider `northlake-saml-standard` (step 2.5) | Keycloak | IdP metadata `https://localhost:8443/realms/northlake/protocol/saml/descriptor`, entity `https://localhost:8443/realms/northlake`; SP entity `urn:energyhippo:eemsuite-web:saml:standard` |
| Keycloak side of both (`/configure`) | Energy Hippo | The Northlake callbacks in step 2.4 |
| `ExternalAuth.EnableThirdPartyLogins` | | On, for SSO and the site's shortcuts |
| A provider's **Allow unsolicited responses** | | On only to test IdP-initiated SAML, which lands on the home page |
| SCIM provisioning connection, paired with `/configure/scim` | Energy Hippo's SCIM endpoint | `https://northlake.energyhippo.com/Public/scim/v2` |
| Stage 3 file schedules, RootDirectory | Delivered source files | `C:\ProgramData\EEM Suite\NorthLake\Gateways\<profile>`, reading `Input` |
| MV90 MDEF/MV9 nodes, FIG schedules | Source timestamps | `TimeStampType=Utc`; Ridgeline keeps `OffsetTimeMinutes=480` |
| BACnet schedule and nodes 10-12 | Native BACnet source | `LocalIpAddress=172.21.29.4`, `UdpPort=47808`; device instances 530101-530103 at ports 47820-47822; BBMD cleared |
| Handheld gateways (Neptune, MVRS) | Handheld returns | `Sync-HandheldReturn.ps1` into `C:\ProgramData\EEM Suite\NorthLake\Gateways\Neptune` or `MVRS` |
| ODBC profile `SyntheticCustomerHistorian` (Profile Manager) and node ODBC-LIBRARY-HISTORIAN | The historian's Access file (step 5) | ODBC, driver `Microsoft Access Driver (*.mdb, *.accdb)`, additional connection parameters `DBQ=<the file>;ReadOnly=1`, Windows authentication off. Needs the profile fix built. Node parameters and the Access query: [historian README](services/historian/README.md) |
| System Constants, SMTP settings | Mailpit | `localhost:1587`, STARTTLS |
| Utility Provider websites | Fictional hosts | `www.valleyelectric.example` and the rest; the pages live at `http://localhost:18081/providers/<slug>/`. Mapping those hosts is still open. |

## When something is off

- **Certificate warning at 8443:** run `Trust-IdentityCertificate.ps1` again
  (LocalMachine for IIS).
- **A shortcut on the site lands on the Energy Hippo sign-in page:** the
  provider key in `NORTHLAKE_EEM_PROVIDER_KEY` does not match an enabled,
  visible provider in an enabled default login realm, or third-party logins
  are off (step 2.5).
- **Keycloak says the redirect URI or ACS is invalid:** the Energy Hippo
  callback is missing from `/configure/oidc` or `/configure/saml` (step 2.4).
- **Keycloak locks a user** after two failed sign-ins within a second; wait, or
  clear it in the admin console.
- **Producer unhealthy:** `docker compose -f services/sources/compose.yml logs producer`.
  A "changed input" message means someone rebuilt the image; see step 3.
- **Historian unhealthy:** `docker compose -f services/sources/compose.yml --profile historian logs historian`.
  If it refuses the source release at start, its image was built from another
  source image; build it again (step 5).
- **BACnet discovery times out:** the Ethernet 3 address changed; see step 7.
