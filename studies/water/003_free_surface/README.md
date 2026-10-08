# Gravity and capillary references

`reference.py` compares the reusable Neumann-potential formulation against six
separated cosine modes in rigid rectangular cells. It covers gravity-only,
gravity plus surface tension, and capillary-only cases. Checks include the full
fluid mass matrix, interior pressure weights and eigenfrequencies across
successive trial degrees. The constant-volume mode is excluded.

The optional independent NGSolve H1/NumberSpace solve uses a volume-mean gauge,
then converts pressure to the same surface-mean gauge. Mesh refinement checks
mass, pressure and gravity/capillary frequencies against closed-form solutions.
This is a fluid-cell reference, not independent validation of the curved
metal/water basin or of hydrostatic prestress.

Run the full prototype study with `python tools/validate_free_surface.py --external`.
See [the research note](../../../docs/research/free_surface/study.md) for
derivations, numerical acceptance criteria and limitations. Small-signal wave
physics is reusable for later sculptures; the basin's material, supports,
profile and sensor coordinates remain prototype-specific.
