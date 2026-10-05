#!/usr/bin/env python3
"""Prepare a fresh SIM0 worktree with the explicitly approved asset exclusions.

Uses locally acquired Git objects only. Preserves the source worktree and archives
each excluded asset and metadata file outside Unity before removing its copy.
No Editor, player, account operation, or control command is launched here.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess


COMMIT = "635dbb6d86ec98e25ea845a97188f7bbe85a09e8"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args])


def inventory_dependencies(source, report):
    """Snapshot source assets and resolved package files, including their metadata."""
    rows = {}
    for name in report["dependencies"]:
        parts = PurePosixPath(name).parts
        base = source / name
        if not base.is_file() and parts[0] == "Packages":
            candidates = list((source / "Library/PackageCache").glob(parts[1] + "@*"))
            if len(candidates) != 1:
                raise ValueError(f"Ambiguous or missing resolved package for {name}")
            base = candidates[0].joinpath(*parts[2:])
        if base.is_file():
            rows[name] = {"bytes": base.stat().st_size, "sha256": digest(base)}
            meta = Path(str(base) + ".meta")
            if meta.is_file():
                rows[name + ".meta"] = {"bytes": meta.stat().st_size, "sha256": digest(meta)}
        elif name.startswith("Resources/"):
            rows[name] = {"builtin": True}
        else:
            raise ValueError(f"Unresolved dependency: {name}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--dependency-report", type=Path, required=True)
    parser.add_argument("--native-track-recovery", action="store_true",
                        help="Apply the separately approved OpenCAV quarantine and disabled scene-entry removal")
    args = parser.parse_args()
    source, project, quarantine, results = [p.resolve() for p in
        (args.source, args.project, args.quarantine, args.results)]
    manifest = Path(__file__).resolve().parent.parent / "integration/autodrive/sim0-exclusions.json"
    patch = manifest.with_name("linux-host-toolchain.patch")
    proposal = json.loads(manifest.read_text())
    report = json.loads(args.dependency_report.read_text())
    if git(source, "rev-parse", "HEAD").decode().strip() != COMMIT or proposal["source_commit"] != COMMIT:
        parser.error("Unexpected source commit")
    if digest(args.dependency_report) != proposal["dependency_report_sha256"]:
        parser.error("Dependency report does not match the approved review")
    if any(p.exists() for p in (project, quarantine, results)):
        parser.error("Project, quarantine and results must be fresh paths")
    for a in (source, project, quarantine, results):
        for b in (source, project, quarantine, results):
            if a != b and a in b.parents:
                parser.error("Source, project, quarantine and results must be separate trees")
    if len({source, project, quarantine, results}) != 4:
        parser.error("Use four distinct paths")
    files = [f for c in proposal["candidates"] for f in c["files"]]
    if len(proposal["candidates"]) != 6 or len(files) != 12:
        parser.error("Unexpected approved exclusion scope")
    recovery_path = manifest.with_name("linux-track-recovery.json")
    recovery = json.loads(recovery_path.read_text()) if args.native_track_recovery else None
    if recovery:
        if recovery["source_commit"] != COMMIT or len(recovery["additional_exclusions"]) != 4:
            parser.error("Unexpected native-track approval scope")
        files += recovery["additional_exclusions"]
        if digest(source / "Assets/Scenes/F1TENTH.unity") != recovery["original_scene_sha256"]:
            parser.error("F1TENTH scene differs from recovery baseline")
        if digest(source / "ProjectSettings/EditorBuildSettings.asset") != recovery["original_build_settings_sha256"]:
            parser.error("Build settings differ from recovery baseline")
    for item in files:
        name = PurePosixPath(item["path"])
        if name.is_absolute() or ".." in name.parts or name.parts[0] != "Assets":
            parser.error("Invalid exclusion path")
        if str(name).removesuffix(".meta") in report["dependencies"]:
            parser.error("Cannot exclude a required scene dependency")
        path = source / name
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            parser.error(f"Original asset differs from approval: {name}")
    required = inventory_dependencies(source, report)
    os.umask(0o077)
    results.mkdir(parents=True)
    before = git(source, "diff", "HEAD")
    before_status = git(source, "status", "--porcelain")
    (results / "original-source.patch").write_bytes(before)
    (results / "required-dependencies.before.json").write_text(json.dumps(required, indent=2) + "\n")
    record = {"started_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source), "project": str(project), "quarantine": str(quarantine),
        "source_commit": COMMIT, "approval": proposal["approval"],
        "manifest_sha256": digest(manifest), "package_patch_sha256": digest(patch),
        "dependency_report_sha256": digest(args.dependency_report),
        "dependency_count": len(report["dependencies"]), "excluded_files": []}
    if recovery:
        record["native_track_recovery"] = {"approval": recovery["approval"],
            "manifest_sha256": digest(recovery_path), "geometry_status": "not generated"}
    try:
        subprocess.run(["git", "-C", str(source), "worktree", "add", "--detach", str(project), COMMIT],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (project / "Library").exists() or git(project, "status", "--porcelain").strip():
            raise ValueError("New worktree is not clean")
        subprocess.run(["git", "-C", str(project), "apply", "--check", str(patch)], check=True)
        subprocess.run(["git", "-C", str(project), "apply", str(patch)], check=True)
        for item in files:
            path, backup = project / item["path"], quarantine / item["path"]
            if digest(path) != item["sha256"]:
                raise ValueError("New worktree file does not match approved hash")
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            if digest(backup) != item["sha256"]:
                raise ValueError("Quarantine copy failed hash verification")
            path.unlink()
            record["excluded_files"].append(item)
        if recovery:
            settings = project / "ProjectSettings/EditorBuildSettings.asset"
            text = settings.read_text()
            entry = recovery["disabled_scene_entry"]
            if text.count(entry) != 1:
                raise ValueError("Expected exactly one disabled OpenCAV build entry")
            settings.write_text(text.replace(entry, "", 1))
            record["native_track_recovery"]["build_settings_sha256"] = digest(settings)
        for name, value in required.items():
            if name.startswith("Assets/") and digest(project / name) != value["sha256"]:
                raise ValueError(f"Required asset changed: {name}")
        record["original_preserved"] = (git(source, "diff", "HEAD") == before
            and git(source, "status", "--porcelain") == before_status
            and all(digest(source / f["path"]) == f["sha256"] for f in files))
        if not record["original_preserved"]:
            raise ValueError("Original worktree preservation check failed")
        record["status"] = "prepared_pending_clean_import"
        record["library_exists"] = (project / "Library").exists()
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        if project.exists():
            (results / "prepared-source.patch").write_bytes(git(project, "diff", "HEAD"))
            record["status_after"] = git(project, "status", "--porcelain").decode()
        (results / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("status", "original_preserved", "dependency_count", "library_exists")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
