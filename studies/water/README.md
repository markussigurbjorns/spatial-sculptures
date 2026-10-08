# Water studies

Implemented: [001_column_loading](001_column_loading/README.md) checks a provisional
shallow-water inertia approximation against a finite-depth analytical fluid cell,
an independent NGSolve potential-flow reference and the validated dry basin.
It computes water volume and loaded metal modes.

[002_potential_flow](002_potential_flow/README.md) adds nonlocal spatial fluid inertia,
interior pressure and kinematic pressure-release surface observations, with
manufactured bowl fields, separated cosine solutions and independent NGSolve
fluid-cell checks. Its basin convergence study supports a separate 80 Hz playback
band. It deliberately omits gravity/capillary restoring forces.

[003_free_surface](003_free_surface/README.md) adds dynamic gravity/capillary
surface coordinates coupled to the shell through reciprocal fluid inertia.
Analytical and independent NGSolve cells check inertia, pressure and dispersion.
Its resting footprint and dry shell equilibrium remain fixed; hydrostatic
prestress and a physical moving-contact-line law remain future work.

Future isolated investigations: menisci, shoreline behavior, dissipation,
droplet forcing and hydrostatic coupling. Record geometry, depth, temperature, excitation and
measurement units. Numerical checks do not replace physical measurements.
