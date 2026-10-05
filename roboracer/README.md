# RoboRacer AVLite plugin

Community plugin for RoboRacer development with AVLite and the source-built AutoDRIVE F1TENTH simulator. **Status: S1-01.** The plugin loads, registers and validates its settings. It does not connect to a simulator yet and drives nothing.

## Exports

| Class | Role |
| --- | --- |
| `TargetSpeedSteeringCommand` | The approved command: target speed [m/s, ≥ 0] and front steering angle [rad, positive left], plus its generation time on the monotonic clock. It is a `ControlCommandBase` subclass, not a relabelled Ackermann acceleration. |
| `AutoDriveBridge` | World bridge for the guarded SIM1-02 AutoDRIVE player. In S1-01 it is disconnected and advertises no sensors. It accepts only valid `TargetSpeedSteeringCommand`s and refuses stock Ackermann commands, including the GUI's manual buttons. |
| `HoldController` | Always requests a standstill. It is the safe default and command-path probe, and needs no plan or localization. |
| `PluginSettings` | Validated settings: loopback host, port, request life (at most the guard's 1 s), speed limit (0 until the motion protocol is confirmed) and steering limit (at most 30°). |

## Register (development checkout)

```yaml
c69_apps:
  c62_community_plugins:
    roboracer: /path/to/this/repository/roboracer
```

Importing the package never starts a simulator, socket, ROS node, thread or process.

## Known consumer behavior

- **Executor:** AVLite runs control and actuation only when the stack or world provides `LOCALIZATION`. `AutoDriveBridge` provides none yet, so a stack built on it never actuates.
- **Visualizer gauges:** the gauges read `controller.cmd`. `HoldController` mirrors its steering there and shows zero acceleration, because none is commanded.
- **Headless dashboard:** it reads the command's `acceleration` with a default, so it shows 0.0.
- **BasicSim:** it integrates acceleration and raises `AttributeError` on the plugin command. Use `AutoDriveBridge`.

## Tests

Run with the AVLite interpreter (each case runs in a fresh process with isolated AVLite/XDG directories):

```bash
<avlite-venv>/bin/python -B -m unittest discover -s roboracer/tests -t .
```
