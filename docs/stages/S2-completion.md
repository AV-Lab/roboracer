# S2 — Completion report and stage review

Date: **2026-10-15**. Request: "go to next step", after the D28/D29 checks and reruns passed. Running report with every run: [S2.md](S2.md). Proposal: [s2-proposal.md v0.1](../planning/s2-proposal.md); budgets and matrix: [s2-budgets-proposal.md v0.1](../planning/s2-budgets-proposal.md). Decisions D20–D29: [approval record](../planning/s1-motion-approval.json). Backend: the frozen [patch-04 backend](../architecture/qualified-backend.md), with the player unchanged (604 files) after every S2 run.

**S2 goal (plan):** one invocation runs repeated AutoDRIVE episodes, validates each initial state, records results, and recovers or fails cleanly after defined faults.

## Summary

- **All six S2 items are delivered**, and every part of the frozen M2 acceptance matrix (D26 A) has passed:
  - **ten consecutive healthy unattended episodes:** 10/10, no recovery action;
  - **each F2 case three times:** 30 passing repetitions; F2-6 and F2-10 each needed one rerun after D28/D29;
  - **five timing windows:** all 10 episodes inside every frozen S1 limit and D25 budget;
  - **replay ×3 fresh processes:** exact on every fixture.
- **No failure is waived.** Five failed acceptance attempts are retained, each with a cause found and fixed before the next approved run (§4). Simulator exit and hang are recorded only as containment.
- **No manual step is hidden.** Every pre-Connect check in an acceptance run was the automated D21 check. The one human step is your single review of the reference image (2026-10-09), recorded as setup.
- **Three open issues** carry into S3 (§5). None blocks the S2 criteria.
- **Stage review: accepted 2026-10-22** ("accept S2-01 to S2-06"). All boxes in §6 are ticked: **S2 is complete**; the original plan is at 16/34.

## 1. S2 items

| Item | Delivered | Evidence |
| --- | --- | --- |
| **S2-01** unattended initialization | One player per batch, with GUI Reset between episodes (D20 A). Each Connect is preceded by an automated text-region check of 5 regions (D21 A; 0 mismatched px in every check). Readiness is checked after each scene load and before any arm: spawn ≤ 0.010 m (measured 0.001), yaw ≤ 1° (0.0°), wheels still, guard disarmed with no fault. Reset → Connect took 5.07–5.08 s. | [S2 §3](S2.md), [§14](S2.md) |
| **S2-02** lifecycle ownership | The runner owns every process group. The orchestrator `roboracer_batch.py` applies the recovery ladder (GUI Reset → fresh player → end the batch) with a wall cap, counts every attempted episode and lists every recovery action. A hang watchdog runs inside GUI Reset too. D27 A plans a fresh player every 4 episodes. Cleanup takes 2.0–2.5 s. Failure evidence is retained: thread snapshots of a hung player, and guard traces with completeness checks. | [S2 §3](S2.md), [§12–§13](S2.md), [§16](S2.md) |
| **S2-03** recording and open-loop replay | The bridge input hook records every raw Devkit message (bounded at 64 MB). Replay goes through the plugin's own assembler, `get_sensor_frame` and controller, is labelled open-loop and never counts as a lap. Exact equality (D24). | [S2 §2](S2.md), §3 below |
| **S2-04** fault policies | F2-1 to F2-10 cover reset during motion, duplicate and out-of-order observations, clock jump, stale speed feedback, Devkit loss, supervisor exit and hang, and simulator exit and hang. `roboracer_f2.py` checks the injection, detection, stop or containment, no contact, recovery, and that only expected processes terminated. The guard rejects the previous epoch's request (`stale-epoch`) at every re-arm. | [S2 §6](S2.md), [§15–§16](S2.md) |
| **S2-05** baseline and budgets | M2 baseline: 5/5 laps on the fixed bridge, F2 10/10 with recovery, five windows, replay exact. Budgets were proposed with that evidence and confirmed (D25, D26 A) before the matrix was frozen. | [S2 §9–§10](S2.md), [budgets](../planning/s2-budgets-proposal.md) |
| **S2-06** M2 acceptance matrix | §2 below | [S2 §14–§16](S2.md) |

## 2. M2 acceptance (frozen matrix, D26 A)

| Part | Result | Evidence (`artifacts/s2/…`) |
| --- | --- | --- |
| Ten consecutive healthy unattended episodes | **Pass.** 10/10 healthy, longest run 10, no recovery action. Lap times 122.9–123.8 s, minimum clearance 0.103–0.106 m. Wall time 1,567 s (cap 2,700 s). | `20261015T092708Z-m2-acceptance-10lap-d27-rerun/` (`m2check-batch10.json`) |
| Five timing windows | **Pass** on all 10 episodes: observation age ≤ 345 ms (budget 400), clock bound ≤ 42 ms (100), generation → guard accept ≤ 196 ms (300) | same |
| Each F2 case three times | **Pass.** Every case has three passing repetitions. Stops 0.35–0.96 s and 0.04–0.22 m from onset (limits 1.5 s, 0.40 m). Every detection is inside its D25 deadline. F2-9 and F2-10 are recorded as containment. | `20261015T120528Z-m2-acceptance-f2x3/` (28/30); `20261015T140518Z-d28-d29-checks-reruns/` (F2-6, F2-10 reruns) |
| Replay ×3 fresh processes per fixture | **Exact on every fixture:** 3 analytical fixtures (identical reports); stationary recording, 258/258 snapshots; 10-episode batch recording, 3,324 + 3,335 + 1,667 snapshots and 5,561 + 5,572 + 2,782 controller commands | `20261015T140518Z-…/acceptance-fixtures-*.json`, `stationary-replay-*.json`; `20261015T092708Z-…/s0*-replay-*.json` |

**Plan acceptance clause, checked one by one:**
- **Batch initialization and termination pass:** every episode was initialized by the automated checks, and every cleanup reaped all owned processes.
- **All expected fault outcomes pass:** §2 above.
- **No old command is reapplied after a reset, reconnect or re-arm:** `stale-epoch` rejection at every re-arm, and nothing applied after the lease cleared (F2-6).
- **Recorded-input regression passes without a closed-loop claim:** every replay report says "open-loop".
- **Approved measured budgets are met:** D25.
- **Healthy batches run unattended with the required sensors in a qualified graphical session** (R2-05): the `:1` desktop qualified in PRE-04, all sensors recorded in every episode.

## 3. Decisions taken during S2

| Decision | Choice |
| --- | --- |
| D20 | A: one player per batch, GUI Reset between episodes |
| D21 | A: automated pre-Connect check plus readiness checks |
| D22 | unattended batches inside the unchanged M6 envelope |
| D23 | F2 catalog as proposed |
| D24 | exact replay equality, ×3 fresh processes |
| D25 | S2 budgets |
| D26 | A: strict 10-episode rule; F2 ×3; five windows; replay ×3 |
| D27 | A: planned fresh player every 4 episodes (keeps each guard trace under its 256 MiB cap) |
| D28 | A: runner heartbeats from a thread gated on main-loop progress |
| D29 | A: the shutdown hang stays a failure; cleanup stops the bridge before the player |

**Deviation from the proposal, already reported:** F2-4 ends the episode and the next one starts after a GUI Reset, instead of re-arming within the same episode. Process faults recover with a fresh player ([S2 §6](S2.md)).

## 4. What is not waived

All of these are retained with their evidence and causes.

| Attempt | Outcome | Cause, and fix before the next run |
| --- | --- | --- |
| Baseline 3-lap batch (§4) | 1/3 healthy | supervisor speed loop not restarted after a Reset; fixed |
| Baseline rerun (§5) | 2/3 | genuine simulator stall, contained |
| Baseline parts halted (§7–§8) | not run | the shared desktop and the Activities overview held the input grab; detection added |
| 10-episode batch, 12 Oct, twice (§11–§12) | 9/10 each | the 256 MiB guard trace cap was misread as a hang; fixed by disconnect-based Reset confirmation, then D27 |
| 10-episode batch, 14 Oct (§13) | 9/10 | readiness rejected an exact spawn (a falsy-zero bug); fixed |
| F2 ×3, r1 F2-6 (§15) | fail | player deadlock at quit; D29 |
| F2 ×3, r2 F2-10 (§15) | fail | about 0.5 s runner-loop stall expired the runner lease; D28 |

**Corrections on record:**
- An early claim of about 125 s of feedback starvation after a Reset was wrong (§3).
- Two "simulator stalls" were really the guard trace cap (§12). The revised rate of genuine stalls is about 1 in 50 laps.

## 5. Open issues carried forward

1. **Player shutdown hang** (vendor deadlock at quit). It occurred 4/27 in S1 and 1/30 batches in F2 ×3; none in the five runner cleanups since D29. It stays counted as a failure, and later runs keep recording whether it recurs.
2. **Genuine simulator stall,** about 1 in 50 laps. It is contained by the watchdog (never a stop) and recovered with a fresh player.
3. **Shared desktop.** The simulator renders on your working desktop `:1`. Any mouse, keyboard or overview activity during a run makes the GUI clicks refuse (safely). A separate qualified display (option C, R2-05) was not adopted.

The simulator itself stays frozen at patch 04 (D18).

## 6. Review requested

The original todos changed in text only: S2-01 to S2-06 now say "delivered; awaiting review" and link here. **I recommend you accept these boxes:**

| Box | Basis |
| --- | --- |
| S2-01, S2-02, S2-03, S2-04, S2-05 | §1 |
| S2-06 | §2 |

**If accepted:**
- the original plan goes from **10/34 to 16/34** (PRE, S1 and S2 complete);
- the amendment stays at 10/10.

**The next stage would be S3** (B: known-map driving with reused/extended ICP). It needs your entry confirmation, and its dependency "suitable scene/map/observations and the permitted initialization envelope qualified" (five initial poses) is still open from PRE-B09.

## 7. Checks

- **Tests:** 183 script tests and 48 plugin tests pass.
- **Player:** 604 files unchanged after every S2 run.
- **Code:** at `cee2763` for the last runs.
- **Last evidence directory:** a 238-file manifest.
