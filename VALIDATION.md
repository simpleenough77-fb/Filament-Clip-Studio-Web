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

- Published the completed macro-enabled workbook at `downloads/Filament_Label_Builder.xlsm`. SHA-256: `f358ffe65df0db1e955e16a59433e5540acc611bf16709beff5b482ec04954cb`.
- The studio includes a direct download link beside the CSV import controls. The workbook remains separate from browser generation and exports the import CSV for the studio.
- ZIP integrity validation passed for the workbook.

## User guide - 2026-09-17

- Added `guide.html` with the studio workflow, Excel CSV builder, styling choices, sleeve support instructions, CSV validation, long-name behavior, and troubleshooting.
- Added a visible User guide / how-to link beside the studio status badge.

## Revised tunnel support clearance — 2026-09-21

- Owner supplied a revised `Filament_Labels.3mf` with a larger tunnel blocker and updated support painting. The attachment SHA-256 is recorded in `author/Tested_Sleeves_Provenance.json`.
- The generated sleeve assets use a 4 mm diameter tunnel blocker and the revised plate-face support paint.
- A derived 0.5 mm relief removes 0.25 mm from each end of the central tunnel, leaving the plate and retaining legs unchanged. The resulting Bambu and Cookiecad sleeve meshes are manifold in the OpenSCAD export.
- Regression coverage passes for sleeve/no-sleeve and inlay/engraved/modifier output combinations. Physical performance of this new relief remains to be confirmed by the owner's print test.
