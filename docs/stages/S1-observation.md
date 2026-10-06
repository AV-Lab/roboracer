# S1-02 (part 1) — Bridge observation path on the guarded player

Date: **2026-10-05**. Run: `20261005T102231Z-s1-02-live`. Plan: [amendment 1.2](../planning/s1-first-amendment.md), order of work step 2.

**The observation half of S1-02 passes.** The plugin's `AutoDriveBridge` now subscribes to the provenance-enabled Devkit topics. It assembles each telemetry frame into one checked snapshot and serves AVLite `SensorFrame`s and a labelled ground-truth pose from it.

- **Scan checks:** the LiDAR beam order, angle convention and mount were checked against the built scene's geometry.
- **Live run:** in a 60-second interlocked run on the SIM1-02 player, every one of the 240 frames that carried acquisition stamps became exactly one snapshot. Each snapshot's scan was that frame's own scan, and each pose was that frame's own IPS/IMU value.

**Not covered here:** command signs and units against observed simulator response, the other half of S1-02. They need motion, which waits for the numerical motion protocol (amendment step 4). **Nothing moved:** the zero-output interlock was on, every request was exact zero, and the plugin's speed limit was 0.

## 1. What was built

| Part | Content |
| --- | --- |
| [`autodrive_observation.py`](../../roboracer/integration/autodrive_observation.py) | ROS-free `SnapshotAssembler`, described below. |
| [`autodrive_bridge.py`](../../roboracer/integration/autodrive_bridge.py) | Construction stays side-effect free. `connect()` creates a private rclpy context (no signal-handler takeover), one node and one executor thread. Snapshots are swapped in atomically. `get_sensor_frame()` returns fresh sensor objects over shared read-only buffers. `observation_age_s()`, `statistics()` and `snapshot_listener` are provided for the supervisor and runner. Advertises `LIDAR_2D` and `IMU`. *As run:* `LOCALIZATION` was gated by a `gt_localization` plugin setting (off). *Superseded the same day* for AVLite plugin-guide conformance: ground-truth `LOCALIZATION` is a static class attribute like `BasicSim`, switched off with AVLite's own filter `c41_world_stack_capabilities`; the setting was removed. The observation path is unchanged. |
| [`autodrive_scan_check.py`](../../scripts/autodrive_scan_check.py) | Independent scan check: exports the player's serialized colliders and ray-casts the vendor scan model from a recorded pose. |
| `autodrive_neutral.py --plugin-observer` | Runs the bridge, loaded by AVLite's own plugin loader with isolated AVLite/XDG directories, as one more read-only child in a live trial. The provenance message now also carries `ips_position`. |
| [`autodrive_s1_observation.py`](../../scripts/autodrive_s1_observation.py) | Offline join of the plugin's snapshots with the raw bridge frames and the independent topic observer. |

**`SnapshotAssembler` checks.** Separate ROS topics are not ordered relative to each other. The assembler therefore keeps each frame's provenance record pending and looks up its members:
- LaserScan, IMU and both encoders by exact acquisition header stamp;
- the header-less IPS `Point` by exact value.

It rejects and counts any frame that fails one of these checks:
- a member proven missing by a newer stamp, or not arriving within 0.5 s;
- the first frame, which is stamped before any clock exchange;
- a session change, a non-increasing sequence or an episode moving backwards;
- non-finite readings, or a scan layout other than the qualified one;
- LiDAR/IPS acquisitions more than 60 ms apart.

Stamps are acquisition times on the host `CLOCK_MONOTONIC`, the same clock domain as supervisor requests. The ground-truth pose is labelled `ground-truth`, with its 1 mm reporting resolution.

**Frames and mounts.** The body origin is the reported IPS point. That point is the rear-axle centre: the serialized `Transforms/Rear Axle Center` agrees with it to about 2 mm. It is not the `Sensors/IPS` object, which sits 0.08 m further forward. Mounts from the serialized SIM1-02 scene:
- LiDAR: (0.2733, 0, 0.096) m;
- IMU: (0.08, 0, 0.055) m;
- wheelbase: 0.331 m.

The scan has 1,081 beams, counter-clockwise from −135° in 0.25° steps, covering 0.06–10 m.

The vendor intensity is a constant 47, so it is padded to 0. The vendor IMU reports no gravity (linear acceleration ≈ 0 at rest), and its orientation is reported to 3 decimals.

## 2. Scan convention, mount and beam order

A ray-cast of the vendor model (`LIDAR.cs`: rays from `Head.position`, the first beam at head yaw + 135° in Unity, stepping anticlockwise) was compared with recorded scans. The pose came from each frame's IPS position and IMU yaw.

The convention is best in all six recorded SIM1-02 first frames:

| Hypothesis | Finite mismatches | Abs. error p50 / p95 | Within 5 mm |
| --- | --- | --- | --- |
| **CCW from −135°, scene mount** | **1** | **2.0 / 8.8–9.2 mm** | **949–954 of 1035** |
| LiDAR at the rear axle | 3 | 28 / 71 mm | 279 |
| Mount mirrored behind the axle | 5 | 53 / 147 mm | 78 |
| Reversed beam order | 53 | 189 / 385 mm | 19 |

The residual matches the pose quantization: 1 mm and 0.001 rad, which is about 5 mm sideways at 5 m. The maximum error of about 95 mm comes from beams grazing an edge.

**Limitation:** all six frames share the spawn pose, so this does not cover other poses.

**Retained failure.** The first comparison was invalid because it predicted no hits at all. Its ray targets included the car's own colliders, serialized at the scene pose, and the LiDAR head sits inside the Hokuyo housing collider. Every two-sided ray therefore hit the housing within the 0.06 m minimum range. Unity's raycast does not report a collider it starts inside, so this was a defect in the tool, not a scan result. Static scenery is now the only target, and an analytical fixture with an enclosing housing guards against a regression.

## 3. Live run (interlocked, disarmed)

The setup was one fresh-process trial: `--profile p0-creep --provenance --guard observe --plugin-observer`, 60 s, on the SIM1-02 player. A visual PID- and window-bound review of the screen was done before Connect. It showed: Guarded, Autonomous, throttle 0.00 %, steering 0.00 rad, speed 0, encoders [0, 0], Disconnected.

**Join checks (all 240 acquisition frames):**

| Check | Result |
| --- | --- |
| Snapshots | 240 of 240, in telemetry order. The only rejection is frame 1 (stamped before any clock exchange); its 5 messages were dropped. |
| Scan identity | 240 of 240 snapshot scans have the same ROS stamp and float32 range hash as the independent observer's message. |
| GT pose | 240 of 240 equal the raw IPS position. Yaw is within 5 mrad of the raw IMU Euler yaw in 240 of 240. |
| Mounts and label | As specified, `ground-truth` on every snapshot. |
| Scan/pose skew | p50 / p95 / max: 24 / 47 / 50 ms, never above one scan period. |
| Clock bound | 40–43 ms. |
| Pose age at commit | 196 / 210 / 219 ms. |
| Commit latency after bridge receipt | 109 / 111 / 112 ms. |

**Latency.** Nearly all of the latency is the runner's 0.1 s reply pacing: the Devkit bridge publishes the provenance message only after its paced reply. Publishing provenance before the reply would remove about 100 ms, and this is recorded as an S1 latency item.

**Standard checks from the existing runner analysis:**
- 241 messages on each of 8 topics, at about 3.9 Hz;
- 233 zero requests accepted and applied;
- 78,377 traced guard steps with 0 nonzero-output steps, 0 rejections and 0 expiries;
- maximum reported displacement 3 mm;
- all children exited 0 and were reaped, and port 4567 was released;
- all 604 player files were unchanged before and after the run.

The plugin observer used about 1.0 % of one core and 112 MiB RSS.

**Retained failure.** The first attempt lost its Connect click, as in SIM1-02. The window stayed Disconnected, and the bounded startup timeout ended the attempt. All five children exited 0, and the port was released. The retry succeeded. Evidence: `observe-failed-connect/`.

## 4. Tests

The plugin suite has 19 tests in `roboracer/tests/` (the 5 from S1-01 plus 14 new):
- scan geometry and range gating;
- recorded-quaternion heading;
- the assembler: coherent commit, provenance arriving first, first-frame rejection, missing-member proof and resynchronisation, timeout, IPS mismatch, identity rules, episode increase, skew, non-finite readings and layout;
- a replay of both recorded SIM1-02 observation runs (every frame after the first commits, in order);
- the bridge surface in a fresh isolated AVLite process, including GT gating, fresh objects and no ROS import without `connect()`.

Three analytical scan-check fixtures pass. The runner (12), provenance (13) and guard (10) suites pass unchanged.

The replay also caught one real detail: the Devkit publishes `angle_min` as the float32 of the literal −2.35619, which is 4.5 µrad from −135°. The layout check therefore allows 1e-5 rad.

## 5. Status and next steps

- **S1-02 stays open.** The observation path, scan/mount/order/masks and source timestamps pass. Command signs and units against observed simulator response remain, and require motion.
- **Next (no motion):** the S1 supervisor skeleton. It will run as a separate process, consume `observation_age_s()` and the snapshot identities, and own the only command path. It will forward zero requests to the guard.
- **Then:** draft the numerical motion protocol from the SIM1-02 and S1 evidence, and stop for confirmation.

Evidence: `artifacts/s1/20261005T102231Z-s1-02-live/` (64-file `evidence-sha256.txt`). Scan-check geometry (third-party collider triangles) stays in `artifacts/s1/20261005T-s1-02-prep/` and is not committed. Commit `6b2e14e` ran the live trial.
