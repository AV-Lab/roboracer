"""Stages s3b and s3v1: B's bring-up laps (S3, D32 A; s3v1 = speed step V1, D35) — the ported A2RL controller on the committed C0 plan.

The plan file is built offline by ``scripts/roboracer_s3_plan.py`` and committed with a provenance
record holding its sha256; ``load_plan`` refuses a file that does not match or exceeds the stage cap.
The controller config keeps B inside the stage envelope: s3b 0.3 m/s (the unchanged M6 envelope), s3v1
0.5 m/s (speed step V1, D36), s3v2 1.0 m/s straights with fault-bounded corners (V2, D40); 0.35 rad steering; lateral MPC applied as in A2RL's latest presets.

Bring-up only: the controller reads the bridge's ego state, i.e. the simulator IPS pose. Laps on this
stage are labelled "bring-up, not an S3 result"; S3 results use ICP (D32 A).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..control.racing_controller import RacingControllerConfig
from .trajectory_tracker import LapTrajectoryTracker

DATA = Path(__file__).resolve().parents[1] / "data"
PLAN_FILE = DATA / "c0-s3b-plan.json"
PROVENANCE_FILE = DATA / "c0-s3b-plan.provenance.json"
# Speed cap per stage: s3b the M6 envelope; s3v1 the first speed step (s3-speed-proposal v0.1, D35/D36).
SPEED_CAP_MPS = {"s3b": 0.3, "s3v1": 0.5, "s3v2": 1.0}


def plan_files(stage: str) -> tuple[Path, Path]:
    return DATA / f"c0-{stage}-plan.json", DATA / f"c0-{stage}-plan.provenance.json"


def controller_config(stage: str = "s3b") -> RacingControllerConfig:
    return RacingControllerConfig(mpc_lateral_mode="apply", speed_cap_mps=SPEED_CAP_MPS[stage], max_wheel_angle_rad=0.35)


def load_plan(stage: str = "s3b", plan_file: Path | None = None, provenance_file: Path | None = None):
    """(tracker, info): the stage's C0 plan as a closed-lap tracker, after checking the file against its
    recorded sha256, its speed cap and the AVLite GlobalPlan shape."""
    default_plan, default_record = plan_files(stage)
    plan_file, provenance_file = plan_file or default_plan, provenance_file or default_record
    raw = plan_file.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    provenance = json.loads(provenance_file.read_text())
    if provenance.get("plan_sha256") != digest:
        raise ValueError(f"{plan_file.name} does not match its provenance record")
    payload = json.loads(raw)
    line = [tuple(p[:2]) for p in payload["ReferenceLine"]]
    speed = payload["ReferenceSpeed"]
    if len(line) < 10 or len(speed) != len(line) or line[0] != line[-1]:
        raise ValueError("plan must be a closed line with one speed per point")
    if max(speed) > SPEED_CAP_MPS[stage] + 1e-9:
        raise ValueError(f"plan speed {max(speed)} exceeds the {stage} cap {SPEED_CAP_MPS[stage]}")
    tracker = LapTrajectoryTracker(path=line, velocity=speed)
    return tracker, {"stage": stage, "plan_file": str(plan_file), "plan_sha256": digest, "points": len(line) - 1,
                     "lap_m": float(tracker.path_s[-1]), "max_speed_mps": max(speed),
                     "source": provenance.get("source"), "report": provenance.get("report")}
