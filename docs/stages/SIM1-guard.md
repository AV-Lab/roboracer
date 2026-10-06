# SIM1-02 — Receiver guard and lease at the actuation hook

Date: **2026-10-05**. Run: `20261005T063753Z-sim1-02`. Protocol: [roboracer.guard/1](../../integration/autodrive/sim1/PROTOCOL.md#roboracerguard1--receiver-guard-sim1-02).

**SIM1-02 passes.** The guard runs in the simulator immediately before each actuation step. It validates every command against an arming epoch, an origin, an ordered sequence, a lifetime and a clock bound it computes from its own timestamps. It applies a command only while that command's lease is live. In guard mode the legacy, manual and GUI control paths are closed, and every accept, reject, apply and state change is acknowledged.

All disarmed P1a command, clock and failure cases passed in three independent fresh-process runs. Across 0.41 M physics steps in six live runs:

- no step produced nonzero output, torque or steer;
- every command reached the actuation hook only if it had been accepted while armed, and only before its expiry.

Two 60-second observation windows forwarded every fresh request without a rejection or an expiry. **Nothing moved:** a zero-output interlock was on throughout, and all accepted commands were exact zero. Moving tests remain behind the SIM1-05 motion protocol.

## 1. Scope

This continues SIM1 under the stage entry recorded for SIM1-01 ("go on the development plan").

**Covered:** SIM1-02's receiver validation and lease, applied/status acknowledgements, the closed bypasses, and the disarmed P1a command, clock and failure cases.

**Not covered, owned by SIM1-03:**

- live reset;
- epoch handling across reset or reconnect;
- stale queued commands across reconnect;
- a GUI-reset guard.

The guard already disarms on any scene load and on disconnect; live reset is not exercised here.

## 2. What was built

| Part | Content |
| --- | --- |
| [`GuardCore.cs`](../../integration/autodrive/sim1/RoboRacer/GuardCore.cs) | Unity-free state machine and validation (disarmed → armed → stopped/fault), plus the receiver clock bound. Compiled into the player and unit-tested under the pinned Editor's Mono: 86 deterministic checks pass, and a removed-duplicate-check mutant fails exactly its two checks. |
| [`Guard.cs`](../../integration/autodrive/sim1/RoboRacer/Guard.cs) | Unity glue. Inactive unless `-roboracerGuard` is given; an interlock forces zero output unless `-roboracerMotionAuthorized` is given (never passed here). It reads actual wheel torques and steer angles back after actuation, faults on any mismatch, and writes a bounded per-step trace. |
| [`vendor-sim1-02.patch`](../../integration/autodrive/sim1/vendor-sim1-02.patch), +12/−3 lines on top of sim1-01 | `VehicleController.FixedUpdate`: a guard call after `GetInput()`, immediately before `Steer()`/`Drive()`, and a read-back after `UpdateWheelPoses()`. `DrivingMode`: starts in "Guarded" mode and the toggle is blocked. `Socket`: guard intake, legacy write skipped, acknowledgement fields, emit-time record, disconnect hook. No physics, scene, sensor or brake change. |
| Bridge side | [`autodrive_guard.py`](../../scripts/autodrive_guard.py): request format, acknowledgement tracker, supervisor stand-in (a separate OS process sending only zero requests), the scripted scenario, and trace analysis. `autodrive_neutral.py --guard observe\|scenario` drives the live runs; `autodrive_derive.py` makes the verified derived copy. |

**Receiver clock bound.** The bridge now also reports when it received the frame it is replying to. The simulator bounds the clock offset using only its own emit and receipt stamps, so a sender cannot narrow the bound by reporting its own estimate. Deadlines map to the earliest possible simulator time. A disjoint new interval is a discontinuity and faults the session.

An offline run of the scenario script against a simulated receiver showed that the first bound design (ping time only) was about 150 ms wide, because the bridge holds every reply for its 100 ms pacing delay. Under that bound, together with a 500 ms lease, a single missed reply let the lease expire. Reporting the frame receipt tightened the bound to the two transit times; the live p50 was about 47 ms.

**Provisional parameters.** The lease is **1 s** (receiver cap and maximum request lifetime). The clock bound may be at most **400 ms** wide, and only exchanges from the last **2 s** count. These values let the stock ~3.9 Hz lock-step loop survive a missed reply. They are test parameters, not qualified motion bounds; SIM1-05 freezes the real values.

## 3. Build and static checks

- **Derived copy:** fresh, from the qualified authoring project. The tracked diff `4965e4fa…` and the status are equal; the Library cache is reused, so this is not a clean-import claim.
- **Build:** incremental IL2CPP, **261.4 s**, exit 0, no C# errors. Both `Provenance.Install` and `Guard.Install` are registered.
- **Source equality:** all seven patched vendor files and six staged RoboRacer files are byte-equal to the reviewed sources.
- **Strict serialized comparison** against the SIM1-01 player passes: 18 collider meshes, 120 scene scripts, numeric geometry and asset mapping all equal.
- **Player integrity:** all 604 player files are unchanged after all runs.
- **Pinned-API compile:** the patched vendor files and RoboRacer sources compile against the pinned 2021.3.9f1 API.
- **Tests:** 78 focused tests pass. They include 10 guard tests that run the C# cases under Mono and the full scenario against a simulated receiver, including a defective one.

The pinned project's fixed timestep is **1 ms**, and the guard runs on every step (measured 992–999 steps/s).

## 4. Live P1a cases (accepted set `scenario-b`, three fresh processes)

Each run had a visual, PID-bound pre-Connect review: Guarded label, HUD Autonomous, readings zero, disconnected, default display. Each case ran in its own arm epoch with live supervisor requests, and was checked against the player's own trace.

| Case | Injection | Required outcome | Runs 1/2/3 |
| --- | --- | --- | --- |
| Baseline | 6 fresh zero requests | each accepted, then acknowledged as applied at a step | pass ×3 |
| Malformed | garbage text; a missing field; a hex value | `malformed`; lease unchanged | pass ×3 |
| Nonfinite | throttle `NaN`, steering `Infinity` | `nonfinite` | pass ×3 |
| Out of range | throttle 1.5, steering −2 | `out-of-range` | pass ×3 |
| Duplicate | the same original in three new envelopes | accepted once, then `duplicate`; the lease expires at the original deadline | pass ×3 |
| Out of order | newer request, then older | newer accepted; older `out-of-order` | pass ×3 |
| Expired original in a new envelope | held past its own deadline, then forwarded | `expired`; never accepted | pass ×3 |
| Envelope replay | reused transport sequence | `envelope-replay`; content not processed | pass ×3 |
| Lifetime | 2 s deadline; deadline equal to generation | `lease-too-long`; `invalid-deadline` | pass ×3 |
| Epoch / origin | previous epoch; foreign origin | `stale-epoch`; `foreign-origin` | pass ×3 |
| Not armed / arming faults | request while disarmed; wrong session; wrong episode; malformed arm; arm while armed | `not-armed`; arm rejected for each reason | pass ×3 |
| Clock uncertainty | reply held 2.6 s without a receipt stamp (one exchange ≥2.6 s wide) | arm and request rejected `clock-uncertain`; normal exchanges re-arm | pass ×3 |
| Clock discontinuity | bridge clock jumped +1 s, then back | `fault clock-discontinuity` both ways; lease cleared; re-arm on the relearned offset | pass ×3 |
| Legacy bypass | `V1 Throttle 0.5` / `V1 Steering −0.3` in 3 replies | 6 counted and ignored; output zero; no fault | pass ×3 |
| Manual / GUI bypass | Up arrow held 1 s; click on the driving-mode button | manual input counted and ignored; `blocked driving-mode`; still armed in Guarded mode | pass ×3 (run 1 needed a second click, see §6) |
| Supervisor loss | SIGKILL the supervisor; the bridge keeps re-forwarding its last request | re-forwards rejected `duplicate`; `stopped lease-expired`; no further acceptance | pass ×3 |
| Devkit loss | SIGKILL the bridge | lease cleared by `disarmed disconnect` after **8.8 / 17.2 / 1.7 ms**; 0 steps applied in the next 2 s | pass ×3 |

**Trace analysis of the accepted runs:**

| | Run 1 | Run 2 | Run 3 |
| --- | ---: | ---: | ---: |
| Physics steps traced | 63,658 | 62,661 | 60,863 |
| Steps with nonzero output, torque or steer | 0 | 0 | 0 |
| Accepted (all exact zero) / applied | 63 / 63 | 57 / 57 | 57 / 57 |
| Rejections | 29 | 29 | 29 |
| Wall-clock lateness of expiry detection, max (ms) | 20.7 | 7.8 | 4.7 |
| Latest applied step relative to expiry (ms) | −5.8 | −0.03 | −0.7 |
| Scenario events missing from the player trace | 0 | 0 | 0 |
| Maximum reported displacement (mm; bound 10) | 2 | 2 | 2 |

**Expiry lateness** is the wall-clock time between the computed expiry and its detection. Unity runs its 1 ms physics steps in per-frame bursts, so no physics step runs in that gap. The guard checks before every step, and no step anywhere applied a command at or after its expiry.

Each run's process accounting:

- **Bridge and first supervisor:** exited −9, the intended kills.
- **Observer, player and second supervisor:** exited 0.
- **Port 4567:** released.

## 5. Observation windows (`observe`, two fresh 60-second processes)

| | obs-1 | obs-2 | SIM1-01 clean-01 / 02 |
| --- | ---: | ---: | ---: |
| Frames / receipt rate (Hz) | 238 / 3.822 | 241 / 3.865 | 3.872 / 3.903 |
| Requests accepted and applied | 230 | 233 | — |
| Rejections / expiries / faults | 0 / 0 / 0 | 0 / 0 / 0 | — |
| Smallest lease margin at application (ms) | 567 | 574 | — |
| Player CPU (% of one core) | 116.5 | 114.7 | 110.0 / 111.9 |
| Player RSS (GiB) | 0.71 | 0.71 | 0.71 / 0.72 |
| Bridge CPU (%) | 21.8 | 22.4 | 18.3 / 22.5 |
| LIDAR age p50 / p95 (ms) | 103.3 / 130.0 | 103.0 / 124.3 | 102.9 / 132.6 · 101.4 / 124.6 |
| Clock bound p50 (ms) | 45.2 | 44.3 | 44.8 / 43.2 |
| Maximum displacement (mm) | 3 | 3 | 3 / 3 |

**Overhead.** The guarded player costs about **4 points more CPU** (one core). That is consistent with the per-step guard and trace at 1 kHz. The receipt rate is about 1 % lower; memory, sensor age and clock bound are unchanged. These are descriptive measurements, not thresholds.

The stock transport stayed lock-step, with no telemetry gap. Every frame carried consistent acknowledgements: no event gap and no overflow.

## 6. Retained failures

1. **`build-console-failed-series-check.log`:** the first build refused before the Editor started. `git apply --check` tested patch 02 against the unpatched tree. The pre-check now applies the series in order to a throwaway index. The project was untouched.
2. **`scenario-a`, first scenario process:** all 14 contract, clock and legacy phases passed, and the player trace passed: 62,786 steps, 0 nonzero, 65 accepted and applied. Three harness defects failed it:
   - the synthetic GUI click was lost and not retried;
   - the supervisor-loss check counted the legitimate acceptance of a request buffered before the kill;
   - the Devkit-loss wait expected a lease expiry, although the disconnect (7.4 ms) had already cleared the lease, and it then parsed a trace line still being written.

   All three were fixed, with regression coverage in the simulated scenario. In `scenario-b` run 1, the first click was again lost; the retry was blocked and logged.
3. **`observe-failed-connect`:** the Connect click was lost, the same intermittent loss as SIM0 and SIM1-01, and the run hit its bounded startup timeout. The guard trace shows 174,890 steps, all zero, with nothing accepted. Its cleanup exposed a defect: the supervisor's blocking send stalled on the never-drained socket, so it needed SIGKILL. Sends are now non-blocking and count drops. This is the only change to `autodrive_guard.py` between the scenario and observation runs.

## 7. Status, limits and next step

- **SIM1-02 passes.** Counts: original plan 2/34; source amendment **6/10** (SIM0-01–04, SIM1-01–02); Linux recovery 4/4.
- **Limits:**
  - **Request clock:** the supervisor stand-in and bridge share the host's `CLOCK_MONOTONIC`. Requests are on the bridge clock, and the receiver never assumes a shared epoch with it.
  - **Stand-in:** it emits normalized zero commands. It is a fixture, not the S1 supervisor, which will own speed in m/s, steering in rad, and bounds.
  - **Trust:** the guard trusts the bridge-reported frame-receipt and ping stamps for the width of its bound.
  - **Detection limit:** a discontinuity smaller than the current bound width (~50 ms) is not detectable.
  - **Hang containment:** a simulator hang is not covered; that belongs to SIM1-05.
- **Next:** SIM1-03. Disarm/reset/epoch/rearm behavior, a verified single C0 start, stale command and sample rejection across reconnect and reset, and GUI reset through the same guard. Still disarmed. No nonzero command reaches the controller.

## 8. Evidence

`artifacts/simulator-build/20261005T063753Z-sim1-02/` contains:

- the derived-copy record, pinned-API compile and focused-test log;
- the build record with executed patches, the strict comparison and player integrity check;
- `scenario-b` and `observe` with their analyses;
- the three retained failures;
- executed tool copies, `review.py`, `result-summary.json` and `reproduction.json`;
- a 186-file manifest, `evidence-sha256.json` (SHA-256 `e5f7942eb0c1bef00ccf3e1fd78a766d66a89930953b18c8d1ea585e95eb91d6`).
