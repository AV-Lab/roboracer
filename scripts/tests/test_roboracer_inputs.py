"""S2-03: input recording format, bounds, and open-loop replay through the plugin's own code.

Encoding tests run in-process (no AVLite). Replay tests import the plugin through AVLite's loader,
so they run in fresh processes with throw-away AVLite/XDG directories (as the plugin tests do).
Run with the AVLite interpreter.
"""

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parent
PLUGIN = REPO / "roboracer"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(PLUGIN / "tests"))
import roboracer_inputs as ri  # noqa: E402
import s1_02_fixtures as fx  # noqa: E402

ROUNDTRIP = r'''
import json, sys, time
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import roboracer_inputs as ri, s1_02_fixtures as fx
plugin = ri.load_plugin(Path(sys.argv[3]))
out = Path(sys.argv[4])
bridge = plugin.AutoDriveBridge()
committed = []
bridge.snapshot_listener = committed.append
recorder = ri.InputRecorder(out)
bridge.message_listener = recorder
ranges = [0.5 + 0.004 * i for i in range(1081)]
for seq in range(1, 6):
    messages, provenance = fx.frame(seq, ranges=ranges, encoder=0.1 * seq)
    for name, message in messages.items():
        bridge._offer(name, message)
    bridge._offer("provenance", NS(data=provenance))
recorder.close()
head, records = ri.read_recording(out)
snapshots, assembly = ri.replay_snapshots(records, plugin)
live = [ri.snapshot_row(s) for s in committed]
print(json.dumps({"committed": len(committed), "messages": recorder.stats["messages"],
                  "comparison": ri.compare_snapshots(snapshots, live), "assembly": assembly}))
'''


def isolated(args):
    with tempfile.TemporaryDirectory() as scratch:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AVLITE_", "XDG_"))}
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=f"{scratch}/mpl",
                   **{name: f"{scratch}/{name.lower()}" for name in (
                       "AVLITE_CONFIG_DIR", "AVLITE_PLUGINS_DIR", "AVLITE_DATA_DIR",
                       "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")})
        result = subprocess.run([sys.executable, "-B", *[a.replace("{scratch}", scratch) for a in args]],
                                env=env, cwd=scratch, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise AssertionError(f"{args[0]} failed:\n{result.stdout[-2000:]}\n{result.stderr[-3000:]}")
        return json.loads(result.stdout.strip().splitlines()[-1])


class EncodingTests(unittest.TestCase):
    def test_every_topic_round_trips_the_fields_the_assembler_reads(self):
        ranges = [0.06 + 0.009 * i for i in range(1080)] + [math.inf]
        messages, provenance = fx.frame(3, ranges=ranges, encoder=1.25)
        for topic, message in messages.items():
            record = json.loads(json.dumps(ri.encode(topic, message, 123)))
            name, back, t = ri.decode(record)
            self.assertEqual((topic, 123), (name, t))
            if topic == "ips":
                self.assertEqual([message.x, message.y, message.z], [back.x, back.y, back.z])
                continue
            self.assertEqual((message.header.stamp.sec, message.header.stamp.nanosec, message.header.frame_id),
                             (back.header.stamp.sec, back.header.stamp.nanosec, back.header.frame_id))
            if topic == "lidar":
                import numpy as np
                self.assertEqual(np.asarray(ranges, dtype=np.float32).tobytes(), back.ranges.tobytes())
                self.assertEqual((message.angle_min, message.angle_increment), (back.angle_min, back.angle_increment))
            elif topic == "imu":
                self.assertEqual(message.orientation.w, back.orientation.w)
                self.assertEqual(message.linear_acceleration.z, back.linear_acceleration.z)
            else:
                self.assertEqual(list(message.position), back.position)
        record = ri.encode("provenance", type("S", (), {"data": provenance})(), 7)
        self.assertEqual(provenance, ri.decode(record)[1].data)

    def test_unknown_topic_refused(self):
        with self.assertRaises(ValueError):
            ri.encode("camera", object(), 0)

    def test_recording_is_bounded_and_marked_truncated(self):
        messages, _ = fx.frame(1)
        with tempfile.TemporaryDirectory() as d:
            recorder = ri.InputRecorder(Path(d) / "in.jsonl", max_bytes=9_000)
            for _ in range(5):
                recorder("lidar", messages["lidar"], 1)  # ~5.9 kB each
            recorder.close()
            self.assertTrue(recorder.stats["truncated"])
            self.assertEqual(1, recorder.stats["messages"])
            self.assertLessEqual(Path(recorder.stats["path"]).stat().st_size, 9_000)
            head, records = ri.read_recording(recorder.stats["path"])
            self.assertEqual(ri.SCHEMA, head["schema"])
            self.assertEqual(1, len(records))

    def test_recorder_never_raises_into_the_bridge(self):
        with tempfile.TemporaryDirectory() as d:
            recorder = ri.InputRecorder(Path(d) / "in.jsonl")
            recorder("lidar", object(), 1)  # unencodable
            recorder.close()
            recorder("ips", fx.frame(1)[0]["ips"], 2)  # after close: ignored
            self.assertEqual((1, 0), (recorder.stats["errors"], recorder.stats["messages"]))

    def test_existing_recording_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "in.jsonl").write_text("x")
            with self.assertRaises(FileExistsError):
                ri.InputRecorder(Path(d) / "in.jsonl")


class ReplayTests(unittest.TestCase):
    def test_bridge_hook_recording_replays_to_identical_snapshots(self):
        r = isolated(["-c", ROUNDTRIP, str(SCRIPTS), str(PLUGIN / "tests"), str(PLUGIN), "{scratch}/in.jsonl"])
        self.assertEqual(5, r["committed"])
        self.assertEqual(30, r["messages"])  # 5 frames x (5 sensor topics + provenance)
        self.assertTrue(r["comparison"]["exact"], r["comparison"])
        self.assertEqual(5, r["comparison"]["replayed"])

    def test_analytical_fixtures_pass_in_three_fresh_processes(self):
        outputs = []
        for _ in range(3):
            r = isolated([str(SCRIPTS / "roboracer_inputs.py"), "fixtures", "--plugin", str(PLUGIN),
                          "--output", "{scratch}/fixtures.json"])
            self.assertTrue(r["pass"])
            outputs.append(r)
        self.assertEqual(outputs[0], {**outputs[0], "pass": True})


if __name__ == "__main__":
    unittest.main()
