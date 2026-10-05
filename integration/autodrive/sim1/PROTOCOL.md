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

# roboracer.guard/1 — receiver guard (SIM1-02)

Built by `autodrive_build.py --sim1-patch` (default `--sim1-through 02`), which applies [`vendor-sim1-02.patch`](vendor-sim1-02.patch) after sim1-01 and stages [`RoboRacer/GuardCore.cs`](RoboRacer/GuardCore.cs) (Unity-free logic, unit-tested under the pinned Mono) and [`RoboRacer/Guard.cs`](RoboRacer/Guard.cs) (Unity glue). The bridge side is [`scripts/autodrive_guard.py`](../../../scripts/autodrive_guard.py).

The guard is **inactive unless the player is launched with `-roboracerGuard`**. Without that flag, the player behaves exactly like the sim1-01 build. With it, the player runs in the qualified autonomous test mode:

- **Actuation hook:** the guard writes the controller's autonomous inputs at the top of `VehicleController.FixedUpdate`, after `GetInput()` and immediately before `Steer()`/`Drive()`, and forces `DrivingMode = 1`. After `UpdateWheelPoses()` it reads back all four wheel-collider motor and brake torques and both front steer angles. Any motor torque while the commanded output is zero (or any steer angle under the interlock) faults the session.
- **Bypasses closed:** legacy `V1 Throttle`/`V1 Steering` Bridge fields are never written to the controller. Nonzero or unparsable legacy values are counted. Manual axes and mouse steering are ignored and counted. The GUI driving-mode toggle is blocked and logged, and the mode label reads "Guarded".
- **Zero-output interlock:** on unless the player is also launched with `-roboracerMotionAuthorized`. Under the interlock, an accepted nonzero command is recorded and counted (`interlock_steps`) but the output is zero. The SIM1-02 runner never passes that flag. Moving tests require the SIM1-05 protocol.
- **Trace:** `-roboracerGuardTrace <existing dir>` writes `guard-trace.jsonl`: a start record, every event, and one record per vehicle `FixedUpdate` (state, epoch, applied id, guard command, actual output, mode, manual-input flag, motor/brake torques, steer angles). It is bounded to 256 MiB.

## States

`disarmed` (startup) → `armed` on a valid arm request. From `armed`:

- lease expiry → `stopped` (`lease-expired <seq>`);
- clock discontinuity or actuation mismatch → `fault`;
- disarm request → `disarmed` (`requested`);
- Socket.IO disconnect → `disarmed` (`disconnect`);
- scene load → `disarmed` (`scene-load`).

`stopped` and `fault` are sticky until an explicit new arm. Every exit from `armed` clears the lease. Each arm increments the epoch and binds one origin.

## Bridge → simulator (reply fields)

| Key | Meaning |
| --- | --- |
| `RR Reply To` | `RR Telemetry Seq` of the frame this reply answers. |
| `RR Reply Frame Receipt` | Bridge monotonic ns when that frame was received. Optional: if absent, the ping time is used, which only widens the clock bound. |
| `RR Ping Mono` | As in sim1/1, stamped immediately before sending. |
| `RR Guard Envelope` | Transport sequence, digits, strictly increasing per connection. A missing or malformed envelope rejects the reply's guard content (`reject envelope - malformed`). A replayed or decreasing envelope rejects it (`envelope-replay`). |
| `RR Guard Arm` | `arm <session> <episode> <origin>` or `disarm`. |
| `RR Guard Request` | `<epoch> <origin> <seq> <genNs> <deadlineNs> <throttle> <steering> <inputs>`, with times on the request source's monotonic clock. `inputs` is an opaque token (≤128 chars), echoed on acceptance so the original request's input identities survive forwarding. |

**Request times:** the supervisor stand-in and the bridge share the host's `CLOCK_MONOTONIC` (Python `time.monotonic_ns`). The simulator never assumes an epoch shared with that clock.

## Receiver clock bound

Each reply whose `RR Reply To` frame is still known (last 64) gives an offset interval (simulator − bridge), computed only from the receiver's own stamps E (emit of that frame) and R (receipt of the reply):

- lower: `E − frameReceipt`
- upper: `R − ping`

Intervals from the last **2 s** are intersected. An interval disjoint from the current intersection is a **clock discontinuity**: the history is cleared, and an armed or stopped session faults. A frame receipt later than the ping is discarded as non-causal. With no interval in the window, requests are rejected as `clock-unavailable`. With an intersection wider than **400 ms**, they are rejected as `clock-uncertain`.

## Request validation (in order; the first failure is the reason)

1. `malformed`: wrong field count, non-digit epoch/seq/times, an invalid origin or inputs token, or unparsable values.
2. `nonfinite`.
3. `out-of-range`: |throttle| or |steering| > 1.
4. `not-armed`.
5. `stale-epoch`.
6. `foreign-origin`.
7. `duplicate`: same seq as the last accepted.
8. `out-of-order`: lower seq than the last accepted.
9. `invalid-deadline`: deadline ≤ generation.
10. `lease-too-long`: deadline − generation > **1 s**.
11. `clock-unavailable` / `clock-uncertain`.
12. `future-generation`: generation + lower bound > now.
13. `expired`: the expiry below is already past.

**Expiry** = min(deadline + lower bound, receipt + **1 s** receiver-local lease). The lower bound is the earliest simulator time the deadline can correspond to. The guard checks expiry again in every `FixedUpdate` before actuation.

A rejection never changes an existing lease. A duplicate cannot extend it.

The 1 s lease, 400 ms clock width and 2 s window are **provisional SIM1-02 test parameters**. They were chosen so the stock ~3.9 Hz lock-step transport tolerates a missed reply. They are not qualified motion bounds; SIM1-05 freezes the real values.

## Simulator → bridge (every telemetry frame, guard mode only)

`RR Capabilities` gains `guard`. The guard fields are:

| Key | Meaning |
| --- | --- |
| `RR Guard Schema` | `roboracer.guard/1`. |
| `RR Guard State` / `Reason` / `Epoch` / `Origin` | Current state machine values. |
| `RR Guard Accepted` / `Applied` | Last accepted seq and last seq applied at the actuation hook (−1 when none). |
| `RR Guard Lease Remaining` | ns until expiry, or −1 when there is no lease. |
| `RR Guard Clock` | `lower upper samples` of the current intersection (`""` when unavailable). |
| `RR Guard Counters` | `accepted rejected expired applied_steps legacy_ignored manual_ignored gui_blocked violations interlock_steps`. |
| `RR Guard Config` | `maxLeaseNs maxClockWidthNs clockWindowNs interlock\|motion-authorized`. |
| `RR Guard Event Seq` / `RR Guard Events` | Total event count, and the `;`-joined `n text` events since the previous frame (bounded to 64, with an explicit `overflow N` marker). |

The bridge's `GuardTracker` rejects a frame that is missing the capability, is not in interlock mode, has an event gap or an overflow, or has an event seq that disagrees with the delivered events.

**Event texts:**

- `state armed epoch E origin`
- `state <disarmed|stopped|fault> <reason>`
- `disarm-request`
- `accept S expiryInNs throttle steering inputs`
- `applied S step N`
- `reject <S|-|arm|envelope ...> <reason>`
- `clock <reason>`
- `blocked driving-mode`
- `violation <detail>`

The player's `guard-trace.jsonl` is the authoritative record. The live scenario cross-checks every event it relied on against the trace.
