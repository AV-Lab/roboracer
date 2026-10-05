# SIM0 — Unity Setup and Activation Handoff

Date: **2026-09-29**. [Chinese version](SIM0-activation-guide.zh-CN.md). Scope: preparation for the [selected full-PRE-first route](../planning/simulator-build-amendment.md). **Current status:** Hub/project creation and a fresh batch compile/exit now pass with a private compiler dependency; see the [startup recovery](SIM0-startup-recovery.md). The remaining blocker concerns [AutoDRIVE source asset import](SIM0-import-review.md), not another account/Locate action. The sequence below preserves the earlier setup handoff.

The user has confirmed complete PRE before S1; S1a is not adopted. The local route is now selected: Unity Hub **3.21.3** was installed at the user's request, and the user subsequently reported successful login and license confirmation. This is a user-confirmed prerequisite. The exact Editor/module are now installed, but an actual empty-project startup failed at the runtime entitlement handoff. See the [attempt report](SIM0-toolchain-attempt.md) / [Chinese report](SIM0-toolchain-attempt.zh-CN.md). Import and build remain unverified. No license eligibility judgment or account operation was performed by the agent.

## Completed Hub setup

Hub is installed at `/home/a2rl/Applications/UnityHub/UnityHub.AppImage`. Launch it from the application menu or with `unityhub` (`/home/a2rl/.local/bin/unityhub`). The launcher uses the official AppImage extraction/run option without changing the Chromium sandbox. The desktop entry and `unityhub://` callback association passed validation; an owned Hub window was observed as viewable during installation.

Evidence: [installation result](../../artifacts/preflight/20260929T062054Z/installation-result.json). The official HTTPS download was completed by resuming a dropped connection; size and local SHA-256 were recorded. That hash identifies the local artifact, not a separately published signature. No Editor was included in the Hub installation.

## Recommended local sequence

1. **Hub installation — completed.** The user-level portable AppImage avoids a system package installation. [Official installation instructions](https://docs.unity.com/en-us/hub/install-hub-linux).
2. **Login and license confirmation — reported complete by the user.** Account details and license files are not needed in project evidence. The editor will verify runtime access. [Official license workflow](https://docs.unity.com/en-us/hub/manage-license).
3. **Pinned editor/module acquisition — completed in isolated scratch.** Use Unity **2021.3.9f1**, changeset `ad3870b89536`, and its **Linux Build Support (IL2CPP)** module from the release archive. Do not substitute the Hub's newest recommended editor. Official links and the prior HTTP availability evidence are already recorded. [Pinned release](https://unity.com/releases/editor/whats-new/2021.3.9f1), [editor management](https://docs.unity.com/en-us/hub/install-editors).
4. **Record executable readiness.** The agent records the editor path/version and a sanitized startup result. No password, serial key, license file or account screenshot is needed. The current canonical installation is `/tmp/roboracer-work/toolchains/2021.3.9f1/`; the previous lowercase-prefixed path remains a compatibility symlink. The prior Editor startup reported `Access token is unavailable` and exited 1 before project creation. Later Hub association exposed a separate folder-derived version/template error, now diagnosed in the [recovery report](SIM0-template-loading.md). In **Installs**, **Remove** the `unity-2021.3.9f1` entry and **Locate** `/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity`. Select **2021.3.9f1** in New project, check template loading and first-open an empty project; the user handles any account/license prompt. Then repeat the bounded batch startup. Neither GUI recovery nor runtime entitlement access has yet been verified after the correction.
5. **Run SIM0 qualification.** Verify the editor can start under the selected entitlement, materialize the pinned source/package closure, build a separate F1TENTH baseline and perform the two specified neutral runs. These remain unperformed. The installed player's successful run does not establish editor/host compatibility or compilation success.

The inspected host is Ubuntu 22.04. The old editor's versioned Linux host list does not include it; preserve that qualification risk and stop on a reproducible incompatibility rather than changing the engine/OS silently. [Versioned requirements](https://docs.unity3d.com/2021.3/Documentation/Manual/system-requirements.html).

## Responsibility and current boundary

The agent can prepare isolated tooling, pinned dependencies, build commands, logs and qualification checks within the agreed scope. The user chooses the applicable license and completes account login/activation; no purchase or account action is implied. GUI execution and writes outside the allowed workspace/scratch may still require scoped execution approval when actually attempted.

Continue the local SIM0 route following the user's readiness confirmation. The full source and editor/module are acquired. Keep SIM0-01 incomplete until the failed runtime entitlement check is resolved and verified. Do not request the full-PRE-before-S1 decision again. SIM1 retains its stage-entry review, and any motion retains the numerical protocol gate.

## Source check

Accessed **2026-09-29**: the official Hub Linux, Hub license management, editor management, exact release and versioned requirements pages linked above. The earlier engine-6000.5 license URL timed out; working Hub documentation supplied the UI workflow. Hub installation/launch evidence and the subsequent user confirmation supersede the initial guidance-only snapshot. Editor acquisition and SIM0 qualification are recorded separately under `artifacts/simulator-build/20260929T063510Z/`; no motion is authorized by this handoff.
