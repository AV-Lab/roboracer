#!/usr/bin/env python3
"""S3 offline shadow of B's controller on a recorded lap (no motion; open-loop).

For every driving tick of one recorded episode, the ported A2RL controller (RacingLineController on the
C0 plan) is given the snapshot pose the tick used and the tick's encoder speed, and its steering and
target speed are recorded next to what the driving controller (A) actually sent. Open-loop: the car
followed A, so this shows B's commands along A's trajectory, not how B would drive. The pose is the
simulator IPS pose ("bring-up, not an S3 result", D32 A).

usage: roboracer_s3_shadow.py --run <run-01> --geometry <c0-geometry.json> --episode N --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--mpc", choices=("off", "shadow", "apply"), default="apply")
    parser.add_argument("--speed-cap", type=float, default=0.3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from shapely import wkt
    from avlite.c10_perception.c11_perception_model import EgoState
    from roboracer.control.racing_controller import RacingControllerConfig, RacingLineController
    from roboracer.planning.c0_track import build_c0_plan
    from roboracer.planning.trajectory_tracker import LapTrajectoryTracker
    from roboracer.planning.velocity_profile import VelocityProfileConfig

    geometry = json.loads(args.geometry.read_text())
    profile = VelocityProfileConfig(top_speed_mps=args.speed_cap, min_speed_mps=0.1, lateral_accel_mps2=3.0,
                                    brake_decel_mps2=2.0, accel_limit_mps2=1.5, curvature_window_m=0.4,
                                    curvature_hold_m=0.5)
    payload, plan_report = build_c0_plan(geometry["centerline"], wkt.loads(geometry["region_wkt"]), spacing_m=0.1,
                                         boundary_margin_m=0.3, profile=profile, start_pin_m=0.05)
    line = [tuple(p[:2]) for p in payload["ReferenceLine"]]
    tracker = LapTrajectoryTracker(path=line, velocity=payload["ReferenceSpeed"])
    # Safe stop disabled here (it would latch on A's path); exceedances are reported per tick instead.
    config = RacingControllerConfig(mpc_lateral_mode=args.mpc, speed_cap_mps=args.speed_cap)
    lateral_limit, yaw_limit = config.safe_stop_lateral_error_m, config.safe_stop_yaw_error_rad
    config.tracking_safe_stop_min_speed_mps = math.inf
    controller = RacingLineController(config=config)

    snapshots = {(s["episode"], s["telemetry_seq"]): s for s in read_jsonl(args.run / "plugin-snapshots.jsonl")}
    rows = []
    for tick in read_jsonl(args.run / "plugin-ticks.jsonl"):
        if tick.get("phase") != "run" or tick.get("telemetry_seq") is None:
            continue
        snap = snapshots.get((args.episode, tick["telemetry_seq"]))
        if snap is None:
            continue
        x, y, _, yaw = snap["pose"]
        speed = float(tick.get("encoder_speed") or 0.0)
        target, steer, detail = controller.steer_and_speed(tracker, EgoState(x=x, y=y, theta=yaw, velocity=speed), 0.1)
        a = tick.get("controller") or {}
        rows.append({"t": (tick["start_ns"] - rows[0]["start_ns"]) / 1e9 if rows else 0.0, "start_ns": tick["start_ns"],
                     "s_m": detail["s_m"], "lateral_error_m": detail["lateral_error_m"],
                     "yaw_error_rad": detail["yaw_error_rad"], "speed": speed, "b_steer": steer, "b_target_speed": target,
                     "a_steer": a.get("steer"), "a_target_speed": a.get("target_speed"),
                     "safe_stop": ("yaw_error" if abs(detail["yaw_error_rad"]) > yaw_limit else
                                   "lateral_error" if abs(detail["lateral_error_m"]) > lateral_limit else "")})
    if not rows:
        raise SystemExit("no driving ticks with snapshots in this episode")

    def stats(values):
        values = sorted(abs(v) for v in values)
        return {"p50": values[len(values) // 2], "p95": values[int(0.95 * (len(values) - 1))], "max": values[-1]}

    diff = [r["b_steer"] - r["a_steer"] for r in rows if r["a_steer"] is not None]
    report = {
        "mode": "open-loop shadow on a recorded lap (B commands along A's trajectory; not a B lap)",
        "pose_source": "simulator IPS (D32 A bring-up; not an S3 result)",
        "run": str(args.run), "episode": args.episode, "ticks": len(rows), "mpc_lateral_mode": args.mpc,
        "plan": plan_report,
        "a_trajectory_vs_racing_line": {"lateral_error_m": stats([r["lateral_error_m"] for r in rows]),
                                         "yaw_error_rad": stats([r["yaw_error_rad"] for r in rows])},
        "b_steer_rad": stats([r["b_steer"] for r in rows]),
        "b_minus_a_steer_rad": stats(diff),
        "b_steer_saturated_ticks": sum(abs(r["b_steer"]) >= controller.config.max_wheel_angle_rad - 1e-9 for r in rows),
        "safe_stop_threshold_exceeded_ticks": sum(bool(r["safe_stop"]) for r in rows),
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows", "plan")}, indent=1))


if __name__ == "__main__":
    main()
