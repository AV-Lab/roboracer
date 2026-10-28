# S3 — Completion report and stage review

Date: **2026-10-28**. Request: "开始" (start the S3 report and review), after D53 A passed. Running report with every run: [S3.md](S3.md). Proposals:
- [s3-proposal.md v0.2](../planning/s3-proposal.md) (D30–D34)
- [s3-speed-proposal.md](../planning/s3-speed-proposal.md) (D35–D39)
- [s3-speed-v2-proposal.md](../planning/s3-speed-v2-proposal.md) (D40–D43)
- [s3-m3-proposal.md](../planning/s3-m3-proposal.md) (D44–D47)
- [s3-acceptance-proposal.md](../planning/s3-acceptance-proposal.md) (D48–D52)

Decisions: [approval record](../planning/s1-motion-approval.json). Backend: the frozen [patch-04 backend](../architecture/qualified-backend.md), with the player unchanged after every S3 run. Source for the port: AV-Lab/a2rl `dev` `0b5cfa8`.

**S3 goal (plan):** B, known-map driving with reused/extended ICP. Map, ICP, control and truth-isolation contracts pass, and completion, pose/tracking error and resources meet pre-approved criteria within the agreed initialization envelope.

## Summary

- **All seven S3 items are delivered,** and the frozen M3 acceptance matrix (D48–D52) has passed:
  - **B, the gate:** 50/50 episodes pass T1–T8, counting one replacement (D53 A) for a player that started with a blank window and never moved. Laps from the IC took 62.69–63.14 s, minimum clearance 0.314 m, ICP p95 ≤ 0.028 m and ≤ 0.015 rad, no localization loss.
  - **A, the comparator:** 50/50 pass, laps 116.9–120.7 s, clearance 0.102 m.
  - **F3:** 15/15.
- **B drives on scan-matched pose only.** On ICP stages the stack sees LiDAR and wheel odometry. The IPS pose and IMU are withheld, and changing simulator truth leaves B's outputs bit-identical (S3-04, F3-5).
- **B reuses the A2RL stack as directed:** the global planner, min-curvature line, velocity profile and lateral controller with MPC. Each module is ported and **tested exactly equal** to the A2RL originals on shared inputs.
- **Speed:**
  - **On ICP (the S3 results):** V1 at 0.5 m/s, lap about 63 s from the IC, about 47 % faster than A on the same stack.
  - **On IPS bring-up:** V2, 1.0 m/s on straights, lap 44.6 s on the old scorer basis (about 40 s from rest), not yet run on ICP.
- **No failure is waived.** Two failed attempts are retained with their causes (§4), as are two flagged analyses.
- **One deviation from D30's wording needs your view:** AVLite's `GreedyLatticePlanner` is not in the driving stack (§5.1).
- **Review requested** (§7): S3-01 to S3-07. If accepted, the original plan goes from 16/34 to 23/34.

## 1. S3 items

| Item | Delivered | Evidence |
| --- | --- | --- |
| **S3-01** map and ICP target | Matching target from the C0 collider geometry: the walls' inner faces sampled every 2 cm, 3,152 points (`roboracer/data/c0-icp-map.json`), with provenance (sha256, source hash, validation). Validated on 200 recorded scans through the plugin's LiDAR mount: median residual 5.7 mm, 100 % within 5 cm. Negative controls all rejected: yaw sign, y mirror, 5 % scale, 0.10 m shift. So origin, yaw, scan direction, scale and mount are verified. The racing-line plan is also a committed file with provenance, and the runner refuses a mismatch. Tampered maps are refused (F3-4 3/3). | [S3 §2](S3.md), [§4](S3.md), [§9](S3.md), [§17](S3.md) |
| **S3-02** ICP extension | `MapIcpLocalization` extends AVLite's `LidarLocalization`, reusing its ICP loop, rigid fit and squashing unchanged. It adds: the map target; KD-tree correspondences with a 0.3 m limit; configuration initialization with a start-up check; wheel-odometry prediction; per-scan validity (inliers, RMS, correction ≤ 0.05 m, degeneracy); and loss after 3 invalid scans, sticky until reinitialization. Validity is labelled match diagnostics, not covariance. Offline on 5 recorded laps: p95 7.3–8.6 mm, compute p95 ≤ 3.0 ms. Stock against extended, on the same recorded lap: stock scan-to-first-scan gives median 5.1 m error at 56 ms per scan. | [S3 §9](S3.md) |
| **S3-03** B with the A2RL stack | Ported (D31: "参考其代码实现", implement by referencing the A2RL code): `RaceLineGlobalPlanner`, min-curvature line, friction-limited velocity profile, trajectory tracker, A2RL lateral chain and lateral MPC with dead-time roll-forward. Exactly equal to the originals in `test_s3_a2rl_port.py`. The profile's target speed goes to the qualified S1 speed loop. Ego velocity comes from wheel odometry through AVLite's sensor frame. **Lattice local planner not included** (§5.1). Responses to stale or invalid inputs: §5.2. | [S3 §1](S3.md), [§4](S3.md), [§10](S3.md), [§12](S3.md) |
| **S3-04** provenance and truth isolation | `withhold_truth` on ICP stages: the IPS pose is filtered out, the IMU withheld, and only LiDAR and wheel odometry are used. Run status records observation and initialization provenance. Proof: replaying recorded laps with IPS (and the provenance value it is matched by) shifted and the IMU rotated gives **bit-identical** B outputs on 831 / 832 steps. The negative control (B on IPS) changes 790 / 791 commands. | [S3 §13](S3.md), F3-5 in [§17](S3.md) |
| **S3-05** M3 baseline A/B | 10 fresh-process episodes, IC0–IC4 × A/B, alternating, on the same ICP stack with truth withheld. All 10 valid. B 62.84–63.00 s and 0.314–0.317 m; A 117.2–120.7 s and 0.104–0.105 m. Two scorer issues found and corrected: the lap-time basis and a time-matched ICP error. The stock/extended ICP comparison is labelled fixture evidence (S3-02 row). | [S3 §14–§16](S3.md) |
| **S3-06** thresholds | T1–T8 proposed from the baseline with margin. D49 makes the approach gentler. All confirmed (D48–D52) before the matrix ran. | [S3 §16–§17](S3.md), [proposal](../planning/s3-acceptance-proposal.md) |
| **S3-07** M3 acceptance | §2 below | [S3 §18](S3.md) |

## 2. M3 acceptance (frozen matrix, D48–D52)

Evidence: `artifacts/s3/20261026T141945Z-m3-acceptance/` (3,772-file manifest; `m3-acceptance-all.json`, per-IC `m3/m3-ic*.json`, `m3/ic0-r07-b-rerun1-m3.json`, `f3/`). Code `a33270a` for the sessions and `537f86c` for the replacement, with no change under `roboracer/` or `scripts/` between them.

| Threshold (D48) | A (comparator), 50 episodes | **B (gates), 50 episodes** |
| --- | --- | --- |
| T1 ICP valid ≥ 99 %, no loss | pass, 0 losses | **pass, 0 losses** |
| T2 position error p95 ≤ 0.05 m, max ≤ 0.10 m (time-matched) | worst 0.012 / 0.035 m | **worst 0.028 / 0.042 m** |
| T3 yaw error p95 ≤ 0.03 rad, max ≤ 0.06 rad | worst 0.011 / 0.025 rad | **worst 0.015 / 0.029 rad** |
| T4 ICP compute p95 ≤ 10 ms, max ≤ 50 ms | worst 3.6 / 15.9 ms | **worst 4.8 / 19.8 ms** |
| T5 valid lap, no contact, off-track or abort | 50/50 | **50/50** |
| T6 B clearance ≥ 0.20 m | (0.102 m, reported only) | **0.314 m** |
| T7 B lap from the IC ≤ 66 s | (116.9–120.7 s) | **62.69–63.14 s** |
| T8 IC within 0.10 m and 5° | max 0.037 m | **max 0.037 m** |
| **Episodes passing T1–T8** | **50/50** | **50/50** (49 in the sessions + 1 replacement, D53 A) |

**F3 (D50), each three times, 15/15:**
- **F3-1** LiDAR freeze: rest 1.03–1.09 s, travel 0.35–0.40 m (limits 1.7 s, 0.65 m).
- **F3-2** heading 0.3 rad off: start-up check rejected, no motion.
- **F3-3** 0.5 m along-track: loss declared, stop 0.73–0.81 s and 0.17–0.20 m after the loss, no contact.
- **F3-4** invalid map: refused.
- **F3-5** forbidden truth: bit-identical outputs.

**Plan acceptance clause, checked one by one:**
- **Map, ICP and control contracts pass:** §1, S3-01 to S3-03.
- **Truth isolation passes:** S3-04 and F3-5.
- **Completion, pose/tracking error and resource budgets meet pre-approved criteria within the agreed initialization envelope:** T1–T8 across all five ICs. They were frozen before the run and not adjusted afterwards.
- **Detectable initialization, overlap and match faults produce the specified state and control inhibition:**
  - F3-2 is rejected at start-up.
  - F3-3 and F3-1 are declared lost or stale, and the car stops.
- **Stale or invalid motion inputs:** §5.2.
- **Geometrically ambiguous wrong matches are an evaluated limitation, not a claim:**
  - At the spawn, along-track position is reported "unobservable".
  - A 0.2 m along-track error is corrected at the first corner; 0.5 m is detected as a loss (F3-3).
  - No universal global-pose validation is claimed.
- **Detected loss ends the episode as a failure; driving stays inhibited until reinitialization:** the loss is sticky, and the stage aborts (F3-3).
- **Missing truth, map coverage or thresholds blocks acceptance:** none was missing.

**Randomness:**
- The plugin is deterministic on identical inputs: replay is bit-identical (S3-04).
- The player exposes no seed. Its uncontrolled variation shows up as B's lap spread of 0.45 s and A's of 3.8 s across the 100 episodes.
- No seed was recorded, because none exists to record.

## 3. Decisions taken during S3

| Decision | Choice |
| --- | --- |
| D30 | S3-03 is the A2RL planning and control stack, not plain Pure Pursuit |
| D31 | port by referencing the A2RL code, with equivalence tests (not vendored) |
| D32 | A (my choice; you deferred): bring-up on IPS, labelled; every S3 result on ICP |
| D33 | faster is better: staged speed steps, each with its own evidence |
| D34 | yes: initial conditions reached by a scripted approach and checked |
| D35–D38 | V1 0.5 m/s: envelope, stop criteria (rest ≤ 1.5 s, travel ≤ 0.65 m), run set |
| D39 | B: for speed steps, rest ≤ 1.5 s plus one frame (≤ 1.7 s); travel stays binding |
| D40–D43 | V2: 1.0 m/s straights, fault-bounded corners, `u_max` 0.24, travel ≤ 1.3 m and rest ≤ 2.0 s, run set |
| D44–D47 | M3: five ICs on B's line, ±0.10 m and ±5°; A = A-lap gap-follow on the same ICP stack; 10-episode baseline; V1 speed |
| D48–D52 | T1–T8; gentler approach; F3-1 to F3-5 ×3; 100 episodes in five sessions; strict on B |
| D53 | A: one replacement B episode for the blank-window start |

## 4. What is not waived

All of these are retained with their evidence and causes.

| Attempt | Outcome | Cause, and what followed |
| --- | --- | --- |
| V1 F1-7 trial 2 (§6) | fail, rest 1.512 s against 1.5 s (travel 0.532 m, inside 0.65 m) | The chain of two 0.5 s leases plus braking leaves about one telemetry frame of margin. Retained under D37; V1 completed under D39 B with three fresh F1-7 passes. |
| M3 acceptance `ic0-r07-b` (§18) | fail, the car never moved | The player started with a blank window, the pre-Connect check refused, and the player needed SIGKILL at cleanup. It was the only start failure in 110 player starts. Replacement passed (D53 A). |

**Flagged analyses, kept alongside their corrections:**
- **m3c-1 plateau rule:** at 0.5–0.6 m/s the car settles over two frames. Re-analysed from 0.4 s, no run repeated (§6).
- **ICP error per tick:** the per-tick figure compared against the latest IPS sample. It was replaced by the time-matched error before the thresholds were proposed (§16).

**Corrections on record:**
- **Lap-time basis:** every S1–S3 lap time from the whole-run scorer includes about 4.6 s of standing still. Comparisons between them hold; M3 counts from the IC (§15).
- **My own tool defects, fixed before any affected result was used:**
  - the ray-cast bias at shallow wall angles;
  - side-wall beams counted in the forward check;
  - no facing beams at the spawn;
  - the falsy-zero stamp;
  - a stale "valid" status that hid a frozen LiDAR;
  - an IPS-only perturbation in the first isolation proof;
  - the IC approach overshoot (0.091 m, fixed by D49).

## 5. Deviations and limits to note at review

### 5.1 No lattice local planner in the driving stack

- **What D30 said:** `GreedyLatticePlanner` was part of the A2RL stack named in D30.
- **What runs instead:** B runs with no local planner. `RacingLineController` tracks the global line directly, as A2RL does in its `legacy` tracking mode, where the lattice does not set the tracked path ([proposal §2](../planning/s3-proposal.md)).
- **When it was recorded:** at bring-up ([S3 §4](S3.md)).
- **What it means:** on a known track without obstacles, the lattice adds nothing to the driven path. Its corridor selection is the S4 avoidance base.
- **Recommendation:** accept S3-03 with the plan text amended to "lattice local planner deferred to S4". Alternatively, ask me to add it now and rerun a B check. That would be new motion.

### 5.2 Stale or invalid inputs: what S3 showed and what it inherits

| Input | Response | Evidence |
| --- | --- | --- |
| Localization stale, lost or wrong at start | abort and stop; start-up rejection | F1-1 ×3 on `s3v1i`, F3-1 to F3-3 ×3 |
| Path data invalid | a plan file that does not match its provenance hash is refused; the runner refuses to start if the global planner and the controller hold different plans; B's tracking safe stop latches until reset | `test_tampered_plan_is_refused` (`test_s3_stage.py`), the runner check in `autodrive_neutral.py`, safe-stop equivalence in `test_s3_a2rl_port.py` (no motion; no lap reached a safe stop) |
| Velocity (speed feedback) stale | supervisor speed loop goes to zero, then inhibits | **inherited, not re-run with B:** S1 M4 feedback blackout and the S2 stale-speed-feedback F2 case. The speed loop and supervisor are unchanged in S3. |

### 5.3 Other limits

- **V2 (1.0 m/s) was run only on IPS bring-up.** Every S3 result on ICP is at V1, 0.5 m/s. V2 on ICP would need its own run approval.
- **Along-track position is unobservable at the spawn** (§2). The spawn rests on configuration, and the scene reload reproduced it to within 0.001 m in every S2 episode.
- **The ICP map and the scorer share a source:** both come from the C0 collider geometry. The map was validated independently against recorded scans, but it is not an independent survey.

## 6. Open issues carried forward

1. **Player start and shutdown faults.** In S3: one blank-window start in 110 starts, and SIGKILL needed at that cleanup. Both are counted as failures where they occur.
2. **Shared desktop `:1`.** User activity, the Activities overview or a screen lock makes runs wait or refuse. Three times in S3 the desktop needed your action: Chrome was closed, one Escape was sent, and the desktop was unlocked before the M3 baseline.
3. **Kinematic model optimistic at V2,** by about 18 %. Not investigated.
4. **Run time:** each episode holds its full 320 s guard window, so a 20-episode session takes about 1 h 55 min.

The simulator stays frozen at patch 04 (D18).

## 7. Review requested

The S3 boxes in the plan now say "delivered; awaiting review" and link here. **I recommend you accept these boxes:**

| Box | Basis |
| --- | --- |
| S3-01, S3-02, S3-04, S3-05, S3-06 | §1 |
| S3-03 | §1, with the §5.1 wording change (lattice deferred to S4) |
| S3-07 | §2 |

**If accepted:**
- the original plan goes from **16/34 to 23/34** (PRE, S1, S2 and S3 complete);
- the amendment stays at 10/10.

**The next stage would be S4** (static obstacles: corridor-constrained avoidance and blocked-path stop). It needs your entry confirmation. Its dependency "exact supported static-obstacle scenes qualified" is open. With the simulator frozen (D18), obstacle scenes need a decision of their own.

## 8. Checks

- **Tests:** plugin suite 76/76 and script suite 191/191 pass (run 2026-10-28 at `ea7d81b`).
- **Player:** unchanged after every S3 run, including the D53 replacement.
- **Code:** `a33270a` for the acceptance sessions; the replacement at `537f86c` with no code change in between.
- **Last evidence directory:** a 3,772-file manifest.
