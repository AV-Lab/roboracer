# SIM0 — Approved Floor-only contact A/B diagnostic

**Subsequent status:** the user approved the read-only review proposed below; its completed [English report](SIM0-pose-review.md) now records the current decision. This document and its frozen evidence preserve the Floor A/B result; its final review-approval request is historical.

Date: **2026-10-01**. Run: `20261001T102325Z-floor`. **The approved diagnostic is complete; SIM0/PRE is still blocked by SIM0-B06.**

**Result.** Filtering the four verified wheel-mesh/Floor pairs removed their post-activation contact points, but body drift remained **3.372 / 3.414 mm** in the two treatments, compared with **3.431 / 3.413 mm** in the controls. All four 60-second windows completed under the unchanged zero-command/encoder/10 mm diagnostic guards. This does not support adopting the filter as a repair. No P0 qualification trial or SIM1/S1 work was started.

The two-run mean is **3.422320 mm control versus 3.392994 mm treatment**, a descriptive difference of **−0.029325 mm (−0.857%)**. Two sequential runs per condition, natural state variation and different logging loads do not establish a reliable improvement or equivalence margin. Drift persists even when the selected mesh contacts are absent. The internal cause remains unknown.

![Four fresh-process body trajectories](../../artifacts/simulator-build/20261001T102325Z-floor/floor-comparison.png)

The figure displays approximately 10 Hz samples; endpoint metrics use all recorded FixedUpdate samples. Curves use individual first-window positions only for display. The live guard retained its first raw telemetry reference throughout. [SVG figure](../../artifacts/simulator-build/20261001T102325Z-floor/floor-comparison.svg), [derived comparison](../../artifacts/simulator-build/20261001T102325Z-floor/comparison-summary.json).

**Authorization and implementation.** The user's “approve” accepted the revised proposal in the [previous contact report](SIM0-contacts.md). The scope was one isolated build, two fresh controls and at most two fresh treatment windows, each up to 60 seconds. The target changed explicitly from Proto Track to the enabled, static, nontrigger `Floor` BoxCollider. Time-constant inertia was replaced, with approval, by exact mass/COM/inertia/rotation equality immediately before and after filtering in the same callback. Both modes still require stable mass/COM after acknowledgment; the control gate also checks the whole window and matching control mass/COM. No mass, COM or inertia setter is used. [Approval](../../artifacts/simulator-build/20261001T102325Z-floor/approval.json), [approved text](../../artifacts/simulator-build/20261001T102325Z-floor/approved-proposal.md), [protocol](../../artifacts/simulator-build/20261001T102325Z-floor/protocol.json).

The existing build/run/analysis tools now accept an explicit Floor profile. Schema-2 bindings, target-bound requests, selected-player hashes and raw-control fingerprints prevent the earlier Proto Track gate from authorizing Floor treatment. Treatment only calls `Physics.IgnoreCollision` on the four named `F1TENTH/Vehicle/{FL,FR,RL,RR} Wheel/Collider` MeshColliders against Floor. Actuator WheelColliders and collider enabled states remain unchanged. The default player path is inactive without diagnostic flags; the legacy Proto Track policy remains available for historical reproduction.

The new project independently copies the qualified authoring baseline and the preceding diagnostic's Library cache. This is an incremental diagnostic build, not a new clean-import qualification. Pinned source: `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`; Unity **2021.3.9f1 / ad3870b89536**. The build finished in **257.388 s**, producing **605 files / 1,515,088,364 bytes**. Final comparison preserves all **9,404 existing source files**, with only seven diagnostic additions. Serialized comparison matches all 18 collider meshes, 662 transforms, 120 script instances, settings and asset mappings. No AVLite core, vendor controller, scene, sensor, brake, friction, timestep, sleep, pose or constraint change was introduced. [Build](../../artifacts/simulator-build/20261001T102325Z-floor/build/build-result.json), [source review](../../artifacts/simulator-build/20261001T102325Z-floor/source-delta-review.json), [player comparison](../../artifacts/simulator-build/20261001T102325Z-floor/player-inspection/comparison.json).

**Gate and intervention evidence.** Both controls passed the revised Floor gate before either treatment launched. Each run used a fresh player/bridge/observer set and a separate PID/window/screenshot-bound Connect review. The parent requested the window only after complete zero telemetry and all eight ROS topics were observed. Filtering was acknowledged **181.821 / 180.937 ms** after the treatment windows began, with no reference reset. Exact before/after property snapshots match in all four runs. [Gate](../../artifacts/simulator-build/20261001T102325Z-floor/control-gate.json), [main-agent pre-treatment review](../../artifacts/simulator-build/20261001T102325Z-floor/control-review-before-treatment.json).

| Contact measurement | Control 01 | Control 02 | Treatment 01 | Treatment 02 |
| --- | ---: | ---: | ---: | ---: |
| Points for each wheel-mesh/Floor pair, entire window | 239,776 | 239,880 | 768 | 752 |
| Points for each pair after acknowledgment | 239,452 | 238,992 | **0** | **0** |
| Stay callbacks in window | 239,776 | 239,880 | 768 | 752 |
| Exit callbacks in window | 0 | 0 | 4 | 4 |
| Nonzero recorded aggregate impulses | 0 | 0 | 0 | 0 |
| Grounded actuator-wheel samples | 100% | 100% | 100% | 100% |

Treatment points occur before filtering; four subsequent exit callbacks have no contact points. Counts are repeated solver reports, not independent impacts. All WheelCollider ground-hit identities still resolve to Floor. The body never reports sleeping; throttle, steering, motor torque, wheel RPM and raw encoders remain zero. Braking remains **85.599998474 Nm per wheel**. No stop, traction or real-car capability is inferred from those observations. Independent streaming analysis verifies phase counts, body deltas, contact counts, pair-filter states and the complete raw/ROS IPS sequences. [Independent evidence](../../artifacts/simulator-build/20261001T102325Z-floor/independent-analysis.json).

**Motion and properties.** Measurements use the exact observation interval in the host monotonic clock. Unity position/velocity axes and units are retained; the main displacement is Unity body Z, corresponding to the recorded IPS X trend.

| Measurement | Control 01 | Control 02 | Treatment 01 | Treatment 02 |
| --- | ---: | ---: | ---: | ---: |
| Body Z change (mm) | 3.431439 | 3.413200 | 3.372014 | 3.413975 |
| Fitted Z drift (mm/s) | 0.056731 | 0.056418 | 0.055830 | 0.056411 |
| Maximum stock-reported displacement (mm) | 4 | 4 | 3 | 4 |
| Window acknowledgment delay (ms) | 121.409 | 230.543 | 181.821 | 180.937 |
| Post-acknowledgment body Z change (mm) | 3.426313 | 3.399491 | 3.359377 | 3.401279 |
| Post-acknowledgment sampled span (s) | 59.876944 | 59.766912 | 59.817590 | 59.818633 |
| Distinct inertia tensors in window | 996 | 988 | 988 | 989 |
| Fixed simulation-time span (s) | 59.943003 | 59.968003 | 60.002003 | 59.992003 |

Mass remains exactly **3.4700000286102295 kg**, and local COM remains `[-7.999999797903001e-05, 0.0643400028347969, -0.004679999779909849] m`. Principal inertia and its rotation still evolve in both modes. Across the four FixedUpdate windows the component ranges are approximately `[0.093603849411, 0.093603990972]`, `[0.100271269679, 0.100271448493]`, and `[0.022816695273, 0.022816764191] kg·m²`. These ranges are observations, not approved tolerances. Exact per-run ranges and snapshots remain in the analysis files.

Sampled body speed has a median of approximately **0.0308–0.0310 mm/s**; sampled Z velocity is much smaller than the fitted Z position drift (Z bounds across runs approximately **−0.003137 to +0.001696 mm/s**). This makes the pose-update/sampling/constraint-correction path a useful follow-up lead. These callback observations do not expose every internal solver operation and do not establish the cause. Vendor wheel-transform updates and naturally changing inertia remain candidates for review, not diagnosed defects.

**Environment, transport and measurement cost.** Ubuntu 22.04, Humble/domain 87/localhost-only DDS, RTX 3080/Vulkan, display `:1`, 1280×720, Manual / Driver's Eye / Low Quality / Scene Light, localhost `127.0.0.1:4567`, existing 1 ms physics step and 100 ms zero-reply delay were retained. Order was A1, A2, B1, B2; there was no randomization or exposed seed control. No new dependency installation was needed. Raw trials and source/configuration fingerprints identify the actual environment.

| Measurement | Control 01 | Control 02 | Treatment 01 | Treatment 02 |
| --- | ---: | ---: | ---: | ---: |
| Raw frames in window / whole run | 237 / 240 | 236 / 239 | 235 / 237 | 235 / 238 |
| In-window receipt rate (Hz) | 3.9604 | 3.9419 | 3.9165 | 3.9232 |
| Receipt gap p95 / max (ms) | 267.59 / 342.68 | 271.74 / 343.88 | 273.31 / 287.73 | 271.62 / 287.37 |
| Last-topic age at deadline, min–max (ms) | 202.46–212.43 | 214.43–224.02 | 89.79–100.13 | 197.68–206.81 |
| Startup to observation (s) | 25.513 | 27.492 | 34.717 | 27.483 |
| Polling beyond deadline (ms) | 106.131 | 104.835 | 6.375 | 106.407 |
| Last raw frame after deadline (ms) | 269.176 | 292.452 | 153.477 | 304.773 |
| Cleanup (s) | 1.644 | 1.645 | 1.595 | 1.644 |
| Combined trace size (MB, decimal) | 546.259 | 565.490 | 375.038 | 327.504 |
| Full-trace logging rate (MB/s) | 6.757 | 6.779 | 4.150 | 3.923 |
| Measured callback cost / trace wall time (%) | 30.05 | 29.46 | 18.86 | 17.93 |
| Player CPU (% of one core) | 134.06 | 134.58 | 126.03 | 125.38 |
| Peak sampled player RSS (MiB) | 735.49 | 735.82 | 737.62 | 736.46 |

All eight topics received the whole-run counts shown above. First scans contain 1081 ranges (1035 finite), and first 1280×720 RGB images match the ROS conversions. Invalid/infinite scan values are retained as observed; this is not a claim that all ranges are finite. Stock scan metadata remains 20 Hz; receipt rates are not source acquisition rates. Deadline metrics exclude cleanup-tail messages. The first raw position reference also excludes earlier unconnected startup physics; the guard is a rounded-telemetry containment check, not a continuous physical displacement bound.

Removing contacts reduces trace volume and measured callback cost. Callback cost excludes initialization, status writes, separately recorded flushes and scheduling effects; CPU/RSS includes startup. GPU memory and whole-host load were not measured. The different instrumentation cost and LateUpdate counts limit causal isolation. There was no workload-equalized or uninstrumented treatment run. Detailed cost, receipt-age, startup and sampling records are retained in [control analysis](../../artifacts/simulator-build/20261001T102325Z-floor/control-analysis.json), [treatment analysis](../../artifacts/simulator-build/20261001T102325Z-floor/treatment-analysis.json), and [comparison](../../artifacts/simulator-build/20261001T102325Z-floor/comparison-summary.json).

**Validation and integrity.** Thirty-five focused tests passed in **3.146 s reported test time**, including actual-C# fixture tests for the exact Floor binding, four setter calls, wrong target rejection, immediate inertia faults, later mass/COM faults and permitted natural inertia evolution. Pinned-engine API compilation passed. Fixtures validate contracts and faults, not Unity physics. The first pre-build test run exposed analyzer variable shadowing; its failure is retained and the corrected suite passed before the one live build. There was no extra build, live retry or substituted condition. [Tests](../../artifacts/simulator-build/20261001T102325Z-floor/focused-tests.json), [initial failure](../../artifacts/simulator-build/20261001T102325Z-floor/focused-tests-initial.log), [API compile](../../artifacts/simulator-build/20261001T102325Z-floor/api-compile.json), [unchanged guard ASTs](../../artifacts/simulator-build/20261001T102325Z-floor/guard-source-review.json).

All twelve trial children exited 0 and were reaped; the editor and all twelve PIDs are absent in the host check, and port 4567 is free. Each player log retains four existing wheel-hull warnings, two shutdown socket errors and two ThreadAbort records; each bridge retains two ROS QoS deprecations. Build review retains the existing 42 C# warning occurrences, two shader warnings, optional TestRunner and licensing/debugger diagnostics. No unclassified reviewed runtime/build pattern remains. [Cleanup](../../artifacts/simulator-build/20261001T102325Z-floor/cleanup-review.json), [runtime log review](../../artifacts/simulator-build/20261001T102325Z-floor/runtime-diagnostic-review.json), [build log review](../../artifacts/simulator-build/20261001T102325Z-floor/build/diagnostic-review.json).

Post-run integrity passes for the selected installed files, baseline and all previous/current diagnostic players, existing baseline/diagnostic source, runtime files and three reference repository states. All **434 + 108 + 145 + 139** previously frozen evidence files still match. This is a listed-file/repository-state audit, not a whole-host audit. [Integrity](../../artifacts/simulator-build/20261001T102325Z-floor/post-run-integrity.json). Executed sources, failed tests, raw trials, screenshots, analysis helpers and document snapshots stay with the evidence; large logs/binaries remain outside source version control. The final `evidence-sha256.json` freezes this study.

**Reproduction.** The common runner handles both conditions through configuration. Exact build/live arguments and limits are retained in [reproduction metadata](../../artifacts/simulator-build/20261001T102325Z-floor/reproduction.json); new live runs require a separate decision. Offline analysis can be repeated with fresh destinations:

```bash
/tmp/roboracer-work/preflight-20260928T113745Z/avlite-venv/bin/python -B \
  scripts/autodrive_neutral.py analyze \
  --results artifacts/simulator-build/20261001T102325Z-floor/treatment \
  --analysis-output /tmp/roboracer-floor-treatment-review.json \
  --plot-directory /tmp/roboracer-floor-treatment-review-plots
```

For controls, replace `treatment` with `control` and optionally add `--contact-gate-output <fresh-file>`. The archived source snapshot pins this analysis version. Study-only independent derivation and plotting helpers are retained for audit; they are not production dependencies.

**Status and next decision.** The bounded diagnostic delivered its comparison. **P0/SIM0/PRE acceptance has not passed**; SIM0-B06 remains open, and original/source-amendment/Linux-recovery counts remain **2/34, 2/10, 3/4**. LNX-04, SIM0-03/04 and PRE-03/04 remain unchecked. Full PRE before S1 remains required. The stock/qualified baseline and independent hardware stopping requirement are unchanged.

**Recommendation:** do not adopt the Floor filter. Before another intervention, perform one bounded **read-only source-and-retained-trace review** of (1) body/root/compound-collider pose writes and synchronization, (2) WheelCollider support and zero-input controller order, and (3) position/velocity/inertia timing and numerical resolution. Deliver a source-linked causal map, ranked hypotheses, and at most one falsifiable next experiment proposal. Use existing files/traces and official pinned-version documentation only; no new build, simulator launch, physics edit, acceptance waiver or S1 work. The review may narrow the uncertainty without identifying a complete cause. Any new live experiment would need its own concrete scope and confirmation.

Per the user's stage-completion gate, work stops here pending confirmation of that next review. No further experiment is automatically authorized.
