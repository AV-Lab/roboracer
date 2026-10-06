# SIM0 — Amended P0 neutral acceptance and baseline report

Date: **2026-10-05**. Run: `20261005T052025Z-p0`.

**SIM0-03 and LNX-04 pass under the amended P0. SIM0-B06 is closed as a documented, inherited simulator characteristic, not a repaired defect.** The source-built F1TENTH player completed both fresh-process 60-second zero-command observations, with full eight-topic delivery, matching first scan/image content and clean owned-process shutdown. This report is the SIM0-04 baseline publication; **SIM0-04 is checked only after your stage review**, which is also the SIM1 entry gate.

## 1. Decision recorded

On 2026-10-05 the user selected option A ("A, go ahead"):

- **Stop the root-cause investigation of SIM0-B06.** The passive creep (~3.4 mm per 60 s along the vehicle's forward axis, zero commands/feedback/encoders) also occurs in the **unmodified installed vendor player** (3 / 4 mm reported versus 3 / 3 mm for the rebuild, [drift study](SIM0-neutral-drift.md)). It is therefore inherited AutoDRIVE/Unity vehicle behavior, not a build regression. Four diagnostic rounds ([kinematics](SIM0-kinematics.md), [contacts](SIM0-contacts.md), [Floor A/B](SIM0-floor-contacts.md), [pose review](SIM0-pose-review.md)) characterized it without changing that conclusion. It is consistent with a slip-based WheelCollider tire model that lacks true static friction, but that mechanism is **not proven**.
- **Amend the P0 position rule** from "any reported position change ends the attempt" to an **inclusive 10 mm displacement bound** from the first complete frame across the 60-second window. This is the same bound the approved diagnostic runs already used. The exact-zero command and feedback guards, the any-encoder-change guard and every other P0 requirement are **unchanged**.
- **Supersede the approved but unexecuted pose-tracing experiment** (`20261001T130821Z-pose-trace`). Its setup (derived copy, `PoseTrace.cs`, controller preview patch, 40 passing tests, API compile, host precheck) is preserved. No tracing build or run occurred.

Why the bound is adequate: the creep rate is about 0.06 mm/s, roughly five orders of magnitude below the intended racing speeds and far below the centimetre-scale localization and stopping quantities that PRE-03/04 and S1 measure. A physics "repair" would make the rebuild diverge from the vendor player, which is the reference SIM0 exists to reproduce. Any future scenario that needs a stationary-hold guarantee (for example, a long pre-start hold) must re-evaluate the creep against its own tolerance.

## 2. Execution

| Item | Value |
| --- | --- |
| Player | `/tmp/roboracer-work/autodrive-builds/native-20260929T122535Z-authoring/AutoDRIVE.x86_64` (the LNX-03/SIM0-02 qualified authoring build) |
| Player integrity | 603/603 files match the pre-drift-study hashes, both before and after the runs |
| Environment | Ubuntu 22.04, ROS 2 Humble domain 87 localhost-only, X11 `:1`, RTX 3080; existing [run context](../../artifacts/preflight/20260928T124339Z/run-context.json) |
| Tool | `scripts/autodrive_neutral.py run --profile p0-creep` (defaults: 2 runs, 60 s, 180 s startup bound, 100 ms reply delay); executed copy retained |
| UI gate | Pre-Connect screenshot visually reviewed for each run: Manual, 0.00 m/s, 0 % throttle, 0 rad steering, encoder ticks [0, 0], disconnected, Driver's Eye / Low Quality / Scene Light. PID/window/screenshot-hash-bound review allowed the Connect click only. |

## 3. Results

| Measurement | run-01 | run-02 |
| --- | ---: | ---: |
| Completed P0 observation | yes | yes |
| Observation span (s) | 60.38 | 60.43 |
| Startup to first complete observation (s) | 21.96 | 20.91 |
| Bridge frames / messages per topic (×8 topics) | 237 / 237 | 237 / 237 |
| Bridge receipt rate (Hz) | 3.901 | 3.895 |
| Receipt interval p50 / p95 / max (ms) | 254.6 / 271.0 / 286.7 | 254.2 / 274.0 / 293.2 |
| Max reported displacement (mm; bound 10) | 3 | 3 |
| Movement / encoder rejections | none | none |
| Throttle / steering replies | all `0.000` | all `0.000` |
| Scan: reported rate / length / finite ranges | 20 Hz / 1081 / 1035 | 20 Hz / 1081 / 1035 |
| Image | 1280×720 rgb8 | 1280×720 rgb8 |
| First raw scan / image equals ROS content | yes / yes | yes / yes |
| Bridge CPU (one core, mean) / max RSS | 21.7 % / 143 MiB | 21.9 % / 143 MiB |
| Child exits (bridge, observer, player) | 0, 0, 0 | 0, 0, 0 |
| Cleanup (s) / port 4567 released | 1.69 / yes | 1.54 / yes |

Reported position moved 0.741 → 0.744 m in both runs, the same direction and magnitude as the earlier drift studies. An independent pass over all 474 bridge frames confirms constant zero throttle, steering and encoder angles/ticks. The ~3.9 Hz receipt rate matches the earlier rebuilt (3.885 / 3.897 Hz) and installed (3.919 / 3.927 Hz) windows with the same 100 ms reply-delay configuration. It is a descriptive transport measurement, not a throughput threshold or acquisition rate, and the stock protocol still provides **no source acquisition timestamps**.

## 4. SIM0 baseline summary (SIM0-04 content)

| Area | Status and evidence |
| --- | --- |
| Toolchain / source | Unity 2021.3.9f1 / ad3870b89536 + Linux IL2CPP, pinned AutoDRIVE `635dbb6d`, private libssl1.1, approved Linux-host compiler package. [Startup recovery](SIM0-startup-recovery.md) |
| Material differences from upstream | Six excluded unrelated assets (+ metadata); two SketchUp tracks recovered as native meshes from the installed player; 16 + 20 scene reference remaps; OpenCAV prefab/scene quarantined and its disabled build entry removed. No physics, sensor, controller or protocol change in the qualified player. [Recovery report](SIM0-linux-recovery-attempt.md) |
| Build | Final IL2CPP build 698.08 s; strict static comparison against the installed player passed (geometry bytes, 662 transforms, 120 scripts, 87 builtin settings, materials). |
| Neutral live behavior | This report: two completed 60-second P0 observations. |
| Known characteristics | Passive forward creep ~3–4 mm/min at zero command (inherited, bounded). Existing wheel-hull and shutdown log diagnostics, matching the installed player. Front motor torque is not cleared on the zero-input branch: **review before any motion authorization** ([pose review §2](SIM0-pose-review.md)). Controller `WheelRadius` 0.0325 m versus WheelCollider 0.059 m: calibrate from measured geometry. |
| Not established | Source acquisition identity/time, receiver command expiry, stop response, scoring/truth interfaces: these are SIM1 scope. |

## 5. Verification

- Focused tool tests: **41 pass** (40 existing plus one new `p0-creep` guard test proving identical bound semantics to the diagnostic profile and a preserved encoder stop). The strict `p0` profile and the diagnostic profile are unchanged.
- Evidence: `artifacts/simulator-build/20261005T052025Z-p0/` with `approval.json`, `runs/`, `analysis.json`, `result-summary.json`, player integrity before and after, and a 42-file `evidence-sha256.json` (manifest SHA-256 `3c52ed5a9fde197d31c812b202db0eba0da66e83b2693b4d3778d75e8e92565a`).
- No owned AutoDRIVE/runner process remained after the runs.

## 6. Status and next gate

Original plan **2/34**; source amendment **3/10** (SIM0-01/02/03); Linux recovery **4/4**. SIM0-04 is ready for review. PRE-03/04 remain open and require SIM1. **Next gate: your SIM0 stage review and SIM1 entry confirmation.** No nonzero command, SIM1 instrumentation or S1 feature work has started.
