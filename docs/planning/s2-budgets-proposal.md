# S2-05 — Proposed M2 budgets and acceptance matrix (for confirmation)

Version **0.1 — for confirmation**. Date: **2026-10-12**. From the completed M2 baseline ([S2 report §9–§10](../stages/S2.md)). Plan rule: budgets are proposed with evidence and confirmed **before** the acceptance matrix is frozen and run. Nothing here changes a frozen S1 limit or an approved criterion.

## 1. Baseline facts

All runs: unattended, M6 envelope, patch-04 player, input recording on.

| Quantity | Measured (baseline) |
| --- | --- |
| Healthy laps in the final 5-lap batch (fixed bridge) | 5/5; lap time 122.9–123.8 s; min clearance 0.104–0.106 m |
| Time per episode in a batch (lap + settle + stop + reset) | 155.5 s |
| Fresh player start → first observation | 13.4–13.5 s |
| GUI Reset click → Connect | 5.07–5.08 s; one click each, except one dropped Reset click retried after 5 s (F2-1) |
| Readiness after a reset | spawn offset 0.001 m, yaw offset 0.0°, wheels still, guard disarmed (every reset) |
| Automated pre-Connect check | 0 mismatched text pixels in every check |
| Cleanup | 2.0–2.5 s |
| Observation age at request, max per lap (fixed bridge) | 312–324 ms; it reached 407 ms with the bridge slowdown |
| Clock bound max | 40–41 ms (fixed); 134 ms with the slowdown |
| Request generation → guard accept, max | 189–192 ms |
| Telemetry gap, max | 229–240 ms |
| F2 stop from onset (F2-4, 5, 7, 8) | 0.51–0.88 s; travel 0.087–0.18 m |
| F2 detection | clock fault 0.32 s; feedback lost 0.70 s; lease expiry 0.59–0.68 s after a supervisor loss; lease cleared 16 ms after a Devkit loss; hang contained at 2.11 s frame age |
| Recovery | 10/10 F2 cases recovered to a healthy next lap; every re-arm rejected the previous epoch's request (`stale-epoch`) |
| Replay | exact on every recording, ×3 fresh processes: up to 4,168 snapshots and 7,569 controller commands |
| Natural simulator stalls | **1** (batch 2, contained) in about 27 full driven laps |

## 2. Proposed budgets (D25)

The frozen S1 limits stay as they are. S2 adds the following budgets; each is checked automatically per episode or per batch.

| Budget | Proposed | Basis |
| --- | --- | --- |
| Readiness after a scene load | spawn ≤ 0.010 m, yaw ≤ 1°, wheels still, guard not armed and no fault | as built (D21); measured 0.001 m, 0.0° |
| Automated pre-Connect check | ≤ 8 mismatched text px per region | as built; measured 0 |
| GUI Reset → Connect | ≤ 20 s (up to 3 Reset clicks and 3 Connect clicks) | measured 5.1 s; one retry seen |
| Fresh player → first observation | ≤ 30 s | measured 13.5 s |
| Cleanup | ≤ 20 s (includes the 15 s shutdown-hang grace) | measured ≤ 2.5 s |
| **Observation age at request, per lap** | **≤ 400 ms** (S2 health budget, inside the S1 limit of 500 ms) | measured ≤ 324 ms; it would have caught the bridge slowdown (407 ms at lap 4) |
| Clock bound | ≤ 100 ms (S2 health budget; S1 limit 400) | measured ≤ 41 ms; 134 ms with the slowdown |
| Request generation → guard accept | ≤ 300 ms (S1 limit 500) | measured ≤ 192 ms |
| Stop after an F2 fault | ≤ 1.5 s and ≤ 0.40 m from onset (frozen S1 criteria) | measured ≤ 0.88 s, ≤ 0.18 m |
| F2 detection deadlines | clock fault ≤ 1.0 s; feedback lost ≤ 1.0 s; lease expiry after a supervisor loss ≤ 1.1 s; lease cleared after a Devkit loss ≤ 1.1 s with nothing applied afterwards; hang contained at ≤ 2.5 s frame age | measured 0.32 / 0.70 / 0.68 / 0.016 / 2.11 s |
| Stale reapplication | every re-arm rejects the previous epoch's request; no old command applied after a reset, reconnect or re-arm | as built |
| Replay | exact equality (D24), 3 fresh processes per fixture | measured exact |
| Batch wall time | 45 min for 10 episodes (raised from 30 min) | 10 × 155.5 s ≈ 26 min, plus margin for one recovery |

The F2-2 and F2-3 outcome stays "the lap continues, or a staleness stop within the S1 stop criteria", with committed snapshots strictly increasing.

## 3. Acceptance matrix (D26)

From the plan: ten consecutive healthy unattended episodes, each F2 case three times, five timing windows, and three fresh-process replays per selected fixture.

| Part | Proposed run | Estimated time (hands off) |
| --- | --- | --- |
| Ten consecutive healthy unattended episodes | one 10-episode batch | about 26 min |
| Five timing windows | episodes 1–5 of that batch (10 s warm-up + 120 s window, `--episode`) | (same batch) |
| F2 ×3 | 30 two-lap batches: F2-1 to F2-10, three times each | about 105 min |
| Replay fixtures ×3 fresh processes | the 3 analytical fixtures, the stationary recording, and the 10-episode batch recording | offline |

**Natural stalls.** One contained stall in about 27 laps. At that rate, a 10-episode batch would run without a stall with roughly 70 % probability.

**Proposed rule (D26 A):** a stall or any other failure inside the 10-episode batch fails that matrix item. It is retained, and the batch is rerun in full only with your approval. There is no relabelling and no "best 10 of 12".
- **Alternative B:** a 12-episode batch that must contain 10 consecutive healthy episodes. That is less strict than the plan's wording, so I do not recommend it.

**Order:** the 10-episode batch first, then the F2 runs, which can be split into three sessions of 10 (about 35 min each).

## 4. Requested reply

- **D25:** confirm or change the budgets in §2.
- **D26:** confirm A, or choose B, for the 10-episode rule; confirm the matrix in §3.

Running the matrix then needs its own run approval and a free desktop.
