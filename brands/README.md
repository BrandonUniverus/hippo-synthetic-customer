# Brand systems

Northlake University and the six organisations that serve it each have a small
design system here, so none of them looks like Energy Hippo or like each other.

| Folder | Organisation | Type | Character |
| --- | --- | --- | --- |
| `northlake/` | Northlake University | Spectral, IBM Plex Sans and Mono | Collegiate: warm paper, white header, navy and gold |
| `valley-electric/` | Valley Electric District | Public Sans | Public power portal: district blue, valley green |
| `river-city/` | River City Utilities | Barlow, Barlow Semi Condensed | Municipal signage: teal, one colour per service |
| `sierra-gas/` | Sierra Gas Utility | Libre Franklin | Corporate gas company: ember on granite |
| `helios/` | Helios Onsite Solar | Manrope | Modern product brand: midnight and sun yellow |
| `thermal-plant/` | Northlake Thermal Plant | Northlake's | A university department: Northlake unit lockup, plant slate |
| `ridgeline-wind/` | Ridgeline Wind | Archivo (expanded), IBM Plex Mono | Engineering: ridge green and sky, endorsed by the plant |

Open `https://localhost:8443/brands/` while the identity stack runs to see all
seven side by side. The page reads these files directly, so an edit shows on the
next refresh.

## What a brand folder holds

| File | Purpose |
| --- | --- |
| `tokens.css` | Every colour, type, spacing, corner and logo value, as CSS custom properties on `:root` |
| `fonts.css` | `@font-face` rules for the brand's self-hosted fonts |
| `fonts/` | Latin-subset WOFF2 files for pages, TTF files for PDF renderers, and each family's SIL Open Font License |
| `logo.svg` | The lockup for white and light surfaces |
| `logo-reversed.svg` | The lockup for the brand's dark surfaces |
| `mark.svg` | The symbol alone, for favicons and app tiles |

`thermal-plant/tokens.css` and `fonts.css` import Northlake's and override only
what differs. Ridgeline's `fonts.css` imports Northlake's for IBM Plex Mono.

## Token names

Every brand defines the same names, so a template written once takes any brand.

| Group | Names |
| --- | --- |
| Brand colour | `--primary`, `--primary-strong`, `--on-primary`, `--accent`, `--accent-ink`, `--on-accent`, `--support` |
| Neutrals | `--ink`, `--muted`, `--canvas`, `--surface`, `--tint`, `--line`, `--line-strong`, `--link`, `--heading-ink` |
| Status | `--positive`, `--negative`, `--caution` and their `-tint` backgrounds |
| Page chrome | `--topbar-bg`, `--topbar-ink`, `--header-bg`, `--header-ink`, `--header-rule`, `--footer-bg`, `--footer-ink` |
| Type | `--font-display`, `--font-text`, `--font-mono`, `--weight-display`, `--weight-strong`, `--tracking-display`, `--case-heading`, `--case-label`, `--case-button`, `--size-h1` to `--size-label`, `--leading-body` |
| Space and shape | `--space-1` to `--space-8`, `--content-width`, `--radius`, `--rule`, `--rule-accent` |
| Logo use | `--logo-height`, `--logo-min-height`, plus clear-space and background rules in the comment beside them |

River City adds `--service-water`, `--service-sewer` and `--service-storm`; the
Thermal Plant adds `--commodity-chilled`, `--commodity-steam` and
`--commodity-power`; Ridgeline adds `--stretch-display`.

Every text colour pair (body, muted, links, button text, header, footer, status)
meets WCAG AA 4.5:1 on its background. Check again after changing a colour.

## Editing

- **Colours, type, spacing, corners:** edit `tokens.css`. Pages that load it pick
  the change up on refresh. Keycloak's sign-in pages cache stylesheets in the
  browser: bump `assetVersion` in `identity/themes/northlake/login/theme.properties`.
- **Logos:** the lettering is outlined to paths, because browsers never load web
  fonts for an SVG shown through `<img>`, a favicon or an email. Change the
  geometry or words in `tools/build_logos.py`, then run
  `python brands/tools/build_logos.py` (needs `fonttools` and `brotli`).
- **Fonts:** all are SIL Open Font License faces from Google Fonts, vendored on
  2026-11-05. Keep the matching `OFL-*.txt` beside any font you add.

## Who uses which brand

| Brand | Used by today |
| --- | --- |
| Northlake | The Northlake site at `https://localhost:8443/`, the Keycloak sign-in, account and admin themes, the configuration pages, the customer browser lab and the handheld simulator. `identity/branding/brand.css` maps the older `--nl-*` names onto these tokens. |
| The six providers | Not yet applied. The provider pages at `localhost:18081`, the utility bills and Northlake's PDFs are produced inside the source producer image, and the bill and PDF renderers are part of the producer's `source_fingerprint`. Restyling them needs a new source release with a new state volume, so it waits for that release. |

When that release happens, the renderers should read colours and fonts from
these folders (`tokens.css` is plain enough to parse in a few lines) instead of
keeping their own copies, for example the provider colours at the top of
`generators/render_bills.py` and `services/sources/web/sources.css`.
