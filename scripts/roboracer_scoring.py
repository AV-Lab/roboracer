#!/usr/bin/env python3
"""Independent episode scoring for track C0 (S1-05): lap, contact and off-track bookkeeping.

The scorer uses only qualified geometry and simulator truth; it never reads the driving stack's
outputs. Truth source: the runner's own Devkit bridge child (``bridge-frames.jsonl``), raw IPS
position (rear-axle centre) and IMU orientation per telemetry frame, timed by IPS acquisition
simulation time.

geometry  Build the C0 reference from the player's serialized colliders (autodrive_scan_check.py
          export): wall footprint = union of the top-down projection of every Proto Track
          triangle (the barriers' full plan-view width, conservative for contact); drivable
          region = the ring between the outer barrier's inner edge and the inner barrier's outer
          edge; centerline = smoothed midpoints between the two edges, arc length 0 at the spawn
          line and increasing in the driving direction; vehicle footprint = plan-view extent of
          the vehicle's own colliders about the rear-axle centre (the IPS point). Third-party
          derived geometry: write it to ignored evidence, never Git.
plot      Draw a geometry file (walls with holes, region, centerline, gates, spawn), optionally
          with one run's truth trajectory.
score     Score one run directory against a geometry file.
          - progress: unwrapped arc length of the rear-axle projection onto the centerline;
          - lap k: cumulative progress >= k*L with the 25/50/75 % gates of that lap passed in
            order (oscillation across the start line cannot accumulate progress);
          - contact: the footprint swept between consecutive frames (convex hull of both
            footprints) overlaps the wall footprint; off-track: the swept footprint is not inside
            the drivable region. Both conservative for 5 Hz sampling; consecutive frames form one
            event with start, end and duration;
          - min clearance: distance from each frame's footprint to the wall footprint;
          - max frame progress: the largest single-frame projection step (cutting the inside of a
            hairpin legitimately advances the projection faster than the car; audit large values).
Fresh JSON outputs only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

GATES = (0.25, 0.5, 0.75)
CENTERLINE_SAMPLES = 2000
SMOOTH_WINDOW = 15


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def yaw_from_quaternion(x, y, z, w):
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


# -- geometry ------------------------------------------------------------------------------------

def build_geometry(colliders: Path, spawn_xy=(0.741, 3.158), spawn_yaw=-math.pi / 2) -> dict:
    import numpy as np
    from shapely.geometry import LinearRing, LineString, Point, Polygon
    from shapely.ops import unary_union

    data = np.load(colliders)
    meta = json.loads(colliders.with_suffix(".json").read_text())
    paths = [c["path"] for c in meta["colliders"]]
    owners = data["owners"]
    track_ids = [i for i, p in enumerate(paths) if p == "Infrastructure/Proto Track"]
    tri = data["triangles"][np.isin(owners, track_ids)][:, :, :2]
    area = 0.5 * np.abs((tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1])
                        - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1]))
    walls = unary_union([Polygon(t) for t in tri[area > 1e-8]]).buffer(0)
    parts = sorted(walls.geoms, key=lambda g: g.area, reverse=True)
    if len(parts) != 2:
        raise SystemExit(f"Expected two barrier loops, found {len(parts)}")
    outer_wall, inner_wall = sorted(parts, key=lambda g: g.envelope.area, reverse=True)
    enclosed = max(outer_wall.interiors, key=lambda r: Polygon(r).area)
    region = Polygon(enclosed).difference(Polygon(inner_wall.exterior))
    if region.geom_type != "Polygon" or len(region.interiors) != 1:
        raise SystemExit("Drivable region is not a single ring")
    spawn = Point(spawn_xy)
    if not region.contains(spawn):
        raise SystemExit("Spawn point is not inside the drivable region")
    outer_edge, inner_edge = LinearRing(region.exterior.coords), LinearRing(region.interiors[0].coords)

    # Centerline: midpoints between the outer edge and its nearest inner-edge points, smoothed.
    length = outer_edge.length
    pts = []
    for k in range(CENTERLINE_SAMPLES):
        p = outer_edge.interpolate(k * length / CENTERLINE_SAMPLES)
        q = inner_edge.interpolate(inner_edge.project(p))
        pts.append(((p.x + q.x) / 2, (p.y + q.y) / 2))
    arr = np.array(pts)
    half = SMOOTH_WINDOW // 2
    padded = np.vstack([arr[-half:], arr, arr[:half]])
    kernel = np.ones(SMOOTH_WINDOW) / SMOOTH_WINDOW
    smooth = np.stack([np.convolve(padded[:, i], kernel, mode="valid") for i in (0, 1)], axis=1)
    ring = LinearRing(smooth)
    # Orient along the driving direction at spawn, then start the parameter at the spawn line.
    s0 = ring.project(spawn)
    a, b = ring.interpolate(s0), ring.interpolate((s0 + 0.05) % ring.length)
    tangent = (b.x - a.x, b.y - a.y)
    if tangent[0] * math.cos(spawn_yaw) + tangent[1] * math.sin(spawn_yaw) < 0:
        ring = LinearRing(smooth[::-1])
        s0 = ring.project(spawn)
    total = ring.length
    centerline = [ring.interpolate((s0 + k * total / CENTERLINE_SAMPLES) % total).coords[0]
                  for k in range(CENTERLINE_SAMPLES)]
    line = LinearRing(centerline)
    widths = [outer_edge.distance(line.interpolate(k * total / 200)) + inner_edge.distance(line.interpolate(k * total / 200))
              for k in range(200)]

    # Vehicle footprint about the rear-axle centre, vehicle frame (x forward, y left).
    sensors = {k: np.array(v) for k, v in meta["sensors_world_unity"].items()}
    rear = sensors["F1TENTH/Transforms/Rear Axle Center"][:3, 3]
    rear_xy = np.array([rear[2], -rear[0]])
    root = sensors["F1TENTH"][:3, :3] @ np.array([0.0, 0.0, 1.0])
    yaw = math.atan2(-root[0], root[2])
    vehicle = data["triangles"][np.isin(owners, [i for i, p in enumerate(paths) if p.startswith("F1TENTH/Vehicle")])]
    rel = vehicle[:, :, :2].reshape(-1, 2) - rear_xy
    c, s = math.cos(-yaw), math.sin(-yaw)
    local = rel @ np.array([[c, s], [-s, c]])
    footprint = {"x_min": float(local[:, 0].min()), "x_max": float(local[:, 0].max()),
                 "y_min": float(local[:, 1].min()), "y_max": float(local[:, 1].max())}

    return {"schema": "roboracer.c0-geometry/1", "track": "C0 = Infrastructure/Proto Track",
            "inputs": {"colliders_npz_sha256": sha256(colliders), "colliders_json_sha256": sha256(colliders.with_suffix(".json")),
                       "player_level0_sha256": meta.get("level0_sha256"), "player_data": meta.get("data")},
            "spawn": {"xy": list(spawn_xy), "yaw": spawn_yaw, "clearance_m": walls.distance(spawn)},
            "centerline": [[round(x, 4), round(y, 4)] for x, y in centerline], "length_m": total,
            "track_width_m": {"min": min(widths), "max": max(widths)},
            "region_wkt": region.wkt, "walls_wkt": walls.wkt, "footprint": footprint, "gates": list(GATES)}


# -- scoring -------------------------------------------------------------------------------------

def footprint_polygon(fp, x, y, yaw):
    from shapely.geometry import Polygon
    c, s = math.cos(yaw), math.sin(yaw)
    corners = [(fp["x_min"], fp["y_min"]), (fp["x_max"], fp["y_min"]), (fp["x_max"], fp["y_max"]), (fp["x_min"], fp["y_max"])]
    return Polygon([(x + c * u - s * v, y + s * u + c * v) for u, v in corners])


def truth_frames(run: Path) -> list[dict]:
    """Raw truth per telemetry frame from the runner's bridge child (independent of the stack)."""
    frames = []
    for line in (run / "bridge-frames.jsonl").read_text().splitlines():
        row = json.loads(line)
        if "motion" not in row or "provenance" not in row:
            continue
        x, y, _ = row["motion"]["Position"]
        q = row["motion"]["Orientation Quaternion"]
        frames.append({"sim_time": row["provenance"]["sources"]["ips"]["sim_time"], "x": x, "y": y,
                       "yaw": yaw_from_quaternion(*q), "telemetry_seq": row["provenance"]["telemetry_seq"],
                       "received_ns": row["received_monotonic_ns"]})
    return frames


def events(flags, frames):
    out, start = [], None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            out.append({"start_sim_time": frames[start]["sim_time"], "end_sim_time": frames[i - 1]["sim_time"],
                        "duration_s": frames[i - 1]["sim_time"] - frames[start]["sim_time"], "frames": i - start})
            start = None
    return out


def score(geometry: dict, frames: list[dict]) -> dict:
    from shapely import wkt
    from shapely.geometry import LinearRing, Point

    region, walls = wkt.loads(geometry["region_wkt"]), wkt.loads(geometry["walls_wkt"])
    line = LinearRing(geometry["centerline"])
    total = geometry["length_m"]
    fp = geometry["footprint"]
    progress, previous_s, laps, gates_passed, max_step = 0.0, None, [], 0, 0.0
    contact, offtrack, clearance, samples = [], [], [], []
    previous_poly = None
    for f in frames:
        poly = footprint_polygon(fp, f["x"], f["y"], f["yaw"])
        swept = poly if previous_poly is None else poly.union(previous_poly).convex_hull
        previous_poly = poly
        s = line.project(Point(f["x"], f["y"]))
        if previous_s is not None:
            delta = s - previous_s
            if delta > total / 2:
                delta -= total
            elif delta < -total / 2:
                delta += total
            progress += delta
            max_step = max(max_step, abs(delta))
        previous_s = s
        lap_index = len(laps)
        within = progress - lap_index * total
        while gates_passed < len(GATES) and within >= GATES[gates_passed] * total:
            gates_passed += 1
        if within >= total and gates_passed == len(GATES):
            laps.append({"lap": lap_index + 1, "sim_time": f["sim_time"]})
            gates_passed = 0
        contact.append(swept.intersects(walls))
        offtrack.append(not region.contains(swept))
        clearance.append(walls.distance(poly))
        samples.append({"sim_time": f["sim_time"], "s_m": s, "progress_m": progress, "clearance_m": clearance[-1]})
    start = frames[0]["sim_time"] if frames else None
    for i, lap in enumerate(laps):
        previous = laps[i - 1]["sim_time"] if i else start
        lap["lap_time_s"] = lap["sim_time"] - previous
    return {"frames": len(frames), "progress_m": progress, "lap_length_m": total, "laps": laps,
            "contact_events": events(contact, frames), "offtrack_events": events(offtrack, frames),
            "min_clearance_m": min(clearance) if clearance else None,
            # Inside a tight bend the projection outruns the car (cutting the inside); audit large steps.
            "max_frame_progress_m": max_step,
            "start_pose": frames[0] if frames else None,
            "start_offset_m": math.dist((frames[0]["x"], frames[0]["y"]), geometry["spawn"]["xy"]) if frames else None,
            "sampling": "telemetry frames (~5 Hz); contact/off-track on the swept footprint between frames",
            "samples": samples}


def _polygon_path(geom):
    """Matplotlib path for a (multi)polygon with holes: exterior CCW, interiors CW (nonzero fill)."""
    import numpy as np
    from matplotlib.path import Path as MplPath
    from shapely.geometry.polygon import orient

    vertices, codes = [], []
    for poly in getattr(geom, "geoms", [geom]):
        poly = orient(poly, 1.0)
        for ring in [poly.exterior, *poly.interiors]:
            xy = np.asarray(ring.coords)
            vertices.extend(xy)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(xy) - 2) + [MplPath.CLOSEPOLY])
    return MplPath(vertices, codes)


def plot(geometry: dict, output: Path, scored: dict | None = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from shapely import wkt

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.add_patch(PathPatch(_polygon_path(wkt.loads(geometry["region_wkt"])), facecolor="#e8f0e8", edgecolor="none",
                           label="drivable region"))
    ax.add_patch(PathPatch(_polygon_path(wkt.loads(geometry["walls_wkt"])), facecolor="#555555", edgecolor="none",
                           label="walls"))
    line = geometry["centerline"] + geometry["centerline"][:1]
    ax.plot([p[0] for p in line], [p[1] for p in line], "--", color="#3366aa", lw=0.8, label="centerline")
    total = geometry["length_m"]
    for fraction in [0.0, *geometry["gates"]]:
        x, y = geometry["centerline"][int(fraction * len(geometry["centerline"])) % len(geometry["centerline"])]
        ax.annotate("start" if fraction == 0 else f"{fraction:.0%}", (x, y), fontsize=8)
    sx, sy = geometry["spawn"]["xy"]
    ax.plot([sx], [sy], "o", color="#cc3333", label="spawn")
    if scored:
        frames = scored["frames_xy"]
        ax.plot([f[0] for f in frames], [f[1] for f in frames], "-", color="#cc3333", lw=1.5, label=scored["label"])
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_title(f"C0 reference: lap {total:.2f} m")
    ax.legend(loc="upper right", fontsize=8)
    fig.savefig(output, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    g = sub.add_parser("geometry")
    g.add_argument("--colliders", type=Path, required=True)
    g.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--geometry", type=Path, required=True)
    s.add_argument("--run", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("plot")
    p.add_argument("--geometry", type=Path, required=True)
    p.add_argument("--run", type=Path, help="optional run directory whose truth trajectory is drawn")
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    if args.mode == "plot":
        geometry = json.loads(args.geometry.read_text())
        scored = None
        if args.run:
            scored = {"frames_xy": [(f["x"], f["y"]) for f in truth_frames(args.run)], "label": args.run.parent.name}
        plot(geometry, args.output, scored)
        return 0
    if args.mode == "geometry":
        result = build_geometry(args.colliders)
        args.output.write_text(json.dumps(result) + "\n")
        print(json.dumps({k: result[k] for k in ("length_m", "track_width_m", "footprint", "spawn")}))
        return 0
    geometry = json.loads(args.geometry.read_text())
    result = score(geometry, truth_frames(args.run))
    result["geometry"] = {"path": str(args.geometry), "sha256": sha256(args.geometry)}
    args.output.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: result[k] for k in ("frames", "progress_m", "laps", "contact_events", "offtrack_events",
                                             "min_clearance_m", "start_offset_m")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
