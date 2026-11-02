#!/usr/bin/env python3
"""S4-06 M4 acceptance (D66-D68): apply U1-U7 to stage-s4 episodes and summarise the matrix.

Each episode needs its live-check judge (``roboracer_s4_judge.py``, ``<results>-judge.json`` beside the results dir).
U1 outcome (T1/T2: one lap on the expected side, not blocked; T3: finished "blocked"); U2 no wall/obstacle contact,
no off-track, no abort; U3 T1/T2 obstacle clearance >= 0.25 m, wall clearance >= 0.20 m (all cases); U4 T3 at rest
>= 1.0 m from the barrier; U5 ICP valid on every driving tick, per-tick error p95 <= 0.05 m and max <= 0.15 m; U6 T1/T2
lap (whole-run basis) <= 72 s; U7 stack tick max <= 80 ms and no tick overruns. D68: strict.

D80 A (S5): U3 is tiered by the free gap on the expected passing side (the fixture's provenance check, reported by
the judge as ``passing_gap``). Full tier (gap >= 0.88 m, or no gap recorded): U3 as above. Narrow tier
(gap < 0.88 m): U3n = obstacle >= 0.10 m and wall >= 0.10 m (the D57 planning margins); U1, U2, U4-U7 unchanged.
0.88 m = car width 0.288 + obstacle 0.25 + wall 0.20 + 2 x 0.07 m measured tracking error (S5 §15).

usage: roboracer_s4_m4.py --runs <results dir> [...] --output <json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OBSTACLE_M, WALL_M, REST_M = 0.25, 0.20, 1.0
ICP_P95_M, ICP_MAX_M = 0.05, 0.15
LAP_S, TICK_MS = 72.0, 80.0
NARROW_GAP_M = 0.88  # D80 A
NARROW_OBSTACLE_M, NARROW_WALL_M = 0.10, 0.10  # D80 A: U3n (D57 planning margins)


def gap_tier(j: dict) -> str:
    gap = (j.get("passing_gap") or {}).get("gap_m")
    return "narrow" if gap is not None and gap < NARROW_GAP_M else "full"


def judge_episode(j: dict) -> dict:
    case, c = j["case"], j["checks"]
    narrow = gap_tier(j) == "narrow"
    obstacle_m, wall_m, u3 = (NARROW_OBSTACLE_M, NARROW_WALL_M, "U3n") if narrow else (OBSTACLE_M, WALL_M, "U3")
    out = {"U2 no contact, off-track or abort": bool(c["contact_free_and_on_track"]) and bool(c["no_abort"]),
           f"{u3} wall clearance >= {wall_m} m": j["min_wall_clearance_m"] is not None and j["min_wall_clearance_m"] >= wall_m}
    icp = j.get("icp_error_vs_ips_m") or {}
    out[f"U5 ICP valid, p95 <= {ICP_P95_M} m, max <= {ICP_MAX_M} m"] = (
        bool(c["icp_valid_while_driving"]) and icp.get("p95") is not None and icp["p95"] <= ICP_P95_M
        and icp["max"] <= ICP_MAX_M)
    tick = j.get("stack_tick_ms") or {}
    out[f"U7 stack tick max <= {TICK_MS} ms, no overruns"] = (tick.get("max") is not None and tick["max"] <= TICK_MS
                                                             and not j.get("tick_overruns"))
    if case == "lap":  # S5 M5: the release profile on the clear track (no obstacle criteria)
        out["U1 one lap, not blocked"] = bool(c["one_lap"]) and bool(c["not_blocked"])
        lap = j["laps"][0]["lap_time_s"] if j.get("laps") else None
        out[f"U6 lap <= {LAP_S} s"] = lap is not None and lap <= LAP_S
    elif case in ("t1", "t2"):
        out["U1 one lap, expected side, not blocked"] = bool(c["one_lap"]) and bool(c["expected_side"]) and bool(c["not_blocked"])
        out[f"{u3} obstacle clearance >= {obstacle_m} m"] = (j["min_obstacle_clearance_m"] is not None
                                                            and j["min_obstacle_clearance_m"] >= obstacle_m)
        lap = j["laps"][0]["lap_time_s"] if j.get("laps") else None
        out[f"U6 lap <= {LAP_S} s"] = lap is not None and lap <= LAP_S
    else:
        out["U1 finished blocked"] = bool(c["finished_blocked"])
        rest = j.get("rest_obstacle_clearance_m")
        out[f"U4 at rest >= {REST_M} m from the barrier"] = rest is not None and rest >= REST_M
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    episodes = []
    for results in args.runs:
        path = results.with_name(results.name + "-judge.json")
        if not path.exists():
            episodes.append({"run": str(results), "case": None, "passed": False, "criteria": {"judge present": False}})
            continue
        j = json.loads(path.read_text())
        criteria = judge_episode(j)
        episodes.append({"run": str(results), "case": j["case"], "passed": all(criteria.values()), "criteria": criteria,
                         "gap_tier": gap_tier(j), "passing_gap": j.get("passing_gap"),
                         "lap_s": j["laps"][0]["lap_time_s"] if j.get("laps") else None,
                         "obstacle_m": j.get("min_obstacle_clearance_m"), "wall_m": j.get("min_wall_clearance_m"),
                         "rest_m": j.get("rest_obstacle_clearance_m"), "icp": j.get("icp_error_vs_ips_m"),
                         "tick_ms": j.get("stack_tick_ms"), "peak_heading_error_rad": j.get("max_abs_yaw_error_rad"),
                         "swerve_m": j.get("max_swerve_m")})
    summary = {}
    for e in episodes:
        s = summary.setdefault(e["case"], {"episodes": 0, "passed": 0, "failed": []})
        s["episodes"] += 1
        s["passed"] += e["passed"]
        if not e["passed"]:
            s["failed"].append({"run": e["run"], "failed": [k for k, v in e["criteria"].items() if not v]})
    report = {"schema": "roboracer.s4-m4/1", "criteria": "D66 U1-U7 (s4-acceptance-proposal v0.1), U3 gap-tiered by D80 A", "rule": "D68 strict",
              "passed": all(e["passed"] for e in episodes), "summary": summary, "episodes": episodes}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"passed": report["passed"], "summary": summary}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
