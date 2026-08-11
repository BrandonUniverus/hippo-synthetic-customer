# Northlake Synthetic Identity Provider

This directory implements the realistic-provider portion of ADR-002a without
changing EnergyHippo. It runs a pinned Keycloak realm behind trusted localhost
HTTPS and derives all fictional users and groups from
[`security/northlake-eem-security-v1.yaml`](../security/northlake-eem-security-v1.yaml).
The same realm is a third-party-style OpenID Connect provider and SAML 2.0
Identity Provider (IdP).

## What is included

- Keycloak 26.7.0 with real login, account, consent, session, logout, and admin pages.
- PostgreSQL-backed users, sessions, realm configuration, and signing keys that
  survive an ordinary stop/start.
- Caddy 2.11.4 terminating HTTPS at `https://localhost:8443`, with a
  30-day localhost certificate beneath a 180-day intermediate CA.
- An unauthenticated, loopback-only configuration page for the ordinary
  provider name, realm, public URL, application URLs, and baseline OIDC/SAML
  registrations, with separate fictional-user and fictional-group pages.
- A small Northlake launchpad that establishes a provider session and directs
  the tester to EnergyHippo without handling passwords or tokens itself.
- 19 checked-in Northlake identities: 18 active and one deliberately disabled,
  plus ignored local additions managed through the Phase 2 page.
- 27 checked-in groups plus ignored local additions, editable synthetic
  membership, and claim shapes for company IDs and EEM permission-profile intent.
- Stable UUIDv5 user, group, role, client, scope, and realm IDs.
- Two bounded confidential OIDC profiles whose IDs, callbacks, post-logout
  callbacks, scopes, consent, PAR policy, client authentication, and access-token
  lifetime can be changed through the local configuration page:
  - Modern: authorization code with required PKCE `S256`, discovery, UserInfo,
    refresh rotation/revocation, and supported RP-initiated logout.
  - Historical Legacy: optional `id_token token` + `form_post` compatibility
    evidence that is explicitly not recommended for new providers.
- One exact SAML service-provider registration:
  - entity ID `urn:energyhippo:eemsuite-web:saml`;
  - HTTP-Redirect AuthnRequest input and forced HTTP-POST responses;
  - signed response and signed assertion using RSA-SHA256;
  - five-minute conditions, `OneTimeUse`, exact audience/ACS validation, and a
    deterministic persistent NameID;
  - SP-initiated login, IdP-initiated login, and SAML single logout;
  - Northlake user, group, company, and permission-profile attributes.
- Discovery, JWKS, UserInfo, refresh rotation and revocation, RP-initiated
  logout, PAR, administrator audit events, and deterministic reset.
- A focused configurable OIDC verifier that exercises the selected PAR and
  client-authentication branches, code + PKCE, configured consent, signed ID
  token, UserInfo, access-token lifetime, refresh rotation/revocation, logout,
  invalid redirect rejection, and the optional Historical Legacy `form_post` flow.
- A live SAML verifier that checks metadata and published signing certificates,
  rejects an unregistered ACS URL, validates both XML signatures and all
  security bindings, checks mapped attributes, exercises SP- and IdP-initiated
  login, performs signed single logout, proves the session ended, and rejects
  the disabled user.

The built-in Keycloak administration console is the initial admin page. This
repository does not reimplement passwords, sessions, consent, or user storage.

## Quick start

From the repository root:

```powershell
python -m pip install -r .\identity\requirements.txt
pwsh .\identity\scripts\Start-Identity.ps1
```

The first run:

1. creates `identity/.env` with cryptographically random local secrets;
2. generates the runtime realm from the checked-in security manifest;
3. starts PostgreSQL, Keycloak, the configuration service, and Caddy;
4. waits for HTTPS discovery;
5. copies the local CA certificate to `identity/.runtime/certs`;
6. executes the complete OIDC, SAML, and administration verifier.

The command does not silently change a machine trust store. Trust the local CA
once before using a browser or EEMSuite:

```powershell
pwsh .\identity\scripts\Trust-IdentityCertificate.ps1
```

Use `-StoreLocation LocalMachine` from an elevated terminal when EEMSuite runs
under IIS or another service account. The default `CurrentUser` store is enough
for a developer-launched process and browser.

Caddy's development root remains valid for ten years and persists in the
Compose-owned data volume. The 30-day localhost leaf and 180-day intermediate
renew automatically. This avoids the default 12-hour leaf rotation that can
leave a long-running browser holding an expired development certificate without
weakening certificate validation.

Then open:

- Northlake launchpad: `https://localhost:8443/`
- Local provider configuration: `https://localhost:8443/configure`
- OIDC profile configuration: `https://localhost:8443/configure/oidc`
- SAML profile configuration: `https://localhost:8443/configure/saml`
- Account/login: `https://localhost:8443/realms/northlake/account/`
- Realm admin: `https://localhost:8443/admin/northlake/console/`
- OIDC discovery: `https://localhost:8443/realms/northlake/.well-known/openid-configuration`
- SAML IdP metadata: `https://localhost:8443/realms/northlake/protocol/saml/descriptor`

## Local provider configuration

`https://localhost:8443/configure` is an intentionally unauthenticated Phase 1
tool for this loopback Docker environment. It renders its common fields from
`configuration/fields.json`, while the Python service remains authoritative for
typed validation and realm generation. The browser never receives Keycloak
administrator credentials and the service never writes to EnergyHippo.

Use **Refresh preview** to validate values and inspect a redacted provider
contract without changing runtime state. **Save** writes the values to the
ignored `identity/.runtime/configuration.json` file for the next ordinary
start. **Apply and reset realm** saves the values and reimports the single
disposable Keycloak realm, so current synthetic sessions and in-realm edits are
discarded. A public hostname or HTTPS port change is saved as pending and takes
effect after the normal stop/start scripts recreate the edge container.

The provider form deliberately covers only the common one-provider settings in
Phase 1. Synthetic users, groups, and bounded OIDC/SAML profiles have the separate
Phase 2 through Phase 5 surfaces below; multiple concurrent realms and a
bounded scenario JSON editor remain later ADR-002b phases. Do not expose the
configuration service on a shared or production network merely because this
localhost lab does not require an administrator login.

## Synthetic user management

`https://localhost:8443/configure/users` lists the checked-in fictional users
and lets a developer create or edit the small Phase 2 identity shape: username,
first and last name, fictional email, enabled state, and synthetic title. It
accepts only the repository's reserved example email domains and deliberately
has no password input, bulk import, or general attribute editor.

Creating a user or selecting **Generate new password** produces a random
development-only password and displays it once for copying. The record and its
credential are stored in ignored `identity/.runtime/users.json`; neither the
checked-in security manifest nor EnergyHippo is changed. Editing a checked-in
identity creates an override in the same ignored document. The persisted
synthetic user id remains the UUIDv5 subject seed across ordinary provider and
user applies.

Every user save regenerates the one disposable Keycloak realm. Current sessions,
consent, and manual in-realm edits are therefore discarded. New Phase 2 users
start without company, group, or permission assignments; Phase 3 adds those
claim-shaping relationships without implying EnergyHippo authorization.

## Synthetic group management

`https://localhost:8443/configure/groups` lists the 27 checked-in fictional
provider groups and lets a developer add, rename, or remove ignored local groups.
Checked-in group definitions remain immutable, while membership for either a
checked-in or local group can be changed through an ignored overlay. Local groups
have no company or permission-profile meaning by default.

The page previews the exact group value selected for the OIDC `groups` claim and
SAML `groups` attribute, plus the complete group list for a selected fictional
user. Every save regenerates the disposable realm. These provider memberships do
not create an EnergyHippo group, company assignment, permission, or user link.

To validate a generated user's real signed ID token, UserInfo response, and
signed SAML assertion against the same persisted membership without printing the
development password, run:

```powershell
pwsh .\identity\scripts\Test-IdentityGroupClaims.ps1 -Username samantha.ireland
```

Replace `samantha.ireland` with any enabled generated username. The verifier reads the
credential only from ignored generated realm state and never writes to
EnergyHippo.

## Bounded OIDC profile configuration

`https://localhost:8443/configure/oidc` is the Phase 4 control surface. It is
intentionally small: every field maps either to a Keycloak client behavior that
Northlake can prove or to an existing EnergyHippo System Administration branch.
It does not expose every Keycloak option and never writes EnergyHippo source,
configuration, or database state.

The configurable matrix is:

- EEM configuration mode: `Authority`, `Discovery`, or `Static`;
- PAR behavior: `UseIfAvailable`, `Require`, or `Disable`;
- token endpoint authentication: `ClientSecretPost` or `ClientSecretBasic`;
- access-token lifetime from 60 through 3,600 seconds;
- exact Modern and Historical Legacy client IDs, redirect URIs, post-logout
  redirect URIs, and bounded scopes;
- Modern provider consent on or off;
- Historical Legacy enabled or disabled.

**Refresh preview** validates the values and produces a secret-free,
ready-to-copy System Administration object. `Static` includes the explicit
authorization, token, issuer, JWKS, UserInfo, and introspection endpoints;
`Authority` and `Discovery` instead provide the appropriate metadata address.
Client-secret fields contain only the ignored local source location, never the
secret itself.

**Save** writes `identity/.runtime/oidc.json` without changing the current
realm. **Apply and verify** saves the same document, replaces the one disposable
realm, and immediately runs the focused verifier. Its persisted, secret-free
result is displayed on the page. A failed verifier is reported as a provider
contract break after the realm apply, which lets later phases deliberately show
unsupported or broken combinations instead of converting them into false
successes.

Run the same focused proof from the host with:

```powershell
pwsh .\identity\scripts\Test-OidcIdentity.ps1
```

The Modern profile is the default and the recommendation for new providers.
Historical Legacy exists only to reproduce already-existing implicit-flow
registrations. Disabling it removes the Keycloak client and records a controlled
skip in the focused verifier.

## Bounded SAML profile configuration

`https://localhost:8443/configure/saml` is the Phase 5 control surface for the
named `Standard` and `Saml2Int` profiles. Each profile has an exact EnergyHippo
provider key, SP entity ID, ACS/logout URL list, subject binding, claim allowlist,
authentication-context allowlist, unsolicited-response policy, and SLO policy.
Callbacks must end in `/saml/{providerKey}/acs` or
`/saml/{providerKey}/logout`; wildcard and root-level legacy callbacks are
rejected.

The generated preview includes the exact Northlake IdP metadata/entity/endpoints
and ready-to-copy EnergyHippo System Administration values, including derived SP
metadata URLs. It does not contain certificate bytes or private material.
`Standard` is enabled by default. Enabling `Saml2Int` requires uploading the
current public half of an EnergyHippo RSA credential. The local service accepts
PEM or DER X.509, validates RSA 2048+, rejects private-key text, and persists only
DER public certificate data in ignored `identity/.runtime/certs` state.

**Apply and verify** proves the Northlake provider contract. Standard exercises
metadata, exact ACS rejection, SP/IdP-initiated login, signatures, bindings,
allowlisted attributes, logout policy, unique IDs, and disabled-user denial.
Saml2Int proves that unsigned AuthnRequests are rejected and that an
IdP-initiated response is directly signed with exactly one AES-256-GCM assertion
encrypted by RSA-OAEP-11/SHA-256/MGF1-SHA256 to the selected public certificate.
Because Northlake never receives the private key, the page labels the installed
EnergyHippo signed-request/decryption path as separate required evidence instead
of claiming it passed.

Local values are stored in ignored `identity/.runtime/saml.json` and
`identity/.runtime/certs/saml2int-sp-public.cer`. Run the same provider-side proof
from the host with:

```powershell
pwsh .\identity\scripts\Test-SamlIdentity.ps1
```

## Northlake SSO launchpad

The root page is intentionally a launchpad rather than a second authentication
application:

1. **Sign in to Northlake** opens Keycloak's account console in a new tab. A
   successful login establishes the normal Northlake realm SSO session.
2. **Open EnergyHippo** sends the tester to `EEMSUITE_APPLICATION_HOME_URL`.
3. The tester chooses Northlake on EnergyHippo's third-party login page.
   EnergyHippo still starts and validates its own OIDC authorization request,
   but Keycloak can complete that request without another password prompt while
   the provider session remains valid.

The relying party must not force `prompt=login` or `max_age=0` when session
reuse is desired. Logout, session expiry, or a browser that does not carry the
Northlake cookie correctly requires authentication again.

This keeps the trust boundary realistic: the launchpad never sees a password,
authorization code, or token. A future Northlake customer website can be added
as a separate synthetic relying party with its own client and callback instead
of coupling API, upload, and webhook scenarios to the identity provider.

View the generated local credentials:

```powershell
pwsh .\identity\scripts\Get-IdentityStatus.ps1 -ShowSecrets
```

Secrets are stored only in ignored files:

- `identity/.env`
- `identity/.runtime/connection.json`
- `identity/.runtime/import/northlake-realm.json`

## OIDC connection profiles

`identity/.runtime/connection.json` contains ready-to-copy sectioned settings
under `eemsuiteConfiguration.modern` and, when enabled,
`eemsuiteConfiguration.legacy`. That ignored host file contains the generated
client secrets. The browser preview under `oidcConfiguration.profiles` is the
safe version for review and never contains them.

Start new-provider testing with Modern code + PKCE:

```json
{
  "OpenIDConnect": {
    "Description": "Northlake Synthetic Identity - modern",
    "ClientID": "eemsuite-web",
    "ClientSecret": "<generated>",
    "ResponseType": "code",
    "Scope": "openid profile email northlake",
    "DiscoveryEndpoint": "https://localhost:8443/realms/northlake/.well-known/openid-configuration",
    "ProtocolProfile": "Modern",
    "ParBehavior": "UseIfAvailable",
    "TokenEndpointAuthMethod": "ClientSecretPost"
  }
}
```

Use Historical Legacy only to reproduce an existing compatibility registration:

```json
{
  "OpenIDConnect": {
    "Description": "Northlake Synthetic Identity - historical legacy",
    "ClientID": "eemsuite-web-legacy",
    "ClientSecret": "<generated>",
    "ResponseType": "id_token token",
    "Scope": "openid profile email northlake",
    "DiscoveryEndpoint": "https://localhost:8443/realms/northlake/.well-known/openid-configuration",
    "ProtocolProfile": "Legacy",
    "ParBehavior": "Disable",
    "TokenEndpointAuthMethod": "ClientSecretPost"
  }
}
```

These files do not modify EnergyHippo configuration or its database. EEMSuite
still needs its existing third-party-login configuration and
`AuthenticationWithOpenIDConnectEnabled` database setting. Unknown external
identities still follow EEMSuite's existing link-to-an-EEM-user flow.

The first registered callback is `https://localhost:7310/signin-oidc`.
The generated clients also register:

- `https://localdev.energyhippo.com/Hippo/signin-oidc`
- `https://localhost/Hippo/signin-oidc`

`https://localhost:7310` is a verifier callback, not a permanently running
application. Keycloak's **Back to Application** link instead uses
`EEMSUITE_APPLICATION_HOME_URL`, which defaults to
`https://localdev.energyhippo.com/Hippo/`. The launchpad's **Open EnergyHippo**
action uses the same value. Change that ignored `.env` setting when another
EEMSuite origin is active.

Use `/configure/oidc` for exact callback, post-logout callback, and scope changes.
The `.env` values remain the defaults when no ignored Phase 4 document exists.
Wildcard callbacks are not used.

The development realm allows 30 minutes for the overall login and for each
individual login page. Once a login transaction has expired, a relying party
using one-time PAR must initiate a fresh authorization request; the provider
cannot safely replay the expired request.

## SAML service-provider contract

`identity/.runtime/connection.json` contains the provider endpoints and the
complete registrations under `clients.saml` (`Standard`) and, when enabled,
`clients.saml2Int`. The default registration is:

```json
{
  "entityId": "urn:energyhippo:eemsuite-web:saml:standard",
  "providerKey": "northlake-saml-standard",
  "validationProfile": "Standard",
  "identityProviderMetadata": "https://localhost:8443/realms/northlake/protocol/saml/descriptor",
  "singleSignOnService": "https://localhost:8443/realms/northlake/protocol/saml",
  "singleLogoutService": "https://localhost:8443/realms/northlake/protocol/saml",
  "assertionConsumerService": "https://localhost:7310/saml/northlake-saml-standard/acs",
  "serviceProviderLogout": "https://localhost:7310/saml/northlake-saml-standard/logout",
  "nameIdFormat": "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
  "responseBinding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
}
```

The first Standard ACS and logout URLs are verifier callbacks. The generated
clients also register EEMSuite's real dynamic-provider routes:
`/Hippo/saml/{providerKey}/acs`, `/metadata`, and `/logout`. Use
`/configure/saml` to change these exact values. The named
`EEMSUITE_SAML_STANDARD_*` or `EEMSUITE_SAML2INT_*` variables remain defaults
when no ignored Phase 5 document exists. Exact URLs are intentional; no wildcard
SAML callbacks are registered.

The EEMSuite implementation should treat the following as mandatory validation,
not merely claim parsing:

- load the IdP entity ID and signing certificates from metadata over trusted
  HTTPS;
- require a valid RSA-SHA256 signature on both the `Response` and `Assertion`;
- trust only the XML nodes returned by signature verification to prevent
  signature-wrapping mistakes;
- match `Destination`, bearer `Recipient`, and `Audience` to the configured
  EEMSuite endpoints/entity ID;
- correlate `InResponseTo` to a locally issued AuthnRequest for SP-initiated
  login and preserve `RelayState`;
- enforce `NotBefore`, `NotOnOrAfter`, `SubjectConfirmationData`, issuer,
  success status, and a small clock-skew allowance;
- reject replayed response/assertion IDs and honor `OneTimeUse`;
- use `(IdP entity ID, persistent NameID)` as the external SAML identity key;
- create the EEMSuite application session only after all protocol validation
  and the existing external-user assignment/linking step succeeds.

The assertion maps these attributes:

- `username`, `email`, `given_name`, and `family_name`;
- `groups`;
- `synthetic_user_id`, `primary_company_id`, `title`, and `synthetic_status`;
- `eem_company_ids` and `eem_permission_profiles`;
- `realm_roles`.

Keycloak's built-in admin console is the settings/user administration surface.
It can be used to disable users, alter mappings, change signature behavior, or
add negative-test clients without building a second identity application.

### Named interoperability profiles

`EEMSUITE_SAML_PROFILES=Standard` is the safe default. It produces a plaintext
assertion client whose Response and assertion are both signed. The EEMSuite
`Standard` validator may accept its documented response-, assertion-, or
dual-signature shapes; this synthetic client deliberately uses the strongest
dual-signature baseline.

To exercise the pinned SAML2Int profile, first configure an EnergyHippo RSA
service-provider credential that supports signing and encryption, export only
its public X.509 certificate, then enable Saml2Int and upload that public file at
`/configure/saml`.

Realm generation then creates a separate `northlake-saml2int` client that
requires signed AuthnRequests and emits encrypted assertions. Missing, malformed,
or non-RSA certificates fail generation. The private key never leaves EEMSuite
and is never written to this repository or the Keycloak connection profile.
Artifact binding and ECP remain disabled; both profiles use HTTP-POST responses.

## Operations

### Status and credentials

```powershell
pwsh .\identity\scripts\Get-IdentityStatus.ps1
pwsh .\identity\scripts\Get-IdentityStatus.ps1 -ShowSecrets
```

### Focused live verification

```powershell
pwsh .\identity\scripts\Test-Identity.ps1
```

Run only the bounded OIDC profile matrix currently installed in the realm:

```powershell
pwsh .\identity\scripts\Test-OidcIdentity.ps1
```

To verify the Northlake SAML provider without being blocked by an unrelated OIDC
regression, run the SAML suite independently:

```powershell
pwsh .\identity\scripts\Test-SamlIdentity.ps1
```

For Standard, that command performs the complete provider proof described above.
When Saml2Int is enabled, it also proves public-certificate binding, secure
encryption shape, and unsigned-request rejection. It deliberately records the
installed EnergyHippo signed-request and private-key decryption proof as a gap;
only the supported EnergyHippo runtime can supply that evidence.

## Future SCIM 2.0 test integration

SCIM should remain separate from the Keycloak login protocols. EnergyHippo will
be the SCIM service provider; Northlake should act like the customer's Entra
provisioning client and drive repeatable `/Users` and `/Groups` sequences into
it. The proposed boundary, mappings, negative cases, and cross-protocol
provision-then-SAML-login scenario are captured in
[SCIM-2.0-TESTING.md](SCIM-2.0-TESTING.md).

### Stop and restart without changing state

```powershell
pwsh .\identity\scripts\Stop-Identity.ps1
pwsh .\identity\scripts\Start-Identity.ps1
```

The database, realm, subjects, sessions, signing keys, and Caddy CA persist.

### Rotate the identity signing key

```powershell
pwsh .\identity\scripts\Rotate-IdentitySigningKey.ps1
```

The script creates a higher-priority RS256 provider through Keycloak's
authenticated Admin REST API, verifies that the new key is active, verifies that
the previous key remains passive and published in JWKS, records the result under
`identity/.runtime`, and reruns the complete OIDC/SAML verifier. The SAML portion
also proves that IdP metadata publishes a certificate that validates newly
signed responses. Reset returns the realm to one generated signing key.

### Deterministic realm reset

```powershell
pwsh .\identity\scripts\Reset-Identity.ps1
```

Reset removes only the Compose-owned PostgreSQL volume after checking its
ownership labels. It preserves the Caddy CA, regenerates the realm from the
manifest, starts the stack, and reruns verification. PowerShell confirmation is
required because user and session state is intentionally destroyed.

### Remove local CA trust

```powershell
pwsh .\identity\scripts\Untrust-IdentityCertificate.ps1
```

The script removes only the thumbprint recorded when this stack installed its
development CA.

### Replace all local secrets

```powershell
pwsh .\identity\scripts\Initialize-Identity.ps1 -Force
pwsh .\identity\scripts\Reset-Identity.ps1
```

Both commands require confirmation. Existing EEMSuite client configuration must
be updated from the new `connection.json`.

### Backup and upgrade

For disposable workstation use, the checked-in manifest/generator plus the
ignored `.env` are the reset source of truth. Do not commit database dumps,
exported realms, credentials, or the Caddy CA.

For a long-lived shared environment, back up all three of these before an
upgrade:

- the PostgreSQL database using the organization's normal PostgreSQL tooling;
- the ignored `.env` in an approved secret store;
- the Caddy data volume, because replacing its local CA invalidates existing
  machine trust.

Upgrades are deliberate source changes: update both the image tag and immutable
digest in `compose.yml`, review the applicable Keycloak upgrade guide, start the
existing database, and run the complete verifier. Also prove ordinary restart
and signing-key rotation before promoting the new image. Never replace a pinned
image with `latest`. Use reset instead of migration only when discarding all
synthetic admin edits and sessions is acceptable.

## Shared development machine

The defaults bind only to `127.0.0.1`. For a shared machine:

1. assign a stable DNS name;
2. change `IDENTITY_HOST`, `IDENTITY_PUBLIC_BASE_URL`, and
   `IDENTITY_BIND_ADDRESS=0.0.0.0` in the ignored `.env`;
3. replace or distribute Caddy's development CA according to the development
   network's trust policy;
4. use exact shared-environment OIDC callback, SAML ACS, and SAML logout URIs;
5. keep the admin console and credentials restricted to the development network.

The issuer hostname and port must be identical from the browser, EEMSuite host,
and any containerized test client. Changing the issuer is a new identity
environment and changes the correct external identity key from `(old iss, sub)`
to `(new iss, sub)`.

## Source and generated-state contract

Checked-in sources:

- `security/northlake-eem-security-v1.yaml`: users, enabled state, companies,
  groups, permission intent, and validation counts.
- `realm/generate_realm.py`: protocol, client, claim, lifetime, and stable-ID rules.
- `configuration/fields.json`: presentation metadata for the Phase 1 form.
- `configuration/settings.py`: typed configuration validation and generated contract.
- `configuration/oidc.py`: bounded OIDC profile validation, ignored-document contract,
  and secret-free EnergyHippo System Administration preview.
- `configuration/users.py`: typed fictional-user validation and ignored overlay storage.
- `configuration/groups.py`: typed fictional-group and membership overlay storage.
- `configuration/server.py`: loopback configuration API and disposable-realm apply boundary.
- `scripts/verify_oidc_baseline.py`: focused Modern and Historical Legacy live proof.
- `compose.yml`: immutable container versions and deployment boundary.
- `Caddyfile`: HTTPS and proxy boundary.

Ignored generated state:

- secrets;
- import JSON containing those secrets and test credentials;
- connection profiles;
- the saved local provider configuration document;
- the saved local OIDC profile document and focused verification result;
- local synthetic-user overrides and their generated development passwords;
- local synthetic-group additions and checked-in-group membership overrides;
- copied development CA;
- PostgreSQL and Caddy Docker volumes.

Passwords remain outside the security manifest. The realistic provider never
writes directly to an EEM database.

## Automated tests

Realm generation:

```powershell
python -m unittest discover -s .\identity\tests -v
```

Static Python compilation:

```powershell
python -m compileall -q .\identity
```

Compose expansion:

```powershell
docker compose --project-directory .\identity --env-file .\identity\.env -f .\identity\compose.yml config --quiet
```

Live provider:

```powershell
pwsh .\identity\scripts\Test-Identity.ps1
pwsh .\identity\scripts\Test-IdentityGroupClaims.ps1 -Username samantha.ireland
```

The live provider verification is intentionally independent of EnergyHippo. Its
job is to prove the provider is realistic and internally coherent so any next
failure observed in an EEMSuite browser round trip belongs to the RP,
configuration, certificate trust, or EEM user-linking path rather than a
half-working mock provider.
