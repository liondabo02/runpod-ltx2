"""AHOS Rig Factory v0.1 — spec-driven rig builder (no per-character code).

Two modes:
  derive : read a character .blend, measure its parts, write character-spec.json
  build  : read character-spec.json, build armature + skinning + shape keys +
           actions, save .blend/.glb + manifest

    blender -b model.blend --factory-startup --python rig_factory.py -- \
        --mode derive --character aden --out specs/aden.json

    blender -b model.blend --factory-startup --python rig_factory.py -- \
        --mode build --spec specs/aden.json --out out/aden [--render none|stills]

Conventions (the only contract a character must satisfy):
  Head, Neck, Torso*, Hips*, Shorts_*, Sleeve_L/R, Arm_L/R, Hand_L/R,
  Thigh_L/R, Shin_L/R, Shoe_Upper_L/R, Sole_L/R, Eye_White_L/R,
  Eye_Iris_L/R, Eye_Pupil_L/R, Eye_Glint_L/R, Eyelid_L/R, Brow_L/R,
  Mouth, Teeth, Tongue, Hair*, Ear_L/R, Nose, Freckle*
"""
import glob
import hashlib
import json
import math
import os
import sys
import time

import bpy
from mathutils import Quaternion, Vector

DEG = math.radians
TAU = math.tau
WARN = []


def log(msg):
    print("[FACTORY] %s" % (msg,), flush=True)


def warn(msg):
    WARN.append(str(msg))
    log("WARNING: %s" % (msg,))


def parse_args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"mode": "derive", "character": None, "out": None, "spec": None,
            "render": "none"}
    i = 0
    while i < len(tail):
        key = tail[i]
        if key in ("--mode", "--character", "--out", "--spec", "--render") and i + 1 < len(tail):
            opts[key.strip("-")] = tail[i + 1]
            i += 2
        else:
            i += 1
    return opts


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(path):
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    return "%s_%s%s" % (root, time.strftime("%Y%m%d-%H%M%S"), ext)


# ---------------------------------------------------------------------------
# measurement helpers
# ---------------------------------------------------------------------------
def part_bounds(objects):
    low = Vector((1e9, 1e9, 1e9))
    high = Vector((-1e9, -1e9, -1e9))
    for obj in objects:
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            for axis in range(3):
                low[axis] = min(low[axis], point[axis])
                high[axis] = max(high[axis], point[axis])
    return {"min": [round(v, 5) for v in low], "max": [round(v, 5) for v in high],
            "center": [round((low[i] + high[i]) / 2, 5) for i in range(3)],
            "size": [round(high[i] - low[i], 5) for i in range(3)]}


def meshes():
    return [o for o in bpy.context.scene.objects
            if o.type == "MESH" and not o.name.startswith("RIGTEST_")]


def group(name_list, all_meshes):
    """Union bounds of every object whose name matches any of the patterns."""
    chosen = []
    for obj in all_meshes:
        for pattern in name_list:
            if pattern.endswith("*") and obj.name.startswith(pattern[:-1]):
                chosen.append(obj)
                break
            if obj.name == pattern:
                chosen.append(obj)
                break
    if not chosen:
        return None
    return part_bounds(chosen), [o.name for o in chosen]


# ---------------------------------------------------------------------------
# mode 1: derive a spec from the mesh alone
# ---------------------------------------------------------------------------
def derive_spec(character_id):
    objs = meshes()
    if not objs:
        raise RuntimeError("no character meshes in the scene")

    def need(patterns):
        found = group(patterns, objs)
        if found is None:
            raise RuntimeError("missing part: %s" % (patterns,))
        return found[0]

    B = {
        "head": need(["Head"]),
        "neck": need(["Neck"]),
        "torso": need(["Torso_Shirt", "Torso*"]),
        "hips": need(["Hips_Shorts", "Hips*"]),
        "mouth": need(["Mouth"]),
        "brow": need(["Brow_L", "Brow_R"]),
    }
    for side in ("L", "R"):
        B["sleeve_" + side] = need(["Sleeve_" + side])
        B["arm_" + side] = need(["Arm_" + side])
        B["hand_" + side] = need(["Hand_" + side])
        B["thigh_" + side] = need(["Thigh_" + side])
        B["shin_" + side] = need(["Shin_" + side])
        B["foot_" + side] = need(["Sole_" + side, "Shoe_Upper_" + side])
        B["eye_" + side] = need(["Eye_White_" + side])
        B["eye_all_" + side] = need(["Eye_White_" + side, "Eye_Iris_" + side,
                                     "Eye_Pupil_" + side, "Eye_Glint_" + side])
        B["eyelid_" + side] = need(["Eyelid_" + side])

    all_bounds = part_bounds(objs)
    ground = all_bounds["min"][2]
    height = all_bounds["max"][2] - ground

    def z(box, edge):
        return box[edge][2]

    # --- spine chain (every value derived from the part boxes) -----------
    hips_lo, hips_hi = z(B["hips"], "min"), z(B["hips"], "max")
    neck_lo, neck_hi = z(B["neck"], "min"), z(B["neck"], "max")
    head_lo, head_hi = z(B["head"], "min"), z(B["head"], "max")

    hips_head = 0.5 * (hips_lo + hips_hi)
    spine_head = hips_hi
    spine_tail = neck_lo + 0.25 * (neck_hi - neck_lo)
    neck_tail = head_lo + 0.25 * (head_hi - head_lo)
    head_tail = neck_tail + 0.66 * (head_hi - head_lo)

    mouth = B["mouth"]
    jaw_head = [0.0, round(mouth["center"][1] * 0.1, 4),
                round(z(mouth, "max") + 0.25 * mouth["size"][2], 4)]
    jaw_tail = [0.0, mouth["min"][1], round(z(mouth, "min") + 0.4 * mouth["size"][2], 4)]

    bones = [
        ("root", [0.0, 0.0, round(ground, 4)], [0.0, -0.15, round(ground, 4)],
         None, False, False),
        ("hips", [0.0, 0.0, round(hips_head, 4)], [0.0, 0.0, round(spine_head, 4)],
         "root", False, True),
        ("spine", [0.0, 0.0, round(spine_head, 4)], [0.0, 0.0, round(spine_tail, 4)],
         "hips", True, True),
        ("neck", [0.0, 0.0, round(spine_tail, 4)], [0.0, 0.0, round(neck_tail, 4)],
         "spine", True, True),
        ("head", [0.0, 0.0, round(neck_tail, 4)], [0.0, 0.0, round(head_tail, 4)],
         "neck", True, True),
        ("jaw", jaw_head, jaw_tail, "head", False, True),
    ]

    for side, sign in (("L", -1.0), ("R", 1.0)):
        thigh, shin, foot = B["thigh_" + side], B["shin_" + side], B["foot_" + side]
        arm, sleeve, hand = B["arm_" + side], B["sleeve_" + side], B["hand_" + side]
        eye, lid = B["eye_" + side], B["eyelid_" + side]

        leg_x = round(thigh["center"][0], 4)
        hip_joint = z(thigh, "max")
        knee = z(shin, "max") - 0.15 * shin["size"][2]
        ankle = z(shin, "min") + 0.03 * shin["size"][2]

        arm_x = round(arm["center"][0], 4)
        arm_top = z(arm, "max")
        elbow = arm_top - 0.42 * arm["size"][2]
        wrist = z(arm, "min") + 0.22 * arm["size"][2]
        hand_end = z(hand, "min") + 0.05 * hand["size"][2]

        bones += [
            ("eye." + side,
             [round(eye["center"][0], 4), round(eye["center"][1], 4), round(eye["center"][2], 4)],
             [round(eye["center"][0], 4), round(eye["center"][1] - 0.09, 4),
              round(eye["center"][2], 4)],
             "head", False, True),
            ("eyelid." + side,
             [round(lid["center"][0], 4), round(lid["center"][1], 4), round(lid["max"][2], 4)],
             [round(lid["center"][0], 4), round(lid["center"][1], 4),
              round(lid["max"][2] - 0.048, 4)],
             "head", False, True),
            ("shoulder." + side,
             [round(sign * 0.13 * B["torso"]["size"][0], 4), 0.0, round(sleeve["center"][2], 4)],
             [round(sleeve["center"][0], 4), 0.0, round(sleeve["center"][2], 4)],
             "spine", False, True),
            ("upper_arm." + side,
             [arm_x, 0.0, round(arm_top, 4)], [arm_x, 0.0, round(elbow, 4)],
             "shoulder." + side, False, True),
            ("forearm." + side,
             [arm_x, 0.0, round(elbow, 4)], [arm_x, 0.0, round(wrist, 4)],
             "upper_arm." + side, True, True),
            ("hand." + side,
             [arm_x, 0.0, round(wrist, 4)], [arm_x, 0.0, round(hand_end, 4)],
             "forearm." + side, True, True),
            ("thigh." + side,
             [leg_x, 0.0, round(hip_joint, 4)], [leg_x, 0.0, round(knee, 4)],
             "hips", False, True),
            ("shin." + side,
             [leg_x, 0.0, round(knee, 4)], [leg_x, 0.0, round(ankle, 4)],
             "thigh." + side, True, True),
            ("foot." + side,
             [leg_x, 0.0, round(ankle, 4)],
             [leg_x, round(foot["min"][1] * 0.85, 4), round(ankle * 0.4, 4)],
             "shin." + side, True, True),
        ]

    bone_rows = [{"name": n, "head": h, "tail": t, "parent": p,
                  "connected": bool(c), "deform": bool(d)}
                 for n, h, t, p, c, d in bones]

    return {
        "schema": "ahos.character-rig-spec.v1",
        "character_id": character_id,
        "source_blend": bpy.data.filepath,
        "derived_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "derived_from": "mesh part bounds + naming convention",
        "units": "meters",
        "ground_z": round(ground, 4),
        "height_m": round(height, 4),
        "part_bounds": B,
        "bones": bone_rows,
        "skin": skin_maps(B),
        "shape_keys": shape_key_spec(B),
        "eye_scale": {"bones": ["eye.L", "eye.R"], "world": [1.0, 0.45, 0.12]},
        "actions": {"idle_wave": 48, "blink_smile": 24, "walk_cycle": 32},
        "warnings": WARN,
    }


def skin_maps(B):
    """Object -> bone assignment rules, derived from names and measured boxes."""
    rigid = {
        "Head": "head", "Hair_Cap": "head", "Star_Clip": "head", "Nose": "head",
        "Ear_L": "head", "Ear_R": "head", "Brow_L": "head", "Brow_R": "head",
        "Teeth": "jaw", "Tongue": "jaw", "Shirt_Kite_Print": "spine",
    }
    for side in ("L", "R"):
        rigid["Hand_" + side] = "hand." + side
        rigid["Shoe_Upper_" + side] = "foot." + side
        rigid["Sole_" + side] = "foot." + side
        rigid["Shoe_Star_" + side] = "foot." + side
        rigid["Eyelid_" + side] = "eyelid." + side
        rigid["Sleeve_" + side] = "upper_arm." + side
        for part in ("Eye_White", "Eye_Iris", "Eye_Pupil", "Eye_Glint"):
            rigid["%s_%s" % (part, side)] = "eye." + side

    auto = {
        "Neck": ["spine", "neck", "head"],
        "Torso_Shirt": ["hips", "spine", "neck"],
        "Shirt_Hem": ["hips", "spine"],
        "Hips_Shorts": ["hips", "spine"],
        "Shorts_Left": ["hips", "thigh.L"],
        "Shorts_Right": ["hips", "thigh.R"],
        "Arm_L": ["upper_arm.L", "forearm.L", "hand.L"],
        "Arm_R": ["upper_arm.R", "forearm.R", "hand.R"],
        "Thigh_L": ["hips", "thigh.L", "shin.L"],
        "Thigh_R": ["hips", "thigh.R", "shin.R"],
        "Shin_L": ["thigh.L", "shin.L", "foot.L"],
        "Shin_R": ["thigh.R", "shin.R", "foot.R"],
    }
    mouth = B["mouth"]
    gradient = {
        "Mouth": {"bones": ["head", "jaw"],
                  "top_z": round(mouth["max"][2] + 0.003, 4),
                  "bottom_z": round(mouth["min"][2] - 0.003, 4)},
    }
    return {
        "rigid": rigid,
        "rigid_prefix": {"Hair_Clump_": "head", "Freckle_": "head", "Hair_": "head"},
        "auto": auto,
        "gradient": gradient,
        "mouth_bones": ["head", "jaw"],
    }


def shape_key_spec(B):
    """Shape key targets, computed from the measured eye/mouth boxes."""
    pivot = B["eye_L"]["center"]          # eye bone pivot = sclera centre
    eye_all = B["eye_all_L"]              # every eye part (pupil protrudes most)
    mouth = B["mouth"]
    height = B["head"]["max"][2] - B["head"]["min"][2]

    squashed_front = pivot[1] + (eye_all["min"][1] - pivot[1]) * 0.45
    lid = {
        "type": "lid",
        "bottom_z": round(eye_all["min"][2] - 0.003, 4),
        "front_y": round(squashed_front - 0.003, 4),
        "x_scale": 1.06,
        "z_stretch": 3.1,
    }
    mouth_h = mouth["size"][2]
    mouth_w = mouth["size"][0]
    return {
        "blink.L": dict(lid, object="Eyelid_L"),
        "blink.R": dict(lid, object="Eyelid_R"),
        "smile": {"object": "Mouth", "type": "smile",
                  "x_scale": 1.30,
                  "corner_lift": round(0.37 * mouth_h, 4),
                  "forward": round(0.058 * mouth_h, 4)},
        "mouth_open": {"object": "Mouth", "type": "mouth_open",
                       "z_scale": 1.80, "x_scale": 0.90,
                       "forward": round(0.033 * mouth_h, 4)},
        "brow_up": {"objects": ["Brow_L", "Brow_R"], "type": "raise",
                    "dz": round(0.036 * height, 4), "dy": round(-0.008 * height, 4)},
        "mouth_width_m": round(mouth_w, 4),
    }


# ---------------------------------------------------------------------------
# mode 2: build the rig from a spec
# ---------------------------------------------------------------------------
def build_armature(spec):
    arm_name = "AHOS_Rig_%s" % spec["character_id"]
    data = bpy.data.armatures.new(arm_name + "_data")
    obj = bpy.data.objects.new(arm_name, data)
    coll = bpy.data.collections.get("CHARACTER") or bpy.context.scene.collection
    coll.objects.link(obj)
    data.display_type = "OCTAHEDRAL"
    obj.show_in_front = True

    for other in bpy.context.scene.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for row in spec["bones"]:
        bone = data.edit_bones.new(row["name"])
        bone.head = Vector(row["head"])
        bone.tail = Vector(row["tail"])
        bone.roll = 0.0
        bone.use_deform = bool(row["deform"])
    for row in spec["bones"]:
        if row["parent"]:
            bone = data.edit_bones[row["name"]]
            bone.parent = data.edit_bones[row["parent"]]
            bone.use_connect = bool(row["connected"])
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.data.pose_position = "POSE"
    log("armature %s: %d bones" % (arm_name, len(data.bones)))
    return obj


def parent_to_armature(obj, arm, auto):
    for selected in bpy.context.scene.objects:
        selected.select_set(False)
    obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO" if auto else "ARMATURE")


def apply_weights(obj, weights, groups):
    for existing in list(obj.vertex_groups):
        obj.vertex_groups.remove(existing)
    made = {}
    for name in groups:
        made[name] = obj.vertex_groups.new(name=name)
    for index, entries in enumerate(weights):
        total = sum(weight for _, weight in entries)
        if total <= 0.0:
            continue
        for group_name, weight in entries:
            if weight > 0.0:
                made[group_name].add([index], weight / total, "REPLACE")


def bone_segment(arm, name):
    bone = arm.data.bones[name]
    return (arm.matrix_world @ bone.head_local, arm.matrix_world @ bone.tail_local)


def distance_to_bone(point, segment):
    start, end = segment
    axis = end - start
    length_sq = axis.length_squared
    if length_sq < 1e-12:
        return (point - start).length
    t = max(0.0, min(1.0, (point - start).dot(axis) / length_sq))
    return (point - (start + axis * t)).length


def normalise(obj, allowed, max_influences=4):
    index_to_name = {group.index: group.name for group in obj.vertex_groups}
    allowed_set = set(allowed)
    segments = {name: bone_segment(bpy.data.objects[obj.parent.name], name) for name in allowed}
    matrix = obj.matrix_world
    per_vertex = []
    fixed = 0
    for vertex in obj.data.vertices:
        entries = [(index_to_name[e.group], e.weight) for e in vertex.groups
                   if index_to_name.get(e.group) in allowed_set and e.weight > 1e-5]
        if not entries:
            point = matrix @ vertex.co
            best = min(allowed, key=lambda n: distance_to_bone(point, segments[n]))
            entries = [(best, 1.0)]
            fixed += 1
        entries.sort(key=lambda pair: -pair[1])
        per_vertex.append(entries[:max_influences])
    apply_weights(obj, per_vertex, allowed)
    return fixed


def skin_all(spec, arm):
    rigid = spec["skin"]["rigid"]
    prefixes = spec["skin"]["rigid_prefix"]
    auto = spec["skin"]["auto"]
    gradient = spec["skin"]["gradient"]
    report = {"rigid": {}, "auto": {}, "gradient": {}, "fixed": 0, "skipped": []}

    for obj in sorted(meshes(), key=lambda item: item.name):
        name = obj.name
        bone = rigid.get(name)
        if bone is None:
            for prefix, target in prefixes.items():
                if name.startswith(prefix):
                    bone = target
                    break
        if bone:
            parent_to_armature(obj, arm, auto=False)
            apply_weights(obj, [[(bone, 1.0)]] * len(obj.data.vertices), [bone])
            report["rigid"][name] = bone
            continue

        if name in gradient:
            cfg = gradient[name]
            parent_to_armature(obj, arm, auto=False)
            matrix = obj.matrix_world
            top, bottom = cfg["top_z"], cfg["bottom_z"]
            weights = []
            for vertex in obj.data.vertices:
                z = (matrix @ vertex.co).z
                t = min(1.0, max(0.0, (top - z) / max(top - bottom, 1e-6)))
                t = t * t * (3.0 - 2.0 * t)
                weights.append([(cfg["bones"][0], 1.0 - t), (cfg["bones"][1], t)])
            apply_weights(obj, weights, cfg["bones"])
            report["gradient"][name] = cfg["bones"]
            continue

        allowed = auto.get(name)
        if allowed is None:
            warn("no skin rule for %s (left unrigged)" % name)
            report["skipped"].append(name)
            continue
        try:
            parent_to_armature(obj, arm, auto=True)
            report["fixed"] += normalise(obj, allowed)
            report["auto"][name] = allowed
        except Exception as exc:
            warn("automatic weights failed on %s (%s) - nearest bone fallback" % (name, exc))
            parent_to_armature(obj, arm, auto=False)
            segments = {bone_name: bone_segment(arm, bone_name) for bone_name in allowed}
            matrix = obj.matrix_world
            weights = []
            for vertex in obj.data.vertices:
                point = matrix @ vertex.co
                best = min(allowed, key=lambda b: distance_to_bone(point, segments[b]))
                weights.append([(best, 1.0)])
            apply_weights(obj, weights, allowed)
            report["auto"][name] = allowed

        modifiers = [m for m in obj.modifiers if m.type == "ARMATURE"]
        modifier = modifiers[0] if modifiers else obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = arm

    return report


# ---------------------------------------------------------------------------
# shape keys
# ---------------------------------------------------------------------------
def ensure_key(obj, name):
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    block = obj.data.shape_keys.key_blocks.get(name)
    if block is None:
        block = obj.shape_key_add(name=name, from_mix=False)
    block.value = 0.0
    return block


def make_shape_keys(spec):
    made = {}
    for name, cfg in spec["shape_keys"].items():
        if not isinstance(cfg, dict) or "type" not in cfg:
            continue
        kind = cfg["type"]

        if kind == "lid":
            obj = bpy.data.objects.get(cfg["object"])
            if obj is None:
                warn("shape key %s: missing %s" % (name, cfg["object"]))
                continue
            block = ensure_key(obj, name)
            matrix = obj.matrix_world
            inverse = matrix.inverted()
            world = [matrix @ v.co.copy() for v in obj.data.vertices]
            top = max(v.z for v in world)
            low = min(v.z for v in world)
            factor = (top - cfg["bottom_z"]) / max(top - low, 1e-6)
            shift = cfg["front_y"] - min(v.y for v in world)
            cx = sum(v.x for v in world) / len(world)
            for index, vertex in enumerate(world):
                block.data[index].co = inverse @ Vector((
                    cx + (vertex.x - cx) * cfg["x_scale"],
                    vertex.y + shift,
                    top - (top - vertex.z) * factor,
                ))
            made[name] = cfg["object"]
            log("shape key %s on %s (z x%.2f, y %.1f mm)"
                % (name, cfg["object"], factor, shift * 1000.0))

        elif kind in ("smile", "mouth_open"):
            obj = bpy.data.objects.get(cfg["object"])
            if obj is None:
                warn("shape key %s: missing %s" % (name, cfg["object"]))
                continue
            block = ensure_key(obj, name)
            coords = [v.co.copy() for v in obj.data.vertices]
            cx = sum(c.x for c in coords) / len(coords)
            cz = sum(c.z for c in coords) / len(coords)
            half = max((abs(c.x - cx) for c in coords), default=1.0) or 1.0
            for index, co in enumerate(coords):
                if kind == "smile":
                    t = min(1.0, abs(co.x - cx) / half)
                    block.data[index].co = Vector((
                        cx + (co.x - cx) * cfg["x_scale"],
                        co.y - cfg["forward"] * t * t,
                        co.z + cfg["corner_lift"] * (t ** 1.6),
                    ))
                else:
                    block.data[index].co = Vector((
                        cx + (co.x - cx) * cfg["x_scale"],
                        co.y - cfg["forward"],
                        cz + (co.z - cz) * cfg["z_scale"],
                    ))
            made[name] = cfg["object"]
            log("shape key %s on %s" % (name, cfg["object"]))

        elif kind == "raise":
            for obj_name in cfg["objects"]:
                obj = bpy.data.objects.get(obj_name)
                if obj is None:
                    warn("shape key %s: missing %s" % (name, obj_name))
                    continue
                block = ensure_key(obj, name)
                for index, vertex in enumerate(obj.data.vertices):
                    block.data[index].co = Vector((vertex.co.x,
                                                   vertex.co.y + cfg["dy"],
                                                   vertex.co.z + cfg["dz"]))
                made[name] = obj_name
            log("shape key %s on %s" % (name, ", ".join(cfg["objects"])))
    return made


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
X_AXIS, Y_AXIS, Z_AXIS = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def key_rot(arm, bone, frame, pairs):
    pose_bone = arm.pose.bones[bone]
    pose_bone.rotation_mode = "QUATERNION"
    inverse = pose_bone.bone.matrix_local.to_3x3().inverted()
    quat = Quaternion((1.0, 0.0, 0.0, 0.0))
    for axis, degrees in pairs:
        quat = quat @ Quaternion((inverse @ Vector(axis)).normalized(), DEG(degrees))
    pose_bone.rotation_quaternion = quat
    pose_bone.keyframe_insert("rotation_quaternion", frame=frame)


def key_loc(arm, bone, frame, world_loc):
    pose_bone = arm.pose.bones[bone]
    pose_bone.location = pose_bone.bone.matrix_local.to_3x3().inverted() @ Vector(world_loc)
    pose_bone.keyframe_insert("location", frame=frame)


def local_scale(pose_bone, world_scale):
    rotation = pose_bone.bone.matrix_local.to_3x3()
    out = [1.0, 1.0, 1.0]
    for i in range(3):
        axis = Vector((0.0, 0.0, 0.0))
        axis[i] = 1.0
        mapped = rotation @ axis
        for j in range(3):
            if abs(mapped[j]) > 0.9:
                out[i] = world_scale[j]
    return Vector(out)


def key_scale(arm, bone, frame, world_scale):
    pose_bone = arm.pose.bones[bone]
    pose_bone.scale = local_scale(pose_bone, world_scale)
    pose_bone.keyframe_insert("scale", frame=frame)


def new_action(arm, name):
    if arm.animation_data is None:
        arm.animation_data_create()
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm.animation_data.action = action
    return action


def set_action_range(action, start, end):
    try:
        action.use_frame_range = True
        action.frame_start = float(start)
        action.frame_end = float(end)
    except Exception as exc:
        warn("frame range on %s: %s" % (action.name, exc))


def attach_key_action(key_id, action, slot_name):
    anim = key_id.animation_data_create()
    anim.action = action
    if getattr(anim, "action_slot", None) is None and hasattr(action, "slots"):
        try:
            anim.action_slot = action.slots.new(id_type="KEY", name=slot_name)
        except Exception as exc:
            warn("KEY slot on %s: %s" % (action.name, exc))
    if getattr(anim, "action_slot", None) is not None:
        key_id["rig_action_slot"] = anim.action_slot.identifier


def smooth_action(action):
    curves = []
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    curves.extend(bag.fcurves)
    if not curves and hasattr(action, "fcurves"):
        curves.extend(action.fcurves)
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


def reset_pose(arm):
    for pose_bone in arm.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pose_bone.location = Vector((0.0, 0.0, 0.0))
        pose_bone.scale = Vector((1.0, 1.0, 1.0))


def key_rest_legs(arm, frame):
    """Every action must key the legs and root, otherwise the previous action's
    pose leaks into the next one (feet drift below the floor)."""
    for side in ("L", "R"):
        for bone in ("thigh." + side, "shin." + side, "foot." + side):
            key_rot(arm, bone, frame, [(X_AXIS, 0.0)])
    key_loc(arm, "root", frame, (0.0, 0.0, 0.0))


def build_idle_wave(arm, total=48):
    action = new_action(arm, "idle_wave")
    for frame in (1, total):
        key_rest_legs(arm, frame)

    def right_arm(frame, shoulder, upper, fore, hand):
        key_rot(arm, "shoulder.R", frame, [(Y_AXIS, shoulder)])
        key_rot(arm, "upper_arm.R", frame, [(Y_AXIS, upper)])
        key_rot(arm, "forearm.R", frame, [(Y_AXIS, fore)])
        key_rot(arm, "hand.R", frame, [(Y_AXIS, hand)])

    for frame, values in ((1, (-2, -4, 0, 0)), (6, (-6, -52, -10, 5)),
                          (11, (-9, -98, -22, 9)), (16, (-9, -98, 6, 2)),
                          (21, (-9, -98, -44, 10)), (26, (-9, -98, 6, 2)),
                          (31, (-9, -98, -40, 9)), (36, (-8, -86, -4, 3)),
                          (43, (-5, -34, -8, 1)), (48, (-2, -4, 0, 0))):
        right_arm(frame, *values)

    for frame, value in ((1, 2), (11, -5), (22, 3), (34, -3), (48, 2)):
        key_rot(arm, "upper_arm.L", frame, [(Y_AXIS, value)])
        key_rot(arm, "forearm.L", frame, [(X_AXIS, value * 0.6)])

    for frame, turn, nod in ((1, 0, 0), (11, 6, -2), (20, 3, 2),
                             (30, 8, -1), (40, 4, 1), (48, 0, 0)):
        key_rot(arm, "head", frame, [(Z_AXIS, turn), (X_AXIS, nod)])
        key_rot(arm, "neck", frame, [(Z_AXIS, turn * 0.35), (X_AXIS, nod * 0.4)])

    for frame in (1, total):
        key_rot(arm, "hips", frame, [(Z_AXIS, 0.0), (Y_AXIS, 0.0)])
    for frame, bob, lean in ((1, 0.0, 0), (12, 0.003, -2), (24, 0.001, 1),
                             (36, 0.004, -2), (48, 0.0, 0)):
        # the lean lives on the spine: rotating the hips would swing the legs and
        # push the planted feet below the floor
        key_rot(arm, "spine", frame, [(Z_AXIS, -lean * 0.6), (Y_AXIS, lean * 0.5)])
        key_loc(arm, "spine", frame, (0.0, 0.0, bob))

    set_action_range(action, 1, total)
    smooth_action(action)
    reset_pose(arm)
    return action


def build_blink_smile(arm, total=24, eye_scale=(1.0, 0.45, 0.12)):
    action = new_action(arm, "blink_smile")
    for frame in (1, total):
        key_rest_legs(arm, frame)
    lids = [bpy.data.objects.get("Eyelid_L"), bpy.data.objects.get("Eyelid_R")]
    key_ids = []
    for lid in lids:
        if lid and lid.data.shape_keys:
            key_ids.append(lid.data.shape_keys)
    mouth = bpy.data.objects.get("Mouth")
    if mouth and mouth.data.shape_keys:
        key_ids.append(mouth.data.shape_keys)
    for brow_name in ("Brow_L", "Brow_R"):
        brow = bpy.data.objects.get(brow_name)
        if brow and brow.data.shape_keys:
            key_ids.append(brow.data.shape_keys)
    for index, key_id in enumerate(key_ids):
        attach_key_action(key_id, action, "Face_%d" % index)

    for frame, value in ((1, 0.0), (5, 0.12), (7, 1.0), (10, 1.0), (13, 0.0), (24, 0.0)):
        for lid, side in zip(lids, ("L", "R")):
            if lid and lid.data.shape_keys:
                block = lid.data.shape_keys.key_blocks.get("blink." + side)
                if block:
                    block.value = value
                    block.keyframe_insert("value", frame=frame)

    if mouth and mouth.data.shape_keys:
        for key_name, curve in (("smile", ((1, 0.0), (6, 0.75), (10, 1.0),
                                           (18, 1.0), (22, 0.5), (24, 0.0))),
                                ("mouth_open", ((1, 0.0), (6, 0.0), (9, 0.7),
                                                (13, 0.25), (18, 0.0), (24, 0.0)))):
            block = mouth.data.shape_keys.key_blocks.get(key_name)
            if block:
                for frame, value in curve:
                    block.value = value
                    block.keyframe_insert("value", frame=frame)

    for brow_name in ("Brow_L", "Brow_R"):
        brow = bpy.data.objects.get(brow_name)
        if brow and brow.data.shape_keys:
            block = brow.data.shape_keys.key_blocks.get("brow_up")
            if block:
                for frame, value in ((1, 0.0), (6, 0.0), (10, 0.7), (16, 0.55),
                                     (20, 0.2), (24, 0.0)):
                    block.value = value
                    block.keyframe_insert("value", frame=frame)

    for frame, nod, turn in ((1, 0, 0), (7, -3, 2), (12, -1, 1), (18, 2, -2), (24, 0, 0)):
        key_rot(arm, "head", frame, [(X_AXIS, nod), (Z_AXIS, turn)])
        key_rot(arm, "spine", frame, [(X_AXIS, nod * 0.25)])
    for frame, jaw in ((1, 0), (6, 0), (9, 8), (13, 3), (18, 0), (24, 0)):
        key_rot(arm, "jaw", frame, [(X_AXIS, jaw)])

    for frame, scale in ((1, (1.0, 1.0, 1.0)), (5, (1.0, 1.0, 1.0)),
                         (7, eye_scale), (10, eye_scale),
                         (13, (1.0, 1.0, 1.0)), (24, (1.0, 1.0, 1.0))):
        for side in ("L", "R"):
            key_scale(arm, "eye." + side, frame, scale)

    set_action_range(action, 1, total)
    smooth_action(action)
    reset_pose(arm)
    return action


def build_walk_cycle(arm, spec, total=32):
    action = new_action(arm, "walk_cycle")
    rows = {row["name"]: row for row in spec["bones"]}
    thigh_row, shin_row = rows["thigh.L"], rows["shin.L"]
    thigh_len = (Vector(thigh_row["head"]) - Vector(thigh_row["tail"])).length
    shin_len = (Vector(shin_row["head"]) - Vector(shin_row["tail"])).length
    hip_z = thigh_row["head"][2]
    ankle_z = shin_row["tail"][2]
    hip_x = abs(thigh_row["head"][0])
    height = spec["height_m"]

    reach = 0.0509 * height
    lift = 0.030 * height
    yaw_deg = 5.0
    leg_len = thigh_len + shin_len
    minimum_drop = (reach * reach) / (2.0 * leg_len) * 1.25
    drop_amp = max(0.0085 * height, minimum_drop)

    def leg_angles(drop, ankle_y):
        vertical = (hip_z - drop) - ankle_z
        distance = min(math.hypot(vertical, ankle_y), leg_len - 1e-4)
        psi = math.degrees(math.atan2(ankle_y, vertical))
        cos_a = (thigh_len ** 2 + distance ** 2 - shin_len ** 2) / (2 * thigh_len * distance)
        cos_k = (thigh_len ** 2 + shin_len ** 2 - distance ** 2) / (2 * thigh_len * shin_len)
        alpha = math.degrees(math.acos(max(-1.0, min(1.0, cos_a))))
        knee = 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, cos_k))))
        return psi - alpha, knee

    for frame in range(1, total + 2):
        phase = (frame - 1) / float(total)
        drop = drop_amp * abs(math.cos(TAU * phase))
        yaw = yaw_deg * math.sin(TAU * phase)

        key_loc(arm, "root", frame, (0.0, -4.0 * reach * phase, 0.0))
        key_rot(arm, "hips", frame, [(Z_AXIS, yaw)])
        key_loc(arm, "hips", frame, (0.0, 0.0, -drop))

        for side, shift, sign in (("L", 0.0, -1.0), ("R", 0.5, 1.0)):
            p = (phase + shift) % 1.0
            if p <= 0.5:
                ankle_y = -reach + 4.0 * reach * p
                ankle_up = 0.0
            else:
                t = (p - 0.5) / 0.5
                smooth = t * t * (3.0 - 2.0 * t)
                ankle_y = reach - 2.0 * reach * smooth
                ankle_up = lift * math.sin(math.pi * t)
            hip_shift = sign * hip_x * math.sin(DEG(yaw))
            thigh_deg, knee_deg = leg_angles(drop + ankle_up, ankle_y - hip_shift)
            key_rot(arm, "thigh." + side, frame, [(X_AXIS, thigh_deg)])
            key_rot(arm, "shin." + side, frame, [(X_AXIS, knee_deg)])
            key_rot(arm, "foot." + side, frame, [(X_AXIS, -(thigh_deg + knee_deg))])

        swing = 16.0 * math.cos(TAU * phase)
        key_rot(arm, "upper_arm.L", frame, [(X_AXIS, swing)])
        key_rot(arm, "upper_arm.R", frame, [(X_AXIS, -swing)])
        key_rot(arm, "forearm.L", frame, [(X_AXIS, 8.0 + 5.0 * math.cos(TAU * phase))])
        key_rot(arm, "forearm.R", frame, [(X_AXIS, 8.0 - 5.0 * math.cos(TAU * phase))])
        key_rot(arm, "spine", frame, [(Z_AXIS, -4.0 * math.sin(TAU * phase)),
                                      (X_AXIS, -2.0)])
        key_rot(arm, "head", frame, [(Z_AXIS, -2.0 * math.sin(TAU * phase))])

    set_action_range(action, 1, total)
    smooth_action(action)
    reset_pose(arm)
    return action


def export_glb(out_dir, arm, character_id):
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "ARMATURE"} and not obj.name.startswith("RIGTEST_"):
            obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    path = safe_path(os.path.join(out_dir, "%s-rigged.glb" % character_id))
    options = dict(filepath=path, export_format="GLB", use_selection=True,
                   export_animations=True, export_animation_mode="ACTIONS",
                   export_skins=True, export_morph=True, export_yup=True)
    try:
        bpy.ops.export_scene.gltf(**options)
    except TypeError as exc:
        warn("glTF options rejected (%s), retrying minimal" % exc)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)
    return path


def main():
    opts = parse_args()

    if opts["mode"] == "derive":
        if not opts["character"]:
            raise SystemExit("--character is required for derive")
        spec = derive_spec(opts["character"])
        target = os.path.abspath(opts["out"] or
                                 os.path.join("specs", "%s.json" % opts["character"]))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(spec, handle, indent=2, ensure_ascii=False)
        log("spec written: %s (%d bones, height %.3f m)"
            % (target, len(spec["bones"]), spec["height_m"]))
        print("DERIVE_OK", flush=True)
        return

    if not opts["spec"]:
        raise SystemExit("--spec is required for build")
    spec_path = os.path.abspath(opts["spec"])
    with open(spec_path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    log("spec: %s (%s, %d bones)" % (spec_path, spec["character_id"], len(spec["bones"])))

    if not meshes():
        raise RuntimeError("no character meshes in the scene - open the character .blend "
                           "before running the factory (empty rigs are not allowed)")

    arm = build_armature(spec)
    skin = skin_all(spec, arm)
    log("skinning: %d rigid / %d auto / %d gradient / %d vertices fixed"
        % (len(skin["rigid"]), len(skin["auto"]), len(skin["gradient"]), skin["fixed"]))
    keys = make_shape_keys(spec)
    log("shape keys: %s" % ", ".join(sorted(keys)))

    idle = build_idle_wave(arm, spec["actions"]["idle_wave"])
    blink = build_blink_smile(arm, spec["actions"]["blink_smile"],
                              tuple(spec["eye_scale"]["world"]))
    walk = build_walk_cycle(arm, spec, spec["actions"]["walk_cycle"])
    actions = [idle, blink, walk]

    scene = bpy.context.scene
    arm.animation_data.action = idle
    scene.frame_start, scene.frame_end = 1, spec["actions"]["idle_wave"]
    scene.frame_set(1)

    out_dir = os.path.abspath(opts["out"] or os.path.join("out", spec["character_id"]))
    os.makedirs(out_dir, exist_ok=True)
    blend_path = safe_path(os.path.join(out_dir, "%s-rigged.blend" % spec["character_id"]))
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    glb_path = export_glb(out_dir, arm, spec["character_id"])

    meshes_list = meshes()
    manifest = {
        "schema": "ahos.character-rig.v3",
        "character_id": spec["character_id"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "builder": "ahos-rig-factory/rig_factory.py",
        "spec": {"path": spec_path, "sha256": sha256_file(spec_path),
                 "derived_from": spec.get("derived_from")},
        "blender": bpy.app.version_string,
        "rig": {"armature": arm.name,
                "bone_count": len(arm.data.bones),
                "deform_bone_count": len([b for b in arm.data.bones if b.use_deform]),
                "bones": [{"name": b.name,
                           "head": [round(v, 4) for v in b.head_local],
                           "tail": [round(v, 4) for v in b.tail_local],
                           "parent": b.parent.name if b.parent else None}
                          for b in arm.data.bones]},
        "skinning": {"rigid": skin["rigid"], "auto": skin["auto"],
                     "gradient": skin["gradient"], "fixed_vertices": skin["fixed"],
                     "skipped": skin["skipped"]},
        "mesh_stats": {"objects": len(meshes_list),
                       "vertices": sum(len(o.data.vertices) for o in meshes_list),
                       "faces": sum(len(o.data.polygons) for o in meshes_list)},
        "shape_keys": keys,
        "actions": [{"name": a.name,
                     "frame_start": round(a.frame_range[0], 2),
                     "frame_end": round(a.frame_range[1], 2)} for a in actions],
        "outputs": {
            "blend": {"path": blend_path, "bytes": os.path.getsize(blend_path),
                      "sha256": sha256_file(blend_path)},
            "glb": {"path": glb_path, "bytes": os.path.getsize(glb_path),
                    "sha256": sha256_file(glb_path)},
        },
        "warnings": WARN,
    }
    manifest_path = os.path.join(out_dir, "rig-manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    log("blend: %s" % blend_path)
    log("glb  : %s" % glb_path)
    log("manifest: %s" % manifest_path)
    print("BUILD_OK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("FACTORY_FAILED", flush=True)
        sys.exit(1)
