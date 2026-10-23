#!/usr/bin/env python3
"""S3-02 offline evaluation (no motion): map ICP and stock AVLite ICP on a recorded lap, scored against IPS.

Each recorded episode is replayed through the plugin's own snapshot assembler; every committed scan goes
through ``MapIcpLocalization`` (initialized from the configured spawn pose, never from IPS) and, for
comparison, through AVLite's stock ``LidarLocalization`` (scan-to-first-scan, seeded with the same pose).
The IPS pose of the same snapshot is the independent reference (offline only; scan/pose skew ~0.04 s is
part of the error). Reports position/yaw error, validity, loss and compute time per scan.

usage: roboracer_s3_icp_eval.py --run <run-01 with plugin-inputs.jsonl> [--episode 1] --output <json>
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
SPAWN = (0.741, 3.158, -math.pi / 2)  # configured C0 spawn (S1-02 recorded spawn; geometry spawn yaw)


def stats(values):
    import numpy as np
    v = np.abs(np.asarray(values, dtype=float))
    return {"p50": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(v.max())} if len(v) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--init-offset", type=float, nargs=3, default=[0.0, 0.0, 0.0], metavar=("DX", "DY", "DYAW"),
                        help="initialization fault: offset added to the configured spawn pose (m, m, rad)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from avlite.c10_perception.c11_perception_model import EgoState, PerceptionModel
    from avlite.c10_perception.c16_localization_algs import LidarLocalization
    from avlite.c50_common.c52_world_sensor_datatypes import SensorFrame
    from roboracer_inputs import load_plugin, read_recording, replay_snapshots

    plugin = load_plugin(REPO / "roboracer")
    map_icp = sys.modules[plugin.__name__ + ".localization.map_icp"] if (plugin.__name__ + ".localization.map_icp") in sys.modules \
        else __import__(plugin.__name__ + ".localization.map_icp", fromlist=["MapIcpLocalization"])
    _, records = read_recording(args.run / "plugin-inputs.jsonl")
    snapshots, _ = replay_snapshots(records, plugin)
    lap = [s for s in snapshots if s.episode == args.episode and s.lidar is not None and s.lidar.points is not None]

    pm = PerceptionModel(ego_vehicle=EgoState(x=SPAWN[0], y=SPAWN[1], theta=SPAWN[2]))
    ours = map_icp.MapIcpLocalization(pm)
    init = (SPAWN[0] + args.init_offset[0], SPAWN[1] + args.init_offset[1], SPAWN[2] + args.init_offset[2])
    ours.initialize(*init)
    stock_pm = PerceptionModel(ego_vehicle=EgoState(x=SPAWN[0], y=SPAWN[1], theta=SPAWN[2]))
    stock = LidarLocalization(stock_pm)

    rows = []
    previous_angle = None
    for snap in lap:
        # Wheel odometry (allowed sensor): mean encoder angle x wheel radius 0.059 m (S1 M1).
        angle = sum(snap.encoder_angles_rad) / 2
        if previous_angle is not None:
            ours.add_odometry((angle - previous_angle) * 0.059)
        previous_angle = angle
        frame = SensorFrame(lidars={"lidar": snap.lidar}, primary_lidar_name="lidar", stamp=snap.lidar.stamp,
                            frame_id="base_link")
        ours.localize(pm, frame)
        t0 = time.perf_counter()
        stock.localize(stock_pm, frame)
        stock_s = time.perf_counter() - t0
        truth = (snap.pose.x, snap.pose.y, snap.pose.yaw)
        st = ours.status
        row = {"telemetry_seq": snap.telemetry_seq, "state": st["state"], "truth": truth}
        if "pose" in st and st["state"] != "initialized":
            x, y, th = st["pose"]
            row.update(pos_err=math.hypot(x - truth[0], y - truth[1]), yaw_err=math.remainder(th - truth[2], math.tau),
                       inlier_fraction=st["inlier_fraction"], inlier_rms_m=st["inlier_rms_m"],
                       correction_m=st["correction_m"], compute_s=st["compute_s"], failed=st["failed"],
                       degenerate=st["degenerate"], constraint_ratio=st["constraint_ratio"])
        e = stock_pm.ego_vehicle
        row.update(stock_pos_err=math.hypot(e.x - truth[0], e.y - truth[1]),
                   stock_yaw_err=math.remainder(e.theta - truth[2], math.tau), stock_compute_s=stock_s)
        rows.append(row)

    scored = [r for r in rows if "pos_err" in r]
    valid = [r for r in scored if r["state"] == "valid"]
    states = {}
    for r in rows:
        states[r["state"]] = states.get(r["state"], 0) + 1
    path = sum(math.dist(a["truth"][:2], b["truth"][:2]) for a, b in zip(rows, rows[1:]))
    report = {
        "schema": "roboracer.s3-icp-eval/1", "run": str(args.run), "episode": args.episode, "scans": len(rows),
        "path_m": path, "initialization": {"source": "configuration", "pose": init, "offset": args.init_offset}, "map_sha256": ours.map_sha256,
        "map_icp": {"states": states, "lost": any(r["state"] == "lost" for r in rows),
                    "first_lost_scan": next((i for i, r in enumerate(rows) if r["state"] == "lost"), None),
                    "valid_but_wrong_scans": sum(1 for r in valid if r["pos_err"] > 0.10 or abs(r["yaw_err"]) > 0.1),
                    "position_error_m": stats([r["pos_err"] for r in valid]),
                    "yaw_error_rad": stats([r["yaw_err"] for r in valid]),
                    "inlier_fraction": stats([r["inlier_fraction"] for r in scored]),
                    "inlier_rms_m": stats([r["inlier_rms_m"] for r in scored]),
                    "degenerate_scans": sum(1 for r in scored if r.get("degenerate")),
                    "compute_ms": {k: v * 1000 for k, v in stats([r["compute_s"] for r in scored]).items()},
                    "limits": ours.limits},
        "stock_avlite_icp": {"position_error_m": stats([r["stock_pos_err"] for r in rows]),
                             "yaw_error_rad": stats([r["stock_yaw_err"] for r in rows]),
                             "final_position_error_m": rows[-1]["stock_pos_err"] if rows else None,
                             "compute_ms": {k: v * 1000 for k, v in stats([r["stock_compute_s"] for r in rows]).items()}},
        "note": "IPS is the offline reference only; scan/pose skew (~0.04 s) is included in the error; inlier "
                "statistics are match diagnostics, not a calibrated covariance",
        "rows": rows}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rows",)}, indent=1))


if __name__ == "__main__":
    main()
