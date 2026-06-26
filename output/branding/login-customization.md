# Northlake University Energy Portal — Login Customization (`CustomLoginInfo`)

Ready-to-transcribe values for the EEM Suite login customization screen. All values
are taken verbatim from `eem-application-branding.md`. Synthetic / fictional.

Brand palette: deep navy `#1F3A5F` · warm gold `#C9A227` · slate gray `#5B6573` · white `#FFFFFF`.
Typeface: Open Sans.

---

## 1 · Core fields

| Field | Value to enter |
| --- | --- |
| `HeaderRightLogoUrl` | `/images/custom/northlake-header-logo.png` |
| `HeaderRightLogoTitle` | `Northlake University` |
| `HideHeader` | `false` |
| `HideFooter` | `false` |
| `LoginHeader` (kicker) | `Energy & Utility Management` |
| `LoginTitle` | `Northlake University` |
| `LoginTitleUnderline` | `Energy Portal` |
| `LoginDescription` | `Secure access to Northlake's campus energy, utility, and sustainability data.` |
| `LoginLaptopCaption` | `Manage Northlake's energy with EEM Suite` |
| `LoginCustomerLogoPath` | `/images/custom/LoginLogoRight.png` |
| `LoginCustomerLogoTitle` | `Northlake University Energy Portal` |
| `LoginHeaderColor` (kicker color) | `#C9A227` |
| `LoginHeaderFontColor` | `#FFFFFF` |
| `HeaderBackGroundColor` | `#1F3A5F` |
| `BackGroundColor` | `#F5F6F8` |
| `LoginFooterTitle` | `Need help?` |
| `EEMLinkURL` | `https://sustainability.northlake.example.edu` |
| `EEMLinkURLText` | `Northlake Sustainability` |

---

## 2 · Feature bullets (`Bullets[]` — Title + Description)

| # | Title | Description |
| --- | --- | --- |
| 1 | `All your utilities, one portal` | `Electricity, gas, water, thermal, and solar across every property.` |
| 2 | `Cost & usage at a glance` | `Track spend and consumption by building, account, and meter.` |
| 3 | `Sustainability built in` | `ENERGY STAR scores and greenhouse-gas reporting from the same data.` |
| 4 | `Right access for every team` | `Facilities, Finance, Housing, and Sustainability each see what they need.` |

---

## 3 · "Need help?" footer contacts (`LoginFooterContact1..3`)

| Slot | Type | Pre | Value | Post |
| --- | --- | --- | --- | --- |
| 1 | `email` | `Email` | `energy.support@northlake.example.edu` | — |
| 2 | `other` (phone) | `Call` | `(916) 555-0142` | `(Mon–Fri, 8am–5pm PT)` |
| 3 | `url` | `Status` | `https://status.northlake.example.edu` | — |

## 4 · Partners (`Partners[]`)

None for launch. (Optional future: Helios Onsite Solar.)

---

## 5 · Image assets (upload to `images/custom/`)

| Slot | File |
| --- | --- |
| Header (top-right) logo | `images/custom/northlake-header-logo.png` (200×48, transparent) |
| Login hero (right panel) | `images/custom/LoginLogoRight.png` (800×600) |
| Favicon | `images/custom/favicon-32.png` (32×32) |
| App icons | `images/custom/app-icon-192.png`, `images/custom/app-icon-512.png` |
| Web manifest | `images/custom/site.webmanifest` (theme `#1F3A5F`) |

---

## Notes for the admin

- **Header logo + navy header.** `HeaderBackGroundColor` is navy (`#1F3A5F`) with white header
  text (`LoginHeaderFontColor #FFFFFF`). The default `northlake-header-logo.png` is the
  **positive** (navy + gold) lockup, which is built to read on a *light* header. Because your
  header background is navy, set `HeaderRightLogoUrl` to the **reversed** file instead —
  `images/custom/northlake-header-logo-reversed.png` (white + gold, ships in the same folder).
  Keep the positive file on hand if you ever switch the header to a light background.
- **Title underline.** `LoginTitleUnderline` ("Energy Portal") renders as a second line under
  `LoginTitle` ("Northlake University") with a gold underline accent — see the mockup.
- **Retina hero / logos.** `northlake-email-logo@2x.png` (296×76) is provided for high-DPI mail
  clients; the login assets are already exported at sufficient resolution.
