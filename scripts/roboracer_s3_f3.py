#!/usr/bin/env python3
"""S3 F3 robustness cases (s3-acceptance-proposal v0.1 section 4, D50): analysis of F3-2, F3-3 and F3-4.

F3-1 (LiDAR freeze on ICP) is judged by ``roboracer_f1.py --criteria v1`` (F1-1 on stage s3v1i) and F3-5 (forbidden
truth) by ``roboracer_s3_isolation.py``.

- ``f3-2`` (configured heading off): the start-up check rejects the initialization, the stage aborts with
  "localization initialization rejected", and the car does not move (IPS travel < 0.01 m).
- ``f3-3`` (configured pose off along-track, unobservable at the spawn): the lap starts; the localization is
  declared lost (first tick with state "lost"); from that moment the car is at rest within 1.7 s and has
  travelled <= 0.65 m (V1 criteria); no contact or off-track.
- ``f3-4`` (invalid map): three tampered copies of the committed ICP map (one point moved, one point removed,
  provenance hash altered) must each be refused at load. No simulator.

usage: roboracer_s3_f3.py --case f3-2|f3-3 --run <run-01> --geometry <c0-geometry.json> --output <json>
       roboracer_s3_f3.py --case f3-4 --output <json>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
STOP_S, TRAVEL_M = 1.7, 0.65


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def case_f3_2(run: Path, geometry: dict) -> dict:
    from roboracer_f1 import truth
    status = json.loads((run / "plugin-observer-status.json").read_text())
    series = truth(rows(run / "bridge-frames.jsonl"))
    travel = sum(math.dist(a[2:], b[2:]) for a, b in zip(series, series[1:]))
    init = (status.get("precheck") or {}).get("localization_initialization") or {}
    checks = {"offset injected": any(status.get("initialization_provenance", {}).get("offset", [0, 0, 0])),
              "start-up check rejected": init.get("accepted") is False,
              "stage aborted on the rejection": status.get("abort") == "localization initialization rejected",
              "no motion (travel < 0.01 m)": travel < 0.01}
    return {"case": "f3-2", "checks": checks, "passed": all(checks.values()), "travel_m": travel, "initialization": init,
            "abort": status.get("abort")}


def case_f3_3(run: Path, geometry: dict) -> dict:
    import roboracer_scoring as rs
    from roboracer_f1 import stop_after, truth
    status = json.loads((run / "plugin-observer-status.json").read_text())
    ticks = rows(run / "plugin-ticks.jsonl")
    lost = next((t for t in ticks if (t.get("localization") or {}).get("state") == "lost"), None)
    series = truth(rows(run / "bridge-frames.jsonl"))
    stop = stop_after(series, lost["start_ns"]) if lost else None
    score = rs.score(geometry, rs.truth_frames(run))
    checks = {"offset injected": any(status.get("initialization_provenance", {}).get("offset", [0, 0, 0])),
              "start-up check accepted (along-track unobservable)":
                  ((status.get("precheck") or {}).get("localization_initialization") or {}).get("accepted") is True,
              "localization declared lost": lost is not None,
              "stage aborted on the loss": (status.get("abort") or "").startswith(("localization lost", "no valid localization")),
              f"rest <= {STOP_S} s from the loss": bool(stop) and stop["stop_s"] is not None and stop["stop_s"] <= STOP_S,
              f"travel <= {TRAVEL_M} m from the loss": bool(stop) and stop["travel_m"] <= TRAVEL_M,
              "no contact or off-track": not score["contact_events"] and not score["offtrack_events"]}
    return {"case": "f3-3", "checks": checks, "passed": all(checks.values()), "stop": stop, "abort": status.get("abort"),
            "progress_before_stop_m": score["progress_m"], "min_clearance_m": score["min_clearance_m"],
            "lost_tick": {k: lost.get(k) for k in ("start_ns", "telemetry_seq", "pose")} if lost else None}


def case_f3_4() -> dict:
    from roboracer.localization.map_icp import MAP_FILE, MAP_PROVENANCE, load_map
    results = {}
    with tempfile.TemporaryDirectory() as d:
        for name in ("point moved", "point removed", "provenance hash altered"):
            m, p = Path(d) / f"{name}.json", Path(d) / f"{name}.provenance.json"
            shutil.copy(MAP_FILE, m)
            shutil.copy(MAP_PROVENANCE, p)
            data = json.loads(m.read_text())
            if name == "point moved":
                data["points"][100][0] += 0.05
                m.write_text(json.dumps(data) + "\n")
            elif name == "point removed":
                del data["points"][100]
                m.write_text(json.dumps(data) + "\n")
            else:
                record = json.loads(p.read_text())
                record["map_sha256"] = "0" * 64
                p.write_text(json.dumps(record) + "\n")
            try:
                load_map(m, p)
                results[name] = "accepted"
            except ValueError as exc:
                results[name] = f"refused: {exc}"
    load_map()  # the committed map still loads
    checks = {f"{k} refused": v.startswith("refused") for k, v in results.items()}
    checks["committed map loads"] = True
    return {"case": "f3-4", "checks": checks, "passed": all(checks.values()), "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", choices=("f3-2", "f3-3", "f3-4"), required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(REPO))
    if args.case == "f3-4":
        result = case_f3_4()
    else:
        if not (args.run and args.geometry):
            parser.error("--run and --geometry are required for f3-2/f3-3")
        geometry = json.loads(args.geometry.read_text())
        result = (case_f3_2 if args.case == "f3-2" else case_f3_3)(args.run, geometry)
    args.output.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: result[k] for k in ("case", "passed")} | {"failed": [k for k, v in result["checks"].items() if not v]}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
