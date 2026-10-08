# Dry support/mount sensitivity

Provisional assumptions changed, with independent convergence checks per case.
Changes use raw SI mobility over 20–200 Hz, all six paths, and full banks.
These changes are not numerical errors or measured uncertainty estimates.

| Case | First frequency (Hz) | Largest response change (%) | Passing 200 Hz bank |
| --- | ---: | ---: | --- |
| [support_half](support_half/convergence.md) | 3.039 | 104.88 | 18 × 18, 128 modes |
| [support_double](support_double/convergence.md) | 6.076 | 161.88 | 18 × 18, 128 modes |
| [mount_narrow](mount_narrow/convergence.md) | 4.297 | 0.08 | 18 × 18, 128 modes |
| [mount_wide](mount_wide/convergence.md) | 4.297 | 0.13 | 18 × 18, 128 modes |

Support cases scale all total X/Y/Z springs together. Mount cases change patch width while retaining each 120 g rigid housing and total applied force. Glue compliance and electrical actuation remain absent.
