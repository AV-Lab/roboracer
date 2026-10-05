# PRE — Permission Recovery and Disarmed Interface Evidence

Date: **2026-09-28**. Run: **20260928T120809Z**. Approved scope: resume PRE under plan v1.0. **Infrastructure checks passed through individually approved host commands. PRE as a whole is incomplete. No actuator `Bridge` message or simulated-motion command was sent.**

Evidence: [run context](../../artifacts/preflight/20260928T120809Z/run-context.json). Scratch diagnostics and new Devkit environment: `/tmp/roboracer-work/preflight-20260928T120809Z`. The AVLite environment/source snapshot from the first attempt was completed in `/tmp/roboracer-work/preflight-20260928T113745Z`. Disposable diagnostics remain outside AVLite's plugin scan root; source text is retained with evidence. No plugin feature implementation was added.

## Verified results and limits

| Check | Actual result | Evidence / boundary |
| --- | --- | --- |
| Command approvals | Available and exercised. The sandbox still rejected PyPI; approved host commands completed downloads. | [Denial](../../artifacts/preflight/20260928T120809Z/sandbox-dependency-denial.json). No globally relaxed network policy is claimed. |
| GPU/display/interfaces | NVIDIA GeForce RTX 3080, X11 `:1`, NVIDIA/DRI devices and normal interface enumeration available. | [Access summary](../../artifacts/preflight/20260928T120809Z/approved-host-access-summary.json). Applies to approved host execution. |
| AVLite installation | Pinned source installed as **0.6.3**, Python **3.10**, NumPy **2.2.6**; `pip check` passed. | [Install report](../../artifacts/preflight/20260928T120809Z/avlite-pip-install-report.json), [commands/results](../../artifacts/preflight/20260928T120809Z/dependency-results.json), [freeze](../../artifacts/preflight/20260928T120809Z/avlite-freeze.stdout.log). |
| Import/profile isolation | Wheel import resolved inside intended venv. Unchanged contract probe passed with runtime/metadata both 0.6.3 and isolated profile value restored to 7. | [Wheel import](../../artifacts/preflight/20260928T120809Z/avlite-import-result.json), [contract probe](../../artifacts/preflight/20260928T120809Z/fresh-avlite-contract.stdout.log). The latter intentionally imports pinned source; distinguish it from the wheel check. |
| Humble DDS | Sender submitted 20 String messages; receiver received the first three and met its predefined stopping condition. Both exited 0 and were reaped. | [Manifest](../../artifacts/preflight/20260928T120809Z/approved-host-dds.json), [receiver](../../artifacts/preflight/20260928T120809Z/approved-host-dds-receive.log). Domain 87, localhost only; not a 3/20 loss-rate measurement. |
| Graphical startup | Owned 1280×720 window rendered through Vulkan/RTX 3080. Manual mode and zero speed/throttle/steering visible. Exit 0, reaped; lifetime **30.50 s**. | [Manifest](../../artifacts/preflight/20260928T120809Z/unity-graphical-startup.json), [window](../../artifacts/preflight/20260928T120809Z/unity-graphical-window.png), [Player log](../../artifacts/preflight/20260928T120809Z/unity-graphical-player.log). No headless or unattended-release qualification. |
| Passive simulator API | Receive-only Socket.IO server on `127.0.0.1:4567` accepted one connection and captured **one actual telemetry frame**. One Connect click; Manual mode retained; zero control replies. | [Observer](../../artifacts/preflight/20260928T120809Z/passive-api-observer.json), [owned run](../../artifacts/preflight/20260928T120809Z/unity-passive-api-startup.json), [connected window](../../artifacts/preflight/20260928T120809Z/unity-passive-api-after.png). No continuous-rate/freshness claim. |
| Observations | 1081 ranges: 1035 finite, 46 non-finite, zero NaNs; finite span 0.5357178–9.854965. Also intensities, encoders, position, orientation, angular velocity, acceleration, and 1280×720 camera image. | [Raw frame](../../artifacts/preflight/20260928T120809Z/passive-api-first-frame.json). Units/frame semantics need qualification. Reported scan rate `20.000` is not measured throughput. |
| Separate conversion environment | NumPy 1.26.4/OpenCV 4.10.0/system Humble cv_bridge passed RGB→ROS serialization→native BGR conversion. Final `pip check` passed after adding missing PyYAML. | [Imports/conversion](../../artifacts/preflight/20260928T120809Z/devkit-import-results.json), [passing check](../../artifacts/preflight/20260928T120809Z/devkit-pip-check-after-repair.stdout.log), [freeze](../../artifacts/preflight/20260928T120809Z/devkit-freeze-after-repair.stdout.log). Stock Devkit has the import blocker below. |
| Recorded sensor DDS transfer | Captured scan/image published from NumPy 1 process and received in NumPy 2 process importing AVLite 0.6.3. Float32 range bytes and RGB image bytes matched. Both exited 0 and were reaped. | [Manifest](../../artifacts/preflight/20260928T120809Z/recorded-sensor-dds.json), [receiver](../../artifacts/preflight/20260928T120809Z/recorded-sensor-dds-receive.log). Recorded-input transport only; no live plugin bridge. Acquisition timestamps and scan geometry were not synthesized. |
| Cleanup/integrity | Owned Unity/observer/DDS children reaped; 4567 listener released. Three source-repository states and nine selected simulator hashes match initial run. | [Integrity](../../artifacts/preflight/20260928T120809Z/post-probe-integrity.json), [port check](../../artifacts/preflight/20260928T120809Z/post-listener-check.json). No global installation, source/core edit, physical command or publishing. |

Passive-run bound: 45 seconds before cleanup; total recorded lifetime **46.37 s** including termination/reaping. Observer was intentionally terminated after Unity with SIGTERM, exit `-15`, and reaped. Its telemetry manifest is a checkpoint; the parent lifecycle record establishes cleanup. It did not reach its independent 55-second deadline.

## Compatibility findings

The fresh AVLite environment meets its NumPy >=2 requirement. Its combined camera-import attempt logged Humble `cv_bridge`'s `_ARRAY_API not found` under NumPy 2.2.6; that environment also lacked `cv2`. Combined camera qualification **failed**, and [stderr](../../artifacts/preflight/20260928T120809Z/avlite-humble-import.stderr.log) is retained. Do not downgrade AVLite below its requirement or modify system ROS to mask this result.

The separate NumPy 1 environment passed native image conversion and sent recorded sensor messages to the NumPy 2 AVLite environment. This supports keeping conversion in a compatible process. It does not qualify every ROS extension or complete production integration.

Historical protocol packages were retained: `python-socketio==4.2.0`, `python-engineio==3.13.0`, `gevent-websocket==0.10.1`. Python 3.10-compatible gevent resolved to **26.9.0**, rather than the historical README's Python 3.8-tested 21.1.2. Exact results are frozen. One-frame reception establishes limited protocol compatibility, not unchanged historical Devkit certification.

`attrdict==2.0.1`, imported by historical F1TENTH config, failed with `ImportError: cannot import name 'Mapping' from 'collections'`. Stock Devkit cannot yet be called Humble-compatible. No shim or fork was silently adopted. A bounded Python 3.10 adaptation in an isolated overlay is the next engineering candidate; a material transport replacement would require the agreed architecture review.

The first Devkit `pip check` exposed inherited Humble `launch-ros`'s PyYAML requirement. PyYAML 6.0.3 resolved that check; failure and subsequent pass are retained separately. An import diagnostic ran before installation finished; `premature-*` results are excluded from compatibility conclusions. The sensor-transfer parent initially retained the String probe's topic label; metadata was corrected against retained child source, preserving the old value/reason. Executed sensor topics are `recorded_fixture/scan` and `recorded_fixture/image`; message results were unchanged. See [diagnostic notes](../../artifacts/preflight/20260928T120809Z/diagnostic-notes.json).

## Simulator evidence boundaries

Live fields match the inspected historical F1TENTH schema, strengthening the 0.3.0-era candidate. Exact release identity and an official distribution checksum match remain unavailable. Unity revision alone is insufficient.

One-frame reception without a `Bridge` reply is consistent with historical [Socket.cs](https://github.com/Tinker-Twins/AutoDRIVE/blob/635dbb6d86ec98e25ea845a97188f7bbe85a09e8/Assets/Scripts/Socket.cs), which emits on connect and application exchange. **Inference:** continuous observations likely require the matching request/reply loop. Source-generation timing, repeated-scan detection, actuator semantics and stop response remain unqualified.

Manual/zero-speed startup and zero-throttle telemetry do not prove braking, watchdog behavior or expiry. Retained-command concerns remain. Camera/telemetry snapshots do not qualify independent track-boundary/contact/progress scoring.

Explicit logs/preferences use scratch paths. Unity also reported a shared Vulkan cache at `/tmp/AutoDRIVE Ecosystem/AutoDRIVE Simulator/vulkan_pso_cache.bin`; complete per-run write isolation is not claimed. No global display-access rule or installation file was changed. [Unity 2021.3 Player flags](https://docs.unity3d.com/2021.3/Documentation/Manual/PlayerCommandLineArguments.html) were rechecked on 2026-09-28; manifests/logs establish actual behavior separately.

## Remaining gates

| Gate | Status / next evidence |
| --- | --- |
| PRE-B01 download access | Operationally resolved for approved commands; sandbox denial persists. Both environments have reports/locks and passing final packaging checks. |
| PRE-B02 display/GPU access | Access/startup restriction resolved. Repeatable unattended sensing still needs qualification. |
| PRE-B03 basic DDS access | Resolved for scoped host tests and recorded sensor delivery. Continuous live integration remains open. |
| PRE-B04 API/scene/scoring/reset | Advanced by one frame; continuous sensing, geometry/clocks, stop/reset and independent scoring remain open. |
| PRE-B05 motion envelope | Numerical operational limits require confirmation before any motion command. No motion protocol was executed. |
| PRE-B06 Devkit compatibility | Newly reproduced attrdict/Python 3.10 blocker. Qualify narrow overlay adaptation and continuous neutral/disarmed path; preserve compatible NumPy process environments. |

**PRE-01 is accepted** for bounded identity, owned-process accounting and isolated profile/output checks, with the shared temporary cache limitation above. **PRE-02–04 remain unchecked.** Plan: one accepted PRE item, 33 unchecked items, no feature-stage acceptance. No lap, collision, control-frequency, latency or racing-performance benchmark ran.

Next work: bounded Devkit compatibility/continuous-observation and stop-path qualification, then a concrete motion-protocol proposal. Approved architecture, Humble, installed simulator and acceptance criteria remain in force. S1 feature work has not started.

Retain evidence while PRE is open. After reproducible integration and necessary locks/fixtures are retained, remove disposable scratch probes/environments or consolidate useful diagnostics into the approved reusable tools. Raw telemetry/images/dependencies remain outside Git.
