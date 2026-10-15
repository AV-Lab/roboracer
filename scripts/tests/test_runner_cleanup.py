"""D28 A: runner heartbeats from a dedicated thread, gated on main-loop progress. D29 A: cleanup order."""
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_neutral import RunnerHeartbeat, cleanup_order


class Clock:
    def __init__(self):
        self.ns = 1_000_000_000

    def __call__(self):
        return self.ns

    def advance(self, s):
        self.ns += int(round(s * 1e9))


class RunnerHeartbeatTests(unittest.TestCase):
    def make(self, enabled=lambda: True):
        self.clock = Clock()
        return RunnerHeartbeat(lambda: None, enabled, clock=self.clock)

    def test_no_beat_before_first_progress(self):
        hb = self.make()
        self.assertFalse(hb.tick())
        self.assertEqual(hb.withheld, 1)

    def test_short_loop_stall_keeps_beating(self):
        # r2 F2-10: the loop stalled about 0.5 s; beats now continue for 0.3 s of it, so the 500 ms
        # lease (last beat at +0.3 s) survives a stall of up to about 0.8 s.
        hb = self.make()
        hb.progress()
        for _ in range(3):
            self.clock.advance(0.1)
            self.assertTrue(hb.tick())
        self.clock.advance(0.1)
        self.assertFalse(hb.tick())
        self.clock.advance(0.1)
        hb.progress()
        self.assertTrue(hb.tick())
        self.assertAlmostEqual(hb.summary()["max_main_loop_gap_s"], 0.5)

    def test_hung_loop_stops_beats_within_window(self):
        hb = self.make()
        hb.progress()
        self.clock.advance(0.31)
        self.assertFalse(hb.tick())
        self.clock.advance(5)
        self.assertFalse(hb.tick())
        self.assertEqual(hb.sent, 0)

    def test_disabled_or_paused_sends_nothing(self):
        state = {"connected": False, "paused": False}
        hb = self.make(lambda: state["connected"] and not state["paused"])
        hb.progress()
        self.assertFalse(hb.tick())  # before Connect
        state["connected"] = True
        self.assertTrue(hb.tick())
        state["paused"] = True  # F1-7: stops immediately, despite fresh progress
        hb.progress()
        self.assertFalse(hb.tick())
        self.assertEqual(hb.withheld, 0)

    def test_stop_ends_beats(self):
        hb = self.make()
        hb.progress()
        hb.stop()
        self.assertFalse(hb.tick())

    def test_thread_beats_and_stops(self):
        sent = []
        hb = RunnerHeartbeat(lambda: sent.append(1), lambda: True, period_s=0.02).start()
        end = time.monotonic() + 0.25
        while time.monotonic() < end:
            hb.progress()
            time.sleep(0.01)
        hb.stop()
        self.assertFalse(hb.thread.is_alive())
        count = len(sent)
        self.assertGreater(count, 5)
        time.sleep(0.06)
        self.assertEqual(len(sent), count)

    def test_thread_records_error_and_stops(self):
        def boom():
            raise ValueError("x")
        hb = RunnerHeartbeat(boom, lambda: True, period_s=0.01)
        hb.progress()
        hb.start().thread.join(timeout=1)
        self.assertFalse(hb.thread.is_alive())
        self.assertEqual(hb.summary()["error"], "ValueError: x")


class CleanupOrderTests(unittest.TestCase):
    def test_bridge_stopped_directly_before_player(self):
        spawned = ["bridge", "supervisor-1", "plugin-stack", "observer", "plugin-observer", "player", "recorder"]
        self.assertEqual(cleanup_order(spawned, label=lambda c: c),
                         ["recorder", "bridge", "player", "plugin-observer", "observer", "plugin-stack", "supervisor-1"])

    def test_reverse_order_without_player_or_bridge(self):
        self.assertEqual(cleanup_order(["bridge", "observer"], label=lambda c: c), ["observer", "bridge"])
        self.assertEqual(cleanup_order(["observer", "player"], label=lambda c: c), ["player", "observer"])


if __name__ == "__main__":
    unittest.main()
