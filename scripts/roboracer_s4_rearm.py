#!/usr/bin/env python3
"""S4 D63 A: judge one controlled-rearm run on stage s4 (T3 fixture, --s4-rearm blocked|cleared).

Common:
- first "blocked" latch and the 2 s hold at rest; then the stage's disarm / re-arm completed;
- the guard driver's supervised-rearm checks (as F1-5): disarm-request seen; requests rejected not-armed while
  disarmed; re-armed with a new epoch; the old-epoch request rejected stale-epoch; no other rejection; no fault;
- no wall or obstacle contact and no off-track (independent scorer, with the fixture); no abort; ICP valid.
rearm-blocked: the obstacle stays; B latches "blocked" again after the rearm; the episode finishes "blocked"; at the end
  the footprint is >= 0.30 m from the barrier (D58); travel after the rearm <= 0.30 m.
rearm-cleared: the fixture was removed at the disarm; after the rearm B is not blocked again and completes the lap
  (the episode finishes on distance).

usage: roboracer_s4_rearm.py --results <runner results dir> --episode <episode export dir> --output <json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roboracer_f1 import stop_after, truth  # noqa: E402

REST_CLEARANCE_M, CREEP_AFTER_REARM_M = 0.30, 0.30


def rows(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = next(args.results.glob("run-*"))
    status = json.loads((run / "plugin-observer-status.json").read_text())
    bridge = json.loads((run / "bridge-status.json").read_text()) if (run / "bridge-status.json").exists() else {}
    episode = json.loads((args.episode / "episode.json").read_text())
    score = json.loads((args.episode / "score.json").read_text())
    s4 = status.get("s4") or {}
    rearm = s4.get("rearm") or {}
    case = rearm.get("case")
    checks = {"first blocked latch before the rearm": bool(s4.get("blocked_before_rearm")),
              "rearm requested and completed": bool(rearm.get("requested_ns")) and bool(rearm.get("rearmed_ns")),
              "no abort": not status.get("abort"),
              "no contact (walls, obstacle) and no off-track": episode["contact_free_and_on_track"]}
    driver_checks = [c for phase in (bridge.get("guard") or {}).get("phases", []) for c in phase.get("checks", [])]
    for c in driver_checks:
        checks[f"guard driver: {c['name']}"] = bool(c["ok"])
    if not driver_checks:
        checks["guard driver checks present"] = False
    ticks = rows(run / "plugin-ticks.jsonl")
    driving = [t for t in ticks if t.get("phase") == "run"]
    checks["ICP valid on every driving tick"] = bool(driving) and all(
        (t.get("localization") or {}).get("state") == "valid" for t in driving)
    series = truth(rows(run / "bridge-frames.jsonl"))
    after = stop_after(series, rearm["rearmed_ns"]) if rearm.get("rearmed_ns") else None
    if case == "blocked":
        checks["latched blocked again after the rearm"] = bool(s4.get("blocked"))
        checks["episode finished as blocked"] = episode["outcome"] == {"state": "finished", "reason": "blocked"}
        rest = (score.get("samples") or [{}])[-1].get("obstacle_clearance_m")
        checks[f"at the end >= {REST_CLEARANCE_M} m from the barrier"] = rest is not None and rest >= REST_CLEARANCE_M
        checks[f"travel after the rearm <= {CREEP_AFTER_REARM_M} m"] = bool(after) and after["travel_m"] <= CREEP_AFTER_REARM_M
    elif case == "cleared":
        checks["fixture removed at the disarm"] = bool(rearm.get("fixture_removed"))
        checks["not blocked again after the rearm"] = s4.get("blocked") is None
        checks["one lap: finished on distance"] = episode["outcome"] == {"state": "finished", "reason": "distance"}
        checks["lap completed (scorer)"] = episode["completed_laps"] >= 1
    else:
        checks["rearm case recorded"] = False
    out = {"schema": "roboracer.s4-rearm/1", "run": str(run), "case": case, "passed": all(checks.values()),
           "checks": checks, "rearm": rearm, "blocked_before_rearm": s4.get("blocked_before_rearm"),
           "blocked_after_rearm": s4.get("blocked"), "outcome": episode["outcome"],
           "rearm_to_rearmed_s": (rearm["rearmed_ns"] - rearm["requested_ns"]) / 1e9 if rearm.get("rearmed_ns") else None,
           "after_rearm": after, "min_obstacle_clearance_m": score.get("min_obstacle_clearance_m"),
           "final_obstacle_clearance_m": (score.get("samples") or [{}])[-1].get("obstacle_clearance_m"),
           "min_wall_clearance_m": score.get("min_clearance_m"), "laps": score.get("laps")}
    args.output.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"case": case, "passed": out["passed"], "checks": checks}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
