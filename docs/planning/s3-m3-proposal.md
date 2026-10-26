# S3-05 proposal — the M3 A/B baseline on ICP

Version **0.1 — proposed 2026-10-26**, for confirmation. Basis:
- the development plan's M3 row: C0, five start/heading cases × ten repetitions per configuration for acceptance, A against B on the same qualified ICP and motion-state provider, GT filters off, identical observation and actuation limits;
- S3-05: a bounded baseline first, then thresholds (S3-06), then the acceptance matrix (S3-07);
- D34 A: initial conditions reached by a scripted approach from the fixed spawn.

**Nothing here authorizes motion.** Decisions D44–D47 are requested in §5.

## 1. What is already qualified

| Item | Evidence |
| --- | --- |
| ICP (map target, extended localizer, validity and loss, start-up check) | S3 §9 (offline, 5 laps) and §12 (live: B laps 3/3 on ICP, every tick valid) |
| Truth isolation (stack sees LiDAR + wheel odometry only) | S3 §13 (bit-identical B outputs under perturbed truth) |
| B on ICP at V1 (0.5 m/s) | S3 §12: 67.6–67.8 s, clearance 0.316 m; F1-1 stops 1.0 s / 0.39 m |
| Stock against extended ICP (the plan's separately labelled fixture comparison) | S3 §9: on the same 5 recorded laps, the stock (scan-to-first-scan) ICP reaches 5.1 m median error, the extended one ≤ 15 mm. **Fixture evidence, not full-course performance.** |

## 2. The two configurations (D45)

Both use the **same stack** except the driving strategy: stage envelope V1 (0.5 m/s cap, 0.35 rad, same aborts), `MapIcpLocalization` initialized at the spawn from configuration, simulator pose filtered out, wheel odometry, the same supervisor and guard.

| | A | B |
| --- | --- | --- |
| Steering | reactive gap-follow (the approved A-lap, `LAP_PARAMS`), from the LiDAR only | A2RL lateral controller and MPC on the committed C0 line |
| Speed | A's own rule (≤ 0.3 m/s by its approved parameters) | A2RL velocity profile, capped at 0.5 m/s |
| ICP | runs; used for the scores, loss detection and the stop rules, not for steering | runs; drives the controller |

A keeps its approved parameters. Raising A to 0.5 m/s would change A, so it is not proposed. The comparison therefore also shows what B's path and speed planning buys.

## 3. Initial conditions (D44)

Five initial conditions at fifths of the lap along B's committed line, heading along the line:

| IC | s on the line | Reached by |
| --- | --- | --- |
| IC0 | 0 m (the spawn) | scene load (no approach) |
| IC1 | 6.25 m | scripted approach |
| IC2 | 12.5 m | scripted approach |
| IC3 | 18.75 m | scripted approach |
| IC4 | 25.0 m | scripted approach |

**Scripted approach** (D34 A):
1. At the start of every episode, ICP is initialized at the spawn from configuration (the same initialization policy for A and B).
2. B drives on ICP at the V1 cap to the target s and stops; the car holds 2 s.
3. The measured episode starts there with the configured algorithm.

**Recorded and checked** (by the labelled monitor and the scorer, IPS): the reached pose and its deviation from the configured pose. Tolerance: ±0.10 m position, ±5° heading. Outside it, the episode is an **initialization failure**, retained. Every approach is recorded as part of the episode's initialization provenance.

**Episode:**
- one valid full lap from the initial condition (all gates in order, measured from the IC), then the qualified stop;
- contact, off-track, detected localization loss, an unrecovered fault or the 200 s wall limit ends it as a failure;
- a detected loss needs an operator reinitialization; every episode is a fresh process, so the next one starts clean.

## 4. Baseline run set (D46) and speed (D47)

- **Baseline (S3-05):** 5 ICs × A/B × 1 repetition = **10 fresh-process episodes**, in alternating order (A B B A A B B A A B), unattended. Estimated 25–30 min.
- **Scores per episode**, all external (IPS and the independent scorer):
  - completion, lap time, contact and off-track, minimum clearance;
  - ICP position and yaw error against IPS, ICP validity and loss events, inlier and degeneracy statistics;
  - B's tracking error to the line;
  - resources.
- **Then S3-06:** propose ICP validity, localization-error, robustness and runtime thresholds from these baseline numbers, for approval before the acceptance matrix (5 ICs × 10 repetitions × A/B = 100 episodes, plus F3 ×3).
- **Speed (D47):** M3 runs at the V1 envelope (0.5 m/s), the speed qualified on ICP. V2 (1.0 m/s straights) on ICP would need its own qualification first.

## 5. Decisions requested

- **D44 — initial conditions:** five ICs at s = 0 / 6.25 / 12.5 / 18.75 / 25 m on B's line, reached by a scripted B approach on ICP from the spawn; tolerance ±0.10 m, ±5°; outside it is a retained initialization failure.
- **D45 — configurations:** A = approved A-lap gap-follow (own speed rule, ≤ 0.3 m/s) with the same ICP running for scores and stops; B = the A2RL stack on ICP; same V1 envelope and stack otherwise.
- **D46 — baseline run set:** 10 fresh-process episodes (5 ICs × A/B × 1), alternating order, scored as in §4.
- **D47 — M3 speed:** the V1 envelope (0.5 m/s).

After confirmation I would build the IC approach, the A-on-ICP stage and IC-relative lap scoring, test them without motion, and then ask for the run approval. A single reply can also approve the 10 baseline episodes, for example "confirm D44–D47 and run the baseline".
