#!/usr/bin/env python3
"""Build the pinned, separate AutoDRIVE SIM0 player and retain bounded evidence.

This tool does not launch the player, activate a license, or issue controls.
Run on the authorized build host; Unity may access its normal user license/cache.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time
from datetime import datetime, timezone


COMMIT = "635dbb6d86ec98e25ea845a97188f7bbe85a09e8"
VERSION = "2021.3.9f1"
CHANGESET = "ad3870b89536"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def git(project, *args):
    return subprocess.check_output(
        ["git", "-C", str(project), *args], text=True
    ).strip()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def process_sample(pid):
    """Record only resource counters, never command lines or environment secrets."""
    try:
        status = Path(f"/proc/{pid}/status").read_text()
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return None
    memory = {}
    for line in status.splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmHWM", "Threads"}:
            memory[key] = value.strip()
    return {
        "monotonic_ns": time.monotonic_ns(),
        "pid": pid,
        "user_cpu_seconds": int(stat[11]) / os.sysconf("SC_CLK_TCK"),
        "system_cpu_seconds": int(stat[12]) / os.sysconf("SC_CLK_TCK"),
        **memory,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--kinematics-probe", action="store_true",
                        help="Stage the approved opt-in motion/contact diagnostic in a fresh derived project")
    parser.add_argument("--pose-trace", action="store_true",
                        help="Add approved opt-in statement markers to the exact pinned controller; requires kinematics")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--import-only", action="store_true")
    operation.add_argument("--audit-scene", action="store_true",
                           help="Inspect F1TENTH dependencies with a temporary Editor-only probe")
    operation.add_argument("--recover-tracks", type=Path,
                           help="Generate approved native tracks from the fingerprinted input manifest")
    operation.add_argument("--verify-native-tracks", type=Path,
                           help="Reload and verify native tracks and their F1TENTH scene instances")
    operation.add_argument("--probe-track-packing", type=Path,
                           help="Build isolated mesh bundles to diagnose vertex packing; never change the scene")
    parser.add_argument("--native-library-dir", type=Path, action="append", default=[],
                        help="Prepend a qualified private native-library directory for this Editor process")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    editor, project = args.editor.resolve(), args.project.resolve()
    output, results = args.output.resolve(), args.results.resolve()
    library_dirs = [path.resolve() for path in args.native_library_dir]
    if any(not path.is_dir() for path in library_dirs):
        parser.error("A private native-library directory does not exist")
    track_inputs = args.recover_tracks or args.verify_native_tracks or args.probe_track_packing
    if track_inputs and not track_inputs.is_file():
        parser.error("Native track input manifest does not exist")
    needs_player = not (args.import_only or args.audit_scene or track_inputs)
    diagnostic_source = Path(__file__).resolve().parents[1] / "integration/autodrive/diagnostics/KinematicsProbe.cs"
    diagnostic_dir = project / "Assets/RoboRacerQualification/Diagnostics"
    if args.kinematics_probe and (not needs_player or not diagnostic_source.is_file() or
            not diagnostic_dir.parent.is_dir() or diagnostic_dir.exists() or diagnostic_dir.with_suffix(".meta").exists()):
        parser.error("Kinematics build requires a prepared derived project with a fresh Diagnostics destination")
    pose_original = pose_patched = None
    if args.pose_trace:
        if not args.kinematics_probe:
            parser.error("Pose tracing requires the explicit kinematics build")
        from autodrive_pose import patch_controller
        pose_original = (project / "Assets/Scripts/VehicleController.cs").read_bytes()
        pose_patched = patch_controller(pose_original)
    if results.exists() or (needs_player and output.exists()):
        parser.error("Use fresh results/output paths; previous evidence is never overwritten")
    if not editor.is_file() or not os.access(editor, os.X_OK):
        parser.error("Editor is missing or not executable")
    if git(project, "rev-parse", "HEAD") != COMMIT:
        parser.error("Unexpected source commit")
    version = (project / "ProjectSettings/ProjectVersion.txt").read_text()
    if f"m_EditorVersionWithRevision: {VERSION} ({CHANGESET})" not in version:
        parser.error("Unexpected project engine version")
    build_settings = (project / "ProjectSettings/EditorBuildSettings.asset").read_text()
    scenes = re.findall(r"- enabled: 1\s+path: ([^\r\n]+)", build_settings)
    if scenes != ["Assets/Scenes/F1TENTH.unity"]:
        parser.error("Expected only the pinned F1TENTH scene enabled")
    settings = (project / "ProjectSettings/ProjectSettings.asset").read_text()
    if not re.search(r"scriptingBackend:\s+Standalone: 1\b", settings):
        parser.error("Expected IL2CPP standalone backend")
    if (project / "Temp/UnityLockfile").exists():
        parser.error("Project lock exists; verify ownership before opening another Editor")
    results.mkdir(parents=True)
    if needs_player:
        output.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Received signal {signum}; clean up the owned Editor")

    signal.signal(signal.SIGTERM, interrupted)
    argv = [str(editor), "-batchmode", "-quit", "-nographics",
            "-projectPath", str(project), "-buildTarget", "linux64",
            "-logFile", str(results / "editor.log")]
    player = output / "AutoDRIVE.x86_64"
    if needs_player:
        argv += ["-buildLinux64Player", str(player)]
    use_probe = args.audit_scene or bool(track_inputs)
    probe_name = "NativeTrackRecovery" if track_inputs else "SceneDependencyAudit"
    audit_source = Path(__file__).resolve().with_name(probe_name + ".cs")
    audit_file = project / ("Assets/Editor/RoboRacer" + probe_name + ".cs")
    audit_parent_created = False
    if use_probe:
        if not audit_source.is_file() or audit_file.exists() or audit_file.with_suffix(".cs.meta").exists():
            parser.error("Missing audit probe or destination already exists")
    if args.audit_scene:
        argv += ["-executeMethod", "RoboRacer.Qualification.SceneDependencyAudit.Run",
                 "-roboracerSceneAudit", str(results / "scene-audit.json")]
    if track_inputs:
        argv += ["-executeMethod", "RoboRacer.Qualification.NativeTrackRecovery.Run",
                 "-roboracerTrackInputs", str(track_inputs.resolve()),
                 "-roboracerTrackReport", str(results / "native-track-report.json"),
                 "-roboracerTrackMode", "generate" if args.recover_tracks else
                 "packing-probe" if args.probe_track_packing else "verify"]
    record = {
        "stage": "SIM0", "operation": "recover-tracks" if args.recover_tracks else
            "verify-native-tracks" if args.verify_native_tracks else
            "probe-track-packing" if args.probe_track_packing else
            "audit" if args.audit_scene else "import" if args.import_only else "build",
        "source_commit": COMMIT, "project": str(project), "editor": str(editor),
        "editor_sha256": digest(editor), "expected_version": VERSION,
        "expected_changeset": CHANGESET, "argv": argv,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": args.timeout, "motion_authorized": False,
        "library_existed_at_start": (project / "Library").exists(),
        "status_before": git(project, "status", "--porcelain"),
        "license_handling": "Use user-managed entitlement; no activation or credentials in CLI",
        "logs": "Private raw editor/console logs may contain licensing metadata; do not publish them without review",
        "private_native_libraries": {
            str(directory): {path.name: digest(path) for path in sorted(directory.glob("*.so*")) if path.is_file()}
            for directory in library_dirs
        },
    }
    environment = os.environ.copy()
    if library_dirs:
        paths = [str(path) for path in library_dirs]
        if environment.get("LD_LIBRARY_PATH"):
            paths.append(environment["LD_LIBRARY_PATH"])
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(paths)
    record["editor_ld_library_path"] = environment.get("LD_LIBRARY_PATH", "")
    if track_inputs:
        record["track_inputs_sha256"] = digest(track_inputs)
    (results / "source-before.patch").write_text(git(project, "diff", "HEAD") + "\n")
    selected = ["Packages/manifest.json", "Packages/packages-lock.json",
                "ProjectSettings/ProjectSettings.asset", "ProjectSettings/TimeManager.asset",
                "ProjectSettings/EditorBuildSettings.asset", "Assets/Scenes/F1TENTH.unity"]
    record["input_sha256"] = {name: digest(project / name) for name in selected}
    write_json(results / "build-result.json", record)
    child = None
    start = time.monotonic()
    try:
        if args.kinematics_probe:
            diagnostic_dir.mkdir()
            diagnostic_dir.with_suffix(".meta").write_text(
                "fileFormatVersion: 2\nguid: 4ed2940e85cd41a989026cba210e253d\nfolderAsset: yes\n"
                "DefaultImporter:\n  externalObjects: {}\n  userData:\n  assetBundleName:\n  assetBundleVariant:\n")
            sources = [diagnostic_source.parent / name for name in
                       ("KinematicsProbe.cs", "ContactProbe.cs", "ContactRelay.cs", "PoseTrace.cs")]
            for origin in [p for source in sources for p in (source, source.with_suffix(".cs.meta"))]:
                target = diagnostic_dir / origin.name
                target.write_bytes(origin.read_bytes())
                (results / ("executed-" + origin.name)).write_bytes(origin.read_bytes())
            record["kinematics_probe"] = {
                "activation": "-roboracerKinematics <fresh absolute output directory>",
                "optional_contacts": "-roboracerContacts control|treatment; treatment additionally waits for a PID/time-bound window request",
                "default_enabled": False, "source": str(diagnostic_source),
                "staged_sha256": {str(p.relative_to(project)): digest(p) for p in
                    [diagnostic_dir.with_suffix(".meta"), *sorted(diagnostic_dir.iterdir())]},
                "retained_in_derived_project": True, "diagnostic_only": True}
            write_json(results / "build-result.json", record)
        if args.pose_trace:
            import difflib
            controller_path = project / "Assets/Scripts/VehicleController.cs"
            if controller_path.read_bytes() != pose_original:
                raise RuntimeError("Controller changed since pose patch validation")
            (results / "controller-before.cs").write_bytes(pose_original)
            (results / "controller-instrumented.cs").write_bytes(pose_patched)
            (results / "controller-pose.patch").write_text("".join(difflib.unified_diff(
                pose_original.decode().splitlines(keepends=True), pose_patched.decode().splitlines(keepends=True),
                fromfile="original/VehicleController.cs", tofile="instrumented/VehicleController.cs")))
            controller_path.write_bytes(pose_patched)
            record["pose_trace"] = {"default_enabled":False,"activation":"-roboracerPoseTrace with Floor control",
                "original_sha256":hashlib.sha256(pose_original).hexdigest(),
                "instrumented_sha256":hashlib.sha256(pose_patched).hexdigest(),"original_statements_preserved":True}
            write_json(results / "build-result.json", record)
        if use_probe:
            audit_parent_created = not audit_file.parent.exists()
            audit_file.parent.mkdir(exist_ok=True)
            audit_file.write_bytes(audit_source.read_bytes())
            record["temporary_editor_probe_sha256"] = digest(audit_source)
            (results / "executed-probe.cs").write_bytes(audit_source.read_bytes())
        with (results / "console.log").open("w") as log, (results / "resources.jsonl").open("w") as metrics:
            child = subprocess.Popen(argv, cwd=project, stdout=log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=True,
                                     env=environment)
            record["pid"] = child.pid
            write_json(results / "build-result.json", record)
            while child.poll() is None:
                if time.monotonic() - start > args.timeout:
                    raise TimeoutError("Editor exceeded the bounded execution window")
                sample = process_sample(child.pid)
                if sample:
                    metrics.write(json.dumps(sample) + "\n")
                    metrics.flush()
                time.sleep(1)
            record["exit_code"] = child.returncode
    except BaseException as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        if child is not None:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                record["termination"] = "SIGTERM owned editor group"
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    record["termination"] = "SIGKILL after bounded SIGTERM wait"
            record.update(exit_code=child.returncode, editor_reaped=True)
        record["wall_seconds"] = time.monotonic() - start
        record["completed_utc"] = datetime.now(timezone.utc).isoformat()
        if use_probe:
            audit_file.unlink(missing_ok=True)
            audit_file.with_suffix(".cs.meta").unlink(missing_ok=True)
            if audit_parent_created and not any(audit_file.parent.iterdir()):
                audit_file.parent.rmdir()
                audit_file.parent.with_suffix(".meta").unlink(missing_ok=True)
            record["temporary_editor_probe_removed"] = not audit_file.exists()
        record["status_after"] = git(project, "status", "--porcelain")
        (results / "source-after.patch").write_text(git(project, "diff", "HEAD") + "\n")
        if needs_player:
            record["output_files"] = {
                str(p.relative_to(output)): {"bytes": p.stat().st_size, "sha256": digest(p)}
                for p in sorted(output.rglob("*")) if p.is_file()
            }
            record["player_exists"] = player.is_file()
        record["acceptance"] = "Pending diagnostic review and required neutral runs; exit code alone is not acceptance"
        write_json(results / "build-result.json", record)
        print(json.dumps({k: record[k] for k in ["operation", "exit_code", "wall_seconds", "acceptance"] if k in record}))
    output_ok = (results / "scene-audit.json").is_file() if args.audit_scene else not needs_player or player.is_file()
    if track_inputs:
        track_report = results / "native-track-report.json"
        output_ok = track_report.is_file() and json.loads(track_report.read_text()).get("passed") is True
    return 0 if record.get("exit_code") == 0 and output_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
