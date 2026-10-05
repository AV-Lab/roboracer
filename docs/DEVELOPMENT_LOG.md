# Development Log

## 2026-09-28 — Research

- Verified repository identities, branch/worktree states and project conventions. Preserved all existing AVLite/A2RL changes. The RoboRacer workspace is writable for documentation but has no valid Git repository.
- Reviewed the official plugin guide, critical AVLite integration source, bounded A2RL patterns, official RoboRacer resources, event-specific rules and simulator alternatives. Main-agent source checks reviewed delegated findings.
- Recommended a native modular map-based plugin, with a reactive baseline, deterministic Gym evaluation and a ROS driver boundary, conditional on target event/hardware confirmation. No core API change or feature implementation started.
- Identified guide/source discrepancies in settings, sensor fields, localization gating and lifecycle assumptions; prepared a bounded runtime probe. It has not been authorized or run.
- Evidence: [research report](research/report.md), [source register](research/source-register.md), [local inventory](research/evidence/local-inventory.json), [remote refs](research/evidence/remote-refs.txt), [validation request](research/validation-request.md).
- Artifact review: local links and Markdown fences checked; proposed probe parsed for syntax only. AVLite target/reference and A2RL Git statuses match the recorded inventory. These are documentation checks, not software acceptance results.
- Limits: source clone retrieval was blocked; remote source snapshots cannot be matched conclusively to advertised refs. No simulator installation, interface run, closed loop, benchmark or hardware validation.
- Next gate: user confirms competition category, hardware/environment assumptions, technical direction and optional probe. Development planning then requires two substantive review rounds and explicit final approval before implementation.

## 2026-09-28 — Research translation

- Added the full [Simplified Chinese report](research/report.zh-CN.md) at the user's request, with reciprocal navigation to the English report. The main agent reviewed the delegated translation sections against the original.
- Verified all 12 sections, 125 table rows, 84 original link targets, inline-code occurrences, commit hashes, decision IDs and Mermaid structure. Local links resolve and code fences are balanced. These are translation/documentation checks only; see [artifact review](research/evidence/artifact-review.md).
- No research conclusions, pending decisions or authorization status changed. No simulator installation, runtime probe, benchmark or plugin implementation was performed for this translation. The technical-direction gate remains open.

## 2026-09-28 — Research decisions and planning round 1

- Recorded the user's selection of physical racing, B, current Humble, official Build hardware reference, labelled early GT, independent hardware stop and eventual private GitHub hosting. Initial multi-car/release scope remains under review.
- Followed the official Build link to the Master BOM (updated 2026-05-15); documented its newer reference and discrepancies with static assembly/driver examples. Hardware calibration and actual onboard performance remain unverified.
- Executed the unchanged, explicitly approved isolated AVLite probe once. Reviewed source identity, profile round trip, datatype fields, missing bridge method, localization gate and partial registry cleanup. Exit 0 is limited to that probe; no simulator, ROS node, GUI, dependency installation or vehicle command was involved. Evidence: [decision follow-up](research/decision-follow-up.md) and [run record](research/evidence/avlite-contract-probe.run.json).
- Observed that the workspace is now a valid `main` repository at `0bf647f8be823c9d6cfa00954297c7a8202f0e26`, with no remote; the agent did not initialize or commit it. Existing AVLite/A2RL source changes were preserved.
- Prepared [development plan v0.1](planning/development-plan.md) for the first substantive review: feature stages, unchecked todos, proposed measurement protocols and baseline-dependent threshold gates. Added current-status navigation to both research-report languages.
- Independent plan review led to explicit baseline → threshold approval → acceptance ordering and a proposed separate ROS command supervisor for publisher failure. Documentation/provenance checks passed: links/fences, 34 unique unchecked todos, unchanged probe hash and unchanged AVLite/A2RL source statuses. These checks do not establish feature acceptance.
- Next gate: review release scope, localization/command choices and stage boundaries. Then revise for review 2 of todos, acceptance, permission needs and risks; explicit final-plan approval is still required before implementation.

## 2026-09-28 — Existing AutoDRIVE inventory

- Inspected the user-supplied `/home/a2rl/Workspace/AutoDRIVE Simulator [Linux]` read-only. Confirmed x86-64 application files, execute permission, F1TENTH scene markers and a Unity 2021.3.9f1 marker; recorded selected file hashes. The engine marker does not identify the AutoDRIVE release.
- Recorded [findings and integration limits](research/autodrive-local-installation.md) with [static evidence](research/evidence/autodrive-local-inventory.json). Exact release/Devkit, headless/GPU behavior, ROS/API operation and closed-loop performance remain unverified.
- Updated both research-report languages and plan v0.1.1. Existing AutoDRIVE is a candidate for complementary validation; no route change or additional release backend was adopted. No simulator launch, configuration change, dependency installation or feature implementation occurred.
- Next gate remains planning review 1. A simulator runtime check requires an approved scope; the earlier authorization covered the isolated AVLite contract probe only.

## 2026-09-28 — Planning revision: AutoDRIVE first

- Applied the user's request to revise the simulator direction in [plan v0.2](planning/development-plan.md): the existing AutoDRIVE installation is the first closed-loop backend; Gym is a later candidate with no mandatory first-release dependency or acceptance.
- Moved Humble/Devkit integration and command supervision into S1. S2 now delivers unattended episodes, recording and fault recovery. Replaced Gym-specific step/seed/map/opponent assumptions with local capability gates and distinct live versus recorded-input measurements.
- Revisited localization tradeoffs without silently changing the estimator proposal: native PF versus AMCL remains a review decision, and the former ROS-free-loop rationale no longer applies. Physical racing, B, Humble and independent hardware stop remain fixed inputs.
- Updated the decision follow-up, AutoDRIVE inspection implications and current-status notes in both research-report languages. Historical evidence and original findings remain intact.
- Reviewed delegated timing/lifecycle findings directly against AVLite source and incorporated atomic snapshots, original command freshness, valid localization, actual control intervals and disarm-before-reset requirements. No simulator, ROS node, dependency installation or plugin implementation was run for this revision.
- Documentation checks passed: local links/fences/whitespace, 34 unique unchecked todos, unchanged probe hash and unchanged AVLite/A2RL source identities/statuses. Evidence: `docs/research/evidence/artifact-review.md`. These checks are not feature acceptance.
- Next gate: review remaining scope/estimator/contracts and the revised todos, acceptance, permission scope and risks; obtain explicit final-plan approval before implementation. The request to revise documents does not approve simulator execution.

## 2026-09-28 — Planning revision: approved ICP reuse and release constraints

- Recorded the user's decisions: dynamic obstacles/multi-car are not mandatory release-1 acceptance; reuse/extend built-in ICP; imported maps/reference paths, initial Pure Pursuit, target-speed/steering and independent command supervision are approved design inputs.
- Updated plan v0.3 and both report-language status notes. Replaced the proposed PF/AMCL implementation choice with a bounded plugin-level ICP extension, and replaced mandatory traffic scenarios with a static-obstacle stage whose exact behavior remains under review.
- Kept the source limitation explicit: stock ICP uses a first-scan reference and does not consume the declared occupancy-map input. Full-map matching, quality/loss behavior and the exact reuse seam require qualification; no core modification, runtime test or feature implementation occurred.
- Asked three focused questions on the first-release physical-delivery boundary, static avoidance versus stopping, and ICP manual initialization/recovery versus automatic global recovery. Routine naming and the already-required baseline-before-threshold policy do not need repeated approval.
- Independently checked delegated review findings and clarified stack-velocity ownership and detectable-initialization limits. Documentation checks passed: links/fences/whitespace, 34 unique unchecked todos, unchanged source-repository states and unchanged probe hash; evidence is in `docs/research/evidence/artifact-review.md`. These are not feature acceptance results.
- Next gate: incorporate those answers, then finalize concrete stage acceptance and runtime-validation scope for further review. Explicit final-plan approval remains pending.

## 2026-09-28 — Planning revision: delivery/recovery decisions and acceptance protocol

- Recorded acceptance of all three recommendations: simulation-only first-release delivery; avoidance of passable static obstacles and stopping at full blockage; operator/configuration initial pose with stop/manual recovery after detected localization loss.
- Updated plan v0.4, the decision record and both report-language status notes. Separated healthy unattended batch initialization from terminal localization-loss handling; resets cannot hide a failed episode or count as automatic recovery.
- Made the acceptance proposal concrete: left-pass/right-pass/blocked static cases, per-stage repetition counts, five 120-second timing windows after separate 10-second warm-up, and held-out-case accounting. These are proposed measurement procedures, not performance results or numerical acceptance thresholds.
- Asked focused questions on minimum layout/initial-condition coverage and whether unattended runs may use a graphical session or virtual display. Exact simulator capabilities remain for engineering verification.
- Documentation checks passed: 173 local links, fences/whitespace, 34 unique unchecked todos and tracked-diff whitespace. Checked run-count arithmetic and the distinction between experiment duration and performance thresholds; evidence is in `docs/research/evidence/artifact-review.md`.
- No simulator, ROS process, dependency installation, new runtime probe or feature implementation was executed. Next gate: incorporate the remaining acceptance choices, then submit the complete plan and bounded qualification/permission scope for final review.

## 2026-09-28 — Planning final-review candidate v1.0

- Recorded the final two scope answers: one qualified track, five reproducible initial conditions and left-pass/right-pass/fully-blocked static cases; graphical or virtual-display unattended operation allowed. All R2 preference questions are resolved.
- Consolidated the full plan and a concise approval summary: five feature stages, 34 unchecked todos, 100 M3 A/B episodes, 30 M4 static episodes and 10 additional M5 held-out episodes, with separate baseline, fault, timing and regression protocols. Counts are proposed acceptance coverage, not test results.
- Reviewed the delegated audit against AVLite source. Required identical qualified ICP/motion-state inputs for M3 A/B, retained the independent supervisor with complementary downstream expiry, and fixed episode success/failure/horizon accounting. Clarified stock Pure Pursuit acceleration versus the approved target-speed payload and standard GUI/profile conformance checks.
- Separated the requested PRE + S1 authorization from a numerical pre-motion protocol and later baseline-derived performance thresholds/stage-entry approvals. No core change, runtime execution, installation, vehicle access or publishing occurred.
- Updated current-status notes in both research-report languages and the decision record. Final document/repository checks are recorded in `docs/research/evidence/artifact-review.md`; all implementation todos remain unchecked.
- Next gate: explicit approval of v1.0 and its scoped PRE + S1 work. Scope-question answers alone do not meet the user's required final-plan approval gate.

## 2026-09-28 — PRE: approved entry, runtime checks and environment blockers

- Recorded the user's explicit v1.0/PRE + S1 approval. Preserved the numerical pre-motion and later stage-entry gates. Added artifact-ignore rules; all implementation todos remain unchecked because PRE acceptance is incomplete.
- Verified writable workspace/scratch/result paths and unchanged source repositories/nine selected simulator fingerprints. Pinned official historical Simulator 0.3.0 (`635dbb6d`) and Devkit 0.3.0 (`4abf7cd8`) in sparse scratch checkouts; source/API compatibility remains a hypothesis requiring live validation.
- Created a clean Python 3.10 venv and pinned AVLite source snapshot. The environment rejected `pypi.org` access during pip bootstrap; AVLite dependency installation did not complete. No alternative download route or shared-environment change was attempted.
- Executed one owned 15.08-second Unity startup with null graphics and no control input. Observed isolated preferences and engine identity, plus rendering/socket errors; terminated/reaped the process. This is startup evidence only, with no sensor/API/closed-loop claim.
- System Humble imports and LaserScan serialization passed. Corrected a disposable probe's topic-name error and retained both attempts; the valid cross-process DDS check failed with 20 publication calls, zero receptions and denied interface enumeration. X11 connection was denied and NVIDIA access failed in this execution environment.
- Evidence and recovery requirements: `docs/stages/PRE.md`, `artifacts/preflight/20260928T113745Z/`. No simulator installation, core/source-repository edit, plugin feature code, physical actuation or publishing occurred. Next action is an execution-environment/access change, then resumption of the failed preflight checks and disarmed API qualification.

## 2026-09-28 — PRE: permission recovery and passive API qualification

- Resumed under available per-command approval. Sandbox PyPI denial persisted; explicitly approved host downloads completed isolated AVLite 0.6.3/NumPy 2.2.6 and a separate NumPy 1.26.4 protocol/conversion environment. Final packaging checks passed; reports and freezes retained.
- Host RTX 3080/X11 and local Humble DDS worked. Owned graphical AutoDRIVE startup/shutdown passed; a receive-only loopback Socket.IO probe captured one real telemetry frame after enabling Connect, with Manual mode retained and no actuator reply. This is single-frame evidence, not measured continuous sensing or a closed loop.
- Recorded 1081-range LiDAR and 1280×720 RGB messages crossed DDS from the NumPy 1 process to the NumPy 2 process importing AVLite; payload bytes matched. Native image conversion passed only in the compatible NumPy 1 environment. Historical attrdict failed on Python 3.10; combined NumPy 2/cv_bridge qualification failed and remains explicitly recorded.
- Re-ran the unchanged AVLite contract probe in the fresh environment; import/profile checks passed. Verified owned child cleanup, port release and unchanged three source repositories/nine selected simulator fingerprints. PRE-01 accepted; other 33 todos remain unchecked. No S1 feature code or motion command.
- Evidence: [recheck report](stages/PRE-permission-recheck.md), `artifacts/preflight/20260928T120809Z/`. Next: bounded Devkit adaptation, continuous disarmed sensing and stop/scene/scoring qualification, then concrete motion limits for confirmation. The original plan approval remains valid.

## 2026-09-28 — PRE: continuous neutral interface and capability blockers

- Qualified the pinned historical F1TENTH Devkit in isolated Humble/Python 3.10 using recorded attrdict/loopback adaptations and colcon builds. Both bounded Manual-mode attempts exchanged 120 all-zero-feedback frames and delivered 120 messages on each of eight topics to an AVLite/NumPy 2 observer. First-frame scan/RGB content comparisons passed.
- Reproduced TF publisher growth (20→1329) and shutdown failures. A disposable cached-broadcaster/gevent-lifecycle overlay passed the follow-up: publisher count 10→10, all child exits 0. Recorded receipt rates 6.494/6.382 Hz; these short stationary samples are not acquisition-rate or performance acceptance. Kept initial failures and differing pacing configurations explicit.
- Verified two static GUI Reset/reconnect trials and read-only installed collider/script extraction. Recorded actual 0.059 m wheel-collider radius, 0.330/0.331 m geometry separations and historical-source discrepancies; did not implement maps/scoring or infer controller calibration from untyped fields.
- PRE-02 accepted; PRE-03/04 remain blocked by acquisition identity/time, receiver expiry/stop, full scoring/scenario qualification and the motion gate. Asked the user to choose a concrete capability route; recommended preparing a separate instrumented AutoDRIVE build, with no such build/acceptance change adopted yet.
- Evidence: [English report](stages/PRE-interface-qualification.md), [Chinese report](stages/PRE-interface-qualification.zh-CN.md), `artifacts/preflight/20260928T124339Z/`. Three source-repository states and nine selected simulator hashes unchanged; all owned PIDs absent and 4567 released. No motion, S1 feature implementation, physical actuation or publication occurred.

## 2026-09-29 — PRE: confirmed option A source/toolchain preparation

- Recorded the user's selection of option A preparation. Preserved physical-racing strategy B, v1.0 acceptance, independent supervision/hardware stop and the numerical motion gate. No editor installation, activation or instrumentation is inferred from that preparation choice.
- Retrieved all 223 tracked C# files, the F1TENTH scene, project/package settings and metadata into a clean pinned inspection worktree. Identified actual acquisition/actuation/reset hooks, package/vendor dependencies and the encoder's hardcoded conversion discrepancy. Full asset closure/import/build remain unverified.
- Verified official Unity 2021.3.9f1 editor/Linux IL2CPP archive HEAD responses and selected pinned package metadata using scoped approved host access. Recorded sandbox denials, an interrupted inefficient partial-clone size inventory and GitHub API rate limiting. Found no local editor; recorded the Ubuntu 22.04 versus documented 2021.3 host-support gap. Asked only for the user's activation/build-host route, without credentials.
- Delivered [English feasibility report](stages/PRE-option-A-feasibility.md), [Chinese report](stages/PRE-option-A-feasibility.zh-CN.md) and [amendment 1.1-A draft](planning/simulator-build-amendment.md): SIM0 baseline build and SIM1 instrumented qualification, with 10 unchecked proposed todos and unchanged original acceptance. Original checklist remains 2/34 accepted; PRE is incomplete.
- Evidence: `artifacts/preflight/20260929T051932Z/`. Three source-repository states and nine selected installed-player hashes unchanged; both source inspection checkouts clean. Documentation/manifest checks are recorded in [artifact review](research/evidence/artifact-review.md). No simulator/editor/ROS launch, motion, plugin feature implementation, commit or push occurred.
- Next gate: concrete amendment review and SIM0 entry; resolve user-managed Unity activation/build-host route. SIM1 and motion remain behind their named confirmation gates.

## 2026-09-29 — Planning: proposed SIM1 deferral

- Answered the user's installed-player/SIM1 questions using the recorded live observations and pinned receiver/actuator/reset source. Distinguished working sensor transport, source-supported limitations and unperformed moving-stop tests.
- Prepared [draft 1.1-B](planning/installed-binary-first-amendment.md) and [Chinese explanation](stages/SIM1-deferral.zh-CN.md): a bounded installed-player S1a closed-loop/normal-stop demonstration before complete PRE, followed by gap reassessment and SIM0/SIM1 only as needed. Original full acceptance remains required; source freshness and final-sender-loss braking cannot be claimed by receipt checks or process containment.
- Kept independent supervision, concrete numerical motion approval and stage-end review. Unity acquisition/activation is not a prerequisite of the proposed first demo. Added four separate unchecked proposal todos; original plan remains 2/34 accepted, with no SIM0/SIM1 item accepted.
- Updated navigation and decision records without inferring approval from a question. No installation, launch, actuation, plugin/source implementation, commit or push. Documentation checks are recorded in `docs/research/evidence/artifact-review.md`.
- Next gate: confirmation of the concrete installed-player-first dependency exception; then qualify the demo prerequisites and prepare its numerical motion protocol. The original release obligations remain open.

## 2026-09-29 — PRE: original sequence retained; activation handoff

- Recorded explicit full PRE-before-S1 continuation. Marked S1a/deferral not adopted and its four todos inactive; continued the previously reviewed source-build route with scoped SIM0 and retained SIM1/motion stage gates. No acceptance criteria or completed marks changed.
- Recorded the user's Unity activation/build-environment answer as not yet determined. Prepared [English guidance](stages/SIM0-activation-guide.md) and [Chinese steps](stages/SIM0-activation-guide.zh-CN.md); rechecked official Hub installation, license management and pinned editor sources. The former engine-license URL timed out; current Hub guidance was accessible.
- Kept account/license choice with the user; no eligibility, activation, purchase or remote-host availability inferred. Updated current plan/report navigation and decision records.
- Validation: documentation links/fences, unique todo states and diff whitespace checked in the artifact review. No installation, application launch, motion, simulator/plugin implementation, commit or push.
- Next: select the build environment and complete user-managed activation, then continue SIM0 qualification. Full PRE remains the prerequisite for S1.

## 2026-09-29 — SIM0: local Hub installation and user-confirmed readiness

- Installed official Unity Hub 3.21.3 at the user's request, under `~/Applications/UnityHub`, with a user CLI/desktop entry and `unityhub://` callback association. Resumed an interrupted official download; verified artifact hashes, desktop validation and an owned visible window. No global packages or simulator/core files were changed.
- The user subsequently confirmed login and license readiness. No credentials, license contents or account actions were collected/performed by the agent. Pinned-Editor runtime access remains distinct from this user confirmation.
- A Hub CLI inventory returned profile-lock diagnostics and no installed-Editor list. Continue through the already approved official archive path, preserving the user's running Hub. Exact Editor/module and complete pinned source acquisition are in progress in isolated paths.
- Evidence: `artifacts/preflight/20260929T062054Z/` and `artifacts/simulator-build/20260929T063510Z/`; bilingual [setup record](stages/SIM0-activation-guide.md). No new acceptance checkbox, motion, instrumentation or S1 plugin feature is claimed. Next: Editor runtime/import/build verification and the two specified neutral runs.

## 2026-09-29 — SIM0: acquired toolchain/source; runtime entitlement blocker

- Acquired all 9,422 tracked simulator files (6,868,307,583 bytes), with a clean pinned worktree and per-file hashes. Installed exact Unity 2021.3.9f1/ad3870b89536 and its Linux IL2CPP module from official archives; retained bundled notices and recorded hashes. Combined extraction/hash operation took 98.73 seconds; `-version` and main-executable linked-library checks passed.
- Actual empty-project startup exited 1 after 46.70 seconds. A licensing-service connection/update message preceded `Access token is unavailable` and failed activation/update. This does not disprove the user's login/license confirmation; runtime access remains blocked as SIM0-B01.
- Hub CLI association exited 0 but its subsequent installed-editor list was empty. Preserved profile-lock diagnostics, the failed first window helper dependency selection and corrected no-visible-window result. No account/license files were read or vendor configuration/code patched. Asked the user to Locate/first-open the installed Editor through Hub and personally complete any account prompt.
- Added an explicit parameterized, import-safe build helper; CLI/help/import checks passed, while actual AutoDRIVE import/build remains untested. Prepared, but did not apply, the approved same-version Linux-host compiler dependency diff. No physics/scene/runtime source changes, simulator launch, motion or S1 feature work occurred.
- Reports: [English](stages/SIM0-toolchain-attempt.md), [Chinese](stages/SIM0-toolchain-attempt.zh-CN.md); evidence: `artifacts/simulator-build/20260929T063510Z/`. Original PRE remains 2/34 accepted; all SIM0 tasks unchecked. Resume after actual Editor access is restored, then qualify batch startup/import/build and two neutral runs. No acceptance reduction or automatic SIM1 entry.

## 2026-09-29 — SIM0: Hub template-loading diagnosis and layout correction

- Investigated the user's template-loading failure using relevant Hub diagnostics, saved Editor registration and read-only vendor code. Hub's Linux folder-based detection retained the lowercase `unity-` prefix used in our installation path. Its actual bundled version parser rejected `unity-2021.3.9f1` and accepted `2021.3.9f1`; all three bundled template archives were present.
- Renamed the owned scratch toolchain folder to `2021.3.9f1`, retaining the previous path as a compatibility symlink. Verified the same Editor inode via both paths and no running Editor before the move. No Hub profile/vendor code, account/license contents, simulator source or shared AVLite tree was modified.
- Requested refresh of the running Hub's entry through Remove/Locate and a template retry. GUI recovery and the prior entitlement failure remain unverified; no new acceptance item, motion or S1 feature is claimed.
- Evidence: `artifacts/simulator-build/20260929T084707Z/`; [English report](stages/SIM0-template-loading.md), [Chinese report](stages/SIM0-template-loading.zh-CN.md). Next: verify corrected Hub registration/template display, actual Editor startup and then the bounded batch path.

## 2026-09-29 — SIM0: verified startup recovery and initial source import

- Verified Hub's corrected 2021.3.9f1/ad3870b89536 registration and the version metadata of the user's successfully created project. Fresh batch startup reached compilation with an already valid license, then failed on missing compatible libssl and a cleanup SIGTRAP; retained the 10.09-second failure.
- Downloaded one libssl1.1 Ubuntu package under the scoped escalation after a sandbox domain denial; verified Ubuntu release signatures and the index/package SHA-256 chain, then extracted only into private scratch. A separate fresh batch project compiled and exited 0 in 22.34 seconds with that library path. SIM0-B01 resolved for this configuration; SIM0-01 checked only after this verification.
- Added an explicit private-native-library option to the existing build tool, with hashes and subprocess-only environment scope. CLI/help/import/AST checks passed. Applied the approved two-file Linux-host toolchain 2.0.4 substitution and started the first complete AutoDRIVE import with no prior Library directory.
- Evidence: `artifacts/simulator-build/20260929T085557Z/`; [English recovery report](stages/SIM0-startup-recovery.md), [Chinese report](stages/SIM0-startup-recovery.zh-CN.md). Full source build, both neutral runs, original PRE-03/04 and SIM1 entry remain pending. No motion or S1 driving implementation.

## 2026-09-29 — SIM0: initial import reviewed; asset-scope decision pending

- Initial import exited 0 after 389.49 seconds with no C# compiler errors, but retained five checkpoint/SearchDatabase import failures and one HDRP SpeedTree upgrader exception. Nine orphan metadata removals and two automatic demo-material upgrades are recorded; F1TENTH scene/project settings are unchanged. Did not treat exit 0 as clean-import acceptance.
- Added an explicit `--audit-scene` mode to the existing build tool and an Editor-only dependency probe. The bounded run exited 0 in 12.01 seconds, identified 276 dependencies, and removed its temporary source/metadata. All six failing assets and both upgraded demo materials are outside the reported F1TENTH set. Static/dynamic-load limitations remain explicit.
- Prepared a byte-fingerprinted, unapplied asset-exclusion candidate manifest and bilingual [import review](stages/SIM0-import-review.md). Requested confirmation because excluding assets changes the qualification input scope beyond the reviewed compiler dependency adaptation. Original files are preserved; no exclusions, player build, simulator launch, motion or SIM1/S1 entry occurred.
- SIM0-01 remains accepted; SIM0-02 is blocked as SIM0-B02 pending the scoped recovery decision and a clean import/build. Original PRE remains incomplete. Evidence: `artifacts/simulator-build/20260929T085557Z/`.

## 2026-09-29 — SIM0: approved import recovery in progress

- Recorded the user's explicit confirmation of exactly six asset exclusions plus their metadata in a separate qualification worktree. Preserved the complete original checkout and archived all twelve files with verified byte hashes; retained the original failed-import evidence.
- Added a repeatable preparation entrypoint and versioned exclusion/package manifests. The fresh worktree has no Library directory; required F1TENTH asset/metadata hashes match the original audited dependency closure. Clean import is running with the same pinned Editor/private library and approved Linux compiler package.
- Prepared a parameterized stationary harness for fresh-process runs, strict zero replies, movement rejection, PID-bound UI review and bounded cleanup. Static/import/CLI and command/telemetry rejection checks passed; live qualification remains pending. No SIM0 completion, motion or SIM1/S1 entry is inferred.
- Evidence: `artifacts/simulator-build/20260929T100424Z/`. Next: review clean import, compare the new Unity dependency audit, build, then perform the two specified stationary runs if prerequisites pass.

## 2026-09-29 — SIM0: targeted recovery verified; required track importer blocker

- Fresh import exited 0 in 364.43 seconds without the five checkpoint failures or tree exception. The required 276 dependency paths and 552 asset/metadata hashes match the baseline; F1TENTH scene/settings are unchanged. Original checkout and twelve excluded file copies are preserved.
- Full diagnostic review found seven OpenCAV missing-prefab GUIDs already present in the earlier log but omitted from the previous summary. Traced them to existing SketchUp files, then expanded the Editor-only audit to inspect actual imported objects and 64-bit local IDs. Both required track files have zero imported objects; all 50 project SKP assets lack imported meshes, while the F1TENTH FBX resolves all inspected references. Unity 2021.3 documentation confirms Linux lacks SketchUp import.
- Stopped before build/runtime as SIM0-B03. Published [English](stages/SIM0-sketchup-blocker.md) and [Chinese](stages/SIM0-sketchup-blocker.zh-CN.md) reports with Windows-host, portable-export and local-derived feasibility choices. No further exclusions, geometry replacement, host switch, motion or SIM1/S1 entry. Requested the user's route decision because it changes approved host/required asset inputs.
- Reusable preparation/neutral/geometry tools are import-safe; command rejection checks and installed-player read-only inventory passed. Neutral harness live validation is pending. Preserved a missing-NumPy analysis attempt, corrected using existing isolated packages; no global install. Three Editor processes exited/reaped; all selected repository/player/original-checkout baselines are unchanged.
- Evidence: `artifacts/simulator-build/20260929T100424Z/`. Original acceptance remains 2/34 and amendment acceptance 1/10. Resume after build-host/asset-route review; retain the full PRE-before-S1 sequence and both stationary trials.

## 2026-09-29 — SIM0: Windows unavailable; Linux recovery proposal

- Recorded the user's constraint that no Windows build host is available. Completed read-only local feasibility rather than selecting an external host or changing the Editor/ROS baseline.
- Verified complete installed position/normal/tangent/UV0/index/submesh data for both tracks, identical render/collider mesh pointers, matching numeric source-material properties and present source textures. Independent raw-buffer decoding agrees with the parser. Reconstruction, visual equivalence and source player behavior remain unverified.
- Published the concrete [English recovery proposal](planning/linux-asset-recovery.md) and [Chinese report](planning/linux-asset-recovery.zh-CN.md). Proposed scope: two native meshes/prefabs, exact F1TENTH reference mapping, preserved OpenCAV prefab/scene quarantine and removal of its disabled build entry, followed by unchanged SIM0 acceptance. Approval requested because this exceeds the six-asset exclusion scope.
- Extended only the reusable read-only inspection tool; actual inventory, import/help/AST checks passed. Selected installed-player/repository baselines and both source-copy diffs remain unchanged. Retained an initial integrity-check format mismatch and its corrected comparison; no source mutation caused it.
- Evidence: `artifacts/simulator-build/20260929T102620Z/`. No conversion, additional exclusion, Editor/player launch, build, motion or stage entry. Original acceptance remains 2/34 and amendment acceptance 1/10; LNX-01–04 are unapproved and unchecked. Next: recovery-scope approval, then implementation and verification in a fresh derived copy.

## 2026-09-29 — SIM0: approved Linux recovery preparation

- Recorded the user's explicit confirmation of the native-track recovery. Prepared three separate pinned copies for initial generation, repeat generation and a final clean build; each preserves 16 exact excluded files and removes only the disabled OpenCAV build entry. All F1TENTH scenes remain unchanged.
- Extended the existing preparation/build tooling and added one parameterized track input/reference tool plus an Editor-only generator/verifier. Corrected a rejected mesh/GameObject naming assumption in the exporter; both exported buffers/attributes then matched the inspected player data.
- Initial import started without Library and exited 0 in 361.44 seconds. No C# errors, import exceptions or missing-prefab diagnostics; 31 fallback-shader lookup messages and null-renderer warnings retained. This does not validate the required scene or player.
- Evidence: `artifacts/simulator-build/20260929T122535Z/`. All LNX tasks remain unchecked. Next: native generation/reload, repeated generation, exact scene mapping, clean build and original neutral acceptance.

## 2026-09-30 — SIM0: retained generation failure and execution blocker

- First native generation compiled and created both mesh/prefab pairs, then failed the mesh-name check after 14.02 seconds. Preserved all failed outputs; an independent read confirms both serialized vertex/index buffers match the installed player. Added explicit name restoration after Unity's CreateAsset and retained strict verification; the correction is not yet live-verified.
- After interruption, the user instructed continuation under a restricted session with approval disabled. Retry exited −5 after 31.03 seconds before generating a report. Recorded repeated package-manager `uv_interface_addresses` failures; independent interface/NETLINK_ROUTE probes returned EPERM. Stopped affected live execution as SIM0-B04 without requesting or bypassing escalation.
- Owned Editor reaped and temporary helper removed. Preserved/cleared its verified stale crash lock under exclusive locks; retained the initial cross-mount rename failure. Original source/player/repository baselines remain unchanged. No scene mapping, player build, neutral trial, motion or next-stage entry occurred.
- Five tool AST/import/help checks and seven scene-mapping guard tests pass. Published [English progress/blocker report](stages/SIM0-linux-recovery-attempt.md) and [Chinese report](stages/SIM0-linux-recovery-attempt.zh-CN.md), with the exact unexecuted retry command and preserved input paths.
- Acceptance remains original 2/34, source amendment 1/10, recovery 0/4. Next: resume the already approved Editor operation in a permitted host context, then finish the unchanged asset/build/runtime checks. Full PRE-before-S1 and SIM1's explicit entry gate remain in force.

## 2026-09-30 — SIM0: host retry, exact recovery and player-packing correction

- Host retry resolved SIM0-B04. Preserved earlier failures; repeated native generation, exact 16 + 20 reference mapping and independent clean imports/loaded-scene checks passed. No AVLite core or installed-player change.
- Two IL2CPP players compiled in 716.04 / 698.04 seconds but strict comparison rejected normal-channel metadata `4` versus baseline `52`. Geometry, recorded builtin settings/script identities and resolved material mappings match; neither rejected player was launched. Direct source-metadata preservation did not survive the player build.
- A 17.02-second isolated bundle probe reproduced the mismatch and demonstrated exact float32-normal authoring as the treatment; both variants retain identical raw buffers, and only the corrected variant retains full metadata. Temporary probe assets removed. Independent byte decoding and two new generations (17.02 / 352.45 seconds) passed; final scene check 12.01 seconds, 285 dependencies / 570 file records, full source allowlist reviewed. LNX-01/02 accepted for the current revision.
- Fourteen focused tests and updated tool import/CLI checks pass. Three reference repository states, selected installed-player/source hashes and 83 frozen evidence files remain unchanged. Evidence: `artifacts/simulator-build/20260929T122535Z/`; bilingual [current report](stages/SIM0-linux-recovery-attempt.md).
- Final authoring player built in 698.08 seconds and passed the full recorded strict comparison, including raw buffers/full channel metadata and resolved material/preview mappings. LNX-03 and SIM0-02 accepted. Two neutral attempts timed out without connection and cleaned up; retained for the following investigation. Original acceptance 2/34, source amendment 2/10. No nonzero actuation, SIM1 or S1 entry.


## 2026-10-01 — SIM0: verified connection and neutral-position blocker

- Added owned-window pointer/focus verification after two connection timeouts. The next attempt stopped before clicking because a different window covered Unity. Window-manager activation then passed targeting checks and established the localhost connection. No simulator source/physics/acceptance change.
- First connected trial delivered 65 processed frames and 65 exact-zero replies; each of eight ROS topics received 65 messages. First-frame 1081-range scan conversion and 1280×720 RGB image pixels match ROS content. Received frame 66 changed reported X by 1 mm; unchanged guard stopped at 16.529 seconds. No second fresh-process trial, no completed 60-second observation. All three children exited/reaped; cleanup 1.594 seconds, endpoint released.
- Read-only investigation found the same 1 mm step with zero encoders in all four retained installed-player segments. IPS reads Transform directly, while transport rounds to three decimals; passive-motion cause and longer-term behavior remain unknown. Matching pre-existing wheel warnings and shutdown diagnostics retained. No assumption that the change is harmless noise.
- Published synchronized English/Chinese results, actual receipt/resource measurements and a concrete diagnostic-only comparison proposal. It requires confirmation because it would permit observation past the original first-position-change stop. No relaxed guard implemented. Evidence: `artifacts/simulator-build/20260929T122535Z/neutral-motion-review.json`, retained attempts and final retry manifest.
- Status: **SIM0-B06**; original 2/34, source amendment 2/10, recovery 3/4. Next: user decision on bounded passive-drift characterization; full PRE and SIM1/S1 gates remain intact.

## 2026-10-01 — SIM0: approved passive-drift comparison completed

- User approved the four-window diagnostic scope. Added an explicit diagnostic profile to the existing runner; default P0 and exact-zero/encoder guards remain intact. Seven focused boundary/guard tests passed; no simulator source, physics or sensor change.
- Two fresh-process windows per player completed: installed 3 / 4 mm, rebuilt 3 / 3 mm, all as monotonic reported-X steps with zero commands/feedback/encoders. Eight topics continued receiving; first raw scan/image conversion matched ROS. Reported displacement is not full-precision body motion or proof of harmless noise.
- Separated exact 60-second receipt metrics from 23.14–83.92 ms polling overshoot and cleanup frames. All 12 owned children exited 0 and were reaped; endpoint released. Existing wheel-hull and shutdown diagnostics retained.
- Integrity matches 9 installed files, 603 rebuilt outputs, 15 selected source/assets, 3 bridge/config files, 3 reference repositories, source diff and all 434 prior frozen evidence files. Bilingual report, trajectories, offline derivation, reproduction and new manifest: [diagnostic report](stages/SIM0-neutral-drift.md), `artifacts/simulator-build/20261001T054121Z-drift/`.
- Diagnostic work is complete; **SIM0-B06 remains open**. Counts unchanged: original 2/34, source amendment 2/10, recovery 3/4. Next decision: a separate read-only body/Transform/wheel diagnostic build and two bounded zero-command runs. This needs a narrow exception to SIM0's instrumentation non-goal; no P0 relaxation, SIM1 or S1 entry.

## 2026-10-01 — SIM0: approved kinematics diagnosis completed

- User's “yes” approved the read-only instrumentation exception. Extended the existing build/run/analysis tools with explicit activation, unique bindings, full-precision state, host-clock/PID/heartbeat checks and bounded logs. Existing P0/zero/encoder/bridge guards remain unchanged; no vehicle/physics/sensor settings or AVLite core changes.
- Initial 64 MiB trace cap failed before Connect at the scene's existing 1 kHz physics rate. Preserved that failed launch, source and player; corrected capacity to 1 GiB in a new derived copy. Two successful incremental builds took 253.361 / 248.366 s. Recorded the deviation: one extra corrective build and a failed pre-connection launch, without expanding the two approved observation windows.
- Both windows completed. Full-precision body Z drift is **3.437 / 3.259 mm**; stock reports **4 / 3 mm**. Axle local offset stays fixed, and all four wheels retain zero motor torque/RPM with 85.599998474 Nm braking. This establishes simulated body drift but leaves the compound-contact/solver cause unresolved. Eight-topic delivery, first scan/image conversion, complete IPS sequence and owned cleanup passed their diagnostic checks.
- Eighteen focused tests passed; strict static comparison and 9,404-file existing-source comparison passed. Installed/baseline/diagnostic player hashes, runtime files, reference repositories and both prior frozen evidence sets remain unchanged. All nine owned children across failed/successful launches are reaped and absent; endpoint released.
- Published [English](stages/SIM0-kinematics.md) / [Chinese](stages/SIM0-kinematics.zh-CN.md) reports with costs, causal limits and a concrete contact-pair A/B proposal. Evidence: `artifacts/simulator-build/20261001T060743Z-kinematics/`. **SIM0-B06 remains open**, counts 2/34, 2/10, 3/4. Proposed collision filtering/further windows await approval; no P0 acceptance, SIM1 or S1 entry.

## 2026-10-01 — SIM0: contact controls completed; treatment gate blocked

- User approved the preceding contact A/B proposal with “yes”. Added explicit contact observation, PID/time-bound window acknowledgment and evidence-gated pair filtering to the existing diagnostic tools. No AVLite core/vendor scene/controller/physics setting change; current treatment target remains Proto Track.
- One isolated build passed in **259.351 s**. Final source comparison retains all **9,404** existing files plus seven approved diagnostic additions; serialized comparison passes. Twenty-nine focused tests and exact-engine API compilation pass.
- Both 60-second controls completed: **3.411 / 3.392 mm** body drift. All four wheel meshes contact **Floor**, with zero reported aggregate collision impulses; WheelCollider ground hits also identify Floor. Mass/COM stay fixed while inertia varies slightly. The declared target and constant-inertia checks fail, so **no treatment was launched**, no gate relaxed and no repair adopted.
- Six owned children exited 0, were reaped and are absent; endpoint released. Fingerprints match installed/baseline/prior/current players, existing source/settings, runtime files, reference repositories and all three frozen predecessors. Preserved provisional during-build checks and corrected offline IPS-field failure; final checks pass, raw trials unchanged.
- Published [English](stages/SIM0-contacts.md) / [Chinese](stages/SIM0-contacts.zh-CN.md) reports with substantial logging cost, causal limits and a concrete Floor-only proposal requiring revised intervention-local inertia verification. Evidence: `artifacts/simulator-build/20261001T073103Z-contacts/`. **SIM0-B06 remains open**; acceptance counts **2/34, 2/10, 3/4**. Next decision requires confirmation; no P0/SIM1/S1 acceptance.

## 2026-10-01 — SIM0: approved Floor A/B completed; drift persists

- User’s “approve” authorized the exact Floor target and intervention-local inertia criterion. Extended the existing diagnostic profile, request/binding evidence and gate; Proto Track controls cannot authorize Floor treatment. Default production/core code and P0/zero/encoder guards remain unchanged.
- One isolated incremental build passed in **257.388 s**; 9,404 existing source files and strict player geometry/settings comparison remain unchanged. **35 focused tests** and pinned-engine API compile passed. Preserved the initial analyzer-variable test failure and its pre-build correction; no extra build or live retry.
- Two controls and two 60-second treatments completed. Post-filter wheel-mesh/Floor contact points are zero; actuator wheels remain grounded, immediate properties match, mass/COM stay fixed, inertia varies naturally. Body drift remains **3.372 / 3.414 mm treatment versus 3.431 / 3.413 mm control**. The descriptive −0.029 mm mean difference is not a demonstrated improvement; logging overhead differs materially.
- Twelve trial children exited 0/reaped, editor/children absent on host, endpoint free. Independent streaming analysis matches motion/contact/IPS records; prior players/source/runtime/reference repositories and all **434 + 108 + 145 + 139** frozen evidence files pass integrity.
- Published [English](stages/SIM0-floor-contacts.md) / [Chinese](stages/SIM0-floor-contacts.zh-CN.md) reports and comparison figure. Evidence: `artifacts/simulator-build/20261001T102325Z-floor/`. **SIM0-B06 remains open**, counts **2/34, 2/10, 3/4**; no repair/P0/SIM1/S1 acceptance. Recommend one bounded read-only pose/velocity/controller/compound-body source-and-trace review before proposing another intervention; await confirmation.

## 2026-10-01 — SIM0: approved read-only pose review completed

- Reviewed the pinned controller, sensor/recorder/camera paths, five decoded script field layouts and compiled physics/time settings. Verified four physical wheel-parent writes per fixed callback with autosync/interpolation enabled. Retained and corrected an offline boolean-alignment decoding failure; final scalar/hierarchy checks pass.
- Reanalysed four frozen windows: sampled Z-velocity integral accounts for **0.287–0.299%** of **3.372–3.431 mm** body movement; mean step is **0.943–0.960 float32 ULP**. COM rotation contributes nanometres; positive increments occur within rendered frames. Existing callbacks cannot separate controller writes from native physics.
- Published [English](stages/SIM0-pose-review.md) / [Chinese](stages/SIM0-pose-review.zh-CN.md) reports with a source-linked causal map, ranked hypotheses and one proposed statement-level tracing experiment. Recorded the separate front-motor-torque clearing concern for future pre-motion review; no repair adopted.
- Analysis consistency/analytic checks and listed-file integrity pass, including all **188** prior frozen evidence files, current 9,404+7 source/605 player files and three reference repository states. Eight official Unity pages archived after a scoped network retry. Evidence: `artifacts/simulator-build/20261001T114229Z-pose-review/`. No Editor/simulator launch, new build or plugin implementation.
- **SIM0-B06 remains open; acceptance stays 2/34, 2/10, 3/4.** No P0/SIM1/S1 acceptance. Stop pending a separate decision on the proposed one-build, at-most-two 10-second neutral tracing windows.

## 2026-10-01/02 — SIM0: approved pose tracing prepared, interrupted before build (recorded 2026-10-05)

- The user's “approve” authorized the single statement-level tracing experiment (one build, at most two 10-second windows). Setup completed in `artifacts/simulator-build/20261001T130821Z-pose-trace/`: fresh derived copy (tracked diff equal to the qualified baseline), `integration/autodrive/diagnostics/PoseTrace.cs`, a 42-line controller preview patch, `--pose-trace` runner/analysis support, 40 focused tests and a pinned-API compile. The host precheck passed on 2026-10-02.
- The previous agent session ended before the instrumentation was installed in the copy; no tracing build or live run occurred, and this entry was not written at the time. The work was superseded on 2026-10-05 (below). All setup files are preserved.

## 2026-10-05 — SIM0: B06 closed by decision; amended P0 runs pass

- Assessed whether further B06 root-causing was necessary. The same ~3–4 mm/min passive creep occurs in the unmodified installed vendor player, so it is inherited simulator behavior, not a build regression. It is about five orders of magnitude below racing speeds, and a physics repair would make the rebuild diverge from the reference. The user selected option A: close the investigation, amend the P0 position rule to an inclusive 10 mm bound (exact-zero and any-encoder-change guards unchanged) and supersede the unexecuted tracing.
- Added `--profile p0-creep` to `autodrive_neutral.py` (same bound semantics as `drift-diagnostic`, normal P0 completion); kept the strict `p0` profile for history. 41 focused tests pass.
- Ran two fresh-process 60-second neutral observations on the qualified authoring player, with visual pre-Connect review of each run. Both completed: 237 messages on each of eight topics, ~3.9 Hz, maximum reported displacement 3 mm, all replies/encoders exactly zero, first scan/image equal to ROS content, all children exit 0, port released, 603/603 player files unchanged before and after.
- **SIM0-03 and LNX-04 accepted.** Counts: original 2/34, source amendment 3/10, recovery 4/4. Published the bilingual [SIM0 report](stages/SIM0-completion.md) as the SIM0-04 baseline; evidence `artifacts/simulator-build/20261005T052025Z-p0/` (42-file manifest). Updated plan/recovery/PRE/report status lines.
- Next gate: user SIM0 stage review (checks SIM0-04) and SIM1 entry confirmation. No nonzero command, SIM1 or S1 work.
