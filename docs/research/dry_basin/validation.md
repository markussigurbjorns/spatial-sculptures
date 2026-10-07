# Computational validation — updated 7 October 2026

These checks verify equations, software and export behavior. They do not validate
a fabricated vessel, hydrophone pressure, radiation or spatial perception.

| Check | Result |
| --- | --- |
| Ordinary Python compilation | Passed for source, prototypes, studies, tools and tests |
| Ruff lint and formatting | Passed |
| Unit suite with NumPy | 93 tests: 92 passed; UDP-delivery test skipped because sockets are forbidden |
| Unit suite without NumPy | 93 tests: 56 passed; 36 optional NumPy tests and the UDP test skipped |
| Imports without Blender | Core wave/state/sensor/modal modules import without `bpy`; NumPy-dependent structural modules are explicitly optional |
| Numerical plate verification | First six frequencies within 0.1517%; finest-mesh shape MAC ≥0.999991 |
| Free shell and membrane checks | Six rigid motions, mass orthogonality and analytical flat membrane energy passed |
| Physical structural changes | Curvature changes eigenmodes; support stiffening raises frequencies; added mass lowers them |
| Basin mesh comparison | 8 × 8 versus 10 × 10: max 0.3847% for first ten ordered frequencies, 2.118% for all sixteen |
| Basin integration comparison | Gauss order 5 versus 7: max 0.001883% on baseline 8 × 8 mesh |
| Independent curved reference | Separate disk-polynomial basis, polar quadrature and orthonormal tangent assembly; no production geometry/assembly/eigensolve imports |
| Reference mathematics | Disk-polynomial orthogonality/derivatives and six free-curved-shell rigid modes passed |
| Mode correspondence | Global matching checked against exhaustive assignment; signs/scales/permutations and degenerate-subspace rotations handled |
| Frequency-only evidence | Default 8 × 8, 16 modes: verified prefix through reference mode 12, about 76.54 Hz |
| Sampled contact-transfer evidence | Default supported cutoff 10 Hz under declared criteria; higher tested cutoffs fail |
| Full impulse response | Common-time, unnormalized signals compared on all six paths; convergence is not established |
| Accuracy gate | A saved unmet or unexamined band produces status 1; stale source hashes rejected |
| Stable high-degree reference | Analytic boundary values/derivatives through degree 48, finite origin derivatives, low-degree independent power-formula comparison and cached replay passed |
| Refined 100 Hz contact study | Meshes 14/18/22/26; reference degrees 24/28/32/36; same material/supports/damping and unchanged prior tolerances |
| Selected contact profile | 18 × 18 cells, 16 modes; worst complex-transfer difference 2.36%; filtered impulse difference 2.14% |
| Reference/mesh/mode refinement at 100 Hz | Reference degree difference 1.57%; candidate 18 → 22 difference 1.93%; final mesh pair 2.45%; reference truncation 0.323%; candidate truncation 0.839% |
| Integration and frequency sampling | Increased quadrature and denser resonance grids pass additional 1% criteria; transfer gates also check the 20–100 Hz interval separately |
| Band-limited output | Pass band to 80 Hz, stop band at 100 Hz; phase, shared channel scale, linear convolution and physical end continuation tested |
| Profile evidence | Source/report digests and structural/contact/damping matching checked; unsupported changes rejected; timing edits allowed |
| Smaller cached playback banks | A matching larger bank supplies leading modes without repeating assembly/eigensolve; coefficients, masses and frequencies retained together |
| Contact-span refinement | Contact knots inserted without changing physical laws; free curved shell retains six rigid motions |
| Assembly memory measurement | Same 18 × 18 structure: process peak RSS about 1509 MiB before, 84 MiB after; assembly-only single-run measurement |
| Optional SciPy eigensolver | Missing-dependency behavior tested; SciPy unavailable and network installation blocked, so numerical comparison of that branch was not run |
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
The saved profile's claim is limited to its tested contact band and filtered
observation. Broadband impulse signals are not declared converged.
Changed thickness/profile/support settings need their own refinement checks.

The updated [convergence report](convergence.md) separates frequency-only evidence
from contact-response criteria. The finite polynomial reference, preceding mesh
and modal truncation are checked separately; a failed check cannot be bypassed by
passing a higher cumulative band. Baseline sampled band support remains 10 Hz. The
[expanded refinement study](contact_refinement.md) supports a 100 Hz sampled
transfer band and the corresponding filtered playback profile. Unfiltered
sixteen-mode contact signals remain unconverged. This study is an independent
numerical implementation of the same shell theory, not a published specimen table.

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
python tools/validate_dry_basin.py
```

Regenerate the independent comparison and its PNG/PDF figures:

```bash
python tools/validate_dry_basin.py --output docs/research/dry_basin/convergence.json
python tools/plot_dry_convergence.py
python tools/validate_dry_basin.py --check-report docs/research/dry_basin/convergence.json --require-band 10
# Returns 1 for the current unmet 20 Hz band:
python tools/validate_dry_basin.py --check-report docs/research/dry_basin/convergence.json --require-band 20
```

Reproduce and select the refined profile, then generate its figures and movie:

```bash
python tools/validate_dry_basin.py --refine-contacts --select-band 100 --output docs/research/dry_basin/contact_refinement.json --profile-output prototypes/001_resonant_surface/dry/profiles/contact_100hz.json
python tools/plot_dry_convergence.py --report docs/research/dry_basin/contact_refinement.json --output docs/research/dry_basin/figures/refined
python tools/run_dry_basin.py --profile contact_100hz --preview --render
# Select/gate a passing recorded case without a solver or NumPy:
python tools/validate_dry_basin.py --check-report docs/research/dry_basin/contact_refinement.json --select-band 100
```

The baseline `--require-band` gate checks its configured starting bank.
`--select-band` checks tested alternatives and the identically filtered impulse
response; it fails when no eligible bank passes. New source hashes invalidate old
reports, and edited physical profiles require a new study. Positive water depth
remains unsupported.

Saved-report checks verify source hashes before evaluating the accuracy gate and
work without NumPy. An unexamined cutoff also returns 1. Smaller research plans
can be selected with `--meshes`, `--degrees`, `--counts`, `--bands` and `--step-hz`;
they do not inherit the default study's supported band. Paths are independent of
the current working directory.

Regenerate the original curated paper data and figures from the repository root:

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
