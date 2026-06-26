# EEM Application Branding — Login & Email

Provided by: Northlake University IT & Communications. Synthetic/fictional. This is
the branding Northlake provides for our EEM Suite portal: the **login page**
customization, **logos**, and **transactional email** look. Field names match the
EEM Suite login customization model (`CustomLoginInfo`) and email template tokens
so they map straight in.

Brand palette (reuse across all assets): **deep navy `#1F3A5F`** (primary),
**warm gold `#C9A227`** (accent), slate gray, white. Typeface: a clean sans
(Open Sans is fine — matches the email templates).

> **Rendered deliverable:** generated assets + templates live in
> [`output/branding/`](../../output/branding/) (logos/icons in `images/custom/`,
> branded email templates in `email-templates/`, filled `login-customization.md`,
> mockups + previews). Email tokens were verified/corrected against the real EEM
> templates. See `output/branding/README.md` for the deployment map.

---

## 1. Login page customization (`CustomLoginInfo`)

| Field | Value |
| --- | --- |
| HeaderRightLogoUrl | `/images/custom/northlake-header-logo.png` |
| HeaderRightLogoTitle | Northlake University |
| HideHeader | false |
| HideFooter | false |
| LoginHeader (kicker) | Energy & Utility Management |
| LoginTitle | Northlake University |
| LoginTitleUnderline | Energy Portal |
| LoginDescription | Secure access to Northlake's campus energy, utility, and sustainability data. |
| LoginLaptopCaption | Manage Northlake's energy with EEM Suite |
| LoginCustomerLogoPath | `/images/custom/LoginLogoRight.png` (the right-side hero image; this exact name is the override EEM looks for) |
| LoginCustomerLogoTitle | Northlake University Energy Portal |
| LoginHeaderColor (kicker) | `#C9A227` |
| LoginHeaderFontColor | `#FFFFFF` |
| HeaderBackGroundColor | `#1F3A5F` |
| BackGroundColor | `#F5F6F8` |
| LoginFooterTitle | Need help? |
| EEMLinkURL | https://sustainability.northlake.example.edu |
| EEMLinkURLText | Northlake Sustainability |

### Bullets (login feature list — `Bullets[]`, Title + Description)

1. **All your utilities, one portal** — Electricity, gas, water, thermal, and solar across every property.
2. **Cost & usage at a glance** — Track spend and consumption by building, account, and meter.
3. **Sustainability built in** — ENERGY STAR scores and greenhouse-gas reporting from the same data.
4. **Right access for every team** — Facilities, Finance, Housing, and Sustainability each see what they need.

### Footer "Need help?" contacts (`LoginFooterContact1..3`)

| Slot | Type | Pre | Value | Post |
| --- | --- | --- | --- | --- |
| 1 | email | Email | energy.support@northlake.example.edu | |
| 2 | other (phone) | Call | (916) 555-0142 | (Mon–Fri, 8am–5pm PT) |
| 3 | url | Status | https://status.northlake.example.edu | |

### Partners (`Partners[]`)

None for launch (optional; could add Helios Onsite Solar later).

---

## 2. Logo & image assets

| Asset | Where it's used | Spec |
| --- | --- | --- |
| **Master logo** | source of all others | Northlake University wordmark + a small lake/leaf mark; vector (SVG) |
| `LoginLogoRight.png` | login hero (right panel) | ~800×600, transparent or on a soft navy/gradient panel; campus + energy feel |
| `northlake-header-logo.png` | login header (top-right) | horizontal logo, transparent, ~200×48, reads on light header |
| `northlake-email-logo.png` | email header | **reversed/white** logo to read on the navy email header, 148×38 (provide @2x 296×76) |
| `favicon` / app icons | browser tab / PWA | 32×32 favicon + 192 & 512 app icons; theme color `#1F3A5F` |

Place login/header logos under `images/custom/` (the path EEM checks for overrides).

---

## 3. Transactional email branding

EEM emails use a shared layout (`_Layout.html`) with tokens and per-email bodies
(Password Reset, Verify Email, Email Changed, Workflow notifications). We provide
the **brand**, not the message logic — keep all `{{tokens}}` intact.

| Element | Northlake value |
| --- | --- |
| Header background | `#1F3A5F` (navy) |
| Accent bar / eyebrow / button | `#C9A227` (gold) — replaces the default EEM orange/red |
| Logo (`{{LogoUrl}}`) | `northlake-email-logo.png` (reversed) |
| Logo link (`{{LogoRedirectUrl}}`) | https://energy.northlake.example.edu |
| Top-right label | "Northlake University Energy Portal" (replaces "Energy Management Notification") |
| Footer | "© {{CurrentYear}} Northlake University Energy Portal — powered by EEM Suite (Energy Hippo, a Univerus company). This is an automated message; replies are not monitored." |
| Support line | "Questions? energy.support@northlake.example.edu" |
| From / Reply-to name | Northlake University Energy Portal / noreply@northlake.example.edu |

Templates to brand (each = `.html` body + `.subject.txt` + `.txt` plain text),
under the `_Layout.html` shell:

- Account / **PasswordReset** (tokens `{{ResetUrl}}`, `{{ExpiresIn}}`)
- Account / **VerifyEmail**
- Account / **EmailChanged**
- Workflow / **Default** (general notification)

Keep subject lines clear; Northlake is fine with the standard wording (e.g.
"Reset your Northlake Energy Portal password").

---

## Open items

- Confirm the support phone, status URL, and sustainability link.
- Confirm whether to co-brand the email footer (as above) or keep vendor-only.
- Provide final brand fonts if different from Open Sans.
