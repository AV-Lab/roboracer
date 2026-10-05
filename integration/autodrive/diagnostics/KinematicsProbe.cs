// Diagnostic-only SIM0 exception. Contact treatment is explicit and separately gated.
using System;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;

namespace RoboRacer.Qualification
{
    [DefaultExecutionOrder(30000)]
    public sealed class KinematicsProbe : MonoBehaviour
    {
        const string Flag = "-roboracerKinematics";
        // The qualified scene advances physics at 1 kHz. Keep every sample and
        // cover startup plus both callback phases without changing that timestep.
        const long MaxBytes = 1024L * 1024 * 1024;
        const long LifetimeNs = 300L * 1000000000;
        static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;
        static readonly Encoding Utf8 = new UTF8Encoding(false);
        [StructLayout(LayoutKind.Sequential)]
        struct Timespec { public long seconds; public long nanoseconds; }
        [DllImport("libc", EntryPoint = "clock_gettime", SetLastError = true)]
        static extern int ClockGetTime(int clockId, out Timespec value);
        [DllImport("libc", EntryPoint = "getpid")]
        static extern int GetPid();

        string directory;
        string contactMode;
        string contactTarget = "proto-track";
        ContactProbe contacts;
        bool poseEnabled;
        PoseTrace pose;
        StreamWriter writer;
        VehicleController controller;
        Rigidbody body;
        Transform root, axle;
        IPS ips;
        WheelCollider[] wheels;
        readonly StringBuilder json = new StringBuilder(8192);
        long startedNs, lastSampleNs, nextFlushNs, bytes, samples, fixedSamples, lateSamples;
        long totalSampleNs, maxSampleNs, totalFlushNs, maxFlushNs, flushCount;
        bool failed;
        string error = "";

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            string[] args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, Flag);
            int contactIndex = Array.IndexOf(args, "-roboracerContacts");
            int targetIndex = Array.IndexOf(args, "-roboracerContactTarget");
            int poseIndex = Array.IndexOf(args, "-roboracerPoseTrace");
            if (index < 0 && contactIndex < 0 && targetIndex < 0 && poseIndex < 0) return;
            try
            {
                if (index < 0 || Array.LastIndexOf(args, Flag) != index || index + 1 == args.Length)
                    throw new InvalidOperationException("Exactly one diagnostic output argument is required");
                string mode = null;
                string target = "proto-track";
                if (targetIndex >= 0)
                {
                    if (contactIndex < 0 || Array.LastIndexOf(args, "-roboracerContactTarget") != targetIndex || targetIndex+1 == args.Length)
                        throw new InvalidOperationException("Contact target requires exactly one contact diagnostic mode");
                    target = args[targetIndex+1];
                    if (target != "floor" && target != "proto-track") throw new InvalidOperationException("Unknown contact target");
                }
                if (contactIndex >= 0)
                {
                    if (Array.LastIndexOf(args, "-roboracerContacts") != contactIndex || contactIndex + 1 == args.Length)
                        throw new InvalidOperationException("Exactly one contact mode is required");
                    mode = args[contactIndex + 1];
                    if (mode != "control" && mode != "treatment") throw new InvalidOperationException("Unknown contact mode");
                }
                string output = args[index + 1];
                if(poseIndex>=0 && (Array.LastIndexOf(args,"-roboracerPoseTrace")!=poseIndex || mode!="control" || target!="floor"))
                    throw new InvalidOperationException("Pose trace requires one explicit flag and unfiltered Floor control mode");
                if (!Path.IsPathRooted(output) || !Directory.Exists(output) ||
                    Directory.GetFileSystemEntries(output).Length != 0)
                    throw new InvalidOperationException("Diagnostic output must be an existing empty absolute directory");
                if (FindObjectsOfType<KinematicsProbe>().Length != 0)
                    throw new InvalidOperationException("Duplicate diagnostic component");
                var ownObject = new GameObject("RoboRacerKinematicsDiagnostic");
                KinematicsProbe probe = ownObject.AddComponent<KinematicsProbe>();
                probe.directory = output; probe.contactMode = mode; probe.contactTarget = target;
                probe.poseEnabled=poseIndex>=0;
            }
            catch (Exception exception)
            {
                Debug.LogError("RoboRacer kinematics bootstrap failed: " + exception);
                Application.Quit(17);
            }
        }

        static long Now()
        {
            Timespec value;
            if (ClockGetTime(1, out value) != 0 || value.nanoseconds < 0 || value.nanoseconds >= 1000000000)
                throw new InvalidOperationException("Linux CLOCK_MONOTONIC read failed");
            return checked(value.seconds * 1000000000 + value.nanoseconds);
        }

        static string Quote(string value)
        {
            var result = new StringBuilder("\"");
            foreach (char ch in value)
            {
                if (ch == '\\' || ch == '"') result.Append('\\').Append(ch);
                else if (ch < 32) result.Append("\\u").Append(((int)ch).ToString("x4", Invariant));
                else result.Append(ch);
            }
            return result.Append('"').ToString();
        }

        void Start()
        {
            try
            {
                startedNs = Now();
                VehicleController[] controllers = FindObjectsOfType<VehicleController>();
                IPS[] sensors = FindObjectsOfType<IPS>();
                if (controllers.Length != 1 || sensors.Length != 1)
                    throw new InvalidOperationException("Expected exactly one active vehicle controller and IPS");
                controller = controllers[0]; ips = sensors[0];
                body = controller.VehicleRigidBody;
                root = controller.Vehicle == null ? null : controller.Vehicle.transform;
                axle = ips.VehicleTransform;
                if (body == null || root == null || root.name != "F1TENTH" || body.transform != root ||
                    axle == null || axle.name != "Rear Axle Center" || !axle.IsChildOf(root))
                    throw new InvalidOperationException("Unexpected body/root/IPS binding");
                wheels = new[] {controller.FrontLeftWheelCollider, controller.FrontRightWheelCollider,
                                controller.RearLeftWheelCollider, controller.RearRightWheelCollider};
                for (int i = 0; i < wheels.Length; i++)
                {
                    if (wheels[i] == null || wheels[i].attachedRigidbody != body)
                        throw new InvalidOperationException("Wheel does not belong to the qualified body");
                    for (int j = 0; j < i; j++)
                        if (wheels[j] == wheels[i]) throw new InvalidOperationException("Duplicate wheel binding");
                }
                if (contactMode != null)
                    contacts = new ContactProbe(contactMode, directory, body, root, Now,
                        () => bytes + (pose==null?0:pose.TraceBytes), Fail, contactTarget);
                writer = new StreamWriter(new FileStream(Path.Combine(directory, "samples.jsonl"),
                    FileMode.CreateNew, FileAccess.Write, FileShare.Read, 65536), Utf8, 65536);
                json.Clear().Append("{\"kind\":\"binding\",\"schema\":1,\"clock\":\"Linux CLOCK_MONOTONIC\",\"pid\":")
                    .Append(GetPid()).Append(",\"engine\":").Append(Quote(Application.unityVersion))
                    .Append(",\"body_instance_id\":").Append(body.GetInstanceID())
                    .Append(",\"root_instance_id\":").Append(root.GetInstanceID())
                    .Append(",\"axle_instance_id\":").Append(axle.GetInstanceID())
                    .Append(",\"body_name\":").Append(Quote(root.name))
                    .Append(",\"axle_name\":").Append(Quote(axle.name))
                    .Append(",\"wheel_order\":[\"front_left\",\"front_right\",\"rear_left\",\"rear_right\"],")
                    .Append("\"units\":\"Unity xyz metres; quaternion xyzw; velocity m/s; angular rad/s; wheel rpm, Nm, degrees, N; IPS z,-x,y\"}");
                WriteLine();
                if(poseEnabled)
                {
                    if(contactMode!="control" || contactTarget!="floor")throw new InvalidOperationException("Pose trace requires Floor control");
                    pose=new PoseTrace(directory,controller,contacts,Now,()=>bytes+contacts.TraceBytes,Fail);
                }
                FlushAndStatus("ready");
            }
            catch (Exception exception) { Fail(exception); }
        }

        void Number(double value)
        {
            if (Double.IsNaN(value) || Double.IsInfinity(value))
                throw new InvalidOperationException("Nonfinite diagnostic state");
            // Float inputs promote exactly to double; R preserves their full value.
            json.Append(value.ToString("R", Invariant));
        }

        void Vector(Vector3 value)
        {
            json.Append('['); Number(value.x); json.Append(','); Number(value.y);
            json.Append(','); Number(value.z); json.Append(']');
        }

        void Rotation(Quaternion value)
        {
            json.Append('['); Number(value.x); json.Append(','); Number(value.y);
            json.Append(','); Number(value.z); json.Append(','); Number(value.w); json.Append(']');
        }

        void Pose(Transform value)
        {
            json.Append("{\"position\":"); Vector(value.position);
            json.Append(",\"rotation\":"); Rotation(value.rotation);
            json.Append(",\"local_position\":"); Vector(value.localPosition);
            json.Append(",\"local_rotation\":"); Rotation(value.localRotation); json.Append('}');
        }

        void FixedUpdate() { Capture("FixedUpdate"); }
        void LateUpdate() { Capture("LateUpdate"); }

        void Capture(string phase)
        {
            if (failed || writer == null) return;
            try
            {
                long begin = Now();
                if (begin - startedNs > LifetimeNs) throw new InvalidOperationException("Diagnostic lifetime bound reached");
                if (controller.CurrentDrivingMode != 0 || controller.CurrentThrottle != 0 || controller.CurrentSteeringAngle != 0)
                    throw new InvalidOperationException("Diagnostic requires Manual and exact-zero control state");
                if (contacts != null && phase == "FixedUpdate") contacts.PollWindow();
                json.Clear().Append("{\"kind\":\"sample\",\"index\":").Append(samples)
                    .Append(",\"monotonic_ns\":").Append(begin).Append(",\"phase\":").Append(Quote(phase))
                    .Append(",\"frame\":").Append(Time.frameCount).Append(",\"time\":"); Number(Time.timeAsDouble);
                json.Append(",\"fixed_time\":"); Number(Time.fixedTimeAsDouble);
                json.Append(",\"fixed_delta_time\":"); Number(Time.fixedDeltaTime);
                json.Append(",\"body\":{\"position\":"); Vector(body.position);
                json.Append(",\"rotation\":"); Rotation(body.rotation);
                json.Append(",\"velocity\":"); Vector(body.velocity);
                json.Append(",\"angular_velocity\":"); Vector(body.angularVelocity);
                json.Append(",\"sleeping\":").Append(body.IsSleeping() ? "true" : "false").Append('}');
                json.Append(",\"root\":"); Pose(root); json.Append(",\"axle\":"); Pose(axle);
                float[] position = ips.CurrentPosition;
                if (position == null || position.Length != 3) throw new InvalidOperationException("Malformed IPS value");
                json.Append(",\"ips\":["); Number(position[0]); json.Append(','); Number(position[1]);
                json.Append(','); Number(position[2]); json.Append(']');
                json.Append(",\"throttle\":"); Number(controller.CurrentThrottle);
                json.Append(",\"steering\":"); Number(controller.CurrentSteeringAngle);
                if (contacts != null) json.Append(",\"contact_state\":").Append(contacts.SampleState());
                json.Append(",\"wheels\":[");
                for (int i = 0; i < wheels.Length; i++)
                {
                    if (i != 0) json.Append(',');
                    WheelCollider wheel = wheels[i]; WheelHit hit;
                    bool grounded = wheel.GetGroundHit(out hit);
                    json.Append("{\"rpm\":"); Number(wheel.rpm);
                    json.Append(",\"motor_torque\":"); Number(wheel.motorTorque);
                    json.Append(",\"brake_torque\":"); Number(wheel.brakeTorque);
                    json.Append(",\"steer_angle\":"); Number(wheel.steerAngle);
                    json.Append(",\"grounded\":").Append(grounded ? "true" : "false");
                    if (grounded)
                    {
                        if (contacts != null) json.Append(",\"collider_id\":").Append(contacts.ColliderId(hit.collider));
                        json.Append(",\"force\":"); Number(hit.force);
                        json.Append(",\"forward_slip\":"); Number(hit.forwardSlip);
                        json.Append(",\"sideways_slip\":"); Number(hit.sidewaysSlip);
                        json.Append(",\"point\":"); Vector(hit.point);
                        json.Append(",\"normal\":"); Vector(hit.normal);
                    }
                    json.Append('}');
                }
                json.Append("]}"); WriteLine(); samples++;
                if (phase == "FixedUpdate") fixedSamples++; else lateSamples++;
                lastSampleNs = begin;
                long cost = Now() - begin; totalSampleNs += cost; maxSampleNs = Math.Max(maxSampleNs, cost);
                if (begin >= nextFlushNs) FlushAndStatus("ready");
            }
            catch (Exception exception) { Fail(exception); }
        }

        void WriteLine()
        {
            string line = json.ToString();
            long length = Utf8.GetByteCount(line) + 1;
            if (bytes + (contacts == null ? 0 : contacts.TraceBytes) + (pose==null?0:pose.TraceBytes) + length > MaxBytes)
                throw new InvalidOperationException("Diagnostic 1 GiB trace bound reached");
            writer.Write(line); writer.Write('\n'); bytes += length;
        }

        void Status(string state)
        {
            string value = "{\"schema\":1,\"pid\":" + GetPid() + ",\"state\":" + Quote(state) +
                ",\"heartbeat_monotonic_ns\":" + Now() + ",\"last_sample_ns\":" + lastSampleNs +
                ",\"samples\":" + samples + ",\"fixed_samples\":" + fixedSamples + ",\"late_samples\":" + lateSamples +
                ",\"trace_bytes\":" + bytes + ",\"max_trace_bytes\":" + MaxBytes +
                ",\"total_sample_ns\":" + totalSampleNs + ",\"max_sample_ns\":" + maxSampleNs +
                ",\"total_flush_ns\":" + totalFlushNs + ",\"max_flush_ns\":" + maxFlushNs +
                ",\"flush_count\":" + flushCount + (contacts == null ? "" : contacts.StatusFields()) +
                (pose==null?"":pose.StatusFields()) +
                ",\"error\":" + Quote(error) + "}\n";
            string destination = Path.Combine(directory, "status.json");
            string temporary = destination + ".tmp";
            File.WriteAllText(temporary, value, Utf8);
            if (File.Exists(destination)) File.Replace(temporary, destination, null);
            else File.Move(temporary, destination);
        }

        void FlushAndStatus(string state)
        {
            long begin = Now(); writer.Flush(); if (contacts != null) contacts.Flush(); if(pose!=null)pose.Flush();
            long cost = Now() - begin; totalFlushNs += cost; maxFlushNs = Math.Max(maxFlushNs, cost); flushCount++;
            Status(state); nextFlushNs = Now() + 500000000;
        }

        void Fail(Exception exception)
        {
            if (failed) return;
            failed = true; error = exception.ToString();
            try { if (writer != null) { writer.Flush(); writer.Dispose(); writer = null; } } catch { }
            try { if (contacts != null) contacts.Dispose(); } catch { }
            try { if (pose != null) pose.Dispose(); } catch { }
            try { if (directory != null) Status("failed"); } catch { }
            Debug.LogError("RoboRacer kinematics diagnostic failed: " + error);
            Application.Quit(17); // Process containment only; never a braking claim.
        }

        void OnApplicationQuit()
        {
            if (failed || writer == null) return;
            try { FlushAndStatus("closed"); writer.Dispose(); writer = null; if (contacts != null) contacts.Dispose(); if(pose!=null)pose.Dispose(); }
            catch (Exception exception) { Fail(exception); }
        }
    }
}
