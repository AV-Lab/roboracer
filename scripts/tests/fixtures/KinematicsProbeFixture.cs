// Test doubles for serialization/fail-closed behavior only. No simulated physics.
using System;
using System.Reflection;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using RoboRacer.Qualification;
namespace UnityEngine
{
    public class DefaultExecutionOrder : Attribute { public DefaultExecutionOrder(int n) {} }
    public enum RuntimeInitializeLoadType { AfterSceneLoad }
    public class RuntimeInitializeOnLoadMethod : Attribute { public RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType v) {} }
    public class Object
    {
        public static VehicleController Vehicle;
        public static IPS Sensor;
        public static DataRecorder Recorder;
        public static List<Collider> Colliders = new List<Collider>();
        static int serial; readonly int id = ++serial;
        public string name;
        public int GetInstanceID() { return id; }
        public static T[] FindObjectsOfType<T>()
        {
            if (typeof(T) == typeof(VehicleController)) return new[] {(T)(object)Vehicle};
            if (typeof(T) == typeof(IPS)) return new[] {(T)(object)Sensor};
            if (typeof(T) == typeof(DataRecorder)) return Recorder==null?new T[0]:new[] {(T)(object)Recorder};
            if (typeof(T) == typeof(Collider)) return Colliders.Select(c=>(T)(object)c).ToArray();
            return new T[0];
        }
    }
    public class MonoBehaviour : Object { public Transform transform; }
    public class GameObject : Object
    {
        public static int Created;
        public static List<GameObject> All = new List<GameObject>();
        public Transform transform;
        public GameObject(string value) { name = value; transform = new Transform {name=value,gameObject=this}; Created++; All.Add(this); }
        public T AddComponent<T>() where T : MonoBehaviour, new() { var value=new T {transform=transform};transform.Components.Add(value);return value; }
        public T[] GetComponents<T>() { return transform.GetComponents<T>(); }
        public static GameObject Find(string path) { return All.FirstOrDefault(g=>ContactProbe.ObjectPath(g.transform)==path); }
    }
    public struct Vector3
    {
        public float x,y,z;
        public Vector3(float a,float b,float c) {x=a;y=b;z=c;}
    }
    public struct Quaternion { public float x,y,z,w; }
    public class Transform : Object
    {
        public Vector3 position, localPosition;
        public Quaternion rotation, localRotation;
        public Transform parent;
        public GameObject gameObject;
        public List<object> Components = new List<object>();
        public T[] GetComponents<T>() { return Components.OfType<T>().ToArray(); }
        public Transform Find(string path) { return GameObject.Find(ContactProbe.ObjectPath(this)+"/"+path)?.transform; }
        public bool IsChildOf(Transform value) { return parent == value; }
    }
    public class Rigidbody : Object
    {
        public Transform transform;
        public Vector3 position, velocity, angularVelocity;
        public Quaternion rotation;
        public float mass=3.47f;
        public Vector3 centerOfMass=new Vector3(0,.06434f,-.00468f), inertiaTensor=new Vector3(.01f,.02f,.03f);
        public Quaternion inertiaTensorRotation=new Quaternion {w=1};
        public bool IsSleeping() { return false; }
    }
    public class Collider : Object
    {
        public Transform transform;
        public Rigidbody attachedRigidbody;
        public bool enabled=true,isTrigger;
    }
    public class MeshCollider : Collider {public bool convex=true;}
    public class BoxCollider : Collider {}
    public struct WheelHit { public float force,forwardSlip,sidewaysSlip; public Vector3 point,normal; public Collider collider; }
    public class WheelCollider : Collider
    {
        public static Collider Ground;
        public float rpm,motorTorque,brakeTorque,steerAngle;
        public bool GetGroundHit(out WheelHit hit)
        {
            hit = new WheelHit {force=8.25f, forwardSlip=.002f, sidewaysSlip=-.001f,
                               point=new Vector3(1,2,3),normal=new Vector3(0,1,0),collider=Ground};
            return true;
        }
    }
    public struct ContactPoint {public Collider thisCollider,otherCollider;public Vector3 point,normal;public float separation;}
    public class Collision
    {
        public Collider collider;
        public Vector3 impulse,relativeVelocity;
        public ContactPoint[] points=new ContactPoint[0];
        public int contactCount {get {return points.Length;}}
        public int GetContacts(ContactPoint[] output){Array.Copy(points,output,Math.Min(points.Length,output.Length));return Math.Min(points.Length,output.Length);}
    }
    public static class Physics
    {
        static HashSet<string> ignored=new HashSet<string>();
        public static int Calls;
        public static bool ChangeInertia;
        static string Key(Collider a,Collider b){return Math.Min(a.GetInstanceID(),b.GetInstanceID())+":"+Math.Max(a.GetInstanceID(),b.GetInstanceID());}
        public static bool GetIgnoreCollision(Collider a,Collider b){return ignored.Contains(Key(a,b));}
        public static void IgnoreCollision(Collider a,Collider b,bool state)
        {
            Calls++;if(state)ignored.Add(Key(a,b));else ignored.Remove(Key(a,b));
            if(ChangeInertia)a.attachedRigidbody.inertiaTensor=new Vector3(1,2,3);
        }
    }
    public static class Time { public static int frameCount=10; public static double timeAsDouble=1.1,fixedTimeAsDouble=1.08; public static float fixedDeltaTime=.02f; }
    public static class Application { public static string unityVersion="fixture"; public static int ExitCode; public static void Quit(int code) { ExitCode=code; } }
    public static class Debug { public static void LogError(string value) { Console.Error.WriteLine(value); } }
}
public class VehicleController : UnityEngine.MonoBehaviour
{
    public UnityEngine.GameObject Vehicle;
    public UnityEngine.Rigidbody VehicleRigidBody;
    public UnityEngine.WheelCollider FrontLeftWheelCollider,FrontRightWheelCollider,RearLeftWheelCollider,RearRightWheelCollider;
    public UnityEngine.Transform FrontLeftWheelTransform,FrontRightWheelTransform,RearLeftWheelTransform,RearRightWheelTransform;
    public int driveType=5;
    public int CurrentDrivingMode;
    public float CurrentThrottle,CurrentSteeringAngle;
}
public class IPS : UnityEngine.MonoBehaviour { public UnityEngine.Transform VehicleTransform; public float[] CurrentPosition; }
public class DataRecorder : UnityEngine.MonoBehaviour
{
    public UnityEngine.GameObject[] Vehicles;
    public UnityEngine.Rigidbody[] VehicleRigidBodies;
    public VehicleController[] VehicleControllers;
    public bool RecordingStatus, Saving;
    public bool getSaveStatus(){return Saving;}
}
public static class Fixture
{
    static UnityEngine.GameObject Child(UnityEngine.GameObject parent,string name)
    {
        var child=new UnityEngine.GameObject(name);child.transform.parent=parent.transform;return child;
    }
    static UnityEngine.MeshCollider Mesh(UnityEngine.GameObject owner,UnityEngine.Rigidbody body,bool convex)
    {
        var mesh=new UnityEngine.MeshCollider {transform=owner.transform,attachedRigidbody=body,convex=convex};
        owner.transform.Components.Add(mesh);UnityEngine.Object.Colliders.Add(mesh);return mesh;
    }
    static void Invoke(KinematicsProbe probe,string name,params object[] args)
    {
        typeof(KinematicsProbe).GetMethod(name,BindingFlags.Instance|BindingFlags.NonPublic).Invoke(probe,args);
    }
    public static int Main(string[] args)
    {
        // Without the explicit flag bootstrap must not allocate a GameObject or write files.
        typeof(KinematicsProbe).GetMethod("Bootstrap",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,null);
        if (UnityEngine.GameObject.Created != 0) return 90;
        var root=new UnityEngine.GameObject("F1TENTH");
        var body=new UnityEngine.Rigidbody {transform=root.transform,position=new UnityEngine.Vector3(.1f,-3.158f,.744f)};
        var axle=new UnityEngine.Transform {name="Rear Axle Center",parent=root.transform,position=body.position};
        var controller=new VehicleController {Vehicle=root,VehicleRigidBody=body};
        var wheels=new UnityEngine.WheelCollider[4];
        for(int i=0;i<4;i++) wheels[i]=new UnityEngine.WheelCollider {attachedRigidbody=body,brakeTorque=85.6f};
        controller.FrontLeftWheelCollider=wheels[0];controller.FrontRightWheelCollider=wheels[1];
        controller.RearLeftWheelCollider=wheels[2];controller.RearRightWheelCollider=wheels[3];
        UnityEngine.Object.Vehicle=controller;
        UnityEngine.Object.Sensor=new IPS {VehicleTransform=axle,CurrentPosition=new[]{.744f,3.158f,.059f}};
        if(args[1]=="binding") axle.name="wrong";
        bool contact=args[1].StartsWith("contact_");
        string mode=args[1].Contains("treatment")?"treatment":"control";
        UnityEngine.MeshCollider[] meshes=new UnityEngine.MeshCollider[4];
        UnityEngine.Collider track=null;
        bool floor=args[1].Contains("floor");
        if(contact)
        {
            var vehicle=Child(root,"Vehicle");string[] names={"FL","FR","RL","RR"};
            for(int i=0;i<4;i++)meshes[i]=Mesh(Child(Child(vehicle,names[i]+" Wheel"),"Collider"),body,true);
            if(floor)
            {
                var surface=new UnityEngine.GameObject("Floor");
                track=new UnityEngine.BoxCollider {transform=surface.transform};
                surface.transform.Components.Add(track);UnityEngine.Object.Colliders.Add(track);
                if(args[1].Contains("dynamic"))track.attachedRigidbody=body;
                if(args[1].Contains("trigger"))track.isTrigger=true;
                if(args[1].Contains("wrongtype"))
                {
                    surface.transform.Components.Remove(track);UnityEngine.Object.Colliders.Remove(track);
                    track=Mesh(surface,null,false);
                }
            }
            else track=Mesh(Child(new UnityEngine.GameObject("Infrastructure"),"Proto Track"),null,false);
            UnityEngine.WheelCollider.Ground=track;
            if(args[1]=="contact_binding")meshes[0].enabled=false;
        }
        var probe=new KinematicsProbe();
        typeof(KinematicsProbe).GetField("directory",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(probe,args[0]);
        if(contact)typeof(KinematicsProbe).GetField("contactMode",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(probe,mode);
        if(floor)typeof(KinematicsProbe).GetField("contactTarget",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(probe,"floor");
        Invoke(probe,"Start");
        int before=UnityEngine.Physics.Calls;
        if(contact && UnityEngine.Application.ExitCode==0)
        {
            Invoke(probe,"Capture","FixedUpdate");
            var contacts=(ContactProbe)typeof(KinematicsProbe).GetField("contacts",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(probe);
            var points=meshes.Select(m=>new UnityEngine.ContactPoint {thisCollider=m,otherCollider=track,
                point=new UnityEngine.Vector3(1,0,2),normal=new UnityEngine.Vector3(0,1,0),separation=-.001f}).ToArray();
            if(args[1]=="contact_overflow")points=new UnityEngine.ContactPoint[257];
            if(args[1]=="contact_nonfinite")points[0].separation=float.NaN;
            contacts.Receive("stay",new UnityEngine.Collision {collider=track,points=points,impulse=new UnityEngine.Vector3(.1f,.2f,.3f)});
            long start=(long)typeof(KinematicsProbe).GetMethod("Now",BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,null)-1000000;
            int pid=System.Diagnostics.Process.GetCurrentProcess().Id;
            if(args[1]=="contact_stale_treatment")start-=4000000000;
            if(args[1]=="contact_foreign_treatment")pid++;
            if(args[1]=="contact_inertia_treatment" || args[1]=="contact_floor_immediate_treatment")UnityEngine.Physics.ChangeInertia=true;
            if(args[1]=="contact_cap")typeof(ContactProbe).GetProperty("TraceBytes").SetValue(contacts,1024L*1024*1024);
            if(args[1]!="contact_pending_treatment")File.WriteAllText(Path.Combine(args[0],"contact-window.request"),
                (floor?"contact-window-v2\n":"contact-window-v1\n")+pid+"\n"+mode+"\n"+
                (floor?(args[1].Contains("wrongtarget")?"proto-track\n":"floor\n"):"")+start+"\n"+(start+60000000000)+"\n");
            typeof(ContactProbe).GetField("nextPoll",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(contacts,0L);
        }
        if(args[1]=="nonfinite") body.velocity=new UnityEngine.Vector3(float.NaN,0,0);
        if(args[1]=="cap") typeof(KinematicsProbe).GetField("bytes",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(probe,1024L*1024*1024);
        if(args[1]=="nonzero") controller.CurrentThrottle=.001f;
        Invoke(probe,"Capture","FixedUpdate");
        if(args[1].Contains("natural"))body.inertiaTensor=new UnityEngine.Vector3(.2f,.3f,.4f);
        if(args[1].Contains("masschange"))body.mass+=1;
        if(args[1].Contains("comchange"))body.centerOfMass=new UnityEngine.Vector3(1,0,0);
        Invoke(probe,"Capture","LateUpdate");
        Invoke(probe,"OnApplicationQuit");
        if(contact)File.WriteAllText(Path.Combine(args[0],"fixture-calls.json"),"{\"before_request\":"+before+",\"total\":"+UnityEngine.Physics.Calls+"}");
        Console.WriteLine(UnityEngine.Application.ExitCode);
        return 0;
    }
}
