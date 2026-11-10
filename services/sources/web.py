"""Static provider pages built from the same published file catalog."""
from __future__ import annotations

import html
import math
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import yaml

from .runtime import atomic_write


PALETTES = {
    "valley_electric_district": "ved", "sierra_gas_utility": "sgu", "river_city_utilities": "rcu",
    "northlake_thermal_plant": "ntp", "helios_onsite_solar": "hos", "ridgeline_wind": "rwl",
}


def render_pages(public: Path, source_root: Path, records, status: dict) -> None:
    public = Path(public)
    for filename in ("brand.css", "site.css", "northlake-logo-reversed.svg", "northlake-mark.svg"):
        atomic_write(public / "branding" / filename, (source_root / "identity" / "branding" / filename).read_bytes())
    for font in (source_root / "identity" / "branding" / "fonts").glob("*.woff2"):
        atomic_write(public / "branding" / "fonts" / font.name, font.read_bytes())
    atomic_write(public / "assets" / "sources.css", (Path(__file__).parent / "web" / "sources.css").read_bytes())
    template = (Path(__file__).parent / "web" / "page.html").read_text(encoding="utf-8")
    providers = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((source_root / "data" / "providers").glob("*.yaml"))]
    groups = defaultdict(list)
    all_records = []
    for record in records:
        groups[record.get("metadata", {}).get("provider", "")].append(record)
        all_records.append(record)
    release = html.escape(str(status["identity"].get("release_id", status["identity"].get("version", "Northlake"))))
    cutoff = html.escape(str(status.get("completed_through") or "Awaiting generation"))
    footer = f'<span>Northlake synthetic customer · Fictional source data</span><span>Through {cutoff}</span>'

    def page(target, title, body, palette="", root="./"):
        text = template.replace("{{root}}", root).replace("{{title}}", html.escape(title)).replace("{{palette}}", palette).replace("{{body}}", body).replace("{{footer}}", footer).replace("{{release}}", release)
        atomic_write(public / target, text.encode("utf-8"))

    cards = []
    bases = [("downloads", "All source files", all_records, None, None)]
    provider_accounts = {}
    for provider in providers:
        key = provider["id"]
        slug = key.replace("_", "-")
        name = provider["displayName"]
        provider_records = groups[key]
        cards.append(f'<a class="nl-card provider-card {PALETTES.get(key, "")}" href="providers/{quote(slug)}/"><span class="provider-band"></span><h2>{html.escape(name)}</h2><p>{len(provider_records):,} published files</p><span class="provider-open">Browse bills and data →</span></a>')
        prefix = "providers/" + slug
        bases.append((prefix, name, provider_records, provider, None))
        accounts = defaultdict(list)
        for record in provider_records:
            account = record.get("metadata", {}).get("account")
            if account:
                accounts[str(account)].append(record)
        provider_accounts[key] = sorted(accounts)
        for account, account_records in sorted(accounts.items()):
            bases.append((prefix + "/accounts/" + account, name + " · " + account, account_records, provider, account))
    collections = []
    for prefix, name, items, provider, account in bases:
        years = sorted({str(record.get("metadata", {}).get("period_start", ""))[:4] for record in items
                        if str(record.get("metadata", {}).get("period_start", ""))[:4].isdigit()}, reverse=True)
        collections.append((prefix, name, items, provider, account, prefix, years, None))
        for year in years:
            selected = [record for record in items if str(record.get("metadata", {}).get("period_start", "")).startswith(year + "-")]
            collections.append((prefix + "/years/" + year, name, selected, provider, account, prefix, years, year))
    body = '<section class="nl-intro"><p class="eyebrow">Northlake University</p><h1>Utility providers and source data</h1><p>Browse the providers serving the campus, download their bills and tariffs, and collect the source files used by Northlake’s meters.</p></section>'
    body += '<div class="provider-grid">' + "".join(cards) + '</div>'
    body += f'<section class="nl-card catalog-card"><div><h2>Gateway and reference files</h2><p>{len(all_records):,} files across the published gateway, billing and reference sources.</p></div><div class="actions"><a class="button secondary" href="downloads/">Browse all files</a><a class="button quiet" href="catalog.json">Download catalog</a></div></section>'
    page("index.html", "Northlake source data", body)
    for prefix, name, items, provider, account, base_prefix, years, selected_year in collections:
        months = defaultdict(list)
        for record in items:
            period = str(record.get("metadata", {}).get("period_start", ""))
            months[period[:7] if len(period) >= 7 else "reference"].append(record)
        month_keys = sorted(months, reverse=True)
        if "reference" in month_keys:
            month_keys.remove("reference")
            month_keys.append("reference")
        if not month_keys:
            month_keys = ["reference"]
        for month in month_keys:
            month_items = sorted(months[month], key=lambda item: item["path"])
            pages = max(1, math.ceil(len(month_items) / 100))
            for number in range(1, pages + 1):
                relative = f"{prefix}/{month}/{number}/index.html"
                depth = len(Path(relative).parts) - 1
                root = "../" * depth
                palette = PALETTES.get(provider["id"], "") if provider else ""
                title = html.escape(name)
                body = f'<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="{root}">All providers</a><span> / {title}</span></nav><section class="nl-intro"><p class="eyebrow">Bills, tariffs and meter data</p><h1>{title}</h1>'
                if provider:
                    address = provider.get("billing", {}).get("businessAddress", {})
                    address_text = ", ".join(str(value) for value in address.values() if value) if isinstance(address, dict) else str(address)
                    body += f'<p>{html.escape(address_text)}</p>'
                body += '</section>'
                if provider and provider_accounts[provider["id"]]:
                    provider_prefix = "providers/" + provider["id"].replace("_", "-")
                    body += '<nav class="month-list" aria-label="Billing account">'
                    current = ' aria-current="page"' if account is None else ""
                    body += f'<a class="button {"primary" if account is None else "secondary"}"{current} href="{root}{provider_prefix}/">All accounts</a>'
                    for choice in provider_accounts[provider["id"]]:
                        current = ' aria-current="page"' if choice == account else ""
                        body += f'<a class="button {"primary" if choice == account else "secondary"}"{current} href="{root}{provider_prefix}/accounts/{quote(choice, safe="")}/">{html.escape(choice)}</a>'
                    body += '</nav>'
                if years:
                    body += '<nav class="month-list" aria-label="File year">'
                    current = ' aria-current="page"' if selected_year is None else ""
                    body += f'<a class="button {"primary" if selected_year is None else "secondary"}"{current} href="{root}{base_prefix}/">All years</a>'
                    for choice in years:
                        current = ' aria-current="page"' if choice == selected_year else ""
                        body += f'<a class="button {"primary" if choice == selected_year else "secondary"}"{current} href="{root}{base_prefix}/years/{choice}/">{choice}</a>'
                    body += '</nav>'
                body += '<nav class="month-list" aria-label="File month">'
                for choice in month_keys:
                    current = ' aria-current="page"' if choice == month else ""
                    body += f'<a class="button {"primary" if choice == month else "secondary"}"{current} href="{root}{prefix}/{quote(choice)}/1/">{html.escape(choice)}</a>'
                body += f'</nav><section class="nl-card files-card"><div class="files-heading"><h2>{html.escape(month)}</h2><span>{len(month_items):,} files · Page {number} of {pages}</span></div>'
                if month_items:
                    body += '<div class="table-scroll"><table><thead><tr><th scope="col">File</th><th scope="col">Type</th><th scope="col">Source</th><th scope="col">Size</th></tr></thead><tbody>'
                    for record in month_items[(number - 1) * 100:number * 100]:
                        metadata = record.get("metadata", {})
                        file_name = Path(record["path"]).name
                        href = root + quote(record["url"], safe="/")
                        body += f'<tr><td><a href="{href}" download>{html.escape(file_name)}</a></td><td>{html.escape(str(metadata.get("kind", "file")))}</td><td>{html.escape(str(metadata.get("source", "")))}</td><td>{record["size"]:,} B</td></tr>'
                    body += '</tbody></table></div>'
                else:
                    body += '<p class="empty-state">No files have been published for this provider yet.</p>'
                body += '</section><nav class="actions pagination" aria-label="File pages">'
                if number > 1:
                    body += f'<a class="button secondary" href="{root}{prefix}/{month}/{number - 1}/">← Previous</a>'
                if number < pages:
                    body += f'<a class="button secondary" href="{root}{prefix}/{month}/{number + 1}/">Next →</a>'
                body += '</nav>'
                page(relative, name, body, palette, root)
                if month == month_keys[0] and number == 1:
                    landing_root = "../" * len(Path(prefix).parts)
                    page(prefix + "/index.html", name, body.replace(root, landing_root), palette, landing_root)
