#!/usr/bin/env python3
"""S4 truth isolation (no motion): with a virtual-obstacle fixture, simulator truth does not reach B's outputs.

The fixture must use the simulator pose to place its obstacles in the scan -- that is the simulated sensor, as
any simulator's LiDAR is. What must not reach the driving stack is the truth that remains on the snapshot after
the sensor is simulated: the IPS pose and the IMU. So the perturbation is applied *after* the fixture.

A recorded run (``plugin-inputs.jsonl``) is replayed through the full S4 stack, assembled by AVLite's
``executor_factory`` exactly as in ``roboracer_s4_closedloop_sim.py`` (scan obstacles, map ICP with the simulator
pose filtered out and truth withheld, the C0 lattice, B in ``selected`` mode), one ``SyncExecuter.step`` per
committed snapshot. Variants, each in a fresh process (the factory loads the plugin once per process):

- ``recorded``;
- ``perturbed``: after the fixture, every snapshot's IPS pose shifted (+3 m, +2 m) and rotated +90 deg, and the
  IMU's angular velocity and acceleration changed. B's outputs (target speed, steer), the stack's pose,
  the detected obstacles and the planner state must be bit-identical to ``recorded``;
- ``control-recorded`` / ``control-perturbed``: the stack on the simulator pose (ground-truth localization, no
  ICP, truth not withheld), without and with the same perturbation. Its commands must change between the two,
  showing that the comparison detects a truth path.

Open-loop: the recorded car followed its own controller; this tests the data path, not closed-loop driving.

usage: roboracer_s4_isolation.py --run <run-01> [--episode 1] --fixture <t.json> --output <json>
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
SPAWN = (0.741, 3.158, -math.pi / 2)
VARIANTS = ("recorded", "perturbed", "control-recorded", "control-perturbed")


def run_variant(variant: str, run: Path, episode: int, fixture: Path, max_steps: int) -> list:
    from roboracer_inputs import decode, read_recording
    import roboracer_s4_closedloop_sim as sim
    import importlib
    control = variant.startswith("control")
    executer, plugin = sim.build_stack(REPO / "roboracer")
    if control:
        # Negative control: ground-truth LOCALIZATION re-enabled (the D32 bring-up path) and truth not withheld.
        from avlite.c40_execution.c49_settings import ExecutionSettings
        ExecutionSettings.c41_world_stack_capabilities = ["LOCALIZATION"]
    vo = importlib.import_module(plugin.__name__ + ".integration.virtual_obstacles")

    class ReplayWorld(plugin.AutoDriveBridge):
        def _with_obstacles(self, snapshot):
            snapshot = super()._with_obstacles(snapshot)
            if not variant.endswith("perturbed"):
                return snapshot
            p = snapshot.pose
            imu = replace(snapshot.imu, angular_velocity=(1.0, -2.0, 3.0), linear_accel=(9.0, -9.0, 4.0))
            return replace(snapshot, pose=replace(p, x=p.x + 3.0, y=p.y + 2.0, yaw=p.yaw + math.pi / 2), imu=imu)

    world = ReplayWorld()
    world.withhold_truth = not control
    world.obstacle_fixture = vo.load_fixture(fixture)
    executer.world = world
    loc, planner, detector = executer.localization, executer.local_planner, executer.perception._detector
    _, records = read_recording(run / "plugin-inputs.jsonl")
    rows, last_seq, initialized = [], None, False
    for record in records:
        topic, message, now_ns = decode(record)
        world._offer(topic, message, now_ns)
        snap = world.latest()
        if snap is None or snap.telemetry_seq == last_seq or snap.episode != episode:
            continue
        last_seq = snap.telemetry_seq
        if not initialized and not control:
            loc.initialize(*SPAWN)
            loc.verify_initialization(world.get_sensor_frame())
            initialized = True
        executer.step(sim_dt=0.1, control_dt=0.099, replan_dt=0.099, perception_dt=0.099, localization_dt=0.099)
        req = world.last_request
        ego = executer.pm.ego_vehicle
        rows.append([snap.telemetry_seq, req.target_speed if req else None, req.steer if req else None,
                     ego.x, ego.y, ego.theta, ego.velocity, loc.status.get("state"),
                     [[a.x, a.y, a.length, a.width] for a in detector.obstacles], planner.blocked,
                     world.get_sensor_frame().imu is not None])
        if len(rows) >= max_steps:
            break
    return rows


def digest(rows) -> str:
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=100000)
    parser.add_argument("--variant", choices=VARIANTS, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.variant:
        rows = run_variant(args.variant, args.run, args.episode, args.fixture, args.max_steps)
        args.output.write_text(json.dumps(rows) + "\n")
        return 0
    if args.output.exists():
        parser.error("output must be fresh")
    results = {}
    for variant in VARIANTS:
        part = args.output.with_name(f"{args.output.stem}-{variant}.json")
        subprocess.run([sys.executable, "-B", __file__, "--run", str(args.run), "--episode", str(args.episode),
                        "--fixture", str(args.fixture), "--max-steps", str(args.max_steps), "--variant", variant,
                        "--output", str(part)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        results[variant] = json.loads(part.read_text())
    base, moved = results["recorded"], results["perturbed"]
    control, control_moved = results["control-recorded"], results["control-perturbed"]
    identical = base == moved
    states = {}
    for row in base:
        states[row[7]] = states.get(row[7], 0) + 1
    detected = sum(1 for row in base if row[8])
    control_differs = sum(1 for a, b in zip(control, control_moved) if a[1:3] != b[1:3])
    report = {"schema": "roboracer.s4-isolation/1", "run": str(args.run), "episode": args.episode,
              "fixture": str(args.fixture), "steps": len(base), "localization_states": states,
              "steps_with_detected_obstacles": detected, "blocked_steps": sum(1 for row in base if row[9]),
              "imu_in_any_frame": any(row[10] for row in base),
              "b_outputs_identical": identical, "sha256": [digest(base), digest(moved)],
              "negative_control_steps_with_changed_commands": control_differs,
              "passed": identical and len(base) > 0 and detected > 0 and control_differs > 0
              and not any(row[10] for row in base),
              "note": "open-loop replay; perturbation applied after the virtual-obstacle fixture; outputs = target speed, "
                      "steer, stack pose and velocity, localization state, detected obstacles, blocked"}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
