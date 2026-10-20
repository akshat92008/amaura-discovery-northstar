# AMAURA LABS — PRESERVED EXPERIMENT AUDIT & ARCHIVE
**Timestamp:** 2026-10-12 01:07:30 IST  
**Archive File:** `stage3/backups/results_backup_20261012_010716.tar.gz`  
**Archive SHA-256:** `95902d63990222a52f1b18009efce523e47aa1b9382d2d452c781f6069acb5ac`  
**Candidates File:** `stage3/candidates/main_candidates.jsonl`  
**Candidates SHA-256:** `61832b1abb28b7f599f8b717b918ff6790ff7b37cba572bc5e0f8b3a5a6777d8`  

## 1. Verified Completed Trial Records

| Trial ID | Arm A Score | Arm B Score | Arm C Score | $\Delta(C - A)$ | Duration | Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trial 01** | 222 | 221 | 221 | -1 | 2.00h (7,218s) | COMPLETED |
| **Trial 02** | 222 | CRASH (None) | 219 | -3 | 1.59h (5,708s) | COMPLETED |
| **Trial 03** | 222 | CRASH (None) | 219 | -3 | 1.47h (5,299s) | COMPLETED |
| **Trial 04** | 222 | CRASH (None) | 222 | 0 | 1.78h (6,402s) | COMPLETED |
| **Trial 05** | 222 | 235 | 221 | -1 | 1.86h (6,707s) | COMPLETED |
| **Trial 06** | 222 | 223 | *In Gen 9-10* | *Pending* | *In Progress* | RUNNING |

## 2. Integrity & Validity Metrics (Trials 01–05)
- **Arm A (Independent Best-of-100):** 261/500 valid (52.2%). Median score: 222.
- **Arm B (Blind Iterative Search):** 155/500 valid (31.0%). Crashed in 3/5 trials.
- **Arm C (Amaura Execution Feedback):** 463/500 valid (**92.6%**). Mean $\Delta(C-A) = -1.60$ colors.

## 3. Preserved Artifacts
- All candidate slots (1,780+ generated) backed up in `stage3/backups/`.
- Per-trial JSON records, status files, and lineage logs persisted atomically.
