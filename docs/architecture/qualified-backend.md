# Qualified backend — AutoDRIVE F1TENTH, patch 04 (SIM1)

Published **2026-10-08** (SIM1-06). Machine-readable identity: `artifacts/sim1-06/20261008T070835Z/qualified-backend.json`, with full file lists in `player-files.sha256` and `devkit-source.sha256`.

This is the simulator backend that every S1 result and every SIM1 qualification refers to. It is **frozen** (D18): there will be no further vendor patches. Later problems are solved in the bridge, supervisor or plugin, or recorded as limitations.

## 1. Identity

| Part | Identity |
| --- | --- |
| Vendor source | AutoDRIVE `635dbb6d86ec98e25ea845a97188f7bbe85a09e8` (F1TENTH, Proto track) |
| Engine | Unity 2021.3.9f1, changeset `ad3870b89536`, Linux IL2CPP; editor sha256 `3f9fb337…` |
| Host toolchain | `integration/autodrive/linux-host-toolchain.patch`, private `libssl1.1` ([scripts README](../../scripts/README.md)); Linux track recovery `integration/autodrive/linux-track-recovery.json` (SIM0) |
| Patch series | `integration/autodrive/sim1/vendor-sim1-01…04.patch`, schema `roboracer.sim1/1`, plus the staged components `RoboRacer/Provenance.cs`, `Guard.cs`, `GuardCore.cs`. All 11 files are byte-identical to the build record. |
| Build | `artifacts/simulator-build/20261007T-sim1-04/build/build-result.json` (sha256 `0d61b82a…`), 321 s, exit 0 |
| Player | `~/roboracer-work/autodrive-builds/20261007T-sim1-04/AutoDRIVE.x86_64/AutoDRIVE.x86_64` — `AutoDRIVE.x86_64` `d31b1f58…`, `GameAssembly.so` `44f9e735…`; 604 files, tree digest `c69b992a…`. Unchanged after every qualification run. |
| Devkit | pinned AutoDRIVE F1TENTH ROS 2 Humble Devkit with the recorded attrdict and compatibility overlays (PRE-02); source tree digest in the manifest |
| AVLite | 0.6.3 in its isolated venv (PRE-01) |
| Plugin and tools | this repository at the manifest's commit: `roboracer/` (bridge, supervisor, controllers), `scripts/` (runner, guard driver, scorer, analysis); 87 files hashed |

**What each patch adds:**
- **01 — provenance.** A versioned handshake; per-source acquisition identity and time; episode and session identity; clock echo; test hooks only behind a launch flag.
- **02 — receiver guard.** The request lease is checked immediately before `Steer`/`Drive`. Legacy, manual and GUI bypasses are closed, there is a zero-output interlock, and applied-command acknowledgements are emitted.
- **03 — D1.** Front motor torque is cleared on zero throttle, so stops brake all four wheels.
- **04 — D18.** The telemetry sequence is process-wide, so it survives a GUI Reset. Pending emits are also cleared on scene load.

The wire protocol is [`integration/autodrive/sim1/PROTOCOL.md`](../../integration/autodrive/sim1/PROTOCOL.md).

## 2. How it is run

- **Launch flags:**
  - `-roboracerGuard`: the guard is always on;
  - `-roboracerMotionAuthorized`: the only way to get nonzero output;
  - `-roboracerTestHooks`: tests only.
- **Who launches it.** Only the runner `scripts/autodrive_neutral.py` launches the player. It passes the motion flag only for a stage named in `docs/planning/s1-motion-approval.json`, and only when the player's hashes equal its build record.
- **Single episode:** `scripts/roboracer_episode.py live --stage m6 …` (see the [stack overview](stack-overview.md)). It writes a manifest, the score and the evidence.
- **Before Connect.** Every live run stops at a pre-Connect screenshot. A review bound to the PID, window and screenshot hash must exist before the Connect click.
- **Rebuild** (only to reproduce; the backend is frozen):

  ```bash
  python3 scripts/autodrive_build.py --editor ~/roboracer-work/toolchains/2021.3.9f1/Editor/Unity \
    --project <fresh prepared checkout> --output <fresh dir> --results <fresh dir> \
    --sim1-patch --sim1-through 04 --native-library-dir <private libssl1.1 dir>
  ```

  Compare the player's hashes with the manifest. A different hash is a different backend and needs requalification.

## 3. Contracts and frozen limits

| Contract | Value | Owner |
| --- | --- | --- |
| Observation age at request | ≤ 500 ms | supervisor |
| Speed feedback stale / lost | 600 / 900 ms | supervisor speed loop (D5 v0.3) |
| Request life | 500 ms from generation; guard cap 1 s | supervisor, guard |
| Runner lease | 500 ms | supervisor |
| Guard clock bound / exchange window | ≤ 400 ms / 2 s | guard |
| Speed / steering (M6 envelope) | ≤ 0.3 m/s target, abort 0.5 m/s; ±0.35 rad | supervisor, stage |
| Stop | ≤ 1.5 s to observed rest; F1 travel ≤ 0.40 m from fault onset | protocol |
| Simulator hang | no telemetry for 2.0 s → player killed; **containment, not a stop** | runner |
| Reset | GUI Reset → scene-load disarm, new episode and epoch; stale requests rejected | guard |

**Actuator conversion** (3 trials each, both players):
- steering: +1 = 30° left, with exact Ackermann wheel angles;
- throttle: + = forward, v = 5.02 m/s × throttle, settling within one frame;
- encoder speed: wheel angle × 0.059 m.

## 4. Measured costs

- Build: 321 s.
- Guard instrumentation: about 4 points of player CPU (SIM1-02).
- GPU p50 22–25 % during laps (D13).
- Telemetry gaps up to 248 ms in laps (0.65 s seen once under GPU starvation, M4).
- Lap cadence: the 10 Hz AVLite loop; observation age max 334 ms.

## 5. Known limitations

- **Contact is geometric.** The player emits no collision events. Contact is the swept footprint against the wall union.
- **Front-sector grazing.** About 0.24 % of front-sector beams disagree with the ray-cast model, all at grazing incidence (SIM1-04).
- **Passive creep.** About 3.4 mm/min at rest, inherited from the vendor (SIM0 option A). It is bounded at 10 mm per stationary run.
- **Single start.** There is one start pose (C0 spawn) and a GUI Reset only. There are no arbitrary initial states, obstacles or unattended reset; those belong to S2–S4.
- **Display.** Graphical display `:1` only. Display-free operation is not qualified.
- **Shutdown hang.** The player intermittently does not exit after SIGTERM (4/27 F1 runs, always after stop and disarm). It is SIGKILLed with thread diagnostics, and not seen in the 7 runs since.
- **Hang is not braking.** Hang containment ends the process; it is never counted as a stop.
