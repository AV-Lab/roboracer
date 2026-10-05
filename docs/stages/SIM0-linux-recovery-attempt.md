# SIM0 — Approved Linux Recovery Attempt

Updated: **2026-10-01**. Run: `20260929T122535Z` (continued across three dates). [中文报告](SIM0-linux-recovery-attempt.zh-CN.md). Approved scope: [native-track recovery](../planning/linux-asset-recovery.md).

**Subsequent result:** the approved [Floor-only A/B diagnostic](SIM0-floor-contacts.md) completed two controls and two treatments. Filtering removed the selected contact points after activation, but treatment body drift remains **3.372 / 3.414 mm**. P0 and SIM0-B06 remain unresolved; no repair adopted. Proposed read-only source/trace review awaits confirmation. The body below preserves the preceding build/P0 checkpoint.

**The corrected Linux IL2CPP player builds and passes the complete recorded static comparison. LNX-01/02/03 and SIM0-01/02 pass. Live telemetry now reaches all eight required ROS topics, with verified scan and camera conversion. However, the first connected neutral trial stopped after 16.53 seconds when reported position changed by 1 mm, despite zero actuator feedback and encoder values. The same reported step appears in retained installed-player observations. Its physical cause and longer-term behavior remain unverified. SIM0-B06 blocks LNX-04 and SIM0-03/04; SIM0 and PRE are not complete.**

The earlier successful generation/import rows below retain their original scope. They do not accept either rejected player. Historical failures and their manifests remain unchanged. The current input manifest is version 2 at `track-inputs-v4/track-inputs.json`; earlier v2/v3 directory names contain version-1 inputs for archived helpers.

## Current result and neutral blocker

The final authoring build exited 0 in **698.08 seconds**, producing **603 files / 1,513,674,732 bytes**, including debug-only output folders. Its source diff and selected source/asset hashes stayed unchanged. The actual player comparison passes: **18 collider meshes, 662 transforms, 87 builtin physics/camera records, 120 script identities**, both tracks' original vertex/index bytes and all 14 channel records, renderer settings, four ordered material mappings and the preview RenderTexture. No geometry tolerance was introduced. Shader binary/pixel identity and untyped script fields are outside that comparison. [Build diagnostics](../../artifacts/simulator-build/20260929T122535Z/player-build-authoring/diagnostic-review.json), [final static review](../../artifacts/simulator-build/20260929T122535Z/player-inspection-authoring/final-static-review.json).

| Retained live attempt | Observed result | Acceptance |
| --- | --- | --- |
| `neutral-authoring` | No connection or telemetry; timed out after 180.66 s. Three owned children exited 0; cleanup 0.59 s; endpoint released. | Incomplete. |
| `neutral-authoring-retry` | Longer click/focus delays still produced no connection; timed out after 180.64 s. Three children exited 0; cleanup 0.64 s; endpoint released. | Incomplete; delays did not solve the problem. |
| `neutral-authoring-input-check` | A new guard proved that Unity had focus but another window was under the pointer. Stopped **before clicking**; cleanup 0.64 s, all children reaped. | Identified a harness targeting defect. Earlier timeouts lacked this trace, so their exact cause is not proven. |
| `neutral-authoring-activated` | Window-manager activation plus pointer/focus/PID checks delivered the Connect click. One localhost Engine.IO 4 WebSocket request and one connection; 65 processed frames / 65 exact-zero replies; all eight ROS topics received 65 messages. Frame 66 changed reported X from **0.742 to 0.743 m** and was rejected before conversion/reply. | **Incomplete:** rejection 16.529 s after the first complete observation. Second fresh-process run was not started. All children exited 0; cleanup **1.594 s**, endpoint released. |

The accepted input-targeting fix changes only the qualification harness. It follows the window-manager activation request described in the [EWMH specification](https://specifications.freedesktop.org/wm/latest-single/), accessed 2026-10-01. Simulator source, physics, sensor workload and the exact-zero/change-detection guards are unchanged.

The connected attempt used ROS 2 Humble, the isolated Devkit/AVLite environments, domain 87, localhost port 4567, RTX 3080/Vulkan, and a **1280×720** player window in **Manual / Driver's Eye / Low Quality / Scene Light**. No driving-mode change, reset or nonzero command occurred. The stream contained **1081 LiDAR ranges** (1035 finite in the first scan), a reported scan rate of 20 Hz and **1280×720 rgb8** images. First-frame scan float32 bytes and decoded image pixels each matched the corresponding ROS message. The measured bridge receipt rate was **3.902 Hz**, p95 gap **268.49 ms**, maximum gap **310.94 ms**, with the explicitly configured 0.1-second reply delay. These are incomplete-run receipt measurements, not source acquisition rates or performance passes. Actual ROS coverage after observation start was only **16.277–16.286 seconds**. [Analysis](../../artifacts/simulator-build/20260929T122535Z/neutral-authoring-activated-analysis.json).

Sampled process costs over 48.01 seconds, including startup/review time: player **101.25% of one CPU core / 729.0 MiB peak sampled RSS**, bridge **10.08% / 142.6 MiB**, observer **2.08% / 67.2 MiB**. Startup to first complete observation was **31.80 seconds**, including screenshot review; this is not an unattended startup benchmark. GPU memory was not measured.

### Findings and limits

- **Verified:** four retained installed-player segments also move from reported X **0.740 to 0.741 m**, over 9.09–15.61 seconds, with zero encoder/actuator fields. They are short segments, including GUI resets, not matched fresh-process 60-second trials.
- **Verified source behavior:** `IPS.FixedUpdate` reads the vehicle's world Transform with no explicit random-noise term. `Socket.cs` serializes position with `F3` formatting. A 1 mm reporting step does not quantify the underlying sub-millimetre change precisely. It must not be dismissed as harmless sensor noise.
- **Unverified:** the cause of the Transform change, whether it settles or accumulates, and dynamic equivalence of the rebuilt player. Contact creep, settling and numerical effects are hypotheses. Zero wheel ticks do not prove zero body translation.
- **Retained diagnostics:** the same four wheel convex-hull warnings occur in the installed and rebuilt players. Existing closed-socket/ThreadAbort diagnostics occur during shutdown; owned-process exit and endpoint release were verified. No wheel simplification or physics change was made.
- **Visual review:** the connected source window and prior installed-player screenshot show the same camera/UI configuration and broadly matching scene. This is a bounded human review, not pixel-equivalence or camera calibration evidence.

[Position/source/diagnostic review](../../artifacts/simulator-build/20260929T122535Z/neutral-motion-review.json). The original P0 requirement explicitly stops unexpected movement for investigation. The guard did so; its result remains a failure to complete P0.

### Historical proposal: diagnostic observation only (subsequently approved and executed)

**Approval update, 2026-10-01:** the user replied “apporve” to this concrete proposal. The four authorized windows have now completed; [results and next decision](SIM0-neutral-drift.md). P0/SIM0 acceptance remains unchanged. The proposal below preserves the pre-approval checkpoint; it is not a pending request.

**Recommended:** approve a separate, bounded comparison of passive drift before deciding whether P0 needs amendment. This proposal is **not implemented or executed** and does not pass any acceptance item.

| Item | Proposed boundary |
| --- | --- |
| Coverage | Installed and source-built players; **two fresh-process observations each**, up to **60 seconds** after a complete frame and all eight topics. Same display/sensor/ROS settings and 0.1-second reply delay; record actual startup/connect offsets. |
| Commands and state | Manual mode, exact-zero replies/feedback, no reset/recentering during a run, unchanged scene/physics/sensors. Retain immediate stops for encoder changes, malformed input and child failure. |
| Position containment | Stop at the first received sample whose Euclidean displacement from its initial reported position is **≥ 0.010 m**. This **proposed diagnostic cap** permits observing beyond one measured 0.001 m reporting step. It is neither a measured baseline nor an acceptance tolerance; stock sampled transport does not establish a real-time physical safety bound. |
| Outcome | Report trajectories, repeatability, content, timing and cleanup, including every early termination. Use measurements to propose a separate P0 decision; keep SIM0-03/04 and LNX-04 unchecked. No SIM1/S1 or nonzero actuation. |

The alternative is to retain the current zero-change criterion and separately authorize a diagnostic source build that records full-precision Rigidbody/Transform/wheel state. That gives better causal evidence but adds a runtime instrumentation diff and a rebuild; any physics repair would then need its own scope/equivalence review. The recommendation avoids changing the simulator before the longer neutral behavior is measured.

Confirmation is needed because observing beyond the first position change changes the **approved P0 stop boundary**. This is not a repeat request for already approved build or Linux recovery permission.

## Player mismatch and verified diagnostic

| Operation | Actual result | Interpretation |
| --- | --- | --- |
| First IL2CPP player | Exit 0, **716.04 s**; 18 collider records, 662 transforms, 87 builtin settings and 120 script identities match. All decoded track attributes and material mappings match. | Both normal-channel metadata values are `4`, while the installed player has `52`. Strict comparison fails; no runtime launch. |
| Source-metadata correction | Complete source channel metadata written and verified; two generations pass in **16.02 / 349.46 s**, with byte-identical Mesh assets. Mapped-scene verification passes in **11.01 s**; source/dependency allowlist review passes. | Preserving serialized source metadata does not prove that the build retains it. |
| Second IL2CPP player | Exit 0, **698.04 s**, 603 files / 1,513,670,108 bytes including debug-only output folders. No compiler/import/missing-prefab/exception/shader error. Source diff and selected asset hashes unchanged during build. | Strict comparison still finds `52 → 4`; resolved material/texture metadata and preview RenderTexture settings match. Two HDRP macro-redefinition warnings and existing C# warnings are retained. Historical **SIM0-B05**, resolved by the final authoring player. |
| Isolated packing probe | **17.02 s**, four meshes: both tracks with captured half normals and exact float-normal promotion. Both variants produce identical captured raw vertex/index bytes; only float-normal authoring produces full metadata `52`. Temporary assets removed; source diff unchanged. | Demonstrates the treatment on an asset bundle, without claiming general undocumented bit semantics or full player equivalence. |
| Authoring correction | First generation/reload passes in **17.02 s**. Independent NumPy decoding confirms exact normal promotion, zero discarded W padding and byte-identical reconstruction of the original captured buffer. | Independent no-Library generation passes in **352.45 s** with byte-identical authoring Mesh files; mapped-scene check passes in **12.01 s**. Source stride is **36 bytes**; the final player restores **32 bytes** and full channel metadata. |

Unity documents FP32-to-FP16 vertex compression; the local unchanged `VertexChannelCompressionMask` is 4054. The observed bundle behavior supplies the evidence for this implementation refinement. The project settings, engine, scene scope, geometry values and runtime acceptance are unchanged. [Unity 2021.3 compression manual](https://docs.unity3d.com/2021.3/Documentation/Manual/mesh-compression.html), accessed 2026-09-30.

Evidence: [first mismatch](../../artifacts/simulator-build/20260929T122535Z/player-channel-mismatch-review.json), [second mismatch](../../artifacts/simulator-build/20260929T122535Z/player-channel-mismatch-metadata-review.json), [second build diagnostics](../../artifacts/simulator-build/20260929T122535Z/player-build-metadata/diagnostic-review.json), [packing comparison](../../artifacts/simulator-build/20260929T122535Z/packing-probe/comparison.json), [raw-byte equality](../../artifacts/simulator-build/20260929T122535Z/packing-probe/raw-buffer-review.json), [independent authoring check](../../artifacts/simulator-build/20260929T122535Z/authoring-source-review.json).

## Delivered work and actual results

| Work | Verified result | Acceptance limit |
| --- | --- | --- |
| Fresh recovery copies | The first three separate pinned worktrees were prepared: primary, repeat-generation and final-build copies. Each preserves 16 excluded asset/metadata files with matching hashes, including the four newly approved OpenCAV files. Only the disabled OpenCAV build entry was removed. | Repeat generation passed without an existing Library. The final copy has completed its first import with the verified native assets and mapped scene. |
| Initial import, 2026-09-29 | Exit 0 in **361.44 s**, starting without Library. No C# errors, import exceptions or missing-prefab diagnostics. The prior seven OpenCAV errors are absent. | 31 fallback-shader lookup messages and null-renderer warnings remain; no rendered-player acceptance. Required SKP assets remain unsupported until native replacement is qualified. |
| Verified track-input export | Captured both tracks' raw vertices and indices; independent float32 attribute hashes match the prior inspection. Original material file identities are recorded. | First export incorrectly equated mesh and GameObject names; that failure is retained. Corrected export passed. |
| First native generation, 2026-09-30 | Editor helper compiled and generated two mesh/prefab pairs. Exit **1** after **14.02 s** when verification detected Unity's filename-derived mesh names. | Failed attempt, not LNX-01 acceptance. All generated files were preserved outside the source copy before retry. |
| Independent archived-output review | Raw vertex and index bytes of **both** archived native meshes match the installed-player buffers exactly. Readability flags in the serialized assets remain false. | The original names `Mesh Proto Track` / `Mesh Berlin Track` became `Proto Track` / `Berlin Track`. This row records the failed first attempt; the corrected host run below verifies reload and scene behavior. |
| Correction | Generation now restores the captured mesh name after `AssetDatabase.CreateAsset` and saves it explicitly. More specific mismatch diagnostics were added. | Live-verified by `generate-03` and independent `generate-repeat`. No tolerance or failed check was removed. |
| Restricted retry | Exit **−5 (SIGTRAP)** after **31.03 s**; 77 package-manager interface-enumeration failures and a native semaphore assertion. No native recovery report was produced. | Historical **SIM0-B04**, resolved by host execution in `generate-03`; no player claim follows from that recovery. |
| Corrected host retry | `generate-03`: exit 0 in **13.01 s**; both meshes and prefabs pass persisted name, raw vertex/index hash, 32-byte layout, bounds, submesh, material and renderer checks. No blocking diagnostics. | Asset generation only. |
| Independent regeneration | `generate-repeat`: exit 0 in **361.49 s**, including its first import without Library. Both native Mesh asset files are byte-identical to the primary generation; both prefab semantic checks pass. Persisted readability/keep flags remain false. | GUIDs and prefab local IDs differ between independent generations and are recorded. No prefab-byte-identity claim. **LNX-01 accepted.** |
| Scene reference mapping | Exactly **16 Proto + 20 Berlin** reference occurrences remapped; reversing them reproduces every original scene byte. Primary Editor reload passes in **12.01 s**, including transforms, activation, materials, collider settings and absence of missing components. | The final cache-free copy also passed the same scene report. |
| Dependency review | Scene closure changes from **276 to 285 paths**: two SKP paths removed; four native assets, four original materials and three original textures added. All newly resolved original material/texture bytes match the pinned source; only the mapped scene changes among shared dependencies. | Static source/asset evidence; player rendering, collider cooking and sensing remain unqualified. |
| Final build-copy transfer | Eleven approved files, including directory metadata and the scene, copied with exact hash matches into the prepared cache-free build copy. Its clean import and scene validation passed in **361.48 s**, with all 570 dependency/metadata hashes matching the reviewed primary copy. | This was the first build-copy preparation. Two players subsequently compiled but failed strict metadata comparison; neither was launched. |
| Local tool checks | Five tools passed AST/import/help checks. **Seven** mapping tests and seven comparison guards pass (14 total). Mapping coverage includes: exact 64-bit IDs, unrelated-byte preservation, source drift, failed generation, project/process mismatch, GUID collision, unknown references and repeated application guards. | Synthetic reference tests only; they do not validate Unity scene loading or simulator behavior. |

The complete diagnostic review separates fallback shader names containing `Error` from actual shader compilation errors. The initial broader regex classification is retained. Compiler/import error counts are not inferred from exit code alone.

## Historical execution blocker and cleanup

`generate-02` ran under the preceding restricted session, where host escalation was unavailable. Its package-manager interface failures and native semaphore assertion were reproduced by read-only errno-1 interface/NETLINK probes. The owned Editor was reaped; its temporary helper and verified owned stale lock were removed, preserving all failure evidence. This was distinct from the asset-name failure.

The user requested a retry after host execution became available. The same pinned Editor/private-library setup then completed `generate-03`, proving that the corrected code executes in the restored host context. SIM0-B04 is operationally resolved. No engine, physics, sensor workload or acceptance threshold changed.

The initial repeat-run diagnostic search matched 31 successfully imported filenames ending in `Exception.cs` and eight warning-icon filenames. Those entries were reviewed and separated from actual diagnostics; the initial classification is retained. Actual compiler/import/missing-prefab/exception errors are zero. The 31 fallback-shader messages and batch null-device shader warnings remain recorded and do not qualify player rendering.

Selected earlier repository/installed-player integrity evidence is preserved. Before mapping, all **552** recorded dependency/metadata hashes matched. Unity virtual `Packages/` paths are resolved through the existing package-cache inventory helper; an initial direct-path assertion is recorded as a review-tool error, not asset drift. The resumed integrity check confirms three repository states, nine selected installed-player files, the three captured track input files, the original source diff and all 83 previously frozen evidence files remain unchanged. [Integrity record](../../artifacts/simulator-build/20260929T122535Z/baseline-integrity-retry.json).

## Reproduction and next action

The user has already approved this recovery scope. No new architecture or asset-scope decision is needed. Host execution is now working. The successful corrected invocation from `/home/a2rl/Workspace/roboracer` was:

```bash
python3 scripts/autodrive_build.py \
  --editor /tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity \
  --project /tmp/roboracer-work/autodrive-native-20260929T122535Z \
  --output /tmp/roboracer-work/autodrive-builds/native-20260929T122535Z \
  --results artifacts/simulator-build/20260929T122535Z/generate-03 \
  --native-library-dir /tmp/roboracer-work/sim0-20260929T085557Z/openssl-compat/extracted/usr/lib/x86_64-linux-gnu \
  --recover-tracks artifacts/simulator-build/20260929T122535Z/track-inputs-v2/track-inputs.json \
  --timeout 600
```

This historical command **completed successfully with its archived version-1 helper**; use the matching `generate-03/executed-probe.cs`, not the current version-2 generator. It is a recorded invocation, not an instruction to overwrite its results. Use fresh project/output/result paths to reproduce generation. The `-repeat` invocation used the same inputs and a 900-second execution bound; both exact Editor invocations are retained in their `build-result.json` files.

Current commands, matching tool snapshots and all attempt arguments are recorded in [retry reproducibility](../../artifacts/simulator-build/20260929T122535Z/reproducibility-retry.json). The successful full build uses the `-authoring` project/output and `player-build-authoring` evidence. The live command was:

```bash
/tmp/roboracer-work/preflight-20260928T113745Z/avlite-venv/bin/python -B scripts/autodrive_neutral.py run \
  --context artifacts/preflight/20260928T124339Z/run-context.json \
  --player /tmp/roboracer-work/autodrive-builds/native-20260929T122535Z-authoring/AutoDRIVE.x86_64 \
  --results artifacts/simulator-build/20260929T122535Z/neutral-authoring-activated
```

This is a retained **failed qualification invocation**, not an instruction to overwrite its evidence or repeat it until it passes. It requires the recorded Humble/display environment, permitted host execution and a fresh PID-bound screenshot review. Current next action is in the [completed diagnostic report](SIM0-neutral-drift.md). The default harness retains the original guard. Tools are documented in [scripts/README.md](../../scripts/README.md).

## Todo and stage status

- **LNX-01:** accepted — repeated native asset generation and reload/identity/layout checks passed.
- **LNX-02:** accepted — exclusions, exact mapping, both loaded-object checks, final clean import and full source/dependency review passed.
- **LNX-03:** accepted — final authoring player build and complete recorded static comparison pass.
- **LNX-04:** unchecked — **SIM0-B06**, first connected run ended at the position-change guard; neither required 60-second run is complete.
- Original plan: **2/34 accepted**. Source amendment: **2/10 accepted (SIM0-01/02)**. Recovery: **3/4 accepted**. Full PRE remains the prerequisite for S1; SIM1 retains explicit stage-entry review.

This is a progress report, not a stage-completion report. No motion or automatic SIM1 entry is authorized by the asset recovery.

Final integrity check: three reference repository states, nine selected installed-player files, all **570** reviewed dependency/metadata records, the source diff/native inputs, all **603** built output files and the **83** originally frozen evidence files are unchanged. All four owned attempts' children are reaped and absent. [Integrity](../../artifacts/simulator-build/20260929T122535Z/post-run-integrity-retry.json). Four retained harness snapshots match the respective run hashes; default zero/movement guards and observer functions match their pre-retry AST. [Tool review](../../artifacts/simulator-build/20260929T122535Z/final-tool-checks-retry.json), [harness history](../../artifacts/simulator-build/20260929T122535Z/neutral-harness-history-review.json).

Current handoff: [summary](../../artifacts/simulator-build/20260929T122535Z/result-summary-retry.json), [reproduction](../../artifacts/simulator-build/20260929T122535Z/reproducibility-retry.json), [separate retry manifest](../../artifacts/simulator-build/20260929T122535Z/evidence-sha256-retry.json). Earlier manifests and failed attempts remain intact.

## Evidence

- [Preparation](../../artifacts/simulator-build/20260929T122535Z/preparation/preparation.json), [import result](../../artifacts/simulator-build/20260929T122535Z/initial-import/build-result.json), [diagnostic review](../../artifacts/simulator-build/20260929T122535Z/initial-import/diagnostic-review.json).
- [Verified export](../../artifacts/simulator-build/20260929T122535Z/track-inputs-v2/track-inputs.json), [failed generation](../../artifacts/simulator-build/20260929T122535Z/generate-01/native-track-report.json), [preserved outputs](../../artifacts/simulator-build/20260929T122535Z/generate-01-archived/result.json), [independent raw-buffer review](../../artifacts/simulator-build/20260929T122535Z/archived-generation-buffer-review.json).
- [Restricted retry](../../artifacts/simulator-build/20260929T122535Z/generate-02/build-result.json), [retry diagnostics](../../artifacts/simulator-build/20260929T122535Z/generate-02/diagnostic-review.json), [read-only interface probe](../../artifacts/simulator-build/20260929T122535Z/sandbox-interface-probe.json), [crash-lock review](../../artifacts/simulator-build/20260929T122535Z/generate-02/crash-lock-review.json).
- [Tool checks](../../artifacts/simulator-build/20260929T122535Z/tool-checks.json), [seven tests](../../artifacts/simulator-build/20260929T122535Z/scene-mapping-tests.txt), [integrity](../../artifacts/simulator-build/20260929T122535Z/post-run-integrity.json).

- [Host resumption](../../artifacts/simulator-build/20260929T122535Z/resumption-retry.json), [corrected generation](../../artifacts/simulator-build/20260929T122535Z/generate-03/native-track-report.json), [repeat comparison](../../artifacts/simulator-build/20260929T122535Z/repeat-generation-review.json), [readability flags](../../artifacts/simulator-build/20260929T122535Z/native-readability-review.json).
- [Reference mapping](../../artifacts/simulator-build/20260929T122535Z/scene-mapping/result.json), [primary scene check](../../artifacts/simulator-build/20260929T122535Z/scene-verify/native-track-report.json), [dependency review](../../artifacts/simulator-build/20260929T122535Z/scene-dependency-review.json), [final-copy transfer](../../artifacts/simulator-build/20260929T122535Z/clean-build-input-transfer.json).

- [Final clean import/scene check](../../artifacts/simulator-build/20260929T122535Z/clean-scene-verify/native-track-report.json), [full source review](../../artifacts/simulator-build/20260929T122535Z/clean-source-review.json).

Current authoring evidence: [independent repeat](../../artifacts/simulator-build/20260929T122535Z/repeat-authoring-review.json), [exact scene mapping](../../artifacts/simulator-build/20260929T122535Z/scene-mapping-authoring/result.json), [scene reload](../../artifacts/simulator-build/20260929T122535Z/scene-verify-authoring/native-track-report.json), [full source review](../../artifacts/simulator-build/20260929T122535Z/source-review-authoring.json), [updated tool checks](../../artifacts/simulator-build/20260929T122535Z/authoring-tool-checks.json).
