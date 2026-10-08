# Wet model verification record

Validated on October 8, 2026 with Python 3.13.13, NumPy 2.2.6, NGSolve 6.2.2608
and Blender 4.5.9 LTS. These are numerical/model checks, not real-vessel measurements.
The [full machine-readable report](validation.json) contains physical parameters,
source hashes, all per-path errors, failed intervals and portable-bank hashes.

The selected approximation uses 18 × 18 shell cells, 256 dry subspace modes,
horizontal/vertical fluid degrees 10/2 and 64 wet playback modes. Water is 65 mm
above the lowest floor point, approximately 23.053 litres, with density 1000 kg/m³.
Each hydrophone lies 20 mm below the mean water surface.

The 0–20, 20–40 and 40–80 Hz intervals pass independently. Responses use SI units:
contact velocity `(m/s)/N`, pressure `Pa/N` and surface elevation `m/N`. Each
observable has six paths (two observation points, three mounting patches).
Surface elevation is checked at the hydrophones' XY coordinates; this is not a
uniform error bound over every displayed water vertex.

| Refinement | Worst observable/path/interval difference through 80 Hz | Criterion |
| --- | ---: | ---: |
| Fluid horizontal degree 8 → 10 | 1.362% | 2% |
| Fluid horizontal degree 10 → 12 | 0.467% | 2% |
| Fluid vertical degree 2 → 3 | 0.146% | 2% |
| Horizontal/shoreline integration refinement | 0.000003% | 1% |
| Dry modal subspace 256 → 512 | 0.039% | 5% |
| Structural mesh 18 → 22 | 1.788% | 5% |
| Structural mesh 22 → 26 | 2.331% | 5% |
| 64-mode playback vs 512-mode bank | 2.245% | 5% |

For pressure alone, 64-mode playback differs by at most 1.064% in these intervals.
The identically filtered finite-pulse pressure comparison differs by 0.121% against
the 512-mode reference. Filtering has a 64 Hz pass band, an 80 Hz stop band and an
80 dB stop-band target. It preserves the time origin and is noncausal.

Mode comparisons include the next complete cluster beyond 80 Hz. The worst relative
frequency difference is 0.0217%; the lowest weighted subspace MAC is 0.99999989.
The resonance-grid integrated-response norm difference is below 0.0011%.
The largest fluid equation residual is below 7e-12 and modal residual below 2e-15.
Scaled polynomial-energy conditioning reaches approximately 2.1e11; observable
refinement and independent references matter alongside these small residuals.

The highest-degree analytical rigid-cell pressure-weight difference is 0.0148%.
Independent NGSolve rigid-cell pressure differs by 0.01293% and its added-inertia
matrix by 0.000014%. Manufactured bowl pressures agree within 7e-14 Pa/(m/s²).
These references verify the stated fluid approximation, with a pressure-release
top. They do not independently validate a curved wet vessel or add gravity waves.

Both higher intervals **80–160 and 160–200 Hz fail**. For example, horizontal
degree 10 → 12 pressure differs by 2.575% and 6.751%, respectively, exceeding the
2% criterion. Surface and retained-bank errors also fail. The dry model's 200 Hz
certificate is not reused for water. See [the convergence figure](convergence.png)
and its [PDF](convergence.pdf).

Reproduction:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/validate_wet_basin.py --external
MPLCONFIGDIR=/tmp/spatial-sculptures-matplotlib python tools/plot_wet_basin.py
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -s tests
python tools/run_wet_basin.py --preview --render
```

All 138 tests were discovered: 137 passed and one UDP bind test was skipped because
the sandbox disallows local socket binding. Without NumPy/SciPy/NGSolve, 62 ordinary
tests passed and 76 optional numerical tests skipped. Ruff and compilation passed
for all 116 Python files. Playback needed no OSC server, SuperCollider or NGSolve.

The default export rendered 60 frames at 30 FPS and muxed a two-second MP4 with
two-channel hydrophone audio. A separate Blender check built the scene twice:
18 objects, one tagged frame callback and one audio strip remained after each
build. Metal and water coordinates, fixed probe positions and frame pressure
values matched the Python arrays. The Workbench preview uses an opaque blue water
surface and symbolic hydrophone leads to keep presentation inexpensive.

Existing dry-profile, external dry-solver and column-loading source hashes remain
current. Generated movies, frames, audio and numerical caches remain ignored;
the small selected playback bank is intentionally retained with this research
evidence. [The study note](study.md) records physical assumptions and primary
references. Gravity/capillary dynamics and physical calibration remain future work.
