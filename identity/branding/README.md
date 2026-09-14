# Northlake identity branding

The Keycloak login pages, account console and realm administration console,
the launchpad, the configuration pages and the customer browser lab all wear
the same Northlake University identity. Northlake is a fictional university in
a local development environment.

Brand sources: `output/branding/Brand Assets.dc.html`,
`output/branding/Login Mockup.dc.html` and
`customer-provided/northlake-university/eem-application-branding.md`.

## Files

| File | Purpose |
| --- | --- |
| `brand.css` | Palette tokens (`--nl-*`), the self-hosted Open Sans faces and the focus ring. Every surface loads it first. |
| `site.css` | Shared page chrome for the launchpad, configuration pages and customer lab: masthead, buttons, fields, badges, notices, footer. |
| `console.css` | PatternFly 5 overrides for the Keycloak account and administration consoles. |
| `northlake-logo.svg`, `northlake-logo-reversed.svg` | Horizontal lockups (mark + wordmark) for light and navy backgrounds. The wordmark is outlined, so they render identically in `<img>`, favicons and email. |
| `northlake-mark.svg`, `northlake-mark-reversed.svg` | The symbol alone. The roundel version doubles as the SVG favicon. |
| `favicon-32.png` | PNG favicon fallback. |
| `northlake-header-logo*.png` | Older raster lockups kept for anything that still needs a PNG. |
| `fonts/` | Open Sans Regular, Semibold, Bold and ExtraBold (WOFF2, Apache 2.0, see `fonts/LICENSE.txt`). |

Regenerate the outlined lockups after changing the wordmark geometry with
`python generators/outline_brand_lockups.py` (needs `fonttools` and `brotli`).
It writes the same two files to `output/branding/images/custom/` and here.

## Palette

Navy `#1F3A5F` is the primary colour and the masthead. Gold `#C9A227` is the
accent: the masthead rule, focus rings on navy controls, current-page markers
and warning notices. Small gold-coloured text uses the darker `#806414` so it
passes contrast on white. Slate `#5B6573` is secondary text, `#2B3340` body
text, `#F5F6F8` the page canvas. Corners are square everywhere.

## How the assets are served

Caddy serves this directory at `/branding/` on both local hosts with
`Cache-Control: no-cache`, so edits show up on the next refresh. Compose also
mounts it into the three Keycloak theme types as `resources/branding`; keep the
empty `resources/branding` mount-point directories under
`identity/themes/northlake` so Docker Desktop can nest the mount inside the
read-only theme directory.

## Keycloak themes

`identity/themes/northlake` holds three themes, assigned to every generated
realm by `generate_realm.py` (including the two lab realms). Existing realms can
select `northlake` for Login, Account and Admin under Realm settings, Themes.

- `login/` extends `keycloak.v2`. `template.ftl` owns the page chrome (masthead
  with the lockup and the realm display name, card, help band, footer);
  `footer.ftl` is the help band; `info.ftl` avoids the duplicated summary on
  sign-out and similar pages; `messages/messages_en.properties` carries the
  Northlake wording; `resources/css/northlake.css` styles every PatternFly 5
  page the parent theme renders (sign-in, password reset, forced password
  update, authenticator setup, one-time codes, passkeys, recovery codes,
  consent, errors, expired pages). Keep `template.ftl` in step with the parent
  when Keycloak is upgraded.
- `account/` extends `keycloak.v3` and `admin/` extends `keycloak.v2`. Both are
  configuration only: `console.css`, the reversed lockup as the masthead brand
  and the favicon.

Compose starts Keycloak with theme caching and the gzip resource cache
disabled, so template, message and stylesheet edits are live on refresh. Browsers
still cache the login stylesheets under Keycloak's fixed resource path, so bump
`assetVersion` in `login/theme.properties` after editing the CSS; the template
appends it to every stylesheet URL.

## Visual review

`python identity/scripts/capture_theme_gallery.py` walks the real flows in a
headless browser and writes desktop and phone screenshots of every page to
`identity/.runtime/evidence/theme-gallery/`. It needs Playwright
(`python -m pip install playwright`, then `python -m playwright install
chromium`) and creates, then deletes, a throwaway `theme.preview` user.
