# Northlake identity branding

The Northlake site, the Keycloak sign-in pages, the account and realm
administration consoles, the configuration pages, the customer browser lab and
the handheld simulator all wear the Northlake University identity. Northlake is
a fictional university in a local development environment.

The design system itself lives in [`brands/northlake/`](../../brands/README.md):
its `tokens.css` holds every colour, type and spacing value, `fonts.css` the
self-hosted Spectral and IBM Plex faces, and the logo files sit beside them.
This folder holds the page chrome that uses it.

## Files

| File | Purpose |
| --- | --- |
| `brand.css` | Imports `brands/northlake/fonts.css` and `tokens.css`, then maps the older `--nl-*` names these pages use onto the brand tokens, with fallbacks. Every surface loads it first. |
| `site.css` | Shared page chrome for the site, configuration pages, customer lab and handheld: university bar, white masthead with the gold rule, buttons, fields, badges, notices, navy footer. |
| `console.css` | PatternFly 5 overrides for the Keycloak account and administration consoles. |
| `northlake-mark.svg`, `northlake-mark-reversed.svg`, `favicon-32.png` | The symbol alone; the roundel version doubles as the SVG favicon. |
| `northlake-logo.svg`, `northlake-logo-reversed.svg`, `northlake-header-logo*.png`, `fonts/` (Open Sans) | The previous Open Sans lockups and faces. The provider pages baked into the source image and the EEM portal kit in `documents/brand/` still use them; new pages use `brands/northlake/logo*.svg`. |

`brand.css` imports with relative paths (`../brands/northlake/...`), which
resolve wherever this folder sits beside `brands/`: under Caddy (`/branding/`
and `/brands/`), inside the Keycloak themes (`resources/branding` and
`resources/brands`) and in the handheld image. A page served without the
brands folder falls back to the literal values in `brand.css`.

Do not redefine the brand token names (`--primary`, `--line`, `--muted` and the
rest, listed in `brands/README.md`) from `--nl-*` names in a page stylesheet:
`brand.css` maps those names back, so the pair becomes circular and both values
turn invalid.

## How the assets are served

Caddy serves this directory at `/branding/` and `brands/` at `/brands/` on both
local hosts with `Cache-Control: no-cache`, so edits show up on the next
refresh. Compose mounts both into the three Keycloak theme types as
`resources/branding` and `resources/brands`; keep the empty mount-point
directories under `identity/themes/northlake/*/resources/` so Docker Desktop can
nest the mounts inside the read-only theme directory. The handheld image copies
this folder and `brands/northlake` at build time.

## Keycloak themes

`identity/themes/northlake` holds three themes, assigned to every generated
realm by `generate_realm.py` (including the two lab realms). Existing realms can
select `northlake` for Login, Account and Admin under Realm settings, Themes.

- `login/` extends `keycloak.v2`. `template.ftl` owns the page chrome (white
  masthead with the lockup and "Information Technology Services", card, help
  band, navy footer naming the realm); `footer.ftl` is the help band;
  `info.ftl` avoids the duplicated summary on sign-out and similar pages;
  `messages/messages_en.properties` carries the Northlake wording ("Sign in
  with your NetID"); `resources/css/northlake.css` styles every PatternFly 5
  page the parent theme renders (sign-in, password reset, forced password
  update, authenticator setup, one-time codes, passkeys, recovery codes,
  consent, errors, expired pages). Keep `template.ftl` in step with the parent
  when Keycloak is upgraded.
- `account/` extends `keycloak.v3` and `admin/` extends `keycloak.v2`. Both are
  configuration only: `console.css`, the reversed lockup from
  `brands/northlake` as the masthead brand, and the favicon.

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
