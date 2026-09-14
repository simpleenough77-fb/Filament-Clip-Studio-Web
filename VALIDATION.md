# Browser edition validation (2026-09-13)

- Direct OpenSCAD WASM compilation found errors in old npm builds and a hull error for Bambu in official 2025.03.25 build. These are not accepted output.
- Final browser uses binary body masters generated with desktop OpenSCAD from unchanged Accepted_Geometry.scad; browser only subtracts and generates label parts. Public users cannot change official spool dimensions through UI.
- First downloaded browser ZIP contains one 3MF plus CSV, two variants, eight separate meshes, two instances, one H2D plate, black and Bambu Green material mappings. Archive CRC validation passed.
- Bambu Studio 02.08.02.61 --info successfully imported the generated 3MF; both clip assemblies report manifold=yes and expected widths 68 and 62.5 mm.
- Headless --slice aborted. No claim of successful slicing or physical printing is made for this browser export. Existing Bambu Studio window contains unrelated unsaved work and was not replaced.
- Browser stress test: 100 instances of two variants generated onto four H2D plates (30/30/30/10). ZIP CRC, instance count, and CSV quantities passed.
- Browser regression harness: mixed-validity CSV skips records with CSV rows 3 and 5; long text ends in one period; generation blocks until acknowledgment; actual filament variants occupy separate plates. Entire 11-clip test completed in 3.959 seconds on the development computer. This is not a performance promise for other devices or 100 distinct variants.

## Side-standing and holder sleeve update — 2026-09-14

- Owner reported successful printing of the previous browser edition.
- CSV import action visually checked with its select aligned to the neighboring buttons.
- Added the two owner-provided complete holder-sleeve STL bodies, preserved byte-for-byte. Their positive standing coordinates are rigidly mapped into label coordinates before lettering; complete assemblies are then rotated -90 degrees around X and centered for packing. No scaling, inferred collar reconstruction, or deformation.
- All six combinations (sleeve yes/no × inlay/engraved/modifier) generated and passed archive, 33 mm height, bed contact, body edge-incidence, and footprint containment checks. Tiny triangles collapsed to repeated vertex indices by STL conversion are omitted because they have zero area.
- Browser regression checks passed with sleeve enabled, including long-name acknowledgment and 11 actual-filament clips on separate plates. Downloaded 3MF inspected: correct sleeve setting, 11 instances and 33 mm heights. Bambu Studio --info reports both assemblies manifold.
- Sleeve source files and label preview coordinate frames remain distinct: flat label previews show the readable face; plate previews/thumbnails use standing geometry. New sleeve print and holder fit are not independently confirmed.

## Sleeve label-face correction — 2026-09-14

- Owner's slicer screenshot identified text on the connector side. Previous bounds/manifold tests did not detect this placement error.
- Corrected the supplied sleeve's rigid rotation: its actual label face is at maximum input Y, not minimum Y. That face now maps to canonical Z=0; lettering extends inward into the original 3.6 mm plate. The collar, connectors and input STL bytes are unchanged.
- Added a regression that requires an outward-facing label surface at Z=0 exceeding 1900 mm²: Bambu 2172.653 mm²; Cookiecad 1995.002 mm². It also checks inward text extrusion after the standing rotation.
- Reran all six sleeve/style export combinations successfully, including manifold body, archive and packing containment checks. Physical printing of this correction remains for the owner to verify.
- Browser asset version advanced to sleeve-face-2. Previously downloaded 3MF files must be regenerated.
