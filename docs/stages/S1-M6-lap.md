# S1-05 stage M6 — one bounded lap of C0 with A-lap

Date: **2026-10-06**. Evidence: `artifacts/s1/20261006T054031Z-m6/` (114-file manifest). Proposal: [s1-05-lap-proposal.md](../planning/s1-05-lap-proposal.md) v0.1. Approval: "approve D9, D10, D11; run M6" ([record](../planning/s1-motion-approval.json)). Code: commit `8a8fa7e`, clean.

**All three permitted trials (D11) completed one lap without contact or off-track.** Each trial ran through the single-episode entrypoint in live mode, `scripts/roboracer_episode.py live --stage m6`:
1. a fresh player at the scene spawn;
2. a visual pre-Connect review, recorded as a manual step;
3. one scripted Connect click;
4. A-lap (`GapFollowController` + `LAP_PARAMS`) driving through AVLite's `SyncExecuter`, the plugin bridge, the supervisor's D5 speed loop and the in-simulator guard;
5. after the run, the independent scorer and the manifest export.

## Results

| | Trial 1 | Trial 2 | Trial 3 |
| --- | --- | --- | --- |
| Outcome (stack) | finished: distance | finished: distance | finished: distance |
| **Laps (independent scorer)** | **1**, 122.7 s | **1**, 123.3 s | **1**, 122.8 s |
| Contact / off-track events | 0 / 0 | 0 / 0 | 0 / 0 |
| Min footprint–wall clearance | 0.105 m | 0.104 m | 0.104 m |
| Path driven / run time | 33.10 m / 138.9 s | 33.11 m / 139.2 s | 33.13 m / 139.1 s |
| Max encoder speed | 0.339 m/s | 0.339 m/s | 0.340 m/s |
| Requested steering | −0.350 to +0.134 rad | −0.350 to +0.133 rad | −0.350 to +0.133 rad |
| Min side (80–100°) / front (±10°) | 0.260 / 1.32 m | 0.260 / 1.31 m | 0.259 / 1.32 m |
| Final stop after the zero request | 0.21 s | 0.21 s | 0.32 s |
| Supervisor | 1446/1446 forwarded | 1451/1451 | 1447/1447 |
| Guard | one final `lease-expired`; no fault or rejection | same | same |
| Latency: generation → supervisor decision (p50 / p95) | 0.11 / 0.14 ms | 0.11 / 0.15 ms | 0.10 / 0.14 ms |
| Latency: generation → guard accept (p50 / p95) | 105 / 168 ms | 104 / 169 ms | 108 / 172 ms |
| Tick overruns | 0 | 0 | 0 |
| Processes | all 5 children exited 0; port released | same | same |

- The player (604 files) was unchanged after every trial. Each manifest confirms the player and `GameAssembly.so` match the SIM1-03 build record, records `unattended_reset: false`, and records the controller parameters actually used.
- The three trials agree to within 0.6 s of lap time and 1 mm of clearance.

## Notes

- **Offline prediction held.** The rollout predicted 0.105 m minimum clearance, a 118 s lap, 0.35 rad peak steering and 0.59 m peak per-frame progress. The live runs measured 0.104–0.105 m, about 123 s, 0.35 rad and 0.58–0.60 m. Live laps are slower because the real speed loop and frame cadence lose a little time in the hairpins.
- **Steering reaches its limit.** In the tightest hairpin, A-lap's request is clamped at −0.35 rad. This is expected (proposal §2) and is not an abort: the stack aborts only when the requested steering *exceeds* 0.35 rad, and the controller clamps to it. It leaves no steering reserve in that bend. Any faster or different track would need a new proposal.
- **Encoder speed above the target.** It reached 0.34 m/s against the 0.3 m/s target (speed-loop overshoot, as in M5). This stays under the 0.5 m/s abort and within the guard's throttle cap of 0.07.
- **The driven path is shorter than centerline progress** (33.1 m path vs 37.4 m progress): the car cuts the inside of both hairpins. The trajectory plots (`m6-trial*-trajectory.png`) show a closed loop inside the drivable ring.

## Status

- **S1-05 demonstrated live.** The parameterized single-episode runner, the independent lap/contact/off-track bookkeeping and the manifest export (with the manual initialization recorded, not called unattended reset) all ran on three real lap episodes.
- **I am not ticking S1-05 or any earlier box.** They await your review.
- **S1-06** (run M1, publish timing/resource/episode measurements, propose budgets) and **S1 acceptance** ("three independent bounded-circuit demonstrations") are not claimed here. These three M6 runs may serve as those demonstrations if you accept them as such.
- **Still not authorized:** speeds above 0.3 m/s, reverse, more than one lap per episode, steering beyond 0.35 rad, unattended reset.
