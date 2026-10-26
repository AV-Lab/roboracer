#!/usr/bin/env python3
"""S3-04 truth isolation (no motion): changing scorer-only truth does not change B's outputs.

A recorded run (``plugin-inputs.jsonl``, every raw Devkit message with its arrival time) is replayed through
the plugin's own ``AutoDriveBridge`` (truth withheld, as on ICP stages), ``MapIcpLocalization`` (configuration
initialization + start-up check) and B's ``RacingLineController`` on the committed plan, one stack step per
committed snapshot. Variants:

- ``recorded``: as recorded.
- ``truth perturbed``: every IPS pose (and the provenance ``ips_position`` the assembler matches it with)
  shifted by (+3 m, +2 m, 0) and every IMU orientation rotated by 90 deg about z -- the simulator truth the
  scorer uses. B's command sequence must be bit-identical to ``recorded``.
- ``negative control``: the same perturbation, but B fed the IPS pose (the D32 bring-up path). Its commands must
  change, showing the comparison detects a truth path.

Open-loop: the recorded car followed its own controller; this tests the data path, not closed-loop driving.

usage: roboracer_s3_isolation.py --run <run-01> [--episode 1] [--stage s3v1i] --output <json>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
SPAWN = (0.741, 3.158, -math.pi / 2)


def perturb(records: list[dict]) -> list[dict]:
    """Shift IPS and rotate IMU orientation (quaternion x, y, z, w) by 90 deg about z."""
    out = []
    c = s = math.sqrt(0.5)
    for r in records:
        r = copy.deepcopy(r)
        if r.get("topic") == "ips":
            x, y, z = r["xyz"]
            r["xyz"] = [x + 3.0, y + 2.0, z]
        elif r.get("topic") == "provenance":
            # The assembler pairs IPS messages with provenance by exact value (ips_position): shift both.
            data = json.loads(r["data"])
            if isinstance(data.get("ips_position"), list):
                x, y, z = data["ips_position"]
                data["ips_position"] = [x + 3.0, y + 2.0, z]
                r["data"] = json.dumps(data)
        elif r.get("topic") == "imu" and "orientation" in r:
            qx, qy, qz, qw = r["orientation"]  # q' = q_z(90) * q
            r["orientation"] = [c * qx - s * qy, c * qy + s * qx, c * qz + s * qw, c * qw - s * qz]
        out.append(r)
    return out


def run(records, plugin, stage: str, episode: int, use_ips: bool):
    import importlib
    from avlite.c10_perception.c11_perception_model import EgoState, PerceptionModel
    from roboracer_inputs import decode
    bridge = plugin.AutoDriveBridge()
    bridge.withhold_truth = not use_ips
    s3b = importlib.import_module(plugin.__name__ + ".planning.s3b")
    tracker, _ = s3b.load_plan(stage)
    cfg = s3b.controller_config(stage)
    cfg.tracking_safe_stop_min_speed_mps = math.inf  # keep the whole chain exercised on the recorded path
    controller = plugin.RacingLineController(config=cfg)
    pm = PerceptionModel(ego_vehicle=EgoState(x=SPAWN[0], y=SPAWN[1], theta=SPAWN[2]))
    loc = plugin.MapIcpLocalization(pm)
    loc.initialize(*SPAWN)
    initialized = False
    last_seq, outputs, truth = None, [], []
    for record in records:
        topic, message, now_ns = decode(record)
        bridge._offer(topic, message, now_ns)
        snap = bridge.latest()
        if snap is None or snap.telemetry_seq == last_seq or snap.episode != episode:
            continue
        last_seq = snap.telemetry_seq
        frame = bridge.get_sensor_frame()
        if use_ips:
            ego = bridge.get_ego_state()
        else:
            if not initialized:
                loc.verify_initialization(frame)
                initialized = True
            else:
                loc.localize(pm, frame)
            ego = pm.ego_vehicle
        target, steer, detail = controller.steer_and_speed(tracker, ego, 0.1)
        outputs.append([snap.telemetry_seq, target, steer, ego.x, ego.y, ego.theta, ego.velocity,
                        loc.status.get("state") if not use_ips else "ips", frame.imu is not None])
        truth.append([snap.pose.x, snap.pose.y, snap.pose.yaw])
    return outputs, truth


def digest(rows) -> str:
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--stage", default="s3v1i")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from roboracer_inputs import load_plugin, read_recording
    plugin = load_plugin(REPO / "roboracer")
    _, records = read_recording(args.run / "plugin-inputs.jsonl")
    perturbed = perturb(records)

    base, truth = run(records, plugin, args.stage, args.episode, use_ips=False)
    moved, truth_moved = run(perturbed, plugin, args.stage, args.episode, use_ips=False)
    control, _ = run(records, plugin, args.stage, args.episode, use_ips=True)
    control_moved, _ = run(perturbed, plugin, args.stage, args.episode, use_ips=True)

    truth_changed = sum(1 for a, b in zip(truth, truth_moved) if a != b)
    identical = base == moved
    control_differs = sum(1 for a, b in zip(control, control_moved) if a[1:3] != b[1:3])
    states = {}
    for row in base:
        states[row[7]] = states.get(row[7], 0) + 1
    report = {
        "schema": "roboracer.s3-isolation/1", "run": str(args.run), "episode": args.episode, "stage": args.stage,
        "steps": len(base), "localization_states": states,
        "imu_in_any_frame": any(r[8] for r in base),
        "truth_rows_changed_by_perturbation": truth_changed,
        "b_outputs_identical": identical, "b_outputs_sha256": [digest(base), digest(moved)],
        "negative_control_steps_with_changed_commands": control_differs,
        "passed": identical and truth_changed == len(base) and control_differs > 0 and not any(r[8] for r in base),
        "note": "open-loop replay of a recorded run; outputs = (target speed, steer, ego pose, velocity, loc state)"}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
