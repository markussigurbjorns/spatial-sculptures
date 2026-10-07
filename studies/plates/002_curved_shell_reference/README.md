# Independent curved-shell reference

This study cross-checks the production dry-basin spline solver using a separately
assembled polynomial Rayleigh–Ritz model. It imports no production spline,
geometry-evaluation, quadrature, stiffness, mass or eigensolve functions. Both
models deliberately share the stated linear Kirchhoff–Love physical assumptions
and configured material, profile, supports and housing masses.

| Production | Reference |
| --- | --- |
| Local C² cubic tensor-product splines | Global Cartesian real Zernike polynomials on the disk |
| Clipped cell integration | Gauss quadrature in squared radius and uniform angle |
| Covariant strains and metric contraction | Orthonormal tangent strains and variation of the normal |
| Diagonally scaled, whitened eigenproblem | Independently mass-whitened Ritz eigenproblem |

The reference graph is re-evaluated from the configuration dictionary. Its square
patches represent rigid mean translations with the same stated spring, inertia
and force laws. Reference eigenvectors have unit modal mass; production sampled
peak normalization is kept separate. All contact transfers are reconstructed in
SI units, so arbitrary mode signs and normalization do not alter their comparison.

Zernike disk polynomials and quadrature are described by
[Greengard and Serkh (2018)](https://arxiv.org/abs/1811.02720). Our Cartesian
evaluation now uses a Jacobi three-term recurrence, with analytically differentiated
recurrences and a Cartesian complex-monomial factor. Values and derivatives remain
finite at the origin. Independent power-formula comparisons, low-degree orthogonality,
and analytic boundary values/derivatives through degree 48 test the evaluator.
Degree 48 is a resource cap, not an accuracy guarantee. Assembly uses bounded
quadrature batches, and source/configuration-keyed archives cache reference solves.

From the repository root:

```bash
python tools/validate_dry_basin.py
python tools/validate_dry_basin.py --config path/to/configuration.json
python tools/validate_dry_basin.py --refine-contacts --select-band 100
```

Baseline defaults compare spline meshes 8/10/12/14, polynomial degrees 12/16/18/20,
and 16/32/48/64 retained modes. `--refine-contacts` uses meshes 14/18/22/26 and degrees
24/28/32/36 through 100 Hz. NumPy suffices; Blender and SuperCollider are unnecessary.
This is an offline study. Larger dense matrices still cost memory; only the optional
production SciPy eigensolve is sparse. Contact-knot refinement is available separately
and does not change the stated support/force/mass laws.

The report records globally matched mode shapes, nearly degenerate subspace
agreement, complex contact velocity/force transfers on all two-pickup × three-force
paths, and two-second unit-impulse contact signals without normalization or phase
alignment. Common frequency grids refine each resonance and use trapezoidal L2
weights; doubling sample density checks interpolation error. Higher quadrature
orders, each candidate's next mesh and the final mesh pair are also checked.
Identically filtered impulse comparisons support a band-limited playback profile.
Its JSON and Markdown outputs default to ignored
`data/fem/001_resonant_surface/convergence.{json,md}`.

```bash
# Save curated paper evidence and generate PNG/PDF figures.
python tools/validate_dry_basin.py --output docs/research/dry_basin/convergence.json
python tools/plot_dry_convergence.py

# Recheck a saved report without repeating the solve; exit 1 for an unmet band.
python tools/validate_dry_basin.py --check-report docs/research/dry_basin/convergence.json --require-band 20
```

The [baseline result](../../../docs/research/dry_basin/convergence.md) supports
only the tested cumulative contact-transfer band up to 10 Hz under the declared
tolerances. The default 8 × 8, 16-mode model has frequency-only evidence through
about 76.54 Hz. These statements describe different observables. The default
unfiltered WAV is not thereby certified. Increasing mode count alone does not
fix coarse-mesh frequency/phase errors.

The [refined study](../../../docs/research/dry_basin/contact_refinement.md) passes
through **100 Hz** with degrees 24/28/32/36 and meshes 14/18/22/26. The smallest
passing playback bank has 18 × 18 cells and 16 modes. Its worst complex-transfer
difference is about 2.4%; identically filtered impulses differ by about 2.1%.
The saved audio filter passes through 80 Hz and reaches its stop band at 100 Hz.
No tolerance or damping parameter was loosened to obtain this result.

This implementation is an independent numerical reference inside this repository,
not a reproduced published vessel-frequency table, an external solver certification,
or an independent physical theory. The finite finest reference and truncation
are themselves tested; failed accuracy checks remain failures. More accurate
references and mesh refinement are needed to expand contact bandwidth, couple
water or compare to a fabricated vessel.
