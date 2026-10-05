using System;
using System.Collections.Generic;
using RoboRacer;

// Deterministic SIM1-02 guard-core cases. Compiled with GuardCore.cs under the
// pinned Editor's Mono (scripts/tests/test_autodrive_guard.py); exit code 0 = pass.
static class GuardCoreTests
{
    const long Ms = 1000000L;
    const string Session = "0123456789abcdef0123456789abcdef";
    static int failures, checks;

    static void Check(bool condition, string name)
    {
        checks++;
        if (!condition) { failures++; Console.WriteLine("FAIL " + name); }
    }

    // Bridge clock = sim clock - 5 s; one exchange per call, 40 ms each way.
    const long Offset = 5000 * Ms;

    static GuardCore Armed(out long now, List<string> log = null)
    {
        var guard = new GuardCore(new GuardConfig());
        if (log != null) guard.Logged += log.Add;
        now = 100000 * Ms;
        Exchange(guard, ref now);
        guard.ArmRequest("arm " + Session + " 1 sup-1", Session, 1, now);
        return guard;
    }

    static void Exchange(GuardCore guard, ref long now, long skew = 0)
    {
        long emit = now;
        long frameReceipt = now + 10 * Ms - Offset + skew; // frame reaches the bridge 10 ms after emission
        long ping = now + 140 * Ms - Offset + skew;        // bridge replies 130 ms later
        now += 150 * Ms;                                   // reply reaches the simulator 10 ms later
        guard.ClockExchange(now, frameReceipt, ping, emit, now);
    }

    static string Req(GuardCore g, long seq, long genSim, long lifeMs, string throttle = "0", string steering = "0", int epoch = -1, string origin = "sup-1")
    {
        long gen = genSim - Offset;
        return string.Join(" ", new[] { (epoch < 0 ? g.Epoch : epoch).ToString(), origin, seq.ToString(), gen.ToString(),
            (gen + lifeMs * Ms).ToString(), throttle, steering, "lidar:7" });
    }

    static string LastEvent(List<string> log) { return log.Count == 0 ? "" : log[log.Count - 1]; }

    static void Main()
    {
        long now;
        var log = new List<string>();

        // Startup is disarmed; requests are rejected and nothing is applied.
        var idle = new GuardCore(new GuardConfig());
        Check(idle.State == GuardState.Disarmed, "startup disarmed");
        Check(!idle.Request("0 sup-1 1 0 1 0 0 x", 1), "request while disarmed rejected");
        Check(idle.Apply(2, 1).AppliedSeq == -1 && idle.Apply(2, 1).Throttle == 0, "disarmed applies zero");

        // Arming needs a usable clock and the current session/episode.
        var noClock = new GuardCore(new GuardConfig());
        noClock.ArmRequest("arm " + Session + " 1 sup-1", Session, 1, 10);
        Check(noClock.State == GuardState.Disarmed, "arm without clock rejected");
        foreach (var bad in new[] { "arm " + Session + " 2 sup-1", "arm ffff 1 sup-1", "arm " + Session + " 1", "arm " + Session + " 1 bad origin", "arm " + Session + " x sup-1" })
        {
            var g = new GuardCore(new GuardConfig());
            long t = 100000 * Ms; Exchange(g, ref t);
            g.ArmRequest(bad, Session, 1, t);
            Check(g.State == GuardState.Disarmed && g.Rejected == 1, "bad arm rejected: " + bad);
        }

        // Accept, apply once, then expire at the earliest mapping of the original deadline.
        var guard = Armed(out now, log);
        Check(guard.State == GuardState.Armed && guard.Epoch == 1, "armed");
        Check(guard.Request(Req(guard, 1, now - 10 * Ms, 300), now), "valid accepted");
        // offset lower bound = emit - frame receipt = Offset - 10 ms, so expiry = gen + 300 ms - 10 ms in sim time
        Check(guard.LeaseExpirySim == now - 10 * Ms + 300 * Ms - 10 * Ms, "conservative deadline mapping");
        var o = guard.Apply(now + Ms, 7);
        Check(o.AppliedSeq == 1 && o.NewlyApplied && LastEvent(log).EndsWith("applied 1 step 7"), "applied ack once");
        Check(!guard.Apply(now + 2 * Ms, 8).NewlyApplied, "no repeated applied ack");
        o = guard.Apply(guard.LeaseExpirySim, 9);
        Check(o.AppliedSeq == -1 && o.Throttle == 0 && guard.State == GuardState.Stopped && guard.Expired == 1, "lease expiry stops");
        Check(!guard.Request(Req(guard, 2, guard.LeaseExpirySim, 300), guard.LeaseExpirySim + Ms), "stopped requires rearm");

        // Receiver-local lease caps a long but permitted original deadline.
        guard = Armed(out now);
        guard.Request(Req(guard, 1, now, 1000), now + 400 * Ms);
        Check(guard.LeaseExpirySim <= now + 400 * Ms + guard.Config.MaxLeaseNs, "receiver lease cap");

        // Content checks, each independent of the lease.
        foreach (var c in new[] {
            new[] { "NaN", "0", "nonfinite" }, new[] { "0", "Infinity", "nonfinite" }, new[] { "-Infinity", "0", "nonfinite" },
            new[] { "1.5", "0", "out-of-range" }, new[] { "0", "-2", "out-of-range" }, new[] { "1.0000001", "0", "out-of-range" },
            new[] { "0x1", "0", "malformed" }, new[] { "", "0", "malformed" } })
        {
            log.Clear();
            guard = Armed(out now, log);
            Check(guard.Request(Req(guard, 1, now, 300), now), "baseline before " + c[2]);
            long expiry = guard.LeaseExpirySim;
            Check(!guard.Request(Req(guard, 2, now, 300, c[0], c[1]), now), "rejected " + c[0] + "/" + c[1]);
            Check(LastEvent(log).EndsWith("reject 2 " + c[2]), "reason " + c[2] + " got " + LastEvent(log));
            Check(guard.LeaseExpirySim == expiry && guard.Apply(now, 1).AppliedSeq == 1, "lease unchanged after " + c[2]);
        }
        foreach (var bad in new[] { "", "1 sup-1 x 0 1 0 0 a", "1 sup-1 1 0 1 0 0", "1 sup-1 1 0 1 0 0 a b", "1 sup-1 -1 0 1 0 0 a", "1 sup 1 1 0 1 0 0 a" })
        {
            log.Clear();
            guard = Armed(out now, log);
            Check(!guard.Request(bad, now) && LastEvent(log).EndsWith("malformed"), "malformed: '" + bad + "'");
        }

        // Ordering, epoch, origin and lifetime.
        log.Clear();
        guard = Armed(out now, log);
        guard.Request(Req(guard, 5, now, 300), now);
        long held = guard.LeaseExpirySim;
        Check(!guard.Request(Req(guard, 5, now + 50 * Ms, 300), now + 50 * Ms) && LastEvent(log).EndsWith("reject 5 duplicate"), "duplicate");
        Check(guard.LeaseExpirySim == held, "duplicate never refreshes the lease");
        Check(!guard.Request(Req(guard, 4, now, 300), now) && LastEvent(log).EndsWith("reject 4 out-of-order"), "out-of-order");
        Check(!guard.Request(Req(guard, 6, now, 300, epoch: 0), now) && LastEvent(log).EndsWith("reject 6 stale-epoch"), "stale epoch");
        Check(!guard.Request(Req(guard, 6, now, 300, origin: "other"), now) && LastEvent(log).EndsWith("reject 6 foreign-origin"), "foreign origin");
        Check(!guard.Request(Req(guard, 6, now, 1001), now) && LastEvent(log).EndsWith("reject 6 lease-too-long"), "lease too long");
        Check(!guard.Request(Req(guard, 6, now, 0), now) && LastEvent(log).EndsWith("reject 6 invalid-deadline"), "zero lifetime");
        Check(!guard.Request(Req(guard, 6, now + 300 * Ms, 300), now) && LastEvent(log).EndsWith("reject 6 future-generation"), "future generation");

        // An original request forwarded late in a new envelope stays expired.
        log.Clear();
        guard = Armed(out now, log);
        long generated = now;
        now += 600 * Ms;
        Exchange(guard, ref now);
        Check(guard.Envelope("1"), "fresh envelope");
        Check(!guard.Request(Req(guard, 1, generated, 300), now) && LastEvent(log).EndsWith("reject 1 expired"), "expired original inside new envelope");
        Check(!guard.Envelope("1") && LastEvent(log).EndsWith("envelope-replay"), "envelope replay");
        Check(!guard.Envelope("0"), "envelope decrease");
        Check(!guard.Envelope(null) && !guard.Envelope("-3") && !guard.Envelope("2 ") && LastEvent(log).EndsWith("malformed"), "malformed envelope");

        // Clock: unavailable after the window, uncertain when wide, fault on discontinuity.
        log.Clear();
        guard = Armed(out now, log);
        now += 2100 * Ms;
        Check(!guard.Request(Req(guard, 1, now, 300), now) && LastEvent(log).EndsWith("clock-unavailable"), "stale clock");
        long emit = now, ping = now + 890 * Ms - Offset;
        now += 900 * Ms;                                   // held reply without a frame-receipt stamp: width 900 ms
        guard.ClockExchange(now, ping, ping, emit, now);
        Check(!guard.Request(Req(guard, 1, now - 10 * Ms, 300), now) && LastEvent(log).EndsWith("clock-uncertain"), "wide clock");
        var heldReply = Armed(out now);
        emit = now; ping = now + 2000 * Ms - Offset;
        now += 2010 * Ms;                                  // a held reply with its receipt stamp stays narrow
        heldReply.ClockExchange(now, emit + 10 * Ms - Offset, ping, emit, now);
        long lo, hi;
        Check(heldReply.Clock.TryCurrent(now, heldReply.Config.ClockWindowNs, out lo, out hi) && hi - lo == 20 * Ms, "receipt stamp bounds a held reply");
        log.Clear();
        guard = Armed(out now, log);
        guard.Request(Req(guard, 1, now, 300), now);
        Exchange(guard, ref now, skew: 1000 * Ms);
        Check(guard.State == GuardState.Fault && !guard.HasLease && guard.Reason == "clock-discontinuity", "forward discontinuity faults");
        Check(guard.Apply(now, 1).AppliedSeq == -1, "fault applies zero");
        Exchange(guard, ref now, skew: 1000 * Ms);
        guard.ArmRequest("arm " + Session + " 1 sup-1", Session, 1, now);
        Check(guard.State == GuardState.Armed && guard.Epoch == 2, "rearm after relearning clock");
        Exchange(guard, ref now, skew: 0);
        Check(guard.State == GuardState.Fault, "backward discontinuity faults");
        var causal = new GuardCore(new GuardConfig());
        causal.ClockExchange(10, 0, 0, 20, 10);
        Check(causal.Clock.Count == 0, "noncausal exchange discarded");
        causal.ClockExchange(100, 50, 40, 0, 100);
        Check(causal.Clock.Count == 0, "frame receipt after ping discarded");

        // Disconnect, scene load and actuation mismatch clear the lease.
        guard = Armed(out now);
        guard.Request(Req(guard, 1, now, 300), now);
        guard.Disconnect();
        Check(guard.State == GuardState.Disarmed && guard.Apply(now, 1).AppliedSeq == -1, "disconnect disarms");
        Check(guard.Envelope("0"), "envelope sequence restarts per connection");
        guard = Armed(out now);
        guard.Request(Req(guard, 1, now, 300), now);
        guard.SceneLoaded();
        Check(guard.State == GuardState.Disarmed && guard.Clock.Count == 0, "scene load disarms and clears clock");
        guard = Armed(out now);
        guard.ActuationMismatch("motor 1");
        Check(guard.State == GuardState.Fault && guard.Violations == 1, "mismatch faults");

        // Re-arming invalidates the previous epoch's requests and sequence.
        guard = Armed(out now);
        guard.Request(Req(guard, 9, now, 300), now);
        guard.ArmRequest("disarm", Session, 1, now);
        guard.ArmRequest("arm " + Session + " 1 sup-1", Session, 1, now);
        Check(guard.Epoch == 2 && guard.Request(Req(guard, 1, now, 300), now), "new epoch restarts sequence");
        Check(!guard.Request(Req(guard, 10, now, 300, epoch: 1), now), "old epoch rejected after rearm");
        guard.ArmRequest("arm " + Session + " 1 sup-1", Session, 1, now);
        Check(guard.Epoch == 2, "arm while armed rejected");

        // Event delivery is bounded with an explicit overflow count.
        guard = Armed(out now);
        guard.DrainEvents();
        for (int i = 0; i < 70; i++) guard.Request("bad", now);
        string drained = guard.DrainEvents();
        Check(drained.Split(';').Length == 65 && drained.EndsWith("overflow 6"), "bounded events");
        Check(guard.DrainEvents() == "", "events drained");

        Console.WriteLine(string.Format("{0} checks, {1} failures", checks, failures));
        Environment.Exit(failures == 0 ? 0 : 1);
    }
}
