# Northlake University — EEM Suite branding animations (POC)

Two production-credible web animations for the EEM Suite portal login + loading
experience, themed for **Northlake University** and built to reskin per customer.

- **Login entrance** — the Northlake mark assembles (lake ripples expand, a gold
  spark settles, the lake horizon draws), then the wordmark rises and a gold
  underline draws. Targets `.auth-branding__figure`. ~2.2 s, then an optional
  ambient ripple.
- **Loading** — the generic Kendo ring is replaced by concentric lake ripples
  pulsing from a gold spark. Overrides `.k-loading-mask .k-loading-image` (56×56),
  ~1.2 s seamless loop, with a Lottie full-page splash variant.

Open `login-animation.html` and `loading-animation.html` in any browser to preview
each (engine toggle, replay, and a reduced-motion preview are built in).

---

## Library & license

| Dependency | Used for | License |
| --- | --- | --- |
| **lottie-web** `5.12.x` ([CDN](https://unpkg.com/lottie-web)) | Login entrance + loading splash JSON playback | **MIT** |
| Pure CSS / SVG | Loading spinner (in-mask) + login fallback engine | none (zero-dependency) |
| Spectral, IBM Plex Sans, IBM Plex Mono (Google Fonts) | Wordmark + UI type | **OFL 1.1** |

**No GSAP / GreenSock.** Every moving part is MIT or zero-dependency. lottie-web is
loaded once for the whole app; each customer is then just a different `.json`.

> The hand-authored `.json` files here are a working POC. Production JSONs would
> normally come from a designer (After Effects → Bodymovin, or LottieFiles).

---

## Files & where they go

| File | What it is | Drop into |
| --- | --- | --- |
| `login-animation.html` | Preview + integration for the login entrance (Lottie **and** CSS/SVG engines) | reference / demo |
| `loading-animation.html` | Preview + integration for the loading mask + Lottie splash | reference / demo |
| `northlake-login.json` | Lottie source — login mark assembly (one-shot) | `app/branding/` (served as a static asset) |
| `northlake-loading.json` | Lottie source — loading ripple loop / splash | `app/branding/` |
| `loading-animation.less` | **Drop-in LESS** overriding `.k-loading-mask .k-loading-image` | **supersedes `loading-animation.less`** |
| `northlake-theme-vars.css` | The five `--color-*` custom-property overrides (+ optional helpers) | global theme layer / `:root` |
| `northlake-mark.svg` | Static Northlake mark (reduced-motion / no-JS fallback, favicon-safe) | `app/branding/` |

### Login entrance — wiring
1. Inside `login/_auth-branding.less`'s `.auth-branding__figure`, replace the static
   `<img>` with a mark host + caption (see snippet 1 on the page).
2. Mount the Lottie (snippet 2) — `fetch` the JSON and pass it as `animationData`,
   then add `is-playing` to the figure to drive the caption + underline (snippet 3).
3. Prefer the CSS/SVG engine instead? The same inline SVG + keyframes ship with no
   runtime — toggle "CSS / SVG" on the page to compare.

### Loading — wiring
1. Replace `loading-animation.less` with the provided `loading-animation.less`.
   It targets the real Kendo selectors, so no markup changes are required; keep the
   optional `.k-loading-text` element for the caption.
2. For a richer full-page boot splash, use `northlake-loading.json` with the same
   lottie-web player (snippet 2 on the loading page).

---

## Reduced motion

Every deliverable honours `@media (prefers-reduced-motion: reduce)`:

- **Login** — animations are *additive*: the composed lockup (mark + wordmark +
  underline) is the **default** state, so no-JS, slow-connection, and reduced-motion
  users see the final result with no flash. JS renders the Lottie's **last frame**
  statically when reduction is requested.
- **Loading** — the ripples and spark stop; the mask holds a calm two-ring static
  mark plus the caption. The Lottie splash stops on a representative frame.

Both pages include a **"Preview reduced motion"** button so you can verify the
fallback without changing OS settings.

---

## Reskin for another customer

The whole system is driven by five theme hooks the EEM app already exposes. To
onboard a new customer, change values — not code.

**1 · Set the theme vars** (`northlake-theme-vars.css`):

```css
:root{
  --color-primary:   #14263F;  /* deepest brand tone — gradient base / ink   */
  --color-primary-2: #1F3A5F;  /* brand color — panel + mark                 */
  --color-accent:    #C9A227;  /* highlight — spark, ripples, underline      */
  --color-tertiary:  #2E6E7E;  /* support — secondary ripple                 */
  --font-size-sm:    0.875rem; /* caption / loading text                     */
}
```

The ripples, spark, underline, panel gradient and caption all read these — the
CSS/SVG engine and the loading mask reskin instantly.

**2 · Swap the mark / motion source:**
- **Lottie path** → replace `northlake-login.json` / `northlake-loading.json` (and
  the colors baked into them). Same player, same markup.
- **CSS/SVG path** → swap `northlake-mark.svg` and the inline `<svg>` in the page's
  `#nl-css-mark` template; the one hard-coded value is the loading spark's `fill` in
  the data-URI (one line in `loading-animation.less`).

No JavaScript or keyframe changes are needed for a reskin.

---

## Notes

- Lottie JSONs are loaded via `fetch(...).then(r => r.json())` + `animationData`
  (rather than lottie's `path:` option) so they work regardless of how the runtime
  resolves relative URLs in your bundler.
- The mark geometry (navy roundel · gold north-star spark · two gold lake-horizon
  bars) follows the Northlake University identity; on the navy panel it is shown as
  a reverse lockup (gold knocked out of navy), so the hard navy disc is omitted.
