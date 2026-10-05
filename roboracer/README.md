# RoboRacer AVLite plugin

Community plugin for RoboRacer development with AVLite and the source-built AutoDRIVE F1TENTH simulator. **Status: S1-02 observation path.** The plugin loads, registers and validates its settings. On `connect()` the bridge reads the provenance-enabled Devkit topics and serves checked observation snapshots. It drives nothing.

## Exports

| Class | Role |
| --- | --- |
| `TargetSpeedSteeringCommand` | The approved command: target speed [m/s, ≥ 0] and front steering angle [rad, positive left], plus its generation time on the monotonic clock. It is a `ControlCommandBase` subclass, not a relabelled Ackermann acceleration. |
| `AutoDriveBridge` | World bridge for the guarded SIM1-02 AutoDRIVE player. Construction has no side effects. `connect()` starts a private rclpy subscription thread; `close()` stops it. Advertises `LIDAR_2D` and `IMU`, plus `LOCALIZATION` from labelled simulator truth only with `gt_localization` on. Each telemetry frame becomes one snapshot only when every member matches the frame's provenance (see `integration/autodrive_observation.py`). Commands are validated, never sent: it accepts only valid `TargetSpeedSteeringCommand`s and refuses stock Ackermann commands, including the GUI's manual buttons. |
| `HoldController` | Always requests a standstill. It is the safe default and command-path probe, and needs no plan or localization. |
| `PluginSettings` | Validated settings: loopback host, port, request life (at most the guard's 1 s), speed limit (0 until the motion protocol is confirmed), steering limit (at most 30°) and `gt_localization` (off by default). |

## Register (development checkout)

```yaml
c69_apps:
  c62_community_plugins:
    roboracer: /path/to/this/repository/roboracer
```

Importing the package never starts a simulator, socket, ROS node, thread or process.

## Known consumer behavior

- **Executor:** AVLite runs control and actuation only when the stack or world provides `LOCALIZATION`. `AutoDriveBridge` provides it only with `gt_localization` on, so by default a stack built on it never actuates.
- **Observation:** body origin is the rear-axle centre (the reported IPS point). LiDAR mount (0.2733, 0, 0.096) m, IMU mount (0.08, 0, 0.055) m. Sensor stamps are acquisition times on the host `CLOCK_MONOTONIC`. The IMU reports no gravity. `EgoState.velocity` is not observed by the bridge and is left unchanged.
- **Visualizer gauges:** the gauges read `controller.cmd`. `HoldController` mirrors its steering there and shows zero acceleration, because none is commanded.
- **Headless dashboard:** it reads the command's `acceleration` with a default, so it shows 0.0.
- **BasicSim:** it integrates acceleration and raises `AttributeError` on the plugin command. Use `AutoDriveBridge`.

## Tests

Run with the AVLite interpreter (each case runs in a fresh process with isolated AVLite/XDG directories):

```bash
<avlite-venv>/bin/python -B -m unittest discover -s roboracer/tests -t .
```
