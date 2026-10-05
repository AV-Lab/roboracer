// Actual PoseTrace implementation under controlled clock/state; no native physics claim.
using System;
using System.IO;
using System.Reflection;
using UnityEngine;
using RoboRacer.Qualification;

public static class PoseFixture
{
    static GameObject Child(GameObject parent,string name)
    { var v=new GameObject(name);v.transform.parent=parent.transform;return v; }
    public static int Main(string[] args)
    {
        string output=args[0],test=args[1],error="";
        PoseTrace.Mark(null,999); // Disabled hooks are inert.
        if(GameObject.Created!=0)return 90;
        var root=new GameObject("F1TENTH");var visual=Child(root,"Vehicle");
        var body=new Rigidbody {transform=root.transform,position=new Vector3(0,0,.75f)};
        var controller=new VehicleController {Vehicle=root,VehicleRigidBody=body};
        var recorder=new DataRecorder {Vehicles=new[]{root},VehicleRigidBodies=new[]{body},VehicleControllers=new[]{controller}};
        UnityEngine.Object.Recorder=recorder;
        var wheels=new WheelCollider[4];var transforms=new Transform[4];
        string[] names={"FL","FR","RL","RR"};
        for(int i=0;i<4;i++)
        {
            transforms[i]=Child(visual,names[i]+" Wheel").transform;
            var c=Child(transforms[i].gameObject,"Collider");
            var mesh=new MeshCollider {transform=c.transform,attachedRigidbody=body};
            c.transform.Components.Add(mesh);UnityEngine.Object.Colliders.Add(mesh);
            wheels[i]=new WheelCollider {attachedRigidbody=body};
        }
        controller.FrontLeftWheelCollider=wheels[0];controller.FrontRightWheelCollider=wheels[1];
        controller.RearLeftWheelCollider=wheels[2];controller.RearRightWheelCollider=wheels[3];
        controller.FrontLeftWheelTransform=transforms[0];controller.FrontRightWheelTransform=transforms[1];
        controller.RearLeftWheelTransform=transforms[2];controller.RearRightWheelTransform=transforms[3];
        var floor=new GameObject("Floor");var surface=new BoxCollider {transform=floor.transform};
        floor.transform.Components.Add(surface);UnityEngine.Object.Colliders.Add(surface);
        long clock=100000000000;Func<long> now=()=>++clock;PoseTrace pose=null;
        var contacts=new ContactProbe("control",output,body,root.transform,now,()=>pose==null?0:pose.TraceBytes,e=>error=e.ToString(),"floor");
        long start=clock-1000,end=start+(test=="duration"?11000000000:10000000000);
        if(test!="pending")
        {
            File.WriteAllText(Path.Combine(output,"contact-window.request"),"contact-window-v2\n"+
                System.Diagnostics.Process.GetCurrentProcess().Id+"\ncontrol\nfloor\n"+start+"\n"+end+"\n");
            contacts.PollWindow();
        }
        if(test=="binding")controller.FrontLeftWheelTransform=transforms[1];
        try
        {
            pose=new PoseTrace(output,controller,contacts,now,()=>contacts.TraceBytes,e=>error=e.ToString());
            if(test=="cap")typeof(PoseTrace).GetProperty("TraceBytes").SetValue(pose,1024L*1024*1024);
            if(test=="nonfinite")body.inertiaTensor=new Vector3(float.NaN,1,2);
            if(test=="recorder")recorder.Saving=true;
            if(test=="nonzero")controller.CurrentThrottle=.1f;
            if(test=="foreign")PoseTrace.Mark(new VehicleController(),0);
            Time.fixedDeltaTime=.0010000000474974513f;
            for(int s=0;s<2;s++)
            {
                Time.fixedTimeAsDouble=s*(double)Time.fixedDeltaTime;Time.timeAsDouble=Time.fixedTimeAsDouble;Time.frameCount=10+s;
                for(int stage=0;stage<7;stage++)PoseTrace.Mark(controller,stage);
                for(int w=0;w<4;w++)for(int stage=10;stage<18;stage++)
                {
                    if(test=="reorder" && w==0 && stage==12)continue;
                    PoseTrace.Mark(controller,stage,wheels[w],transforms[w]);
                    // Known injected shift between position-write brackets: one float32 ULP.
                    if(stage==13)body.position=new Vector3(0,0,body.position.z+(float)Math.Pow(2,-24));
                }
                PoseTrace.Mark(controller,7);PoseTrace.Mark(controller,8);
            }
            clock=end+1;PoseTrace.Mark(controller,0);pose.Flush();
        }
        catch(Exception e){error=e.ToString();}
        string fields=pose==null?"":pose.StatusFields();
        File.WriteAllText(Path.Combine(output,"pose-fixture.json"),"{\"error\":\""+error.Replace("\\","\\\\").Replace("\"","\\\"").Replace("\r"," ").Replace("\n"," ")+"\",\"physics_setters\":"+Physics.Calls+fields+"}");
        if(pose!=null)pose.Dispose();contacts.Dispose();return 0;
    }
}
