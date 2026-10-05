"""Contact diagnostic contracts and offline evidence; no import-time operations."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


TARGETS = [f"F1TENTH/Vehicle/{wheel} Wheel/Collider" for wheel in ("FL", "FR", "RL", "RR")]
TRACK = "Infrastructure/Proto Track"
PROFILES = {"proto-track": (TRACK, "MeshCollider", "time-constant"),
            "floor": ("Floor", "BoxCollider", "intervention-local")}


def mass_com(properties):
    return {k: properties[k] for k in ("mass", "center_of_mass")}


def _finite(value):
    if isinstance(value, dict):
        for x in value.values(): _finite(x)
    elif isinstance(value, list):
        for x in value: _finite(x)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite contact evidence")


def player_identity(player):
    names = [player.name, "GameAssembly.so", "UnityPlayer.so", "AutoDRIVE_Data/level0",
             "AutoDRIVE_Data/globalgamemanagers", "AutoDRIVE_Data/sharedassets0.assets"]
    return {name: hashlib.sha256((player.parent / name).read_bytes()).hexdigest() for name in names}


def check_status(state, mode, start, end, now, closed=False, target="proto-track"):
    if mode not in ("control", "treatment") or state.get("contact_mode") != mode:
        raise RuntimeError("Contact mode does not match the owned trial")
    if (target not in PROFILES or state.get("contact_target", "proto-track") != target or
            state.get("inertia_policy", "time-constant") != PROFILES[target][2]):
        raise RuntimeError("Contact target/policy does not match the owned trial")
    keys = ("contact_bytes", "contact_records", "collision_records", "contact_window_start_ns",
            "contact_window_end_ns", "contact_activation_ns", "contact_total_ns", "contact_max_ns")
    if any(type(state.get(k)) is not int or state[k] < 0 for k in keys):
        raise RuntimeError("Malformed contact counters")
    if type(state.get("trace_bytes")) is not int or state["trace_bytes"] < 0:
        raise RuntimeError("Malformed kinematics byte counter")
    if not state["contact_bytes"] or state["trace_bytes"] + state["contact_bytes"] > 1024**3:
        raise RuntimeError("Combined contact trace exceeded the diagnostic bound")
    if state["contact_records"] - state["collision_records"] not in (0, 1):
        raise RuntimeError("Contact activation/collision counters disagree")
    counts = state.get("contact_pair_counts")
    if not isinstance(counts, list) or len(counts) != 4 or any(type(x) is not int or x < 0 for x in counts):
        raise RuntimeError("Malformed contact pair counters")
    activated = state["contact_activation_ns"]
    if start is None:
        if activated or state["contact_window_start_ns"] or state["contact_window_end_ns"]:
            raise RuntimeError("Contact intervention activated before complete telemetry")
    elif activated:
        if (state["contact_window_start_ns"], state["contact_window_end_ns"]) != (start, end):
            raise RuntimeError("Contact activation has the wrong observation interval")
        if not start <= activated <= min(end, start + 3_000_000_000, now):
            raise RuntimeError("Invalid contact activation timestamp")
    elif closed or now - start > 3_000_000_000:
        raise RuntimeError("Contact window request was not acknowledged")


def write_window_request(directory, pid, mode, start, end, target="proto-track"):
    if (target not in PROFILES or mode not in ("control", "treatment") or type(pid) is not int or pid <= 0 or
            type(start) is not int or type(end) is not int or start <= 0 or not 0 < end-start <= 60_000_000_000):
        raise ValueError("Invalid contact window request")
    path = directory / "contact-window.request"
    if path.exists():
        raise ValueError("Contact window request already exists")
    value = f"contact-window-v1\n{pid}\n{mode}\n{start}\n{end}\n"
    if target == "floor":
        value = f"contact-window-v2\n{pid}\n{mode}\n{target}\n{start}\n{end}\n"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(value)
    temporary.replace(path)
    return {"path": str(path), "sha256": hashlib.sha256(value.encode()).hexdigest()}


def analyze_contacts(directory, run, kinematics):
    path = directory / "contacts.jsonl"
    status = json.loads((directory / "status.json").read_text())
    start, end = run["observation_start_ns"], run["diagnostic_deadline_ns"]
    target = run.get("contact_target", "proto-track")
    surface, surface_type, policy = PROFILES[target]
    check_status(status, run["contact_mode"], start, end, status["heartbeat_monotonic_ns"], closed=True, target=target)
    digest = hashlib.sha256()
    counts, all_counts, phases, pairs = Counter(), Counter(), Counter(), {}
    records = collisions = 0
    last_ns = 0
    activations = []
    with path.open("rb") as stream:
        line = next(stream); digest.update(line); header = json.loads(line); _finite(header)
        if header.get("kind") != "contact_binding" or header.get("schema") not in (1, 2) or header.get("mode") != run["contact_mode"]:
            raise ValueError("Wrong contact trace binding")
        if (header.get("target_profile", "proto-track") != target or
                header.get("inertia_policy", "time-constant") != policy or (target == "floor" and header["schema"] != 2)):
            raise ValueError("Wrong contact target/policy binding")
        if header.get("pid") != kinematics["binding"]["pid"]:
            raise ValueError("Wrong contact producer PID")
        if header.get("clock") != "Linux CLOCK_MONOTONIC":
            raise ValueError("Wrong contact clock")
        registry = {c["id"]: c for c in header["colliders"]}
        ids, track = header["wheel_mesh_ids"], header["track_id"]
        if len(registry) != len(header["colliders"]) or len(ids) != 4 or len(set(ids)) != 4:
            raise ValueError("Ambiguous contact binding")
        if [registry[i]["path"] for i in ids] != TARGETS or registry[track]["path"] != surface:
            raise ValueError("Wrong contact target paths")
        if any(registry[i]["type"] != (surface_type if i == track else "MeshCollider") or not registry[i]["enabled"] or registry[i]["trigger"] for i in [*ids, track]):
            raise ValueError("Wrong contact target types/state")
        if header["schema"] == 2 and (registry[track]["attached_body_id"] != 0 or
                any(not registry[i]["convex"] or registry[i]["attached_body_id"] == 0 for i in ids) or
                len({registry[i]["attached_body_id"] for i in ids}) != 1):
            raise ValueError("Wrong contact rigidbody/convex binding")
        for line in stream:
            digest.update(line); row = json.loads(line); _finite(row)
            if row["index"] != records or row["monotonic_ns"] <= last_ns:
                raise ValueError("Missing/reordered contact records")
            records += 1; last_ns = row["monotonic_ns"]
            if row["kind"] == "window_activation":
                activations.append(row); continue
            if row["kind"] != "collision" or row["phase"] not in ("enter", "stay", "exit"):
                raise ValueError("Unexpected contact record")
            collisions += 1
            inside = start <= row["monotonic_ns"] <= end
            if inside: phases[row["phase"]] += 1
            for p in row["points"]:
                pair = {p["a"], p["b"]}
                pair_target = next((i for i in ids if pair == {i, track}), None)
                if pair_target is not None:
                    all_counts[pair_target] += 1
                    if inside: counts[pair_target] += 1
                if inside:
                    names = sorted([registry[p["a"]]["path"], registry[p["b"]]["path"]])
                    key = " <-> ".join(names)
                    value = pairs.setdefault(key, {"points": 0, "separation_min_m": p["separation"],
                        "separation_max_m": p["separation"], "normal_min": p["normal"][:], "normal_max": p["normal"][:]})
                    value["points"] += 1
                    value["separation_min_m"] = min(value["separation_min_m"], p["separation"])
                    value["separation_max_m"] = max(value["separation_max_m"], p["separation"])
                    value["normal_min"] = [min(a,b) for a,b in zip(value["normal_min"],p["normal"])]
                    value["normal_max"] = [max(a,b) for a,b in zip(value["normal_max"],p["normal"])]
    if records != status["contact_records"] or collisions != status["collision_records"] or path.stat().st_size != status["contact_bytes"]:
        raise ValueError("Contact trace/final counters disagree")
    if [all_counts[i] for i in ids] != status["contact_pair_counts"] or len(activations) != 1:
        raise ValueError("Contact pair/activation accounting disagrees")
    activation = activations[0]
    if (activation["mode"], activation["start_ns"], activation["end_ns"], activation["monotonic_ns"]) != (
            run["contact_mode"], start, end, status["contact_activation_ns"]):
        raise ValueError("Contact activation record disagrees with the run")
    if activation["before_ignored"] != [False]*4 or activation["after_ignored"] != [run["contact_mode"] == "treatment"]*4:
        raise ValueError("Incorrect collision-pair intervention")
    properties = [p["contact_state"] for p in kinematics["phases"].values()]
    constant = all(p["properties_constant"] for p in properties)
    constant = constant and all(p["first_properties"] == activation["properties"] for p in properties)
    local_equal = None
    if header["schema"] == 2:
        if activation.get("target_profile") != target:
            raise ValueError("Activation target differs")
        local_equal = activation["before_properties"] == activation["after_properties"] == activation["properties"]
    mass_com_constant = all(p.get("mass_com_constant", p["properties_constant"]) and
                            mass_com(p["first_properties"]) == mass_com(activation["properties"]) for p in properties)
    return {"binding": header, "trace_sha256": digest.hexdigest(), "records": records, "collision_records": collisions,
            "trace_bytes": path.stat().st_size, "window_collision_phases": dict(phases),
            "window_target_points": {registry[i]["path"]: counts[i] for i in ids}, "window_pairs": pairs,
            "activation": activation, "activation_delay_ms": (activation["monotonic_ns"]-start)/1e6,
            "properties_constant": constant, "properties": activation["properties"],
            "mass_com_constant": mass_com_constant, "immediate_properties_equal": local_equal,
            "contact_callback_mean_ms": status["contact_total_ns"] / collisions / 1e6 if collisions else None,
            "contact_callback_max_ms": status["contact_max_ns"] / 1e6,
            "limits": ["Point counts include repeated contacts, not independent collision events",
                       "No stay callbacks from sleeping bodies; absence alone does not prove no contact",
                       "Aggregate collision impulse is not a separate per-point impulse"]}


def make_gate(analysis, source):
    runs = analysis["runs"]
    reasons = []
    target = analysis["attempt"].get("contact_target", "proto-track")
    surface, surface_type, policy = PROFILES[target]
    if len(runs) != 2 or analysis["attempt"].get("contact_mode") != "control": reasons.append("Exactly two controls required")
    identities, pids, properties = [], [], []
    for r in runs:
        c = r.get("contact_analysis")
        if not c or not r.get("completed_diagnostic_window") or r.get("error"):
            reasons.append(r["run"]+": incomplete control evidence");continue
        if r.get("contact_mode") != "control" or c["binding"]["mode"] != "control":
            reasons.append(r["run"]+": not a control")
        if any(c["window_target_points"].get(p,0) <= 0 for p in TARGETS): reasons.append(r["run"]+": not all four target contact pairs observed")
        if r.get("contact_target", "proto-track") != target or c["binding"].get("target_profile", "proto-track") != target:
            reasons.append(r["run"]+": contact target differs")
        if target == "floor":
            if c["binding"].get("schema") != 2 or c["binding"].get("inertia_policy") != policy:
                reasons.append(r["run"]+": Floor policy evidence missing")
            if not c.get("mass_com_constant"): reasons.append(r["run"]+": mass/COM varies")
            if c.get("immediate_properties_equal") is not True: reasons.append(r["run"]+": immediate properties differ")
        elif not c["properties_constant"]: reasons.append(r["run"]+": mass/COM/inertia varies")
        if any(x["exit_code"] != 0 or not x["reaped"] for x in r["children"]) or not r["endpoint_released"]:
            reasons.append(r["run"]+": cleanup failed")
        if r["bridge_status"].get("errors") or any(r["recorded_message_counts"].get(t,0) == 0 for t in
            ("throttle","steering","left_encoder","right_encoder","ips","imu","lidar","front_camera")):
            reasons.append(r["run"]+": transport evidence incomplete")
        identities.append(r["player_identity"]); pids.append(r["kinematics_analysis"]["binding"]["pid"])
        properties.append(mass_com(c["properties"]) if target == "floor" else c["properties"])
    if len(pids)!=2 or len(set(pids))!=2: reasons.append("Controls must use distinct fresh processes")
    if not identities or any(x!=identities[0] for x in identities): reasons.append("Player identity differs")
    if not properties or any(x!=properties[0] for x in properties): reasons.append("Control mass/COM differs" if target == "floor" else "Control mass/COM/inertia differs")
    result = {"schema":1,"eligible":not reasons,"reasons":reasons,"targets":TARGETS,"track":surface,
            "control_analysis":str(source.resolve()),"control_analysis_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "player_identity":identities[0] if identities else None,"properties":properties[0] if properties else None,
            "p0_accepted":False,"maximum_treatment_runs":2}
    if target == "floor": result.update(schema=2, contact_target=target, inertia_policy=policy)
    return result


def verify_gate(path, player, target="proto-track"):
    gate = json.loads(path.read_text()); source = Path(gate["control_analysis"])
    if gate.get("contact_target", "proto-track") != target:
        raise ValueError("Control gate contact target differs from requested treatment")
    if hashlib.sha256(source.read_bytes()).hexdigest() != gate.get("control_analysis_sha256"):
        raise ValueError("Control analysis fingerprint changed")
    actual = make_gate(json.loads(source.read_text()), source)
    if gate != actual or not actual["eligible"] or actual["player_identity"] != player_identity(player):
        raise ValueError("Contact treatment gate failed: " + repr(actual["reasons"]))
    evidence = json.loads(source.read_text())
    for name, expected in evidence["source_sha256"].items():
        if hashlib.sha256((Path(evidence["results_path"])/name).read_bytes()).hexdigest() != expected:
            raise ValueError("Control raw evidence changed: " + name)
    return gate
