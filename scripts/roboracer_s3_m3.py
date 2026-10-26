#!/usr/bin/env python3
"""S3-05 M3 A/B episode analysis (s3-m3-proposal v0.1, D44-D46): one row per episode, external scores only.

For each episode (``<name>/run-01`` of a ``s3m3a``/``s3m3b`` run) the independent C0 scorer (IPS truth +
qualified geometry) scores the approach and the measured lap separately: the lap starts at the stage's
``episode_start_ns`` (the reached initial condition), so its lap, lap time, contact/off-track and clearance are
measured from the IC. Also: the IC check (reached pose and deviation), ICP validity/loss and ICP-vs-IPS error
per tick (scan-time ICP pose against the latest IPS sample: includes timing offset), B's tracking error to the
line, and the stage's finish/abort.

usage: roboracer_s3_m3.py --geometry <c0-geometry.json> --episodes <dir>... --output <json>
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


def pct(values, q):
    values = sorted(values)
    return values[int(q * (len(values) - 1))] if values else None


def analyze(run: Path, geometry: dict) -> dict:
    import roboracer_scoring as rs
    status = json.loads((run / "plugin-observer-status.json").read_text())
    m3 = status.get("m3") or {}
    start_ns = m3.get("episode_start_ns")
    frames = rs.truth_frames(run, episode=None) if len(rs.run_episodes(run)) <= 1 else rs.truth_frames(run, 1)
    approach = [f for f in frames if start_ns is None or f["received_ns"] < start_ns]
    lap_frames = [f for f in frames if start_ns is not None and f["received_ns"] >= start_ns]
    lap = rs.score(geometry, lap_frames) if lap_frames else None
    appr = rs.score(geometry, approach) if len(approach) > 1 else None
    ticks = [json.loads(l) for l in (run / "plugin-ticks.jsonl").read_text().splitlines() if l.strip()]
    run_ticks = [t for t in ticks if t.get("phase") == "run" and t.get("localization")]
    states = Counter(t["localization"]["state"] for t in run_ticks)
    err = [math.hypot(t["localization"]["pose"][0] - t["pose"][0], t["localization"]["pose"][1] - t["pose"][1])
           for t in run_ticks if t["localization"].get("pose") and t.get("pose")]
    lateral = [abs(t["controller"]["lateral_error_m"]) for t in run_ticks
               if isinstance(t.get("controller"), dict) and "lateral_error_m" in t["controller"]]
    lap_ok = bool(lap and lap["laps"])
    clean = bool(lap) and not lap["contact_events"] and not lap["offtrack_events"]
    approach_clean = appr is None or (not appr["contact_events"] and not appr["offtrack_events"])
    reached = m3.get("reached") or {}
    row = {
        "run": str(run), "ic": m3.get("ic"), "algorithm": m3.get("algorithm"),
        "abort": status.get("abort"), "finish_reason": status.get("finish_reason"),
        "ic_deviation_m": reached.get("deviation_m"), "ic_deviation_rad": reached.get("deviation_rad"),
        "approach_s": (m3.get("approach") or {}).get("duration_s"), "approach_clean": approach_clean,
        "lap_completed": lap_ok, "lap_time_s": lap["laps"][0]["lap_time_s"] if lap_ok else None,
        "contact_free_and_on_track": clean, "min_clearance_m": lap["min_clearance_m"] if lap else None,
        "localization_states": dict(states), "localization_lost": states.get("lost", 0) > 0,
        "icp_vs_ips_m": {"p50": pct(err, 0.5), "p95": pct(err, 0.95), "max": max(err) if err else None},
        "b_lateral_error_m_p95": pct(lateral, 0.95) if m3.get("algorithm") == "B" else None,
        "max_encoder_speed": max((t.get("encoder_speed") or 0.0 for t in run_ticks), default=None),
    }
    row["valid_episode"] = (row["abort"] is None and lap_ok and clean and approach_clean
                            and not row["localization_lost"])
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--episodes", type=Path, nargs="+", required=True, help="run-01 directories")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    geometry = json.loads(args.geometry.read_text())
    rows = [analyze(run, geometry) for run in args.episodes]
    summary = {}
    for algorithm in ("A", "B"):
        mine = [r for r in rows if r["algorithm"] == algorithm]
        times = [r["lap_time_s"] for r in mine if r["lap_time_s"]]
        summary[algorithm] = {"episodes": len(mine), "valid": sum(r["valid_episode"] for r in mine),
                              "lap_time_s": {"min": min(times, default=None), "max": max(times, default=None)},
                              "min_clearance_m": min((r["min_clearance_m"] for r in mine if r["min_clearance_m"] is not None),
                                                     default=None)}
    report = {"schema": "roboracer.s3-m3/1", "episodes": rows, "summary": summary}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    for r in rows:
        print(json.dumps({k: r[k] for k in ("ic", "algorithm", "valid_episode", "lap_time_s", "min_clearance_m",
                                            "ic_deviation_m", "abort", "localization_states")}))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
