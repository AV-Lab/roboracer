#!/usr/bin/env python3
"""S4 first live checks: judge one stage-s4 episode against the pass criteria fixed before the runs (S4 §7).

T1/T2 (pass cases): one lap; passed on the expected side; no wall or obstacle contact and no off-track (independent
scorer); no abort; ICP valid on every driving tick. T3 (blocked): finished as "blocked"; at rest with the footprint
>= 0.30 m from the obstacle (D58); no contact; no abort; ICP valid on every driving tick.

Also reported: obstacle and wall clearance, B's lateral swerve (largest |d| from the racing line around the obstacle,
from IPS), the blocked latch, ICP error against IPS (time-matched per tick: the ICP pose against the IPS of the
snapshot used), and stack tick times.

usage: roboracer_s4_judge.py --episode <episode export dir> --results <runner results dir> --case t1|t2|t3 --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REST_CLEARANCE_M = 0.30  # D58


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--case", choices=("t1", "t2", "t3", "lap"), required=True,
                        help="lap: the release profile on the clear track (no fixture; S5 M5)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from shapely.geometry import LinearRing, Point, Polygon
    episode = json.loads((args.episode / "episode.json").read_text())
    score = json.loads((args.episode / "score.json").read_text())
    run = next(args.results.glob("run-*"))
    status = json.loads((run / "plugin-observer-status.json").read_text())
    ticks = [json.loads(l) for l in (run / "plugin-ticks.jsonl").read_text().splitlines() if l.strip()]
    fixture = status["s4"]["fixture"]
    obstacle = Polygon(json.loads(Path(fixture["path"]).read_text())["obstacles"][0]["polygon"]) if fixture else None
    plan = json.loads((Path(__file__).resolve().parents[1] / "roboracer/data/c0-s3v1-plan.json").read_text())
    line = LinearRing([p[:2] for p in plan["ReferenceLine"]])

    driving = [t for t in ticks if t.get("phase") == "run"]
    icp_states = {}
    errors = []
    swerve = []
    for t in driving:
        loc = t.get("localization") or {}
        icp_states[loc.get("state")] = icp_states.get(loc.get("state"), 0) + 1
        if loc.get("state") == "valid" and loc.get("pose") and t.get("pose"):
            errors.append(math.dist(loc["pose"][:2], t["pose"][:2]))
        if t.get("pose") and obstacle is not None:
            p = Point(t["pose"][0], t["pose"][1])
            if p.distance(obstacle) < 1.5:
                # signed lateral offset from the racing line: + left of the driving direction
                s = line.project(p)
                a, b = line.interpolate(s), line.interpolate(min(s + 0.05, line.length))
                cross = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
                swerve.append(math.copysign(p.distance(line), cross))
    end = episode["outcome"]
    s = episode["score"]
    contact_free = episode["contact_free_and_on_track"]
    icp_ok = set(icp_states) <= {"valid"} and bool(icp_states)
    checks = {"no_abort": end["state"] != "aborted", "contact_free_and_on_track": contact_free,
              "icp_valid_while_driving": icp_ok}
    blocked = status["s4"].get("blocked")
    if args.case == "lap":
        checks["one_lap"] = episode["completed_laps"] >= 1
        checks["not_blocked"] = blocked is None
        checks["no fixture (clear track)"] = fixture is None
    elif args.case in ("t1", "t2"):
        checks["one_lap"] = episode["completed_laps"] >= 1
        side = max(swerve, key=abs) if swerve else 0.0
        checks["expected_side"] = (side > 0) if args.case == "t1" else (side < 0)
        checks["not_blocked"] = blocked is None
    else:
        checks["finished_blocked"] = end["state"] == "finished" and end["reason"] == "blocked"
        last = score.get("samples", [])[-1] if score.get("samples") else {}
        rest = last.get("obstacle_clearance_m")
        checks["rest_clearance_ge_0.30"] = rest is not None and rest >= REST_CLEARANCE_M
    tick_ms = sorted((t["end_ns"] - t["start_ns"]) / 1e6 for t in ticks if t.get("stepped"))
    report = {"schema": "roboracer.s4-live-check/1", "case": args.case, "passed": all(checks.values()),
              "checks": checks, "outcome": end, "laps": s.get("laps"),
              "min_obstacle_clearance_m": s.get("min_obstacle_clearance_m"),
              "min_wall_clearance_m": s.get("min_clearance_m"),
              "obstacle_contact_events": s.get("obstacle_contact_events"),
              "rest_obstacle_clearance_m": (score.get("samples") or [{}])[-1].get("obstacle_clearance_m"),
              "max_swerve_m": max(swerve, key=abs) if swerve else None, "blocked": blocked,
              "icp_states_while_driving": icp_states,
              "icp_error_vs_ips_m": {"p50": sorted(errors)[len(errors) // 2], "p95": sorted(errors)[int(len(errors) * 0.95)],
                                     "max": max(errors)} if errors else None,
              "stack_tick_ms": {"p50": tick_ms[len(tick_ms) // 2], "max": tick_ms[-1]} if tick_ms else None,
              "max_abs_yaw_error_rad": max((abs((t.get("controller") or {}).get("yaw_error_rad") or 0.0) for t in driving),
                                           default=None),
              "safe_stop_yaw_error_rad": (status.get("controller_config") or {}).get("safe_stop_yaw_error_rad"),
              "tick_overruns": status.get("tick_overruns"),
              "note": "ICP error compares the tick's ICP pose with the IPS of the same tick's snapshot (scan-time skew "
                      "included); virtual obstacles (D54 A): contact is a scored footprint overlap"}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("case", "passed", "checks", "outcome")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
