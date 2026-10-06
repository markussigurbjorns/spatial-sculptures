# Resonant-surface experiments

These are artistic/research parameter variations, not unit tests. Each module
exposes `configure(config) -> config` and receives a fresh copy of the baseline.
It changes only parameters and uses the common geometry/simulation/build code.

- `001_three_exciters.py`: unmodified baseline with three independently phased sources.
- `002_close_frequencies.py`: 59.00, 59.08, 59.17 Hz; shared wavelength, real-time
  phase scale, and a longer, more finely sampled animation to observe slow beating.

Run from the repository root:

```bash
python tools/run_blender.py 001_resonant_surface --experiment 002_close_frequencies
```

For a new variation, add `003_your_question.py` and explicitly change the fields
that matter. Describe the research question, assumptions, and observations in its
docstring or accompanying notes. Leave defaults untouched. Configuration is plain
Python; no registry or configuration framework is required.
