# Research Artifact Review

Date: 2026-09-28. Reviewer: main agent.

- Checked that local Markdown targets in the report, source register, log and validation request exist; no missing targets found.
- Checked fenced-code delimiter balance.
- Parsed `avlite_contract_probe.py` using Python `ast.parse`; syntax accepted. Did not execute the probe or import its AVLite dependencies.
- Re-read critical source supporting delegated findings: profile save/load, sensor dataclasses, command fields, localization gate, loader/unregister, executor stop, headless exceptions/launch, mapping truth path, FTG/ICP limitations, A2RL publication/private scheduling, and modern simulator APIs/ROS message definitions.
- Independently confirmed the two AVLite committed trees differ only by one `.gitignore` line and obtained the simulator ref advertisements.
- Compared all three source-repository Git statuses with `local-inventory.json`; unchanged.
- Confirmed the report distinguishes source/document evidence, engineering proposals, unresolved questions and absent runtime evidence. No feature acceptance or benchmark result is asserted.

Outstanding at the original research handoff: optional API probe authorization; selected simulator checkout/environment qualification; target event, hardware and technical-direction confirmation. The later [decision follow-up](../decision-follow-up.md) supersedes that pending status where decisions or new evidence exist.

## Simplified Chinese translation review — 2026-09-28

- Main-agent comparison covered all translated sections, including delegated sections 4–6. Technical claims, evidence qualifications, limitations and pending decisions remain aligned with the English report.
- Confirmed 12 numbered sections, matching subsection counts and 125 table rows; all 84 original link targets remain in the same order. Reciprocal language-navigation links were added separately.
- Inline-code occurrences match within every section. Two word-order differences follow Chinese grammar and preserve meaning. Commit hashes and discrepancy/decision IDs match in order.
- Mermaid node identifiers, edges and graph structure are unchanged; display labels are translated. Fenced blocks are balanced, and local link targets exist.
- This review checks document fidelity only. It adds no installation, runtime, performance or safety evidence and grants no approval to proceed.

## Decision follow-up and planning review — 2026-09-28

- Independently inspected the Build-linked Master BOM and relevant official driver/manufacturer sources; recorded differences from static Build prose in the decision addendum.
- Reviewed every field of the authorized probe output, including expected localization-gate stderr. Confirmed its script hash is unchanged and the temporary profile directory was removed. This adds only the scoped runtime evidence listed in the addendum.
- Compared the three AVLite/A2RL source-repository statuses with the original inventory, normalizing its omitted terminal newline; all match. The workspace's new valid Git state is separately recorded.
- Reviewed the draft with an independent agent and corrected baseline/threshold/acceptance ordering, publisher-crash ownership and ambiguous fault/run-count coverage. The main agent reviewed and integrated those recommendations.
- Checked local links and fenced-block balance across all Markdown documents. The draft contains 34 unique unchecked todos and five complete feature stages. No implementation item is marked complete.
- Current gate: first plan review, followed by a substantive second review and explicit final-plan approval. No simulator or functional plugin work has started.

## AutoDRIVE-first plan revision review — 2026-09-28

- Applied the user's simulator-direction feedback in plan v0.2. Reviewed the stage changes as an integration redesign, including early Humble/Devkit transport, actuation conversion, supervised expiry and externally advancing simulator clocks.
- Independently re-read the AVLite sources underlying delegated advice: atomic snapshots and buffer lifetime, GT/localization gating, held-command publication, the controller's `sim_dt` argument, reset-before-command-clear ordering, Sync stop behavior, factory injection and headless exception handling. No AutoDRIVE runtime claim follows from those source checks.
- Checked 170 local Markdown link occurrences across nine Markdown documents; no missing target, unbalanced fence or trailing whitespace was found. Confirmed 34 unique unchecked implementation todos and zero completed items. `git diff --check` passed for tracked changes; the direct document checks also covered the untracked plan/addenda.
- Compared HEAD, branch and worktree status for the target AVLite, reference AVLite and A2RL repositories with `planning-baseline.json`; all matched. The authorized probe script's SHA256 also remained unchanged. No runtime probe was repeated.
- Current report notes in English and Chinese both supersede the historical Gym-first recommendation; historical research/probe/inventory evidence is preserved. Gym remains a later candidate with no mandatory first-release delivery.
- Reviewed a second delegated pass over the rewritten plan. Clarified S1 operational limits before motion, supervisor/runner failure domains and downstream-expiry blockers, display-backed unattended operation versus optional headless operation, and qualification of every M3 start/heading. These are proposed acceptance obligations, not observed capabilities.
- These are source/documentation checks, not plugin acceptance, simulator qualification or performance measurements. Final-plan approval, remaining architecture/scope choices and approved runtime qualification remain pending.

## ICP reuse and narrowed first-release review — 2026-09-28

- Checked that plan v0.3 records the user's selected ICP route, approved map/tracker/command/supervisor design and exclusion of dynamic/multi-car behavior from mandatory first-release acceptance. PF/AMCL implementation and programmable opponents no longer appear as required todos.
- Reviewed delegated feedback against the built-in ICP and Pure Pursuit sources. Assigned plugin ownership of valid stack velocity after GT is disabled, and limited wrong-initialization rejection to defined detectable cases instead of promising universal global-pose validation from local ICP.
- Verified 173 local Markdown link occurrences, balanced fences and whitespace across the documentation; `git diff --check` passed. Confirmed 34 unique unchecked implementation todos and zero completion marks.
- Compared target AVLite, reference AVLite and A2RL HEAD/branch/worktree states with the recorded planning baseline; all matched. The existing authorized probe script hash is unchanged. No tests, simulator, ROS node or feature code were executed for this revision.
- English/Chinese current-status notes and the decision follow-up reflect the same confirmed choices. Remaining focused questions concern delivery boundary, static-obstacle response and ICP initialization/recovery; their answers and final-plan approval are still pending.

## Delivery/recovery confirmation and acceptance review — 2026-09-28

- Plan v0.4 closes R2-01–03 in accordance with the user's acceptance of all recommendations. Verified that static avoidance is required for passable cases, blocked-track stopping is distinct from completion, and physical-car work remains outside the first release.
- Checked the separation between configured initial poses for healthy batches and failed localization episodes requiring operator recovery. Failed or unstarted episodes cannot be hidden as successful automatic resets.
- Reviewed proposed run-count arithmetic: M3 is 50 × K episodes per algorithm, M4 is 30 × K, and M5 adds 10 × K held-out episodes, where K awaits the minimum-layout decision. M1/M2 timing windows each have their own warm-up. These are proposed protocols, not accepted performance values or executed runs.
- Documentation checks passed: 173 local links, balanced fences, no trailing whitespace, 34 unique unchecked todos and `git diff --check`. No implementation item was marked complete and no runtime test was executed.
- Current focused questions are minimum scenario coverage and the display requirement for unattended operation. Final-plan approval and bounded runtime qualification remain pending.

## Final-review plan v1.0 — 2026-09-28

- Applied Q16/R2-04 and Q17/R2-05: one qualified track, five initial conditions, left-pass/right-pass/fully-blocked static cases, and graphical/virtual-display unattended operation. All five R2 preference decisions are reflected in the full plan, approval summary, decision record and English/Chinese report status notes.
- Reviewed the delegated final audit against source. The AVLite actuation gate requires a localization provider; M3 A/B therefore share the same qualified ICP/motion state with GT filters disabled. The stock Pure Pursuit controller returns acceleration; reuse of its lateral geometry does not imply that its full command is the approved target-speed payload.
- Preserved the independent supervisor as required architecture, with complementary downstream expiry. Fixed per-scenario lap/progress targets, terminal failures, horizon-freezing and attempted-episode accounting. Standard AVLite GUI visibility/profile checks follow the official plugin guide.
- Checked the run matrix: 100 M3 episodes, 30 M4 static episodes, and 10 additional M5 held-out episodes on C0. M5's three fresh-environment smoke runs include its three nominal laps without double counting. Baselines, timing windows and fault repetitions remain separately identified.
- Documentation checks passed across 10 Markdown files: 178 local-link occurrences, balanced fences, no trailing whitespace and 34 unique unchecked implementation todos. `git diff --check` passed; direct checks also covered untracked planning/addendum files.
- Target AVLite, reference AVLite and A2RL HEAD/branch/worktree states match `planning-baseline.json`. The approved contract-probe script hash is unchanged. No simulator, ROS node, dependency installation, feature test or new runtime probe was executed.
- These are planning/source/documentation checks only. v1.0 awaits explicit final approval for scoped PRE + S1; the concrete pre-motion protocol, measured performance thresholds and later stage-entry confirmations remain the stated execution gates.

## Approved PRE evidence review — 2026-09-28

- Recorded the user's explicit v1.0/PRE + S1 approval and preserved the separate motion/performance/later-stage gates. Reviewed the new preflight report against manifests and raw logs; incomplete or failed checks are not marked accepted.
- Confirmed startup-only scope: owned Unity process, 15-second observation bound, explicit log/XDG locations, no API server or control publisher, controlled termination and reaping. Exit code 0 coexists with rendering/socket errors and does not establish sensor or closed-loop qualification.
- Checked system-Humble import/serialization results and the corrected cross-process DDS failure (20 publication calls, zero received). Retained the first invalid-topic probe attempt separately. The corrected disposable probe's retained text matches its recorded SHA256.
- Reviewed pinned historical source directly; distinguished it from current-branch agent findings and from the unqualified installed binary. Verified source repository states and nine selected simulator fingerprints after runtime probing.
- Documentation checks passed across 11 Markdown files: 214 local-link occurrences, balanced fences, no trailing whitespace, and 34 unique unchecked todos. All 14 preflight JSON evidence files parsed; `git diff --check` passed. `git check-ignore` confirms runtime artifacts are excluded by the new workspace rule.
- PRE remains blocked by dependency-download/display/DDS restrictions and incomplete live API qualification. S1 feature implementation has not started. No core change, physical actuation, publication or attempt to bypass an execution-policy denial occurred.

## Resumed PRE evidence review — 2026-09-28

- Reviewed approved-host access recovery separately from the continuing sandbox PyPI denial. Installation reports/freezes and final pip checks establish the two isolated environments; no blanket permission or stock Devkit compatibility claim was substituted.
- Checked owned graphical startup and receive-only API evidence: Manual mode, zero actuator replies, one telemetry frame, 1081 ranges and a 1280×720 camera image. Reported 20 Hz metadata is not a measured stream. Observer SIGTERM/reaping and the parent's total cleanup duration are stated explicitly.
- Reviewed cross-environment recorded-sensor delivery against both child logs: byte matches passed with NumPy 1.26.4 on the sender and NumPy 2.2.6/AVLite 0.6.3 on the receiver. This is recorded-input transport, not a live plugin or closed-loop result.
- Preserved the NumPy 2/cv_bridge failure, Python 3.10/attrdict failure, initial missing-PyYAML failure and premature import diagnostic. Corrected the sensor parent's copied topic metadata with the original value/reason retained; no executed result changed.
- Fresh installed-import and unchanged source-contract/profile checks passed; source/binary baselines remained unchanged. PRE-01 alone is checked. PRE-02–04 and all feature items remain unchecked; stopping, freshness, scene/scoring/reset and motion approval are still open.
- Documentation/evidence checks passed: 13 Markdown files, 249 local links, balanced fences/whitespace, 34 unique todos (1 checked, 33 unchecked), 40 valid JSON files, 96 indexed evidence-file hashes and both DDS probe-source hashes. `git diff --check` passed and runtime artifacts remain ignored. No simulator/ROS process is intentionally left running; owned children were reaped and 4567 was released.

## Continuous neutral PRE evidence review — 2026-09-28

- Reviewed both attempts against raw Bridge/ROS traces and owned-window screenshots. Each delivered 120 messages on each of eight topics. First-frame float32 range/RGB content matches passed for all four connection segments. Manual mode and zero-only replies were retained; no motion, plugin execution or braking claim.
- Preserved initial TF publisher growth and shutdown failures. Confirmed that the corrected attempt held publisher count at 10, exited all children normally and released resources. Recorded pacing differs between attempts, so the rate difference is not attributed solely to the TF change. Short-run RSS does not establish long-run stability.
- Reviewed asset parser errors separately from successful builtin geometry, mesh and script-header extraction. Recorded source/asset geometry and timing-field discrepancies without inventing missing custom type trees, source acquisition timestamps or receiver expiry.
- Updated PRE-02 only after corrected dependency/build/live/lifecycle evidence passed. PRE-03/04 remain unchecked; new capability blockers and three concrete route options are in both report languages. A separate instrumented-build preparation scope awaits the user; no acceptance change or simulator implementation has been adopted.
- Documentation checks passed across 15 Markdown files with 282 local links, balanced fences/whitespace and 34 unique todos (2 accepted, 32 unchecked). All 24 JSON files present at that check and all runtime JSONL rows parsed. Later result/index artifacts were validated separately. `git diff --check` and artifact-ignore checks passed.
- Rechecked unchanged three source-repository states and nine selected simulator fingerprints. All six owned child PIDs are absent; approved-host listener output shows no 4567 listener. The final run index records evidence-file hashes. Original installation/shared source trees remain unchanged; Unity's shared temporary cache exception remains documented.

## 2026-09-29 — Option A preparation and amendment review

- Reviewed the fixed-source inventory directly: 223/223 tracked C# files materialized, clean inspection worktrees, selected package/editor metadata reachable; no installation/import/build/runtime claim inferred. Preserved the interrupted lazy-fetch inventory and GitHub API rate limit.
- English/Chinese feasibility reports agree on evidence levels, source identity, toolchain/host risk, pending activation route and the motion hold. The draft amendment preserves original acceptance and labels all new interfaces, commands and stages as proposed.
- Documentation checks: 18 Markdown files, 351 local-link occurrences, balanced fences and no trailing whitespace. Original checklist: 34 unique IDs, only PRE-01/02 accepted. Amendment: 10 additional unique IDs, all unchecked. `git diff --check` passed; artifacts remain ignored. Generated index links were checked again after finalization.
- Three original repository states and nine selected installed-player fingerprints match the prior run; both pinned source worktrees are clean. No simulator/editor/ROS process was launched. The check is scoped integrity evidence, not exhaustive write tracing.
- JSON validation and evidence hash verification are recorded in `artifacts/preflight/20260929T051932Z/documentation-checks.json` and `evidence-sha256.json`. Runtime build/stop/closed-loop tests were not performed because this turn was the approved preparation scope. PRE stays incomplete, with the concrete amendment/SIM0 entry and activation route remaining for review.

## 2026-09-29 — Installed-player-first deferral proposal

- Reviewed the unchanged v1.0 PRE/S1/F1/F2 requirements before proposing a separate S1a milestone. Source identity/time, downstream expiry and full scoring remain original acceptance obligations; only the proposed demonstration entry sequence changes.
- English draft 1.1-B and Chinese explanation distinguish receipt/source time, normal commanded stopping and final-path-loss containment. Both keep independent supervision, numerical motion approval and stage-end confirmation. Source-build work is proposed for later, not recorded as completed or approved.
- Checked local Markdown links, fences, whitespace and unique checklist IDs. Original plan remains 34 todos / two accepted; source-build draft has ten unchecked todos; installed-player-first draft has four unchecked todos. No runtime or feature tests were run for this documentation proposal.
- Detailed validation and document hashes: `artifacts/planning/20260929T055636Z/review.json`. No runtime evidence or original artifact hashes were changed by this review.

## 2026-09-29 — Full PRE-first decision and Unity activation handoff

- Confirmed current navigation reflects the user's decision: full PRE before S1; S1a/deferral not adopted. Its four unchecked todos remain inactive history. Original 34 todos retain two accepted; ten source-build todos remain unchecked.
- Reviewed English/Chinese setup guidance for consistent activation responsibility, exact editor/module pin, evidence limits and the user's undecided build environment. No license eligibility or runtime/build success is inferred.
- Checked local Markdown links, balanced fences, whitespace, unique todo IDs and `git diff --check`. Detailed results and document hashes: `artifacts/planning/20260929T060342Z/review.json`.
- Documentation-only work: no dependency installation, account access, GUI launch, simulation, actuation or implementation test was performed. Historical runtime artifacts remain unchanged.

## 2026-09-29 — Hub installation and SIM0 toolchain attempt

- Reviewed official Hub 3.21.3 installation against artifact/package hashes, desktop validation, callback association and the owned visible-window observation. The later user's login/license confirmation is recorded separately from runtime Editor readiness.
- Confirmed complete tracked source closure (9,422 files / 6,868,307,583 bytes), exact Editor/module archive extraction and actual version 2021.3.9f1/ad3870b89536. Retained 278 discovered bundled license/notice files in their source/toolchain locations; no account license file was read.
- Reviewed the failed empty-project probe: exit 1 after 46.70 seconds, no project created, licensing-service connection followed by unavailable-access-token/activation failure. Preserved Hub CLI registration's exit-0/empty-list discrepancy and window-inspection limitations. Do not interpret these as a wrong password or a successful activation.
- Build helper CLI/import/syntax checks passed; actual AutoDRIVE import/build and both P0 neutral runs remain unperformed. The same-version Linux-host dependency diff is prepared but unapplied; source worktree remains clean. All SIM0 checkboxes stay unchecked and original acceptance stays 2/34.
- Integrity checks confirm unchanged three reference/source repository states and nine selected supplied-player hashes. No simulator, ROS driving pipeline or physical hardware was launched. The owned empty-project Editor was reaped; no simulator endpoint was acquired in this attempt.
- Documentation checks: 25 Markdown files, 425 local-link occurrences, balanced fences/whitespace, 48 unique IDs across original/active-route/inactive-history plans and passing `git diff --check`. Evidence JSON and private-log modes were checked. Details: `artifacts/simulator-build/20260929T063510Z/documentation-checks.json`; frozen artifacts are indexed separately, excluding the earlier mutable Hub console log.
- English/Chinese attempt reports agree on the specific runtime blocker, retained work and user-assisted Hub first-open recovery. This is an incomplete-stage report; it does not authorize SIM1 or motion.

## 2026-09-29 — Hub recovery, batch compilation and initial import audit

- Verified corrected Hub registration and user-created project metadata, retained the first batch compiler/libssl failure, then reviewed the authenticated private dependency and successful fresh batch compile/exit. SIM0-01 alone is newly accepted; original PRE remains two accepted out of 34 and full SIM0 remains incomplete.
- Reviewed the 389.49-second import's exit-0/asset-error discrepancy, full induced diff and the 12.01-second actual Unity dependency audit. All six failed assets and both changed demo materials are outside the 276 reported F1TENTH dependencies; scene/project settings are unchanged. The temporary Editor-only probe was removed. Candidate exclusions remain unapplied pending the scope decision.
- Python build-tool AST/import/CLI checks and its real Unity audit passed. English/Chinese reports agree on observed results, static-audit limits and the pending input-scope proposal. Final documentation checks cover 31 Markdown files, line-qualified local links, fences, whitespace, JSON evidence and private-log modes. Initial helper assumptions about line suffixes and the supplied player's Data-directory name were corrected against actual files; their limited failures do not represent runtime acceptance.
- Three original repository identity/status snapshots and nine selected supplied-player hashes match the previous baseline. This is scoped integrity evidence, not exhaustive write tracing. No player build, simulator motion, S1 feature, commit or push occurred.
- Evidence: `artifacts/simulator-build/20260929T085557Z/documentation-checks.json`, `post-run-integrity.json`, `result-summary.json` and `import-recovery-proposal.json`. SIM0-B02 remains open; no acceptance criterion was relaxed.

## 2026-09-29 — Approved asset preparation and model-reference blocker

- Reviewed exactly twelve preserved exclusion files against the approved manifest; original worktree diff and selected repository/player baselines unchanged. New import started with no Library and exited 0, but missing OpenCAV references remain; it is not accepted as clean. Retained initial diagnostic classification, whose narrow exception regex omitted missing-prefab wording, and the corrected category counts.
- Compared 276 Unity-reported dependency paths and 552 required file hashes, then checked actual imported objects/local IDs. This exposed the critical track importer limitation that path/hash equality does not detect. Expanded C# probe actually compiled/ran and was removed. All recorded Editor processes exited/reaped.
- Added bilingual blocker reports, current navigation and explicit recovery choices without changing acceptance or entering another stage. Original plan remains two of 34 checked; amendment remains one of 10 checked. New stationary harness has local rejection/import checks only, not runtime acceptance.
- New scene inventory parsed 18 installed collider meshes/120 script identities without errors. Initial analysis environment failure is retained separately; corrected isolated-package provenance recorded. No installation or player change occurred.
- Final document/code/evidence checks and manifest: `artifacts/simulator-build/20260929T100424Z/documentation-checks.json` and `evidence-sha256.json`.

## 2026-09-29 — Read-only Linux recovery feasibility

- Checked the installed tracks' complete render/collider attributes against an independent raw-resource decoder and matched numeric material fields to pinned source. Source texture presence is recorded separately from untested shader/pixel equivalence. The inventory reports 18 collider meshes, 120 script identities and no parse errors.
- Reviewed both unused OpenCAV assets and their reference chain: prefab → sole serialized scene referrer → disabled build-list entry. The proposed four-file quarantine and one-entry setting removal remain unapplied; no unbounded SKP pruning is authorized.
- English/Chinese proposals agree on exact scene/asset scope, evidence limits, four unchecked recovery tasks and unchanged SIM0/stage gates. Updated current navigation to reflect Windows unavailability; earlier host-choice reports are retained as history.
- Inspector import/help/AST checks passed. Three repository state snapshots, nine selected installed-player hashes, both simulator source-copy diffs and target scene/build-settings hashes match the recorded baselines. The first comparison mistakenly used binary-patch output against the stored standard diff; preserved that failed check and corrected only the comparison representation.
- Final documentation checks, source/evidence snapshots and hash manifest are in `artifacts/simulator-build/20260929T102620Z/`. No conversion/build/runtime or additional completed acceptance item is claimed.

## 2026-09-30 — Approved native recovery attempt and restricted retry

- Reviewed three exact preparation copies and all quarantined hashes. Initial import has no recorded C# error/import exception/missing-prefab diagnostic; separated 31 fallback lookup messages from actual shader compiler errors and retained the initial regex classification.
- Preserved the rejected exporter assumption and failed native generation. Independently decoded both archived text assets' raw buffers: vertices/indices match the installed inputs, while mesh names differ. This corroborates partial preservation without claiming a passed reload/prefab/scene test.
- Recorded the current sandbox failure separately from conversion: retry produced no native report, exited SIGTRAP, and was reaped. Read-only interface/NETLINK_ROUTE probes reproduced EPERM. The checked crash lock was preserved and cleared; no player or motion was launched.
- Seven mapping guard tests and five tool AST/import/help checks pass. Three reference repositories, nine installed-player fingerprints, original/previous-source diffs and the new scenes remain unchanged. No acceptance checkbox advanced.
- English/Chinese reports, code snapshots, final documentation checks and evidence manifest are under `artifacts/simulator-build/20260929T122535Z/`. The prepared naming correction, repeat generation, real scene mapping, build and neutral acceptance remain unverified.


## 2026-09-30–10-01 — Host recovery, strict player comparison and live blocker

- Main-agent review confirmed exact normal-authoring promotion, independent generation, reversible scene mapping and complete source/dependency allowlist. Two failed player metadata comparisons were retained; the four-mesh bundle probe supplied causal evidence for the corrected authoring treatment. Final 698.08-second player build and full recorded static comparison pass, including original raw buffers and all channel metadata.
- Reviewed the two connection timeouts and the guarded wrong-window termination. With window-manager activation, the owned-target trace, handshake, eight topics and first-frame scan/image hashes verify actual transport. The position guard then correctly failed the trial on the first 1 mm reported change; the two 60-second observations are not complete.
- Independently compared retained installed-player segments and pinned IPS/Socket/VehicleController source. The same reported step exists in the earlier data; no causal physics equivalence or harmless-noise claim follows. Runtime wheel warnings and shutdown diagnostics remain documented. All owned trial processes were reaped; no default guard relaxation or motion command occurred.
- English/Chinese current reports and checklists reflect only LNX-01/02/03 and SIM0-01/02 acceptance. Proposed passive-drift diagnostics remain unapproved. Final retry integrity, reproduction/source snapshots and documentation evidence are separate from the immutable original 83-file manifest.

## 2026-10-01 — Approved passive-drift study

- Reviewed all four diagnostic runs against the approved profile, exact-zero replies/feedback, fixed-window receipts and raw-to-ROS position sequences. No P0 completion flag was set. Independent Decimal-based displacement derivation agrees with the per-player analyzers; the trajectories are monotonic in reported X with unchanged Y/Z and zero encoders.
- Reviewed all four completed-window screenshots and the standalone four-panel plot. Same Manual/display configuration remains visible; human image review cannot establish millimetre-scale motion or pixel equivalence.
- Classified retained log matches: existing four wheel-hull warnings/run, two shutdown socket errors/run, 1 / 2 / 1 / 1 ThreadAbort diagnostics, Devkit QoS deprecations and allocator statistics. No unclassified diagnostic-pattern matches; no error-free claim.
- Seven focused harness tests passed. Reviewed before/after fingerprints and clean process/endpoint state. The old 434-file frozen evidence set remains unchanged; current evidence is separately frozen. No simulator/core edit or acceptance-checkbox advancement.
- English/Chinese report tables, scope boundaries and proposed read-only kinematics exception match. The proposal remains unapproved and unimplemented; full PRE before S1 and explicit SIM1 review remain in force. Final documentation/source snapshots and checks are under `artifacts/simulator-build/20261001T054121Z-drift/`.

## 2026-10-01 — Approved full-precision diagnostic review

- The previous read-only proposal was subsequently approved with “yes” and completed in `20261001T060743Z-kinematics`. Preserve the preceding entry as its historical approval checkpoint. Two completed diagnostic windows remain ineligible for P0; the initial log-cap failure and corrective build are explicit deviations in both new reports.
- Eighteen focused tests passed. Actual Unity builds, strict serialized comparisons, full existing-source hashes, healthy/closed trace status, sequence/byte counters and an independent exact-window derivation support the recorded results. A mock Unity fixture is not represented as engine physics validation.
- Main agent viewed both pre-Connect and completion screenshots and both plots. Zero display values do not establish millimetre-scale stationarity. Full-precision body drift, fixed axle offset and all-wheel braking are verified; the contact/solver hypothesis remains unproven.
- Prior 434-file and 108-file evidence archives, selected installed files, full baseline/diagnostic players, runtime files and reference repositories retain their fingerprints. Raw Unity logs remain private, ignored artifacts. The English/Chinese reports disclose diagnostic overhead, shutdown warnings, cleanup tails and causal limits.
- Current counts remain original 2/34, source amendment 2/10 and recovery 3/4. The new proposed contact-pair A/B changes collision behavior and has a separate approval boundary. No automatic adoption, P0 relaxation or SIM1/S1 entry.

## 2026-10-01 — Contact-control study review

- Main agent reviewed actual engine API compilation, 29 passing focused tests, unchanged P0/zero/encoder/transport guard AST, final 9,404-file source comparison and strict serialized player comparison.
- Independently streamed contact and kinematics evidence: two completed controls, actual wheel-mesh/Floor identities, zero aggregate collision impulses, **3.411 / 3.392 mm** body drift and varying inertia. Actual treatment gate is ineligible; no B launch or P0 acceptance. Offline IPS-field and deadline-age corrections retain their earlier sources/results.
- Reviewed both process-specific pre-Connect and completion screenshots plus both trajectory plots. Reviewed vendor/build/shutdown warnings without dropping them. Verified owned process/port cleanup and listed installed/baseline/current/prior/source/runtime/repository fingerprints, including all **434 + 108 + 145** prior frozen files.
- Checked **507 local Markdown targets**, balanced code fences, Python AST and `git diff --check`; final checks pass. Initial link-parser false positives from supported `path:line` notation are retained separately; filenames/links were not weakened to pass. Todo counts remain **2/34, 2/10, 3/4**, with unique IDs. Raw artifacts remain Git-ignored.
- Evidence: `artifacts/simulator-build/20261001T073103Z-contacts/`; [English report](../../stages/SIM0-contacts.md) / [中文](../../stages/SIM0-contacts.zh-CN.md). Revised Floor target and intervention-local inertia verification are proposals awaiting confirmation, not implemented changes or repaired-physics claims.

## 2026-10-01 — Floor-only A/B report and evidence review

- Reviewed actual gate/activation records and independently streamed both conditions. All four 60-second windows completed; two treatments removed all selected post-activation contact points while drift remained **3.372 / 3.414 mm**. Exact immediate property equality, stable mass/COM, grounded wheels and raw/ROS IPS sequence checks pass. Inertia evolves naturally. No root cause, repair or P0 pass is asserted.
- Reviewed one 257.388-second build, exact-engine API compile and **35 passing focused tests**, retaining the initial analyzer-variable failure. Existing source (9,404 files), serialized player comparison and guard-function ASTs pass. Executed Python/C# code matches pre-build source snapshots.
- Host confirms editor and twelve trial PIDs absent; children exited 0/reaped, port free. Reviewed retained build/runtime warnings and instrumentation/transport costs. All four prior evidence archives and preserved players/source/runtime/reference repository states pass integrity.
- English/Chinese reports share data-derived motion/transport tables and the same approval/acceptance boundaries. Comparison figure visually reviewed; a footer overlap was corrected before delivery. Local document links, balanced fences, whitespace and checklist counts were checked; counts remain **2/34, 2/10, 3/4**. Evidence: `artifacts/simulator-build/20261001T102325Z-floor/`; [English](../../stages/SIM0-floor-contacts.md) / [中文](../../stages/SIM0-floor-contacts.zh-CN.md).
- No additional build/trial was used. **SIM0-B06 remains unresolved**; proposed next source-and-trace review is read-only and awaits confirmation. No default physics repair, P0 relaxation, SIM1 or S1 entry.
