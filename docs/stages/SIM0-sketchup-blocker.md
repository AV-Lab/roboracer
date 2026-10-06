# SIM0 — Linux SketchUp Import Blocker

Date: **2026-09-29**. Run: `20260929T100424Z`.

**Subsequent decision:** the user cannot provide a Windows build host. The local read-only feasibility investigation is now complete; see the [bounded Linux recovery proposal](../planning/linux-asset-recovery.md). Its native track reconstruction and exact OpenCAV isolation are awaiting approval. The choices below preserve the earlier decision context; Windows is no longer an available recommendation.

**The approved six-asset recovery was applied and removed its targeted failures, but SIM0 is not complete. The required F1TENTH track meshes cannot be imported by this Linux Editor. Build and neutral trials are paused at SIM0-B03 pending a build-host or asset-conversion decision.**

## Verified work and acceptance

| Check | Actual result | Acceptance meaning |
| --- | --- | --- |
| Separate qualification checkout | Pinned `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`; original checkout preserved. Exactly six approved assets and six metadata files archived with matching hashes outside Unity's import tree. | Approved preparation completed. No broader exclusions. |
| Clean initial import attempt | No pre-existing Library; Unity 2021.3.9f1/ad3870b89536, private authenticated libssl1.1, approved Linux toolchain 2.0.4 substitution. Exit 0 after **364.43 s**. | Five checkpoint importer failures and the tree upgrader exception no longer occur. Other unresolved references prevent clean-import acceptance. |
| Dependency/path/hash comparison | **276** paths unchanged; **552** required asset/metadata file hashes unchanged; no F1TENTH scene or ProjectSettings diff. | Confirms preserved input bytes, not successful model import. |
| Bounded dependency audit | Exit 0, **12.01 s**, temporary Editor-only probe removed. | Inspection completed; no player or Play mode. |
| Expanded model/object audit | Exit 0, **11.01 s**, temporary probe removed. Both required track files are generic `DefaultAsset` objects with **zero imported subassets/meshes**. | Required track references cannot resolve. SIM0-02 remains unchecked. |
| Linux IL2CPP player / neutral trials | Not started / **0 of 2** completed. | SIM0-02/03/04 remain unchecked. No motion, SIM1 or S1 entry. |
| Preservation | Three reference repository identity/status snapshots, nine selected installed-player hashes, and the original qualification diff match their prior baselines. | Scoped integrity verified, not exhaustive filesystem tracing. |

All three owned Editor invocations exited and were reaped. Original plan remains **2/34 accepted**; the source-build amendment remains **1/10 accepted (SIM0-01 only)**. PRE remains incomplete.

## Root cause and correction to the earlier review

The completed import logs contain seven missing-prefab GUID diagnostics under `Assets/Prefabs/OpenCAV/OpenCAV.prefab`. Comparison with the first import proves these diagnostics were already present; the earlier six-failure summary omitted them. They were not caused by the approved exclusions. The seven referenced `.skp` files actually exist, so further investigation was required before proposing another exclusion.

The expanded probe queries actual importer types and imported object/local-ID sets. It demonstrates the problem also affects **required racing assets**:

| Source asset | Actual Linux import | Serialized F1TENTH references |
| --- | --- | --- |
| `Assets/Models/Infrastructure/F1TENTH Tracks/Proto Track.skp` | `UnityEditor.AssetImporter`, main type `UnityEditor.DefaultAsset`; no imported objects. | 16 reference occurrences cannot resolve, including mesh references. |
| `Assets/Models/Infrastructure/F1TENTH Tracks/Berlin Track.skp` | Same result; no imported objects. | 20 reference occurrences cannot resolve. |
| `Assets/Models/Vehicle/F1TENTH/F1TENTH.fbx` — comparison control | `UnityEditor.ModelImporter`; 2,824 objects, including 564 meshes. | All 576 inspected reference occurrences resolve. |

Across the project, **50 `.skp` assets produced no imported mesh objects** in this audit. Unity's version-specific documentation explicitly excludes SketchUp import on Linux. This matches the actual 2021.3.9f1 behavior; changing only Ubuntu's version does not supply the missing importer. [Unity 2021.3 SketchUp limitations](https://docs.unity3d.com/2021.3/Documentation/Manual/class-SketchUpImporter.html#limitations), accessed 2026-09-29.

The earlier path-only dependency audit was insufficient to establish imported geometry validity. This limitation is now recorded explicitly, and the reusable audit includes importer/object checks. No scene was opened/saved and no runtime source, renderer, vehicle physics or sensor configuration was changed.

The clean-import log also retains compiler warnings, null-graphics shader diagnostics and 31 fallback-shader lookup messages. The named fallback shader's source file exists in the pinned Shader Graph package; these messages are not proof of a missing download. Their rendered-player consequences remain unverified. Nine orphan metadata removals and two demo-material upgrades match the previous import. None is silently treated as a runtime pass.

The supplied installed player remains usable for its previously qualified scope. A fresh read-only inventory again found **18 collider meshes and 120 script identities**, with Proto active and Berlin inactive. Its compiled geometry already exists; the new problem concerns reconstructing it from `.skp` source on Linux. The new source player does not yet exist.

## Recovery choices for review

These are proposed changes, not authorization to change the host or scene inputs. Keep ROS 2 Humble and the local Linux runtime/AVLite environment for every choice.

| Choice | Benefit | Cost and remaining risk | Plan impact |
| --- | --- | --- | --- |
| **H — Use a Windows x86_64 build host with the pinned Editor, then run the Linux player locally. Recommended if a host is available.** | Preserves the source asset format and avoids reconstructing track geometry. Upstream already selects the Windows-to-Linux toolchain. | Requires an available machine, user-managed entitlement, exact Editor/Linux IL2CPP module, dependency access and artifact transfer. Exact import/build success on that machine is unverified. | Add host qualification and a portable build invocation; retain clean import, resolved references, build and both local neutral trials. No host selected or uploaded to yet. |
| **P — Obtain portable track assets from an authoritative source or convert on a supported authoring host, then build on Linux.** | Keeps future build/experiment cycles local once inputs are qualified. | Requires full mesh topology, units, transforms, normals/UVs, materials/submeshes, collider and reference validation. `.fbx`/native-asset conversion is not a filename change. OpenCAV import diagnostics still need an explicit treatment. | A separately reviewed asset-preparation patch and equivalence checks become part of SIM0. No scene references or assets changed under this proposal. |
| **L — Investigate a local derived-asset route using the supplied player's compiled geometry.** | The local installation already contains inspectable track geometry; no external build machine needed for the initial feasibility investigation. | Only read-only collider extraction is currently verified. Complete render/collider reconstruction, reference remapping and reproducibility have not been demonstrated. Highest provenance/equivalence burden; it would be a separately identified derived backend. | First approve a bounded feasibility investigation and concrete patch proposal. Conversion or substitution would require subsequent review before acceptance runs. |

Unity documents Windows-to-Linux IL2CPP building in the toolchain family. The online `@2.0` manual currently renders **2.0.11**; this supports the general route, not a claim that the project's pinned **2.0.4** combination has run successfully on Windows. No package upgrade is proposed here. [Unity toolchain manual](https://docs.unity3d.com/Packages/com.unity.toolchain.win-x86_64-linux-x86_64@2.0/manual/index.html), accessed 2026-09-29.

**Recommendation:** choose H if a Windows build host is available. If local-only work is required, first choose between an authoritative portable export (P) and the bounded feasibility investigation (L); do not assume geometry equivalence. More exclusions, repeated Linux imports, engine migration or the previously rejected PRE deferral are not automatic recovery actions.

Confirmation is required because the [approved amendment](../planning/simulator-build-amendment.md) says “Fail on missing references” and permits no automatic environment substitution. The user's latest confirmation covered exactly six unused assets and their metadata; it did not authorize replacing required track geometry or switching build hosts. Acceptance thresholds and the two neutral runs are unchanged.

## Preserved tools, evidence and reproduction

- [Preparation result](../../artifacts/simulator-build/20260929T100424Z/preparation/preparation.json), [versioned exclusion manifest](../../integration/autodrive/sim0-exclusions.json), [preparation tool](../../scripts/autodrive_prepare.py).
- [Import result](../../artifacts/simulator-build/20260929T100424Z/clean-import/build-result.json), [diagnostic review](../../artifacts/simulator-build/20260929T100424Z/clean-import/diagnostic-review.json), [old/new prefab diagnostics](../../artifacts/simulator-build/20260929T100424Z/missing-prefab-comparison.json).
- [Dependency/hash comparison](../../artifacts/simulator-build/20260929T100424Z/dependency-comparison.json), [actual model audit](../../artifacts/simulator-build/20260929T100424Z/model-audit/scene-audit.json), [resolved-reference review](../../artifacts/simulator-build/20260929T100424Z/model-reference-review.json).
- [Track input/installed geometry inventory](../../artifacts/simulator-build/20260929T100424Z/track-input-inventory.json), [read-only scene inventory](../../artifacts/simulator-build/20260929T100424Z/geometry-installed/scene.json), [analysis environment](../../artifacts/simulator-build/20260929T100424Z/geometry-environment.json). The first analysis launch lacked NumPy; its [failure](../../artifacts/simulator-build/20260929T100424Z/geometry-environment-initial.json) is retained. The corrected analysis combined the existing isolated analysis packages without installing/changing global dependencies.
- [Harness checks](../../artifacts/simulator-build/20260929T100424Z/harness-checks.json): preparation/neutral tools are import-safe; zero-reply and malformed-motion rejection checks passed using the prior recorded frame. The new neutral runner has **not** run a player. [Tool documentation](../../scripts/README.md).
- [Integrity](../../artifacts/simulator-build/20260929T100424Z/post-run-integrity.json), [result summary](../../artifacts/simulator-build/20260929T100424Z/result-summary.json), [source access record](../../artifacts/simulator-build/20260929T100424Z/web-sources.json).

The derived checkout is `/tmp/roboracer-work/autodrive-635dbb6d-qualified-20260929T100424Z`; excluded bytes are under `/tmp/roboracer-work/autodrive-excluded-20260929T100424Z`. Original source and historical logs remain preserved. These scratch paths are not durable storage.

The existing build tool's `--audit-scene` mode reproduces the model inspection with the pinned Editor and explicit private native-library directory; exact argv is retained in [model audit execution](../../artifacts/simulator-build/20260929T100424Z/model-audit/build-result.json). Use fresh result paths. Do not run a player build expecting valid track geometry until the selected recovery route is qualified.
