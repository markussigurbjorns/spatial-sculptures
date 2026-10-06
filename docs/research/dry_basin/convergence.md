# Dry-basin numerical convergence

Independently assembled spline and disk-polynomial Ritz models share shell assumptions.
This is numerical cross-verification, not specimen or acoustic validation.

Default supported sampled transfer band: **10.0 Hz**.
All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.

| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) | Unfiltered impulse error vs reference (%) |
| ---: | ---: | ---: | ---: | ---: |
| 8 | 16 | 76.541 | 10.0 | 92.36 |
| 8 | 32 | 76.541 | 10.0 | 95.58 |
| 8 | 48 | 76.541 | 10.0 | 105.09 |
| 8 | 64 | 76.541 | 10.0 | 110.38 |
| 10 | 16 | 145.906 | 10.0 | 86.24 |
| 10 | 32 | 145.906 | 10.0 | 83.89 |
| 10 | 48 | 145.906 | 10.0 | 88.54 |
| 10 | 64 | 145.906 | 10.0 | 89.98 |
| 12 | 16 | 145.906 | 10.0 | 84.70 |
| 12 | 32 | 242.658 | 10.0 | 77.60 |
| 12 | 48 | 242.658 | 10.0 | 74.70 |
| 12 | 64 | 242.658 | 10.0 | 87.13 |
| 14 | 16 | 145.906 | 10.0 | 84.61 |
| 14 | 32 | 423.900 | 10.0 | 77.41 |
| 14 | 48 | 423.900 | 10.0 | 64.69 |
| 14 | 64 | 423.900 | 10.0 | 52.59 |

Frequency checks: ≤1% difference and subspace MAC ≥0.99.
Reference checks: ≤0.25% frequency difference and subspace MAC ≥0.995.
Complex contact transfer: ≤10% relative L2 per pickup/exciter path; reference, mesh and modal refinement each ≤5%.
Signals retain SI units and common time; no listening normalization or phase alignment.
See JSON for individual path errors, failed checks, configurations and source provenance.

Shared Kirchhoff-Love physics; independently assembled numerical reference.
Sampled complex L2 tolerances are not pointwise bounds or broadband certification.
Transfer band assumes band-limited input/output; default WAV is unfiltered.
Finite reference/modal banks; no measured vessel, fluid or acoustic radiation.
