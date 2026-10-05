#!/usr/bin/env python3
"""S1-03 stage M3 (open-loop identification holds, steering 0): analysis of one trial.

Holds are taken from the guard's per-step trace (runs of nonzero applied throttle); speed
from the calibration source's per-frame encoder log (mean wheel angle x 0.059 m over encoder
acquisition sim time). Per hold it reports the acceleration curve, initial acceleration per unit
throttle (plant gain b), whether speed plateaued (steady state for the feedforward map), and
braking (start speed, time, distance, deceleration). Protocol criteria (§3, proposal D8):
  - applied torque = 85.6 x throttle / 4 per wheel; after the hold motor torque 0 with brakes;
  - forward travel; encoder travel agrees with IPS travel within 5 mm + 5 %;
  - caps: speed <= 0.5 m/s, hold travel <= 0.5 m, |yaw| <= 10 deg, lateral <= 0.15 m;
  - stop qualification: speed < 0.02 m/s within 1.5 s of the last nonzero request's generation,
    travel after it < 0.15 m;
  - no guard fault or rejection; every supervisor decision forwarded.
Fresh JSON output; nonzero exit on failure.
"""

import argparse
import json
import math
from pathlib import Path

MOTOR_TORQUE_NM, BRAKE_NM, FIXED_STEP_S, LIFE_S = 85.6, 85.5999984741211, 0.001, 0.5
SPEED_CAP, TRAVEL_CAP, STOP_SPEED, STOP_WINDOW_S, STOP_TRAVEL_M = 0.5, 0.5, 0.02, 1.5, 0.15
WHEEL_RADIUS_M = 0.059


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(directory: Path) -> dict:
    trace = rows(directory / "guard/guard-trace.jsonl")
    steps = [r for r in trace if r.get("k") == "step"]
    events = [(r, r["text"].split(" ", 1)[1]) for r in trace if r.get("k") == "event"]
    frames = rows(directory / "calibration-frames.jsonl")
    bridge = [r for r in rows(directory / "bridge-frames.jsonl") if "provenance" in r]
    status = json.loads((directory / "calibration-status.json").read_text())
    supervisor = [r for r in rows(directory / "supervisor-trace.jsonl") if r["event"] == "request"]
    failures = []

    faults = [t for _, t in events if t.startswith("state fault")]
    rejects = [t for _, t in events if t.startswith("reject ")]
    if faults or rejects:
        failures.append(f"guard faults {faults} / rejections {rejects}")
    if any(r["decision"] != "forwarded" for r in supervisor):
        failures.append("supervisor rejected a calibration request")
    if any(s["out"][1] != 0 or s["steer"] != [0, 0] for s in steps):
        failures.append("nonzero steering")
    if status.get("abort"):
        failures.append("calibration aborted: " + status["abort"])
    accepts = {}
    for r, text in events:
        parts = text.split()
        if len(parts) >= 6 and parts[0] == "accept":  # accept <seq> <expiryInNs> <throttle> <steering> <inputs>
            accepts[int(parts[1])] = {"step": r["step"], "remaining_s": int(parts[2]) / 1e9}
    offsets = sorted(r["provenance"]["sources"]["left_encoder"]["sim_time"] -
                     r["provenance"]["sources"]["left_encoder"]["step"] * FIXED_STEP_S
                     for r in bridge if r["provenance"]["sources"]["left_encoder"].get("acquired"))
    offset = offsets[len(offsets) // 2]

    runs, begin = [], None
    for i, s in enumerate(steps):
        if s["out"][0] != 0 and begin is None:
            begin = i
        elif s["out"][0] == 0 and begin is not None:
            runs.append((begin, i - 1))
            begin = None
    planned = status.get("holds", [])
    if len(runs) != len(planned):
        failures.append(f"{len(runs)} applied holds for {len(planned)} recorded")

    holds = []
    for index, (first, last) in enumerate(runs):
        seg = steps[first:last + 1]
        throttle = seg[0]["out"][0]
        expected = MOTOR_TORQUE_NM * throttle / 4
        torque_ok = all(all(abs(m - expected) <= 1e-4 for m in s["motor"]) for s in seg)
        # Windows stop at the next hold (holds are only ~1.5 s apart; the first analysis let them overlap).
        next_first = runs[index + 1][0] if index + 1 < len(runs) else len(steps)
        after = steps[last + 1:min(last + 1 + 2000, next_first)]
        released = bool(after) and all(s["motor"] == [0, 0, 0, 0] and all(abs(b - BRAKE_NM) < 1e-3 for b in s["brake"])
                                       for s in after)
        start_sim = seg[0]["step"] * FIXED_STEP_S + offset
        end_sim = seg[-1]["step"] * FIXED_STEP_S + offset
        next_sim = steps[next_first]["step"] * FIXED_STEP_S + offset if next_first < len(steps) else math.inf
        accept = accepts.get(seg[-1]["applied"])
        generation_sim = (accept["step"] * FIXED_STEP_S + offset + accept["remaining_s"] - LIFE_S) if accept else None
        window = [f for f in frames if start_sim - 0.25 <= f["encoder_sim_time"] <= min(end_sim + 2.5, next_sim - 0.01)]
        during = [f for f in window if start_sim < f["encoder_sim_time"] <= end_sim + 0.05]
        curve = [{"t_s": round(f["encoder_sim_time"] - start_sim, 4), "speed_mps": f["encoder_speed_mps"]} for f in window]
        accel = []
        for a, b in zip(during, during[1:]):
            dt = b["encoder_sim_time"] - a["encoder_sim_time"]
            if dt > 0:
                accel.append({"speed_mps": (a["encoder_speed_mps"] + b["encoder_speed_mps"]) / 2,
                              "accel_mps2": (b["encoder_speed_mps"] - a["encoder_speed_mps"]) / dt})
        initial = during[0]["encoder_speed_mps"] / max(during[0]["encoder_sim_time"] - start_sim, 1e-3) if during else None
        late = accel[-2:]
        plateau = bool(late) and all(abs(a["accel_mps2"]) < 0.05 for a in late)
        # Settling: first frame within 10 % of the final steady speed (frames are ~0.2 s apart,
        # so this is an upper bound on the response time).
        steady_reference = (sum(f["encoder_speed_mps"] for f in during[-3:]) / len(during[-3:])) if len(during) >= 3 else None
        settle_frame = next((f for f in during if steady_reference and abs(f["encoder_speed_mps"] - steady_reference)
                             <= 0.1 * steady_reference), None)
        settle_s = settle_frame["encoder_sim_time"] - start_sim if settle_frame else None
        peak = max((f["encoder_speed_mps"] for f in window), default=0.0)
        brake_start_speed = next((f["encoder_speed_mps"] for f in reversed(window) if f["encoder_sim_time"] <= end_sim + 0.05), None)
        stop_frame = next((f for f in window if f["encoder_sim_time"] > end_sim and all(
            g["encoder_speed_mps"] < STOP_SPEED for g in window if g["encoder_sim_time"] >= f["encoder_sim_time"])), None)
        def angle_at(t):  # last frame acquired at or before t (conservative: includes motion after it)
            earlier = [f for f in window if f["encoder_sim_time"] <= t]
            return (earlier[-1] if earlier else window[0])["encoder_angle_rad"] if window else 0.0

        hold_travel = (window[-1]["encoder_angle_rad"] - angle_at(start_sim)) * WHEEL_RADIUS_M if window else 0.0
        brake_distance = (window[-1]["encoder_angle_rad"] - angle_at(end_sim)) * WHEEL_RADIUS_M if window else None
        brake_time = stop_frame["encoder_sim_time"] - end_sim if stop_frame else None
        stop_from_generation = stop_frame["encoder_sim_time"] - generation_sim if stop_frame and generation_sim else None
        travel_after_generation = ((window[-1]["encoder_angle_rad"] - angle_at(generation_sim)) * WHEEL_RADIUS_M
                                   if generation_sim and window else None)
        before = [f for f in frames if f["encoder_sim_time"] <= start_sim]
        last_frame = window[-1] if window else None
        origin = before[-1]["pose"] if before else None
        ips_travel = lateral = yaw = None
        if origin and last_frame:
            dx, dy = last_frame["pose"][0] - origin[0], last_frame["pose"][1] - origin[1]
            ips_travel = math.cos(origin[2]) * dx + math.sin(origin[2]) * dy
            lateral = max(abs(-math.sin(origin[2]) * (f["pose"][0] - origin[0]) + math.cos(origin[2]) * (f["pose"][1] - origin[1]))
                          for f in window)
            yaw = max(abs(math.degrees(math.remainder(f["pose"][2] - origin[2], math.tau))) for f in window)
        row = {"throttle": throttle, "applied_s": len(seg) * FIXED_STEP_S, "end_reason": (planned[index] if index < len(planned) else {}).get("end_reason"),
               "torque_ok": torque_ok, "released_with_brakes": released, "peak_speed_mps": peak,
               "initial_accel_mps2": initial, "initial_accel_per_unit_throttle": initial / throttle if initial else None,
               "plateau": plateau, "steady_speed_mps": steady_reference if plateau else None,
               "steady_gain_mps_per_unit_throttle": steady_reference / throttle if plateau and steady_reference else None,
               "settle_within_s": settle_s,
               "accel_vs_speed": accel, "brake_start_speed_mps": brake_start_speed, "brake_time_s": brake_time,
               "brake_distance_m": brake_distance,
               "brake_decel_mps2": (brake_start_speed / brake_time) if brake_time and brake_start_speed else None,
               "hold_travel_m": hold_travel, "ips_travel_m": ips_travel, "lateral_m": lateral, "yaw_change_deg": yaw,
               "stop_from_generation_s": stop_from_generation, "travel_after_generation_m": travel_after_generation,
               "speed_curve": curve}
        checks = {
            "torque": torque_ok, "released": released, "forward": hold_travel > 0,
            "encoder_vs_ips": ips_travel is not None and abs(hold_travel - ips_travel) <= 0.005 + 0.05 * abs(hold_travel),
            "caps": peak <= SPEED_CAP and hold_travel <= TRAVEL_CAP and (yaw or 0) <= 10 and (lateral or 0) <= 0.15,
            "stop": stop_from_generation is not None and stop_from_generation <= STOP_WINDOW_S
                    and travel_after_generation is not None and travel_after_generation < STOP_TRAVEL_M}
        row["checks"], row["passed"] = checks, all(checks.values())
        if not row["passed"]:
            failures.append(f"hold {index} throttle {throttle}: " + ", ".join(k for k, v in checks.items() if not v))
        holds.append(row)

    gains = [h["steady_gain_mps_per_unit_throttle"] for h in holds if h["steady_gain_mps_per_unit_throttle"]]
    settles = [h["settle_within_s"] for h in holds if h["settle_within_s"] is not None]
    return {"run": str(directory), "holds": holds,
            "steady_gain_mps_per_unit_throttle": sorted(gains)[len(gains) // 2] if gains else None,
            "steady_gain_spread": [min(gains), max(gains)] if gains else None,
            "settle_within_s_max": max(settles) if settles else None,
            "finish_reason": status.get("finish_reason"), "abort": status.get("abort"), "precheck": status.get("precheck"),
            "supervisor_decisions": len(supervisor), "guard_steps": len(steps),
            "guard_stops": [t for _, t in events if t.startswith("state stopped")],
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
    print(json.dumps({"holds": [{k: h[k] for k in ("throttle", "applied_s", "end_reason", "peak_speed_mps",
                                                  "steady_gain_mps_per_unit_throttle", "settle_within_s", "plateau", "brake_distance_m",
                                                  "stop_from_generation_s", "passed")} for h in report["holds"]],
                      "steady_gain": report["steady_gain_mps_per_unit_throttle"], "settle_max_s": report["settle_within_s_max"], "failures": report["failures"],
                      "passes": report["passes"]}))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
