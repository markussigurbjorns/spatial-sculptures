# 001 — Dry modal reference plate

A physical reference study for the resonant-surface research project. It models
small-amplitude transverse vibration of a homogeneous rectangular plate,
simply supported continuously along all four edges. **It does not model the
curved basin, its four local supports, water, hydrophone pressure or acoustic radiation.**

The [working paper](../../../docs/research/modal_reference/paper.md) documents
assumptions, equations, computed results, limitations and seven references.
The [decision record](../../../docs/research/modal_reference/decisions.md) distinguishes
project choices from unmeasured parameters.

## Run and listen

From the repository root, using Python 3.11+:

```bash
python tools/run_modal_study.py
```

This generates `results/modes.csv`, `response.csv`, `report.json`, and
`contact_pickups.wav`, plus `configuration.json` and `coupling.csv`. Open the WAV
in an audio player. No Blender, SuperCollider,
OSC server or third-party dependency is required. NumPy accelerates offline
sampling if present; install the optional `.[fast]` extra if needed. The scalar
fallback is slower, so use `--duration 0.5 --modes 3` for a short first check.

The audio is the velocity at two ideal metal contact pickups, reconstructed from
the computed modes. A single reported gain normalizes both channels; there is no
noise generator or unrelated resonator bank. This is not calibrated microphone
or hydrophone audio. Left/right assignment labels the two pickups and does not
simulate a spatial listening position. Low modes include infrasonic vibration.

To load it into SuperCollider, evaluate this file-loading expression with your
absolute repository path:

```supercollider
"/absolute/path/to/spatial-sculptures/studies/plates/001_modal_reference/listen.scd".load;
```

After it reports that the buffer is loaded, evaluate `~playModalReference.value`.
Stop with `~stopModalReference.value`. This is a separate reference-study player;
the existing water prototype's OSC listening sketch keeps its original mapping.
The new file player provides a place for later DSP with model-generated input.
Its runtime remains unverified in the sandbox environment that blocks server
networking; WAV generation and sample values are tested independently.

## Inspect in Blender

```bash
blender --python studies/plates/001_modal_reference/build.py
```

To select another installation, invoke its executable path with the same arguments.
Press Space over the timeline. This lightweight Workbench view reconstructs
plate displacement from physical modal coordinates. It uses **displacement ×2000**
and **time ×0.02**, so you can inspect otherwise small and fast vibrations.
For example, five seconds of displayed animation represent 0.1 physical seconds.
The WAV stays at normal physical speed; this inspection view and the WAV are not
synchronized playback. The scene records time/gain/energy as custom properties.

A headless check:

```bash
blender --background --factory-startup --python-exit-code 1 --python tests/validate_modal_blender.py
```

## Parameters and variations

Edit `config.py` or add an explicit Python file under [experiments/](experiments/README.md).
Physical parameters, mounting requests and presentation settings are separated.
They can be provisional: measurements are for later calibration and validation.

| Configuration | What this reference actually computes |
| --- | --- |
| `plate.length_x`, `length_y` | Flat rectangular dimensions, metres |
| `plate.youngs_modulus`, `density`, `poisson_ratio` | Homogeneous isotropic material response, Pa and kg/m³ |
| `plate.thickness` | Uniform thickness, metres; changes both stiffness and mass |
| `profile` | `flat_rectangle`, zero rise, no imported mesh |
| `supports` | Continuous `simply_supported_edges` |
| `impulses`, `drives` | Positions, total N·s/N, timing, phase/frequency and square patch width in metres |
| Each excitation's `mounting` | Rigid patch with unit force direction `(0, 0, 1)` or `(0, 0, -1)` |
| `pickups` | Finite XY positions of ideal metal contact-velocity pickups |
| `water.depth_m` | Zero for this dry model |
| `damping_ratio`, `modes_per_axis` | Assumed modal damping and retained basis size |
| `duration`, `sample_rate` | Physical seconds and audio samples/s |
| `visual_gain`, `visual_time_scale`, `display_fps` | Inspection only; do not change the computed physical response |

`Profile` can record a requested rise or mesh path; `Supports` can record local
contacts with position, width, stiffness and damping. `thickness_map`, mounting
mass/compliance and positive water depth are future solver requests. **The current
solver rejects them explicitly, before writing a run or clearing a Blender scene.**
Adding a configurable field does not implement its physics. The exported report
lists the supported model capabilities. For example, `Water(depth_m=0.04)` requests
a wet model and fails with a clear unsupported-setting error in this dry reference.

The default is a 0.03 N·s impulse over a 50 mm square patch,
with no ongoing drive. E = 193 GPa and density = 8030 kg/m³ are typical manufacturer
data; ν = 0.30 and modal damping ratio 0.005 are unmeasured assumptions.
The 1.44 × 1.16 m reference with 5 mm thickness weighs about 67 kg; that rectangle
is not the basin and its mass is not a fabrication prediction.

```bash
python tools/run_modal_study.py --driven --output studies/plates/001_modal_reference/results/driven
python tools/run_modal_study.py --modes 8 --no-audio --output studies/plates/001_modal_reference/results/64_modes
```

`--driven` adds forces at the three proposed exciter positions, using
59.0/61.3/57.8 Hz. Forces are in N; they are not the original artistic amplitude
weights. Harmonic input switches on at the configured start with zero pre-existing
motion. Exact free and forced solutions permit reproducible backwards sampling.
Excitation patches must fit on the plate. A finite patch attenuates high-mode
coupling; impulse bandwidth and modal truncation still affect the result.

Run the eight named parameter variations with a small workload:

```bash
python tools/run_modal_experiments.py --duration 0.5 --modes 4 --audio
```

Read `results/experiments/comparison.md`, or open the per-case WAV files. The suite
compares frequencies, mass, retained energy and sampled pickup peak/RMS in SI units.
`coupling.csv` records dimensionless excitation and pickup weights for every mode;
placement can change these weights even when mode shapes/frequencies stay unchanged.
Optional WAVs are independently normalized, so compare raw data for physical levels.
Use `--output` to retain separate runs. All generated results remain ignored in Git.

To inspect the same selected experiment:

```bash
blender --python studies/plates/001_modal_reference/build.py -- --experiment 004_center_excitation
```

Every run saves `configuration.json`. Both the Python tool and Blender accept
`--config <configuration.json>` to reproduce it even after defaults change.
`report.json` is also accepted. Snapshot selection cannot be combined with
`--experiment` or `--driven`; Python's `--duration`/`--modes` remain explicit overrides.

Mechanical energy is in joules **for the retained modes**. Increasing mode count
shows that the default 36-mode broadband impulse response is not converged.
This remains an analytical, inspectable model with explicit truncation rather
than a verified representation of a fabricated vessel.

## Regenerate paper figures

Matplotlib and NumPy are optional plotting dependencies:

```bash
python -m pip install -e '.[paper]'
python tools/run_modal_study.py
python tools/plot_modal_study.py
python tools/plot_modal_experiments.py
```

The plotting command reads configuration from `report.json`, not potentially
changed defaults. It exports standalone PNG/PDF figures and truncation data into
`docs/research/modal_reference/figures/`. In a restricted environment, set
`MPLCONFIGDIR=/tmp/spatial-sculptures-matplotlib` when running the figure tool.
Raw study results are ignored in Git; curated paper figures and their parameter
summary are intentionally retained. The report records parameters, source hashes,
Python version, backend and audio gain.

The comparison plot exports standalone PNG/PDF from saved experiment results.
The paper's [parameter study](../../../docs/research/modal_reference/parameter_experiments.md)
records the complete default suite separately from quick runs.

## Validation

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Checks include square-plate frequency/scaling, supported boundaries, modal mass
by quadrature, free/forced ODE residuals, zero-damping resonance, conservation and
dissipation, nodal excitation, deterministic sampling, batched/scalar agreement,
and dependency-free WAV output. These establish implementation correctness for
the stated model, not physical accuracy for a basin. Real-vessel dry/wet
measurements, pressure coupling and radiation are subsequent work.
