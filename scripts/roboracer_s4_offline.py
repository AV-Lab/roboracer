#!/usr/bin/env python3
"""S4 offline check (no motion): scan-derived obstacle detection on recorded laps, with and without fixtures.

A recorded run (``plugin-inputs.jsonl``) is replayed through the plugin's own ``AutoDriveBridge`` (truth withheld,
as on ICP stages; optionally with a virtual-obstacle fixture), ``MapIcpLocalization`` (configuration
initialization and start-up check) and ``ScanObstacleDetection`` on the ICP pose, one step per committed snapshot.

Reported per run:
- ICP validity under the fixture (obstacle returns are outliers to the wall map);
- without a fixture: phantom obstacles (any confirmed detection is a false positive);
- with a fixture, on scans before the car reaches the obstacle (the recorded car drives its own, open-loop path):
  the first confirmed detection (distance from the car to the obstacle), the share of scans with the obstacle
  confirmed while it is in view, the detected box against the true polygon (centre error, coverage of the true
  polygon by the detected box), and detections that are not the obstacle (false positives).

usage: roboracer_s4_offline.py --run <run-01> [--episode 1] [--fixture <t1.json>] --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
SPAWN = (0.741, 3.158, -math.pi / 2)


def replay(records, plugin, episode: int, fixture_path: Path | None):
    import importlib
    from avlite.c10_perception.c11_perception_model import EgoState, PerceptionModel
    from roboracer_inputs import decode
    vo = importlib.import_module(plugin.__name__ + ".integration.virtual_obstacles")
    bridge = plugin.AutoDriveBridge()
    bridge.withhold_truth = True
    if fixture_path:
        bridge.obstacle_fixture = vo.load_fixture(fixture_path)
    pm = PerceptionModel(ego_vehicle=EgoState(x=SPAWN[0], y=SPAWN[1], theta=SPAWN[2]))
    loc = plugin.MapIcpLocalization(pm)
    loc.initialize(*SPAWN)
    detector = plugin.ScanObstacleDetection()
    initialized, last_seq, rows = False, None, []
    for record in records:
        topic, message, now_ns = decode(record)
        bridge._offer(topic, message, now_ns)
        snap = bridge.latest()
        if snap is None or snap.telemetry_seq == last_seq or snap.episode != episode:
            continue
        last_seq = snap.telemetry_seq
        frame = bridge.get_sensor_frame()
        if not initialized:
            loc.verify_initialization(frame)
            initialized = True
        else:
            loc.localize(pm, frame)
        detector.detect(pm, frame)
        rows.append({"seq": snap.telemetry_seq, "truth": [snap.pose.x, snap.pose.y, snap.pose.yaw],
                     "icp": [pm.ego_vehicle.x, pm.ego_vehicle.y, pm.ego_vehicle.theta],
                     "icp_state": loc.status.get("state"), "candidates": detector.status["candidates"],
                     "free_points": detector.status["free_points"],
                     "obstacles": [[a.x, a.y, a.theta, a.length, a.width] for a in detector.obstacles]})
    return rows, (bridge.statistics()["virtual_obstacles"] if fixture_path else None)


def box_polygon(x, y, theta, length, width):
    from shapely.geometry import Polygon
    c, s = math.cos(theta), math.sin(theta)
    return Polygon([(x + c * u - s * v, y + s * u + c * v)
                    for u, v in ((-length / 2, -width / 2), (length / 2, -width / 2), (length / 2, width / 2),
                                 (-length / 2, width / 2))])


def analyse(rows, fixture_path: Path | None, reach_m: float = 0.6):
    from shapely.geometry import Point, Polygon
    states = {}
    for r in rows:
        states[r["icp_state"]] = states.get(r["icp_state"], 0) + 1
    out = {"steps": len(rows), "icp_states": states}
    if fixture_path is None:
        phantom = [r for r in rows if r["obstacles"]]
        out.update(phantom_scans=len(phantom), phantom_examples=[{"seq": r["seq"], "obstacles": r["obstacles"]}
                                                                for r in phantom[:5]],
                   candidate_scans=sum(1 for r in rows if r["candidates"]))
        return out
    truth = Polygon(json.loads(fixture_path.read_text())["obstacles"][0]["polygon"])
    window, first, hits, false_pos, centre, cover = [], None, 0, 0, [], []
    for r in rows:
        car = Point(r["truth"][0], r["truth"][1])
        distance = car.distance(truth)
        if distance <= reach_m:
            break  # the recorded car reaches the obstacle: later scans are not meaningful
        window.append(r)
        on = [o for o in r["obstacles"] if box_polygon(*o).buffer(0.10).intersects(truth)]
        false_pos += len(r["obstacles"]) - len(on)
        if on:
            hits += 1
            first = first if first is not None else {"seq": r["seq"], "distance_m": distance}
            best = max(on, key=lambda o: box_polygon(*o).intersection(truth).area)
            centre.append(math.dist(best[:2], (truth.centroid.x, truth.centroid.y)))
            cover.append(box_polygon(*best).intersection(truth).area / truth.area)
    out.update(window_scans=len(window), confirmed_scans=hits, first_confirmed=first, false_positive_detections=false_pos,
               centre_error_m=_stats(centre), true_polygon_covered=_stats(cover),
               icp_states_in_window=_count(r["icp_state"] for r in window))
    return out


def _stats(values):
    if not values:
        return None
    values = sorted(values)
    return {"n": len(values), "min": values[0], "p50": values[len(values) // 2], "max": values[-1]}


def _count(items):
    out = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be fresh")
    from roboracer_inputs import load_plugin, read_recording
    plugin = load_plugin(REPO / "roboracer")
    _, records = read_recording(args.run / "plugin-inputs.jsonl")
    rows, stats = replay(records, plugin, args.episode, args.fixture)
    report = {"schema": "roboracer.s4-offline/1", "run": str(args.run), "episode": args.episode,
              "fixture": str(args.fixture) if args.fixture else None, "fixture_stats": stats,
              "result": analyse(rows, args.fixture),
              "note": "open-loop replay of a recorded lap; detection scored on scans before the car reaches the obstacle"}
    args.output.write_text(json.dumps({**report, "rows": rows}) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
