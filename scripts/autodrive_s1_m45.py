#!/usr/bin/env python3
"""S1-03 stages M4 (closed-loop speed) and M5 (reactive A on the segment): analysis of one trial.

Sources (one run directory): plugin-ticks.jsonl (AVLite ticks: stage phase, target, encoder
speed, clearances), plugin-snapshots.jsonl (committed snapshots: encoder angles and
acquisition sim times), supervisor-trace.jsonl (requests, speed-loop control records, the
blackout event), guard/guard-trace.jsonl (accept/applied events, per-step output) and
plugin-observer-status.json.

M4 criteria (proposal v0.2, D8): per speed step, mean speed over the last 1 s within
+-0.05 m/s of v*, overshoot <= 0.1 m/s, at most 2 brake events (throttle -> 0 while v* > 0);
stop from 0.3 m/s within 1.5 s; stale feedback -> throttle 0 within 0.4 s plus one frame
(0.2 s), then inhibition. M5: completes (6 m or 40 s) without abort; final stop within 1.5 s.
Both: no guard fault or rejection, exactly one final lease expiry, output within the stage
profile, latency chain (D7) reported per clock. Fresh JSON output; nonzero exit on failure.
"""

import argparse
import json
import math
from pathlib import Path

FIXED_STEP_S, WHEEL_RADIUS_M = 0.001, 0.059
STEER_LIMIT_DEG = 30.0


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def percentiles(values, points=(50, 95, 100)):
    if not values:
        return None
    ordered = sorted(values)
    return [round(ordered[min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1)], 4) for p in points]


def speed_series(snapshots):
    """(encoder sim time, speed m/s) between consecutive committed snapshots."""
    out, previous = [], None
    for s in snapshots:
        angle = sum(s["encoders"]) / 2
        sim = s["sources"]["left_encoder"]["sim_time"]
        if previous and sim > previous[1]:
            out.append((sim, (angle - previous[0]) * WHEEL_RADIUS_M / (sim - previous[1]), s["telemetry_seq"]))
        previous = (angle, sim)
    return out


def analyze(directory: Path) -> dict:
    ticks = rows(directory / "plugin-ticks.jsonl")
    snapshots = rows(directory / "plugin-snapshots.jsonl")
    supervisor = rows(directory / "supervisor-trace.jsonl")
    guard = rows(directory / "guard/guard-trace.jsonl")
    status = json.loads((directory / "plugin-observer-status.json").read_text())
    profile = status.get("stack_profile")
    failures = []

    steps = [g for g in guard if g.get("k") == "step"]
    events = [(g, g["text"].split(" ", 1)[1]) for g in guard if g.get("k") == "event"]
    texts = [t for _, t in events]
    faults = [t for t in texts if t.startswith("state fault")]
    rejects = [t for t in texts if t.startswith("reject ")]
    stops = [t for t in texts if t.startswith("state stopped")]
    if faults or rejects:
        failures.append(f"guard faults {faults} / rejections {rejects}")
    if len(stops) != 1 or not stops[0].startswith("state stopped lease-expired"):
        failures.append(f"expected exactly one final lease expiry, got {stops}")
    steer_max = 0.0 if profile == "m4" else round(0.35 / math.radians(STEER_LIMIT_DEG), 6)
    if any(not (0 <= s["out"][0] <= 0.07) or abs(s["out"][1]) > steer_max + 1e-9 for s in steps):
        failures.append("guard output outside the stage profile")
    if status.get("abort"):
        failures.append("abort: " + status["abort"])

    requests = [r for r in supervisor if r["event"] == "request"]
    run_ticks = [t for t in ticks if t.get("phase") == "run"]
    if not run_ticks:
        failures.append("stage never reached the run phase")
        return {"run": str(directory), "profile": profile, "failures": failures, "passes": False}
    run_start_ns = run_ticks[0]["start_ns"]
    series = speed_series(snapshots)
    # Encoder sim time <-> bridge monotonic: committed snapshots carry both (stamp is acquisition, mono s).
    pairs = [(s["sources"]["left_encoder"]["sim_time"], s["sources"]["left_encoder"]["stamp"]) for s in snapshots]
    offset_mono_minus_sim = sorted(m - t for t, m in pairs)[len(pairs) // 2]

    def mono_of_sim(sim):
        return sim + offset_mono_minus_sim

    def speeds_between(a_ns, b_ns):
        return [(t, v) for t, v, _ in series if a_ns <= mono_of_sim(t) * 1e9 <= b_ns]

    result = {"run": str(directory), "profile": profile, "phase_final": status.get("stage_phase"),
              "finish_reason": status.get("finish_reason"), "abort": status.get("abort"),
              "precheck": status.get("precheck"), "guard_steps": len(steps), "guard_stops": stops,
              "requests": len(requests), "decisions": {}}
    for r in requests:
        result["decisions"][r["decision"]] = result["decisions"].get(r["decision"], 0) + 1

    if profile == "m4":
        from autodrive_neutral import M4_SCHEDULE, M4_BLACKOUT_AT_S
        step_rows = []
        controls = [r for r in requests if r.get("control")]
        for index, (start, end, target) in enumerate(M4_SCHEDULE[:3]):
            a, b = run_start_ns + start * 1e9, run_start_ns + end * 1e9
            window = speeds_between(b - 1e9, b)
            in_step = speeds_between(a, b)
            mean = sum(v for _, v in window) / len(window) if window else None
            overshoot = max((v for _, v in in_step), default=0.0) - target
            us = [r["control"]["u"] for r in controls if a <= r["t"] <= b]
            brakes = sum(1 for x, y in zip(us, us[1:]) if x > 0 and y == 0)
            row = {"target": target, "mean_last_1s": mean, "overshoot": overshoot, "brake_events": brakes,
                   "u_last": us[-1] if us else None, "trim_last": next((r["control"]["trim"] for r in reversed(controls)
                                                                       if a <= r["t"] <= b), None),
                   "speed_curve": [(round((mono_of_sim(t) * 1e9 - run_start_ns) / 1e9, 3), round(v, 4)) for t, v in in_step]}
            row["passed"] = mean is not None and abs(mean - target) <= 0.05 and overshoot <= 0.1 and brakes <= 2
            if not row["passed"]:
                failures.append(f"speed step {target}: mean {mean}, overshoot {overshoot:.3f}, brakes {brakes}")
            step_rows.append(row)
        result["speed_steps"] = step_rows
        # Stop from 0.3 m/s: first request with target 0 at the 9 s step boundary.
        zero = next((r for r in requests if r.get("target_speed") == 0.0 and r["t"] >= run_start_ns + 8.9e9), None)
        stop_s = None
        if zero:
            after = speeds_between(zero["gen_ns"], zero["gen_ns"] + 3e9)
            stop_at = next((t for t, v in after if v < 0.02 and all(w < 0.02 for u, w in after if u >= t)), None)
            stop_s = mono_of_sim(stop_at) - zero["gen_ns"] / 1e9 if stop_at is not None else None
        result["stop_from_0p3_s"] = stop_s
        if stop_s is None or stop_s > 1.5:
            failures.append(f"stop from 0.3 m/s took {stop_s}")
        # Stale feedback.
        blackout = next((r for r in supervisor if r["event"] == "feedback-blackout"), None)
        stale = next((r for r in controls if blackout and r["t"] >= blackout["t"]
                      and r["control"]["rule"] in ("stale-feedback", "feedback-lost") and r["control"]["u"] == 0), None)
        lost = next((r for r in requests if blackout and r["t"] >= blackout["t"] and r["decision"] == "feedback-lost"), None)
        result["stale_feedback"] = {
            "blackout_t": blackout and blackout["t"],
            "zero_throttle_after_s": (stale["t"] - blackout["t"]) / 1e9 if stale and blackout else None,
            "inhibited_after_s": (lost["t"] - blackout["t"]) / 1e9 if lost and blackout else None,
            "forwarded_after_inhibition": sum(1 for r in requests if lost and r["t"] > lost["t"] and r["decision"] == "forwarded")}
        sf = result["stale_feedback"]
        if sf["zero_throttle_after_s"] is None or sf["zero_throttle_after_s"] > 0.6 or sf["inhibited_after_s"] is None \
                or sf["forwarded_after_inhibition"]:
            failures.append(f"stale feedback: {sf}")
    else:
        result["path_m"] = max((t.get("path_m", 0.0) for t in ticks), default=0.0)
        result["run_s"] = (max(t["start_ns"] for t in ticks if t.get("phase") in ("run",)) - run_start_ns) / 1e9
        result["min_side_m"] = min(min(t["left"], t["right"]) for t in run_ticks if "left" in t)
        result["min_front10_m"] = min(t["front10"] for t in run_ticks if "front10" in t)
        steers = [t["controller"]["steer"] for t in run_ticks if t.get("controller") and "steer" in t["controller"]]
        result["requested_steer_rad_min_max"] = [min(steers), max(steers)] if steers else None
        result["max_speed_mps"] = max((v for t, v, _ in series), default=0.0)
        if result["finish_reason"] not in ("distance", "time"):
            failures.append(f"M5 did not complete: {result['finish_reason']}")

    # Final stop: from the first zero request of the stopping phase.
    stop_tick = next((t for t in ticks if t.get("phase") == "stopping"), None)
    final_stop = None
    if stop_tick:
        after = speeds_between(stop_tick["start_ns"], stop_tick["start_ns"] + 4e9)
        at = next((t for t, v in after if v < 0.02 and all(w < 0.02 for u, w in after if u >= t)), None)
        final_stop = mono_of_sim(at) - stop_tick["start_ns"] / 1e9 if at is not None else None
    result["final_stop_s"] = final_stop
    if profile == "m5" and (final_stop is None or final_stop > 1.5):
        failures.append(f"final stop took {final_stop}")

    # D7 latency chain: request generation -> supervisor decision (mono); accept -> applied (sim).
    accepted = {}
    for g, text in events:
        parts = text.split()
        if parts and parts[0] == "accept" and len(parts) >= 6:
            accepted[parts[5]] = {"step": g["step"], "seq": int(parts[1]), "remaining_s": int(parts[2]) / 1e9}
        if parts and parts[0] == "applied":
            for v in accepted.values():
                if v["seq"] == int(parts[1]):
                    v["applied_step"] = int(parts[3])
    forwarded = [r for r in requests if r["decision"] == "forwarded"]
    decision_ms = [(r["t"] - r["gen_ns"]) / 1e6 for r in forwarded]
    gen_to_accept = [(0.5 - a["remaining_s"]) * 1e3 for a in accepted.values()]
    accept_to_applied = [(a["applied_step"] - a["step"]) * FIXED_STEP_S * 1e3 for a in accepted.values() if "applied_step" in a]
    tick_to_gen = []
    for r in forwarded:
        tick = next((t for t in reversed(ticks) if t["start_ns"] <= r["gen_ns"]), None)
        if tick:
            tick_to_gen.append((r["gen_ns"] - tick["start_ns"]) / 1e6)
    result["latency_ms"] = {"tick_to_generation": percentiles(tick_to_gen),
                            "generation_to_supervisor_decision": percentiles(decision_ms),
                            "generation_to_guard_accept": percentiles(gen_to_accept),
                            "guard_accept_to_applied_sim": percentiles(accept_to_applied),
                            "forwarded": len(forwarded), "accepted": len(accepted)}
    result["failures"], result["passes"] = failures, not failures
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    report = analyze(args.run)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    summary = {k: report.get(k) for k in ("profile", "finish_reason", "abort", "stop_from_0p3_s", "stale_feedback",
                                         "path_m", "final_stop_s", "failures", "passes")}
    summary["steps"] = [{k: s[k] for k in ("target", "mean_last_1s", "overshoot", "brake_events")}
                        for s in report.get("speed_steps", [])]
    print(json.dumps(summary))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
