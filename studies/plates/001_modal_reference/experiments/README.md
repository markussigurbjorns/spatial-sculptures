# Dry reference parameter experiments

These are artistic/research variations, not unit tests. Each numbered Python file
contains a small `configure(config)` function applied to fresh study defaults.
Copy a file and change a parameter to add a case; no geometry or solver duplication
is needed. File names are discovered in sorted order.

| Experiment | Change from baseline |
| --- | --- |
| `001_baseline` | 5 mm plate, 50 mm off-centre impulse patch, damping ratio 0.005 |
| `002_thin_3mm` | Uniform thickness 3 mm |
| `003_thick_7mm` | Uniform thickness 7 mm |
| `004_center_excitation` | Impulse patch moved to (0, 0) m |
| `005_wide_contact` | 150 mm patch; total impulse stays 0.03 N·s |
| `006_more_damping` | Damping ratio 0.02 for all retained modes |
| `007_shifted_pickups` | Pickups moved to (0, 0) and (0.40, −0.20) m |
| `008_three_drives` | Add the three prescribed harmonic forces to the impulse |

Run a small comparison, including optional listening files:

```bash
python tools/run_modal_experiments.py --duration 0.5 --modes 4 --audio
```

The default output is `studies/plates/001_modal_reference/results/experiments/`.
Each case has a configuration snapshot, report, mode/coupling tables and SI response;
`comparison.md`, `comparison.csv` and `comparison.json` summarize the run. Duration
and mode overrides apply to every case. Without `--audio` the suite skips WAV
generation. Use `--output` to keep another run, since rerunning replaces generated
files in the selected output directory.

```bash
python tools/run_modal_experiments.py --experiments 001_baseline 004_center_excitation
python tools/run_modal_study.py --experiment 002_thin_3mm
python tools/run_modal_study.py --list-experiments
```

Named single runs automatically go into `results/<name>/`, separately from suite
outputs under `results/experiments/`. To replay
exact saved values rather than today's defaults:

```bash
python tools/run_modal_study.py --config studies/plates/001_modal_reference/results/002_thin_3mm/configuration.json --output studies/plates/001_modal_reference/results/replay
blender --python studies/plates/001_modal_reference/build.py -- --config studies/plates/001_modal_reference/results/002_thin_3mm/configuration.json
```

The Blender view also accepts `--experiment 002_thin_3mm`. It remains magnified
slow-motion inspection; the WAV uses normal physical time.

Optional publication figures use Matplotlib:

```bash
python tools/plot_modal_experiments.py
```

This saves PNG/PDF charts in the comparison directory. All comparisons use
unnormalized SI quantities. Each optional WAV has its own reported normalization
gain; listening loudness cannot compare physical levels between cases. Peak/RMS
estimates refer to each reported dense response grid. Driven cases receive energy,
so their energy ratio is not a ring-down decay measure. Modal truncation and
unmeasured assumptions apply to every case.
