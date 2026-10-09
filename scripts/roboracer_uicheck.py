#!/usr/bin/env python3
"""Automated pre-Connect check of the AutoDRIVE player window (S2, D21 A).

Replaces the per-Connect human screenshot review in S2 batches. Only the near-white text pixels
(min RGB channel >= 170) of five safe-state regions of the 1280x720 window are compared with a
reference screenshot that a person reviewed once (`roboracer.ui-reference/1`):

- connection state ("Disconnected"),
- mode ("Guarded"),
- HUD driving mode, gear and speed,
- HUD throttle and steering,
- HUD encoder ticks.

The 3D view, simulation time, frame rate and lap timer are not compared: the semi-transparent HUD
shows the moving 3D view underneath, so raw pixels are not stable (S2 entry evidence). Measured on
10 safe screenshots: 0 mismatching text pixels per region; a Connected screen differs by 942 px and
a Manual-mode screen by 810 + 214 px. A region passes with at most `MAX_MISMATCH_PX` mismatches.

The check is necessary, not sufficient: after Connect and before any arm, the runner also checks
telemetry readiness (new episode, guard disarmed, spawn pose, wheels still).

Usage:
  roboracer_uicheck.py reference --image PNG --note TEXT --output FRESH.json   (records the one-time review)
  roboracer_uicheck.py check --reference REF.json --image PNG
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "roboracer.ui-reference/1"
TEXT_MIN = 170
MAX_MISMATCH_PX = 8
SIZE = (1280, 720)
REGIONS = {
    "connection state (Disconnected)": (0, 245, 256, 300),
    "mode (Guarded)": (0, 312, 256, 368),
    "HUD driving mode, gear, speed": (1040, 115, 1280, 160),
    "HUD throttle, steering": (1040, 172, 1280, 202),
    "HUD encoder ticks": (1040, 212, 1280, 230),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _text_masks(path: Path):
    import numpy as np
    from PIL import Image
    image = Image.open(path).convert("RGB")
    if image.size != SIZE:
        raise ValueError(f"{path}: window image is {image.size}, expected {SIZE}")
    pixels = np.asarray(image, dtype=np.int16)
    return {name: pixels[y0:y1, x0:x1].min(axis=2) >= TEXT_MIN for name, (x0, y0, x1, y1) in REGIONS.items()}


def make_reference(image: Path, note: str, reviewer: str) -> dict:
    masks = _text_masks(image)
    return {"schema": SCHEMA, "image": str(Path(image).resolve()), "image_sha256": sha256(image),
            "regions": {k: list(v) for k, v in REGIONS.items()},
            "text_pixels": {k: int(m.sum()) for k, m in masks.items()},
            "text_min": TEXT_MIN, "max_mismatch_px": MAX_MISMATCH_PX,
            "review": {"reviewer": reviewer, "note": note,
                       "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}}


def load_reference(path: Path) -> dict:
    ref = json.loads(Path(path).read_text())
    if ref.get("schema") != SCHEMA:
        raise ValueError(f"{path} is not a {SCHEMA} record")
    if sha256(ref["image"]) != ref["image_sha256"]:
        raise ValueError("reference image changed since its review")
    if {k: tuple(v) for k, v in ref["regions"].items()} != REGIONS or ref["text_min"] != TEXT_MIN:
        raise ValueError("reference was recorded with different regions or threshold")
    return ref


def check(image: Path, reference: dict) -> dict:
    """Per-region mismatching text pixels between `image` and the reviewed reference."""
    got, want = _text_masks(image), _text_masks(reference["image"])
    mismatch = {name: int((got[name] != want[name]).sum()) for name in REGIONS}
    return {"image": str(image), "image_sha256": sha256(image), "reference_sha256": reference["image_sha256"],
            "mismatch_px": mismatch, "max_mismatch_px": reference["max_mismatch_px"],
            "passed": all(v <= reference["max_mismatch_px"] for v in mismatch.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("reference")
    r.add_argument("--image", type=Path, required=True)
    r.add_argument("--note", required=True, help="what the reviewer saw")
    r.add_argument("--reviewer", required=True)
    r.add_argument("--output", type=Path, required=True)
    c = sub.add_parser("check")
    c.add_argument("--reference", type=Path, required=True)
    c.add_argument("--image", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "reference":
        with args.output.open("x") as f:
            json.dump(make_reference(args.image, args.note, args.reviewer), f, indent=1)
        print(json.dumps({"output": str(args.output)}))
        return 0
    result = check(args.image, load_reference(args.reference))
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
