# S1-03 stage M3 — open-loop throttle identification

Date: **2026-10-05**. Run: `20261005T123651Z-m3`. [Chinese report](S1-M3-identification.zh-CN.md). Proposal: [s1-03-controller-proposal.md v0.1](../planning/s1-03-controller-proposal.md), D8. Approval: "approve D4 A, D5, D6, D7; run M3 only" ([record](../planning/s1-motion-approval.json)).

> **Correction (2026-10-05, from [M3b](S1-M3b-identification.md)):** the steady-state gain below (4.89–4.91) was biased low by an analysis window that included the first post-hold (already braking) frame. Re-analysed, M3 gives **5.02 / 5.03 / 5.02 m/s per unit throttle** (steady speeds 0.0251 / 0.0503 / 0.1005 m/s). All other results stand. The original analysis is retained in the evidence.

**M3 passes, and it changes the plant model.** Held throttle does not keep accelerating the car. Within one telemetry frame (≤ 0.23 s), speed settles at a steady value proportional to throttle:

**v ≈ 4.90 m/s × throttle**, linear to within 0.5 % over 0.005–0.02 (0.025–0.10 m/s).

Zero throttle stops the car within about one frame, at a braking distance of about 0.19 s × speed. The approved D5 numbers were derived from a pure-accelerator model, and **u_max = 0.03 would cap speed at about 0.15 m/s**. A revised D5 (proposal v0.2) and a short M3b (linearity up to 0.3 m/s) are proposed for confirmation. M4 and M5 are not authorized.

## 1. Setup

- **Stage `m3`.** Throttle {0, 0.005, 0.01, 0.02}, steering exactly 0. It opens only with the approval record and the SIM1-03 (D1) build record.
- **Holds.** The calibration source sends each hold every frame (frame-locked). Each hold ends at encoder speed ≥ 0.3 m/s, 2.0 s, or 0.4 m of encoder travel, then zero throttle brakes the car. The next hold starts only from rest, at least 1.5 s later.
- **Speed measurement.** The mean of both wheel-encoder angles × 0.059 m, over encoder acquisition simulation time. M1 confirmed the encoder `JointState` position is wheel rotation in rad.
- **Safety rules.** All §3 rules applied: pre-check, abort monitor, 18 s armed limit, 2 m bridge containment.

## 2. Results (trial 4)

| Throttle | Applied | End reason | Steady speed | Gain (m/s per unit) | Settled within | Brake time / distance | Stop after last request's generation | Travel after it |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.005 | 2.07 s | 2 s | 0.0245 m/s | 4.89 | 0.22 s | 0.22 s / 4.7 mm | 0.55 s | 10 mm |
| 0.01 | 2.05 s | 2 s | 0.049 m/s | 4.90 | 0.23 s | 0.23 s / 9.3 mm | 0.56 s | 19 mm |
| 0.02 | 2.05 s | 2 s | 0.098 m/s | 4.91 | 0.22 s | 0.22 s / 18.6 mm | 0.55 s | 42 mm |

The speed curves are flat from the first frame after throttle starts until throttle ends. The first frame is already at 99–100 % of steady speed, so the settling time is bounded by the frame period, not resolved below it.

- **Torque:** exactly 85.6 × throttle / 4 per wheel during every hold. Afterwards all motor torque was 0 with brakes at 85.6 N·m until the next hold (D1).
- **Path:** lateral deviation ≤ 1 mm and 0.0° yaw change, moving forward. Encoder travel (51.6 / 102.7 / 205.4 mm) agrees with IPS travel (51 / 103 / 205 mm) to within 0.6 mm.
- **Command path and processes:**
  - 78 requests, all forwarded;
  - guard checks passed: armed, no rejection, no fault, exactly one final `lease-expired` with zero output, disarmed;
  - 45,188 traced steps;
  - the trial ended by itself in 54 s, all children exited 0, the port was released, and all 604 player files were unchanged.
- **Reading M1 again:** M1's "peak speed ≈ 4.7 m/s per unit throttle for a 0.2 s pulse" was simply this steady-state gain, reached within the pulse. Its derived "acceleration" figure was an artefact of frame quantization.

## 3. Attempts (all retained)

| Attempt | Outcome | Cause |
| --- | --- | --- |
| 1–3 | No connection, no motion | The GNOME session on display :1 was **locked**. The lock screen swallowed the synthetic Connect clicks, while the window-level capture still showed the player normally. Attempt 3 retried the click twice (the new bounded retry). All children exited 0; no command reached the vehicle. The user unlocked the session. |
| 4 | **Pass** | Unassisted, 54 s, first click. |

These count conservatively as 4 of the 6 allowed trials.

**Analysis correction (retained).** The first analysis let each hold's 2.5 s post-hold window overlap the next hold, which starts about 1.5 s later. That broke the stop, brake and peak checks for holds 0 and 1 (`m3-trial4-analysis-v1-flagged.json`). Windows now end at the next hold. Braking is measured from the last frame before the throttle ended. The meaningless "initial acceleration" metric was replaced by the steady-state gain and a settling bound.

## 4. Consequences and next step

- **D5 must be re-derived.** The plant is a static gain with a short lag (K ≈ 4.9 m/s per unit throttle, settling ≤ one frame), plus about 0.13 s from request generation to application and 0.2 s frame quantization. The [proposal v0.2](../planning/s1-03-controller-proposal.md) revises D5:
  - feedforward u = v*/K plus a small, bounded integral trim;
  - u_max = 0.07 (about 0.34 m/s);
  - a rise limit of 0.02 per frame;
  - unchanged stale-feedback and overspeed rules.

  It also proposes **M3b**: holds at 0.03, 0.045 and 0.06 to confirm linearity up to about 0.3 m/s before M4.
- **Unattended runs:** keep the desktop unlocked. `idle-delay` is now 0, but `lock-enabled` is still true, so a manual or suspend lock would block runs again. Since the window-level capture cannot see a lock screen, a root-screen lock check before Connect is a cheap future addition.

Evidence: `artifacts/s1/20261005T123651Z-m3/` (114-file `evidence-sha256.txt`; attempts 1–3 retained, plus `display-root-locked.png` and `display-root-unlocked.png`). Tests: 93 script tests and 26 plugin tests pass.
