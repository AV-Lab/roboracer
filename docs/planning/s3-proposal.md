# S3 proposal — B: known-map driving on the A2RL planning and control stack

Version **0.2 — decisions recorded 2026-10-22**: "D30. yes D31 参考其代码实现 D32这个我无法回答 D33速度肯定是越快越好 D34 yes" ([record](s1-motion-approval.json); outcome in §7). Entry: S2 accepted ("accept S2-01 to S2-06"). **Your direction for S3:** build on the A2RL plugin's global planner, local planner and control, which are validated in Autoverse, and do not develop RoboRacer planning or control from scratch.

**Nothing here authorizes motion.** Decisions D30–D34 are requested in §6.

## 1. Source read

- **Repository:** `AV-Lab/a2rl` (the AVLite community plugin), branch `dev`.
  - Fetched 2026-10-22: `origin/dev` moved `ae5436d` → **`0b5cfa8`** (24 new commits, from "completed a lap in 78s" to stage 15C).
  - Read from a clean export (`~/roboracer-work/a2rl-dev-0b5cfa8`, `SOURCE_COMMIT`).
  - Your checkout `~/avlite/community_plugins/a2rl` has uncommitted local changes in 20 files. It was only fetched, never pulled or modified.
- **Validated performance:**
  - Stage 15C ran 5 laps with a mean flying lap of **62.72 s** (best 62.66 s), commit message of `0b5cfa8`.
  - The best recorded lap is 57.85 s (YasMarina North, about 3 km, up to 38.6 m/s; `docs/a2rl_autoverse_optimization_summary_report.md`).
- **Validated stack** (profile `a2rl_can`): `RaceGlobalPlanner` → AVLite `GreedyLatticePlanner` → `A2RLBaseStackController`, on ground-truth localization. The latest presets drive with the lateral MPC applied (delay 0.14 s, understeer gradient 0.001 s²/m).
- **Compatibility:** every AVLite module the reused files import exists in our pinned AVLite `c8b0ce1` (`c51_capabilities`, `c54_trajectory_tracker`, `GreedyLatticePlanner`, `GlobalPlan`, `ControlComand`).

## 2. What is reused, and how

| A2RL component | What it does | Reuse in S3 |
| --- | --- | --- |
| **Global planner:** `planning/strategies.py` `RaceGlobalPlanner` | serves the offline race trajectory as the AVLite global plan | **as-is** |
| `planning/racing_line.py` `generate_min_curvature_racing_line_candidate` | min-curvature line: bounded L-BFGS-B over normal offsets within the bounds less a margin, optional curvature reweighting, pinned offsets (e.g. the start) | **as-is**, run offline on the C0 reference. Only parameters change: margin and the lap-length checks of its YasMarina validator. |
| `planning/velocity_profile.py` `build_friction_limited_velocity_profile` | curvature envelope plus forward-backward lateral, brake and accel limits; optional friction ellipse and peak-curvature limit | **as-is** (pure Python). C0 configuration; the YasMarina per-distance caps and floors are left empty. |
| `planning/track_inspection.py` | geometry report (curvature, width) | **as-is** |
| **Local planner:** AVLite `GreedyLatticePlanner` | short-horizon lattice in the validated profile; with tracking mode `legacy` the controller tracks the global line | **as-is**, same mode as A2RL. Its corridor selection becomes the S4 avoidance base. |
| `planning/trajectory_tracker.py` | KD-tree s/d projection on closed laps | **as-is** |
| **Control:** `control/base_stack_controller.py`, lateral chain | steering = atan(L·κ_ff) − k·(e_y + L_yaw·(e_ψ + l_r·κ)), curvature preview, preview pure-pursuit blend, steer-excess limit, tracking safe stop | **as-is** code, with **C0 parameters** (§3) |
| `control/lateral_mpc.py` `LateralMpc` | kinematic LTV MPC on [e_y, e_ψ, δ] with steering lag and dead-time roll-forward; closed form, numpy only | **as-is**, `apply` mode as in the latest presets. The dead-time compensation is the key fit for our ~0.3 s observation age (§3). |
| `control/base_stack_controller.py`, longitudinal chain | force → throttle and brake % through the EAV24 engine map, gears and resistance | **not applicable**: our actuator is a single throttle in [−1, 1] with K = 5.02 m/s per unit (S1 M3b). The **target speed from the A2RL velocity profile** goes to our qualified speed loop (S1 D5 v0.3, supervisor) instead. |
| `integration/*`, `execution/*`, `activation.py` presets, CAN/ROS/Autoverse scripts | Autoverse/EAV24 transport, launch and tuning presets | **not reused**: the qualified AutoDRIVE bridge, supervisor and guard stay |
| `AutoVerseGroundTruthLocalization` | ground-truth pose | **not reused**: the S3 plan requires scan matching to the map (ICP), with no privileged pose in the driving stack |

**How the code is brought in (D31 A):**
- The reused files are vendored **unmodified** from `0b5cfa8` into `roboracer/vendor/a2rl/`, with a provenance file (commit and per-file sha256). A test fails if any vendored file changes.
- RoboRacer-specific behaviour lives only in an adapter (`roboracer/planning/a2rl_adapter.py`). The adapter builds the C0 plan, sets the controller configuration and maps its steering output and the profile's target speed onto our command path.

## 3. Scale and timing: what must change between Autoverse and AutoDRIVE

| Quantity | A2RL / Autoverse | RoboRacer C0 (measured) | Consequence |
| --- | --- | --- | --- |
| Track | YasMarina North, about 3 km | Proto Track, 31.3 m, width 1.14–2.55 m | Racing-line margin ≈ footprint half-width 0.15 m + 0.15 m |
| Vehicle | EAV24, wheelbase 3.1 m, steer ≤ 0.342 rad | F1TENTH, wheelbase 0.324 m, track 0.236 m, steer ≤ 30° (0.524 rad), slew 183°/s | `wheelbase_m`, `max_wheel_angle_rad`, `mpc_steer_lag_s` (≈ 0.08 s from the slew) |
| Pose | ground truth at 250 Hz, about 0.1 s old | scan-matched pose on ~5.6 Hz scans, observation age ≤ 345 ms at request | `mpc_delay_s` ≈ 0.3 s; speed bounded by dead-time travel (§4) |
| Control period | 0.01 s | AVLite tick 0.1 s; a new observation every ~0.18 s (median frame interval, S2 recovery lap) | MPC `dt_s` = 0.1 with about 15 steps (1.5 s preview) |
| Longitudinal | force and gear model | throttle-only, identified gain, bounded speed loop | profile target speed → existing speed loop |
| Safe-stop thresholds | 2.5 m lateral, 0.2 rad yaw, above 7 m/s | must scale to the track | lateral ≈ 0.25 m, active at all speeds; tied to the guard abort |

Gains (`kp_steer_fb`, `lookahead_distance_yaw_m`, MPC weights) are **re-identified**, not re-designed, using the same procedure the A2RL stages used: shadow mode first, then apply.

## 4. Plan changes this needs

1. **S3-03 says "Pure Pursuit".** Under your direction, B uses the A2RL controller (its lateral chain and MPC, which includes a preview pure-pursuit blend), and its speeds come from the A2RL velocity profile. **D30** changes the S3-03 wording.
2. **The plan lists "optimal raceline generation" as a non-goal.** Reusing A2RL's existing min-curvature generator is not new development, so it fits that non-goal. **D30** records this reading.
3. **Speed.** Every S1/S2 run was in the M6 envelope (≤ 0.3 m/s). A2RL-style speed profiles need more. With about 0.3 s of pose dead time, 1 m/s means 0.3 m of blind travel on a track 1.14 m wide at its narrowest. **D33** keeps the first S3 laps inside the M6 cap and puts any higher speed in a separate, evidence-based motion proposal.
4. **Initial conditions.** M3 asks for paired runs from defined initial conditions. PRE-B09 left the five initial poses open, and the simulator is frozen (D18), so there is no pose-setting API. **D34** decides how initial conditions are produced.

## 5. Stages (S3-01 to S3-07 unchanged, with A2RL inserted)

1. **No motion:**
   - vendor the A2RL files with provenance;
   - build the C0 reference, bounds and racing line with A2RL's generator (pinned start offsets at the spawn);
   - velocity profile at the cap;
   - the adapter;
   - unit tests and fixtures: the line inside the bounds less the margin, the profile limits respected, controller outputs on recorded S2 lap inputs (replay, open-loop);
   - the S3-01 map/ICP target.
2. **Shadow under motion** (needs a run approval): the existing A lap drives; the A2RL controller and MPC run alongside on the same inputs and only log.
3. **B bring-up laps at ≤ 0.3 m/s** (needs a run approval):
   - first with the pose source of D32;
   - then with ICP (S3-02).
4. **S3-04 to S3-07** as planned: truth isolation, the M3 baseline A/B, thresholds, acceptance.

## 6. Decisions requested

- **D30 — plan wording.** S3-03 delivers B with **the A2RL planning and control stack**:
  - `RaceGlobalPlanner` with the A2RL min-curvature line and friction-limited velocity profile;
  - `GreedyLatticePlanner`;
  - the A2RL lateral controller with its lateral MPC;
  - instead of plain Pure Pursuit, and with the non-goal read as above.

  Confirm, or change.
- **D31 — reuse mechanism.**
  - **A (recommended):** vendor unmodified files from `0b5cfa8` with sha256 provenance and a no-modification test; all RoboRacer specifics in one adapter.
  - **B:** import at runtime from your A2RL checkout. Not reproducible: it has local uncommitted changes and moves with your work.
  - **C:** a git submodule pinned to `0b5cfa8`. Equivalent to A, but it needs repository access at checkout time.
- **D32 — pose for the controller bring-up.** The plan forbids privileged pose in B.
  - **A (recommended):** bring the A2RL controller up first on the simulator IPS pose, **labelled "bring-up, not an S3 result"**, so tracking problems are separated from ICP problems. Then switch to ICP; every S3 result uses ICP.
  - **B:** ICP from the first B lap.
- **D33 — speed for S3.**
  - **A (recommended):** S3 bring-up and the M3 baseline stay inside the M6 envelope (≤ 0.3 m/s, same aborts). Any higher speed needs its own motion proposal with measured dead-time and stop evidence.
  - **B:** propose a staged higher-speed envelope now, before any B lap.
- **D34 — initial conditions for M3.**
  - **A (recommended):** each initial condition is a recorded pose reached by a scripted approach from the fixed spawn under A, checked against tolerances before B takes over.
  - **B:** only the fixed spawn. That rescopes M3's initial-condition requirement.
  - (A simulator pose API is excluded by the D18 freeze.)

## 7. Decisions (2026-10-22)

| Decision | Outcome |
| --- | --- |
| D30 | **Yes.** S3-03 wording changed in the plan. |
| D31 | **Port, not vendor.** The planners and the lateral control are implemented in the RoboRacer plugin following the A2RL `0b5cfa8` code. Each ported function names its A2RL source file and function, and equivalence tests compare the port with the A2RL code on the same inputs where the A2RL code runs standalone. |
| D32 | **A, chosen by me after you deferred it.** The controller is brought up first on the simulator's IPS pose, labelled "bring-up, not an S3 result". Reason: if the first B laps also used the new ICP pose, a bad lap could not tell a tracking problem from a localization problem. Every S3 result uses ICP. |
| D33 | **Faster is better.** Lap time becomes an S3 objective. Speed rises in stages above the M6 cap (0.3 m/s); each stage needs its own short motion proposal with measured stop distance and pose dead time, and its own run approval. The first such proposal follows the no-motion work. |
| D34 | **A.** Initial conditions are recorded poses reached by a scripted approach from the fixed spawn. |

**What D31 changes in §2:** "as-is" there now means *the same algorithm and structure, ported*, not copied files. §2's "How the code is brought in" (vendoring) is superseded.
