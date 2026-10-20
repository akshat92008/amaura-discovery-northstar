# AMAURA LABS — PRESERVED EXPERIMENT AUDIT & ARCHIVE
**Timestamp:** 2026-10-13 09:56:31 IST  
**Archive File:** `stage3/backups/results_backup_20261013_095631.tar.gz`  
**Archive SHA-256:** `b7461ad36792f9600149bd2fdc3c2c59c9802a902631148279f1e9a394d5f5dd`  
**Candidates File:** `stage3/candidates/main_candidates.jsonl`  
**Candidates SHA-256:** `543936d9b818c087bd09b03dfef1b3809adffb3d7d3e4e0adc5312c0b2eff787`  

## 1. Verified Completed Trial Records (Trials 01–13)

| Trial ID | Seed | Arm A Score | Arm B Score | Arm C Score | $\Delta(C - A)$ | Duration | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trial 01** | `30301` | 222 | 221 | **221** | -1 | 2.00h (7,218s) | COMPLETED |
| **Trial 02** | `30302` | 222 | CRASH (None) | **219** | -3 | 1.59h (5,708s) | COMPLETED |
| **Trial 03** | `30303` | 222 | CRASH (None) | **219** | -3 | 1.47h (5,299s) | COMPLETED |
| **Trial 04** | `30304` | 222 | CRASH (None) | **222** | 0 | 1.78h (6,402s) | COMPLETED |
| **Trial 05** | `30305` | 222 | 235 | **221** | -1 | 1.86h (6,693s) | COMPLETED |
| **Trial 06** | `30306` | 222 | 223 | **221** | -1 | 1.74h (6,271s) | COMPLETED |
| **Trial 07** | `30307` | 222 | CRASH (None) | **222** | 0 | 1.51h (5,432s) | COMPLETED |
| **Trial 08** | `30308` | 222 | CRASH (None) | **221** | -1 | 1.33h (4,791s) | COMPLETED |
| **Trial 09** | `30309` | 222 | 224 | **221** | -1 | 2.32h (8,359s) | COMPLETED |
| **Trial 10** | `30310` | 222 | 225 | **220** | -2 | 2.23h (8,017s) | COMPLETED |
| **Trial 11** | `30311` | 222 | 226 | **219** | -3 | 2.10h (7,556s) | COMPLETED |
| **Trial 12** | `30312` | 221 | CRASH (None) | **220** | -1 | 2.13h (7,656s) | COMPLETED |
| **Trial 13** | `30313` | 221 | 225 | **221** | 0 | 1.93h (6,957s) | COMPLETED |
| **Trial 14** | `30314` | 221 | 226 | *In Gen 3/10* | *Pending* | *In Progress* | RUNNING |

## 2. Integrity & Statistical Metrics (Trials 01–13)
- **Arm C vs Arm A:** 10 Wins, 3 Ties, 0 Losses. Mean $\Delta(C-A) = -1.31$ colors (95% CI: $[-1.92, -0.77]$, Wilcoxon $p = 0.00195$).
- **Arm C Self-Improvement (Gen 1 -> Gen 10):** 13/13 improved. Mean gain $= -3.38$ colors (95% CI: $[-4.31, -2.46]$, Wilcoxon $p = 0.00024$).
- **Validity Rates:** Arm C = 90.54%, Arm A = 52.14%, Arm B = 49.04% (6/13 trial crashes).
