# PRE — Continuous Interface Qualification and Capability Decision

Date: **2026-09-28**. Run: **20260928T124339Z**. Status: **PRE-02 passed for the pinned disarmed interface; PRE-03/04 remain blocked. PRE is not complete.** No motion command or S1 feature implementation occurred.

**Subsequent decision, 2026-09-29:** the user selected option A preparation. See the [feasibility report](PRE-option-A-feasibility.md) and [draft amendment](../planning/simulator-build-amendment.md). The pending-choice language below is historical; source compilation and instrumentation are still unperformed, and PRE acceptance is unchanged.

## Verified outcome

The installed AutoDRIVE application now exchanges continuous telemetry with an isolated Humble Devkit. All eight published message streams reach a separate process importing the installed AVLite 0.6.3 under NumPy 2.2.6. The Devkit runs under Python 3.10/NumPy 1.26.4. Two bounded attempts each covered 60 frames before a GUI Reset and 60 after reconnecting. Manual mode was retained; every outgoing Bridge reply was constrained to zero throttle and zero steering.

The first attempt exposed publisher growth and shutdown failures. A narrow disposable Devkit overlay corrected those issues; the second attempt completed with all three owned processes exiting normally. This qualifies the dependency/build/continuous-sensor/lifecycle part of PRE. It does **not** qualify autonomous control, braking, source acquisition freshness, a plugin closed loop or race performance.

Evidence: [run context](../../artifacts/preflight/20260928T124339Z/run-context.json), [analysis](../../artifacts/preflight/20260928T124339Z/neutral-analysis.json), [initial runtime manifest](../../artifacts/preflight/20260928T124339Z/neutral-run.json), [corrected runtime manifest](../../artifacts/preflight/20260928T124339Z/cached-tf/neutral-run.json).

## Pinned configuration and bounded adaptations

- Existing simulator installation remains at `/home/a2rl/Workspace/AutoDRIVE Simulator [Linux]`. Its selected binary/asset fingerprints define the local baseline. Unity is 2021.3.9f1; a matching engine version and API shape do not prove an exact AutoDRIVE release or source-to-binary match.
- Official Devkit source: `Tinker-Twins/AutoDRIVE`, commit `4abf7cd819042aaf65539375c870247d453c7fe2`, F1TENTH ROS 2 package. Historical simulator source: commit `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`. The package declares 0.1.0 within that historical Devkit release.
- Four attrdict 2.0.1 imports were changed from `collections` to `collections.abc` in a scratch overlay. Installed dependencies and shared environments were not patched. [Patch](../../artifacts/preflight/20260928T124339Z/attrdict-python310.patch).
- The copied incoming bridge binds only `127.0.0.1:4567`. [Patch](../../artifacts/preflight/20260928T124339Z/devkit-loopback.patch).
- After the initial live failure, the copied bridge reuses one TF broadcaster and handles SIGTERM/SIGINT through the gevent server with explicit ROS cleanup. [Patch](../../artifacts/preflight/20260928T124339Z/devkit-tf-lifecycle.patch).
- Both isolated colcon builds passed. Bytecode-disabled and legacy `script-dir` warnings are retained. The official outgoing command node and teleoperation node were never launched.
- ROS domain 87, localhost-only, reliable KeepLast depth 1; display `:1`, owned 1280×720 window, Vulkan on the host RTX 3080. GUI actions were Connect, Reset and Connect. No driving-mode change or keyboard driving input occurred.
- The neutral-only wrapper capped each connection at 60 processed frames, then withheld replies. The first attempt inserted a 100 ms reply delay; the corrected attempt used zero added delay. These configurations differ, so their rate difference is **not** an isolated TF optimization benchmark.

The disposable probes and patches are retained in the ignored run artifacts. Their eventual production design remains S1 work. No AVLite core, reference-plugin source or installed simulator file was modified.

## Actual measurements

| Measurement | Initial attempt | Corrected attempt |
| --- | --- | --- |
| Processed Bridge frames | 60 + Reset + 60 | 60 + Reset + 60 |
| Received messages per topic, all eight topics | 120 each | 120 each |
| Segment receipt rates | 3.780 / 3.797 Hz | 6.494 / 6.382 Hz |
| Largest measured inter-receipt interval | 297.08 ms | 176.25 ms |
| ROS node publisher count, first → last frame | 20 → 1329 | 10 → 10 |
| Bridge RSS, first → last sampled frame | 138256 → 214560 kB | 137324 → 144248 kB |
| Bridge shutdown | SIGTERM exceeded 5 s; owned SIGKILL, exit −9 | SIGTERM, exit 0 |
| Observer shutdown | Exit 1: ROS context was shut down twice | SIGTERM, exit 0 |
| Simulator shutdown | Exit 0 | Exit 0 |
| Total wall time including cleanup | 57.71 s | 39.81 s |

The streams are throttle, steering, left/right encoder, IPS, IMU, LiDAR and front camera. Across all 240 frames, throttle/steering feedback and encoder values remained zero. Reported position was within x=0.740–0.741 m, y=3.158 m, z=0.059 m at the protocol's three-decimal precision. All four observed starts had the same first reported pose. This is bounded static/reset evidence, not bitwise reproducibility or a measured stopping tolerance.

Each scan had 1081 samples. First-frame fixtures had 1035 finite ranges; camera images decoded to 1280×720 RGB. For the first frame of each of four connection segments, float32 scan bytes and decoded RGB bytes matched an actual received ROS message. The observer imported AVLite but did not run an AVLite bridge/plugin/executor.

The API's `LIDAR Scan Rate = 20.000` is a reported setting. It is **not** the measured Bridge receipt rate or a proven unique-acquisition rate. These short stationary runs are qualification observations, not M1/M2 performance acceptance.

## Installed geometry and source discrepancies

Read-only UnityPy 1.25.3 inspection extracted builtin serialized types from the installed `Data/level0`, all 18 referenced collider meshes and 120 script identities. A separate analysis environment was used; inherited ROS PYTHONPATH initially contaminated its packaging check, and the explicitly isolated check subsequently passed. The original failed check remains recorded.

| Finding | Evidence level / implication |
| --- | --- |
| Proto Track is active; Berlin Track is inactive in the serialized hierarchy. | Installed-asset fact. Proto is the candidate C0; no runtime track-switch API is qualified. |
| F1TENTH Rigidbody mass is approximately 3.47 kg; WheelCollider radius is approximately 0.059 m. | Installed-asset values, not hardware calibration or complete physics validation. |
| Front/rear wheel-transform longitudinal separation is 0.330 m; named axle-center separation is 0.331 m. | Installed geometry. These differ from the historical controller's 0.324 m parameter and its 0.0325 m wheel-radius field; do not merge them into one unqualified calibration. |
| Rear axle initial transform maps approximately to (0.740, 3.160, 0.060) using historical IPS's `(z, −x, y)` basis. | Consistent with, but not a complete verification of, settled telemetry around (0.740, 3.158, 0.059). Motion-based sign/reference checks remain. |
| Most custom MonoBehaviour field trees were absent. | Initial full parsing errors are retained. Builtin transforms/colliders and script-header identities parsed successfully; custom controller fields were not fabricated from untyped bytes. |
| Devkit front-wheel TF uses 0.141537/0.0765 constants. | Source discrepancy with F1TENTH geometry. Do not use that wheel TF as calibrated kinematics. |
| Devkit `time_increment = (1 / scan_rate) / 360`. | The received value is about 0.000138889 s despite 1081 samples. It is not a verified per-beam acquisition interval and must not be used for deskewing. |

Evidence: [asset inspection](../../artifacts/preflight/20260928T124339Z/installed-scene-inspection.json), [collider/script extraction](../../artifacts/preflight/20260928T124339Z/installed-scene-meshes.json), [geometry summary](../../artifacts/preflight/20260928T124339Z/installed-geometry-summary.json). Extracting mesh bounds does not qualify a whole-footprint contact/off-track/lap scorer. No map, reference path or scenario feature was implemented.

## Remaining capability blockers

| ID | Verified evidence and uncertainty | Affected approved requirement |
| --- | --- | --- |
| PRE-B07 | Actual Bridge payloads have 13 fields and no acquisition timestamps, acquisition sequence, simulator clock or command acknowledgment ID. Devkit ROS stamps are assigned during message construction. | Source freshness/coherence and acquisition-rate claims cannot be inferred from receipt/publication time. A new reception can contain an old scan. Payload equality alone cannot distinguish a valid unchanged scene from a held acquisition. |
| PRE-B08 | The inspected historical Socket/VehicleController source has no receiver-side command lease and retains autonomous commands. No installed-binary expiry guarantee or runtime moving-stop test is established. | The approved plan explicitly requires surviving downstream expiry for stop-on-supervisor-failure. Terminating Unity contains a simulation failure; it does not demonstrate braking. |
| PRE-B09 | One fixed start plus GUI Reset/reconnect works at rest. No API for arbitrary initial state, static obstacle placement or collision/lap events was found in the matched source/payload. | Five reproducible initial states, T1/T2/T3, independent event scoring and complete reset/clock qualification remain unresolved. This does not assert that every hidden application capability is impossible. |
| PRE-B05 | No numerical motion protocol is approved; autonomous signs/limits, neutral braking and speed conversion are unqualified. | PRE-03 and S1 motion remain held. New timing/expiry contracts must be selected before proposing meaningful numerical limits. |

The access blockers and attrdict failure are resolved for the tested scoped commands/overlay. **More general filesystem or network permission will not add these missing simulator contracts.**

## Concrete decision proposal — not approved or implemented

The current plan says: “A dead or hung sole publisher cannot deliver a new stop command: the surviving downstream receiver must enforce qualified expiry, or the stop-on-supervisor-failure acceptance case remains blocked.” It also requires that repeated publication not refresh sensor acquisition freshness. Neither requirement is marked passed.

| Option | Benefit | Cost / risk / plan impact |
| --- | --- | --- |
| **A. Prepare a separate instrumented AutoDRIVE build — recommended.** | Preserve the existing acceptance goals and AutoDRIVE/Humble/ICP direction. Add observable acquisition identity/time, receiver expiry and disarm, evaluator-only events, and controlled reset/start/static fixtures. | New simulator build and maintenance scope. First verify complete official source/assets and the exact Unity build toolchain; source-to-installed equivalence is not proven. No compatible Unity editor was found on PATH or the checked conventional roots. Downloads, licensing availability, build success and physics equivalence remain unknown. |
| B. Keep the installed binary and revise affected acceptance explicitly. | Avoid a Unity build dependency; preserve the demonstrated integration path. | Receipt-age checks are weaker than acquisition freshness; process termination is containment rather than braking. Some scenario coverage may remain unavailable. This reduces or splits agreed acceptance and cannot silently count as full PRE/release completion. |
| C. Retain the plan and wait for a qualified upstream distribution/API. | Avoid maintaining a simulator fork and avoid weakening acceptance. | Delivery remains blocked until an identified distribution demonstrates the required contracts; no schedule is promised. |

For A, the **next authorization requested is only a PRE preparation extension**: inspect the complete pinned source and build prerequisites, check whether a separate supported editor/build environment can be obtained, and submit a bounded simulator amendment with files, contracts, dependencies and acceptance. Preserve the current installation and its evidence; do not change AVLite core, vehicle physics or the plugin's approved target-speed/steering boundary. No simulator instrumentation implementation, editor/license acquisition, motion or revised-plan acceptance is inferred from choosing that preparation route. Any required installation approval will identify actual paths and packages.

Candidate amendment responsibilities are: (1) sensor-specific acquisition counters and timestamps, plus simulation-step/time reporting; (2) simulator-side expiry using an explicit clock and a bounded final command lease, complementary to the independent supervisor; (3) reset/start configuration and fixed static fixtures while disarmed; (4) evaluator-only truth/contact/progress outputs separated from driving inputs. Each must be validated in the separate build before replacing any qualified installed-binary result. The implementation plan and numerical motion protocol will be revised for review after feasibility is established.

**Recommendation:** approve preparation for A. Ordinary Devkit compatibility work is already completed; changing the simulator build is a material boundary expressly reserved for user confirmation. The technical direction B, Humble, ICP and independent hardware stop remain unchanged.

## Stage status and continuation

- PRE-01: accepted previously; identity/integrity rechecked for this run.
- PRE-02: accepted for the fingerprinted local application, pinned official Devkit plus recorded narrow overlays, isolated Humble dependencies, continuous disarmed data and bounded lifecycle.
- PRE-03: unchecked; source timing/control/retention/stop and the numerical motion gate remain unresolved.
- PRE-04: unchecked; a fixed static Reset and installed geometry are verified, but required clocks/scoring/start/scenario qualification is incomplete.

There are **2 accepted and 32 unchecked plan todos**. S1 feature implementation has not started. All owned runtime children were reaped. Selected source/binary integrity and evidence hashes are recorded in the run's final audit. No repository commit, remote creation, push, physical-device access or global installation occurred.

## Sources and reproduction boundary

Read on 2026-09-28: pinned local official Devkit `autodrive_incoming_bridge.py`, `config.py`, `setup.py`, `package.xml`; pinned simulator `Socket.cs`, `VehicleController.cs`, `IPS.cs`, `IMU.cs`, `LIDAR.cs`, `SceneReset.cs`, `LapTimer.cs`, `Timer.cs` and `ProjectSettings/ProjectVersion.txt`; installed assets; and [UnityPy's primary README](https://github.com/K0lb3/UnityPy/blob/master/README.md) plus installed 1.25.3 parser source. Package installation reports/freezes, build commands, source patches, probe snapshots, runtime commands/environment, traces and screenshots are under [this run](../../artifacts/preflight/20260928T124339Z/run-context.json).

The scratch environments and probe programs are disposable and are not a supported plugin CLI. Exact argv and paths are in the runtime/build manifests; rerunning requires the same scoped display/DDS access, a free local port, the pinned environments and new result directories. The current installation also uses a shared `/tmp/AutoDRIVE Ecosystem/AutoDRIVE Simulator/` graphics cache; complete per-run write isolation is not claimed.
