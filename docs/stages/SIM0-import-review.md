# SIM0 — Initial Import Review and Recovery Proposal

**Update, 2026-09-29:** the user confirmed the six-asset recovery below. It was applied only to a separate qualification worktree, removing the targeted failures. Further review found required SketchUp track objects unavailable on Linux; see the [current blocker report](SIM0-sketchup-blocker.md). The original findings/scope below remain historical, with the omitted OpenCAV diagnostics corrected in the new report. Acceptance remains pending. Evidence: `artifacts/simulator-build/20260929T100424Z/`.


Date: **2026-09-29**. Run: `20260929T085557Z`. **SIM0-01 passed. SIM0-02 is blocked by initial asset-import failures; the proposed asset-scope change awaits user confirmation. No player build or neutral run has started.**

## Actual outcomes

The first AutoDRIVE import started with no project `Library` directory, using the pinned Editor, verified private libssl1.1 and the approved same-version Linux-host compiler adaptation. It exited **0 after 389.49 seconds**, with **zero C# compiler errors**. Diagnostic review nevertheless found **five asset-import failures** and an HDRP SpeedTree material-upgrader exception. Exit 0 therefore does not establish a clean import or complete SIM0-02.

The five failures concern binary TensorFlow training-checkpoint `.ckpt.index` files under `Assets/ML Resources/Results/CrossJunctionNavigation/`. Unity's SearchDatabase importer treated their `.index` extension as a search-index configuration and attempted JSON parsing. Each file is 2,077 bytes; this is not evidence that the source download was incomplete.

The separate exception occurs while importing `Assets/Plugins/Windridge City/Windridge City Assets/StaticObjects/Models/Foliage/Broadleaf/Broadleaf_Mobile.spm`. The stack enters HDRP 12.1.7's SpeedTree material-upgrader after a missing fallback-shader diagnostic. Its complete cause and the effect of a graphical cold import remain unproven; do not silently patch HDRP or change the renderer.

Unity also deleted nine orphan `.meta` files whose corresponding assets were absent from the pinned Git tree, and upgraded two demo materials. The full before/after diff is retained. **F1TENTH.unity and ProjectSettings have no diff**, and package changes are limited to the reviewed two-file host-toolchain substitution.

## Target-scene audit

Ran a bounded, temporary **Editor-only** probe using `AssetDatabase.GetDependencies("Assets/Scenes/F1TENTH.unity", true)`. It exited **0 in 12.01 seconds**, reported **276 dependencies**, and was removed afterward. None of the six failing assets or two changed demo materials appears in that set. No scene was opened/saved by the probe and Play mode was not entered.

A bounded byte scan found no reference to the nine orphan GUIDs in the inspected present scene-dependency files/metadata. No matching dynamic-loader expression was found in the inspected `Assets/Scripts` C# files. These checks have explicit limits: they do not prove every possible runtime asset load or qualify the new player's behavior.

The incremental audit run had no repeated asset-import failures. That warm-cache observation does not replace the required clean initial import; the original failures remain recorded.

## Proposed recovery — not applied

Prepare a **separate qualification copy** with the six identified assets and their metadata preserved outside Unity's imported asset area. Keep the complete upstream checkout and byte-level hashes. The [concrete candidate manifest](../../artifacts/simulator-build/20260929T085557Z/import-recovery-proposal.json) identifies every candidate file, size and SHA-256.

Repeat the clean import/build and compare the Unity-reported F1TENTH dependency set and required asset hashes against the audited source. New missing references, changes to required dependencies or physics/sensor/scene changes stop qualification. Other unused asset references may require a further review; this proposal does not authorize arbitrary pruning or vendor-package changes. Retain the original two fresh-process 60-second neutral trials afterward.

**Benefit:** addresses failures in assets outside the selected racing scene while preserving the pinned runtime, renderer and original files. **Cost:** adds an explicit source-preparation manifest and a fresh import/build attempt. **Remaining risk:** static dependencies may omit dynamic loads, and other unused assets may refer to the excluded items. Actual build/neutral evidence remains necessary.

The alternative is to keep every asset in the import and investigate the full-project importer failures, potentially involving additional vendor tooling or rendering changes. This has broader scope and less predictable effort.

Confirmation is requested because the proposed change alters the qualification build inputs beyond the previously reviewed compiler-package adaptation. It does **not** relax acceptance, authorize motion or enter SIM1/S1. The earlier template/licensing startup problem is resolved independently; no further account action is requested by this report.

## Evidence

- [Startup recovery](SIM0-startup-recovery.md) and [run summary](../../artifacts/simulator-build/20260929T085557Z/result-summary.json).
- [Initial import result](../../artifacts/simulator-build/20260929T085557Z/initial-import/build-result.json) and [induced diff](../../artifacts/simulator-build/20260929T085557Z/initial-import/source-after.patch).
- [Unity dependency report](../../artifacts/simulator-build/20260929T085557Z/scene-audit/scene-audit.json), [dependency review](../../artifacts/simulator-build/20260929T085557Z/scene-dependency-review.json), and [bounded source check](../../artifacts/simulator-build/20260929T085557Z/source-hygiene-review.json).
- Reusable audit entrypoint: [build helper](../../scripts/autodrive_build.py) with `--audit-scene`, using [Editor-only probe](../../scripts/SceneDependencyAudit.cs). This mode never creates or starts a player.
