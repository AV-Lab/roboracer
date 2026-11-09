# RoboRacer AVLite plugin

Community plugin that lets AVLite drive the source-built AutoDRIVE F1TENTH simulator.

**Status: release 1 (S5).** The release profile is stage `s4`: the A2RL racing-line stack on map ICP at 0.5 m/s, with static-obstacle detection and avoidance on the C0 track. Versions, launch, reset, calibration and limitations are in the operations guide, [`../release/README.md`](../release/README.md). Qualification evidence is in [`../docs/stages/S5.md`](../docs/stages/S5.md).

Importing the package never starts a simulator, socket, ROS node, thread or process.

## Exports

| Class | AVLite role | What it does |
| --- | --- | --- |
| `AutoDriveBridge` | world bridge | Reads the provenance-enabled Devkit topics and serves checked snapshots (LiDAR, IMU, wheel odometry). It withholds simulator truth when the stage asks it to, can add virtual obstacles to the scans (a fixture, D54), and sends `TargetSpeedSteeringCommand`s to the supervisor. It refuses stock Ackermann commands. |
| `MapIcpLocalization` | localization | Extends AVLite's `LidarLocalization`: its point-to-point ICP of each scan against the committed map `data/c0-icp-map.json` (hash-checked), with KD-tree correspondences, initialization by configuration only, a start-up check, validity gating and an obstacle mask (D61). |
| `ScanObstacleDetection` | perception | Wall-map subtraction and AVLite FastBEV clustering. An obstacle is confirmed after 2 scans. |
| `RaceLineGlobalPlanner` | global planner | The committed racing line (`data/c0-s3v1-plan.json`, the V1 profile). |
| `C0LatticePlanner` | local planner | AVLite's `GreedyLatticePlanner` at C0 scale. Additions: a latched blocked stop (D58, gated, with a stop-distance guard), early avoidance, AVLite's overtake mode off, and map-derived bounds (`data/c0-lattice-bounds.json`) (D78–D79). |
| `RacingLineController` | controller | The A2RL racing-line tracking (lateral MPC, speed profile), in mode `selected` on the lattice plan. Safe stop on a yaw error > 0.35 rad (D65). |
| `HoldController` | controller | Always requests a standstill (safe default, command-path probe). |
| `SpeedStepController`, `GapFollowController` | controllers | Calibration and S1/S2 tools. Not part of the release profile. |
| `TargetSpeedSteeringCommand` | command | Target speed [m/s, ≥ 0] and front steering angle [rad, positive left], stamped on the monotonic clock. |
| `PluginSettings` | settings | Validated: loopback host and port, request life (at most 1 s), speed limit, steering limit (at most 30°). AVLite saves them to `plugin_roboracer.yaml` in its config directory. |

## Supervisor and guard

Every command passes through a separate supervisor process (`roboracer/runtime/supervisor_process.py`, protocol `roboracer.supervisor/1`) and then the guard built into the player.
- **Supervisor:** needs runner heartbeats (500 ms lease; inhibition is sticky). It rejects stale requests and observations, and bounds the normalized throttle and steering to the stage's profile.
- **Motion gate:** motion is allowed only for a stage in the approval record (`docs/planning/s1-motion-approval.json`). The gate cannot be opened in code.

## Data files

| File | Content | Provenance |
| --- | --- | --- |
| `data/c0-s3v1-plan.json` | V1 racing line and speed profile. Its `LeftBound`/`RightBound` are inaccurate in places and are not used by the lattice. | `.provenance.json` beside it |
| `data/c0-icp-map.json` | C0 wall map for ICP and wall subtraction | `.provenance.json` |
| `data/c0-lattice-bounds.json` | Lattice track bounds from the C0 map (D79) | `.provenance.json`; builder `scripts/roboracer_s5_lattice_bounds.py` |

## Register

```yaml
c69_apps:
  c62_community_plugins:
    roboracer: /path/to/this/repository/roboracer
```

**Requirements:**
- AVLite 0.6.3 (commit `50dcd00`).
- ROS 2 Humble, sourced, for `AutoDriveBridge.connect()`. Loading the plugin does not need ROS.
- The pinned environment is built by `scripts/roboracer_s5_env.py` (see the operations guide).
- Live runs go through the stage runner (`scripts/roboracer.py live`). AVLite's visualizer is for configuration only (D76).

## Tests

```bash
<avlite-venv>/bin/python -B -m unittest discover -s roboracer/tests -t .
<avlite-venv>/bin/python -B -m unittest discover -s scripts/tests
```

Each plugin test case runs in a fresh process with isolated AVLite and XDG directories.
