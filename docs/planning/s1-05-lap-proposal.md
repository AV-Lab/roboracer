# S1-05 Stage M6 — One Bounded Lap of C0 — Proposal for Confirmation

Version **0.1**, 2026-10-06. [Chinese version](s1-05-lap-proposal.zh-CN.md). Builds on the [S1 motion protocol](s1-motion-protocol.md) and the confirmed [S1-03 controller proposal v0.3](s1-03-controller-proposal.md). **Nothing here is authorized until you confirm it.** Laps are still listed as not authorized in the [approval record](s1-motion-approval.json).

## 1. Why a new stage

- S1-05 needs the runner, the independent scorer and the manifest to cover a full lap; S1-06 then needs three bounded-circuit runs.
- M5 (≤ 6 m or 40 s) is the largest confirmed envelope. One C0 lap is 31.33 m of centerline and takes about 2 minutes at the approved speed.
- M5 showed that baseline A does not center. An offline check (below) shows what that means over a whole lap: A gets within **6–11 mm** of a wall at the hairpins.

## 2. Offline evidence (no motion)

Tool: `scripts/roboracer_rollout.py`, a planning check and not acceptance evidence.
- **Plant:** the measured M3/M3b plant (speed settles within one frame, u_max 0.07 ≈ 0.35 m/s, steering slew 183°/s), rear-axle bicycle kinematics (wheelbase 0.324 m), one observation per 0.2 s of simulation time, and a delay from observation to applied command.
- **Simulated LiDAR:** a 2-D ray cast against the qualified wall footprint. Checked against recorded data:
  - the M5 spawn scan: p50 1.8 mm, p95 7.9 mm, with 1 mismatch in 1035 beams;
  - M5's per-frame side sector minima: ≤ 4 mm over 129 frames;
  - the front sector: p95 3 cm.
- **Judging:** the M5 stack's abort rules apply, and the independent scorer judges the result.

| Variant | Delay | Result | Footprint–wall min | Side sector min | Max \|steer\| | Mean speed |
| --- | --- | --- | --- | --- | --- | --- |
| A (approved, ±0.35 rad) | 0.25 s | 1 lap, no contact | **0.006 m** | 0.173 m | 0.350 | 0.238 m/s |
| A | 0.40 s | 1 lap, no contact | **0.011 m** | 0.175 m | 0.350 | 0.239 m/s |
| **A-lap (proposed)** | 0.25 s | 1 lap, no contact or off-track | **0.105 m** | 0.257 m | 0.350 | 0.239 m/s |
| A-lap | 0.40 s | 1 lap, no contact or off-track | 0.107 m | 0.259 m | 0.350 | 0.238 m/s |
| A-lap, limit 0.5 rad | 0.25 / 0.40 / 0.60 s | 1 lap, no contact or off-track | 0.105–0.111 m | 0.257–0.262 m | 0.354 | 0.238 m/s |

- A-lap completes the loop in about 118 s and stays within the approved ±0.35 rad.
- The tightest bend (s ≈ 26 m) has a smoothed centerline radius of 0.72–0.93 m, and 0.35 rad gives a turning radius of 0.89 m. A-lap reaches the limit there; with a 0.5 rad limit it would need only 0.354 rad, so there is little reserve at 0.35 rad, but none is missing.
- The simulated scan omits sensor noise, which the recorded scans show to be at the millimetre level. The rollout is not the simulator: the live run is the test.

## 3. Decisions needed

**D9 — controller for the lap: A-lap.** This is `GapFollowController` with `LAP_PARAMS` (`roboracer/control/gap_follow.py`). Its defaults remain exactly A, so M5 is unchanged. Three changes from A:
- **Centering:** the gap heading gets `atan2(0.5 · (d_left − d_right)/2, 1.0 m)` added, with d from the nearest returns within 80–100° on each side, capped at 2 m.
- **Side-clearance speed cap:** v* ≤ 1.0 · (min(d_left, d_right) − 0.15 m).
- **Turn slowdown:** v* ≤ 0.3 · (1 − |steer|/0.8), instead of /0.6, so the car does not crawl through the hairpins.

Unchanged: speed ≤ 0.3 m/s, |steer| ≤ 0.35 rad, front rule 0.25 · (d_front − 0.5), disparity extension, and LiDAR only (no pose, no map).

**D10 — stage M6 limits.**
- **Supervisor and guard:** exactly as in M5. That means the D5 v0.3 speed loop (u_max 0.07, overspeed 0.5 m/s, stale 0.6 s / lost 0.9 s), guard throttle ≤ 0.07, |steering| ≤ 0.668 (0.35 rad), and the same lease.
- **Stack aborts, as in M5:**
  - side (80–100°) < 0.15 m;
  - front (±10°) < 0.5 m;
  - requested |steer| > 0.35 rad;
  - no new observation for 0.5 s;
  - encoder speed > 0.5 m/s;
  - a guard fault.
- **End:** 33 m of driven path (one lap plus the opening straight again, about 140 s) or 200 s, whichever comes first. Then zero is requested and the lease is allowed to expire, as in M5.
- **Containment (new):** M5's radius from the start cannot be used, because a lap goes up to 11.8 m from the spawn and comes back. M6 instead uses a fail-closed axis-aligned box in the bridge: the qualified track's wall extent plus 0.3 m, x ∈ [−4.23, 2.12], y ∈ [−9.04, 7.65]. Leaving the box stops the bridge, as the radius does today.
- **Scoring:** after the run, `roboracer_episode.py` runs the independent scorer. A lap counts only with all gates passed in order; contact and off-track are judged from the swept footprint.

**D11 — trials.** Run up to 3 trials of M6, each a fresh player at the scene spawn with the same manual pre-Connect review.
- Stop after the first abort, contact or off-track, and report before any further trial.
- These are the S1-05 lap demonstrations. S1-06's "three bounded-circuit demonstrations" will be proposed separately, once S1-05 is reviewed.

## 4. What confirming this does not do

- It does not accept S1-02 to S1-05, and does not change any acceptance criterion.
- It does not authorize speeds above 0.3 m/s, reverse, steering beyond ±0.35 rad, more than one lap per episode, unattended reset, or the B stack.

## 5. Requested reply

Confirm or change D9 (A-lap parameters), D10 (M6 limits, end condition and box containment) and D11 (up to 3 trials, stopping at the first failure). Until then, only recorded-input scoring and offline checks run.
