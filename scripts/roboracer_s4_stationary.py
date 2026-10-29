#!/usr/bin/env python3
"""S4 stationary live check analysis: the S4 stack under HoldController with a near fixture (no motion).

Reads a ``--s4-stationary-fixture`` run (``plugin-ticks.jsonl``, ``plugin-observer-status.json``) and reports:
ICP start-up and validity against IPS, obstacle detection against the fixture polygon, the lattice's clear edges
and blocked latch, B's shadow command (target speed, steer), and that every forwarded request stayed zero.

usage: roboracer_s4_stationary.py --run <results/run-01> --fixture <fixture.json> --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from shapely.geometry import Polygon
    status = json.loads((args.run / "plugin-observer-status.json").read_text())
    rows = [json.loads(line) for line in (args.run / "plugin-ticks.jsonl").read_text().splitlines() if line.strip()]
    s4 = [r["s4"] for r in rows if "s4" in r]
    truth = Polygon(json.loads(args.fixture.read_text())["obstacles"][0]["polygon"])
    states, err, hits, centre, blocked_first, targets, steers, clear = {}, [], 0, [], None, [], [], []
    for i, r in enumerate(s4):
        st = r["icp"]["state"]
        states[st] = states.get(st, 0) + 1
        if st == "valid" and r["icp"]["pose"]:
            err.append(math.dist(r["icp"]["pose"][:2], r["icp"]["ips"][:2]))
        on = [o for o in r["obstacles"] if Polygon(_box(*o)).buffer(0.10).intersects(truth)]
        if on:
            hits += 1
            centre.append(min(math.dist(o[:2], (truth.centroid.x, truth.centroid.y)) for o in on))
        if r["blocked"] and blocked_first is None:
            blocked_first = {"tick": i, "reason": r["blocked_reason"]}
        clear.append(r["planner"]["clear_level0_edges"])
        if r["b_shadow"] is not None:
            targets.append(r["b_shadow"]["target_speed"])
            steers.append(r["b_shadow"]["steer"])
    holds = [r["hold_request"] for r in s4 if r["hold_request"] is not None]
    report = {"schema": "roboracer.s4-stationary/1", "run": str(args.run), "fixture": args.fixture.name,
              "ticks_with_s4": len(s4), "icp_initialization": status.get("s4_stationary", {}).get("icp_initialization"),
              "icp_states": states, "icp_error_vs_ips_m": _stats(err),
              "ticks_with_obstacle_detected": hits, "detected_centre_error_m": _stats(centre),
              "false_detections": sum(len(r["obstacles"]) for r in s4) - hits,
              "clear_level0_edges": _stats(clear), "blocked_first": blocked_first,
              "b_shadow_target_speed_mps": _stats(targets), "b_shadow_steer_rad": _stats(steers),
              "hold_requests_all_zero": all(h == 0.0 for h in holds), "hold_requests": len(holds),
              "statistics": status.get("statistics", {}).get("virtual_obstacles"),
              "tick_overruns": status.get("tick_overruns"), "ticks": status.get("ticks")}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


def _box(x, y, theta, length, width):
    c, s = math.cos(theta), math.sin(theta)
    return [(x + c * u - s * v, y + s * u + c * v) for u, v in ((-length / 2, -width / 2), (length / 2, -width / 2),
                                                                 (length / 2, width / 2), (-length / 2, width / 2))]


def _stats(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return {"n": len(values), "min": values[0], "p50": values[len(values) // 2], "max": values[-1]}


if __name__ == "__main__":
    main()
