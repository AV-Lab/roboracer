# SIM1-03 — Reset, epoch and re-arm: tooling, first live case, and a blocking defect

Date: **2026-10-07**. Request: "go on" (after M1). Scope: [source-build amendment](../planning/simulator-build-amendment.md) SIM1-03, resumed before S1 acceptance as [amendment 1.2](../planning/s1-first-amendment.md) requires. **All work is disarmed or interlocked:** the player ran without motion authorization, so the guard could output only zero.

SIM1-03 item: *Deliver disarm/reset/epoch/rearm behavior and a verified single C0 start, with stale command/sample rejection across reconnect/reset. GUI reset must enter the same guard. Demonstrate P1a reset/replay cases.*

## 1. What a GUI Reset does in this build (from source)

- **Scene reload:** `SceneReset.cs` reloads the whole scene. Every in-scene object is recreated, including the Socket.IO component, so the connection drops and the player shows **Disconnected** until Connect is clicked again.
- **Guard and provenance survive:** both are process-wide.
  - On every scene load after startup, the guard calls `Core.SceneLoaded()`, which disarms it with reason `scene-load` and clears its clock samples. The epoch counter persists.
  - Provenance increments the **episode** and clears its per-episode stamp tables.
- **The defect.** The telemetry sequence `RRTelemetrySeq` is an *instance* field of the in-scene `Socket` (`Socket.cs:34`), so it **restarts at 1 after every reset**. That contradicts [`PROTOCOL.md`](../../integration/autodrive/sim1/PROTOCOL.md) ("strictly increasing per process, starting at 1"). The guard's emit-time map (`Guard.emits`, keyed by that sequence) is also never cleared on a scene load.

## 2. Tooling (commit `56e214d`; 126 script tests pass)

- **Guard driver, `reset` mode.** The sequence:
  1. Arm, then accept one pre-reset request and keep its exact text for replay.
  2. Request the `gui-reset` action.
  3. Check that the guard disarmed with reason `scene-load` and that the episode advanced by one.
  4. Wait for clock exchanges to resume.
  5. Check the rejections:
     - a request while disarmed: `not-armed`;
     - an arm naming the old episode: `wrong-episode`;
     - re-arming in the new episode: accepted, with a new epoch;
     - an old-epoch request: `stale-epoch`;
     - the replayed pre-reset request: `stale-epoch`.
  6. Check that fresh requests are accepted and applied, and that there is no fault.

  It is tested end to end against the model guard, which now handles scene loads.
- **Runner, `gui-reset` action:**
  1. Click Reset at (52, 606), up to three tries, confirmed by `state disarmed scene-load` in the guard trace.
  2. Wait for the scene to settle, then capture `ui-after-reset.png`.
  3. Wait for a **second PID-, window- and screenshot-bound review** (`ui-review-reset.json`) before clicking Connect.
  4. Confirm the reconnection and resumed frames.
  5. Record the **C0 start check**: position offset from the spawn, and whether the encoders are still.

  Runner heartbeats continue during the action, so the supervisor's runner lease reflects real liveness. The bridge accepts exactly one reconnection, in reset mode only. `--guard reset` runs with the stationary plugin stack (supervisor plus AVLite `HoldController`).

## 3. First live case on the current SIM1-03 player (`artifacts/s1/20261007T070019Z-sim1-03/r0-current-build*`)

| Step | Observed |
| --- | --- |
| Pre-Connect review | Guarded, zeros, at the spawn, Disconnected |
| Armed; zero requests accepted | `state armed epoch 1 sup-1`; accepted through seq 14 |
| GUI Reset (1 click) | guard `state stopped lease-expired 14` (no requests while the socket was down), then **`state disarmed scene-load`** |
| Reloaded scene (reviewed) | simulation time restarted (00:00:04), Disconnected, Guarded, zeros, IPS [0.74, 3.16, 0.06] |
| Reconnect (1 click) | second connection accepted |
| First frame after the reset | **rejected by the bridge: `Duplicate or out-of-order telemetry seq 1 after 14`**. The bridge failed closed and the runner stopped the trial. |
| Cleanup | all five processes exited 0; the player is unchanged; no motion at any point |

The reset path and the guard behave as designed, but the restarted telemetry sequence makes the qualified player **fail closed on every reconnect after a reset**. The post-reset rejection cases (stale-epoch, wrong-episode, replay) could not be reached on this build.

## 4. Proposed fix — needs your decision (D18)

**D18 — patch and rebuild (recommended).** A new vendor patch `vendor-sim1-03b.patch`:
- `Socket.cs`: `private long RRTelemetrySeq` → `private static long RRTelemetrySeq`, so the sequence is process-wide, as `PROTOCOL.md` already states;
- `Guard.cs`: in the scene-load handler, also clear `emits`, so emit times from the previous scene are never paired with new frames.

No physics, actuation, sensor or scene change. Then:
1. Build a new player `20261007T-sim1-03b` with the pinned Unity 2021.3.9f1. The current SIM1-03 player stays untouched.
2. Requalify without motion: the SIM1-01 provenance and SIM1-02 guard P1a checks once, and the SIM1-03 reset case ×3 (fresh processes, reviewed before both Connects).
3. **Motion on the new player is not covered by D18.** All M0–M6 and M1 evidence stays tied to the current player. Before any future motion on the new build, I'd propose one M6 regression lap for your approval.

**Alternative:** keep the current player and record SIM1-03 as blocked by the defect. S1 acceptance would then remain blocked.

## 5. D18 approved ("D18, please"): patch 04, rebuild, requalification — **SIM1-03 passes 3/3**

- **Patch:** [`vendor-sim1-04.patch`](../../integration/autodrive/sim1/vendor-sim1-04.patch) makes `RRTelemetrySeq` static (process-wide). `Guard.cs` clears its emit map on scene load. Series level `04` in `autodrive_build.py` (`2eac698`).
- **Fixing the move first:** the `/tmp` → `~/roboracer-work` move had broken the git worktree links of the pinned source repository. `git worktree repair` relinked the four existing derived projects; the base resolves to `635dbb6d`.
- **Build:** a fresh derived copy (86 s, tracked diff `4965e4fa…` equal to the base), then Unity 2021.3.9f1 through patch 04 in **321 s**.
  - Player: `~/roboracer-work/autodrive-builds/20261007T-sim1-04/AutoDRIVE.x86_64/AutoDRIVE.x86_64`, `GameAssembly.so` sha256 `44f9e735…`.
  - The scene comparison with the SIM1-03 player is equal in every section: collider meshes, 662 transforms, settings, track geometry, script identities.
  - Evidence: `artifacts/simulator-build/20261007T-sim1-04/`.
- **No-motion requalification** (`…/requal/`, 208-file manifest; no motion authorization in any run):

| Check | Result |
| --- | --- |
| SIM1-02 guard scenario (all P1a phases) | **16/16 phases pass**; trace clean; **0 nonzero output steps**; Devkit loss cleared the lease 35 ms after the kill, with 0 steps applied afterwards. Matches the qualified SIM1-02 run. |
| SIM1-01 LiDAR freeze | **pass**: 22 frozen frames, all carrying the reused identity; age monotonic to 4.86 s; other sources fresh; telemetry sequence advancing; resumed after 1 frame. |
| SIM1-03 reset ×3 | **3/3 pass, 19/19 checks each**: `scene-load` disarm; episode 1 → 2; C0 start at the spawn (offset 0.000 m, wheels still); `not-armed`, `wrong-episode`, new epoch 2, `stale-epoch` for the old-epoch and replayed requests; fresh requests accepted and applied; no fault; all processes exit 0; one Reset click and one Connect click each. |
| Player integrity | 604 files unchanged after all runs |

- **Failed attempt, retained:** reset attempt 1 on the new player failed because of my tooling. The Reset click's window-focus waits (about 0.7 s) sent no runner heartbeats, so the 500 ms runner lease inhibited the supervisor. The driver then waited about 3 min for a request, until the known passive creep (about 3.4 mm/min) reached the 10 mm stationary bound and the bridge stopped the run. Fixed in `0ac6c29` (heartbeats during window targeting); the patch itself was confirmed working in that attempt (episode 2 frames accepted).
- **Simulator frozen:** per D18 there are no further vendor patches. Future problems are solved in the bridge, supervisor or plugin, or recorded as known limitations.
- **Not yet done:** no motion has run on the new player. All motion evidence (M0–M6, M1) is on the SIM1-03 player. Moving motion to the new player needs your approval; I'd propose one M6 regression lap first.

## 6. Regression lap on the patch-04 player (2026-10-08; "approve one regression lap on the new build")

One fresh-process M6 lap with the unchanged D9/D10 envelope, A-lap and window video (`artifacts/s1/20261008T062420Z-m6-regression/`).

- **Result:** a clean lap of 122.9 s with clearance 0.106 m, finishing on distance with no abort.
  - Final stop 0.34 s.
  - The 120 s timing window is within every frozen limit.
  - Runner exit 0; the player is unchanged.
- **Comparison with the nine SIM1-03-player laps** (`comparison-with-sim1-03-laps.json`): **10 of 11 measures fall inside the old range.**
  - Inside the range: lap time, clearance, max speed, steering range, final stop, observation age p95, command → observed p95, telemetry max, and player CPU.
  - Outside: driven path is 33.147 m against an old maximum of 33.145 m. That is only where the last frame landed past the 33 m end point.
- **Conclusion:** patch 04 does not change driving behaviour. **The patch-04 player is the qualified player for further work**, and all earlier motion evidence (SIM1-03 player) still stands.

## 7. Also done today

- **Player shutdown-hang check, no motion.** Two stationary interlocked sessions, with and without recording, both shut down cleanly. That's too few to settle the cause, so the runner now captures the player's thread states if it is still alive 10 s after SIGTERM (`7aeb6eb`). Evidence `artifacts/s1/20261007T065223Z-hang-check/`.
