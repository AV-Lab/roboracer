# RoboRacer release 1 — operations guide

Release 1 of the RoboRacer AVLite community plugin (`roboracer/`) on the source-built AutoDRIVE F1TENTH simulator. It was qualified in stage S5; the evidence is in [S5](../docs/stages/S5.md). **Simulation only.** It is not published; this tree is prepared for a private repository (D75).

**Release profile:** stage `s4` on the C0 track. That is the A2RL racing-line stack ("B", D45) on map ICP localization, V1 speed (0.5 m/s), with the S4 static-obstacle stack: scan obstacle detection and the C0 lattice planner. D69 froze it; D78–D79 changed it.

## 1. Supported versions

Everything below is pinned in [`pins.json`](pins.json) and the lock files in this directory. A different version is not qualified.

| Component | Version |
| --- | --- |
| Host | Ubuntu 22.04.5, x86-64, GNOME on X11, NVIDIA GPU with Vulkan (qualified on an RTX 3080) |
| Python | 3.10.12 (`/usr/bin/python3.10`) |
| ROS 2 | Humble, `/opt/ros/humble` |
| AVLite | 0.6.3, commit `50dcd00`; source tarball sha256 pinned |
| AutoDRIVE Devkit | 0.3.0, commit `4abf7cd`, package `autodrive_f1tenth`, with [`patches/devkit-loopback.patch`](patches/devkit-loopback.patch) and [`patches/devkit-tf-lifecycle.patch`](patches/devkit-tf-lifecycle.patch); `attrdict==2.0.1` with [`patches/attrdict-python310.patch`](patches/attrdict-python310.patch) |
| Simulator | AutoDRIVE player, vendor patch 04 (D18), 604 files checked against a sha256 list; **frozen** and provided separately (not rebuilt or redistributed). Built from AutoDRIVE `635dbb6` with Unity 2021.3.9f1 ([qualified backend](../docs/architecture/qualified-backend.md)) |
| A2RL port | AV-Lab/a2rl `dev` `0b5cfa8` (unchanged at `fe2fc01`) |
| Track | C0 (Proto Track) only |

- **Unity host note:** Unity 2021.3 does not list Ubuntu 22.04 as a supported host. The player was built and qualified on it anyway; this is recorded as a qualification risk.
- **Display:** the player needs a graphical X11 display (`:1`). Running without a display is not qualified.

## 2. Build the environment

The environment is rebuilt offline from hashed locks (D70). Use `scripts/roboracer_s5_env.py`:

```bash
python3 scripts/roboracer_s5_env.py wheelhouse          # once, online: downloads the locked wheels
python3 scripts/roboracer_s5_env.py build  --output ~/roboracer-work/<env>   # offline, --require-hashes
python3 scripts/roboracer_s5_env.py verify --output ~/roboracer-work/<env>
```

- **`build`:**
  - creates the AVLite venv (26 packages) and the Devkit venv (16 packages);
  - applies the patches above;
  - writes a zeroed `api_config.ini`;
  - writes the environment's `run-context.json`.
- **`verify`:** checks the package sets against the locks, the AVLite version, the plugin and bridge imports, the zeroed `api_config.ini` and the simulator's 604-file identity. All 7 checks must pass.
- **Qualified environment:** `~/roboracer-work/s5-fresh-20261102T3` (S5 §7).

## 3. Launch

The supported way to drive is the stage runner, through the single entrypoint `scripts/roboracer.py` (D71). The AVLite visualizer is for configuration only, because it cannot start a live run (D76).

```bash
source /opt/ros/humble/setup.bash
python3 scripts/roboracer.py --context ~/roboracer-work/<env>/run-context.json live \
    --stage s4 --duration 235 --results <dir> --output <dir>-episode [--fixture t1|t2|t3|<path>] [--judge t1|t2|t3]
python3 scripts/roboracer.py replay | export | compare ...   # offline; see --help
```

`--dry-run` prints the commands without running them.

**What a live episode does** (`scripts/autodrive_neutral.py`):
1. **Refuses a motion stage that is not approved.** The stage must be listed in [`docs/planning/s1-motion-approval.json`](../docs/planning/s1-motion-approval.json). In this project every live run set also had its own recorded approval.
2. **Refuses to start** without the zeroed `api_config.ini`, or if the player's files differ from its build record.
3. **Starts the player** with the guard (`-roboracerGuard`). Motion is authorized only for an approved stage.
4. **Checks the window automatically, then clicks Connect once** (D21 A).
5. **Starts the processes:** the Devkit bridge, the observer, the supervisor and the AVLite stack (10 Hz).
6. **Keeps the lease alive:** the runner heartbeats the supervisor (500 ms lease, D28).
7. **On shutdown,** checks that the player was left unchanged and writes the export (`episode.json`, `score.json`, manifest).

**An episode ends** on:
- one lap: 33 m or 200 s (D10);
- "blocked": at rest for 2.0 s after the lattice latched blocked (D58);
- an abort:
  - a guard fault;
  - localization lost, or no valid ICP fix for 0.5 s;
  - no new obstacle result or observation for 0.5 s (D56);
  - overspeed (0.7 m/s at V1);
  - steering request > 0.35 rad;
  - side clearance < 0.15 m or front clearance < 0.5 m;
  - a scene reload;
- a simulator hang: no telemetry for 2 s. The player is then killed, and this is never counted as a stop.

## 4. Reset and rearm

- **Scene reset:** a GUI Reset reloads the whole scene. The guard disarms (`scene-load`), the episode number advances, and requests from the old episode are rejected (`stale-epoch`) ([SIM1-03 reset](../docs/stages/SIM1-03-reset.md)).
- **After a reset:** the car is back at the spawn within 0.010 m and 1°; Reset to Connect takes about 5.1 s.
- **Batches:** one player per batch with a Reset between episodes, and a fresh player every 4 episodes (D20 A, D27 A).
- **Start positions:** a reset always returns to the one spawn, (0.741, 3.158, −π/2). The other start positions (M3 ICs, H1) are reached by a scripted approach (D44, D49), not by reset.
- **Rearm:** `--s4-rearm blocked|cleared` disarms and re-arms the guard 2.0 s after a blocked rest and resets the lattice (D63).
- **Desktop :1 is shared with the user's session:**
  - Clicks are refused if the pointer or focus moves, or another client holds the input grab (for example the Activities overview).
  - A locked screen swallows the Connect click.
  - Leave the desktop alone while runs are going.

## 5. Calibration and the validated envelope

| Item | Value | Source |
| --- | --- | --- |
| Steering | +1 = 30° left, Ackermann geometry; slew about 183°/s | [S1 M0](../docs/stages/S1-M0-steering.md) |
| Throttle → speed | v ≈ 5.03 m/s × throttle, validated to 0.60 m/s (M3c) and 1.21 m/s (M3d) | [S3 §6, §8](../docs/stages/S3.md) |
| Speed | **V1: 0.5 m/s**, overspeed abort 0.7 m/s. The only speed on ICP. V2 (1.0 m/s) passed only on simulator-truth localization and is **not** part of the release | D35–D43 |
| Localization | Map ICP on `roboracer/data/c0-icp-map.json` (3,152 points; 5.7 mm median residual on 200 scans; a tampered map is refused) | [S3](../docs/stages/S3-completion.md) |
| Lattice bounds | `roboracer/data/c0-lattice-bounds.json`, built from the C0 map with a 2-D 0.20 m wall margin; refused for another plan | D79, [S5 §15](../docs/stages/S5.md) |
| Safe stop | yaw error > 0.35 rad (stage `s4`) | D65 |
| Latency | observation age limit 500 ms (S2 max 345 ms); pose age about 0.3 s, compensated in the MPC | [S2](../docs/stages/S2-completion.md), [S3](../docs/stages/S3.md) |

**The validated envelope:**
- **Track and speed:** C0 at 0.5 m/s on map ICP.
- **Starts:**
  - the spawn;
  - five M3 initial conditions at s = 0, 6.25, 12.5, 18.75 and 25 m (±0.10 m, ±5°);
  - held-out H1 at s = 21.875 m.
- **Obstacles:** one static virtual box of 0.25 m (T1/T2 at s = 7.5 m, H2 at 7.0, H3 at 14.75, held-out H4 at 18.25), or a full-width barrier (T3).
- **Passing gaps:**
  - a gap of ≥ 0.88 m on the passing side meets U3: obstacle ≥ 0.25 m, wall ≥ 0.20 m;
  - a gap of 0.488–0.88 m meets U3n: obstacle and wall ≥ 0.10 m (D80);
  - with no passable gap, the car stops ≥ 1.0 m short (T3) and at least 0.30 m from the obstacle (D58).

## 6. Qualification results

| Stage | Criteria | Result |
| --- | --- | --- |
| S2 | M2 (D26 A) | 10/10 unattended episodes; F2 × 3; replay exact |
| S3 | T1–T8 (D48) | B 50/50; F3 15/15 |
| S4 | U1–U7 (D66–D68) | T1/T2/T3 30/30; F4 9/9 |
| S5 M5 | D72/D73 | regression pass; held-out start H1 5/5; H2 0/5, which led to D78 ([§8](../docs/stages/S5.md)) |
| S5 re-qualification | U1–U7 with U3 tiered (D80) | M4 30/30 (with the D81 re-run); F4 9/9; clear laps 3/3; **held-out H4 5/5**; H3, H2 5/5; offline all pass ([§18–§21](../docs/stages/S5.md)) |

F1, F3 and H1 were not re-run in the re-qualification: their stages do not use the lattice.

## 7. Known limitations

**Scope:**
- Simulation only, C0 only, one car.
- Obstacles are static virtual obstacles injected into the scans; contact is a scored footprint overlap (D54). Moving obstacles, physical obstacles and other cars are not supported.
- No evidence on an unseen track. The held-out cases use the same layout.

**Speed:**
- V1 only on ICP.
- V2 was never run on ICP. The kinematic model is about 18 % optimistic at V2.

**Narrow gaps:**
- The controller tracks the lattice path with about 0.07 m of error (it cuts bends).
- Because of that, U3 can be met only where the passing gap is ≥ 0.88 m. Narrower gaps meet only U3n (0.10/0.10 m).
- D80 changed this criterion after H3 failed it; this is stated openly.

**Thin margins:**
- Obstacle clearance: H2 0.257 m (0.007 m over U3) and T2 0.279 m.
- Heading: about 0.15 rad below the 0.35 rad safe stop.

**Track data:**
- The racing plan's own boundary data (`c0-s3v1-plan.json`) is up to 0.24 m outside the real walls in places.
- The lattice therefore uses map-derived bounds (D79). Anything else that reads the plan's `LeftBound`/`RightBound` gets the inaccurate values.

**ICP:**
- The along-track position is unobservable at the spawn; no global-pose validation is claimed.
- An undetected obstacle near a wall could bias ICP.
- The ICP map and the scorer share one source (the C0 collider geometry).

**Infrastructure:**
- **Runner stalls:** a runner main-loop stall once expired the supervisor lease and stopped a run (D81). The stop was safe.
  - It coincided to the second with host maintenance: a systemd reload, a snap auto-refresh, and apt and fwupd timers ([S5 audit §6](../docs/stages/S5-audit.md)).
  - Hold snap and apt auto-updates during run sessions.
  - Stalls are now recorded per run.
- **Simulator:**
  - a genuine stall about once in 50 laps;
  - a blank-window start about once in 110 runs;
  - a shutdown hang;
  - passive creep of about 3.4 mm/min;
  - the player has no seed.
- **Run time:** about 37 min per 10-episode session.

**Host paths:**
- Some defaults point at this host's workspace and evidence: `scripts/roboracer.py` (player, build record, UI reference, geometry), `scripts/roboracer_s5_env.py` (the preflight and simulator-identity paths), and `scripts/roboracer_episode.py` (the AVLite checkout recorded in provenance).
- On another host, pass the corresponding options or edit these defaults.
- Tests that need this host's evidence skip when it is absent.

**Tools:**
- The AVLite visualizer cannot run live, because ground-truth perception is not implemented by design (D76).
- `setting-cli validate` does not check plugin sections.
- F2 was not verified with profile B.
