# Validation record — 6 October 2026

This record concerns mathematical/software checks, not physical validation.
Parameters and source hashes are recorded in [computed_summary.json](computed_summary.json).

| Check | Result |
| --- | --- |
| Ordinary Python compilation | Passed for `src`, `prototypes`, `studies`, `tools`, `tests` |
| Ruff checks and formatting | Passed |
| Standard-library unittest suite with NumPy installed | 69 tests: 68 passed, 1 UDP delivery test skipped because sockets are forbidden |
| Full suite without NumPy | 69 tests: 55 passed, 14 skipped (13 optional NumPy tests, 1 blocked UDP delivery test) |
| Original Blender prototype integration | Passed, including repeated builds, live/timeline cleanup and sampling without NumPy |
| Modal Blender integration | Passed in Blender 4.5.9: mode-derived coordinates, boundary displacement, time/gain metadata, backwards scrubbing, rebuild cleanup, named/saved configurations, rejected wet request without clearing the scene, and switching to the sculpture |
| Offline output | Generated 2-channel, 48 kHz, 16-bit PCM; 192,000 frames = 4 physical seconds |
| Reference figures | Generated PNG/PDF from recorded parameters and SI response data; visually inspected, including the parameter comparison |
| Parameter experiment suite | All 8 cases exported with 36 modes, 4 s duration; short 16-mode, 0.5 s suite also generated 8 WAV files |
| Saved-configuration replay | Numerical response, mode/coupling tables and WAV bytes match; tested with NumPy, Blender and sockets unavailable |
| Unsupported physics | Curvature, local supports, thickness map, mass/compliant mounting and positive water depth rejected explicitly |
| Launch from another working directory | Saved-configuration export from `/tmp` passed |
| Stale comparison data | Plotting rejects a changed case report before producing a figure |
| Source provenance | Refreshed hashes include the shared `mode_bank.py` response engine; plate results are unchanged |
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
python tools/run_modal_experiments.py
python tools/plot_modal_experiments.py
```

Software checks include the square-plate reference frequency, dimensional scaling,
modal mass integration, oscillator ODE residuals, energy conservation/dissipation,
nodal excitation, exact undamped resonance, scalar/array agreement, rejected
invalid inputs and WAV export without NumPy. The 36-mode impulse response is
explicitly **not broadband-converged**, as the paper's truncation table shows.
