# Dry-basin numerical convergence

Independently assembled spline and disk-polynomial Ritz models share shell assumptions.
This is numerical cross-verification, not specimen or acoustic validation.

Configured starting bank's supported sampled transfer band: **10.0 Hz**.
All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.

| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) | Unfiltered impulse error (%) | Filtered impulse error (%) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 16 | 76.541 | 10.0 | 92.36 | 70.01 |
| 8 | 32 | 76.541 | 10.0 | 95.58 | 70.00 |
| 8 | 48 | 76.541 | 10.0 | 105.09 | 69.99 |
| 8 | 64 | 76.541 | 10.0 | 110.38 | 69.99 |
| 10 | 16 | 145.906 | 10.0 | 86.24 | 33.75 |
| 10 | 32 | 145.906 | 10.0 | 83.89 | 33.71 |
| 10 | 48 | 145.906 | 10.0 | 88.54 | 33.71 |
| 10 | 64 | 145.906 | 10.0 | 89.98 | 33.71 |
| 12 | 16 | 145.906 | 10.0 | 84.70 | 12.86 |
| 12 | 32 | 241.887 | 10.0 | 77.60 | 12.83 |
| 12 | 48 | 241.887 | 10.0 | 74.70 | 12.83 |
| 12 | 64 | 241.887 | 10.0 | 87.13 | 12.75 |
| 14 | 16 | 145.906 | 10.0 | 84.61 | 1.89 |
| 14 | 32 | 241.887 | 10.0 | 77.41 | 1.65 |
| 14 | 48 | 241.887 | 10.0 | 64.69 | 1.54 |
| 14 | 64 | 241.887 | 10.0 | 52.59 | 0.96 |

Filtered impulse column: identical zero-phase FIR, pass band 160 Hz, stop band 200 Hz; raw SI gain and phase retained.
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
