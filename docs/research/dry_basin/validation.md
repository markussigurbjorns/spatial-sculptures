# Computational validation — 6 October 2026

These checks verify equations, software and export behavior. They do not validate
a fabricated vessel, hydrophone pressure, radiation or spatial perception.

| Check | Result |
| --- | --- |
| Ordinary Python compilation | Passed for source, prototypes, studies, tools and tests |
| Ruff lint and formatting | Passed |
| Unit suite with NumPy | 69 tests: 68 passed; UDP-delivery test skipped because sockets are forbidden |
| Unit suite without NumPy | 69 tests: 55 passed; 13 optional NumPy tests and the UDP test skipped |
| Imports without Blender | Core wave/state/sensor/modal modules import without `bpy`; NumPy-dependent structural modules are explicitly optional |
| Numerical plate verification | First six frequencies within 0.1517%; finest-mesh shape MAC ≥0.999991 |
| Free shell and membrane checks | Six rigid motions, mass orthogonality and analytical flat membrane energy passed |
| Physical structural changes | Curvature changes eigenmodes; support stiffening raises frequencies; added mass lowers them |
| Basin mesh comparison | 8 × 8 versus 10 × 10: max 0.3847% for first ten ordered frequencies, 2.118% for all sixteen |
| Basin integration comparison | Gauss order 5 versus 7: max 0.001883% on baseline 8 × 8 mesh |
| Cache and replay | Mode normalization and arrays survive save/load; keys track structure/source; forcing/presentation changes reuse modes |
| Audio/visual state | WAV samples match reconstructed physical contact velocity within PCM quantization; video times and energy match the same response |
| Exposure and slow inspection | Exposure average checked against dense sampling; slowing picture leaves physical WAV duration unchanged |
| Dry Blender adapter | Vector coordinates, common time origin, audio strip, scrubbing, module reload, callback cleanup and silent slow inspection passed in Blender 4.5.9 |
| Existing Blender consumers | Original water prototype and analytical plate integrations passed |
| Actual MP4 export | 60 H.264 frames at 30 FPS; stereo 48 kHz AAC; both streams exactly 2.000 s |
| Unsupported request | Positive water depth and invalid damping/direction rejected before creating caches |
| Working-directory independence | Saved configuration launched successfully from `/tmp`, including output path with spaces |
| Audibility / hardware playback / SuperCollider server | Not evaluated; audio-device and server runtime validation unavailable here |
| Curved-shell exact benchmark / measured vessel / fluid coupling | Not yet implemented or measured |

The baseline discrete eigenproblem residual was below 3 × 10⁻⁸, with scaled mass
condition number about 787. This measures the algebraic solve, not physical accuracy.
Higher retained modes and broadband impulse signals are not declared converged.
Changed thickness/profile/support settings need their own refinement checks.

Reproduce software checks:

```bash
python -m compileall -q src prototypes studies tools tests
ruff check .
ruff format --check .
PYTHONPATH=src python -m unittest discover -s tests
blender --background --factory-startup --python-exit-code 1 --python tests/validate_dry_blender.py
blender --background --factory-startup --python-exit-code 1 --python tests/validate_modal_blender.py
blender --background --factory-startup --python-exit-code 1 --python tests/validate_blender.py
python tools/run_dry_basin.py --preview --render
```

Regenerate the curated paper data and figures from the repository root:

```bash
python tools/validate_structure.py --output docs/research/dry_basin/verification.json
python - <<'PY'
import json
import subprocess
import sys
from pathlib import Path

reports = {}
for source in sorted(Path('prototypes/001_resonant_surface/dry/experiments').glob('[0-9]*.py')):
    output = Path('prototypes/001_resonant_surface/renders/dry_experiments') / source.stem
    subprocess.run([
        sys.executable, 'tools/run_dry_basin.py', '--experiment', source.stem,
        '--duration', '0.5', '--preview', '--output', str(output),
    ], check=True)
    reports[source.stem] = json.loads((output / 'report.json').read_text())
Path('docs/research/dry_basin/results.json').write_text(json.dumps({
    'scope': 'provisional dry shell, no physical measurements or fluid coupling',
    'reports': reports,
}, indent=2))
PY
python tools/plot_dry_basin.py
```

The plotting tool rejects source/hash mismatches before producing figures. Curated
JSON contains source provenance and full parameters; cached coefficients and run
outputs can be regenerated. The render adapter computes no shell or oscillator
equation. Its Blender validation script first generates an offline test fixture
and then exercises the adapter.
