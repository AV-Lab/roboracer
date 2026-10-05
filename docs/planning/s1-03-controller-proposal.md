# S1-03 Target-Speed Controller and Reactive Baseline A — Proposal for Confirmation

Version: **0.1 — DRAFT, not confirmed.** Date: 2026-10-05. [Chinese version](s1-03-controller-proposal.zh-CN.md). This follows [motion protocol v0.1](s1-motion-protocol.md) §4 "After M0–M2". Evidence: [M0](../stages/S1-M0-steering.md), [M1](../stages/S1-M1-throttle.md), [M2](../stages/S1-M2-stops.md).

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

**D5 — the backend speed controller** (in the supervisor, used only for AVLite `request`s; calibration stages unchanged). Per forwarded frame:
- `u = clamp(u_ff(v*) + Kp·e + Ki·∫e, 0, u_max)`, with `e = v* − v`.
  - `v` is the encoder speed from D4.
  - `u_ff` is the feedforward map from M3.
  - The integrator is clamped (anti-windup) and frozen while saturated.
- **Rate limit:** u may rise at most 0.005 per frame; it may fall without limit.
- **Target 0:** u = 0, a hard brake.
- **Overspeed:** v > v* + 0.15 m/s, or v > 0.5 m/s → u = 0 for that frame.
- **Stale feedback:** feedback older than 0.4 s, or missing → u = 0 (the plan's rule); after 0.6 s → disarm.
- **Initial gains**, from the M1 plant estimate b ≈ 24 m/s² per unit throttle, targeting about a 1 s closed-loop time constant:
  - Kp = 1/(b·τ) ≈ **0.04** per m/s;
  - Ki = Kp/2 s ≈ **0.02** per m/s per s;
  - **u_max = 0.03** for S1-03.
- **Stability margin:** with about 0.45 s of delay at the 1 rad/s crossover, the estimated phase margin is about 37°. M4 will retune within ±50 % only, with each change recorded.
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
| Supervisor AVLite path | exact zero only | the D5 controller, u_max = 0.03, hard overspeed 0.5 m/s |
| Steering while moving | rejected | allowed in M5 only, \|steer\| ≤ 0.35 rad |
| Approval record | M0–M2 | adds the confirmed stages |

## 5. What confirming this does not do

- It does not accept S1-02, S1-03 or S1-04, or any todo, and does not change acceptance criteria.
- It does not authorize laps, speeds above 0.3 m/s, reverse, or the B stack.
- Each of M3, M4 and M5 is run only after its own go-ahead.

## 6. Requested reply

Please confirm or change:
- **D4** (A or B);
- **D5**: controller form, gains, u_max and the stale/overspeed rules;
- **D6**: A's design and its limits;
- **D7**;
- **D8**: which stages to run now (for example, "M3 only").
