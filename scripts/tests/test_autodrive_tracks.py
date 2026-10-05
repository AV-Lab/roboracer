"""Reference mapping guards with synthetic Unity text; no Unity or asset dependencies."""

import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("autodrive_tracks", Path(__file__).parents[1] / "autodrive_tracks.py")
TRACKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACKS)


class ReferenceMappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scene = self.root / "Assets/Scenes/F1TENTH.unity"
        self.scene.parent.mkdir(parents=True)
        self.policy = {"source_commit": "fixture-commit", "tracks": []}
        rows, text = [], ["%YAML 1.1\n# Preserve every unrelated byte.\nuntouched: {fileID: 77}\n"]
        for i, name in enumerate(("Proto Track", "Berlin Track"), 1):
            guid = str(i) * 32
            t = {"name": name, "source_guid": guid, "source_mesh_id": "-6898062887461957196",
                 "source_gameobject_id": "919132149155446097", "source_transform_id": "-8679921383154817045",
                 "reference_count": 4}
            self.policy["tracks"].append(t)
            for field, old_id in (("prefab", "100100000"), ("gameObject", t["source_gameobject_id"]),
                                  ("transform", t["source_transform_id"]), ("mesh", t["source_mesh_id"])):
                text.append(f"{field}: {{fileID: {old_id}, guid: {guid},\n    type: 3}}\n")
            rows.append({"name": name, "meshGuid": str(i + 2) * 32, "prefabGuid": str(i + 4) * 32,
                         "meshLocalId": "4300000", "gameObjectLocalId": "9007199254740993",
                         "transformLocalId": "-9007199254740995"})
        self.original = "".join(text)
        self.scene.write_text(self.original)
        self.policy["original_scene_sha256"] = TRACKS.digest(self.scene)
        self.report = self.root / "native-track-report.json"
        self.report_data = {"passed": True, "tracks": rows}
        self.report.write_text(json.dumps(self.report_data))
        self.invocation = self.root / "build-result.json"
        self.invocation.write_text(json.dumps({"editor_reaped": True, "project": str(self.root.resolve())}))
        self.results = self.root / "results"
        self.results.mkdir()
        self.args = types.SimpleNamespace(project=self.root, generated_report=self.report, results=self.results)
        self.git = patch.object(TRACKS.subprocess, "check_output", return_value="fixture-commit\n")
        self.git.start()
        self.addCleanup(self.git.stop)

    def test_maps_large_ids_without_float_rounding_and_preserves_other_bytes(self):
        result = TRACKS.apply(self.args, self.policy)
        after = self.scene.read_text()
        self.assertTrue(result["reversible_exact_reference_only_patch"])
        self.assertEqual([m["count"] for m in result["mappings"]], [4, 4])
        self.assertIn("fileID: 9007199254740993", after)
        self.assertIn("fileID: -9007199254740995", after)
        self.assertIn("untouched: {fileID: 77}", after)
        self.assertEqual(after.count("type: 2}"), 2)
        self.assertEqual((self.results / "scene-before.unity").read_text(), self.original)

    def test_failed_generation_cannot_change_scene(self):
        self.report_data["passed"] = False
        self.report.write_text(json.dumps(self.report_data))
        with self.assertRaisesRegex(ValueError, "did not pass"):
            TRACKS.apply(self.args, self.policy)
        self.assertEqual(self.scene.read_text(), self.original)

    def test_different_project_or_live_editor_is_rejected(self):
        for values in ({"editor_reaped": False, "project": str(self.root.resolve())},
                       {"editor_reaped": True, "project": "/unrelated/project"}):
            with self.subTest(values=values):
                self.invocation.write_text(json.dumps(values))
                with self.assertRaisesRegex(ValueError, "another project"):
                    TRACKS.apply(self.args, self.policy)
                self.assertEqual(self.scene.read_text(), self.original)

    def test_changed_source_is_rejected_before_writing(self):
        altered = self.original + "# User change\n"
        self.scene.write_text(altered)
        with self.assertRaisesRegex(ValueError, "unmodified baseline"):
            TRACKS.apply(self.args, self.policy)
        self.assertEqual(self.scene.read_text(), altered)

    def test_unrecognized_local_reference_is_rejected(self):
        altered = self.original.replace("fileID: 100100000", "fileID: 100100001", 1)
        self.scene.write_text(altered)
        self.policy["original_scene_sha256"] = TRACKS.digest(self.scene)
        with self.assertRaisesRegex(ValueError, "Unexpected source local ID"):
            TRACKS.apply(self.args, self.policy)
        self.assertEqual(self.scene.read_text(), altered)

    def test_guid_collision_is_rejected(self):
        self.report_data["tracks"][0]["prefabGuid"] = self.report_data["tracks"][0]["meshGuid"]
        self.report.write_text(json.dumps(self.report_data))
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            TRACKS.apply(self.args, self.policy)
        self.assertEqual(self.scene.read_text(), self.original)

    def test_repeat_patch_is_rejected(self):
        TRACKS.apply(self.args, self.policy)
        after = self.scene.read_bytes()
        with self.assertRaisesRegex(ValueError, "unmodified baseline"):
            TRACKS.apply(self.args, self.policy)
        self.assertEqual(self.scene.read_bytes(), after)


if __name__ == "__main__":
    unittest.main()
