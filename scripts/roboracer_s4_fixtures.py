#!/usr/bin/env python3
"""S4 (D55): build the T1/T2/T3 virtual-obstacle fixtures on C0 from the committed V1 racing line.

T1 left pass:   a box centred ``--offset`` right of the line at s = ``--pass-s``, aligned with the track.
T2 right pass:  the mirror (left of the line).
T3 fully blocked: a barrier across the whole drivable width at s = ``--block-s``, reaching
                  ``--block-overlap`` into both walls so no gap remains.

Each fixture is written with a provenance record (sha256, inputs, parameters) and a geometry check
against the scorer's drivable region: the free gap on each side of the obstacle along its cross
section, and whether that gap passes the car (footprint width + 2 x margin).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "roboracer/data/c0-s3v1-plan.json"
GEOMETRY = REPO.parent.parent.parent / "artifacts/s1/20261006T051902Z-s1-05/c0-geometry.json"
SCHEMA = "roboracer.virtual-obstacles/1"


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frame_at(line, s_target):
    """Point, unit tangent and unit left normal of the closed polyline at arc length s."""
    s = 0.0
    for a, b in zip(line, line[1:]):
        seg = math.dist(a, b)
        if s + seg >= s_target:
            f = (s_target - s) / seg
            p = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
            t = ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
            return p, t, (-t[1], t[0])
        s += seg
    raise ValueError(f"s = {s_target} beyond the line")


def rectangle(p, t, n, along, across_lo, across_hi):
    """Corners of a rectangle centred on p along the track (+-along/2), from across_lo to across_hi on n."""
    corners = []
    for u, v in ((-along / 2, across_lo), (along / 2, across_lo), (along / 2, across_hi), (-along / 2, across_hi)):
        corners.append([round(p[0] + u * t[0] + v * n[0], 5), round(p[1] + u * t[1] + v * n[1], 5)])
    return corners


def gaps(region, polygon, p, n, reach=3.0):
    """Free length on the left and right of the obstacle along the cross section through p (normal n)."""
    from shapely.geometry import LineString, Polygon
    section = LineString([(p[0] - reach * n[0], p[1] - reach * n[1]), (p[0] + reach * n[0], p[1] + reach * n[1])])
    from shapely.geometry import Point
    crossing = section.intersection(region)
    crossing = [g for g in getattr(crossing, "geoms", [crossing]) if g.distance(Point(p)) < 1e-6]  # this track part only
    free = crossing[0].difference(Polygon(polygon))
    pieces = [free] if free.geom_type == "LineString" else list(getattr(free, "geoms", []))
    out = {"left_m": 0.0, "right_m": 0.0}
    for piece in (g for g in pieces if not g.is_empty):
        mid = piece.interpolate(0.5, normalized=True)
        side = "left_m" if (mid.x - p[0]) * n[0] + (mid.y - p[1]) * n[1] > 0 else "right_m"
        out[side] = max(out[side], piece.length)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--geometry", type=Path, default=GEOMETRY)
    parser.add_argument("--output", type=Path, default=REPO / "scripts/s4-fixtures")
    parser.add_argument("--pass-s", type=float, default=7.5)
    parser.add_argument("--offset", type=float, default=0.45)
    parser.add_argument("--box", type=float, default=0.25)
    parser.add_argument("--block-s", type=float, default=5.0)
    parser.add_argument("--block-depth", type=float, default=0.20)
    parser.add_argument("--block-overlap", type=float, default=0.20)
    parser.add_argument("--margin", type=float, default=0.10, help="clearance per side for a passable corridor (D57)")
    args = parser.parse_args()
    from shapely import wkt
    from shapely.geometry import Polygon

    plan = json.loads(args.plan.read_text())
    geometry = json.loads(args.geometry.read_text())
    region = wkt.loads(geometry["region_wkt"])
    car_width = geometry["footprint"]["y_max"] - geometry["footprint"]["y_min"]
    needed = car_width + 2 * args.margin
    line = [(x, y) for x, y, _ in plan["ReferenceLine"]]
    inputs = {"plan": {"path": str(args.plan.relative_to(REPO)), "sha256": sha256(args.plan)},
              "geometry": {"path": str(args.geometry), "sha256": sha256(args.geometry)}}

    p, t, n = frame_at(line, args.pass_s)
    half = args.box / 2
    cases = {
        "t1-left-pass": (rectangle(p, t, n, args.box, -args.offset - half, -args.offset + half), p, n, "left"),
        "t2-right-pass": (rectangle(p, t, n, args.box, args.offset - half, args.offset + half), p, n, "right"),
    }
    q, tq, nq = frame_at(line, args.block_s)
    cases["t3-blocked"] = (rectangle(q, tq, nq, args.block_depth, -3.0, 3.0), q, nq, None)
    # T3: clip to the drivable region grown by the overlap, so the barrier ends inside both walls.
    from shapely.geometry import Point
    t3 = Polygon(cases["t3-blocked"][0]).intersection(region.buffer(args.block_overlap))
    t3 = [g for g in getattr(t3, "geoms", [t3]) if g.contains(Point(q))]  # the piece across this track part
    if len(t3) != 1:
        raise SystemExit("T3 barrier does not form one polygon across the track at s")
    t3 = t3[0]
    cases["t3-blocked"] = ([[round(x, 5), round(y, 5)] for x, y in list(t3.exterior.coords)[:-1]], q, nq, None)

    args.output.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name, (polygon, at, normal, expected) in cases.items():
        side = gaps(region, polygon, at, normal)
        passable = {k: v >= needed for k, v in side.items()}
        if expected and not (passable[f"{expected}_m"] and not passable["left_m" if expected == "right" else "right_m"]):
            raise SystemExit(f"{name}: expected exactly one passable corridor on the {expected}, got {side}")
        if expected is None and any(passable.values()):
            raise SystemExit(f"{name}: a passable gap remains: {side}")
        fixture = args.output / f"{name}.json"
        fixture.write_text(json.dumps({"schema": SCHEMA, "name": name,
                                       "obstacles": [{"id": f"{name}-1", "polygon": polygon}]}, indent=1) + "\n")
        check = {"gaps_m": side, "needed_m": needed, "car_width_m": car_width, "passable": passable,
                 "expected_corridor": expected, "obstacle_area_m2": Polygon(polygon).area,
                 "obstacle_inside_region_m2": Polygon(polygon).intersection(region).area}
        record = {"schema": "roboracer.virtual-obstacles-provenance/1", "fixture": fixture.name,
                  "fixture_sha256": sha256(fixture), "inputs": inputs, "builder": {"path": "scripts/roboracer_s4_fixtures.py",
                  "sha256": sha256(Path(__file__))}, "parameters": vars(args) | {"plan": None, "geometry": None, "output": None},
                  "check": check}
        fixture.with_name(f"{name}.provenance.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
        summary[name] = check
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
