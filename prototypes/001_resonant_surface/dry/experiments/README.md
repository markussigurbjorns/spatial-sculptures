# Dry-basin parameter experiments

Each numbered Python file implements `configure(config)` and returns explicit
changes to the same model. Parameters use SI units; they are provisional.

| Experiment | Change from baseline |
| --- | --- |
| `001_baseline` | Curved 5 mm basin, four spring supports, three 0.12 kg housings, one impulse |
| `002_flat_profile` | Zero rise/asymmetry; elliptical plan and local supports retained |
| `003_soft_supports` | Each translational support stiffness divided by four |
| `004_heavier_exciters` | Each rigid housing mass increased to 0.60 kg |
| `005_thin_3mm` | Uniform thickness reduced to 3 mm |
| `006_three_drives` | No impulse; three prescribed 1.0/0.85/0.95 N harmonic forces |

```bash
python tools/run_dry_basin.py --experiment 002_flat_profile --preview --render --output prototypes/001_resonant_surface/renders/dry_flat
```

Each output contains a complete JSON configuration, modal frequencies/masses,
source hashes, retained energy, pre-normalization pickup peaks, WAV and frame data.
Replay with `--config path/to/configuration.json`. Keep separate output directories
for comparisons. Normalized WAV loudness does not compare mechanical amplitudes.

Support and housing changes represent rigid translating patches. No rotational
foot stiffness or compliant exciter adhesive is modeled. Flat-profile frequencies
are numerical frequencies of a supported ellipse, not the simply-supported
rectangular analytical reference. Thin-shell mesh convergence must be rechecked
after substantial profile/thickness/support changes.
