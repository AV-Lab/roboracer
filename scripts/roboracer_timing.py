#!/usr/bin/env python3
"""S1-06 timing/resource/episode measurement for one AVLite-stack run, against the frozen S1 limits.

Window (plan sampling protocol): a warm-up after the stage's run phase starts, then a fixed
measurement window, both in monotonic wall time; defaults 10 s + 120 s. A run whose run phase ends
before the window closes is reported as incomplete for timing (its partial values are kept).

Measured per window (clock domain in each name):
- telemetry: frame rate and period, unique acquisitions per source, simulation real-time factor;
- ages: bridge-computed source age at receipt, observation age at request generation
  (generation - IPS acquisition), speed-feedback age, clock bound, snapshot pose age and scan/pose skew;
- control: tick period/duration/overruns, request rate and decisions, runner heartbeat interval;
- latency chain: tick -> request generation, generation -> supervisor decision, generation -> guard
  accept, guard accept -> applied (simulation steps), and generation -> first telemetry frame whose
  IPS acquisition step is at or after the applied step (command-to-observed-response);
- resources: CPU % (user+system over the window), RSS max, threads per owned process; device GPU
  utilization/memory when the run sampled it (gpu.jsonl);
- episode: stop response, laps/contact/off-track (independent scorer) when geometry is given.
Frozen S1 limits are checked and reported; nothing here is a performance target.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Frozen S1 operational limits (motion protocol v0.1, controller proposal v0.3, lap proposal v0.1).
LIMITS = {
    "observation_age_at_request_ms": 500.0,     # D3
    "feedback_stale_ms": 600.0,                 # D5 v0.3 (zero throttle)
    "feedback_lost_ms": 900.0,                  # D5 v0.3 (inhibit)
    "telemetry_gap_ms": 500.0,                  # stack: no new observation -> abort
    "runner_heartbeat_ms": 500.0,               # runner lease
    "clock_bound_ms": 400.0,                    # guard receiver clock bound
    "request_life_ms": 500.0,                   # lease from generation
    "final_stop_s": 1.5,                        # stop qualification
    "speed_abort_mps": 0.5,
    "steer_rad": 0.35,
}


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def pct(values, points=(50, 95, 100)):
    values = sorted(v for v in values if v is not None and math.isfinite(v))
    if not values:
        return None
    out = {}
    for p in points:
        k = (len(values) - 1) * p / 100
        lo, hi = math.floor(k), math.ceil(k)
        out["p%d" % p if p < 100 else "max"] = values[lo] + (values[hi] - values[lo]) * (k - lo)
    out["n"] = len(values)
    return out


def guard_events(guard, forwarded):
    """Accept/applied events of forwarded requests. Guard event text:
    "<event#> accept <seq> <lease_left_ns> <throttle> <steering> <inputs>" and
    "<event#> applied <seq> step <step>"; rows carry the player's CLOCK_MONOTONIC ("mono")."""
    accepted, applied = {}, {}
    for g in guard:
        if g.get("k") != "event":
            continue
        parts = g["text"].split()
        if len(parts) >= 4 and parts[1] == "accept" and int(parts[2]) in forwarded:
            accepted[int(parts[2])] = {"step": g["step"], "mono": g.get("mono"), "remaining_ms": int(parts[3]) / 1e6}
        elif len(parts) >= 5 and parts[1] == "applied":
            applied.setdefault(int(parts[2]), int(parts[4]))
    return accepted, applied


def measure(run: Path, warmup_s=10.0, window_s=120.0, geometry: Path | None = None) -> dict:
    ticks, frames = rows(run / "plugin-ticks.jsonl"), rows(run / "bridge-frames.jsonl")
    snapshots, trace = rows(run / "plugin-snapshots.jsonl"), rows(run / "supervisor-trace.jsonl")
    guard, resources, gpu = rows(run / "guard/guard-trace.jsonl"), rows(run / "resources.jsonl"), rows(run / "gpu.jsonl")
    status = json.loads((run / "plugin-observer-status.json").read_text())
    run_ticks = [t for t in ticks if t.get("phase") == "run"]
    if not run_ticks:
        return {"run": str(run), "complete": False, "reason": "no run phase"}
    run_start, run_end = run_ticks[0]["start_ns"], run_ticks[-1]["start_ns"]
    lo, hi = run_start + int(warmup_s * 1e9), run_start + int((warmup_s + window_s) * 1e9)
    complete = run_end >= hi
    hi_eff = min(hi, run_end)
    span = (hi_eff - lo) / 1e9

    def inside(ns):
        return ns is not None and lo <= ns < hi_eff

    out = {"run": str(run), "stage": status.get("stack_profile"), "warmup_s": warmup_s, "window_s": window_s,
           "complete": complete, "measured_s": span, "run_phase_s": (run_end - run_start) / 1e9,
           "clock_domains": "monotonic wall ns unless named *_sim"}

    # Telemetry and sources.
    fw = [f for f in frames if "provenance" in f and inside(f["received_monotonic_ns"])]
    rx = [f["received_monotonic_ns"] for f in fw]
    periods = [(b - a) / 1e6 for a, b in zip(rx, rx[1:])]
    sources = {}
    for name in ("lidar", "ips", "imu", "left_encoder", "right_encoder"):
        seen = {f["provenance"]["sources"][name]["seq"] for f in fw if name in f["provenance"]["sources"]}
        reused = sum(1 for f in fw if f["provenance"]["sources"].get(name, {}).get("reused"))
        ages = [f["provenance"]["sources"][name].get("age_ns", math.nan) / 1e6 for f in fw if name in f["provenance"]["sources"]]
        sources[name] = {"unique_per_s": len(seen) / span if span > 0 else None, "reused_frames": reused,
                         "age_at_receipt_ms": pct(ages)}
    sim = [f["provenance"]["sources"]["ips"]["sim_time"] for f in fw]
    out["telemetry"] = {"frames": len(fw), "rate_hz": len(fw) / span if span > 0 else None, "period_ms": pct(periods),
                        "real_time_factor": (sim[-1] - sim[0]) / ((rx[-1] - rx[0]) / 1e9) if len(fw) > 1 else None,
                        "clock_bound_ms": pct([f["provenance"]["clock"]["bound_ns"] / 1e6 for f in fw]),
                        "sources": sources}
    sw = [s for s in snapshots if inside(s["committed_monotonic_ns"])]
    out["snapshots"] = {"count": len(sw), "pose_age_at_commit_ms": pct([s["pose_age_at_commit_s"] * 1e3 for s in sw]),
                        "scan_pose_skew_ms": pct([s["scan_pose_skew_s"] * 1e3 for s in sw])}

    # Control path.
    tw = [t for t in ticks if inside(t["start_ns"])]
    starts = [t["start_ns"] for t in tw]
    requests = [r for r in trace if r.get("event") == "request" and inside(r["gen_ns"])]
    heartbeats = [r["t"] for r in trace if r.get("event") == "heartbeat" and inside(r["t"])]
    decisions = {}
    for r in requests:
        decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1
    out["control"] = {
        "tick_period_ms": pct([(b - a) / 1e6 for a, b in zip(starts, starts[1:])]),
        "tick_duration_ms": pct([(t["end_ns"] - t["start_ns"]) / 1e6 for t in tw]),
        "tick_overruns_run_total": status.get("tick_overruns"),
        "request_rate_hz": len(requests) / span if span > 0 else None, "decisions": decisions,
        "observation_age_at_request_ms": pct([(r["gen_ns"] - r["observation"]["stamp_ns"]) / 1e6 for r in requests]),
        "feedback_age_at_request_ms": pct([r["control"]["feedback_age_ns"] / 1e6 for r in requests
                                          if r.get("control") and r["control"].get("feedback_age_ns") is not None]),
        "control_rules": {},
        # Only the first heartbeat is traced; the runner lease outcome is the inhibited decisions.
        "runner_heartbeats_traced": len(heartbeats),
        "inhibited_decisions": sum(1 for r in requests if r["decision"] == "inhibited"),
    }
    for r in requests:
        rule = (r.get("control") or {}).get("rule")
        out["control"]["control_rules"][rule] = out["control"]["control_rules"].get(rule, 0) + 1

    # Latency chain.
    forwarded = {r["forwarded"]["seq"]: r for r in requests if r["decision"] == "forwarded"}
    accepted, applied = guard_events(guard, forwarded)
    frame_steps = sorted((f["provenance"]["sources"]["ips"]["step"], f["received_monotonic_ns"])
                         for f in frames if "provenance" in f)
    response = []
    for seq, step in applied.items():
        if seq not in forwarded:
            continue
        hit = next((ns for s, ns in frame_steps if s >= step), None)
        if hit is not None:
            response.append((hit - forwarded[seq]["gen_ns"]) / 1e6)
    tick_to_gen = []
    for r in forwarded.values():
        tick = next((t for t in reversed(tw) if t["start_ns"] <= r["gen_ns"]), None)
        if tick:
            tick_to_gen.append((r["gen_ns"] - tick["start_ns"]) / 1e6)
    out["latency_ms"] = {
        "tick_to_generation": pct(tick_to_gen),
        "generation_to_supervisor_decision": pct([(r["t"] - r["gen_ns"]) / 1e6 for r in forwarded.values()]),
        "generation_to_guard_accept": pct([LIMITS["request_life_ms"] - a["remaining_ms"] for a in accepted.values()]),
        "generation_to_guard_accept_same_host_mono": pct([(a["mono"] - forwarded[s]["gen_ns"]) / 1e6
                                                          for s, a in accepted.items() if a.get("mono")]),
        "guard_accept_to_applied_sim": pct([(applied[s] - a["step"]) * 1.0 for s, a in accepted.items() if s in applied]),
        "generation_to_first_observation_after_apply": pct(response),
        "forwarded": len(forwarded), "accepted": len(accepted), "applied": sum(1 for s in applied if s in forwarded),
        "note": "guard_accept_to_applied_sim in ms of simulation time (1 ms fixed step). The guard takes the newest "
                "request once per telemetry reply, so earlier requests between replies are superseded: "
                "accepted <= forwarded. generation_to_guard_accept uses the guard's own lease estimate; the "
                "same_host_mono variant subtracts CLOCK_MONOTONIC stamps from two processes on one host"}

    # Resources.
    proc = {}
    for label in sorted({r["label"] for r in resources}):
        rs_ = [r for r in resources if r["label"] == label and inside(r["monotonic_ns"])]
        if len(rs_) < 2:
            continue
        cpu = (rs_[-1]["user_cpu_seconds"] + rs_[-1]["system_cpu_seconds"] - rs_[0]["user_cpu_seconds"]
               - rs_[0]["system_cpu_seconds"]) / ((rs_[-1]["monotonic_ns"] - rs_[0]["monotonic_ns"]) / 1e9)
        proc[label] = {"cpu_pct_of_one_core": 100 * cpu, "rss_max_mib": max(int(r["VmRSS"].split()[0]) for r in rs_) / 1024,
                       "threads_max": max(int(r["Threads"]) for r in rs_), "samples": len(rs_)}
    gw = [g for g in gpu if inside(g["monotonic_ns"]) and "utilization_pct" in g]
    out["resources"] = {"processes": proc,
                        "gpu": {"utilization_pct": pct([g["utilization_pct"] for g in gw]),
                                "memory_used_mib": pct([g["memory_used_mib"] for g in gw]),
                                "query_ms": pct([g["query_ms"] for g in gw])} if gw else
                               {"sampled": False, "note": "run predates GPU sampling (gpu.jsonl)"}}

    # Stop and episode.
    import autodrive_s1_m45 as m45
    analysis = m45.analyze(run)
    out["stop_and_bounds"] = {k: analysis.get(k) for k in ("finish_reason", "abort", "final_stop_s", "max_speed_mps",
                                                           "requested_steer_rad_min_max", "min_side_m", "min_front10_m",
                                                           "path_m", "failures")}
    if geometry:
        import roboracer_scoring as rs
        score = rs.score(json.loads(geometry.read_text()), rs.truth_frames(run))
        out["episode"] = {k: score[k] for k in ("laps", "contact_events", "offtrack_events", "min_clearance_m",
                                                "progress_m", "max_frame_progress_m")}

    out["limits"] = check_limits(out)
    return out


def _max(stat):
    return stat["max"] if stat else None


def check_limits(m: dict) -> dict:
    c, t, sb = m["control"], m["telemetry"], m["stop_and_bounds"]
    period = t["period_ms"]
    checks = {
        "observation_age_at_request_ms": (_max(c["observation_age_at_request_ms"]), LIMITS["observation_age_at_request_ms"]),
        "feedback_age_at_request_ms (stale)": (_max(c["feedback_age_at_request_ms"]), LIMITS["feedback_stale_ms"]),
        "telemetry_gap_ms": (_max(period), LIMITS["telemetry_gap_ms"]),
        "runner_lease_inhibitions": (c["inhibited_decisions"], 0),
        "clock_bound_ms": (_max(t["clock_bound_ms"]), LIMITS["clock_bound_ms"]),
        "generation_to_guard_accept_ms": (_max(m["latency_ms"]["generation_to_guard_accept"]), LIMITS["request_life_ms"]),
        "final_stop_s": (sb.get("final_stop_s"), LIMITS["final_stop_s"]),
        "max_speed_mps": (sb.get("max_speed_mps"), LIMITS["speed_abort_mps"]),
        "max_abs_requested_steer_rad": (max(abs(v) for v in sb["requested_steer_rad_min_max"])
                                        if sb.get("requested_steer_rad_min_max") else None, LIMITS["steer_rad"]),
    }
    out = {}
    for name, (value, limit) in checks.items():
        within = None if value is None else value <= limit + 1e-9
        out[name] = {"measured_max": value, "limit": limit, "within": within,
                     "margin": None if value is None else limit - value}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True, help="run-01 directory")
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--warmup", type=float, default=10.0)
    parser.add_argument("--window", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    result = measure(args.run, args.warmup, args.window, args.geometry)
    args.output.write_text(json.dumps(result, indent=1) + "\n")
    lim = result.get("limits", {})
    print(json.dumps({"complete": result["complete"], "measured_s": result.get("measured_s"),
                      "limits_within": {k: v["within"] for k, v in lim.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
