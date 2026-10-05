using UnityEngine;

namespace RoboRacer.Qualification
{
    // Attached only under the explicitly enabled contact diagnostic.
    public sealed class ContactRelay : MonoBehaviour
    {
        public ContactProbe Owner;
        void OnCollisionEnter(Collision value) { if (Owner != null) Owner.Receive("enter", value); }
        void OnCollisionStay(Collision value) { if (Owner != null) Owner.Receive("stay", value); }
        void OnCollisionExit(Collision value) { if (Owner != null) Owner.Receive("exit", value); }
    }
}
