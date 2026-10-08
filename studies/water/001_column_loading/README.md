# Shallow-column water-loading reference

This first water study separates three questions:

1. Is the added-inertia implementation numerically correct?
2. When does its shallow-column approximation resemble a solvable fluid problem?
3. How does this approximation change the configured basin's structural modes?

The reusable implementation is [fluid_loading.py](../../../src/spatial_sculptures/simulation/fluid_loading.py).
The basin's depths and density are specified in
[prototype configuration](../../../prototypes/001_resonant_surface/water_loading/config.py).
This directory contains the independent flat-cell [reference](reference.py), with
an analytical solution and an optional NGSolve 3D Laplace solve.

From the repository root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/study_water_loading.py --external-plate
python tools/plot_water_loading.py
```

The study needs NumPy (`.[numerical]`). `--external-plate` also needs NGSolve
(`.[external]`); omit that flag to run without it. Plotting needs Matplotlib
(`.[paper]`). Blender and SuperCollider are not involved.

Generated results and modes live in ignored
`data/fem/001_resonant_surface/water_loading/`. The plotting helper checks hashes
and curates them into `docs/research/water_loading/`.
See the [referenced write-up](../../../docs/research/water_loading/study.md).

## Reference boundary conditions

The flat reference has a prescribed sine-product velocity on its bottom and
zero perturbation potential on its top **and four vertical sides**. These
pressure-release sides permit a separated analytical solution; they are not
rigid container walls. Its added mass per projected area is
`rho*tanh(k*h)/k`, with limit `rho*h` at zero wavenumber. The column approximation
uses `rho*h`, and its approximation error increases with `k*h`.

The numerical plate check tests the column law against its own independent plate
formula. The NGSolve check tests finite-depth potential flow against its different
analytical formula. Keeping them separate prevents a successful assembly test
from being presented as proof of the approximation's physical adequacy.

## Limits

The basin uses local vertical column flux on its wet graph footprint. It has no
lateral fluid solve, hydrophone pressure, sloshing, capillary waves, viscosity,
added water damping or hydrostatic prestress. The shell mid-surface approximates
the fluid floor. The dry 200 Hz contact certificate does not certify these loaded
modes. A pass means the declared **numerical checks** passed; it is not a wet
basin accuracy certificate. No water-loaded audio or rendering is enabled yet.
