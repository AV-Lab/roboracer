// Opt-in statement-level observation only. No vehicle/physics setters.
using System;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace RoboRacer.Qualification
{
    public sealed class PoseTrace : IDisposable
    {
        public const int RecordBytes = 216;
        public const int StagesPerStep = 41;
        const long MaxBytes = 1024L * 1024 * 1024;
        static PoseTrace instance;
        readonly VehicleController controller;
        readonly Rigidbody body;
        readonly Transform root;
        readonly DataRecorder recorder;
        readonly WheelCollider[] wheels;
        readonly Transform[] transforms;
        readonly ContactProbe contacts;
        readonly Func<long> now, otherBytes;
        readonly Action<Exception> fail;
        readonly BinaryWriter writer;
        int cursor;
        bool active, finished, disposed;
        long step = -1, firstNs, lastNs, captureNs, maxCaptureNs, records, steps;
        double lastFixedTime;
        public long TraceBytes { get; private set; }

        public PoseTrace(string directory, VehicleController target, ContactProbe contact,
                         Func<long> clock, Func<long> other, Action<Exception> failure)
        {
            if (instance != null) throw new InvalidOperationException("Duplicate pose tracer");
            controller=target; body=target.VehicleRigidBody; root=target.Vehicle.transform;
            contacts=contact; now=clock; otherBytes=other; fail=failure;
            if (contacts==null || (int)controller.driveType!=5)
                throw new InvalidOperationException("Pose trace requires the qualified CAWD controller and Floor control window");
            DataRecorder[] recorders=UnityEngine.Object.FindObjectsOfType<DataRecorder>();
            if(recorders.Length!=1) throw new InvalidOperationException("Ambiguous data recorder binding");
            recorder=recorders[0];
            if(recorder.Vehicles.Length!=1 || recorder.Vehicles[0]!=controller.Vehicle ||
               recorder.VehicleRigidBodies.Length!=1 || recorder.VehicleRigidBodies[0]!=body ||
               recorder.VehicleControllers.Length!=1 || recorder.VehicleControllers[0]!=controller)
                throw new InvalidOperationException("Unexpected data recorder vehicle binding");
            wheels=new[]{target.FrontLeftWheelCollider,target.FrontRightWheelCollider,target.RearLeftWheelCollider,target.RearRightWheelCollider};
            transforms=new[]{target.FrontLeftWheelTransform,target.FrontRightWheelTransform,target.RearLeftWheelTransform,target.RearRightWheelTransform};
            string[] names={"FL","FR","RL","RR"};
            var bindings=new StringBuilder();
            for(int i=0;i<4;i++)
            {
                string path="F1TENTH/Vehicle/"+names[i]+" Wheel";
                if(transforms[i]==null || ContactProbe.ObjectPath(transforms[i])!=path || wheels[i].attachedRigidbody!=body)
                    throw new InvalidOperationException("Unexpected pose wheel binding");
                Transform child=transforms[i].Find("Collider");
                MeshCollider[] mesh=child==null?new MeshCollider[0]:child.GetComponents<MeshCollider>();
                if(mesh.Length!=1 || !mesh[0].enabled || mesh[0].isTrigger || mesh[0].attachedRigidbody!=body)
                    throw new InvalidOperationException("Unexpected pose mesh binding");
                if(i>0)bindings.Append(',');
                bindings.Append("{\"wheel\":").Append(i).Append(",\"transform_id\":").Append(transforms[i].GetInstanceID())
                    .Append(",\"path\":\"").Append(path).Append("\",\"wheel_collider_id\":").Append(wheels[i].GetInstanceID())
                    .Append(",\"mesh_collider_id\":").Append(mesh[0].GetInstanceID()).Append('}');
            }
            string header="{\"schema\":1,\"record_bytes\":216,\"stages_per_step\":41,\"byte_order\":\"little\","
                +"\"clock\":\"Linux CLOCK_MONOTONIC\",\"float_storage\":\"IEEE754 binary32\","
                +"\"layout\":\"<qqiiiqdd37fiiff\",\"pid\":"+System.Diagnostics.Process.GetCurrentProcess().Id
                +",\"controller_id\":"+controller.GetInstanceID()+",\"body_id\":"+body.GetInstanceID()
                +",\"root_id\":"+root.GetInstanceID()+",\"recorder_id\":"+recorder.GetInstanceID()
                +",\"wheel_bindings\":["+bindings+"]}\n";
            byte[] encoded=new UTF8Encoding(false).GetBytes(header);
            if(encoded.Length+otherBytes()>MaxBytes)throw new InvalidOperationException("Diagnostic 1 GiB trace bound reached");
            using(var file=new FileStream(Path.Combine(directory,"pose-binding.json"),FileMode.CreateNew,FileAccess.Write))
                file.Write(encoded,0,encoded.Length);
            TraceBytes=encoded.Length;
            writer=new BinaryWriter(new FileStream(Path.Combine(directory,"pose.bin"),FileMode.CreateNew,
                FileAccess.Write,FileShare.Read,65536));
            instance=this;
        }

        public static void Mark(VehicleController source, int stage, WheelCollider wheel=null, Transform mesh=null)
        {
            PoseTrace value=instance;
            if(value==null || value.disposed || value.finished)return;
            try { value.Capture(source,stage,wheel,mesh); }
            catch(Exception e) { value.finished=true; value.fail(e); }
        }

        void Capture(VehicleController source,int stage,WheelCollider wheel,Transform mesh)
        {
            if(source!=controller)throw new InvalidOperationException("Foreign pose controller");
            if(!active)
            {
                if(stage!=0 || contacts.ActivationNs==0)return;
                long at=now();
                if(contacts.WindowEnd-contacts.WindowStart>10000000000L || at>=contacts.WindowEnd)
                    throw new InvalidOperationException("Missing or oversized pose observation window");
                active=true;
            }
            long begin=now();
            if(cursor==0 && begin>=contacts.WindowEnd) { finished=true; return; }
            int expected=cursor<7?cursor:cursor<39?10+(cursor-7)%8:cursor==39?7:8;
            int expectedWheel=cursor>=7 && cursor<39?(cursor-7)/8:-1;
            if(stage!=expected || (expectedWheel<0 ? wheel!=null || mesh!=null :
                wheel!=wheels[expectedWheel] || mesh!=transforms[expectedWheel]))
                throw new InvalidOperationException("Missing, reordered or foreign pose stage");
            if(cursor==0)
            {
                double fixedTime=Time.fixedTimeAsDouble;
                if(step>=0 && Math.Abs((fixedTime-lastFixedTime)-Time.fixedDeltaTime)>1e-9)
                    throw new InvalidOperationException("Missing or duplicate pose physics step");
                step++; lastFixedTime=fixedTime;
            }
            if(Time.fixedTimeAsDouble!=lastFixedTime)
                throw new InvalidOperationException("Pose stages crossed a physics step");
            if(TraceBytes+otherBytes()+RecordBytes>MaxBytes)
                throw new InvalidOperationException("Diagnostic 1 GiB trace bound reached");
            // Snapshot into values before serialization. The first pair has no intervening query.
            Vector3 p=body.position, repeat=body.position;
            Quaternion q=body.rotation;
            Vector3 rp=root.position; Quaternion rq=root.rotation;
            Vector3 velocity=body.velocity, angular=body.angularVelocity, com=body.centerOfMass, inertia=body.inertiaTensor;
            Quaternion inertiaRotation=body.inertiaTensorRotation;
            float mass=body.mass;
            Vector3 afterReads=body.position;
            int flags=(recorder.RecordingStatus?1:0)|(recorder.getSaveStatus()?2:0);
            int mode=controller.CurrentDrivingMode;
            float throttle=controller.CurrentThrottle,steering=controller.CurrentSteeringAngle;
            if(mode!=0 || throttle!=0 || steering!=0 || flags!=0 || (int)controller.driveType!=5)
                throw new InvalidOperationException("Pose trace requires Manual exact-zero control and inactive recorder");
            // Check all float values before emitting any bytes of this record.
            Check(p);Check(repeat);Check(q);Check(rp);Check(rq);Check(velocity);Check(angular);
            Check(com);Check(inertia);Check(inertiaRotation);Check(mass);Check(afterReads);Check(throttle);Check(steering);
            writer.Write(records);writer.Write(step);writer.Write(stage);writer.Write(expectedWheel);writer.Write(Time.frameCount);
            writer.Write(begin);writer.Write(Time.fixedTimeAsDouble);writer.Write(Time.timeAsDouble);
            Write(p);Write(repeat);Write(q);Write(rp);Write(rq);Write(velocity);Write(angular);Write(com);Write(inertia);
            Write(inertiaRotation);writer.Write(mass);Write(afterReads);writer.Write(flags);writer.Write(mode);writer.Write(throttle);writer.Write(steering);
            TraceBytes+=RecordBytes;records++;if(firstNs==0)firstNs=begin;lastNs=begin;
            cursor++;if(cursor==StagesPerStep){cursor=0;steps++;}
            long cost=now()-begin;captureNs+=cost;maxCaptureNs=Math.Max(maxCaptureNs,cost);
        }

        static void Check(float v) { if(float.IsNaN(v)||float.IsInfinity(v))throw new InvalidOperationException("Nonfinite pose state"); }
        static void Check(Vector3 v) { Check(v.x);Check(v.y);Check(v.z); }
        static void Check(Quaternion v) { Check(v.x);Check(v.y);Check(v.z);Check(v.w); }
        void Write(Vector3 v) { writer.Write(v.x);writer.Write(v.y);writer.Write(v.z); }
        void Write(Quaternion v) { writer.Write(v.x);writer.Write(v.y);writer.Write(v.z);writer.Write(v.w); }
        public void Flush() { writer.Flush(); }
        public string StatusFields()
        {
            bool complete=active && cursor==0 && now()>=contacts.WindowEnd;
            return ",\"pose_schema\":1,\"pose_record_bytes\":216,\"pose_stages_per_step\":41,\"pose_bytes\":"+TraceBytes
                +",\"pose_records\":"+records+",\"pose_steps\":"+steps+",\"pose_pending_stage\":"+cursor
                +",\"pose_first_ns\":"+firstNs+",\"pose_last_ns\":"+lastNs+",\"pose_total_capture_ns\":"+captureNs
                +",\"pose_max_capture_ns\":"+maxCaptureNs+",\"pose_window_complete\":"+(complete?"true":"false");
        }
        public void Dispose()
        {
            if(disposed)return;
            disposed=true;writer.Dispose();if(instance==this)instance=null;
        }
    }
}
