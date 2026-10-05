using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RoboRacer
{
    /*
    SIM1-02 receiver guard (roboracer.guard/1): the Unity side of GuardCore.

    Inactive unless the player is launched with -roboracerGuard; then it is the
    qualified autonomous test mode:
      - the controller is forced to autonomous mode and its inputs are written
        only here, immediately before Steer/Drive in VehicleController.FixedUpdate;
      - legacy "V1 Throttle"/"V1 Steering" Bridge fields, manual axes and the GUI
        driving-mode toggle are ignored and counted;
      - a zero-output interlock is on unless -roboracerMotionAuthorized is given,
        so an accepted nonzero command is recorded but never applied;
      - after actuation the actual wheel-collider torques and steer angles are read
        back, and any torque the guard did not command faults the session.
    -roboracerGuardTrace <existing dir> writes every event and FixedUpdate step to
    guard-trace.jsonl (bounded).
    */
    public static class Guard
    {
        public const string Schema = "roboracer.guard/1";
        public static readonly bool Active = HasArg("-roboracerGuard");
        public static readonly bool MotionAuthorized = HasArg("-roboracerMotionAuthorized");
        public static bool Interlock { get { return !MotionAuthorized; } }
        public static readonly GuardCore Core = new GuardCore(new GuardConfig());
        public static long InterlockSteps { get; private set; }

        const long MaxTraceBytes = 256L * 1024 * 1024;
        static readonly Dictionary<long, long> emits = new Dictionary<long, long>();
        static VehicleController bound;
        static StreamWriter trace;
        static long traceBytes;
        static int unflushedSteps;
        static bool sceneSeen;
        static double outThrottle, outSteering;
        static GuardOutput lastOutput;
        static long manualThisStep;

        static bool HasArg(string name)
        {
            return Array.IndexOf(Environment.GetCommandLineArgs(), name) >= 0;
        }

        static string ArgValue(string name)
        {
            string[] args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Install()
        {
            if (!Active) return;
            string directory = ArgValue("-roboracerGuardTrace");
            if (directory != null)
            {
                if (!Directory.Exists(directory))
                    throw new InvalidOperationException("RoboRacer guard trace directory does not exist");
                var stream = new FileStream(Path.Combine(directory, "guard-trace.jsonl"), FileMode.CreateNew, FileAccess.Write);
                trace = new StreamWriter(stream, new UTF8Encoding(false));
                Write("{\"k\":\"start\",\"schema\":\"" + Schema + "\",\"session\":\"" + Provenance.Session
                      + "\",\"pid\":" + System.Diagnostics.Process.GetCurrentProcess().Id.ToString(CultureInfo.InvariantCulture)
                      + ",\"config\":\"" + ConfigText() + "\",\"mono\":" + Num(Provenance.MonotonicNs()) + "}", true);
                Application.quitting += () => { if (trace != null) { trace.Flush(); trace.Dispose(); trace = null; } };
            }
            Core.Logged += line => Write("{\"k\":\"event\",\"mono\":" + Num(Provenance.MonotonicNs()) + ",\"step\":"
                                         + Num(Provenance.FixedStep) + ",\"text\":\"" + Escape(line) + "\"}", true);
            SceneManager.sceneLoaded += (scene, mode) =>
            {
                bound = null;
                if (sceneSeen) Core.SceneLoaded(); // the first load is startup, already disarmed
                sceneSeen = true;
            };
        }

        static string Num(long value) { return value.ToString(CultureInfo.InvariantCulture); }
        static string Num(double value) { return value.ToString("R", CultureInfo.InvariantCulture); }

        static string Escape(string text)
        {
            return (text ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        static string ConfigText()
        {
            return Core.Config.Format() + (Interlock ? " interlock" : " motion-authorized");
        }

        static void Write(string line, bool flush)
        {
            if (trace == null) return;
            if (traceBytes + line.Length + 1 > MaxTraceBytes)
            {
                trace.WriteLine("{\"k\":\"truncated\"}");
                trace.Flush();
                trace.Dispose();
                trace = null;
                return;
            }
            trace.WriteLine(line);
            traceBytes += line.Length + 1;
            if (flush || ++unflushedSteps >= 50)
            {
                trace.Flush();
                unflushedSteps = 0;
            }
        }

        public static string Capabilities(string baseline)
        {
            return Active ? baseline + " guard" : baseline;
        }

        // ---- Socket.cs hooks (main thread) ---------------------------------

        // Returns true when the guard owns the control inputs, so the vendor write must be skipped.
        public static bool OnBridge(JSONObject json, long receiptNs)
        {
            if (!Active) return false;
            long ping, replyTo, emit, frameReceipt;
            if (json.HasField("RR Ping Mono") && json.HasField("RR Reply To")
                && long.TryParse(json.GetField("RR Ping Mono").str, NumberStyles.None, CultureInfo.InvariantCulture, out ping)
                && long.TryParse(json.GetField("RR Reply To").str, NumberStyles.None, CultureInfo.InvariantCulture, out replyTo)
                && emits.TryGetValue(replyTo, out emit))
            {
                if (!json.HasField("RR Reply Frame Receipt") || !long.TryParse(json.GetField("RR Reply Frame Receipt").str,
                        NumberStyles.None, CultureInfo.InvariantCulture, out frameReceipt))
                    frameReceipt = ping; // conservative: only widens the bound
                Core.ClockExchange(receiptNs, frameReceipt, ping, emit, receiptNs);
            }
            bool arm = json.HasField("RR Guard Arm"), request = json.HasField("RR Guard Request");
            if (arm || request)
            {
                string envelope = json.HasField("RR Guard Envelope") ? json.GetField("RR Guard Envelope").str : null;
                if (Core.Envelope(envelope))
                {
                    if (arm) Core.ArmRequest(json.GetField("RR Guard Arm").str, Provenance.Session, Provenance.Episode, receiptNs);
                    if (request) Core.Request(json.GetField("RR Guard Request").str, receiptNs);
                }
            }
            foreach (string key in new[] { "V1 Throttle", "V1 Steering" })
            {
                if (!json.HasField(key)) continue;
                double value;
                if (!double.TryParse(json.GetField(key).str, NumberStyles.Float, CultureInfo.InvariantCulture, out value) || value != 0)
                    Core.CountLegacy();
            }
            return true;
        }

        public static void OnDisconnect()
        {
            if (Active) Core.Disconnect();
        }

        public static void AddTelemetry(Dictionary<string, string> data)
        {
            if (!Active) return;
            long now = Provenance.MonotonicNs();
            data["RR Guard Schema"] = Schema;
            data["RR Guard State"] = GuardCore.Name(Core.State);
            data["RR Guard Reason"] = Core.Reason;
            data["RR Guard Epoch"] = Num(Core.Epoch);
            data["RR Guard Origin"] = Core.Origin;
            data["RR Guard Accepted"] = Num(Core.LastAcceptedSeq);
            data["RR Guard Applied"] = Num(Core.LastAppliedSeq);
            data["RR Guard Lease Remaining"] = Num(Core.HasLease ? Core.LeaseExpirySim - now : -1);
            data["RR Guard Clock"] = Core.ClockText(now);
            data["RR Guard Counters"] = Core.Counters() + " " + Num(InterlockSteps);
            data["RR Guard Config"] = ConfigText();
            data["RR Guard Event Seq"] = Num(Core.EventSeq);
            data["RR Guard Events"] = Core.DrainEvents();
        }

        public static void NoteEmit(long telemetrySeq, long emitNs)
        {
            if (!Active) return;
            emits[telemetrySeq] = emitNs;
            emits.Remove(telemetrySeq - 64);
        }

        // ---- DrivingMode.cs hook --------------------------------------------

        public static bool BlockGui(string action)
        {
            if (!Active) return false;
            Core.GuiActionBlocked(action);
            return true;
        }

        // ---- VehicleController.cs hooks (FixedUpdate) -----------------------

        public static void BeforeActuation(VehicleController controller)
        {
            if (!Active) return;
            if (bound == null) bound = controller;
            controller.DrivingMode = 1;
            if (controller != bound)
            {
                controller.AutonomousThrottle = 0; // single-vehicle guard: any other vehicle is held at zero
                controller.AutonomousSteering = 0;
                return;
            }
            manualThisStep = 0;
            if (Input.GetAxis("Vertical") != 0 || Input.GetAxis("Horizontal") != 0 || Input.GetMouseButton(0))
            {
                Core.CountManual();
                manualThisStep = 1;
            }
            lastOutput = Core.Apply(Provenance.MonotonicNs(), Provenance.FixedStep);
            outThrottle = lastOutput.Throttle;
            outSteering = lastOutput.Steering;
            if (Interlock && (outThrottle != 0 || outSteering != 0))
            {
                InterlockSteps++;
                outThrottle = 0;
                outSteering = 0;
            }
            controller.AutonomousThrottle = (float)outThrottle;
            controller.AutonomousSteering = (float)outSteering;
        }

        public static void AfterActuation(VehicleController controller)
        {
            if (!Active || controller != bound) return;
            WheelCollider[] wheels = { controller.FrontLeftWheelCollider, controller.FrontRightWheelCollider,
                                       controller.RearLeftWheelCollider, controller.RearRightWheelCollider };
            var line = new StringBuilder(320);
            line.Append("{\"k\":\"step\",\"step\":").Append(Num(Provenance.FixedStep))
                .Append(",\"mono\":").Append(Num(Provenance.MonotonicNs()))
                .Append(",\"state\":\"").Append(GuardCore.Name(Core.State))
                .Append("\",\"epoch\":").Append(Num(Core.Epoch))
                .Append(",\"applied\":").Append(Num(lastOutput.AppliedSeq))
                .Append(",\"cmd\":[").Append(Num(lastOutput.Throttle)).Append(',').Append(Num(lastOutput.Steering))
                .Append("],\"out\":[").Append(Num(outThrottle)).Append(',').Append(Num(outSteering))
                .Append("],\"mode\":").Append(Num(controller.DrivingMode))
                .Append(",\"manual\":").Append(Num(manualThisStep));
            string mismatch = null;
            line.Append(",\"motor\":[");
            for (int i = 0; i < 4; i++)
            {
                float torque = wheels[i].motorTorque;
                line.Append(i > 0 ? "," : "").Append(Num((double)torque));
                if (outThrottle == 0 && torque != 0) mismatch = "motor " + i.ToString(CultureInfo.InvariantCulture);
            }
            line.Append("],\"brake\":[");
            for (int i = 0; i < 4; i++) line.Append(i > 0 ? "," : "").Append(Num((double)wheels[i].brakeTorque));
            line.Append("],\"steer\":[").Append(Num((double)wheels[0].steerAngle)).Append(',').Append(Num((double)wheels[1].steerAngle)).Append("]}");
            if (Interlock && (wheels[0].steerAngle != 0 || wheels[1].steerAngle != 0)) mismatch = mismatch ?? "steer";
            Write(line.ToString(), false);
            if (mismatch != null) Core.ActuationMismatch(mismatch);
        }
    }
}
