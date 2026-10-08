# External dry-shell cross-validation

**Status: executed and passed on 8 October 2026 for the configured dry basin over
20–200 Hz.** The analytical plate prerequisite, independent refinement and all six
complex contact paths pass their declared criteria. The worst interval response
difference from production is 5.39%; the largest matched frequency difference is
0.084%. See the [results and limits](../../../docs/research/dry_basin/external_results.md).

This study implements a separate mixed Kirchhoff–Love shell in
[NGSolve](https://ngsolve.org/), following its
[HHJ/Regge formulation](https://docu.ngsolve.org/ngs24/SaS/linear_KL_RM_shell_HHJ_TDNNS.html).
It receives plain parameters and independently constructs geometry, triangular
mesh, shell matrices, contact coupling, eigenmodes and modal response. It imports
none of the production shell, spline, Ritz-reference or response implementation.
The runner uses production code only to prepare the comparison request and compare
outputs. Reusing production matrices with another eigensolver would miss assembly
errors and is deliberately excluded.

This is an offline research check. Ordinary simulation, audio export and Blender
playback do not depend on NGSolve or SciPy. A real basin is not needed.

## Run

From the repository root:

```bash
python -m venv .venv-external
.venv-external/bin/python -m pip install -e '.[external]'
.venv-external/bin/python tools/validate_external_dry_basin.py --check-dependencies
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv-external/bin/python tools/validate_external_dry_basin.py
```

If NGSolve and SciPy are already installed in your ordinary Python environment,
run `python tools/validate_external_dry_basin.py` directly. Setting
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` limits solver thread use.

The extra pins NGSolve 6.2.2608; actual NumPy/SciPy/NGSolve versions are recorded
in the result. Pip installation is NGSolve's
[documented approach](https://ngsolve.org/installation.html). A separate virtual
environment keeps the solver dependencies out of Blender. Use that environment's
Python for every command. Initial assembly/eigensolving can take significant time
and memory; this is separate from cached audiovisual playback. The five basin
solves took about four minutes in this run; that is not a controlled benchmark.

The default runner prepares the current `contact_200hz` model on a 20–200 Hz grid
with 0.025 Hz background spacing and additional resonance samples. An existing
request can instead be supplied with `--request /absolute/path/request.json`.
`--output` selects another directory, including paths with spaces. Script paths
and default repository paths resolve independently of the working directory.

## Checks, in order

1. **Analytical plate prerequisite.** Six simply supported rectangular-plate
   frequencies must agree with the closed formula within 0.5%. Normal displacement
   is constrained at the rim; rotations remain free. In-plane boundary constraints
   remove unrelated rigid motions and do not affect the flat bending problem.
   A failed prerequisite stops the study before generating basin data.
2. **Independent basin refinement.** Mesh lengths 0.12/0.085/0.06 m, quadratic rims
   32/48/64 segments, cubic displacement and quadratic moment/Regge spaces.
   Refine quadrature separately and double the final rim segment count separately.
   Banks 256/384/512 retain off-resonance contributions above the comparison band.
3. **Mode correspondence.** Compare physical-area-weighted Cartesian displacement
   shapes, matching signs/order and close-frequency subspaces. Include all modes
   through the comparison band and the next complete cluster (at least twelve).
4. **Six contact paths.** Two point vertical-velocity pickups and three area-weighted
   unit-force exciters. Compare raw complex `(m/s)/N`, preserving amplitude and phase.
   Evaluate the whole interval and separate 20–40/40–80/80–160/160–200 Hz intervals.
5. **Resolution of the frequency grid.** Evaluate the external response directly
   on a denser grid that includes its own resonances. The interpolation check tests
   whether the supplied grid resolves that response. The exported solver comparison
   itself applies no interpolation or fitted gain/phase.

Declared tolerances live in [the runner](../../../tools/validate_external_dry_basin.py).
External mesh/contact truncation differences must be at most 5%; separate rim,
quadrature and frequency-grid differences at most 1%. External mode refinement
uses 0.25% frequency difference and MAC at least 0.995; production-to-external
comparison uses 1% frequency difference, MAC at least 0.99 and at most 10% complex
response difference on every path and interval. These finite refinement criteria
are research decisions, not exact error bounds or physical accuracy claims.

If a check fails, inspect the recorded stage before choosing finer meshes,
more modes, higher quadrature or a denser request grid. Do not lower the tolerances
just to obtain a pass. Changing the provisional physical parameters is a new study.
The runner retains failures and does not promote an unconverged external reference
to a validation pass merely because it resembles the production model.

## Physical matching and differences

Both models use the configured stress-free graph, uniform thickness, isotropic
plane stress, translational mass, free rim and constant modal damping ratio. Both
use springs on **mean patch translation**, rigid exciter masses on mean XYZ
translation, total unit force distributed over physical patch area, and point
global-Z velocity pickups. No water, transverse shear, rotary inertia, gravity
prestress, rim reinforcement, adhesive compliance or electrical actuator is added.

The external discretization differs in two explicit ways:

- Netgen generates quadratic triangles with conforming support/exciter boundaries.
  Quadratic spline arcs approximate the ellipse. A degree-six geometry deformation
  represents the cubic graph composed with this quadratic XY map. Rim refinement
  must pass separately. `--geometry-order 1 --rim-segments 64 128 256` retains the
  earlier straight-polygon study, which failed the response refinement criteria.
- HHJ bending moments and facet rotations replace the production C2 splines.
  Regge interpolation of membrane strain follows the external formulation's
  membrane-locking treatment; it converges toward the same continuum energy.

Only discontinuous, massless stresses are eliminated. Displacement bubble mass is
retained; facet rotations remain massless. The shift-invert eigensolve uses
[SciPy's documented positive-semidefinite mass case](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.eigsh.html).
Artificial rotary mass would change the requested problem. Algebraic residuals,
matrix symmetry and modal mass orthogonality are checked before exporting.
Contact regions must be disjoint and strictly internal; touching or overlapping
patches are rejected rather than silently meshed differently.

## Outputs and meaning

Generated files live in ignored `data/fem/001_resonant_surface/external_solver/`:

- `report.json`: overall status, policy, settings, checks and source identities.
- `plate_check.json`: prerequisite results, only after the external runtime runs.
- `mesh_*_modes.npz` and diagnostics: frequencies, modal contact residues and sampled
  shapes for independent meshes, plus separate rim/quadrature variations.
- `external_mobility.csv`, `external_source.json`, `comparison.json`: all six
  complex paths, their provenance and production agreement.
- `exchange_self_check.json`: explicitly labelled comparison-tool check; it is
  never treated as external evidence.

Exit status **0** means every declared check passed; **1** means a completed check
failed; **2** means dependencies, input or execution prevented completion. An
interrupted run remains `running`; unavailable runtime is `runtime_unavailable`.
Old result files in the directory must be interpreted through the current
`report.json` and its file/source hashes, rather than their mere presence.

Curated modal banks, raw complex curves, plots and hashed provenance are retained
in [the paper's external results](../../../docs/research/dry_basin/external/).
Regenerate them after a completed solve with
`python tools/plot_external_dry_basin.py` (requires the optional `.[paper]` extra).
The earlier failed polygon report is retained alongside the successful result.

This pass establishes agreement between numerical models of the
provisional **dry** sculpture. It would not calibrate a fabricated vessel, predict
hydrophone pressure, or demonstrate water coupling. Physical calibration is deferred.
