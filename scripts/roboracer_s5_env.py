#!/usr/bin/env python3
"""S5-01 (D70 A): reproducible plugin/Devkit environments from recorded locks.

Subcommands:

lock        Export the qualified environments into ``release/``: exact pip locks of the AVLite and Devkit venvs
            (``pip freeze --all``; AVLite itself is installed from its pinned source tarball, not from the index), the
            Devkit and attrdict patches, and ``release/pins.json`` (AVLite commit and tarball sha256, Devkit commit and
            package path, patched-file sha256s, the colcon command, the simulator identity list, Python version).
wheelhouse  The one network step: ``pip download --no-deps`` of every locked package from PyPI into a local wheelhouse,
            then hashed requirement files (``release/*-requirements.lock``) with each file's sha256.
build       A fresh environment under a new directory, offline only: venvs from ``/usr/bin/python3.10``; packages with
            ``--no-index --find-links <wheelhouse> --require-hashes``; AVLite from its tarball; the Devkit package from its
            pinned checkout plus the recorded patches, built with colcon against ``/opt/ros/humble``; the attrdict overlay
            from the locked wheel plus its patch. Every expected sha256 is checked; a run-context for the fresh
            environment is written.
verify      The fresh environment's package sets equal the locks; imports work (AVLite, the plugin, rclpy and the Devkit
            bridge module through the overlay); the simulator's 604-file identity is unchanged.

The simulator is not rebuilt or redistributed: it is the separately provided patch-04 player, verified by hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

REPO = Path(__file__).resolve().parents[1]
RELEASE = REPO / "release"
WORK = Path.home() / "roboracer-work"
QUALIFIED = {
    "avlite_python": WORK / "preflight-20260928T113745Z/avlite-venv/bin/python",
    "devkit_python": WORK / "preflight-20260928T120809Z/devkit-venv/bin/python",
    "avlite_tarball": WORK / "preflight-20260928T113745Z/avlite-source.tar",
    "devkit_checkout": WORK / "preflight-20260928T113745Z/devkit-0.3.0",
    "devkit_build_copy": WORK / "preflight-20260928T124339Z/devkit-src/autodrive_f1tenth",
    "compat": WORK / "preflight-20260928T124339Z/compat",
    "player_identity": Path("/home/a2rl/Workspace/roboracer/artifacts/sim1-06/20261008T070835Z/player-files.sha256"),
    "player_dir": WORK / "autodrive-builds/20261007T-sim1-04/AutoDRIVE.x86_64",
}
PRE = Path("/home/a2rl/Workspace/roboracer/artifacts/preflight")
DEVKIT_PACKAGE = "ADSS Toolkit/autodrive_ros2/autodrive_f1tenth"
BRIDGE_FILE = "autodrive_f1tenth/autodrive_incoming_bridge.py"
PATCHES = {"devkit": ["devkit-loopback.patch", "devkit-tf-lifecycle.patch"], "attrdict": ["attrdict-python310.patch"]}
LOCKS = {"avlite": "avlite", "devkit": "devkit"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(argv, **kw):
    print("+", " ".join(map(str, argv)), flush=True)
    kw.setdefault("env", clean_env())  # never inherit a sourced ROS PYTHONPATH into pip
    return subprocess.run([str(a) for a in argv], check=True, **kw)


def clean_env() -> dict:
    """No PYTHONPATH: a sourced ROS 2 setup would otherwise make pip list /opt/ros packages as if they were in the venv."""
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}


def norm(text: str) -> str:
    """PEP 503-style name normalization, applied to versions and file names as well."""
    import re
    return re.sub(r"[-_.]+", "_", text.lower())


def freeze(python: Path) -> list[str]:
    out = subprocess.run([str(python), "-m", "pip", "freeze", "--all"], check=True, capture_output=True, text=True,
                         env=clean_env()).stdout
    return sorted(line for line in out.splitlines() if line.strip())


# -- lock ---------------------------------------------------------------------------------------------------------

def cmd_lock(args):
    RELEASE.mkdir(exist_ok=True)
    (RELEASE / "patches").mkdir(exist_ok=True)
    setup = json.loads((PRE / "20260928T113745Z/avlite-environment-setup.json").read_text())
    avlite_commit = next(c[-1] for c in setup["commands"] if c[:1] == ["git"] and "archive" in c)
    source_lock = json.loads((PRE / "20260928T113745Z/official-source-lock.json").read_text())
    context = json.loads((WORK / "run-context.json").read_text())
    for env in LOCKS:
        lines = [l for l in freeze(QUALIFIED[f"{env}_python"]) if not l.startswith("avlite @ ")]
        (RELEASE / f"{env}-freeze.txt").write_text("\n".join(lines) + "\n")
    for group, names in PATCHES.items():
        for name in names:
            shutil.copyfile(PRE / "20260928T124339Z" / name, RELEASE / "patches" / name)
    colcon = json.loads((PRE / "20260928T124339Z/devkit-colcon-build.json").read_text())["argv"]
    pins = {
        "schema": "roboracer.release-pins/1", "python": "3.10.12 (/usr/bin/python3.10)", "ros": "/opt/ros/humble",
        "avlite": {"commit": avlite_commit, "tarball": str(QUALIFIED["avlite_tarball"]),
                   "tarball_sha256": sha256(QUALIFIED["avlite_tarball"]),
                   "version": subprocess.run([str(QUALIFIED["avlite_python"]), "-m", "pip", "show", "avlite"],
                                             capture_output=True, text=True).stdout.split("Version: ")[1].split()[0]},
        "devkit": {"commit": source_lock["checkouts"]["devkit-0.3.0"]["commit"], "checkout": str(QUALIFIED["devkit_checkout"]),
                   "package": DEVKIT_PACKAGE, "patches": {n: sha256(RELEASE / "patches" / n) for n in PATCHES["devkit"]},
                   "patched_file": BRIDGE_FILE,
                   "patched_file_sha256": sha256(QUALIFIED["devkit_build_copy"] / BRIDGE_FILE),
                   "colcon_argv_recorded": colcon,
                   # The Devkit's outgoing bridge writes install/share/autodrive_f1tenth/api_config.ini at runtime; PRE
                   # left it zeroed, and the runner refuses to start unless both commands are zero. Not a build product.
                   "api_config_ini": (QUALIFIED["devkit_build_copy"].parents[1] / "install/share/autodrive_f1tenth/"
                                      "api_config.ini").read_text(),
                   "api_config_ini_sha256": sha256(QUALIFIED["devkit_build_copy"].parents[1] /
                                                   "install/share/autodrive_f1tenth/api_config.ini")},
        "attrdict_overlay": {"package": "attrdict==2.0.1", "patch": PATCHES["attrdict"][0],
                             "patch_sha256": sha256(RELEASE / "patches" / PATCHES["attrdict"][0]),
                             "files": {f: sha256(QUALIFIED["compat"] / "attrdict" / f)
                                       for f in sorted(os.listdir(QUALIFIED["compat"] / "attrdict")) if f.endswith(".py")},
                             "recorded_patch": context["attrdict_patch"]},
        "simulator": {"identity_list": str(QUALIFIED["player_identity"]), "identity_list_sha256": sha256(QUALIFIED["player_identity"]),
                      "files": sum(1 for _ in QUALIFIED["player_identity"].read_text().splitlines()),
                      "note": "separately provided patch-04 player (D18); verified, not rebuilt or redistributed"},
        "a2rl_port": {"source": "AV-Lab/a2rl dev 0b5cfa8 (S3); fe2fc01 checked unchanged for the ported files (S4)"},
        "freeze_counts": {env: len((RELEASE / f"{env}-freeze.txt").read_text().splitlines()) for env in LOCKS}}
    (RELEASE / "pins.json").write_text(json.dumps(pins, indent=1) + "\n")
    print(json.dumps({k: pins[k] for k in ("avlite", "freeze_counts")}, indent=1))


# -- wheelhouse ---------------------------------------------------------------------------------------------------

def cmd_wheelhouse(args):
    house = Path(args.wheelhouse)
    house.mkdir(parents=True, exist_ok=True)
    for env in LOCKS if not args.hash_only else ():
        python = QUALIFIED[f"{env}_python"]
        run([python, "-m", "pip", "--isolated", "--disable-pip-version-check", "download", "--no-deps", "--no-cache-dir",
             "--index-url", "https://pypi.org/simple", "--dest", house, "-r", RELEASE / f"{env}-freeze.txt"])
    # Source-only packages are built into wheels once, here (build tools may come from PyPI), so that the offline
    # rebuild never builds anything; the lock then lists both the archive's and the wheel's hash.
    for archive in sorted(house.glob("*.tar.gz")):
        stem = norm(archive.name[:-len(".tar.gz")])
        if not any(norm(w.name).startswith(stem + "_") for w in house.glob("*.whl")):
            run([QUALIFIED["avlite_python"], "-m", "pip", "--isolated", "--disable-pip-version-check", "wheel", "--no-deps",
                 "--no-cache-dir", "--index-url", "https://pypi.org/simple", "--wheel-dir", house, archive], env=clean_env())
    # AVLite itself: a wheel built once from the pinned tarball (its build needs setuptools>=61, newer than the locked
    # runtime setuptools); the offline rebuild installs this wheel by hash.
    pins = json.loads((RELEASE / "pins.json").read_text())
    if not any(w.name.startswith(f"avlite-{pins['avlite']['version']}-") for w in house.glob("*.whl")):
        tarball = Path(pins["avlite"]["tarball"])
        if sha256(tarball) != pins["avlite"]["tarball_sha256"]:
            raise SystemExit("AVLite tarball does not match pins.json")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(tarball) as t:
                t.extractall(tmp)
            run([QUALIFIED["avlite_python"], "-m", "pip", "--isolated", "--disable-pip-version-check", "wheel", "--no-deps",
                 "--no-cache-dir", "--index-url", "https://pypi.org/simple", "--wheel-dir", house, tmp])
    files = {p.name: sha256(p) for p in sorted(house.iterdir()) if p.is_file() and p.name != "SHA256SUMS"}
    wheel = next(n for n in files if n.startswith(f"avlite-{pins['avlite']['version']}-"))
    (RELEASE / "avlite-package.lock").write_text(
        f"avlite=={pins['avlite']['version']} \\\n    --hash=sha256:{files[wheel]}\n")
    (house / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n, h in files.items()))
    for env in LOCKS:
        out = []
        for line in (RELEASE / f"{env}-freeze.txt").read_text().splitlines():
            name, version = line.split("==")
            prefix = f"{norm(name)}_{norm(version)}_"  # the name and version, then a separator (pydantic != pydantic_core)
            matches = [f for f in files if norm(f).startswith(prefix)]
            if not matches:
                raise SystemExit(f"no downloaded file for {line}")
            out.append(line + "".join(f" \\\n    --hash=sha256:{files[m]}" for m in matches))
        (RELEASE / f"{env}-requirements.lock").write_text("\n".join(out) + "\n")
    print(json.dumps({"files": len(files), "wheelhouse": str(house)}))


# -- build --------------------------------------------------------------------------------------------------------

def apply_patch(target: Path, patch: Path):
    run(["patch", "--forward", "--batch", str(target), str(patch)])


def cmd_build(args):
    out = Path(args.output)
    if out.exists():
        raise SystemExit("--output must be fresh")
    house = Path(args.wheelhouse)
    pins = json.loads((RELEASE / "pins.json").read_text())
    out.mkdir(parents=True)
    record = {"schema": "roboracer.fresh-environment/1", "output": str(out), "wheelhouse": str(house), "checks": {}}
    pip = ["-m", "pip", "--isolated", "--disable-pip-version-check", "install", "--no-index", "--no-cache-dir",
           "--find-links", str(house)]
    for env in LOCKS:
        venv = out / f"{env}-venv"
        run(["/usr/bin/python3.10", "-m", "venv", venv])
        run([venv / "bin/python", *pip, "--require-hashes", "-r", RELEASE / f"{env}-requirements.lock"])
    # AVLite from its pinned tarball (offline; its dependencies are already installed from the lock).
    record["checks"]["avlite tarball sha256 (source of the wheel)"] = (
        sha256(Path(pins["avlite"]["tarball"])) == pins["avlite"]["tarball_sha256"])
    run([out / "avlite-venv/bin/python", *pip, "--no-deps", "--require-hashes", "-r", RELEASE / "avlite-package.lock"])
    # Devkit package: pinned checkout + recorded patches, then colcon against /opt/ros/humble.
    checkout = Path(pins["devkit"]["checkout"])
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    record["checks"]["devkit checkout at the pinned commit"] = head == pins["devkit"]["commit"]
    record["checks"]["devkit checkout clean"] = not subprocess.run(
        ["git", "-C", str(checkout), "status", "--short"], capture_output=True, text=True).stdout.strip()
    src = out / "devkit-src/autodrive_f1tenth"
    shutil.copytree(checkout / pins["devkit"]["package"], src)
    for name in PATCHES["devkit"]:
        apply_patch(src / BRIDGE_FILE, RELEASE / "patches" / name)
    record["checks"]["devkit patched file sha256"] = sha256(src / BRIDGE_FILE) == pins["devkit"]["patched_file_sha256"]
    colcon = (f"source /opt/ros/humble/setup.bash && colcon --log-base {out}/colcon-log build --base-paths {src} "
              f"--build-base {out}/build --install-base {out}/install --merge-install --packages-select autodrive_f1tenth "
              f"--event-handlers console_direct+ desktop_notification-")
    run(["bash", "-c", colcon], env=dict(clean_env(), PATH=f"{out}/devkit-venv/bin:" + os.environ["PATH"]))
    api = out / "install/share/autodrive_f1tenth/api_config.ini"
    api.write_text(pins["devkit"]["api_config_ini"])
    record["checks"]["devkit api_config.ini zeroed, sha256 as qualified"] = sha256(api) == pins["devkit"]["api_config_ini_sha256"]
    # attrdict overlay: the locked wheel's package files + the recorded Python 3.10 patch.
    wheel = next(p for p in house.iterdir() if p.name.lower().startswith("attrdict-2.0.1"))
    overlay = out / "compat"
    with zipfile.ZipFile(wheel) as z:
        for member in z.namelist():
            if member.startswith("attrdict/") and member.endswith(".py"):
                target = overlay / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(member))
    run(["patch", "--forward", "--batch", "-d", str(overlay / "attrdict"), "-p1", "-i",
         str(RELEASE / "patches" / PATCHES["attrdict"][0])])
    files = {f: sha256(overlay / "attrdict" / f) for f in pins["attrdict_overlay"]["files"]}
    record["checks"]["attrdict overlay sha256 (every file)"] = files == pins["attrdict_overlay"]["files"]
    # Scratch directories and a run-context for the fresh environment (same layout as the qualified one).
    environment = {}
    for name in ("avlite-config", "plugins", "data", "xdg-config", "xdg-data", "xdg-cache", "matplotlib", "pip-cache", "ros-log"):
        (out / name).mkdir()
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", AVLITE_CONFIG_DIR=str(out / "avlite-config"),
                       AVLITE_PLUGINS_DIR=str(out / "plugins"), AVLITE_DATA_DIR=str(out / "data"),
                       XDG_CONFIG_HOME=str(out / "xdg-config"), XDG_DATA_HOME=str(out / "xdg-data"),
                       XDG_CACHE_HOME=str(out / "xdg-cache"), MPLCONFIGDIR=str(out / "matplotlib"),
                       PIP_CACHE_DIR=str(out / "pip-cache"), ROS_LOG_DIR=str(out / "ros-log"), AVLITE_ROS_DISTRO="humble")
    context = {"run_id": out.name, "scratch": str(out), "environment": environment,
               "avlite_python": str(out / "avlite-venv/bin/python"), "devkit_python": str(out / "devkit-venv/bin/python"),
               "devkit_source": str(src), "compat_overlay": str(overlay), "attrdict_patch": pins["attrdict_overlay"]["recorded_patch"],
               "built_by": "scripts/roboracer_s5_env.py build (D70 A)", "pins_sha256": sha256(RELEASE / "pins.json")}
    (out / "run-context.json").write_text(json.dumps(context, indent=1) + "\n")
    record["passed"] = all(record["checks"].values())
    (out / "build-record.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record, indent=1))
    return 0 if record["passed"] else 1


# -- verify -------------------------------------------------------------------------------------------------------

def cmd_verify(args):
    out = Path(args.output)
    context = json.loads((out / "run-context.json").read_text())
    pins = json.loads((RELEASE / "pins.json").read_text())
    checks = {}
    for env in LOCKS:
        got = [l for l in freeze(Path(context[f"{env}_python"])) if not l.startswith(("avlite @ ", "avlite=="))]  # avlite: own check
        want = (RELEASE / f"{env}-freeze.txt").read_text().splitlines()
        checks[f"{env} packages equal the lock ({len(want)})"] = got == want
    avlite_version = subprocess.run([context["avlite_python"], "-m", "pip", "show", "avlite"], capture_output=True,
                                    text=True).stdout
    checks["avlite version as pinned"] = f"Version: {pins['avlite']['version']}" in avlite_version
    env = dict(os.environ, **context["environment"])
    probe = ("import avlite, numpy, scipy, shapely; from avlite.c60_apps.c62_factory import executor_factory; "
             "import sys; sys.path.insert(0, %r); import roboracer; print(sorted(roboracer.__all__))" % str(REPO))
    r = subprocess.run([context["avlite_python"], "-c", probe], env=env, capture_output=True, text=True)
    checks["avlite + plugin import"] = r.returncode == 0 and "C0LatticePlanner" in r.stdout
    devkit = ("source /opt/ros/humble/setup.bash && PYTHONPATH=%s:%s/install/lib/python3.10/site-packages:$PYTHONPATH "
              "%s -c 'import rclpy, attrdict, socketio, gevent; from autodrive_f1tenth import autodrive_incoming_bridge; "
              "print(\"ok\")'" % (context["compat_overlay"], out, context["devkit_python"]))
    r2 = subprocess.run(["bash", "-c", devkit], env=env, capture_output=True, text=True)
    checks["devkit bridge import (rclpy, overlay, colcon install)"] = r2.returncode == 0 and r2.stdout.strip().endswith("ok")
    import configparser
    api = configparser.ConfigParser()
    api.read(out / "install/share/autodrive_f1tenth/api_config.ini")
    checks["devkit api_config.ini present with zero commands (runner pre-launch check)"] = (
        api.has_section("f1tenth_1") and all(api.getfloat("f1tenth_1", k) == 0 for k in ("throttle_command", "steering_command")))
    r3 = subprocess.run(["sha256sum", "-c", "--quiet", pins["simulator"]["identity_list"]], cwd=QUALIFIED["player_dir"],
                        capture_output=True, text=True)
    checks[f"simulator identity ({pins['simulator']['files']} files)"] = r3.returncode == 0
    report = {"schema": "roboracer.fresh-environment-verify/1", "output": str(out), "checks": checks,
              "passed": all(checks.values()), "stderr": {"plugin": r.stderr[-800:], "devkit": r2.stderr[-800:]}}
    (out / "verify-record.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("checks", "passed")}, indent=1))
    return 0 if report["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lock")
    w = sub.add_parser("wheelhouse")
    w.add_argument("--wheelhouse", default=str(WORK / "s5-wheelhouse"))
    w.add_argument("--hash-only", action="store_true", help="only (re)write the hashed locks from the downloaded files")
    b = sub.add_parser("build")
    b.add_argument("--wheelhouse", default=str(WORK / "s5-wheelhouse"))
    b.add_argument("--output", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--output", required=True)
    args = parser.parse_args()
    return {"lock": cmd_lock, "wheelhouse": cmd_wheelhouse, "build": cmd_build, "verify": cmd_verify}[args.cmd](args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
