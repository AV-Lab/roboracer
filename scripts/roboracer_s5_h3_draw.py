#!/usr/bin/env python3
"""S5 (D78 A): pre-registered draw of the new held-out obstacle case H3, from geometry only (no simulation).

H2 was used to develop the D78 fix, so it is no longer held out. H3 is fixed by this rule *before* the fix is
evaluated:

- candidates: s on a 0.25 m grid over [3 m, lap - 3 m], at least 2 m from T3 (5.0), H2 (7.0) and T1/T2 (7.5);
  the standard box (0.25 m, centre 0.30 m left or right of the V1 line) must leave exactly one passable side
  (car width + 2 x 0.10 m, as the fixture builder checks);
- narrowing class: candidates whose track width at the box is at or below the median candidate width;
- draw: index = sha256(KEY) mod the number of narrow candidates.

Writes the fixture and its provenance with the S4 builder's format (``--write``), or prints the draw only.

D79 A (H4): H3 was then used to find the plan-bound error, so H4 is drawn the same way before that fix, with
``--key`` "roboracer S5 D79 A H4 draw 2026-11-02", ``--exclude-s 14.75`` (H3) and ``--name h4``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

from roboracer_s4_fixtures import GEOMETRY, PLAN, REPO, SCHEMA, frame_at, gaps, rectangle, sha256

KEY = "roboracer S5 D78 A H3 draw 2026-11-02"
USED_S = (5.0, 7.0, 7.5)
BOX, OFFSET, MARGIN = 0.25, 0.30, 0.10


def width(region, p, n):
    from shapely.geometry import LineString, Point
    section = LineString([(p[0] - 3 * n[0], p[1] - 3 * n[1]), (p[0] + 3 * n[0], p[1] + 3 * n[1])]).intersection(region)
    return [g for g in getattr(section, "geoms", [section]) if g.distance(Point(p)) < 1e-6][0].length


def candidates(line, region, needed, used_s=USED_S):
    length = sum(math.dist(a, b) for a, b in zip(line, line[1:]))
    out, k = [], 0
    while 3.0 + 0.25 * k <= length - 3.0:
        s = 3.0 + 0.25 * k
        k += 1
        if any(abs(s - u) < 2.0 for u in used_s):
            continue
        p, t, n = frame_at(line, s)
        # box right of the line -> pass on the left (as T1); box left -> pass on the right (as T2)
        for side, lo, hi in (("left", -OFFSET - BOX / 2, -OFFSET + BOX / 2), ("right", OFFSET - BOX / 2, OFFSET + BOX / 2)):
            polygon = rectangle(p, t, n, BOX, lo, hi)
            side_gaps = gaps(region, polygon, p, n)
            ok = {key: v >= needed for key, v in side_gaps.items()}
            if ok[f"{side}_m"] and not ok["right_m" if side == "left" else "left_m"]:
                out.append({"s": s, "pass": side, "width_m": width(region, p, n), "gaps_m": side_gaps,
                            "polygon": polygon})
    return length, out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path, help="directory to write the fixture + provenance into")
    parser.add_argument("--key", default=KEY)
    parser.add_argument("--exclude-s", type=float, action="append", default=[], help="also keep 2 m from this s")
    parser.add_argument("--name", default="h3")
    args = parser.parse_args()
    from shapely import wkt
    from shapely.geometry import Polygon
    plan = json.loads(PLAN.read_text())
    geometry = json.loads(GEOMETRY.read_text())
    region = wkt.loads(geometry["region_wkt"])
    car_width = geometry["footprint"]["y_max"] - geometry["footprint"]["y_min"]
    needed = car_width + 2 * MARGIN
    line = [(x, y) for x, y, _ in plan["ReferenceLine"]]
    length, cands = candidates(line, region, needed, USED_S + tuple(args.exclude_s))
    median = statistics.median(c["width_m"] for c in cands)
    narrow = [c for c in cands if c["width_m"] <= median]
    index = int(hashlib.sha256(args.key.encode()).hexdigest(), 16) % len(narrow)
    draw = narrow[index]
    summary = {"key": args.key, "excluded_s": list(USED_S) + args.exclude_s, "lap_length_m": length, "needed_m": needed, "n_candidates": len(cands),
               "median_width_m": median, "n_narrow": len(narrow), "index": index,
               "draw": {k: v for k, v in draw.items() if k != "polygon"}}
    if args.write:
        name = f"{args.name}-{draw['pass']}-pass"
        args.write.mkdir(parents=True, exist_ok=True)
        fixture = args.write / f"{name}.json"
        fixture.write_text(json.dumps({"schema": SCHEMA, "name": name,
                                       "obstacles": [{"id": f"{name}-1", "polygon": draw["polygon"]}]}, indent=1) + "\n")
        record = {"schema": "roboracer.virtual-obstacles-provenance/1", "fixture": fixture.name,
                  "fixture_sha256": sha256(fixture),
                  "inputs": {"plan": {"path": str(PLAN.relative_to(REPO)), "sha256": sha256(PLAN)},
                             "geometry": {"path": str(GEOMETRY), "sha256": sha256(GEOMETRY)}},
                  "builder": {"path": "scripts/roboracer_s5_h3_draw.py", "sha256": sha256(Path(__file__))},
                  "draw": summary,
                  "check": {"gaps_m": draw["gaps_m"], "needed_m": needed, "car_width_m": car_width,
                            "expected_corridor": draw["pass"], "obstacle_area_m2": Polygon(draw["polygon"]).area,
                            "obstacle_inside_region_m2": Polygon(draw["polygon"]).intersection(region).area}}
        fixture.with_name(f"{name}.provenance.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
