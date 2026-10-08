# Plate studies

Future investigations: plate modes, Chladni patterns, excitation location, and
material/thickness comparisons. Distinguish measured boundary conditions from
visual approximations. The first implementation is an analytical dry-plate reference.

Implemented: [001_modal_reference](001_modal_reference/README.md) models a dry,
simply supported rectangular plate. It includes analytical modes, physical impulse
and harmonic responses, contact-velocity pickups, and a referenced working paper.
It is a reference study rather than a prediction of the curved basin.

[003_external_shell](003_external_shell/README.md) independently assembles an
NGSolve shell and passes the configured dry basin's 20–200 Hz comparison gates.
Its external dependencies are optional and separate from Blender playback.
