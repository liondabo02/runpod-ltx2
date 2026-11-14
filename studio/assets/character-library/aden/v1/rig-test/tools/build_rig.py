"""Build the Aden rig: armature, skinning, shape keys, actions, renders.

Run (headless):
    blender -b aden-character-v1.blend --factory-startup --python build_rig.py -- \
        --out <rig-test folder> --render none|stills|full

The source .blend is only read. Every result is written into the output
folder as a *new* file (never overwriting an existing one).
"""
import hashlib
import json
import glob
import math
import os
import sys
import time

import bpy
from mathutils import Quaternion, Vector

TAU = math.tau
DEG = math.radians
ARMATURE_NAME = "AdenRig"
ARMATURE_DATA = "AdenArmature"
WARNINGS = []
START_TIME = time.time()


def log(msg):
    print("[RIG] %s" % (msg,), flush=True)


def warn(msg):
    WARNINGS.append(str(msg))
    log("WARNING: %s" % (msg,))


def parse_args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"out": None, "render": "none"}
    i = 0
    while i < len(tail):
        key = tail[i]
        if key == "--out" and i + 1 < len(tail):
            opts["out"] = tail[i + 1]
            i += 2
        elif key == "--render" and i + 1 < len(tail):
            opts["render"] = tail[i + 1].lower()
            i += 2
        else:
            i += 1
    return opts


def safe_path(path):
    """Never overwrite: append a timestamp when the target already exists."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = "%s_%s%s" % (root, stamp, ext)
    log("target exists, using new file name: %s" % (candidate,))
    return candidate


def sha256_file(path):
    if not os.path.exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Section 1: skeleton definition (values measured by inspect_scene.py)
# ---------------------------------------------------------------------------
def bone_table():
    """(name, head, tail, parent, connected, deform) - 24 bones."""
    bones = [
        ("root", (0.0, 0.0, 0.0), (0.0, -0.15, 0.0), None, False, False),
        ("hips", (0.0, 0.0, 0.38), (0.0, 0.0, 0.46), "root", False, True),
        ("spine", (0.0, 0.0, 0.46), (0.0, 0.0, 0.64), "hips", True, True),
        ("neck", (0.0, 0.0, 0.64), (0.0, 0.0, 0.78), "spine", True, True),
        ("head", (0.0, 0.0, 0.78), (0.0, 0.0, 1.08), "neck", True, True),
        ("jaw", (0.0, -0.02, 0.85), (0.0, -0.19, 0.80), "head", False, True),
    ]
    for side, sx in (("L", -1.0), ("R", 1.0)):
        bones += [
            ("eye." + side,
             (sx * 0.078, -0.18, 0.925), (sx * 0.078, -0.27, 0.925),
             "head", False, True),
            ("eyelid." + side,
             (sx * 0.078, -0.174, 0.978), (sx * 0.078, -0.174, 0.930),
             "head", False, True),
            ("shoulder." + side,
             (sx * 0.05, 0.0, 0.60), (sx * 0.155, 0.0, 0.60),
             "spine", False, True),
            ("upper_arm." + side,
             (sx * 0.195, 0.0, 0.60), (sx * 0.195, 0.0, 0.49),
             "shoulder." + side, False, True),
            ("forearm." + side,
             (sx * 0.195, 0.0, 0.49), (sx * 0.195, 0.0, 0.40),
             "upper_arm." + side, True, True),
            ("hand." + side,
             (sx * 0.195, 0.0, 0.40), (sx * 0.195, 0.0, 0.28),
             "forearm." + side, True, True),
            ("thigh." + side,
             (sx * 0.078, 0.0, 0.34), (sx * 0.078, 0.0, 0.19),
             "hips", False, True),
            ("shin." + side,
             (sx * 0.078, 0.0, 0.19), (sx * 0.078, 0.0, 0.055),
             "thigh." + side, True, True),
            ("foot." + side,
             (sx * 0.078, 0.0, 0.055), (sx * 0.078, -0.13, 0.02),
             "shin." + side, True, True),
        ]
    return bones


# ---------------------------------------------------------------------------
# Section 2: skin mapping (source object -> bone / allowed bones)
# ---------------------------------------------------------------------------
RIGID = {
    "Head": "head",
    "Hair_Cap": "head",
    "Star_Clip": "head",
    "Nose": "head",
    "Ear_L": "head",
    "Ear_R": "head",
    "Brow_L": "head",
    "Brow_R": "head",
    "Teeth": "jaw",
    "Tongue": "jaw",
    "Shirt_Kite_Print": "spine",
    "Hand_L": "hand.L",
    "Hand_R": "hand.R",
    "Shoe_Upper_L": "foot.L",
    "Sole_L": "foot.L",
    "Shoe_Star_L": "foot.L",
    "Shoe_Upper_R": "foot.R",
    "Sole_R": "foot.R",
    "Shoe_Star_R": "foot.R",
    # sleeves are a single cone around the shoulder joint: automatic weights
    # split them across shoulder+upper_arm and produced a torn flap when the
    # arm was raised, so they are locked to the upper arm instead.
    "Sleeve_L": "upper_arm.L",
    "Sleeve_R": "upper_arm.R",
}
for _side in ("L", "R"):
    for _part in ("Eye_White", "Eye_Iris", "Eye_Pupil", "Eye_Glint"):
        RIGID["%s_%s" % (_part, _side)] = "eye.%s" % _side
    RIGID["Eyelid_%s" % _side] = "eyelid.%s" % _side

RIGID_PREFIX = {
    "Hair_Clump_": "head",
    "Freckle_": "head",
}

# automatic weights are restricted to these bones per object afterwards
AUTO_ALLOWED = {
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

# mouth gets a manual vertical gradient: upper lip -> head, lower lip -> jaw
MOUTH_BONES = ("head", "jaw")
MOUTH_TOP_Z = 0.838
MOUTH_BOTTOM_Z = 0.772


def rigid_bone_for(name):
    if name in RIGID:
        return RIGID[name]
    for prefix, bone in RIGID_PREFIX.items():
        if name.startswith(prefix):
            return bone
    return None


# ---------------------------------------------------------------------------
# Section 3: armature creation + posing helpers
# ---------------------------------------------------------------------------
def create_armature():
    old = bpy.data.objects.get(ARMATURE_NAME)
    if old is not None:
        warn("object %s already exists, reusing it" % ARMATURE_NAME)
        return old

    arm_data = bpy.data.armatures.new(ARMATURE_DATA)
    arm_obj = bpy.data.objects.new(ARMATURE_NAME, arm_data)
    coll = bpy.data.collections.get("CHARACTER") or bpy.context.scene.collection
    coll.objects.link(arm_obj)
    arm_data.display_type = "OCTAHEDRAL"
    arm_obj.show_in_front = True

    view_layer = bpy.context.view_layer
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    table = bone_table()
    for name, head, tail, parent, connected, deform in table:
        edit_bone = arm_data.edit_bones.new(name)
        edit_bone.head = Vector(head)
        edit_bone.tail = Vector(tail)
        edit_bone.roll = 0.0
        edit_bone.use_deform = deform
    for name, head, tail, parent, connected, deform in table:
        if parent:
            edit_bone = arm_data.edit_bones[name]
            edit_bone.parent = arm_data.edit_bones[parent]
            edit_bone.use_connect = bool(connected)

    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj.data.pose_position = "POSE"
    log("armature created: %d bones" % len(arm_data.bones))
    return arm_obj


def key_bone(arm_obj, bone_name, frame, rot_pairs=None, world_loc=None):
    """Key a bone using *world-space* axes (converted to bone local space)."""
    pose_bone = arm_obj.pose.bones[bone_name]
    pose_bone.rotation_mode = "QUATERNION"
    quat = Quaternion((1.0, 0.0, 0.0, 0.0))
    if rot_pairs:
        inv = pose_bone.bone.matrix_local.to_3x3().inverted()
        for axis, degrees in rot_pairs:
            local_axis = (inv @ Vector(axis)).normalized()
            quat = quat @ Quaternion(local_axis, DEG(degrees))
    pose_bone.rotation_quaternion = quat
    pose_bone.keyframe_insert("rotation_quaternion", frame=frame)
    if world_loc is not None:
        pose_bone.location = pose_bone.bone.matrix_local.to_3x3().inverted() @ Vector(world_loc)
        pose_bone.keyframe_insert("location", frame=frame)


def reset_pose(arm_obj):
    for pose_bone in arm_obj.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pose_bone.location = Vector((0.0, 0.0, 0.0))
        pose_bone.scale = Vector((1.0, 1.0, 1.0))


# ---------------------------------------------------------------------------
# Section 4: skinning
# ---------------------------------------------------------------------------
def ensure_group(obj, name):
    group = obj.vertex_groups.get(name)
    if group is None:
        group = obj.vertex_groups.new(name=name)
    return group


def bone_segments(arm_obj, names):
    segments = {}
    for name in names:
        bone = arm_obj.data.bones[name]
        segments[name] = (arm_obj.matrix_world @ bone.head_local,
                          arm_obj.matrix_world @ bone.tail_local)
    return segments


def dist_point_segment(point, a, b):
    ab = b - a
    length_sq = ab.length_squared
    if length_sq < 1e-12:
        return (point - a).length
    t = max(0.0, min(1.0, (point - a).dot(ab) / length_sq))
    return (point - (a + ab * t)).length


def apply_weights(obj, weights, groups_needed):
    """Replace every vertex group with the given {vertex: [(group, w), ...]}."""
    for group in list(obj.vertex_groups):
        obj.vertex_groups.remove(group)
    groups = {name: ensure_group(obj, name) for name in groups_needed}
    for index, entries in enumerate(weights):
        total = sum(w for _, w in entries)
        if total <= 0.0:
            continue
        for group_name, weight in entries:
            if weight > 0.0:
                groups[group_name].add([index], weight / total, "REPLACE")


def parent_to_armature(obj, arm_obj, auto=False):
    for selected in bpy.context.scene.objects:
        selected.select_set(False)
    obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    kind = "ARMATURE_AUTO" if auto else "ARMATURE"
    bpy.ops.object.parent_set(type=kind)


def nearest_bone_weights(obj, arm_obj, allowed, power=4.0):
    """Fallback: smooth inverse-distance blend over the allowed bones."""
    segments = bone_segments(arm_obj, allowed)
    matrix = obj.matrix_world
    weights = []
    for vertex in obj.data.vertices:
        point = matrix @ vertex.co
        distances = []
        for name in allowed:
            distance = dist_point_segment(point, *segments[name])
            distances.append((name, max(distance, 1e-4)))
        distances.sort(key=lambda pair: pair[1])
        nearest = distances[:2]
        raw = [(name, 1.0 / (distance ** power)) for name, distance in nearest]
        weights.append(raw)
    return weights


def read_weights(obj, allowed, max_influences=4):
    index_to_name = {group.index: group.name for group in obj.vertex_groups}
    allowed_set = set(allowed)
    result = []
    empty = 0
    for vertex in obj.data.vertices:
        entries = []
        for element in vertex.groups:
            name = index_to_name.get(element.group)
            if name in allowed_set and element.weight > 1e-5:
                entries.append((name, element.weight))
        if not entries:
            empty += 1
        entries.sort(key=lambda pair: -pair[1])
        result.append([(name, weight) for name, weight in entries[:max_influences]])
    return result, empty


def fix_unweighted(obj, arm_obj, allowed, weights):
    segments = bone_segments(arm_obj, allowed)
    matrix = obj.matrix_world
    fixed = 0
    for index, entries in enumerate(weights):
        if entries:
            continue
        point = matrix @ obj.data.vertices[index].co
        best = min(allowed, key=lambda name: dist_point_segment(point, *segments[name]))
        weights[index] = [(best, 1.0)]
        fixed += 1
    return fixed


def ensure_armature_modifier(obj, arm_obj):
    modifiers = [mod for mod in obj.modifiers if mod.type == "ARMATURE"]
    modifier = modifiers[0] if modifiers else obj.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = arm_obj
    modifier.use_vertex_groups = True
    return modifier


def build_skinning(arm_obj):
    report = {"auto": {}, "rigid": {}, "manual_gradient": {}, "fallback": {},
              "unweighted_fixed": 0, "failed": []}
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    all_deform = [bone.name for bone in arm_obj.data.bones if bone.use_deform]

    for obj in sorted(meshes, key=lambda item: item.name):
        allowed = AUTO_ALLOWED.get(obj.name)
        rigid_bone = rigid_bone_for(obj.name)

        if rigid_bone:
            parent_to_armature(obj, arm_obj, auto=False)
            apply_weights(obj, [[(rigid_bone, 1.0)]] * len(obj.data.vertices), [rigid_bone])
            report["rigid"][obj.name] = rigid_bone
        elif obj.name == "Mouth":
            parent_to_armature(obj, arm_obj, auto=False)
            matrix = obj.matrix_world
            weights = []
            for vertex in obj.data.vertices:
                z = (matrix @ vertex.co).z
                t = (MOUTH_TOP_Z - z) / (MOUTH_TOP_Z - MOUTH_BOTTOM_Z)
                t = min(1.0, max(0.0, t))
                t = t * t * (3.0 - 2.0 * t)
                weights.append([(MOUTH_BONES[0], 1.0 - t), (MOUTH_BONES[1], t)])
            apply_weights(obj, weights, list(MOUTH_BONES))
            report["manual_gradient"][obj.name] = {
                "bones": list(MOUTH_BONES), "top_z": MOUTH_TOP_Z, "bottom_z": MOUTH_BOTTOM_Z}
        else:
            if allowed is None:
                allowed = all_deform
                warn("%s has no explicit skin map, using every deform bone" % obj.name)
            try:
                parent_to_armature(obj, arm_obj, auto=True)
                weights, empty = read_weights(obj, allowed)
                fixed = fix_unweighted(obj, arm_obj, allowed, weights)
                apply_weights(obj, weights, allowed)
                report["auto"][obj.name] = {"bones": allowed, "unweighted_fixed": fixed}
                report["unweighted_fixed"] += fixed
                if empty:
                    log("  %s: %d vertices had no automatic weight, fixed" % (obj.name, fixed))
            except Exception as exc:  # bone heat can fail on tiny/closed shells
                warn("automatic weights failed on %s (%s); using inverse-distance fallback"
                     % (obj.name, exc))
                if obj.parent is None or obj.parent != arm_obj:
                    parent_to_armature(obj, arm_obj, auto=False)
                weights = nearest_bone_weights(obj, arm_obj, allowed)
                apply_weights(obj, weights, allowed)
                report["fallback"][obj.name] = str(exc)

        ensure_armature_modifier(obj, arm_obj)

    report["failed"] = sorted(set(report["failed"]))
    return report


# ---------------------------------------------------------------------------
# Section 5: shape keys
# ---------------------------------------------------------------------------
def ensure_shape_key(obj, name):
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    block = obj.data.shape_keys.key_blocks.get(name)
    if block is None:
        block = obj.shape_key_add(name=name, from_mix=False)
    block.value = 0.0
    block.slider_min = 0.0
    block.slider_max = 1.0
    return block


def local_coords(obj):
    return [vertex.co.copy() for vertex in obj.data.vertices]


def build_shape_keys():
    report = {}
    for obj in bpy.data.objects:
        if obj.type == "MESH" and abs(obj.scale[0] - 1.0) > 1e-4:
            warn("%s has non-unit scale %s" % (obj.name, tuple(round(v, 4) for v in obj.scale)))

    # blink.L / blink.R: stretch the lid downwards and bring it in front of the pupil.
    # The eyelid meshes are centred on their own origin, so the deformation is
    # computed in WORLD space and converted back to local space.
    for side, obj_name in (("L", "Eyelid_L"), ("R", "Eyelid_R")):
        obj = bpy.data.objects[obj_name]
        name = "blink." + side
        block = ensure_shape_key(obj, name)
        matrix = obj.matrix_world
        inverse = matrix.inverted()
        world = [matrix @ co for co in local_coords(obj)]
        top_z = max(co.z for co in world)
        center_x = sum(co.x for co in world) / len(world)
        front_y = min(co.y for co in world)
        shift_y = -0.2495 - front_y          # in front of the pupil (-0.239)
        for index, co in enumerate(world):
            block.data[index].co = inverse @ Vector((
                center_x + (co.x - center_x) * 0.95,
                co.y + shift_y,
                top_z - (top_z - co.z) * 3.6,
            ))
        report[name] = {"object": obj_name, "type": "lid_stretch",
                        "eye_coverage": "z %.3f -> %.3f, front y -0.2495"
                                        % (top_z, top_z - (top_z - min(c.z for c in world)) * 3.6)}

    # smile + mouth_open on the same mouth mesh
    mouth = bpy.data.objects["Mouth"]
    coords = local_coords(mouth)
    center_x = sum(co.x for co in coords) / len(coords)
    center_z = sum(co.z for co in coords) / len(coords)
    half_width = max(abs(co.x - center_x) for co in coords) or 1.0

    smile = ensure_shape_key(mouth, "smile")
    for index, co in enumerate(coords):
        t = min(1.0, abs(co.x - center_x) / half_width)
        smile.data[index].co = Vector((
            center_x + (co.x - center_x) * 1.30,
            co.y - 0.0035 * t * t,
            co.z + 0.022 * (t ** 1.6),
        ))
    report["smile"] = {"object": "Mouth", "type": "corners_up_wide"}

    opened = ensure_shape_key(mouth, "mouth_open")
    for index, co in enumerate(coords):
        opened.data[index].co = Vector((
            center_x + (co.x - center_x) * 0.90,
            co.y - 0.002,
            center_z + (co.z - center_z) * 1.80,
        ))
    report["mouth_open"] = {"object": "Mouth", "type": "open_vertical"}

    # brow_up on both brows (same key name, two meshes)
    for obj_name in ("Brow_L", "Brow_R"):
        obj = bpy.data.objects[obj_name]
        block = ensure_shape_key(obj, "brow_up")
        for index, co in enumerate(local_coords(obj)):
            block.data[index].co = Vector((co.x, co.y - 0.003, co.z + 0.017))
        report.setdefault("brow_up", {"objects": []})
        report["brow_up"]["objects"].append(obj_name)
        report["brow_up"]["type"] = "raise"
    return report


# ---------------------------------------------------------------------------
# Section 6: action helpers
# ---------------------------------------------------------------------------
def new_action(arm_obj, name):
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm_obj.animation_data.action = action
    return action


def set_action_range(action, start, end):
    """Manual frame range so glTF/render use exactly the intended clip length."""
    try:
        action.use_frame_range = True
        action.frame_start = float(start)
        action.frame_end = float(end)
    except Exception as exc:
        warn("could not set manual frame range on %s: %s" % (action.name, exc))


def attach_key_action(key_id, action, slot_name):
    anim = key_id.animation_data_create()
    anim.action = action
    if getattr(anim, "action_slot", None) is None and hasattr(action, "slots"):
        try:
            anim.action_slot = action.slots.new(id_type="KEY", name=slot_name)
        except Exception as exc:
            warn("could not create KEY slot on %s: %s" % (action.name, exc))
    if getattr(anim, "action_slot", None) is not None:
        # remember which slot belongs to this Key so actions can be re-linked
        key_id["rig_action_slot"] = anim.action_slot.identifier
    return anim


def stored_slot_name(keys):
    try:
        return str(keys["rig_action_slot"])
    except KeyError:
        return None


def find_slot(action, wanted):
    """Resolve an action slot by its identifier (Blender 4.4+ slotted actions)."""
    if not hasattr(action, "slots"):
        return None
    if wanted:
        for slot in action.slots:
            if getattr(slot, "identifier", None) == wanted:
                return slot
        try:
            return action.slots.get(wanted)
        except (KeyError, TypeError):
            return None
    return None


def key_shape(block, frame, value):
    block.value = value
    block.keyframe_insert("value", frame=frame)


def iter_fcurves(action):
    curves = []
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in getattr(strip, "channelbags", []):
                    curves.extend(channelbag.fcurves)
    if not curves and hasattr(action, "fcurves"):
        curves.extend(action.fcurves)
    return curves


def smooth_action(action, interpolation="BEZIER"):
    for curve in iter_fcurves(action):
        for point in curve.keyframe_points:
            point.interpolation = interpolation
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


def action_stats(action):
    return {
        "name": action.name,
        "slots": len(action.slots) if hasattr(action, "slots") else 0,
        "fcurves": len(iter_fcurves(action)),
        "frame_range": [round(v, 2) for v in action.frame_range],
    }


X_AXIS = (1.0, 0.0, 0.0)
Y_AXIS = (0.0, 1.0, 0.0)
Z_AXIS = (0.0, 0.0, 1.0)


def build_idle_wave(arm_obj):
    """48 frames: right arm lifts, hand waves, head follows."""
    action = new_action(arm_obj, "idle_wave")

    def right_arm(frame, shoulder, upper, fore, hand):
        key_bone(arm_obj, "shoulder.R", frame, [(Y_AXIS, shoulder)])
        key_bone(arm_obj, "upper_arm.R", frame, [(Y_AXIS, upper)])
        key_bone(arm_obj, "forearm.R", frame, [(Y_AXIS, fore)])
        key_bone(arm_obj, "hand.R", frame, [(Y_AXIS, hand)])

    right_arm(1, -2, -4, 0, 0)
    right_arm(6, -6, -52, -10, 5)
    right_arm(11, -9, -98, -22, 9)
    right_arm(16, -9, -98, 6, 2)
    right_arm(21, -9, -98, -44, 10)
    right_arm(26, -9, -98, 6, 2)
    right_arm(31, -9, -98, -40, 9)
    right_arm(36, -8, -86, -4, 3)
    right_arm(43, -5, -34, -8, 1)
    right_arm(48, -2, -4, 0, 0)

    for frame, value in ((1, 2), (11, -5), (22, 3), (34, -3), (48, 2)):
        key_bone(arm_obj, "upper_arm.L", frame, [(Y_AXIS, value)])
        key_bone(arm_obj, "forearm.L", frame, [(X_AXIS, value * 0.6)])

    for frame, turn, nod in ((1, 0, 0), (11, 6, -2), (20, 3, 2),
                             (30, 8, -1), (40, 4, 1), (48, 0, 0)):
        key_bone(arm_obj, "head", frame, [(Z_AXIS, turn), (X_AXIS, nod)])
        key_bone(arm_obj, "neck", frame, [(Z_AXIS, turn * 0.35), (X_AXIS, nod * 0.4)])

    for frame, bob, lean in ((1, 0.0, 0), (12, 0.003, -2), (24, 0.001, 1),
                             (36, 0.004, -2), (48, 0.0, 0)):
        # the bob lives on the spine, never on the hips: hips motion would
        # lift/sink the feet because the legs are FK below the pelvis.
        key_bone(arm_obj, "hips", frame, [(Y_AXIS, lean)])
        key_bone(arm_obj, "spine", frame, [(Z_AXIS, -lean * 0.6)],
                 world_loc=(0.0, 0.0, bob))

    set_action_range(action, 1, 48)
    smooth_action(action)
    reset_pose(arm_obj)
    log("action idle_wave built: %s" % (action_stats(action),))
    return action


def build_blink_smile(arm_obj):
    """24 frames: both eyes blink, mouth smiles, jaw opens slightly."""
    action = new_action(arm_obj, "blink_smile")

    eyelid_l = bpy.data.objects["Eyelid_L"].data.shape_keys
    eyelid_r = bpy.data.objects["Eyelid_R"].data.shape_keys
    mouth = bpy.data.objects["Mouth"].data.shape_keys
    brow_l = bpy.data.objects["Brow_L"].data.shape_keys
    brow_r = bpy.data.objects["Brow_R"].data.shape_keys

    for index, key_id in enumerate((eyelid_l, eyelid_r, mouth, brow_l, brow_r)):
        attach_key_action(key_id, action, "AdenFace_%d" % index)

    blink_curve = ((1, 0.0), (5, 0.12), (7, 1.0), (10, 1.0), (13, 0.0), (24, 0.0))
    for frame, value in blink_curve:
        key_shape(eyelid_l.key_blocks["blink.L"], frame, value)
        key_shape(eyelid_r.key_blocks["blink.R"], frame, value)

    for frame, value in ((1, 0.0), (6, 0.75), (10, 1.0), (18, 1.0), (22, 0.5), (24, 0.0)):
        key_shape(mouth.key_blocks["smile"], frame, value)

    for frame, value in ((1, 0.0), (6, 0.0), (9, 0.7), (13, 0.25), (18, 0.0), (24, 0.0)):
        key_shape(mouth.key_blocks["mouth_open"], frame, value)

    for key_id in (brow_l, brow_r):
        for frame, value in ((1, 0.0), (6, 0.0), (10, 0.7), (16, 0.55), (20, 0.2), (24, 0.0)):
            key_shape(key_id.key_blocks["brow_up"], frame, value)

    for frame, nod, turn in ((1, 0, 0), (7, -3, 2), (12, -1, 1), (18, 2, -2), (24, 0, 0)):
        key_bone(arm_obj, "head", frame, [(X_AXIS, nod), (Z_AXIS, turn)])
        key_bone(arm_obj, "spine", frame, [(X_AXIS, nod * 0.25)])

    for frame, jaw in ((1, 0), (6, 0), (9, 8), (13, 3), (18, 0), (24, 0)):
        key_bone(arm_obj, "jaw", frame, [(X_AXIS, jaw)])

    set_action_range(action, 1, 24)
    smooth_action(action)
    reset_pose(arm_obj)
    log("action blink_smile built: %s" % (action_stats(action),))
    return action


def build_walk_cycle(arm_obj):
    """32 frames, two steps, analytic 2-bone leg IK, no foot sliding.

    The clip carries 0.24 m of root motion (forward = -Y) so the planted foot
    stays fixed in world space: remove the root location curves for an
    in-place variant of the same cycle.
    """
    action = new_action(arm_obj, "walk_cycle")
    total = 32
    thigh_len = 0.150
    shin_len = 0.135
    hip_z = 0.340
    ankle_z = 0.055
    reach = 0.060                 # half step length (m)
    stride = 4.0 * reach          # metres travelled per full cycle
    lift = 0.035                  # swing foot clearance

    def leg_angles(drop, ankle_y):
        """2-bone IK: thigh/shin rotation (deg) that put the ankle on target."""
        vertical = (hip_z - drop) - ankle_z
        distance = min(math.hypot(vertical, ankle_y), thigh_len + shin_len - 1e-4)
        psi = math.degrees(math.atan2(ankle_y, vertical))
        cos_alpha = (thigh_len ** 2 + distance ** 2 - shin_len ** 2) / (2 * thigh_len * distance)
        cos_knee = (thigh_len ** 2 + shin_len ** 2 - distance ** 2) / (2 * thigh_len * shin_len)
        alpha = math.degrees(math.acos(max(-1.0, min(1.0, cos_alpha))))
        knee = 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, cos_knee))))
        return psi + alpha, knee

    for frame in range(1, total + 2):
        phase = (frame - 1) / float(total)
        # pelvis is lowest at contact (legs need reach) and highest at passing
        # (legs nearly straight) - the natural walk bob, and it keeps the IK
        # from producing a permanently crouched stance.
        drop = 0.010 * abs(math.cos(TAU * phase))
        key_bone(arm_obj, "root", frame, [],
                 world_loc=(0.0, -stride * phase, 0.0))
        key_bone(arm_obj, "hips", frame,
                 [(Z_AXIS, 5.0 * math.sin(TAU * phase))],
                 world_loc=(0.0, 0.0, -drop))

        for side, shift in (("L", 0.0), ("R", 0.5)):
            p = (phase + shift) % 1.0
            if p <= 0.5:                       # stance: foot fixed on the floor
                ankle_y = -reach + 4.0 * reach * p
                ankle_up = 0.0
            else:                              # swing: foot lifts and reaches
                t = (p - 0.5) / 0.5
                smooth = t * t * (3.0 - 2.0 * t)
                ankle_y = reach - 2.0 * reach * smooth
                ankle_up = lift * math.sin(math.pi * t)
            thigh, shin = leg_angles(drop + ankle_up, ankle_y)
            key_bone(arm_obj, "thigh." + side, frame, [(X_AXIS, thigh)])
            key_bone(arm_obj, "shin." + side, frame, [(X_AXIS, shin)])
            key_bone(arm_obj, "foot." + side, frame, [(X_AXIS, -(thigh + shin))])

        swing = 16.0 * math.cos(TAU * phase)
        key_bone(arm_obj, "upper_arm.L", frame, [(X_AXIS, swing)])
        key_bone(arm_obj, "upper_arm.R", frame, [(X_AXIS, -swing)])
        key_bone(arm_obj, "forearm.L", frame, [(X_AXIS, 8.0 + 5.0 * math.cos(TAU * phase))])
        key_bone(arm_obj, "forearm.R", frame, [(X_AXIS, 8.0 - 5.0 * math.cos(TAU * phase))])
        key_bone(arm_obj, "spine", frame,
                 [(Z_AXIS, -4.0 * math.sin(TAU * phase)), (X_AXIS, -2.0)])
        key_bone(arm_obj, "head", frame, [(Z_AXIS, -2.0 * math.sin(TAU * phase))])

    set_action_range(action, 1, total)
    smooth_action(action)
    reset_pose(arm_obj)
    log("action walk_cycle built: %s" % (action_stats(action),))
    return action


# ---------------------------------------------------------------------------
# Section 7: scene, camera, render helpers
# ---------------------------------------------------------------------------
def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.show_shadows = True
    shading.shadow_intensity = 0.35
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.curvature_ridge_factor = 1.2
    shading.curvature_valley_factor = 1.0
    shading.show_object_outline = True
    shading.background_type = "VIEWPORT"
    shading.background_color = (0.09, 0.10, 0.13)
    log("scene set to Workbench 640x640 @24fps")


def create_camera_and_ground():
    scene = bpy.context.scene
    if scene.camera is None:
        cam_data = bpy.data.cameras.new("RigTestCamera")
        cam_data.lens = 50.0
        cam_obj = bpy.data.objects.new("RigTestCamera", cam_data)
        scene.collection.objects.link(cam_obj)
        cam_obj.location = Vector((1.15, -2.45, 0.92))
        target = Vector((0.0, 0.0, 0.58))
        cam_obj.rotation_euler = (target - cam_obj.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam_obj
        log("camera created at %s" % (tuple(round(v, 2) for v in cam_obj.location),))

    if "RIGTEST_Ground" not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0.0, 0.0, 0.005))
        ground = bpy.context.active_object
        ground.name = "RIGTEST_Ground"
        material = bpy.data.materials.new("RIGTEST_GroundMat")
        material.use_nodes = True
        material.diffuse_color = (0.30, 0.32, 0.37, 1.0)
        ground.data.materials.append(material)
        log("ground plane created at z=0.005")


def set_pose(arm_obj, pose):
    reset_pose(arm_obj)
    for bone_name, pairs in pose.items():
        pose_bone = arm_obj.pose.bones[bone_name]
        pose_bone.rotation_mode = "QUATERNION"
        inv = pose_bone.bone.matrix_local.to_3x3().inverted()
        quat = Quaternion((1.0, 0.0, 0.0, 0.0))
        for axis, degrees in pairs:
            quat = quat @ Quaternion((inv @ Vector(axis)).normalized(), DEG(degrees))
        pose_bone.rotation_quaternion = quat
    bpy.context.view_layer.update()


TEST_POSE = {
    "upper_arm.L": [(Y_AXIS, 62.0)],
    "forearm.L": [(Y_AXIS, 32.0)],
    "upper_arm.R": [(Y_AXIS, -24.0)],
    "thigh.R": [(X_AXIS, -32.0)],
    "shin.R": [(X_AXIS, 48.0)],
    "foot.R": [(X_AXIS, -12.0)],
    "head": [(Z_AXIS, 16.0), (X_AXIS, -5.0)],
    "jaw": [(X_AXIS, 9.0)],
}


def render_still(path, frame=None):
    scene = bpy.context.scene
    if frame is not None:
        scene.frame_set(frame)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)
    return path


def render_animation(arm_obj, action, out_dir, name, frame_start, frame_end):
    scene = bpy.context.scene
    arm_obj.animation_data.action = action
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(frame_start)
    base = os.path.join(out_dir, name)
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.gopsize = 12
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = base
    bpy.ops.render.render(animation=True)
    produced = None
    candidates = sorted(glob.glob(os.path.join(out_dir, name + "*.mp4")))
    if candidates:
        produced = candidates[0]
    if produced is None:
        warn("no mp4 produced for %s (looked for %s*.mp4)" % (name, base))
    else:
        log("rendered %s (%d frames)" % (produced, frame_end - frame_start + 1))
    return produced


# ---------------------------------------------------------------------------
# Section 8: save, export, manifest
# ---------------------------------------------------------------------------
def collect_bone_data(arm_obj):
    rows = []
    for bone in arm_obj.data.bones:
        rows.append({
            "name": bone.name,
            "head": [round(v, 4) for v in bone.head_local],
            "tail": [round(v, 4) for v in bone.tail_local],
            "parent": bone.parent.name if bone.parent else None,
            "connected": bool(bone.use_connect),
            "deform": bool(bone.use_deform),
            "length": round(bone.length, 4),
        })
    return rows


def mesh_totals():
    objects = [o for o in bpy.data.objects
               if o.type == "MESH" and not o.name.startswith("RIGTEST_")]
    return {
        "objects": len(objects),
        "vertices": sum(len(o.data.vertices) for o in objects),
        "faces": sum(len(o.data.polygons) for o in objects),
    }


def collect_shape_keys():
    rows = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type != "MESH" or obj.data.shape_keys is None:
            continue
        for block in obj.data.shape_keys.key_blocks:
            if block.name == "Basis":
                continue
            rows.append({"name": block.name, "object": obj.name,
                         "vertices": len(block.data)})
    return rows


def export_glb(out_dir, arm_obj):
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "ARMATURE"} and not obj.name.startswith("RIGTEST_"):
            obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    path = safe_path(os.path.join(out_dir, "aden-character-rigged.glb"))
    options = dict(filepath=path, export_format="GLB", use_selection=True,
                   export_animations=True, export_animation_mode="ACTIONS",
                   export_skins=True, export_morph=True, export_yup=True,
                   export_apply=False)
    try:
        bpy.ops.export_scene.gltf(**options)
    except TypeError as exc:
        warn("glTF export with full options failed (%s); retrying minimal options" % exc)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)
    if os.path.exists(path):
        log("exported glb: %s (%.1f KB)" % (path, os.path.getsize(path) / 1024.0))
    else:
        warn("glb export wrote no file at %s" % path)
    return path


def file_entry(path, extra=None):
    entry = {"path": path,
             "exists": os.path.exists(path),
             "bytes": os.path.getsize(path) if os.path.exists(path) else 0,
             "sha256": sha256_file(path)}
    if extra:
        entry.update(extra)
    return entry


def write_manifest(out_dir, arm_obj, skin, key_report, actions, renders, proof,
                   source, source_sha, blend_path, glb_path, render_mode):
    shape_keys = collect_shape_keys()
    manifest = {
        "schema": "ahos.character-rig.v1",
        "character_id": "aden",
        "version": "v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "technical_only": True,
        "identity_status": "PENDING_IDENTITY_REVIEW",
        "blender": bpy.app.version_string,
        "render_engine": bpy.context.scene.render.engine,
        "render_mode": render_mode,
        "source": {"blend": source, "sha256": source_sha},
        "outputs": {
            "blend": file_entry(blend_path),
            "glb": file_entry(glb_path),
        },
        "rig": {
            "armature": ARMATURE_NAME,
            "bone_count": len(arm_obj.data.bones),
            "deform_bone_count": len([b for b in arm_obj.data.bones if b.use_deform]),
            "bones": collect_bone_data(arm_obj),
            "side_convention": "L = -X, R = +X (follows source object naming; character faces -Y)",
            "skinning": {
                "rigid_objects": skin["rigid"],
                "automatic_weight_objects": skin["auto"],
                "manual_gradient_objects": skin["manual_gradient"],
                "fallback_objects": skin["fallback"],
                "unweighted_vertices_fixed": skin["unweighted_fixed"],
            },
        },
        "mesh_stats": mesh_totals(),
        "shape_keys": shape_keys,
        "shape_key_names": sorted({row["name"] for row in shape_keys}),
        "shape_key_note": "blink.L/blink.R live on the eyelid meshes, smile/mouth_open on Mouth, "
                          "brow_up on both brow meshes (Blender shape keys are per mesh datablock).",
        "actions": [
            dict(action_stats(action),
                 frame_start=start, frame_end=end,
                 seconds=round((end - start + 1) / 24.0, 3))
            for action, start, end in actions
        ],
        "renders": {
            "rig_proof": file_entry(proof) if proof else None,
            "stills": renders.get("stills", []),
            "videos": renders.get("videos", []),
        },
        "warnings": WARNINGS,
        "notes": [
            "Skinning: automatic weights (bone heat) for the deformable parts, "
            "rigid single-bone weights for the 60-object chibi parts, "
            "manual vertical gradient for the mouth (head -> jaw).",
            "Shape keys are spread over the meshes that own the geometry.",
            "All media is rendered with CPU Workbench (no GPU, no paid add-on).",
        ],
    }
    path = safe_path(os.path.join(out_dir, "rig-manifest.json"))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    log("manifest written: %s" % path)
    return path


def set_active_action(arm_obj, action):
    """Keep armature and shape-key animation in sync (slotted actions)."""
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
            wanted = stored_slot_name(keys)
            target = find_slot(action, wanted)
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


# ---------------------------------------------------------------------------
# Section 9: main
# ---------------------------------------------------------------------------
def main():
    opts = parse_args()
    source = bpy.data.filepath
    if not source:
        raise RuntimeError("no .blend file loaded")
    out_dir = os.path.abspath(opts["out"] or os.path.join(os.path.dirname(source), "rig-test"))
    preview_dir = os.path.join(out_dir, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    log("=" * 68)
    log("source: %s" % source)
    log("output: %s" % out_dir)
    log("render mode: %s" % opts["render"])

    scene = bpy.context.scene
    scene.frame_set(1)
    source_sha = sha256_file(source)

    arm_obj = create_armature()
    skin = build_skinning(arm_obj)
    log("skinning: %d rigid / %d automatic / %d gradient / %d fallback / %d vertices fixed"
        % (len(skin["rigid"]), len(skin["auto"]), len(skin["manual_gradient"]),
           len(skin["fallback"]), skin["unweighted_fixed"]))
    keys = build_shape_keys()
    log("shape keys: %s" % (sorted(keys.keys()),))

    setup_scene()
    create_camera_and_ground()

    proof = None
    if opts["render"] != "none":
        set_pose(arm_obj, TEST_POSE)
        proof = safe_path(os.path.join(preview_dir, "00-rig-test-pose.png"))
        render_still(proof)
        log("rig proof still: %s" % proof)
    reset_pose(arm_obj)

    idle = build_idle_wave(arm_obj)
    face = build_blink_smile(arm_obj)
    walk = build_walk_cycle(arm_obj)
    actions = [(idle, 1, 48), (face, 1, 24), (walk, 1, 32)]

    set_active_action(arm_obj, idle)
    scene.frame_start, scene.frame_end = 1, 48
    scene.frame_set(1)

    blend_path = safe_path(os.path.join(out_dir, "aden-character-rigged.blend"))
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    log("blend saved: %s" % blend_path)
    glb_path = export_glb(out_dir, arm_obj)

    renders = {"stills": [], "videos": []}
    if opts["render"] in ("stills", "full"):
        for action, start, end in actions:
            set_active_action(arm_obj, action)
            for tag, frame in (("start", start), ("mid", int((start + end) / 2)), ("end", end)):
                path = safe_path(os.path.join(preview_dir, "%s_%s_f%02d.png"
                                              % (action.name, tag, frame)))
                render_still(path, frame=frame)
                renders["stills"].append(file_entry(path, {"action": action.name,
                                                           "frame": frame,
                                                           "resolution": "640x640"}))
                log("still: %s" % path)
    if opts["render"] == "full":
        for action, start, end in actions:
            set_active_action(arm_obj, action)
            path = render_animation(arm_obj, action, preview_dir, action.name, start, end)
            if path:
                renders["videos"].append(file_entry(path, {"action": action.name,
                                                           "frame_start": start,
                                                           "frame_end": end,
                                                           "resolution": "640x640",
                                                           "fps": 24}))

    set_active_action(arm_obj, idle)
    scene.frame_set(1)

    write_manifest(out_dir, arm_obj, skin, keys, actions, renders, proof,
                   source, source_sha, blend_path, glb_path, opts["render"])
    log("done in %.1f s" % (time.time() - START_TIME,))
    print("BUILD_OK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("BUILD_FAILED", flush=True)
        sys.exit(1)






