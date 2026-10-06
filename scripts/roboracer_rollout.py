#!/usr/bin/env python3
"""Offline kinematic rollout of the reactive controller on C0 (S1-05 lap proposal evidence; no motion).

Not a simulator substitute and not acceptance evidence: a planning check that a controller
variant can plausibly complete the qualified C0 loop inside the stage limits before any lap is
proposed for live motion.

Model (all from S1 measurements):
- scan: 2D ray cast from the LiDAR mount (0.2733 m ahead of the rear axle) against the boundary
  of the qualified wall footprint, 1081 beams CCW from -135 deg, 0.06..10 m; validated against
  recorded scans (``validate``);
- cadence: one observation per 0.2 s of simulation time (telemetry ~5 Hz); the command computed
  from it is applied after LATENCY_S (tick wait + generation -> guard accept, D7 p95 rounded up);
- speed: first-order to the target (tau 0.1 s; the M3 plant settles within one frame), capped at
  0.35 m/s (u_max 0.07 x K 5.02); steering: slew 183 deg/s to the command, +-30 deg lock;
- kinematics: rear-axle bicycle, wheelbase 0.324 m, integrated at 0.01 s.
Stack limits mirrored from the M5 StackStage: abort on side (80..100 deg) < 0.15 m, front
(+-10 deg) < 0.5 m, requested |steer| above the stage limit. The independent scorer
(roboracer_scoring.score) judges laps, contact and off-track from the rollout frames.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roboracer_scoring as rs  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
LIDAR_MOUNT_X = 0.2733
BEAMS, ANGLE_MIN, STEP = 1081, math.radians(-135.0), math.radians(0.25)
RANGE_MIN, RANGE_MAX = 0.06, 10.0
WHEELBASE = 0.324
FRAME_S, PHYSICS_S, LATENCY_S = 0.2, 0.01, 0.25
SPEED_TAU_S, SPEED_CAP = 0.1, 0.35
SLEW_RAD_S, LOCK_RAD = math.radians(183.0), math.radians(30.0)
BEAM_ANGLES = ANGLE_MIN + STEP * np.arange(BEAMS)


def wall_segments(walls) -> np.ndarray:
    segs = []
    for poly in getattr(walls, "geoms", [walls]):
        for ring in [poly.exterior, *poly.interiors]:
            xy = np.asarray(ring.coords)
            segs.append(np.hstack([xy[:-1], xy[1:]]))
    return np.vstack(segs)


def cast(segments: np.ndarray, x, y, yaw) -> np.ndarray:
    """Ranges (inf = no return) from the LiDAR at rear-axle pose (x, y, yaw)."""
    ox, oy = x + LIDAR_MOUNT_X * math.cos(yaw), y + LIDAR_MOUNT_X * math.sin(yaw)
    a = yaw + BEAM_ANGLES
    dx, dy = np.cos(a)[:, None], np.sin(a)[:, None]
    ex, ey = (segments[:, 2] - segments[:, 0])[None], (segments[:, 3] - segments[:, 1])[None]
    wx, wy = (segments[:, 0] - ox)[None], (segments[:, 1] - oy)[None]
    den = dx * ey - dy * ex
    ok = np.abs(den) > 1e-12
    den = np.where(ok, den, 1.0)
    t = (wx * ey - wy * ex) / den
    u = (wx * dy - wy * dx) / den
    hit = ok & (t >= RANGE_MIN) & (t <= RANGE_MAX) & (u >= 0) & (u <= 1)
    return np.where(hit, t, np.inf).min(axis=1)


def points(ranges):
    finite = np.isfinite(ranges)
    return np.stack([ranges[finite] * np.cos(BEAM_ANGLES[finite]), ranges[finite] * np.sin(BEAM_ANGLES[finite])], 1)


def sector_min(ranges, low_deg, high_deg):
    lo, hi = int((low_deg + 135) / 0.25), int((high_deg + 135) / 0.25)
    values = ranges[lo:hi + 1]
    values = values[np.isfinite(values)]
    return float(values.min()) if len(values) else math.inf


def rollout(geometry: dict, policy, steer_limit: float, max_time_s: float, distance_m: float,
            latency_s: float = LATENCY_S) -> dict:
    """policy(points) -> (target speed, steer, detail). Ends at distance, time or a stack abort."""
    from shapely import wkt
    segments = wall_segments(wkt.loads(geometry["walls_wkt"]))
    (x, y), yaw = geometry["spawn"]["xy"], geometry["spawn"]["yaw"]
    v = delta = 0.0
    t, path, pending, applied = 0.0, 0.0, [], (0.0, 0.0)
    frames, ticks, end = [], [], None
    next_frame = 0.0
    while end is None:
        if t >= next_frame - 1e-9:
            next_frame += FRAME_S
            ranges = cast(segments, x, y, yaw)
            frames.append({"sim_time": t, "x": x, "y": y, "yaw": yaw, "telemetry_seq": len(frames) + 1, "received_ns": 0})
            info = {"t": round(t, 3), "x": x, "y": y, "v": v, "path_m": path, "front10": sector_min(ranges, -10, 10),
                    "left": sector_min(ranges, 80, 100), "right": sector_min(ranges, -100, -80)}
            speed, steer, detail = policy(points(ranges))
            info.update(target_speed=speed, steer=steer, detail=detail)
            ticks.append(info)
            if min(info["left"], info["right"]) < 0.15:
                end = ("abort", "side clearance %.2f m" % min(info["left"], info["right"]))
            elif info["front10"] < 0.5:
                end = ("abort", "forward clearance %.2f m" % info["front10"])
            elif abs(steer) > steer_limit + 1e-9:
                end = ("abort", "requested steer %.3f rad" % abs(steer))
            elif path >= distance_m:
                end = ("finished", "distance")
            elif t >= max_time_s:
                end = ("finished", "time")
            if end is not None:
                break
            pending.append((t + latency_s, (speed, steer)))
        while pending and pending[0][0] <= t + 1e-9:
            applied = pending.pop(0)[1]
        target_v, target_delta = applied
        v += (min(target_v, SPEED_CAP) - v) * (1 - math.exp(-PHYSICS_S / SPEED_TAU_S))
        delta += max(-SLEW_RAD_S * PHYSICS_S, min(SLEW_RAD_S * PHYSICS_S, target_delta - delta))
        delta = max(-LOCK_RAD, min(LOCK_RAD, delta))
        yaw += v * math.tan(delta) / WHEELBASE * PHYSICS_S
        step = v * PHYSICS_S
        x, y, path, t = x + step * math.cos(yaw), y + step * math.sin(yaw), path + step, t + PHYSICS_S
    score = rs.score(geometry, frames)
    return {"end": {"state": end[0], "reason": end[1], "sim_time_s": t, "path_m": path},
            "score": {k: score[k] for k in ("progress_m", "laps", "contact_events", "offtrack_events", "min_clearance_m",
                                        "max_frame_progress_m")},
            "max_abs_steer_rad": max(abs(k["steer"]) for k in ticks),
            "min_side_m": min(min(k["left"], k["right"]) for k in ticks),
            "min_front10_m": min(k["front10"] for k in ticks),
            "mean_speed_mps": path / t if t else 0.0, "ticks": ticks}


def validate(geometry: dict, run: Path, first_raw: Path | None) -> dict:
    """Compare the 2D cast with a recorded full scan and with recorded per-tick sector minima."""
    from shapely import wkt
    segments = wall_segments(wkt.loads(geometry["walls_wkt"]))
    out = {}
    if first_raw is not None:
        frame = json.loads(first_raw.read_text())
        measured = np.array([math.inf if s == "inf" else float(s) for s in frame["V1 LIDAR Range Array"].split()])
        px, py, _ = (float(v) for v in frame["V1 Position"].split())
        yaw = float(frame["V1 Orientation Euler Angles"].split()[2])
        predicted = cast(segments, px, py, yaw)
        both = np.isfinite(measured) & np.isfinite(predicted)
        err = np.abs(measured[both] - predicted[both])
        out["full_scan"] = {"both_finite": int(both.sum()),
                            "finite_mismatch": int((np.isfinite(measured) != np.isfinite(predicted)).sum()),
                            "abs_error_m_p50_p95_max": [float(np.percentile(err, q)) for q in (50, 95, 100)]}
    rows = [json.loads(line) for line in (run / "plugin-ticks.jsonl").read_text().splitlines()]
    seen, errors = set(), {"front10": [], "left": [], "right": []}
    for row in rows:
        if "pose" not in row or row.get("telemetry_seq") in seen:
            continue
        seen.add(row["telemetry_seq"])
        x, y, yaw = row["pose"]
        ranges = cast(segments, x, y, yaw)
        for key, (lo, hi) in (("front10", (-10, 10)), ("left", (80, 100)), ("right", (-100, -80))):
            errors[key].append(sector_min(ranges, lo, hi) - row[key])
    out["sector_minima"] = {k: {"frames": len(v), "error_m_p50_p95_max_abs": [
        float(np.percentile(np.abs(v), 50)), float(np.percentile(np.abs(v), 95)), float(np.max(np.abs(v)))],
        "signed_mean_m": float(np.mean(v))} for k, v in errors.items()}
    out["note"] = "Recorded poses are rounded to 1 mm; the cast uses the plan-view wall footprint"
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--run", type=Path, required=True, help="run-01 directory with plugin-ticks.jsonl")
    v.add_argument("--first-raw", type=Path)
    r = sub.add_parser("rollout")
    r.add_argument("--variant", choices=("a", "lap"), required=True)
    r.add_argument("--steer-limit", type=float, default=0.35)
    r.add_argument("--time", type=float, default=200.0)
    r.add_argument("--distance", type=float, default=33.0)
    r.add_argument("--latency", type=float, default=LATENCY_S, help="observation -> applied command, s")
    for p in (v, r):
        p.add_argument("--geometry", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    geometry = json.loads(args.geometry.read_text())
    if args.mode == "validate":
        result = validate(geometry, args.run, args.first_raw)
        print(json.dumps(result))
    else:
        sys.path.insert(0, str(REPO))
        from roboracer.control import gap_follow as gf
        params = gf.GapFollowParams() if args.variant == "a" else gf.LAP_PARAMS
        params = gf.GapFollowParams(**{**params.__dict__, "max_steer_rad": args.steer_limit})
        result = rollout(geometry, lambda pts: gf.gap_follow(pts, params), args.steer_limit, args.time, args.distance,
                         args.latency)
        result.update(variant=args.variant, params=params.__dict__, latency_s=args.latency)
        print(json.dumps({k: result[k] for k in ("variant", "latency_s", "end", "score", "max_abs_steer_rad", "min_side_m",
                                                 "min_front10_m", "mean_speed_mps")}))
    args.output.write_text(json.dumps(result, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
