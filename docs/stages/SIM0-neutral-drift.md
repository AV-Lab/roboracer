# SIM0 — Approved Passive-Drift Diagnostic

Date: **2026-10-01**. Study: `20261001T054121Z-drift`. [中文报告](SIM0-neutral-drift.zh-CN.md). Predecessor: [Linux recovery and original P0 stop](SIM0-linux-recovery-attempt.md).

**Follow-up approval, 2026-10-01:** the user replied “yes” to the read-only kinematics build and two bounded observations. That narrow SIM0 instrumentation exception has now been executed; see the [completed kinematics report and next decision](SIM0-kinematics.md). Execution evidence: `artifacts/simulator-build/20261001T060743Z-kinematics/`. The proposal below remains the historical scope record.

**The approved comparison completed four diagnostic windows: installed player 3 / 4 mm, rebuilt player 3 / 3 mm maximum reported displacement. Every trajectory increases in X through successive 1 mm steps; reported Y/Z and encoders remain unchanged. Exact-zero commands and actuator feedback were retained. This establishes that the observed drift is not unique to the rebuilt player. It does not establish its physical cause, harmlessness or dynamic equivalence. SIM0-B06 remains open; P0, SIM0 and PRE have not passed.**

## Authorization and method

The user's “apporve” authorized the concrete diagnostic comparison in the preceding report. [Approval](../../artifacts/simulator-build/20261001T054121Z-drift/approval.json) and [protocol](../../artifacts/simulator-build/20261001T054121Z-drift/protocol.json) preserve that scope. The existing parameterized runner gained an explicit `drift-diagnostic` profile. The default `p0` profile still rejects the first position or encoder change. A diagnostic result sets `completed_diagnostic_window=true`, **never** `completed_observation=true`.

Two fresh-process runs per player used the same Ubuntu 22.04 / ROS 2 Humble host, domain 87, localhost `127.0.0.1:4567`, RTX 3080/Vulkan, display `:1`, 1280×720 window and **Manual / Driver's Eye / Low Quality / Scene Light**. Only the reviewed, PID-bound Connect control was clicked. No reset, recentering, driving-mode change, nonzero command or simulator source/physics/sensor edit occurred. The qualified Devkit and AVLite virtual environments remained separate; replies retained the 0.1-second delay.

The order was installed 01, installed 02, source 01, source 02. It was not randomized. Position remained referenced to the **first raw frame**. The 60-second window started at the later of first complete bridge processing and first complete eight-topic ROS observation, using the same host monotonic clock. The diagnostic stopped at **reported Euclidean displacement ≥10 mm**, any encoder change, nonzero/nonfinite feedback or reply, malformed input or child failure. The 10 mm cap is diagnostic containment, **not a P0 tolerance or real-time physical safety bound**.

The parent polls at 100 ms. Actual completion exceeded the nominal deadline by **23.14–83.92 ms**, followed by screenshot capture and process teardown. The analysis therefore distinguishes the exact `[0,60]` receipt window from all retained frames. Last raw receipts during shutdown were 93.81–232.22 ms after the deadline; none changed the maximum displacement. No deliberate extension, re-zeroing or late settling window was used.

## Results

| Player / run | Actual window (s) | X first → last (m) | Max displacement (mm) | Frames inside exact window / total | Diagnostic / P0 |
| --- | ---: | --- | ---: | ---: | --- |
| Installed 01 | 60.041878 | 0.743 → 0.746 | 3 | 235 / 237 | Complete / incomplete |
| Installed 02 | 60.023143 | 0.742 → 0.746 | 4 | 236 / 238 | Complete / incomplete |
| Source 01 | 60.024083 | 0.744 → 0.747 | 3 | 233 / 235 | Complete / incomplete |
| Source 02 | 60.083921 | 0.742 → 0.745 | 3 | 234 / 236 | Complete / incomplete |

Reported Y/Z stayed **3.158 / 0.059 m** in all samples. Encoder angles/ticks, throttle and steering remained zero in every recorded raw/ROS sample; processed-frame and guarded zero-reply counts match. All eight topics received the total count shown for their run, and the complete IPS position sequence matches the raw sequence. No diagnostic guard rejection or reconnect occurred.

![Four reported displacement trajectories](../../artifacts/simulator-build/20261001T054121Z-drift/derived/drift.png)

The first changed sample arrived at **17.406 / 3.703 / 16.608 / 7.385 s**, respectively. Subsequent steps continued in the same direction. Those four times identify when the unchanged P0 position rule would reject these recorded trajectories; they are not four additional executed P0 tests. Two trials per player and different startup/connect ages do not establish distributional equivalence or a settled asymptote. Zero encoder ticks do not prove zero body translation.

| Player / run | Bridge receipt Hz, exact window | Gap p95 / max (ms), exact window | Last-topic receipt age at deadline (ms, min–max) | Startup to observation (s) | Cleanup (s) |
| --- | ---: | --- | --- | ---: | ---: |
| Installed 01 | 3.921 | 270.12 / 278.71 | 145.00–154.50 | 48.898 | 1.595 |
| Installed 02 | 3.928 | 268.33 / 277.37 | 0.42–10.39 | 44.570 | 1.594 |
| Source 01 | 3.887 | 272.99 / 279.78 | 125.38–137.35 | 67.807 | 1.644 |
| Source 02 | 3.900 | 272.06 / 284.56 | 80.57–89.80 | 40.939 | 1.595 |

All eight topics continued receiving during each window; elapsed time alone was not used as delivery evidence. Rates are **host receipt measurements**, not sensor acquisition frequency. Stock LiDAR metadata still reports 20 Hz; the protocol has no source acquisition identity. Startup includes manual screenshot review and is not an unattended-launch benchmark. The retained full-trace analyzers include startup-edge/cleanup frames, so their rates differ slightly from this fixed-window table.

Every run had **1081 ranges**, with **1035 finite ranges in its first scan**, and **1280×720 rgb8** images. Each first raw scan's float32 representation and decoded image pixels matched one ROS message. This verifies the reviewed conversion, not every frame's acquisition freshness or physical sensor fidelity.

| Player / run | Player CPU (% of one core) / peak sampled RSS (MiB) | Bridge CPU / RSS | Observer CPU / RSS |
| --- | --- | --- | --- |
| Installed 01 | 109.24 / 731.1 | 16.07 / 142.6 | 3.08 / 67.6 |
| Installed 02 | 109.66 / 724.4 | 16.89 / 142.6 | 3.18 / 62.4 |
| Source 01 | 107.86 / 733.7 | 13.85 / 142.8 | 2.67 / 67.6 |
| Source 02 | 109.75 / 740.0 | 17.66 / 142.7 | 3.29 / 67.6 |

Resource samples span approximately 100.89–127.47 seconds of each owned process's lifetime, including startup. These are contextual costs, not a controlled performance comparison. GPU memory and whole-host resource use were not measured. Every owned player, bridge and observer exited 0 and was reaped; all 12 PIDs were absent afterward and port 4567 had no listener.

## Source, diagnostics and interpretation

Read-only inspection of the pinned source/scene establishes:

- `IPS.FixedUpdate` reads the **Rear Axle Center child Transform**, mapped as `(Unity z, −Unity x, Unity y)`. `Socket.cs` formats its coordinates with `F3`. The reported positive-X progression corresponds to increasing Unity Z, not Unity X.
- The scene uses a non-kinematic, interpolated Rigidbody with no constraints. It does not expose full-precision body pose, velocity or contacts in the recorded stock packet.
- The zero-throttle code applies wheel braking; the scene's serialized `MotorTorque` is **85.6**, distinct from the script initializer. This source path is not a measurement of actual runtime brake torque or contact slip.

[Source/scene evidence](../../artifacts/simulator-build/20261001T054121Z-drift/source-motion-context.json). Contact creep, settling, interpolation/sampling effects and body-versus-child motion remain hypotheses. Rounding limits resolution; it does not explain a changing underlying position by itself. The evidence does not justify labeling the drift harmless noise or increasing P0's tolerance.

All four player logs retain the four pre-existing wheel convex-hull warnings. Each has two closed/closing-socket errors at shutdown; ThreadAbort diagnostics number **1 / 2 / 1 / 1**. The bridge emits the two existing ROS QoS deprecation warnings. Allocator “Failed count” entries are statistics, not additional exception events. The reviewed diagnostic-pattern scan has no unclassified matches; this is not a claim that the logs are error-free. [Line-based review](../../artifacts/simulator-build/20261001T054121Z-drift/derived/log-review.json). Final screenshots retain the reviewed Manual/zero-display configuration; that visual check is not millimetre-scale motion evidence.

## Engineering verification and evidence

Seven focused tests passed in **0.077 s**, covering default P0 behavior, inclusive 10 mm decimal/diagonal boundaries, encoder precedence, exact-zero/nonfinite rejection, unknown profiles and excessive run limits. Existing zero-reply/input/observer guard functions retain their prior AST. The actual executed tool and tests are snapshotted; no simulator rebuild occurred in this study. [Tool checks](../../artifacts/simulator-build/20261001T054121Z-drift/tool-checks.json).

Post-run integrity matches **9 selected installed-player files, all 603 rebuilt output files, 15 selected source/assets, 3 runtime configuration/bridge files, 3 reference repository states, the source diff and all 434 files of the preceding frozen evidence manifest**. [Integrity](../../artifacts/simulator-build/20261001T054121Z-drift/post-run-integrity.json). This is bounded fingerprint evidence, not an exhaustive filesystem-write audit.

Evidence root: `artifacts/simulator-build/20261001T054121Z-drift/`. Primary records: `installed/`, `source/`, `installed-analysis.json`, `source-analysis.json`, `derived/comparison.json`, `derived/trajectories.csv`, `visual-review.json`, `cleanup-review.json` and `evidence-sha256.json`. Raw artifacts remain ignored by Git. The archived `analysis-recipe.py` is an offline derivation record; the reusable live/analysis entrypoint remains `scripts/autodrive_neutral.py`. It introduces no plugin runtime dependency.

Offline reproduction, from this workspace, with a new output directory:

```bash
/tmp/roboracer-work/preflight-20260928T113745Z/avlite-venv/bin/python -B \
  artifacts/simulator-build/20261001T054121Z-drift/analysis-recipe.py \
  artifacts/simulator-build/20261001T054121Z-drift \
  /tmp/roboracer-drift-review
```

The original live command/context and exact player paths are preserved in `reproduction.json` and each `run.json`. Reproduction instructions do not authorize additional live trials.

## Status and proposed next decision

**Diagnostic study complete; SIM0-B06 unresolved.** Acceptance counts stay **2/34 original plan, 2/10 source amendment, 3/4 Linux recovery**. LNX-04, SIM0-03/04 and PRE-03/04 remain unchecked. No SIM1/S1 or RoboRacer feature implementation started. The only timing deviation was the documented polling/capture/teardown tail; the strict analysis window remains 60 seconds.

**Recommendation: authorize a separate read-only kinematics diagnostic build**, before any P0 or physics decision. This proposal is not implemented. Its concrete scope is:

| Boundary | Proposed work |
| --- | --- |
| Source/output isolation | Derive a new identified scratch copy and Linux player from the qualified authoring baseline; preserve both existing players. One opt-in diagnostic component and its metadata under `Assets/RoboRacerQualification/Diagnostics/`, with patch/provenance and build hooks in existing qualification tooling. No saved-scene or existing physics/controller/sensor/protocol changes. |
| Measurements | Log full-precision Rigidbody pose/linear and angular velocity/sleep state; root and rear-axle world/local Transform pose; current IPS value; four wheels' RPM, motor/brake torque, steering and available ground-contact force/slip. Label FixedUpdate/LateUpdate samples and engine/host-correlatable timestamps; do not call these a sensor acquisition contract. |
| Activation and containment | Explicit diagnostic startup flag only; validate unique target bindings before observation. Bound output and fail the diagnostic on missing targets, logging failure/overflow or nonfinite state. No setters that alter vehicle/physics state. Keep zero-command, encoder and 10 mm reported-position stops. |
| Build/run budget | One successful diagnostic build plus **two fresh-process, up-to-60-second source-player diagnostic windows**, using the same reviewed settings. Reuse the existing parameterized build/run tools. No additional installed-player run is proposed. Record actual cost/overhead; the previous uninstrumented build took 698.08 s, which is context, not a promised build time. |
| Review outcome | Correlate rounded IPS steps with body/child/contact state and report causal limits, instrumentation overhead, cleanup and integrity. Diagnostic completion cannot accept P0. Any physics repair, tolerance change or further experiment returns for a concrete decision. |

The named read APIs exist in the exact installed Unity 2021.3.9f1 Physics/Vehicles module documentation; [API review](../../artifacts/simulator-build/20261001T054121Z-drift/diagnostic-api-review.json). Runtime probe compilation and behavior are unverified. The extra work adds a rebuild and measurement overhead but can separate body translation from Transform/reporting effects. Repeating unchanged stock trials supplies no full-precision state; relaxing acceptance now would leave the cause unresolved.

**Confirmation is required because [the approved SIM0 scope](../planning/simulator-build-amendment.md) explicitly lists “Non-goals: instrumentation”.** The earlier approval covered the four completed stock-player observations only. This proposed narrow exception preserves P0, full-PRE-before-S1 and the separate SIM1 entry decision.
