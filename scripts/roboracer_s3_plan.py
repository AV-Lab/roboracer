#!/usr/bin/env python3
"""Build the committed C0 plan for stage s3b (S3): the A2RL min-curvature line and velocity profile on the
collider-derived C0 reference, with a provenance record (inputs, parameters, code, sha256).

usage: roboracer_s3_plan.py --geometry <c0-geometry.json> [--speed-cap 0.3] [--output-dir roboracer/data]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PARAMS = {"spacing_m": 0.1, "boundary_margin_m": 0.3, "start_pin_m": 0.05,
          "profile": {"min_speed_mps": 0.1, "lateral_accel_mps2": 3.0, "brake_decel_mps2": 2.0,
                      "accel_limit_mps2": 1.5, "curvature_window_m": 0.4, "curvature_hold_m": 0.5}}


# V2 (D40): corners bounded by the fault drift, lateral 2 x 0.20 m / 1.3 s^2 ~ 0.24 m/s^2; acceleration as the
# supervisor's throttle rise allows (0.10/s x K ~ 0.5 m/s^2).
STAGE_PROFILE = {"s3v2": {"lateral_accel_mps2": 0.24, "accel_limit_mps2": 0.5}}
FAULT_SWEEP_K_S, FAULT_SWEEP_MIN_M, FAULT_SWEEP_GATED = 1.3, 0.05, ("s3v2",)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--stage", choices=("s3b", "s3v1", "s3v2"), default="s3b")
    parser.add_argument("--speed-cap", type=float, default=None, help="default: the stage cap (s3b 0.3, s3v1 0.5)")
    parser.add_argument("--output-dir", type=Path, default=REPO / "roboracer/data")
    args = parser.parse_args()

    from shapely import wkt
    from roboracer.planning.c0_track import build_c0_plan
    from roboracer.planning.velocity_profile import VelocityProfileConfig

    from roboracer.planning.s3b import SPEED_CAP_MPS
    args.speed_cap = args.speed_cap if args.speed_cap is not None else SPEED_CAP_MPS[args.stage]
    geometry = json.loads(args.geometry.read_text())
    profile_params = dict(PARAMS["profile"], **STAGE_PROFILE.get(args.stage, {}))
    profile = VelocityProfileConfig(top_speed_mps=args.speed_cap, **profile_params)
    payload, report = build_c0_plan(geometry["centerline"], wkt.loads(geometry["region_wkt"]),
                                    spacing_m=PARAMS["spacing_m"], boundary_margin_m=PARAMS["boundary_margin_m"],
                                    profile=profile, start_pin_m=PARAMS["start_pin_m"])
    # D40: every plan point's straight-ahead fault sweep (1.3 s x speed) keeps >= 0.05 m to the walls.
    from roboracer_s3_fault_envelope import sweep_clearance
    sweep, worst_point = sweep_clearance(payload, geometry, wkt.loads(geometry["region_wkt"]), FAULT_SWEEP_K_S)
    report["fault_sweep"] = {"k_s": FAULT_SWEEP_K_S, "min_clearance_m": sweep, "worst_point": worst_point,
                             "required_m": FAULT_SWEEP_MIN_M}
    if args.stage in FAULT_SWEEP_GATED and sweep < FAULT_SWEEP_MIN_M:
        raise SystemExit(f"{args.stage} plan fails the fault sweep: {sweep:.3f} m < {FAULT_SWEEP_MIN_M} m")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan = args.output_dir / f"c0-{args.stage}-plan.json"
    plan.write_text(json.dumps(payload) + "\n")
    code = {name: sha256(REPO / name) for name in (
        "roboracer/planning/c0_track.py", "roboracer/planning/racing_line.py", "roboracer/planning/velocity_profile.py")}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    provenance = {
        "schema": "roboracer.s3-plan/1", "stage": args.stage, "plan_file": plan.name, "plan_sha256": sha256(plan),
        "source": {"geometry": str(args.geometry), "geometry_sha256": sha256(args.geometry),
                   "track": geometry.get("track"), "centerline_points": len(geometry["centerline"]),
                   "note": "collider-derived S1-05 geometry, the same source as the scorer's; S3-01 must make the "
                           "driving map a separate validated asset (S3-04)"},
        "a2rl_source": "AV-Lab/a2rl dev 0b5cfa8 (ported, D31)",
        "parameters": dict(PARAMS, profile=profile_params, speed_cap_mps=args.speed_cap), "code_sha256": code, "git_head_at_build": head,
        "report": report}
    (args.output_dir / f"c0-{args.stage}-plan.provenance.json").write_text(json.dumps(provenance, indent=1) + "\n")
    print(json.dumps({"plan": str(plan), "sha256": provenance["plan_sha256"], "report": report}, indent=1))


if __name__ == "__main__":
    main()
