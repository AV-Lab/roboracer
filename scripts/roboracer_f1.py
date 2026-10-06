#!/usr/bin/env python3
"""S1-06 F1 fault-case analysis (M1 protocol v0.1, D14/D15/D16) for one run directory.

Frozen pass criteria, common to every case (D14, D15):
- the fault was injected (fault-inject.json) at 6.0 s of run time;
- the case's expected detection is present (per-case rules below);
- stop: IPS speed < 0.02 m/s within 1.5 s of the injection (for F1-5: of the disarm) and
  travel after the injection <= 0.40 m until that stop;
- no nonzero throttle applied by the guard after the detection deadline (injection + 1.1 s:
  runner lease 0.5 s + request life 0.5 s + one 0.1 s tick), until any approved re-arm (F1-5);
- no guard fault; no contact and no off-track (independent scorer) when geometry is given;
- processes: every owned child reaped (run.json, or the wrapper's F1-8 reaping record).
Speed is from consecutive IPS positions over IPS acquisition simulation time.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STOP_SPEED_MPS, STOP_WITHIN_S, TRAVEL_MAX_M = 0.02, 1.5, 0.40
DETECTION_DEADLINE_S = 1.1


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def read(path: Path):
    return json.loads(path.read_text()) if path.exists() else {}


def truth(frames):
    """[(received_ns, sim_time, x, y)] from the runner's bridge frames."""
    out = []
    for f in frames:
        if "motion" in f and "provenance" in f:
            x, y, _ = f["motion"]["Position"]
            out.append((f["received_monotonic_ns"], f["provenance"]["sources"]["ips"]["sim_time"], x, y))
    return out


def stop_after(series, start_ns, end_ns=None):
    """First frame time (received ns) after `start_ns` from which speed stays < STOP_SPEED_MPS until
    `end_ns` (or the end), and the path travelled from `start_ns` to that frame."""
    pts = [p for p in series if p[0] >= start_ns and (end_ns is None or p[0] <= end_ns)]
    prior = [p for p in series if p[0] < start_ns]
    if prior:
        pts.insert(0, prior[-1])
    speeds = []
    for a, b in zip(pts, pts[1:]):
        dt, step = b[1] - a[1], math.dist(a[2:], b[2:])
        # Only the share of a frame interval after `start_ns` counts as travel after it.
        if a[0] >= start_ns:
            share = 1.0
        else:
            share = max(0.0, (b[0] - start_ns) / (b[0] - a[0])) if b[0] > a[0] else 0.0
        speeds.append((b[0], step / dt if dt > 0 else 0.0, step * share))
    stop_ns, travel = None, 0.0
    for i, (t, v, d) in enumerate(speeds):
        if all(w < STOP_SPEED_MPS for _, w, _ in speeds[i:]):
            stop_ns = t
            break
        travel += d
    if stop_ns is None:
        travel = sum(d for _, _, d in speeds)
    return {"stop_s": (stop_ns - start_ns) / 1e9 if stop_ns is not None else None, "travel_m": travel,
            "frames": len(speeds)}


def analyze(run: Path, geometry: Path | None = None, episode: Path | None = None) -> dict:
    inject = read(run / "fault-inject.json")
    status = read(run / "plugin-observer-status.json")
    run_json = read(run / "run.json")
    case = inject.get("case") or run_json.get("f1_case")
    out = {"run": str(run), "case": case, "checks": {}, "details": {}}

    def check(name, ok, **detail):
        out["checks"][name] = {"ok": bool(ok), **detail}

    check("fault injected at 6.0 s of run time", bool(inject) and abs(inject.get("run_elapsed_s", 0) - 6.0) <= 0.15,
          run_elapsed_s=inject.get("run_elapsed_s"))
    if not inject:
        out["passed"] = False
        return out
    t0 = inject["injected_ns"]
    frames = rows(run / "bridge-frames.jsonl")
    series = truth(frames)
    guard = rows(run / "guard/guard-trace.jsonl")
    events = [(g["mono"], g["text"].split(" ", 1)[1]) for g in guard if g.get("k") == "event"]
    trace = rows(run / "supervisor-trace.jsonl")
    requests = [r for r in trace if r.get("event") == "request"]
    ticks = rows(run / "plugin-ticks.jsonl")
    stats = status.get("statistics", {})

    # Stop reference: the injection, or for F1-5 the guard's disarm.
    ref = t0
    rearm_ns = None
    if case == "f1-5":
        disarm = next((m for m, t in events if m >= t0 and t == "disarm-request"), None)
        rearm = next((m for m, t in events if disarm and m > disarm and t.startswith("state armed epoch")), None)
        check("guard disarm-request after injection", disarm is not None)
        ref = disarm or t0
        rearm_ns = rearm
    stop = stop_after(series, ref, rearm_ns)
    out["details"]["stop"] = stop
    check("stop within 1.5 s", stop["stop_s"] is not None and stop["stop_s"] <= STOP_WITHIN_S, stop_s=stop["stop_s"])
    check("travel after injection <= 0.40 m", stop["travel_m"] <= TRAVEL_MAX_M, travel_m=stop["travel_m"])

    deadline = t0 + int(DETECTION_DEADLINE_S * 1e9)
    window_end = rearm_ns or float("inf")
    late = [g for g in guard if g.get("k") == "step" and deadline <= g["mono"] < window_end and g["out"][0] != 0]
    if case not in ("f1-8", "f1-9") or guard:
        check("no nonzero throttle after the detection deadline", not late, steps=len(late),
              first=late[0]["mono"] if late else None)
    check("no guard fault", not any(t.startswith("state fault") for _, t in events))

    after = [r for r in requests if r["gen_ns"] >= t0]
    forwarded_after = [r for r in after if r["decision"] == "forwarded"]
    expiry = next(((m, t) for m, t in events if m >= t0 and t.startswith("state stopped lease-expired")), None)
    last_forwarded = None
    if expiry is not None:
        last_forwarded = max((r["gen_ns"] for r in requests if r["decision"] == "forwarded" and r["gen_ns"] <= expiry[0]),
                             default=None)
    lease_ok = expiry is not None and last_forwarded is not None and expiry[0] - last_forwarded <= 0.55e9
    abort = status.get("abort") or ""
    abort_tick = next((t for t in ticks if t.get("phase") == "stopping" and t["start_ns"] >= t0), None)

    if case in ("f1-1", "f1-2"):
        key = "scan/pose skew" if case == "f1-1" else "scan layout differs from the qualified convention"
        check(f"snapshots rejected: {key}", stats.get("rejections", {}).get(key, 0) > 0,
              rejections=stats.get("rejections"))
        check("stack aborted on no new observation", abort.startswith("no new observation"), abort=abort)
        snaps = [s["committed_monotonic_ns"] for s in rows(run / "plugin-snapshots.jsonl")]
        last_good = max((s for s in snaps if abort_tick and s <= abort_tick["start_ns"]), default=None)
        gap = (abort_tick["start_ns"] - last_good) / 1e9 if abort_tick and last_good else None
        check("abort <= 0.6 s after the last good snapshot", gap is not None and gap <= 0.6, gap_s=gap)
        check("supervisor refused stale observations", any(r["decision"] == "stale-observation" for r in after),
              decisions=sorted({r["decision"] for r in after}))
    elif case == "f1-3":
        check("no request generated after the hang", not [r for r in requests if r["gen_ns"] > t0 + 0.15e9],
              count=len([r for r in requests if r["gen_ns"] > t0 + 0.15e9]))
        check("guard lease expired <= 0.5 s after the last forwarded generation", lease_ok, expiry=expiry)
    elif case == "f1-4":
        refused = stats.get("command_rejections", {})
        check("plugin refused the non-finite target speed",
              any("target_speed is not a finite number" in k for k in refused), command_rejections=refused)
        direct = inject.get("direct_nan", {})
        hit = next((r for r in requests if r.get("seq") == direct.get("seq")), None)
        check("supervisor rejected the direct NaN request as non-finite", hit is not None and hit["decision"] == "non-finite",
              decision=hit and hit["decision"])
        nonfinite_to_guard = [t for _, t in events if t.startswith("accept ") and ("nan" in t.lower() or "inf" in t.lower())]
        check("nothing non-finite reached the guard", not nonfinite_to_guard)
        check("no request forwarded after the injection", not [r for r in forwarded_after if r["gen_ns"] > t0 + 0.15e9],
              count=len(forwarded_after))
        check("guard lease expired <= 0.5 s after the last forwarded generation", lease_ok, expiry=expiry)
    elif case == "f1-5":
        driver = read(run / "bridge-status.json").get("guard", {})
        phase = (driver.get("phases") or [{}])[0]
        check("guard driver re-arm checks passed", phase.get("passed") is True,
              failed=[c for c in phase.get("checks", []) if not c["ok"]])
        moved = stop_after(series, rearm_ns or t0)["travel_m"] if rearm_ns else 0.0
        check("car moved again after re-arm", moved >= 0.1, travel_after_rearm_m=moved)
        final = next((t for t in ticks if t.get("phase") == "stopping" and t["start_ns"] > (rearm_ns or t0)), None)
        final_stop = stop_after(series, final["start_ns"]) if final else None
        check("final stop within 1.5 s of the zero request", final_stop and final_stop["stop_s"] is not None
              and final_stop["stop_s"] <= STOP_WITHIN_S, final_stop=final_stop)
    elif case == "f1-6":
        child = next((c for c in run_json.get("children", []) if c["label"] == "plugin-stack"), {})
        check("AVLite stack killed as expected", child.get("expected_kill") is True and "F1-6" in child.get("termination", ""),
              termination=child.get("termination"))
        check("guard lease expired <= 0.5 s after the last forwarded generation", lease_ok, expiry=expiry)
    elif case == "f1-7":
        paused = run_json.get("heartbeat_paused_ns")
        inhibited = [r for r in requests if r["decision"] == "inhibited"]
        first_inhibited = min((r["t"] for r in inhibited), default=None)
        delay = (first_inhibited - paused) / 1e9 if paused and first_inhibited else None
        check("runner heartbeats paused", paused is not None)
        check("supervisor inhibited (runner lease) within 0.6 s of the pause", delay is not None and delay <= 0.6,
              delay_s=delay, refused=len(inhibited))
        check("no request forwarded after inhibition",
              not [r for r in requests if first_inhibited and r["t"] > first_inhibited and r["decision"] == "forwarded"])
        check("guard lease expired <= 0.5 s after the last forwarded generation", lease_ok, expiry=expiry)
    elif case == "f1-8":
        reaping = read(episode).get("f1_8") if episode else None
        check("runner SIGKILLed by the episode wrapper", bool(reaping) and reaping.get("killed") is True)
        check("orphaned children reaped", bool(reaping) and reaping.get("all_gone") is True,
              reaped=reaping and reaping.get("reaped"))
        check("guard lease expired after the runner exit", expiry is not None, expiry=expiry)
        sup = read(run / "supervisor-1-status.json")
        check("supervisor inhibited by its runner lease", sup.get("reason") == "runner-lease-expired" or
              any(r["decision"] == "inhibited" for r in after), state=sup.get("state"), reason=sup.get("reason"))
    elif case == "f1-9":
        d16 = run_json.get("d16") or {}
        check("runner recorded the injected error", "F1-9 injected runner error" in (run_json.get("error") or ""),
              error=run_json.get("error"))
        check("D16: guard disarmed before cleanup", d16.get("disarmed") is True, d16=d16)
        check("D16: wheels stopped before cleanup", d16.get("stopped") is True, d16=d16)
        check("guard disarm-request recorded", any(t == "disarm-request" and m >= t0 for m, t in events))

    if case != "f1-8":
        children = run_json.get("children", [])
        check("all owned children reaped", bool(children) and all(c.get("reaped") for c in children),
              children=[(c["label"], c.get("exit_code"), c.get("termination")) for c in children])
    if geometry:
        import roboracer_scoring as rs
        score = rs.score(json.loads(geometry.read_text()), rs.truth_frames(run))
        out["details"]["episode"] = {k: score[k] for k in ("contact_events", "offtrack_events", "min_clearance_m")}
        check("no contact and no off-track", not score["contact_events"] and not score["offtrack_events"],
              min_clearance_m=score["min_clearance_m"])
    out["passed"] = all(c["ok"] for c in out["checks"].values())
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True, help="run-01 directory")
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--episode", type=Path, help="episode.json (F1-8 reaping record)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    result = analyze(args.run, args.geometry, args.episode)
    args.output.write_text(json.dumps(result, indent=1, default=str) + "\n")
    print(json.dumps({"case": result["case"], "passed": result["passed"],
                      "failed": [k for k, v in result["checks"].items() if not v["ok"]],
                      "stop": result["details"].get("stop")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
