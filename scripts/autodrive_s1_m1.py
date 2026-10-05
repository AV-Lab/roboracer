#!/usr/bin/env python3
"""Motion protocol v0.1 stage M1 (forward throttle pulses, steering 0): analysis of one trial.

Pulses are taken from the guard's per-step trace (runs of nonzero applied throttle); motion
from the calibration source's per-frame log (IPS pose, IPS simulation time). Criteria
(s1-motion-protocol.md §3-§4, M1):
  - travel along vehicle +x for every pulse that moved; both encoders change with one sign;
  - applied motor torque = 85.6 N m x throttle / 4 per wheel (CAWD) during a pulse; after it,
    every motor torque is exactly 0 with brakes applied (D1) and no guard fault;
  - stop qualification: speed < 0.02 m/s within 1.5 s of the pulse request's generation, and
    travel after it < 0.15 m (bounded conservatively by the pulse's whole travel);
  - caps: peak speed <= 0.5 m/s, travel <= 0.5 m, |yaw change| <= 10 deg, lateral <= 0.15 m;
  - every supervisor decision forwarded; no guard rejection.
Also writes the response map (throttle, applied duration, peak speed, travel). Fresh JSON
output; nonzero exit when any criterion fails.
"""

import argparse
import json
import math
from pathlib import Path

MOTOR_TORQUE_NM, BRAKE_NM, FIXED_STEP_S, LIFE_S = 85.6, 85.5999984741211, 0.001, 0.5
SPEED_CAP, TRAVEL_CAP, STOP_SPEED, STOP_WINDOW_S, STOP_TRAVEL_M = 0.5, 0.5, 0.02, 1.5, 0.15


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(directory: Path) -> dict:
    trace = rows(directory / "guard/guard-trace.jsonl")
    steps = [r for r in trace if r.get("k") == "step"]
    texts = [(r, r["text"].split(" ", 1)[1]) for r in trace if r.get("k") == "event"]
    frames = rows(directory / "calibration-frames.jsonl")
    bridge = [r for r in rows(directory / "bridge-frames.jsonl") if "provenance" in r]
    status = json.loads((directory / "calibration-status.json").read_text())
    supervisor = [r for r in rows(directory / "supervisor-trace.jsonl") if r["event"] == "request"]
    failures = []

    faults = [t for _, t in texts if t.startswith("state fault")]
    rejects = [t for _, t in texts if t.startswith("reject ")]
    if faults or rejects:
        failures.append(f"guard faults {faults} / rejections {rejects}")
    if any(r["decision"] != "forwarded" for r in supervisor):
        failures.append("supervisor rejected a calibration request")
    if any(s["out"][1] != 0 or s["cmd"][1] != 0 or s["steer"] != [0, 0] for s in steps):
        failures.append("nonzero steering")
    if status.get("abort"):
        failures.append("calibration aborted: " + status["abort"])
    accepts = {}
    for _, text in texts:
        parts = text.split()
        if len(parts) >= 6 and parts[0] == "accept":  # accept <seq> <expiryInNs> <throttle> <steering> <inputs>
            accepts[int(parts[1])] = {"remaining_s": int(parts[2]) / 1e9, "throttle": float(parts[3])}

    # Guard step index -> IPS simulation time (both from the same fixed-step clock).
    offsets = sorted(r["provenance"]["sources"]["ips"]["sim_time"] - r["provenance"]["sources"]["ips"]["step"] * FIXED_STEP_S
                     for r in bridge if r["provenance"]["sources"]["ips"].get("acquired"))
    offset = offsets[len(offsets) // 2]

    runs, start = [], None
    for i, s in enumerate(steps):
        if s["out"][0] != 0 and start is None:
            start = i
        elif s["out"][0] == 0 and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(steps) - 1))
    planned = status.get("pulses", [])
    if len(runs) != len(planned):
        failures.append(f"{len(runs)} applied pulses for {len(planned)} planned")

    pulses = []
    for index, (first, last) in enumerate(runs):
        seg = steps[first:last + 1]
        throttle = seg[0]["out"][0]
        expected = MOTOR_TORQUE_NM * throttle / 4
        torque_ok = all(all(abs(m - expected) <= 1e-4 for m in s["motor"]) and s["brake"] == [0, 0, 0, 0] for s in seg)
        after = steps[last + 1:last + 1 + 2000]
        released = all(s["motor"] == [0, 0, 0, 0] and all(abs(b - BRAKE_NM) < 1e-3 for b in s["brake"]) for s in after)
        end_sim = seg[-1]["step"] * FIXED_STEP_S + offset
        start_sim = seg[0]["step"] * FIXED_STEP_S + offset
        applied_seq = seg[0]["applied"]
        accept = accepts.get(applied_seq, {})
        gen_to_accept = LIFE_S - accept["remaining_s"] if "remaining_s" in accept else None
        plan = planned[index] if index < len(planned) else {}
        window = [f for f in frames if start_sim - 0.3 <= f["ips_sim_time"] <= end_sim + 3.0]
        before = [f for f in frames if f["ips_sim_time"] < start_sim]
        origin = before[-1]["pose"] if before else plan.get("start")
        heading = origin[2]

        def along(f):
            dx, dy = f["pose"][0] - origin[0], f["pose"][1] - origin[1]
            return math.cos(heading) * dx + math.sin(heading) * dy, abs(-math.sin(heading) * dx + math.cos(heading) * dy)

        travel = max((along(f)[0] for f in window), default=0.0)
        lateral = max((along(f)[1] for f in window), default=0.0)
        yaw = max((abs(math.degrees(math.remainder(f["pose"][2] - heading, math.tau))) for f in window), default=0.0)
        peak = max((f["speed_mps"] for f in window), default=0.0)
        stop = next((f["ips_sim_time"] - end_sim for f in window if f["ips_sim_time"] > end_sim
                     and f["speed_mps"] < STOP_SPEED and all(g["speed_mps"] < STOP_SPEED for g in window
                                                             if g["ips_sim_time"] >= f["ips_sim_time"])), None)
        applied_s = len(seg) * FIXED_STEP_S
        stop_from_generation = (gen_to_accept + applied_s + stop) if gen_to_accept is not None and stop is not None else None
        row = {"throttle": throttle, "applied_steps": len(seg), "applied_s": applied_s, "guard_seq": applied_seq,
               "generation_to_accept_s": gen_to_accept, "torque_per_wheel_nm": seg[0]["motor"],
               "expected_torque_per_wheel_nm": expected, "torque_ok": torque_ok, "released_with_brakes": released,
               "peak_speed_mps": peak, "travel_m": travel, "lateral_m": lateral, "yaw_change_deg": yaw,
               "stop_after_application_s": stop, "stop_from_generation_s": stop_from_generation,
               "planned_throttle": plan.get("throttle")}
        moved = travel > 0.002
        checks = {"torque": torque_ok, "released": released,
                  "forward": travel >= -0.002 and (not moved or travel > 0),
                  "caps": peak <= SPEED_CAP and travel <= TRAVEL_CAP and yaw <= 10 and lateral <= 0.15,
                  "stop": stop_from_generation is not None and stop_from_generation <= STOP_WINDOW_S
                          and travel < STOP_TRAVEL_M,
                  "planned": plan.get("throttle") is not None and abs(plan["throttle"] - throttle) < 1e-9}
        row["checks"] = checks
        row["passed"] = all(checks.values())
        if not row["passed"]:
            failures.append(f"pulse {index} throttle {throttle}: " + ", ".join(k for k, v in checks.items() if not v))
        pulses.append(row)

    first_motion = bridge[0]["motion"]
    last_motion = bridge[-1]["motion"]
    ticks = [b - a for a, b in zip(first_motion["Encoder Ticks"], last_motion["Encoder Ticks"])]
    angles = [b - a for a, b in zip(first_motion["Encoder Angles"], last_motion["Encoder Angles"])]
    total_travel = sum(max(p["travel_m"], 0) for p in pulses)
    if total_travel > 0.002 and not (all(t > 0 for t in ticks) or all(t < 0 for t in ticks)):
        failures.append(f"encoder ticks did not change with one sign: {ticks}")
    stops = [t for _, t in texts if t.startswith("state stopped")]
    return {"run": str(directory), "pulses": pulses, "encoder_tick_change": ticks, "encoder_angle_change_rad": angles,
            "encoder_sign_forward": "positive" if all(t > 0 for t in ticks) else "negative" if all(t < 0 for t in ticks) else None,
            "total_travel_m": total_travel, "finish_reason": status.get("finish_reason"), "abort": status.get("abort"),
            "precheck": status.get("precheck"), "guard_stops": stops, "supervisor_decisions": len(supervisor),
            "guard_steps": len(steps), "failures": failures, "passes": not failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    report = analyze(args.run)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"pulses": [{k: p[k] for k in ("throttle", "applied_s", "peak_speed_mps", "travel_m",
                                                    "stop_from_generation_s", "passed")} for p in report["pulses"]],
                      "failures": report["failures"], "passes": report["passes"]}))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
