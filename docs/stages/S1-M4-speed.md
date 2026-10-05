# S1-03 stage M4 — closed-loop speed (in progress; not passed)

Date: **2026-10-05**. Run: `20261005T152922Z-m4`. Proposal: [s1-03-controller-proposal.md](../planning/s1-03-controller-proposal.md) (v0.2, with a v0.3 change request in §7). Approval: "yes run M4 and M5" ([record](../planning/s1-motion-approval.json)).

**M4 has not passed. M5 was not started.** The full stack now drives the car: AVLite `SpeedStepController` → plugin bridge → supervisor speed loop (D5), using the supervisor's own encoder feedback (D4 A) → guard. Most criteria passed, but speed tracking at 0.2 and 0.3 m/s failed. The cause is identified: the approved 0.4 s stale-feedback threshold is shorter than the feedback age this setup produces. A narrow threshold change (v0.3) awaits your confirmation.

## Built for M4/M5 (all tested)

- **Supervisor (D4/D5):**
  - stages `m4`/`m5` for AVLite requests;
  - `SpeedLoop`: static inverse feedforward K = 5.02, bounded integral trim, u_max 0.07, rise limit 0.1 per s, overspeed and stale-feedback rules;
  - exact steering conversion;
  - its own encoder-speed subscription (`--feedback`), plus a blackout test hook.
- **Plugin (D6):**
  - `SpeedStepController` (test controller);
  - `GapFollowController` (reactive A: follow-the-gap with disparity extension, |steer| ≤ 0.35 rad, v* ≤ 0.3 m/s);
  - `EgoState.velocity` from encoder speed.
- **Runner:**
  - range-checked stage profiles;
  - an AVLite stack stage driver with the stage abort rules;
  - analysis `autodrive_s1_m45.py`, including the D7 latency chain.

The runner raises the plugin's `max_target_speed_mps` to 0.3 inside the stack process only; the shipped default stays 0.

## Trial 3 results

| Criterion | Result |
| --- | --- |
| Step 0.1 m/s: mean of the last 1 s | 0.109 m/s ✓; overshoot 0.050 ✓; brake events 2 ✓ |
| Step 0.2 m/s | 0.164 m/s ✗ (needs ±0.05); overshoot 0.051 ✓; brake events 4 ✗ |
| Step 0.3 m/s | 0.189 m/s ✗; overshoot 0.049 ✓; brake events 3 ✗ |
| Stop from 0.3 m/s (limit 1.5 s) | 0.45 s ✓ |
| Stale feedback → throttle 0 (limit 0.4 s + one frame) | 0.20 s after the blackout ✓; inhibited 0.40 s after it; 0 forwarded afterwards ✓ |
| Final stop | 0.11 s ✓ |
| Guard | no fault, no rejection, one final lease expiry; throttle ≤ 0.07, steering 0 ✓ |
| Latency chain (D7, p50) | tick → request generation 0.45 ms; generation → supervisor decision 0.19 ms; generation → guard accept 198 ms; accept → first applied step 1 ms (simulation time) |

**Cause.**
- The supervisor's encoder feedback arrives once per telemetry frame: p50 243 ms, p95 284 ms. That is slower than M3b's 206 ms, with the extra subscriber running. Delivery adds about 155 ms.
- At request time, feedback is therefore p50 274 ms, p95 405 ms, max 564 ms old.
- The 0.4 s stale rule therefore fired routinely (11 of 104 control decisions). Each time it commanded zero throttle, which is a hard brake: the car stopped within a frame and the rise limit ramped it back. The speed trace shows this cycling directly.
- Between those events, the commanded throttle and measured speed agree with K = 5.02.

## Attempts (all retained)

| Attempt | Outcome | Motion |
| --- | --- | --- |
| 0 | The supervisor could not import `rclpy`: the runner had replaced `PYTHONPATH` instead of extending it. Fixed. | none (player never started) |
| 1 | The player segfaulted during start-up, after Vulkan initialisation. The monitor layout had just changed to a single 2560 × 1440 display. It did not recur. | none |
| 2 | The supervisor inhibited itself on the first request, because "no feedback yet" was treated as "feedback lost". Fixed: no feedback yet → zero throttle, not inhibition. Stopped with SIGTERM; clean cleanup. | none (the guard never armed) |
| 3 | Ran to completion; speed tracking failed as above. | 1.9 m straight, ≤ 0.35 m/s |

Evidence: `artifacts/s1/20261005T152922Z-m4/` (96-file manifest). All 604 player files were unchanged. Tests: 94 script tests and 38 plugin tests pass.
