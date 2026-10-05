# S1 — Supervisor skeleton and the full no-motion command path

Date: **2026-10-05**. Run: `20261005T110210Z-s1-supervisor`. [Chinese report](S1-supervisor.zh-CN.md). Plan: [amendment 1.2](../planning/s1-first-amendment.md), order of work step 3. Next: [motion protocol draft](../planning/s1-motion-protocol.md).

**The S1 supervisor skeleton passes, with no motion.** The approved command architecture now runs end to end with real components:

AVLite `SyncExecuter` + `HoldController` (own process) → plugin `AutoDriveBridge` → **supervisor** (own process, `roboracer.supervisor/1`) → Devkit bridge guard inbox → in-simulator receiver guard.

In a 60-second interlocked run, every one of the 233 commands the guard accepted traced back through a forwarded supervisor request to one AVLite request. Each carried exact-zero values, its original generation time, `deadline = generation + 500 ms`, and the snapshot identity of the AVLite tick that produced it. The runner-liveness lease worked live: when the runner stopped heartbeating at cleanup, the supervisor inhibited itself within the lease.

**Nothing moved:** the guard interlock was on, the supervisor's motion gate is closed in code, and the plugin speed limit is 0.

## 1. What was built

| Part | Content |
| --- | --- |
| [`supervisor_core.py`](../../roboracer/runtime/supervisor_core.py) | Pure logic, described below. |
| [`supervisor_process.py`](../../roboracer/runtime/supervisor_process.py) | Started with `python -m roboracer.runtime.supervisor_process`. One abstract datagram socket for requests and heartbeats, and non-blocking forwarding to the guard inbox; a full or missing receiver is counted. Writes a decision trace (capped at 64 MiB) and a periodic status file, and exits 0 on SIGTERM/SIGINT. Importing the module does nothing, as the AVLite loader requires. |
| Bridge request path | `connect(supervisor=...)` / `connect_supervisor()` open a non-blocking socket. Each distinct command is sent once, so AVLite re-applying its held command every tick is counted, not re-sent. Each request carries the identity (sequence and acquisition stamps) of the snapshot its tick used. |
| Tick-pinned snapshot | `SyncExecuter` calls `get_sensor_frame()` and then, separately, `get_ego_state()`. The ground-truth pose now comes from the same snapshot as that tick's sensor frame, so a frame committed between the two calls cannot mix generations. |
| Runner | `autodrive_neutral.py --plugin-stack` replaces the stand-in with the real supervisor and runs AVLite at 10 Hz in a separate process. The runner sends heartbeats from its main loop, starting after the Connect sequence (whose input handling blocks for about 1 s). |
| [`autodrive_s1_supervisor.py`](../../scripts/autodrive_s1_supervisor.py) | End-to-end join of AVLite ticks, the supervisor trace and the guard trace. |

**`supervisor_core.py`.** It checks each request in a fixed order; the first failure is the reason:
1. malformed;
2. inhibited, or no runner yet;
3. wrong origin, duplicate or out-of-order sequence (a sequence is consumed even when a later check fails);
4. non-finite values;
5. request generated in the future, or older than its 500 ms life;
6. bad observation identity, an observation older than 500 ms, or one stamped more than 100 ms in the future;
7. outside the speed or steering limits;
8. `motion-not-authorized`.

Expiry is always measured from the request's original generation time; forwarding never refreshes it. The runner-liveness lease is 500 ms, and inhibition is sticky. The motion gate cannot be opened in code: `Limits(motion_authorized=True)` raises. Only exact zero is forwarded, as throttle and steering `"0"`.

## 2. Live run (interlocked, exact zero)

The setup was one fresh-process trial: `--profile p0-creep --provenance --guard observe --plugin-stack`, 60 s, on the SIM1-02 player. A visual PID- and window-bound review was done before Connect: Guarded, Autonomous, zeros, Disconnected. Connect succeeded on the first click.

| Check | Result |
| --- | --- |
| AVLite stack | 873 ticks at 100.0 ms (p95 100.3, max 101.1 ms), 0 overruns. Tick work p50 0.16 ms. |
| Requests | 631 sent, 0 refused or dropped. 242 were held back locally before the first snapshot (`no_observation`); 0 held re-sends. |
| Supervisor | 622 forwarded, 0 rejected during the observation. 9 `inhibited` after it ended: the runner stopped heartbeating, and the lease expired 292 ms after the observation ended. |
| Guard | 233 accepted, all traced to forwarded zero requests; 389 forwarded requests were superseded at the bridge, which forwards only the newest request at the 3.9 Hz telemetry rate. 81,180 traced steps with 0 nonzero output; 0 rejections, 0 expiries. |
| Snapshot identity | Every request names its own tick's snapshot. The observation join still passes: 241 of 241 acquisition frames, with scan and pose identity. |
| Request age at supervisor | p50 / p95 / max: 0.09 / 0.12 / 0.18 ms. |
| Observation age at supervisor | p50 / p95 / max: 326 / 443 / 489 ms, against the 500 ms limit. |
| Guard lease left at accept | p50 363 ms, p5 320 ms, min 311 ms. |
| Other | Maximum displacement 4 mm. All 5 children exited 0, and port 4567 was released. All 604 player files were unchanged. The supervisor used 0.36 % of one core and 86 MiB; the AVLite stack used 1.2 % and 143 MiB. |

**Finding for the motion protocol.** Observation age is the tightest margin: at most 489 ms against a 500 ms limit. Its parts are:
- about 43 ms from acquisition to emission;
- transit;
- the runner's 100 ms reply pacing, which delays the provenance message;
- up to one telemetry period (about 258 ms) of waiting for the next frame.

Telemetry at 3.9 Hz also limits closed-loop control. The [protocol draft](../planning/s1-motion-protocol.md) proposes how to handle this.

**Analysis correction (retained).** The first analysis flagged the 9 post-run `inhibited` decisions as failures (`s1-supervisor-analysis-v1-flagged.json`). It now accepts them only when inhibition came from lease expiry after the observation ended, and still fails on any rejection or state change during the observation. Observation ages are now computed over forwarded requests only.

## 3. Tests

The plugin suite has 26 tests, 7 of them new:
- core forwarding with the original generation time;
- the runner requirement and sticky lease;
- the full validation order;
- sequence and origin rules;
- that motion cannot be authorized;
- the real process over its sockets (forward, motion gate, malformed input, live lease inhibition, clean exit);
- the bridge client (no-observation, held re-send, tick-pinned identity across a snapshot committed mid-tick).

The runner, provenance, guard and scan-check suites pass. An offline smoke run of the stack and supervisor without a simulator showed 10 Hz ticks and both exiting 0. That smoke run also found AVLite's float time sum skipping control on about 20 % of ticks; the stage periods are now 0.99 × the tick period.

## 4. Status

- **Done (no motion):** S1 order of work steps 1–3. The S1-04 supervisor behaviours shown here (stale/non-finite requests, runner loss) are demonstrated without motion only; S1-04 still needs them under motion.
- **Next:** the [numerical motion protocol draft](../planning/s1-motion-protocol.md). **Stopped for confirmation**; no command that can move the vehicle has been sent.

Evidence: `artifacts/s1/20261005T110210Z-s1-supervisor/` (39-file `evidence-sha256.txt`). Commit `d0728df` ran the live trial.
