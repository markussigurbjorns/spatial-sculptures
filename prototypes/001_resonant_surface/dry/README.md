# Dry resonant basin

This is the sculpture's first numerical structural model. Python computes a linear
curved-shell eigenproblem offline, caches its modes, then generates displacement
and contact-velocity audio from one modal response. Blender only displays supplied
coordinates. The original artistic water prototype remains available separately.

There is **no water in this model**. Pickups are ideal vertical contacts on the
metal, not hydrophones. Audio is normalized metal velocity, not predicted underwater
pressure, airborne sound or a spatialized listener recording.

From the repository root, with Python 3.11+ and NumPy installed:

```bash
# Install the optional numerical dependency if needed.
python -m pip install -e '.[numerical]'

# Generate WAV, configuration, frame bundle and report without Blender.
python tools/run_dry_basin.py --preview

# Open a lightweight Blender scene; press Space to play picture and audio.
python tools/run_dry_basin.py --preview --view

# Render a two-second movie with audio; requires Blender and FFmpeg.
python tools/run_dry_basin.py --preview --render
```

Outputs default to `../renders/dry/`: `dry_basin.mp4` when rendered,
`contact_pickups.wav`, `frames.npz`, `configuration.json`, `report.json` and rendered
PNG frames. `BLENDER_BIN` and `FFMPEG_BIN` override the executable names. The launcher
resolves source paths relative to itself and returns subprocess failures.
Use a different `--output` directory to retain each run; an existing movie is only
replaced by a successful render, so changing parameters without rendering leaves
that older movie in place.

The first run solves the eigenproblem. Later runs reuse matching modes in
`data/fem/001_resonant_surface/`. Structural settings and solver source are hashed;
changing forces, duration, damping, pickups or display settings does not require
another solve. `--rebuild` forces one. Cached mode arrays use NumPy archives without
pickle. Cache files, generated audio and renders are ignored by Git.

## Configurable assumptions

Edit [config.py](config.py), choose a named [experiment](experiments/README.md), or
replay/edit an exported JSON snapshot:

```bash
python tools/run_dry_basin.py --experiment 003_soft_supports --preview --render
python tools/run_dry_basin.py --experiment 006_three_drives --duration 4 --preview
python tools/run_dry_basin.py --config prototypes/001_resonant_surface/renders/dry/configuration.json --preview --view
```

The 1.44 × 1.16 m elliptical graph has 120 mm rise and 6 mm cubic asymmetry,
uniform 5 mm thickness, and stainless-steel-like provisional material properties.
Its free rim has no welded stiffener. Four square patches have independent total
X/Y/Z spring stiffnesses. Each exciter has configurable position, mounting width,
housing mass, unit global force direction and prescribed harmonic force. Rigid
housing inertia and loading couple through the surface-area mean of each patch.
These are not models of glue compliance, actuator impedance or electrical drive.
All these dimensions and assumptions affect the computed structure.

The default is a 0.03 N·s impulse at the first mounting patch, followed by ring-down.
All three housing masses are present; sustained forces are zero. Damping is an
assumed constant modal ratio, 0.005. Two contacts sample global vertical velocity
at the candidate pickup locations. Positive `water_depth_m` is rejected explicitly.
Variable thickness, imported vessel geometry, rotational mounts, fluid coupling,
gravity prestress and nonlinear motion are not implemented.

## Audio and picture timing

WAV channels 1 and 2 are the two contact signals. One shared normalization gain
preserves their relative levels; separate runs normalize independently, so compare
SI velocities in their reports rather than normalized loudness. SuperCollider is
not required for this offline path. Its later DSP/feedback layer can consume these
signals without changing the structural equations.

Audio is evaluated at 48 kHz in physical time. The 30 FPS visualization uses the
same modes and clock, with displacement magnified ×1500. Motion too fast for video
is represented by averaging displacement over half a frame, using several physical
samples. This is a temporal presentation filter, **not optical motion blur or a
complete picture of audio-rate oscillation**. It can suppress rapid motion. Setting
`exposure_fraction=0` displays instantaneous samples and can visibly alias.

Frame 1 and the first WAV sample both start at time zero. Requested duration is
rounded to whole visual frames and recorded in the report. The MP4 combines those
frames and the physical-speed WAV; custom odd image dimensions are padded by one
pixel as needed for encoding. In Blender, audio starts at frame 1, uses audio-sync
playback, and is attenuated to 0.2 for auditioning. Device playback was not evaluated
here; check the rendered file if interactive playback is choppy.

For a separate slow, silent inspection:

```bash
python tools/run_dry_basin.py --preview --view --inspection-speed 0.1 --duration 0.5 --output /tmp/dry-inspection
```

This changes only the visual time scale. The WAV remains at physical speed and is
omitted from the slowed Blender timeline. Slow inspection cannot export a movie
with the unretimed soundtrack.

## Verification and limits

```bash
python tools/validate_structure.py
PYTHONPATH=src python -m unittest discover -s tests
blender --background --factory-startup --python-exit-code 1 --python tests/validate_dry_blender.py
```

The flat numerical model reproduces the first six analytical simply-supported
plate frequencies within 0.152% on an 8 × 8 spline mesh. For the provisional basin,
8 × 8 versus 10 × 10 cells changes the first ten ordered frequencies by up to 0.385%
and all sixteen by up to 2.12%. These are observed refinement differences, not
accuracy bounds or physical validation. The lowest modes include support/body
motion. The small dense solver is intended for limited offline studies, not large
meshes or a converged broadband impulse sound.

See the [technical paper](../../../docs/research/dry_basin/paper.md) for equations,
references, computed figures and the validation record. An independent curved
reference and contact-response convergence runner are now available:

```bash
python tools/validate_dry_basin.py
```

The runner compares separately assembled disk-polynomial Ritz modes with spline
meshes, matches nearly degenerate mode groups, varies retained modes and checks
all six contact/exciter paths in SI units. It writes JSON and a readable table in
`data/fem/001_resonant_surface/`. It is an offline numerical check; no Blender or
audio server is needed. `--config` selects a saved physical configuration.

The current default has frequency-only evidence through approximately **76.54 Hz**,
but all contact-transfer criteria pass only up to the tested **10 Hz** cutoff.
The unfiltered WAV is not certified by that band. The refined reference and mesh
still fail stricter checks at higher cutoffs; simply adding more modes does not
resolve this. Read [the result table](../../../docs/research/dry_basin/convergence.md)
and [independent study](../../../studies/plates/002_curved_shell_reference/README.md).

Gate a recorded result without repeating the numerical solve:

```bash
python tools/validate_dry_basin.py --check-report docs/research/dry_basin/convergence.json --require-band 20
```

This returns status 1 for the current unmet 20 Hz criterion. The next numerical
task is to improve reference/local-patch resolution and mesh convergence for a
chosen audible band. Dry-vessel measurements, water loading and pressure sensing
remain subsequent work. Playback and render defaults are preserved.
