#!/usr/bin/env python3
"""S3-01: the C0 ICP matching target, built and validated against recorded scans (no motion).

Target: the edges of the drivable region (the walls' inner faces, which is what the LiDAR sees), from the
collider-derived C0 geometry, sampled every ``--spacing`` m, written to ``roboracer/data/c0-icp-map.json``
with a provenance record (source hashes, spacing, code hash).

Validation (frame semantics: origin, yaw sign, scan row direction, scale, LiDAR mount): recorded scans are
placed in the map frame with the recorded IPS pose (``p_world = T(pose) @ base_to_sensor @ p_sensor``) and
their distance to the target is measured. The asset passes when the median residual is <= 0.02 m and
>= 90 % of points lie within 0.05 m. Deliberately wrong frame conventions (yaw sign flipped, y mirrored,
5 % scale, 0.10 m origin shift) must fail the same test, showing the check rejects inconsistent assets.
The IPS pose is used here only offline, to validate the asset; it never enters the localizer.

usage: roboracer_s3_map.py --geometry <c0-geometry.json> --run <run-01 with plugin-inputs.jsonl> [--episode 1]
       [--spacing 0.02] [--samples 200] [--output-dir roboracer/data] --report <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

MEDIAN_MAX_M, WITHIN_M, WITHIN_FRACTION = 0.02, 0.05, 0.90


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target_points(region, spacing: float):
    """Points every ``spacing`` m along every ring of the drivable region."""
    import numpy as np
    rings = [region.exterior, *region.interiors]
    points = []
    for ring in rings:
        n = max(8, int(math.ceil(ring.length / spacing)))
        points += [ring.interpolate(i * ring.length / n).coords[0] for i in range(n)]
    return np.asarray(points, dtype=float)


def world_points(snapshot, pose):
    """Scan points in the map frame for a (x, y, yaw) pose."""
    import numpy as np
    body = snapshot.lidar.to_base(snapshot.lidar.points)[:, :2]
    x, y, yaw = pose
    c, s = math.cos(yaw), math.sin(yaw)
    return body @ np.array([[c, s], [-s, c]]) + np.array([x, y])


def residual_stats(tree, points) -> dict:
    import numpy as np
    d, _ = tree.query(points)
    return {"points": int(len(d)), "median_m": float(np.median(d)), "p95_m": float(np.percentile(d, 95)),
            "within_fraction": float(np.mean(d <= WITHIN_M))}


def passes(stats: dict) -> bool:
    return stats["median_m"] <= MEDIAN_MAX_M and stats["within_fraction"] >= WITHIN_FRACTION


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--spacing", type=float, default=0.02)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=REPO / "roboracer/data")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    import numpy as np
    from scipy.spatial import cKDTree
    from shapely import wkt
    from roboracer_inputs import load_plugin, read_recording, replay_snapshots

    geometry = json.loads(args.geometry.read_text())
    region = wkt.loads(geometry["region_wkt"])
    target = target_points(region, args.spacing)
    tree = cKDTree(target)

    plugin = load_plugin(REPO / "roboracer")
    _, records = read_recording(args.run / "plugin-inputs.jsonl")
    snapshots, _ = replay_snapshots(records, plugin)
    lap = [s for s in snapshots if s.episode == args.episode and s.lidar is not None and s.lidar.points is not None
           and len(s.lidar.points)]
    picked = [lap[i] for i in np.linspace(0, len(lap) - 1, min(args.samples, len(lap))).astype(int)]

    variants = {
        "as recorded": lambda p: p,
        "yaw sign flipped": lambda p: (p[0], p[1], -p[2]),
        "origin shifted 0.10 m": lambda p: (p[0] + 0.10, p[1], p[2]),
    }
    results = {}
    for name, change in variants.items():
        pts = np.vstack([world_points(s, change((s.pose.x, s.pose.y, s.pose.yaw))) for s in picked])
        results[name] = residual_stats(tree, pts)
    base = np.vstack([world_points(s, (s.pose.x, s.pose.y, s.pose.yaw)) for s in picked])
    results["y mirrored"] = residual_stats(tree, base * np.array([1.0, -1.0]))
    centre = target.mean(axis=0)
    results["scale x1.05"] = residual_stats(tree, (base - centre) * 1.05 + centre)
    for row in results.values():
        row["passes"] = passes(row)

    ok = results["as recorded"]["passes"] and not any(r["passes"] for k, r in results.items() if k != "as recorded")
    report = {"schema": "roboracer.s3-icp-map-validation/1", "run": str(args.run), "episode": args.episode,
              "snapshots_used": len(picked), "target_points": int(len(target)), "spacing_m": args.spacing,
              "criteria": {"median_max_m": MEDIAN_MAX_M, "within_m": WITHIN_M, "within_fraction": WITHIN_FRACTION},
              "variants": results, "asset_accepted": ok}
    args.report.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "variants"}))
    for name, row in results.items():
        print(f"  {name:24s} median {row['median_m']:.4f} m  within 5 cm {row['within_fraction']:.3f}  passes {row['passes']}")
    if not ok:
        raise SystemExit("ICP map target rejected: frame validation failed")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "c0-icp-map.json"
    out.write_text(json.dumps({"schema": "roboracer.icp-map/1", "frame": "C0 IPS/map frame (x, y in m)",
                               "spacing_m": args.spacing, "points": [[round(x, 5), round(y, 5)] for x, y in target]}) + "\n")
    provenance = {"schema": "roboracer.icp-map-provenance/1", "map_file": out.name, "map_sha256": sha256(out),
                  "source": {"geometry": str(args.geometry), "geometry_sha256": sha256(args.geometry),
                             "track": geometry.get("track"), "region": "drivable-region edges (wall inner faces)"},
                  "validation": {k: report[k] for k in ("run", "episode", "snapshots_used", "criteria", "variants")},
                  "code_sha256": sha256(Path(__file__))}
    (args.output_dir / "c0-icp-map.provenance.json").write_text(json.dumps(provenance, indent=1) + "\n")
    print(json.dumps({"map": str(out), "sha256": provenance["map_sha256"], "points": len(target)}))


if __name__ == "__main__":
    main()
