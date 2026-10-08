// Run the studio's own OpenSCAD (WebAssembly) from Node, the way compile-worker.js does in the browser.
//   node tools/openscad_node.mjs input.scad output.(stl|svg|csg)
// `import("/author/<file>.stl")` in the code resolves to author/<file>.stl in this repository. Used by the geometry tests,
// so they need no OpenSCAD install.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [input, output] = process.argv.slice(2);
const code = fs.readFileSync(input, 'utf8');
const {default: OpenSCAD} = await import(path.join(root, 'vendor/openscad/openscad.js'));
const log = [];
const m = await OpenSCAD({noInitialRun: true, print: t => log.push(t), printErr: t => log.push(t),
  wasmBinary: fs.readFileSync(path.join(root, 'vendor/openscad/openscad.wasm'))});
const read = f => new Uint8Array(fs.readFileSync(f));
for (const d of ['/fonts', '/fontcache', '/author']) m.FS.mkdir(d);
for (const f of ['LiberationSans-Bold.ttf', 'LiberationSerif-Bold.ttf', 'DejaVuSans-Bold.ttf']) m.FS.writeFile('/fonts/' + f, read(path.join(root, 'fonts', f)));
m.FS.writeFile('/fonts/fonts.conf', '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/fonts</dir><cachedir>/fontcache</cachedir></fontconfig>');
m.ENV.FONTCONFIG_PATH = '/fonts'; m.ENV.FONTCONFIG_FILE = '/fonts/fonts.conf';
const files = new Set(['Labels.scad', 'Accepted_Geometry.scad', ...[...code.matchAll(/\/author\/([\w.-]+\.stl)/g)].map(x => x[1])]);
for (const f of files) m.FS.writeFile('/author/' + f, read(path.join(root, 'author', f)));
m.FS.writeFile('/input.scad', code);
const ext = path.extname(output);
const result = m.callMain(['/input.scad', '--backend=Manifold', '--enable=textmetrics', '-o', '/output' + ext]);
if (result !== 0 || log.some(l => /^ERROR:/.test(l))) { process.stderr.write(log.join('\n') + '\n'); process.exit(1); }
fs.writeFileSync(output, m.FS.readFile('/output' + ext));
process.stderr.write(log.join('\n') + '\n');
