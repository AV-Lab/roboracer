# S1-06 — M1 progress: five timing windows pass; F1-1 trial 1 fails a frozen timing criterion (run stopped)

Date: **2026-10-06**. Approval: "approve D12, D13, D14, D15, D16; run M1" ([record](../planning/s1-motion-approval.json); [protocol v0.1](../planning/s1-06-m1-protocol.md)).

**Summary:**
- **D12 (circuit runs):** recorded. The three M6 laps count as M1's circuit demonstrations.
- **D13 (five timing windows):** done and passed.
- **D14 (F1 fault matrix):** stopped after the first real trial. F1-1 trial 1 broke two frozen timing checks: the vehicle stopped **1.61 s** after the injection (limit 1.5 s), and the guard applied throttle **24 ms** past the 1.1 s detection deadline. The cause is a defect in my protocol's timing reference, not in the system (§3).
- **Next:** following the protocol, I have stopped and ask for a decision (D17, §4) before any further F1 trial.

## 1. D13 — five declared timing windows (`artifacts/s1/20261006T061501Z-m1-timing/`)

Five fresh-process M6 laps on clean commit `4e3f6fc`, with GPU sampling on. Each 10 s + 120 s window was complete.

| Quantity | Range across the 5 windows |
| --- | --- |
| Laps (independent scorer) | 1 each; 0 contact / 0 off-track; clearance 0.104–0.106 m; lap 122.9–123.3 s |
| Telemetry | 5.78–5.83 Hz; period p95 212–214 ms, max 251 ms; real-time factor 1.000 |
| Observation age at request | p50 162–171 ms; p95 267–278 ms; max 346 ms (limit 500) |
| Command → first observation after it applied | p50 162–169 ms; p95 226–235 ms; max 269 ms |
| Generation → guard accept, p95 | 160–173 ms by lease estimate; 103–105 ms same-host |
| Supervisor decision, p95 | ≤ 0.14 ms |
| Ticks | max period 101.6 ms; 0 overruns |
| Clock bound, max | 42 ms (limit 400) |
| Final stop | 0.16–0.36 s (limit 1.5) |
| Max speed | 0.340 m/s (abort at 0.5) |
| CPU, % of one core | player 134–137, bridge 28, observer 8, stack 3, supervisor 2 |
| RSS, max | player 768 MiB, bridge 150, stack 147, supervisor 108, observer 73 MiB |
| GPU (device) | utilization p50 22–25 %, max 70 %; memory max 1686 MiB of 10240 |

Every frozen S1 limit held in all five windows. The player was unchanged after every run.

## 2. F1 tooling (commits `7b811bf`, `4e7b92c`)

- Stage-triggered injections for F1-1 to F1-9, plus the guard-driver disarm/rearm trigger.
- The D16 runner-error stop: disarm, observe the stop, then clean up.
- The F1-8 runner kill and orphan reaping.
- `roboracer_f1.py`, the per-case analysis.
- 122 script tests (11 new, including disarm → `not-armed` → rearm → `stale-epoch` against the guard model) and 41 plugin tests pass.

**Deviations from the protocol text, decided before any F1 run:**
- **F1-2 and F1-4 hooks:** these wrap the stack process's bridge and controller *instances* instead of adding hooks to the plugin source. The shipped plugin stays unchanged.
- **F1-2 rejection reason:** a NaN scan is rejected by the existing scan-validation check (`scan layout differs from the qualified convention`), not `non-finite reading` as the protocol text said.

**Failed attempts, both retained:**
- Attempt 1: the stack child refused `--f1-case f1-1`, because the freeze mapping applied in every mode. It was fixed in `4e7b92c`. No Connect and no motion happened.
- Attempt 2: refused before launch, because the episode output directory was not fresh.

## 3. F1-1 trial 1 — missing scan (`artifacts/s1/20261006T064801Z-m1-f1/f1-1-t1*`)

The injection came at 6.10 s of run time, at 0.27 m/s on the straight. Timeline (ms after injection, host monotonic):

| t | Event |
| --- | --- |
| 0 | Stack writes the freeze request (the bridge sends it with its next paced reply) |
| +344 | Last good snapshot (its scan was acquired just before the freeze) |
| +552 | First telemetry frame with the LiDAR frozen (reused) |
| +601 / +701 | Supervisor still forwards: observation age 348 / 449 ms, under the 500 ms limit |
| +816 | Guard accepts that last request with its remaining lease |
| +801 onward | Supervisor refuses every request: `stale-observation` |
| +1000 | Stack aborts, "no new observation for 0.60 s", and requests zero (refused as stale, as designed) |
| +1124 | Guard: `state stopped lease-expired`; throttle 0 |
| +1391 / +1606 | Frames show the car slowing, then at rest; frames are ~215 ms apart |

| Frozen check | Result |
| --- | --- |
| Snapshots rejected for `scan/pose skew`; stack abort on no new observation; supervisor `stale-observation` | **pass** |
| Travel after injection ≤ 0.40 m | **pass**: 0.358 m |
| No contact or off-track; no guard fault; all processes reaped; player unchanged | **pass** |
| Stop within 1.5 s of injection | **fail**: 1.606 s, the first frame at rest |
| No nonzero throttle after injection + 1.1 s | **fail**: throttle 0.0585 until +1124 ms |
| Abort ≤ 0.6 s after the last good snapshot (my analysis value; protocol text: 0.5 s) | **fail**: 0.656 s |

**Cause: a defect in the protocol, not in the system.** The protocol measured from the moment the stack *requested* the fault, but a missing scan only begins once the simulator acts on the request: 0.35–0.55 s later, since the request rides the next paced reply and the next acquisition. After that, the confirmed limits themselves allow:
- up to 500 ms of observation age;
- 500 ms of request life;
- about 0.2 s of braking;
- up to one frame (~0.2 s) before the stop is observed.

The designed worst case is therefore about 1.7 s from the request, and the 1.5 s / 1.1 s checks could not hold for F1-1. The 0.5–0.6 s abort check likewise ignored the stack's 100 ms tick: its rule fires at the first tick more than 0.5 s after the tick that last saw a new snapshot, so up to about 0.7 s after the snapshot.

Measured from the fault's **onset** (the first frozen frame, +552 ms):
- the guard's last nonzero throttle came at +0.57 s;
- the car was at rest by the next frame, 1.05 s later;
- every layer acted in its designed order.

## 4. Decision needed — D17 (protocol v0.2 change request)

The plan forbids changing criteria after seeing results. **I therefore keep F1-1 trial 1 recorded as a failure under v0.1, whatever you decide.** The question is what applies to the remaining runs.

**(Recommended) A — measure from the fault's onset.** A new set of 3 F1-1 trials replaces the failed one.
- **Onset per case:**
  - F1-1: the first telemetry frame with a frozen LiDAR;
  - F1-2: the first corrupted scan;
  - F1-5: the guard's `disarm-request`;
  - all other cases: the injection itself (immediate effect).
- **Kept:** stop within 1.5 s of onset; no throttle after onset + 1.1 s; travel ≤ 0.40 m counted from the injection (stricter); every other check unchanged.
- **Abort check:** set to the stack's actual rule, ≤ 0.7 s after the last good snapshot (0.5 s plus two 100 ms ticks).
- **Reporting:** the injection-to-onset latency is reported for every case, and the stop time is stated as "first frame at rest", including up to one frame.

**B — keep the injection reference, but widen F1-1 and F1-2 to the designed worst case:** stop ≤ 2.0 s and throttle deadline 1.7 s.

Either way, the F1 matrix restarts at F1-1 with three fresh trials. All other cases are unchanged and unrun.

**Not changed:** the five D13 windows, D12, and every frozen operational limit. No check box is ticked.
