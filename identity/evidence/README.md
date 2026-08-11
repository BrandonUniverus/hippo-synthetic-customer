# Northlake identity evidence

Phase 9 turns the Northlake lab into a repeatable evidence producer for the
identity work planned by ADR-021, ADR-022, ADR-026, and ADR-027. It does not
claim that EnergyHippo has passed an integration merely because Keycloak or a
Northlake protocol verifier passed.

## Environment boundary

The persistent `northlake` realm is the restart-stability environment. It must
contain exactly one normal Modern OIDC registration and one normal Standard
SAML registration. Fault controls, destructive cases, additional clients, and
configuration combinations belong in the disposable `northlake-lab-a` and
`northlake-lab-b` realms.

`Promote-IdentityStableRealm.ps1` enforces that boundary and rejects any realm
other than the exact `northlake` realm. The stable profile uses discovery,
`UseIfAvailable` PAR, `client_secret_post`, no provider consent screen,
Persistent NameID, SAML Single Logout, and no legacy or SAML2Int profile. This
is a stable baseline, not a statement that the disabled profiles are
unsupported; those profiles remain covered in the bounded lab matrix.

## Coverage contract

`coverage-catalog.json` maps every declared implementation checkpoint from the
four ADRs to one or more scenarios. Catalog validation fails when a checkpoint,
classification, evidence reference, stable/lab boundary, or vendor-claim
boundary is missing.

Each scenario has exactly one expected classification:

- `supported-pass`: the described capability is expected to pass in its named
  environment;
- `supported-controlled-failure`: the deterministic negative fixture must be
  rejected at the intended boundary;
- `unsupported-clean-rejection`: Northlake must not accidentally claim an
  unimplemented protocol feature;
- `future-capability`: the ADR reserves the capability but current code must not
  be reported as supporting it; or
- `forbidden-security-downgrade`: no local form or JSON value may bypass the
  security ceiling.

The catalog covers every typed field, uses deterministic all-pairs generation
for ordinary independent OIDC and SAML settings, and keeps selected security
cases exhaustive. `fault-fixtures.json` defines secret-free recipes for the
same six OIDC and SAML fault classes: malformed, tampered, replayed,
unavailable, stale, and oversized. It describes how to create a fixture but
does not store tokens, assertions, passwords, or private keys.

## Run the acceptance harness

Start from a healthy local stack and run:

```powershell
pwsh .\identity\scripts\Promote-IdentityStableRealm.ps1
pwsh .\identity\scripts\Test-IdentityEvidence.ps1
```

The harness validates the catalog, runs the full Python suite, promotes and
verifies the stable realm, verifies OIDC, SAML, group claims, two-realm
scenarios, and the browser lab, then performs an explicit provider outage and
full Compose restart. The harness has no skip-restart mode because an
abbreviated result must not be mistaken for Phase 9 acceptance.

Signing-key rollover is deliberately separate because every invocation creates
a new key. Run it once for the intended rollover event:

```powershell
pwsh .\identity\scripts\Rotate-IdentitySigningKey.ps1
```

The rotation result must prove a new active OIDC signing key, retention of the
old published key, a passing post-rotation protocol verifier, and overlapping
old/new SAML metadata certificates. The main evidence harness consumes that
latest result and never rotates a key implicitly.

## Evidence output

Ignored runtime evidence is written below `identity/.runtime/evidence`:

- `stable-before.json` and `stable-after.json` contain only the stable issuer,
  hashed synthetic subject identifiers, public signing-key and certificate
  fingerprints, configuration hash, and pinned/running image identifiers;
- `restart-stability.json` proves the outage was observable and that the realm,
  issuer, subjects, clients, OIDC keys, SAML metadata, configuration, and image
  stayed stable after recovery; and
- `identity-evidence.json` is the final redacted manifest.

The manifest records the Northlake and EnergyHippo revisions and dirty-path
counts, immutable Keycloak image digest, scenario and fault-fixture versions,
configuration hash, safe command results, artifact hashes, scenario outcomes,
and every explicit proof gap. It deliberately drops command output and rejects
sensitive field names or possible bearer material before writing.

An EnergyHippo revision in this manifest is identification only. The Phase 9
harness reads Git metadata but does not build, run, configure, or change the
EnergyHippo checkout.

## Independent and external proof

Keycloak is the deterministic local reference provider; it must never be
reported as Entra, Okta, Shibboleth, InCommon, or an independent SAML vendor.
Those vendor scenarios remain explicit gaps until the corresponding external
tenant or implementation is available.

OpenID Foundation RP conformance is also independent of the Keycloak verifier.
The catalog points to the official [RP testing
plans](https://openid.net/certification/connect_rp_testing/), [RP Logout testing
plans](https://openid.net/certification/connect_rp_logout_testing/), and
[conformance suite](https://openid.net/certification/about-conformance-suite/).
Northlake records that work as a gap until the applicable plans run against an
installed EnergyHippo relying party.

Other intentional installed-environment gaps include supported EnergyHippo
provider administration, non-root-path hosting, two simultaneous Web
processes, local-login fallback, real browser round trips through EnergyHippo,
SCIM lifecycle credentials and audit evidence, and a shared development-host
deployment. A local provider pass cannot close any of those gaps.
