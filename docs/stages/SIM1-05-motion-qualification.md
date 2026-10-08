# SIM1-05 — Motion protocol, P1b cases, PRE-03/04 checks and simulator-hang containment

Date: **2026-10-08**. Request: "go on with SIM1-05". Player: the qualified patch-04 player (D18, frozen). New evidence:
- `artifacts/s1/20261008T065049Z-sim1-05-hang/` (90-file `MANIFEST.sha256`): three stationary, interlocked hang tests;
- `artifacts/s1/20261008T070048Z-d19-actuator/` (127-file `MANIFEST.sha256`): the D19 actuator repeats, M0 ×2 and M3b ×2, approved with "approve D19 A; run M0 and M3b repeats" (§5).

SIM1-05 item: *Submit the concrete numerical motion protocol, then execute approved P1b cases and the original PRE-03/04 checks. Qualify normalized actuator conversion, raw encoder-based speed and observed stopping; record simulator-hang containment separately.*

## Summary

- **Most of SIM1-05 was already done in S1.** The motion protocol and every moving test were run under amendment 1.2. This report maps each requirement to that evidence.
- **One gap was untested: simulator-hang containment.** It is now built and passes **3/3**. It is recorded separately below and is not counted as a stop.
- **The last gap is closed.** The open-loop actuator stages each ran once, but P1b asks for "three times each". You approved **D19 A**, and M0 and M3b were each run twice more on the patch-04 player. **All four trials pass** and agree with trial 1 (§5).

## 1. Simulator-hang containment (new, recorded separately)

**What a hang is.** The player process still exists but sends no telemetry. A hung player also freezes its own physics, so the guard and lease cannot act; braking cannot be proven. The only remedy is to end the process. This is therefore **containment, not a stop**, and it is never used as stop evidence.

**Watchdog** (runner, `47511de`):
- It triggers when the player is alive and connected but its last telemetry frame is older than **2.0 s**.
- The 2.0 s threshold is about 3× the worst gap seen in any qualified run (0.65 s, under GPU starvation in M4). Normal gaps are ≤ 0.25 s.
- On a hang it records the frame age and the player's thread states, SIGKILLs the player's process group, and fails the run with `Simulator hang … player killed (containment)`.
- The hang is stored under its own key (`simulator_hang`, classification "containment (process termination), not a stop").
- **Test hook:** `--sim-hang-test N` SIGSTOPs the whole player N s after observation starts. It is refused with any motion stage.

**Test:** three fresh-process sessions.
- Setup: guard observe, interlocked player with no motion authorization, and the AVLite stack in hold.
- Each pre-Connect screenshot was reviewed before the Connect click.
- Each player was SIGSTOPped 10 s into observation.

| Run | Detected after injection | Frame age at detection | Contained (detection → player reaped) | Player state at detection | Other children | Player left |
| --- | --- | --- | --- | --- | --- | --- |
| hang-1 | 2.14 s | 2.10 s | 134 ms | T (stopped) | all exit 0 | none |
| hang-2 | 2.04 s | 2.00 s | 145 ms | T (stopped) | all exit 0 | none |
| hang-3 | 1.92 s | 2.02 s | 142 ms | T (stopped) | all exit 0 | none |

- **Detection timing.** It was ≤ 2.15 s after injection. Hang-3 is under 2 s because its last frame arrived 0.10 s before the injection.
- **Stationary.** All three runs show 0 nonzero actuator frames, encoder ticks 0, and displacement ≤ 1 mm (IPS resolution).
- **Clean exit.** In each run the endpoint was released, and the runner exited 1 by design (a hang is a failed run).
- **Player integrity.** All 604 player files were unchanged after the three runs.
- **Limit.** This is containment of the process only. A hang while moving would leave the car where physics froze. In a frozen simulator that is harmless, but it is not a stop, and no moving hang test is proposed.

## 2. Numerical motion protocol (frozen)

Every P1b bound is frozen, confirmed by you and enforced in code:

| P1b bound | Frozen value | Where |
| --- | --- | --- |
| Speed | M6 envelope ≤ 0.3 m/s target, abort at 0.5 m/s | [M6 proposal](../planning/s1-05-lap-proposal.md) (D9–D11) |
| Steering, slew | ±0.35 rad requested; slew is the vendor's 183°/s (measured, M0) | D9, [M0](S1-M0-steering.md) |
| Duration, area | end at 33 m or 200 s; containment box x[−4.23, 2.12] y[−9.04, 7.65] | D10/D11 |
| Clearance | independent scorer: no contact or off-track; M6 min 0.104 m | [S1-05](S1-05-episodes.md) |
| Source/observation age | 500 ms (D3); speed feedback stale/lost 600/900 ms (D5 v0.3) | [protocol](../planning/s1-motion-protocol.md), [S1-03 proposal](../planning/s1-03-controller-proposal.md) |
| Request life, leases | request 500 ms from generation; runner lease 500 ms; guard cap 1 s | protocol §3 |
| Clock error | guard clock bound ≤ 400 ms, 2 s exchange window (SIM1-02 values kept) | `GuardCore.cs` |
| Stop | ≤ 1.5 s to observed rest; F1 travel ≤ 0.40 m from onset, stack abort ≤ 0.7 s | [M1 protocol v0.2](../planning/s1-06-m1-protocol.md) (D17 A) |
| Process containment | runner owns all process groups; D16 runner error → disarm, then stop; **simulator hang → kill after 2.0 s (this report)** | runner |

The SIM1-02 guard values were provisional: a 1 s lease cap, a 400 ms clock width and a 2 s window. They are kept unchanged. All S1 motion ran under them with large margins: clock bound max 42 ms and lease left at accept ≥ 311 ms ([measurements](S1-06-measurements.md)).

## 3. P1b cases and qualifications → evidence

| Requirement | Evidence | Repeats |
| --- | --- | --- |
| **Normalized actuator conversion, steering** | M0: +1 = 30° left, Ackermann angles exact to 0.0001°, slew 183°/s, expiry returns to 0 | **3** (trial 1 + D19 ×2) |
| **Normalized actuator conversion, throttle** | M1: + = forward, torque 21.4 N·m × throttle per wheel; M3/M3b: v = 5.02 m/s × throttle, linear 0.025–0.30 m/s, settles within one frame | M1 1 (4 pulses), M3 1, **M3b 3** (trial 1 + D19 ×2) |
| **Raw encoder-based speed** | wheel angle × 0.059 m over encoder acquisition time; encoder travel matches IPS within 0.6 mm (M3) and 1.5 mm (M3b); closed-loop M4 tracks 0.1/0.2/0.3 m/s (means 0.109/0.212/0.311) | M3, M3b, M4 trial 5; used by the speed loop in M5 and all 10 laps |
| **Observed stopping** | final stops: M4 0.34 s, M5 0.17 s, M6 ≤ 0.32 s, regression lap 0.34 s; limit 1.5 s | 3 M6 + 5 D13 + video + regression laps |
| **Stop cases** (lease expiry, runner loss) | M2 a/b (single), then **F1-3 stale request, F1-6 algorithm exit, F1-7 runner hang, F1-8 runner exit** | **3 each** ([M1 results](S1-06-M1-results.md)) |
| **Fault cases** | F1-1 LiDAR freeze, F1-2 NaN scan, F1-4 non-finite request, F1-5 disarm/re-arm, F1-9 runner error (D16) | **3 each**, 27/27 under v0.2; the v0.1 F1-1 failure is retained |
| **Driving cases** | M6 lap ×3 (D12 counts them as the circuit runs), D13 five timing windows | 3 and 5 |
| **Coordinate, sign and geometry conversions** | analytical ring fixtures (S1-05); SIM1-04 ray-cast fixtures on 10 laps (side p95 ≤ 4.4 mm), spawn offset 0 | 10 laps |
| **C0 progress, full-footprint off-track, contact independent of the GUI** | independent scorer (S1-05), SIM1-04 contact ±2 cm fixture on 10 laps | 10 laps |
| **Exceptions and incomplete episodes retained** | F1-1 v0.1 failure, M4 trials 1–4, reset attempt 1, player shutdown hangs (4/27) | — |

**Platform.** All of this ran on the SIM1-03 player except the regression lap. The regression lap showed patch 04 does not change driving: 10/11 measures fell inside the old range, and the 11th is end-point placement ([SIM1-03 report §6](SIM1-03-reset.md)). The SIM1-01/02/03 no-motion rechecks also pass on patch 04.

## 4. Original PRE-03/04 checks → evidence

**PRE-03** — *actual sensor/control transport, frames, units, timestamps, command retention and stop response within an approved bounded simulated-motion envelope.*

| Part | Evidence |
| --- | --- |
| Transport | isolated Devkit + bridge, versioned handshake ([SIM1-01](SIM1-provenance.md)); AVLite → bridge → supervisor → guard, traced end to end ([supervisor](S1-supervisor.md)) |
| Frames, units | scan convention, mount and order ([S1-02](S1-observation.md)); steering/throttle signs and units (M0, M1); encoder rad × 0.059 m (M3) |
| Timestamps | per-source acquisition identity and time; clock bound ≤ 42 ms in motion |
| Command retention | the guard lease: no command outlives its request (500 ms) or the 1 s cap; expiry returns to zero (M0, M2, F1-3/6) |
| Stop response | M2, F1 ×27, lap ends; all within the approved envelope |

**PRE-03 is satisfied**, now including three repeats of each open-loop actuator stage (D19).

**PRE-04** — *freeze the S1 scene/start/geometry and qualify clocks, the selected display mode, evaluator inputs and reset method.*

| Part | Evidence |
| --- | --- |
| Scene, start, geometry | C0 geometry from the player's colliders; scene equal on patch 04; spawn offset 0.000 m in 10 laps and after each reset ([SIM1-04](SIM1-04-evaluator.md)) |
| Clocks | acquisition simulation time per source; guard clock exchange; timing windows (D13) |
| Display mode | graphical, X display `:1`, 1280×720 player window, frame rate 60 Hz. Every run reviewed by screenshot before Connect. GPU p50 22–25 % (D13). Display-free operation is optional and not qualified. |
| Evaluator inputs | evaluator-only truth, per episode ([evaluator interface](../architecture/evaluator-interface.md)) |
| Reset method | GUI Reset → scene-load disarm, new episode and epoch, stale rejection; 3/3 on patch 04 ([SIM1-03](SIM1-03-reset.md)) |

**PRE-04 is satisfied by existing evidence.**

**Sources of evidence.** Both PRE items use S1 evidence, as amendment 1.2 allows when it meets the unchanged criteria. Their check boxes stay for your review at SIM1-06.

## 5. D19 — remaining P1b repeats (approved and run)

P1b asks for actuator cases "three times each". Each open-loop actuator stage ran once.

**Proposal A (recommended).** Run **M0 ×2** and **M3b ×2** on the patch-04 player, unchanged, with the same stage limits, approval checks and abort rules as their first runs.
- **M0:** steering only, brakes on, no translation expected.
- **M3b:** three straight holds at throttle 0.03/0.045/0.06, each from rest, ≤ 0.35 m of encoder travel, peak about 0.3 m/s.
- **Effect:** each stage then has 3 trials. M1's throttle-sign pulses are covered by M3b (same sign, larger throttle), and M2 is superseded by F1-3/F1-7 ×3.
- **Pass:** the same criteria as the first runs, plus agreement with them:
  - M0 angles within 0.0001°;
  - M3b gain within 1 % of 5.02.

**Alternative B.** Count the closed-loop runs as the actuator repeats: M4 trial 5, M5, M6 ×3, D13 ×5 and the regression lap all used the same conversions without fault. This needs no motion, but it is a weaker reading of P1b, because steering angles and the open-loop gain are not measured directly.

**Decision:** "approve D19 A; run M0 and M3b repeats" (2026-10-08, [record](../planning/s1-motion-approval.json)).

### Results

**How they ran.** Four fresh-process trials ran on the patch-04 player, with unchanged stage code and limits. Each pre-Connect screenshot was reviewed before the click.
- Every trial ended by itself on the first Connect click.
- All children exited 0 and the endpoint was released.
- There was no player shutdown hang.
- All 604 player files were unchanged afterwards.

**Comparison with trial 1.** Trial 1 ran on the SIM1-03 player. It was re-analysed with today's analysis scripts so that all three trials are compared the same way (`*-trial1-reanalysis.json`); the original analyses are kept.

**M0 (steering only, brakes on):**

| | Trial 1 | Trial 2 | Trial 3 |
| --- | --- | --- | --- |
| Result | pass | pass | pass |
| Worst wheel-angle error vs vendor Ackermann | 5.6×10⁻⁶° | 5.6×10⁻⁶° | 5.6×10⁻⁶° |
| Signs (+ left, inner wheel steers more) | all 6 commands | all 6 | all 6 |
| Measured slew | 183.2–184.6°/s | same | same |
| Steering back to 0 after lease expiry | 0.09 ms | 0.09 ms | 0.10 ms |
| Displacement | 1 mm | 1 mm | 1 mm |

**M3b (three straight holds at throttle 0.03 / 0.045 / 0.06):**

| | Trial 1 | Trial 2 | Trial 3 |
| --- | --- | --- | --- |
| Result | pass | pass | pass |
| Gain per level (m/s per unit throttle) | 5.016 / 5.010 / 4.921 | 5.018 / 5.009 / 4.914 | 5.019 / 5.007 / 4.920 |
| Representative gain (the analysis's steady gain) | 5.010 (−0.20 % vs 5.02) | 5.009 (−0.22 %) | 5.007 (−0.26 %) |
| Settled within | 0.23 s | 0.23 s | 0.22 s |
| Peak speed | 0.302 m/s | 0.302 m/s | 0.302 m/s |
| Stop after the request's generation | 0.55–0.56 s | 0.55–0.57 s | 0.55–0.57 s |
| Lateral deviation, yaw change | 1.4 mm, 0.06° | 0.4 mm, 0.0° | 1.4 mm, 0.0° |
| Encoder vs IPS travel (whole run) | 0.922 vs 0.918 m | 0.921 vs 0.917 m | 0.912 vs 0.908 m |

**Against the D19 pass criteria:**
- **M0 angles within 0.0001°:** met.
- **M3b gain within 1 % of 5.02:** met for the representative gain (−0.2 to −0.26 %) and for the 0.03 and 0.045 levels.
- **The 0.06 level reads 4.91–4.92 (−2 %) in all three trials, trial 1 included.** That hold stops at the 0.3 m/s speed cap after about 0.63 s, with a single settled frame, so its estimate comes from one frame. It was already reported this way in M3b. Across trials it varies by 0.15 %.

**Conclusion:** the normalized actuator conversion and encoder speed are repeatable to well under 1 % across three trials and both qualified players.

## 6. Status

- **Delivered:** the hang watchdog, its 3/3 containment test, and the full evidence map for P1b and PRE-03/04.
- **Delivered after approval:** D19 A, with M0 ×2 and M3b ×2 all passing. Every P1b actuator, stop and fault case now has three trials.
- **Open:** the intermittent player shutdown hang (4/27 F1 runs; diagnostics in place, not seen in the 7 runs since).
- **Check box:** left for your review.
- **Tests:** 131 script tests pass.
- **Next:** SIM1-06, which publishes the qualified backend and the PRE completion report.
