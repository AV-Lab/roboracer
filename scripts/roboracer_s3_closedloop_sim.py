#!/usr/bin/env python3
"""S3 no-motion closed-loop check: B (ported A2RL controller + C0 plan) on a kinematic bicycle with the
measured AutoDRIVE timing, at several speed caps.

Plant: kinematic bicycle (wheelbase 0.324 m), 1 ms steps; steering slew 183 deg/s outward (S1 M0);
speed follows the target with a first-order lag and +-accel/brake limits; NO tyre slip, so the
lateral-acceleration limit is an assumption of the velocity profile, not something this checks.
Sensing: a new pose every ``--pose-period`` s (S2 median frame interval 0.18 s), already
``--pose-age`` s old when used (S2 observation age up to 0.345 s); the controller ticks every 0.1 s.
Clearance: the car's footprint rectangle (C0 geometry) against the drivable region, every 10 ms.

This is planning evidence for the speed-stage proposal (D33), not a driving result.

usage: roboracer_s3_closedloop_sim.py --geometry <c0-geometry.json> --caps 0.3 0.5 1 ... --output <json>
"""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def simulate(payload, geometry, region, cap, *, mpc, pose_period, pose_age, laps=2, accel=1.5, brake=2.0,
             speed_tau=0.15, slew_radps=math.radians(183.0)):
    from shapely.affinity import rotate, translate
    from shapely.geometry import Polygon
    from avlite.c10_perception.c11_perception_model import EgoState
    from roboracer.control.racing_controller import RacingControllerConfig, RacingLineController
    from roboracer.planning.trajectory_tracker import LapTrajectoryTracker

    line = [tuple(p[:2]) for p in payload["ReferenceLine"]]
    tracker = LapTrajectoryTracker(path=line, velocity=payload["ReferenceSpeed"])
    lap_m = tracker.path_s[-1]
    cfg = RacingControllerConfig(mpc_lateral_mode=mpc, speed_cap_mps=cap)
    ctl = RacingLineController(config=cfg)
    fp = geometry["footprint"]
    body = Polygon([(fp["x_min"], fp["y_min"]), (fp["x_max"], fp["y_min"]), (fp["x_max"], fp["y_max"]),
                    (fp["x_min"], fp["y_max"])])
    x, y = geometry["spawn"]["xy"]
    th, v, delta = geometry["spawn"]["yaw"], 0.0, 0.0
    dt_plant, n_plant = 0.001, 100            # controller every 0.1 s
    history = collections.deque()             # (t, x, y, th, v) for delayed poses
    t, pose, next_pose_t = 0.0, None, 0.0
    history.append((t, x, y, th, v))
    target, steer = 0.0, 0.0
    progress, last_s = 0.0, None
    worst_lat, min_clear, stop_reason, contact = 0.0, math.inf, "", False
    lap_times = []
    while t < 400.0 and len(lap_times) < laps:
        while history and history[0][0] < t - pose_age - 0.5:
            history.popleft()
        if t + 1e-9 >= next_pose_t:  # a new observation arrives, already pose_age old
            old = min(history, key=lambda h: abs(h[0] - (t - pose_age)))
            pose = old
            next_pose_t += pose_period
        _, ox, oy, oth, ov = pose
        target, steer, detail = ctl.steer_and_speed(tracker, EgoState(x=ox, y=oy, theta=oth, velocity=ov), 0.1)
        if detail.get("safe_stop") and not stop_reason:
            stop_reason = f"{detail['safe_stop']} at s={detail['s_m']:.2f} m, t={t:.1f} s"
        for k in range(n_plant):
            # steering: outward moves slew-limited, moves toward zero immediate (S1 M0 vendor behaviour)
            if abs(steer) < abs(delta) or steer * delta < 0:
                delta = steer if steer * delta >= 0 else 0.0
            else:
                delta += max(-slew_radps * dt_plant, min(slew_radps * dt_plant, steer - delta))
            dv = (target - v) / speed_tau * dt_plant
            v = max(0.0, v + max(-brake * dt_plant, min(accel * dt_plant, dv)))
            x += v * math.cos(th) * dt_plant
            y += v * math.sin(th) * dt_plant
            th += v / 0.324 * math.tan(delta) * dt_plant
            t += dt_plant
            if k % 10 == 0:
                history.append((t, x, y, th, v))  # 10 ms pose history for the delayed observations
                car = translate(rotate(body, th, origin=(0, 0), use_radians=True), x, y)
                clear = car.exterior.distance(region.exterior) if region.contains(car) else -1.0
                for hole in region.interiors:
                    clear = min(clear, car.exterior.distance(hole)) if clear >= 0 else clear
                min_clear = min(min_clear, clear)
                contact = contact or clear < 0
        s, d = tracker.convert_xy_to_sd(x, y)
        worst_lat = max(worst_lat, abs(d))
        if last_s is not None:
            ds = s - last_s
            if ds < -lap_m / 2:
                ds += lap_m
            progress += ds
            if progress >= lap_m * (len(lap_times) + 1):
                lap_times.append(t)
        last_s = s
        if contact or (stop_reason and v < 1e-3):
            break
    flying = [b - a for a, b in zip(lap_times, lap_times[1:])]
    return {"cap_mps": cap, "mpc": mpc, "laps_completed": len(lap_times), "first_lap_s": lap_times[0] if lap_times else None,
            "flying_lap_s": flying[0] if flying else None, "max_lateral_error_m": worst_lat,
            "min_footprint_clearance_m": min_clear, "contact": contact, "safe_stop": stop_reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--caps", type=float, nargs="+", default=[0.3, 0.5, 1.0, 1.5, 2.0, 3.0])
    parser.add_argument("--lateral-accel", type=float, default=3.0, help="profile assumption, m/s^2")
    parser.add_argument("--accel", type=float, default=1.5,
                        help="profile and plant acceleration limit, m/s^2 (the supervisor's throttle rise 0.10/s x K ~ 0.5)")
    parser.add_argument("--pose-period", type=float, default=0.18)
    parser.add_argument("--pose-age", type=float, default=0.3)
    parser.add_argument("--mpc", nargs="+", default=["off", "apply"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from shapely import wkt
    from roboracer.planning.c0_track import build_c0_plan
    from roboracer.planning.velocity_profile import VelocityProfileConfig

    geometry = json.loads(args.geometry.read_text())
    region = wkt.loads(geometry["region_wkt"])
    results = []
    for cap in args.caps:
        profile = VelocityProfileConfig(top_speed_mps=cap, min_speed_mps=min(0.3, cap), lateral_accel_mps2=args.lateral_accel,
                                        brake_decel_mps2=2.0, accel_limit_mps2=args.accel, curvature_window_m=0.4,
                                        curvature_hold_m=0.5)
        payload, plan = build_c0_plan(geometry["centerline"], region, spacing_m=0.1, boundary_margin_m=0.3,
                                      profile=profile, start_pin_m=0.05)
        for mpc in args.mpc:
            row = simulate(payload, geometry, region, cap, mpc=mpc, pose_period=args.pose_period, pose_age=args.pose_age,
                           accel=args.accel)
            row["profile_estimated_lap_s"] = plan["profile"]["estimated_lap_s"]
            results.append(row)
            print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    args.output.write_text(json.dumps({"model": "kinematic bicycle, no slip (planning evidence, not a driving result)",
                                       "pose_period_s": args.pose_period, "pose_age_s": args.pose_age,
                                       "profile_lateral_accel_mps2": args.lateral_accel, "results": results}, indent=1) + "\n")


if __name__ == "__main__":
    main()
