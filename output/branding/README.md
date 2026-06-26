# Northlake University — EEM Portal Branding

Branding assets and templates for the **Northlake University Energy Portal**
(EEM Suite). Everything here is brand chrome + imagery — no message logic was
changed. Synthetic / fictional.

**Start here:** open **`Brand Assets.dc.html`** for a visual index of everything,
or **`Login Mockup.dc.html`** for the full login page.

---

## Brand basics

| | |
| --- | --- |
| Deep navy (primary) | `#1F3A5F` |
| Warm gold (accent) | `#C9A227` |
| Slate gray | `#5B6573` |
| Canvas / page bg | `#F5F6F8` |
| Typeface | Open Sans |

**Mark.** A gold north-star above a leaf-shaped lake (the leaf doubles as the
lake surface; the midrib is the waterline) inside a navy roundel — "Northlake"
+ a sustainability cue. It harmonizes with the existing Northlake University
ecosystem mark and stays legible down to 16px.

---

## Files

```
output/branding/
├─ Brand Assets.dc.html          Visual index of all assets (open this)
├─ Login Mockup.dc.html          Full branded EEM login page
├─ login-customization.md        Ready-to-transcribe CustomLoginInfo values
├─ README.md
├─ images/custom/                ← upload these to EEM's images/custom/
│  ├─ northlake-logo.svg                 Master lockup, navy + gold (vector)
│  ├─ northlake-logo-reversed.svg        Master lockup, reversed / white (vector)
│  ├─ northlake-mark.svg                 Symbol only (vector)
│  ├─ northlake-mark-reversed.svg        Symbol only, reversed (vector)
│  ├─ LoginLogoRight.png                 Login hero / right panel  (800×600)
│  ├─ northlake-header-logo.png          Header logo, positive     (200×48, transparent)
│  ├─ northlake-header-logo-reversed.png Header logo, reversed     (200×48, transparent)
│  ├─ northlake-email-logo.png           Email header logo, white  (148×38, transparent)
│  ├─ northlake-email-logo@2x.png        Email header logo @2x     (296×76, transparent)
│  ├─ favicon-32.png                     Favicon                   (32×32)
│  ├─ app-icon-192.png  app-icon-512.png PWA / app icons
│  └─ site.webmanifest                   Manifest, theme #1F3A5F
├─ email-templates/              ← mirrors EEM's shared-layout structure
│  ├─ _Layout.html                       Shared wrapper (navy header, gold bar, footer)
│  ├─ Account/
│  │  ├─ PasswordReset.html / .subject.txt / .txt
│  │  ├─ VerifyEmail.html  / .subject.txt / .txt
│  │  └─ EmailChanged.html / .subject.txt / .txt
│  └─ Workflow/
│     └─ Default.html      / .subject.txt / .txt
└─ previews/                     Rendered email samples (preview only — do NOT upload)
```

---

## Login customization

All filled `CustomLoginInfo` values (kicker, title + underline, description,
laptop caption, 4 bullets, header/background colors, "Need help?" footer with 3
contacts, sustainability CTA) are in **`login-customization.md`**, formatted to
transcribe straight into the EEM admin screen. `Login Mockup.dc.html` shows them
assembled.

> **One thing to check:** `HeaderBackGroundColor` is navy (`#1F3A5F`). The default
> `northlake-header-logo.png` is built to read on a *light* header, so on a navy
> header set `HeaderRightLogoUrl` to `northlake-header-logo-reversed.png` (shipped
> in the same folder). Details in `login-customization.md`.

---

## Email templates — brand only, tokens preserved

The structure mirrors EEM: a shared `_Layout.html` wrapper + per-email body
fragments injected at `{{Body}}`. Only the brand chrome changed — navy `#1F3A5F`
header, **gold `#C9A227`** accent bar / eyebrow / button (replacing the default
orange/red), the reversed Northlake email logo, the top-right label "Northlake
University Energy Portal", and the co-branded footer. Mobile media queries and
table-based, client-safe HTML are intact.

**Tokens used per template** (none renamed, removed, or restyled):

| Template | Tokens |
| --- | --- |
| `_Layout.html` | `{{Subject}}` `{{Preheader}}` `{{LogoUrl}}` `{{LogoRedirectUrl}}` `{{Body}}` `{{CurrentYear}}` `{{MachineName}}` |
| `Account/PasswordReset` | `{{ResetUrl}}` `{{ExpiresIn}}` |
| `Account/VerifyEmail` | `{{VerifyUrl}}` * · `{{ExpiresIn}}` |
| `Account/EmailChanged` | `{{NewEmail}}` * · `{{LogoRedirectUrl}}` |
| `Workflow/Default` | `{{Subject}}` · `{{Message}}` * · `{{LogoRedirectUrl}}` |

\* The brief only specified `PasswordReset`'s tokens (`{{ResetUrl}}`, `{{ExpiresIn}}`).
The starred names follow EEM conventions but are **best-guess placeholders** — please
confirm them against your original VerifyEmail / EmailChanged / Workflow templates and
rename to match if they differ. The brand chrome won't change either way.

`{{LogoUrl}}` should resolve to `northlake-email-logo.png`; `{{LogoRedirectUrl}}`
to `https://energy.northlake.example.edu` (per the spec).

---

## Notes

- **Fonts in SVG.** The vector wordmarks use live Open Sans text (self-loaded via
  a Google Fonts `@import`, matching the ecosystem convention). Open them where the
  web is available, or convert text → outlines for a fully portable file.
- **PNGs** are flattened with the wordmark baked in, so they need no font.
- **`previews/`** holds fully-assembled email samples (sample token values) used by
  the Brand Assets page — they are for review only, not for upload to EEM.
