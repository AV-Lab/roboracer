#!/usr/bin/env python3
"""S2 F2 fault-case analysis (proposal v0.1 section 5, D23) for one batch directory (roboracer_batch.py --f2-case).

Each F2 batch has two episodes: the fault is injected in episode 1 at 6.0 s of run time; episode 2 must be
a healthy lap after the recovery (GUI Reset inside the session, or a fresh player for process faults).

Common checks: injection recorded at >= 6.0 s of run time in episode 1; the case's expected detection;
recovery (episode 2 healthy); no contact and no off-track in episode 1 (independent scorer); owned
processes reaped with only the expected terminations.
Stop (where the case expects a stop): IPS speed < 0.02 m/s within 1.5 s of the fault onset and travel
<= 0.40 m from the onset (the frozen S1 stop criteria, D17 A). Simulator exit/hang (F2-9/F2-10) is
containment: the process is gone, and it is never evaluated or counted as a stop.
Guard events are timed by the host receipt of the telemetry frame that carried them.

Proposed criteria for the baseline; they are frozen with the M2 budgets before acceptance (plan).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roboracer_f1 import STOP_WITHIN_S, TRAVEL_MAX_M, read, rows, stop_after, truth  # noqa: E402

EXPECTS_STOP = {"f2-3": "if the stage stopped", "f2-4": True, "f2-5": True, "f2-7": True, "f2-8": True}
CONTAINMENT = ("f2-9", "f2-10")


def guard_events(frames):
    """[(host receipt ns, event text)] from the bridge's per-frame guard acknowledgements."""
    out = []
    for f in frames:
        for item in (f.get("guard") or {}).get("events", []):
            text = item[1] if isinstance(item, (list, tuple)) else str(item)
            out.append((f["received_monotonic_ns"], text))
    return out


def first_after(events, start_ns, prefix):
    hit = next(((t, e) for t, e in events if t >= start_ns and e.startswith(prefix)), None)
    return {"event": hit[1], "after_onset_s": (hit[0] - start_ns) / 1e9} if hit else None


def analyze(batch_dir: Path, geometry: Path | None = None) -> dict:
    batch = read(batch_dir / "batch.json")
    run = batch_dir / "session-01" / "run-01"
    status, inject = read(run / "run.json"), read(run / "f2-inject.json")
    case = inject.get("case") or status.get("f2_case")
    frames = rows(run / "bridge-frames.jsonl")
    events = guard_events(frames)
    onset = inject.get("injected_ns")
    checks, out = {}, {"case": case, "batch": str(batch_dir), "injection": inject}
    checks["injected at >= 6.0 s run time in episode 1"] = bool(inject) and inject.get("run_elapsed_s", 0) >= 6.0 \
        and inject.get("episode") == 1
    plugin = read(run / "plugin-observer-status.json")
    stats = plugin.get("statistics", {})
    snaps = rows(run / "plugin-snapshots.jsonl")
    seqs = [s["telemetry_seq"] for s in snaps]
    if case == "f2-1":
        hit = first_after(events, onset or 0, "state disarmed scene-load")
        out["detection"] = hit
        checks["scene-load disarm after the injection"] = hit is not None
        reset = next((a for a in status.get("guard_actions", []) if a.get("source") == "f2-1"), {})
        checks["back at the spawn, wheels still (readiness)"] = bool((reset.get("readiness") or {}).get("passed"))
    elif case in ("f2-2", "f2-3"):
        key = "f2_duplicated" if case == "f2-2" else "f2_reordered"
        out["injected_messages"] = plugin.get(key)
        out["assembler_rejections"] = stats.get("rejections")
        checks["fault delivered"] = bool(plugin.get(key))
        checks["rejected by the assembler (sequence not increasing)"] = \
            stats.get("rejections", {}).get("telemetry sequence not increasing", 0) > 0
        checks["committed snapshots strictly increasing"] = all(b > a for a, b in zip(seqs, seqs[1:]))
    elif case == "f2-4":
        out["detection"] = {k: first_after(events, onset or 0, p) for k, p in
                            (("discontinuity", "clock clock-discontinuity"), ("fault", "state fault clock-discontinuity"))}
        checks["clock discontinuity -> guard fault"] = all(out["detection"].values())
    elif case == "f2-5":
        trace = rows(run / "supervisor-trace.jsonl")
        blackout = next((r for r in trace if r.get("event") == "feedback-blackout"), None)
        lost = next((r for r in trace if r.get("decision") == "feedback-lost" or r.get("rejected") == "feedback-lost"
                     or (r.get("event") == "state" and r.get("reason") == "feedback-lost")), None)
        out["detection"] = {"blackout_ns": blackout and blackout["t"], "feedback_lost_after_s":
                            (lost["t"] - blackout["t"]) / 1e9 if blackout and lost else None}
        checks["feedback blackout -> supervisor feedback-lost"] = bool(blackout and lost)
    elif case == "f2-6":
        loss = status.get("devkit_loss") or {}
        out["detection"] = {k: loss.get(k) for k in ("lease_cleared_after_kill_ms", "applied_steps_after_clear",
                                                     "observed_after_clear_s")}
        checks["lease cleared after the Devkit kill"] = loss.get("lease_cleared_after_kill_ms") is not None
        checks["nothing applied after the lease cleared"] = loss.get("applied_steps_after_clear") == 0
    elif case in ("f2-7", "f2-8"):
        hit = first_after(events, onset or 0, "state stopped lease-expired")
        out["detection"] = hit
        checks["guard lease expiry after the supervisor loss"] = hit is not None and hit["after_onset_s"] <= 1.1
    elif case == "f2-9":
        player = next((c for c in status.get("children", []) if c["label"] == "player"), {})
        out["containment"] = {"termination": player.get("termination")}
        checks["player killed (containment, not a stop)"] = "F2-9" in str(player.get("termination"))
    elif case == "f2-10":
        hang = status.get("simulator_hang") or {}
        out["containment"] = {k: hang.get(k) for k in ("frame_age_s", "classification")}
        checks["hang contained by the watchdog (not a stop)"] = bool(hang) and hang.get("frame_age_s", 9) <= 2.5
    expects = EXPECTS_STOP.get(case)
    stage = read(run / "stage-episodes.json").get("episodes", [])
    first = stage[0] if stage else {}
    if expects == "if the stage stopped" and first.get("finish_reason") == "distance":
        expects = False
        out["stop"] = "not required: the lap continued through the reordered window"
    if expects and onset:
        stop = stop_after(truth(frames), onset)
        out["stop"] = stop
        checks[f"stopped within {STOP_WITHIN_S} s of onset"] = stop["stop_s"] is not None and stop["stop_s"] <= STOP_WITHIN_S
        checks[f"travel <= {TRAVEL_MAX_M} m"] = stop["travel_m"] <= TRAVEL_MAX_M
    if geometry is not None and frames:
        import roboracer_scoring as rs
        try:
            scored = rs.score(read(geometry), rs.truth_frames(run, 1))
            checks["episode 1: no contact, no off-track"] = not scored["contact_events"] and not scored["offtrack_events"]
        except Exception as exc:
            out["score_error"] = f"{type(exc).__name__}: {exc}"
    episodes = batch.get("episodes", [])
    second = episodes[1] if len(episodes) > 1 else {}
    out["recovery"] = {"actions": batch.get("recovery_actions"), "episode_2": {k: second.get(k) for k in (
        "session", "outcome", "finish_reason", "score")}}
    checks["recovered: episode 2 healthy"] = second.get("outcome") == "healthy"
    unexpected = [c["label"] for s in sorted(batch_dir.glob("session-*/run-01/run.json"))
                  for c in read(s).get("children", []) if c.get("exit_code") not in (0, None) and not c.get("expected_kill")]
    checks["processes: only expected terminations"] = not unexpected
    out.update(checks=checks, unexpected_terminations=unexpected, passed=all(checks.values()),
               classification="containment" if case in CONTAINMENT else "stop/detection")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch", type=Path, required=True, help="roboracer_batch.py output directory")
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="fresh JSON report")
    args = parser.parse_args(argv)
    result = analyze(args.batch, args.geometry)
    with args.output.open("x") as f:
        json.dump(result, f, indent=1)
    print(json.dumps({"case": result["case"], "passed": result["passed"],
                      "failed": [k for k, v in result["checks"].items() if not v]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
