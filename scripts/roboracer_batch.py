#!/usr/bin/env python3
"""Unattended S2 batch: one invocation runs repeated AutoDRIVE episodes and recovers or fails cleanly
(S2-01/02; proposal v0.1 sections 2-3, D20 A, D21 A, D22).

A batch is a sequence of *sessions*. Each session is one runner invocation (autodrive_neutral.py run
--guard batch) with a fresh player that runs the remaining episodes, GUI Reset between them, with
the automated pre-Connect and readiness checks; nobody reviews anything during the batch. Recovery:

1. inside a session, a scene reset (GUI Reset) starts every next episode;
2. if a session fails (initialization failure, a hung or exited player, any runner error), the next
   session starts a fresh player for the remaining episodes;
3. if that session fails too without completing an episode, the batch ends.

The batch also ends at its wall-time cap. Every attempted episode is counted, including a failed
initialization (plan: an episode starts when its runner begins recorded initialization), and every
recovery action is listed in the result. Each driving episode is scored independently
(roboracer_scoring, per simulator episode); "healthy" means: the stage finished on distance with
no abort, at least one complete lap, no contact and no off-track.

Usage (motion needs its own run approval, D22):
  roboracer_batch.py --stage m6 --episodes 3 --output FRESH_DIR --context ... --player ... \\
      --build-record ... --geometry ... --ui-reference ... [--record-inputs]
  roboracer_batch.py --stage stationary --episodes 3 ...   (interlocked player, HoldController)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SCHEMA = "roboracer.batch/1"


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def runner_command(args, results: Path, episodes: int, first: bool) -> list[str]:
    command = [sys.executable, "-B", str(args.runner), "run", "--context", str(args.context),
               "--player", str(args.player), "--results", str(results), "--profile", "p0-creep", "--provenance",
               "--guard", "batch", "--episodes", str(episodes), "--ui-reference", str(args.ui_reference),
               "--reply-delay", "0.05", "--runs", "1", "--duration", str(args.duration),
               "--guard-timeout", str(int(episodes * (args.duration + 60) + 60))]
    if args.stage == "m6":
        command += ["--motion-stage", "m6", "--build-record", str(args.build_record)]
    else:
        command += ["--plugin-stack"]
    if args.record_inputs:
        command += ["--record-inputs"]
    if args.f2_case and first:
        command += ["--f2-case", args.f2_case]  # injected in the batch's first episode (D23)
    if args.sim_hang_first_session and first:
        command += ["--sim-hang-test", str(args.sim_hang_first_session)]  # recovery test (stationary only)
    return command


def all_reviews_automated(status: dict) -> bool:
    """True when the initial Connect and every post-reset reconnect used the automated D21 check."""
    resets = [a for a in status.get("guard_actions", []) if a.get("kind") == "gui-reset"]
    initial = (status.get("manual_mode_review") or {}).get("automated")
    return bool(initial) and all((a.get("review") or {}).get("automated") for a in resets if a.get("review"))


def session_episodes(args, run: Path) -> list[dict]:
    """Episodes this session completed, with an outcome each."""
    status = read(run / "run.json")
    # A failed run has no bridge_at_end; the Devkit bridge rewrites bridge-status.json every frame, so its
    # last copy holds the guard phases up to the failure.
    guard = (status.get("bridge_at_end") or read(run / "bridge-status.json")).get("guard") or {}
    phases = {p["phase"]: p for p in guard.get("phases", [])}
    if args.stage == "m6":
        import roboracer_scoring as rs
        geometry = read(args.geometry)
        out = []
        for entry in read(run / "stage-episodes.json").get("episodes", []):
            item = {"number": entry["number"], "sim_episode": entry["episode"], "finish_reason": entry["finish_reason"],
                    "abort": entry["abort"], "path_m": entry["path_m"]}
            try:
                scored = rs.score(geometry, rs.truth_frames(run, entry["episode"]))
                item["score"] = {k: scored[k] for k in ("laps", "progress_m", "min_clearance_m", "start_offset_m")}
                item["score"]["contact_events"] = len(scored["contact_events"])
                item["score"]["offtrack_events"] = len(scored["offtrack_events"])
                healthy = (entry["finish_reason"] == "distance" and entry["abort"] is None and len(scored["laps"]) >= 1
                           and not scored["contact_events"] and not scored["offtrack_events"])
            except Exception as exc:  # an unscorable episode is not healthy
                item["score_error"] = f"{type(exc).__name__}: {exc}"
                healthy = False
            phase = phases.get(f"episode {entry['number']}")
            item["guard_phase_passed"] = phase.get("passed") if phase else None
            item["outcome"] = "healthy" if healthy and item["guard_phase_passed"] else "failed"
            out.append(item)
        return out
    out = []
    for number in range(1, args.episodes + 1):
        phase = phases.get(f"episode {number}")
        if phase is None or phase.get("last_frame") is None:
            break
        out.append({"number": number, "guard_phase_passed": phase["passed"],
                    "outcome": "healthy" if phase["passed"] else "failed"})
    return out


def run_batch(args) -> dict:
    out = args.output
    out.mkdir()
    started = time.monotonic()
    batch = {"schema": SCHEMA, "started_utc": utc_now(), "stage": args.stage, "target_episodes": args.episodes,
             "wall_cap_s": args.wall_cap_s, "invocation": sys.argv, "sessions": [], "episodes": [],
             "recovery_actions": [], "end_reason": None}

    def save():
        (out / "batch.json").write_text(json.dumps(batch, indent=1) + "\n")

    failed_streak = 0
    while len(batch["episodes"]) < args.episodes:
        if time.monotonic() - started > args.wall_cap_s:
            batch["end_reason"] = "wall-time cap"
            break
        index = len(batch["sessions"]) + 1
        remaining = args.episodes - len(batch["episodes"])
        results = out / f"session-{index:02d}"
        command = runner_command(args, results, remaining, first=index == 1)
        session = {"session": index, "results": str(results), "episodes_requested": remaining,
                   "started_utc": utc_now(), "command": command}
        batch["sessions"].append(session)
        save()
        with (out / f"session-{index:02d}-console.log").open("w") as log:
            session["exit_code"] = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                                  timeout=args.wall_cap_s + 900).returncode
        run = results / "run-01"
        status = read(run / "run.json")
        session.update(completed_utc=utc_now(), error=status.get("error"),
                       wall_s=status.get("wall_seconds"), startup_to_observation_s=status.get("startup_to_observation_seconds"),
                       ui_checks=[(c["label"], c["passed"]) for c in status.get("ui_checks", [])],
                       all_reviews_automated=all_reviews_automated(status),
                       simulator_hang=status.get("simulator_hang"))
        completed = session_episodes(args, run)
        for item in completed:
            if args.f2_case and index == 1 and item["number"] == 1:
                item["f2_case"] = args.f2_case  # judged by roboracer_f2.py, not as a lap
            batch["episodes"].append(dict(item, index=len(batch["episodes"]) + 1, session=index))
        ended_short = len(completed) < remaining
        if (session["exit_code"] != 0 or ended_short) and len(batch["episodes"]) < args.episodes:
            # The episode in progress (or being initialized) when the session failed counts as attempted.
            # (Also with exit 0: F2-6 Devkit loss ends a session cleanly before its episodes are done.)
            entry = {"index": len(batch["episodes"]) + 1, "session": index, "number": len(completed) + 1,
                     "outcome": "failed", "failure": status.get("error") or
                     (f"runner exit {session['exit_code']}" if session["exit_code"] else "session ended early")}
            if args.f2_case and index == 1 and entry["number"] == 1:
                entry["f2_case"] = args.f2_case
            batch["episodes"].append(entry)
            failed_streak = failed_streak + 1 if not completed else 1
            if failed_streak >= 2:
                batch["end_reason"] = "restart failed: two sessions in a row ended without completing an episode"
                save()
                break
            if len(batch["episodes"]) < args.episodes:
                batch["recovery_actions"].append({"after_session": index, "action": "fresh player (recovery step 2)",
                                                  "reason": entry["failure"]})
        else:
            failed_streak = 0
        save()
    batch["end_reason"] = batch["end_reason"] or "all episodes attempted"
    outcomes = [e["outcome"] == "healthy" for e in batch["episodes"]]
    streak = best = 0
    for ok in outcomes:
        streak = streak + 1 if ok else 0
        best = max(best, streak)
    batch.update(completed_utc=utc_now(), wall_s=time.monotonic() - started, attempted=len(outcomes),
                 healthy=sum(outcomes), longest_healthy_streak=best,
                 # Unattended: every Connect (initial and after each reset) used the automated D21 check.
                 unattended=all(s.get("all_reviews_automated") for s in batch["sessions"]),
                 passed=len(outcomes) == args.episodes and all(outcomes))
    save()
    return batch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=("m6", "stationary"), required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True, help="fresh batch directory")
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--player", type=Path, required=True)
    parser.add_argument("--ui-reference", type=Path, required=True)
    parser.add_argument("--build-record", type=Path)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--duration", type=float, default=None,
                        help="per-episode cap, s (default: 235 for m6, 15 for stationary)")
    parser.add_argument("--wall-cap-s", type=float, default=1800.0, help="batch wall-time cap (proposal: 30 min)")
    parser.add_argument("--record-inputs", action="store_true")
    parser.add_argument("--f2-case", default=None, help="S2 F2 fault case for the first episode (stage m6, D23)")
    parser.add_argument("--sim-hang-first-session", type=float, default=None,
                        help="stationary recovery test: SIGSTOP the first session's player this many s in")
    parser.add_argument("--runner", type=Path, default=HERE / "autodrive_neutral.py", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.f2_case and args.stage != "m6":
        parser.error("--f2-case needs --stage m6")
    if args.sim_hang_first_session is not None and args.stage != "stationary":
        parser.error("--sim-hang-first-session is a stationary test")
    args.duration = args.duration or (235.0 if args.stage == "m6" else 15.0)
    if args.episodes < 1:
        parser.error("--episodes must be at least 1")
    if args.stage == "m6" and not (args.build_record and args.geometry):
        parser.error("--stage m6 needs --build-record and --geometry")
    batch = run_batch(args)
    print(json.dumps({k: batch[k] for k in ("attempted", "healthy", "longest_healthy_streak", "end_reason", "passed")}))
    return 0 if batch["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
