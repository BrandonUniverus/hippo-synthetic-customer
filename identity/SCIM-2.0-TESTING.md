# Northlake SCIM 2.0 Test Integration

**Status:** Integration design only; no SCIM endpoint or client is implemented
in this change.

## Decision

Keep SCIM provisioning separate from the Northlake Keycloak OIDC/SAML identity
provider.

EnergyHippo will be the SCIM 2.0 service provider. A future harness in this
repository will act as the Northlake customer's provisioning client, in the
same role as Microsoft Entra. It will send deterministic `User` and `Group`
operations to EnergyHippo and verify both the SCIM responses and the resulting
login behavior.

This matches the protocol roles in the SCIM core schema and HTTP protocol:

- [RFC 7643](https://www.rfc-editor.org/rfc/rfc7643.html) defines the JSON
  schemas for users, groups, discovery, and extensions.
- [RFC 7644](https://www.rfc-editor.org/rfc/rfc7644.html) defines the HTTP
  operations, filtering, pagination, PATCH, errors, and bulk behavior.

Keycloak continues to answer only the authentication question: "did Northlake
authenticate this subject?" SCIM answers the lifecycle question: "which EEM
account, company memberships, and permission groups should exist now?"

## Proposed test boundary

```text
Northlake manifest
  +-- generates Keycloak users/groups ----> OIDC and SAML login
  +-- generates SCIM fixtures ------------> Northlake SCIM runner
                                               |
                                               v
                                      EnergyHippo /scim/v2
                                               |
                                               v
                                  shared EEM identity/permission data
```

The SCIM service belongs in the product-owned API/application-service layer so
the Web login flow and API provisioning endpoint use the same identity records.
The public route may be exposed through the Web host or reverse proxy, but it
must not create a second Web-only user store.

## Tenant and company binding

Company context should be bound to the SCIM provisioning connection, not
accepted from an arbitrary SAML/OIDC scope or a caller-controlled user field.

For each customer connection EnergyHippo should issue or configure:

- a tenant-specific SCIM base URL;
- a revocable bearer credential stored as a secret;
- the allowed EEM company or company set;
- explicit SCIM-group-to-EEM-member-group mappings;
- an audit identity and rate-limit policy.

The Northlake runner should receive those values through ignored local
configuration. No bearer token belongs in the checked-in manifest, logs, test
snapshots, or generated reports.

## Stable identity and mapping

| SCIM value | Northlake fixture | EnergyHippo meaning |
|---|---|---|
| `User.externalId` | Stable Northlake/Entra-style object ID | Provider-scoped correlation key; never a username |
| `User.userName` | `samantha.ireland` | Human login/display identifier, subject to normalization rules |
| `User.active` | Manifest status | Enables or disables the EEM account without deleting audit history |
| `User.name` / `emails` | Manifest contact fields | EEM contact data according to mutability policy |
| `Group.externalId` | Stable Northlake group ID | Provider-scoped group correlation key |
| `Group.displayName` | Northlake group name | Lookup input for an administrator-approved EEM mapping |
| `Group.members` | Stable SCIM user IDs | Company membership and permission-group assignments through the mapping |

EnergyHippo should generate and return its own stable SCIM `id`. Repeated
requests correlate through `(provisioning connection, externalId)`; SAML login
correlates separately through `(IdP entity ID, persistent NameID)`. Both links
point at the same internal EEM user rather than being treated as interchangeable
external identifiers.

## First executable scenario

The highest-value end-to-end test is:

1. Read `/ServiceProviderConfig`, `/ResourceTypes`, and `/Schemas`.
2. `POST /Users` for Samantha and retain EnergyHippo's returned `id` and
   `meta.version`.
3. Filter with `GET /Users?filter=userName eq "samantha.ireland"` and prove the
   same resource is returned.
4. `POST /Groups` for the configured company-admin mapping and add Samantha by
   SCIM `id`.
5. Authenticate Samantha through Northlake SAML and prove the pre-provisioned
   EEM account is used with the mapped permissions.
6. `PATCH /Users/{id}` with `active=false`.
7. Repeat the valid SAML authentication and prove EnergyHippo denies the local
   application session because the provisioned account is inactive.

This separates authentication success from application authorization and
deprovisioning, which is the real integration risk.

## Required runner coverage

The Northlake runner should add scenarios in this order:

1. Discovery, content types, schema URNs, and authentication failures.
2. User create/read/filter/replace/PATCH/deactivate and idempotent retry.
3. Group create, membership add/remove, pagination, and mapped permissions.
4. Duplicate `externalId` and `userName`, unsupported filters, malformed PATCH,
   stale version, missing member, and cross-tenant isolation.
5. `429`/`5xx` retry behavior, out-of-order operations, repeated DELETE, and
   concurrent membership changes.
6. Cross-protocol reconciliation with both SAML and OIDC after provision,
   update, group change, and deactivation.

Bulk can follow after the normal resource lifecycle is correct. Password
provisioning should remain unsupported unless a later product requirement
explicitly introduces it.

## Suggested repository shape

```text
identity/
  scim/
    fixtures/          # generated from the Northlake manifest
    scenarios/         # ordered provisioning and negative cases
    runner/            # SCIM 2.0 client and response assertions
  scripts/
    Test-ScimIdentity.ps1
```

The runner should emit a redacted machine-readable result alongside concise
console output, just like the current identity verifier. It should never become
the production SCIM service or share Keycloak's database.
