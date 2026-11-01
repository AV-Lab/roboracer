#!/usr/bin/env python3
"""RoboRacer single entrypoint (S5-03, D71): live episodes, recorded-input replay, export and comparison.

It wraps the qualified tools and changes none of their defaults:

live     One stage episode on the AutoDRIVE player with its export (``roboracer_episode.py live``). With ``--fixture``
         (stage s4) the virtual-obstacle fixture is used, and with ``--judge t1|t2|t3`` the live-check judge is applied.
         Motion stages are refused unless the approval record lists them (the runner and supervisor interlock).
replay   Open-loop recorded-input replay of one run through the plugin's own code, exact equality
         (``roboracer_inputs.py replay``), or the analytical replay fixtures (``--fixtures``). Never a lap.
export   Re-export a finished runner results directory into an episode export (``roboracer_episode.py recorded``).
compare  An A/B or run-to-run table over groups of episode exports: ``--group LABEL=DIR[,DIR...]`` (repeatable).

Defaults are the qualified paths (player patch 04, its build record, the reviewed UI reference, the C0 geometry);
``--context`` selects the environment (e.g. a fresh S5 environment's run-context.json). ``--dry-run`` prints the
commands instead of running them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
ARTIFACTS = Path("/home/a2rl/Workspace/roboracer/artifacts")
DEFAULTS = {
    "context": Path.home() / "roboracer-work/run-context.json",
    "player": Path.home() / "roboracer-work/autodrive-builds/20261007T-sim1-04/AutoDRIVE.x86_64/AutoDRIVE.x86_64",
    "build_record": ARTIFACTS / "simulator-build/20261007T-sim1-04/build/build-result.json",
    "ui_reference": ARTIFACTS / "s2/20261009T062247Z-m2-batch1/ui-reference.json",
    "geometry": ARTIFACTS / "s1/20261006T051902Z-s1-05/c0-geometry.json",
}
FIXTURES = {"t1": "t1-left-pass", "t2": "t2-right-pass", "t3": "t3-blocked"}


def live_commands(args) -> list[list[str]]:
    python = json.loads(Path(args.context).read_text())["avlite_python"]
    episode = [python, "-B", str(SCRIPTS / "roboracer_episode.py"), "live", "--stage", args.stage,
               "--duration", str(args.duration), "--context", str(args.context), "--player", str(args.player),
               "--build-record", str(args.build_record), "--ui-reference", str(args.ui_reference),
               "--geometry", str(args.geometry), "--results", str(args.results), "--output", str(args.output)]
    if args.fixture:
        fixture = Path(args.fixture)
        if not fixture.suffix:
            fixture = REPO / "scripts/s4-fixtures" / f"{FIXTURES.get(args.fixture, args.fixture)}.json"
        episode += ["--obstacle-fixture", str(fixture.resolve())]
    for flag in ("f1_case", "f4_case", "s4_rearm", "m3_ic"):
        value = getattr(args, flag)
        if value is not None:
            episode += ["--" + flag.replace("_", "-"), str(value)]
    commands = [episode]
    if args.judge:
        commands.append([python, "-B", str(SCRIPTS / "roboracer_s4_judge.py"), "--episode", str(args.output),
                         "--results", str(args.results), "--case", args.judge,
                         "--output", str(Path(str(args.output)).with_name(Path(str(args.output)).name + "-judge.json"))])
    return commands


def replay_commands(args) -> list[list[str]]:
    python = json.loads(Path(args.context).read_text())["avlite_python"]
    tool = [python, "-B", str(SCRIPTS / "roboracer_inputs.py")]
    if args.fixtures:
        return [tool + ["fixtures", "--plugin", str(REPO / "roboracer"), "--output", str(args.output)]]
    return [tool + ["replay", "--run", str(args.run), "--plugin", str(REPO / "roboracer"), "--output", str(args.output)]]


def export_commands(args) -> list[list[str]]:
    python = json.loads(Path(args.context).read_text())["avlite_python"]
    return [[python, "-B", str(SCRIPTS / "roboracer_episode.py"), "recorded", "--results", str(args.results),
             "--geometry", str(args.geometry), "--output", str(args.output)]]


def summarize(directory: Path) -> dict:
    episode = json.loads((directory / "episode.json").read_text())
    score = episode["score"]
    laps = [lap["lap_time_s"] for lap in score.get("laps") or []]
    return {"export": str(directory), "stage": episode.get("stage"), "outcome": episode["outcome"],
            "completed_laps": episode["completed_laps"], "lap_s": laps[0] if laps else None,
            "contact_free_and_on_track": episode["contact_free_and_on_track"],
            "min_wall_clearance_m": score.get("min_clearance_m"),
            "min_obstacle_clearance_m": score.get("min_obstacle_clearance_m"),
            "s4_blocked": bool(episode.get("s4_blocked"))}


def compare(groups: list[str]) -> dict:
    out = {"schema": "roboracer.compare/1", "groups": {}}
    for spec in groups:
        label, _, dirs = spec.partition("=")
        rows = [summarize(Path(d)) for d in dirs.split(",") if d]
        laps = [r["lap_s"] for r in rows if r["lap_s"] is not None]
        walls = [r["min_wall_clearance_m"] for r in rows if r["min_wall_clearance_m"] is not None]
        obstacles = [r["min_obstacle_clearance_m"] for r in rows if r["min_obstacle_clearance_m"] is not None]
        out["groups"][label] = {
            "episodes": len(rows), "contact_free": sum(r["contact_free_and_on_track"] for r in rows),
            "laps": sum(r["completed_laps"] >= 1 for r in rows), "blocked": sum(r["s4_blocked"] for r in rows),
            "lap_s": [min(laps), max(laps)] if laps else None,
            "min_wall_clearance_m": min(walls) if walls else None,
            "min_obstacle_clearance_m": min(obstacles) if obstacles else None, "episodes_detail": rows}
    return out


def table(result: dict) -> str:
    lines = ["| group | episodes | contact-free | laps | blocked | lap (s) | min wall (m) | min obstacle (m) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for label, g in result["groups"].items():
        lap = "–" if not g["lap_s"] else f"{g['lap_s'][0]:.2f}–{g['lap_s'][1]:.2f}"
        wall = "–" if g["min_wall_clearance_m"] is None else f"{g['min_wall_clearance_m']:.3f}"
        obst = "–" if g["min_obstacle_clearance_m"] is None else f"{g['min_obstacle_clearance_m']:.3f}"
        lines.append(f"| {label} | {g['episodes']} | {g['contact_free']} | {g['laps']} | {g['blocked']} | {lap} | {wall} | {obst} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--context", type=Path, default=DEFAULTS["context"])
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    live = sub.add_parser("live")
    live.add_argument("--stage", required=True)
    live.add_argument("--duration", type=float, default=235.0)
    live.add_argument("--results", type=Path, required=True)
    live.add_argument("--output", type=Path, required=True)
    live.add_argument("--fixture", help="t1 | t2 | t3 | a fixture file (stage s4)")
    live.add_argument("--judge", choices=("t1", "t2", "t3"))
    for flag in ("--f1-case", "--f4-case", "--s4-rearm"):
        live.add_argument(flag)
    live.add_argument("--m3-ic", type=int)
    for name in ("player", "build_record", "ui_reference", "geometry"):
        live.add_argument("--" + name.replace("_", "-"), type=Path, default=DEFAULTS[name])
    replay = sub.add_parser("replay")
    replay.add_argument("--run", type=Path)
    replay.add_argument("--fixtures", action="store_true")
    replay.add_argument("--output", type=Path, required=True)
    export = sub.add_parser("export")
    export.add_argument("--results", type=Path, required=True)
    export.add_argument("--geometry", type=Path, default=DEFAULTS["geometry"])
    export.add_argument("--output", type=Path, required=True)
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("--group", action="append", required=True, help="LABEL=DIR[,DIR...] of episode exports")
    cmp_.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "replay" and not (args.fixtures or args.run):
        parser.error("replay needs --run or --fixtures")
    if args.command == "compare":
        result = compare(args.group)
        if args.output.exists():
            parser.error("--output must be fresh")
        args.output.write_text(json.dumps(result, indent=1) + "\n")
        args.output.with_suffix(".md").write_text(table(result) + "\n")
        print(table(result))
        return 0
    commands = {"live": live_commands, "replay": replay_commands, "export": export_commands}[args.command](args)
    for command in commands:
        print("+", " ".join(command), flush=True)
        if not args.dry_run:
            code = subprocess.run(command).returncode
            if code:
                return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
