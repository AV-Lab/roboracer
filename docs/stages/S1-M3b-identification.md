# S1-03 stage M3b — throttle identification up to 0.3 m/s

Date: **2026-10-05**. Run: `20261005T133323Z-m3b`. [Chinese report](S1-M3b-identification.zh-CN.md). Proposal: [s1-03-controller-proposal.md v0.2](../planning/s1-03-controller-proposal.md), D8. Approval: "comfirm", the reply to "confirm or change revised D5 and whether to run M3b" ([record](../planning/s1-motion-approval.json)).

**M3b passes on the first trial.** The throttle-to-speed relation stays linear up to the M4 range, and it corrects M3's number. Speed settles within one frame at

**v ≈ 5.02 m/s × throttle, from 0.025 to 0.30 m/s (throttle 0.005–0.06).**

M3 reported 4.90 because of an analysis window bug (below). The corrected M3 data gives 5.02–5.03, consistent with M3b. M4 and M5 are not authorized.

## 1. Setup

The setup is the same as M3, with these differences:
- stage `m3b` allows throttle {0, 0.03, 0.045, 0.06} only, with steering exactly 0;
- each hold ends at **0.35 m** of encoder travel instead of 0.4 m. At about 0.3 m/s one frame covers about 6 cm and braking about 6 cm, so this keeps each hold under the 0.5 m cap. It is a change that only reduces motion.

All §3 rules applied: pre-check, abort monitor, 18 s armed limit, 2 m bridge containment. The desktop's automatic locking had been disabled at the user's request.

## 2. Results (trial 1)

| Throttle | Applied | End reason | Steady speed | Gain (m/s per unit) | Settled within | Brake time / distance | Stop after last request's generation | Travel after it |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.03 | 2.02 s | 2 s | 0.150 m/s | 5.02 | 0.22 s | 0.22 s / 28 mm | 0.55 s | 58 mm |
| 0.045 | 1.92 s | 0.35 m travel | 0.225 m/s | 5.01 | 0.23 s | 0.22 s / 42 mm | 0.56 s | 91 mm |
| 0.06 | 0.63 s | 0.3 m/s speed | 0.295 m/s (1 settled frame) | 4.92 | 0.23 s | 0.22 s / 56 mm | 0.56 s | 121 mm |

- **Pass criteria (proposal v0.2):** all M3 criteria hold, and K is within ±10 % of 4.90 at every level (+2.4 %, +2.2 %, +0.4 %).
- **Braking:** distance ≈ 0.19 s × speed, the same as M3, and the car stops within one frame.
- **Torque:** exactly 85.6 × throttle / 4 per wheel during each hold, then motor torque 0 with brakes applied (D1).
- **Path:** lateral 0 mm and yaw 0.0°. Encoder travel (302.7 / 431.5 / 187.5 mm) matches IPS (302 / 430 / 186 mm) to within 1.5 mm. Peak hold travel was 0.43 m, under the 0.5 m cap. Peak speed was 0.302 m/s, under the 0.5 m/s cap.
- **Command path and processes:**
  - 70 requests, all forwarded;
  - guard checks passed: armed, no rejection, no fault, exactly one final `lease-expired` with zero output, disarmed;
  - 46,820 traced steps;
  - the trial ended by itself in 55 s on the first click, all children exited 0, the port was released, and all 604 player files were unchanged.

## 3. Analysis correction (retained), which also corrects M3

The first M3b analysis flagged "no plateau" (`m3b-trial1-analysis-v1-flagged.json`). Its "during hold" frames included the first frame acquired *after* the throttle ended, which already shows braking (for example 0.152 → 0.139 m/s). The plateau test and the steady-speed average both used it.

The fix:
- count only frames acquired while throttle was applied;
- take steady speed as the mean after the first (settling) frame;
- call it a plateau when those frames agree within 5 %.

Re-running the **M3** trial with the fixed analysis (`m3-trial4-reanalysis-v3.json`) gives gains of **5.02 / 5.03 / 5.02**, not 4.89–4.91. M3's steady speeds were 0.0251 / 0.0503 / 0.1005 m/s. Every other M3 result is unchanged. The [M3 report](S1-M3-identification.md) now carries this correction.

## 4. Consequences

- **D5 uses K = 5.02.** This is the measured value, +2.4 % from the 4.90 in v0.2, within the confirmed ±10 % retuning rule.
  - The integral-loop crossover becomes K·Ki ≈ 0.50 rad/s, with a phase margin of about 77° (unchanged).
  - u_max = 0.07 now corresponds to about 0.35 m/s, which still covers v* = 0.3 m/s.
- **Linearity:** the map is linear over the whole S1-03 range (0.025–0.30 m/s), so no lookup table is needed.
- **Next:** M4 (closed-loop speed) and M5 (A on the segment) await your go-ahead, per proposal v0.2. D5 is now fully parameterized by measurement.

Evidence: `artifacts/s1/20261005T133323Z-m3b/` (40-file `evidence-sha256.txt`). Trials: 1 of 6. Tests: 93 script tests and 26 plugin tests pass.
