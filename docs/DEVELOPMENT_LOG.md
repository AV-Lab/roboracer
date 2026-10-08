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

- Added the full Simplified Chinese report at the user's request (all Chinese versions were removed on 2026-10-06, also at the user's request), with reciprocal navigation to the English report. The main agent reviewed the delegated translation sections against the original.
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
- Evidence: [English report](stages/PRE-interface-qualification.md), `artifacts/preflight/20260928T124339Z/`. Three source-repository states and nine selected simulator hashes unchanged; all owned PIDs absent and 4567 released. No motion, S1 feature implementation, physical actuation or publication occurred.

## 2026-09-29 — PRE: confirmed option A source/toolchain preparation

- Recorded the user's selection of option A preparation. Preserved physical-racing strategy B, v1.0 acceptance, independent supervision/hardware stop and the numerical motion gate. No editor installation, activation or instrumentation is inferred from that preparation choice.
- Retrieved all 223 tracked C# files, the F1TENTH scene, project/package settings and metadata into a clean pinned inspection worktree. Identified actual acquisition/actuation/reset hooks, package/vendor dependencies and the encoder's hardcoded conversion discrepancy. Full asset closure/import/build remain unverified.
- Verified official Unity 2021.3.9f1 editor/Linux IL2CPP archive HEAD responses and selected pinned package metadata using scoped approved host access. Recorded sandbox denials, an interrupted inefficient partial-clone size inventory and GitHub API rate limiting. Found no local editor; recorded the Ubuntu 22.04 versus documented 2021.3 host-support gap. Asked only for the user's activation/build-host route, without credentials.
- Delivered [English feasibility report](stages/PRE-option-A-feasibility.md) and [amendment 1.1-A draft](planning/simulator-build-amendment.md): SIM0 baseline build and SIM1 instrumented qualification, with 10 unchecked proposed todos and unchanged original acceptance. Original checklist remains 2/34 accepted; PRE is incomplete.
- Evidence: `artifacts/preflight/20260929T051932Z/`. Three source-repository states and nine selected installed-player hashes unchanged; both source inspection checkouts clean. Documentation/manifest checks are recorded in [artifact review](research/evidence/artifact-review.md). No simulator/editor/ROS launch, motion, plugin feature implementation, commit or push occurred.
- Next gate: concrete amendment review and SIM0 entry; resolve user-managed Unity activation/build-host route. SIM1 and motion remain behind their named confirmation gates.

## 2026-09-29 — Planning: proposed SIM1 deferral

- Answered the user's installed-player/SIM1 questions using the recorded live observations and pinned receiver/actuator/reset source. Distinguished working sensor transport, source-supported limitations and unperformed moving-stop tests.
- Prepared [draft 1.1-B](planning/installed-binary-first-amendment.md): a bounded installed-player S1a closed-loop/normal-stop demonstration before complete PRE, followed by gap reassessment and SIM0/SIM1 only as needed. Original full acceptance remains required; source freshness and final-sender-loss braking cannot be claimed by receipt checks or process containment.
- Kept independent supervision, concrete numerical motion approval and stage-end review. Unity acquisition/activation is not a prerequisite of the proposed first demo. Added four separate unchecked proposal todos; original plan remains 2/34 accepted, with no SIM0/SIM1 item accepted.
- Updated navigation and decision records without inferring approval from a question. No installation, launch, actuation, plugin/source implementation, commit or push. Documentation checks are recorded in `docs/research/evidence/artifact-review.md`.
- Next gate: confirmation of the concrete installed-player-first dependency exception; then qualify the demo prerequisites and prepare its numerical motion protocol. The original release obligations remain open.

## 2026-09-29 — PRE: original sequence retained; activation handoff

- Recorded explicit full PRE-before-S1 continuation. Marked S1a/deferral not adopted and its four todos inactive; continued the previously reviewed source-build route with scoped SIM0 and retained SIM1/motion stage gates. No acceptance criteria or completed marks changed.
- Recorded the user's Unity activation/build-environment answer as not yet determined. Prepared [English guidance](stages/SIM0-activation-guide.md); rechecked official Hub installation, license management and pinned editor sources. The former engine-license URL timed out; current Hub guidance was accessible.
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
- Reports: [English](stages/SIM0-toolchain-attempt.md); evidence: `artifacts/simulator-build/20260929T063510Z/`. Original PRE remains 2/34 accepted; all SIM0 tasks unchecked. Resume after actual Editor access is restored, then qualify batch startup/import/build and two neutral runs. No acceptance reduction or automatic SIM1 entry.

## 2026-09-29 — SIM0: Hub template-loading diagnosis and layout correction

- Investigated the user's template-loading failure using relevant Hub diagnostics, saved Editor registration and read-only vendor code. Hub's Linux folder-based detection retained the lowercase `unity-` prefix used in our installation path. Its actual bundled version parser rejected `unity-2021.3.9f1` and accepted `2021.3.9f1`; all three bundled template archives were present.
- Renamed the owned scratch toolchain folder to `2021.3.9f1`, retaining the previous path as a compatibility symlink. Verified the same Editor inode via both paths and no running Editor before the move. No Hub profile/vendor code, account/license contents, simulator source or shared AVLite tree was modified.
- Requested refresh of the running Hub's entry through Remove/Locate and a template retry. GUI recovery and the prior entitlement failure remain unverified; no new acceptance item, motion or S1 feature is claimed.
- Evidence: `artifacts/simulator-build/20260929T084707Z/`; [English report](stages/SIM0-template-loading.md). Next: verify corrected Hub registration/template display, actual Editor startup and then the bounded batch path.

## 2026-09-29 — SIM0: verified startup recovery and initial source import

- Verified Hub's corrected 2021.3.9f1/ad3870b89536 registration and the version metadata of the user's successfully created project. Fresh batch startup reached compilation with an already valid license, then failed on missing compatible libssl and a cleanup SIGTRAP; retained the 10.09-second failure.
- Downloaded one libssl1.1 Ubuntu package under the scoped escalation after a sandbox domain denial; verified Ubuntu release signatures and the index/package SHA-256 chain, then extracted only into private scratch. A separate fresh batch project compiled and exited 0 in 22.34 seconds with that library path. SIM0-B01 resolved for this configuration; SIM0-01 checked only after this verification.
- Added an explicit private-native-library option to the existing build tool, with hashes and subprocess-only environment scope. CLI/help/import/AST checks passed. Applied the approved two-file Linux-host toolchain 2.0.4 substitution and started the first complete AutoDRIVE import with no prior Library directory.
- Evidence: `artifacts/simulator-build/20260929T085557Z/`; [English recovery report](stages/SIM0-startup-recovery.md). Full source build, both neutral runs, original PRE-03/04 and SIM1 entry remain pending. No motion or S1 driving implementation.

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
- Stopped before build/runtime as SIM0-B03. Published [English](stages/SIM0-sketchup-blocker.md) reports with Windows-host, portable-export and local-derived feasibility choices. No further exclusions, geometry replacement, host switch, motion or SIM1/S1 entry. Requested the user's route decision because it changes approved host/required asset inputs.
- Reusable preparation/neutral/geometry tools are import-safe; command rejection checks and installed-player read-only inventory passed. Neutral harness live validation is pending. Preserved a missing-NumPy analysis attempt, corrected using existing isolated packages; no global install. Three Editor processes exited/reaped; all selected repository/player/original-checkout baselines are unchanged.
- Evidence: `artifacts/simulator-build/20260929T100424Z/`. Original acceptance remains 2/34 and amendment acceptance 1/10. Resume after build-host/asset-route review; retain the full PRE-before-S1 sequence and both stationary trials.

## 2026-09-29 — SIM0: Windows unavailable; Linux recovery proposal

- Recorded the user's constraint that no Windows build host is available. Completed read-only local feasibility rather than selecting an external host or changing the Editor/ROS baseline.
- Verified complete installed position/normal/tangent/UV0/index/submesh data for both tracks, identical render/collider mesh pointers, matching numeric source-material properties and present source textures. Independent raw-buffer decoding agrees with the parser. Reconstruction, visual equivalence and source player behavior remain unverified.
- Published the concrete [English recovery proposal](planning/linux-asset-recovery.md). Proposed scope: two native meshes/prefabs, exact F1TENTH reference mapping, preserved OpenCAV prefab/scene quarantine and removal of its disabled build entry, followed by unchanged SIM0 acceptance. Approval requested because this exceeds the six-asset exclusion scope.
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
- Five tool AST/import/help checks and seven scene-mapping guard tests pass. Published [English progress/blocker report](stages/SIM0-linux-recovery-attempt.md), with the exact unexecuted retry command and preserved input paths.
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
- Published [English](stages/SIM0-kinematics.md) reports with costs, causal limits and a concrete contact-pair A/B proposal. Evidence: `artifacts/simulator-build/20261001T060743Z-kinematics/`. **SIM0-B06 remains open**, counts 2/34, 2/10, 3/4. Proposed collision filtering/further windows await approval; no P0 acceptance, SIM1 or S1 entry.

## 2026-10-01 — SIM0: contact controls completed; treatment gate blocked

- User approved the preceding contact A/B proposal with “yes”. Added explicit contact observation, PID/time-bound window acknowledgment and evidence-gated pair filtering to the existing diagnostic tools. No AVLite core/vendor scene/controller/physics setting change; current treatment target remains Proto Track.
- One isolated build passed in **259.351 s**. Final source comparison retains all **9,404** existing files plus seven approved diagnostic additions; serialized comparison passes. Twenty-nine focused tests and exact-engine API compilation pass.
- Both 60-second controls completed: **3.411 / 3.392 mm** body drift. All four wheel meshes contact **Floor**, with zero reported aggregate collision impulses; WheelCollider ground hits also identify Floor. Mass/COM stay fixed while inertia varies slightly. The declared target and constant-inertia checks fail, so **no treatment was launched**, no gate relaxed and no repair adopted.
- Six owned children exited 0, were reaped and are absent; endpoint released. Fingerprints match installed/baseline/prior/current players, existing source/settings, runtime files, reference repositories and all three frozen predecessors. Preserved provisional during-build checks and corrected offline IPS-field failure; final checks pass, raw trials unchanged.
- Published [English](stages/SIM0-contacts.md) reports with substantial logging cost, causal limits and a concrete Floor-only proposal requiring revised intervention-local inertia verification. Evidence: `artifacts/simulator-build/20261001T073103Z-contacts/`. **SIM0-B06 remains open**; acceptance counts **2/34, 2/10, 3/4**. Next decision requires confirmation; no P0/SIM1/S1 acceptance.

## 2026-10-01 — SIM0: approved Floor A/B completed; drift persists

- User’s “approve” authorized the exact Floor target and intervention-local inertia criterion. Extended the existing diagnostic profile, request/binding evidence and gate; Proto Track controls cannot authorize Floor treatment. Default production/core code and P0/zero/encoder guards remain unchanged.
- One isolated incremental build passed in **257.388 s**; 9,404 existing source files and strict player geometry/settings comparison remain unchanged. **35 focused tests** and pinned-engine API compile passed. Preserved the initial analyzer-variable test failure and its pre-build correction; no extra build or live retry.
- Two controls and two 60-second treatments completed. Post-filter wheel-mesh/Floor contact points are zero; actuator wheels remain grounded, immediate properties match, mass/COM stay fixed, inertia varies naturally. Body drift remains **3.372 / 3.414 mm treatment versus 3.431 / 3.413 mm control**. The descriptive −0.029 mm mean difference is not a demonstrated improvement; logging overhead differs materially.
- Twelve trial children exited 0/reaped, editor/children absent on host, endpoint free. Independent streaming analysis matches motion/contact/IPS records; prior players/source/runtime/reference repositories and all **434 + 108 + 145 + 139** frozen evidence files pass integrity.
- Published [English](stages/SIM0-floor-contacts.md) reports and comparison figure. Evidence: `artifacts/simulator-build/20261001T102325Z-floor/`. **SIM0-B06 remains open**, counts **2/34, 2/10, 3/4**; no repair/P0/SIM1/S1 acceptance. Recommend one bounded read-only pose/velocity/controller/compound-body source-and-trace review before proposing another intervention; await confirmation.

## 2026-10-01 — SIM0: approved read-only pose review completed

- Reviewed the pinned controller, sensor/recorder/camera paths, five decoded script field layouts and compiled physics/time settings. Verified four physical wheel-parent writes per fixed callback with autosync/interpolation enabled. Retained and corrected an offline boolean-alignment decoding failure; final scalar/hierarchy checks pass.
- Reanalysed four frozen windows: sampled Z-velocity integral accounts for **0.287–0.299%** of **3.372–3.431 mm** body movement; mean step is **0.943–0.960 float32 ULP**. COM rotation contributes nanometres; positive increments occur within rendered frames. Existing callbacks cannot separate controller writes from native physics.
- Published [English](stages/SIM0-pose-review.md) reports with a source-linked causal map, ranked hypotheses and one proposed statement-level tracing experiment. Recorded the separate front-motor-torque clearing concern for future pre-motion review; no repair adopted.
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

## 2026-10-05 — SIM0 accepted; SIM1 entered; SIM1-01 source provenance passes

- Recorded the user's “go on the development plan” as the SIM0 stage review (SIM0-04 checked) and SIM1 entry confirmation, as the preceding SIM0 report named them.
- Added `RoboRacer.Provenance` (session/episode identity, fixed-step counter, per-source acquisition stamps, `Stopwatch` clock, launch-flag-gated freeze hooks that fail closed) and a +45/−1 vendor patch adding hooks to LIDAR/IPS/IMU/WheelEncoder/Socket. No physics, controller, scene or actuation change. Protocol: `integration/autodrive/sim1/PROTOCOL.md`. Extended `autodrive_build.py --sim1-patch`, added `autodrive_provenance.py`, and added `--provenance` / `--freeze-test` to the neutral runner (ping clock-echo, acquisition-time ROS headers, provenance topic).
- Reused the superseded pose-trace worktree as the derived copy (disk 24 GB free; tracked diff equal to the baseline). Pinned-API compile check passed. Incremental IL2CPP build 251.37 s, exit 0; strict serialized comparison passed; vendor diff byte-equal to the patch.
- Live, disarmed, Manual, exact-zero: two clean 60 s runs and three LIDAR-freeze trials, all with consecutive telemetry sequences. Each freeze carried the reused identity on every frozen frame, with age rising to 4.7–5.0 s and new scans resuming within 1–2 frames. Hook requests to a hook-less player were rejected and counted. ROS headers matched acquisition mapping except the first frame (before the first clock exchange). Clock offset −52…−5 ms with ±40–76 ms bound. Overhead indistinguishable from SIM0.
- Retained two failures: a runner CLI check that wrongly rejected the observer (fixed with a regression test, before any player launch), and one lost Connect click (bounded timeout, clean cleanup, retry succeeded). 54 focused tests pass. Evidence `artifacts/simulator-build/20261005T053316Z-sim1/` (125-file manifest); bilingual [report](stages/SIM1-provenance.md).
- Counts: original 2/34, source amendment 5/10, recovery 4/4. Next: SIM1-02 receiver guard (disarmed). No nonzero command sent.

## 2026-10-05 — Disk cleanup: superseded build copies removed

- At the user's request ("old builds only"), deleted nine superseded Unity project copies under `/tmp/roboracer-work/` (`autodrive-20261001T060743Z-kinematics`, `-kinematics-logging-fix`, `autodrive-20261001T073103Z-contacts`, `autodrive-20261001T102325Z-floor`, `autodrive-native-20260929T122535Z` plus `-repeat`/`-build`/`-metadata`, `autodrive-635dbb6d-qualified-20260929T100424Z`) and their six players in `autodrive-builds/`. Free disk 22 GB → 163 GB.
- Kept: pristine source `autodrive-635dbb6d-baseline`, the SIM0-qualified `autodrive-native-20260929T122535Z-authoring` copy and player, the current `autodrive-20261005T053316Z-sim1` copy and player, toolchains, the small `*-excluded-*` file sets, and all repository evidence. No open files or running editor/player at deletion.
- Consequence: evidence for the deleted builds remains in `artifacts/simulator-build/`, but those players can no longer be relaunched or re-hashed; reproducing them requires a rebuild from the baseline plus the recorded recovery/diagnostic inputs.

## 2026-10-05 — SIM1-02 receiver guard passes (disarmed)

- Recorded the user's “go on development plan” as continuation into SIM1-02 within the confirmed SIM1 entry. Added `RoboRacer.GuardCore` (Unity-free state machine, request validation, receiver-side clock bound, lease) and `RoboRacer.Guard` (activated only by `-roboracerGuard`; zero-output interlock unless `-roboracerMotionAuthorized`; post-actuation torque/steer read-back; bounded per-step trace), plus a +12/−3 `vendor-sim1-02.patch` (guard immediately before `Steer`/`Drive`, legacy Bridge write skipped, GUI mode toggle blocked, acknowledgements, disconnect hook). Protocol `roboracer.guard/1` in `integration/autodrive/sim1/PROTOCOL.md`.
- Added `autodrive_guard.py` (supervisor stand-in as its own process, acknowledgement tracker, scripted P1a scenario, trace analysis), `autodrive_neutral.py --guard observe|scenario`, `autodrive_derive.py` (verified derived copies) and `autodrive_build.py --sim1-through`. 86 C# guard-core checks under the pinned Mono; 78 focused Python tests, including the full scenario against a simulated (and a defective) receiver. That simulation exposed a ~150 ms clock bound and a lease that tolerated no missed reply; fixed by a bridge frame-receipt stamp and a provisional 1 s lease.
- Fresh derived copy (tracked diff `4965e4fa…` equal); incremental IL2CPP build 261.4 s, exit 0; patched sources byte-equal; strict comparison against the SIM1-01 player passed; 604/604 player files unchanged after the runs. Pinned fixed timestep is 1 ms; the guard runs every step.
- Live, interlocked: 17 P1a cases ×3 fresh processes all pass (`scenario-b`); Devkit loss cleared the lease in 1.7–17.2 ms via disconnect. Across 0.41 M traced steps, 0 had nonzero output/torque/steer, and every applied command was accepted while armed and before expiry. Two 60 s observation windows: 230/233 requests accepted and applied, 0 rejections/expiries, ~4 points player CPU over SIM1-01.
- Retained failures: a patch-series pre-check that tested 02 against the unpatched tree (fixed before any Editor start); `scenario-a` (trace passed; three harness defects fixed: GUI click retry, supervisor-loss check window, Devkit-loss wait/partial-line read); `observe-failed-connect` (lost Connect click; exposed a blocking supervisor send, now non-blocking). Evidence `artifacts/simulator-build/20261005T063753Z-sim1-02/` (186-file manifest); bilingual [report](stages/SIM1-guard.md).
- Counts: original 2/34, source amendment 6/10, recovery 4/4. Next: SIM1-03 disarm/reset/epoch/rearm and stale-command rejection across reconnect/reset, still disarmed. No nonzero command reached the controller.

## 2026-10-05 — Sequencing amendment 1.2: S1 before remaining PRE

- The user asked to postpone PRE and start S1 immediately. Given three options, they selected starting S1 on the SIM1-02 build. Recorded as [amendment 1.2](planning/s1-first-amendment.md), superseding the 2026-09-29 PRE-first instruction.
- S1 is entered. PRE-03/04 and the postponed SIM1-03–06 now gate S1 acceptance rather than entry; all criteria and the 34 original todos are unchanged. The numerical motion protocol becomes S1's first gate, and the guard's zero-output interlock stays on until it is confirmed.
- Order: S1-01 plugin loading/settings, then S1-02 observation bridge and the supervisor skeleton (no motion), then the motion protocol for confirmation.

## 2026-10-05 — S1-01: plugin loading, settings and command consumers pass

- Created the `roboracer/` AVLite community plugin. Exports:
  - `TargetSpeedSteeringCommand`: target speed in m/s and steering in rad, positive left, with a monotonic generation stamp; a `ControlCommandBase` subclass, not a relabelled Ackermann acceleration;
  - `AutoDriveBridge`: disconnected in S1-01, advertises no sensors, and validates every command;
  - `HoldController`: always requests a standstill;
  - a Pydantic `PluginSettings`: loopback host, port, request life ≤ 1 s, speed limit 0 until the motion protocol is confirmed, steering ≤ 30°.
- 5 tests (`roboracer/tests/`) run each case in a fresh AVLite 0.6.3 process with isolated AVLite/XDG directories. They cover:
  - registration through AVLite's own loader, with no side effects;
  - the factory loading the community plugin, and actuation gated off without localization;
  - the command delivered through the real Sync execution path via a test-only GT bridge;
  - the settings round-trip, with 7 invalid values rejected;
  - the consumer matrix: GUI manual Ackermann commands refused; gauge mirror; headless dashboard shows 0.0 acceleration; BasicSim fails loudly.
- The Tk GUI was not launched. Evidence: `artifacts/s1/20261005T074139Z-s1-01/`.
- Next: S1-02, the observation bridge on the guarded SIM1-02 player and the supervisor skeleton (no motion); then the numerical motion protocol for confirmation.

## 2026-10-05 — S1-02: bridge observation path passes (interlocked, no motion)

- Recorded the user's "go on" as continuation of S1-02 within the S1 entry of amendment 1.2.
- **Scan check fixed and passed.** The WIP `autodrive_scan_check.py` first comparison was invalid (retained): its ray targets included the vehicle's own colliders, which enclose the LiDAR head, so every beam was blanked inside the 0.06 m minimum range. With static scenery only, the vendor convention (CCW from −135°, 0.25°, 1081 beams, head 0.2733 m ahead / 0.096 m above the rear-axle IPS point) is best in all six SIM1-02 first frames: 1 finite mismatch, p50 2.0 mm, p95 ≤ 9.2 mm. All frames share the spawn pose. Three analytical fixtures added.
- **Observation path.** Added `roboracer/integration/autodrive_observation.py` (ROS-free `SnapshotAssembler`: pending provenance records, members matched by acquisition header stamp or IPS value, fail-closed rejections, CLOCK_MONOTONIC acquisition stamps, labelled GT pose). `AutoDriveBridge` subscribes only on `connect()` (private rclpy context, no signal takeover), serves atomic `SensorFrame`s, and advertises `LIDAR_2D`/`IMU`. `LOCALIZATION` is gated by the new `gt_localization` setting (default off). The runner's provenance message now carries `ips_position`; added `--plugin-observer` and `autodrive_s1_observation.py`.
- 19 plugin tests pass, including a replay of both recorded SIM1-02 observation runs. The replay found the Devkit's float32 `angle_min` (−2.35619, 4.5 µrad off), so the layout tolerance is 1e-5 rad. Runner/provenance/guard/scan-check suites pass.
- **Live run.** Ran 60 s on the SIM1-02 player: interlocked, zero requests, speed limit 0. Each run had a visual PID/window-bound pre-Connect review.
  - The first attempt lost its Connect click; it was retained, cleanup was clean, and the retry passed.
  - 240/240 acquisition frames became exactly one snapshot each, in order; the only rejection was the first frame.
  - Scan identity (stamp and float32 hash against the independent observer), GT pose (IPS equality) and yaw (≤ 5 mrad) matched in 240/240.
  - Skew ≤ 50 ms; clock bound 40–43 ms.
  - Commit latency was ~110 ms, almost all of it the runner's 0.1 s reply pacing, which precedes provenance publication.
  - Guard trace: 0 nonzero-output steps in 78,377. Maximum displacement 3 mm. All children exited 0, the port was released, and all 604 player files were unchanged.
- Evidence `artifacts/s1/20261005T102231Z-s1-02-live/` (64-file manifest); bilingual [report](stages/S1-observation.md).
- **S1-02 stays open** for command signs/units against observed response (needs motion). Next (no motion): the S1 supervisor skeleton, then draft the numerical motion protocol and stop for confirmation. Acceptance count unchanged (3/34).

## 2026-10-05 — Plugin checked against the AVLite plugin development guide

- At the user's request, audited `roboracer/` against `/home/a2rl/avlite/docs/plugin-development.md` (AVLite dev checkout, source 0.6.3).
- **Already conformant:**
  - layout and `__init__.py` exports;
  - Pydantic `PluginSettingsSchema` with a `PluginSettings` singleton, filepath assigned by the loader (as in the built-ins);
  - no `config/` folder or `plugin_*.yaml`; tests live under `tests/`, which the loader skips;
  - controller `control(ego, plan, control_dt, perception_model, sensors)` and `reset()`;
  - `control_ego_state(cmd, dt)`;
  - 2D scans padded to (N, 4) float32 in the device frame, with `base_to_sensor` mounts;
  - fresh sensor objects per frame, with the capability filter applied in the atomic `get_sensor_frame` override (allowed for atomic reads);
  - `logging.getLogger(__name__)`.
- **Changed:**
  - **Static ground-truth capability.** The bridge's ground-truth `LOCALIZATION` was a `@property` driven by a plugin `gt_localization` setting, which duplicated AVLite's Bridge Setting filter. It is now a public `frozenset` class attribute, like the guide example and the built-in `BasicSim`. The ground truth is switched off with AVLite's `c41_world_stack_capabilities`; the setting was removed.
  - **Default behaviour.** By default AVLite's control path now runs, and `HoldController`'s zero requests reach `control_ego_state`, where they are only validated and recorded. Nothing is sent to the simulator, and motion still requires the supervisor, guard authorization and the confirmed protocol.
  - **Getter.** Added `get_lidar_data()`, so the getter API serves the advertised LiDAR.
  - **README.** Now covers requirements and setup: ROS 2 Humble for `connect()`, the provenance Devkit and the SIM1-02 player, no pip extras and no `launch.sh`. It also documents the settings file location and the GT filter.
- **Tests.** S1-01 factory cases now use AVLite's filter (default: commands reach the bridge; filtered: never actuates), replacing the test-only GT subclass. The S1-02 bridge case checks that contracts are class-attribute `frozenset`s. 19 plugin tests pass with ResourceWarnings as errors; runner tests pass. The live S1-02 evidence is unaffected because the observation path is unchanged; the reports note the superseded setting.

## 2026-10-05 — S1 supervisor skeleton passes (no motion); motion protocol drafted, awaiting confirmation

- Recorded the user's "go on the task" as continuation to amendment 1.2 steps 3–4.
- **Supervisor.** Added `roboracer.supervisor/1` as its own process:
  - `runtime/supervisor_core.py` is the pure logic: validation order, expiry from the original generation time, a 500 ms runner lease with sticky inhibition, and a motion gate that cannot be opened in code;
  - `runtime/supervisor_process.py` runs it with non-blocking sockets and a bounded trace.
- **Bridge.** It sends each distinct command once, carrying its tick's snapshot identity. The tick-pinned snapshot keeps GT pose and sensors in one frame. This also fixed a stray `snapshot_listener` reset in `close()`.
- **Runner.** `autodrive_neutral.py --plugin-stack` runs AVLite `SyncExecuter` + `HoldController` at 10 Hz with the real supervisor. Runner heartbeats start after Connect.
- **Tests.** 26 plugin tests pass, including the real process over sockets. An offline smoke run found AVLite's float time sum skipping control on ~20 % of ticks; the stage periods are now 0.99 × the tick period.
- **Live, interlocked, exact zero (60 s).** Connect worked first time.
  - 873 ticks at 100 ms with 0 overruns.
  - 631 requests sent, 622 forwarded, 0 rejected during the observation. 9 were `inhibited` after it ended, when the runner lease expired 292 ms after the observation ended.
  - 233/233 guard acceptances trace to AVLite requests, with the original generation time and deadline = generation + 500 ms.
  - Guard: 0 nonzero-output steps in 81,180. Maximum displacement 4 mm. All children exited 0, the port was released, and all 604 player files were unchanged.
  - Observation age at the supervisor was p95 443 / max 489 ms against a 500 ms limit, which is the tightest margin.
- The first analysis flagged the post-run inhibition; it is retained, and the rule was refined. Evidence `artifacts/s1/20261005T110210Z-s1-supervisor/` (39 files); bilingual [report](stages/S1-supervisor.md).
- **Motion protocol draft v0.1** ([EN](planning/s1-motion-protocol.md)):
  - **Facts:** CAWD with 85.6 N·m total (throttle 0.01 ≈ 4 m/s² ideal); steering slew 183°/s; spawn corridor 0.54/0.74 m.
  - **Decisions:** D1, the front-motor-torque clearing patch (a pre-motion blocker); D2, a calibration request source; D3, freshness via earlier provenance publication.
  - **Stages:** M0 steering only, M1 minimal throttle pulses (0.002–0.01, 0.25 s, caps 0.5 m/s and 0.5 m), M2 expiry/runner-loss stops. Common abort and stop-qualification rules.
- **Stopped for confirmation.** No command that can move the vehicle has been sent. Acceptance count unchanged (3/34).

## 2026-10-05 — Motion protocol v0.1: D1 A, D2, D3 applied; M0 (steering only) passes

- **Approval.** The user replied "approve D1 A, D2, D3; run M0 only", recorded in `planning/s1-motion-approval.json`. M1, M2 and AVLite target-speed motion remain unauthorized.
- **D1 A.** `vendor-sim1-03.patch` (+2 lines) makes the zero-throttle branch also clear the front motor torques. The SIM1-03 player was built from a fresh verified derived copy (273 s, exit 0). The strict serialized comparison against the SIM1 reference is equal.
- **D2.** Added a scripted calibration source (`autodrive_neutral.py calibrate`) and supervisor stage `m0`: throttle 0, steering in {0, ±0.1, ±0.5, ±1}, opened only with the approval record. AVLite motion is still closed in code. The runner passes `-roboracerMotionAuthorized` only for an approved stage, on a player whose build record includes 03 and whose `GameAssembly.so` hash matches. Outbound guard requests are checked against the stage profile.
- **Guard driver.** Added a `calibration` mode and fixed a defect found by its simulation: the driver re-forwarded older skipped requests once the source went silent.
- **D3.** Provenance is now published before the paced reply, and pacing cut to 50 ms. Observation age at the supervisor went from 326/443/489 to 206/304/318 ms.
- **M0 trials.** Every motion trial got a visual pre-Connect review. Four attempts, all retained:
  - 0: not launched (my wrapper's `set -u` broke ROS sourcing).
  - 1: failed closed at full lock, because my feedback bound didn't allow 3-decimal rounding (0.524). The source aborted to zero, with no translation.
  - 2: all criteria met, but the runner's completion check ignored calibration mode, so I stopped it with SIGTERM (clean). Its 5 mm whole-run displacement was passive creep in the 150 s idle tail; it was 1 mm in the M0 window.
  - 3: **pass**, unassisted, in 54 s.
- **M0 results.**
  - +1 = 30° **left**, confirmed by angle sign and by the Ackermann inner wheel.
  - Wheel angles equal the vendor geometry (wheelbase 324, track 236) to within 0.0001°.
  - Outward slew is 183.2–184.6°/s in simulation time. Return to zero is instantaneous, which is vendor behaviour.
  - Expiry case: `lease-expired` while +0.5 was held, and steering was back at 0 within 0.09 ms.
  - 1 mm displacement, encoders unchanged, and motor torque/throttle exactly 0 on all 44,848 steps.
  - All 169 requests were forwarded, with no rejection or fault. All 604 player files were unchanged, and all children exited 0.
- **Analysis fix.** Slew must be measured in fixed steps, because wall-clock stamps are bunched by Unity's per-frame physics catch-up.
- **Tests.** 89 script tests and 26 plugin tests pass.
- **Records.** Evidence `artifacts/s1/20261005T113714Z-m0/` (92 files). Bilingual [report](stages/S1-M0-steering.md).
- **Next.** The user's decision on M1. Acceptance count unchanged (3/34).

## 2026-10-05 — M1 (forward throttle pulses) passes

- **Approval.** The user replied "approve M1 as drafted"; the approval record now lists M0 and M1. M2 and AVLite motion remain unauthorized.
- **Added.**
  - Supervisor/runner stage `m1`: throttle {0, 0.002, 0.005, 0.01, 0.02}, steering exactly 0. Throttle feedback is checked at those values, and the bridge child fails closed at 2 m total displacement.
  - An event-driven M1 calibration source. Each pulse lasts exactly one telemetry interval (~0.20 s after D3). It escalates only under the caps, plus a linear-extrapolation skip rule.
  - All §3 workspace and abort rules, an 18 s armed limit, and a silent finish so the lease expires with zero output.
  - Analysis `autodrive_s1_m1.py`.
- **Trial 1.** The vehicle sequence completed, but the source exited its loop and the runner failed the trial on the child exit. An analysis parser defect (6-field accept events) initially hid the stop timings. Re-analysed, every pulse passes. Fixed both.
- **Trial 2: pass, unassisted, 52 s.**
  - Throttle 0.002 / 0.005 / 0.01 / 0.02 was applied for 0.20 s each.
  - Torque per wheel was exactly 85.6 × throttle / 4.
  - Peak speeds were 0.010 / 0.020 / 0.045 / 0.095 m/s, and travel 2 / 4 / 10 / 19 mm forward, with 0 mm lateral and 0° yaw.
  - Stops came 0.35–0.58 s after generation.
  - After every pulse all motor torque was 0 with brakes applied (D1 verified live).
  - Encoders +180 ticks / +0.589 rad, which matches 35 mm of IPS travel at a 0.059 m radius.
  - All 85 requests were forwarded; observation age was 97/110/120 ms.
  - No fault or rejection, one final lease expiry, all 604 player files unchanged.
- **Finding.** The ideal-force estimate in the protocol overstated the response ~20×; the measured response map replaces it.
- **Records.** Evidence `artifacts/s1/20261005T115944Z-m1/` (67 files). Bilingual [report](stages/S1-M1-throttle.md). 91 script tests and 26 plugin tests pass.
- **Next.** The user's decision on M2. S1-02's box is left for user review. Acceptance count unchanged (3/34).

## 2026-10-05 — M2 (stops under motion) passes; motion protocol v0.1 complete

- **Approval.** The user replied "yes run M2"; the approval record now lists M0–M2.
- **Added.**
  - Stage `m2` (throttle {0, 0.01}, steering 0).
  - A `--m2-case a|b` option and an M2 calibration source, which never sends a zero to stop: stopping is the mechanism under test.
  - A runner heartbeat pause, triggered by a pause file the source writes.
  - Analysis `autodrive_s1_m2.py`.
- **Case a (hang): pass.**
  - One 0.01 request, applied 0.368 s.
  - `lease-expired` came the step after throttle ended, then motor torque 0 with brakes.
  - Peak 0.051 m/s, 18 mm travel; stopped 0.78 s after generation.
- **Case b (runner loss): pass.**
  - The supervisor inhibited exactly 0.5 s after the last heartbeat received (cadence 117 ms; 0.405 s after the runner noticed the pause).
  - It then rejected 12/12 `inhibited`, with 0 forwarded after inhibition.
  - Throttle was applied 0.768 s, then the guard lease expired.
  - 38 mm travel; stopped 0.76 s after the last forwarded generation, with 28 mm after it.
- **Retained analysis correction.** The first check measured inhibition from the pause notice.
- **Both trials.** Unassisted, all children exited 0, the port was released, all 604 player files were unchanged, and there was no guard fault or rejection.
- **Records.** Evidence `artifacts/s1/20261005T122018Z-m2/` (68 files); bilingual [report](stages/S1-M2-stops.md). 92 script tests and 26 plugin tests pass.
- **Next.** Draft the S1-03 target-speed controller proposal from the M1 response map and stop for confirmation. S1-02/S1-04 boxes await user review. Acceptance count unchanged (3/34).

## 2026-10-05 — S1-03 controller proposal v0.1 drafted (no motion)

- At the user's request ("yes draft the S1-03 controller"), wrote [planning/s1-03-controller-proposal.md](planning/s1-03-controller-proposal.md) (EN/ZH), grounded in the M0–M2 measurements.
- **D4** feedback source: recommended supervisor-owned subscription (encoder speed), versus bridge-reported speed.
- **D5** supervisor PI with feedforward:
  - Kp ≈ 0.04, Ki ≈ 0.02, u_max 0.03, rise limit 0.005/frame;
  - hard brake on target 0, on overspeed (v* + 0.15 or 0.5 m/s), and on feedback older than 0.4 s (disarm at 0.6 s);
  - exact steering conversion;
  - about 37° estimated phase margin with 0.45 s of delay.
- **D6** reactive A: `GapFollowController`, follow-the-gap with disparity extension, |steer| ≤ 0.35 rad, v* ≤ 0.3 m/s from steer and front clearance, GT never used for control. `EgoState.velocity` comes from encoders.
- **D7** latency chain on separate clocks; physics progress in simulator time.
- **D8** stages:
  - M3 open-loop identification holds (0.005/0.01/0.02 until 0.3 m/s, 2 s or 0.5 m);
  - M4 closed-loop speed steps (0.1/0.2/0.3 m/s);
  - M5 A on the segment (≤ 6 m / 40 s).
- **Status.** Nothing executed; awaiting confirmation. `max_target_speed_mps` stays 0.

## 2026-10-05 — M3 approved; blocked by a locked desktop (no motion)

- **Approval.** The user replied "approve D4 A, D5, D6, D7; run M3 only". The approval record now lists M3 and D4–D7; M4/M5 are not authorized.
- **Added.**
  - Stage `m3`: throttle {0, 0.005, 0.01, 0.02}, steering 0.
  - An encoder-speed M3 calibration source. Holds end at 0.3 m/s, 2 s or 0.4 m of encoder travel, then a hard brake; each starts from rest; §3 aborts apply.
  - Analysis `autodrive_s1_m3.py` (plant gain, plateau, braking, stop qualification, encoder vs IPS).
  - A bounded Connect retry in the runner.
  - 93 script tests and 26 plugin tests pass.
- **Trials 1–3: Connect lost, retained.**
  - Each trial had a visual pre-Connect review of the player window, which looked normal.
  - The player made no handshake request at all (0 transport requests). Click targeting was identical to the successful M2 runs.
  - Trial 3 retried the click twice, with the same result.
  - All children exited 0, and the port was released. No command reached the vehicle, and nothing moved.
- **Cause.** The GNOME session on display :1 is **locked** (`display-root-locked.png`). The lock screen swallows synthetic input, while the window-level capture still shows the player's own content.
- **Unblocking.** Needs the user to unlock the desktop, and preferably to keep auto-lock off for unattended runs. 3 of the 6 M3 trials are counted conservatively.
- **Evidence.** `artifacts/s1/20261005T123651Z-m3/`.

## 2026-10-05 — M3 passes after unlock; plant is a static gain; proposal v0.2

- **Trial 4.** The user unlocked the desktop ("unlocked, rerun M3"); a full-screen capture confirmed it. Trial 4 passed unassisted (first click, 54 s).
  - Holds 0.005/0.01/0.02 for 2 s each.
  - Steady speed 0.0245/0.049/0.098 m/s: **K = 4.90 m/s per unit throttle** (4.89–4.91), settled within one frame (≤ 0.23 s).
  - Braking in about one frame (4.7/9.3/18.6 mm).
  - Stops 0.55–0.56 s after the last request's generation.
  - Torque exact, D1 release verified, lateral ≤ 1 mm, encoder vs IPS within 0.6 mm.
  - 78/78 forwarded, one final lease expiry, all 604 player files unchanged.
- **M1 reinterpreted.** Its "per 0.2 s pulse" response was this steady-state gain.
- **Retained analysis correction.** Post-hold windows overlapped the next hold; they now end at it. The steady-state gain replaces the initial-acceleration metric.
- **Proposal v0.2.**
  - D5 re-derived: feedforward v*/K plus an integral trim (Ki 0.10, ±0.01), no P term, about 77° phase margin, u_max 0.07, rise limit 0.02/frame.
  - Added M3b: holds 0.03/0.045/0.06, to confirm linearity up to about 0.3 m/s.
  - Awaiting confirmation; M4/M5 not authorized.
- **Desktop note.** `idle-delay` is 0 but `lock-enabled` is still true. A future runner improvement: check the root screen for a lock screen before Connect.
- **Records.** Evidence `artifacts/s1/20261005T123651Z-m3/` (114 files); bilingual [report](stages/S1-M3-identification.md). 93 script tests and 26 plugin tests pass.

## 2026-10-05 — Desktop auto-lock disabled; proposal v0.2 confirmed; M3b passes; M3 gain corrected

- **Desktop.** At the user's request ("please prevent desktop lock"), set `org.gnome.desktop.screensaver lock-enabled` and `ubuntu-lock-on-suspend` to false. `idle-delay` was already 0 and AC idle suspend already 'nothing'; manual Super+L is still possible. Saved a project memory about lock screens blocking Connect.
- **Approval.** The user replied "comfirm" to "confirm or change revised D5 and whether to run M3b". Recorded as confirming proposal v0.2 (revised D5) and M3b; the approval record adds M3B. M4/M5 are not authorized.
- **Added.** Stage `m3b` (throttle {0, 0.03, 0.045, 0.06}, steering 0), sharing the M3 source, with a 0.35 m travel end, a motion-reducing change to stay under the 0.5 m cap. The analysis checks K within ±10 % of 4.90.
- **M3b trial 1: pass**, first click, 55 s.
  - Steady speeds 0.150 / 0.225 / 0.295 m/s, giving K 5.02 / 5.01 / 4.92; the last has one settled frame, because the hold ended at 0.3 m/s.
  - Settled within one frame; brake 0.19 s × speed.
  - Stops 0.55–0.56 s after the last request's generation.
  - Peak hold travel 0.43 m; lateral 0 mm, yaw 0.0°.
  - 70/70 forwarded, one final lease expiry, all 604 player files unchanged.
- **Analysis correction (retained).** The steady-speed window included the first post-hold, braking frame. Fixed, and **M3 was re-analysed: K = 5.02–5.03, not 4.90**. The M3 report carries the correction, and D5 uses K = 5.02 (within the confirmed ±10 % rule).
- **Records.** Evidence `artifacts/s1/20261005T133323Z-m3b/` (40 files); bilingual [report](stages/S1-M3b-identification.md). 93 script tests and 26 plugin tests pass.
- **Next.** M4/M5 await the user's go-ahead.

## 2026-10-05 — M4 built and run; speed tracking blocked by the stale-feedback threshold; v0.3 change request

- **Approval.** The user replied "yes run M4 and M5"; recorded, with M5 to run only after M4 passes.
- **Built.**
  - Supervisor stages m4/m5 with `SpeedLoop` (D5 v0.2: K 5.02, trim, u_max 0.07, rise 0.1/s, overspeed and stale rules) and its own encoder feedback subscription (D4 A).
  - `SpeedStepController` and `GapFollowController` (D6); encoder `EgoState.velocity`.
  - Runner AVLite stage driver with abort rules; analysis with the D7 latency chain.
  - Offline smoke tests of both stacks passed.
- **Attempts 0–2 (no motion).**
  - 0: supervisor `PYTHONPATH` dropped the ROS paths.
  - 1: player segfault at start-up, right after a monitor-layout change.
  - 2: "no feedback yet" was treated as loss, so the supervisor inhibited itself; fixed.
- **Trial 3 (motion).**
  - Step 0.1 OK, but steps 0.2/0.3 missed (means 0.164/0.189, 3–4 brakes).
  - Stop from 0.3 m/s in 0.45 s; stale-feedback cut in 0.20 s, then inhibition; final stop 0.11 s; no guard fault.
  - Cause: feedback age at the supervisor is p95 405 / max 564 ms (frame period p95 284 ms + about 155 ms delivery), so the approved 0.4 s stale rule hard-brakes routinely.
- **Analysis fix.** The stop-from-0.3 m/s window ran into the next step.
- **Proposal v0.3 (change request).** Stale threshold 0.6 s, loss threshold 0.9 s; nothing else changes. Awaiting confirmation; no further M4 or M5 runs.
- **Records.** Evidence `artifacts/s1/20261005T152922Z-m4/` (96 files); [report](stages/S1-M4-speed.md).

## 2026-10-05 — v0.3 confirmed; M4 trial 4 stopped by the guard lease during a slow telemetry gap

- **Approval.** The user replied "yes rerun M4"; recorded as confirming proposal v0.3 (stale 0.6 s, loss 0.9 s). The M4 stale criterion is now 0.6 s + one frame.
- **Trial 4.** Unassisted run, no abort, no guard fault.
  - The supervisor improved: only 3 stale events (11 before).
  - The 0.1 m/s step averaged 0.128 m/s with 0 brake events.
  - Then **telemetry slowed**: frame period p50 286 / p95 328 / **max 648 ms**, against 206 ms in M3b; the player rendered at 34 Hz.
  - One 648 ms gap outlived the approved 500 ms request life, so the guard's lease expired (`state stopped lease-expired 72`). The car stopped, and later requests were rejected as `not-armed`, as designed.
  - Stop and stale cut otherwise worked: stop from 0.3 m/s 0.23 s, stale → zero 0.50 s, inhibit 0.80 s.
- **Cause.** Environment. `nvidia-smi` shows 9.5 of 10 GB of GPU memory held by two of the user's `thellmbook` Python processes (7.6 + 1.0 GB). The simulator is starved, which probably also explains attempt 1's start-up segfault.
- **Status.** Not something to tune away. Asked the user to free the GPU (or approve a longer request life); M5 not run.

## 2026-10-05 — GPU freed; M4 passes; M5 (reactive A) passes — S1-03 demonstrated

- **GPU.** At the user's instruction ("You can kill the Python processes to free the GPU memory"), sent SIGTERM to the two `thellmbook` Jupyter kernels (PIDs 952235, 1166408; 7.6 + 1.0 GB). Both exited within 4 s; GPU memory went from 9.5 GB to 874 MiB, and the Jupyter server was left running. The player is back at 60 Hz, with a frame period of p50 210 / max 241 ms.
- **M4 trial 5: pass.**
  - Speed means 0.109 / 0.212 / 0.311 m/s (±0.05 needed), overshoot ≤ 0.037, 0 brake events.
  - Stop from 0.3 m/s 0.34 s; blackout → zero throttle 0.50 s, inhibit 0.80 s.
  - 2.26 m straight; one final lease expiry; no guard fault.
  - Latency p50: generation → supervisor decision 0.12 ms, → guard accept 145 ms; accept → applied 1 ms (simulation time).
- **M5 trial 1: pass.** `GapFollowController` drove 6.06 m in 21.0 s through AVLite (D6), with steering −0.068 to 0 rad and encoder speed ≤ 0.35 m/s.
  - Side clearance ≥ 0.28 m, front ≥ 1.49 m; final stop 0.17 s.
  - 267/267 forwarded, no stale events, one final lease expiry, no guard fault.
  - Finding: A does not center; right clearance shrank 0.54 → 0.28 m as the corridor widened. Noted for laps.
- **Records.** All 604 player files unchanged. 94 script tests and 39 plugin tests pass. Evidence `artifacts/s1/20261005T152922Z-m4/` (159 files) and `artifacts/s1/20261005T160657Z-m5/` (39 files); bilingual reports [M4](stages/S1-M4-speed.md) and [M5](stages/S1-M5-reactive.md).
- **Next.** The S1-02/03/04 check boxes await user review. Laps (S1-05/06) and higher speeds are not authorized.

## 2026-10-06 — S1-05 non-motion parts: independent scorer, episode entrypoint, manifest; M6 lap proposal

- **Request.** "go on with S1-05". No motion was run.
- **Scorer** (`scripts/roboracer_scoring.py`).
  - C0 geometry comes from the player's own collider export: centerline 31.33 m, width 1.14–2.55 m, footprint x −0.101..0.425 / y −0.145..0.143 m about the rear axle.
  - Laps need cumulative progress ≥ k·L with ordered 25/50/75 % gates. Contact and off-track use the swept footprint, with de-duplicated events.
  - Two fixture expectations were wrong, not the scorer: lap time is resolved to one frame, and on a curve the front-outer footprint corner is the closest point.
  - Added a `plot` subcommand (walls drawn with holes) and a max single-frame progress audit value. Inside a hairpin the projection legitimately outruns the car, by up to 0.59 m per frame in rollouts.
- **Episode entrypoint** (`scripts/roboracer_episode.py`).
  - `live`: m4/m5 only, through the existing runner. `recorded`: re-scores existing results. Both use the shared `roboracer.episode/1` schema plus `roboracer.episode-manifest/1`.
  - The initialization is recorded as a manual pre-Connect review, with `unattended_reset: false`.
  - Recorded M5 trial 1: 6.06 m, clean, min clearance 0.123 m. Recorded M4 trial 5: 2.26 m, clean. Binaries match the SIM1-03 build record.
- **Lap check** (`scripts/roboracer_rollout.py`, offline).
  - The 2-D cast matches recorded scans: full scan p95 7.9 mm, side sectors ≤ 4 mm.
  - Over one lap, A comes within 6–11 mm of a wall. A-lap (`LAP_PARAMS`: centering 0.5, side speed cap, slowdown /0.8, same 0.35 rad / 0.3 m/s) keeps 0.105 m and is insensitive to 0.25–0.6 s of latency.
  - `GapFollowParams` defaults are exactly A, and a test pins this.
- **Proposal.** [s1-05-lap-proposal.md](planning/s1-05-lap-proposal.md) v0.1 asks for D9 (A-lap), D10 (M6: M5 limits, end at 33 m or 200 s, fail-closed track bounding-box containment instead of the start radius) and D11 (≤ 3 trials, stop at the first failure).
- **Records.** 106 script tests and 41 plugin tests pass. Evidence `artifacts/s1/20261006T051902Z-s1-05/` (27 files). Bilingual [report](stages/S1-05-episodes.md).
- **Next.** M6 awaits confirmation. S1-02 to S1-05 check boxes are unticked.

## 2026-10-06 — M6 confirmed and run: A-lap completes one C0 lap in 3/3 trials

- **Approval.** "approve D9, D10, D11; run M6". The approval record gains M6, D9–D11, and a narrowed not-authorized list.
- **Wiring** (commit `8a8fa7e`).
  - M6 stage in the supervisor and runner (M5 limits).
  - Fail-closed box containment in the bridge (`outside_containment`) instead of the start radius.
  - The stack selects `LAP_PARAMS` and records `controller_params`; it ends at 33 m or 200 s.
  - `roboracer_episode.py live --stage m6`.
  - Offline smoke run: the supervisor accepts M6, and the stack loads A-lap.
- **Trials** (fresh player each time; visual pre-Connect review; GPU free at 858 MiB). All 3 finished on distance with one lap each by the independent scorer, and no contact or off-track.
  - Clearance 0.105 / 0.104 / 0.104 m; lap 122.7 / 123.3 / 122.8 s; final stop 0.21 / 0.21 / 0.32 s.
  - Supervisor forwarded everything; one final lease expiry per trial; no guard fault.
  - Generation → guard accept p50 about 105 ms; all children exited 0; the player is unchanged.
  - The offline rollout predicted 0.105 m clearance. Steering clamps at 0.35 rad in the tightest hairpin, as predicted.
- **Records.** 107 script tests and 41 plugin tests pass. Evidence `artifacts/s1/20261006T054031Z-m6/` (114 files). Bilingual [report](stages/S1-M6-lap.md).
- **Next.** The S1-02 to S1-05 check boxes await user review. S1-06 and S1 acceptance are not claimed.

## 2026-10-06 — S1-06: first timing/resource/episode measurements; M1 protocol drafted

- **Request.** "go on with S1-06". In the plan's run matrix, M1 means: three circuit runs, each F1 fault case ×3, and five timing windows (10 s warm-up + 120 s), frozen before the runs. No motion was run.
- **Tool.** `scripts/roboracer_timing.py` measures, per window and per clock domain:
  - telemetry and source rates and ages, observation and feedback age at request, and clock bound;
  - tick and request rates;
  - the latency chain, including command → first observation acquired after it applied;
  - per-process CPU/RSS and GPU;
  - stop and episode results.
  It checks each value against the frozen S1 limits.
  - Two first-pass errors, both caught on the real traces and fixed: guard event text starts with an event number, and only the first runner heartbeat is traced, so the runner lease is checked through inhibited decisions instead.
- **Runner.** GPU sampling via `nvidia-smi` once per second in a separate thread (`gpu.jsonl`), so a query (~22 ms) never delays heartbeats. Checked on this host.
- **First measurements** (M6 laps, preliminary, 3 × 120 s windows, all complete):
  - telemetry 5.8 Hz (period p95 212 ms, max 248 ms); real-time factor 1.000;
  - observation age at request p95 ~270 ms, max 334 ms; command → observed p95 ~225 ms;
  - ticks 100.0 ms with 0 overruns; supervisor decision 0.15 ms;
  - CPU: player 138 %, bridge 28 %, stack 3 % of one core.
  - All frozen limits held. Steering sits at its clamp by design.
- **Protocol.** [s1-06-m1-protocol.md](planning/s1-06-m1-protocol.md) v0.1 asks for:
  - D12: count the M6 laps as the circuit demos;
  - D13: five M6 timing laps;
  - D14: nine F1 cases ×3, injected at 6 s on the straight;
  - D15: F1 stop within 1.5 s and ≤ 0.40 m after injection at 0.3 m/s;
  - D16: runner error cleanup disarms and observes the stop before killing processes.
  It also drafts S2 budgets.
- **Records.** 111 script tests and 41 plugin tests pass. Evidence `artifacts/s1/20261006T064500Z-s1-06/`. Bilingual [report](stages/S1-06-measurements.md).

## 2026-10-06 — M1: D13 timing windows pass; F1 tooling; F1-1 trial 1 fails v0.1 timing (stopped for D17)

- **Approval.** "approve D12, D13, D14, D15, D16; run M1". Recorded in the approval record (commit `4e3f6fc`).
- **D13.** Five fresh M6 laps, each with a complete 10 s + 120 s window and GPU sampling. All clean (1 lap each, 0.104–0.106 m) and within every frozen limit.
  - Observation age max 346 ms; command → observed p95 ≤ 235 ms; 0 tick overruns.
  - GPU p50 22–25 %, max 70 %, 1.69 GB.
  - Player CPU 134–137 % of one core.
- **F1 tooling** (`7b811bf`):
  - stage-triggered injections at 6.0 s;
  - the guard-driver disarm/rearm trigger, tested against the model guard;
  - D16 runner-error stop; F1-8 runner kill and reaping;
  - `roboracer_f1.py`.
  - F1-2 and F1-4 hooks wrap stack-process instances, so the plugin source is unchanged. A NaN scan is rejected as `scan layout differs ...` (the protocol text said `non-finite reading`).
- **Attempts.**
  - F1-1 attempt 1 failed at stack startup (freeze mapped in every mode; fixed `4e7b92c`; no motion).
  - Attempt 2 was refused before launch (output directory not fresh).
- **F1-1 trial 1: fail** under v0.1.
  - Stop 1.606 s after the injection request (limit 1.5); throttle until +1124 ms (deadline +1100).
  - The freeze took effect 0.55 s after the request (it rides the next paced reply and acquisition). The 500 ms observation-age limit and the 500 ms lease then allowed the rest by design.
  - Detection order correct; travel 0.358 m; no contact.
  - From onset: stop 1.05 s, last throttle +0.57 s.
  - My abort check (≤ 0.6 s) also ignored the 100 ms tick.
- **Stopped** per protocol. D17 asks for (A, recommended) onset-referenced timing with an abort bound of ≤ 0.7 s, or (B) a widened F1-1/F1-2 bound. Trial 1 stays a recorded failure either way.
- **Records.** 122 script tests and 41 plugin tests pass. Evidence `artifacts/s1/20261006T061501Z-m1-timing/` and `artifacts/s1/20261006T064801Z-m1-f1/`. Bilingual [progress report](stages/S1-06-M1-progress.md).

## 2026-10-06 — Stack overview written

- **Request.** "explain the current autonomous software stack ... is AVLite actually running?" followed by "write this down".
- **Doc.** Bilingual [stack overview](architecture/stack-overview.md): AVLite runs as the framework (plugin loader, `executor_factory`, the `SyncExecuter` 10 Hz tick, interfaces); no AVLite algorithm runs; all driving logic is roboracer plugin code (bridge, snapshot assembler, gap-follow, supervisor); the guard is in the simulator. Includes the evidence and the limits of what has been exercised.
- **Status.** M1 F1 runs remain paused for D17.

## 2026-10-06 — Chinese versions removed

- **Request.** "remove all Chinese version docs".
- **Done.** Deleted all 38 `*.zh-CN.md` files and removed every link to them from the English docs (88 lines). `SIM1-deferral.zh-CN.md` had no English counterpart; its subject, the not-adopted 1.1-B amendment, remains in English (`planning/installed-binary-first-amendment.md`). Historical mentions of past Chinese reports in this log and in review notes are kept as history.
- **From now on** reports and proposals are English only.

## 2026-10-06 — Lap video: replay renderer and AutoDRIVE-window recording

- **Request.** "do both and only record AutoDRIVE window area not entire screen".
- **Replay.** `scripts/roboracer_replay.py` draws a top-down replay from the recorded truth over the C0 geometry: footprint, trail, speed/target/steering traces, clearance and progress. It is a reconstruction, not simulator footage; LiDAR scans are not shown, because runs keep only per-scan hashes. Default window: run phase − 3 s to finished + 3 s. Timing lap 5: `artifacts/s1/20261006T061501Z-m1-timing/replay/timing5-replay.mp4` (147 s, 1280×720, 15 fps).
- **Recording.** `--record-video` (runner and `roboracer_episode.py live`) starts `ffmpeg x11grab -window_id <AutoDRIVE client window>` right after Connect: only the AutoDRIVE window, 15 fps, libx264 ultrafast, written to `run-01/player-window.mp4`. It is optional (its exit never aborts a run), and cleanup stops it before the player.
- **Checks.** Single-window capture was verified on a test window: exact size, window content only, no desktop. Capturing the decoration frame fails on odd heights, so the client window is used. Not yet exercised live: the first use will be the next approved M1 run (enabled in the F1 run script). Its CPU appears in `resources.jsonl` as `recorder`.

## 2026-10-06 — Extra M6 lap with AutoDRIVE-window video

- **Request.** "run a lap and record a video". Recorded in the approval record (`35daf67`) as one extra M6 lap, same envelope, with `--record-video`.
- **Lap: clean.** 1 lap at 123.1 s; 0 contact / 0 off-track; 0.105 m; final stop 0.37 s; every frozen limit held in the 120 s window; player unchanged.
- **Video.** Only the AutoDRIVE window: `artifacts/s1/20261006T075048Z-m6-video/lap1/run-01/player-window.mp4` (236.6 s, 1280×720, 15 fps, 92 MB), plus a trimmed copy `lap1-autodrive-window.mp4` (Connect → finished + 5 s; 150 s, 20 MB). Recorder cost: 9.5 % of one core, 188 MiB; telemetry and observation ages unchanged versus the D13 windows.
- **Runner exit 1, after the lap.** The read-only ROS observer exited 1 at cleanup: rclpy's SIGTERM handler shut the context down between `rclpy.ok()` and `spin_once` ("context is not valid"). The runner flagged "Owned-process cleanup requires review", so the episode export says *incomplete*; the driving result is unaffected. First occurrence in about 20 runs; the recorder's load plausibly shifted the timing. Fixed: an error raised after the context has shut down is treated as the requested stop (`shutdown_race` in the observer status); other errors still raise. The run is kept as recorded.

## 2026-10-06 — Working environments moved from /tmp to ~/roboracer-work

- **Request.** "move /tmp/roboracer-work to ~/roboracer-work". Reason: Ubuntu 22.04 clears `/tmp` at boot, which would delete the AVLite/Devkit virtualenvs, the patched SIM1-03 player and the Unity toolchain (99 GB).
- **Move.** A rename on the same filesystem (`/dev/nvme0n1p2`); nothing was running from it. Rewrote the old prefix in 33 runtime files: the `bin/` scripts of the three virtualenvs, the Devkit colcon `install/` setup scripts, and two colcon `build/` prefix files. Logs, git metadata and pip `direct_url.json` are left as history.
- **Run context.** New `~/roboracer-work/run-context.json`: the original `artifacts/preflight/20260928T124339Z/run-context.json` (sha256 `e252740b…`, kept unchanged as evidence) with only the path prefix changed, plus a `relocation` note. Runs now pass this context.
- **Repo.** Tests that use the Unity toolchain or the authoring source now resolve `~/roboracer-work` (they had silently skipped while the path was missing); the `scripts/README.md` examples are updated. Historical evidence and stage reports keep their original `/tmp` paths.
- **Checks.** 122 script tests (none skipped) and 41 plugin tests pass. The Devkit bridge imports from the new install, with the runner's environment. The offline M6 stack + supervisor smoke run passes. The player is byte-identical (604 files).

## 2026-10-07 — D17 A; M1 F1 matrix 27/27 under protocol v0.2

- **Decision.** "resume D17" → the user chose **A** (time F1 stops from the fault onset). Recorded as D17 plus a v0.2 stage approval; protocol §8.
- **Analysis.** `roboracer_f1.py --criteria v0.1|v0.2`. v0.1 still reproduces trial 1's failure exactly.
  - Fix: the abort and F1-5 final-stop references are the tick *before* the first "stopping" row, because the row is written before the phase switch. This corrects a 100 ms error; trial 1 still fails v0.1.
- **Pre-motion refusal.** The motion build-record check compared the recorded `/tmp` player path. It now maps the documented relocation and checks both player binaries by hash (`68edb7f`).
- **Runs.** 27 fresh-process F1 episodes with window recording, all reviewed before Connect. **All pass v0.2.**
  - Stop after onset: 0.37–1.33 s. Travel after injection: 0.05–0.33 m. Clearance ≥ 0.30 m.
  - No guard fault; the player is unchanged.
  - Results per case in the [M1 results](stages/S1-06-M1-results.md).
- **Open.** Player shutdown hang in 4/27 runs: SIGKILL after SIGTERM, even with the grace raised to 15 s (`83aa1a9`). It happened after stop and disarm, and the guard traces are complete. All four were recording runs (correlation only); a no-motion check is proposed.
  - F1-8 recordings end when the runner is killed.
- **Records.** 123 script tests and 41 plugin tests pass. Evidence `artifacts/s1/20261007T051931Z-m1-f1-v02/` (1,009 files).

## 2026-10-07 — Player shutdown hang: stationary check and diagnostics

- **Check (no motion).** Two stationary, interlocked S1-stack sessions (guard observe, HoldController zeros, player without motion authorization, 30 s), one with window recording and one without. Both shut down cleanly: player exit 0, cleanup 2.2 s. Evidence `artifacts/s1/20261007T065223Z-hang-check/`.
- **Reading.** At the observed ~15 % hang rate, two clean sessions neither confirm nor rule out the recorder; the hangs so far were all driving runs. A stationary A/B large enough to tell would need dozens of reviewed sessions, so I stopped at two.
- **Diagnostics instead.** If the player is alive 10 s after SIGTERM, the runner now writes `player-hang-diagnostics.json` (per-thread name, state and kernel wait channel, plus process status) before the remaining 5 s and SIGKILL. `ptrace_scope` = 1 rules out attaching gdb. The next hang will show where the player is blocked.
- **Tests.** 125 script tests pass.

## 2026-10-07 — SIM1-03 resumed: reset tooling; current player fails closed after GUI Reset

- **Request.** "go on" after M1. SIM1-03 is required before S1 acceptance (amendment 1.2). All work disarmed or interlocked; no motion authorization.
- **Tooling** (`56e214d`). Guard-driver `reset` mode (scene-load disarm, episode +1, not-armed / wrong-episode / new epoch / stale-epoch / replay checks), tested against the model guard. Runner `gui-reset` action: Reset click, reviewed reload, reconnect, C0-start check, heartbeats during the wait. Bridge allows one reconnection in reset mode.
- **Live r0 on the current player.** The Reset produced `state disarmed scene-load`, the scene reloaded at the spawn, and the reconnect succeeded. Then the bridge rejected the first new frame: `Duplicate or out-of-order telemetry seq 1 after 14`, and failed closed. All processes exited 0; no motion.
- **Cause.** `RRTelemetrySeq` is an instance field of the in-scene Socket (`Socket.cs:34`) and restarts after a scene reload, contrary to `PROTOCOL.md`. `Guard.emits` is not cleared on scene load either.
- **Proposal (D18).** Patch `vendor-sim1-03b` (static sequence; clear `emits` on scene load), rebuild into a new player directory, requalify without motion (SIM1-01/02 once, reset ×3). Motion on the new build would need separate approval. [SIM1-03 report](stages/SIM1-03-reset.md).

## 2026-10-07 — Direction: official simulator (amendment 1.3 draft)

- **User.** "It takes a lot of time to build a patched simulator. I think we shouldn't struggle on this; we should use the official simulator to integrate." D18 (patch and rebuild) is therefore not pursued.
- **Draft.** [Amendment 1.3](planning/official-simulator-amendment.md), PRE option B. The official player (`AutoDRIVE Simulator [Linux]`, Nov 2023) is present and unchanged.
  - Proposals: D19, a bridge-side command lease plus a simulator-kill watchdog for bridge loss; D20, explicitly revised S1 acceptance (receipt-age freshness, bridge loss as containment, SIM1-03–06 withdrawn); D21, the requalification order on the official build.
  - Existing patched-build evidence stays valid for that build. No motion on the official build without per-stage approval.

## 2026-10-07 — D18: patch 04 built and requalified; SIM1-03 passes 3/3; simulator frozen

- **Decision.** "D18, please" (after the comparison with the official-simulator route; amendment 1.3 is not adopted).
- **Patch.** `vendor-sim1-04.patch` (static `RRTelemetrySeq`) plus `Guard.cs` clearing `emits` on scene load (`2eac698`). Repaired the source repository's git worktree links broken by the move.
- **Build.** Derived copy 86 s; Unity build 321 s; the scene is equal to the SIM1-03 player in every section. Player `~/roboracer-work/autodrive-builds/20261007T-sim1-04/AutoDRIVE.x86_64/AutoDRIVE.x86_64`, GameAssembly `44f9e735…`.
- **Requalification (no motion).**
  - Guard scenario: 16/16 phases, 0 nonzero output steps, Devkit-loss lease cleared in 35 ms.
  - LiDAR freeze: pass.
  - **SIM1-03 reset 3/3** (19/19 checks each; spawn offset 0.000 m).
  - Player unchanged.
  - One reset attempt failed on my tooling (no heartbeats during the Reset click inhibited the supervisor); fixed in `0ac6c29`.
- **Policy.** The simulator is frozen: no further vendor patches.
- **Next.** Motion on the new player needs approval; I propose one M6 regression lap. SIM1-04 to SIM1-06 remain for S1 acceptance. [Report](stages/SIM1-03-reset.md); evidence `artifacts/simulator-build/20261007T-sim1-04/`.

## 2026-10-08 — Regression lap on the patch-04 player: no change

- **Approval.** "approve one regression lap on the new build." Recorded (`ff6b563`).
- **Lap.** Clean: 1 lap, 122.9 s, clearance 0.106 m, stop 0.34 s, all frozen limits held, exit 0, player unchanged. The runner's motion build-record and hash check accepted the new player.
- **Comparison.** 10/11 measures inside the range of the nine previous-build laps; the 11th is the path overshoot past 33 m (+1.5 mm). The patch-04 player is now the qualified player.
- **Evidence.** `artifacts/s1/20261008T062420Z-m6-regression/` (window video included). [Report §6](stages/SIM1-03-reset.md).
