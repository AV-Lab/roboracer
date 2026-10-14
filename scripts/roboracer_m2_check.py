#!/usr/bin/env python3
"""S2 M2 acceptance check of one unattended batch against D26 A and the D25 budgets (s2-budgets-proposal.md).

D26 A: every episode of the batch is healthy (ten consecutive for the 10-episode item); any failure fails the
item, and no failure is relabelled. D25 budgets, checked here:
- readiness after each scene load: spawn <= 0.010 m, yaw <= 1 deg, wheels still, guard not armed and no fault;
- automated pre-Connect check <= 8 px per region; GUI Reset click -> Connect <= 20 s;
- fresh player -> first observation <= 30 s; cleanup <= 20 s; batch wall time <= the cap;
- per driven episode (timing tool, 10 s warm-up + 120 s): the frozen S1 limits, plus the S2 health budgets
  observation age at request <= 400 ms, clock bound <= 100 ms, request generation -> guard accept <= 300 ms;
- guard batch phases all pass, including the previous epoch's request rejected stale-epoch at every re-arm.
Replay equality (D24) is checked separately with roboracer_inputs.py (three fresh processes per fixture).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roboracer_timing as rt  # noqa: E402

S2_HEALTH = {"observation_age_at_request_ms": 400.0, "clock_bound_ms": 100.0, "generation_to_guard_accept_ms": 300.0}
STARTUP_S, CLEANUP_S, RESET_TO_CONNECT_S, UI_PX = 30.0, 20.0, 20.0, 8
READY_OFFSET_M = 0.010


def read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def check(batch_dir: Path, geometry: Path | None, expected_episodes: int) -> dict:
    batch = read(batch_dir / "batch.json")
    checks, details = {}, {}
    episodes = batch.get("episodes", [])
    checks[f"{expected_episodes} episodes attempted, all healthy (D26 A)"] = \
        len(episodes) == expected_episodes and all(e["outcome"] == "healthy" for e in episodes)
    checks["no recovery action needed"] = not batch.get("recovery_actions")
    checks["unattended (every Connect used the automated check)"] = bool(batch.get("unattended"))
    checks["batch wall time within the cap"] = batch.get("wall_s", 1e9) <= batch.get("wall_cap_s", 0)
    details["episodes"] = [{k: e.get(k) for k in ("index", "session", "outcome", "finish_reason", "abort")} |
                           {"laps": [round(l["lap_time_s"], 1) for l in (e.get("score") or {}).get("laps", [])],
                            "min_clearance_m": (e.get("score") or {}).get("min_clearance_m")} for e in episodes]
    timing = []
    for s in batch.get("sessions", []):
        run = Path(s["results"]) / "run-01"
        status = read(run / "run.json")
        guard = (status.get("bridge_at_end") or read(run / "bridge-status.json")).get("guard") or {}
        key = f"session {s['session']}"
        checks[f"{key}: startup <= {STARTUP_S:.0f} s"] = status.get("startup_to_observation_seconds") is not None and status["startup_to_observation_seconds"] <= STARTUP_S
        checks[f"{key}: cleanup <= {CLEANUP_S:.0f} s"] = status.get("cleanup_seconds") is not None and status["cleanup_seconds"] <= CLEANUP_S
        ui = [max(c["mismatch_px"].values()) for c in status.get("ui_checks", [])]
        checks[f"{key}: automated checks <= {UI_PX} px"] = bool(ui) and max(ui) <= UI_PX
        resets = [a for a in status.get("guard_actions", []) if a.get("kind") == "gui-reset"]
        waits = [(a["connect_clicks"][-1] - a["clicks"][0]) / 1e9 for a in resets if a.get("clicks") and a.get("connect_clicks")]
        checks[f"{key}: Reset -> Connect <= {RESET_TO_CONNECT_S:.0f} s"] = len(waits) == len(resets) and \
            all(w <= RESET_TO_CONNECT_S for w in waits)
        ready = [a.get("readiness") or {} for a in resets]
        offsets = [(a.get("c0_start") or {}).get("offset_m") for a in resets]
        checks[f"{key}: readiness after every reset"] = all(r.get("passed") for r in ready) and \
            all(o is not None and o <= READY_OFFSET_M for o in offsets)
        trace = run / "guard" / "guard-trace.jsonl"
        truncated = trace.exists() and trace.stat().st_size > 1024 and \
            b'{"k":"truncated"}' in trace.read_bytes()[-256:]
        checks[f"{key}: guard per-step trace complete (not truncated at 256 MiB)"] = trace.exists() and not truncated
        phases = guard.get("phases", [])
        checks[f"{key}: guard batch phases pass"] = bool(phases) and all(p["passed"] for p in phases)
        stale = [c for p in phases for c in p["checks"] if c["name"] == "previous-epoch request rejected stale-epoch"]
        checks[f"{key}: stale-epoch rejection at every re-arm"] = len(stale) == len(resets) and all(c["ok"] for c in stale)
        details[key] = {"startup_s": status.get("startup_to_observation_seconds"), "cleanup_s": status.get("cleanup_seconds"),
                        "ui_max_px": max(ui) if ui else None, "reset_to_connect_s": [round(w, 2) for w in waits],
                        "spawn_offsets_m": offsets}
        reported = read(run / "stage-episodes.json").get("episodes", [])
        for n in range(1, len(reported) + 1):
            r = rt.measure(run, geometry=geometry, episode=n)
            lim = r.get("limits") or {}
            row = {"session": s["session"], "episode": n, "complete": r.get("complete"),
                   "s1_limits_within": all(v["within"] for v in lim.values()),
                   **{k: round(lim[k]["measured_max"], 1) for k in S2_HEALTH if k in lim and lim[k]["measured_max"] is not None}}
            row["s2_health_within"] = all(row.get(k, 1e9) <= v for k, v in S2_HEALTH.items())
            timing.append(row)
    details["timing"] = timing
    checks["every episode: complete 120 s window"] = bool(timing) and all(t["complete"] for t in timing)
    checks["every episode: frozen S1 limits"] = bool(timing) and all(t["s1_limits_within"] for t in timing)
    checks["every episode: S2 health budgets (D25)"] = bool(timing) and all(t["s2_health_within"] for t in timing)
    return {"batch": str(batch_dir), "checks": checks, "details": details, "passed": all(checks.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = check(args.batch, args.geometry, args.episodes)
    with args.output.open("x") as f:
        json.dump(result, f, indent=1)
    print(json.dumps({"passed": result["passed"], "failed": [k for k, v in result["checks"].items() if not v]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
