"""Run the actual probe against test doubles; this does not qualify Unity physics."""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


class KinematicsSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        data = Path(os.environ.get("ROBORACER_UNITY_DATA",
                    str(Path("~/roboracer-work/toolchains/2021.3.9f1/Editor/Data").expanduser())))
        cls.mono = data / "MonoBleedingEdge/bin/mono"
        compiler = data / "MonoBleedingEdge/lib/mono/4.5/csc.exe"
        if not cls.mono.is_file() or not compiler.is_file():
            raise unittest.SkipTest("Pinned Mono compiler unavailable; no runtime claim")
        cls.scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.fixture = Path(cls.scratch.name) / "fixture.exe"
        result = subprocess.run([str(cls.mono), str(compiler), "-nologo", "-out:" + str(cls.fixture),
            str(cls.root / "integration/autodrive/diagnostics/KinematicsProbe.cs"),
            str(cls.root / "integration/autodrive/diagnostics/ContactProbe.cs"),
            str(cls.root / "integration/autodrive/diagnostics/ContactRelay.cs"),
            str(cls.root / "integration/autodrive/diagnostics/PoseTrace.cs"),
            str(cls.root / "scripts/tests/fixtures/KinematicsProbeFixture.cs")], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def run_fixture(self, case):
        out = Path(self.scratch.name) / case
        out.mkdir()
        result = subprocess.run([str(self.mono), str(self.fixture), str(out), case], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        status = json.loads((out / "status.json").read_text())
        path = out / "samples.jsonl"
        rows = [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
        return result, status, rows

    def test_complete_records_preserve_precision_and_phase(self):
        result, status, rows = self.run_fixture("valid")
        self.assertEqual("0", result.stdout.strip())
        self.assertEqual("closed", status["state"])
        self.assertEqual(2, status["samples"])
        self.assertEqual(["FixedUpdate", "LateUpdate"], [r["phase"] for r in rows[1:]])
        for r in rows[1:]:
            self.assertEqual(struct.unpack("f", struct.pack("f", .1))[0], r["body"]["position"][0])
            self.assertEqual(4, len(r["wheels"]))
            self.assertTrue(all(w["grounded"] for w in r["wheels"]))
            self.assertGreater(r["monotonic_ns"], 0)
        self.assertLess(rows[1]["monotonic_ns"], rows[2]["monotonic_ns"])

    def test_wrong_binding_fails_before_sampling(self):
        result, status, rows = self.run_fixture("binding")
        self.assertEqual("17", result.stdout.strip())
        self.assertEqual("failed", status["state"])
        self.assertIn("binding", status["error"])
        self.assertEqual([], rows)

    def test_nonfinite_state_does_not_emit_invalid_json(self):
        result, status, rows = self.run_fixture("nonfinite")
        self.assertEqual("17", result.stdout.strip())
        self.assertEqual("failed", status["state"])
        self.assertIn("Nonfinite", status["error"])
        self.assertEqual(["binding"], [r["kind"] for r in rows])

    def test_trace_cap_fails_without_a_partial_record(self):
        result, status, rows = self.run_fixture("cap")
        self.assertEqual("17", result.stdout.strip())
        self.assertIn("1 GiB", status["error"])
        self.assertEqual(["binding"], [r["kind"] for r in rows])

    def test_nonzero_control_is_rejected(self):
        result, status, rows = self.run_fixture("nonzero")
        self.assertEqual("17", result.stdout.strip())
        self.assertIn("exact-zero", status["error"])
        self.assertEqual(["binding"], [r["kind"] for r in rows])

    def test_contact_control_records_all_pairs_without_setters(self):
        _, status, rows = self.run_fixture("contact_control")
        self.assertEqual("closed", status["state"])
        self.assertEqual([1]*4, status["contact_pair_counts"])
        directory = Path(self.scratch.name) / "contact_control"
        self.assertEqual({"before_request": 0, "total": 0}, json.loads((directory/"fixture-calls.json").read_text()))
        contacts = [json.loads(s) for s in (directory/"contacts.jsonl").read_text().splitlines()]
        self.assertEqual(["contact_binding", "collision", "window_activation"], [r["kind"] for r in contacts])
        self.assertEqual(4, len(contacts[1]["points"]))
        self.assertEqual([False]*4, contacts[-1]["after_ignored"])
        self.assertEqual(contacts[0]["track_id"], rows[-1]["wheels"][0]["collider_id"])

    def test_contact_treatment_only_applies_four_pairs_after_request(self):
        for case, count in (("contact_pending_treatment", 0), ("contact_treatment", 4)):
            with self.subTest(case=case):
                _, status, rows = self.run_fixture(case)
                self.assertEqual("closed", status["state"])
                calls = json.loads((Path(self.scratch.name)/case/"fixture-calls.json").read_text())
                self.assertEqual(0, calls["before_request"])
                self.assertEqual(count, calls["total"])
                self.assertEqual([bool(count)]*4, rows[-1]["contact_state"]["ignored"])

    def test_contact_invalid_request_never_filters_pairs(self):
        for case in ("contact_stale_treatment", "contact_foreign_treatment"):
            with self.subTest(case=case):
                _, status, _ = self.run_fixture(case)
                self.assertEqual("failed", status["state"])
                self.assertIn("window request", status["error"])
                self.assertEqual(0, json.loads((Path(self.scratch.name)/case/"fixture-calls.json").read_text())["total"])

    def test_contact_binding_capacity_finite_and_property_failures(self):
        for case, error in (("contact_binding", "MeshCollider state"), ("contact_overflow", "Contact count"),
                            ("contact_nonfinite", "Nonfinite"), ("contact_cap", "1 GiB"),
                            ("contact_inertia_treatment", "mass/COM/inertia")):
            with self.subTest(case=case):
                _, status, _ = self.run_fixture(case)
                self.assertEqual("failed", status["state"])
                self.assertIn(error, status["error"])


    def test_floor_local_inertia_policy_and_exact_surface(self):
        for case in ("contact_floor_control", "contact_floor_treatment", "contact_floor_natural_treatment"):
            with self.subTest(case=case):
                _, status, rows = self.run_fixture(case)
                self.assertEqual("closed", status["state"])
                self.assertEqual("floor", status["contact_target"])
                directory = Path(self.scratch.name) / case
                calls = json.loads((directory/"fixture-calls.json").read_text())
                self.assertEqual(0, calls["before_request"])
                self.assertEqual(4 if "treatment" in case else 0, calls["total"])
                contacts = [json.loads(s) for s in (directory/"contacts.jsonl").read_text().splitlines()]
                activation = contacts[-1]
                self.assertEqual(activation["before_properties"], activation["after_properties"])
                if "natural" in case:
                    self.assertNotEqual(rows[-1]["contact_state"]["properties"]["inertia_tensor"], activation["after_properties"]["inertia_tensor"])

    def test_floor_rejects_property_faults_and_wrong_binding(self):
        for suffix, error, calls in (("immediate_treatment", "mass/COM/inertia", 4),
                                     ("masschange_treatment", "mass/COM", 4),
                                     ("comchange_control", "mass/COM", 0),
                                     ("wrongtarget_treatment", "foreign", 0),
                                     ("dynamic", "surface collider state", 0),
                                     ("trigger", "surface collider state", 0),
                                     ("wrongtype", "surface collider state", 0)):
            case = "contact_floor_"+suffix
            with self.subTest(case=case):
                _, status, _ = self.run_fixture(case)
                self.assertEqual("failed", status["state"])
                self.assertIn(error, status["error"])
                directory = Path(self.scratch.name) / case
                self.assertEqual(calls, json.loads((directory/"fixture-calls.json").read_text())["total"])


if __name__ == "__main__":
    unittest.main()
