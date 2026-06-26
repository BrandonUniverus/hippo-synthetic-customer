# Design Brief — Generate Northlake EEM Portal Branding

Paste the block below into Claude (design / document + image generation). It
generates the Northlake logo assets, the filled login customization, and the
branded transactional email templates. Source of truth for content/values:
`eem-application-branding.md` (attach it). Structural reference for emails:
EEM's templates at `src/Content/EEMSuite.Content/Content/EmailTemplates/EEMSuite.Web/`.

---

You are generating the **branding assets and templates** for Northlake
University's EEM Suite energy portal (fictional customer). Work from the attached
`eem-application-branding.md` for all values. Brand palette: **deep navy
`#1F3A5F`**, **warm gold `#C9A227`**, slate gray, white. Clean sans typeface
(Open Sans). Everything is synthetic/fictional — keep a light "Synthetic" note in
any delivery README, not on the assets themselves.

## 1. Logos & images (generate)

Design a **Northlake University** wordmark with a small lake/leaf mark, then export:
- **Master logo** — SVG (navy + gold on transparent; plus a reversed/white version).
- `LoginLogoRight.png` — login hero / right-panel image (~800×600), the logo on a
  soft navy gradient with a subtle campus + energy motif; transparent edges OK.
- `northlake-header-logo.png` — horizontal logo for the login top-right, transparent,
  ~200×48, must read on a light header.
- `northlake-email-logo.png` — **reversed/white** logo for the navy email header,
  148×38, plus @2x (296×76).
- **Favicon + app icons** — 32×32 favicon and 192/512 PNG app icons; theme `#1F3A5F`.

## 2. Login customization (output as ready-to-enter values)

Produce the filled `CustomLoginInfo` values exactly from `eem-application-branding.md`
(header/customer logo paths, kicker, title + underline, description, laptop caption,
4 bullets [Title + Description], header/background colors, "Need help?" footer with
the 3 contacts, and the Sustainability CTA link). Present as a clean config
block/table an admin can transcribe, and a small mock of how the login page looks.

## 3. Transactional email templates (generate, brand-only changes)

Mirror EEM's email structure exactly — a shared `_Layout.html` wrapper + per-email
body fragments — changing only the **brand chrome**, never the logic:

- Re-skin `_Layout.html`: navy `#1F3A5F` header, a **gold `#C9A227` accent bar**
  (replacing the default orange), `{{LogoUrl}}` = the Northlake reversed email logo,
  top-right label "Northlake University Energy Portal," and the co-branded footer
  from the spec. **Keep every token:** `{{Subject}}`, `{{Preheader}}`, `{{LogoUrl}}`,
  `{{LogoRedirectUrl}}`, `{{Body}}`, `{{CurrentYear}}`, `{{MachineName}}`.
- Brand the per-email bodies (gold eyebrow + button instead of orange/red),
  **preserving every body token exactly** (e.g. PasswordReset uses `{{ResetUrl}}`
  and `{{ExpiresIn}}` — do not rename, remove, or invent tokens):
  - Account / **PasswordReset** (.html + .subject.txt + .txt)
  - Account / **VerifyEmail** (.html + .subject.txt + .txt)
  - Account / **EmailChanged** (.html + .subject.txt + .txt)
  - Workflow / **Default** (.html + .subject.txt + .txt)
- Keep the mobile media queries and table-based layout (email-client-safe HTML).
- Subjects can say "Northlake Energy Portal" instead of "EEM Suite" where natural.

## Output

Write to an `output/branding/` folder: the SVG/PNG assets, a `login-customization`
config file (values + a login mockup), and an `email-templates/` tree matching
EEM's layout (`_Layout.html` + `Account/*` + `Workflow/*`). Include a short README
listing each file and where it goes. Do not change any `{{token}}`; you are
generating brand chrome and images, not message logic.

---
