# PRE — Option A Feasibility and Amendment Handoff

Date: **2026-09-29**. Run: `20260929T051932Z`. [Proposed plan amendment](../planning/simulator-build-amendment.md). [Current PRE status](PRE.md).

**Outcome: preparing a separate instrumented AutoDRIVE build is feasible enough to recommend a bounded build-qualification stage. It is not yet a verified build or a completed PRE.** The user confirmed option A: source/toolchain investigation and a reviewable amendment. This run performed that preparation. No editor installation, activation, simulator implementation, simulator launch, vehicle command or plugin feature implementation occurred.

The approved v1.0 checklist remains **2 accepted / 34 total**. PRE-03/04 remain unchecked. The amendment proposes a specific source-build extension while retaining the existing acceptance goals; its implementation has not been approved by this investigation alone.

## 1. Verified findings

| Area | Evidence obtained | Consequence / limit |
| --- | --- | --- |
| Exact source | Historical Simulator 0.3.0 commit `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`; clean detached inspection worktree. All **223 tracked C# files**, the F1TENTH scene, project/package settings and asset identity metadata materialized. | Sufficient for a bounded code/interface review. Other asset bodies remain partially fetched; this is not a complete build checkout. |
| Project structure | 9,422 tracked files; no tracked submodule entries or root `.gitattributes`. Build settings enable only `Assets/Scenes/F1TENTH.unity`. | An unmodified F1TENTH baseline can be attempted before instrumentation. No existing `BuildPipeline.BuildPlayer` call was found in the 223 inspected C# files; the documented editor CLI provides a baseline build route. |
| Asset references | 4,999 unique metadata GUIDs, no duplicates in that inventory; 133 distinct scene GUID references, 21 without a match in repository metadata. | Two are Unity built-in marker GUIDs; other references require package/editor resolution. They are unresolved by this audit, not established missing assets. Full reference closure requires editor import. |
| Editor pin | Project specifies **Unity 2021.3.9f1**, changeset `ad3870b89536`. No Unity editor/Hub was found on PATH or in the inspected standard installation locations. | An existing runnable player does not provide an editor, build modules or activation. No license files or credentials were inspected. |
| Host | Ubuntu 22.04.5, x86-64, glibc 2.35; existing GNOME/X11 session; about **250 GiB free** on the filesystem at inventory time. | Enough to justify a bounded acquisition attempt, not proof that all downloads/import caches/builds fit. GPU/display execution was established in the previous PRE run, not rerun here. |
| Official archives | HTTP HEAD 200 for exact Linux editor and Linux IL2CPP support archives: **2,480,027,276** and **55,713,748 bytes**, respectively. | About 2.54 GB compressed combined. No archive body was downloaded. This excludes Hub, project assets, package dependencies and expanded/import/build space. HTTP headers are not an installed-toolchain test or authenticated content digest. |
| Dependencies | Manifest has 53 direct entries; lock has 70 entries: 42 built-in and 28 registry packages. Linux-host toolchain 2.0.4, Linux sysroot 2.0.4, Windows-host cross-toolchain 2.0.4 and Test Framework 1.3.2 all appeared in official registry responses. | Metadata availability only. Package downloads, import and compilation remain unverified. The source manifest currently selects the Windows-host cross-toolchain. |
| Physics baseline | Fixed timestep `0.001`, maximum allowed timestep `0.1`, time scale `1`; source retains the existing WheelCollider/controller model. | Preserve these settings in baseline qualification. A 1 ms configured timestep does not prove 1,000 physics updates per wall second or deterministic repeatability. |
| Local integrity | Original AVLite/A2RL repositories and nine selected installed-player fingerprints are checked separately in this run's integrity record. | Only the owned scratch checkout and research artifacts were added. Selected-file checks do not prove exhaustive filesystem immutability. |

Evidence: [source inventory](../../artifacts/preflight/20260929T051932Z/source-contract-inventory.json), [materialization record](../../artifacts/preflight/20260929T051932Z/source-materialization.json), [host inventory](../../artifacts/preflight/20260929T051932Z/toolchain-inventory.json), [archive headers](../../artifacts/preflight/20260929T051932Z/unity-download-headers.json), [package metadata](../../artifacts/preflight/20260929T051932Z/unity-package-availability.json).

## 2. Build feasibility and risks

The exact editor release is still listed with Linux installation modules. Unity's versioned 2021.3 requirements list Ubuntu 18.04/20.04 and CentOS 7 for the Linux editor; this host's Ubuntu 22.04 is outside that documented list. This is a qualification risk, not an observed build failure. First attempt the pinned editor in an isolated toolchain directory; if it fails because of host compatibility, stop with the failure log and compare another authorized build host against an engine migration. Do not silently upgrade Unity, alter the host OS, or describe a container as an officially supported workaround. [Release page](https://unity.com/releases/editor/whats-new/2021.3.9f1), [2021.3 requirements](https://docs.unity3d.com/2021.3/Documentation/Manual/system-requirements.html).

The project selects an IL2CPP standalone backend and a Windows-host Linux cross-toolchain. The official Linux-host package `com.unity.toolchain.linux-x86_64@2.0.4` exists and declares the same pinned sysroot dependencies. The amendment permits a recorded, build-only package adaptation in the separate checkout, preserving all unrelated dependency pins and vehicle/scene settings. Package resolution must verify the resulting lock; registry metadata does not prove that adaptation will compile. [Linux IL2CPP toolchain documentation](https://docs.unity3d.com/2021.3/Documentation/Manual/linux-IL2CPPcrosscompiler.html).

A user-scoped Hub AppImage is an available installation route; the current official guide describes FUSE3 and an extraction fallback. A system-wide apt repository is unnecessary for the proposed first attempt. The editor and Linux IL2CPP module can be pinned independently of the current Hub version. The user must choose and activate an applicable Unity entitlement through their own account; account access, purchases and credential handling are not implied. The pending question asks only whether activation will use local Hub, an existing authorized build environment, or a still-undecided route. [Hub installation](https://docs.unity.com/en-us/hub/install-hub-linux), [current activation guidance](https://docs.unity.com/en-us/engine/6000.5/manual/get-started/install-and-upgrade/licenses-and-activation/managing-your-unity-license). Current Hub/license guidance does not establish old-editor compatibility; that remains a runtime check.

The source includes Robotec native imports and numerous vendor assets even though the inspected F1TENTH scene uses the project raycast LiDAR script. Preserve the full dependency closure initially. Deleting apparently unused folders before qualification could break compilation or references. The repository root identifies BSD-2-Clause terms, while inspected vendor notices identify additional terms for some assets. Retain notices and keep the simulator source/build out of the future plugin GitHub push until its actual redistribution set is reviewed; private hosting is not evidence that all assets share the root license. This is an observed packaging constraint, not a legal determination. [Pinned source and notices](https://github.com/Tinker-Twins/AutoDRIVE/tree/635dbb6d86ec98e25ea845a97188f7bbe85a09e8), [inspection record](../../artifacts/preflight/20260929T051932Z/third-party-notice-inspection.json).

## 3. Source seams for the proposed extension

These are **design proposals**, not interfaces already provided by AutoDRIVE.

| Inspected source | Current behavior | Proposed bounded change |
| --- | --- | --- |
| `Socket.cs`, Socket.IO component | Telemetry follows Bridge replies; disconnect changes UI state. Incoming events are drained in `Update`. No acquisition identity, receiver lease or applied-command acknowledgement. | Versioned capability handshake, bounded communication and separate telemetry scheduling; explicit rejection of legacy actuator writes in the qualified mode. Observation and command events must not rely on nonzero commands or replies to maintain liveness. |
| `LIDAR.cs`, `WheelEncoder.cs`, `IMU.cs`, `IPS.cs` | Sensors update on physics callbacks; payloads retain their latest values without source identity. Camera capture occurs during serialization. | Stamp actual acquisition completion with episode/source identity, sequence, physics time and receiver monotonic time. Publish immutable samples with individual timestamps; never assign fresh acquisition time to an old array. Preserve existing camera workload in baseline comparisons. |
| `VehicleController.cs` | `FixedUpdate` obtains input, steers and drives. Zero drive torque selects brake torque in source; inspector range annotations are not runtime validation. | Check receiver authorization/expiry directly before actuator application; invalid/expired requests enter a latched stopped/fault state. Validate finite values, bounds, epoch and original request age. Verify brake application before proposing bounded movement. |
| `SceneReset.cs`, scene/controller state | GUI reset reloads the scene. No verified external episode transaction. | Introduce disarm → epoch invalidation → reset/init → fresh-observation → explicit rearm behavior. Manual single-start S1 initialization remains possible; unattended and five-start qualification remain tied to their existing later stages. |
| `LapTimer.cs`, colliders/transforms | GUI lap logic and rounded telemetry do not establish independent scoring. | Export evaluator-only geometry/truth/contact information and an independently validated progress/footprint scorer for the selected C0. Driving observations remain separately filtered. |

The new receiver guard **complements the approved independent supervisor process**. It cannot stop physics while the entire simulator main thread is frozen; the runner must record and contain that failed episode. On resume, expired authorization must be rejected before any further actuator application. Process termination is not scored as braking.

Clock synchronization also needs a real contract: sender/receiver monotonic epochs cannot be assumed identical. Preserve original command generation/valid-until information, bound clock conversion uncertainty, and impose a receiver-local maximum lease. Duplicate forwarding must not renew authorization. If clock bounds or source acquisition freshness are unavailable, arming remains blocked.

The encoder implementation contains hardcoded `0.065` wheel diameter and a fixed tick-distance factor, whereas previous installed-object inspection found WheelCollider radius `0.059 m`. Therefore existing convenience speed fields are not accepted as calibrated vehicle speed. Use raw timestamped counts with explicitly qualified radius/resolution/sign; compare wheel-derived speed with evaluator-only truth during the approved motion experiment. Wheel slip remains a residual limitation. This proposal does not retune vehicle dynamics or leak truth into the later ICP driving profile.

## 4. Recommended amendment and retained scope

The [reviewable amendment](../planning/simulator-build-amendment.md) adds **SIM0: reproducible baseline build** and **SIM1: instrumented qualification backend**, with explicit stage-end review. SIM0 starts with source/asset acquisition, a licensed pinned editor, one clean build and two neutral sensor-producing launches. SIM1 supplies source freshness, guarded actuation and the minimum independent scoring needed to complete PRE. Motion still requires its numerical protocol first.

S1–S5 retain their functional acceptance and run matrix. Humble, plugin-only ICP extension, Pure Pursuit, target-speed/steering and independent process supervision remain selected. General scene editing, physics improvements, another simulator, moving opponents and automatic localization recovery are not added. Required unattended/five-start/static-fixture controls are assigned to S2/S3/S4 qualification, rather than implementing every later feature before the first loop.

The cost is a Unity toolchain, a maintained upstream patch set, import/build time and new simulator contract tests. The benefit is an inspectable source of timestamps, expiry and scorer data while preserving acceptance. Performance overhead and behavioral equivalence to the supplied binary remain unknown until measured. An instrumented source build will be a **new named backend baseline**, not a byte-equivalent replacement for the user's installation.

## 5. Validation record and remaining gates

| Evidence level | Current status |
| --- | --- |
| Official documentation and pinned code reviewed | Completed for this preparation scope. |
| All tracked C# and scene identity metadata retrieved | Completed; full asset bodies/package closure still pending. |
| Editor/module endpoints and selected package versions reachable | Passed via explicitly approved host HTTP checks; sandbox domain denials retained. |
| Editor downloaded/installed/activated | **Not performed.** |
| Project fully imported/built | **Not performed.** |
| Instrumentation implemented / new API qualified | **Not performed.** |
| Moving stop / AVLite closed loop | **Not performed.** |

Two investigative limitations are retained. A `git ls-tree --long` size inventory triggered excessive lazy fetches in the partial clone and was interrupted; the replacement uses tree identities without asserting total download size. The GitHub recursive-tree API returned HTTP 403 rate limiting; Git transport provided the code/metadata instead. Initial `--no-checkout` worktree creation did not materialize files; the subsequent recorded `read-tree -mu HEAD` completed, and the worktree was verified clean. These are preparation outcomes, not successful build tests.

The Test Framework documentation URL for the 1.3 family currently resolves to 1.3.9, whereas the project pins 1.3.2. Registry metadata confirms 1.3.2 exists. Test CLI details must be checked against the installed pinned package before use; the newer family page is not recorded as exact-version runtime evidence. [Test Framework reference](https://docs.unity3d.com/Packages/com.unity.test-framework@1.3/manual/reference-command-line.html).

**Required next decision:** review the amendment and authorize entry to SIM0 if its scope is accepted. The remaining environment information is the user's Unity activation/build-host route. No permission for a global install, account login by the agent, paid license, OS migration, motion or SIM1 entry is bundled into a routine download request. The requirement to review this material extension comes from the user's architecture/acceptance confirmation rules and approved v1.0 section 4, not a skill or a renewed approval of the already accepted racing route.

## 6. Sources and evidence

All external pages and endpoints cited above were accessed **2026-09-29**. They concern the pinned historical simulator/toolchain, not a future race-rule version. The original competition-year/category question remains open without blocking this simulation preparation.

- [Run context](../../artifacts/preflight/20260929T051932Z/run-context.json), [result summary](../../artifacts/preflight/20260929T051932Z/result-summary.json), [integrity](../../artifacts/preflight/20260929T051932Z/post-preparation-integrity.json), [evidence hashes](../../artifacts/preflight/20260929T051932Z/evidence-sha256.json).
- [Full source tree identities](../../artifacts/preflight/20260929T051932Z/official-source-tree.txt), [initial partial inventory](../../artifacts/preflight/20260929T051932Z/official-source-inventory.json), [materialization and contract inventory](../../artifacts/preflight/20260929T051932Z/source-contract-inventory.json).
- [Network outcomes](../../artifacts/preflight/20260929T051932Z/source-network-checks.json), [official release download links](../../artifacts/preflight/20260929T051932Z/unity-release-download-links.json), [versioned editor CLI](https://docs.unity3d.com/2021.3/Documentation/Manual/EditorCommandLineArguments.html).
- Source inspection worktree: `/tmp/roboracer-work/preflight-20260929T051932Z/source-inspection`. It is disposable; evidence lives in the workspace artifact directory. No scratch checkout is the production plugin.
