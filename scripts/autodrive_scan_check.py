#!/usr/bin/env python3
"""Independent check of the AutoDRIVE LiDAR scan convention against scene geometry.

export   Read the built player's serialized colliders (UnityPy, read-only) and write the
         active, enabled collider triangles in the ROS world basis with their layers, plus
         the static sensor transforms, to a fresh .npz. Third-party geometry: keep the
         output in ignored evidence, never in Git.
compare  Ray-cast the vendor scan model from a recorded telemetry pose (IPS position,
         IMU yaw) against static layer-0 triangles (vehicle colliders excluded) and compare with that frame's measured ranges
         under competing hypotheses for beam order and LiDAR mount. Writes fresh JSON.

ROS world basis = (Unity z, -Unity x, Unity y); x forward/y left/z up for the vehicle.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

# Serialized F1TENTH LIDAR component (Assets/Scenes/F1TENTH.unity).
ANGLE_MIN_DEG, ANGLE_MAX_DEG, RESOLUTION_DEG = -135.0, 135.0, 0.25
RANGE_MIN_M, RANGE_MAX_M = 0.06, 10.0
SENSORS = ("F1TENTH/Sensors/LIDAR/Head", "F1TENTH/Sensors/IPS", "F1TENTH/Sensors/IMU",
           "F1TENTH/Transforms/Rear Axle Center", "F1TENTH/Transforms/Front Axle Center", "F1TENTH")


def ros_basis(points):
    points = np.asarray(points, dtype=float)
    return points[..., [2, 0, 1]] * np.array([1.0, -1.0, 1.0])


def export(args):
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    from scipy.spatial.transform import Rotation

    env = UnityPy.load(str(args.data / "level0"))
    objects = list(env.objects)
    rows = {}
    for obj in objects:
        if obj.type.name in ("GameObject", "Transform"):
            rows[obj.path_id] = (obj.type.name, obj.parse_as_dict())
    gos = {k: tree for k, (kind, tree) in rows.items() if kind == "GameObject"}
    transforms = {tree["m_GameObject"]["m_PathID"]: tree for kind, tree in rows.values() if kind == "Transform"}

    def parent(go):
        key = transforms[go]["m_Father"]["m_PathID"]
        return rows[key][1]["m_GameObject"]["m_PathID"] if key else None

    def world(go):
        row = transforms[go]
        m = np.eye(4)
        m[:3, :3] = Rotation.from_quat([row["m_LocalRotation"][k] for k in "xyzw"]).as_matrix() @ np.diag(
            [row["m_LocalScale"][k] for k in "xyz"])
        m[:3, 3] = [row["m_LocalPosition"][k] for k in "xyz"]
        up = parent(go)
        return world(up) @ m if up else m

    def path(go):
        up = parent(go)
        return (path(up) + "/" if up else "") + gos[go]["m_Name"]

    def active(go):
        up = parent(go)
        return bool(gos[go]["m_IsActive"]) and (active(up) if up else True)

    triangles, layers, owners, colliders = [], [], [], []
    for obj in objects:
        kind = obj.type.name
        if kind not in ("MeshCollider", "BoxCollider", "SphereCollider", "CapsuleCollider", "WheelCollider"):
            continue
        collider = obj.parse_as_object()
        go = collider.m_GameObject.m_PathID
        record = {"path": path(go), "type": kind, "layer": int(gos[go]["m_Layer"]),
                  "enabled": bool(collider.m_Enabled), "active": active(go)}
        colliders.append(record)
        if kind != "MeshCollider" or not (record["enabled"] and record["active"]):
            continue
        mesh = collider.m_Mesh.deref_parse_as_object()
        handler = MeshHandler(mesh)
        handler.process()
        vertices = np.asarray(handler.m_Vertices, dtype=float)
        indices = np.asarray(handler.m_IndexBuffer, dtype=np.int64).reshape(-1, 3)
        m = world(go)
        points = ros_basis(vertices @ m[:3, :3].T + m[:3, 3])
        triangles.append(points[indices])
        layers.append(np.full(len(indices), record["layer"]))
        owners.append(np.full(len(indices), len(colliders) - 1))
    by_path = {path(go): go for go in transforms}
    sensors = {name: world(by_path[name]).tolist() for name in SENSORS if name in by_path}
    np.savez_compressed(args.output, triangles=np.concatenate(triangles), layers=np.concatenate(layers),
                        owners=np.concatenate(owners))
    meta = {"data": str(args.data), "level0_sha256": hashlib.sha256((args.data / "level0").read_bytes()).hexdigest(),
            "colliders": colliders, "sensors_world_unity": sensors,
            "npz_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
    args.output.with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps({"triangles": int(sum(len(t) for t in triangles)),
                      "mesh_colliders": sum(c["type"] == "MeshCollider" for c in colliders),
                      "layer0_mesh_colliders": sorted({c["path"] for c in colliders
                                                       if c["type"] == "MeshCollider" and c["layer"] == 0
                                                       and c["enabled"] and c["active"]})}))


def raycast(origin, directions, triangles, max_range):
    """Nearest hit distance per direction (Möller–Trumbore); inf when nothing within max_range."""
    v0, e1, e2 = triangles[:, 0], triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    best = np.full(len(directions), np.inf)
    for start in range(0, len(triangles), 20000):
        a, b, c = v0[start:start + 20000], e1[start:start + 20000], e2[start:start + 20000]
        p = np.cross(directions[:, None, :], c[None])                 # (R, T, 3)
        det = np.einsum("rtk,tk->rt", p, b)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = origin - a                                                 # (T, 3)
        u = np.einsum("tk,rtk->rt", s, p) * inv
        q = np.cross(s, b)                                             # (T, 3)
        v = np.einsum("rk,tk->rt", directions, q) * inv
        t = np.einsum("tk,tk->t", c, q)[None] * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0) & (t <= max_range)
        best = np.minimum(best, np.where(hit, t, np.inf).min(axis=1))
    return best


def measured_ranges(frame):
    values = []
    for text in frame["V1 LIDAR Range Array"].split():
        values.append(math.inf if text == "inf" else float(text))
    return np.asarray(values)


def compare(args):
    data = np.load(args.geometry)
    meta = json.loads(args.geometry.with_suffix(".json").read_text())
    frame = json.loads(args.frame.read_text())
    # The vehicle's own colliders are serialized at the scene pose and enclose the LiDAR head; Unity's
    # Physics.Raycast never reports a collider its origin starts inside, so ray-cast static scenery only.
    vehicle = np.array([c["path"].startswith("F1TENTH/") for c in meta["colliders"]])
    keep = (data["layers"] == 0) & ~vehicle[data["owners"]]
    tri = data["triangles"][keep]
    sensors = {k: np.asarray(v) for k, v in meta["sensors_world_unity"].items()}
    ips = np.array([float(v) for v in frame["V1 Position"].split()])
    yaw = float(frame["V1 Orientation Euler Angles"].split()[2])
    measured = measured_ranges(frame)
    n = int(round((ANGLE_MAX_DEG - ANGLE_MIN_DEG) / RESOLUTION_DEG)) + 1
    if len(measured) != n:
        raise SystemExit(f"Expected {n} beams, measured {len(measured)}")
    # Static scene: mounts relative to the rear axle in the vehicle frame (heading from the scene root).
    root = sensors["F1TENTH"]
    heading = ros_basis(root[:3, :3] @ np.array([0.0, 0.0, 1.0]))
    scene_yaw = math.atan2(heading[1], heading[0])
    rear = ros_basis(sensors["F1TENTH/Transforms/Rear Axle Center"][:3, 3])
    head = ros_basis(sensors["F1TENTH/Sensors/LIDAR/Head"][:3, 3])
    rot = np.array([[math.cos(-scene_yaw), -math.sin(-scene_yaw)], [math.sin(-scene_yaw), math.cos(-scene_yaw)]])
    mount_xy = rot @ (head - rear)[:2]
    mount = np.array([mount_xy[0], mount_xy[1], head[2] - rear[2]])
    hypotheses = {
        "convention: ccw from -135 deg, mount from scene": (1.0, mount),
        "reversed beam order": (-1.0, mount),
        "lidar at rear axle (no mount)": (1.0, np.array([0.0, 0.0, mount[2]])),
        "mount mirrored (behind axle)": (1.0, np.array([-mount[0], mount[1], mount[2]])),
    }
    angles = np.deg2rad(ANGLE_MIN_DEG + RESOLUTION_DEG * np.arange(n))
    results = {}
    for name, (order, offset) in hypotheses.items():
        c, s = math.cos(yaw), math.sin(yaw)
        origin = ips + np.array([c * offset[0] - s * offset[1], s * offset[0] + c * offset[1], offset[2]])
        world_angles = yaw + order * angles
        directions = np.stack([np.cos(world_angles), np.sin(world_angles), np.zeros(n)], axis=1)
        predicted = raycast(origin, directions, tri, RANGE_MAX_M)
        predicted[predicted <= RANGE_MIN_M] = np.inf
        both = np.isfinite(predicted) & np.isfinite(measured)
        error = np.abs(predicted[both] - measured[both])
        results[name] = {
            "beams": n, "both_finite": int(both.sum()),
            "finite_mismatch": int((np.isfinite(predicted) != np.isfinite(measured)).sum()),
            "abs_error_m_p50_p95_max": [float(np.percentile(error, q)) for q in (50, 95, 100)] if both.any() else None,
            "within_5mm": int((error <= 0.005).sum())}
    best = min(results, key=lambda k: (results[k]["finite_mismatch"],
                                       results[k]["abs_error_m_p50_p95_max"][1] if results[k]["abs_error_m_p50_p95_max"] else 1e9))
    report = {"frame": str(args.frame), "geometry": str(args.geometry), "geometry_npz_sha256": meta["npz_sha256"],
              "ips_position": ips.tolist(), "imu_yaw_rad": yaw, "scene_yaw_rad": scene_yaw,
              "mount_from_scene_m": mount.tolist(), "layer0_static_triangles": int(len(tri)),
              "excluded_vehicle_triangles": int(((data["layers"] == 0) & vehicle[data["owners"]]).sum()),
              "hypotheses": results, "best": best,
              "convention_passes": best == "convention: ccw from -135 deg, mount from scene"}
    if args.output.exists():
        raise SystemExit("Output must be fresh")
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"best": best, "convention": results["convention: ccw from -135 deg, mount from scene"]}))
    return 0 if report["convention_passes"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    e = sub.add_parser("export")
    e.add_argument("--data", type=Path, required=True, help="Player AutoDRIVE_Data directory")
    e.add_argument("--output", type=Path, required=True, help="Fresh .npz path")
    c = sub.add_parser("compare")
    c.add_argument("--geometry", type=Path, required=True)
    c.add_argument("--frame", type=Path, required=True, help="Recorded first-raw-frame.json")
    c.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "export":
        if args.output.exists() or args.output.with_suffix(".json").exists():
            parser.error("Output must be fresh")
        return export(args)
    return compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
