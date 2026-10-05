"""S1 supervisor process: ``python -m roboracer.runtime.supervisor_process --name ... --target ...``.

Import-safe (the AVLite loader imports every plugin module): only ``main()`` opens sockets.

Input (one Linux abstract datagram socket, ``\\0<name>``), JSON messages:
  {"kind": "heartbeat", "seq": n}                         from the runner
  {"kind": "request", "origin", "seq", "gen_ns", "target_speed", "steer",
   "observation": {"telemetry_seq", "stamp_ns"}}           from the AVLite bridge
Output: forwarded requests to the Devkit bridge's guard inbox (``\\0<target>``), in the
inbox's existing format. Sends never block; a full or absent receiver is counted.
Every decision is appended to ``--trace`` (bounded); ``--status`` is rewritten periodically.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import socket
import time

from .supervisor_core import Limits, SupervisorCore

TRACE_LIMIT_BYTES = 64 * 1024 * 1024


def _write_status(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as stream:
        json.dump(value, stream)
    os.replace(temporary, path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Abstract socket name this supervisor binds")
    parser.add_argument("--target", required=True, help="Abstract socket name of the guard inbox")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--request-life-ms", type=float, default=500.0)
    parser.add_argument("--max-observation-age-ms", type=float, default=500.0)
    parser.add_argument("--runner-lease-ms", type=float, default=500.0)
    args = parser.parse_args(argv)
    limits = Limits(request_life_ns=int(args.request_life_ms * 1e6),
                    max_observation_age_ns=int(args.max_observation_age_ms * 1e6),
                    runner_lease_ns=int(args.runner_lease_ms * 1e6))
    core = SupervisorCore(origin=args.origin, limits=limits)
    inbox = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    inbox.bind("\0" + args.name)
    inbox.setblocking(False)
    outbox = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    outbox.setblocking(False)
    trace = open(args.trace, "w", buffering=1)
    written, io = 0, {"received": 0, "malformed_json": 0, "sent": 0, "refused": 0, "dropped": 0, "trace_truncated": False}
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))
    signal.signal(signal.SIGINT, lambda *_: stop.append(True))

    def record(row):
        nonlocal written
        if written >= TRACE_LIMIT_BYTES:
            io["trace_truncated"] = True
            return
        text = json.dumps(row) + "\n"
        trace.write(text)
        written += len(text)

    def status():
        _write_status(args.status, dict(core.status(), pid=os.getpid(), io=io, ready=True,
                                        monotonic_ns=time.monotonic_ns()))

    status()
    next_status = time.monotonic()
    try:
        while not stop:
            readable, _, _ = select.select([inbox], [], [], 0.02)
            now = time.monotonic_ns()
            changed = core.tick(now)
            if changed:
                record({"t": now, "event": "state", "state": core.state, "reason": core.reason})
            if readable:
                while True:
                    try:
                        payload = inbox.recv(4096)
                    except BlockingIOError:
                        break
                    now = time.monotonic_ns()
                    io["received"] += 1
                    try:
                        message = json.loads(payload)
                        kind = message.get("kind")
                    except (ValueError, AttributeError):
                        io["malformed_json"] += 1
                        record({"t": now, "event": "malformed-json"})
                        continue
                    if kind == "heartbeat":
                        before = core.state
                        reason = core.heartbeat(message.get("seq"), now)
                        if reason or core.state != before:
                            record({"t": now, "event": "heartbeat", "seq": message.get("seq"),
                                    "rejected": reason, "state": core.state})
                        continue
                    decision = core.submit(message if kind == "request" else {}, now)
                    row = {"t": now, "event": "request", "origin": message.get("origin"),
                           "seq": message.get("seq"), "gen_ns": message.get("gen_ns"),
                           "observation": message.get("observation"), "target_speed": message.get("target_speed"),
                           "steer": message.get("steer"), "decision": decision.reason}
                    if decision.forward is not None:
                        try:
                            outbox.sendto(json.dumps(decision.forward).encode(), "\0" + args.target)
                            io["sent"] += 1
                            row["forwarded"] = decision.forward
                        except (ConnectionRefusedError, FileNotFoundError):
                            io["refused"] += 1
                            row["send"] = "refused"
                        except BlockingIOError:
                            io["dropped"] += 1
                            row["send"] = "dropped"
                    record(row)
            if time.monotonic() >= next_status:
                status()
                next_status = time.monotonic() + 0.2
    finally:
        status()
        trace.close()
        inbox.close()
        outbox.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
