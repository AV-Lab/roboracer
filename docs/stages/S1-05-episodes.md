# S1-05 — Single-episode runner, independent scoring and manifest (non-motion part)

Date: **2026-10-06**. Evidence: `artifacts/s1/20261006T051902Z-s1-05/` (27-file manifest). Request: "go on with S1-05". **No motion was run.** Laps need the [M6 lap proposal](../planning/s1-05-lap-proposal.md), which awaits confirmation.

Plan item: *Deliver the parameterized single-episode runner, independent lap/contact/off-track bookkeeping and manifest export. Record initial-state setup, including any manual step; do not call it unattended reset.*

## Delivered

| Part | Where | What it does |
| --- | --- | --- |
| C0 reference geometry | `scripts/roboracer_scoring.py geometry` | Built from the player's own serialized colliders (sha identical to the SIM1-02 export). Walls = the plan-view union of every Proto Track triangle. Drivable region = the ring between the two barriers. Centerline 31.33 m, track width 1.14–2.55 m. Vehicle footprint from the vehicle's colliders about the rear axle: x −0.101..0.425 m, y −0.145..0.143 m. |
| Independent scorer | `roboracer_scoring.py score` | Uses only simulator truth (the runner's own bridge child, IPS + IMU per telemetry frame, simulation time) and the geometry; it never reads the stack. Laps: cumulative centerline progress ≥ k·L with the 25/50/75 % gates passed in order, so oscillating across the line cannot count. Contact: the swept footprint between frames touches a wall. Off-track: the swept footprint leaves the region. Events are de-duplicated with start, end and duration. Also reports min clearance and the largest single-frame progress step (an audit value). |
| Plot | `roboracer_scoring.py plot` | Walls drawn with their holes (fixes the earlier fill), centerline, gates, spawn and an optional trajectory. |
| Single-episode entrypoint | `scripts/roboracer_episode.py` | `live`: one fresh-process episode on an approved AVLite stage (only m4/m5 today), through the existing runner. `recorded`: re-scores an existing results directory. Both write the same `episode.json` (`roboracer.episode/1`), plus `score.json` and `manifest.json`. The outcome (finished, aborted or incomplete, with the reason) is taken from what the stack recorded, never inferred from the score. |
| Manifest | `manifest.json` (`roboracer.episode-manifest/1`) | Code identities and dirty paths (roboracer, AVLite) and tool hashes, including the runner's hash at run time. Player and `GameAssembly.so` hashes checked against the build record. Configuration and environment overrides, the approval record hash, scene geometry hashes and spawn. Start conditions (first truth frame, offset from spawn, workspace precheck). **Initialization:** fresh player at the scene spawn; a person reviews the pre-Connect screenshot; then one scripted Connect click, recorded as a manual step with the review note and screenshot hash, and `unattended_reset: false`. Also: no randomization, the clock domains, truth provenance, child processes with exit codes and cleanup, and host/GPU/display. |

## Qualification

- **Tests:** 106 script tests (12 new) and 41 plugin tests (2 new) pass.
- **Scorer fixtures:** analytical ring tests cover a full lap timed to one frame, oscillation across the line, a reverse lap, 1.5 laps counting once, one de-duplicated wall-contact event with its duration, and a crossing caught only by the swept footprint.
- **Recorded episodes:**

| Episode | Outcome (from the stack) | Progress | Contact / off-track | Min footprint clearance |
| --- | --- | --- | --- | --- |
| M5 trial 1 | finished: distance | 6.06 m | none / none | 0.123 m |
| M4 trial 5 | finished: schedule complete | 2.26 m | none / none | 0.384 m |

- Both manifests show the player and `GameAssembly.so` matching the SIM1-03 build record, and the runner's hash equal to its hash at run time.

## Finding for laps (offline, no motion)

A 2-D LiDAR rollout (`scripts/roboracer_rollout.py`) uses the measured plant and the stack's abort rules. Its simulated scan matches recorded M5 scans to a p95 of 7.9 mm across the full scan and within 4 mm on the side sectors. Over a full C0 lap:
- **A** completes the loop but brings the footprint within **6–11 mm** of a wall at the hairpins.
- The proposed **A-lap** (centering plus a side-clearance speed cap) keeps **0.105 m** with the same 0.35 rad and 0.3 m/s limits. Its result does not change with 0.25–0.6 s of latency.

The [M6 proposal](../planning/s1-05-lap-proposal.md) asks you to confirm D9–D11.

## Status

- The non-motion S1-05 deliverables are complete and qualified on recorded inputs.
- **Update (same day):** M6 was confirmed and run through the live entrypoint. All 3 trials completed one lap with no contact or off-track ([M6 report](S1-M6-lap.md)).
- I am not ticking S1-05; it awaits your review.
