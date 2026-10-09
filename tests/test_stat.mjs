// Checks what the usage Worker accepts and stores. Run: node tests/test_stat.mjs
import assert from 'node:assert/strict';
import { clean } from '../worker/stat.js';

const base = { clips: 4, holders: 1, plates: 2, printer: 'creality-220x220', nfc: false, sleeve: true, vendors: { 'Bambu Lab': 4 } };
let e = clean({ ...base, slicer: 'orca', multicolor: true });
assert.equal(e.slicer, 'orca'); assert.equal(e.multicolor, 1); assert.equal(e.printer, 'creality-220x220');
for (const s of ['bambu_studio', 'orca', 'creality_print', 'elegoo', 'anycubic', 'prusa']) assert.equal(clean({ ...base, slicer: s }).slicer, s);
assert.equal(clean({ ...base, slicer: 'cura' }).slicer, null);        // unknown values are not stored
assert.equal(clean({ ...base, slicer: "x'); DROP TABLE events;--" }).slicer, null);
assert.equal(clean(base).slicer, null); assert.equal(clean(base).multicolor, 0); // older pages send neither field
assert.equal(clean({ ...base, clips: 0 }), null);
assert.equal(clean({ ...base, printer: 'bambu-256x256-dual' }).printer, 'bambu-256x256-dual');
console.log('stat worker checks passed');
