# SIM0 — Project Creation and Batch Startup Recovery

Date: **2026-09-29**. Run: `20260929T085557Z`. [Chinese report](SIM0-startup-recovery.zh-CN.md). **Template registration and actual batch startup are recovered. SIM0-01 passes; full SIM0/PRE acceptance remains pending.**

## Verified results

- Hub now records **2021.3.9f1 / ad3870b89536** at `/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Unity`, and its official release lookup succeeds. The user reports project creation succeeded; `/home/a2rl/My project/ProjectSettings/ProjectVersion.txt` independently confirms the pinned Editor/revision. The agent only inspected this user-created project.
- The first fresh batch retry created its scratch project and recognized an already valid license, but the bundled **.NET 5.0.3** compiler failed with `No usable version of libssl was found`. Editor cleanup then hit a semaphore assertion/SIGTRAP: child exit **-5**, **10.09 seconds**. Retained failure evidence is not a passing startup result.
- Extracted Ubuntu `libssl1.1` **1.1.1f-1ubuntu2.24 / amd64** into private scratch. Verified the official `focal-security` InRelease signatures with the installed Ubuntu archive keyring, the package-index hash from that release and the package SHA-256 from the index. No system package or maintainer script was installed/run.
- A second fresh batch project, with only that private native-library search path added, compiled and exited **0 after 22.34 seconds**. The project was created, the pinned revision appeared in the log, the successful batch-exit marker was present, and the compiler/libssl failure was absent. The owned Editor was reaped.

The access-token warning can appear before the Editor recognizes an already valid license; it is not alone sufficient to identify a blocking licensing failure. The observed successful fresh batch startup resolves **SIM0-B01** for this local configuration. The template issue and licensing state remain distinct observations.

## Qualified dependency boundary

The private library directory is:

```text
/tmp/roboracer-work/sim0-20260929T085557Z/openssl-compat/extracted/usr/lib/x86_64-linux-gnu
```

Pass it explicitly with `scripts/autodrive_build.py --native-library-dir PATH`. The tool records library fingerprints and modifies only the environment of its Editor subprocess. It does not change the system's OpenSSL 3, the pinned Editor binaries, Hub's launch environment or projects opened directly through Hub. The user's GUI-created project is not a verified compilation/build result.

The initial download was blocked by the sandbox's domain allowlist; the scoped escalated request then acquired the signed metadata and one required package from `security.ubuntu.com`. The package was extracted with `dpkg-deb --extract` under `/tmp/roboracer-work/`.

This is a locally tested dependency configuration, not a claim that Unity 2021.3.9f1/.NET 5 is supported on Ubuntu 22.04 or that the legacy dependency is a current general-purpose security baseline. Microsoft documents the different OpenSSL dependencies across Ubuntu releases and the legacy runtime's support status in its [.NET Ubuntu guide](https://learn.microsoft.com/en-us/dotnet/core/install/linux-ubuntu-decision), accessed **2026-09-29**.

## Continuation and evidence

**Subsequent import review:** the first full import exited 0 but contained asset failures. A Unity audit identifies them outside the F1TENTH dependency set; a scoped preparation proposal is awaiting confirmation. See the [current import report](SIM0-import-review.md). Startup recovery does not clear these source-import failures.

Applied the previously reviewed two-file manifest/lock change from Windows-host to Linux-host toolchain **2.0.4** in the separate pinned AutoDRIVE checkout. No physics, sensor, scene or runtime-source change was made by this adaptation. Initial import started with no `Library` directory; its actual outcome and all induced diffs must be reviewed before building the player. No driving or SIM1 instrumentation is authorized by this recovery.

- [Corrected Hub/project verification](../../artifacts/simulator-build/20260929T085557Z/hub-recovery-verification.json).
- [First batch retry](../../artifacts/simulator-build/20260929T085557Z/editor-startup/result.json).
- [Signed dependency provenance and hashes](../../artifacts/simulator-build/20260929T085557Z/openssl-compatibility-dependency.json).
- [Successful batch recovery checks](../../artifacts/simulator-build/20260929T085557Z/startup-recovery-result.json).
- [Initial import record](../../artifacts/simulator-build/20260929T085557Z/initial-import/build-result.json).

Original plan status remains **PRE-01/02 accepted; PRE-03/04 open**. The source-build amendment now has **SIM0-01 accepted**, with SIM0-02/03/04 and all SIM1 items pending. SIM0 still requires an accepted source build, two specified neutral runs and a stage report before SIM1 entry review.
