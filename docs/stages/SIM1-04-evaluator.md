# SIM1-04 — Evaluator-only truth, geometry, contact and progress fixtures

Date: **2026-10-08**. Request: "go on with SIM1-04". **No motion and no simulator change** (the simulator is frozen at patch 04, D18). Evidence: `artifacts/s1/20261008T-sim1-04-fixtures/`.

SIM1-04 item: *Deliver evaluator-only truth, contact and geometry inputs plus validated C0 frame/footprint/progress fixtures; document allowed driving observations separately. Do not use GUI lap count as authority.*

## Delivered

| Part | Where |
| --- | --- |
| Allowed driving observations vs evaluator-only inputs; GUI lap and collision counters not authoritative | [`docs/architecture/evaluator-interface.md`](../architecture/evaluator-interface.md) |
| Evaluator truth (IPS position + IMU yaw, IPS acquisition simulation time) from the runner's own bridge child, **per episode**: frames from different episodes are never mixed, and an IPS sample from another episode is refused | `roboracer_scoring.truth_frames(run, episode)`, `run_episodes()`; the score reports its episode |
| C0 geometry (walls, region, centerline, gates, spawn) and vehicle footprint, both from the player's own colliders | `roboracer_scoring.py geometry` (S1-05); unchanged on the patch-04 player (scene comparison equal) |
| Geometric contact and off-track (swept footprint), laps with ordered gates, clearance | `roboracer_scoring.score` (S1-05) |
| Fixtures on recorded runs | `scripts/roboracer_sim1_04.py` |

## Fixture results: 10 recorded clean laps, 12,608 frames, both qualified players

Runs: the M6 trials 1–3, D13 timing laps 1–5 and the video lap on the SIM1-03 player, plus the regression lap on the patch-04 player. **All checks pass in all 10.**

| Fixture | Result |
| --- | --- |
| Frame, pose and geometry: walls ray-cast from the recorded truth pose and LiDAR mount, against the per-tick LiDAR sector minima over each whole lap | Side sectors: p95 **3.7–4.4 mm**, max 16 mm. Front ±10°: p95 1.9–2.5 cm. |
| Same, against the full recorded spawn scan (1081 beams) | p95 6.9–7.6 mm |
| Spawn: first truth frame vs the geometry spawn | **0.000 m** in every run |
| Single episode per run | yes |
| Progress and laps: independent scorer | **exactly 1 lap** per run; progress 37.40–37.44 m; lap time 122.7–123.3 s; clearance 0.104–0.106 m; no contact or off-track |
| Contact on real traces: a mid-lap window of 5 frames moved towards the nearest wall by clearance **+2 cm** | **exactly one contact event** covering the window, in all 10 |
| Same, moved by clearance **−2 cm** | **no contact**, in all 10 |
| Episode truth (unit tests) | a multi-episode run is refused without selection; selection returns only that episode; a foreign-episode IPS sample is refused |

**Known limits, characterised:**
- **Front-sector outliers.** 2 of 817 frames in the regression lap (0.24 %) differ by more than 0.2 m, with a worst case of 2.3 m across all laps. Both are **grazing-incidence** beams on a distant wall: turning the predicted pose by just ±1° moves the predicted front minimum by 0.5–2.6 m, and scan and pose are acquired 20–50 ms apart while turning. The single finite-versus-no-return beam in each spawn scan is the same grazing effect. These don't affect side clearance, contact or progress.
- **Contact is geometric.** The frozen player emits no collision events, and the SIM0 contact diagnostics were a separate build. Contact is the swept plan-view footprint against the plan-view wall union: conservative, and validated analytically (S1-05 ring fixtures) and on real traces (above). No real wall contact has been driven, and none will be without a separate approval.

## Status

- **The SIM1-04 deliverables are complete**, without motion or simulator changes. The check box is left for your review.
- **Tests:** 129 script tests pass (3 new, for episode truth).
- **Remaining for S1 acceptance:**
  - SIM1-05: the concrete motion protocol (done, as the S1 motion protocol); the approved P1b cases; the original PRE-03/04 checks;
  - SIM1-06: publish the qualified backend and the PRE completion report;
  - your review of the check boxes.
