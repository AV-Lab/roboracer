# S4 — Completion report and stage review

Date: **2026-11-01**. Running report with every run: [S4.md](S4.md). Proposals:
- [s4-proposal.md v0.1](../planning/s4-proposal.md) (D54–D60)
- [s4-acceptance-proposal.md v0.1](../planning/s4-acceptance-proposal.md) (D66–D68)

Decisions D54–D68: [approval record](../planning/s1-motion-approval.json). Backend: the frozen patch-04 player (D18), unchanged after every S4 run. A2RL source: `dev` `fe2fc01`; the files ported in S3 are unchanged since `0b5cfa8`.

**S4 goal (plan):** B avoids static obstacles where a qualified traversable corridor exists, resumes reference-path progress, and stops predictably when the track is fully blocked.

## Summary

- **All six S4 items are delivered,** and the frozen M4 acceptance matrix (D66–D68) has passed:
  - **T1/T2/T3 × 10: 30/30** on U1–U7;
  - **F4-1/2/3 × 3: 9/9.**
- **Obstacles are virtual (D54 A).** The frozen player has no obstacle objects and no placement API. A bridge fixture ray-casts them into the LiDAR scan, and the independent scorer checks footprint overlap with the same polygons. "Contact" is therefore a scored overlap, not a physical collision. Every result carries this label.
- **The stack is reused, not rebuilt:**
  - AVLite's `FastBEVLidarDetection`, with wall-map subtraction;
  - AVLite's `GreedyLatticePlanner`, at C0 scale;
  - A2RL's `selected_local` tracking, ported and equivalence-tested;
  - S3's map ICP, with an obstacle mask (D61);
  - S3's supervisor and guard, unchanged.
- **Driving outputs are truth-isolated.** With a fixture, the truth left on each snapshot (IPS pose, IMU) was perturbed after the fixture was applied, and B's outputs stayed bit-identical.
- **No failure is waived.** Six failed attempts are retained with their causes (§4). Four of them were my own integration defects, each found from the run logs and fixed before the next approved run.
- **Two deviations need your view at review:** §5.1 (the footprint check) and §5.2 (S4-03 wording).
- **Stage review: accepted 2026-11-01** ("accept, go ahead S5"). All boxes are ticked, S4-02 and S4-03 worded per §5.1 and §5.2: **S4 is complete**; the original plan is at 29/34.

## 1. S4 items

| Item | Delivered | Evidence |
| --- | --- | --- |
| **S4-01** scan-derived obstacles | `ScanObstacleDetection`: scan points within 0.05 m of the validated wall map are removed; then AVLite BEV segmentation and rectangle fitting at C0 scale. A cluster needs ≥ 4 points and confirmation on 2 consecutive scans. Results are stamped; the stage aborts when there is no new result for 0.5 s (D56). Inputs are the scan and the stack's ICP pose only. Truth isolation is proven with a fixture. Offline: 0 phantoms in 1,662 scans; T1/T2 confirmed from 7.4 m. | [S4 §2](S4.md), [§4](S4.md), [§6](S4.md) |
| **S4-02** corridor-constrained avoidance and blocked stop | `C0LatticePlanner`: AVLite's lattice with listed C0 settings (2 m edges; corridor of half the car width + 0.10 m; deterministic sampling; C0 ego box) and B in A2RL `selected` mode. **D58:** two consecutive replans with no collision-free in-bounds edge, or a planner error, latch "blocked" (target 0) until rearm. **D61:** ICP ignores confirmed obstacles. **D65:** B's yaw-error safe stop is 0.35 rad (A2RL's validated value). | [S4 §3](S4.md), [§6](S4.md), [§19](S4.md) |
| **S4-03** fixtures | T1/T2 (0.25 m box 0.30 m off the line; one passable side) and T3 (full-width barrier). Each is a hash-checked fixture built by a script with gap checks against the drivable region. Each run records the fixture's path and sha256. The scorer reads the same fixture independently. | [S4 §2](S4.md), [§6](S4.md) |
| **S4-04** demonstration | Passing T1/T2; stopping at T3; controlled rearm (blocked ×3: re-latches with 0 m creep; cleared ×3: completes the lap; all of F1-5's guard checks); stale input F4-2 ×3; planning failure F4-3 ×3; blocked path F4-1 ×3. | [S4 §9](S4.md), [§12](S4.md), [§15](S4.md) |
| **S4-05** baseline and criteria | M4 baseline T1/T2/T3 × 3. The first baseline exposed the yaw-error safe-stop margin (D65). After D65 the rerun passed 9/9, with costs reported. Criteria U1–U7 were proposed from it and confirmed before acceptance. | [S4 §18](S4.md), [§20](S4.md), [proposal](../planning/s4-acceptance-proposal.md) |
| **S4-06** acceptance matrix | §2 below | [S4 §22–§23](S4.md) |

## 2. M4 acceptance (frozen D66–D68)

Evidence: `artifacts/s4/20261101T083922Z-m4-acceptance-rerun/` (1,338-file manifest). Code `95b9e28`. Unattended; player unchanged.

| Item | Result | Worst value against its criterion |
| --- | --- | --- |
| T1 × 10 | **10/10** | obstacle 0.352 m (≥ 0.25); wall 0.291 m (≥ 0.20); lap 68.9 s (≤ 72); ICP max 0.107 m (≤ 0.15); tick 56 ms (≤ 80) |
| T2 × 10 | **10/10** | obstacle 0.388 m; wall 0.270 m; lap 69.1 s; ICP max 0.097 m; tick 60 ms |
| T3 × 10 | **10/10** | at rest 1.416 m (≥ 1.0); wall 0.345 m |
| F4-1 × 3 | 3/3 | at rest ≥ 1.405 m |
| F4-2 × 3 | 3/3 | rest ≤ 1.29 s (≤ 1.7), travel ≤ 0.49 m (≤ 0.65) |
| F4-3 × 3 | 3/3 | rest ≤ 0.73 s, travel ≤ 0.20 m |

- **Contact:** none in any run, wall or obstacle; ICP was valid on every driving tick.
- **Peak heading error:** at most 0.204 rad (reported; the safe stop is at 0.35 rad).

**Plan acceptance clause, checked one by one:**
- **Analytical clearance and fault cases pass:**
  - the fixture gap checks;
  - the scorer and fixture unit tests;
  - F4 × 3 in the matrix.
- **The agreed static-obstacle matrix passes:** 30/30.
- **A blocked-track stop is scored independently of lap completion:** the T3 outcome is "blocked", judged by U1/U4, with no lap requirement.
- **Unsupported static scenes:** physical obstacles in the frozen player are unsupported. The agreed alternative is D54 A (virtual obstacles). This is recorded as a scope decision, not a physical-obstacle claim.
- **Dynamic obstacles and multi-car:** not required and not claimed.

## 3. Decisions taken during S4

| | Choice |
| --- | --- |
| D54 | A: virtual static obstacles at the sensor boundary |
| D55 | T1/T2/T3 scenarios (T1/T2 offset later changed by D62) |
| D56 | scan detection with wall subtraction, 2-scan confirmation, 0.5 s freshness |
| D57 | AVLite lattice with C0 settings; A2RL `selected` tracking |
| D58 | latched blocked stop until rearm |
| D59 | V1 envelope on ICP |
| D60 | F4-1/2/3 |
| D61 | A: ICP ignores confirmed obstacles |
| D62 | B: T1/T2 box 0.30 m off the line (the line is blocked) |
| D63 | A: rearm in the same episode |
| D64 | M4 baseline T1/T2/T3 × 3 |
| D65 | A: yaw-error safe stop 0.35 rad on `s4` |
| D66–D68 | U1–U7; 30 episodes + F4 × 3; strict |

## 4. What is not waived

| Attempt | Outcome | Cause, and fix before the next approved run |
| --- | --- | --- |
| First live T1 (§8) | "blocked" at the run start; never moved | lattice latched before localization; reset at run start (mine) |
| Rearm-blocked 1 (§14) | guard check "no rejection" failed; behaviour correct | `--s4-rearm` not passed to the bridge child (mine) |
| Baseline T2 r1, r2 (§18) | yaw-error safe stop after the pass (r1 then ICP loss and abort; r2 no lap) | 0.2 rad threshold with ~0 margin; D65 |
| Acceptance attempt 1 (§22): T1 ×2, F4-2 ×1, F4-3 ×1 | "blocked" at the run start | stale pre-localization detections; detector reset at run start (mine; completes the §8 fix) |

**Corrections on record:**
- the shadow-B start in the stationary check (§4);
- the weak negative control in the first isolation tool (§4);
- the detector edge-on threshold (§4);
- the pinned approval-record test (§8).

## 5. Deviations and limits to note at review

### 5.1 "Whole-footprint clearance checking" (S4-02, D57)

D57 said a whole-footprint check runs on the selected path before use. **No separate check was added.** The clearance check is AVLite's own corridor test on every lattice edge:
- the path is buffered by half the C0 car width + 0.10 m;
- it is extended by half the car length at both ends;
- edges intersecting an obstacle, or leaving the bounds minus the same clearance, are rejected.

This sweeps the whole footprint along the path. The independent scorer checks the real footprint every frame, and no acceptance run had contact. If you want a separate, explicit footprint check on the selected path, it is a small addition, but it would need a re-run.

### 5.2 S4-03 "through the shared scenario interface"

The fixtures are configured through `--obstacle-fixture` on the runner and the episode entrypoint. That is the same interface as every other stage option, recorded in each run's provenance. **They are virtual obstacles (D54 A),** not simulator scene objects.

### 5.3 Other limits

- **Speed:** V1 only (0.5 m/s), on ICP.
- **Obstacle near a wall:** before D61, ICP was biased at a degenerate spot. D61 fixes this for *detected* obstacles. An undetected obstacle near a wall would still bias ICP.
- **Heading-error margin:** about 0.15 rad to the 0.35 rad safe stop at the T1/T2 return manoeuvre. A gentler lattice return was evaluated (§18) but not adopted.
- **Run time:** one T1/T2 episode holds the 235 s guard window, so a 10-episode session takes about 37 minutes.

## 6. Review requested

The S4 boxes in the plan now say "delivered; awaiting review". **I recommend you accept S4-01 to S4-06,** with S4-02 worded per §5.1 and S4-03 per §5.2.

**If accepted:**
- the original plan goes to **29/34** (PRE, S1, S2, S3 and S4 complete);
- the next stage is **S5** (reproducible AutoDRIVE-qualified release). It needs your entry confirmation.

## 7. Checks

- **Tests:** plugin 95/95 and scripts 204/204 (at `95b9e28`).
- **Player:** unchanged after every S4 run.
- **Last evidence directory:** a 1,338-file manifest.
