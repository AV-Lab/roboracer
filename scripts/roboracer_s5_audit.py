#!/usr/bin/env python3
"""S5-05 (D75): audit of the evidence paths cited in the docs, and of the evidence manifests.

1. Every ``artifacts/...`` path cited in ``docs/**/*.md``, ``release/README.md`` and ``roboracer/README.md`` must exist
   under the workspace (the directory that holds ``artifacts/``).
2. Every evidence directory with a ``MANIFEST.sha256`` that is cited must still verify: every listed file present with
   its recorded sha256.
3. Open TODO/FIXME markers in ``roboracer/`` and ``scripts/``, and unchecked plan boxes in the development plan.

Offline, read-only; writes one JSON report. usage: roboracer_s5_audit.py --output <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent.parent.parent if (REPO.parent.name == "worktrees") else REPO
PATH_RE = re.compile(r"artifacts/[A-Za-z0-9_./-]+(\*)?")
# cited paths that are not evidence, with the reason (reported, not counted as missing)
NOT_EVIDENCE = {
    "artifacts/s1a/": "planned output of the inactive S1A amendment (never adopted, see its line 5)",
}


def placeholder(p: str) -> bool:
    return "..." in p or "REPLACE_WITH" in p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cited_paths(files):
    out = {}
    for f in files:
        for m in PATH_RE.finditer(f.read_text(errors="replace")):
            p = m.group(0) if m.group(1) else m.group(0).rstrip(".,;:)`")
            out.setdefault(p, set()).add(str(f.relative_to(REPO)))
    return out


def manifest_root(path: Path):
    for d in [path, *path.parents]:
        if (d / "MANIFEST.sha256").exists():
            return d
        if d == WORKSPACE / "artifacts":
            return None
    return None


def verify_manifest(root: Path) -> dict:
    bad, n = [], 0
    for line in (root / "MANIFEST.sha256").read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.lstrip("*").strip()
        n += 1
        f = root / name
        if not f.exists():
            bad.append({"file": name, "problem": "missing"})
        elif sha256(f) != digest:
            bad.append({"file": name, "problem": "sha256 differs"})
    return {"files": n, "problems": bad}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    docs = sorted((REPO / "docs").rglob("*.md")) + [REPO / "release/README.md", REPO / "roboracer/README.md"]
    cited = cited_paths(docs)
    missing, excluded, roots = [], [], {}
    for p, sources in sorted(cited.items()):
        if placeholder(p) or p in NOT_EVIDENCE:
            excluded.append({"path": p, "reason": NOT_EVIDENCE.get(p, "template placeholder"), "cited_in": sorted(sources)})
            continue
        matches = sorted(WORKSPACE.glob(p)) if p.endswith("*") else [WORKSPACE / p]
        if not matches or not all(m.exists() for m in matches):
            missing.append({"path": p, "cited_in": sorted(sources)})
            continue
        for full in matches:
            root = manifest_root(full)
            if root is not None:
                roots.setdefault(root, set()).update(sources)
    manifests = {}
    for root in sorted(roots):
        manifests[str(root.relative_to(WORKSPACE))] = verify_manifest(root)
    todo = []
    for d in ("roboracer", "scripts"):
        for f in (REPO / d).rglob("*.py"):
            if f.name == Path(__file__).name:
                continue
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if re.search(r"\b(TODO|FIXME|XXX)\b", line):
                    todo.append(f"{f.relative_to(REPO)}:{i}: {line.strip()[:120]}")
    plan = (REPO / "docs/planning/development-plan.md").read_text().splitlines()
    unchecked = [f"docs/planning/development-plan.md:{i}: {l.strip()[:100]}" for i, l in enumerate(plan, 1)
                 if l.lstrip().startswith("- [ ]")]
    report = {"schema": "roboracer.s5-audit/1", "workspace": str(WORKSPACE), "docs_scanned": len(docs),
              "cited_paths": len(cited), "missing_paths": missing, "excluded_not_evidence": excluded,
              "manifests_checked": len(manifests),
              "manifests_with_problems": {k: v for k, v in manifests.items() if v["problems"]},
              "manifest_files_verified": sum(v["files"] for v in manifests.values()),
              "todo_markers": todo, "unchecked_plan_boxes": unchecked}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in report.items()}, indent=1))
    return 0 if not missing and not report["manifests_with_problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
