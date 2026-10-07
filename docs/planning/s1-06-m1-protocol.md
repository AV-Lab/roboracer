# S1-06 — M1 Run Protocol (F1 Fault Matrix and Timing Windows) — Proposal for Confirmation

Version **0.2**, 2026-10-07 (v0.1 2026-10-06; v0.2 = D17 A, §8). Plan item S1-06: *Run M1, preserve failures and publish first timing/resource/episode measurements against the frozen S1 operational limits. Propose later performance budgets for review before S2 acceptance.* The run matrix defines M1 as: C0; A; GT-labelled; three independent bounded-circuit runs; each F1 case three times; five timing windows under the sampling protocol; duration, bounds and tolerances frozen before the runs. **Nothing here runs until you confirm it.**

## 1. Already measured (no new motion)

`scripts/roboracer_timing.py` measured the three M6 laps with the plan's sampling window: 10 s warm-up from the start of the run phase, then 120 s. The [S1-06 report](../stages/S1-06-measurements.md) has the numbers. Every frozen S1 limit held with margin:
- observation age at request: max 334 ms (limit 500);
- telemetry gap: max 248 ms (limit 500);
- clock bound: max 42 ms (limit 400);
- final stop: max 0.32 s (limit 1.5).

These three windows were not declared as timing runs before they ran, so they are reported as preliminary. GPU use was not sampled; the runner now samples it every second from a separate thread.

## 2. Decisions needed

**D12 — circuit demonstrations.**
- **(Recommended)** Count the three M6 laps (2026-10-06, all clean, scored independently, run under the confirmed M6 bounds) as M1's three independent bounded-circuit runs.
- The alternative is three more M6 laps.

**D13 — five timing windows.** Five fresh-process M6 lap episodes, unchanged from M6 (A-lap, same limits, box containment, end at 33 m or 200 s), with GPU sampling on.
- Window: 10 s warm-up after the run phase starts, then 120 s. A lap's run phase lasts about 139 s, so the window fits.
- The same stop rule as M6 applies: at the first abort, contact or off-track, stop and report.
- These are timing runs. If you want them also counted as extra circuit evidence, say so; by default they are reported separately.

**D14 — F1 fault matrix**, below. Nine cases, each run 3 times in fresh processes: 27 short episodes.

**D15 — stop bound for faults at speed.** The protocol's stop qualification (stop within 1.5 s and under 0.15 m after the last nonzero request) was set for the M1–M3 pulses at ≤ 0.06 throttle. At M6's 0.3 m/s the worst designed path is a runner hang: the supervisor forwards until its 0.5 s runner lease expires, and the guard then honours the last request for up to 0.5 s. That alone allows up to 1.0 s × 0.3 m/s = 0.30 m before braking, which takes about one frame.
- **(Recommended)** For F1 cases: stop (speed < 0.02 m/s) within **1.5 s** of the injection, keeping the time limit, and travel after the injection **≤ 0.40 m**. Also no contact and no off-track by the independent scorer.
- This adds a bound for a new regime; it does not change any earlier stage's criteria.

**D16 — runner error cleanup order (code change).** Today, a runner exception terminates the owned processes straight away, so a stop is never observed: killing the player counts as containment, not braking.
- **(Recommended)** On error, the runner first sends a guard disarm and stops heartbeating. It then waits up to 2 s for the guard to report `disarmed` and the encoder speed to reach 0, records the result, and only then terminates its children.

## 3. F1 cases (each ×3)

**Common to every case:**
- **Setup:** an M6 episode (fresh player at the spawn, visual pre-Connect review, A-lap, M6 limits).
- **Injection:** made by the stack stage at **6.0 s** of run time. By then the car is at about 0.3 m/s on the opening straight, about 1.5 m from the spawn, where M5 and M6 showed ≥ 1.3 m clear ahead.
- **End:** the episode ends **8 s** after the injection, or earlier if the case ends the processes.
- **Every case must show:**
  - the expected detection;
  - no nonzero command applied after the detection deadline;
  - the D15 stop bound;
  - no guard fault, unless the case lists one;
  - no contact and no off-track;
  - all processes reaped and the player unchanged.

| # | Case | Injection | Expected detection and outcome (frozen) |
| --- | --- | --- | --- |
| F1-1 | Missing scan | Test hook freezes LiDAR acquisition for 5 s (the player is started with `-roboracerTestHooks`, as in SIM1-01); the bridge forwards the freeze request on a trigger from the stack | Snapshots rejected for `scan/pose skew` within 1 frame. The stack aborts on "no new observation" ≤ 0.5 s after the last good snapshot and requests zero. The supervisor refuses requests on observations older than 500 ms (`stale-observation`). Stop per D15. |
| F1-2 | Invalid scan | The stack's bridge replaces incoming scan ranges with NaN for 5 s (a test-only hook in `AutoDriveBridge`, off by default) | Snapshots rejected for `non-finite reading`; then the same outcome as F1-1. |
| F1-3 | Stale request (algorithm hang) | The stack stops stepping AVLite (process alive, no requests) | The guard's lease expires ≤ 0.5 s after the last generation (`state stopped lease-expired`). Stop per D15. |
| F1-4 | Non-finite request | (a) The controller returns a NaN target speed; (b) one NaN request is also sent straight to the supervisor socket, bypassing the plugin | (a) The plugin refuses it (`target_speed is not a finite number`) and sends nothing. (b) The supervisor rejects it as `non-finite`. Nothing non-finite reaches the guard; the lease expires; stop per D15. |
| F1-5 | Disarm / rearm | The runner sends a guard disarm; after 3 s at rest it re-arms (new epoch), and the stack resumes driving for 3 s, then requests zero | Guard `disarm-request`, then stop per D15. While disarmed: zero output, and requests rejected `not-armed`. Requests from the old epoch rejected `stale-epoch`. After rearm, new requests are accepted and the car moves again. One final lease expiry. |
| F1-6 | Algorithm exit | The runner SIGKILLs the AVLite stack process (marked as an expected kill) | No requests arrive; the guard lease expires ≤ 0.5 s after the last generation; stop per D15. The runner records the exit and keeps observing until the case ends. |
| F1-7 | Runner hang | The runner stops heartbeating (the M2 mechanism) while staying alive | The supervisor inhibits at its 0.5 s runner lease (`runner-lease-expired`) and refuses later requests; the guard lease expires; stop per D15. |
| F1-8 | Runner exit | The episode wrapper SIGKILLs the runner process | The supervisor inhibits via the runner lease; the guard lease expires; stop per D15, observed in the guard trace and the player's telemetry log. The wrapper then reaps the orphaned children by their recorded process groups. |
| F1-9 | Runner error | An exception is raised in the runner's main loop | D16 order: disarm, stop observed within the D15 bound, then cleanup. The run records the error and remains in the evidence. |

**Preservation:** failed, aborted and timed-out attempts are kept and reported. Following D11, I stop a case at its first unexpected outcome and report before repeating it.

## 4. What gets built before any run (no motion)

- **Fault trigger:** the stack stage writes `fault-inject.json` at the injection time. The bridge, runner and controller hooks act on it. Every hook is off unless a case is selected, and each case is selected only on the command line (`--f1-case`).
- **Hooks:** the test-only `AutoDriveBridge` scan corruption and controller NaN output, plus the D16 cleanup order and the wrapper's runner-kill/orphan reaping. Each gets unit tests and an offline smoke run without the simulator.
- **Analysis:** `roboracer_f1.py` checks each case's frozen expected outcome from the traces. `roboracer_timing.py` covers the timing windows.

## 5. Proposed later budgets (for review before S2 acceptance; not S1 criteria)

These are drafted from the measured windows and will be revised after D13's runs. They are budgets for S2 regression monitoring, not targets.

| Quantity | Measured (3 laps, worst value) | Proposed S2 budget |
| --- | --- | --- |
| Telemetry period p95 / max | 212 / 248 ms | ≤ 250 / 400 ms |
| Observation age at request p95 / max | 277 / 334 ms | ≤ 350 / 450 ms (limit 500) |
| Command → first observation after apply, p95 | 229 ms | ≤ 300 ms |
| Generation → guard accept p95 (lease estimate) | 162 ms | ≤ 250 ms |
| Tick period max, overruns | 102.9 ms, 0 | ≤ 110 ms, 0 per 120 s |
| Supervisor decision p95 | 0.15 ms | ≤ 5 ms |
| Final stop after zero request | 0.32 s | ≤ 1.0 s (limit 1.5) |
| Player / bridge CPU | 138 % / 28 % of one core | report only (host-dependent) |

## 6. What confirming this does not do

- It does not accept S1 or any check box.
- It does not authorize speeds above 0.3 m/s, reverse, steering beyond 0.35 rad, more than one lap per episode, unattended reset, or fault cases other than F1-1 to F1-9.

## 7. Requested reply

Confirm or change D12–D16. I will then build §4, smoke-test it offline, and run D13 and the F1 matrix in that order. I will stop at the first unexpected outcome.

## 8. v0.2 — D17 A (confirmed 2026-10-07)

After F1-1 trial 1 failed v0.1's timing checks (see the [M1 progress report](../stages/S1-06-M1-progress.md)), the user chose **D17 A**: time F1 stops from the fault's onset, not from the stack's injection request.

- **Onset per case:**
  - F1-1: the first telemetry frame whose LiDAR is reused (frozen);
  - F1-2: the first corrupted scan, recorded by the hook;
  - F1-5: the guard's `disarm-request`;
  - all other cases: the injection.
- **Stop:** speed < 0.02 m/s within **1.5 s of onset**. The stop time is the first telemetry frame at rest, so it can include up to one frame (~0.2 s).
- **Throttle deadline:** no nonzero throttle applied after **onset + 1.1 s**, up to any approved re-arm (F1-5).
- **Travel:** ≤ 0.40 m, still counted from the **injection** (stricter).
- **Abort check (F1-1, F1-2):** the stack aborts ≤ **0.7 s** after the last good snapshot (its 0.5 s rule plus two 100 ms ticks).
- **Reporting:** the injection-to-onset delay is reported for every case.
- **Unchanged:** every other check.

Applying the rules:
- F1-1 trial 1 stays a recorded **v0.1 failure**. F1-1 restarts with three fresh trials, then F1-2 to F1-9, three each.
- The analysis (`scripts/roboracer_f1.py --criteria v0.1|v0.2`) reproduces both versions.
- **Analysis fix found while preparing v0.2:** the stage switches to "stopping" inside a tick whose log row still says "run", so the abort and F1-5 final-stop references are the tick *before* the first "stopping" row. This corrects a 100 ms measurement error. Trial 1 still fails v0.1 with the correction (gap 0.656 s > 0.6 s).
