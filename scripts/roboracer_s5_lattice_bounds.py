#!/usr/bin/env python3
"""S5 (D79 A): lattice track bounds from the C0 map, replacing the plan's LeftBound/RightBound for the lattice only.

The plan's bounds (``c0-s3v1-plan.json``, S3) are outside the real walls by up to 0.24 m in places (S5 §12), and
the lattice's wall inset (half car width + 0.20 m, D78 A) is measured from them. Here the bounds come from the C0
drivable region (the scorer geometry; the same map the plugin's ICP map is built from), per plan waypoint:

1. **Conservative window.** AVLite checks an edge point at arc length s against waypoint
   ``searchsorted(path_s, s, 'left')``, i.e. waypoint i covers s in (S[i-1], S[i]]; edge points are 0.2 m apart.
   Bound i is the narrowest real-wall offset (along the line normal) over [S[i-1] - 0.2, S[i] + 0.2], sampled
   every 0.01 m.
2. **2-D margin.** The car's side at the lattice limit (d = bound -/+ 0.20) must be >= 0.20 m from the walls in
   true 2-D distance (a notch or corner can be closer than along the normal); a waypoint that falls short is
   tightened until it holds.
3. **Checks.** No bound is outside a real wall anywhere; the racing line (d = 0) is inside the lattice limit at
   every waypoint (so clear laps are unaffected).

Writes ``roboracer/data/c0-lattice-bounds.json`` and its provenance. Offline; nothing is simulated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "roboracer/data/c0-s3v1-plan.json"
GEOMETRY = REPO.parent.parent.parent / "artifacts/s1/20261006T051902Z-s1-05/c0-geometry.json"
OUTPUT = REPO / "roboracer/data/c0-lattice-bounds.json"
SCHEMA = "roboracer.lattice-bounds/1"
HALF_WIDTH_M = 0.288 / 2
WALL_MARGIN_M = 0.20  # D78 A (U3 wall)
EDGE_POINT_SPACING_M = 0.2  # 10 points on a 2 m edge (C0_PLANNING)
STEP_M = 0.01


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(plan: dict, region, *, window=EDGE_POINT_SPACING_M, step=STEP_M, margin=WALL_MARGIN_M):
    from shapely.geometry import LineString, Point
    line = [(x, y) for x, y, _ in plan["ReferenceLine"]]
    S = np.concatenate([[0.0], np.cumsum([math.dist(a, b) for a, b in zip(line, line[1:])])])
    lap = float(S[-1])
    walls = region.boundary

    def frame(s):
        s = s % lap
        i = int(np.clip(np.searchsorted(S, s, side="right") - 1, 0, len(line) - 2))
        a, b = line[i], line[i + 1]
        seg = math.dist(a, b)
        f = (s - S[i]) / seg
        p = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
        t = ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
        return p, (-t[1], t[0])

    def walls_at(s):
        p, n = frame(s)
        sec = LineString([(p[0] - 3 * n[0], p[1] - 3 * n[1]), (p[0] + 3 * n[0], p[1] + 3 * n[1])]).intersection(region)
        piece = [g for g in getattr(sec, "geoms", [sec]) if g.distance(Point(p)) < 1e-6][0]
        ends = [(c[0] - p[0]) * n[0] + (c[1] - p[1]) * n[1] for c in piece.coords]
        return max(ends), min(ends)

    def xy(s, d):
        p, n = frame(s)
        return (p[0] + d * n[0], p[1] + d * n[1])

    left, right, tightened = [], [], 0
    for i in range(len(line)):
        lo = (S[i - 1] if i > 0 else S[0]) - window
        hi = S[i] + window
        samples = np.arange(lo, hi + 1e-9, step)
        offsets = [walls_at(s) for s in samples]
        lb = min(o[0] for o in offsets)
        rb = max(o[1] for o in offsets)
        for _ in range(100):  # 2-D margin at the lattice limit
            short_l = min(Point(xy(s, lb - margin)).distance(walls) for s in samples) - margin
            short_r = min(Point(xy(s, rb + margin)).distance(walls) for s in samples) - margin
            if short_l >= -1e-4 and short_r >= -1e-4:
                break
            tightened += 1
            if short_l < -1e-4:
                lb += short_l - 0.002
            if short_r < -1e-4:
                rb -= short_r - 0.002
        left.append(round(float(lb), 5))
        right.append(round(float(rb), 5))
    return S, left, right, tightened, walls_at, frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--geometry", type=Path, default=GEOMETRY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    from shapely import wkt
    plan = json.loads(args.plan.read_text())
    region = wkt.loads(json.loads(args.geometry.read_text())["region_wkt"])
    S, left, right, tightened, walls_at, _ = build(plan, region)
    inset = HALF_WIDTH_M + WALL_MARGIN_M
    # checks
    lap = float(S[-1])
    worst_outside = 0.0
    for s in np.arange(0.0, lap, STEP_M):
        i = int(np.clip(np.searchsorted(S, s, side="left"), 0, len(S) - 1))
        lw, rw = walls_at(s)
        worst_outside = max(worst_outside, left[i] - lw, rw - right[i])
    line_room = min(min(l - inset for l in left), min(-r - inset for r in right))
    old_excess = [max(ol - l, r - orr) for ol, l, orr, r in zip(plan["LeftBound"], left, plan["RightBound"], right)]
    worst_outside, line_room = float(worst_outside), float(line_room)
    checks = {"no bound outside a real wall (m, <= 0.001: 0.01 m sampling, 1e-5 rounding)": worst_outside,
              "racing line inside the lattice limit at every waypoint (min room, m, >= 0)": line_room,
              "waypoints tightened for the 2-D margin": tightened,
              "plan bound minus map bound, max (m)": float(max(old_excess))}
    ok = bool(worst_outside <= 1e-3 and line_room >= 0.0)
    data = {"schema": SCHEMA, "plan_sha256": sha256(args.plan), "waypoints": len(left),
            "reference_line_first_last": [plan["ReferenceLine"][0][:2], plan["ReferenceLine"][-1][:2]],
            "LeftBound": left, "RightBound": right}
    args.output.write_text(json.dumps(data) + "\n")
    record = {"schema": "roboracer.lattice-bounds-provenance/1", "file": args.output.name, "sha256": sha256(args.output),
              "inputs": {"plan": {"path": str(args.plan.relative_to(REPO)), "sha256": sha256(args.plan)},
                         "geometry": {"path": str(args.geometry), "sha256": sha256(args.geometry)}},
              "builder": {"path": "scripts/roboracer_s5_lattice_bounds.py", "sha256": sha256(Path(__file__))},
              "parameters": {"window_m": EDGE_POINT_SPACING_M, "step_m": STEP_M, "wall_margin_m": WALL_MARGIN_M,
                             "half_width_m": HALF_WIDTH_M},
              "checks": checks, "passed": ok}
    args.output.with_name(args.output.stem + ".provenance.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record["checks"] | {"passed": ok}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
