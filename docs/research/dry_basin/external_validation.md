# Independent solver and measurement exchange

The repository now prepares and compares complex **metal contact velocity per
applied force**, in `(m/s)/N`. It preserves amplitude, phase and every exciter/pickup
path. An independent NGSolve result now passes the configured 20–200 Hz study;
see the [completed results](external_results.md). No real-vessel measurement is supplied.
The existing disk-polynomial reference is independently implemented, but shares
the same shell assumptions; it is not a third-party solver benchmark.

## External solver implementation — 8 October 2026

The [NGSolve HHJ/Regge shell study](../../../studies/plates/003_external_shell/README.md)
and [runner](../../../tools/validate_external_dry_basin.py) implement a
software-only check. They independently construct the shell from plain parameters,
then gate comparison on an analytical plate prerequisite, mesh/mode refinement,
rim and quadrature refinement, mode-shape correspondence and frequency sampling.
Both raw amplitude and phase must agree on all six paths and smaller listening
intervals. NGSolve is optional, isolated from the simulation and Blender.

**Runtime validation passed on 8 October 2026** with NGSolve 6.2.2608, SciPy 1.18.1
and NumPy 2.2.6. The largest matched frequency difference is 0.084%; the worst
interval complex-response difference is 5.39%, below the declared 10% limit on
every path and interval. Curved geometry passes the independent refinement gates;
the earlier failed straight-rim trial is retained. Physical calibration is deferred.

To create an isolated solver environment:

```bash
python -m venv .venv-external
.venv-external/bin/python -m pip install -e '.[external]'
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv-external/bin/python tools/validate_external_dry_basin.py
```

With the dependencies already installed, use
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/validate_external_dry_basin.py`.

See the study README for settings, outputs, tolerances and how failed refinement
differs from failed agreement. Exit status 2 and `runtime_unavailable` explicitly
record an unavailable solver. No results from self-comparison are relabelled as
independent data. The [recorded status](external_solver_status.json) summarizes
the completed run; the [full report](external/report.json) retains all gates and hashes.

## Exchange with other solvers

Prepare a comparison without Blender or SuperCollider:

```bash
python tools/check_dry_response.py prepare
```

This writes `request.json`, `model_mobility.csv` and `model_source.json` into
`data/fem/001_resonant_surface/external_check/`. `--config`, `--output`, `--lower-hz`,
`--upper-hz` and `--step-hz` select another configuration or common sampling grid.
The default uses the checked 200 Hz profile over 20–200 Hz. Resonances receive extra
samples, and interval boundaries are included explicitly. Increasing the grid
density may be necessary when a supplied solver or specimen has different narrow
resonances. A checked profile rejects requests above its supported cutoff.

## Match the physical problem

An external solve must reproduce the request's graph, isotropic plane-stress
material, uniform thickness, free rim and translational consistent mass. In
particular, the supports are **springs on patch-mean displacement**: their stiffness
matrix is `k * mean(N) * mean(N).T`. A distributed bed of independent springs has
a different stiffness. Exciter housings similarly add rigid patch-mean inertia in
all three Cartesian directions. Each force has a total magnitude of one newton
along its configured direction, distributed by physical surface area over its
patch. Pickups are point global-Z velocities. Damping is the configured modal ratio.

Use a different discretization and independently converged geometry, quadrature,
mesh, damping implementation and modal truncation. Include modes above the compared
band until their off-resonance contact contribution stabilizes. Simply solving
the repository's exported matrices with another eigensolver would not test shell
assembly or physical assumptions. Shear, rotary inertia, prestress and mounting
compliance require an explicitly documented model comparison if added.

The [NGSolve Kirchhoff–Love shell tutorial](https://docu.ngsolve.org/ngs24/SaS/linear_KL_RM_shell_HHJ_TDNNS.html)
provides a separate mixed shell formulation and discusses membrane locking.
It is a candidate implementation reference; its published hyperboloid example
has different geometry, loading and boundary conditions and has **not** been run
as a basin benchmark here. The new study uses its formulation rather than that
hyperboloid's results. The basin-specific results are recorded separately.

## Import the result

Return all six paths on the requested frequency grid. CSV columns are:

```text
pickup,exciter,frequency_hz,real_m_per_s_per_n,imag_m_per_s_per_n
```

Indices start at one. Each path must have finite, strictly increasing frequencies,
with no duplicates. A harmonic response uses `Re(H * exp(+i*2*pi*f*t))`; under this
convention velocity is `i*2*pi*f` times displacement. An opposite phasor convention
requires complex conjugation before export. Document any polarity or channel-delay
correction; no correction is fitted by the comparison tool.

Save a source JSON alongside the supplied CSV:

```json
{
  "kind": "external_solver",
  "source": "Solver name, version, model location and author",
  "units": "(m/s)/N",
  "harmonic_convention": "exp(+i*2*pi*f*t)",
  "request_sha256": "SHA256 of request.json",
  "data_sha256": "SHA256 of the supplied CSV",
  "notes": "Refinement evidence and differences from the requested physical assumptions"
}
```

Use `kind="measurement"` for calibrated observations of a vessel, or
`kind="synthetic_test"` for generated fixtures. The prepared model's own metadata
uses `kind="model_prediction"`; self-comparison is labelled and supplies no
independent evidence. SHA256 identifies files, not the truth of a source label.

```bash
python tools/check_dry_response.py compare \
  data/fem/001_resonant_surface/external_check/request.json \
  data/fem/001_resonant_surface/external_check/supplied.csv \
  --source data/fem/001_resonant_surface/external_check/supplied_source.json \
  --output data/fem/001_resonant_surface/external_check/comparison.json
```

The tool rejects stale source files, wrong units, missing paths, mismatched hashes
and frequency grids. It reports complex relative L2 separately for each of the
six paths, the whole interval and smaller intervals. The denominator is the
supplied observation. No loudness normalization, phase alignment or interpolation
is applied. Status 1 means the chosen agreement tolerance fails; invalid input
returns status 2. A sampled agreement result is not a physical accuracy bound or
automatic calibration. Repeat measurements and denser grids remain necessary.
