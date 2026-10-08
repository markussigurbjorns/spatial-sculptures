# Nonlocal pressure-release fluid potential

This study replaces independent water columns with a three-dimensional Laplace
weak problem over the actual resting water volume. It checks fluid inertia and
interior pressure against separated analytical solutions, an independent NGSolve
tetrahedral cell and manufactured harmonic fields in an asymmetric bowl.

The rectangular reference has a pressure-release top and **rigid vertical sides**.
The earlier column study's sine reference had pressure-release vertical sides.
These are different boundary conditions; their mode shapes are not interchangeable.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/validate_wet_basin.py --external
```

NumPy is sufficient for the production model. `--external` requires the optional
NGSolve environment. All numerical work runs outside Blender. These checks concern
the stated equations, rather than calibrated sound from a fabricated vessel.

See [the derivation and validation scope](../../../docs/research/wet_basin/study.md).
Gravity/capillary surface resonances, compressibility, moving shorelines, static
water-load prestress and fluid damping are subsequent modeling stages.
