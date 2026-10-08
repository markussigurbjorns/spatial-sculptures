# Water studies

Implemented: [001_column_loading](001_column_loading/README.md) checks a provisional
shallow-water inertia approximation against a finite-depth analytical fluid cell,
an independent NGSolve potential-flow reference and the validated dry basin.
It computes water volume and loaded metal modes.

[002_potential_flow](002_potential_flow/README.md) adds nonlocal spatial fluid inertia,
interior pressure and kinematic pressure-release surface observations, with
manufactured bowl fields, separated cosine solutions and independent NGSolve
fluid-cell checks. Its basin convergence study supports a separate 80 Hz playback
band. Gravity/capillary surface modes and moving contact lines remain future work.

Future isolated investigations: standing waves, capillary waves, droplets and
coupled free-surface dynamics. Record geometry, depth, temperature, excitation and
measurement units. Numerical checks do not replace physical measurements.
