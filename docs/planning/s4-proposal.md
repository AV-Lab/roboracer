# S4 proposal — static-obstacle response

Version **0.1, 2026-10-28**; **D54 A decided 2026-10-29** ("D54 A，用虚拟障碍物"); D55–D60 open. Entry: S3 accepted ("accept S3-01 to S3-07"), then S4 entry approved ("批准", approve). **No motion is proposed in this document.** Every motion run will need its own approval, as before.

**S4 goal (plan):**
- B avoids static obstacles where a qualified traversable corridor exists, resumes reference-path progress, and stops predictably when the track is fully blocked.
- Matrix M4: T1/T2/T3 on C0, ten repetitions each with B (30 episodes), plus each F4 case three times.

## 1. The constraint: no obstacles in the frozen simulator

- **No obstacle API.** PRE-B09 found no API in the AutoDRIVE source or payload to place static obstacles ([PRE interface qualification](../stages/PRE-interface-qualification.md)). The C0 scene contains no obstacle objects.
- **No rebuild.** The simulator is frozen at patch 04 (D18). Adding obstacles to the scene would require a rebuild, which D18 excludes.
- **The plan's rule:** "Required unsupported static scenes remain blocked until an alternative or explicit scope revision is agreed." So S4 needs that alternative agreed first: **D54**.

## 2. What is reused (your S3 direction: build on A2RL)

I fetched A2RL `dev`: it moved from `0b5cfa8` to **`fe2fc01`**.
- The new commits add launch presets, YasMarina data and a probe script.
- **None of the files ported in S3 changed,** so the S3 port stays current.

**What A2RL uses for obstacles:**
- **Local planner:** AVLite's `GreedyLatticePlanner`, in tracking mode `selected_local`. In that mode the controller tracks the lattice's selected path (`trajectory_reference_mode = "selected"`).
- **Obstacle list:** copied from the simulator's ground-truth perception model (`execution/executer.py:3757`). S4 forbids this, so the obstacle list must come from scans.

| Part | Source | Reuse in S4 |
| --- | --- | --- |
| Local planner | AVLite `GreedyLatticePlanner` (`c28_local_lattice_planners.py`): lateral-offset lattice, polygon collision check with inflation and safety margin, boundary-violation check, urgent-collision switch | **as-is** (AVLite core, like `LidarLocalization` in S3), with C0-scale parameters |
| Path tracking | A2RL `base_stack_controller.py`: `trajectory_reference_mode = "selected"` branch | **port** into `RacingLineController` with an equivalence test (D31). The S3 port has only the `global` branch. |
| Obstacle detection | AVLite `FastBEVLidarDetection` (`c15_perception_algs.py`): ordered 2D scan → gap segmentation → rotating-calipers rectangle, in map frame | **as-is**, after removing scan points that match the S3 ICP wall map (walls are not obstacles) |
| Obstacle model | AVLite `PerceptionModel.static_obstacles` | as-is; filled only from the detector |
| Localization | S3 `MapIcpLocalization` | unchanged; obstacle returns are outliers to the wall map, and their effect on ICP validity is checked offline first |

**This also closes the S3-03 deviation:** the lattice planner enters the driving stack in S4 ([S3 completion §5.1](../stages/S3-completion.md)).

## 3. Scenario geometry on C0

From the committed plan's bounds:
- the straights are only **1.2–1.3 m** wide;
- the opening straight widens to **1.5–1.8 m at s ≈ 6.5–8.5 m** (heading change < 0.05 rad per metre);
- the corners reach 2.0–2.5 m.

The car's footprint is about 0.3 m wide. A passable corridor needs that plus a margin on each side, so the pass cases go on the s ≈ 6.5–8.5 m stretch.

| Case | Obstacle | Expected outcome |
| --- | --- | --- |
| **T1 left pass** | 0.25 × 0.25 m box at s = 7.5 m, centred 0.45 m right of the racing line (edges about 0.89 m left and 0.90 m right) | pass on the left, through a gap of about 1.2 m; the right gap of about 0.33 m is below the about 0.5 m needed (car plus 0.10 m each side), so only one corridor exists; resume the line; complete the lap |
| **T2 right pass** | the same box, 0.45 m left of the line | pass on the right (mirror of T1); complete the lap |
| **T3 fully blocked** | a barrier across the full width at s = 5.0 m (width 1.34 m) | stop before it, with the whole footprint at least 0.30 m away; stay stopped; no lap expected |

The exact positions are fixed after the offline check (§6, step 1). Each case's geometry is a committed fixture file with a sha256, recorded in every run.

## 4. Decisions requested

- **D54 — obstacle source — decided A (2026-10-29):**
  - **A (recommended): virtual static obstacles at the sensor boundary.**
    - A fixture in the bridge, outside the driving stack, shortens each LiDAR beam to the first hit on the fixture's obstacle polygons. The ray-cast uses the simulator pose of the same snapshot, as a simulated sensor would.
    - The driving stack sees only the modified scan. It never sees the obstacle geometry, and S3's truth-isolation proof is extended to cover this.
    - The independent scorer checks the car's footprint against the same polygons. **Contact is a scored overlap, not a physical collision:** the car would pass through a virtual box. This is labelled in every result.
    - Error from the scan/pose skew of about 0.04 s: about 0.02 m at 0.5 m/s.
  - **B: offline only.** Recorded scans with virtual obstacles, open-loop, plus the kinematic closed-loop check. No live S4 runs. This rescopes S4 acceptance.

  Physical obstacles would need a simulator rebuild, which D18 excludes; I am not proposing that.
- **D55 — scenarios:** T1, T2 and T3 as in §3, with positions finalized by the offline check.
- **D56 — obstacle perception (S4-01):**
  - Scan points within 0.05 m of the S3 wall map are removed.
  - AVLite `FastBEVLidarDetection` runs on the rest, at C0 scale.
  - **Quality:** a cluster needs at least 4 points and must be confirmed on 2 consecutive scans.
  - **Freshness:** the obstacle list is stamped with its scan time. If it is older than 0.5 s, the stack stops, under the same rule as S3's localization staleness.
- **D57 — planning and tracking (S4-02):**
  - AVLite `GreedyLatticePlanner` with C0 parameters. The obstacle inflation is half the car width plus 0.10 m.
  - The controller tracks the selected path (A2RL `selected_local` mode, ported).
  - A whole-footprint clearance check runs on the selected path before it is used.
- **D58 — blocked track and planning failure:**
  - **Trigger:** no collision-free, in-bounds lattice edge, or the planner errors or misses its deadline.
  - **Response:** target speed 0, latched until rearm. It is reported as a "blocked" outcome, scored independently of lap completion.
- **D59 — speed:** the V1 envelope on ICP (0.5 m/s) with its accepted stop criteria. A higher speed would be a separate step.
- **D60 — F4 cases, each three times:**
  - **F4-1** blocked path (T3 geometry, separate from the matrix);
  - **F4-2** stale obstacle observation (scans freeze with an obstacle ahead);
  - **F4-3** planning failure (an injected planner fault).

  Each stops within the V1 stop criteria, and nothing is applied after the stop.

## 5. What is not changed

These stay as accepted in S3:
- the supervisor, guard and speed loop;
- the ICP localizer and the wall map;
- truth isolation;
- the frozen player.

A remains reactive gap-follow and is not part of the S4 matrix (the plan's M4 is B only).

## 6. Order of work (after D54–D60)

1. **Offline, no motion:**
   - add virtual obstacles to recorded S3 laps and run detection, ICP validity and the lattice choice open-loop;
   - run the kinematic closed-loop check of T1, T2 and T3 with the measured timing;
   - port the selected-path branch, with equivalence tests;
   - fix the positions.
2. **Stationary live check:** a fixture in front of the parked car; detection and the planner's choice are logged. No motion.
3. **Run approvals, in order:**
   - first T1, T2 and T3 once each;
   - then the M4 baseline (S4-05) and its proposed thresholds;
   - then the frozen M4 matrix, 30 episodes plus F4 ×3 (S4-06).
