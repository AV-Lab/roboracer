#!/usr/bin/env python3
"""Top-down replay video of one recorded run (no simulator, no motion).

Draws the vehicle footprint (rear-axle IPS truth + IMU yaw, linearly interpolated between telemetry
frames on simulation time) over the qualified C0 geometry, with a trail, and a side panel: time,
encoder speed, the controller's target speed and steering (AVLite ticks), the scorer's footprint
clearance and lap progress, and the stage phase. It is a reconstruction from recorded data, not
simulator footage; the LiDAR scan itself is not shown (runs keep only per-scan hashes).
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roboracer_scoring as rs  # noqa: E402


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def unwrap(angles):
    out, offset = [], 0.0
    for i, a in enumerate(angles):
        if i and a + offset - out[-1] > math.pi:
            offset -= 2 * math.pi
        elif i and a + offset - out[-1] < -math.pi:
            offset += 2 * math.pi
        out.append(a + offset)
    return out


def render(run: Path, geometry_path: Path, output: Path, fps: int = 15, speedup: float = 1.0,
           start_s: float | None = None, end_s: float | None = None, title: str | None = None) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter
    from matplotlib.patches import PathPatch, Polygon as MplPolygon
    from shapely import wkt

    geometry = json.loads(geometry_path.read_text())
    frames = rs.truth_frames(run)
    score = rs.score(geometry, frames)
    samples = score["samples"]
    # Host monotonic ↔ simulation time from the frames (same rows), for the AVLite tick channel.
    mono = [f["received_ns"] for f in frames]
    sim = [f["sim_time"] - frames[0]["sim_time"] for f in frames]
    xs, ys = [f["x"] for f in frames], [f["y"] for f in frames]
    yaws = unwrap([f["yaw"] for f in frames])
    ticks = [t for t in rows(run / "plugin-ticks.jsonl") if "phase" in t]
    tick_t = [(t["start_ns"] - mono[0]) / 1e9 for t in ticks]  # wall since first frame ≈ sim (RTF 1.000)

    def at(series, t):
        i = max(0, min(len(sim) - 2, bisect.bisect_right(sim, t) - 1))
        span = sim[i + 1] - sim[i]
        w = 0.0 if span <= 0 else min(1.0, max(0.0, (t - sim[i]) / span))
        return series[i] + w * (series[i + 1] - series[i])

    def tick_at(t):
        i = bisect.bisect_right(tick_t, t) - 1
        return ticks[i] if i >= 0 else {}

    # Default window: 3 s before the stage's run phase to 3 s after it finished (no long parked tail).
    run_t = [tick_t[i] for i, t in enumerate(ticks) if t["phase"] == "run"]
    done_t = [tick_t[i] for i, t in enumerate(ticks) if t["phase"] == "finished"]
    auto_start = max(sim[0], run_t[0] - 3.0) if run_t else sim[0]
    auto_end = min(sim[-1], done_t[0] + 3.0) if done_t else sim[-1]
    t_first = auto_start if start_s is None else start_s
    t_last = auto_end if end_s is None else min(end_s, sim[-1])
    step = speedup / fps
    times = [t_first + k * step for k in range(int((t_last - t_first) / step) + 1)]

    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_axes([0.02, 0.04, 0.42, 0.9])
    panel = fig.add_axes([0.47, 0.52, 0.51, 0.42])
    panel.axis("off")
    sp = fig.add_axes([0.52, 0.29, 0.45, 0.19])
    st = fig.add_axes([0.52, 0.06, 0.45, 0.19])
    ax.add_patch(PathPatch(rs._polygon_path(wkt.loads(geometry["region_wkt"])), facecolor="#e8f0e8", edgecolor="none"))
    ax.add_patch(PathPatch(rs._polygon_path(wkt.loads(geometry["walls_wkt"])), facecolor="#555555", edgecolor="none"))
    line = geometry["centerline"] + geometry["centerline"][:1]
    ax.plot([p[0] for p in line], [p[1] for p in line], "--", color="#3366aa", lw=0.6)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_xticks([])
    ax.set_yticks([])
    trail, = ax.plot([], [], "-", color="#cc3333", lw=1.2)
    car = MplPolygon([[0, 0]] * 4, closed=True, facecolor="#1f77b4", edgecolor="black", lw=0.8, zorder=5)
    ax.add_patch(car)
    fp = geometry["footprint"]
    corners = [(fp["x_min"], fp["y_min"]), (fp["x_max"], fp["y_min"]), (fp["x_max"], fp["y_max"]), (fp["x_min"], fp["y_max"])]

    speed_t = [(tick_t[i], t.get("encoder_speed")) for i, t in enumerate(ticks) if t.get("encoder_speed") is not None]
    target_t = [(tick_t[i], (t.get("controller") or {}).get("target_speed")) for i, t in enumerate(ticks)
                if (t.get("controller") or {}).get("target_speed") is not None]
    steer_t = [(tick_t[i], (t.get("controller") or {}).get("steer")) for i, t in enumerate(ticks)
               if (t.get("controller") or {}).get("steer") is not None]
    for axis, series, label, color in ((sp, speed_t, "encoder speed", "#1f77b4"), (sp, target_t, "target", "#ff7f0e"),
                                       (st, steer_t, "steer request", "#2ca02c")):
        axis.plot([a for a, _ in series], [b for _, b in series], color=color, lw=1, label=label)
    sp.set_ylabel("m/s")
    sp.set_ylim(-0.02, 0.45)
    st.set_ylabel("rad")
    st.set_ylim(-0.4, 0.4)
    st.set_xlabel("time since first frame [s]")
    for axis in (sp, st):
        axis.set_xlim(t_first, t_last)
        axis.legend(loc="upper right", fontsize=8)
        axis.grid(alpha=0.3)
    cursors = [axis.axvline(t_first, color="black", lw=0.8) for axis in (sp, st)]
    text = panel.text(0, 1, "", va="top", family="monospace", fontsize=12)
    fig.suptitle(title or f"Replay (reconstructed from recorded truth): {run.parent.name}", fontsize=12)

    sample_t = [s["sim_time"] - frames[0]["sim_time"] for s in samples]
    lap_len = geometry["length_m"]
    trail_x, trail_y = [], []
    writer = FFMpegWriter(fps=fps, codec="libx264", bitrate=-1, extra_args=["-pix_fmt", "yuv420p", "-crf", "23"])
    with writer.saving(fig, str(output), dpi=100):
        for t in times:
            x, y, yaw = at(xs, t), at(ys, t), at(yaws, t)
            c, s = math.cos(yaw), math.sin(yaw)
            car.set_xy([(x + c * u - s * v, y + s * u + c * v) for u, v in corners])
            trail_x.append(x)
            trail_y.append(y)
            trail.set_data(trail_x, trail_y)
            for cur in cursors:
                cur.set_xdata([t, t])
            k = max(0, bisect.bisect_right(sample_t, t) - 1)
            smp = samples[k]
            tick = tick_at(t)
            ctl = tick.get("controller") or {}
            v = tick.get("encoder_speed")
            text.set_text(
                f"t           {t:7.1f} s\n"
                f"phase       {tick.get('phase', '-')}\n"
                f"speed       {v if v is None else round(v, 3)} m/s\n"
                f"target      {ctl.get('target_speed', float('nan')):.3f} m/s\n"
                f"steer req   {ctl.get('steer', float('nan')):+.3f} rad\n"
                f"clearance   {smp['clearance_m']:.3f} m (footprint to wall)\n"
                f"progress    {smp['progress_m']:6.2f} m  ({smp['progress_m'] / lap_len * 100:5.1f} % of lap)\n"
                f"laps scored {sum(1 for lap in score['laps'] if lap['sim_time'] - frames[0]['sim_time'] <= t)}")
            writer.grab_frame()
    plt.close(fig)
    return {"output": str(output), "frames": len(times), "fps": fps, "speedup": speedup,
            "duration_s": len(times) / fps, "laps": score["laps"], "min_clearance_m": score["min_clearance_m"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True, help="run-01 directory")
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="fresh .mp4")
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--speedup", type=float, default=1.0)
    parser.add_argument("--start", type=float, help="seconds after the first frame (default: run phase - 3 s)")
    parser.add_argument("--end", type=float, help="default: stage finished + 3 s")
    parser.add_argument("--full", action="store_true", help="whole recording, no trimming")
    parser.add_argument("--title")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    start, end = (0.0, 1e9) if args.full else (args.start, args.end)
    print(json.dumps(render(args.run, args.geometry, args.output, args.fps, args.speedup, start, end,
                            args.title)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
