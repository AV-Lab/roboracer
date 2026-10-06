# Autonomous stack overview — what AVLite runs, what the roboracer plugin provides

Status as of **2026-10-06** (S1-06, M1 in progress). [Chinese version](stack-overview.zh-CN.md). This page describes the stack used in the M4–M6 runs, the D13 timing laps and the F1 fault cases. It was checked against the AVLite source (`avlite/c60_apps/c62_factory.py`, `avlite/c40_execution/c44_sync_executer.py`, `avlite/c40_execution/c42_execution_strategy.py`) and the recorded runs.

**Short answer.** AVLite really runs, as the framework: its plugin loader, `executor_factory`, the `SyncExecuter` 10 Hz tick loop, and its interfaces and data model. **No AVLite algorithm runs.** Perception, localization, mapping and planning are not instantiated, and the controller is the plugin's. All driving logic is roboracer plugin code. The supervisor is plugin code in a separate process; the guard lives in the simulator.

## 1. Data and command path

```
AutoDRIVE simulator (Unity player, with roboracer vendor patches: provenance, guard, D1)
   │  telemetry ~5.8 Hz: LiDAR, IMU, encoders, IPS pose, plus provenance stamps
   ▼
Devkit bridge process (AutoDRIVE Python Devkit, run by our runner as its own child)
   │  ROS 2 topics; carries the guard's commands back in the paced replies
   ▼
AVLite stack process
   ├─ AVLite  : plugin loader → executor_factory → SyncExecuter.step()   (10 Hz)
   ├─ plugin  : AutoDriveBridge      (an AVLite WorldBridge)      ROS topics → one sensor snapshot per tick
   └─ plugin  : GapFollowController  (an AVLite ControlStrategy)  LiDAR → target speed + steering
   │  request {target speed, steering, the observation it was computed from}   (abstract Unix socket)
   ▼
Supervisor process (plugin code, roboracer.runtime): checks + speed loop → normalized throttle/steering
   ▼
Guard (C# inside the simulator, roboracer patch): arming epoch, lease ≤ 1 s, limits → wheels
```

## 2. What comes from AVLite (`/home/a2rl/avlite`)

| Component | What it does in our runs |
| --- | --- |
| Plugin system | Loads `roboracer` as a community plugin (`AppSettings.c62_community_plugins`, `executor_factory(load_plugins=True)`), the same path the AVLite app uses. |
| `executor_factory` | Builds the stack from registered names. We pass `executer_type="SyncExecuter"`, `bridge="AutoDriveBridge"` and `controller_strategy_name="GapFollowController"`, plus `HoldController` / `SpeedStepController` in earlier stages. Perception, localization, mapping, global planner and local planner are given empty names, so the factory creates none of them. |
| `SyncExecuter.step()` | AVLite's tick. Each tick it: (1) takes one sensor frame from the bridge (`get_sensor_frame()`); (2) copies the ground-truth pose into its ego state, because the bridge declares `StackCapability.LOCALIZATION`; (3) calls `controller.control(ego, plan, sensors=...)` (`_control_step`); (4) applies the held command through `world.control_ego_state()` (`_simulate_step`, zero-order hold every tick). |
| Interfaces and data model | `WorldBridge`, `ControlStrategy`, `ControlCommand`, `EgoState`, `PerceptionModel` and the capability flags (`WorldCapability.LIDAR_2D`, `StackCapability.LOCALIZATION`). The plugin implements these. |

## 3. What comes from the roboracer plugin (`roboracer/`)

| Component | Source | Role |
| --- | --- | --- |
| `AutoDriveBridge` | `roboracer/integration/autodrive_bridge.py` | The AVLite world bridge for AutoDRIVE. It subscribes to the Devkit's ROS 2 topics and computes encoder speed. It sends each request to the supervisor, tagged with the observation it used, and refuses any command type other than `TargetSpeedSteeringCommand`. |
| `SnapshotAssembler` | `roboracer/integration/autodrive_observation.py` | Builds one consistent snapshot per telemetry frame: scan, IMU, encoders and pose with matching acquisition provenance. It rejects stale, malformed or inconsistent frames (session, sequence, scan layout, non-finite readings, scan/pose skew). |
| `GapFollowController` (A; A-lap with `LAP_PARAMS`) | `roboracer/control/gap_follow.py` | **The only driving algorithm.** Follow-the-gap with disparity extension, using the LiDAR only; it never reads the pose or a map. A-lap (M6, M1) adds centering and a side-clearance speed cap. |
| `SpeedStepController`, `HoldController` | `roboracer/control/` | Test controllers for M4 (scripted speed steps) and the zero-command stages. |
| `TargetSpeedSteeringCommand` | `roboracer/runtime/commands.py` | The approved command type, with its own validation (finite values, limits, generation stamp). |
| Supervisor | `roboracer/runtime/supervisor_core.py`, `supervisor_process.py` | A separate process. It checks origin, sequence, request life (500 ms), observation age (500 ms) and the runner lease (500 ms). It runs the D5 speed loop (target speed → throttle, its own encoder-feedback subscription, stale/lost feedback cut-offs) and converts steering exactly. |

## 4. Not plugin code

| Component | Source | Role |
| --- | --- | --- |
| Guard | `integration/autodrive/sim1/RoboRacer/GuardCore.cs` (in the player) | The last authority before actuation: arming epoch, origin, sequence, lease, clock bound and limits. On expiry or disarm it brakes with zero throttle. |
| Runner and stage scripts | `scripts/autodrive_neutral.py` | The test harness. It owns the processes, the pre-Connect review and the stage schedules. Its abort monitors are the only users of the ground-truth pose. |
| Scorer and measurement tools | `scripts/roboracer_scoring.py`, `roboracer_episode.py`, `roboracer_timing.py`, `roboracer_f1.py` | Independent evaluation: laps, contact and off-track from simulator truth; timing and resources; the F1 fault checks. |

## 5. Evidence that AVLite executes (not only imports)

- **Loaded from AVLite's environment.** The stack status records `avlite/__init__.py` from the AVLite environment and the plugin loaded from `roboracer/`.
- **Every request is generated inside its tick.** All supervisor requests (1,446 in an M6 lap) were generated inside `SyncExecuter.step()`. The tick period is 100.0 ms (p95 100.4 ms) and tick → request takes about 1 ms ([S1-06 measurements](../stages/S1-06-measurements.md)).
- **Its hold behaviour shows.** AVLite re-applies the held command every tick. The bridge counts these repeats as `held_resend` and does not resend them, matching `_simulate_step`.
- **The ego state is labelled ground truth,** through the `LOCALIZATION` capability. A-lap never reads it.

## 6. Limits of what has been exercised

- **AVLite algorithms:** none of its perception, localization, mapping, planning or control has been used yet.
- **AVLite app and GUI:** not running. The stack process (`plugin_observe` in `scripts/autodrive_neutral.py`) builds the executer through AVLite's own factory, then calls `executer.step()` every 100 ms itself. That is AVLite's headless execution path, not the AVLite application.
- **Speed setting:** the 0.3 m/s target-speed limit is set only inside the stack process during an approved stage; the shipped plugin default is 0.
- **Later work:** running under the AVLite app, and replacing ground-truth localization or gap-follow with AVLite or other modules. This is later-stage work (the A/B stack stage, M3 in the plan).
