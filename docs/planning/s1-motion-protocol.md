# S1 Numerical Motion Protocol — Draft for Confirmation

Version: **0.1 — confirmed in part** on 2026-10-05: "approve D1 A, D2, D3; run M0 only" ([record](s1-motion-approval.json)). **M0 passed** ([report](../stages/S1-M0-steering.md)). M1 and M2 are not authorized. Date: 2026-10-05. [Chinese version](s1-motion-protocol.zh-CN.md). Required by [amendment 1.2](s1-first-amendment.md) before any command that can move the vehicle. Evidence: [SIM1-02 guard](../stages/SIM1-guard.md), [S1-02 observation](../stages/S1-observation.md), [S1 supervisor](../stages/S1-supervisor.md).

**Until you confirm this document (or a changed version), nothing here is executed.** The guard's zero-output interlock stays on, `-roboracerMotionAuthorized` is not passed, and the supervisor's motion gate stays closed in code.

## 1. Facts this protocol is built on

| Quantity | Value | Source |
| --- | --- | --- |
| Drivetrain | CAWD (all-wheel drive, common actuator), `MotorTorque` 85.6 N·m → 21.4 N·m per wheel × throttle | serialized scene; SIM0 pose review |
| Zero throttle | 85.6 N·m brake on every wheel | `VehicleController.Drive()`; guard trace |
| Vehicle | 3.47 kg; wheel collider radius 0.059 m; wheelbase 0.331 m (scene axles) | SIM0 reviews; S1-02 |
| Throttle authority | Ideal force ≈ 1,450 N × throttle, so **throttle 0.01 ≈ 4 m/s²** before the traction limit. Even 0.01 is a strong command. | derived |
| Steering | ±1 normalized = ±30° commanded. +1 is **expected** to be left (`SteeringAngle = −AutonomousSteering·30°`; Unity's positive `steerAngle` is right), **not yet verified**. Slew 183.3°/s, so a full 30° takes 0.16 s. Ackermann split per wheel. | source; serialized `SteeringRate` |
| Telemetry | 3.87 Hz (period p50 258 ms, max 286 ms); scan 20 Hz | SIM1-02, S1 |
| Observation age at supervisor | p50 / p95 / max: 326 / 443 / 489 ms | S1 supervisor run |
| Guard | lease ≤ 1 s; clock bound ~40–60 ms; lease left at accept: min 311 ms with a 500 ms request life | SIM1-02, S1 |
| Spawn pose | IPS (0.741, 3.158), heading −90°. Corridor clearance from the LiDAR: left 0.74 m, right 0.54 m, ±5° ahead 7.36 m, ±15° ahead 2.26 m (the track curves). | recorded scan |
| Passive creep | ~3–4 mm/min at rest | SIM0 |

## 2. Decisions needed before any stage

**D1 — front-motor-torque clearing (pre-motion blocker).** With CAWD, the zero-throttle branch clears only the *rear* motor torques. After any nonzero command, the front wheels keep their last motor torque while braking. The guard's read-back then faults on the first nonzero→zero transition, so every stop would end in `fault`, and the front torque keeps acting against the brake.
- **(Recommended) A:** a one-line vendor patch (`vendor-sim1-03.patch`, about +2 lines) that also zeroes the front motor torques in that branch. This is a minimal, explicit simulator change: it alters only the transition behaviour, and is recorded as a deviation from the reference.
- **B:** no patch; the guard tolerates front torque while braking. This is not recommended, because it hides a real actuation mismatch.

**D2 — calibration commands.** The approved algorithm command is *target speed*, and there is no speed controller yet. Measuring the response needs open-loop normalized throttle and steering.
- **(Recommended)** Add a separate `calibration` request source: a scripted process with its own origin. It goes through the **same supervisor and guard**, each stage profile bounds its values in code, and AVLite stays on `HoldController`. The target-speed controller (S1-03) is designed afterwards from the measured response.

**D3 — observation freshness.** Keep the 500 ms observation-age limit and remove the avoidable latency: publish the provenance message **before** the paced reply, and cut the reply pacing from 100 ms to 50 ms. This is a tooling change only; the simulator is unchanged. The expected maximum age is then about 390 ms. If this is not done, the limit would have to rise to 600 ms.

## 3. Common rules for every motion stage

- **Authorization:** the guarded player is started with `-roboracerMotionAuthorized` **only** for a confirmed stage. The supervisor's stage profile is selected explicitly. Each stage gets its own fresh-process trials and a visual pre-Connect review, as now.
- **Request life:** 500 ms from generation (guard maximum 1 s). Runner lease: 500 ms. Observation-age limit: 500 ms (per D3).
- **Workspace:** start only from the spawn pose, after a zero-command settle of at least 3 s. Abort before any command when:
  - the LiDAR minimum in ±15° ahead (for forward stages) is under **1.5 m**;
  - either side minimum (±80–100°) is under **0.4 m**;
  - the IPS differs from spawn by more than 20 mm.
- **Abort monitor:** the runner reads each committed snapshot and aborts on any of:
  - speed from IPS differences above the stage cap;
  - displacement from the stage start above the cap;
  - |yaw change| > 10°;
  - lateral deviation > 0.15 m;
  - forward clearance < 1.0 m;
  - side clearance < 0.25 m;
  - any guard `fault`;
  - a missing snapshot for more than 600 ms.

  **Abort action:** stop forwarding, then a disarm request, then let the lease expire (≤ 500 ms). Killing the player is containment only, never evidence of braking.
- **Stop qualification (for every pulse):** after the last nonzero request is generated, IPS speed must fall below **0.02 m/s within 1.5 s**, and travel after that request must stay under **0.15 m**.
- **Bounds per stage:** at most 6 trials, each at most 20 s of armed time, and cumulative travel at most 3 m per trial. Every trial starts in a fresh process. Failures are retained, and no stage is repeated without review.

## 4. Stages (each run only after confirmation; results reviewed before the next)

**M0 — steering only, wheels braked (no translation intended).**
- Throttle exactly 0. Steering normalized +0.1, −0.1, +0.5, −0.5, +1.0, −1.0, each held 1.0 s, with 1.0 s at 0 between.
- **Pass:**
  - wheel steer read-back sign: + is left, as the guard reads both front collider angles;
  - magnitude within 0.5° of the Ackermann value for 30° × command;
  - slew 183 ± 10°/s;
  - return to 0 after each step;
  - IPS displacement ≤ 5 mm.
- Also one **expiry case:** hold +0.5, then stop forwarding. The steering must return to 0 within the remaining lease plus 0.2 s.

**M1 — throttle sign and minimal straight pulses (forward only).**
- Steering 0. Pulses of throttle 0.002, 0.005, 0.01 (0.02 only if 0.01 stays under the caps), each held **0.25 s**, then zero (brake). Each pulse starts from rest.
- **Caps:** speed 0.5 m/s, travel 0.5 m per pulse.
- **Pass:**
  - travel along vehicle +x (sign), and encoders change with the expected sign;
  - stop qualification met;
  - no guard fault, with D1 applied;
  - peak speed and travel recorded against throttle and duration (the response map that S1-03 needs).

**M2 — expiry and runner-loss stops under motion.**
- A 0.01 throttle pulse during which (a) the supervisor stops forwarding, which simulates an algorithm hang, and separately (b) the runner stops heartbeating.
- **Pass:** guard lease expiry or supervisor inhibition stops the vehicle, meeting the stop qualification measured from the last forwarded request's generation.
- These are the F1/S1-04 cases under motion.

**After M0–M2:** propose the S1-03 target-speed controller (gains, slew limits, speed cap) from the M1 response map, for separate confirmation. The plugin's `max_target_speed_mps` stays 0 until then.

## 5. What confirming this does not do

- It does not accept S1, M1 or any todo; it does not change acceptance criteria.
- It does not authorize reverse motion, laps, steering while moving, or any speed controller.
- It does not move to S2.

## 6. Requested reply

Please confirm or change **D1 (A/B), D2, D3**, the **numbers in §3–§4**, and which stages are authorized (for example, "M0 only", or "M0–M2 in order with review between").
