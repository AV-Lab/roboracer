# S1 motion stage M2 — stops under motion: algorithm hang and runner loss

Date: **2026-10-05**. Run: `20261005T122018Z-m2`. Protocol: [s1-motion-protocol.md v0.1](../planning/s1-motion-protocol.md) §3–§4. Approval: "yes run M2" ([record](../planning/s1-motion-approval.json)).

**M2 passes in both cases.** The vehicle was driven at throttle 0.01 with steering 0. In each case it was then stopped by the independent mechanisms alone; no zero command was ever sent to stop it:

- **(a) Algorithm hang.** The request source sent one 0.01 request and went silent. The guard's lease expired 500 ms after that request's generation, with the throttle still applied. From that step on, all motor torque was 0 with brakes applied, and the car stopped **0.78 s** after the request's generation.
- **(b) Runner loss.** The runner stopped heartbeating while the source kept requesting 0.01 every frame. The supervisor inhibited itself exactly at its 500 ms runner lease and refused every later request (12 of 12 `inhibited`). The guard's lease then expired with throttle still applied, and the car stopped **0.76 s** after the last forwarded request's generation.

These are the F1/S1-04 "stale request" and "runner exit/hang" cases, now shown **under motion**.

## 1. Setup

- **Stage `m2`:** throttle {0, 0.01}, steering exactly 0. It opens only with the approval record and the SIM1-03 (D1) build record.
- **Per case:** one fresh-process trial per case (each ends in a sticky guard stop) with a visual pre-Connect review. The common §3 rules applied: spawn and clearance pre-check (forward 2.26 m, sides 0.74 / 0.54 m, at rest), the abort monitor, an 18 s armed limit, and 2 m bridge containment.
- **Case (a):** after a 3 s settle, the calibration source sends a single 0.01 request locked to a telemetry frame, then nothing.
- **Case (b):** the source writes a pause request, which the runner's main loop picks up; from then it sends no heartbeats. The source requests 0.01 on every frame for 3 s, then stops. The supervisor's 500 ms runner lease must cut it off.
- **Stopping:** in both cases the source never sends zero to stop the vehicle. On an abort it could only fall silent; no abort occurred.

## 2. Results

| | Case (a) hang | Case (b) runner loss |
| --- | --- | --- |
| Throttle applied (guard) | 0.368 s | 0.768 s |
| Torque per wheel | 0.214 N·m (= 85.6 × 0.01 / 4) | 0.214 N·m |
| What ended it | `state stopped lease-expired 22`, the step after the last 0.01 step | `state stopped lease-expired 24`, the step after the last 0.01 step |
| After the stop | motor torque 0 and brakes 85.6 N·m on all wheels (2,000 steps checked) | same |
| Generation → guard accept | 0.131 s | 0.130 s |
| Peak speed / travel | 0.051 m/s / 18 mm | 0.051 m/s / 38 mm |
| Lateral / yaw change | 1 mm / 0.0° | 1 mm / 0.0° |
| **Stop after the last forwarded generation** (limit 1.5 s) | **0.78 s** | **0.76 s** |
| **Travel after it** (limit 0.15 m) | **18 mm** | **28 mm** |
| Requests | 1 nonzero, none forwarded afterwards | 15 nonzero: 3 forwarded, then 12 rejected `inhibited`, 0 forwarded after inhibition |
| Guard driver checks | armed, no rejection, no fault, one final lease expiry, disarmed | same |

**Supervisor timing in case (b).**
- The runner's heartbeat cadence was 117 ms on average (38 heartbeats).
- The supervisor inhibited 0.405 s after the runner *noticed* the pause request. That puts the last heartbeat it received 95 ms before the notice, within one heartbeat interval. So the lease fired exactly 500 ms after the last heartbeat.
- **Analysis correction (retained):** my first check measured from the pause notice and required 0.5–0.7 s, which flagged this correct behaviour (`m2-b-analysis-v1-flagged.json`). The corrected check requires inhibition at most 0.5 s + 20 ms tick after the notice, and no earlier than 0.5 s − 1.5 heartbeat intervals.

**Why case (b) applied throttle longer.** The supervisor forwards until its lease expires (up to 0.5 s after the last heartbeat), and the guard then honours the last forwarded request until its own lease ends (0.5 s after generation). The worst-case application after a runner loss is therefore about one heartbeat interval + 0.5 s + 0.5 s. Here it was 0.77 s, and the stop still met the protocol bound with a large margin.

**Process and player:** both trials ended by themselves (49 s and 48 s), and all children exited 0. The port was released, and all 604 player files were unchanged.

## 3. Status

- **M0, M1 and M2 all passed.** Motion protocol v0.1 is complete.
- **Shown under motion:**
  - steering and throttle signs and units;
  - D1 release with brakes;
  - guard lease expiry with throttle applied;
  - supervisor runner-lease inhibition.

  These provide the F1/S1-04 cases "stale request" (hang → expiry) and "runner exit/hang" (runner loss → inhibition) under motion. S1-04 also lists missing/invalid observations, non-finite requests and algorithm exit; those were shown without motion and are not re-run here.
- **Not authorized:** AVLite target-speed motion, reverse, laps, and steering while moving.
- **Next (protocol §4 "After M0–M2"):** draft the S1-03 target-speed controller from the M1 response map: about 4.7 m/s peak and 0.95 m travel per unit throttle per 0.2 s pulse; telemetry about 5 Hz; stop within 0.8 s. Stop for your confirmation. The plugin's `max_target_speed_mps` stays 0 until then. I am not checking S1-02 or S1-04 boxes myself; they await your review.

Evidence: `artifacts/s1/20261005T122018Z-m2/` (68-file `evidence-sha256.txt`). Tests: 92 script tests and 26 plugin tests pass.
