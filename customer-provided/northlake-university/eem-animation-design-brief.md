# Design Brief — Northlake Login & Loading Animations (POC)

Paste the block below into Claude (design / front-end generation). It produces two
Northlake-branded, **per-customer** web animations as a POC: a login entrance
animation and a loading animation.

**Dependencies:** new libraries are allowed **only if MIT or Apache-2.0 licensed**,
and the library used must be named with its license. This makes **Lottie** the
recommended path — it's the natural per-customer model (ship the player once, swap a
JSON per customer).

> **Rendered deliverable:** generated animations live in
> [`output/branding/animations/`](../../output/branding/animations/) — login +
> loading (Lottie JSON + CSS/SVG), `northlake-theme-vars.css`, and a README. Built
> on **lottie-web (MIT)**, no GSAP; verified against the `.k-loading-mask` /
> `.auth-branding__figure` hooks with reduced-motion fallbacks.

Integration facts (so output drops in):
- App has **no** animation library today; adding one is fine **if MIT/Apache-2.0**.
- App themes via CSS custom properties: `--color-accent`, `--color-primary-2`,
  `--color-tertiary`, `--color-primary`, `--font-size-sm`.
- Loading today: a Kendo loading mask restyled in `loading-animation.less` —
  `.k-loading-mask` overlay, `.k-loading-image` (56×56) spinner via
  `@keyframes app-loading-spin`, optional `.k-loading-text` caption.
- Login hero markup: `.auth-branding` › `.auth-branding__figure` (img + figcaption),
  styled by `login/_auth-branding.less`.

---

You are creating a **proof-of-concept set of two web animations** for Northlake
University's EEM Suite portal (fictional). Brand: deep navy `#1F3A5F`, warm gold
`#C9A227`, slate/teal support tones, white. Motif: "Northlake" = north + lake →
**concentric lake ripples + a leaf/energy spark** (tie to the logo's lake/leaf
mark). Tone: calm, premium, institutional — subtle, not flashy.

## Licensing rule (important)

Any new dependency must be **MIT or Apache-2.0**, and you must state the license you
chose. Eligible: **Lottie** (`lottie-web` or `@lottiefiles/dotlottie-web`) — MIT;
`anime.js` — MIT; **Motion One** (`motion`) — MIT; Rive web runtime — MIT. **Do not
use GSAP/GreenSock** (not MIT/Apache). Pure CSS/SVG (no dependency) is also fine.

## Recommended approach

- **Primary — Lottie (MIT):** ship `lottie-web`/`@lottiefiles/dotlottie-web` once;
  each customer is just a different `.json`/`.lottie` file. Use it for the rich
  login entrance. Deliver the player integration + a **working sample Lottie JSON**
  for Northlake (hand-authored simple shape animation is fine for the POC), and note
  that production JSONs would come from a designer (After Effects/LottieFiles).
- **Alternative — anime.js or Motion One (MIT)** animating inline SVG, if you'd
  rather hand-author the motion as code for the POC.
- **Loading spinner:** a small **CSS/SVG** loop is fine here (zero-dep, lives in the
  Kendo mask); offer a Lottie version too for a richer full-page splash.
- Always include a **`prefers-reduced-motion: reduce`** static fallback.

## Per-customer model

Whatever you choose, make reskinning a customer trivial: **Lottie** → swap the JSON
(+ theme colors); **CSS/SVG** → change the `--color-*` custom properties and swap the
SVG mark. Northlake values: `--color-primary-2:#1F3A5F` (navy),
`--color-accent:#C9A227` (gold), a teal `--color-tertiary`.

## Performance & quality

Prefer `transform`/`opacity` motion; 60fps; seamless loops; keep payloads modest
(Lottie player + JSON, or a small CSS/SVG block). Email-/browser-safe, accessible.

### Deliverable 1 — Login entrance animation (targets `.auth-branding__figure`)

The Northlake mark **assembles** (lake ripples expand; a gold leaf/energy spark
settles), then the wordmark fades/slides up and a **gold underline draws** under the
title. ~1.8–2.5s; optional subtle ambient ripple after. Layers over a soft navy
gradient panel; must not block the form. Lottie recommended.

### Deliverable 2 — Loading animation (overrides `.k-loading-mask .k-loading-image`, 56×56)

Replace the generic ring with a Northlake loader — concentric lake ripples pulsing
outward from the leaf/energy mark (or the mark gently pulsing). Keep the
`.k-loading-text` hook. ~1.0–1.4s seamless loop; readable on the translucent blurred
mask. CSS/SVG is fine here; also provide a Lottie version for a full-page splash.

## Output

Write to `output/branding/animations/`:
- `login-animation.html` — standalone preview + the integration (Lottie player init
  **or** CSS/SVG) targeting `.auth-branding__figure`.
- `loading-animation.html` — standalone preview + the drop-in LESS overriding
  `.k-loading-mask .k-loading-image` (supersedes `loading-animation.less`), plus a
  Lottie splash variant.
- `northlake-login.json` / `northlake-loading.json` — Lottie sources if used.
- `northlake-theme-vars.css` — the CSS custom-property override block.
- `README.md` — files + where they go, **the library and its license**, reduced-motion
  behavior, and a "reskin for another customer" recipe (swap JSON or vars + mark).

Keep it production-credible: clean, accessible, license-compliant (MIT/Apache only),
and clearly per-customer.

---
