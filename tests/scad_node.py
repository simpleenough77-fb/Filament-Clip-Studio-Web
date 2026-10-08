"""Run OpenSCAD for the geometry tests through the studio's own WebAssembly build (tools/openscad_node.mjs), so they
need no OpenSCAD install. Use as `g.run_scad = scad_node.runner(workdir)`."""
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools' / 'openscad_node.mjs'


def runner(work):
    work = Path(work)
    async def run(code, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        source = target.with_suffix('.scad')
        # The generator names files by their real path; the WebAssembly build sees them under /author.
        source.write_text(code.replace(str(ROOT / 'author'), '/author'))
        p = subprocess.run(['node', str(RUNNER), str(source), str(target)], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return p.stderr
    return run
