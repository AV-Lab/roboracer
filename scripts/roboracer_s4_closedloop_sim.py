#!/usr/bin/env python3
"""S4 no-motion closed-loop check: the full S4 stack in AVLite's own executer on a kinematic C0 car.

The stack is assembled through AVLite's ``executor_factory`` exactly as the live runner would assemble it for S4:
``PerceptionPipeline`` with ``ScanObstacleDetection``, ``MapIcpLocalization`` (simulator pose filtered out,
truth withheld), ``RaceLineGlobalPlanner`` on the committed V1 plan, ``C0LatticePlanner`` and
``RacingLineController`` in A2RL ``selected`` mode, ticked by ``SyncExecuter.step`` every 0.1 s.

The world is a subclass of the plugin's ``AutoDriveBridge``, so the sensor frame, truth withholding, wheel
odometry and the virtual-obstacle hook are the plugin's own code. It synthesizes each snapshot:
- LiDAR: 1,081 beams ray-cast against the C0 drivable region's walls (scorer geometry) with Gaussian range noise
  (``--range-noise``, fixed seed), then the virtual-obstacle fixture through the bridge hook;
- a new snapshot every ``--pose-period`` s (S2 median 0.18 s), acquired ``--pose-age`` s before it is offered;
- wheel odometry = the plant speed at acquisition.

Plant (as the S3 check): kinematic bicycle (wheelbase 0.324 m), 1 ms steps; steering slew 183 deg/s outward,
instant toward zero; speed follows the target with a 0.15 s lag within +1.5 / -2.0 m/s^2. No tyre slip.

Scored independently from the plant state every 10 ms: footprint (C0 geometry) against the walls and against the
fixture polygons; progress along the racing line; for a blocked case the footprint's distance to the obstacle once
stopped. This is planning evidence, not a driving result.

usage: roboracer_s4_closedloop_sim.py --geometry <c0-geometry.json> --fixture <t1.json> [--fixture ...] --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
SPAWN = (0.741, 3.158, -math.pi / 2)
WHEELBASE_M = 0.324


def build_stack(plugin_dir: Path):
    import importlib
    from avlite.c60_apps.c69_settings import AppSettings
    from avlite.c40_execution.c49_settings import ExecutionSettings
    from avlite.c10_perception.c19_settings import PerceptionSettings
    from avlite.c60_apps.c62_factory import executor_factory
    AppSettings.c62_default_plugins = []
    AppSettings.c62_community_plugins = {"roboracer": str(plugin_dir)}
    ExecutionSettings.c41_world_stack_capabilities = []  # simulator pose filtered out (S3-03)
    PerceptionSettings.c12_detection_strategy = "ScanObstacleDetection"
    PerceptionSettings.c12_tracking_strategy = ""
    PerceptionSettings.c12_prediction_strategy = ""
    executer = executor_factory(
        executer_type="SyncExecuter", bridge="AutoDriveBridge", perception_strategy_name="PerceptionPipeline",
        localization_strategy_name="MapIcpLocalization", mapping_strategy_name="",
        global_planner_strategy_name="RaceLineGlobalPlanner", local_planner_strategy_name="C0LatticePlanner",
        controller_strategy_name="RacingLineController", execution_task_names=[],
        default_global_trajectory_file=str(plugin_dir / "data/c0-s3v1-plan.json"), map_file="", load_plugins=True)
    plugin = sys.modules["avlite.plugins.roboracer"]
    s3b = importlib.import_module("avlite.plugins.roboracer.planning.s3b")
    cfg = s3b.controller_config("s3v1")
    cfg.trajectory_reference_mode = "selected"  # A2RL tracking mode selected_local (D57)
    executer.controller.config = cfg
    executer.controller.reset()
    plugin.PluginSettings.max_target_speed_mps = cfg.speed_cap_mps
    return executer, plugin


def make_world(plugin, geometry, fixture_path, rng, range_noise):
    import importlib
    import numpy as np
    from shapely import wkt
    obs = importlib.import_module(plugin.__name__ + ".integration.autodrive_observation")
    vo = importlib.import_module(plugin.__name__ + ".integration.virtual_obstacles")
    from avlite.c50_common.c52_world_sensor_datatypes import Imu, Lidar

    region = wkt.loads(geometry["region_wkt"])
    walls = vo.ObstacleFixture(name="c0-walls", sha256="", polygons=tuple(
        np.asarray(ring.coords[:-1], dtype=float) for ring in [region.exterior, *region.interiors]))

    class SimWorld(plugin.AutoDriveBridge):
        """The plugin bridge fed with synthesized snapshots (no ROS)."""

        def offer_state(self, seq, t_acq, x, y, yaw, v):
            hits = vo.first_hits(walls, vo.lidar_origin(x, y, yaw), yaw + vo.BEAM_ANGLES_RAD)
            ranges = np.where(hits <= obs.SCAN_RANGE_MAX_M, hits + rng.normal(0.0, range_noise, hits.shape), np.inf)
            published = ranges.astype(np.float32)
            published.setflags(write=False)
            points = obs.scan_points(published)
            points.setflags(write=False)
            lidar = Lidar(sensor_name="lidar", sensor_id="sim-lidar", stamp=t_acq,
                          base_to_sensor=obs.translation(obs.LIDAR_MOUNT_M), points=points)
            imu = Imu(sensor_name="imu", sensor_id="sim-imu", stamp=t_acq, base_to_sensor=obs.translation(obs.IMU_MOUNT_M),
                      linear_accel=(0.0, 0.0, 0.0), angular_velocity=(0.0, 0.0, 0.0))
            pose = obs.GroundTruthPose(x=x, y=y, z=0.059, yaw=yaw, stamp=t_acq)
            snap = obs.Snapshot(session="sim", episode=1, telemetry_seq=seq, lidar=lidar, imu=imu, pose=pose,
                                encoder_angles_rad=(0.0, 0.0), scan_ranges=published, sources={}, clock_bound_s=0.0,
                                scan_pose_skew_s=0.0, committed_monotonic_ns=int(t_acq * 1e9))
            with self._lock:
                if self.obstacle_fixture is not None:
                    snap = self._with_obstacles(snap)
                self._encoder_speed[seq] = v
                self._snapshot = snap
                self.connected = True

    world = SimWorld()
    world.withhold_truth = True
    if fixture_path:
        world.obstacle_fixture = vo.load_fixture(fixture_path)
    return world, region


def simulate(fixture_path, geometry, plugin_dir, *, pose_period, pose_age, range_noise, seed, t_max, accel=1.5,
             brake=2.0, speed_tau=0.15, slew_radps=math.radians(183.0)):
    import collections
    import numpy as np
    from shapely.affinity import rotate, translate
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    executer, plugin = build_stack(plugin_dir)
    world, region = make_world(plugin, geometry, fixture_path, np.random.default_rng(seed), range_noise)
    executer.world = world
    obstacles = (unary_union([Polygon(o["polygon"]) for o in json.loads(Path(fixture_path).read_text())["obstacles"]])
                 if fixture_path else None)
    planner, loc, ctl = executer.local_planner, executer.localization, executer.controller
    detector = executer.perception._detector
    line = planner.global_trajectory
    lap_m = float(line.path_s[-1])
    fp = geometry["footprint"]
    body = Polygon([(fp["x_min"], fp["y_min"]), (fp["x_max"], fp["y_min"]), (fp["x_max"], fp["y_max"]), (fp["x_min"], fp["y_max"])])

    x, y, th = SPAWN
    v, delta, t, seq = 0.0, 0.0, 0.0, 0
    history = collections.deque([(0.0, x, y, th, v)])
    next_snapshot = 0.0
    target, steer = 0.0, 0.0
    progress, last_s = 0.0, None
    min_wall, min_obstacle, contact, offtrack = math.inf, math.inf, False, False
    events, icp_states, blocked_at, rest_since, initialized = [], {}, None, None, False
    max_lateral = 0.0
    timing = []

    def offer_due(now):
        nonlocal next_snapshot, seq
        while now + 1e-9 >= next_snapshot:
            t_acq = max(0.0, next_snapshot - pose_age)
            old = min(history, key=lambda h: abs(h[0] - t_acq))
            seq += 1
            world.offer_state(seq, old[0], old[1], old[2], old[3], old[4])
            next_snapshot += pose_period

    while t < t_max:
        offer_due(t)
        if not initialized and world.latest() is not None:
            loc.initialize(*SPAWN)
            init = loc.verify_initialization(world.get_sensor_frame())
            events.append({"t": round(t, 2), "event": "icp start-up check", "accepted": bool(init.get("accepted"))})
            initialized = True
            if not init.get("accepted"):
                break
        started = time.perf_counter()
        executer.step(sim_dt=0.1, control_dt=0.099, replan_dt=0.099, perception_dt=0.099, localization_dt=0.099)
        timing.append(time.perf_counter() - started)
        request = world.last_request
        if request is not None:
            target, steer = float(request.target_speed), float(request.steer)
        state = loc.status.get("state")
        icp_states[state] = icp_states.get(state, 0) + 1
        if state == "lost":
            events.append({"t": round(t, 2), "event": "localization lost"})
            target = 0.0
        if planner.blocked and blocked_at is None:
            blocked_at = {"t": round(t, 2), "reason": planner.blocked_reason, "speed_mps": v,
                          "obstacle_distance_m": None}
            events.append({"t": round(t, 2), "event": "blocked latched", "reason": planner.blocked_reason})
        for k in range(100):
            if abs(steer) < abs(delta) or steer * delta < 0:
                delta = steer if steer * delta >= 0 else 0.0
            else:
                delta += max(-slew_radps * 0.001, min(slew_radps * 0.001, steer - delta))
            dv = (target - v) / speed_tau * 0.001
            v = max(0.0, v + max(-brake * 0.001, min(accel * 0.001, dv)))
            x += v * math.cos(th) * 0.001
            y += v * math.sin(th) * 0.001
            th += v / WHEELBASE_M * math.tan(delta) * 0.001
            t += 0.001
            if k % 10 == 0:
                history.append((t, x, y, th, v))
                while history[0][0] < t - pose_age - 0.5:
                    history.popleft()
                car = translate(rotate(body, th, origin=(0, 0), use_radians=True), x, y)
                inside = region.contains(car)
                offtrack = offtrack or not inside
                wall = min(car.exterior.distance(r) for r in [region.exterior, *region.interiors]) if inside else 0.0
                min_wall = min(min_wall, wall)
                if obstacles is not None:
                    od = car.distance(obstacles)
                    min_obstacle = min(min_obstacle, od)
                    contact = contact or od <= 0.0
                if k % 50 == 0:
                    offer_due(t)
        s, d = line.convert_xy_to_sd(x, y)
        max_lateral = max(max_lateral, abs(d))
        if last_s is not None:
            ds = s - last_s
            if ds < -lap_m / 2:
                ds += lap_m
            elif ds > lap_m / 2:
                ds -= lap_m
            progress += ds
        last_s = s
        if contact or offtrack:
            events.append({"t": round(t, 2), "event": "contact" if contact else "off-track"})
            break
        if progress >= lap_m:
            events.append({"t": round(t, 2), "event": "lap complete"})
            break
        if v < 0.01 and t > 2.0:
            rest_since = rest_since if rest_since is not None else t
            if t - rest_since >= 2.0 and (blocked_at is not None or state == "lost"):
                break
        else:
            rest_since = None
    car = translate(rotate(body, th, origin=(0, 0), use_radians=True), x, y)
    rest_obstacle = car.distance(obstacles) if obstacles is not None else None
    if blocked_at is not None:
        blocked_at["obstacle_distance_m"] = rest_obstacle
    return {"fixture": Path(fixture_path).name if fixture_path else None, "t_end_s": round(t, 2),
            "progress_m": progress, "lap_m": lap_m, "lap_complete": progress >= lap_m, "contact": contact,
            "offtrack": offtrack, "min_wall_clearance_m": min_wall,
            "min_obstacle_clearance_m": min_obstacle if obstacles is not None else None,
            "rest_obstacle_clearance_m": rest_obstacle if v < 0.01 else None, "final_speed_mps": v,
            "max_abs_d_from_line_m": max_lateral, "blocked": blocked_at, "icp_states": icp_states, "events": events,
            "planner": dict(planner.diagnostics), "detector": dict(detector.status),
            "tick_ms": {"p50": 1e3 * sorted(timing)[len(timing) // 2], "max": 1e3 * max(timing)} if timing else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, action="append", default=[], help="repeat; 'none' for no obstacle")
    parser.add_argument("--pose-period", type=float, default=0.18)
    parser.add_argument("--pose-age", type=float, default=0.3)
    parser.add_argument("--range-noise", type=float, default=0.005)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--t-max", type=float, default=90.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be fresh")
    geometry = json.loads(args.geometry.read_text())
    results = []
    for fixture in args.fixture or [Path("none")]:
        row = simulate(None if str(fixture) == "none" else fixture, geometry, REPO / "roboracer",
                       pose_period=args.pose_period, pose_age=args.pose_age, range_noise=args.range_noise,
                       seed=args.seed, t_max=args.t_max)
        results.append(row)
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k != "events"}),
              flush=True)
    args.output.write_text(json.dumps({"model": "kinematic bicycle, no slip; synthesized scans (planning evidence, "
                                       "not a driving result)", "args": {k: str(v) for k, v in vars(args).items()},
                                       "results": results}, indent=1) + "\n")


if __name__ == "__main__":
    main()
