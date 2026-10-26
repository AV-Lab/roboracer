# S3-06 proposal — ICP thresholds and the M3 acceptance matrix

Version **0.1 — confirmed 2026-10-26** ("confirm": D48–D52; [record](s1-motion-approval.json)). Each run session still needs its own run approval. Basis:
- the S3-05 baseline (10/10 valid, [S3 §15](../stages/S3.md));
- the first ICP laps and F1-1 (§12);
- the offline ICP qualification and the initialization faults (§9);
- the truth-isolation proof (§13).

Plan rule: thresholds are proposed from the baseline and approved **before** the acceptance set is frozen; no retrospective adjustment.

**Nothing here authorizes motion.** Decisions D48–D52 are requested in §6.

## 1. Baseline numbers the thresholds come from

The ICP error is **time-matched**: the ICP pose of each matched scan against the IPS pose of the snapshot it came from. The earlier per-tick figure mixed in up to one frame of travel; its 0.08 m single-tick maxima were that, with corrections of 0.1–0.7 mm. The matched error still contains the scan/pose acquisition skew (~0.04 s, ~2 cm at 0.5 m/s).

| Measure | A (5 episodes) | B (5 episodes) | Other evidence |
| --- | --- | --- | --- |
| Valid ICP scans during the lap | 100 % | 100 % | ICP laps ×3: 100 % |
| Localization losses | 0 | 0 | 0 |
| Position error, matched, p95 / max | 0.009–0.011 / ≤ 0.026 m | 0.021–0.025 / ≤ 0.038 m | offline (5 laps): p95 ≤ 0.009, max ≤ 0.015 m |
| Yaw error, matched, p95 / max | ≤ 0.0094 / ≤ 0.018 rad | ≤ 0.0143 / ≤ 0.028 rad | |
| Inlier fraction, minimum | 1.00 | 1.00 | |
| Largest per-scan correction | ≤ 0.0154 m | ≤ 0.0109 m | limit 0.05 m |
| ICP compute p95 / max | ≤ 3.3 / ≤ 13.0 ms | ≤ 4.8 / ≤ 12.6 ms | scan period ~180 ms |
| Lap from the IC | 117.2–120.7 s | 62.84–63.00 s | |
| Minimum clearance | 0.104–0.105 m | 0.314–0.317 m | |
| IC deviation | 0.021–0.056 m | 0.020–0.091 m | tolerance 0.10 m |

## 2. Proposed thresholds (D48), checked per episode

| # | Threshold | Proposed | Margin over the baseline |
| --- | --- | --- | --- |
| T1 | ICP validity during the lap | ≥ 99 % of matched scans valid; **no loss** in a healthy episode | baseline 100 % |
| T2 | Position error (matched) | p95 ≤ **0.05 m**, max ≤ **0.10 m** | 2× / 2.6× B's worst |
| T3 | Yaw error (matched) | p95 ≤ **0.03 rad**, max ≤ **0.06 rad** | 2.1× / 2.1× |
| T4 | ICP runtime | p95 ≤ **10 ms**, max ≤ **50 ms** per scan | 2× / 3.8× |
| T5 | Completion and safety (A and B) | one valid lap from the IC; no contact or off-track in approach or lap; no abort | baseline 10/10 |
| T6 | B clearance | ≥ **0.20 m** | B 0.314 m |
| T7 | B lap from the IC | ≤ **66.0 s** | B 63.0 s + 3 s |
| T8 | IC reached | ±0.10 m, ±5° (D44, unchanged) | see D49 |

**A is the comparator** (development plan: "B must meet its approved performance criteria; A provides the retained comparator results"). A's T1–T5 results are recorded and reported, and **only B gates acceptance**. A failure of A is retained and reported, not hidden.

Residuals and inlier fractions are match diagnostics, **not a calibrated covariance** (S3-02).

## 3. Approach change before acceptance (D49)

IC1 B stopped 0.091 m past its IC (tolerance 0.10 m): the speed loop had not reached the 0.1 m/s creep yet. Over 100 episodes that could fail by chance.

Proposed:
- approach slowdown √(2 a d) with a = **0.25 m/s²** (was 0.5);
- creep zone **0.5 m** at 0.1 m/s (was 0.2 m);
- stop requested 0.03 m early (unchanged).

This adds about 3 s per approach. The tolerance stays ±0.10 m. Checked in the stage unit test, then on the first acceptance episodes.

## 4. Robustness cases (D50): F3, each three times

| Case | Injection | Expected outcome | Motion |
| --- | --- | --- | --- |
| F3-1 scan loss | LiDAR freeze mid-straight while B drives on ICP (as F1-1 on `s3v1i`) | stop by "no new observation" or "no valid localization": rest ≤ 1.7 s, travel ≤ 0.65 m (V1 criteria) | yes |
| F3-2 incorrect initialization (heading) | configured spawn pose off by 0.3 rad | start-up check rejects; no arm, no motion | no (car interlocked) |
| F3-3 incorrect initialization (along-track) | configured spawn off by 0.5 m along the opening straight (the unobservable direction, S3 §9) | lap starts; at the first corner the localization is **lost**; the stage stops: rest ≤ 1.7 s, travel ≤ 0.65 m from the loss | yes |
| F3-4 invalid map | map file altered after commit | refused at load (hash mismatch); the stack does not start | no |
| F3-5 forbidden truth | IPS and IMU-orientation truth perturbed in a recorded run | B's outputs bit-identical (S3-04 proof) | no (offline) |

F3-3 needs one test hook: a configured-pose offset, selected on the command line and recorded. Every other case uses existing paths.

## 5. Acceptance matrix (D51, D52)

- **Episodes:** 5 ICs × 10 repetitions × A/B = **100 fresh-process episodes**, alternating A/B order within each IC, unattended. Plus F3 ×3 (9 motion runs, 6 non-motion checks).
- **Duration:** A about 3 min and B about 2 min per episode, so **about 4.5 h** of driving. Proposed as 5 sessions (one per IC, about 55 min each), each needing the desktop untouched.
- **Rule (D52, as D26 A):** any B episode failing T1–T8 fails the matrix item. It is retained, and a rerun needs approval. No "best 10 of 12", no relabelling. A's results are reported only.

## 6. Decisions requested

- **D48 — thresholds** T1–T8 as in §2 (B gates; A is the comparator).
- **D49 — approach change:** deceleration 0.25 m/s², creep zone 0.5 m; tolerance unchanged.
- **D50 — F3 cases** F3-1 to F3-5 as in §4, each three times.
- **D51 — matrix:** 100 episodes + F3, in five per-IC sessions.
- **D52 — failure rule:** strict on B (as D26 A); A reported only.

After confirmation I would build D49 and the F3-3 hook, test them without motion, and then ask for the run approval for the first session.
