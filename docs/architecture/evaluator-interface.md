# Driving observations vs evaluator-only inputs (SIM1-04)

Status as of **2026-10-08**, on the frozen patch-04 player. This page separates what the **driving stack** may observe from what only the **evaluator** (scorer, monitors, analysis) may use. It is the "document allowed driving observations separately" part of SIM1-04. See also the [stack overview](stack-overview.md).

## 1. Allowed driving observations (AVLite stack)

Delivered by `AutoDriveBridge` as one validated snapshot per telemetry frame (`roboracer/integration/autodrive_observation.py`).

| Observation | Source | Rule |
| --- | --- | --- |
| LiDAR scan (1081 beams, ±135°) | `/autodrive/f1tenth_1/lidar` | In the LiDAR frame (mount 0.2733 m ahead of the rear axle). Rejected if stale, malformed or non-finite, or if its scan/pose skew exceeds the limit. |
| IMU (orientation, rates, acceleration) | `/autodrive/f1tenth_1/imu` | Same snapshot rules. |
| Wheel encoders | `left_encoder`, `right_encoder` | Encoder speed for the AVLite ego velocity, and in the supervisor's speed loop. |
| Acquisition provenance | `/autodrive/f1tenth_1/provenance` | Session, episode, sequence and acquisition stamps. Used only to validate and age observations, never as a driving signal. |

**Baseline A** (`GapFollowController`) uses **only the LiDAR**. The planned **controller B** (S3) may add encoders and IMU, and map-based localization from scans.

## 2. Evaluator-only inputs (never read by driving code)

| Input | Source | Used by |
| --- | --- | --- |
| Ground-truth pose: IPS position (rear-axle centre) and IMU orientation | The runner's own Devkit bridge child (`bridge-frames.jsonl`), timed by IPS acquisition simulation time, one episode at a time | Independent scorer; stage monitors (path, aborts); timing tool |
| C0 geometry: wall footprint, drivable region, centerline, gates, spawn | Built from the player's serialized colliders (`roboracer_scoring.py geometry`) | Scorer: laps, contact, off-track, clearance |
| Vehicle footprint (−0.101..0.425 m × ±0.144 m about the rear axle) | The vehicle's own colliders | Scorer: contact and clearance |
| Guard and supervisor traces | Player guard trace; supervisor trace | Stop, lease and fault checks |

- **Labelled, unused by A:** AVLite's ego state carries the ground-truth pose, labelled `ground-truth` through `StackCapability.LOCALIZATION`. Baseline A never reads it.
- **For S3:** the plan requires showing that removing ground truth doesn't change driving outputs (S3-04).
- **Episodes:** a run that spans a reset (several episodes) is scored per episode. Mixing episodes is refused, because simulation time restarts at a scene reload.

## 3. Not used as authority

- **The GUI lap counter and lap timer** (HUD "THIS LAP / LAST LAP / BEST LAP") are never read. Laps, lap times, contact and off-track come only from the independent scorer.
- **GUI collision counters** are not used either. Contact is the swept vehicle footprint intersecting the wall footprint, a geometric definition validated in SIM1-04.
- **Simulator collision events** are not available in the frozen player (D18); the SIM0 contact diagnostics were a separate diagnostic build. Contact detection is therefore geometric, and conservative: it uses the full plan-view footprint and the full plan-view wall.

## 4. Validation (SIM1-04 fixtures)

On 10 recorded clean laps (12,608 frames) from both qualified players (`scripts/roboracer_sim1_04.py`), all checks pass:
- **Frame, pose and geometry:** the walls ray-cast from the recorded truth pose and mount match the LiDAR side sectors within 4.4 mm (p95) over whole laps, and the spawn scan within 7.6 mm (p95).
- **Spawn and laps:** the spawn offset is 0 in every run; each run scores exactly one lap.
- **Contact:** positive and negative fixtures on real traces are detected correctly.

See the [SIM1-04 report](../stages/SIM1-04-evaluator.md).
