# Northlake documents

Northlake's documents are PDFs. The Markdown behind each one lives in
`sources/`, and each source renders as a Northlake University PDF at the same
path from the repository root:

| Source | PDF |
| --- | --- |
| `sources/documents/intake-package/00-cover-letter.md` | `documents/intake-package/00-cover-letter.pdf` |
| `sources/documents/guides/*.md` | `documents/guides/*.pdf` |
| `sources/documents/rate-tariffs/*.md` | `documents/rate-tariffs/*.pdf` |
| `sources/documents/brand/**/*.md` | `documents/brand/**/*.pdf` |
| `sources/implementation/**/*.md` | `implementation/**/*.pdf` |

The facilities and meter register, the source-system inventory and the gateway
coverage have no Markdown source: `generators/northlake_packet.py` renders them
straight from the packet.

## Render

```powershell
python -m pip install -r generators/requirements.txt
python generators/documents/build_documents.py
python generators/documents/build_documents.py --check
```

The build renders every source and rewrites a PDF only when its bytes change;
the output is deterministic. `--check` exits with status 1 when a PDF is missing
or stale, or when a link points at nothing. To render one file elsewhere:
`python -m generators.documents.render_northlake_pdf <source.md> <output.pdf>`.

## Writing a source

- One `#` title, `##` sections, `###` detail. Tables, lists, block quotes (set as
  gold callouts), fenced code and `---` rules are supported. Tables with eight or
  more columns, or rows that would wrap deeply, go on landscape pages.
- Write links relative to the PDF, not the source. Link another document by its
  `.pdf` name; link data, samples and code by their real path. The build reports
  any link whose target does not exist.
- The masthead shows the department and document type, and the footer shows
  who prepared the document and when. `build_documents.py` sets defaults per
  folder: Northlake documents carry the packet issue date from
  `data/scenarios/northlake-onboarding-v1.yaml`, and `implementation/` documents
  are prepared by the Energy Hippo implementation team. Front matter overrides
  them:

  ```text
  ---
  department: Facilities Operations
  document_type: Implementation intake package
  prepared_by: Samantha Ireland, Director of Campus Operations
  ---
  ```

  Other fields: `title`, `subtitle`, `date`, `audience`, `status`,
  `document_label` (the running header on later pages).

## Customer voice

Documents under `documents/` are written as Northlake's Facilities, Housing,
Sustainability, Finance and IT teams would write them, before any
implementation-specific mapping. Use customer and facilities language: property,
site, building, department, cost center, utility account, service agreement,
meter, measured point, data source, billing contact. Avoid implementation
language: seed table, internal point id, gateway runtime, import component,
database schema.

## Fonts

| File | Source | License |
| --- | --- | --- |
| `fonts/OpenSans-*.ttf` | The brand's own faces in `identity/branding/fonts`, converted from WOFF2 | Apache 2.0 (`fonts/LICENSE-Apache-2.0.txt`) |
| `fonts/DroidSansMono.ttf` | Android font set; used for code | Apache 2.0 (`fonts/LICENSE-Apache-2.0.txt`) |
| `fonts/NotoSansSymbols-Subset.ttf` | Noto Sans Symbols, cut to the arrow, math, box, shape, symbol and dingbat blocks; used for glyphs Open Sans lacks | SIL OFL 1.1 (`fonts/OFL-NotoSansSymbols.txt`) |

The brand kit has no italic Open Sans, so emphasis is set in Semibold. Status
emoji print as coloured symbols, and subscript digits as real subscripts.
