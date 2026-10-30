#!/usr/bin/env python3
"""S4 F4 fault cases (D60) on stage s4: judge one run against the V1 stop criteria from the injection.

- F4-2 stale obstacle observation (the detector frozen while scans keep arriving): the stage aborts with
  "no new obstacle observation" (D56).
- F4-3 planning failure (every lattice replan raises): the lattice latches "blocked" with a planner-error reason and
  the episode ends as "blocked" (D58).

Common: injected at 4.0 s of run time; from the injection the car is at rest (IPS speed < 0.02 m/s) within 1.7 s
and has travelled <= 0.65 m (V1, D37/D39 B); no positive throttle applied by the guard after injection + 1.7 s;
no wall or obstacle contact and no off-track (independent scorer); no guard fault.
(F4-1, the blocked path, is the T3 fixture and is judged by roboracer_s4_judge.py --case t3.)

usage: roboracer_s4_f4.py --results <runner results dir> --episode <episode export dir> --output <json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roboracer_f1 import stop_after, truth  # noqa: E402

STOP_S, TRAVEL_M, INJECT_S = 1.7, 0.65, 4.0


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
    episode = json.loads((args.episode / "episode.json").read_text())
    inject = (status.get("s4") or {}).get("f4") or {}
    case = inject.get("case")
    checks = {"fault injected at 4.0 s of run time": bool(inject) and abs(inject.get("run_elapsed_s", 0) - INJECT_S) <= 0.15}
    out = {"schema": "roboracer.s4-f4/1", "run": str(run), "case": case, "checks": checks, "injection": inject}
    if not inject:
        out["passed"] = False
        args.output.write_text(json.dumps(out, indent=1) + "\n")
        print(json.dumps({"case": case, "passed": False}))
        return 1
    t0 = inject["injected_ns"]
    blocked = status["s4"].get("blocked") or {}
    if case == "f4-2":
        checks["aborted on the stale obstacle observation (D56)"] = (status.get("abort") or "").startswith(
            "no new obstacle observation")
    else:
        checks["blocked latched on the planner error (D58)"] = (blocked.get("reason") or "").startswith("planner error")
        checks["episode finished as blocked"] = episode["outcome"] == {"state": "finished", "reason": "blocked"}
    series = truth(rows(run / "bridge-frames.jsonl"))
    stop = stop_after(series, t0)
    checks[f"rest <= {STOP_S} s from the injection"] = stop["stop_s"] is not None and stop["stop_s"] <= STOP_S
    checks[f"travel <= {TRAVEL_M} m from the injection"] = stop["travel_m"] <= TRAVEL_M
    guard = rows(run / "guard/guard-trace.jsonl")
    late = [g for g in guard if g.get("k") == "step" and g["mono"] >= t0 + int(STOP_S * 1e9) and g["out"][0] > 0]
    checks[f"no positive throttle after injection + {STOP_S} s"] = not late
    checks["no guard fault"] = not any(g.get("k") == "event" and " state fault" in " " + g["text"] for g in guard)
    checks["no contact (walls, obstacle) and no off-track"] = episode["contact_free_and_on_track"]
    out.update(passed=all(checks.values()), stop=stop, abort=status.get("abort"), blocked=blocked or None,
               outcome=episode["outcome"], late_positive_throttle_steps=len(late),
               min_obstacle_clearance_m=episode["score"].get("min_obstacle_clearance_m"))
    args.output.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"case": case, "passed": out["passed"], "checks": checks, "stop": stop}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
