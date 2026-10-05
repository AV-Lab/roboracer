"""S1-02: coherent observation snapshots, scan conversion and the bridge observation surface.

Analytical fixtures (synthetic messages), a replay of the recorded SIM1-02 topic traces when the
evidence is present, and bridge cases in fresh isolated AVLite processes. Run with the AVLite
interpreter: ``<avlite python> -m unittest discover -s roboracer/tests -t .``
"""

import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

from roboracer.tests import s1_02_fixtures as fx
from roboracer.tests.test_s1_01_plugin import probe

PLUGIN = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("autodrive_observation", PLUGIN / "integration/autodrive_observation.py")
obs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = obs  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(obs)
EVIDENCE = Path("/home/a2rl/Workspace/roboracer/artifacts/simulator-build/20261005T063753Z-sim1-02")


class ScanConversionTests(unittest.TestCase):
    def test_beam_geometry_follows_vendor_convention(self):
        ranges = [math.inf] * 1081
        ranges[0], ranges[540], ranges[1080], ranges[900] = 1.0, 2.0, 3.0, 4.0  # -135, 0, +135, +90 deg
        points = obs.scan_points(ranges)
        self.assertEqual((4, 4), points.shape)
        self.assertEqual("float32", str(points.dtype))
        expected = [(math.cos(math.radians(-135)), math.sin(math.radians(-135))), (2.0, 0.0),
                    (4 * math.cos(math.radians(90)), 4.0), (3 * math.cos(math.radians(135)), 3 * math.sin(math.radians(135)))]
        for row, (x, y) in zip(points, expected):
            self.assertAlmostEqual(row[0], x, places=5)
            self.assertAlmostEqual(row[1], y, places=5)
            self.assertEqual((row[2], row[3]), (0.0, 0.0))

    def test_out_of_range_beams_dropped(self):
        ranges = [0.05, 0.06, 10.0, 10.5, math.inf] + [math.inf] * 1076
        self.assertEqual(2, len(obs.scan_points(ranges)))

    def test_recorded_quaternion_gives_scene_heading(self):
        self.assertAlmostEqual(-math.pi / 2, obs.yaw_from_quaternion(0.011, 0.011, -0.707, 0.707), places=2)


class AssemblerTests(unittest.TestCase):
    def setUp(self):
        self.a = obs.SnapshotAssembler()

    def test_coherent_frame_commits_with_monotonic_stamps_and_mounts(self):
        snaps = fx.deliver(self.a, *fx.frame(2), now_ns=7)
        self.assertEqual(1, len(snaps))
        s = snaps[0]
        self.assertEqual((fx.SESSION, 1, 2), (s.session, s.episode, s.telemetry_seq))
        record = json.loads(fx.frame(2)[1])
        self.assertAlmostEqual((record["sources"]["lidar"]["mono_end_ns"] - fx.OFFSET_NS) / 1e9, s.lidar.stamp)
        self.assertAlmostEqual(fx.BOUND_NS / 1e9, s.clock_bound_s)
        self.assertEqual([0.2733, 0.0, 0.096], s.lidar.base_to_sensor[:3, 3].tolist())
        self.assertEqual([0.08, 0.0, 0.055], s.imu.base_to_sensor[:3, 3].tolist())
        self.assertEqual("ground-truth", s.pose.label)
        self.assertEqual((0.741, 3.158, 0.059), (s.pose.x, s.pose.y, s.pose.z))
        self.assertAlmostEqual(0.017, s.scan_pose_skew_s)
        self.assertEqual(1081, len(s.lidar.points))
        self.assertEqual({}, self.a.rejections)

    def test_provenance_arriving_before_members_still_commits(self):
        snaps = fx.deliver(self.a, *fx.frame(2), provenance_first=True)
        self.assertEqual(1, len(snaps))
        self.assertEqual(0, self.a.dropped)

    def test_first_frame_without_clock_is_rejected(self):
        self.assertEqual([], fx.deliver(self.a, *fx.frame(1, basis="bridge-publication")))
        self.assertEqual({"stamp basis is not acquisition (no clock exchange yet)": 1}, self.a.rejections)
        self.assertEqual(1, len(fx.deliver(self.a, *fx.frame(2))))  # leftovers dropped, next frame clean

    def test_member_proven_missing_rejects_and_resynchronises(self):
        messages, provenance = fx.frame(2)
        self.assertEqual([], fx.deliver(self.a, messages, provenance, skip=("lidar",)))
        self.assertEqual(1, len(self.a.pending))  # waits: the scan may be late
        snaps = fx.deliver(self.a, *fx.frame(3))  # a newer scan proves frame 2's is missing
        self.assertEqual([3], [s.telemetry_seq for s in snaps])
        self.assertEqual({"stamp mismatch": 1}, self.a.rejections)
        self.assertGreater(self.a.dropped, 0)

    def test_incomplete_frame_times_out(self):
        messages, provenance = fx.frame(2)
        fx.deliver(self.a, messages, provenance, skip=("ips",), now_ns=0)
        self.assertEqual([], self.a.offer("left_encoder", fx.frame(9)[0]["left_encoder"], obs.PENDING_LIMIT_NS + 1))
        self.assertEqual({"incomplete frame": 1}, self.a.rejections)
        self.assertEqual(0, len(self.a.pending))

    def test_ips_value_mismatch_never_commits(self):
        messages, provenance = fx.frame(2)
        messages["ips"].x += 0.001
        self.assertEqual([], fx.deliver(self.a, messages, provenance))
        self.assertEqual(1, len(self.a.pending))

    def test_identity_rules(self):
        fx.deliver(self.a, *fx.frame(5))
        self.assertEqual([], fx.deliver(self.a, *fx.frame(5)))
        record = json.loads(fx.frame(6)[1])
        record["session"] = "0" * 32
        self.assertEqual([], self.a.offer_provenance(json.dumps(record), 0))
        self.assertEqual([], fx.deliver(self.a, *fx.frame(7, episode=0)))
        self.assertEqual([], self.a.offer_provenance("not json", 0))
        self.assertEqual({"telemetry sequence not increasing": 1, "session changed": 1, "episode moved backwards": 1,
                          "malformed provenance": 1}, self.a.rejections)

    def test_episode_increase_accepted(self):
        fx.deliver(self.a, *fx.frame(2))
        self.assertEqual([2], [s.episode for s in fx.deliver(self.a, *fx.frame(3, episode=2))])

    def test_reading_and_layout_checks(self):
        cases = {"scan/pose skew": fx.frame(2, lidar_lag_s=0.2),
                 "non-finite reading": fx.frame(3, encoder=math.nan),
                 "scan layout differs from the qualified convention": fx.frame(4, ranges=[1.0] * 1080)}
        for reason, (messages, provenance) in cases.items():
            self.assertEqual([], fx.deliver(self.a, messages, provenance), reason)
        self.assertEqual(set(cases), set(self.a.rejections))
        self.assertEqual(1, len(fx.deliver(self.a, *fx.frame(5))))


@unittest.skipUnless((EVIDENCE / "observe/run-01/ros-messages.jsonl").is_file(), "SIM1-02 evidence not present")
class RecordedReplayTests(unittest.TestCase):
    """Replays recorded arrival order and header stamps. The recorded traces hold range hashes
    only, so scans are placeholders; IPS values come from the bridge frame trace (the runner
    now publishes them in the provenance message)."""

    def replay(self, run):
        directory = EVIDENCE / run
        positions = {}
        for line in (directory / "bridge-frames.jsonl").open():
            row = json.loads(line)
            if "provenance" in row:
                positions[row["provenance"]["telemetry_seq"]] = row["motion"]["Position"]
        a, snaps, provenance_count = obs.SnapshotAssembler(), [], 0
        for line in (directory / "ros-messages.jsonl").open():
            row = json.loads(line)
            topic, now = row["topic"], row["received_monotonic_ns"]
            if topic == "provenance":
                record = dict(row["data"], ips_position=positions[row["data"]["telemetry_seq"]])
                provenance_count += 1
                snaps += a.offer_provenance(json.dumps(record), now)
            elif topic in obs.TOPICS:
                message = fx.NS(x=row["position"][0], y=row["position"][1], z=row["position"][2]) if topic == "ips" \
                    else self.message(topic, row)
                snaps += a.offer(topic, message, now)
        return a, snaps, provenance_count

    @staticmethod
    def message(topic, row):
        h = fx.header(row["stamp_ns"], row["frame"])
        if topic == "lidar":
            return fx.NS(header=h, ranges=[5.0] * row["count"], angle_min=row["angle_min"],
                         angle_increment=row["angle_increment"])
        if topic == "imu":
            return fx.NS(header=h, orientation=fx.NS(**dict(zip("xyzw", row["orientation"]))),
                         angular_velocity=fx.NS(**dict(zip("xyz", row["angular_velocity"]))),
                         linear_acceleration=fx.NS(**dict(zip("xyz", row["linear_acceleration"]))))
        return fx.NS(header=h, position=row["position"])

    def test_recorded_runs_commit_every_frame_after_the_first(self):
        for run in ("observe/run-01", "observe/run-02"):
            a, snaps, count = self.replay(run)
            with self.subTest(run=run):
                self.assertEqual({"stamp basis is not acquisition (no clock exchange yet)": 1}, a.rejections)
                self.assertEqual(count - 1, len(snaps))
                self.assertEqual(list(range(2, count + 1)), [s.telemetry_seq for s in snaps])
                self.assertLessEqual(max(s.scan_pose_skew_s for s in snaps), 0.06)
                self.assertTrue(all(abs(s.pose.yaw + math.pi / 2) < 0.01 for s in snaps))


class BridgeTests(unittest.TestCase):
    def test_bridge_observation_surface(self):
        r = probe("s1-02-bridge")
        self.assertEqual(["IMU", "LIDAR_2D"], r["world_capabilities"])
        self.assertEqual({"default": [], "gt_enabled": ["LOCALIZATION"]}, r["stack_capabilities"])
        self.assertEqual({"lidar_points": None, "imu": None}, r["before"])
        after = r["after"]
        self.assertEqual(1081, after["lidar_points"])
        self.assertEqual([0.2733, 0.0, 0.096], after["lidar_mount"])
        self.assertTrue(after["fresh_objects"])
        self.assertEqual({"default": [0.0, 0.0], "gt_enabled": [0.741, 3.158]}, after["ego_xy"])
        self.assertAlmostEqual(-math.pi / 2, after["gt_theta"], places=2)
        self.assertEqual(1, after["committed"])
        self.assertEqual(r["watched_modules"], [])


if __name__ == "__main__":
    unittest.main()
