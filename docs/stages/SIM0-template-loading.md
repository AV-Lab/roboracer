# SIM0 — Hub Template Loading Recovery

Date: **2026-09-29**. Run: `20260929T084707Z`. **Historical diagnosis; subsequent corrected registration, project creation and batch startup are verified in the [recovery report](SIM0-startup-recovery.md). SIM0/PRE remain incomplete.** The observations below retain the original failed retries and handoff.

## Verified cause

The user reported **Unable to load templates** when creating a project. Hub's saved Editor registration contains `unity-2021.3.9f1`, and its log records that this version was not recognized and was cached as unsupported. The real Editor previously reported **2021.3.9f1**. All three bundled template archives are present.

Read-only inspection of the installed Hub **3.21.3** explains the mismatch: its Linux `findUnityVersion` takes the installation directory name and strips only a capitalized `Unity-` prefix. The lowercase `unity-` name used during our toolchain setup therefore became part of the registered version. Template retrieval constructs a Unity version object before its remote lookup; that parser rejects this string. Running an unchanged copy of the bundled parser reproduced the error for `unity-2021.3.9f1`, while `2021.3.9f1` parsed successfully as branch `2021.3`.

The log also records a missing template manifest, but Hub's code handles that case by writing an empty manifest; that file now exists. There is no evidence from the inspected matching log entries that template downloading itself failed because of the network. This does not establish general network health or successful template rendering after repair.

## Applied correction

Renamed the owned scratch installation to:

```text
/tmp/roboracer-work/toolchains/2021.3.9f1
```

The previous `unity-2021.3.9f1` path is a compatibility symlink to the same installation. Both executable paths resolve to the same inode. No Editor process was running at the check preceding the move. The Editor/module contents, Hub vendor code and live user profile were not modified. No reinstall or engine upgrade was performed.

## Required Hub refresh

1. Under **Installs**, use **Remove** on the entry labelled `unity-2021.3.9f1`. This removes a manually located entry from Hub while retaining the installation files, according to the [official Editor management guide](https://docs.unity.com/en-us/hub/add-editor).
2. Select **Locate**, then choose `/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity`.
3. In **New project**, select **2021.3.9f1** and check that the **3D** template appears. Refreshing the running Hub through its UI avoids modifying its live registration file externally.
4. Create/open an empty project with this exact Editor. Any account/license prompt remains user-managed. Successful template loading alone does not prove Editor licensing or automated build readiness.

**First retry:** the user still saw the error. The saved registration and 08:47:58 UTC log show that the old lowercase-prefixed path was added again. The corrected path has not yet been tested through Hub. In the Locate file chooser, use **Ctrl+L** to enter the full canonical executable path above; verify that the Installs card says **2021.3.9f1**, without `unity-`, before retrying templates.

The prior `Access token is unavailable` startup failure remains unresolved until a new Editor startup succeeds. Its relationship to this registration problem is not established. After GUI startup, repeat the bounded batch startup before AutoDRIVE import/build. No source instrumentation, simulator motion, new accepted todo or S1 implementation is part of this repair.

## Evidence

- [Recovery result and actual parser output](../../artifacts/simulator-build/20260929T084707Z/recovery-result.json).
- [Saved registration before repair](../../artifacts/simulator-build/20260929T084707Z/hub-registration-before.json).
- [Selected diagnostic evidence](../../artifacts/simulator-build/20260929T084707Z/diagnostic-evidence.json).
- Installed Hub source inspected: `editorUtils_linux-qBKwSSJb.js`, `unityTemplateService-ZY-LcmL-.js`, and `dist-cfnt_kzM.js` from its official `app.asar`. No vendor source was patched.
- Official manual-Editor association/removal documentation accessed **2026-09-29**, linked above.

Next observation: user refreshes the Editor entry and reports whether templates load; then verify the current registration and actual project startup. No GUI recovery success is inferred from the parser check.
