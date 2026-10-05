#!/usr/bin/env python3
"""S1-02 live check: join the plugin bridge's committed snapshots with the independent records.

For one retained run directory (``autodrive_neutral.py run --plugin-observer``):

- every telemetry frame after the first (stamped at publication) must yield exactly one
  snapshot, in order, and the plugin must report no other rejection;
- each snapshot's scan must be the frame's own LaserScan: its ROS stamp equals the
  independent observer's message stamp and the float32 range hashes are equal;
- each GT pose must equal the frame's raw IPS position and match the raw IMU yaw within the
  reported 3-decimal resolution;
- mounts, source stamps, scan/pose skew and commit latency are summarized.

Writes a fresh JSON report; exits nonzero when any check fails.
"""

import argparse
import json
import math
from pathlib import Path

LIDAR_MOUNT = [0.2733, 0.0, 0.096]
IMU_MOUNT = [0.08, 0.0, 0.055]


def rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def percentiles(values, points=(50, 95, 100)):
    if not values:
        return None
    ordered = sorted(values)
    return [ordered[min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1)] for p in points]


def analyze(directory: Path) -> dict:
    frames = [r for r in rows(directory / "bridge-frames.jsonl") if "provenance" in r]
    snapshots = rows(directory / "plugin-snapshots.jsonl")
    observer = rows(directory / "ros-messages.jsonl")
    status = json.loads((directory / "plugin-observer-status.json").read_text())
    scans = {r["stamp_ns"]: r for r in observer if r["topic"] == "lidar"}
    by_seq = {f["provenance"]["telemetry_seq"]: f for f in frames}
    expected = [f["provenance"]["telemetry_seq"] for f in frames if f.get("stamp_basis") == "acquisition"]
    # The final frame may be in flight when the trial stops; it can be absent from the snapshots.
    got = [s["telemetry_seq"] for s in snapshots]
    failures = []
    if got != expected[:len(got)] or len(expected) - len(got) > 1:
        failures.append(f"snapshot sequence differs: {len(got)} snapshots for {len(expected)} acquisition frames")
    rejections = status["statistics"]["rejections"]
    allowed = {"stamp basis is not acquisition (no clock exchange yet)"}
    if set(rejections) - allowed or rejections.get(next(iter(allowed)), 0) > 1:
        failures.append(f"unexpected rejections: {rejections}")
    scan_matches = pose_matches = yaw_ok = 0
    latency, skew, bound, age = [], [], [], []
    for s in snapshots:
        frame = by_seq[s["telemetry_seq"]]
        stamp = s["sources"]["lidar"]["ros_stamp_ns"]
        if stamp in scans and scans[stamp]["range_sha256"] == s["scan_sha256"]:
            scan_matches += 1
        if s["pose"][:3] == frame["motion"]["Position"]:
            pose_matches += 1
        euler_yaw = frame["motion"]["Orientation Euler Angles"][2]
        difference = math.remainder(s["pose"][3] - euler_yaw, math.tau)
        yaw_ok += abs(difference) <= 0.005  # quaternion and Euler are each reported with 3 decimals
        if s["lidar_mount"] != LIDAR_MOUNT or s["imu_mount"] != IMU_MOUNT or s["pose_label"] != "ground-truth":
            failures.append(f"mount/label differs at {s['telemetry_seq']}")
        latency.append((s["committed_monotonic_ns"] - frame["received_monotonic_ns"]) / 1e6)
        skew.append(s["scan_pose_skew_s"] * 1e3)
        bound.append(s["clock_bound_s"] * 1e3)
        age.append(s["pose_age_at_commit_s"] * 1e3)
    for name, count in (("scan", scan_matches), ("pose", pose_matches), ("yaw", yaw_ok)):
        if count != len(snapshots):
            failures.append(f"{name} matched {count}/{len(snapshots)}")
    if not snapshots:
        failures.append("no snapshots")
    return {"run": str(directory), "frames": len(frames), "acquisition_frames": len(expected),
            "snapshots": len(snapshots), "plugin_statistics": status["statistics"],
            "plugin_settings": {k: status.get(k) for k in ("gt_localization", "max_target_speed_mps")},
            "scan_matches": scan_matches, "pose_matches": pose_matches, "yaw_within_5mrad": yaw_ok,
            "commit_latency_after_bridge_receipt_ms_p50_p95_max": percentiles(latency),
            "pose_age_at_commit_ms_p50_p95_max": percentiles(age),
            "scan_pose_skew_ms_p50_p95_max": percentiles(skew),
            "clock_bound_ms_p50_p95_max": percentiles(bound),
            "failures": failures, "passes": not failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    report = analyze(args.run)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("snapshots", "acquisition_frames", "failures", "passes")}))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
