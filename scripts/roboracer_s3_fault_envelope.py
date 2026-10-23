#!/usr/bin/env python3
"""S3 speed steps: fault-stop envelope of a C0 plan (no motion).

A fault (e.g. runner loss, F1-7) leaves the car running straight on its current heading until it stops:
steering returns to 0 with the guard lease. Measured at V1 (0.5 m/s): F1-7 travels 0.49-0.54 m, i.e. about
1.08 s x speed. For every plan point this sweeps the car footprint straight ahead for ``k x v(s)`` (v = the
plan's target speed there) and reports the smallest clearance to the drivable region's edge; a plan passes
if every sweep keeps ``--min-clearance``.

Corner speeds: with straight-line travel d = k v from a curve of radius R the drift is about d^2 / (2R), so
capping drift at delta means v^2 / R <= 2 delta / k^2 -- a lateral-acceleration limit. The velocity
profile's ``lateral_accel_mps2`` therefore bounds the fault drift in every corner at once.

usage: roboracer_s3_fault_envelope.py --geometry <c0-geometry.json> --caps 0.5 0.75 1.0 --lateral-accel 0.24
       [--k 1.3] [--min-clearance 0.05] --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def sweep_clearance(payload, geometry, region, k_s: float):
    from shapely.affinity import rotate, translate
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    fp = geometry["footprint"]
    body = Polygon([(fp["x_min"], fp["y_min"]), (fp["x_max"], fp["y_min"]), (fp["x_max"], fp["y_max"]),
                    (fp["x_min"], fp["y_max"])])
    line = [p[:2] for p in payload["ReferenceLine"]]
    speed = payload["ReferenceSpeed"]
    boundary = region.boundary
    worst = (math.inf, None)
    for i in range(len(line) - 1):
        (x0, y0), (x1, y1) = line[i], line[i + 1]
        heading = math.atan2(y1 - y0, x1 - x0)
        d = k_s * speed[i]
        start = translate(rotate(body, heading, origin=(0, 0), use_radians=True), x0, y0)
        end = translate(start, d * math.cos(heading), d * math.sin(heading))
        swept = unary_union([start, end]).convex_hull
        clearance = swept.distance(boundary) if region.contains(swept) else -swept.difference(region).area
        if clearance < worst[0]:
            worst = (clearance, i)
    return worst


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--caps", type=float, nargs="+", required=True)
    parser.add_argument("--lateral-accel", type=float, nargs="+", default=[3.0])
    parser.add_argument("--accel", type=float, default=0.5, help="profile acceleration limit (throttle rise 0.10/s x K)")
    parser.add_argument("--k", type=float, default=1.3, help="fault travel per unit speed, s")
    parser.add_argument("--min-clearance", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from shapely import wkt
    from roboracer.planning.c0_track import build_c0_plan
    from roboracer.planning.velocity_profile import VelocityProfileConfig

    geometry = json.loads(args.geometry.read_text())
    region = wkt.loads(geometry["region_wkt"])
    rows = []
    for a_lat in args.lateral_accel:
        for cap in args.caps:
            profile = VelocityProfileConfig(top_speed_mps=cap, min_speed_mps=min(0.3, cap), lateral_accel_mps2=a_lat,
                                            brake_decel_mps2=2.0, accel_limit_mps2=args.accel, curvature_window_m=0.4,
                                            curvature_hold_m=0.5)
            payload, report = build_c0_plan(geometry["centerline"], region, spacing_m=0.1, boundary_margin_m=0.3,
                                            profile=profile, start_pin_m=0.05)
            clearance, index = sweep_clearance(payload, geometry, region, args.k)
            speed = payload["ReferenceSpeed"]
            row = {"lateral_accel_mps2": a_lat, "cap_mps": cap, "min_speed_mps": round(min(speed), 3),
                   "estimated_lap_s": round(report["profile"]["estimated_lap_s"], 2),
                   "fault_sweep_min_clearance_m": round(clearance, 3), "worst_point": index,
                   "worst_point_speed_mps": round(speed[index], 3) if index is not None else None,
                   "passes": clearance >= args.min_clearance}
            rows.append(row)
            print(json.dumps(row), flush=True)
    args.output.write_text(json.dumps({"k_s": args.k, "min_clearance_m": args.min_clearance, "rows": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
