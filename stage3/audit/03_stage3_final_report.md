# AMAURA LABS STAGE 3: CERTIFIED FINAL REPORT
**Domain:** Minimum Vertex Graph Coloring
**Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b`
**Protocol Revision:** Revision 4.3 (Frozen Pre-Registration)
**Execution Mode:** Strictly Sequential (Concurrency = 1, Exactly One In-Flight Request)
**Design:** $T = 30$ Paired Trials $\times$ 3 Arms $\times$ $N = 100$ Slots (9,000 Total Candidate Slots)
**Total Wall-Clock Time:** 38.62 hours (139031.5 s)
**Total Inference Calls:** 5,117
**Total Tokens:** 48,089,420 (Input: 35,774,321, Output: 12,315,099)
**Total Inference Cost:** $292.05

---

## 1. EXECUTIVE SUMMARY & FINAL DECISION

**Final Preregistered Decision:** `NOT_SUPPORTED`

### Primary Continuous Endpoint (C vs A on Dual-Valid Trials)
- **Dual-Validity Gate ($P(\text{valid}) \ge 90\%$ for both arms):**
  - Arm C Validity: **100.0%** (0/30)
  - Arm A Validity: **100.0%** (0/30)
  - Gate Passed: `True`
- **Dual-Valid Paired Difference $\Delta_t = \text{Score}_{C,t} - \text{Score}_{A,t}$:**
  - Dual-Valid Trials Count: **30 / 30**
  - Mean Paired Difference $\mathbb{E}[\Delta]$: **0.3333 colors**
  - Median Paired Difference: **0.5 colors**
  - 95% Bootstrap CI: **[-6.1008, 6.7]**
  - Two-Sided Paired Wilcoxon $p$-value: **0.9741132070078699**
  - Holm-Bonferroni Adjusted $p$-value: **0.9741132070078699**
  - Practical Criterion Met (CI upper bound $< -1.0$ color): `False`

### Binary Reliability Endpoint
- Arm C Failures: 30 | Arm A Failures: 30
- Risk Difference $\text{RD} = P(\text{Fail}_C) - P(\text{Fail}_A)$: 0.0000 (95% CI: [0.0, 0.0])
- Exact Two-Sided McNemar $p$-value: 1.0
- Reliability Failure Triggered: `False`

### Worst-Case Bounded-Imputation Sensitivity Analysis ($S_{penalty} = 19,001$)
- Imputed Mean Difference $\mathbb{E}[\Delta_{imputed}]$: **0.3333 colors**
- Imputed 95% Bootstrap CI: **[-6.1008, 6.7]**
- Imputed Paired Wilcoxon $p$-value: **0.9741132070078699**

---

## 2. TRIAL-BY-TRIAL RESULTS (T = 1..30)

| Trial | Seed | Arm A Dev | Arm A Hidden | Arm B Dev | Arm B Hidden | Arm C Dev | Arm C Hidden | $\Delta_{C-A}$ (Hidden) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 01 | 30301 | 222 | 1292 | 221 | 1247 | 221 | 1278 | -14 |
| 02 | 30302 | 222 | 1277 | FAIL | FAIL | 219 | 1277 | +0 |
| 03 | 30303 | 222 | 1275 | FAIL | FAIL | 219 | 1237 | -38 |
| 04 | 30304 | 222 | 1257 | FAIL | FAIL | 222 | 1287 | +30 |
| 05 | 30305 | 222 | 1287 | 235 | 1330 | 221 | 1271 | -16 |
| 06 | 30306 | 222 | 1272 | 223 | 1280 | 221 | 1281 | +9 |
| 07 | 30307 | 222 | 1257 | FAIL | FAIL | 222 | 1280 | +23 |
| 08 | 30308 | 222 | 1297 | FAIL | FAIL | 221 | 1282 | -15 |
| 09 | 30309 | 222 | 1281 | 224 | 1270 | 221 | 1282 | +1 |
| 10 | 30310 | 222 | 1275 | 225 | 1282 | 220 | 1254 | -21 |
| 11 | 30311 | 222 | 1274 | 226 | 1273 | 219 | 1255 | -19 |
| 12 | 30312 | 221 | 1284 | FAIL | FAIL | 220 | 1248 | -36 |
| 13 | 30313 | 221 | 1251 | 225 | 1278 | 221 | 1278 | +27 |
| 14 | 30314 | 222 | 1276 | FAIL | FAIL | 222 | 1290 | +14 |
| 15 | 30315 | 220 | 1253 | FAIL | FAIL | 221 | 1280 | +27 |
| 16 | 30316 | 220 | 1260 | FAIL | FAIL | 221 | 1263 | +3 |
| 17 | 30317 | 222 | 1281 | 223 | 1276 | 220 | 1283 | +2 |
| 18 | 30318 | 222 | 1273 | 227 | 1285 | 220 | 1266 | -7 |
| 19 | 30319 | 221 | 1278 | 235 | 1334 | 222 | 1269 | -9 |
| 20 | 30320 | 222 | 1275 | FAIL | FAIL | 221 | 1277 | +2 |
| 21 | 30321 | 222 | 1278 | 227 | 1289 | 222 | 1290 | +12 |
| 22 | 30322 | 221 | 1275 | FAIL | FAIL | 225 | 1287 | +12 |
| 23 | 30323 | 222 | 1280 | 223 | 1264 | 222 | 1279 | -1 |
| 24 | 30324 | 221 | 1281 | 222 | 1276 | 220 | 1277 | -4 |
| 25 | 30325 | 221 | 1280 | FAIL | FAIL | 221 | 1267 | -13 |
| 26 | 30326 | 222 | 1248 | 227 | 1311 | 220 | 1251 | +3 |
| 27 | 30327 | 222 | 1271 | 222 | 1280 | 221 | 1269 | -2 |
| 28 | 30328 | 222 | 1267 | 222 | 1270 | 221 | 1279 | +12 |
| 29 | 30329 | 220 | 1243 | FAIL | FAIL | 222 | 1280 | +37 |
| 30 | 30330 | 223 | 1272 | FAIL | FAIL | 221 | 1263 | -9 |

---

## 3. SECONDARY COMPARISON: ARM C vs ARM B (BLIND ITERATIVE)

- Dual-Valid Count: 16 / 30
- Mean Difference $\mathbb{E}[\Delta_{C-B}]$: **-11.4375 colors**
- 95% Bootstrap CI: **[-25.5625, 1.1891]**
- Raw Wilcoxon $p$-value: **0.3062337331376457**
- Holm-Bonferroni Adjusted $p$-value: **0.6124674662752914**

---

## 4. SCIENTIFIC AUDIT PROVENANCE

1. **Deterministic Lineage:** All 9,000 generated candidate codes, prompts, seeds, latency records, and token usages are immutably logged in `stage3/candidates/main_candidates.jsonl`.
2. **Technical Firewall Integrity:** The 200 hidden benchmark instances were technically blocked via `PermissionError` until all 30 trial selections were frozen in `SELECTIONS_FROZEN`.
3. **Strictly Sequential:** Concurrency = 1. Zero batching, zero concurrent requests, zero hidden retries or replacements.
4. **State Machine Audit:** State transitions logged in `stage3/audit/audit_log.jsonl`.
