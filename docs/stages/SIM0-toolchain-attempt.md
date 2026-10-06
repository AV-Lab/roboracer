# SIM0 — Toolchain Acquisition and Editor Startup Blocker

**Historical attempt:** the startup blocker described here is now resolved by the [verified recovery](SIM0-startup-recovery.md). The current incomplete SIM0 item concerns [source asset import](SIM0-import-review.md).

Date: **2026-09-29**. Run: `20260929T063510Z`. **SIM0 is incomplete.** The pinned source, Editor and Linux IL2CPP module are acquired; the Editor's runtime entitlement handoff failed before project creation/import. Full PRE remains required before S1.

## Delivered preparation and measured outcomes

**Later recovery update:** the user's template-loading error exposed a lowercase folder-prefix/version-registration bug. The scratch installation is now canonically at `/tmp/roboracer-work/toolchains/2021.3.9f1`, with the old path preserved as a symlink. Follow the [current Remove/Locate instructions](SIM0-template-loading.md); the observations below describe the original attempt and do not establish recovery.

| Check | Observed result | Evidence / limit |
| --- | --- | --- |
| Unity Hub | Official **3.21.3**, user-level launcher, desktop entry and callback; an owned visible window was verified during installation. | [Installation evidence](../../artifacts/preflight/20260929T062054Z/installation-result.json). The user subsequently reported login and license confirmation. |
| Simulator source closure | Commit `635dbb6d86ec98e25ea845a97188f7bbe85a09e8`; **9,422 tracked files, 6,868,307,583 bytes**, clean checkout, per-file hashes. | [Source manifest](../../artifacts/simulator-build/20260929T063510Z/source-closure.json). Complete tracked assets, not yet imported Unity/package closure. |
| Editor archive | **2,480,027,276 bytes**; extracted from the exact official release URL. | SHA-256 `2d9c7643f317d255dc12b72fa7ddffac6c13794d7ba04272941d3d977e087480`. |
| Linux IL2CPP archive | **55,713,748 bytes**; corresponding player support present after extraction. | SHA-256 `c89634943258c7a2ee5d8b363ed1e833f8440f689befd98708e590aec2a75b57`. |
| Archive extraction | Both completed; **98.73 s** combined extraction/hash operation. Bundled notices retained. | [Installation manifest](../../artifacts/simulator-build/20260929T063510Z/toolchain-installation.json). Local hashes identify artifacts; no separate publisher signature was verified. |
| Editor identity/load dependencies | `Unity -version` exited 0 and printed **2021.3.9f1**; startup log identifies **ad3870b89536**. Main executable `ldd` reported no missing linked libraries. | [Binary check](../../artifacts/simulator-build/20260929T063510Z/editor-binary-check.json). This does not prove every dynamically loaded component works. |
| Empty-project startup | Exited **1 after 46.70 s**; no project was created. License-client connection and an update message preceded an unavailable-access-token error and cancelled activation dialog. | [Run result](../../artifacts/simulator-build/20260929T063510Z/editor-startup/result.json), [sanitized diagnosis](../../artifacts/simulator-build/20260929T063510Z/editor-startup/diagnostic-summary.json). **Failed; not an Editor-readiness pass.** |
| Hub CLI association | Registration command exited 0, but subsequent installed-editor JSON was `[]`; GUI-profile database-lock diagnostics were also observed. | [Registration attempt](../../artifacts/simulator-build/20260929T063510Z/hub-editor-registration.json). Exit 0 did not establish successful association; the exact cause is not proven. |
| Build tooling | Added the explicit, import-safe [parameterized build entrypoint](../../scripts/autodrive_build.py) and [usage notes](../../scripts/README.md). CLI/help/import checks passed. | No AutoDRIVE import or build has been executed through it. This is tooling preparation, not a delivered driving feature. |

The first Hub CLI inventory and later registration attempt are retained. A window-inspection helper initially used a venv without Xlib; the corrected dependency environment ran, but found no viewable matching Hub window. This is not evidence of account logout or Hub absence on every display/workspace. Account contents were not inspected.

## SIM0-B01: Editor entitlement handoff

**Verified:** the user reported login/license confirmation; the Editor communicated with LicensingClient but then reported `Access token is unavailable` and failed activation/update before creating its empty probe project. The subsequent generic username/password diagnostic does not establish that the user's password was incorrect or that their entitlement is inapplicable.

**Unknown:** whether registering and first opening this archived Editor through the signed-in Hub resolves the handoff, whether another user-visible licensing step is required, or whether the old Editor/new Hub combination has another compatibility issue. The installed player's operation does not resolve these questions.

**Recovery requested:** in Hub, use **Installs → Locate** and select:

```text
/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity
```

Then create/open an empty project with **2021.3.9f1** and complete any account/license prompts personally. Return only whether the Editor opens or the non-sensitive error text. No password, key, license file or account screenshot is needed. The [official manual-Editor association workflow](https://docs.unity.com/en-us/hub/add-editor) supports Locate. This is a concrete runtime recovery step, not another request to approve the development route.

If it succeeds, re-run a bounded batch startup to verify the automated build path independently; a GUI-only success does not pass the batch build. If it fails, preserve diagnostics and discuss the precise supported recovery; do not change the engine, license selection or OS automatically.

## Preserved work and continuation

- Source: `/tmp/roboracer-work/autodrive-635dbb6d-baseline`.
- Editor/module: `/tmp/roboracer-work/toolchains/unity-2021.3.9f1`.
- Evidence: `artifacts/simulator-build/20260929T063510Z/`; downloaded archives and disposable setup helpers remain under `/tmp/roboracer-work/sim0-20260929T063510Z/`.
- Prepared a two-file [Linux-host toolchain diff](../../artifacts/simulator-build/20260929T063510Z/linux-host-toolchain.proposed.patch), **not applied**. It changes only the Windows-host compiler dependency to native Linux at **2.0.4**, preserving sysroot **2.0.5 / 2.0.4**. [Rationale and hashes](../../artifacts/simulator-build/20260929T063510Z/linux-host-toolchain-proposal.json). Package resolution/build is unverified.

After runtime entitlement access works: qualify the approved host-toolchain adaptation, perform the first complete AutoDRIVE import/build, inspect all induced diffs/diagnostics, then run P0's two fresh-process **60-second neutral observations** through the qualified Humble/AVLite environments. Record resources, receipt timing, required fields/images, displacement, geometry differences and cleanup. No observation or build-time performance threshold has been invented.

No source instrumentation, simulator launch, motion command or S1 plugin implementation occurred in this attempt. The original AVLite/A2RL repositories and supplied AutoDRIVE installation were not edited. No global packages, engine upgrade, physical hardware action or publication was performed. Unity may update its normal user caches/service logs during the explicitly authorized startup; raw logs remain private and excluded from Git. Scratch assets/toolchains are disposable and are not a redistribution package.

**Acceptance remains unchanged:** PRE-01/02 are the only two accepted original items; all four SIM0 tasks remain unchecked. SIM0-01 is blocked by actual Editor runtime entitlement access; SIM0-02/03/04 depend on it. SIM1 retains explicit entry confirmation after the SIM0 report, and moving tests retain the numerical protocol gate.

## Sources and evidence scope

Official sources accessed **2026-09-29**: [Hub Linux installation](https://docs.unity.com/en-us/hub/install-hub-linux), [exact Editor release](https://unity.com/releases/editor/whats-new/2021.3.9f1), [2021.3 Editor CLI](https://docs.unity3d.com/2021.3/Documentation/Manual/EditorCommandLineArguments.html), [Hub CLI usage](https://docs.unity.com/en-us/hub/use-hub-cli), and [manual Editor association](https://docs.unity.com/en-us/hub/add-editor). The Hub CLI reference URL timed out; installed Hub 3.21.3's bundled help/parser confirmed the association option. No Hub code or configuration database was patched.

Runtime outcomes above come from local results, not from documentation availability. Ubuntu 22.04 remains outside the pinned Editor's versioned documented host list; no general host compatibility conclusion follows from `-version` or the observed licensing failure.
