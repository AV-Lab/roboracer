# roboracer.sim1/1 — AutoDRIVE telemetry provenance extension

Applies to the AutoDRIVE `635dbb6d` F1TENTH player built with `scripts/autodrive_build.py --sim1-patch`. It adds fields to the existing Socket.IO `Bridge` exchange. Every stock field is unchanged, and the stock Devkit ignores the new keys, so the extension is backward compatible.

Sources: [`RoboRacer/Provenance.cs`](RoboRacer/Provenance.cs) (new component) and [`vendor-sim1-01.patch`](vendor-sim1-01.patch), which adds hooks to `LIDAR`, `IPS`, `IMU`, `WheelEncoder` and `Socket`. The consumer-side validator is [`scripts/autodrive_provenance.py`](../../../scripts/autodrive_provenance.py).

## Simulator → bridge (every telemetry frame)

| Key | Meaning |
| --- | --- |
| `RR Schema` | `roboracer.sim1/1`. A consumer rejects any other value. |
| `RR Session` | 32-hex GUID generated once per player process. It must not change within a bridge connection. |
| `RR Episode` | Starts at 1 and increments on every scene load (including GUI Reset). Source sequences restart per episode. |
| `RR Telemetry Seq` | Strictly increasing per process, starting at 1. A duplicate or decrease is rejected. |
| `RR Capabilities` | Space-separated. `provenance clock-echo` always; `test-hooks` only when launched with `-roboracerTestHooks`. |
| `RR Clock` | `Stopwatch <frequency Hz>`, the simulator monotonic clock source and resolution. |
| `RR Ping Echo` | The last `RR Ping Mono` value received from the bridge, verbatim (`""` before the first). |
| `RR Ping Receipt Mono` | Simulator monotonic ns when that request was handled (main thread, `OnBridge`). |
| `RR Emit Mono` | Simulator monotonic ns immediately before `socket.Emit`. |
| `RR Test Frozen` | Comma list of currently frozen sources (empty unless test hooks are active). |
| `RR Test Hook Rejections` | Count of hook requests rejected (hooks disabled, or unknown source). |
| `V1 RR <Source> Stamp` | One per source: `LIDAR`, `IPS`, `IMU`, `Left Encoder`, `Right Encoder`, `Front Camera`. Format below. |

**Stamp format:** `seq episode step simTime monoNs monoEndNs`, in invariant culture, with `simTime` in round-trip (`R`) format.

- `seq`: per-source acquisition sequence in this episode. `0` means not yet acquired.
- `step`: fixed-step index. A hidden `ProvenanceClock` at execution order −32000 increments it before the sensors run.
- `simTime`: `Time.timeAsDouble`, which is fixed time when stamped inside `FixedUpdate`.
- `monoNs` / `monoEndNs`: the acquisition interval on the simulator monotonic clock. They are equal for instantaneous sensors, and bracket `FrameGrabber.CaptureFrame` for the camera.

**Acquisition points:**
- LIDAR: the end of `LaserScan()`, one instantaneous raycast sweep per scan period. There are no per-beam timestamps.
- IPS, IMU and encoders: the end of their `FixedUpdate`.
- Camera: capture inside telemetry emission, so every frame carries a newly captured image.

A source whose data has not been re-acquired since the previous frame is **retransmitted with its old identity**, and consumers classify it as reused.

## Bridge → simulator (optional reply fields)

| Key | Meaning |
| --- | --- |
| `RR Ping Mono` | Bridge monotonic ns, stamped immediately before the reply is sent. Digits only. |
| `RR Test Freeze` | `""` clears, `lidar` / `ips` / `lidar,ips` freezes the source (the acquisition hook returns early). Honored only with `-roboracerTestHooks`; otherwise counted in `RR Test Hook Rejections`. |

Control fields remain `V1 Throttle` / `V1 Steering`. The neutral runner's guard permits only exact zeros plus these two optional keys.

## Clock model

No shared epoch is assumed. For the echo of a ping sent at bridge time T1, handled at simulator time R, emitted at E and received at bridge time T4:

- offset θ = ((R − T1) + (E − T4)) / 2 (simulator minus bridge)
- error bound = ((T4 − T1) − (E − R)) / 2

The validator uses the tightest-bound sample among the last 16 exchanges. An acquisition's bridge-clock time is `monoEndNs − θ`, with the same bound. Repeated, unknown or non-causal echoes are ignored or rejected. The bound includes Unity's main-thread queueing and the time spent moving a ~3.7 MB camera frame. On this host it measured about 40–75 ms (see the [SIM1-01 report](../../../docs/stages/SIM1-provenance.md)).

## Devkit publication (`autodrive_neutral.py --provenance`)

- **Header stamps:** for LaserScan, Imu, JointState (encoders) and Image, the header stamp is set to acquisition time mapped into ROS time: `ros_now − (mono_now − (monoEndNs − θ))`. Before the first clock exchange (the first frame), the vendor publication stamp remains, and the frame is recorded with `stamp_basis: bridge-publication`. Point (IPS) has no header and is carried only on the provenance topic.
- **`/autodrive/f1tenth_1/provenance`** (`std_msgs/String`, JSON): published once per frame with session, episode, telemetry sequence, and for every source its seq/step/sim time/ROS stamp/reused flag/age/age bound, plus the clock sample.

## Fail-closed rules (validator)

The validator rejects a frame and the bridge stops replying when any of the following occurs:
- missing fields, a wrong schema, or missing required capabilities;
- a test-hook capability that differs from the trial's expectation;
- a session change, a duplicate or decreasing telemetry sequence, or an episode moving backwards;
- a malformed or nonfinite stamp, or a stamp from a different episode;
- a source sequence moving backwards, or a reused sequence whose stamp differs;
- an acquisition time later than emission.

An episode increase is accepted and clears per-source history; reset handling belongs to SIM1-03.
