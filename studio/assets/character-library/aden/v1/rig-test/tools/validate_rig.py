"""Independent verification of the rigged Aden file (opens the saved .blend).

Checks: armature persistence, skin weights, shape keys, actions, deformation
stress (edge stretch), foot ground contact / slide, GLB contents, and renders
extra QA stills (blink peak, smile peak, face close-up, shoulder close-up).

Run:
    blender -b aden-character-rigged.blend --factory-startup --python validate_rig.py -- \
        --out <rig-test folder> --blend <rigged .blend> --glb <rigged .glb> [--qa 1]
"""
import glob
import hashlib
import json
import math
import os
import struct
import sys
import time

import bpy
from mathutils import Vector

DEG = math.radians
WARNINGS = []
RESULTS = {}


def log(msg):
    print("[VAL] %s" % (msg,), flush=True)


def warn(msg):
    WARNINGS.append(str(msg))
    log("WARNING: %s" % (msg,))


def parse_args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"out": os.path.dirname(os.path.abspath(bpy.data.filepath)),
            "blend": bpy.data.filepath, "glb": None, "qa": True}
    i = 0
    while i < len(tail):
        key = tail[i]
        if key in ("--out", "--blend", "--glb", "--qa") and i + 1 < len(tail):
            value = tail[i + 1]
            if key == "--qa":
                opts["qa"] = value.lower() not in ("0", "false", "no")
            else:
                opts[key.strip("-")] = value
            i += 2
        else:
            i += 1
    return opts


REQUIRED_BONES = [
    "root", "hips", "spine", "neck", "head", "jaw",
    "shoulder.L", "shoulder.R", "upper_arm.L", "upper_arm.R",
    "forearm.L", "forearm.R", "hand.L", "hand.R",
    "thigh.L", "thigh.R", "shin.L", "shin.R", "foot.L", "foot.R",
    "eye.L", "eye.R", "eyelid.L", "eyelid.R",
]
REQUIRED_KEYS = {"blink.L", "blink.R", "smile", "mouth_open", "brow_up"}
REQUIRED_ACTIONS = {"idle_wave": (1, 48), "blink_smile": (1, 24), "walk_cycle": (1, 32)}


def verify_structure():
    arm_obj = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("RIGTEST_")]
    check = {
        "armature_found": arm_obj is not None,
        "armature_name": arm_obj.name if arm_obj else None,
        "bone_count": len(arm_obj.data.bones) if arm_obj else 0,
        "missing_bones": [],
        "extra_bones": [],
        "mesh_objects": len(meshes),
        "meshes_parented": 0,
        "meshes_with_armature_modifier": 0,
        "meshes_without_vertex_groups": [],
        "vertex_groups_without_bone": [],
        "total_vertices": 0,
        "total_faces": 0,
        "unweighted_vertices": 0,
        "shape_keys": {},
    }
    if arm_obj is None:
        warn("no armature in file")
        return check, None

    names = [bone.name for bone in arm_obj.data.bones]
    check["missing_bones"] = [name for name in REQUIRED_BONES if name not in names]
    check["extra_bones"] = [name for name in names if name not in REQUIRED_BONES]
    deform_bones = {bone.name for bone in arm_obj.data.bones if bone.use_deform}

    for obj in meshes:
        check["total_vertices"] += len(obj.data.vertices)
        check["total_faces"] += len(obj.data.polygons)
        if obj.parent == arm_obj:
            check["meshes_parented"] += 1
        if any(mod.type == "ARMATURE" and mod.object == arm_obj for mod in obj.modifiers):
            check["meshes_with_armature_modifier"] += 1
        if not obj.vertex_groups:
            check["meshes_without_vertex_groups"].append(obj.name)
        for group in obj.vertex_groups:
            if group.name not in deform_bones:
                check["vertex_groups_without_bone"].append("%s:%s" % (obj.name, group.name))
        index_to_name = {group.index: group.name for group in obj.vertex_groups}
        for vertex in obj.data.vertices:
            total = 0.0
            for element in vertex.groups:
                if index_to_name.get(element.group) in deform_bones:
                    total += element.weight
            if total <= 1e-4:
                check["unweighted_vertices"] += 1
        if obj.data.shape_keys:
            keys = [block.name for block in obj.data.shape_keys.key_blocks if block.name != "Basis"]
            if keys:
                check["shape_keys"][obj.name] = keys

    found_keys = {name for names in check["shape_keys"].values() for name in names}
    check["missing_shape_keys"] = sorted(REQUIRED_KEYS - found_keys)

    actions = {action.name: action for action in bpy.data.actions}
    check["actions"] = sorted(actions.keys())
    check["missing_actions"] = sorted(set(REQUIRED_ACTIONS) - set(actions.keys()))
    check["action_ranges"] = {
        name: [round(v, 2) for v in actions[name].frame_range]
        for name in actions if name in REQUIRED_ACTIONS
    }
    return check, arm_obj


TRACK_OBJECTS = ["Head", "Arm_L", "Arm_R", "Hand_L", "Hand_R",
                 "Thigh_L", "Thigh_R", "Shin_L", "Shin_R",
                 "Sole_L", "Sole_R", "Mouth", "Eyelid_L", "Eyelid_R"]
STRESS_OBJECTS = ["Torso_Shirt", "Neck", "Hips_Shorts", "Shorts_Left", "Shorts_Right",
                  "Sleeve_L", "Sleeve_R", "Arm_L", "Arm_R", "Thigh_L", "Thigh_R",
                  "Shin_L", "Shin_R", "Mouth"]


def evaluated_geometry(obj, depsgraph):
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    matrix = eval_obj.matrix_world
    verts = [matrix @ vertex.co for vertex in mesh.vertices]
    edges = [(edge.vertices[0], edge.vertices[1]) for edge in mesh.edges]
    eval_obj.to_mesh_clear()
    return verts, edges


def edge_lengths(verts, edges):
    return [(verts[a] - verts[b]).length for a, b in edges]


def bounds(verts):
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    low = [min(xs), min(ys), min(zs)]
    high = [max(xs), max(ys), max(zs)]
    return {"min": low, "max": high,
            "center": [(low[i] + high[i]) / 2 for i in range(3)]}


def check_action(action, start, end, step=2):
    scene = bpy.context.scene
    arm_obj = next(o for o in bpy.data.objects if o.type == "ARMATURE")

    arm_obj.data.pose_position = "REST"
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    rest = {}
    for name in STRESS_OBJECTS:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            verts, edges = evaluated_geometry(obj, depsgraph)
            rest[name] = edge_lengths(verts, edges)
    arm_obj.data.pose_position = "POSE"

    set_action(arm_obj, action)

    samples = {}
    nonfinite = 0
    stress = {name: {"max_ratio": 1.0, "max_frame": start, "bad_edges": 0}
              for name in STRESS_OBJECTS}

    for frame in range(start, end + 1, step):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        for name in TRACK_OBJECTS:
            obj = bpy.data.objects.get(name)
            if obj is None:
                continue
            verts, _ = evaluated_geometry(obj, depsgraph)
            if any(not all(math.isfinite(c) for c in vertex) for vertex in verts):
                nonfinite += 1
            samples.setdefault(name, []).append({"frame": frame, "bounds": bounds(verts)})

        if frame in (start, (start + end) // 2, end):
            for name in STRESS_OBJECTS:
                obj = bpy.data.objects.get(name)
                if obj is None:
                    continue
                verts, edges = evaluated_geometry(obj, depsgraph)
                lengths = edge_lengths(verts, edges)
                base = rest.get(name) or []
                ratio = 1.0
                bad = 0
                for index, value in enumerate(lengths):
                    if index >= len(base) or base[index] < 1e-7:
                        continue
                    current = value / base[index]
                    ratio = max(ratio, current)
                    if current > 2.0:
                        bad += 1
                if ratio > stress[name]["max_ratio"]:
                    stress[name]["max_ratio"] = ratio
                    stress[name]["max_frame"] = frame
                stress[name]["bad_edges"] = max(stress[name]["bad_edges"], bad)

    motion = {}
    for name, rows in samples.items():
        centers = [row["bounds"]["center"] for row in rows]
        motion[name] = {
            "center_range": [round(max(c[i] for c in centers) - min(c[i] for c in centers), 4)
                             for i in range(3)],
            "lowest_z": round(min(row["bounds"]["min"][2] for row in rows), 4),
            "highest_z": round(max(row["bounds"]["max"][2] for row in rows), 4),
            "frames_sampled": len(rows),
        }

    feet = {}
    for side in ("L", "R"):
        name = "Sole_" + side
        rows = samples.get(name, [])
        if not rows:
            continue
        ground = min(row["bounds"]["min"][2] for row in rows)
        contact = [row for row in rows if row["bounds"]["min"][2] <= ground + 0.004]
        xs = [row["bounds"]["center"][0] for row in contact]
        ys = [row["bounds"]["center"][1] for row in contact]
        feet[name] = {
            "lowest_z": round(ground, 4),
            "contact_samples": len(contact),
            "slide_x": round(max(xs) - min(xs), 4) if xs else 0.0,
            "slide_y": round(max(ys) - min(ys), 4) if ys else 0.0,
        }

    return {
        "action": action.name,
        "frames": [start, end],
        "sampled_step": step,
        "motion": motion,
        "stress": stress,
        "feet": feet,
        "nonfinite_objects": nonfinite,
    }


def read_glb(path):
    with open(path, "rb") as handle:
        data = handle.read()
    magic, version, total = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise ValueError("not a GLB container")
    offset = 12
    while offset < len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:  # JSON
            return json.loads(chunk.decode("utf-8"))
    raise ValueError("no JSON chunk in GLB")


def glb_summary(path):
    if not path or not os.path.exists(path):
        return {"exists": False, "path": path}
    gltf = read_glb(path)
    animations = gltf.get("animations", [])
    skins = gltf.get("skins", [])
    meshes = gltf.get("meshes", [])
    morph_prims = 0
    for mesh in meshes:
        for primitive in mesh.get("primitives", []):
            if primitive.get("targets"):
                morph_prims += 1
    return {
        "exists": True,
        "path": path,
        "bytes": os.path.getsize(path),
        "animation_count": len(animations),
        "animations": [{"name": a.get("name"),
                        "channels": len(a.get("channels", [])),
                        "samplers": len(a.get("samplers", []))} for a in animations],
        "skin_count": len(skins),
        "max_joints": max((len(s.get("joints", [])) for s in skins), default=0),
        "mesh_count": len(meshes),
        "morph_target_primitives": morph_prims,
        "node_count": len(gltf.get("nodes", [])),
        "material_count": len(gltf.get("materials", [])),
        "generator": gltf.get("asset", {}).get("generator"),
    }


def set_action(arm_obj, action):
    """Assign the action to the armature *and* to the matching shape-key slots."""
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = action
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.data.shape_keys is None:
            continue
        keys = obj.data.shape_keys
        anim = keys.animation_data
        if anim is None:
            continue
        target = None
        if hasattr(action, "slots"):
            try:
                wanted = str(keys["rig_action_slot"])
            except KeyError:
                wanted = None
            if wanted:
                for slot in action.slots:
                    if getattr(slot, "identifier", None) == wanted:
                        target = slot
                        break
            if target is None:
                key_slots = [slot for slot in action.slots
                             if getattr(slot, "target_id_type", "KEY") == "KEY"]
                if len(key_slots) == 1:
                    target = key_slots[0]
        if target is not None:
            anim.action = action
            anim.action_slot = target
        else:
            anim.action = None
            for block in keys.key_blocks:
                block.value = 0.0


def render_qa(arm_obj, qa_dir):
    scene = bpy.context.scene
    shots = [
        ("blink_smile", 8, "qa_blink_peak_f08.png", None),
        ("blink_smile", 16, "qa_smile_peak_f16.png", None),
        ("blink_smile", 8, "qa_face_closeup_blink_f08.png", "face"),
        ("blink_smile", 18, "qa_face_closeup_smile_f18.png", "face"),
        ("blink_smile", 1, "qa_face_closeup_rest_f01.png", "face"),
        ("walk_cycle", 5, "qa_walk_contact_f05.png", None),
        ("walk_cycle", 9, "qa_walk_passing_f09.png", None),
        ("idle_wave", 21, "qa_idle_wave_peak_f21.png", None),
        ("idle_wave", 21, "qa_shoulder_closeup_f21.png", "shoulder"),
    ]
    cam_main = scene.camera
    cam_data = bpy.data.cameras.new("RIGTEST_FaceCam")
    cam_data.lens = 70.0
    cam_face = bpy.data.objects.new("RIGTEST_FaceCam", cam_data)
    scene.collection.objects.link(cam_face)

    def aim(obj, location, target):
        obj.location = Vector(location)
        obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()

    results = []
    for action_name, frame, filename, view in shots:
        action = bpy.data.actions.get(action_name)
        if action is None:
            warn("QA shot skipped, missing action %s" % action_name)
            continue
        set_action(arm_obj, action)
        if view == "face":
            aim(cam_face, (0.58, -1.50, 0.99), (0.0, -0.02, 0.900))
            scene.camera = cam_face
        elif view == "shoulder":
            aim(cam_face, (0.75, -0.85, 1.00), (0.16, 0.0, 0.62))
            scene.camera = cam_face
        else:
            scene.camera = cam_main
        scene.frame_set(frame)
        path = os.path.join(qa_dir, filename)
        if os.path.exists(path):
            warn("QA still already exists, skipped: %s" % path)
            results.append({"path": path, "skipped": True})
            continue
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        results.append({"path": path, "action": action_name, "frame": frame,
                        "view": view or "main", "bytes": os.path.getsize(path)})
        log("QA still: %s" % path)
    scene.camera = cam_main
    return results


def check_face_channels():
    """Proves the shape keys are actually driven by the action (values + geometry)."""
    arm_obj = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    action = bpy.data.actions.get("blink_smile")
    if action is None:
        return {}
    set_action(arm_obj, action)
    scene = bpy.context.scene
    values = {}
    for frame in (1, 8, 16, 24):
        scene.frame_set(frame)
        rows = {}
        for name in ("Eyelid_L", "Eyelid_R", "Mouth", "Brow_L", "Brow_R"):
            obj = bpy.data.objects.get(name)
            if obj and obj.data.shape_keys:
                rows[name] = {b.name: round(b.value, 3)
                              for b in obj.data.shape_keys.key_blocks if b.name != "Basis"}
        values[str(frame)] = rows

    mouth = bpy.data.objects["Mouth"]
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    rest = bounds(evaluated_geometry(mouth, depsgraph)[0])
    scene.frame_set(16)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    smile = bounds(evaluated_geometry(mouth, depsgraph)[0])

    def size(box):
        return [round(box["max"][i] - box["min"][i], 4) for i in range(3)]

    eyelid = bpy.data.objects.get("Eyelid_L")
    scene.frame_set(8)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    lid_closed = bounds(evaluated_geometry(eyelid, depsgraph)[0]) if eyelid else None
    scene.frame_set(1)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    lid_open = bounds(evaluated_geometry(eyelid, depsgraph)[0]) if eyelid else None

    return {
        "values_at_frames": values,
        "mouth_size_rest": size(rest),
        "mouth_size_smile": size(smile),
        "eyelid_size_open": size(lid_open) if lid_open else None,
        "eyelid_size_closed": size(lid_closed) if lid_closed else None,
        "eyelid_min_z_open": round(lid_open["min"][2], 4) if lid_open else None,
        "eyelid_min_z_closed": round(lid_closed["min"][2], 4) if lid_closed else None,
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconcile_manifest(out_dir):
    """Attach the real rendered media (names include Blender's frame range)."""
    path = os.path.join(out_dir, "rig-manifest.json")
    if not os.path.exists(path):
        warn("no rig-manifest.json to reconcile")
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    preview_dir = os.path.join(out_dir, "previews")
    videos = []
    for action in manifest.get("actions", []):
        name = action.get("name")
        found = sorted(glob.glob(os.path.join(preview_dir, name + "*.mp4")))
        if not found:
            warn("missing video for %s" % name)
            continue
        video = found[0]
        videos.append({
            "action": name,
            "path": video,
            "bytes": os.path.getsize(video),
            "sha256": sha256_file(video),
            "frame_start": action.get("frame_start"),
            "frame_end": action.get("frame_end"),
            "fps": 24,
            "resolution": "640x640",
        })
    stills = manifest.get("renders", {}).get("stills", [])
    for entry in stills:
        still_path = entry.get("path")
        if still_path and os.path.exists(still_path):
            entry["bytes"] = os.path.getsize(still_path)
            entry["sha256"] = sha256_file(still_path)
    manifest.setdefault("renders", {})
    manifest["renders"]["stills"] = stills
    manifest["renders"]["videos"] = videos
    manifest["warnings"] = [text for text in manifest.get("warnings", [])
                            if "no mp4 produced" not in text]
    manifest["media_reconciled_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    log("manifest reconciled: %d videos / %d stills" % (len(videos), len(stills)))
    return {"videos": videos, "still_count": len(stills), "manifest": path}


def main():
    opts = parse_args()
    blend = os.path.abspath(opts["blend"])
    out_dir = os.path.abspath(opts["out"])
    qa_dir = os.path.join(out_dir, "previews", "qa")
    os.makedirs(qa_dir, exist_ok=True)
    log("reopened file: %s" % blend)
    log("armature objects: %s" % [o.name for o in bpy.data.objects if o.type == "ARMATURE"])

    structure, arm_obj = verify_structure()
    action_checks = {}
    for name, (start, end) in REQUIRED_ACTIONS.items():
        action = bpy.data.actions.get(name)
        if action is None:
            warn("missing action %s" % name)
            continue
        action_checks[name] = check_action(action, start, end)
        hand = action_checks[name]["motion"].get("Hand_R", {}).get("center_range")
        log("%s: hand_R travel=%s, foot slide L=%s" % (
            name, hand, action_checks[name]["feet"].get("Sole_L", {}).get("slide_y")))

    glb = glb_summary(opts.get("glb"))
    face_channels = check_face_channels()
    blink_peak = (face_channels.get("values_at_frames", {})
                  .get("8", {}).get("Eyelid_L", {}).get("blink.L"))
    log("blink.L at frame 8 = %s ; mouth size rest=%s smile=%s" % (
        blink_peak, face_channels.get("mouth_size_rest"),
        face_channels.get("mouth_size_smile")))
    qa = render_qa(arm_obj, qa_dir) if (opts.get("qa") and arm_obj) else []
    media = reconcile_manifest(out_dir)

    findings = []
    if structure["missing_bones"]:
        findings.append({"level": "error", "text": "missing bones: %s" % structure["missing_bones"]})
    if structure.get("missing_shape_keys"):
        findings.append({"level": "error",
                         "text": "missing shape keys: %s" % structure["missing_shape_keys"]})
    if structure["missing_actions"]:
        findings.append({"level": "error", "text": "missing actions: %s" % structure["missing_actions"]})
    if structure["unweighted_vertices"]:
        findings.append({"level": "error", "text": "%d unweighted vertices"
                                                    % structure["unweighted_vertices"]})
    if blink_peak is not None and blink_peak < 0.9:
        findings.append({"level": "error",
                         "text": "blink.L only reached %.2f at frame 8 (shape key not driven)"
                                 % blink_peak})
    if structure["meshes_parented"] < structure["mesh_objects"]:
        findings.append({"level": "warn", "text": "only %d/%d meshes parented to the rig" % (
            structure["meshes_parented"], structure["mesh_objects"])})
    if structure["meshes_with_armature_modifier"] < structure["mesh_objects"]:
        findings.append({"level": "warn", "text": "only %d/%d meshes have the armature modifier" % (
            structure["meshes_with_armature_modifier"], structure["mesh_objects"])})

    worst_stress = 1.0
    worst_object = None
    for name, data in action_checks.items():
        if data["nonfinite_objects"]:
            findings.append({"level": "error", "text": "%s produced non-finite vertices" % name})
        for obj_name, stress in data["stress"].items():
            if stress["max_ratio"] > worst_stress:
                worst_stress = stress["max_ratio"]
                worst_object = "%s/%s" % (name, obj_name)
            if stress["max_ratio"] > 2.5:
                findings.append({"level": "error",
                                 "text": "%s: %s stretches x%.2f at frame %s (tearing)"
                                         % (name, obj_name, stress["max_ratio"],
                                            stress["max_frame"])})
        for foot, info in data["feet"].items():
            if info["lowest_z"] < -0.002:
                findings.append({"level": "warn", "text": "%s: %s goes below the floor (z=%.4f)"
                                                         % (name, foot, info["lowest_z"])})

    if glb.get("exists"):
        if glb.get("animation_count", 0) < 3:
            findings.append({"level": "warn", "text": "GLB contains %s animations (expected 3)"
                                                     % glb.get("animation_count")})
        if glb.get("skin_count", 0) < 1:
            findings.append({"level": "error", "text": "GLB has no skin"})
        if glb.get("morph_target_primitives", 0) < 1:
            findings.append({"level": "warn", "text": "GLB has no morph target primitives"})
    else:
        findings.append({"level": "error", "text": "GLB missing: %s" % opts.get("glb")})

    results = {
        "schema": "ahos.character-rig-validation.v1",
        "validated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blend": blend,
        "reopen_ok": bool(arm_obj is not None and not structure["missing_bones"]),
        "structure": structure,
        "actions": action_checks,
        "face_channels": face_channels,
        "glb": glb,
        "media": media,
        "qa_stills": qa,
        "worst_edge_stretch": {"ratio": round(worst_stress, 3), "where": worst_object},
        "findings": findings,
        "warnings": WARNINGS,
    }
    path = os.path.join(out_dir, "validation.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, ensure_ascii=False)
    log("validation written: %s" % path)
    log("findings: %d" % len(findings))
    for finding in findings:
        log("  [%s] %s" % (finding["level"], finding["text"]))
    print("VALIDATION_OK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("VALIDATION_FAILED", flush=True)
        sys.exit(1)




