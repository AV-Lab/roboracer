# S1-06 — M1 results: circuits, timing windows and the full F1 matrix

Dates: **2026-10-06 – 2026-10-07**. Protocol: [s1-06-m1-protocol.md](../planning/s1-06-m1-protocol.md), **v0.2** (D17 A, §8). Approvals: "approve D12, D13, D14, D15, D16; run M1"; "resume D17" → **A** ([record](../planning/s1-motion-approval.json)). Earlier progress: [M1 progress](S1-06-M1-progress.md), [first measurements](S1-06-measurements.md).

**M1 is complete:**
- three bounded circuits (D12);
- five timing windows (D13);
- **all 27 F1 trials pass under v0.2** (nine cases, three each).

The one v0.1 failure (F1-1, 2026-10-06) is kept as recorded. Two anomalies are open, neither affecting what the cases test (§4).

## 1. Circuits and timing (summary)

| Item | Result | Evidence |
| --- | --- | --- |
| D12, three circuit runs | The three M6 laps: 1 lap each, 0 contact / 0 off-track, clearance ≥ 0.104 m | `artifacts/s1/20261006T054031Z-m6/` |
| D13, five timing windows | All complete (10 s + 120 s) and within every frozen limit. Observation age max 346 ms (limit 500); command → observed p95 ≤ 235 ms; 0 tick overruns; GPU p50 22–25 %. | `artifacts/s1/20261006T061501Z-m1-timing/` |

## 2. F1 matrix under v0.2 (`artifacts/s1/20261007T051931Z-m1-f1-v02/`)

**How each trial ran:**
- a fresh player with a visual pre-Connect review;
- A-lap in the M6 envelope;
- the fault injected at 6.0 s of run time, on the opening straight;
- the case ending 8 s later;
- the AutoDRIVE window recorded.

All runs used committed code (`0b44b50` to `83aa1a9`; the commits between them are a runner path fix and a cleanup-grace change, §4). The analysis is `scripts/roboracer_f1.py --criteria v0.2`.

| Case | Pass | Onset after injection | Stop after onset (≤ 1.5 s) | Travel after injection (≤ 0.40 m) | Expected detection seen |
| --- | --- | --- | --- | --- | --- |
| F1-1 missing scan (LiDAR freeze) | **3/3** | 0.45–0.49 s | 0.62–1.05 s | 0.25–0.33 m | `scan/pose skew` rejections; stack abort ≤ 0.7 s after the last good snapshot; supervisor `stale-observation` |
| F1-2 invalid scan (NaN) | **3/3** | 0.13–0.16 s | 0.86–1.09 s | 0.22–0.24 m | scan-validation rejections; stack abort; `stale-observation` |
| F1-3 stale request (stack hang) | **3/3** | 0 | 0.68–0.80 s | 0.13 m | no request after the hang; guard lease expiry ≤ 0.5 s after the last generation |
| F1-4 non-finite request | **3/3** | 0 | 0.60–0.70 s | 0.11–0.13 m | plugin refused NaN (e.g. 80 refusals); supervisor `non-finite` on the direct NaN; nothing non-finite reached the guard |
| F1-5 disarm / re-arm | **3/3** | 0.04–0.12 s | 0.37–0.39 s | 0.05–0.08 m | `disarm-request`; `not-armed` while disarmed; new epoch; old epoch `stale-epoch`; driving resumed; one final expiry |
| F1-6 algorithm exit (SIGKILL stack) | **3/3** | 0 | 0.75–0.88 s | 0.16 m | expected kill recorded; guard lease expiry |
| F1-7 runner hang (heartbeats stop) | **3/3** | 0 | 1.25–1.33 s | 0.27–0.28 m | supervisor `runner-lease-expired` ≤ 0.6 s after the pause; guard lease expiry |
| F1-8 runner exit (SIGKILL runner) | **3/3** | 0 | 1.12–1.23 s | 0.25–0.27 m | supervisor inhibited; guard lease expiry; all orphaned children reaped (SIGTERM) |
| F1-9 runner error (D16) | **3/3** | 0 | 0.57–0.69 s | 0.09–0.13 m | injected error recorded; D16 disarm and stop confirmed (e.g. after 0.56 s) before any process was terminated |

**Common to every trial:**
- no contact or off-track (clearance ≥ 0.30 m);
- no guard fault;
- no nonzero throttle after onset + 1.1 s;
- all owned processes reaped;
- the player unchanged (604 files);
- no player process left behind.

The slowest stops, F1-7 and F1-8, are the designed worst case: up to 0.5 s of runner lease, plus 0.5 s of request life, plus braking.

## 3. Failures and refused attempts (retained)

- **v0.1, F1-1 trial 1: fail.** Stop 1.606 s from the injection request. Kept as a failure. See [progress](S1-06-M1-progress.md) and D17.
- **Before any motion:** two attempts on 2026-10-06 (stack startup, output not fresh), and one on 2026-10-07. That last one was refused by the motion-stage build-record check after the environments moved to `~/roboracer-work`. The check now maps the documented relocation and verifies both player binaries by hash (`68edb7f`).

## 4. Open anomalies (do not affect the F1 results)

1. **Player shutdown hang: 4 of 27 runs** (F1-5 t1/t2, F1-6 t3, F1-7 t1). At cleanup the player did not exit after SIGTERM, even with the grace raised from 5 s to 15 s (`83aa1a9`), and was SIGKILLed. Because of this the runner flags "cleanup requires review" and exits 1. These kills happened after the car had stopped and been disarmed; each guard trace is complete to the end (final disarm, then zero output).
   - **Correlation:** all four occurred in runs with window recording; none in about 25 earlier runs without it. That is not yet a cause.
   - **Proposed:** a short no-motion check, a few player start/stop cycles with and without the recorder.
2. **F1-8 recordings end early.** When the runner is SIGKILLed, the recorder stops with it. The files are playable (22–23 s) but don't cover the reaping phase.

The 2026-10-06 observer shutdown race (rclpy) is fixed and did not recur in these 27 runs.

## 5. Proposed S2 budgets (protocol §5), checked against D13

The D13 worst values, compared with the first measurements:
- observation age max 346 ms (was 334);
- command → observed p95 235 ms (was 229);
- telemetry max 251 ms (was 248).

All stay inside the proposed S2 budgets (≤ 450 ms, ≤ 300 ms and ≤ 400 ms respectively). **The budgets are unchanged and await your review before S2 acceptance.**

## 6. Status

- **S1-06:** M1 has run, failures are preserved, measurements are published and budgets are proposed. The check box is left for your review.
- **S1 acceptance is not claimed.** Amendment 1.2 still requires SIM1-03 (scene reset and re-initialization), SIM1-04, SIM1-05 (P1b, PRE-03/04) and SIM1-06 before S1 acceptance, and the S1-02 to S1-06 check boxes await your review.
