#!/usr/bin/env python3
"""S4-05 M4 baseline: aggregate stage-s4 runs (T1/T2/T3) into per-case spreads for proposing M4 criteria.

Reads, per run, the live-check judge (``roboracer_s4_judge.py``) and the run's tick log. Reports per case:
pass count; lap time (T1/T2, whole-run basis); minimum obstacle and wall clearance; lateral swerve (T1/T2); blocked
latch distance/speed and rest clearance (T3); ICP validity and error against IPS (per tick, scan-time skew included);
and costs: stack tick, ICP compute, detection compute (scans processed), lattice replan.

usage: roboracer_s4_baseline.py --runs <results dir> [...] --output <json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def stats(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    return {"n": len(v), "min": v[0], "p50": v[len(v) // 2], "p95": v[min(len(v) - 1, int(len(v) * 0.95))], "max": v[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="runner results dirs with <name>-judge.json beside")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = {}
    for results in args.runs:
        judge = json.loads(results.with_name(results.name + "-judge.json").read_text())
        run = next(results.glob("run-*"))
        ticks = [json.loads(l) for l in (run / "plugin-ticks.jsonl").read_text().splitlines() if l.strip()]
        driving = [t for t in ticks if t.get("phase") == "run"]
        c = cases.setdefault(judge["case"], {"runs": [], "lap_s": [], "obstacle_m": [], "wall_m": [], "swerve_m": [],
                                             "rest_m": [], "latch_path_m": [], "latch_speed_mps": [], "icp_p95_m": [],
                                             "icp_max_m": [], "icp_invalid": 0, "tick_ms": [], "icp_ms": [],
                                             "detect_ms": [], "replan_ms": [], "yaw_error_rad": [], "passed": 0})
        c["runs"].append(str(results))
        c["passed"] += bool(judge["passed"])
        c["lap_s"].append(judge["laps"][0]["lap_time_s"] if judge.get("laps") else None)
        c["obstacle_m"].append(judge["min_obstacle_clearance_m"])
        c["wall_m"].append(judge["min_wall_clearance_m"])
        c["swerve_m"].append(abs(judge["max_swerve_m"]) if judge.get("max_swerve_m") is not None else None)
        if judge["case"] == "t3":
            c["rest_m"].append(judge["rest_obstacle_clearance_m"])
            c["latch_path_m"].append((judge.get("blocked") or {}).get("path_m"))
            c["latch_speed_mps"].append((judge.get("blocked") or {}).get("speed_mps"))
        icp = judge.get("icp_error_vs_ips_m") or {}
        c["yaw_error_rad"].append(judge.get("max_abs_yaw_error_rad"))
        c["icp_p95_m"].append(icp.get("p95"))
        c["icp_max_m"].append(icp.get("max"))
        c["icp_invalid"] += sum(v for k, v in (judge.get("icp_states_while_driving") or {}).items() if k != "valid")
        c["tick_ms"] += [(t["end_ns"] - t["start_ns"]) / 1e6 for t in driving if t.get("stepped")]
        c["icp_ms"] += [1e3 * (t.get("localization") or {}).get("compute_s") for t in driving
                        if (t.get("localization") or {}).get("compute_s") is not None]
        seen = set()
        for t in driving:
            s4 = t.get("s4") or {}
            stamp = s4.get("obstacles_stamp")
            ms = (s4.get("detector") or {}).get("compute_s")
            if stamp not in seen and ms is not None:
                seen.add(stamp)
                c["detect_ms"].append(1e3 * ms)
            replan = (s4.get("planner") or {}).get("replan_s")
            if replan is not None:
                c["replan_ms"].append(1e3 * replan)
    report = {"schema": "roboracer.s4-baseline/1", "cases": {}}
    for name, c in sorted(cases.items()):
        report["cases"][name] = {"runs": len(c["runs"]), "passed": c["passed"], "icp_invalid_driving_ticks": c["icp_invalid"],
                                 **{k: stats(v) for k, v in c.items() if isinstance(v, list) and k != "runs"},
                                 "run_dirs": c["runs"]}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    for name, c in report["cases"].items():
        print(name, {k: (v if not isinstance(v, dict) else {s: round(x, 3) for s, x in v.items() if s != "n"})
                     for k, v in c.items() if k != "run_dirs" and v is not None})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
