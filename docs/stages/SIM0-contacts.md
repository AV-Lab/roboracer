# SIM0 — Contact Controls and Treatment Gate

Date: **2026-10-01**. Study: `20261001T073103Z-contacts`. Predecessor: [full-precision drift diagnosis](SIM0-kinematics.md).

**Subsequent execution:** the Floor-only proposal below was approved with “approve” and completed as [a separate A/B study](SIM0-floor-contacts.md). Both treatments ran after the revised gate passed; filtering removed contacts but did not resolve drift. This report and its frozen evidence preserve the earlier stop-before-B checkpoint.

**Both approved 60-second controls completed. Treatment B was blocked by the declared gate and was not launched. The four wheel meshes contact a separate `Floor` BoxCollider, not the proposed `Infrastructure/Proto Track` target in the recorded windows. Actual inertia also varies slightly without intervention. Body drift remains 3.411 / 3.392 mm. No physics repair was adopted; P0, SIM0 and PRE remain incomplete.**

## Scope and gate outcome

The user's **“yes”** approved the preceding report's bounded contact A/B proposal: one isolated diagnostic build, two fresh controls, and at most two treatment windows only after verifying the four named wheel-MeshCollider/Proto-Track pairs. The same zero-command/encoder guards, first-raw-frame position reference and inclusive **10 mm reported-displacement cap** applied. No reset or re-zero was authorized. [Approval](../../artifacts/simulator-build/20261001T073103Z-contacts/approval.json), [exact approved proposal](../../artifacts/simulator-build/20261001T073103Z-contacts/approved-proposal.md).

The [control gate](../../artifacts/simulator-build/20261001T073103Z-contacts/control-gate.json) is **ineligible**, with two substantive findings:

1. Neither control recorded any of the four required wheel-mesh/Proto-Track pairs. Recorded body collision callbacks instead identify the four wheel meshes against `Floor`. All four actuator WheelColliders also report `Floor` as their ground-hit collider.
2. Mass and center of mass are constant, but actual inertia tensor/principal-axis rotation are not exactly constant over a window, and the two controls' window-acknowledgment snapshots differ. The implemented constant-inertia prerequisite therefore also fails.

The proposal's target was an unverified hypothesis. Live evidence corrects that hypothesis; it does not authorize silently substituting `Floor`. The constant-inertia requirement was a conservative diagnostic design assumption that these controls disprove. It is **not** evidence that our intervention changed inertia: no intervention ran. The gate was preserved rather than relaxed. A direct offline check of the actual gate rejects treatment before launch; no treatment result directory exists. [Gate review](../../artifacts/simulator-build/20261001T073103Z-contacts/treatment-gate-review.json).

## Delivered diagnostic capability and build verification

The existing parameterized build/run/analyze tools now support optional contact logging and a separately gated treatment path. `ContactProbe` and `ContactRelay` supplement `KinematicsProbe`; no AVLite core, vendor controller, saved scene, package, physics or sensor configuration changed. Their default runtime path remains inactive without explicit diagnostic flags.

The logger records collider identity/type/path, contact point/normal/separation, aggregate collision impulse, wheel ground-hit identity, and actual body mass/COM/inertia. It validates bindings, finite values, sequence/count/byte integrity and bounded output. The unchanged scene uses a **0.001 s physics timestep**. Combined motion/contact logs are limited to **1 GiB per process**, and probe lifetime remains 300 seconds.

The parent writes a fresh PID/mode/monotonic-time-bound window request only after complete bridge and eight-topic observations. Control acknowledges without a physics setter; the unexecuted treatment path would filter only the declared four pairs. Requests older than three seconds, wrong bindings/PIDs/modes, changed requests, missing heartbeat and incorrect ignored-pair states fail. Control acknowledgments occurred **99.815 / 118.722 ms** after observation start. No reference was reset at acknowledgment.

One incremental Linux IL2CPP build succeeded in **259.351 s**, with **605 output files / 1,515,025,645 bytes**, using commit `635dbb6d86ec98e25ea845a97188f7bbe85a09e8` and Unity **2021.3.9f1 / ad3870b89536**. The extra output filename versus the previous diagnostic is a generated `Assembly-CSharp2.cpp` backup. The independently copied Library cache is recorded; this is not a clean-import rerun.

All **9,404 existing Assets/Packages/ProjectSettings files** and the pre-existing tracked diff match the qualified authoring baseline. Additions are exactly three diagnostic C# files, their metadata and directory metadata: **seven files**. The final serialized comparison passes for **18 mesh-collider records, 662 transforms, recorded builtin settings, 120 script instances, track geometry and resolved asset mappings**. Static equality does not establish dynamic equivalence. [Source comparison](../../artifacts/simulator-build/20261001T073103Z-contacts/source-delta-review.json), [player comparison](../../artifacts/simulator-build/20261001T073103Z-contacts/player-inspection/comparison.json).

Build diagnostics retain **42 existing C# warning occurrences, two shader warnings, an optional TestRunner warning, the existing access-token diagnostic and an Editor shutdown debugger-listener message**. Each was reviewed before live launch; no unclassified reviewed pattern remains. [Build review](../../artifacts/simulator-build/20261001T073103Z-contacts/build/diagnostic-review.json).

## Measurements and interpretation

Both fresh processes used Ubuntu 22.04, ROS 2 Humble/domain 87, localhost `127.0.0.1:4567`, RTX 3080/Vulkan, display `:1`, 1280×720, and **Manual / Driver's Eye / Low Quality / Scene Light**. Each received a separate PID/window/screenshot-bound Connect action. Zero replies retain the 0.1 s delay. No random seed was set; no seed control is exposed by this diagnostic. Version, configuration and process identity are retained.

Metrics select the exact 60 seconds after the later of first complete bridge processing and first complete eight-topic observation. The live motion guard still uses the **first raw position**, including the earlier reference. It is a rounded-telemetry containment check, not a continuous physical bound or stopping-distance measurement.

| Measurement | Control 01 | Control 02 |
| --- | ---: | ---: |
| Body Z change, FixedUpdate (mm) | 3.411353 | 3.392398 |
| Rear-axle Z change (mm) | 3.411293 | 3.392398 |
| Fitted body drift (mm/s) | 0.056350 | 0.055943 |
| Maximum stock-reported displacement (mm) | 4 | 3 |
| FixedUpdate / LateUpdate samples in window | 59,998 / 3,187 | 59,977 / 3,131 |
| In-window stay callbacks | 239,988 | 239,912 |
| Recorded points for **each** wheel mesh ↔ Floor pair | 239,988 | 239,912 |
| Recorded points for **each** wheel mesh ↔ Proto Track pair | 0 | 0 |
| Nonzero aggregate collision impulses in window | 0 | 0 |
| Distinct sampled inertia tensors in window | 987 | 983 |
| Messages received on **each** of eight topics, entire run | 239 | 240 |
| Completed diagnostic / completed P0 | Yes / No | Yes / No |

![Control 01 body and reported drift](../../artifacts/simulator-build/20261001T073103Z-contacts/control-plots/run-01.png)

[Control 02 plot](../../artifacts/simulator-build/20261001T073103Z-contacts/control-plots/run-02.png). Plot series use independent first-window sample origins; this is not source acquisition synchronization.

Every selected sample in both callback phases has zero throttle, steering, wheel RPM and motor torque; all wheels are grounded with **85.599998474 Nm brake torque**. Rear-axle local position is fixed, and the body never reports sleeping. Wheel ground-hit IDs resolve to the enabled, nontrigger `Floor` BoxCollider. Contact IDs are process-local; hierarchy/type binding, not repeated numeric ID values, establishes identity.

Each observed wheel-mesh/Floor pair contributes four contact points per stay callback. Counts are repeated solver reports, not independent impacts or collision incidents. All recorded in-window aggregate impulses are **zero**. Separations remain positive, approximately **3.842–6.864 mm**, and normals are nearly Unity +Y. This does not prove penetration, load sharing, or that these meshes drive the observed drift. Unity documents that contacts can be generated while colliders are separated within their contact offsets; live per-collider offsets and internal solver steps were not measured. [Unity 2021.3 contact offset](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Collider-contactOffset.html), accessed 2026-10-01.

Mass is exactly **3.4700000286102295 kg** in the sampled state. COM remains `[-0.000079999998, 0.064340002835, -0.004679999780] m` in body coordinates. Across the two FixedUpdate windows, principal inertia components lie within:

| Component | Minimum (kg·m²) | Maximum (kg·m²) |
| --- | ---: | ---: |
| I₁ | 0.093603849411 | 0.093603990972 |
| I₂ | 0.100271269679 | 0.100271448493 |
| I₃ | 0.022816697136 | 0.022816764191 |

The largest component span is about **1.788×10⁻⁷ kg·m²**; inertia rotation varies as well. These are small recorded variations, not a proposed allowable tolerance. The vendor controller updates wheel-parent poses every FixedUpdate from `GetWorldPose`. Unity documents automatic inertia calculation from attached colliders unless set by script. That combination motivates an inertia/compound-collider hypothesis; it does not establish why the values change or whether they cause drift. [Source/API evidence](../../artifacts/simulator-build/20261001T073103Z-contacts/source-and-api-review.json), [Unity 2021.3 inertia tensor](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Rigidbody-inertiaTensor.html), accessed 2026-10-01.

## Transport, instrumentation cost and cleanup

| Measurement | Control 01 | Control 02 |
| --- | ---: | ---: |
| In-window raw frames / receipt rate (Hz) | 237 / 3.9508 | 237 / 3.9595 |
| Receipt gap p95 / maximum (ms) | 274.58 / 301.64 | 270.33 / 302.77 |
| Last-topic receipt age at deadline, min–max (ms) | 112.72–122.20 | 214.47–225.17 |
| Player startup to complete observation (s) | 28.886 | 33.182 |
| Polling beyond deadline (ms) | 70.875 | 40.632 |
| Cleanup (s) | 1.644 | 1.644 |
| Combined trace bytes, including startup/cleanup | 569,563,651 | 602,344,659 |
| Logging rate over full trace (MB/s) | 6.763 | 6.782 |
| Measured motion + contact callback cost / trace wall time | 29.63% | 29.05% |
| Motion sample cost mean / maximum (ms) | 0.122681 / 60.552 | 0.119634 / 47.892 |
| Contact callback cost mean / maximum (ms) | 0.042150 / 6.786 | 0.041298 / 36.388 |
| Player CPU (% of one core) / peak sampled RSS (MiB) | 138.24 / 724.35 | 135.29 / 737.39 |

Logging overhead is substantial. Callback measurements exclude initialization, status writes, separately measured flushes and scheduling effects. Process metrics include startup; GPU memory and whole-host load were not measured. Completion screenshots show 56 / 50 FPS, not sustained frame-rate results. Similar drift to the preceding study does not demonstrate zero instrumentation effect.

First 1081-range scans and 1280×720 RGB images match their ROS conversions; the complete raw/ROS IPS sequences match. All actuator/encoder records remain zero. Actual receipt rate is not the reported 20 Hz LiDAR acquisition rate. Last raw frames arrive **127.560 / 267.469 ms after** the nominal deadline during capture/cleanup; fixed-window metrics exclude them. [Main analysis](../../artifacts/simulator-build/20261001T073103Z-contacts/control-analysis.json), [independent derivation](../../artifacts/simulator-build/20261001T073103Z-contacts/independent-analysis.json), [exact-window timing](../../artifacts/simulator-build/20261001T073103Z-contacts/window-timing-review.json).

Before the window, the first-to-first-in-window body Y changes approximately −5.799 mm and Z changes **1.324 / 1.618 mm** over **24.025 / 28.612 s** of probe sampling. No artificial settling interval was added. Physics before first raw telemetry remains outside the stock position guard.

All six owned children exited 0, were reaped and are absent at the host check; port 4567 is released. Both player logs retain four existing detailed-wheel hull warnings and two shutdown socket errors; ThreadAbort counts are **1 / 2**. Each bridge log retains two ROS QoS deprecations. No unclassified reviewed runtime pattern remains. [Cleanup](../../artifacts/simulator-build/20261001T073103Z-contacts/cleanup-review.json), [runtime review](../../artifacts/simulator-build/20261001T073103Z-contacts/runtime-diagnostic-review.json).

## Engineering checks, deviations and reproduction

**29 focused tests passed in 6.553 s reported test time:** 11 runner/guard tests, nine actual-C# fixture tests, two synthetic kinematics-analysis tests and seven contact-evidence tests. Exact-engine API compilation also passed. Fixture tests verify serialization, opt-in behavior, request timing/PID rejection, bounded logs, exact pair-setter calls and fault handling; they do not simulate physics. The live controls validate the observation path. **The treatment's live behavior remains unverified.** [Test evidence](../../artifacts/simulator-build/20261001T073103Z-contacts/focused-tests.json), [API compile](../../artifacts/simulator-build/20261001T073103Z-contacts/api-compile.json).

Post-run integrity passes for nine selected installed files, all 603 baseline player files, both prior 604-file diagnostic players, this 605-file player, 9,404 existing files in each of the baseline/new projects, seven additions, three runtime files, and three reference repository states. All **434 + 108 + 145** previously frozen evidence files match. [Integrity](../../artifacts/simulator-build/20261001T073103Z-contacts/post-run-integrity.json).

There was **no extra build, live retry or treatment substitution**. Provisional checks and offline corrections are retained: a premature during-build source check counted Unity's temporary StreamingAssets files, and a provisional player inspection ran before build completion. Fresh post-build checks passed after Unity removed the temporary source files; the provisional records are not acceptance evidence. The study-only independent analysis initially used an incorrect IPS field and failed before output; the corrected offline rerun passed. A subsequent timing review separated the mislabelled post-cleanup message-age field from actual deadline age; the earlier output is retained, and the corrected derivation agrees with `window-timing-review.json`. None of these corrections changed raw trials, gate criteria or P0.

Evidence root: `artifacts/simulator-build/20261001T073103Z-contacts/`. Executed sources, raw traces, screenshots, bounded reviews, reproduction parameters and failed/provisional checks remain separate. Large results are ignored by Git. `evidence-sha256.json` freezes the study. Study-only derivation/integrity scripts are retained with evidence; reusable tools remain in `scripts/`.

Offline reproduction, using fresh destinations:

```bash
/tmp/roboracer-work/preflight-20260928T113745Z/avlite-venv/bin/python -B \
  scripts/autodrive_neutral.py analyze \
  --results artifacts/simulator-build/20261001T073103Z-contacts/control \
  --analysis-output /tmp/roboracer-contact-review.json \
  --plot-directory /tmp/roboracer-contact-review-plots \
  --contact-gate-output /tmp/roboracer-contact-review-gate.json
```

## Status and proposed next decision

**The approved diagnostic reached its stop-before-B outcome. It is not a completed A/B comparison or a SIM0/PRE pass.** Counts remain **2/34 original plan, 2/10 source amendment, 3/4 Linux recovery**. SIM0-B06 remains open; LNX-04, SIM0-03/04 and PRE-03/04 remain unchecked. SIM1/S1 have not started.

**Recommendation, pending confirmation: one revised Floor-only A/B diagnostic.** Its purpose is to exclude or support a contribution from the actually observed wheel-mesh/Floor interaction. Zero reported impulses reduce the evidence for a direct force explanation, so improvement is not promised. It would require two explicit changes to the current experiment:

| Decision | Proposed scope |
| --- | --- |
| Actual target | Bind exactly the four named wheel MeshColliders against the verified enabled, static, nontrigger **`Floor` BoxCollider**. Never use a name-only wildcard or filter actuator WheelColliders. |
| Inertia check | Replace the disproved **time-constant inertia** prerequisite with an **immediate before/after pair-filter check** within the same callback, requiring exact equality of mass/COM/inertia/rotation across the setter operation. Keep mass/COM constant over each window; record naturally evolving inertia and compare its ranges/time series descriptively. No inertia/COM/mass setter or reset. This is a proposed diagnostic-criterion change, not an adopted waiver or P0 change. |
| Budget and matching control | One new isolated build; two fresh matching controls, then at most two fresh treatment windows after their Floor-contact/transport/binding checks. Up to 60 seconds each. Preserve every previous build/trial; no repeated-until-pass search. |
| Intervention and containment | Apply only four pair filters after complete zero telemetry establishes the existing reference. Record application time, never re-zero. Keep colliders enabled, unchanged actuator/brake/friction/timestep/sleep/pose/constraints and the same zero/encoder/10 mm guards. Unexpected immediate property change or guard failure terminates the attempt. |
| Outcome | Report drift, velocity, ground support, impulses, inertia evolution and instrumentation costs. Natural inertia differences limit isolation; mixed/unchanged results remain inconclusive. No automatic repair adoption, P0 acceptance or SIM1/S1 entry. |

Benefit: test the correct observed contact pairs with matching controls. Cost: another build, revised binding/check fixtures and up to four windows with substantial logs. Risk: removing a contact pair can alter support or drift even though reported control impulses are zero; zero impulse does not expose every solver operation. A lower-risk alternative is additional read-only wheel-transform/inertia sampling, but that still cannot measure the effect of removing the pair. Freezing inertia, disabling colliders or accepting P0 drift would introduce different interventions/acceptance changes and is outside this recommendation.

**Confirmation is required by the approved stop condition, “If target contact identity cannot be established, stop before B and report the evidence,” and by the user's boundary on changes affecting safety/acceptance.** The corrected target and revised inertia check exceed the experiment just completed. Neither is implemented. Full PRE before S1 remains unchanged.
