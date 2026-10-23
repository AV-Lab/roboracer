# S3 speed proposal V2 — 1.0 m/s straights with fault-bounded corners

Version **0.1 — proposed 2026-10-23**, for confirmation. Basis:
- D33, "faster is better";
- V1 passed: 0.5 m/s laps in 67.4–67.7 s, [S3 §6–7](../stages/S3.md);
- the user's "go for my call" to proceed with the speed proposal.

**Nothing here authorizes motion.** Decisions D40–D43 are requested in §5.

## 1. What limits the next step (from V1's measurements)

- **The fault stop, not tracking.** B tracked as tightly at 0.5 m/s as at 0.3 m/s (lateral p95 0.046 m).
- **Runner loss (F1-7) is the longest stop:** 1.27–1.51 s and 0.49–0.54 m at 0.5 m/s, i.e. about **1.08 s × speed** of straight-line travel. Steering returns to 0 when the guard lease expires.
- **Corner drift:** a straight run of d = k·v from a curve of radius R drifts about d²/(2R). Capping the drift at δ gives **v²/R ≤ 2δ/k²**, a lateral-acceleration limit. A2RL's friction-limited velocity profile already has that parameter (`lateral_accel_mps2`), so one setting bounds the fault drift in every corner at once.
- With k = 1.3 s (V1's travel allowance) and δ = 0.20 m (B keeps 0.31 m footprint clearance), that is **0.24 m/s²**. Corners stay near today's speed (tightest radius 1.38 m: 0.58 m/s), while straights can go faster.

**Geometric check** (`scripts/roboracer_s3_fault_envelope.py`, no motion): from every point of a plan, the car's footprint is swept straight ahead for 1.3 s × the target speed there, and its smallest clearance to the walls is recorded.

| Profile | Straight cap | Fault-sweep clearance | Passes (≥ 0.05 m) | Profile lap estimate |
| --- | --- | --- | --- | --- |
| flat (today's V1) | 0.5 m/s | 0.227 m | yes | 62.3 s |
| corners unlimited (3 m/s²) | 0.75 m/s | 0.059 m | barely | 41.5 s |
| corners unlimited (3 m/s²) | 1.0 m/s | **−0.02 m (into the wall)** | no | 31.1 s |
| **corners 0.24 m/s²** | **1.0 m/s** | **0.120 m** | **yes** | **38.1 s** |
| corners 0.24 m/s² | 1.5 m/s | 0.119 m | yes | 34.3 s |

**Closed-loop kinematic check** (measured timing, worst pose age 0.345 s, MPC applied, 0.5 m/s² acceleration as the supervisor's throttle rise allows):

| Profile | Flying lap | Clearance | Notes |
| --- | --- | --- | --- |
| 0.5 m/s flat | 62.1 s | 0.315 m | the real V1 laps took 67.5 s, about 9 % slower than this model |
| **1.0 m/s straights, corners 0.24 m/s²** | **37.8 s** (≈ 41 s real) | 0.313 m | no safe stop |
| 1.5 m/s straights, corners 0.24 m/s² | 33.7 s | 0.314 m | small gain: the corners dominate |

**Recommendation: V2 = 1.0 m/s on straights, corners limited by the fault-drift bound.**
- It saves about 26 s per lap against V1.
- 1.5 m/s would add only about 4 s, and would first need throttle identification up to about 1.8 m/s, which the 7.6 m opening straight cannot hold.

## 2. Step V2 (stage `s3v2`)

| Limit | V1 (`s3v1`) | V2 |
| --- | --- | --- |
| Straight speed cap | 0.5 m/s | **1.0 m/s** |
| Corner speed | flat 0.5 m/s | **profile lateral limit 0.24 m/s²** (fault drift ≤ 0.20 m); profile acceleration 0.5 m/s², braking 2.0 m/s² |
| Plan gate | — | **the committed plan must pass the fault sweep** (≥ 0.05 m at 1.3 s × speed); the builder refuses it otherwise |
| Throttle `u_max` | 0.12 | **0.24** (≈ 1.2 m/s at K = 5.03; final value from the identification) |
| Overspeed: supervisor inhibit and stage abort | 0.7 m/s | **1.2 m/s** |
| Steering, containment, lap distance, feedback rules, precheck, guard | as M6 | unchanged |

## 3. V2 run set (one approval; stops at the first failure)

1. **M3d identification ×3** (no steering, opening straight), as M3c with holds at throttle 0.16, 0.20 and 0.24 (≈ 0.8 / 1.0 / 1.2 m/s).
   - Each hold ends at 1.25 m/s, 2.0 s or 1.6 m of travel. Abort caps: 1.35 m/s and 2.0 m per hold, 6.0 m per trial.
   - Gate: K × 0.24 between 1.1 and 1.3 m/s.
2. **Fault stops on `s3v2`:** F1-3 ×3 and F1-7 ×3, injected on the opening straight (6.0 s run time, by then at about 1.0 m/s).
3. **B laps ×3 on `s3v2`:** IPS pose (bring-up label), automated pre-Connect check.

**Pass criteria (V2):**

| Part | Criterion |
| --- | --- |
| Identification | steady speed linear within ±10 % of the median K; settling ≤ 0.5 s; braking ≤ 0.25 s × speed |
| Fault stops | travel ≤ **1.3 m** (1.3 s × 1.0 m/s); rest ≤ **2.0 s** = 1.7 s (D39 B) + the extra braking from 1.0 instead of 0.5 m/s at the measured ~1.6 m/s² (M3c: 0.11 m from 0.60 m/s); nothing applied after the stop; no contact |
| B laps | one lap each, no contact or off-track, no abort, no safe stop, minimum clearance ≥ 0.20 m |

Any failure fails the step. It is retained, and a rerun needs approval.

**Not covered by a run:** a fault mid-corner. The fault sweep covers it geometrically for every plan point. Injecting faults in corners is a separate test that could be added later if you want it.

## 4. Later levers (not proposed now)

- **Shorter detection chain:** for example a 0.3 s runner lease (D28 already decouples heartbeats from loop stalls). This cuts k from about 1.08 to about 0.9 s and allows faster corners for the same drift.
- **ICP (S3-01/02)** remains required before any lap counts as an S3 result.

## 5. Decisions requested

- **D40 — V2 speed shape:** straights 1.0 m/s; corners limited by the fault-drift bound (lateral 0.24 m/s² for δ = 0.20 m, k = 1.3 s); the plan must pass the fault sweep.
- **D41 — V2 envelope (`s3v2`):** `u_max` 0.24 (final from the identification); overspeed 1.2 m/s; all other limits unchanged.
- **D42 — V2 stop criteria:** travel ≤ 1.3 m; rest ≤ 2.0 s.
- **D43 — V2 run set:** M3d ×3, F1-3 ×3 and F1-7 ×3 on `s3v2`, B laps ×3.

**A single reply can confirm all four and approve the run set** (for example "confirm D40–D43 and run V2"). I would then build `s3v2`, M3d and the sweep gate, test them without motion, and run the set.
