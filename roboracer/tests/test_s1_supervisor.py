"""S1 supervisor skeleton: validation order, expiry from generation, runner lease, the real
process over its sockets, and the bridge's request client. No simulator, no ROS.
Run with the AVLite interpreter: ``<avlite python> -m unittest discover -s roboracer/tests -t .``
"""

import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from roboracer.tests.test_s1_01_plugin import probe

PLUGIN = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("supervisor_core", PLUGIN / "runtime/supervisor_core.py")
core_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core_module
spec.loader.exec_module(core_module)
Limits, SupervisorCore = core_module.Limits, core_module.SupervisorCore

MS = 1_000_000
NOW = 10_000 * MS


def request(seq=1, gen=NOW - 50 * MS, speed=0.0, steer=0.0, telemetry=7, stamp=NOW - 200 * MS, origin="avlite"):
    return {"origin": origin, "seq": seq, "gen_ns": gen, "target_speed": speed, "steer": steer,
            "observation": {"telemetry_seq": telemetry, "stamp_ns": stamp}}


def active():
    s = SupervisorCore(origin="sup-1")
    s.heartbeat(1, NOW - 100 * MS)
    return s


class CoreTests(unittest.TestCase):
    def test_zero_request_forwarded_with_original_generation(self):
        s = active()
        d = s.submit(request(), NOW)
        self.assertTrue(d.accepted)
        self.assertEqual({"origin": "sup-1", "seq": 1, "gen_ns": NOW - 50 * MS, "deadline_ns": NOW + 450 * MS,
                          "throttle": "0", "steering": "0", "inputs": "avlite.1.t7"}, d.forward)
        self.assertEqual(2, s.submit(request(seq=2), NOW).forward["seq"])

    def test_requires_runner_and_lease_is_sticky(self):
        s = SupervisorCore(origin="sup-1")
        self.assertEqual("no-runner", s.submit(request(), NOW).reason)
        s.heartbeat(1, NOW)
        self.assertEqual("heartbeat sequence not increasing", s.heartbeat(1, NOW))
        self.assertIsNone(s.tick(NOW + 500 * MS))
        self.assertEqual("inhibited", s.tick(NOW + 501 * MS))
        s.heartbeat(2, NOW + 600 * MS)  # a late heartbeat does not re-enable forwarding
        self.assertEqual("inhibited", s.submit(request(gen=NOW + 590 * MS, stamp=NOW + 500 * MS), NOW + 600 * MS).reason)

    def test_validation_order(self):
        cases = [
            ("malformed", {"seq": 1}),
            ("malformed", dict(request(), seq=True)),
            ("malformed", dict(request(), origin="bad origin")),
            ("malformed", dict(request(), steer="0")),
            ("non-finite", request(speed=float("nan"))),
            ("future-request", request(gen=NOW + 1)),
            ("stale-request", request(gen=NOW - 501 * MS)),
            ("observation-identity", request(telemetry=0)),
            ("stale-observation", request(stamp=NOW - 501 * MS)),
            ("future-observation", request(stamp=NOW + 101 * MS)),
            ("limit", request(speed=0.1)),
            ("limit", request(speed=-0.0001)),
            ("limit", request(steer=0.6)),
            ("motion-not-authorized", request(steer=0.1)),
        ]
        for index, (reason, message) in enumerate(cases, start=1):
            s = active()
            if isinstance(message.get("seq"), int) and not isinstance(message.get("seq"), bool):
                message = dict(message, seq=index)
            with self.subTest(reason=reason, message=message):
                d = s.submit(message, NOW)
                self.assertEqual((False, reason, None), (d.accepted, d.reason, d.forward))

    def test_sequence_and_origin(self):
        s = active()
        s.submit(request(seq=5), NOW)
        self.assertEqual("duplicate", s.submit(request(seq=5), NOW).reason)
        self.assertEqual("out-of-order", s.submit(request(seq=4), NOW).reason)
        self.assertEqual("origin", s.submit(request(seq=6, origin="other"), NOW).reason)
        self.assertEqual("non-finite", s.submit(request(seq=7, steer=float("inf")), NOW).reason)
        self.assertEqual("duplicate", s.submit(request(seq=7), NOW).reason)  # a failed seq is consumed
        self.assertTrue(s.submit(request(seq=8), NOW).accepted)

    def test_motion_cannot_be_authorized_and_life_is_bounded(self):
        with self.assertRaises(ValueError):
            Limits(motion_authorized=True)
        with self.assertRaises(ValueError):
            Limits(request_life_ns=1_000_000_001)


class ProcessTests(unittest.TestCase):
    def test_process_forwards_inhibits_and_exits_cleanly(self):
        tag = f"rr-test-{os.getpid()}-{time.monotonic_ns()}"
        target = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        target.bind("\0" + tag + "-target")
        target.settimeout(2.0)
        self.addCleanup(target.close)
        with tempfile.TemporaryDirectory() as scratch:
            status, trace = Path(scratch, "status.json"), Path(scratch, "trace.jsonl")
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "roboracer.runtime.supervisor_process", "--name", tag,
                 "--target", tag + "-target", "--origin", "sup-1", "--status", str(status), "--trace", str(trace)],
                cwd=PLUGIN.parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 30
                while not status.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                self.addCleanup(sender.close)

                def send(message):
                    sender.sendto(json.dumps(message).encode(), "\0" + tag)

                send({"kind": "heartbeat", "seq": 1})
                now = time.monotonic_ns()
                send(dict(request(seq=1, gen=now, stamp=now - 100 * MS), kind="request"))
                forwarded = json.loads(target.recv(4096))
                self.assertEqual(("sup-1", 1, now, now + 500 * MS, "0", "0", "avlite.1.t7"),
                                 tuple(forwarded[k] for k in ("origin", "seq", "gen_ns", "deadline_ns", "throttle",
                                                              "steering", "inputs")))
                send(dict(request(seq=2, gen=now, steer=0.2, stamp=now), kind="request"))
                sender.sendto(b"not json", "\0" + tag)
                send({"kind": "request", "seq": 9})
                time.sleep(0.8)  # runner silent beyond the 500 ms lease
                now = time.monotonic_ns()
                send(dict(request(seq=3, gen=now, stamp=now), kind="request"))
                time.sleep(0.3)
            finally:
                process.send_signal(signal.SIGTERM)
                out, err = process.communicate(timeout=10)
            self.assertEqual(0, process.returncode, err)
            final = json.loads(status.read_text())
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            decisions = [r["decision"] for r in rows if r["event"] == "request"]
            self.assertEqual(["forwarded", "motion-not-authorized", "malformed", "inhibited"], decisions)
            self.assertIn({"event": "state", "state": "inhibited", "reason": "runner-lease-expired"},
                          [{k: r[k] for k in ("event", "state", "reason")} for r in rows if r["event"] == "state"])
            self.assertEqual(("inhibited", 1, 1), (final["state"], final["io"]["sent"], final["io"]["malformed_json"]))


class BridgeClientTests(unittest.TestCase):
    def test_bridge_sends_each_command_once_with_tick_snapshot_identity(self):
        r = probe("s1-supervisor-client")
        self.assertEqual("no_observation", r["before_snapshot"])
        first = r["requests"][0]
        self.assertEqual(("request", "avlite", 1, 0.0, 0.0), tuple(first[k] for k in ("kind", "origin", "seq",
                                                                                          "target_speed", "steer")))
        self.assertEqual(2, first["observation"]["telemetry_seq"])
        self.assertEqual(r["generated"][0], first["gen_ns"])
        self.assertEqual(1, r["io"]["held_resend"])
        # Frame 3 committed mid-tick: pose and the next request still use the tick's frame 2.
        self.assertEqual([0.741, 3.158], r["ego_mid_tick"])
        self.assertEqual(2, r["requests"][1]["observation"]["telemetry_seq"])
        self.assertEqual(3, r["requests"][2]["observation"]["telemetry_seq"])  # after the next tick
        self.assertEqual({"sent": 3, "refused": 0, "dropped": 0, "held_resend": 1, "no_observation": 1}, r["io"])


if __name__ == "__main__":
    unittest.main()
