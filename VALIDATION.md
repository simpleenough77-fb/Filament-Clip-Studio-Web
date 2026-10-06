# Browser edition validation (2026-09-13)

- Direct OpenSCAD WASM compilation found errors in old npm builds and a hull error for Bambu in official 2025.03.25 build. These are not accepted output.
- Final browser uses binary body masters generated with desktop OpenSCAD from unchanged Accepted_Geometry.scad; browser only subtracts and generates label parts. Public users cannot change official spool dimensions through UI.
- First downloaded browser ZIP contains one 3MF plus CSV, two variants, eight separate meshes, two instances, one H2D plate, black and Bambu Green material mappings. Archive CRC validation passed.
- Bambu Studio 02.08.02.61 --info successfully imported the generated 3MF; both clip assemblies report manifold=yes and expected widths 68 and 62.5 mm.
- Headless --slice aborted. No claim of successful slicing or physical printing is made for this browser export. Existing Bambu Studio window contains unrelated unsaved work and was not replaced.
- Browser stress test: 100 instances of two variants generated onto four H2D plates (30/30/30/10). ZIP CRC, instance count, and CSV quantities passed.
- Browser regression harness: mixed-validity CSV skips records with CSV rows 3 and 5; long text ends in one period; generation blocks until acknowledgment; actual filament variants occupy separate plates. Entire 11-clip test completed in 3.959 seconds on the development computer. This is not a performance promise for other devices or 100 distinct variants.

## Holder sleeves, supports and tunnel blockers — 2026-09-16

- Owner supplied `Filament_Labels.3mf` containing both sleeve geometries, painted support regions, and support blockers placed in each filament tunnel. SHA-256: `f2b1194666b655e084ebf41149ddb764625e8ce0bc57b31266766714920ba922`. Meshes and paint data are extracted with component transforms applied; unrelated printer/project metadata is omitted. Provenance and extracted geometry hashes are stored in `author/Tested_Sleeves_Provenance.json`.
- The generated studio now uses those two owner-tested mesh bodies. Sleeved clips are placed flat with text facing the bed. The user's support painting is transferred to all three label styles, and the tunnel support blockers are included as native Bambu Studio blocker parts.
- Selecting Holder sleeve immediately displays a warning that supports are required. The sleeved 3MF enables manual supports and uses the tested project's interface and clearance settings.
- All six combinations (sleeve yes/no × inlay/engraved/modifier) pass generated archive, manifold, height/footprint, support-paint, blocker and support-settings checks. Bambu Studio 02.08.02.61 `--info` imports the sleeved project and reports both clip bodies manifold, with footprints 68 × 33 mm and 62.5 × 33 mm.
- Owner reports the supplied 3MF printed successfully. New studio output is structurally verified and imports in Bambu Studio; no additional physical print of a newly generated project is claimed.
- The supported setup uses a 0.2 mm top and bottom Z gap, two interface layers on each side, 0.35 mm XY clearance and no build-plate-only restriction. Confirm the support preview and your own filament profile before printing.

## Excel label builder - 2026-09-17

- Updated the macro-enabled workbook at `downloads/Filament_Label_Builder.xlsm` from the owner-provided corrected file. SHA-256: `fb2573be51878d04decf68c8a4bad55d424c006e93264d8c8a0392f1a119104b`.
- The studio includes a direct download link beside the User guide / how-to link at the top of the page. The workbook remains separate from browser generation and exports the import CSV for the studio.
- ZIP integrity validation passed for the workbook.

## User guide - 2026-09-17

- Added `guide.html` with the studio workflow, Excel CSV builder, styling choices, sleeve support instructions, CSV validation, long-name behavior, and troubleshooting.
- Added a visible User guide / how-to link beside the studio status badge.

## Revised tunnel support clearance — 2026-09-21

- Owner supplied a revised `Filament_Labels.3mf` with a larger tunnel blocker and updated support painting. The attachment SHA-256 is recorded in `author/Tested_Sleeves_Provenance.json`.
- The generated sleeve assets use a 4 mm diameter tunnel blocker and the revised support paint, including sleeve coverage.
- A derived 0.5 mm relief removes 0.25 mm from each end of the central tunnel, leaving the plate and retaining legs unchanged. The resulting Bambu and Cookiecad sleeve meshes are manifold in the OpenSCAD export.
- Regression coverage passes for sleeve/no-sleeve and inlay/engraved/modifier output combinations. Physical performance of this new relief remains to be confirmed by the owner's print test.

## Owner-provided working sleeve project — 2026-09-21

- The supplied `Filament_Labels-Sleeve.3mf` is now the geometry reference. Its sleeve bodies preserve a continuous plate, shorten the tunnel ends without a plate notch, use 4 mm tunnel blockers, and carry support painting onto the sleeve/retaining geometry.
- Sleeve exports now force `enable_support=1` and `support_type=normal(manual)` whenever a tunnel blocker is present, even if the selected printer preset disables support.

## Multi-slicer export (2026-10-05)

Real exports from `tools/export_samples.py` (desktop OpenSCAD) were sliced with each slicer's command line on macOS (arm64):
Bambu Studio 02.08, Orca Slicer 2.4.x, ElegooSlicer 1.5.x and PrusaSlicer 2.9.6.

| Slicer | Printer groups tried | Result |
| --- | --- | --- |
| Bambu Studio | Bambu 350x320, 256x256 (sleeve), Creality 220x220, Prusa 250x210 (sleeve) | One G-code per plate; supports on sleeve files; tool changes on multi-color files |
| Orca Slicer | Bambu 350x320 / 256x256, Creality 220x220 / 400x400, Anycubic 300x300, Prusa 250x210 and 180x180 | One G-code per plate; every move inside the bed. Sleeve batch also opened in the app (Orca Slicer, generic Marlin printer): no support warning, plate 1 slices with manual supports (26.85 g). |
| ElegooSlicer | Bambu 256x256, Creality 220x220, Elegoo 256x256 / 325x325, Prusa 180x180 | One G-code per plate. Sleeve batch also opened in the app with the Elegoo Centauri Carbon system printer selected (which swaps the print profile): no support warning, plate 1 slices with manual supports (27.63 g). |
| PrusaSlicer | Prusa 250x210 (plain, sleeve, single, multi-color), Creality 300x300, Bambu 350x320 | Sliced; supports present; tool changes on multi-color |
| Creality Print 7.2.2 | not checked | Its command line crashes (SIGSEGV in `CLI::run`) even for `--info`, so only the version check could be exercised. |
| Snapmaker Orca 2.4.0 | Snapmaker U1 (270x270): four-color batch; two-plate sleeve + holders batch | Opened in the app and sliced to U1 G-code with a prime tower, every object on the bed. The sleeve batch, with the U1 profile selected, shows no support warning and slices plate 1 with manual supports (16 g). Its command line segfaults on every file, even with edits, so only the app was used. Plate 2 (holders) was not seen to finish. |
| Anycubic Slicer Next | not checked | Not installed (no Homebrew cask). Written as an Orca-family project. |

GUI checks (PrusaSlicer 2.9.4, Orca Slicer): both recognize the file as a project (PrusaSlicer's "Open as project" prompt; Orca's "customized preset" notice for the generic printer), and PrusaSlicer shows the supports and tunnel blockers.

Findings that shaped the writers:

- Snapmaker Orca replaces the project's print profile with the U1 profile (supports off) when the U1 is the printer, which drops project-level support settings. Orca-family sleeve objects therefore carry `enable_support` and `support_type` themselves.
- Snapmaker Orca's command line rejects a project whose version tag has a major version above 1 (`Snapmaker_Orca-2.3.3` fails with "File Version 2.3.0.3 not supported"), so the tag is `Snapmaker_Orca-01.10.00.00`, which both the app and the command line's version check accept.
- Orca, ElegooSlicer and Creality Print compare the file's version tag with their own; a Bambu Studio 02.08 tag is rejected by all three. Each slicer gets its own tag (see `author/slicers.py`).
- The full Bambu printer preset fails Orca's range checks (for example `tree_support_wall_count=-1`), and a project without settings loads "geometry only", which drops the plates. The Orca-family writer therefore carries a slim, valid config (about 70 settings).
- Bambu Studio rejects `gcode_flavor=marlin2`; `marlin` is accepted by all.
- PrusaSlicer 2.9 has one bed, so a batch with several plates is written as one project per plate. Supported clips need about 6 mm between them or its conflict check aborts.
- PrusaSlicer's and Creality Print's command lines crash on toolpath conflicts and some inputs; treat their crashes as tool bugs, not file errors, unless the same file also fails in the app.
