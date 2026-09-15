# Design Brief — Default Energy Hippo / EEM Suite Theme

The out-of-the-box look that ships when **no customer branding** is applied — the
baseline that per-customer skins (e.g. Northlake University) override via the same
hooks/variables. Paste the block below into Claude (design + image generation).

Grounded in the current app: default `CustomLoginInfo` strings, the EEM email
`_Layout.html` palette/tokens, the `energyhippo-icons` set, and the
`.auth-branding__figure` / `.k-loading-mask` integration points.

---

You are designing the **default Energy Hippo / EEM Suite** theme — the shippable,
out-of-the-box look used when a customer has no custom branding. It is the baseline
that per-customer skins override (same CSS hooks + `--color-*` variables). Refresh
and modernize the existing Energy Hippo identity; keep it clean, professional, and
consistent across login, email, and animations. Synthetic/internal is fine.

BRAND — Energy Hippo / EEM Suite™ (a Univerus company), grounded in the live app:
- Signature **orange `#F5811F`**; deeper **red-orange `#EB4623`** (eyebrows/buttons);
  near-black **charcoal `#231F20`** (ink/headers); **teal `#3C7088` / `#4F9CBC`**
  (links/kicker); warm off-white **canvas `#EFECE6`**; grays `#6B7280`, `#9CA3AF`.
  Typeface **Open Sans**.
- **Mark:** the Energy Hippo hippo. **Wordmark:** "EEM Suite" with an "Energy Hippo
  · a Univerus company" lockup. Design a clean hippo mark + wordmark that harmonizes
  with the existing `energyhippo-icons` style (attach the current logo if you have it
  for continuity).

LICENSE RULE: any dependency must be MIT or Apache-2.0 (Lottie/`lottie-web` is MIT
for the animations); **no GSAP/GreenSock**. State the library + license.

Produce the default theme kit (mirror the per-customer kit structure):

1) LOGOS & IMAGES
- Master Energy Hippo / EEM Suite logo — SVG + reversed/white.
- `LoginLogoRight.png` — default login hero (~800×600), the modern replacement for
  the legacy `EEM-Laptop.png`.
- header logo (200×48 transparent, + reversed), email logo white 148×38 (+@2x),
  favicon-32, app-icon 192 & 512, `site.webmanifest` (theme `#231F20`).

2) DEFAULT LOGIN CUSTOMIZATION (`CustomLoginInfo` defaults)
Use the product defaults: `LoginCustomerLogoTitle` = "Energy Hippo EEM Suite™";
`LoginLaptopCaption` = "Make the most of your energy with EEM Suite"; headline
"Secure access to EEM Suite" + a short description; **4 product value-prop bullets**
(unify all utility data; track cost & usage; sustainability — ENERGY STAR + GHG;
tenant rebilling / multi-site); header/background colors from the palette; a
"Need help?" footer with Energy Hippo support (`support@energyhippo.example.com`,
a phone, a status URL); CTA → `energyhippo.com`. Output as ready-to-enter config
values + a login-page mockup.

3) EMAIL TEMPLATES (default refresh — keep every token)
Refresh the shared `_Layout.html` + the 4 per-email bodies in the default palette
(charcoal header, **orange accent bar**, EEM email logo, top-right label "Energy
Management Notification", footer "© {{CurrentYear}} Energy Hippo, Inc. · A Univerus
company. This is an automated message; replies are not monitored."). Preserve EVERY
token exactly:
- `_Layout`: `{{Subject}}` `{{Preheader}}` `{{LogoUrl}}` `{{LogoRedirectUrl}}` `{{Body}}` `{{CurrentYear}}` `{{MachineName}}`
- `Account/PasswordReset`: `{{ResetUrl}}` `{{ExpiresIn}}`
- `Account/VerifyEmail`: `{{VerifyUrl}}` `{{ExpiresIn}}`
- `Account/EmailChanged`: `{{NewEmail}}` `{{ChangedOn}}` `{{SupportUrl}}`
- `Workflow/Default`: `{{Subject}}` `{{Body}}`
Each as `.html` + `.subject.txt` + `.txt`; keep mobile media queries + table-based,
client-safe HTML.

4) ANIMATIONS (default theme — the base customers override)
- Login entrance targeting `.auth-branding__figure`; loading animation overriding
  `.k-loading-mask .k-loading-image` (56×56) and a Lottie full-page splash.
- Energy Hippo motif (a friendly hippo + an energy spark; orange/charcoal/teal),
  calm and premium. **Lottie (MIT)** + a CSS/SVG fallback; `prefers-reduced-motion`
  static state. Provide the Lottie JSONs.

5) THEME LAYER
A default **`eem-theme-vars.css`** setting the `--color-*` custom properties to the
Energy Hippo defaults (`--color-primary:#231F20`, `--color-accent:#F5811F`,
`--color-tertiary:#3C7088`, etc.) — the **base layer**. Note that customer skins
(e.g. `northlake-theme-vars.css`) override these same vars + swap the mark/JSON.

OUTPUT → a `branding-default/` folder:
- `images/custom/` (logos, hero, header/email logos, favicon, app icons, webmanifest)
- `login-customization.md` (default values) + a login mockup
- `email-templates/` (`_Layout.html` + `Account/*` + `Workflow/*`)
- `animations/` (login + loading HTML, Lottie JSONs, `loading-animation.less`,
  `eem-theme-vars.css`)
- `README.md` — files, where each deploys, and **the library + license**.

This is the shippable default, so it must be production-credible, accessible, and
on-brand with the existing Energy Hippo identity. Do not change any `{{token}}`.

---
