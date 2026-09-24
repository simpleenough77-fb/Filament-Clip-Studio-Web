# Filament Clip Studio — browser edition

Generate readable filament clips for the accepted Bambu Lab and Cookiecad spool fits. This free static application runs its calculations on your device, with no account, paid generation service, or uploaded batches.

## Use

Choose filament combinations, import a CSV if desired, review labels and any shortened names, then download a ZIP containing one multi-plate Bambu Studio 3MF and an import-ready CSV. Assign the real printing filament presets and inspect the slice in Bambu Studio before printing.

The official catalog is maintained through this repository by its owner. Visitors can select catalog entries; there is no public catalog-writing endpoint. Forks may maintain their own catalogs under the license. Drafts and named batches are stored in browser local storage and do not synchronize between devices. Download CSV backups before clearing browser data.

The first visit downloads about 28 MB of application/runtime assets. A desktop browser is recommended for large batches. Quantity is limited to 100 clips. Three fonts, independent text parts, engraved/modifier styles, printer keep-outs and actual-filament plate grouping are supported. Clips are exported standing on their sides (33 mm tall), with plate layout based on their standing footprints. Choose **Holder sleeve → Include holder sleeve** to use the author-supplied collar models for AMS holders; the correct version is selected automatically for each spool. Spreadsheet CSV files are uploaded with Import CSV, or rows copied from a spreadsheet are added with Paste rows.

## Local use and hosting

Serve this directory as static files (for example `python3 -m http.server 8000`) and open http://localhost:8000. Do not open index.html with file://. All runtime dependencies are included; no generation server is needed. The site is published by the workflow described below. There are no credentials, analytics, paid API calls, or private batch files in this distribution.

## Mechanical lineage

The accepted revision-10 `author/Accepted_Geometry.scad` is unchanged. Bambu width is 68 mm, Cookiecad 62.5 mm, plate thickness 3.6 mm, and retainer corner radius 3 mm. The owner accepted physical prototype fits and confirmed successful printing of the previous browser export. The new side-standing sleeve export still requires its own print/fit check. These clips are filament retainers, not spool carrying handles.

MGM86's excellent filament clips inspired the design and served as visual/dimensional references. See [MGM86](https://makerworld.com/en/@mgm86) and [Filament Clip with Label and Stock Indicator](https://makerworld.com/en/models/2163144-filament-clip-with-label-and-stock-indicator). No MGM mesh is bundled here. This attribution describes provenance; it is not an independent legal determination of originality.

The browser's OpenSCAD build encountered a hull error when directly compiling the Bambu body. Accordingly, author-generated binary body masters are compiled from the unchanged source using desktop OpenSCAD; the browser imports those masters and applies the variable lettering. Changes to official spool fits require rebuilding the masters, preserving their source hashes, and physical testing.

## Validation and limits

On 2026-09-13, local browser tests generated both clip types, a 100-clip/4-plate shared-color project, and an 11-clip actual-filament project with separate plates. CSV invalid-record reporting and truncation acknowledgment passed. Bambu Studio 02.08.02.61 imported the two-clip project with both assemblies reported manifold. Headless slicing aborted in this environment, so successful slicing and physical printing of the browser exports remain unverified. Read `VALIDATION.md` before relying on the release.

## License

Application code and original project contributions: GPL-3.0-or-later, authorized by Avishai Avivi on 2026-09-13. See LICENSE. Third-party components retain their own licenses; see THIRD_PARTY.md. Manufacturer names identify compatibility and filament products; no endorsement is implied.

## Build, tests and deployment

GitHub Actions (`.github/workflows/pages.yml`) runs the fast checks on every push and pull request, then deploys `main` to Cloudflare Workers static assets (https://filamentclip.com, configured in `wrangler.jsonc`; headers in `_headers`). It needs the repository variable `CLOUDFLARE_ACCOUNT_ID` and secret `CLOUDFLARE_API_TOKEN` (Workers Scripts: Edit). When the variable `PRIMARY_HOST` is set, GitHub Pages serves only a redirect to it (old links keep working, and `downloads/catalog.csv` stays available there). The Pages source must be set to **GitHub Actions** (Settings → Pages).

- `python tests/test_quick.py` — catalog integrity, CSV import regressions and the catalog feed (no OpenSCAD needed).
- `node tests/test_paste.mjs` — conversion of rows pasted from a spreadsheet.
- `python tools/build_site.py` — writes `downloads/catalog.csv` (the Google Sheets builder imports it with `=IMPORTDATA`) and `SOURCE_HASHES.json`. The deploy also stamps the build badge with the commit and date. Both files are generated, not committed.
- The geometry tests in `tests/test_standing_exports.py` and `tests/test_sleeve_label_face.py` need a local OpenSCAD install and are run by hand.

The Google Sheets CSV builder: https://docs.google.com/spreadsheets/d/17I2c2LSQdosgysyYz1NXYAqdRnsjegUHCgwkq1jBLrE/copy
