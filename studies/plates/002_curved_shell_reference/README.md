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
evaluation uses explicit polynomial coefficients and derivatives, rather than
their stable recurrence algorithms. Reference degree is capped at 20 because
high-degree power evaluation needs additional numerical-stability work.

From the repository root:

```bash
python tools/validate_dry_basin.py
python tools/validate_dry_basin.py --config path/to/configuration.json
```

Defaults compare spline meshes 8/10/12/14, polynomial degrees 12/16/18/20, and
16/32/48/64 retained modes. NumPy is the only numerical dependency; Blender and
SuperCollider are unnecessary. This is an offline study. Larger dense meshes cost
more memory and should be selected deliberately.

The report records globally matched mode shapes, nearly degenerate subspace
agreement, complex contact velocity/force transfers on all two-pickup × three-force
paths, and two-second unit-impulse contact signals without normalization or phase
alignment. Its JSON and Markdown outputs default to ignored
`data/fem/001_resonant_surface/convergence.{json,md}`.

```bash
# Save curated paper evidence and generate PNG/PDF figures.
python tools/validate_dry_basin.py --output docs/research/dry_basin/convergence.json
python tools/plot_dry_convergence.py

# Recheck a saved report without repeating the solve; exit 1 for an unmet band.
python tools/validate_dry_basin.py --check-report docs/research/dry_basin/convergence.json --require-band 20
```

The [current result](../../../docs/research/dry_basin/convergence.md) supports
only the tested cumulative contact-transfer band up to 10 Hz under the declared
tolerances. The default 8 × 8, 16-mode model has frequency-only evidence through
about 76.54 Hz. These statements describe different observables. The default
unfiltered WAV is not thereby certified. Increasing mode count alone does not
fix coarse-mesh frequency/phase errors.

This implementation is an independent numerical reference inside this repository,
not a reproduced published vessel-frequency table, an external solver certification,
or an independent physical theory. The finite finest reference and truncation
are themselves tested; failed accuracy checks remain failures. More accurate
references and mesh refinement are needed before claiming an audible contact
bandwidth, coupling water or comparing to a fabricated vessel.
