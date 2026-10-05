#!/usr/bin/env python3
"""Read-only serialized player geometry inventory for SIM0 comparisons.

Uses the isolated UnityPy/NumPy/SciPy analysis environment. Never opens Unity,
saves assets, or claims runtime calibration/contact/scoring qualification.
"""

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time


def compare_geometry(reference, candidate):
    """Compare recorded geometry without mistaking build object IDs for coordinates.

    Extended inventories resolve material/texture metadata and camera targets.
    Shader binaries, texture pixels and untyped MonoBehaviour settings remain
    outside this comparison and require separate qualification.
    """
    def multiset(rows):
        return Counter(json.dumps(row, sort_keys=True, allow_nan=False) for row in rows)

    def transforms(report):
        return [dict(row, local={k: v for k, v in row["local"].items()
                                if k not in {"m_GameObject", "m_Father", "m_Children"}})
                for row in report["transforms"]]

    def physics(report):
        kinds = {"Rigidbody", "WheelCollider", "BoxCollider", "MeshCollider",
                 "SphereCollider", "CapsuleCollider", "Camera"}
        result, references = [], []
        for row in report["components"]:
            if row["type"] not in kinds:
                continue
            values = {}
            for key, value in row["tree"].items():
                if isinstance(value, dict) and set(value) == {"m_FileID", "m_PathID"}:
                    if key == "m_GameObject":
                        continue  # Its hierarchy path is retained in the row.
                    if key == "m_Mesh" and row["type"] == "MeshCollider":
                        continue  # Full collider mesh records are compared separately.
                    if value["m_PathID"]:
                        references.append({"path": row["path"], "type": row["type"],
                                           "field": key, "pointer": value})
                        value = {"non_null_reference_requires_review": True}
                values[key] = value
            result.append(dict(row, tree=values))
        return result, references

    def tracks(report):
        return [{"path": row["path"], "attributes": row["attributes"],
                 "vertex_channels": row["vertex_channels"],
                 "index_count": row["index_count"], "indices_sha256": row["indices_sha256"],
                 "mesh_settings": {k: v for k, v in row["mesh_settings"].items()
                                   if k != "m_StreamData"}}
                for row in report["track_details"]]

    a_physics, a_refs = physics(reference)
    b_physics, b_refs = physics(candidate)
    sections = {
        "collider_meshes": (reference["meshes"], candidate["meshes"]),
        "transforms": (transforms(reference), transforms(candidate)),
        "builtin_settings": (a_physics, b_physics),
        "track_geometry": (tracks(reference), tracks(candidate)),
        "script_identity_counts": ([{k: s[k] for k in ("class", "namespace", "assembly")}
                                    for s in reference["scripts"]],
                                   [{k: s[k] for k in ("class", "namespace", "assembly")}
                                    for s in candidate["scripts"]]),
    }
    compared = {}
    for name, (a, b) in sections.items():
        before, after = multiset(a), multiset(b)
        compared[name] = {"equal": before == after, "reference_count": len(a),
                          "candidate_count": len(b),
                          "reference_only": [json.loads(v) for v in (before - after).elements()],
                          "candidate_only": [json.loads(v) for v in (after - before).elements()]}
    def reference_assets(report):
        if "builtin_asset_references" not in report:
            return None
        if any("resolved_mapping" not in material for track in report["track_details"]
               for material in track["materials"]):
            return None
        return {"builtin": report["builtin_asset_references"],
                "tracks": [{"path": track["path"],
                            "materials": [m["resolved_mapping"] for m in track["materials"]]}
                           for track in report["track_details"]]}

    a_assets, b_assets = reference_assets(reference), reference_assets(candidate)
    assets_equal = None if a_assets is None or b_assets is None else all(
        multiset(a_assets[key]) == multiset(b_assets[key]) for key in ("builtin", "tracks"))
    if len(reference["meshes"]) != 18 or len(reference["track_details"]) != 2:
        raise ValueError("Comparison requires the inspected 18-collider/two-track baseline")
    return {"numeric_geometry_equal": not reference["errors"] and not candidate["errors"]
            and all(row["equal"] for row in compared.values()), "sections": compared,
            "reference_nonnull_asset_references": a_refs,
            "candidate_nonnull_asset_references": b_refs,
            "asset_mapping_equal": assets_equal,
            "asset_mapping_comparison": {"reference": a_assets, "candidate": b_assets},
            "normalization": ["Transform object/parent/child IDs omitted; hierarchy paths, local numeric fields and world matrices retained",
                              "Component owner IDs omitted; owner hierarchy paths retained",
                              "MeshCollider mesh pointers compared through the full collider mesh records",
                              "Mesh stream file/offset omitted; decoded attributes, packing and topology retained",
                              "Other nonnull builtin asset references listed; extended inventories resolve camera targets",
                              "Material shaders resolved by name and textures by recorded metadata; shader binaries and texture pixels are not compared"],
            "acceptance": "Not stage acceptance: reference coverage, source diff, rendering and live runs require review"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--track-details", action="store_true",
                        help="Read track render/collider attributes for a recovery proposal; never export Unity assets")
    parser.add_argument("--reference", type=Path,
                        help="Compare geometry with a previous --track-details scene.json; does not accept rendering/runtime")
    args = parser.parse_args()
    if args.results.exists() or not (args.data / "level0").is_file():
        parser.error("Need a player Data directory with level0 and a fresh results directory")
    if args.reference and (not args.track_details or not args.reference.is_file()):
        parser.error("--reference requires an existing inventory and --track-details")
    import numpy as np
    from scipy.spatial.transform import Rotation
    import UnityPy
    from UnityPy.classes.PPtr import PPtr
    from UnityPy.helpers.MeshHelper import MeshHandler

    started = time.monotonic()
    args.results.mkdir(parents=True)
    env = UnityPy.load(str(args.data / "level0"))
    objects = list(env.objects)
    builtin = {"GameObject", "Transform", "Rigidbody", "WheelCollider", "MeshCollider",
               "BoxCollider", "SphereCollider", "CapsuleCollider", "Camera"}
    if args.track_details:
        builtin.update({"MeshFilter", "MeshRenderer"})
    rows, errors = {}, []
    for obj in objects:
        if obj.type.name in builtin:
            try:
                rows[obj.path_id] = {"type": obj.type.name, "tree": obj.parse_as_dict()}
            except Exception as exc:
                errors.append({"path_id": obj.path_id, "type": obj.type.name, "error": repr(exc)})
    gos = {key: row["tree"] for key, row in rows.items() if row["type"] == "GameObject"}
    transforms = {row["tree"]["m_GameObject"]["m_PathID"]: row["tree"]
                  for row in rows.values() if row["type"] == "Transform"}

    def vector(value):
        return [value[key] for key in "xyz"]

    def parent(go):
        key = transforms[go]["m_Father"]["m_PathID"]
        return rows[key]["tree"]["m_GameObject"]["m_PathID"] if key else None

    @lru_cache(None)
    def world(go):
        row = transforms[go]
        matrix = np.eye(4)
        matrix[:3, :3] = Rotation.from_quat([row["m_LocalRotation"][key] for key in "xyzw"]).as_matrix() @ np.diag(vector(row["m_LocalScale"]))
        matrix[:3, 3] = vector(row["m_LocalPosition"])
        ancestor = parent(go)
        return world(ancestor) @ matrix if ancestor else matrix

    @lru_cache(None)
    def active(go):
        ancestor = parent(go)
        return bool(gos[go]["m_IsActive"]) and (active(ancestor) if ancestor else True)

    @lru_cache(None)
    def hierarchy(go):
        ancestor = parent(go)
        return (hierarchy(ancestor) + "/" if ancestor else "") + gos[go]["m_Name"]

    geometry, meshes, scripts, track_details = [], [], [], []
    for go in transforms:
        path = hierarchy(go)
        if path == "F1TENTH" or path.startswith(("F1TENTH/", "Infrastructure/")):
            matrix = world(go)
            geometry.append({"path": path, "active": active(go), "local": transforms[go],
                             "world_unity_transform": matrix.tolist(),
                             "world_ros_basis_position": [matrix[2, 3], -matrix[0, 3], matrix[1, 3]]})
    components, builtin_asset_references = [], []
    for key, row in rows.items():
        if row["type"] in builtin - {"GameObject", "Transform"}:
            go = row["tree"]["m_GameObject"]["m_PathID"]
            if go in transforms:
                components.append({"path": hierarchy(go), "type": row["type"], "active": active(go), "tree": row["tree"]})
                if row["type"] == "Camera" and row["tree"]["m_TargetTexture"]["m_PathID"]:
                    owner = next(obj for obj in objects if obj.path_id == key)
                    target = PPtr(assetsfile=owner.assets_file, **row["tree"]["m_TargetTexture"]).deref()
                    if target.type.name != "RenderTexture":
                        raise ValueError("Unexpected nonnull camera target type")
                    builtin_asset_references.append({"path": hierarchy(go), "type": row["type"],
                                                     "field": "m_TargetTexture", "target_type": target.type.name,
                                                     "target": target.parse_as_dict()})
    for obj in objects:
        try:
            if obj.type.name == "MonoBehaviour":
                header = obj.parse_monobehaviour_head()
                script = header.m_Script.deref_parse_as_object()
                scripts.append({"path_id": obj.path_id, "game_object_id": header.m_GameObject.m_PathID,
                                "class": script.m_ClassName, "namespace": script.m_Namespace, "assembly": script.m_AssemblyName})
            if obj.type.name == "MeshCollider":
                collider = obj.parse_as_object()
                mesh = collider.m_Mesh.deref_parse_as_object()
                handler = MeshHandler(mesh)
                handler.process()
                vertices = np.asarray(handler.m_Vertices, dtype="<f8")
                indices = np.asarray(handler.m_IndexBuffer, dtype="<u4")
                go = collider.m_GameObject.m_PathID
                transform = world(go)
                points = vertices @ transform[:3, :3].T + transform[:3, 3]
                ros = points[:, [2, 0, 1]] * np.array([1, -1, 1])
                meshes.append({"path": hierarchy(go), "name": mesh.m_Name,
                               "enabled": bool(collider.m_Enabled), "active": active(go), "convex": bool(collider.m_Convex),
                               "vertices": len(vertices), "indices": len(indices),
                               "vertices_sha256": hashlib.sha256(vertices.tobytes()).hexdigest(),
                               "indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
                               "ros_basis_bounds": [ros.min(axis=0).tolist(), ros.max(axis=0).tolist()]})
                if args.track_details and hierarchy(go) in ("Infrastructure/Proto Track", "Infrastructure/Berlin Track"):
                    attributes = {}
                    for name in ("m_Vertices", "m_Normals", "m_Tangents", "m_Colors",
                                 "m_UV0", "m_UV1", "m_UV2", "m_UV3", "m_UV4", "m_UV5", "m_UV6", "m_UV7"):
                        values = getattr(handler, name, None)
                        if values is None or not len(values):
                            attributes[name] = {"count": 0}
                        else:
                            array = np.asarray(values, dtype="<f4")
                            attributes[name] = {"count": len(array), "shape": list(array.shape),
                                                "finite": bool(np.isfinite(array).all()),
                                                "decoded_float32_sha256": hashlib.sha256(array.tobytes()).hexdigest()}
                    mesh_tree = mesh.object_reader.parse_as_dict()
                    renderers = [item for item in objects if item.type.name == "MeshRenderer"
                                 and item.parse_as_dict()["m_GameObject"]["m_PathID"] == go]
                    filters = [item for item in objects if item.type.name == "MeshFilter"
                               and item.parse_as_dict()["m_GameObject"]["m_PathID"] == go]
                    materials = []
                    for renderer in renderers:
                        for pointer in renderer.parse_as_object().m_Materials:
                            material = pointer.deref()
                            value = material.parse_as_dict()
                            # Resolve volatile build references without discarding material values.
                            resolved = json.loads(json.dumps(value))
                            shader = PPtr(assetsfile=material.assets_file, **value["m_Shader"]).deref_parse_as_dict()
                            resolved["m_Shader"] = {"name": shader.get("m_ParsedForm", {}).get("m_Name") or shader.get("m_Name")}
                            if not resolved["m_Shader"]["name"]:
                                raise ValueError("Unresolved material shader name")
                            for _, texenv in resolved["m_SavedProperties"]["m_TexEnvs"]:
                                pointer = texenv["m_Texture"]
                                if pointer["m_PathID"]:
                                    texture = PPtr(assetsfile=material.assets_file, **pointer).deref_parse_as_dict()
                                    texenv["m_Texture"] = {key: texture.get(key) for key in
                                        ("m_Name", "m_Width", "m_Height", "m_TextureFormat", "m_MipCount", "m_ColorSpace", "m_TextureSettings")}
                                else:
                                    texenv["m_Texture"] = None
                            materials.append({"asset_file": material.assets_file.name,
                                              "path_id": material.path_id, "tree": value,
                                              "resolved_mapping": resolved})
                    track_details.append({"path": hierarchy(go), "mesh_asset_file": mesh.object_reader.assets_file.name,
                                          "mesh_path_id": mesh.object_reader.path_id,
                                          "attributes": attributes,
                                          "mesh_settings": {key: mesh_tree.get(key) for key in
                                              ("m_IndexFormat", "m_MeshCompression", "m_IsReadable", "m_KeepVertices", "m_KeepIndices", "m_LocalAABB", "m_SubMeshes", "m_Shapes", "m_StreamData")},
                                          "vertex_channels": mesh_tree["m_VertexData"]["m_Channels"],
                                          "index_count": len(indices), "indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
                                          "indices_within_vertex_count": bool(len(indices) and int(indices.max()) < len(vertices)),
                                          "materials": materials,
                                          "renderers": [item.parse_as_dict() for item in renderers],
                                          "filters": [item.parse_as_dict() for item in filters],
                                          "collider": obj.parse_as_dict(),
                                          "game_object": gos[go], "transform": transforms[go]})
        except Exception as exc:
            errors.append({"path_id": obj.path_id, "type": obj.type.name, "error": repr(exc)})
    report = {"data": str(args.data.resolve()), "unitypy_version": UnityPy.__version__,
              "level0_sha256": hashlib.sha256((args.data / "level0").read_bytes()).hexdigest(),
              "qualification": "Static serialized fields only; no runtime contact/scoring or kinematic calibration claim",
              "basis": "(Unity.z, -Unity.x, Unity.y) from historical IPS source; not independently calibrated",
              "types": dict(Counter(obj.type.name for obj in objects)), "transforms": geometry,
              "components": components, "meshes": meshes, "scripts": scripts, "errors": errors,
              "track_details": track_details,
              "builtin_asset_references": builtin_asset_references,
              "wall_seconds": time.monotonic() - started}
    (args.results / "scene.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"meshes": len(meshes), "scripts": len(scripts), "errors": errors, "wall_seconds": report["wall_seconds"]}))
    if args.reference:
        comparison = compare_geometry(json.loads(args.reference.read_text()), report)
        comparison["reference_sha256"] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
        comparison["tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (args.results / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
        print(json.dumps({key: comparison[key] for key in ("numeric_geometry_equal", "asset_mapping_equal")}))
        if not comparison["numeric_geometry_equal"] or comparison["asset_mapping_equal"] is False:
            return 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
