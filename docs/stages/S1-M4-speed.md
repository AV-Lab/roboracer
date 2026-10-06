# S1-03 stage M4 — closed-loop speed

Date: **2026-10-05**. Run: `20261005T152922Z-m4`. Proposal: [s1-03-controller-proposal.md](../planning/s1-03-controller-proposal.md), v0.3. Approvals: "yes run M4 and M5"; v0.3 thresholds, "yes rerun M4"; GPU freed, "You can kill the Python processes to free the GPU memory" ([record](../planning/s1-motion-approval.json)).

**M4 passes (trial 5).** For the first time the car is driven by AVLite through the target-speed path:
- AVLite `SpeedStepController` requests target speeds;
- the plugin bridge carries them to the supervisor;
- the supervisor's speed loop (D5 v0.3) turns each target into throttle, using encoder speed from its own subscription (D4 A);
- the guard applies it.

On the straight, with steering exactly 0, speed tracks 0.1 / 0.2 / 0.3 m/s with no brake chatter. It stops from 0.3 m/s in 0.34 s, and a deliberate feedback blackout cuts throttle and then inhibits the supervisor.

## Results (trial 5)

| Target | Mean over last 1 s (±0.05 needed) | Overshoot (≤ 0.1) | Brake events (≤ 2) |
| --- | --- | --- | --- |
| 0.1 m/s | 0.109 | 0.027 | 0 |
| 0.2 m/s | 0.212 | 0.037 | 0 |
| 0.3 m/s | 0.311 | 0.027 | 0 |

- **Stop from 0.3 m/s:** 0.34 s (limit 1.5 s). **Final stop:** 0.13 s.
- **Stale feedback** (the supervisor ignores its encoder feedback from 12 s on): throttle 0 after 0.50 s (limit 0.6 s + one frame), inhibition after 0.80 s, nothing forwarded afterwards. Exactly one final `lease-expired` stop with zero output.
- **Feedback age** before the blackout: p50 211 ms, p95 299 ms, max 324 ms. Telemetry frame period: p50 210 ms, max 241 ms.
- **Latency chain (D7)**, each segment on its own clock:

  | Segment | p50 | p95 | max |
  | --- | --- | --- | --- |
  | AVLite tick → request generation | 0.29 ms | 0.37 ms | 0.51 ms |
  | generation → supervisor decision | 0.12 ms | 0.15 ms | 0.21 ms |
  | generation → guard accept | 145 ms | 185 ms | 238 ms |
  | accept → first applied step (simulation time) | 1 ms | 1 ms | 1 ms |

- **Travel and path:** 2.26 m in a straight line, under the 2.5 m limit. Guard output stayed within throttle ≤ 0.07 and steering 0, with no guard fault or rejection.
- **Requests:** 171 forwarded, plus 16 rejected as `inhibited` and 1 as `feedback-lost` after the blackout, as intended.
- **Processes and player:** all children exited 0, the port was released, and all 604 player files were unchanged.

## Attempts (all retained; 2 of 6 driving trials used)

| Attempt | Outcome | Cause and handling |
| --- | --- | --- |
| 0 | No motion | The supervisor could not import `rclpy`: the runner replaced `PYTHONPATH` instead of extending it. Fixed. |
| 1 | No motion | The player segfaulted during start-up. The GPU was nearly full (see attempt 4). |
| 2 | No motion | "No feedback yet" was treated as "feedback lost", so the supervisor inhibited itself on the first request. Fixed. |
| 3 | Ran; tracking failed | The 0.4 s stale threshold sat below the measured feedback age (max 564 ms) and hard-braked routinely. Proposal **v0.3** raised it to 0.6 s, and loss to 0.9 s; you confirmed it. |
| 4 | Ran; stopped by the guard | Telemetry slowed (frame gaps up to 648 ms, render rate 34 Hz) because two `thellmbook` Jupyter kernels held 8.6 of 10 GB of GPU memory. The guard lease expired and stopped the car, as designed. With your permission I terminated those two kernels (SIGTERM), and GPU use fell to 874 MiB. |
| 5 | **Pass** | Render rate 60 Hz, frame period 210 ms. |

The proposal's change log records the D5 history: v0.2 numbers, then K = 5.02 from M3b, then the v0.3 thresholds.
