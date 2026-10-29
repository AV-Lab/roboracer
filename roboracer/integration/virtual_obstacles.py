"""Virtual static obstacles at the sensor boundary (S4, D54 A).

The frozen AutoDRIVE player (D18) has no obstacle objects and no API to place any (PRE-B09). A fixture
therefore adds static obstacles where a simulated sensor would see them: each committed snapshot's
LiDAR beams are ray-cast against the fixture's world-frame polygons from the LiDAR origin at that
snapshot's simulator pose, and every beam that hits an obstacle before its published return is
shortened to the hit.

This is part of the simulated world, not of the driving stack: the stack receives only the modified
scan. It never sees the polygons, and the simulator pose used here is the same truth the bridge
already withholds from ICP stages. The independent scorer reads the same fixture to score footprint
overlap; that overlap is the "contact", because the car would drive through a virtual box.

Error: the scan and the IPS pose of one snapshot are up to 0.06 s apart (``MAX_SCAN_POSE_SKEW_S``),
measured about 0.04 s, i.e. about 0.02 m of obstacle displacement at 0.5 m/s.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .autodrive_observation import (LIDAR_MOUNT_M, SCAN_ANGLE_MIN_RAD, SCAN_BEAMS, SCAN_INCREMENT_RAD,
                                    SCAN_RANGE_MAX_M, Snapshot, scan_points)

SCHEMA = "roboracer.virtual-obstacles/1"
BEAM_ANGLES_RAD = SCAN_ANGLE_MIN_RAD + SCAN_INCREMENT_RAD * np.arange(SCAN_BEAMS)


@dataclass(frozen=True)
class ObstacleFixture:
    name: str
    sha256: str
    polygons: tuple[np.ndarray, ...]  # each (K, 2) world-frame vertices, K >= 3, not closed

    @property
    def edges(self) -> tuple[np.ndarray, np.ndarray]:
        """Segment start points and vectors of every polygon edge, (E, 2) each."""
        starts = np.concatenate([p for p in self.polygons])
        ends = np.concatenate([np.roll(p, -1, axis=0) for p in self.polygons])
        return starts, ends - starts


def provenance_path(fixture_file: Path) -> Path:
    fixture_file = Path(fixture_file)
    return fixture_file.with_name(fixture_file.stem + ".provenance.json")


def load_fixture(fixture_file: Path, provenance_file: Path | None = None) -> ObstacleFixture:
    """A fixture whose sha256 matches its provenance record; refuses anything else."""
    raw = Path(fixture_file).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    record = json.loads(Path(provenance_file or provenance_path(fixture_file)).read_text())
    if record.get("fixture_sha256") != digest:
        raise ValueError(f"{Path(fixture_file).name} does not match its provenance record")
    data = json.loads(raw)
    if data.get("schema") != SCHEMA:
        raise ValueError(f"obstacle fixture schema must be {SCHEMA}")
    polygons = []
    for obstacle in data.get("obstacles", []):
        vertices = np.asarray(obstacle["polygon"], dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3 or not np.isfinite(vertices).all():
            raise ValueError(f"obstacle {obstacle.get('id')!r} needs at least 3 finite (x, y) vertices")
        if np.allclose(vertices[0], vertices[-1]):
            vertices = vertices[:-1]
        area = 0.5 * float(np.sum(vertices[:, 0] * np.roll(vertices[:, 1], -1) - np.roll(vertices[:, 0], -1) * vertices[:, 1]))
        if abs(area) < 1e-4:
            raise ValueError(f"obstacle {obstacle.get('id')!r} has no area")
        vertices.setflags(write=False)
        polygons.append(vertices)
    if not polygons:
        raise ValueError("obstacle fixture holds no obstacles")
    return ObstacleFixture(name=str(data.get("name", Path(fixture_file).stem)), sha256=digest, polygons=tuple(polygons))


def lidar_origin(x: float, y: float, yaw: float) -> tuple[float, float]:
    """LiDAR origin in the world for a rear-axle-centre pose (the IPS reference point)."""
    c, s = math.cos(yaw), math.sin(yaw)
    return x + c * LIDAR_MOUNT_M[0] - s * LIDAR_MOUNT_M[1], y + s * LIDAR_MOUNT_M[0] + c * LIDAR_MOUNT_M[1]


def first_hits(fixture: ObstacleFixture, origin_xy, beam_yaw: np.ndarray) -> np.ndarray:
    """Distance along each beam to its first obstacle edge; inf where none is hit."""
    starts, vectors = fixture.edges
    d = np.stack([np.cos(beam_yaw), np.sin(beam_yaw)], axis=1)  # (B, 2)
    w = starts - np.asarray(origin_xy, dtype=float)  # (E, 2)
    denom = d[:, None, 0] * vectors[None, :, 1] - d[:, None, 1] * vectors[None, :, 0]  # cross(d, e), (B, E)
    cross_we = w[None, :, 0] * vectors[None, :, 1] - w[None, :, 1] * vectors[None, :, 0]  # cross(w, e), (1, E)
    cross_wd = w[None, :, 0] * d[:, None, 1] - w[None, :, 1] * d[:, None, 0]  # cross(w, d), (B, E)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = cross_we / denom
        u = cross_wd / denom
    hit = (np.abs(denom) > 1e-12) & (t > 0.0) & (u >= 0.0) & (u <= 1.0)
    return np.where(hit, t, np.inf).min(axis=1)


def occlude_ranges(fixture: ObstacleFixture, ranges: np.ndarray, x: float, y: float, yaw: float) -> np.ndarray:
    """Published ranges with every beam cut at its first obstacle hit within the LiDAR's maximum range."""
    hits = first_hits(fixture, lidar_origin(x, y, yaw), yaw + BEAM_ANGLES_RAD)
    ranges = np.asarray(ranges, dtype=np.float64)
    cut = (hits <= SCAN_RANGE_MAX_M) & ~(ranges <= hits)  # also replaces no-return (inf / beyond max) beams
    out = ranges.copy()
    out[cut] = hits[cut]
    return out


def apply_fixture(fixture: ObstacleFixture, snapshot: Snapshot) -> tuple[Snapshot, int]:
    """The snapshot as the LiDAR would have published it with the obstacles present, and the beams changed."""
    pose = snapshot.pose
    new = occlude_ranges(fixture, snapshot.scan_ranges, pose.x, pose.y, pose.yaw)
    changed = int(np.count_nonzero(new != np.asarray(snapshot.scan_ranges, dtype=np.float64)))
    if not changed:
        return snapshot, 0
    published = new.astype(np.float32)
    published.setflags(write=False)
    points = scan_points(published)
    points.setflags(write=False)
    return replace(snapshot, lidar=replace(snapshot.lidar, points=points), scan_ranges=published), changed
