#!/usr/bin/env python3
"""Single-episode entrypoint for AutoDRIVE C0 (S1-05): run or re-score one episode, export its manifest.

live      Run one fresh-process episode through autodrive_neutral.py on an approved AVLite motion
          stage, then score and export it. Initialization is NOT an unattended reset: each episode
          starts a fresh player at the scene's default spawn, and a person reviews the pre-Connect
          screenshot (review.py) before the single scripted Connect click. The runner waits for that
          review; this tool records it as a manual step.
recorded  Score and export an existing results directory (recorded-input mode). Same result schema.

Outputs (fresh files in --output): episode.json (roboracer.episode/1: outcome, independent score
summary) and manifest.json (roboracer.episode-manifest/1: code and binary identity, configuration,
scene, start conditions, initialization incl. manual steps, randomization, clocks, provenance,
invocation, processes, host). The full per-frame score goes to score.json.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roboracer_scoring as rs  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
AVLITE = Path("/home/a2rl/avlite")
APPROVAL = REPO / "docs/planning/s1-motion-approval.json"
# Only the approved AVLite motion stages (M6: lap proposal v0.1, "approve D9, D10, D11; run M6").
LIVE_STAGES = ("m4", "m5", "m6", "s3b", "s3v1", "s3v2", "s3v1i", "s3m3a", "s3m3b")  # S3 B bring-up (D32 A); speed steps V1 (D35), V2 (D40)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def git_identity(path: Path):
    def git(*args):
        done = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else None
    status = git("status", "--porcelain")
    return {"path": str(path), "head": git("rev-parse", "HEAD"),
            "dirty": None if status is None else bool(status),
            "dirty_paths": None if status is None else status.splitlines()}


def file_identity(path: Path | None):
    if path is None or not path.exists():
        return {"path": None if path is None else str(path), "exists": False}
    return {"path": str(path), "sha256": rs.sha256(path), "bytes": path.stat().st_size}


def host_identity():
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used",
                          "--format=csv,noheader"], capture_output=True, text=True)
    return {"hostname": platform.node(), "kernel": platform.release(), "python": sys.version.split()[0],
            "cpu_count": os.cpu_count(), "gpu": gpu.stdout.strip().splitlines() if gpu.returncode == 0 else None,
            "display": os.environ.get("DISPLAY"), "session_type": os.environ.get("XDG_SESSION_TYPE"),
            "captured_utc": utc_now()}


def run_directory(results: Path) -> Path:
    runs = sorted(results.glob("run-*"))
    if len(runs) != 1:
        raise SystemExit(f"Expected exactly one run-* directory in {results}, found {len(runs)}")
    return runs[0]


def outcome(status, run, runner_exit):
    """The episode's end as the stack recorded it; never inferred from the score."""
    if status is None or run is None:
        return {"state": "incomplete", "reason": "missing run.json or plugin status"}
    if status.get("abort"):
        return {"state": "aborted", "reason": status["abort"]}
    if runner_exit not in (None, 0):
        return {"state": "incomplete", "reason": f"runner exit {runner_exit}"}
    if status.get("stage_phase") != "finished":
        return {"state": "incomplete", "reason": f"stage phase {status.get('stage_phase')}"}
    return {"state": "finished", "reason": status.get("finish_reason")}


def export(results: Path, geometry_path: Path, output: Path, mode: str, invocation: dict,
           runner_exit=None, build_record: Path | None = None, player: Path | None = None) -> dict:
    run = run_directory(results)
    run_json, result_json = read_json(run / "run.json"), read_json(results / "result.json")
    status = read_json(run / "plugin-observer-status.json")
    geometry = json.loads(geometry_path.read_text())
    score = rs.score(geometry, rs.truth_frames(run))
    score["geometry"] = {"path": str(geometry_path), "sha256": rs.sha256(geometry_path)}
    end = outcome(status, run_json, runner_exit)
    summary = {k: score[k] for k in ("frames", "progress_m", "lap_length_m", "laps", "contact_events",
                                     "offtrack_events", "min_clearance_m", "start_offset_m")}
    clean = not score["contact_events"] and not score["offtrack_events"]
    episode = {"schema": "roboracer.episode/1", "mode": mode, "results": str(results), "run": str(run),
               "stage": status.get("stack_profile") if status else None, "outcome": end,
               "score": summary, "contact_free_and_on_track": clean,
               "completed_laps": len(score["laps"]),
               "scorer": "roboracer_scoring.py (independent: simulator truth + qualified geometry only)"}

    children = (run_json or {}).get("children", [])
    build = read_json(build_record) if build_record else None
    if player is None:
        argv = next((c["argv"] for c in children if c.get("label") == "player"), None)
        player = Path(argv[0]) if argv else None
    binaries = {"player": file_identity(player),
                "game_assembly": file_identity(player.parent / "GameAssembly.so" if player else None),
                "build_record": file_identity(build_record)}
    if build:
        recorded = build.get("output_files", {})
        binaries["build"] = {"source_commit": build.get("source_commit"), "sim1_patch": build.get("sim1_patch"),
                             "editor_version": build.get("expected_version")}
        binaries["matches_build_record"] = {
            name: binaries[key].get("sha256") == recorded.get(name, {}).get("sha256")
            for key, name in (("player", "AutoDRIVE.x86_64"), ("game_assembly", "GameAssembly.so"))}
    manual = (run_json or {}).get("manual_mode_review")
    manifest = {
        "schema": "roboracer.episode-manifest/1", "exported_utc": utc_now(), "mode": mode,
        "invocation": invocation,
        "code": {"roboracer": git_identity(REPO), "avlite": git_identity(AVLITE),
                 "tools_sha256": {p.name: rs.sha256(p) for p in (Path(__file__), Path(rs.__file__),
                                                                  REPO / "scripts/autodrive_neutral.py")},
                 "runner_tool_sha256_at_run": (result_json or {}).get("tool_sha256"),
                 "note": "Code identity is captured at export; for recorded mode compare runner_tool_sha256_at_run."},
        "binaries": binaries,
        "configuration": {"stage": episode["stage"], "runner_result": result_json,
                          "environment_overrides": (run_json or {}).get("environment_overrides"),
                          "guard": (run_json or {}).get("guard"),
                          "motion_approval": file_identity(APPROVAL),
                          "max_target_speed_mps": (status or {}).get("max_target_speed_mps")},
        "scene": {"track": geometry.get("track"), "geometry": score["geometry"], "geometry_inputs": geometry.get("inputs"),
                  "lap_length_m": geometry.get("length_m"), "spawn": geometry.get("spawn")},
        "start_conditions": {"first_truth_frame": score["start_pose"], "offset_from_spawn_m": score["start_offset_m"],
                             "workspace_precheck": (status or {}).get("precheck")},
        "initialization": {
            "method": "fresh player process at the scene's default spawn; guard interlocked until "
                      + ("the automated D21 pre-Connect check passes" if (run_json or {}).get("ui_checks") else
                         "a person reviews the pre-Connect screenshot") + "; one scripted Connect click",
            "ui_checks": (run_json or {}).get("ui_checks"),
            "unattended_reset": False,
            "manual_steps": [{"step": "visual pre-Connect review", "record": manual}] if manual else [],
            "scripted_actions": (run_json or {}).get("actions")},
        "randomization": {"seeds": None, "note": "No randomized inputs; the simulator is not bitwise reproducible"},
        "clocks": {"truth": "IPS acquisition simulation time per telemetry frame (~5 Hz)",
                   "stack": "SyncExecuter 10 Hz wall-clock ticks on pinned snapshots; physics progress in simulation time",
                   "latency": "measured per clock domain; no cross-clock subtraction"},
        "provenance": {"truth_source": "runner bridge child bridge-frames.jsonl (not the driving stack)",
                       "provenance_enabled": (run_json or {}).get("provenance"),
                       "source_acquisition_identity_available": (run_json or {}).get("source_acquisition_identity_available")},
        "processes": {"children": children, "runner_exit": runner_exit,
                      "cleanup_seconds": (run_json or {}).get("cleanup_seconds"),
                      "endpoint_released": (run_json or {}).get("endpoint_released"),
                      "started_utc": (run_json or {}).get("started_utc"),
                      "completed_utc": (run_json or {}).get("completed_utc")},
        "host": host_identity(),
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("score.json", score), ("episode.json", episode), ("manifest.json", manifest)):
        (output / name).write_text(json.dumps(value, indent=1) + "\n")
    return episode


def kill_runner_when_requested(runner, results: Path, observe_s=10.0, timeout_s=600.0):
    """F1-8 runner exit (M1 protocol v0.1): when the AVLite stage asks, SIGKILL the runner; keep
    the orphaned children running for `observe_s` so the supervisor's runner lease and the guard
    lease act and the stop is recorded; then terminate each orphaned process group (pids from the
    runner's last run.json checkpoint) and record the reaping."""
    import signal
    import time
    request = None
    deadline = time.monotonic() + timeout_s
    while runner.poll() is None and time.monotonic() < deadline:
        found = sorted(results.glob("run-*/kill-runner-request.json"))
        if found:
            request = found[0]
            break
        time.sleep(0.05)
    if request is None:
        return {"killed": False, "reason": "no request before the runner ended"}
    record = {"killed": True, "kill_ns": time.monotonic_ns(), "request": str(request)}
    runner.kill()
    runner.wait()
    time.sleep(observe_s)
    run_json = json.loads((request.parent / "run.json").read_text())
    reaped = []
    for child in run_json.get("children", []):
        pid, entry = child["pid"], {"label": child["label"], "pid": child["pid"]}
        for sig, wait in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 2.0)):
            try:
                os.killpg(pid, sig)
            except ProcessLookupError:
                entry.setdefault("result", "already gone")
                break
            end = time.monotonic() + wait
            while time.monotonic() < end:
                try:
                    os.killpg(pid, 0)
                except ProcessLookupError:
                    entry["result"] = f"terminated by {sig.name}"
                    break
                time.sleep(0.05)
            if "result" in entry:
                break
        entry.setdefault("result", "still alive")
        reaped.append(entry)
    record.update(reaped=reaped, reaped_ns=time.monotonic_ns(),
                  all_gone=all(e["result"] != "still alive" for e in reaped))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)
    live = sub.add_parser("live")
    live.add_argument("--stage", choices=LIVE_STAGES, required=True)
    live.add_argument("--duration", type=float, required=True, help="guard duration, seconds")
    live.add_argument("--results", type=Path, required=True, help="fresh runner results directory")
    live.add_argument("--context", type=Path, required=True)
    live.add_argument("--player", type=Path, required=True)
    live.add_argument("--build-record", type=Path, required=True)
    live.add_argument("--f1-case", default=None, help="S1-06 F1 fault case (M1 protocol v0.1; stage m6)")
    live.add_argument("--m3-ic", type=int, default=None, help="S3-05 M3 initial condition 0-4 (stages s3m3a/s3m3b)")
    live.add_argument("--icp-init-offset", type=float, nargs=3, default=None, help="S3 F3-2/F3-3 configured-pose offset")
    live.add_argument("--record-video", action="store_true", help="record only the AutoDRIVE window")
    live.add_argument("--ui-reference", type=Path, default=None,
                      help="S2 (D21 A): reviewed UI reference; the automated pre-Connect check replaces review.py")
    rec = sub.add_parser("recorded")
    rec.add_argument("--results", type=Path, required=True, help="existing runner results directory")
    rec.add_argument("--build-record", type=Path)
    for p in (live, rec):
        p.add_argument("--geometry", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True, help="fresh episode export directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be fresh")
    invocation = {"argv": sys.argv, "cwd": os.getcwd(), "python": sys.executable, "started_utc": utc_now()}
    runner_exit = None
    if args.mode == "live":
        if args.results.exists():
            parser.error("--results must be fresh")
        command = [sys.executable, "-B", str(REPO / "scripts/autodrive_neutral.py"), "run",
                   "--context", str(args.context), "--player", str(args.player),
                   "--build-record", str(args.build_record), "--results", str(args.results),
                   "--profile", "p0-creep", "--provenance", "--guard", "calibration",
                   "--motion-stage", args.stage, "--reply-delay", "0.05", "--runs", "1",
                   "--duration", str(args.duration), *(["--f1-case", args.f1_case] if args.f1_case else []),
                   *(["--m3-ic", str(args.m3_ic)] if args.m3_ic is not None else []),
                   *(["--icp-init-offset", *map(str, args.icp_init_offset)] if args.icp_init_offset else []),
                   *(["--record-video"] if args.record_video else []),
                   *(["--ui-reference", str(args.ui_reference)] if args.ui_reference else [])]
        invocation["runner_argv"] = command
        print(json.dumps({"runner": "started", "manual_step": None if args.ui_reference else
                          "review ui-before-connect.png, then run review.py"}), flush=True)
        args.results.parent.mkdir(parents=True, exist_ok=True)
        with open(f"{args.results}-console.log", "w") as log:
            runner = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            if args.f1_case == "f1-8":
                invocation["f1_8"] = kill_runner_when_requested(runner, args.results)
            runner_exit = runner.wait()
    episode = export(args.results, args.geometry, args.output, args.mode, invocation, runner_exit,
                     args.build_record, getattr(args, "player", None))
    if invocation.get("f1_8"):
        episode["f1_8"] = invocation["f1_8"]
        (args.output / "episode.json").write_text(json.dumps(episode, indent=1) + "\n")
    print(json.dumps({k: episode[k] for k in ("stage", "outcome", "completed_laps", "contact_free_and_on_track")}
                     | {"progress_m": episode["score"]["progress_m"], "min_clearance_m": episode["score"]["min_clearance_m"]}))
    return 0 if runner_exit in (None, 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
