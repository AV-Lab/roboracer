#!/usr/bin/env python3
"""Motion protocol v0.1 stage M2 (stops under motion at throttle 0.01): analysis of one trial.

Case a (algorithm hang): one 0.01 request, then the source is silent. Case b (runner loss):
the runner stops heartbeating while 0.01 is requested every frame. Criteria (§3-§4, M2):
  - exactly one throttle run in the guard trace, ended by `state stopped lease-expired` while
    0.01 was still applied; from that step on, motor torque 0 and brakes applied; no fault;
  - stop qualification from the last forwarded request's generation: speed < 0.02 m/s within
    1.5 s and travel after it < 0.15 m;
  - caps: peak speed <= 0.5 m/s, travel <= 0.5 m, lateral <= 0.15 m, |yaw change| <= 10 deg;
  - case a: one nonzero request, nothing forwarded after it;
  - case b: the supervisor inhibits itself (runner-lease-expired) 0.5-0.7 s after the heartbeat
    pause, forwards nothing afterwards, and rejects the source's continued requests as inhibited.
Fresh JSON output; nonzero exit when any criterion fails.
"""

import argparse
import json
import math
from pathlib import Path

FIXED_STEP_S, LIFE_S, BRAKE_NM = 0.001, 0.5, 85.5999984741211
SPEED_CAP, TRAVEL_CAP, STOP_SPEED, STOP_WINDOW_S, STOP_TRAVEL_M = 0.5, 0.5, 0.02, 1.5, 0.15


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(directory: Path) -> dict:
    trace = rows(directory / "guard/guard-trace.jsonl")
    steps = [r for r in trace if r.get("k") == "step"]
    events = [(r, r["text"].split(" ", 1)[1]) for r in trace if r.get("k") == "event"]
    frames = rows(directory / "calibration-frames.jsonl")
    bridge = [r for r in rows(directory / "bridge-frames.jsonl") if "provenance" in r]
    status = json.loads((directory / "calibration-status.json").read_text())
    run = json.loads((directory / "run.json").read_text())
    supervisor = rows(directory / "supervisor-trace.jsonl")
    requests = [r for r in supervisor if r["event"] == "request"]
    case = status.get("case")
    failures = []

    faults = [t for _, t in events if t.startswith("state fault")]
    rejects = [t for _, t in events if t.startswith("reject ")]
    if faults or rejects:
        failures.append(f"guard faults {faults} / rejections {rejects}")
    if status.get("abort"):
        failures.append("abort: " + status["abort"])
    if any(s["out"][1] != 0 or s["steer"] != [0, 0] for s in steps):
        failures.append("nonzero steering")

    offsets = sorted(r["provenance"]["sources"]["ips"]["sim_time"] - r["provenance"]["sources"]["ips"]["step"] * FIXED_STEP_S
                     for r in bridge if r["provenance"]["sources"]["ips"].get("acquired"))
    offset = offsets[len(offsets) // 2]
    runs, begin = [], None
    for i, s in enumerate(steps):
        if s["out"][0] != 0 and begin is None:
            begin = i
        elif s["out"][0] == 0 and begin is not None:
            runs.append((begin, i - 1))
            begin = None
    if len(runs) != 1:
        failures.append(f"{len(runs)} throttle runs (expected 1)")
        return {"run": str(directory), "case": case, "failures": failures, "passes": False}
    first, last = runs[0]
    seg = steps[first:last + 1]
    stops = [(r, t) for r, t in events if t.startswith("state stopped")]
    expiry = None
    if len(stops) != 1 or not stops[0][1].startswith("state stopped lease-expired"):
        failures.append(f"expected one lease-expired stop, got {[t for _, t in stops]}")
    else:
        event = stops[0][0]
        before = [s for s in steps if s["step"] < event["step"]]
        after = [s for s in steps if s["step"] >= event["step"]][:2000]
        released = all(s["out"][0] == 0 and s["motor"] == [0, 0, 0, 0] and all(abs(b - BRAKE_NM) < 1e-3 for b in s["brake"])
                       for s in after)
        expiry = {"event": stops[0][1], "step": event["step"], "throttle_before": before[-1]["out"][0] if before else None,
                  "throttle_run_end_step": seg[-1]["step"], "released_with_brakes": released}
        if expiry["throttle_before"] != 0.01 or not released or abs(event["step"] - seg[-1]["step"]) > 2:
            failures.append(f"expiry did not end the throttle run cleanly: {expiry}")

    forwarded = [r for r in requests if r["decision"] == "forwarded"]
    nonzero = [r for r in forwarded if r.get("forwarded", {}).get("throttle") != "0"]
    last_forward = nonzero[-1] if nonzero else None
    accepts = {}
    for r, text in events:
        parts = text.split()
        if len(parts) >= 6 and parts[0] == "accept":  # accept <seq> <expiryInNs> <throttle> <steering> <inputs>
            accepts[int(parts[1])] = {"step": r["step"], "remaining_s": int(parts[2]) / 1e9}
    accept = accepts.get(last_forward["forwarded"]["seq"]) if last_forward else None
    if accept is None:
        failures.append("last forwarded nonzero request was not accepted by the guard")
        generation_sim = None
    else:
        generation_sim = accept["step"] * FIXED_STEP_S + offset + accept["remaining_s"] - LIFE_S
    start = status["pulse"]["start"]
    heading = start[2]

    def along(f):
        dx, dy = f["pose"][0] - start[0], f["pose"][1] - start[1]
        return math.cos(heading) * dx + math.sin(heading) * dy, abs(-math.sin(heading) * dx + math.cos(heading) * dy)

    moving = [f for f in frames if f["ips_sim_time"] >= status["pulse"]["start_sim"]]
    peak = max((f["speed_mps"] for f in moving), default=0.0)
    travel = max((along(f)[0] for f in moving), default=0.0)
    lateral = max((along(f)[1] for f in moving), default=0.0)
    yaw = max((abs(math.degrees(math.remainder(f["pose"][2] - heading, math.tau))) for f in moving), default=0.0)
    stop_s = travel_after = None
    if generation_sim is not None:
        later = [f for f in moving if f["ips_sim_time"] > generation_sim]
        stop_frame = next((f for f in later if all(g["speed_mps"] < STOP_SPEED for g in later
                                                   if g["ips_sim_time"] >= f["ips_sim_time"])), None)
        stop_s = stop_frame["ips_sim_time"] - generation_sim if stop_frame else None
        at_generation = [f for f in moving if f["ips_sim_time"] <= generation_sim]
        base = along(at_generation[-1])[0] if at_generation else 0.0
        travel_after = max((along(f)[0] for f in later), default=base) - base
    if stop_s is None or stop_s > STOP_WINDOW_S or travel_after is None or travel_after >= STOP_TRAVEL_M:
        failures.append(f"stop qualification: {stop_s} s, {travel_after} m after the last forwarded generation")
    if peak > SPEED_CAP or travel > TRAVEL_CAP or lateral > 0.15 or yaw > 10 or travel <= 0:
        failures.append(f"caps/sign: peak {peak}, travel {travel}, lateral {lateral}, yaw {yaw}")

    calibration = [r for r in requests if r.get("kind") == "calibration" and r.get("throttle") == 0.01]
    detail = {}
    if case == "a":
        detail = {"nonzero_requests": len(calibration), "forwarded_after_pulse": len(forwarded) - forwarded.index(last_forward) - 1
                  if last_forward in forwarded else None}
        if detail["nonzero_requests"] != 1 or detail["forwarded_after_pulse"] != 0:
            failures.append(f"case a: {detail}")
    elif case == "b":
        paused = run.get("heartbeat_paused_ns")
        states = [r for r in supervisor if r["event"] == "state"]
        inhibited = next((r for r in states if r["state"] == "inhibited" and r["reason"] == "runner-lease-expired"), None)
        after = [r for r in requests if inhibited and r["t"] >= inhibited["t"]]
        detail = {"heartbeat_paused_ns": paused, "inhibited_after_pause_s": (inhibited["t"] - paused) / 1e9
                  if inhibited and paused else None,
                  "requests_after_inhibition": len(after),
                  "forwarded_after_inhibition": sum(r["decision"] == "forwarded" for r in after),
                  "inhibited_rejections": sum(r["decision"] == "inhibited" for r in after),
                  "nonzero_requests": len(calibration), "nonzero_forwarded": len(nonzero)}
        if detail["inhibited_after_pause_s"] is None or not 0.5 <= detail["inhibited_after_pause_s"] <= 0.7 or \
                detail["forwarded_after_inhibition"] or not detail["inhibited_rejections"]:
            failures.append(f"case b: {detail}")
    else:
        failures.append(f"unknown case {case}")
    return {"run": str(directory), "case": case, "applied_steps": len(seg), "applied_s": len(seg) * FIXED_STEP_S,
            "torque_per_wheel_nm": seg[0]["motor"], "expiry": expiry, "last_forwarded_seq": last_forward and last_forward["forwarded"]["seq"],
            "generation_to_accept_s": LIFE_S - accept["remaining_s"] if accept else None,
            "peak_speed_mps": peak, "travel_m": travel, "lateral_m": lateral, "yaw_change_deg": yaw,
            "stop_after_last_generation_s": stop_s, "travel_after_last_generation_m": travel_after,
            "case_detail": detail, "precheck": status.get("precheck"), "guard_steps": len(steps),
            "failures": failures, "passes": not failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    report = analyze(args.run)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report.get(k) for k in ("case", "applied_s", "peak_speed_mps", "travel_m",
                                                 "stop_after_last_generation_s", "travel_after_last_generation_m",
                                                 "case_detail", "failures", "passes")}))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
