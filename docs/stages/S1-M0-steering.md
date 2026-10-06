# S1 motion stage M0 — steering only, wheels braked

Date: **2026-10-05**. Run: `20261005T113714Z-m0`. Protocol: [s1-motion-protocol.md v0.1](../planning/s1-motion-protocol.md). Approval: "approve D1 A, D2, D3; run M0 only" ([record](../planning/s1-motion-approval.json)).

**M0 passes.** The first commands that could actuate anything were sent: steering only, with throttle exactly 0 and the brakes on. They went through the full chain (calibration source → supervisor → guard), on a motion-authorized player.

- **Sign:** positive normalized steering turns **left** and negative turns **right**. This is confirmed by the wheel angle signs and, independently, by Ackermann geometry: the inner front wheel steers more.
- **Angles:** they match the vendor geometry to within 0.0001° at every command.
- **Slew:** the slew rate is the serialized 183°/s.
- **Expiry:** when requests stopped, the guard's lease expired and the steering went straight back to 0.
- **Translation:** the car did not translate (1 mm, the IPS resolution).

M1 and M2 are **not** authorized and were not run.

## 1. Decisions applied

| Decision | What was done |
| --- | --- |
| **D1 A** | [`vendor-sim1-03.patch`](../../integration/autodrive/sim1/vendor-sim1-03.patch) adds two lines: the zero-throttle branch now also zeroes the front motor torques. The SIM1-03 player was built from a fresh verified derived copy (01→02→03, 273 s, exit 0). Strict serialized comparison against the SIM1 reference: geometry and asset mapping are equal, so only code changed. This is a recorded deviation from the reference. |
| **D2** | A scripted calibration source (`autodrive_neutral.py calibrate`) observes through the plugin's `AutoDriveBridge` and sends `calibration` requests. Supervisor stage `m0` accepts only throttle 0 and steering in {0, ±0.1, ±0.5, ±1.0}. It opens only with the committed approval record, whose hash is in the supervisor status. AVLite target-speed motion stays closed in code. |
| **D3** | The Devkit bridge publishes provenance before its paced reply (122 of 122 frames), and the reply pacing is now 50 ms. Observation age at the supervisor dropped from p50/p95/max 326/443/489 ms to **206/304/318 ms**. |

**Runner gates for motion.** `-roboracerMotionAuthorized` is passed only when all of these hold:
- `--motion-stage` names a stage listed in the approval record;
- the player's own build record includes vendor-sim1-03;
- `GameAssembly.so` matches its recorded hash.

Every outbound guard request is checked against the stage profile before sending. The bridge accepts steering feedback only up to 30° (allowing for 3-decimal rounding), and throttle feedback must remain exactly 0.

## 2. Results (attempt 3; attempt 2 identical)

| Command | Turns | Inner wheel | Final FL / FR (°) | Max error vs vendor geometry | Slew (°/s, sim time) |
| --- | --- | --- | --- | --- | --- |
| +0.1 | left | left | −3.058 / −2.944 | < 0.0001° | 184.6 |
| −0.1 | right | right | +2.944 / +3.058 | < 0.0001° | 184.6 |
| +0.5 | left | left | −16.537 / −13.719 | < 0.0001° | 184.6 |
| −0.5 | right | right | +13.719 / +16.537 | < 0.0001° | 184.6 |
| +1.0 | left | left | −36.170 / −25.503 | 0.00001° | 183.2 |
| −1.0 | right | right | +25.503 / +36.170 | 0.00001° | 183.2 |
| +0.5 (expiry hold) | left | left | −16.537 / −13.719 | < 0.0001° | 184.6 |

- **Geometry:** Ackermann split of 30° × command, with the serialized wheelbase 324 and track 236. A 0.5° tolerance was allowed; the observed error is effectively zero.
- **Slew criterion:** 183 ± 10°/s, measured in simulation time (fixed steps × 1 ms).
- **Return to 0:** instantaneous, within one fixed step, after every step. The vendor `Steer()` code snaps to 0 when moving toward zero; only outward moves are slew-limited. This is recorded as vendor behaviour.
- **Expiry case:** +0.5 was held and the source then stopped sending. The guard logged `state stopped lease-expired 169` while +0.5 was applied, and both wheels were at 0 within **0.09 ms** of that step.
- **Translation and torque:** IPS displacement over the M0 window (16.8 s) was 1.0 mm, the reporting resolution. Encoders were unchanged. All 44,848 traced steps had motor torque and throttle exactly 0, with the brakes applied.
- **Command path:** 169 calibration requests, all forwarded by the supervisor. The guard driver checks passed: armed, no rejection, no fault, exactly one final lease expiry, disarmed.
- **Steering feedback:** ±0.524 rad at full lock (30°, rounded to 3 decimals).
- **Process and player:** the trial ended by itself in 54 s. All 5 children exited 0, and the port was released. All 604 player files were unchanged before and after.

## 3. Attempts (all retained)

| Attempt | Outcome | Cause and handling |
| --- | --- | --- |
| 0 | Not launched | My wrapper's `set -u` broke `source /opt/ros/humble/setup.bash`; no process started. |
| 1 | Failed closed at +1.0 | My runner's steering-feedback bound was exactly 30° (0.5235988 rad), but telemetry reports full lock rounded to `0.524`. The bridge child rejected the frame and stopped replying. The calibration source aborted to zero ("no new observation for 0.61 s"); no translation, zero torque. The completed segments (±0.1, ±0.5, +1.0) already showed the correct sign and angles. Fix: allow 3-decimal rounding (0.5245 rad). |
| 2 | Criteria met; tooling defect | The runner's completion check knew only `observe`, so the trial idled until I stopped it with SIGTERM (clean cleanup). The analysis first flagged 5.0 mm whole-run displacement. That was passive creep during the 150 s idle tail (first reached 145 s after the profile ended). Inside the M0 window it was 1.0 mm. Fixes: calibration trials now end when the driver completes, and translation is measured over the stage window, with the whole run reported separately. |
| 3 | **Pass** | Unassisted, 54 s. Matches attempt 2 on every number above. |

These are 3 motion trials of the 6 allowed. Another analysis artefact found and fixed: slew measured on wall-clock stamps is wrong, because Unity runs several 1 ms physics steps back to back per rendered frame. The calibration-mode simulation also found a guard-driver defect: once the request source went silent, the driver re-forwarded older skipped requests. It now never forwards a request older than one already forwarded.

## 4. Status

- **M0: passed.** S1-02's command steering sign and units are now verified against observed simulator response (normalized ±1 = 30°, positive = left). **Throttle sign and units remain open (M1).**
- **Not authorized and not run:** M1 (throttle pulses), M2 (expiry and runner-loss stops under motion), and any AVLite target-speed motion.
- **Next:** your decision on M1. The protocol's M1 numbers are unchanged: throttle 0.002–0.01, 0.25 s pulses, caps 0.5 m/s and 0.5 m.

Evidence: `artifacts/s1/20261005T113714Z-m0/` (92-file `evidence-sha256.txt`; attempts 1 and 2 retained). Build: `artifacts/simulator-build/20261005T-sim1-03/`. Tests: 89 script tests and 26 plugin tests pass.
