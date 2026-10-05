# SIM0 — Full-Precision Neutral-Drift Diagnosis

Date: **2026-10-01**. Study: `20261001T060743Z-kinematics`. [中文报告](SIM0-kinematics.zh-CN.md). Predecessor: [four-window passive-drift comparison](SIM0-neutral-drift.md).

**Subsequent authorization:** the user's next “yes” approved the contact A/B scope proposed at the end of this report. The isolated study is `20261001T073103Z-contacts`; its [approval record](../../artifacts/simulator-build/20261001T073103Z-contacts/approval.json) preserves the exact boundary. Historical results and frozen evidence below remain unchanged. This does not authorize P0 acceptance, production adoption, SIM1 or S1.

**The two approved diagnostic windows completed. The simulated Rigidbody itself moved by 3.437 / 3.259 mm in Unity Z during the exact 60-second windows. Rear-axle motion closely follows the body; its local offset stays fixed. Stock position reports show 4 / 3 mm steps in mapped X. This establishes body drift in the instrumented simulator, beyond decimal formatting or an independently moving sensor child. It does not identify the solver/contact cause or establish real-car behavior. SIM0-B06 remains open; P0, SIM0 and PRE have not passed.**

## Authorization, implementation and retained failure

The user's **“yes”** approved the preceding report's narrow SIM0 exception: an isolated, opt-in, read-only kinematics build and two fresh-process observations of up to 60 seconds, retaining the diagnostic 10 mm reported-position cap and unchanged P0. [Approval record](../../artifacts/simulator-build/20261001T060743Z-kinematics/approval.json).

The existing build/run/analysis entrypoints now support this explicit diagnostic. One component records body/root/rear-axle pose, linear/angular velocity, sleep state, IPS, and four wheels' RPM, torque, steering and available ground-hit force/slip. It validates unique bindings, finite values, same-host Linux CLOCK_MONOTONIC, PID and heartbeat. It changes no vehicle/physics/sensor setting. The component is inactive without its explicit startup flag; the inactive branch is fixture-tested, not a separate live uninstrumented-player trial. Full-precision means preserving the engine's existing float values, not increasing physics precision.

**A logging-capacity defect required a corrective build.** The qualified scene already uses a **0.001 s physics timestep**. The initial **64 MiB** cap filled after **29.582 s**, at about **2.269 MB/s**, before Connect or any observation window. The player exited 17; the parent contained and reaped all three processes in **0.592 s**. The retained trace has **30,799 samples / 67,107,720 bytes**. It is a failed pre-connection launch, not a completed trial or causal baseline.

The cap was corrected to **1 GiB per process**, with the same **300 s** logging lifetime, full sampling, physics timestep and motion guards. A second isolated derived project/output preserved the first project, player and failure. The builds succeeded in **253.361 / 248.366 s**, respectively. This is a deviation from the proposed one-build budget: **one extra corrective build and one failed pre-connection launch; the two approved observation windows were not expanded**. The cap failure and both source versions remain in the evidence. A wrong analysis interpreter initially lacked NumPy; the existing qualified mixed environment resolved that without an installation. [Failure and correction](../../artifacts/simulator-build/20261001T060743Z-kinematics/logging-cap-failure.json).

## Build and source verification

Both derived projects use source commit `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`, Editor **2021.3.9f1 / ad3870b89536**, the already qualified private native dependency and Linux IL2CPP path. The corrective player contains **604 files / 1,514,442,513 bytes**. Each copy reused an independently copied Library cache; these incremental builds do not replace the preceding clean-import qualification.

All **9,404 existing Assets/Packages/ProjectSettings files** in the corrective project are byte-identical to the qualified authoring baseline. Only the diagnostic C# file, its metadata and directory metadata were added; the existing tracked diff is unchanged. The strict serialized comparison passes for **18 mesh-collider records, 662 transforms, recorded builtin settings, 120 script instances, track geometry/channel metadata and resolved asset mappings**. This is bounded static equivalence, not a dynamic-equivalence claim. [Source review](../../artifacts/simulator-build/20261001T060743Z-kinematics/source-delta-review-logging-fix.json), [player comparison](../../artifacts/simulator-build/20261001T060743Z-kinematics/player-inspection-logging-fix/comparison.json).

The corrected build retains **42 existing C# warning occurrences**, **2 shader warnings**, an optional TestRunner assembly warning, the already present missing-access-token diagnostic followed by valid-license confirmation, and a debugger-listener message during successful Editor shutdown. Allocation statistics are retained separately. No unclassified reviewed diagnostic pattern remains. The broader debugger review completed after player launch but before Connect. No build-exit-only acceptance is claimed. [Build review](../../artifacts/simulator-build/20261001T060743Z-kinematics/build-logging-fix/diagnostic-review.json).

## Observation method and results

Both runs used Ubuntu 22.04, ROS 2 Humble domain 87, localhost `127.0.0.1:4567`, RTX 3080/Vulkan, display `:1`, 1280×720, and **Manual / Driver's Eye / Low Quality / Scene Light**. Each fresh process received a separately inspected, PID/window/screenshot-bound Connect action. No reset, recentering, nonzero command or mode change occurred. The Devkit and AVLite environments remained separate; zero replies retained the 0.1 s delay.

The observation starts at the later of first complete bridge processing and first complete eight-topic ROS observation. Analysis selects exactly the next **60 s** on the shared host monotonic clock. The live guard remains referenced to the first raw position and stops at reported displacement **≥10 mm**, any encoder change, nonzero/nonfinite command/feedback, malformed data or child/probe failure. This cap is diagnostic containment, not P0 tolerance, braking or a real-time physical bound.

Startup is also retained. From the first probe sample to the first in-window sample, body Y changes about **−5.799 mm**, and Z changes **1.099 / 2.692 mm**, over **20.478 / 46.926 s**. These are endpoint differences, not startup maxima. The 10 mm stock-message guard does not cover physics before the first received frame. No extra settling period was introduced; startup includes the separate screenshot review. [Startup endpoints](../../artifacts/simulator-build/20261001T060743Z-kinematics/startup-motion-review.json).

| Measurement | Run 01 | Run 02 |
| --- | ---: | ---: |
| Actual elapsed observation, including polling (s) | 60.077677 | 60.029604 |
| Rigidbody Z change, exact window (mm) | 3.437042 | 3.259420 |
| Rear-axle Z change, exact window (mm) | 3.436923 | 3.259301 |
| Body Z fitted drift (mm/s) | 0.056790 | 0.054779 |
| Raw stock X first → last (m) | 0.741 → 0.745 | 0.743 → 0.746 |
| Maximum reported displacement (mm) | 4 | 3 |
| FixedUpdate / LateUpdate samples, exact window | 60,003 / 3,474 | 59,999 / 3,394 |
| Raw frames in exact window / total | 235 / 238 | 232 / 234 |
| Messages received on **each** of eight topics | 238 | 234 |
| Completed diagnostic / completed P0 | Yes / No | Yes / No |

![Run 01 body, axle and reported position](../../artifacts/simulator-build/20261001T060743Z-kinematics/plots/run-01.png)

[Run 02 plot](../../artifacts/simulator-build/20261001T060743Z-kinematics/plots/run-02.png). Plot curves use their own first in-window sample; different quantization offsets are expected. The plotted body and axle overlap at this scale. Raw reported Y/Z remain **3.158 / 0.059 m**. FixedUpdate body X is unchanged and body Y spans less than **0.000708 mm**. Neither callback phase observed the body sleeping.

The rear-axle local position remains exactly constant in both phases. FixedUpdate IPS equals the mapped current axle position `(Unity z, −Unity x, Unity y)` in every selected sample. Root/body differences are below **0.000260 mm per coordinate** across both phases; LateUpdate IPS/axle differences are below **0.000358 mm per coordinate**. These effects are far smaller than the accumulated drift. All **235 / 232** in-window stock positions match rounded full-precision IPS somewhere within a ±0.5 s receipt neighborhood. This content comparison does **not** identify the precise acquisition sample.

The probe executes after the vendor scripts at order 30000 versus 0. FixedUpdate runs before the subsequent physics step; LateUpdate provides a separate view. It does not expose internal solver substeps. [Unity 2021.3 execution order](https://docs.unity3d.com/2021.3/Documentation/Manual/ExecutionOrder.html), accessed 2026-10-01; local ordering evidence in [sampling reference](../../artifacts/simulator-build/20261001T060743Z-kinematics/sampling-phase-reference.json).

## What the wheel and velocity evidence establishes

For **all selected samples in both phases and both runs**, all four wheels report:

- motor torque **0 Nm**, RPM **0**, steering **0°**;
- brake torque **85.599998474 Nm** and grounded state true;
- forward/sideways slip **0** as returned by WheelCollider's API.

FixedUpdate ground-force ranges across the two runs are approximately **7.307–7.337 N** front-left, **7.296–7.318 N** front-right, **8.084–8.106 N** rear-left and **8.065–8.095 N** rear-right. These measurements verify the actual zero-input brake path. They do not establish that every vehicle collider is slip-free or that zero encoder ticks imply a stationary body.

The body Z positions change in multiples of **5.96046448×10⁻⁸ m**. Steps range from −1 to +3 such increments and include reversals; the fine trajectory is not strictly monotonic even though rounded stock X increases monotonically. Sampled Z velocity is much smaller than the position-derived drift: integrating the pre-step samples with the recorded fixed interval yields about **0.010226 / 0.010228 mm**, versus **3.437 / 3.259 mm** position change. A calculation using body pose and the source's serialized center of mass gives essentially the same Z displacement. That COM calculation assumes the source assignment remains current; runtime COM was not independently sampled. The velocity sum is descriptive, not an identity for the internal solver or a proof of a particular defect.

**Verified:** body position changes, sensor local offset is fixed, the zero/brake path is active, and fine state continues evolving. **Design judgment:** inspect compound-collider contact and position-update behavior next. **Unverified:** which contact or numerical mechanism causes the drift, its response to load/track/commands, and whether any repair preserves useful racing dynamics.

Static inspection finds four enabled convex MeshColliders at `F1TENTH/Vehicle/{FL,FR,RL,RR} Wheel/Collider`, alongside the four actuator WheelColliders. `VehicleController.UpdateWheelPose` updates their parent wheel transforms each physics callback. The detailed `Wheel-N-solid1` MeshColliders named in the convex-hull warnings are **disabled**; the warning alone cannot identify the cause. The current ground-hit fields do not identify the compound MeshCollider contact pairs. [Collider inventory](../../artifacts/simulator-build/20261001T060743Z-kinematics/read-only-contact-inventory.json), [source/API review](../../artifacts/simulator-build/20261001T060743Z-kinematics/next-contact-proposal-evidence.json).

## Transport, cost and cleanup

| Measurement | Run 01 | Run 02 |
| --- | ---: | ---: |
| Exact-window bridge receipt rate (Hz) | 3.9259 | 3.8691 |
| Receipt gap p95 / maximum (ms) | 270.68 / 277.66 | 277.78 / 310.22 |
| Last-topic receipt age at deadline, min–max (ms) | 233.65–243.53 | 136.01–146.46 |
| Player startup to complete observation (s) | 25.422 | 51.315 |
| Cleanup (s) | 1.645 | 1.745 |
| Total probe samples, including startup/cleanup | 84,879 | 113,051 |
| Trace bytes | 184,810,392 | 246,140,387 |
| Measured sample cost, mean / maximum (ms) | 0.102513 / 5.390063 | 0.103146 / 12.777487 |
| Flush cost, mean / maximum (ms) | 0.073121 / 0.148135 | 0.075470 / 0.160951 |
| Player CPU, % of one core / peak sampled RSS (MiB) | 117.81 / 731.91 | 117.25 / 733.61 |
| Bridge CPU / RSS (MiB) | 20.52 / 142.19 | 15.90 / 142.48 |
| Observer CPU / RSS (MiB) | 3.77 / 64.55 | 2.95 / 67.79 |

Capture/serialization/buffered-write costs sum to approximately **10.78% / 10.89%** of total trace wall time; this excludes initialization, status-file writes, separate flushes and scheduling effects. Logging produced **2.290 / 2.299 MB/s**. These are substantial diagnostic costs. Previous uninstrumented source runs measured **107.86% / 109.75%** player CPU, but different startup ages/workloads and two sequential trials do not support a controlled overhead estimate or performance equivalence. Resource windows include startup; GPU memory and whole-host cost were not measured. Display screenshots show 58 / 56 Hz at completion, not a sustained frame-rate benchmark.

Each run's first **1081-range** scan (1035 finite ranges) and **1280×720 RGB** image match a ROS message after the reviewed conversion. The complete raw IPS sequence equals the ROS sequence; all recorded actuator/encoder fields and emitted commands remain zero. All topics continue arriving. Reported LiDAR metadata remains 20 Hz; receipt rate does not establish acquisition frequency.

Polling exceeded the nominal window by **77.677 / 29.604 ms**. Final raw receipts extend **265.480 / 119.916 ms** beyond the deadline during capture/cleanup. Fixed-window metrics exclude these tails. No deliberate observation extension or late re-zeroing was used.

The completed trials' six children exited 0, were reaped, and are absent; port 4567 has no listener. The three children from the cap failure are also reaped/absent, with the failed player exit 17 preserved. Each successful player log retains four hull warnings, two shutdown socket errors and **2 / 1** ThreadAbort diagnostics. The bridge retains two ROS QoS deprecations. No unclassified reviewed runtime pattern remains; this is not an error-free-log claim. [Runtime review](../../artifacts/simulator-build/20261001T060743Z-kinematics/runtime-diagnostic-review.json), [cleanup](../../artifacts/simulator-build/20261001T060743Z-kinematics/cleanup-review.json).

## Engineering evidence and reproduction

**18 focused tests pass:** 11 runner/guard tests, 5 tests compiling/executing the actual C# probe against a mock Unity fixture, and 2 synthetic offline-analysis tests. The first 16 completed in **2.488 s** reported test time; the retained final analysis test run took **0.105 s**. The C# fixture verifies serialization, inactive-by-default behavior and failure paths, not physics. Separate exact-engine API compilation and the two actual players establish the exercised engine compatibility. Original P0/zero/encoder/bridge/observer guard functions retain their prior AST. An offline unclosed-file ResourceWarning was corrected before the retained final check; no failed required test was waived.

Post-run integrity matches **9 selected installed files, all 603 baseline player files, both 604-file diagnostic players, all 9,404 existing source/settings files in the baseline and corrected copy, the 3 diagnostic additions, 3 runtime configuration/bridge files and 3 reference repository states**. Both prior frozen manifests also match: **434 + 108 files**. This is bounded fingerprint evidence, not a whole-filesystem audit. [Integrity](../../artifacts/simulator-build/20261001T060743Z-kinematics/post-run-integrity.json).

Evidence root: `artifacts/simulator-build/20261001T060743Z-kinematics/`. The failed `neutral/` and successful `neutral-logging-fix/` are distinct. Initial and corrected executed sources are retained in separate snapshots; raw logs/traces remain ignored by Git. The final `evidence-sha256.json` freezes this study. The study-specific `analysis-review.py` is retained for independent derivation; reusable tooling remains in `scripts/`.

Offline reproduction from this workspace, using fresh outputs:

```bash
/tmp/roboracer-work/preflight-20260928T113745Z/avlite-venv/bin/python -B \
  scripts/autodrive_neutral.py analyze \
  --results artifacts/simulator-build/20261001T060743Z-kinematics/neutral-logging-fix \
  --analysis-output /tmp/roboracer-kinematics-review.json \
  --plot-directory /tmp/roboracer-kinematics-review-plots
```

Actual build/run commands, paths and dependencies are retained in `reproduction.json`, each build-result and each run record. These instructions authorize no further live experiment.

## Status and next decision

**Diagnostic study complete; underlying SIM0-B06 unresolved.** Acceptance stays **2/34 original plan, 2/10 source amendment, 3/4 Linux recovery**. LNX-04, SIM0-03/04 and PRE-03/04 stay unchecked. No SIM1/S1 or RoboRacer feature implementation has begun.

**Historical next-scope proposal: one isolated contact A/B diagnostic, subsequently approved.** See the [contact outcome](SIM0-contacts.md): two controls completed and the declared gate stopped B. The original proposal is retained below. This would test the specific wheel-MeshCollider interaction hypothesis, without adopting a physics repair:

| Boundary | Proposed experiment |
| --- | --- |
| Isolation and build | One new derived diagnostic build; preserve every current player/source/evidence set. Add explicit contact-observation and treatment flags to the existing parameterized tools. No saved-scene, package, controller or AVLite core edit. |
| Added observation | Record actual collider pair identities, contact points/normals/separation, aggregate collision impulse, wheel ground-hit collider identity, body COM/inertia and pose/state. Validate exact bindings and bounded output. Collision callbacks require live verification; sleeping bodies do not emit stay callbacks, so absence alone is not evidence of no contact. [Unity API](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/MonoBehaviour.OnCollisionStay.html), accessed 2026-10-01. |
| Control A | Two fresh-process, zero-command, up-to-60-second windows with all existing contacts enabled and the extra read-only logging. Confirm whether the four named wheel MeshColliders contact `Infrastructure/Proto Track`. If target contact identity cannot be established, stop before B and report the evidence. |
| Treatment B | Only after that gate: two fresh-process windows using pair-specific `Physics.IgnoreCollision` for those four MeshColliders against the one verified Proto Track MeshCollider. Activate only after complete zero telemetry establishes the existing first-frame guard reference, at the beginning of the timed window; record application time and do not re-zero after filtering. Keep the actuator WheelColliders and every collider enabled; no inertia/COM/mass, friction, brake, timestep, sleep, pose or constraint setter. Verify unchanged actual mass/COM/inertia and the intended ignored-pair state. |
| Containment and budget | At most four windows total, same first-frame reference, 10 mm cap, exact-zero and encoder guards, Manual mode, owned cleanup and bounded logging. No extra installed-player runs, repeated-until-pass search or nonzero command. Record startup-age and instrumentation differences; no invented performance target. |
| Outcome | Compare body drift, velocity, contacts, grounded state, settings and overhead. Mixed/unchanged results remain inconclusive. Do not automatically promote B, mark P0 complete or change acceptance. Return with a repair/no-repair recommendation and its validation needs. |

Pair filtering is preferable here to disabling the wheel meshes because attached colliders can affect automatically calculated inertia. Actual inertia must still be checked. [Unity inertia documentation](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Rigidbody-inertiaTensor.html), accessed 2026-10-01. The exact installed PhysicsModule XML documents `IgnoreCollision`, its readback and contact APIs; two web API pages were inaccessible and are recorded as such, not claimed as read. The Proto MeshCollider combines track surfaces: B would ignore those wheel-mesh pairs against the **whole track collider**, not selectively against its floor triangles. That altered response is confined to the bounded passive diagnostic and is not qualified for racing.

Benefit: a causal intervention with a matching instrumented control. Cost: one more build, contact tooling and up to four windows; the latest 248.366 s build is context, not a promised duration. Risks: contact filtering can alter support behavior or produce an early guard stop; instrumentation and startup differences can confound small effects. Preserve failures and report those limits. A lower-impact alternative is contact logging alone, but it cannot establish the effect of removing a contact pair. Revising P0 to tolerate observed drift would change acceptance while leaving the physical model unresolved and is not recommended from this evidence alone.

**Confirmation is required because the approved [read-only scope](SIM0-neutral-drift.md#status-and-proposed-next-decision) permits no existing physics-state changes and returns any further experiment for a concrete decision. The proposed pair filtering changes collision behavior and exceeds the completed two-window budget.** P0 and the full-PRE-before-S1 sequence remain unchanged.
