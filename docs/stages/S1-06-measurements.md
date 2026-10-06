# S1-06 — First timing, resource and episode measurements (from the M6 laps)

Date: **2026-10-06**. Evidence: `artifacts/s1/20261006T064500Z-s1-06/`. Request: "go on with S1-06". **No motion was run for this report.** The rest of M1 (F1 fault matrix, five dedicated timing windows) awaits the [M1 protocol](../planning/s1-06-m1-protocol.md).

## Method

- **Tool:** `scripts/roboracer_timing.py` (new).
- **Window:** the plan's sampling window, a 10 s warm-up after the stage's run phase starts, then 120 s of monotonic wall time, applied to each of the three M6 laps (`20261006T054031Z-m6`).
- **Labelling:** these windows were not declared as timing runs before they ran, so they are **preliminary**. The five declared windows are D13 in the protocol.
- **Clocks:** each value is named by its clock domain. "Same-host mono" subtracts CLOCK_MONOTONIC stamps from two processes on this host. The guard's lease estimate is its own conservative, clock-bound figure.

## Results (window complete in all three: 120.0 s)

| Quantity | Trial 1 | Trial 2 | Trial 3 |
| --- | --- | --- | --- |
| Telemetry rate; period p50 / p95 / max | 5.80 Hz; 166 / 212 / 245 ms | 5.83 Hz; 164 / 212 / 248 ms | 5.82 Hz; 165 / 212 / 234 ms |
| Unique acquisitions per source; reused | 5.8/s for each of LiDAR, IPS, IMU and both encoders; 0 reused | same | same |
| Simulation real-time factor | 1.000 | 1.000 | 1.000 |
| Source age at receipt, LiDAR / IPS (p95) | 119 / 90 ms | 117 / 92 ms | 118 / 92 ms |
| Observation age at request (p50 / p95 / max) | 168 / 277 / 330 ms | 164 / 269 / 334 ms | 164 / 271 / 323 ms |
| Speed-feedback age at request, max | 330 ms | 334 ms | 323 ms |
| Clock bound (p95 / max) | 40 / 42 ms | 40 / 41 ms | 40 / 41 ms |
| Snapshot pose age; scan/pose skew (p95) | 99; 47 ms | 101; 47 ms | 100; 47 ms |
| Tick period p95 / max; tick duration p95; overruns | 100.4 / 102.9; 1.6 ms; 0 | 100.4 / 101.3; 1.6 ms; 0 | 100.4 / 101.2; 1.6 ms; 0 |
| Requests | 10.0 Hz, 1200 forwarded, rule `control` | same | same |
| Tick → request generation (p95) | 1.5 ms | 1.5 ms | 1.5 ms |
| Generation → supervisor decision (p95 / max) | 0.14 / 0.43 ms | 0.15 / 1.15 ms | 0.14 / 0.96 ms |
| Generation → guard accept, lease estimate (p50 / p95 / max) | 99 / 157 / 190 ms | 99 / 162 / 191 ms | 100 / 163 / 189 ms |
| Generation → guard accept, same-host mono (p50 / p95 / max) | 59 / 102 / 120 ms | 56 / 102 / 120 ms | 57 / 102 / 119 ms |
| Guard accept → applied (simulation time) | 1 ms | 1 ms | 1 ms |
| **Command → first observation acquired after it applied** (p50 / p95 / max) | 161 / 222 / 263 ms | 161 / 225 / 267 ms | 163 / 229 / 265 ms |
| Final stop after the zero request | 0.21 s | 0.21 s | 0.32 s |
| Episode | 1 lap, 0 contact, 0 off-track, 0.105 m | 1 lap, clean, 0.104 m | 1 lap, clean, 0.104 m |

**Resources** (CPU as % of one core over the window; RSS max):

| Process | CPU | RSS | Threads |
| --- | --- | --- | --- |
| Player (AutoDRIVE) | 137–138 % | 762–770 MiB | 71–73 |
| Devkit bridge | 28 % | 149–150 MiB | 41 |
| ROS observer | 8.5 % | 73 MiB | 26 |
| AVLite stack (plugin) | 3.0 % | 146 MiB | 42 |
| Supervisor | 2.2 % | 108–109 MiB | 42 |
| GPU | not sampled in these runs. The runner now samples device utilization and memory every second from a separate thread (about 22 ms per query, checked on this host). Per-process attribution is not available, because the player renders through OpenGL. | | |

## Against the frozen S1 operational limits (worst of the three trials)

| Limit | Frozen value | Measured max | Margin |
| --- | --- | --- | --- |
| Observation age at request (D3) | 500 ms | 334 ms | 166 ms |
| Speed feedback stale / lost (D5 v0.3) | 600 / 900 ms | 334 ms | 266 ms |
| Telemetry gap (stack abort) | 500 ms | 248 ms | 252 ms |
| Runner lease (500 ms) | no inhibition | 0 inhibited decisions | — |
| Guard clock bound | 400 ms | 42 ms | 358 ms |
| Request life, generation → guard accept | 500 ms | 191 ms | 309 ms |
| Final stop | 1.5 s | 0.32 s | 1.18 s |
| Speed (abort) | 0.5 m/s | 0.340 m/s | 0.16 m/s |
| Requested steering | 0.35 rad | 0.350 rad (clamped) | 0 |

Every frozen limit held. The only one with zero margin is steering, which by design sits at its clamp in the tightest hairpin.

## Observations

- **The telemetry path is the long pole.** The car acts on an observation about 270 ms old (p95), and its effect is seen in an observation about 225 ms after the command (p95). Supervisor and stack computation add under 2 ms. The ages come from the ~5.8 Hz telemetry period and the paced reply, not from AVLite.
- **Guard acceptance is about 58 % of forwarded requests.** The guard takes the newest request once per telemetry reply, so the 10 Hz requests between replies are superseded. This is expected and was never a loss.
- **The guard's lease estimate runs about 40 ms above the same-host value.** That is the clock-bound margin it deliberately adds.
- **Runs are highly repeatable:** the three trials agree within a few ms on every percentile.

## Status

- **S1-06 delivered so far:**
  - the measurement tool;
  - the first measurements, against the frozen limits;
  - GPU sampling in the runner;
  - draft later budgets (protocol §5).
- **Remaining M1 work:** the F1 matrix (27 short episodes) and five declared timing windows, both under the [M1 protocol](../planning/s1-06-m1-protocol.md). D12–D16 await your confirmation.
- **Tests:** 111 script tests (4 new) and 41 plugin tests pass. No check box is ticked.
