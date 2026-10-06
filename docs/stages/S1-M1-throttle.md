# S1 motion stage M1 — throttle sign and minimal straight pulses

Date: **2026-10-05**. Run: `20261005T115944Z-m1`. Protocol: [s1-motion-protocol.md v0.1](../planning/s1-motion-protocol.md) §3–§4. Approval: "approve M1 as drafted" ([record](../planning/s1-motion-approval.json)).

**M1 passes.** These were the first commands that moved the vehicle: four forward throttle pulses with steering exactly 0, each from rest and followed by zero throttle (brakes).

- **Sign:** positive normalized throttle moves the car **forward along its +x** with 0 mm lateral deviation and 0° yaw change. Both encoders count **up**.
- **Torque:** applied torque is exactly 85.6 N·m × throttle / 4 per wheel (CAWD).
- **Stops:** after every pulse the D1 patch leaves all motor torque at 0 with brakes applied. The car stops 0.35–0.58 s after the request's generation (limit 1.5 s).

The response was about 20× weaker than the ideal-force estimate in the protocol. Every pulse, including the optional 0.02, stayed far under the 0.5 m/s and 0.5 m caps. **M2 is not authorized and was not run.**

## 1. How the stage ran

- **Request source.** The calibration source is event-driven on committed snapshots. Since D3, a snapshot commits before the bridge's 50 ms paced reply. The throttle request is therefore sent on frame *k*, forwarded in that frame's reply, and replaced by zero on frame *k+1*: each pulse is **one telemetry interval, 0.199–0.201 s**. The protocol drafted 0.25 s; the telemetry period after D3 is about 0.20 s, and the applied durations come from the guard's per-step trace.
- **Sequence.** 0.002 → 0.005 → 0.01 → 0.02. Each step required:
  - every earlier pulse under both caps;
  - the previous peak, scaled linearly to the next throttle, under the speed cap. This is a conservative addition that can only skip motion.

  Each pulse started from rest (IPS speed < 0.02 m/s) at least 3 s after the previous one.
- **Workspace and abort monitor (§3).** Before the pulses: spawn offset 0 mm, forward ±15° clear for 2.26 m, sides 0.74 / 0.54 m. Throughout, the source checked speed and travel caps, yaw > 10°, lateral > 0.15 m, forward clearance < 1.0 m, side clearance < 0.25 m, guard fault, and a snapshot gap > 0.6 s. The bridge child also fails closed at 2 m total displacement.
- **Command bounds.**
  - The supervisor's stage `m1` profile allows throttle {0, 0.002, 0.005, 0.01, 0.02} and steering exactly 0. It opens only with the approval record.
  - The runner checks every outbound guard request against that profile, and accepts throttle feedback only at those values (3 decimals) with steering feedback exactly 0.
  - Motion authorization requires the SIM1-03 build record (D1) and a matching `GameAssembly.so` hash.
  - Armed time is limited to 18 s, and the trial ends by going silent, so the guard's lease expires with zero output.

## 2. Results (trial 2; trial 1 identical to within 1 mm/s)

| Throttle | Applied (guard) | Torque per wheel, measured / expected (N·m) | Peak speed (m/s) | Travel | Lateral / yaw | Stop after generation | Generation → accept |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.002 | 0.199 s | 0.043 / 0.043 | 0.010 | 2 mm | 0 mm / 0.0° | 0.35 s | 0.13 s |
| 0.005 | 0.200 s | 0.107 / 0.107 | 0.020 | 4 mm | 0 mm / 0.0° | 0.35 s | 0.13 s |
| 0.01 | 0.201 s | 0.214 / 0.214 | 0.045 | 10 mm | 0 mm / 0.0° | 0.55 s | 0.13 s |
| 0.02 | 0.200 s | 0.428 / 0.428 | 0.095 | 19 mm | 0 mm / 0.0° | 0.58 s | 0.13 s |

**Response map.**
- Peak speed ≈ 4.7 m/s per unit throttle and travel ≈ 0.95 m per unit throttle, for a 0.20 s pulse. Both are roughly linear.
- The ideal-force estimate in the protocol (0.01 → about 4 m/s², or about 0.8 m/s after 0.2 s) overstated the response about 20×. The estimate ignored wheel inertia and contact losses; the measurements replace it.
- Speed is IPS-based: 1 mm resolution over about 0.2 s frames. It is a lower bound on true peak speed, and 0.002 sits at the resolution limit.

**Cross-checks.**
- **Encoders:** both moved +180 ticks, +0.589 rad. That rotation times the 0.059 m wheel-collider radius is 34.8 mm, against 35 mm of IPS travel. So the encoder angle is wheel rotation in rad, positive forward, about 1,920 ticks per revolution.
- **Release with brakes (D1):** after every pulse, all four motor torques are exactly 0 and all brakes are 85.6 N·m, over 2,000 steps checked each. The guard raised no fault.
- **Stops:** all four meet the stop qualification. Speed fell below 0.02 m/s within 0.58 s of the request's generation, and each pulse's whole travel (≤ 19 mm) was under the 0.15 m bound.
- **Command path:** 85 calibration requests, all forwarded. Observation age at the supervisor was 97 / 110 / 120 ms (p50 / p95 / max), because requests now leave at snapshot commit. Guard checks passed: armed, no rejection, no fault, exactly one final `lease-expired` with zero output, disarmed. 43,095 traced steps; steering exactly 0 on all of them.
- **Process and player:** the trial ended by itself in 52 s, and all 5 children exited 0. The port was released, and all 604 player files were unchanged. Total travel in the trial was 35 mm, against a 3 m limit.

## 3. Trials (both retained)

| Trial | Outcome | Cause and handling |
| --- | --- | --- |
| 1 | Vehicle sequence complete; trial marked failed | The M1 calibration source exited its loop when finished, and the runner treats an exiting child as a failure. The trial stopped before the guard driver's final checks. A parser defect in my analysis (accept events have 6 fields once the event number is stripped) first hid the stop timings. Re-analysed: every pulse passes, with the same numbers as trial 2. Fixes: the source idles until SIGTERM; the parser is corrected. |
| 2 | **Pass** | Unassisted, 52 s. |

These are 2 trials of the 6 allowed.

## 4. Status

- **M0 and M1 passed.** S1-02's command signs and units are now verified against observed simulator response:
  - steering ±1 = ±30°, positive = left;
  - throttle positive = forward, with torque = 21.4 N·m × throttle per wheel, and the measured short-pulse response map.

  S1-02's remaining check box covers the bridge deliverable, whose observation half passed earlier. I am leaving the box unchecked for your review rather than marking it myself.
- **Not authorized and not run:** M2 (expiry and runner-loss stops under motion) and any AVLite target-speed motion.
- **Next:** your decision on M2, as drafted (a 0.01 pulse with (a) the supervisor stopping forwarding and (b) the runner stopping heartbeats). After M0–M2, the protocol calls for the S1-03 target-speed controller proposal. The response map above is its input.

Evidence: `artifacts/s1/20261005T115944Z-m1/` (67-file `evidence-sha256.txt`). Tests: 91 script tests and 26 plugin tests pass.
