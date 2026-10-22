# S3 speed proposal — raising B above 0.3 m/s (D33), first step V1

Version **0.1 — proposed 2026-10-22**, for confirmation. Basis:
- D33, "faster is better": lap time is an S3 objective, and speed rises in stages, each with its own evidence and run approval.
- The first B laps at 0.3 m/s: 3/3 clean, 108.7–108.8 s, [S3 §5](../stages/S3.md).

**Nothing here authorizes motion.** Decisions D35–D38 are requested in §5.

## 1. What limits speed today, and what is known

| Item | Today (M6 / s3b envelope) | Known from evidence |
| --- | --- | --- |
| Speed cap | 0.3 m/s target; aborts at 0.5 m/s encoder speed | B's laps peak at 0.351 m/s (speed-loop overshoot; A's peak 0.340 m/s) |
| Throttle | normalized ≤ 0.07 (`u_max`), feedforward v/K plus a bounded integral trim, rise ≤ 0.10 per second | K = 5.02 m/s per unit, **identified only up to 0.30 m/s** (S1 M3b) |
| Braking | zero throttle is a hard brake (85.6 N·m per wheel, D1) | stops in about one frame, braking distance ≈ 0.19 s × speed (S1 M3) |
| Fault stops | the frozen S1 criteria: ≤ 1.5 s and ≤ 0.40 m from fault onset | measured at 0.3 m/s: 0.35–1.33 s and 0.04–0.31 m (F1, F2); the slowest is runner loss (F1-7: inhibit at the 0.5 s runner lease, then guard expiry), whose 0.31 m equals about 1.03 s × speed |
| Pose | IPS (bring-up, D32 A), a new pose every ~0.18 s, up to 0.345 s old | the no-motion check (S3 §3) shows B tracking up to 2 m/s with the A2RL MPC |
| Track | C0: opening straight 7.6 m (s = 0.5–8.1 m); tightest radius 1.38 m; B's line keeps ≥ 0.31 m from the walls | |

**The binding constraint is a fault stop in a corner, not tracking.**
- After a fault, the guard lease expires (detection up to ~0.6 s), then the brake acts (~0.2 s). Steering returns to 0 with the lease, so the car runs straight while it stops.
- The worst-case travel is taken as 1.3 s × v (F1-7 measured about 1.03 s × v), and the drift from a curve of radius R is about d²/(2R):

| Cap | Worst-case fault travel (1.3 s × v) | Drift in the tightest corner (R 1.38 m) | Against B's 0.31 m clearance |
| --- | --- | --- | --- |
| 0.3 m/s | 0.39 m | 0.06 m | inside |
| **0.5 m/s** | **0.65 m** | **0.15 m** | **inside, with margin** |
| 0.75 m/s | 0.98 m | 0.35 m | at the wall |
| 1.0 m/s | 1.30 m | 0.61 m | contact possible |

So the first step is **0.5 m/s everywhere**. Steps above it need either measured shorter stops or corner speeds limited by the profile (fast straights, slower corners). That is decided after V1, from V1's measured stops.

## 2. Step V1: 0.5 m/s

**Envelope for stage `s3v1`.** Only the speed-related limits change; everything else is unchanged from M6/s3b.

| Limit | M6 / s3b | V1 |
| --- | --- | --- |
| Target speed cap (controller and supervisor) | 0.3 m/s | **0.5 m/s** |
| Throttle `u_max` | 0.07 | **0.12** (≈ 0.6 m/s at K = 5.02; final value from the identification) |
| Overspeed: supervisor inhibit and stage abort | 0.5 m/s | **0.7 m/s** |
| Steering | ≤ 0.35 rad | unchanged (B's laps peak at 0.256 rad) |
| Containment box, lap distance, stale/lost feedback, workspace precheck, guard | as M6 | unchanged |
| Velocity profile | flat 0.3 (curvature limits are above it) | flat 0.5. The corner limit at 3 m/s² grip is 2.0 m/s, so corners are not slowed at V1. |

**Predicted lap** (no-motion check): about 62 s, against 108.7 s at 0.3 m/s.

## 3. V1 run set (one approval)

1. **Speed identification (no steering, opening straight).**
   - Like S1 M3b: straight-line throttle holds at 0.08, 0.10 and 0.12. Each hold ends at the target speed, 2.0 s or 2.5 m of travel, then zero throttle brakes.
   - Three trials, fresh process each.
   - Measures K above 0.3 m/s (linearity), settling, and braking distance from up to 0.6 m/s.
   - **The final `u_max` is set from this** (K × u_max ≈ 0.6 m/s).
2. **Fault stops at V1**, B driving on `s3v1`, injected on the opening straight (6.0 s run time, about 2.5 m in):
   - F1-3 (algorithm hang → guard lease expiry) ×3;
   - F1-7 (runner heartbeats paused → supervisor inhibit) ×3.
3. **B laps at V1:** three fresh-process single episodes on `s3v1`, IPS pose (bring-up label), automated pre-Connect check.

**Pass criteria (V1):**

| Part | Criterion |
| --- | --- |
| Identification | steady speed linear in throttle within ±10 % of one fitted K; settling within 0.5 s; braking distance ≤ 0.25 s × speed |
| Fault stops | rest ≤ 1.5 s and travel ≤ **0.65 m** (1.3 s × 0.5 m/s; F1-7 is expected at about 0.52 m) from fault onset; nothing applied after the stop; no contact |
| B laps | one lap each, no contact or off-track (independent scorer), no abort, no safe stop, minimum clearance ≥ 0.20 m |

Any failure fails the step. It is retained, and a rerun needs approval.

## 4. After V1

- **Proposal V2** with corner-limited speed: the profile's lateral limit is chosen so a fault stop in any corner stays inside the clearance, using V1's measured stop time. Straights could then run 1 m/s or more.
- **ICP (S3-01/02)** can be developed in parallel without motion. S3 results need it.
- **The frozen S1 stop criteria still apply to M6 and s3b** and are not changed retroactively. V1's criteria apply to V1 only.

## 5. Decisions requested

- **D35 — first speed step: V1 = 0.5 m/s everywhere** (recommended).
  - Alternative: 0.75 m/s. Its worst-case corner fault drift (0.35 m) reaches B's 0.31 m clearance, so I do not recommend it before stops at speed are measured.
- **D36 — V1 envelope as in §2:**
  - cap 0.5 m/s;
  - `u_max` 0.12, final value from the identification;
  - overspeed 0.7 m/s;
  - all other limits unchanged.
- **D37 — V1 stop criteria:** rest ≤ 1.5 s and travel ≤ 0.65 m from fault onset (scaled as 1.3 s × the cap, not below the S1 0.40 m).
- **D38 — V1 run set as in §3:** identification ×3, F1-3 ×3, F1-7 ×3, B laps ×3.

**A single reply can confirm D35–D38 and approve the V1 run set** ("approve D35–D38 and the V1 runs"). I would then implement stage `s3v1` and the identification holds, test them without motion, and run the set in order, stopping at the first failure.
