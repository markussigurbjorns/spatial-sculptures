# Dry-basin numerical convergence

Independently assembled spline and disk-polynomial Ritz models share shell assumptions.
This is numerical cross-verification, not specimen or acoustic validation.

Configured starting bank's supported sampled transfer band: **none recorded** (the starting bank may be absent from this plan).
All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.

| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) | Unfiltered impulse error (%) | Filtered impulse error (%) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 14 | 16 | 145.890 | 15.0 | 85.27 | 12.53 |
| 14 | 32 | 423.836 | 15.0 | 78.25 | 12.48 |
| 14 | 48 | 423.836 | 15.0 | 66.01 | 12.49 |
| 14 | 64 | 423.836 | 15.0 | 54.40 | 12.48 |
| 18 | 16 | 145.890 | 100.0 | 85.20 | 2.14 |
| 18 | 32 | 429.673 | 100.0 | 78.16 | 2.03 |
| 18 | 48 | 488.778 | 100.0 | 64.36 | 1.97 |
| 18 | 64 | 488.778 | 100.0 | 13.71 | 1.70 |
| 22 | 16 | 145.890 | 100.0 | 85.20 | 3.42 |
| 22 | 32 | 429.673 | 100.0 | 78.16 | 3.35 |
| 22 | 48 | 536.528 | 100.0 | 64.33 | 3.31 |
| 22 | 64 | 652.829 | 100.0 | 4.78 | 3.18 |
| 26 | 16 | 145.890 | 100.0 | 85.20 | 1.84 |
| 26 | 32 | 429.673 | 100.0 | 78.16 | 1.70 |
| 26 | 48 | 536.528 | 100.0 | 64.30 | 1.63 |
| 26 | 64 | 652.829 | 100.0 | 1.86 | 1.30 |

Smallest passing playback profile: **18 × 18, 16 modes**; sampled transfer band **100 Hz**.

Filtered impulse column: identical zero-phase FIR, pass band 80 Hz, stop band 100 Hz; raw SI gain and phase retained.
Frequency checks: ≤1% difference and subspace MAC ≥0.99.
Reference checks: ≤0.25% frequency difference and subspace MAC ≥0.995.
Complex contact transfer: ≤10% relative L2 per pickup/exciter path; reference, mesh and modal refinement each ≤5%.
Quadrature and frequency-grid refinement: ≤1%; candidate-to-next-mesh refinement also ≤5%.
Signals retain SI units and common time; no listening normalization or phase alignment.
See JSON for individual path errors, failed checks, configurations and source provenance.

Shared Kirchhoff-Love physics; independently assembled numerical reference.
Sampled complex L2 tolerances are not pointwise bounds or broadband certification.
Transfer band assumes band-limited input/output; default WAV is unfiltered.
Finite reference/modal banks; no measured vessel, fluid or acoustic radiation.
