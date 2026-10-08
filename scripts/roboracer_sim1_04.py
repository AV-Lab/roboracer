#!/usr/bin/env python3
"""SIM1-04 fixtures on recorded runs (no motion, no simulator change): evaluator-only truth, geometry,
footprint, progress and contact for track C0.

Per run (run-01 directories of recorded M6/D13 laps):
- frame/pose/geometry: the qualified wall footprint ray-cast from the recorded truth pose (IPS + IMU yaw,
  LiDAR mount) against the recorded spawn scan and the per-tick LiDAR sector minima of the whole lap;
- spawn: first truth frame vs the geometry spawn;
- progress: laps, progress, lap time and min clearance from the independent scorer (one episode);
- contact (real trace): frames in a mid-lap window are moved towards the nearest wall by their own
  clearance + 0.02 m, which must give exactly one contact event covering the window, and by clearance -
  0.02 m, which must give none. This exercises the scorer on real geometry and real poses.
The GUI lap counter is never read.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roboracer_rollout as ro  # noqa: E402
import roboracer_scoring as rs  # noqa: E402


def shifted(geometry, frames, start, count, extra_m):
    """Copy of `frames` with frames[start:start+count] moved along their footprint's shortest path to the
    walls by (own clearance + extra_m)."""
    from shapely import wkt
    from shapely.ops import nearest_points
    walls = wkt.loads(geometry["walls_wkt"])
    out = [dict(f) for f in frames]
    for i in range(start, start + count):
        f = out[i]
        poly = rs.footprint_polygon(geometry["footprint"], f["x"], f["y"], f["yaw"])
        a, b = nearest_points(poly, walls)
        d = math.dist((a.x, a.y), (b.x, b.y))
        if d == 0:
            continue
        ux, uy = (b.x - a.x) / d, (b.y - a.y) / d
        move = d + extra_m
        f["x"], f["y"] = f["x"] + ux * move, f["y"] + uy * move
    return out


def check_run(run: Path, geometry_path: Path) -> dict:
    geometry = json.loads(geometry_path.read_text())
    episodes = rs.run_episodes(run)
    frames = rs.truth_frames(run, episodes[0] if len(episodes) > 1 else None)
    out = {"run": str(run), "episodes": episodes, "frames": len(frames)}
    first_raw = run / "first-raw-frame.json"
    out["cast"] = ro.validate(geometry, run, first_raw if first_raw.exists() else None)
    out["spawn_offset_m"] = math.dist((frames[0]["x"], frames[0]["y"]), geometry["spawn"]["xy"])
    score = rs.score(geometry, frames)
    out["score"] = {k: score[k] for k in ("progress_m", "laps", "min_clearance_m", "contact_events", "offtrack_events",
                                         "max_frame_progress_m", "episode")}
    # Contact fixture on a mid-lap window where the car is moving.
    start = len(frames) // 2
    hit = rs.score(geometry, shifted(geometry, frames, start, 5, +0.02))
    miss = rs.score(geometry, shifted(geometry, frames, start, 5, -0.02))
    window = (frames[start]["sim_time"], frames[start + 4]["sim_time"])
    events = hit["contact_events"]
    out["contact_fixture"] = {
        "window_sim_time": window,
        "shift_plus_2cm": {"events": events,
                           "one_event_covering_window": len(events) == 1 and events[0]["start_sim_time"] <= window[0] + 0.25
                           and events[0]["end_sim_time"] >= window[1] - 0.25},
        "shift_minus_2cm": {"events": miss["contact_events"], "no_event": not miss["contact_events"]}}
    sm = out["cast"]["sector_minima"]
    out["checks"] = {
        "single episode": len(episodes) == 1,
        "spawn offset <= 0.02 m": out["spawn_offset_m"] <= 0.02,
        "side sector cast error p95 <= 0.01 m": max(sm[k]["error_m_p50_p95_max_abs"][1] for k in ("left", "right")) <= 0.01,
        "front sector cast error p95 <= 0.05 m": sm["front10"]["error_m_p50_p95_max_abs"][1] <= 0.05,
        "exactly one lap scored": len(score["laps"]) == 1,
        "no contact / off-track on the real lap": not score["contact_events"] and not score["offtrack_events"],
        "contact fixture: +2 cm detected as one event": out["contact_fixture"]["shift_plus_2cm"]["one_event_covering_window"],
        "contact fixture: -2 cm not detected": out["contact_fixture"]["shift_minus_2cm"]["no_event"]}
    if out["cast"].get("full_scan"):
        fs = out["cast"]["full_scan"]
        out["checks"]["spawn full-scan cast p95 <= 0.01 m"] = fs["abs_error_m_p50_p95_max"][1] <= 0.01
    out["passed"] = all(out["checks"].values())
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--run", type=Path, action="append", required=True, help="run-01 directory (repeatable)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    results = [check_run(run, args.geometry) for run in args.run]
    args.output.write_text(json.dumps({"schema": "roboracer.sim1-04-fixtures/1", "runs": results,
                                       "passed": all(r["passed"] for r in results)}, indent=1, default=str) + "\n")
    for r in results:
        print(json.dumps({"run": Path(r["run"]).parent.name, "passed": r["passed"],
                          "failed": [k for k, v in r["checks"].items() if not v],
                          "side_p95": max(r["cast"]["sector_minima"][k]["error_m_p50_p95_max_abs"][1] for k in ("left", "right")),
                          "front_p95": r["cast"]["sector_minima"]["front10"]["error_m_p50_p95_max_abs"][1],
                          "spawn_offset": r["spawn_offset_m"], "laps": len(r["score"]["laps"]),
                          "clearance": r["score"]["min_clearance_m"]}))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
