# S1-03 stage M5 — reactive baseline A on the track segment

Date: **2026-10-05**. Run: `20261005T160657Z-m5`. Proposal: [s1-03-controller-proposal.md](../planning/s1-03-controller-proposal.md), v0.3 (D6, D8). Approval: "yes run M4 and M5", run after M4 passed ([record](../planning/s1-motion-approval.json)).

**M5 passes on the first trial.** This is the S1-03 demonstration: the reactive baseline A, AVLite's `GapFollowController`, drives the car along the track segment through AVLite's own execution path:
- the `SyncExecuter` runs at 10 Hz on pinned snapshots, with ground-truth pose labelled and used only for monitoring;
- the plugin bridge carries each request to the supervisor;
- the supervisor's speed loop and exact steering conversion produce the command;
- the guard applies it.

The car steered while moving for the first time. It drove 6.06 m in 21 s, then requested zero and stopped.

## Results (trial 1)

| Item | Result |
| --- | --- |
| End condition | 6 m of path (6.06 m) after 21.0 s; no abort |
| Speed | target 0.27–0.30 m/s from A; encoder speed up to 0.35 m/s, under the 0.5 m/s abort |
| Steering requested by A | −0.068 to 0 rad (a slight right correction as the corridor opens on the left; limit ±0.35 rad) |
| Clearance | side ≥ 0.28 m (abort below 0.15 m); ±10° ahead ≥ 1.49 m (abort below 0.5 m) |
| Final stop | 0.17 s after the zero request; exactly one final `lease-expired` stop with zero output |
| Supervisor | 267 forwarded; rules applied: 210 `control`, 55 `target-zero`, 2 `no-feedback-yet`; no stale-feedback events |
| Guard | no fault, no rejection; output within throttle ≤ 0.07 and \|steering\| ≤ 0.668 (0.35 rad) |
| Latency chain (D7, p50 / p95) | tick → request generation 0.92 / 1.46 ms; generation → supervisor decision 0.11 / 0.16 ms; generation → guard accept 128 / 176 ms; accept → first applied step 1 ms (simulation time) |
| Processes and player | all children exited 0; the port was released; all 604 player files unchanged |

**Observation for later stages.** A heads for the deepest free direction, not the middle of the corridor. As the corridor widened on the left, the right-side clearance fell from 0.54 m to 0.28 m. That is inside this stage's limits, but full laps (S1-05/06) will need either a centering term or a stricter side-clearance speed rule. This is recorded, not changed.

## Status

- **S1-03 demonstrated (M3, M3b, M4, M5):** A runs through AVLite's actual execution path, with labelled GT, paced sampling (10 Hz ticks, physics progress in simulation time) and the measured command-to-response chain above.
- **Plan check boxes:** I am not ticking S1-02, S1-03 or S1-04 myself; they await your review against their full criteria.
- **Not authorized:** laps (S1-05/06), speeds above 0.3 m/s, reverse.

Evidence: `artifacts/s1/20261005T160657Z-m5/` (39-file manifest). Tests: 94 script tests and 39 plugin tests pass.
