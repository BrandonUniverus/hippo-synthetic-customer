---
title: Stage 11. Third-party integrations
subtitle: Identity, provisioning, message broker, mail, ENERGY STAR, EnergyAI, the public API
status: Research only; no editor files yet
---

# Stage 11. Third-party integrations

Stage 10 ends with a database that is complete in itself: restore it anywhere
and every report, rate, bill and allocation is there. Stage 11 is everything
Northlake does with a system that is not inside that database: signing in
through the university's identity provider, receiving users and groups from
its provisioning system, publishing interval data to a message broker, sending
mail, talking to ENERGY STAR Portfolio Manager and EnergyAI, and being called
by other systems through the public API. These are the product's biggest
customer-facing capabilities and the ones a restored database alone cannot
demonstrate.

This chapter is research. It records what the product integrates with, where
each integration's configuration actually lives, what outside service it
needs, and what breaks when the database is restored on a different server.
It ends with a proposal for the stage and the decisions that shape it. No
YAML files or checks exist yet.

## The three places configuration lives

The portability question turns on one distinction. An integration's settings
sit in one of three places, and only the first travels with the backup.

| Place | Examples | Travels with the backup |
| --- | --- | --- |
| Database rows entered through a screen | Identity realms and providers, SCIM connections, ENERGY STAR property links, event-bus event types | Yes, including any URL or host name they contain |
| Configuration keys per installation | Message broker provider and RabbitMQ connection, SMTP host and credentials, task credentials for ENERGY STAR and EnergyAI, SCIM and SAML security limits | No; they live in the instance's configuration store and are re-entered per server |
| State inside the outside service | The Keycloak realm with its users, groups, signing keys and client secrets; RabbitMQ queues; the mail inbox; the Portfolio Manager sandbox account | No; the service is brought along or rebuilt beside the application |

Database-resident settings that contain host names are the tricky class:
they restore correctly but point at wherever the outside service was when
they were typed.

## Inventory

### Identity: OpenID Connect and SAML

**What the product has.** A full third-party identity console on the web at
Security Administration, Third-Party Identity, with sections for realms, OIDC
providers, SAML providers, behavior, SCIM and group authority. Providers,
realms, secrets, SAML metadata snapshots and trust anchors, token sessions and
correlation bindings are all database rows in the IdentityProvider and
Identity schemas. Seven legacy fixed providers (Windows, Microsoft, Facebook,
Google, Twitter, Azure, OpenID Connect) are seeded disabled; no realm and no
Northlake provider exist on the instance yet. SAML clock skew, issue age and
replay lifetimes, and metadata fetch limits, are configuration keys, not rows.

**Outside service.** The synthetic identity provider in `identity/`: a Keycloak
26.7 realm named `northlake` generated from the security manifest (23 users,
29 groups, stable identifiers), behind Caddy at `https://localhost:8443`,
with PostgreSQL for realm state and keys. It offers two OIDC client profiles
(Modern code plus PKCE, and a Historical Legacy implicit profile), two SAML
service-provider registrations (Standard and Saml2Int), two disposable lab
realms for issuer and subject scenarios, a separate customer-site origin for
cross-site session evidence, a launchpad, and verifiers for both protocols.
Its README carries the ready-to-copy EEM values: discovery endpoint
`https://localhost:8443/realms/northlake/.well-known/openid-configuration`,
client `eemsuite-web`, scopes `openid profile email northlake`; SAML entity ID
`urn:energyhippo:eemsuite-web:saml:standard` with metadata at
`.../protocol/saml/descriptor`.

**Portability.** Three things bind the database rows to a place.

- The issuer and metadata URLs. Because the lab publishes itself at
  `localhost:8443`, a second server that runs the same compose bundle has the
  same issuer, and the restored provider rows keep working. A shared identity
  server on another host would need a stable DNS name instead.
- The registered callbacks. Keycloak allows exact redirect, post-logout and
  assertion consumer URLs; the lab registers `https://localdev.energyhippo.com/Hippo/...`
  and `https://localhost/Hippo/...`. A server that serves the site under
  another host name must add its callbacks through the lab's `/configure/oidc`
  and `/configure/saml` pages, or the site's host name must be a convention
  every server follows.
- Trust. The lab's private CA must be trusted on each server
  (`Trust-IdentityCertificate.ps1`), and the SAML metadata trust anchor the
  product snapshots is that CA's chain.

Client secrets are stored on the EEM side in the provider secret table, so
they restore; the same secret must exist in the realm on the other server,
which is true when the realm is generated deterministically from the manifest
and the same `.env`.

### Provisioning: SCIM 2.0

**What the product has.** EEM is the SCIM service provider at
`/Public/scim/v2`. Connections, credentials, company scopes, templates,
authority families and the provisioned user and group resources are rows in
the Provisioning schema, created on the console's SCIM section. Rate limits,
page sizes, credential lifetime (90 days) and rollover overlap are
configuration keys.

**Outside service.** The lab's SCIM client harness (`identity/SCIM-2.0-TESTING.md`)
plays the customer's provisioning system in the same role as Microsoft Entra:
deterministic user and group lifecycles against a connection named
`eem-local` with the template "Northlake external-only users" and group
bindings keyed by external ID. Earlier interop work found Entra's exact
requirements (mandatory If-Match on mutations, boolean `active`, member
removal form), and those cases are in the harness.

**Portability.** The connection row restores, but its credential has a
90-day lifetime and is a secret the harness must hold too. Stage 11 should
plan on re-issuing the SCIM credential on each server from the console and
feeding it to the harness, rather than carrying it in the backup.

### Message broker: RabbitMQ

**What the product has.** A broker abstraction with four providers: in-memory,
SQLite (the default), file drop and RabbitMQ. Everything is configuration
keys under `MessageBroker`: provider, queue providers, the RabbitMQ URI or
host, port, virtual host, user name, password, queue kind (classic or quorum),
exchange `eemsuite.broker`, publisher confirms, prefetch, heartbeat, recovery,
queue length, single active consumer and retry delays. Nothing about the
broker is in the database. Publishers today are the interval-data publish
component (gateway output to broker queues), the handheld events publisher,
brokered email delivery and one customer task. Hippo Tools has a Message
Broker workbench for inspecting queues.

**Outside service.** The product repository already ships a development
RabbitMQ (`BuildScripts/Local/Docker`, image `eemsuite-rabbitmq-dev`, ports
5672 and 15672, user `eemsuite`) inside a local-services compose file that
also runs Mailpit, an SFTP server and an HTTP fixture server.

**Portability.** None needed. Switching Northlake to RabbitMQ is a per-server
configuration change plus the container. The baseline database is unaffected,
which is why the broker does not belong in Stage 10. What Stage 11 adds is
the decision to run Northlake on RabbitMQ so the interval publish path and the
handheld event path are exercised on a real broker, and the queue names and
expected messages to check.

### Mail: SMTP

**What the product has.** An SMTP section of configuration keys (host, port,
SSL or STARTTLS, credentials, from address and name, timeout, retries) and a
queued email delivery pipeline with its own queue and lease settings. Flows
that send: password reset and invitations, email changes, the AP upload
emailer, scheduled report delivery, instant report email, alarm notifications
and job failure alerts. Hippo Tools has an Email Test Tool. Templates live
under the content folder, some flows still send raw text.

**Outside service.** Mailpit from the same local-services compose file, with
an inbox UI and an HTML-check API the templates were tuned against.

**Portability.** Configuration keys per server; the inbox is disposable.
Stage 9's delivery to 100+ recipients needs this to be in place, so the mail
sink is a prerequisite Stage 11 provides rather than a capability of its own.

### ENERGY STAR Portfolio Manager

**What the product has.** Property setup and rating requests on the web
(Stage 8), a sync task whose parameters are the root URL, customer prefix,
Portfolio Manager user name and account password, and a client with timeout
and retry settings. Scores arrive only from Portfolio Manager. Property links
(the Portfolio Manager property IDs) are database rows once linked.

**Outside service.** A Portfolio Manager sandbox account. Nothing in either
repository provides one; it is an account Energy Hippo holds.

**Portability.** The credentials are task parameters per server. The property
IDs restore with the database and stay valid as long as the same sandbox
account is used everywhere.

### EnergyAI

**What the product has.** A client task with user name, password, upload URL
and download URL parameters. Enrollment of loads, weather sites and periods
is database-only with no screen (finding 12).

**Outside service.** The EnergyAI service. Lowest priority; Stage 9 carries
it as a proposed capability pending the enrollment screen.

### Weather and file sources

NOAA and Aeris Weather gateways call public HTTP services; Aeris needs a
client id and secret entered as gateway task parameters (Stage 3). The ODBC
historian and any SFTP-delivered formats use the SFTP and HTTP fixture
containers from the product's local-services compose. These are Stage 3
capabilities with a Stage 11 dependency.

### The public API and the event bus

**What the product has.** The `/Public` API with Swagger locked to
administrators, service principals (principal type Service, authentication
policy WorkloadOnly) with API keys issued from Users and Groups, and an event
bus whose 37 event types include 24 that outside systems may publish through
the API (bill import events, task and workflow run events, email requests,
report delivery events, client invalidation, configuration materialized).
Security notices can be raised toward specific applications. SignalR pushes
to browsers and desktop apps are internal.

**Outside service.** None today. A small Northlake integration client
(publishing a bill-import event, reading interval data, creating a user
through SCIM) would be the way to exercise this end to end.

**Portability.** Service principals and their key hashes are database rows;
the plain key is issued once and held by the caller, so it is re-issued per
server like the SCIM credential.

## What would break on a second server

Restoring the Stage 10 database on another machine and starting the
application, with nothing else done:

- Local sign-in, every report, rate and bill: works.
- Sign-in through Northlake: fails until the identity bundle runs beside the
  application with the same issuer, the CA is trusted, and the site's host
  name matches a registered callback.
- SCIM: the connection exists, its credential must be re-issued.
- Broker: falls back to the SQLite provider unless the RabbitMQ keys are set.
- Mail: nothing sends until SMTP keys point at a sink.
- ENERGY STAR and EnergyAI: the tasks fail validation until their parameters
  are entered.
- Passkeys and any WebAuthn credential: bound to the site's origin, so a new
  host name invalidates them; MFA policies restore.

## Proposal

Make Stage 11 the "Northlake external services" stage with three parts.

1. **One services bundle.** A compose project that brings the identity lab
   (Keycloak, PostgreSQL, Caddy, the configuration and customer sites) together
   with RabbitMQ, Mailpit and the SFTP and HTTP fixture containers from the
   product's development stack, under one `.env` per server and one start
   script. The identity lab already does the hard part; the bundle adds the
   other four services and a host-name convention.
2. **A per-server configuration set.** The configuration keys Northlake needs
   for the broker, SMTP, ENERGY STAR and EnergyAI, written as one JSON
   document per manifest for Assembly Configuration or the instance
   configuration files, with the secrets left as placeholders the server
   fills. This is what makes the second server behave like the first.
3. **The database-resident integration setup, entered through the console.**
   The Northlake realm, the Modern and Legacy OIDC providers, the Standard and
   Saml2Int SAML providers with their correlation bindings, the SCIM
   connection with its template and group bindings, and the service
   principals for the API client. These are the rows that belong in the
   baseline, on the condition below.

The condition is a host-name convention. If every Northlake server serves the
site as `https://localdev.energyhippo.com/Hippo` (a hosts-file entry) and
runs the identity bundle at `https://localhost:8443`, the identity rows in the
baseline are valid everywhere and Stage 11's database work can be done once.
Without that convention the identity rows are re-entered per server, and the
baseline should carry none of them.

When it is built, the stage folder would hold:

```text
stage-11-third-party/
  01-services-bundle.yaml        what runs, on which host names and ports, from which .env
  02-configuration-keys.yaml     MessageBroker, Smtp, EnergyStar, EnergyAI keys per server
  03-identity-realm.yaml         Security Administration > Third-Party Identity > Realms
  04-oidc-providers.yaml         the Modern and Historical Legacy providers
  05-saml-providers.yaml         the Standard and Saml2Int providers, correlation bindings
  06-scim-connection.yaml        connection, credential rollover, template, group bindings
  07-api-service-principals.yaml Users & Groups > service principals and API keys
  08-acceptance.yaml             sign-in per protocol, SCIM lifecycle, a brokered publish,
                                 a delivered mail, an ENERGY STAR sync, an API publish
  checks.sql
```

## Decisions needed

- **Host names.** Adopt the convention above, or accept per-server identity
  setup. This decides whether identity rows go into the baseline.
- **Broker for the baseline build.** Run Northlake on RabbitMQ from Stage 3
  onward so the publish paths are exercised while data loads, or keep SQLite
  until Stage 11. Running RabbitMQ early costs one container and no database
  change.
- **Portfolio Manager sandbox.** Which account, and who holds it. Stage 8
  cannot show scores without it.
- **EnergyAI.** Whether to pursue the service connection at all before the
  enrollment screen exists.
- **An integration client.** Whether Northlake gets a small client program
  that publishes to the API and drives SCIM, or whether the identity lab's
  harness is extended to cover both.

## Findings so far

- The SCIM credential lifetime (90 days by default) means a baseline that
  carried a credential would expire; re-issue per server is the right model,
  and the console supports rollover.
- The seven legacy fixed providers are seeded disabled on every install; a
  customer that never uses them sees them in the console. Worth a review of
  whether they should be hidden until enabled.
- Nothing in either repository provides ENERGY STAR or EnergyAI test
  services; both stay external accounts.
