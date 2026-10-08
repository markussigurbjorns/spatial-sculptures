# Dry-basin numerical convergence

Independently assembled spline and disk-polynomial Ritz models share shell assumptions.
This is numerical cross-verification, not specimen or acoustic validation.

Configured starting bank's supported sampled transfer band: **none recorded** (the starting bank may be absent from this plan).
All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.

| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) | Unfiltered impulse error (%) | Filtered impulse error (%) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 18 | 32 | 241.882 | 80.0 | 88.06 | 1.74 |
| 18 | 64 | 241.882 | 80.0 | 75.13 | 1.73 |
| 18 | 128 | 241.882 | 200.0 | 69.21 | 1.70 |
| 18 | 384 | 241.882 | 200.0 | 83.33 | 1.70 |
| 18 | 512 | 241.882 | 200.0 | 83.33 | 1.70 |
| 22 | 32 | 241.882 | 80.0 | 88.06 | 3.18 |
| 22 | 64 | 241.882 | 80.0 | 75.02 | 3.19 |
| 22 | 128 | 241.882 | 150.0 | 61.42 | 3.18 |
| 22 | 384 | 241.882 | 200.0 | 70.49 | 3.18 |
| 22 | 512 | 241.882 | 200.0 | 70.60 | 3.18 |
| 26 | 32 | 241.882 | 80.0 | 88.06 | 1.36 |
| 26 | 64 | 241.882 | 80.0 | 75.00 | 1.34 |
| 26 | 128 | 241.882 | 150.0 | 56.74 | 1.30 |
| 26 | 384 | 241.882 | 200.0 | 53.81 | 1.30 |
| 26 | 512 | 241.882 | 200.0 | 55.16 | 1.30 |

Smallest passing playback profile: **18 × 18, 128 modes**; sampled transfer band **200 Hz**.

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


Additional interval gates use edges [20.0, 40.0, 80.0, 160.0, 200.0] Hz. Each interval repeats the reference, mesh, truncation and independent-response criteria separately.
Strong lower-frequency resonances cannot compensate for a failed upper interval.
