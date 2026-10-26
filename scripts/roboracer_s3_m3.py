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
    # Time-matched: on each tick where the ICP pose changed (a new scan was matched), compare it with the IPS pose of
    # the snapshot that tick used (its telemetry_seq); the per-tick figure above mixes in up to one frame of travel.
    snaps = {}
    for line in (run / "plugin-snapshots.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            snaps[row["telemetry_seq"]] = row["pose"]
    matched, matched_yaw, previous = [], [], None
    for t in run_ticks:
        pose = t["localization"].get("pose")
        if pose and pose != previous and t.get("telemetry_seq") in snaps:
            truth = snaps[t["telemetry_seq"]]
            matched.append(math.hypot(pose[0] - truth[0], pose[1] - truth[1]))
            matched_yaw.append(abs(math.remainder(pose[2] - truth[3], math.tau)))
        previous = pose
    fractions = [t["localization"]["inlier_fraction"] for t in run_ticks if t["localization"].get("inlier_fraction") is not None]
    corrections = [t["localization"]["correction_m"] for t in run_ticks if t["localization"].get("correction_m") is not None]
    compute = [t["localization"]["compute_s"] * 1000 for t in run_ticks if t["localization"].get("compute_s")]
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
        "icp_error_matched_m": {"n": len(matched), "p50": pct(matched, 0.5), "p95": pct(matched, 0.95),
                                "max": max(matched) if matched else None},
        "icp_yaw_error_matched_rad": {"p95": pct(matched_yaw, 0.95), "max": max(matched_yaw) if matched_yaw else None},
        "icp_inlier_fraction_min": min(fractions) if fractions else None,
        "icp_correction_m_max": max(corrections) if corrections else None,
        "icp_compute_ms": {"p95": pct(compute, 0.95), "max": max(compute) if compute else None},
        "b_lateral_error_m_p95": pct(lateral, 0.95) if m3.get("algorithm") == "B" else None,
        "max_encoder_speed": max((t.get("encoder_speed") or 0.0 for t in run_ticks), default=None),
    }
    row["valid_episode"] = (row["abort"] is None and lap_ok and clean and approach_clean
                            and not row["localization_lost"])
    # D48 thresholds T1-T8 (s3-acceptance-proposal v0.1); B gates acceptance, A is reported (D52).
    valid_share = states.get("valid", 0) / max(1, sum(states.values()))
    me, my, mc = row["icp_error_matched_m"], row["icp_yaw_error_matched_rad"], row["icp_compute_ms"]
    checks = {
        "T1 ICP valid >= 99 % and no loss": valid_share >= 0.99 and not row["localization_lost"],
        "T2 position error p95 <= 0.05 m, max <= 0.10 m": me["p95"] is not None and me["p95"] <= 0.05 and me["max"] <= 0.10,
        "T3 yaw error p95 <= 0.03 rad, max <= 0.06 rad": my["p95"] is not None and my["p95"] <= 0.03 and my["max"] <= 0.06,
        "T4 ICP compute p95 <= 10 ms, max <= 50 ms": mc["p95"] is not None and mc["p95"] <= 10 and mc["max"] <= 50,
        "T5 valid lap, no contact/off-track/abort": row["valid_episode"],
        "T8 IC within 0.10 m and 5 deg": (row["ic"] == 0 or (row["ic_deviation_m"] is not None and
                                          row["ic_deviation_m"] <= 0.10 and row["ic_deviation_rad"] <= math.radians(5))),
    }
    if row["algorithm"] == "B":
        checks["T6 B clearance >= 0.20 m"] = row["min_clearance_m"] is not None and row["min_clearance_m"] >= 0.20
        checks["T7 B lap from the IC <= 66.0 s"] = row["lap_time_s"] is not None and row["lap_time_s"] <= 66.0
    row["thresholds"] = checks
    row["passes_thresholds"] = all(checks.values())
    row["gates_acceptance"] = row["algorithm"] == "B"
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
                              "pass_thresholds": sum(r["passes_thresholds"] for r in mine),
                              "lap_time_s": {"min": min(times, default=None), "max": max(times, default=None)},
                              "min_clearance_m": min((r["min_clearance_m"] for r in mine if r["min_clearance_m"] is not None),
                                                     default=None)}
    report = {"schema": "roboracer.s3-m3/1", "episodes": rows, "summary": summary}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    for r in rows:
        print(json.dumps({k: r[k] for k in ("ic", "algorithm", "valid_episode", "passes_thresholds", "lap_time_s",
                                            "min_clearance_m", "ic_deviation_m", "abort", "localization_states")}))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
