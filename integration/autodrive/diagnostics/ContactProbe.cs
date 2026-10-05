// Bounded contact evidence and the single approved collision-pair intervention.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace RoboRacer.Qualification
{
    public sealed class ContactProbe : IDisposable
    {
        const long MaxBytes = 1024L * 1024 * 1024;
        static readonly Encoding Utf8 = new UTF8Encoding(false);
        static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;
        readonly string mode, directory, targetProfile;
        readonly Rigidbody body;
        readonly Func<long> now, otherBytes;
        readonly Action<Exception> fail;
        readonly MeshCollider[] meshes = new MeshCollider[4];
        readonly Collider track;
        readonly Dictionary<int, Collider> registry = new Dictionary<int, Collider>();
        readonly ContactPoint[] buffer = new ContactPoint[256];
        readonly long[] pairCounts = new long[4];
        readonly StringBuilder json = new StringBuilder(16384);
        StreamWriter writer;
        string requestText, windowProperties, windowMassCom;
        long nextPoll, windowStart, windowEnd, activationNs, records, collisionRecords, totalNs, maxNs;
        public long TraceBytes { get; private set; }

        static string Quote(string value)
        {
            return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r").Replace("\t", "\\t") + "\"";
        }
        static void Number(StringBuilder b, double value)
        {
            if (Double.IsNaN(value) || Double.IsInfinity(value)) throw new InvalidOperationException("Nonfinite contact state");
            b.Append(value.ToString("R", Invariant));
        }
        static void Vector(StringBuilder b, Vector3 value)
        {
            b.Append('['); Number(b,value.x); b.Append(','); Number(b,value.y); b.Append(','); Number(b,value.z); b.Append(']');
        }
        static void Rotation(StringBuilder b, Quaternion value)
        {
            b.Append('['); Number(b,value.x); b.Append(','); Number(b,value.y); b.Append(','); Number(b,value.z); b.Append(','); Number(b,value.w); b.Append(']');
        }
        public static string ObjectPath(Transform t)
        {
            string path = t.name;
            while (t.parent != null) { t = t.parent; path = t.name + "/" + path; }
            return path;
        }

        public ContactProbe(string selectedMode, string output, Rigidbody target, Transform root,
                            Func<long> clock, Func<long> other, Action<Exception> failure, string selectedTarget = "proto-track")
        {
            mode = selectedMode; directory = output; body = target; now = clock; otherBytes = other; fail = failure;
            targetProfile = selectedTarget;
            if (mode != "control" && mode != "treatment") throw new InvalidOperationException("Unknown contact mode");
            if (targetProfile != "proto-track" && targetProfile != "floor") throw new InvalidOperationException("Unknown contact target");
            string[] names = {"FL", "FR", "RL", "RR"};
            for (int i = 0; i < names.Length; i++)
            {
                Transform found = root.Find("Vehicle/" + names[i] + " Wheel/Collider");
                MeshCollider[] candidates = found == null ? new MeshCollider[0] : found.GetComponents<MeshCollider>();
                if (candidates.Length != 1) throw new InvalidOperationException("Ambiguous wheel MeshCollider binding");
                meshes[i] = candidates[0];
                if (!meshes[i].enabled || !meshes[i].convex || meshes[i].isTrigger || meshes[i].attachedRigidbody != body)
                    throw new InvalidOperationException("Unexpected wheel MeshCollider state");
            }
            string surfacePath = targetProfile == "floor" ? "Floor" : "Infrastructure/Proto Track";
            var surfaces = new List<Collider>();
            foreach (Collider c in UnityEngine.Object.FindObjectsOfType<Collider>())
                if (ObjectPath(c.transform) == surfacePath) surfaces.Add(c);
            if (surfaces.Count != 1) throw new InvalidOperationException("Ambiguous contact surface binding");
            track = surfaces[0];
            if ((targetProfile == "floor" ? !(track is BoxCollider) : !(track is MeshCollider) || ((MeshCollider)track).convex) ||
                !track.enabled || track.isTrigger || track.attachedRigidbody != null)
                throw new InvalidOperationException("Unexpected contact surface collider state");
            foreach (Collider c in UnityEngine.Object.FindObjectsOfType<Collider>()) registry.Add(c.GetInstanceID(),c);
            if (registry.Count == 0 || registry.Count > 512) throw new InvalidOperationException("Unbounded collider registry");
            foreach (MeshCollider mesh in meshes)
                if (Physics.GetIgnoreCollision(mesh,track)) throw new InvalidOperationException("Target collision pair already ignored");
            if (root.GetComponents<ContactRelay>().Length != 0) throw new InvalidOperationException("Duplicate contact relay");
            try
            {
                writer = new StreamWriter(new FileStream(Path.Combine(output,"contacts.jsonl"),FileMode.CreateNew,
                    FileAccess.Write,FileShare.Read,65536),Utf8,65536);
                json.Append("{\"kind\":\"contact_binding\",\"schema\":2,\"target_profile\":").Append(Quote(targetProfile))
                    .Append(",\"inertia_policy\":").Append(Quote(InertiaPolicy)).Append(",\"pid\":")
                    .Append(System.Diagnostics.Process.GetCurrentProcess().Id).Append(",\"mode\":").Append(Quote(mode))
                    .Append(",\"clock\":\"Linux CLOCK_MONOTONIC\",\"track_id\":").Append(ColliderId(track))
                    .Append(",\"wheel_mesh_ids\":[");
                for (int i=0;i<4;i++) { if(i>0) json.Append(','); json.Append(ColliderId(meshes[i])); }
                json.Append("],\"colliders\":["); bool first=true;
                foreach (var pair in registry)
                {
                    Collider c=pair.Value; if(!first) json.Append(','); first=false;
                    json.Append("{\"id\":").Append(pair.Key).Append(",\"path\":").Append(Quote(ObjectPath(c.transform)))
                        .Append(",\"type\":").Append(Quote(c.GetType().Name)).Append(",\"enabled\":").Append(c.enabled?"true":"false")
                        .Append(",\"trigger\":").Append(c.isTrigger?"true":"false")
                        .Append(",\"attached_body_id\":").Append(c.attachedRigidbody == null ? 0 : c.attachedRigidbody.GetInstanceID())
                        .Append(",\"convex\":").Append(c is MeshCollider ? (((MeshCollider)c).convex ? "true" : "false") : "null").Append('}');
                }
                json.Append("],\"properties\":").Append(Properties()).Append('}'); Write(); writer.Flush();
                root.gameObject.AddComponent<ContactRelay>().Owner = this;
            }
            catch { Dispose(); throw; }
        }

        public int ColliderId(Collider collider)
        {
            if (collider == null || !registry.ContainsKey(collider.GetInstanceID()))
                throw new InvalidOperationException("Unknown diagnostic contact collider");
            return collider.GetInstanceID();
        }
        string Properties()
        {
            var b = new StringBuilder(256); b.Append("{\"mass\":"); Number(b,body.mass);
            b.Append(",\"center_of_mass\":"); Vector(b,body.centerOfMass);
            b.Append(",\"inertia_tensor\":"); Vector(b,body.inertiaTensor);
            b.Append(",\"inertia_rotation\":"); Rotation(b,body.inertiaTensorRotation); return b.Append('}').ToString();
        }
        string InertiaPolicy { get { return targetProfile == "floor" ? "intervention-local" : "time-constant"; } }
        string MassCom()
        {
            var b = new StringBuilder(); Number(b,body.mass); b.Append(':'); Vector(b,body.centerOfMass); return b.ToString();
        }
        string PairState()
        {
            var b = new StringBuilder("[");
            for(int i=0;i<4;i++)
            {
                if(!meshes[i].enabled || !track.enabled) throw new InvalidOperationException("Diagnostic collider unexpectedly disabled");
                bool ignored=Physics.GetIgnoreCollision(meshes[i],track);
                if(ignored != (mode=="treatment" && activationNs!=0)) throw new InvalidOperationException("Unexpected ignored-pair state");
                if(i>0)b.Append(',');b.Append(ignored?"true":"false");
            }
            return b.Append(']').ToString();
        }
        public string SampleState()
        {
            string properties=Properties();
            if(targetProfile=="floor" && activationNs!=0 && MassCom()!=windowMassCom)
                throw new InvalidOperationException("Timed-window mass/COM changed");
            if(targetProfile=="proto-track" && mode=="treatment" && activationNs!=0 && properties!=windowProperties)
                throw new InvalidOperationException("Treatment changed actual mass/COM/inertia");
            return "{\"mode\":"+Quote(mode)+",\"activation_ns\":"+activationNs+",\"ignored\":"+PairState()+",\"properties\":"+properties+"}";
        }

        public long WindowStart { get { return windowStart; } }
        public long WindowEnd { get { return windowEnd; } }
        public long ActivationNs { get { return activationNs; } }

        public void PollWindow()
        {
            long at=now(); if(at<nextPoll)return; nextPoll=at+100000000;
            string path=Path.Combine(directory,"contact-window.request");
            if(!File.Exists(path)) { if(requestText!=null)throw new InvalidOperationException("Window request disappeared"); return; }
            if(new FileInfo(path).Length>256)throw new InvalidOperationException("Oversized contact window request");
            string value=File.ReadAllText(path);
            if(requestText!=null) { if(value!=requestText)throw new InvalidOperationException("Window request changed");return; }
            string[] fields=value.Split('\n'); int pid; long start,end;
            bool floor = targetProfile=="floor";
            int offset = floor ? 4 : 3;
            if(fields.Length!=(floor?7:6) || fields[0]!=(floor?"contact-window-v2":"contact-window-v1") ||
               fields[fields.Length-1]!="" || fields[2]!=mode || (floor && fields[3]!=targetProfile) ||
               !Int32.TryParse(fields[1],out pid) || pid!=System.Diagnostics.Process.GetCurrentProcess().Id ||
               !Int64.TryParse(fields[offset],out start) || !Int64.TryParse(fields[offset+1],out end) ||
               start<=0 || end<=start || end-start>60000000000L || at<start || at-start>3000000000L || at>=end)
                throw new InvalidOperationException("Invalid, stale or foreign contact window request");
            requestText=value;windowStart=start;windowEnd=end;windowProperties=Properties();windowMassCom=MassCom();
            string before=PairState();
            if(mode=="treatment") foreach(MeshCollider mesh in meshes)Physics.IgnoreCollision(mesh,track,true);
            activationNs=now();
            string after=PairState();
            string afterProperties=Properties();
            json.Clear().Append("{\"kind\":\"window_activation\",\"index\":").Append(records)
                .Append(",\"monotonic_ns\":").Append(activationNs).Append(",\"start_ns\":").Append(start)
                .Append(",\"end_ns\":").Append(end).Append(",\"mode\":").Append(Quote(mode))
                .Append(",\"before_ignored\":").Append(before).Append(",\"after_ignored\":").Append(after)
                .Append(",\"target_profile\":").Append(Quote(targetProfile))
                .Append(",\"before_properties\":").Append(windowProperties).Append(",\"after_properties\":").Append(afterProperties)
                .Append(",\"properties\":").Append(windowProperties).Append('}');Write();records++;
            if(afterProperties!=windowProperties)throw new InvalidOperationException("Collision filtering changed mass/COM/inertia");
        }

        public void Receive(string phase, Collision collision)
        {
            if(writer==null)return;
            try
            {
                long begin=now();int count=collision.contactCount;
                if(count<0 || count>buffer.Length)throw new InvalidOperationException("Contact count exceeds diagnostic bound");
                if(collision.GetContacts(buffer)!=count)throw new InvalidOperationException("Incomplete contact capture");
                json.Clear().Append("{\"kind\":\"collision\",\"index\":").Append(records)
                    .Append(",\"monotonic_ns\":").Append(begin).Append(",\"phase\":").Append(Quote(phase))
                    .Append(",\"fixed_time\":");Number(json,Time.fixedTimeAsDouble);
                json.Append(",\"other_id\":").Append(ColliderId(collision.collider))
                    .Append(",\"impulse\":");Vector(json,collision.impulse);
                json.Append(",\"relative_velocity\":");Vector(json,collision.relativeVelocity);
                json.Append(",\"points\":[");
                for(int i=0;i<count;i++)
                {
                    ContactPoint p=buffer[i];int a=ColliderId(p.thisCollider),b=ColliderId(p.otherCollider);
                    for(int j=0;j<4;j++)if((a==meshes[j].GetInstanceID()&&b==track.GetInstanceID()) ||
                        (b==meshes[j].GetInstanceID()&&a==track.GetInstanceID()))pairCounts[j]++;
                    if(i>0)json.Append(',');json.Append("{\"a\":").Append(a).Append(",\"b\":").Append(b)
                        .Append(",\"point\":");Vector(json,p.point);json.Append(",\"normal\":");Vector(json,p.normal);
                    json.Append(",\"separation\":");Number(json,p.separation);json.Append('}');
                }
                json.Append("]}");Write();records++;collisionRecords++;
                long cost=now()-begin;totalNs+=cost;maxNs=Math.Max(maxNs,cost);
            }
            catch(Exception e){fail(e);}
        }
        void Write()
        {
            string line=json.ToString();long size=Utf8.GetByteCount(line)+1;
            if(TraceBytes+otherBytes()+size>MaxBytes)throw new InvalidOperationException("Combined diagnostic 1 GiB trace bound reached");
            writer.Write(line);writer.Write('\n');TraceBytes+=size;
        }
        public string StatusFields()
        {
            return ",\"contact_mode\":"+Quote(mode)+",\"contact_target\":"+Quote(targetProfile)+",\"inertia_policy\":"+Quote(InertiaPolicy)+
                ",\"contact_bytes\":"+TraceBytes+",\"contact_records\":"+records+
                ",\"collision_records\":"+collisionRecords+",\"contact_window_start_ns\":"+windowStart+
                ",\"contact_window_end_ns\":"+windowEnd+",\"contact_activation_ns\":"+activationNs+
                ",\"contact_total_ns\":"+totalNs+",\"contact_max_ns\":"+maxNs+
                ",\"contact_pair_counts\":["+String.Join(",",pairCounts)+"]";
        }
        public void Flush(){if(writer!=null)writer.Flush();}
        public void Dispose(){if(writer!=null){writer.Dispose();writer=null;}}
    }
}
