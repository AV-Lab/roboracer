# PRE — Current Qualification Status

Updated: **2026-10-05**. **Complete PRE before S1 remains confirmed.** PRE-01/02, SIM0-01–04 and LNX-01–04 accepted ([SIM0 report](SIM0-completion.md)); SIM1 entered on the user's “go on the development plan”. **SIM1-01 passes:** per-source acquisition identity, clock-offset bounds and acquisition-time ROS headers through the isolated Devkit ([English](SIM1-provenance.md) / [中文](SIM1-provenance.zh-CN.md)). **SIM1-02 passes:** a receiver guard and lease immediately before actuation reject every disarmed P1a command/clock/failure case, with legacy/manual/GUI bypasses closed and a zero-output interlock ([English](SIM1-guard.md) / [中文](SIM1-guard.zh-CN.md)). PRE-03/04 still require SIM1-03–05; no nonzero command has reached the controller (rejected fault-injection values and ignored legacy-bypass probes only).

## Reports and evidence

- [Approved read-only pose review](SIM0-pose-review.md) / [中文报告](SIM0-pose-review.zh-CN.md), run `20261001T114229Z-pose-review`: source/compiled bindings, four retained-trace derivations, causal map and ranked hypotheses. No new build/live run; next statement-level experiment is proposed, not approved.

- [Approved Floor-only A/B result](SIM0-floor-contacts.md) / [中文报告](SIM0-floor-contacts.zh-CN.md), run `20261001T102325Z-floor`: one build, two controls, two treatments, 35 focused tests, verified filtering and unchanged baseline. Drift persists; no P0 acceptance.

- [Approved contact controls and blocked treatment](SIM0-contacts.md) / [中文报告](SIM0-contacts.zh-CN.md), run `20261001T073103Z-contacts`: one build, two controls, failed treatment gate, 29 focused tests, unchanged prior evidence. No B trial or P0 acceptance.

- [Approved full-precision diagnosis](SIM0-kinematics.md) / [中文报告](SIM0-kinematics.zh-CN.md), run `20261001T060743Z-kinematics`: two completed diagnostic windows, verified body drift and braking, preserved logging-cap failure/corrective build, 18 focused tests and baseline integrity. P0 remains incomplete; the subsequently approved contact study is recorded above.

- [Approved passive-drift comparison](SIM0-neutral-drift.md) / [中文报告](SIM0-neutral-drift.zh-CN.md), run `20261001T054121Z-drift`: four diagnostic windows, monotonic reported drift in both players, eight-topic/content review, unchanged files and clean process exit. No P0 acceptance; its kinematics follow-up was subsequently approved and completed in the newer report.
- [Approved Linux recovery and neutral blocker](SIM0-linux-recovery-attempt.md) / [中文报告](SIM0-linux-recovery-attempt.zh-CN.md), run `20260929T122535Z`: independently regenerated assets, 698.08-second final build, complete strict static comparison, verified live data conversion, preserved UI failures and position-guard termination. No completed 60-second observations.
- [Linux-only feasibility and bounded recovery proposal](../planning/linux-asset-recovery.md) / [中文报告](../planning/linux-asset-recovery.zh-CN.md), run `20260929T102620Z`: independent track attribute decoding, render/collider identity, material/texture-source review and exact proposed scene/OpenCAV changes. Read-only investigation completed; its bounded implementation was subsequently approved.
- [Approved isolation result and Linux SketchUp blocker](SIM0-sketchup-blocker.md) / [中文报告](SIM0-sketchup-blocker.zh-CN.md), run `20260929T100424Z`: separate preserved checkout, 364.43-second import, unchanged 276 dependency paths/552 hashes, actual required-track object failure, and three recovery choices.
- [Initial import review and proposed recovery](SIM0-import-review.md) / [中文报告](SIM0-import-review.zh-CN.md), run `20260929T085557Z`: 389.49-second first import, retained asset failures, unchanged F1TENTH/project settings and a 276-dependency Unity audit. Historical proposal subsequently confirmed and applied; the newer model audit identifies SIM0-B03.
- [Verified Editor startup recovery](SIM0-startup-recovery.md) / [中文报告](SIM0-startup-recovery.zh-CN.md), run `20260929T085557Z`: Hub/project verification, retained compiler-host failure, signed private dependency and successful 22.34-second fresh batch startup. SIM0-B01 resolved; SIM0-01 accepted. Source build and neutral runs remain separate requirements.
- [Hub template-loading recovery](SIM0-template-loading.md) / [中文报告](SIM0-template-loading.zh-CN.md), run `20260929T084707Z`: reproduced Hub's rejection of the lowercase `unity-` installation-folder prefix and corrected the scratch layout. The later startup recovery report verifies recovery; this entry preserves the earlier attempt.
- Decision history only: [S1a/deferral proposal — not adopted](../planning/installed-binary-first-amendment.md) / [中文说明](SIM1-deferral.zh-CN.md). Its four proposed tasks are inactive, not completed.
- [Current option A feasibility report](PRE-option-A-feasibility.md) / [中文报告](PRE-option-A-feasibility.zh-CN.md), run `20260929T051932Z`: source/interface inventory, pinned editor/package availability, host compatibility risk and a [reviewable implementation amendment](../planning/simulator-build-amendment.md).
- [Continuous interface report](PRE-interface-qualification.md) / [中文报告](PRE-interface-qualification.zh-CN.md), run `20260928T124339Z`: continuous neutral telemetry, corrected Devkit lifecycle, static Reset, installed geometry and capability options.
- [Permission recovery](PRE-permission-recheck.md), run `20260928T120809Z`: isolated installs, host GPU/display/DDS, one passive frame and recorded-sensor transfer.
- [Initial attempt](PRE-initial-attempt.md), run `20260928T113745Z`: historical access failures and pinned sources. Its policy/status statements describe that attempt.
- Latest live [measurements](../../artifacts/preflight/20260928T124339Z/neutral-analysis.json), [corrected runtime](../../artifacts/preflight/20260928T124339Z/cached-tf/neutral-run.json); current [preparation results](../../artifacts/preflight/20260929T051932Z/result-summary.json) and [integrity](../../artifacts/preflight/20260929T051932Z/post-preparation-integrity.json).

## Verified outcomes and limits

| Area | Verified | Remaining boundary |
| --- | --- | --- |
| AVLite/dependencies | Isolated AVLite 0.6.3/NumPy 2.2.6; Humble Devkit/NumPy 1.26.4; recorded narrow Python 3.10 overlay and colcon builds. | No RoboRacer plugin acceptance. Stock Devkit without adaptations is not qualified. |
| Live transport | Two bounded attempts, each with 120 zero-feedback frames; every one of eight ROS topics received 120 messages per attempt. | Manual mode only; no autonomous control or braking. |
| Corrected lifecycle | TF publisher count fixed at 10; simulator, observer and bridge all exited 0 and were reaped. | Earlier TF growth/SIGKILL/observer failure retained; no long-duration leak-free claim. |
| Timing | Corrected receipt rates 6.494/6.382 Hz; maximum measured interval 176.25 ms. | No acquisition timestamp/sequence or simulator clock. Reported 20 Hz is not verified acquisition throughput. |
| Reset/display | Two owned-window static Reset/reconnect trials; sensor-producing Vulkan display. | No motion-clearance/reset proof, five-start setup or unattended batch acceptance. |
| Geometry | Installed Proto active/Berlin inactive; 18 collider meshes extracted, actual mass/wheel radius/transforms recorded. | Full frame/calibration/contact/off-track/lap scoring remains unqualified. |
| Source/toolchain acquisition | Complete pinned source: 9,422 tracked files / 6,868,307,583 bytes; exact Editor/module and fresh empty-project batch compilation/exit verified. Private authenticated libssl1.1 resolves the reproduced compiler dependency failure. | Native-track recovery and the source build are now accepted under their scoped amendment; P0 runtime acceptance is blocked by SIM0-B06. The Ubuntu 22.04 documented-host gap remains. |
| Integrity/cleanup | Three source-repository states and nine selected simulator hashes unchanged; all owned PIDs absent, local 4567 released. | Unity's shared temporary graphics cache remains; no exhaustive write-isolation claim. |

**Original plan: 2 accepted and 32 unchecked todos. Source-build amendment: SIM0-01/02 accepted and eight unchecked.** Prior access/Devkit blockers retain their recorded resolution. SIM0-B06 is the current neutral-run blocker; PRE-B05 remains the numerical-motion hold, and PRE-B07–09 remain for SIM1 qualification.

## Confirmed direction and next prerequisite

The existing evidence cannot establish source acquisition freshness or receiver-side command expiry; requested scene controls/scoring are also incomplete. The approved plan requires these capabilities and explicitly distinguishes process containment from braking.

After reviewing the source-build route and the optional deferral, the user instructed continuation of the original full-PRE-first sequence. Continue scoped SIM0 toolchain/baseline qualification under [amendment 1.1-A](../planning/simulator-build-amendment.md); SIM1 follows its predecessor's report and explicit stage-entry confirmation. Complete the required timing, downstream expiry/stop, geometry/scoring and motion qualification before entering S1. S1a is not an active stage and cannot bypass PRE-03/04.

The native-track build/static work and approved diagnostic/review scopes have reached their documented outcomes; P0 remains incomplete. Floor filtering did not remove drift. The latest read-only review proposes one statement-level tracing experiment with its exact scope in the current report. Await that separate confirmation before any instrumentation/build/live run. Preserve full PRE and SIM1’s explicit entry gate.
