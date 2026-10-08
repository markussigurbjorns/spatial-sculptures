# Dry-basin numerical convergence

Independently assembled spline and disk-polynomial Ritz models share shell assumptions.
This is numerical cross-verification, not specimen or acoustic validation.

Configured starting bank's supported sampled transfer band: **none recorded** (the starting bank may be absent from this plan).
All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.

| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) | Unfiltered impulse error (%) | Filtered impulse error (%) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 18 | 32 | 241.752 | 40.0 | 87.60 | 0.97 |
| 18 | 64 | 241.752 | 80.0 | 75.51 | 0.93 |
| 18 | 128 | 241.752 | 200.0 | 69.43 | 0.89 |
| 18 | 384 | 241.752 | 200.0 | 83.61 | 0.89 |
| 18 | 512 | 241.752 | 200.0 | 83.61 | 0.89 |
| 22 | 32 | 241.752 | 40.0 | 87.60 | 1.61 |
| 22 | 64 | 241.752 | 80.0 | 75.40 | 1.60 |
| 22 | 128 | 241.752 | 150.0 | 61.62 | 1.58 |
| 22 | 384 | 241.752 | 200.0 | 70.72 | 1.58 |
| 22 | 512 | 241.752 | 200.0 | 70.83 | 1.58 |
| 26 | 32 | 241.752 | 40.0 | 87.59 | 0.79 |
| 26 | 64 | 241.752 | 80.0 | 75.38 | 0.71 |
| 26 | 128 | 241.752 | 150.0 | 56.94 | 0.66 |
| 26 | 384 | 241.752 | 200.0 | 53.99 | 0.66 |
| 26 | 512 | 241.752 | 200.0 | 55.35 | 0.66 |

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
