"""Contact evidence gates: reject incomplete controls and altered raw evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_contacts import (TARGETS, TRACK, analyze_contacts, check_status,
                               make_gate, player_identity, verify_gate, write_window_request)


class ContactEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.start, self.end = 10_000_000_000, 70_000_000_000
        self.properties = {"mass": 3.47, "center_of_mass": [0, .064, 0],
                           "inertia_tensor": [.1, .2, .3], "inertia_rotation": [0, 0, 0, 1]}

    def status(self):
        return dict(contact_mode="control", contact_bytes=100, trace_bytes=200,
                    contact_records=1, collision_records=0, contact_window_start_ns=self.start,
                    contact_window_end_ns=self.end, contact_activation_ns=self.start+1,
                    contact_total_ns=0, contact_max_ns=0, contact_pair_counts=[0]*4,
                    heartbeat_monotonic_ns=self.end+1)

    def test_window_identity_timing_and_bounds(self):
        state = self.status()
        check_status(state, "control", self.start, self.end, self.end, closed=True)
        for changes, start in [({}, None), ({"contact_activation_ns": self.start-1}, self.start),
                               ({"contact_activation_ns": self.start+3_000_000_001}, self.start),
                               ({"contact_window_end_ns": self.end+1}, self.start),
                               ({"contact_bytes": 1024**3}, self.start),
                               ({"contact_pair_counts": [0, 0, 0, -1]}, self.start),
                               ({"contact_mode": "treatment"}, self.start)]:
            with self.subTest(changes=changes, start=start), self.assertRaises(RuntimeError):
                check_status(dict(state, **changes), "control", start, self.end, self.end, closed=True)

    def test_pending_window_and_atomic_request(self):
        state = dict(self.status(), contact_records=0, contact_activation_ns=0,
                     contact_window_start_ns=0, contact_window_end_ns=0)
        check_status(state, "control", None, None, self.start)
        check_status(state, "control", self.start, self.end, self.start+1)
        with self.assertRaises(RuntimeError):
            check_status(state, "control", self.start, self.end, self.start+3_000_000_001)
        item = write_window_request(self.root, 100, "control", self.start, self.end)
        data = Path(item["path"]).read_bytes()
        self.assertEqual(data, b"contact-window-v1\n100\ncontrol\n10000000000\n70000000000\n")
        self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
        with self.assertRaises(ValueError):
            write_window_request(self.root, 100, "control", self.start, self.end)

    def trace(self, floor=False):
        ids = [1, 2, 3, 4]
        header = dict(kind="contact_binding", schema=1, pid=100, mode="control",
                      clock="Linux CLOCK_MONOTONIC", wheel_mesh_ids=ids, track_id=5,
                      colliders=[dict(id=i, path=p, type="MeshCollider", enabled=True, trigger=False)
                                 for i, p in zip([*ids, 5], [*TARGETS, TRACK])], properties=self.properties)
        activation = dict(kind="window_activation", index=0, monotonic_ns=self.start+1,
                          start_ns=self.start, end_ns=self.end, mode="control",
                          before_ignored=[False]*4, after_ignored=[False]*4, properties=self.properties)
        collision = dict(kind="collision", index=1, monotonic_ns=self.start+2,
                         phase="stay", impulse=[0, 1, 0], other_id=5, relative_velocity=[0, 0, 0],
                         points=[dict(a=i, b=5, separation=-.001, normal=[0, 1, 0], point=[0, 0, 0]) for i in ids])
        if floor:
            header.update(schema=2, target_profile="floor", inertia_policy="intervention-local")
            for c in header["colliders"]:
                c.update(attached_body_id=0 if c["id"] == 5 else 99, convex=None if c["id"] == 5 else True)
            header["colliders"][-1].update(path="Floor", type="BoxCollider")
            activation.update(target_profile="floor", before_properties=copy.deepcopy(self.properties), after_properties=copy.deepcopy(self.properties))
        return [header, activation, collision]

    def analyze_fixture(self, rows, floor=False):
        data = "".join(json.dumps(r)+"\n" for r in rows)
        (self.root / "contacts.jsonl").write_text(data)
        status = dict(self.status(), contact_bytes=len(data.encode()), contact_records=2,
                      collision_records=1, contact_pair_counts=[1]*4)
        if floor: status.update(contact_target="floor", inertia_policy="intervention-local")
        (self.root / "status.json").write_text(json.dumps(status))
        run = dict(observation_start_ns=self.start, diagnostic_deadline_ns=self.end, contact_mode="control")
        if floor: run["contact_target"] = "floor"
        kinematics = dict(binding={"pid": 100}, phases={p: {"contact_state": dict(
            properties_constant=not floor, mass_com_constant=True, first_properties=self.properties)} for p in ("FixedUpdate", "LateUpdate")})
        return analyze_contacts(self.root, run, kinematics)

    def test_contact_identity_and_window_counts(self):
        result = self.analyze_fixture(self.trace())
        self.assertEqual(result["window_target_points"], dict.fromkeys(TARGETS, 1))
        self.assertTrue(result["properties_constant"])
        self.assertEqual(result["window_collision_phases"], {"stay": 1})
        self.assertEqual(result["activation_delay_ms"], .000001)

    def test_contact_loss_wrong_binding_and_nonfinite_rejected(self):
        for mutation in ("loss", "binding", "nan", "ignore", "clock"):
            rows = self.trace()
            if mutation == "loss": rows[-1]["index"] = 2
            elif mutation == "binding": rows[0]["colliders"][0]["path"] = "different wheel"
            elif mutation == "nan": rows[-1]["points"][0]["separation"] = float("nan")
            elif mutation == "ignore": rows[1]["after_ignored"][0] = True
            else: rows[0]["clock"] = "wall clock"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.analyze_fixture(rows)

    def controls(self, floor=False):
        player = self.root / "player" / "AutoDRIVE.x86_64"
        for name in (player.name, "GameAssembly.so", "UnityPlayer.so", "AutoDRIVE_Data/level0",
                     "AutoDRIVE_Data/globalgamemanagers", "AutoDRIVE_Data/sharedassets0.assets"):
            path = player.parent / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
        evidence = self.root / "raw.json"
        evidence.write_text('{"source":"fixture"}')
        contact = self.analyze_fixture(self.trace(floor), floor)
        runs = []
        for index in (1, 2):
            runs.append(dict(run=f"run-{index:02d}", contact_mode="control", error=None,
                completed_diagnostic_window=True, contact_analysis=copy.deepcopy(contact),
                children=[dict(exit_code=0, reaped=True) for _ in range(3)], endpoint_released=True,
                bridge_status={"errors": []}, recorded_message_counts=dict.fromkeys(
                    ("throttle", "steering", "left_encoder", "right_encoder", "ips", "imu", "lidar", "front_camera"), 1),
                player_identity=player_identity(player), kinematics_analysis={"binding": {"pid": 100+index}}))
        analysis = dict(attempt={"contact_mode": "control"}, runs=runs, results_path=str(self.root),
                        source_sha256={"raw.json": hashlib.sha256(evidence.read_bytes()).hexdigest()})
        if floor:
            analysis["attempt"]["contact_target"] = "floor"
            for r in runs: r["contact_target"] = "floor"
        source = self.root / "analysis.json"
        source.write_text(json.dumps(analysis))
        return analysis, source, player

    def test_two_complete_controls_enable_treatment(self):
        analysis, source, player = self.controls()
        gate = make_gate(analysis, source)
        self.assertTrue(gate["eligible"], gate["reasons"])
        self.assertFalse(gate["p0_accepted"])
        path = self.root / "gate.json"
        path.write_text(json.dumps(gate))
        self.assertEqual(verify_gate(path, player), gate)

    def test_incomplete_or_inconsistent_controls_disable_treatment(self):
        analysis, source, _ = self.controls()
        for mutation in ("missing_pair", "incomplete", "properties", "same_pid", "player", "exit", "transport"):
            altered = copy.deepcopy(analysis); r = altered["runs"][1]
            if mutation == "missing_pair": r["contact_analysis"]["window_target_points"][TARGETS[0]] = 0
            elif mutation == "incomplete": r["completed_diagnostic_window"] = False
            elif mutation == "properties": r["contact_analysis"]["properties"]["mass"] = 4
            elif mutation == "same_pid": r["kinematics_analysis"]["binding"]["pid"] = 101
            elif mutation == "player": r["player_identity"]["GameAssembly.so"] = "different"
            elif mutation == "exit": r["children"][0]["exit_code"] = 1
            else: r["recorded_message_counts"]["lidar"] = 0
            with self.subTest(mutation=mutation):
                self.assertFalse(make_gate(altered, source)["eligible"])

    def test_modified_raw_evidence_blocks_treatment(self):
        analysis, source, player = self.controls()
        gate = self.root / "gate.json"
        gate.write_text(json.dumps(make_gate(analysis, source)))
        (self.root / "raw.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "raw evidence changed"):
            verify_gate(gate, player)


    def test_floor_gate_allows_natural_inertia_but_not_property_faults(self):
        analysis, source, player = self.controls(floor=True)
        analysis["runs"][1]["contact_analysis"]["properties"]["inertia_tensor"] = [.11, .21, .31]
        source.write_text(json.dumps(analysis))
        gate = make_gate(analysis, source)
        self.assertTrue(gate["eligible"], gate["reasons"])
        path = self.root / "gate.json"; path.write_text(json.dumps(gate))
        self.assertEqual(verify_gate(path, player, "floor"), gate)
        with self.assertRaisesRegex(ValueError, "target differs"):
            verify_gate(path, player, "proto-track")
        for field, value in (("mass_com_constant", False), ("immediate_properties_equal", False)):
            altered = copy.deepcopy(analysis)
            altered["runs"][1]["contact_analysis"][field] = value
            self.assertFalse(make_gate(altered, source)["eligible"])
        altered = copy.deepcopy(analysis)
        altered["runs"][1]["contact_analysis"]["properties"]["center_of_mass"][0] = .1
        self.assertFalse(make_gate(altered, source)["eligible"])
        altered = copy.deepcopy(analysis)
        altered["runs"][1]["contact_analysis"]["binding"]["target_profile"] = "proto-track"
        self.assertFalse(make_gate(altered, source)["eligible"])

    def test_floor_immediate_difference_recorded_and_type_rejected(self):
        rows = self.trace(True)
        rows[1]["after_properties"]["inertia_tensor"][0] += .01
        self.assertFalse(self.analyze_fixture(rows, True)["immediate_properties_equal"])
        for field, value in (("type", "MeshCollider"), ("attached_body_id", 99), ("trigger", True)):
            rows = self.trace(True); rows[0]["colliders"][-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.analyze_fixture(rows, True)

    def test_floor_request_and_status_are_profile_bound(self):
        item = write_window_request(self.root, 100, "treatment", self.start, self.end, "floor")
        self.assertEqual(Path(item["path"]).read_text(), "contact-window-v2\n100\ntreatment\nfloor\n10000000000\n70000000000\n")
        state = dict(self.status(), contact_target="floor", inertia_policy="intervention-local")
        check_status(state, "control", self.start, self.end, self.end, target="floor")
        with self.assertRaises(RuntimeError):
            check_status(state, "control", self.start, self.end, self.end)
        with self.assertRaises(RuntimeError):
            check_status(self.status(), "control", self.start, self.end, self.end, target="floor")

    def test_proto_controls_cannot_authorize_floor(self):
        analysis, source, player = self.controls()
        path = self.root / "gate.json"; path.write_text(json.dumps(make_gate(analysis, source)))
        with self.assertRaisesRegex(ValueError, "target differs"):
            verify_gate(path, player, "floor")


if __name__ == "__main__":
    unittest.main()
