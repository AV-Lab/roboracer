# S2 proposal — unattended episodes, diagnosis and fault recovery

Version **0.1 — for confirmation**. Date: **2026-10-08**. Entry: "go on with S2", after PRE and S1 were accepted ("accept all recommended boxes"). Backend: the frozen [qualified patch-04 backend](../architecture/qualified-backend.md). Feasibility evidence: `artifacts/s2/20261008T092831Z-entry/`.

**S2 goal (plan):** one invocation runs repeated AutoDRIVE episodes, validates each initial state, records results, and recovers or fails cleanly after defined faults.

**M2 acceptance (plan):**
- C0, with the same A envelope;
- **ten consecutive healthy unattended episodes**;
- **each F2 case three times**;
- five timing windows;
- three fresh-process replays per selected fixture;
- correct initialization, ownership and fault outcomes;
- **no stale reapplication**;
- approved time and age budgets and replay tolerances.

**Baseline first:** three initialization cycles, each F2 case once and five timing windows. Budgets are then proposed for your approval, and the acceptance matrix is frozen afterwards.

Nothing here authorizes motion. Decisions D20–D24 are requested in §6.

## 1. What S1 already provides

| Need | Already qualified | Gap for S2 |
| --- | --- | --- |
| Reset mechanism | GUI Reset → scene-load disarm, new episode and epoch, stale requests rejected; 3/3 stationary on patch 04 (SIM1-03) | Not yet used **between driving episodes** or unattended |
| Process ownership | runner owns every process group; hang watchdog; D16 runner error → disarm, then stop | No **recovery**: any fault ends the invocation |
| Initial-state checks | spawn offset 0.000 m in every run; episode and epoch checks in the reset scenario | **A person reviews every pre-Connect screenshot.** That is a manual step in every episode. |
| Recording | snapshot identities, ticks, supervisor and guard traces, bridge frames | **Raw scans are not recorded** (only hashes), so no algorithm replay is possible |
| Faults (F2 list) | disarmed (P1a, SIM1-02): duplicate/out-of-order, clock discontinuity, supervisor loss, Devkit loss, reset/replay; stationary: simulator hang (SIM1-05) | **None under motion**, and no recovery after them |

## 2. Unattended initialization (S2-01) — feasibility measured

A GUI Reset reloads the scene **disconnected**, so every episode needs a Connect click. Today I review a screenshot before each click.

**The proposal replaces that review with an automated check of the same screen regions.** Only the near-white text pixels of five regions are compared against a reviewed reference:
- the connection state, which must read "Disconnected";
- the mode, which must read "Guarded";
- the HUD's driving mode, gear and speed;
- throttle and steering;
- encoder ticks.

The 3D view, simulation time, frame rate and lap timer are excluded.

| Test (`ui-stability-text.txt`) | Result |
| --- | --- |
| 10 safe-state screenshots (patch-04 player runs and one after a GUI Reset) | **0 mismatched pixels** in all five regions |
| Raw pixels without the text filter | not stable: the semi-transparent HUD shows the moving 3D view (up to 13 intensity steps) |
| Negative control: a Connected screen | caught: 942 px in the connection region |
| Negative control: a Manual-mode screen | caught: 810 px in the mode region, 214 px in the HUD |

The safety design does not change.
- The guard starts every scene disarmed, and the motion flag is fixed at launch.
- **After** Connect and **before** arming, the runner also checks telemetry:
  - a new episode and epoch;
  - guard disarmed with no fault;
  - all sources freshly acquired in the new episode;
  - pose at the C0 spawn within a tolerance (proposed: 0.010 m, 1°; measured: 0.000 m);
  - wheels still (encoders unchanged over 1 s).

Any failure means no arm, and the episode is recorded as a **failed initialization**.

**Cycle components measured so far** (S1 runs; `cycle-times.txt`):
- fresh process to first observation: median 18 s, including my review wait;
- cleanup: median 2.2 s.

GUI Reset to a ready state has not been timed under automation. The baseline measures it.

## 3. Lifecycle and recovery (S2-02)

**One invocation is one batch:** a fresh player, Connect, then for each episode:
1. initialize (§2);
2. arm;
3. drive one A-lap (the M6 envelope);
4. stop;
5. disarm;
6. score;
7. GUI Reset.

**Recovery ladder after a failed episode:**
1. GUI Reset;
2. if that fails, or the player is hung or gone, restart the player (fresh process, automated check, Connect);
3. if the restart fails, **end the batch** and report.

Each step is recorded. A recovered batch is labelled with every recovery action, and nothing is hidden.

The batch also ends on:
- any containment-box exit or contact (as in S1);
- two consecutive failed recoveries;
- a wall-time cap (proposed: 30 min per batch).

## 4. Recording and replay (S2-03) — no motion needed to build

- **Recorder.** An optional message hook at the bridge's single input, `AutoDriveBridge._offer`, records every raw Devkit message with its arrival time: scan ranges as float32, IMU, encoders, IPS and provenance text. It is bounded (proposed: 64 MB per episode; a lap is about 6 MB). With the hook off, the bridge is unchanged.
- **Replay** (open-loop, labelled as such).
  - Recorded messages are fed in arrival order into a fresh `SnapshotAssembler`. Every committed snapshot must match the live record (sequence, episode and scan hash).
  - Then, for every live tick, the snapshot it used goes through the same `get_sensor_frame` path into the same controller class and parameters. The command must equal the live tick's target speed and steer.
- **Fixtures:**
  - analytical scans (corridor, offset corridor, ring), whose outputs are computed independently;
  - recorded episodes (a stationary recording now; laps once motion is approved).

  Each is replayed in **three fresh processes**.

## 5. F2 fault catalog (S2-04), proposed injection and expected outcome

All F2 cases are injected during an A-lap inside the M6 envelope, once each in the baseline. Every case also checks that **no stale command is reapplied** after it. The stop criteria are the frozen S1 ones: ≤ 1.5 s to observed rest, measured from fault onset.

| Case | Injection | Expected outcome | Recovery |
| --- | --- | --- | --- |
| F2-1 reset during motion | GUI Reset click mid-lap | scene-load disarm; car back at spawn; old-epoch requests `stale-epoch` | initialize the next episode |
| F2-2 duplicate observations | bridge test hook re-delivers each message of 5 frames | assembler rejects duplicates (no snapshot); driving continues | none needed |
| F2-3 out-of-order observations | hook swaps provenance order for 5 frames | rejected frames counted; no snapshot out of order; driving continues or stops on staleness | none needed |
| F2-4 clock jump | step the bridge's clock-exchange offset by 1 s | guard disarms on clock discontinuity; stop | rearm with a new epoch; continue the episode |
| F2-5 stale speed feedback | supervisor ignores encoder feedback (as M4) | throttle 0 after 0.6 s, inhibit after 0.9 s; stop | new supervisor, next episode |
| F2-6 Devkit loss | SIGKILL the Devkit bridge process | no telemetry → stack and supervisor stop; guard Devkit-loss clears the lease | restart the bridge, then reset |
| F2-7 supervisor exit | SIGKILL the supervisor | guard lease expiry; stop | restart the supervisor; next episode |
| F2-8 supervisor hang | SIGSTOP the supervisor | guard lease expiry; stop | kill and restart; next episode |
| F2-9 simulator exit | SIGKILL the player | **containment, not a stop**: the process is gone | fresh player |
| F2-10 simulator hang | SIGSTOP the player | watchdog kill after 2.0 s; **containment, not a stop** | fresh player |

## 6. Decisions requested

- **D20 — initialization mechanism.**
  - **A (recommended):** one player per batch, with GUI Reset between episodes and a fresh player only as recovery.
  - **B:** a fresh player for every episode. This is slower, about 20–30 s more per episode.
- **D21 — automated pre-Connect check.**
  - **A (recommended):** replace the per-Connect human review with the text-region check (§2) plus the telemetry readiness checks. You review the reference image once; that is recorded as setup, not hidden.
  - **B:** keep the human review. Batches would not be unattended, and S2 acceptance could not pass.
- **D22 — S2 motion scope.** Allow unattended batches and GUI Reset between laps, inside the **unchanged M6 envelope**: A-lap, ≤ 0.3 m/s, one lap per episode, the containment box, and the same aborts. This removes "unattended reset" from the not-authorized list for S2 only. Each live run set still gets its own "run" approval, starting with the baseline (§7).
- **D23 — F2 catalog.** Confirm or change the cases, injections and expected outcomes in §5.
- **D24 — replay tolerance.** Require **exact equality** of snapshot identities and controller outputs on this host and environment (both are deterministic float64 code), with three fresh-process replays per fixture. Any difference fails.

## 7. Plan and order

1. **Now, no motion:**
   - the recorder and replay tool, with analytical fixtures and unit tests;
   - a stationary interlocked recording, replayed;
   - the batch runner and initialization checks, tested stationary on the interlocked player (Reset, check, Connect, readiness ×3, all unattended);
   - the F2 injection hooks, tested disarmed.
2. **After D20–D24 and a "run" approval:** the **M2 baseline**:
   - one batch of three laps (three initialization cycles);
   - each F2 case once;
   - five 120 s timing windows (10 s warm-up).
3. **Then:** propose budgets (initialization tolerances, timeouts, age and latency, observation windows, replay tolerance) from the baseline.
4. **After your approval:** freeze the acceptance matrix — 10 consecutive episodes, F2 ×3, five windows, replays ×3 — and run it.
