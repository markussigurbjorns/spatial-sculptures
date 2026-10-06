# Decisions and assumptions — modal reference

Recorded 6 October 2026. These are research choices, not fabrication specifications.

| Decision | Status | Rationale / consequence |
| --- | --- | --- |
| Flat-plate reference before curved-basin FEM | Selected by the project owner | Gives an analytical reference and keeps the first physical implementation lightweight. No claim that the flat plate predicts the basin. |
| Provisional material and supports | Selected by the project owner | No vessel measurements or final support details are available. |
| Rectangular, homogeneous, isotropic Kirchhoff–Love plate | Implemented | Small transverse displacement; no membrane tension, curvature, shear deformation or rotary inertia. |
| Simply supported on all four edges | Implemented assumption | Displacement and normal bending moment vanish at edges; slopes are free. This differs from the sculpture's four local supports. |
| 1.44 × 1.16 m, 5 mm thickness | Provisional | Width/length reflect the current sculpture's envelope; the rectangle has a different area and structural response. Thickness carries over from configuration, not from a fabricated specimen. |
| Stainless-steel-like E = 193 GPa, density = 8030 kg/m³ | Manufacturer typical data | Cleveland-Cliffs 304/304L sheet, 2021. Does not select a supplier or certify a specimen. |
| Poisson ratio 0.30; damping ratio 0.005 for every mode | Unmeasured assumptions | Keep explicit and configurable; replace through fitting/measurement. Damping is phenomenological. |
| 6 × 6 retained modes | Computational choice | 36 independent modes, approximately 14.28–514.03 Hz. Broadband truncation is not declared converged. |
| 50 mm square excitation patch | Provisional | Uniform pressure over a finite area; total force is in N and total impulse in N·s. Reduces the pathological high-mode energy of a spatial point impulse. |
| Default 0.03 N·s impulse at t = 0 | Provisional | Tests ring-down without sustained input; no assertion that this is a water drop. |
| Optional three harmonic drives | Implemented experiment | Frequencies/positions copied from sculpture; amplitudes deliberately redefined as force in N, not the original dimensionless artistic weights. |
| Two ideal point contact-velocity pickups | Implemented | Reuse candidate XY locations, but they sample metal velocity in m/s; they are not hydrophones. |
| Offline 48 kHz PCM with one normalization gain | Implemented listening output | Preserves relative channel levels; no calibrated SPL, pressure, radiation or stereo spatialization. |
| Blender displacement ×2000 and time ×0.02 | Inspection choices | Explicit gain and slow motion expose fast, small vibration. WAV playback uses physical time; the slow-motion view is not synchronized to that WAV. |
| Working technical manuscript in Markdown + BibTeX | Initial publication form | Paper, source code and computed figures evolve together. Authorship, venue and final formatting remain open. |

Before a curved-basin model, decide material grade, measured thickness/profile,
local support stiffness/contact area, exciter mounting/force calibration, and the
frequency band of interest. Before water coupling, decide fill depth and the
accuracy required for surface motion versus underwater pressure. Before physical
validation, define repeatable recordings and sensor calibration. None of these
later decisions blocks the dry analytical reference.
