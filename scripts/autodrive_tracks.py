#!/usr/bin/env python3
"""Explicit SIM0 native-track input export, reference mapping and verification.

Run export in the isolated asset-analysis environment. All inputs are local;
this tool never starts Unity, the simulator, or a control process.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "integration/autodrive/linux-track-recovery.json"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def bounds(value):
    return {"center": [value["m_Center"][k] for k in "xyz"],
            "extents": [value["m_Extent"][k] for k in "xyz"]}


def export(args, policy):
    import numpy as np
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler

    scene = json.loads(args.inventory.read_text())
    if digest(args.data / "level0") != scene["level0_sha256"]:
        raise ValueError("Installed scene differs from the inspected input")
    env = UnityPy.load(str(args.data / "level0"))
    exported = []
    raw_dtype = np.dtype({"names": ["m_Vertices", "m_Normals", "m_Tangents", "m_UV0"],
        "formats": [("<f4", 3), ("<f2", 4), ("<f2", 4), ("<f2", 2)],
        "offsets": [0, 12, 20, 28], "itemsize": 32})
    for track in policy["tracks"]:
        detail = next(t for t in scene["track_details"] if t["path"] == "Infrastructure/" + track["name"])
        collider_obj = next(obj for obj in env.objects if obj.type.name == "MeshCollider"
            and obj.parse_as_dict()["m_GameObject"] == detail["collider"]["m_GameObject"])
        mesh = collider_obj.parse_as_object().m_Mesh.deref_parse_as_object()
        handler = MeshHandler(mesh)
        handler.process()
        settings = detail["mesh_settings"]
        inspected_mesh = next(t for t in scene["meshes"] if t["path"] == detail["path"])
        if (mesh.m_Name != inspected_mesh["name"] or mesh.object_reader.path_id != detail["mesh_path_id"]
                or settings["m_MeshCompression"] or settings["m_IndexFormat"] != 1):
            raise ValueError("Unexpected mesh identity/packing")
        stream = settings["m_StreamData"]
        if stream["path"] != "sharedassets0.assets.resS":
            raise ValueError("Unexpected vertex resource path")
        with (args.data / stream["path"]).open("rb") as f:
            f.seek(stream["offset"])
            raw = f.read(stream["size"])
        count = detail["attributes"]["m_Vertices"]["count"]
        if len(raw) != count * 32:
            raise ValueError("Incomplete or unexpected vertex buffer")
        decoded = np.frombuffer(raw, raw_dtype)
        for name in raw_dtype.names:
            h = hashlib.sha256(np.asarray(decoded[name], dtype="<f4").tobytes()).hexdigest()
            if h != detail["attributes"][name]["decoded_float32_sha256"]:
                raise ValueError("Independent attribute decoder mismatch: " + name)
        indices = np.asarray(handler.m_IndexBuffer, dtype="<u4")
        if (len(indices) != detail["index_count"] or int(indices.max()) >= count
                or hashlib.sha256(indices.tobytes()).hexdigest() != detail["indices_sha256"]):
            raise ValueError("Index buffer differs from inspected input")
        prefix = track["name"].replace(" ", "-").lower()
        vertex_path, index_path = args.results / (prefix + ".vertices.bin"), args.results / (prefix + ".indices.bin")
        vertex_path.write_bytes(raw)
        index_path.write_bytes(indices.tobytes())
        renderer = detail["renderers"][0]
        scalar_settings, vector_settings = [], []
        for name, value in renderer.items():
            if isinstance(value, (int, bool)):
                scalar_settings.append({"name": name, "boolean": isinstance(value, bool), "value": int(value)})
            elif isinstance(value, dict) and set(value) == set("xyzw"):
                vector_settings.append({"name": name, "value": [value[k] for k in "xyzw"]})
            elif name not in {"m_GameObject", "m_Materials", "m_StaticBatchInfo"}:
                if not isinstance(value, dict) or value != {"m_FileID": 0, "m_PathID": 0}:
                    raise ValueError("Unsupported nonempty renderer field: " + name)
        if renderer["m_StaticBatchInfo"] != {"firstSubMesh": 0, "subMeshCount": 0}:
            raise ValueError("Cannot recover a static-batched track")
        materials = ["Assets/Models/Infrastructure/F1TENTH Tracks/Materials/" + material["tree"]["m_Name"] + ".mat"
                     for material in detail["materials"]]
        if len(materials) != 2 or any(not (args.source / p).is_file() for p in materials):
            raise ValueError("Required original materials not present")
        exported.append({"name": track["name"], "meshName": mesh.m_Name, "vertexFile": str(vertex_path.resolve()),
            "indexFile": str(index_path.resolve()), "vertexSha256": digest(vertex_path),
            "indexSha256": digest(index_path), "vertexCount": count, "indexCount": len(indices),
            "bounds": bounds(settings["m_LocalAABB"]), "isReadable": settings["m_IsReadable"],
            "vertexChannels": detail["vertex_channels"],
            "keepVertices": settings["m_KeepVertices"], "keepIndices": settings["m_KeepIndices"],
            "submeshes": [{"indexStart": s["firstByte"] // 4, "indexCount": s["indexCount"],
                "baseVertex": s["baseVertex"], "firstVertex": s["firstVertex"],
                "vertexCount": s["vertexCount"], "topology": s["topology"],
                "bounds": bounds(s["localAABB"])} for s in settings["m_SubMeshes"]],
            "materialPaths": materials, "materialSha256": [digest(args.source / p) for p in materials],
            "scalarSettings": scalar_settings, "vectorSettings": vector_settings,
            "layer": detail["game_object"]["m_Layer"], "active": detail["game_object"]["m_IsActive"],
            "localPosition": [detail["transform"]["m_LocalPosition"][k] for k in "xyz"],
            "localScale": [detail["transform"]["m_LocalScale"][k] for k in "xyz"],
            "colliderCookingOptions": detail["collider"]["m_CookingOptions"]})
    record = {"formatVersion": 2, "normalAuthoring": "float32x3",
        "assetDirectory": policy["native_asset_directory"], "tracks": exported,
        "sourceCommit": policy["source_commit"], "policySha256": digest(POLICY),
        "inventorySha256": digest(args.inventory), "unityPyVersion": UnityPy.__version__,
        "playerInputs": {name: digest(args.data / name) for name in
                         ("level0", "sharedassets0.assets", "sharedassets0.assets.resS")}}
    write(args.results / "track-inputs.json", record)
    return {"status": "exported_verified_inputs", "tracks": len(exported)}


def apply(args, policy):
    if subprocess.check_output(["git", "-C", str(args.project), "rev-parse", "HEAD"], text=True).strip() != policy["source_commit"]:
        raise ValueError("Unexpected source commit")
    report = json.loads(args.generated_report.read_text())
    if not report["passed"] or len(report["tracks"]) != 2:
        raise ValueError("Generation report did not pass")
    invocation = json.loads(args.generated_report.with_name("build-result.json").read_text())
    if not invocation.get("editor_reaped") or invocation["project"] != str(args.project.resolve()):
        raise ValueError("Generation belongs to another project or its Editor is not reaped")
    guids = [t[k] for t in report["tracks"] for k in ("meshGuid", "prefabGuid")]
    if len(set(guids)) != 4:
        raise ValueError("Generated asset GUIDs must be distinct")
    scene = args.project / "Assets/Scenes/F1TENTH.unity"
    if digest(scene) != policy["original_scene_sha256"]:
        raise ValueError("Scene is not the approved unmodified baseline")
    before = scene.read_text()
    text = before
    mappings = []
    for track in policy["tracks"]:
        row = next(t for t in report["tracks"] if t["name"] == track["name"])
        prefab_guid = row["prefabGuid"]
        mesh_guid = row["meshGuid"]
        for guid in (prefab_guid, mesh_guid):
            if not re.fullmatch(r"[0-9a-f]{32}", guid):
                raise ValueError("Invalid generated asset GUID")
        ids = {track["source_mesh_id"]: (row["meshLocalId"], mesh_guid, 2),
               track["source_gameobject_id"]: (row["gameObjectLocalId"], prefab_guid, 3),
               track["source_transform_id"]: (row["transformLocalId"], prefab_guid, 3),
               "100100000": ("100100000", prefab_guid, 3)}
        pattern = re.compile(r"\{fileID: (-?\d+), guid: " + track["source_guid"] + r",\s*type: 3\}")
        matches = list(pattern.finditer(text))
        if len(matches) != track["reference_count"]:
            raise ValueError("Unexpected source track reference count")
        def replace(match):
            if match[1] not in ids:
                raise ValueError("Unexpected source local ID: " + match[1])
            local_id, guid, kind = ids[match[1]]
            old = match[0]
            new = old.replace("fileID: " + match[1] + ",", "fileID: " + str(local_id) + ",", 1)
            return new.replace(track["source_guid"], guid, 1).replace("type: 3}", f"type: {kind}}}")
        updated = pattern.sub(replace, text)
        if track["source_guid"] in updated:
            raise ValueError("Unmapped source GUID remains")
        mappings.append({"name": track["name"], "count": len(matches), "mapping": ids,
                         "sourceGuid": track["source_guid"]})
        text = updated
    (args.results / "scene-before.unity").write_text(before)
    # Reversing the exact substitutions must recover every byte of the original.
    reversed_text = text
    for m in mappings:
        for old_id, (new_id, new_guid, kind) in m["mapping"].items():
            pat = re.compile(r"\{fileID: " + re.escape(str(new_id)) + ", guid: " + new_guid + r",\s*type: " + str(kind) + r"\}")
            reversed_text = pat.sub(lambda x: x[0].replace("fileID: " + str(new_id) + ",", "fileID: " + old_id + ",", 1)
                .replace(new_guid, m["sourceGuid"], 1).replace(f"type: {kind}}}", "type: 3}"), reversed_text)
    if reversed_text != before:
        raise ValueError("Reference patch changes bytes outside the verified mapping")
    scene.write_text(text)
    return {"status": "applied", "scene_before_sha256": hashlib.sha256(before.encode()).hexdigest(),
            "scene_after_sha256": digest(scene), "mappings": mappings,
            "reversible_exact_reference_only_patch": True}


def archive_generated(args, policy, require_failure=False):
    report = json.loads(args.generated_report.read_text())
    invocation = json.loads(args.generated_report.with_name("build-result.json").read_text())
    if ((require_failure and report["passed"]) or not invocation.get("editor_reaped")
            or invocation["project"] != str(args.project.resolve())):
        raise ValueError("Archive requires the expected generation status and its owned Editor reaped")
    if digest(args.project / "Assets/Scenes/F1TENTH.unity") != policy["original_scene_sha256"]:
        raise ValueError("Cannot archive generated assets after the scene was remapped")
    folder = args.project / "Assets/RoboRacerQualification"
    allowed = {"Tracks.meta"} | {"Tracks/" + t["name"] + ext
        for t in policy["tracks"] for ext in (".asset", ".asset.meta", ".prefab", ".prefab.meta")}
    files = {str(p.relative_to(folder)): digest(p) for p in folder.rglob("*") if p.is_file()}
    if not files or not set(files) <= allowed:
        raise ValueError("Refusing to archive unexpected assets")
    meta = folder.with_suffix(".meta")
    meta_hash = digest(meta)
    backup = args.results / "RoboRacerQualification"
    shutil.move(str(folder), str(backup))
    shutil.move(str(meta), str(backup.with_suffix(".meta")))
    if any(digest(backup / name) != value for name, value in files.items()) or digest(backup.with_suffix(".meta")) != meta_hash:
        raise ValueError("Archived output hash mismatch")
    return {"status": ("passed" if report["passed"] else "failed") + "_generated_assets_archived", "files": files,
            "directory_meta_sha256": meta_hash, "original_scene_preserved":
                digest(args.project / "Assets/Scenes/F1TENTH.unity") == policy["original_scene_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    p = modes.add_parser("export")
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p = modes.add_parser("apply")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--generated-report", type=Path, required=True)
    p = modes.add_parser("archive-failed")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--generated-report", type=Path, required=True)
    p = modes.add_parser("archive-generated", help="Preserve a superseded generation before exact-input regeneration")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--generated-report", type=Path, required=True)
    for p in modes.choices.values():
        p.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    if args.results.exists():
        parser.error("Use a fresh results directory")
    args.results.mkdir(parents=True)
    result = {}
    try:
        policy = json.loads(POLICY.read_text())
        actions = {"export": export, "apply": apply,
                   "archive-failed": lambda a, p: archive_generated(a, p, require_failure=True),
                   "archive-generated": archive_generated}
        result = actions[args.mode](args, policy)
        result["tool_sha256"] = digest(Path(__file__))
        print(json.dumps(result))
        return 0
    except BaseException as exc:
        result = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
        raise
    finally:
        write(args.results / "result.json", result)


if __name__ == "__main__":
    raise SystemExit(main())
