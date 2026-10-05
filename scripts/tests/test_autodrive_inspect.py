"""Acceptance-comparison guards; no Unity or scientific packages required."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_inspect import compare_geometry


def fixture():
    return {
        "errors": [],
        "meshes": [{"path": f"collider/{i}", "vertices_sha256": "vertices",
                    "indices_sha256": "indices"} for i in range(18)],
        "transforms": [{"path": "F1TENTH/Wheel", "active": True,
                        "local": {"m_GameObject": {"m_PathID": 100},
                                  "m_Father": {"m_PathID": 200}, "m_Children": [],
                                  "m_LocalPosition": {"x": 0.0, "y": 1.0, "z": 0.0}},
                        "world_unity_transform": [[1, 0, 0, 0]],
                        "world_ros_basis_position": [0, 0, 1]}],
        "components": [{"path": "F1TENTH/Vehicle", "type": "BoxCollider",
                        "active": True, "tree": {"m_GameObject": {"m_FileID": 0, "m_PathID": 100},
                                                   "m_Size": {"x": 1.0}}}] * 2,
        "track_details": [{"path": name, "attributes": {"m_Vertices": {"hash": "exact"}},
                           "vertex_channels": [{"dimension": 3}], "index_count": 6,
                           "indices_sha256": "indices",
                           "mesh_settings": {"m_IsReadable": False,
                                             "m_StreamData": {"offset": 123}}}
                          for name in ("Proto", "Berlin")],
        "scripts": [{"class": "LIDAR", "namespace": "", "assembly": "Assembly-CSharp",
                     "path_id": 10, "game_object_id": 100}],
    }


class GeometryComparisonTests(unittest.TestCase):
    def test_build_ids_offsets_and_list_order_are_not_geometry(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["transforms"][0]["local"]["m_GameObject"]["m_PathID"] = 999
        b["transforms"][0]["local"]["m_Father"]["m_PathID"] = 888
        b["track_details"][0]["mesh_settings"]["m_StreamData"]["offset"] = 456
        b["meshes"].reverse()
        b["scripts"][0]["path_id"] = 42
        self.assertTrue(compare_geometry(a, b)["numeric_geometry_equal"])

    def test_coordinate_or_topology_change_fails(self):
        for kind in ("position", "topology", "attribute"):
            with self.subTest(kind=kind):
                a = fixture()
                b = copy.deepcopy(a)
                if kind == "position":
                    b["transforms"][0]["local"]["m_LocalPosition"]["x"] = 0.001
                elif kind == "topology":
                    b["meshes"][0]["indices_sha256"] = "different"
                else:
                    b["track_details"][0]["attributes"]["m_Vertices"]["hash"] = "different"
                self.assertFalse(compare_geometry(a, b)["numeric_geometry_equal"])

    def test_duplicate_collider_count_is_preserved(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["components"].pop()
        self.assertFalse(compare_geometry(a, b)["numeric_geometry_equal"])

    def test_serialized_channel_upper_bits_are_not_silently_masked(self):
        a = fixture()
        b = copy.deepcopy(a)
        a["track_details"][0]["vertex_channels"][0]["dimension"] = 52
        b["track_details"][0]["vertex_channels"][0]["dimension"] = 4
        result = compare_geometry(a, b)
        self.assertFalse(result["numeric_geometry_equal"])
        self.assertFalse(result["sections"]["track_geometry"]["equal"])

    def test_nonnull_asset_reference_is_explicitly_unaccepted(self):
        a = fixture()
        a["components"].append({"path": "Camera", "type": "Camera", "active": True,
                                "tree": {"m_TargetTexture": {"m_FileID": 2, "m_PathID": 12}}})
        b = copy.deepcopy(a)
        b["components"][-1]["tree"]["m_TargetTexture"]["m_PathID"] = 34
        result = compare_geometry(a, b)
        self.assertTrue(result["numeric_geometry_equal"])
        self.assertNotEqual(result["reference_nonnull_asset_references"],
                            result["candidate_nonnull_asset_references"])
        self.assertIn("Not stage acceptance", result["acceptance"])
        self.assertIsNone(result["asset_mapping_equal"])

    def test_material_and_camera_metadata_drift_are_detected(self):
        a = fixture()
        a["builtin_asset_references"] = [{"path": "Camera", "target": {"m_Width": 1280}}]
        for track in a["track_details"]:
            track["materials"] = [{"resolved_mapping": {"m_Name": "Outer Face",
                                   "m_Shader": {"name": "HDRP/Lit"},
                                   "texture": {"m_Name": "Wall", "m_Width": 1024}}}]
        b = copy.deepcopy(a)
        b["track_details"].reverse()
        self.assertTrue(compare_geometry(a, b)["asset_mapping_equal"])
        for kind in ("shader", "texture", "camera"):
            with self.subTest(kind=kind):
                b = copy.deepcopy(a)
                if kind == "camera":
                    b["builtin_asset_references"][0]["target"]["m_Width"] = 640
                else:
                    material = b["track_details"][0]["materials"][0]["resolved_mapping"]
                    if kind == "shader":
                        material["m_Shader"]["name"] = "FallbackError"
                    else:
                        material["texture"]["m_Name"] = "Different Wall"
                result = compare_geometry(a, b)
                self.assertTrue(result["numeric_geometry_equal"])
                self.assertFalse(result["asset_mapping_equal"])
        del b["track_details"][0]["materials"][0]["resolved_mapping"]
        self.assertIsNone(compare_geometry(a, b)["asset_mapping_equal"])

    def test_parse_error_or_incomplete_baseline_cannot_pass(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["errors"].append("unreadable collider")
        self.assertFalse(compare_geometry(a, b)["numeric_geometry_equal"])
        a["meshes"].pop()
        with self.assertRaises(ValueError):
            compare_geometry(a, b)


if __name__ == "__main__":
    unittest.main()
