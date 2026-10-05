# SIM1-01 — Source provenance and acquisition identity

Date: **2026-10-05**. Run: `20261005T053316Z-sim1`. [Chinese report](SIM1-provenance.zh-CN.md). Protocol: [roboracer.sim1/1](../../integration/autodrive/sim1/PROTOCOL.md).

**SIM1-01 passes.** The instrumented player sends a versioned handshake, process session and episode identity, and per-source acquisition stamps with every telemetry frame. The isolated Devkit validates them, restamps ROS headers to acquisition time using a measured clock-offset bound, and publishes a provenance topic. Two clean 60-second observations and three source-freeze trials completed with zero commands and no telemetry gaps. Overhead could not be distinguished from SIM0. **No motion, receiver guard or arming exists yet**; those are SIM1-02/03.

## 1. Entry and scope

The user's "go on the development plan" (2026-10-05) followed the SIM0 report that named SIM0-04 stage review and SIM1 entry as the next gate. It is recorded as both: **SIM0-04 checked, SIM1 entered.** This run covers SIM1-01 only: Manual mode, exact-zero replies and the amended `p0-creep` guards throughout.

## 2. What was built

| Part | Content |
| --- | --- |
| New component | [`RoboRacer/Provenance.cs`](../../integration/autodrive/sim1/RoboRacer/Provenance.cs): session GUID; episode counter advanced on every scene load; fixed-step counter (hidden object, execution order −32000); per-source sequence and stamps; `Stopwatch` monotonic clock; launch-flag-gated freeze hooks that fail closed. It writes no simulation state. |
| Vendor patch | [`vendor-sim1-01.patch`](../../integration/autodrive/sim1/vendor-sim1-01.patch), +45/−1 lines: a stamp call at the end of each acquisition in `LIDAR.LaserScan`, `IPS`, `IMU` and `WheelEncoder`; freeze early-returns in LIDAR and IPS; in `Socket`, ping/freeze reading, camera capture bracketing and the new telemetry fields. No physics, controller, scene or actuation change. |
| Build path | `autodrive_build.py --sim1-patch` validates an unpatched project and a clean `git apply --check`, stages the component, applies the patch and records hashes. Incremental IL2CPP build: **251.37 s**, exit 0, no C# errors. |
| Bridge / validator | [`autodrive_provenance.py`](../../scripts/autodrive_provenance.py) (import-safe) plus `autodrive_neutral.py --provenance` / `--freeze-test`. The reply guard still allows only exact-zero controls plus `RR Ping Mono` / `RR Test Freeze`. |

**Static verification.**
- The patched sources compile against the pinned 2021.3.9f1 API before the build.
- After the build, the vendor diff in the derived copy is byte-equal to the patch.
- The strict serialized comparison passes: numeric geometry and asset mapping are equal, with 18 meshes and 120 scene scripts, the same as earlier accepted derived builds.
- `RuntimeInitializeOnLoads.json` registers `RoboRacer.Provenance.Install`.
- All 603 player files are unchanged after the runs.

**Derived copy.** I reused the superseded, never-modified pose-trace worktree (its tracked diff equals the qualified baseline, `4965e4fa…`) because only 24 GB of disk remains. It inherits a Library cache, so this is not a clean-import claim, the same as the earlier diagnostic builds.

## 3. Live results

Each fresh process had visual, PID-bound pre-Connect review: Manual, all readings zero, disconnected, unchanged display settings.

| Measurement | clean-01 | clean-02 | freeze-01 | freeze-02 | freeze-03 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Observation (s) | 60 | 60 | 30 | 30 | 30 |
| Frames / telemetry-seq gaps | 235 / 0 | 237 / 0 | 120 / 0 | 119 / 0 | 120 / 0 |
| Receipt rate (Hz) | 3.872 | 3.903 | 3.903 | 3.871 | 3.916 |
| Max reported displacement (mm; bound 10) | 3 | 3 | 2 | 2 | 2 |
| LIDAR acquisitions between frames (p50) | 5 | 5 | 5 | 5 | 5 |
| LIDAR age at bridge p50 / p95 (ms) | 102.9 / 132.6 | 101.4 / 124.6 | 110.4 / — | 101.0 / — | 101.7 / — |
| IPS/IMU/encoder age p50 (ms) | 85.6 | 84.7 | 83.8 | 86.6 | 84.7 |
| Camera capture age p50 (ms) | 42.2 | 41.2 | 40.7 | 42.9 | 41.2 |
| Clock offset range (ms) | −51.3…−29.0 | −47.9…−28.3 | −48.8…−5.2 | −52.5…−19.0 | −50.8…−27.8 |
| Offset bound p50 / max (ms) | 44.8 / 57.3 | 43.2 / 56.4 | 43.4 / 73.4 | 45.1 / 75.6 | 42.8 / 60.5 |
| ROS headers equal to acquisition mapping | 1170/1175 | 1180/1185 | 595/600 | 590/595 | 595/600 |
| Hook capability / rejections | none / 1 | none / 1 | yes / 0 | yes / 0 | yes / 0 |
| Child exits; port released | 0,0,0; yes | 0,0,0; yes | 0,0,0; yes | 0,0,0; yes | 0,0,0; yes |

- **Ages** are bridge receipt minus acquisition, ± the offset bound. They include the bridge's 100 ms zero-reply pacing cycle and the ~3.7 MB camera payload. These are descriptive measurements, not thresholds.
- **Freeze-run LIDAR p95** values are dominated by the intentional freeze (see section 4).
- **First-frame headers:** in every run, the 5 header stamps that do not match the acquisition mapping are the first frame's five stamped messages, published before the first clock exchange. That frame is recorded as `stamp_basis: bridge-publication`.
- **Clock offset:** every estimate is consistent with a shared monotonic epoch (0 lies within each bound). This is not assumed; acquisition times always carry the bound.
- **Hook-rejection probe:** each clean run sent one freeze request to a player launched without test hooks. The player rejected and counted it, and nothing froze.

**Overhead against SIM0** (same configuration, `20261005T052025Z-p0`): player CPU 107–112 % of one core against 111–112 %; player RSS 0.74–0.76 GB against 0.74–0.75 GB; bridge CPU 18–22 % against 22 %; receipt rate 3.87–3.92 Hz against 3.90 Hz. No material difference.

## 4. P1a cases covered by SIM1-01

| Case | Method | Result (×3 unless noted) |
| --- | --- | --- |
| Source freeze despite continued publication | Live: LIDAR frozen 10–15 s after first frame via test hook | All 18/18/19 frozen frames carried the **same** LIDAR identity (reused), with age rising monotonically to 4.73/4.81/4.97 s. Telemetry and all other sources kept advancing, and LaserScan kept publishing with its **original** acquisition stamp. New scans resumed within 1/2/1 frames. |
| Sample reuse / retransmission identity | Live (above) plus recorded-frame tests | Old seq/step/time/stamp preserved exactly. A reused seq with a different stamp is rejected. |
| Queue / drop behavior | Live, 5 runs | The stock transport is lock-step (one outstanding request). Every run had consecutive telemetry sequences with no drop. Five LIDAR scans per frame are superseded inside the simulator, which is visible as the acquisition gap. |
| Duplicate / out-of-order frames | Recorded-frame fixtures | Rejected (deterministic tests). |
| Malformed / nonfinite / negative stamps | Recorded-frame fixtures | Rejected. |
| Schema / session / capability mismatch, cross-episode stamps, acquisition after emission | Recorded-frame fixtures | Rejected. |
| Clock exchange: non-causal, repeated or unknown echo | Fixtures | Rejected or ignored. Live bound reported per exchange. |

**Not covered by SIM1-01 (later items):**
- expired requests in forwarding envelopes, clock discontinuity, and supervisor or Devkit loss: SIM1-02;
- **live** reset/reconnect and stale queued commands: SIM1-03. The episode counter that SIM1-03 relies on is implemented and fixture-tested, but no reset was exercised live here.

## 5. Retained failures

1. `clean-failed-cli`: my runner's new profile check also rejected the observer child, which gets no `--profile`. It failed before any player launch. I narrowed the check to run/bridge modes and added a regression test.
2. `clean-failed-connect`: the Connect click passed every input-target check (pointer chain, focus, coordinates), but the connection never toggled. The run hit the bounded startup timeout, all children exited 0, and the port was released. The player log shows no exception. This matches SIM0's earlier intermittent first-click losses. The single retry connected, and all later runs connected first time.

## 6. Verification and evidence

- **Tests:** 54 focused tests pass, including 13 new provenance tests: contract/fault fixtures, freeze evaluation, the reply guard and CLI scoping.
- **Evidence:** `artifacts/simulator-build/20261005T053316Z-sim1/`. It holds the build record and executed patch, the strict comparison, clean and freeze runs with analyses, both failed attempts, executed tool copies, `result-summary.json`, `reproduction.json`, and a 125-file manifest (SHA-256 `9a1e3735411d2ad3f1dfddaeea8a27cfe8bbf434c80baa298ba3924e7e529e7c`).

## 7. Status and next step

- **Counts:** original plan 2/34; source amendment **5/10** (SIM0-01–04, SIM1-01); Linux recovery 4/4.
- **Next:** SIM1-02, receiver validation and a lease immediately before `Steer`/`Drive`, with applied-command acknowledgements and the disarmed P1a command/clock/failure cases. That step adds an actuation-path guard but still no nonzero command. Moving tests stay behind the numerical motion protocol (SIM1-05).
