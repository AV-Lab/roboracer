# SIM0 — Linux-only Track Asset Recovery Proposal

Date: **2026-09-29**, execution status updated **2026-10-01**. **Approved by the user’s explicit “confirmed”.** [中文报告](linux-asset-recovery.zh-CN.md). Feasibility evidence: `20260929T102620Z`; [execution report](../stages/SIM0-linux-recovery-attempt.md): `20260929T122535Z`.

**LNX-01/02/03/04 pass (2026-10-05).** SIM0-B06 was closed by the user's option A as inherited simulator creep, with the P0 position rule amended to an inclusive 10 mm bound; both amended-P0 neutral runs then passed ([SIM0 report](../stages/SIM0-completion.md)). No physics repair adopted; full PRE before S1 remains required.

The proposal below records the selected response to Windows-host unavailability: recover the two required tracks from the supplied Linux player and qualify a separately named source build. The native route bypasses the two required SketchUp imports without changing engine, physics, sensor workload or the final comparison.

## 1. What the investigation establishes

The previous [blocker report](../stages/SIM0-sketchup-blocker.md) establishes that Unity 2021.3.9f1 on Linux does not import the required SketchUp files. This is independent of the earlier Hub/template and compiler-library problems, whose recorded recoveries remain valid. The installed player contains already compiled geometry and remains usable within its previously qualified scope.

Read-only inspection of that player found:

| Property | Proto Track | Berlin Track |
| --- | --- | --- |
| Vertices / 32-bit indices | 110,436 / 167,340 | 104,460 / 157,644 |
| Submeshes / ordered material slots | 2 / Outer Face, Inner Face | 2 / Outer Face, Inner Face |
| Render/collision mesh | Both reference the same mesh, path ID 213 | Both reference the same mesh, path ID 413 |
| Local transform | Position `(0, 0.127, 0)`, identity rotation, scale 1 | Same position/rotation, scale 0.5 |
| Activation | Active | Inactive |

Both track roots have no children. Neither renderer uses a static-batch mesh or additional vertex streams. Each mesh retains positions, normals, tangents, UV0, indices, submesh descriptions and bounds. All decoded attributes are finite; indices are within their vertex ranges. An independent decoder of the raw resource bytes matches the UnityPy MeshHandler results for all four populated attributes on both tracks. The buffers have a 32-byte vertex stride: float32 positions, float16 normals/tangents and float16 UV0.

The four installed materials match all 120 float and 16 color properties of their corresponding pinned source materials after float32 normalization; their render queues also match. The source files for the three referenced textures are present. **This does not establish shader-binary identity, texture pixel equivalence or rendered-camera equivalence.** Reusing the source materials is a supported design candidate, not a completed visual qualification.

The expanded inspection tool ran successfully in **0.795 s**, reporting 18 collider meshes, 120 script identities and no parse errors. This is one static inspection duration, not a simulator performance measurement. No Unity Editor/player was launched and no source scene, asset or setting was changed during this feasibility run.

## 2. Exact proposed change scope

Perform all source changes in a **fresh, separate derived checkout** of `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`. Preserve the installed player, original source checkout, prior qualified copy, excluded bytes and historical failures.

| Location | Proposed operation and boundary |
| --- | --- |
| `Assets/RoboRacerQualification/Tracks/` | Add `Proto Track.asset`, `Berlin Track.asset`, `Proto Track.prefab`, `Berlin Track.prefab`, their metadata and new directory metadata. Meshes derive from the fingerprinted installed buffers; prefabs supply the matching GameObject/Transform/MeshFilter/MeshRenderer identities. |
| `Assets/Scenes/F1TENTH.unity` | Remap only the two track prefab/model/mesh references to those native assets. Preserve local scene object IDs, parent relationships, transforms, activation, material order, renderer settings and existing collider components/settings. The current scene has 16 Proto and 20 Berlin reference occurrences to review; this is not just a filename substitution. |
| `Assets/Prefabs/OpenCAV/OpenCAV.prefab` and `.meta` | Preserve and quarantine outside the import tree. This unused prefab causes the seven remaining missing-SketchUp-prefab diagnostics. |
| `Assets/Scenes/OpenCAV.unity` and `.meta` | Preserve and quarantine with its prefab. It is the only serialized scene referrer found, so removing only the prefab would leave a new dangling scene reference. |
| `ProjectSettings/EditorBuildSettings.asset` | Remove only the disabled OpenCAV scene entry. Keep F1TENTH as the sole enabled scene and retain every other entry/setting. |
| Existing six exclusions and Linux compiler patch | Retain their already approved, fingerprinted scope. No additional bulk asset pruning or package upgrades. |
| Workspace qualification tools and evidence | Extend the parameterized preparation/inspection workflow with explicit native-asset generation and comparison. Keep it outside the default plugin runtime; record input/tool/output hashes and exact invocations. |

The OpenCAV prefab and scene are outside the recorded 276-path F1TENTH dependency closure. A serialized GUID scan found the scene's only referring file to be the build settings, where its entry is disabled. This is bounded static evidence; it cannot exclude every possible dynamic asset load. The four proposed additional exclusion files have exact hashes in the [exclusion review](../../artifacts/simulator-build/20260929T102620Z/additional-exclusion-review.json). These approved exclusions and the disabled-entry edit have now been applied in the separate recovery copies; see the execution report.

Keep the pinned Editor **2021.3.9f1/ad3870b89536**, Linux IL2CPP module, private native-library configuration, ROS 2 Humble, vehicle/physics/sensor workload and approved plugin architecture. The native-asset route bypasses the unsupported SketchUp import for these two tracks; it does not make the upstream project's other SketchUp-dependent scenes Linux-compatible.

## 3. Proposed execution and acceptance

These four **approved recovery tasks** are separate from the existing 34-item plan and 10-item source amendment. None is complete at implementation entry.

- [x] LNX-01 — Generate/reload both native meshes and prefabs from fingerprinted inputs, preserving attribute values, topology, submeshes, bounds, material order and runtime readability/workload. Do not simplify, optimize or recalculate geometry. Repeat independently without Library. **Passed for current revision, 2026-09-30:** generation **17.02 s**, independent generation/import **352.45 s**, byte-identical authoring Mesh files. Captured normal XYZ is exactly promoted to float32 in a 36-byte source vertex; original zero W padding and exact reverse packing are independently checked. The unchanged Unity compressor reproduces the required 32-byte layout/full metadata in the diagnostic bundle; full player comparison is LNX-03. [Repeat evidence](../../artifacts/simulator-build/20260929T122535Z/repeat-authoring-review.json), [independent buffer proof](../../artifacts/simulator-build/20260929T122535Z/authoring-source-review.json). Earlier direct-half revisions remain preserved, not accepted as players.
- [x] LNX-02 — Apply only the explicit track mapping, four-file OpenCAV quarantine and disabled-entry removal. Review every reference, scene override, collider/material setting and source diff; require no unresolved object or blocking import/compiler diagnostic. **Passed for current revision, 2026-09-30:** exact **16 + 20** substitutions reverse to original scene bytes; loaded scene check **12.01 s** passes. Clean initial import had no Library; 285 dependency paths/570 asset-metadata records and the full changed-file allowlist are reviewed. Known orphan-meta cleanup and two unused material migrations are retained. [Final source review](../../artifacts/simulator-build/20260929T122535Z/source-review-authoring.json).
- [x] LNX-03 — Produce and strictly compare the F1TENTH Linux IL2CPP player after LNX-02. **Passed, 2026-09-30:** 698.08-second build; original track vertex/index bytes and all channel records, 18 collider meshes, 662 transforms, 87 builtin settings, 120 script identities and resolved material/preview mappings match. Earlier failures remain preserved; no geometric tolerance introduced. [Final review](../../artifacts/simulator-build/20260929T122535Z/player-inspection-authoring/final-static-review.json).
- [x] LNX-04 — Complete both fresh-process 60-second neutral observations, content and cleanup review under unchanged P0. **Passed 2026-10-05 under the user-approved amended P0 (10 mm creep bound; other guards unchanged)**, see the [SIM0 report](../stages/SIM0-completion.md). History: **Blocked: SIM0-B06.** First P0 attempt rejected a 1 mm position step; zero completed P0 observations. Four later approved diagnostic windows show continuing drift in both players and do not accept P0. The full-precision diagnosis confirms body drift; later contact controls blocked B on target/inertia prerequisites. Resolve the cause/repair, then meet the full P0 contract. No motion, SIM1 or S1 entry follows from recovery approval.

Results belong under a fresh `artifacts/simulator-build/<run-id>/`; generated third-party assets, Unity caches and player binaries stay in separately identified scratch/output directories. Preserve notices and input provenance. Do not publish reconstructed assets or assume future redistribution permission from local qualification; GitHub publication is not part of this proposal.

Native mesh asset creation and explicit vertex/submesh layout are documented Unity 2021.3 capabilities. **The exact captured layout now passes Editor reload and independent regeneration checks.** In particular, half-precision normal packing, serialization, renderer properties and collider cooking must be checked rather than inferred from API availability. [Mesh API](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Mesh.html), [asset creation](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/AssetDatabase.CreateAsset.html), [vertex layout](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Rendering.VertexAttributeDescriptor.html), [submesh API](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Mesh.SetSubMesh.html), accessed 2026-09-29.

## 4. Benefits, risks and alternatives

| Consideration | Assessment and response |
| --- | --- |
| Local development cycle | Avoids an unavailable Windows host and creates repeatable local source-build inputs if qualified. Additional preparation/comparison tooling is required. No completion-time or performance estimate has been measured. |
| Provenance | Track geometry derives from the supplied compiled player, not a newly imported authoring model. Identify the backend accordingly; static equality does not establish complete source/binary or real-world equivalence. |
| Rendering/physics | Attribute and numeric material matches reduce uncertainty, but shader compilation, visual output and collider cooking still require build/runtime checks. Preserve workload and stop on mismatch. |
| Reproducibility | Pin source/player/Editor/tool fingerprints and compare repeated generation. `/tmp` is disposable; retain reconstruction instructions and evidence rather than treating a Unity Library cache as the build input. |
| Unexpected dependency/import errors | The bounded OpenCAV exclusion may not remove every remaining error. Retain new failures and review any larger asset/scene change before applying it. |
| Available alternatives | An authoritative portable export would still be useful, but none is currently supplied; the inspected pinned track directory has only the two SKPs and four materials. This is not an exhaustive claim about online availability. Windows hosting is unavailable per the user. Engine migration is a separate, unqualified change. |

The current upstream simulator README requests a newer Editor than this pinned historical project; that is not evidence that upgrading this checkout preserves behavior. No migration is selected. [Official simulator branch](https://github.com/Tinker-Twins/AutoDRIVE/tree/AutoDRIVE-Simulator), accessed 2026-09-29.

## 5. Approval boundary and current status

**Approval recorded:** the user's explicit “confirmed” approves the complete bounded scope in sections 2–3: recover the two native tracks, remap their F1TENTH references, quarantine the unused OpenCAV prefab/scene and remove its disabled build entry, then run the unchanged SIM0 checks in a separate copy.

The confirmation satisfies the user's change-control requirement for these required geometry/scene changes and broader exclusions. It permits this SIM0 recovery without reducing acceptance or authorizing motion/automatic SIM1 entry. Environment-enforced access prompts may still require narrowly scoped approval when an actual command needs it.

Original acceptance remains **2/34**; source amendment acceptance is **3/10 (SIM0-01/02/03)**; recovery is **4/4**. SIM0-04 (stage review), PRE-03/04 and all plugin feature acceptance remain open.

## 6. Evidence

- [Scope](../../artifacts/simulator-build/20260929T102620Z/scope.json), [installed track detail](../../artifacts/simulator-build/20260929T102620Z/installed-detail/scene.json), [component settings](../../artifacts/simulator-build/20260929T102620Z/track-component-detail.json).
- [Independent attribute and numeric material comparison](../../artifacts/simulator-build/20260929T102620Z/attribute-material-review.json), [source texture mapping](../../artifacts/simulator-build/20260929T102620Z/texture-source-review.json).
- [Additional exclusions and static reference review](../../artifacts/simulator-build/20260929T102620Z/additional-exclusion-review.json), [unapplied scope manifest](../../artifacts/simulator-build/20260929T102620Z/local-recovery-proposal.json).
- [Reusable read-only inspection tool](../../scripts/autodrive_inspect.py), [tool usage](../../scripts/README.md), [prior actual model-import audit](../../artifacts/simulator-build/20260929T100424Z/model-audit/scene-audit.json).
