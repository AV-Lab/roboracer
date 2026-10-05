#!/usr/bin/env python3
"""Create a fresh derived copy of the qualified AutoDRIVE authoring project for an incremental build.

Registers a new detached worktree of the pinned source, mirrors the base project's working
tree and Library cache into it (never .git, Temp or Logs), and verifies that its tracked diff
and status equal the base. The base is only read. This is not a clean-import qualification.
No Editor, player, account operation or control command is launched.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

COMMIT = "635dbb6d86ec98e25ea845a97188f7bbe85a09e8"
QUALIFIED_DIFF_SHA256 = "4965e4fa2c538fed2c3609a9544ec9bbfc112a628ca5f1cccf31bb9ed1bc13a7"


def git(project, *args):
    return subprocess.check_output(["git", "-C", str(project), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="Qualified authoring project (read only)")
    parser.add_argument("--derived", type=Path, required=True, help="Fresh path for the new worktree")
    parser.add_argument("--record", type=Path, required=True, help="Fresh JSON record path")
    args = parser.parse_args()
    base, derived = args.base.resolve(), args.derived.resolve()
    if derived.exists() or args.record.exists():
        parser.error("Derived project and record must be fresh paths")
    if git(base, "rev-parse", "HEAD").decode().strip() != COMMIT:
        parser.error("Base is not at the pinned source commit")
    if (base / "Temp/UnityLockfile").exists():
        parser.error("Base project is open in an Editor")
    base_diff = git(base, "diff", "HEAD")
    if hashlib.sha256(base_diff).hexdigest() != QUALIFIED_DIFF_SHA256:
        parser.error("Base tracked diff is not the qualified baseline")
    base_status = git(base, "status", "--porcelain")
    source = Path(git(base, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()).parent
    start = time.monotonic()
    git(source, "worktree", "add", "--no-checkout", "--detach", str(derived), COMMIT)
    subprocess.run(["rsync", "-a", "--exclude=/.git", "--exclude=/Temp", "--exclude=/Logs",
                    str(base) + "/", str(derived) + "/"], check=True)
    git(derived, "reset", "--quiet")  # index from HEAD; the mirrored working tree is untouched
    derived_diff = git(derived, "diff", "HEAD")
    record = {
        "base_project": str(base), "cache_source": str(base / "Library"), "derived": str(derived),
        "source_repository": str(source), "commit": COMMIT, "created_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.monotonic() - start, "independent_copy": True, "clean_import_claim": False,
        "tracked_diff_equal": derived_diff == base_diff,
        "status_equal": git(derived, "status", "--porcelain") == base_status,
        "tracked_diff_sha256": hashlib.sha256(derived_diff).hexdigest()}
    args.record.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
    return 0 if record["tracked_diff_equal"] and record["status_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
