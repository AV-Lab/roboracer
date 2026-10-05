using System;
using System.Collections.Generic;
using System.Globalization;

namespace RoboRacer
{
    /*
    SIM1-02 receiver guard core (roboracer.guard/1). No UnityEngine dependency,
    so the same source is unit-tested under Mono and compiled into the player.

    All times are nanoseconds. "Sim" times are this process's monotonic clock;
    request times are the sender's (bridge/supervisor) monotonic clock. No shared
    epoch is assumed: every exchange bounds offset = sim - bridge from both sides
    using only this receiver's own stamps, so a sender cannot widen or move the
    bound by reporting its own estimate.

      lower: the bridge received telemetry emitted at E at its time Tr (Tr <= T1),
             so Tr + offset >= E          =>  offset >= E - Tr
      upper: the ping was handled at R after it was sent,
             so T1 + offset <= R          =>  offset <= R - T1

    Requests are converted conservatively: a deadline expires at deadline + lower
    (the earliest sim time it could correspond to), and is further capped by a
    receiver-local lease from acceptance.
    */
    public enum GuardState { Disarmed, Armed, Stopped, Fault }

    public sealed class GuardConfig
    {
        public long MaxLeaseNs = 1000000000L;       // receiver-local cap and maximum request lifetime (provisional SIM1-02 value)
        public long MaxClockWidthNs = 400000000L;   // widest usable offset interval
        public long ClockWindowNs = 2000000000L;    // only exchanges this recent bound the offset
        public int MaxEvents = 64;                  // events retained between telemetry frames

        public string Format()
        {
            return string.Format(CultureInfo.InvariantCulture, "{0} {1} {2}", MaxLeaseNs, MaxClockWidthNs, ClockWindowNs);
        }
    }

    public sealed class ClockBounds
    {
        struct Sample { public long At, Lower, Upper; }
        readonly List<Sample> samples = new List<Sample>();

        public int Count { get { return samples.Count; } }

        public void Clear() { samples.Clear(); }

        // Returns null when consistent, otherwise the fault reason. A fault clears history.
        public string Add(long simNow, long lower, long upper, long windowNs)
        {
            if (lower > upper) { samples.Clear(); return "clock-noncausal"; }
            Prune(simNow, windowNs);
            long lo, hi;
            if (Intersect(out lo, out hi) && (lower > hi || upper < lo))
            {
                samples.Clear();
                return "clock-discontinuity";
            }
            samples.Add(new Sample { At = simNow, Lower = lower, Upper = upper });
            return null;
        }

        public bool TryCurrent(long simNow, long windowNs, out long lower, out long upper)
        {
            Prune(simNow, windowNs);
            return Intersect(out lower, out upper);
        }

        void Prune(long simNow, long windowNs)
        {
            samples.RemoveAll(s => simNow - s.At > windowNs);
        }

        bool Intersect(out long lower, out long upper)
        {
            lower = long.MinValue; upper = long.MaxValue;
            if (samples.Count == 0) return false;
            foreach (var s in samples)
            {
                lower = Math.Max(lower, s.Lower);
                upper = Math.Min(upper, s.Upper);
            }
            return true;
        }
    }

    public struct GuardOutput
    {
        public double Throttle, Steering;
        public long AppliedSeq;   // -1 when no accepted command is being applied
        public bool NewlyApplied; // first application step of AppliedSeq
    }

    public sealed class GuardCore
    {
        public readonly GuardConfig Config;
        public readonly ClockBounds Clock = new ClockBounds();
        public GuardState State { get; private set; }
        public string Reason { get; private set; }
        public int Epoch { get; private set; }
        public string Origin { get; private set; }
        public long LastAcceptedSeq { get; private set; }
        public long LastAppliedSeq { get; private set; }
        public long LeaseExpirySim { get; private set; }
        public bool HasLease { get; private set; }
        public long EventSeq { get; private set; }
        public long Accepted, Rejected, Expired, AppliedSteps, LegacyIgnored, ManualIgnored, GuiBlocked, Violations;

        readonly List<string> events = new List<string>();
        long droppedEvents;
        long lastEnvelope = -1;
        double leaseThrottle, leaseSteering;

        public GuardCore(GuardConfig config)
        {
            Config = config;
            State = GuardState.Disarmed;
            Reason = "startup";
            Origin = "-";
            LastAcceptedSeq = -1;
            LastAppliedSeq = -1;
        }

        public static string Name(GuardState state)
        {
            switch (state)
            {
                case GuardState.Armed: return "armed";
                case GuardState.Stopped: return "stopped";
                case GuardState.Fault: return "fault";
                default: return "disarmed";
            }
        }

        // ---- events -------------------------------------------------------

        void Event(string text)
        {
            EventSeq++;
            if (events.Count >= Config.MaxEvents) { droppedEvents++; return; }
            events.Add(EventSeq.ToString(CultureInfo.InvariantCulture) + " " + text);
        }

        public event Action<string> Logged; // full record (the glue writes it to the trace file)

        void Log(string text)
        {
            Event(text);
            if (Logged != null) Logged(EventSeq.ToString(CultureInfo.InvariantCulture) + " " + text);
        }

        // Events since the previous call, ";"-joined; an overflow marker reports dropped entries.
        public string DrainEvents()
        {
            if (droppedEvents > 0) events.Add("overflow " + droppedEvents.ToString(CultureInfo.InvariantCulture));
            string text = string.Join(";", events.ToArray());
            events.Clear();
            droppedEvents = 0;
            return text;
        }

        void Leave(GuardState state, string reason)
        {
            HasLease = false;
            if (State == state && Reason == reason) return;
            State = state;
            Reason = reason;
            Log("state " + Name(state) + " " + reason);
        }

        // ---- inputs -------------------------------------------------------

        // bridgeFrameReceiptNs: when the bridge received the frame it is replying to (pass the
        // ping time when unknown, which only widens the bound).
        public void ClockExchange(long simNow, long bridgeFrameReceiptNs, long bridgePingNs, long simEmitOfRepliedFrame, long simReceipt)
        {
            string fault = bridgeFrameReceiptNs > bridgePingNs ? "clock-noncausal"
                : Clock.Add(simNow, simEmitOfRepliedFrame - bridgeFrameReceiptNs, simReceipt - bridgePingNs, Config.ClockWindowNs);
            if (fault == null) return;
            Log("clock " + fault);
            if (State == GuardState.Armed || State == GuardState.Stopped) Leave(GuardState.Fault, fault);
        }

        // Transport envelopes must strictly increase within one connection; a replayed
        // envelope is rejected as a whole and returns false.
        public bool Envelope(string text)
        {
            long seq;
            if (!ParseLong(text, out seq))
            {
                Rejected++;
                Log("reject envelope - malformed");
                return false;
            }
            if (seq <= lastEnvelope)
            {
                Rejected++;
                Log("reject envelope " + seq.ToString(CultureInfo.InvariantCulture) + " envelope-replay");
                return false;
            }
            lastEnvelope = seq;
            return true;
        }

        public void Disconnect()
        {
            lastEnvelope = -1;
            Leave(GuardState.Disarmed, "disconnect");
        }

        public void SceneLoaded()
        {
            Clock.Clear();
            Leave(GuardState.Disarmed, "scene-load");
        }

        public void ActuationMismatch(string detail)
        {
            Violations++;
            Log("violation " + detail);
            Leave(GuardState.Fault, "actuation-mismatch");
        }

        bool ClockUsable(long now, out long lower, out long upper, out string reason)
        {
            reason = null;
            if (!Clock.TryCurrent(now, Config.ClockWindowNs, out lower, out upper)) reason = "clock-unavailable";
            else if (upper - lower > Config.MaxClockWidthNs) reason = "clock-uncertain";
            return reason == null;
        }

        // "arm <session> <episode> <origin>" or "disarm".
        public void ArmRequest(string text, string session, int episode, long now)
        {
            string[] f = (text ?? "").Split(' ');
            if (f.Length == 1 && f[0] == "disarm")
            {
                Log("disarm-request");
                Leave(GuardState.Disarmed, "requested");
                return;
            }
            string reason = null;
            int requestedEpisode;
            if (f.Length != 4 || f[0] != "arm" || !int.TryParse(f[2], NumberStyles.None, CultureInfo.InvariantCulture, out requestedEpisode) || !IsToken(f[3], 32))
                reason = "malformed";
            else if (State == GuardState.Armed) reason = "already-armed";
            else if (f[1] != session) reason = "wrong-session";
            else if (requestedEpisode != episode) reason = "wrong-episode";
            else
            {
                long lower, upper;
                ClockUsable(now, out lower, out upper, out reason);
            }
            if (reason != null)
            {
                Rejected++;
                Log("reject arm " + reason);
                return;
            }
            Epoch++;
            Origin = f[3];
            LastAcceptedSeq = -1;
            HasLease = false;
            State = GuardState.Armed;
            Reason = "requested";
            Log("state armed epoch " + Epoch.ToString(CultureInfo.InvariantCulture) + " " + Origin);
        }

        static bool IsToken(string text, int maximum)
        {
            if (string.IsNullOrEmpty(text) || text.Length > maximum) return false;
            foreach (char c in text)
                if (!(char.IsLetterOrDigit(c) && c < 128) && c != '-' && c != '_' && c != '.' && c != ':') return false;
            return true;
        }

        static bool ParseLong(string text, out long value)
        {
            return long.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out value);
        }

        // "<epoch> <origin> <seq> <genNs> <deadlineNs> <throttle> <steering> <inputs>", sender clock.
        // Returns true when accepted. Rejection never changes an existing lease.
        public bool Request(string text, long now)
        {
            string[] f = (text ?? "").Split(' ');
            long seq = -1;
            string reason = Validate(f, now, ref seq);
            string id = seq >= 0 ? seq.ToString(CultureInfo.InvariantCulture) : "-";
            if (reason != null)
            {
                Rejected++;
                Log("reject " + id + " " + reason);
                return false;
            }
            return true;
        }

        string Validate(string[] f, long now, ref long seq)
        {
            long epoch, gen, deadline;
            double throttle, steering;
            if (f.Length != 8 || !ParseLong(f[0], out epoch) || !IsToken(f[1], 32) || !ParseLong(f[2], out seq)
                || !ParseLong(f[3], out gen) || !ParseLong(f[4], out deadline) || !IsToken(f[7], 128))
            {
                if (f.Length < 3 || !ParseLong(f[2], out seq)) seq = -1;
                return "malformed";
            }
            if (!double.TryParse(f[5], NumberStyles.Float, CultureInfo.InvariantCulture, out throttle)
                || !double.TryParse(f[6], NumberStyles.Float, CultureInfo.InvariantCulture, out steering))
                return "malformed";
            if (double.IsNaN(throttle) || double.IsInfinity(throttle) || double.IsNaN(steering) || double.IsInfinity(steering))
                return "nonfinite";
            if (Math.Abs(throttle) > 1 || Math.Abs(steering) > 1) return "out-of-range";
            if (State != GuardState.Armed) return "not-armed";
            if (epoch != Epoch) return "stale-epoch";
            if (f[1] != Origin) return "foreign-origin";
            if (seq == LastAcceptedSeq) return "duplicate";
            if (seq < LastAcceptedSeq) return "out-of-order";
            if (deadline <= gen) return "invalid-deadline";
            if (deadline - gen > Config.MaxLeaseNs) return "lease-too-long";
            long lower, upper;
            string clock;
            if (!ClockUsable(now, out lower, out upper, out clock)) return clock;
            if (gen + lower > now) return "future-generation";
            long expiry = Math.Min(deadline + lower, now + Config.MaxLeaseNs);
            if (expiry <= now) return "expired";

            Accepted++;
            LastAcceptedSeq = seq;
            HasLease = true;
            LeaseExpirySim = expiry;
            leaseThrottle = throttle;
            leaseSteering = steering;
            Log(string.Format(CultureInfo.InvariantCulture, "accept {0} {1} {2} {3} {4}", seq, expiry - now, throttle.ToString("R", CultureInfo.InvariantCulture), steering.ToString("R", CultureInfo.InvariantCulture), f[7]));
            return null;
        }

        public void CountLegacy() { LegacyIgnored++; }
        public void CountManual() { ManualIgnored++; }
        public void GuiActionBlocked(string what) { GuiBlocked++; Log("blocked " + what); }

        // Called immediately before the controller's Steer/Drive in FixedUpdate.
        public GuardOutput Apply(long now, long step)
        {
            var output = new GuardOutput { AppliedSeq = -1 };
            if (State == GuardState.Armed && HasLease && now >= LeaseExpirySim)
            {
                Expired++;
                Leave(GuardState.Stopped, "lease-expired " + LastAcceptedSeq.ToString(CultureInfo.InvariantCulture));
            }
            if (State == GuardState.Armed && HasLease)
            {
                output.Throttle = leaseThrottle;
                output.Steering = leaseSteering;
                output.AppliedSeq = LastAcceptedSeq;
                AppliedSteps++;
                if (LastAcceptedSeq != LastAppliedSeq)
                {
                    LastAppliedSeq = LastAcceptedSeq;
                    output.NewlyApplied = true;
                    Log("applied " + LastAcceptedSeq.ToString(CultureInfo.InvariantCulture) + " step " + step.ToString(CultureInfo.InvariantCulture));
                }
            }
            return output;
        }

        public string Counters()
        {
            return string.Format(CultureInfo.InvariantCulture, "{0} {1} {2} {3} {4} {5} {6} {7}",
                Accepted, Rejected, Expired, AppliedSteps, LegacyIgnored, ManualIgnored, GuiBlocked, Violations);
        }

        public string ClockText(long now)
        {
            long lower, upper;
            if (!Clock.TryCurrent(now, Config.ClockWindowNs, out lower, out upper)) return "";
            return string.Format(CultureInfo.InvariantCulture, "{0} {1} {2}", lower, upper, Clock.Count);
        }
    }
}
