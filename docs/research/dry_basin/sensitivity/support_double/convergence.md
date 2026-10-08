# Dry-basin numerical convergence

Independently assembled spline and disk-polynomial Ritz models share shell assumptions.
This is numerical cross-verification, not specimen or acoustic validation.

Configured starting bank's supported sampled transfer band: **none recorded** (the starting bank may be absent from this plan).
All lower tested cutoffs must pass. Band support does not certify the unfiltered WAV.

| Cells/axis | Modes | Frequency-only prefix (Hz) | Sampled transfer band (Hz) | Unfiltered impulse error (%) | Filtered impulse error (%) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 18 | 32 | 242.904 | 80.0 | 89.79 | 2.95 |
| 18 | 64 | 242.904 | 100.0 | 75.98 | 2.91 |
| 18 | 128 | 242.904 | 200.0 | 70.25 | 2.90 |
| 18 | 384 | 242.904 | 200.0 | 84.58 | 2.90 |
| 18 | 512 | 242.904 | 200.0 | 84.59 | 2.90 |
| 22 | 32 | 242.904 | 80.0 | 89.80 | 5.48 |
| 22 | 64 | 242.904 | 100.0 | 75.88 | 5.46 |
| 22 | 128 | 242.904 | 200.0 | 62.36 | 5.45 |
| 22 | 384 | 242.904 | 200.0 | 71.58 | 5.45 |
| 22 | 512 | 242.904 | 200.0 | 71.69 | 5.45 |
| 26 | 32 | 242.904 | 80.0 | 89.79 | 2.29 |
| 26 | 64 | 242.904 | 80.0 | 75.84 | 2.25 |
| 26 | 128 | 242.904 | 200.0 | 57.59 | 2.23 |
| 26 | 384 | 242.904 | 200.0 | 54.61 | 2.23 |
| 26 | 512 | 242.904 | 200.0 | 55.98 | 2.23 |

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
