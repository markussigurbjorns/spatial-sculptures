# Computational validation — updated 8 October 2026

These checks verify equations, software and export behavior. They do not validate
a fabricated vessel, hydrophone pressure, radiation or spatial perception.

| Check | Result |
| --- | --- |
| Ordinary Python compilation | Passed for source, prototypes, studies, tools and tests |
| Ruff lint and formatting | Passed |
| Unit suite with NumPy/SciPy/NGSolve | 123 tests: 122 passed; sandbox UDP socket test skipped |
| Unit suite without NumPy | 123 tests: 62 passed; 61 optional numerical/runtime tests skipped |
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
| Earlier 100 Hz profile | 18 × 18 cells, 16 modes; broad complex-transfer difference 2.36%; filtered impulse difference 2.14% |
| Reference/mesh/mode refinement at 100 Hz | Reference degree difference 1.57%; candidate 18 → 22 difference 1.93%; final mesh pair 2.45%; reference truncation 0.323%; candidate truncation 0.839% |
| Integration and frequency sampling | Increased quadrature and denser resonance grids pass additional 1% criteria; transfer gates also check the 20–100 Hz interval separately |
| Band-limited output | Pass band to 80 Hz, stop band at 100 Hz; phase, shared channel scale, linear convolution and physical end continuation tested |
| Extended 200 Hz study | Meshes 18/22/26; degrees 24/28/32/36; full banks 512 modes; reference truncation 384 → 512 |
| Separate interval gates | 20–40, 40–80, 80–160 and 160–200 Hz each pass reference/mesh/truncation/independent-response criteria; interval quadrature and frequency-grid differences each below 1% |
| Selected 200 Hz profile | 18 × 18 cells, 128 modes; worst interval difference 5.38%; filtered impulse difference 1.70%; pass 160 Hz / stop 200 Hz |
| Upper interval completeness | 160–200 Hz: reference degree difference 3.10%, reference truncation 0.464%, production 128 → 512 truncation 4.54% |
| Bounded contact audio | Batched observations match full-history impulse/drive traces, including delayed events and every force path |
| Audio projection memory | Selected 128-mode / 2 s / 48 kHz case: process peak RSS about 239 MiB full-history versus 51 MiB chunked; excludes solving, FIR and Blender |
| Below-first-resonance cutoff | Absence of a resonance below a cutoff allows response gates to run; entirely missing mode comparison still fails |
| External data exchange | CSV complex round-trip, missing paths, SI units, file/source identity, gain/phase errors and labelled self-comparison tested |
| External study contracts | Production-import isolation, disjoint patches, unit forces, modal phase/scale, polygon area refinement, interval gates and explicit missing-runtime status passed |
| External curved geometry | Graph height/normal preservation and quadratic-rim area improvement checked in NGSolve; internal patch interfaces retained |
| External NGSolve prerequisite | Six analytical plate frequencies: maximum relative difference 2.63e-9, below 0.5% limit |
| External NGSolve refinement | Mesh-pair worst responses 0.6352% / 0.1386%; rim 0.0500%; additional quadrature 0.00000218%; mode truncation 0.7549%; grid 0.1365%; all declared gates passed |
| External production agreement | 20–200 Hz, all six raw complex contact paths: worst interval difference 5.3863% below 10%; 19 matched modes, largest frequency difference 0.0840%, minimum subspace MAC 0.9999975 |
| Retained external failure | Earlier straight-polygon mesh/rim refinement failed and was not promoted; historical report retained; no tolerance relaxed |
| Support/mount variants | Half/double total support stiffness and half/1.5× mounting widths each pass their own 200 Hz study with 18 × 18 cells and 128 modes; all evidence/profile digests checked |
| Profile evidence | Source/report digests and structural/contact/damping matching checked; unsupported changes rejected; timing edits allowed |
| Smaller cached playback banks | A matching larger bank supplies leading modes without repeating assembly/eigensolve; coefficients, masses and frequencies retained together |
| Contact-span refinement | Contact knots inserted without changing physical laws; free curved shell retains six rigid motions |
| Assembly memory measurement | Same 18 × 18 structure: process peak RSS about 1509 MiB before, 84 MiB after; assembly-only single-run measurement |
| Optional SciPy eigensolver | Six plate modes match NumPy within 1e-8 relative tolerance; mass orthogonality within 1e-8 and residual below 1e-6; full 200 Hz production profile remains NumPy |
| Cache and replay | Mode normalization and arrays survive save/load; keys track structure/source; forcing/presentation changes reuse modes |
| Audio/visual state | WAV samples match reconstructed physical contact velocity within PCM quantization; video times and energy match the same response |
| Exposure and slow inspection | Exposure average checked against dense sampling; slowing picture leaves physical WAV duration unchanged |
| Dry Blender adapter | Vector coordinates, common time origin, audio strip, scrubbing, module reload, callback cleanup and silent slow inspection passed in Blender 4.5.9 |
| Existing Blender consumers | Original water prototype and analytical plate integrations passed |
| Actual MP4 export | 60 H.264 frames at 30 FPS; stereo 48 kHz AAC; both streams exactly 2.000 s |
| Unsupported dry request | Positive water depth and invalid damping/direction rejected before creating dry caches; water loading has a separate study entry point |
| Working-directory independence | Saved configuration launched successfully from `/tmp`, including output path with spaces |
| Audibility / hardware playback / SuperCollider server | Not evaluated; audio-device and server runtime validation unavailable here |
| External shell solve / measured vessel / fluid coupling | External NGSolve study passed for the configured dry 20–200 Hz case; separate provisional column-loading study added, physical calibration deferred, basin pressure/free-surface solve absent |
| Water-loading study | Zero-depth recovery, analytical volume/inertia, nonnegative loading and integration checks pass; independent flat-fluid added masses within 0.073%; no certified wet contact band |

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

The [200 Hz study](contact_bandwidth.md) strengthens this with smaller frequency
intervals and larger reference banks. A 32-mode case passes the cumulative integrals
but fails the upper intervals; the saved profile uses 128 modes. The earlier 100 Hz
profile retains its declared broader-band criteria. Shape matching now covers the
tested band and next complete cluster; higher modes still contribute to transfer,
truncation and impulse calculations. New support/mount configurations receive
their own [sensitivity evidence](sensitivity/comparison.md).

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

Reproduce the stronger bandwidth study and the support/mount variations:

```bash
python tools/validate_dry_basin.py --extend-contacts --select-band 200 --output docs/research/dry_basin/contact_bandwidth.json --profile-output prototypes/001_resonant_surface/dry/profiles/contact_200hz.json
python tools/plot_dry_convergence.py --report docs/research/dry_basin/contact_bandwidth.json --output docs/research/dry_basin/figures/bandwidth
python tools/study_dry_sensitivity.py --output docs/research/dry_basin/sensitivity
python tools/run_dry_basin.py --profile contact_200hz --preview --render
python tools/check_dry_response.py prepare
```

External and measured datasets must follow the [exchange format](external_validation.md).
Prepared model data and synthetic unit fixtures only test that tool's behavior;
they supply no external validation. The [measurement plan](measurement_plan.md)
records the remaining physical work.

The [NGSolve study](../../../studies/plates/003_external_shell/README.md) is an
optional `.[external]` workflow. Its completed solver run passes the configured
dry basin's 20–200 Hz criteria; ordinary unit tests supply separate evidence.
The [status record](external_solver_status.json), [full report](external/report.json)
and [results with plots](external_results.md) record the computation and its limits.
With the dependencies already installed, reproduce it with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/validate_external_dry_basin.py
python tools/plot_external_dry_basin.py
```

The runner returns 2 when dependencies/execution are unavailable, 1 when a
completed criterion fails and 0 only when prerequisite, external refinement and
production agreement gates all pass. No thresholds were relaxed and no external
data were fabricated. Physical calibration has been deferred by the user.

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
