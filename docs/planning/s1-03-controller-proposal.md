# S1-03 Target-Speed Controller and Reactive Baseline A — Proposal for Confirmation

Version: **0.2 — D5 revised after M3; awaiting confirmation of the changes.**
- **v0.1:** confirmed on 2026-10-05 with "approve D4 A, D5, D6, D7; run M3 only". M3 passed ([report](../stages/S1-M3-identification.md)).
- **What M3 changed:** the plant is a static gain (v ≈ 4.9 m/s × throttle, settled within one frame), not an accelerator. The v0.1 D5 gains and u_max = 0.03 therefore no longer fit. **D5 below is revised and needs your confirmation**, and **M3b** is added to D8.
- **Unchanged:** D4, D6 and D7 are as confirmed.
- **v0.3 change request (2026-10-05, after M4 trial 3; awaiting confirmation):** raise D5's stale-feedback thresholds from **0.4 s → 0.6 s** (zero throttle) and from **0.6 s → 0.9 s** (inhibit). Everything else is unchanged; see §7.
- **v0.2 confirmed** on 2026-10-05 ("comfirm"). **M3b passed** ([report](../stages/S1-M3b-identification.md)): linear over 0.025–0.30 m/s with **K = 5.02**. M3's 4.90 was an analysis-window bias, now corrected. Under the confirmed ±10 % rule, D5 uses K = 5.02; u_max = 0.07 is then about 0.35 m/s. M4 and M5 are not yet authorized.

Date: 2026-10-05. [Chinese version](s1-03-controller-proposal.zh-CN.md). This follows [motion protocol v0.1](s1-motion-protocol.md) §4 "After M0–M2". Evidence: [M0](../stages/S1-M0-steering.md), [M1](../stages/S1-M1-throttle.md), [M2](../stages/S1-M2-stops.md).

**Nothing in this document is executed until you confirm it, or a changed version.** Until then:
- the plugin's `max_target_speed_mps` stays 0;
- the supervisor forwards only exact zero for AVLite requests;
- no new motion stage is opened;
- steering while moving remains unauthorized.

## 1. What S1-03 must deliver (plan, unchanged)

> S1-03 — Deliver A through AVLite's actual execution path with visible GT labels, paced sampling and measured command-to-response behavior. Do not count executor ticks as physics steps.

The plan also fixes these rules:
- **Conversion lives in the backend.** "Keep measured speed feedback, conversion, saturation, rate limits and calibration in the backend actuation layer", and do not keep a second longitudinal PID in the algorithm.
- **The supervisor stops on stale feedback.** If a speed-feedback controller is needed, the supervisor "also stops on stale feedback".
- **A is reactive.** It is "a small reactive integration baseline: reactive steering without reference-path/corridor planning".
- **AVLite velocity** comes from "approved timestamped motion observations", not assumed GT.

## 2. Measured facts this proposal is built on

| Quantity | Value | Source |
| --- | --- | --- |
| Steering | normalized ±1 = ±30° internal angle, positive = left; Ackermann split exact; slew 183°/s outward, instant return to 0 | M0 |
| Throttle | positive = forward; torque 21.4 N·m × throttle per wheel; zero throttle = 85.6 N·m brake on all wheels (a hard brake, not coasting); negative throttle not characterized and not authorized | M1, vendor source |
| Short-pulse response | 0.2 s pulse: peak ≈ 4.7 m/s and travel ≈ 0.95 m per unit throttle; initial acceleration ≈ 24 m/s² per unit throttle (0.02 → ≈ 0.48 m/s²). **Steady-state speed for a held throttle is unknown** (no pulse was held). | M1 |
| Stops | throttle → 0 stops the car within 0.35–0.58 s of request generation (M1). Expiry or inhibition stops it within 0.78 s (M2). | M1, M2 |
| Speed feedback | Encoder angle = wheel rotation (rad, 3 decimals; +0.589 rad = 35 mm at r = 0.059 m). Resolution ≈ 0.06 mm per 0.001 rad, far better than IPS (1 mm). Acquisition-stamped per frame. | M1, S1-02 |
| Telemetry / actuation update | Frames about every 0.20 s (5 Hz); one forwarded request per frame. Observation age at the supervisor p95 110 ms. Request generation → guard accept ≈ 0.13 s. | M1, M2 |
| AVLite | `SyncExecuter` paced at 10 Hz wall clock; each tick reads one pinned snapshot | S1 supervisor |
| Workspace at spawn | heading −90°; corridor ≈ 1.27 m wide (left 0.74 m, right 0.54 m); straight ahead ≈ 7.4 m (±5°) before the track curves | S1-02 scan |

**Consequences:**
1. A speed loop can update at most at 5 Hz, with about 0.3–0.45 s of total delay (acquisition → decision → forward → apply).
2. Zero throttle is a hard brake, so the controller can only drive or brake hard; it cannot coast.
3. The steady-state throttle-to-speed relation must be measured before closing the loop.

## 3. Decisions needed

**D4 — where the speed loop's feedback comes from** (the loop itself lives in the supervisor, per the plan).
- **(Recommended) A: the supervisor subscribes itself.** It reads the encoder, IPS and provenance topics through the same `SnapshotAssembler`, in a private rclpy context, and computes speed from encoder angles and acquisition stamps. The supervisor's input then never depends on the algorithm process being correct, and "stale feedback → stop" is measured on the supervisor's own clock. Cost: rclpy in the supervisor process.
- **B: the bridge sends measured speed with each request.** This is simpler, but the feedback passes through the algorithm process. An algorithm-side bug could then feed the loop a wrong speed, although an algorithm hang still stops the car through expiry.

**D5 — the backend speed controller (REVISED in v0.2 after M3).** It lives in the supervisor and is used only for AVLite `request`s; calibration stages are unchanged.

**Measured plant (M3):**
- v_ss = K·u, with K = 4.90 m/s per unit throttle (4.89–4.91 over 0.005–0.02);
- settles within one frame (≤ 0.23 s);
- about 0.13 s from request generation to application, plus 0.2 s frame quantization;
- zero throttle is a hard brake, stopping within about one frame.

**Control law, per forwarded frame:**
- `u = clamp(v*/K + u_I, 0, u_max)`, a static inverse feedforward plus a bounded integral trim.
  - `u_I ← clamp(u_I + Ki·e·Δt, −0.01, +0.01)`, where `e = v* − v`, `v` is the encoder speed from D4, and Δt is the encoder acquisition sim-time interval.
  - `u_I` is frozen while u is saturated, and reset to 0 whenever v* = 0.
- There is **no proportional term**: the feedforward is already the plant inverse, and the trim only corrects model error (±0.01 ≈ ±0.05 m/s).
- **Ki = 0.10** per m/s per s, which gives an integral-loop crossover of K·Ki ≈ 0.49 rad/s. With about 0.45 s of total delay, the phase margin is about 90° − 0.49 × 0.45 rad ≈ **77°**.
- **u_max = 0.07** (about 0.34 m/s), enough for v* = 0.3 m/s with trim margin.
- **Rate limit:** u may rise at most 0.02 per frame (≈ 0.1 m/s per frame); it may fall without limit.
- **Target 0:** u = 0 (hard brake), and the trim resets.
- **Overspeed, unchanged:** v > v* + 0.15 m/s, or v > 0.5 m/s → u = 0 for that frame.
- **Stale feedback, unchanged:** feedback older than 0.4 s, or missing → u = 0; after 0.6 s → disarm.
- **Retuning:** M4 may adjust Ki within ±50 % and K within ±10 % of the M3/M3b value only, with every change recorded.

**Validity range:** K is measured only up to 0.1 m/s (u = 0.02). M3b (D8) must confirm it up to about 0.3 m/s (u ≈ 0.06) before M4 uses it.
- **Steering:** converted exactly, `normalized = clamp(steer_rad / 0.5236, −1, 1)`, with no extra rate limit (the vendor slews at 183°/s). Steering is forwarded only when D8 authorizes steering while moving; until then any nonzero steer is rejected.

**D6 — A, the reactive baseline, as an AVLite plugin `ControlStrategy` (`GapFollowController`).**
- **Steering:** follow-the-gap with disparity extension on the LiDAR in the vehicle frame (scan from the `SensorFrame`, mount applied).
  - Ignore beams outside ±100°.
  - Inflate obstacles by half the vehicle width (0.15 m) + 0.10 m margin.
  - Steer toward the deepest free direction, with steer = atan(2·L·sin α / l_d) (L = 0.324 m, l_d = 1.0 m), clamped to ±0.35 rad.
- **Target speed:** `v* = min(0.3, 0.3 · (1 − |steer| / 0.6), 0.25 · (d_front − 0.5))`, floored at 0, where `d_front` is the minimum range within ±10°. It never uses GT pose.
- **Output:** a `TargetSpeedSteeringCommand`. GT pose is used only for labelled logging and progress.
- **AVLite state:** the bridge fills `EgoState.velocity` from encoder speed, labelled `encoder`, so AVLite state has an approved velocity source. GT velocity is not used.

**D7 — paced sampling and the command-to-response measurement.**
- AVLite runs at 10 Hz wall clock; the stage periods are 0.99 × the tick period (as now).
- Physics progress uses simulator time from provenance (sim time and fixed steps), never tick counts.
- For every forwarded request, the chain is recorded:
  - AVLite tick start → request generation → supervisor decision → guard accept (sim) → first applied step;
  - then the first observed response: encoder speed change > 0.01 m/s for throttle, or the wheel angle reaching 90 % of its target for steering.
- These are reported as separate latencies, never summed across unrelated clocks.

**D8 — the next motion stages.** Each is confirmed and run separately, with all motion-protocol §3 rules unless changed below.
- **M3, identification (open loop, straight, steering 0).** Calibration holds of throttle 0.005, 0.01 and 0.02. Each holds until encoder speed ≥ 0.3 m/s, 2.0 s, or 0.5 m of travel, then zero. Each starts from rest. Up to 6 trials, from a fresh process at spawn. It measures steady-state speed vs throttle (if reached), acceleration vs speed, and the brake-stop distance from 0.3 m/s. This gives `u_ff` and confirms b.
- **M3 result (v0.2):** passed. v ≈ 4.90 m/s × throttle, settling within one frame, linear over 0.005–0.02.
- **M3b, NEW in v0.2: identification up to the M4 range (open loop, straight, steering 0).** It uses the same source, rules and end conditions as M3 (encoder speed ≥ 0.3 m/s, 2.0 s, or 0.4 m of travel, then zero throttle), with holds of throttle **0.03, 0.045 and 0.06**, expected at about 0.15, 0.22 and 0.29 m/s.
  - **Pass:** the M3 criteria, plus K within ±10 % of 4.90 at every level (otherwise the measured map replaces the single gain in D5).
  - **Expected per hold:** at most about 0.4 m of travel plus braking of about 0.19 s × speed (≤ 60 mm), so about 1.4 m per trial. The 7.4 m straight ahead covers this.
  - **Trials:** at most 6.
- **M4, closed-loop speed (straight, steering 0, D5 active).** AVLite runs a test controller requesting v* = 0.1, 0.2 and 0.3 m/s, each for 3 s, then 0. At most 2.5 m of travel per trial. Pass:
  - mean speed within ±0.05 m/s of v* over the last 1 s of each step;
  - overshoot ≤ 0.1 m/s, and no throttle/brake chatter (at most 2 brake events per step);
  - a stop from 0.3 m/s within 1.5 s;
  - stale-feedback injection (encoder topic withheld) → u = 0 within 0.4 s plus one frame.
- **M5, A on the circuit segment (steering while moving).** `GapFollowController` drives from spawn for at most 6 m or 40 s, with v* ≤ 0.3 m/s, then the runner requests 0 and disarms. This is the S1-03 demonstration and its command-to-response measurement. Extra abort rules:
  - side clearance < 0.15 m;
  - forward clearance (±10°) < 0.5 m;
  - speed > 0.5 m/s;
  - |steer| > 0.35 rad requested;
  - 2 consecutive frames without a snapshot.
- **Not covered here:** full laps (the M1 circuit episode, S1-05/06), speeds above 0.3 m/s, reverse.

## 4. Settings that change only after confirmation

| Setting | Now | M4/M5 |
| --- | --- | --- |
| `max_target_speed_mps` (plugin) | 0 | 0.3 |
| Supervisor AVLite path | exact zero only | the D5 (v0.2) controller, u_max = 0.07, hard overspeed 0.5 m/s |
| Steering while moving | rejected | allowed in M5 only, \|steer\| ≤ 0.35 rad |
| Approval record | M0–M2 | adds the confirmed stages |

## 5. What confirming this does not do

- It does not accept S1-02, S1-03 or S1-04, or any todo, and does not change acceptance criteria.
- It does not authorize laps, speeds above 0.3 m/s, reverse, or the B stack.
- Each of M3, M4 and M5 is run only after its own go-ahead.

## 6. Requested reply

D4, D6 and D7 are already confirmed. For v0.2, please confirm or change:
- **revised D5**: feedforward with integral trim, K = 4.90, Ki = 0.10, trim ±0.01, u_max = 0.07, rise limit 0.02 per frame;
- whether to run **M3b** (throttle 0.03 / 0.045 / 0.06).

M4 and M5 stay unauthorized until you say otherwise.

## 7. v0.3 change request: stale-feedback thresholds (after M4 trial 3)

**What M4 trial 3 showed** ([report](../stages/S1-M4-speed.md)):
- **Feedback age.** The supervisor's own encoder feedback (D4 A) arrives every telemetry frame: p50 243 ms, p95 284 ms, max 298 ms. That is slower than in M3b (206 ms), with the additional subscriber running. Delivery takes about 155 ms more. At request time the feedback is therefore **p50 274 ms, p95 405 ms, max 564 ms old**.
- **Spurious hard brakes.** The 0.4 s stale rule fires routinely. Zero throttle is a hard brake, so the car stops within a frame and the rise limit ramps it back. That cycling pulled the 0.2 / 0.3 m/s step means down to 0.164 / 0.189 m/s, with 3–4 brake events per step.
- **Loss rule.** The 0.6 s loss rule would occasionally inhibit a healthy run.
- **Everything else passed:**
  - the stop from 0.3 m/s took 0.45 s;
  - the stale-feedback cut took 0.20 s, with inhibition 0.40 s after the blackout;
  - the final stop took 0.11 s;
  - there was no guard fault.

**Proposed change.**
- `stale_ns` 0.4 s → **0.6 s**, giving zero throttle (hard brake);
- `lost_ns` 0.6 s → **0.9 s**, giving sticky inhibition.

Each threshold is the measured maximum age (564 ms) plus a margin. Nothing else changes.

**Cost.** The worst-case reaction to frozen feedback rises from about 0.4 s + one frame to about 0.6 s + one frame, and braking still takes about one frame. At the 0.35 m/s throttle-cap speed, that adds at most about 7 cm of travel before braking. The guard's own lease (0.5 s from generation) and the supervisor's runner lease are unchanged, so a hung algorithm or runner is still stopped exactly as in M2.

**Alternative (not recommended alone):** cut the bridge's reply pacing from 50 ms to 0, a tooling change that shortens the frame period. On its own it would leave a max age of about 0.5 s, still above 0.4 s.

**Requested reply:** confirm v0.3 (thresholds 0.6 / 0.9 s), and say whether to re-run M4, then M5 if M4 passes.
