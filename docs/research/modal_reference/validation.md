# Validation record — 6 October 2026

This record concerns mathematical/software checks, not physical validation.
Parameters and source hashes are recorded in [computed_summary.json](computed_summary.json).

| Check | Result |
| --- | --- |
| Ordinary Python compilation | Passed for `src`, `prototypes`, `studies`, `tools`, `tests` |
| Ruff checks and formatting | Passed |
| Standard-library unittest suite with NumPy installed | 49 tests: 48 passed, 1 UDP delivery test skipped because sockets are forbidden |
| Suite without NumPy | Dependency-free modal trace/WAV/export paths passed; optional array comparisons skip |
| Original Blender prototype integration | Passed, including repeated builds, live/timeline cleanup and sampling without NumPy |
| Modal Blender integration | Passed in Blender 4.5.9: mode-derived coordinates, boundary displacement, time/gain metadata, backwards scrubbing, rebuild cleanup and switching to the sculpture |
| Offline output | Generated 2-channel, 48 kHz, 16-bit PCM; 192,000 frames = 4 physical seconds |
| Reference figures | Generated PNG/PDF from recorded parameters and SI response data; visually inspected |
| Launch from another working directory | One-mode export from `/tmp` passed |
| Source provenance | Recorded source hashes match the current model, audio exporter and study tool |
| SuperCollider playback and audible evaluation | Not validated here: server networking is unavailable in the sandbox |
| Real-vessel measurements / acoustic radiation / hydrophone pressure / listener study | Not implemented or measured |

Reproduce checks from the repository root:

```bash
python -m compileall -q src prototypes studies tools tests
ruff check .
ruff format --check .
PYTHONPATH=src python -m unittest discover -s tests
blender --background --factory-startup --python-exit-code 1 --python tests/validate_modal_blender.py
blender --background --factory-startup --python-exit-code 1 --python tests/validate_blender.py
python tools/run_modal_study.py
python tools/plot_modal_study.py
```

Software checks include the square-plate reference frequency, dimensional scaling,
modal mass integration, oscillator ODE residuals, energy conservation/dissipation,
nodal excitation, exact undamped resonance, scalar/array agreement, rejected
invalid inputs and WAV export without NumPy. The 36-mode impulse response is
explicitly **not broadband-converged**, as the paper's truncation table shows.
