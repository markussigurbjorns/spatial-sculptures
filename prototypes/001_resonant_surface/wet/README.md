# Wet resonant basin — spatial potential model

The metal and water now share a **linear, nonlocal fluid-inertia model**. Interior
virtual hydrophones sample dynamic pressure in Pa. One modal response produces
metal motion, kinematic water elevation and pressure audio; Python owns all
equations and Blender consumes precomputed frames.

```bash
# NumPy only; NGSolve and SuperCollider are unnecessary for playback.
python tools/run_wet_basin.py --preview --view
python tools/run_wet_basin.py --preview --render
python tools/run_wet_basin.py --preview --duration 4
```

Press Space in Blender for playback. `--render` requires FFmpeg and writes
`prototypes/001_resonant_surface/renders/wet/wet_basin.mp4`. Without either view
option, export produces `hydrophones.wav`, raw/filtered pressure in `pressure.npz`,
`frames.npz`, a configuration snapshot and a report. The default demonstration is
two seconds long. `--preview` reduces image resolution and presentation meshes,
while retaining the numerical model. It loads saved portable modes and observations,
so playback does not repeat fluid or structural assembly.

The two WAV channels correspond to the two hydrophones. They contain the modeled
**pressure perturbation**, after a common offline listening filter and gain. They
are not calibrated real hydrophone recordings, speaker radiation or binaural audio.
The initial pulse acts at exciter 1: 0.03 N s delivered as 3 N for 10 ms. It is not
a falling-water-drop model.

## What water means here

The configuration uses 65 mm above the lowest basin point, water density 1000 kg/m³,
and two probes 20 mm below the mean surface. The resting volume is approximately
23.05 litres. The water has spatial potential flow and nonlocal inertia, rather
than independent columns. The top is pressure-release (`φ=0`); surface elevation
comes from its linear kinematic condition.

This stage has **no gravity/capillary waves, fluid damping, compressibility,
hydrostatic prestress or moving contact line**. The visible water is not the old
artistic ripple overlay. Both surfaces use the same exposure-averaged physical
response with magnification for legibility; a video frame cannot display every
audio oscillation. Hydrophones stay at their configured resting XYZ locations.

## Evidence and configuration

The saved [wet evidence](../../../docs/research/wet_basin/validation.json) checks
0–20, 20–40 and 40–80 Hz separately, including contact velocity, pressure and
surface elevation. The selected bank uses 18 × 18 shell cells, 256 dry basis modes,
fluid degree 10 horizontally / 2 vertically and 64 wet playback modes.
The output filter passes through **64 Hz** and reaches its stop band at **80 Hz**.
Higher tested intervals fail; the dry model's 200 Hz evidence does not establish a
wet band. This initial sound is therefore restricted to low frequencies.

Edit [config.py](config.py) for depth, density, probe positions, pulse duration and
tested playback settings. Changes invalidate evidence; rerun the water validation
before exporting. Changing the resolution family requires adding explicit cases
to the study. The dry baseline's profile, material, thickness, support and exciter
mounting properties are recorded independently in the evidence snapshot.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/validate_wet_basin.py --external
MPLCONFIGDIR=/tmp/spatial-sculptures-matplotlib python tools/plot_wet_basin.py
```

Omit `--external` without NGSolve. Structural study caches live in ignored `data/fem/`;
the selected portable playback bank and numerical report live in the research
directory. Export rejects stale source hashes, failed gates and altered artifacts.
See [the research note](../../../docs/research/wet_basin/study.md) for equations,
primary references, assumptions and the limits of numerical agreement.

Future stages add free-surface restoring forces and resonances, independent curved
wet-vessel validation, DSP feedback and eventually measurements. Real hydrophone
data can later replace simulated pressure without putting the DSP or numerical
solver inside Blender. The original artistic and certified dry demos remain
separate reproducible experiments.
