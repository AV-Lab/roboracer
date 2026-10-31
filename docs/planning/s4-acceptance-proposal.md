# S4-06 proposal — M4 acceptance criteria and matrix

Version **0.1, 2026-11-01**. This is based on the M4 baseline after D65 A ([S4 §20](../stages/S4.md)): T1, T2 and T3 × 3, 9/9 passed. It also uses the first baseline (§18), whose T2 failures are retained, and the F4 and rearm runs (§12, §15). **No motion is proposed here.** The acceptance run needs its own approval.

**Plan (M4):**
- T1/T2/T3 on C0, **ten repetitions each with B (30 episodes)**;
- F4 cases separately, three times each;
- approved avoidance and blocked-stop criteria;
- no moving-opponent criterion.

## 1. Baseline evidence (D64 rerun, `artifacts/s4/20261031T204742Z-m4-baseline-d65/`)

| Measure | T1 (3) | T2 (3) | T3 (3) |
| --- | --- | --- | --- |
| Lap, whole-run basis | 68.31–68.33 s | 68.83–69.03 s | — |
| Minimum obstacle clearance | 0.350–0.371 m | 0.400–0.416 m | rest 1.443–1.506 m |
| Minimum wall clearance | 0.291–0.293 m | 0.274–0.293 m | 0.328–0.355 m |
| Swerve from the line | 0.40–0.41 m (left) | 0.45–0.46 m (right) | — |
| Blocked latch | — | — | after 2.75–2.81 m at 0.50 m/s |
| ICP | valid on every driving tick; per-tick error p95 ≤ 0.023 m, max ≤ 0.049 m | p95 ≤ 0.024 m, max ≤ 0.073 m | p95 ≤ 0.019 m |
| Peak heading error (safe stop 0.35 rad) | 0.191–0.195 rad | 0.195–0.234 rad | 0.152–0.187 rad |
| Stack tick, max | 38.6 ms | 38.8 ms | 41.4 ms (budget 100 ms) |

ICP error is measured per tick: the tick's ICP pose against the IPS of the same snapshot, so the scan/pose skew is included.

## 2. D66 — per-episode criteria (B gates every episode)

| | Criterion | Baseline | Basis |
| --- | --- | --- | --- |
| **U1** | **Outcome.** T1/T2: one lap, passed on the expected side, not blocked. T3: finished "blocked". | all | S4-04 behaviour |
| **U2** | No wall or obstacle contact and no off-track (independent scorer); no abort | all | plan |
| **U3** | T1/T2 obstacle clearance **≥ 0.25 m**; wall clearance **≥ 0.20 m** (all cases) | ≥ 0.35 m; ≥ 0.27 m | margin about 0.1 m; wall as S3 T6 |
| **U4** | T3 at rest **≥ 1.0 m** from the barrier | ≥ 1.44 m | D58 sets ≥ 0.30 m. Without the D61 mask, ICP fails inside about 0.93 m of a full blockage, so 1.0 m keeps the stop where the localization evidence holds. |
| **U5** | ICP valid on every driving tick; per-tick error p95 **≤ 0.05 m**, max **≤ 0.15 m** | ≤ 0.024 / ≤ 0.073 m | p95 as S3 T2. The max is wider than S3's time-matched 0.10 m, because the per-tick measure includes the skew (0.122 m at a hard stop in §18). |
| **U6** | T1/T2 lap (whole-run basis) **≤ 72 s** | 68.3–69.0 s | about +3 s, as S3 T7 |
| **U7** | Stack tick max **≤ 80 ms**; no tick overruns | ≤ 41.4 ms | 100 ms tick |

**Reported, not gated:** peak heading error (the 0.35 rad safe stop itself enforces it through U1), swerve, latch distance and speed, and the costs per module.

## 3. D67 — matrix and F4

- **30 episodes:** T1, T2, T3 × 10, in **three sessions of 10**, each interleaved T1 T2 T3. Every episode is a fresh process. About 45 minutes per session.
- **F4 × 3 each** (F4-1, F4-2, F4-3) in a separate session, with the §11 criteria unchanged: rest ≤ 1.7 s and travel ≤ 0.65 m from the injection, the expected detection, no positive throttle afterwards, no contact.
- **Rearm:** demonstrated in §15 (S4-04); not repeated in the matrix.

## 4. D68 — failure rule

**Strict**, as D52 in S3:
- any episode failing U1–U7, or any F4 run failing its criteria, fails the matrix item;
- failures are retained, and a rerun happens only with your approval;
- runs continue past a failure, and a session stops only on infrastructure (a grabbed desktop or a left player).
