using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RoboRacer
{
    /*
    SIM1-01 source provenance (schema roboracer.sim1/1).

    Records, at the moment each sensor acquires, a per-source sequence, the
    episode, the fixed-step index, simulation time and the process monotonic
    clock. It never writes simulation state. Episodes advance on every scene
    load, so a GUI Reset invalidates prior identities.

    Test hooks (source freezes) exist only when the player is launched with
    -roboracerTestHooks; otherwise every hook request is counted and rejected.
    */
    public static class Provenance
    {
        public const string Schema = "roboracer.sim1/1";
        public static readonly string Session = Guid.NewGuid().ToString("N");
        public static readonly bool TestHooks =
            Array.IndexOf(Environment.GetCommandLineArgs(), "-roboracerTestHooks") >= 0;
        static readonly string[] FreezableKinds = { "lidar", "ips" };

        public static int Episode { get; private set; }
        public static long FixedStep { get; private set; }
        public static long HookRejections { get; private set; }
        public static string FrozenKinds { get { return string.Join(",", frozen); } }

        static readonly HashSet<string> frozen = new HashSet<string>();
        static readonly Dictionary<int, long> sequences = new Dictionary<int, long>();
        static readonly Dictionary<int, Stamp> stamps = new Dictionary<int, Stamp>();

        public struct Stamp
        {
            public long Seq; // 0 means no acquisition yet in this episode
            public int Episode;
            public long Step;
            public double SimTime;
            public long MonoNs;
            public long MonoEndNs;

            // "seq episode step simTime monoNs monoEndNs"; invariant culture, round-trip time.
            public string Format()
            {
                return string.Format(CultureInfo.InvariantCulture, "{0} {1} {2} {3:R} {4} {5}",
                    Seq, Episode, Step, SimTime, MonoNs, MonoEndNs);
            }
        }

        public static long MonotonicNs()
        {
            long ticks = Stopwatch.GetTimestamp();
            return Stopwatch.Frequency == 1000000000L ? ticks : (long)(ticks * (1e9 / Stopwatch.Frequency));
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Install()
        {
            SceneManager.sceneLoaded += (scene, mode) =>
            {
                Episode++;
                sequences.Clear();
                stamps.Clear();
                frozen.Clear();
            };
            var host = new GameObject("RoboRacerProvenance");
            host.hideFlags = HideFlags.HideInHierarchy;
            UnityEngine.Object.DontDestroyOnLoad(host);
            host.AddComponent<ProvenanceClock>();
        }

        internal static void AdvanceFixedStep() { FixedStep++; }

        // Call at the end of the source's acquisition; Time.timeAsDouble is fixed time inside FixedUpdate.
        public static void Record(UnityEngine.Object source)
        {
            long now = MonotonicNs();
            RecordInterval(source, now, now);
        }

        public static void RecordInterval(UnityEngine.Object source, long startNs, long endNs)
        {
            int id = source.GetInstanceID();
            long seq;
            sequences.TryGetValue(id, out seq);
            sequences[id] = ++seq;
            stamps[id] = new Stamp { Seq = seq, Episode = Episode, Step = FixedStep,
                SimTime = Time.timeAsDouble, MonoNs = startNs, MonoEndNs = endNs };
        }

        public static Stamp Get(UnityEngine.Object source)
        {
            Stamp stamp;
            if (source == null || !stamps.TryGetValue(source.GetInstanceID(), out stamp))
                stamp = new Stamp { Episode = Episode };
            return stamp;
        }

        public static bool Frozen(string kind)
        {
            return TestHooks && frozen.Contains(kind);
        }

        // "" clears freezes; "lidar" / "ips" / "lidar,ips" freeze those sources. Fails closed.
        public static void ApplyTestRequest(string request)
        {
            var kinds = new List<string>();
            foreach (string part in (request ?? "").Split(','))
                if (part.Trim().Length > 0) kinds.Add(part.Trim());
            if (!TestHooks)
            {
                if (kinds.Count > 0) HookRejections++;
                return;
            }
            foreach (string kind in kinds)
            {
                if (Array.IndexOf(FreezableKinds, kind) < 0)
                {
                    HookRejections++;
                    return;
                }
            }
            frozen.Clear();
            frozen.UnionWith(kinds);
        }
    }

    [DefaultExecutionOrder(-32000)]
    public class ProvenanceClock : MonoBehaviour
    {
        void FixedUpdate() { Provenance.AdvanceFixedStep(); }
    }
}
