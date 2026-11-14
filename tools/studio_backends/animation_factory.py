"""AHOS Animation Factory v0.1 - beat-driven acting on any rigged character.

    blender -b <rigged.blend> --factory-startup --python animation_factory.py -- \
        --plan plan.json --out <dir> --contract rig-contract.json

Beats: walk_to, look_at, turn_to, pick_up, talk. Every beat is a parameterised
procedure that reads bone / shape-key names from the rig contract; no
character-specific code lives here.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

DEG = math.radians
X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
LOG = []


def log(msg):
    text = "[ANIM] %s" % (msg,)
    LOG.append(text)
    print(text, flush=True)


def parse_args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"plan": None, "out": None, "contract": None}
    i = 0
    while i < len(tail):
        if tail[i] in ("--plan", "--out", "--contract") and i + 1 < len(tail):
            opts[tail[i].strip("-")] = tail[i + 1]
            i += 2
        else:
            i += 1
    return opts


def set_bone(arm, name, frame, rotations=None, location=None):
    pb = arm.pose.bones.get(name)
    if pb is None:
        return False
    pb.rotation_mode = "QUATERNION"
    inv = pb.bone.matrix_local.to_3x3().inverted()
    quat = Quaternion((1.0, 0.0, 0.0, 0.0))
    for axis, degrees in rotations or ():
        quat = quat @ Quaternion((inv @ Vector(axis)).normalized(), DEG(degrees))
    pb.rotation_quaternion = quat
    pb.keyframe_insert("rotation_quaternion", frame=frame)
    if location is not None:
        pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(location)
        pb.keyframe_insert("location", frame=frame)
    return True


def key_shape(keys, block_name, frame, value):
    if keys is None:
        return False
    block = keys.key_blocks.get(block_name)
    if block is None:
        return False
    block.value = value
    block.keyframe_insert("value", frame=frame)
    return True


def smooth(action):
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "BEZIER"
                        point.handle_left_type = "AUTO_CLAMPED"
                        point.handle_right_type = "AUTO_CLAMPED"


# ---------------------------------------------------------------------------
# beat procedures
# ---------------------------------------------------------------------------
def beat_walk_to(arm, start, frames, distance=0.5):
    steps = max(2, int(round(frames / 8.0)))
    for index in range(steps + 1):
        frame = start + int(round(index * frames / float(steps)))
        phase = index / float(steps)
        swing = 22.0 * math.sin(2.0 * math.pi * phase)
        set_bone(arm, "thigh.L", frame, [(X, swing)])
        set_bone(arm, "thigh.R", frame, [(X, -swing)])
        set_bone(arm, "shin.L", frame, [(X, max(0.0, -swing) * 0.9 + 4.0)])
        set_bone(arm, "shin.R", frame, [(X, max(0.0, swing) * 0.9 + 4.0)])
        set_bone(arm, "foot.L", frame, [(X, -swing * 0.7)])
        set_bone(arm, "foot.R", frame, [(X, swing * 0.7)])
        set_bone(arm, "upper_arm.L", frame, [(X, -swing * 0.7)])
        set_bone(arm, "upper_arm.R", frame, [(X, swing * 0.7)])
        set_bone(arm, "root", frame, [], location=(0.0, -distance * phase, 0.0))
        set_bone(arm, "spine", frame, [(Z, 3.0 * math.sin(4.0 * math.pi * phase))])
    return {"beat": "walk_to", "start": start, "frames": frames, "distance_m": distance}


def beat_look_at(arm, start, frames, yaw=25.0, pitch=-6.0):
    for frame, factor in ((start, 0.0), (start + int(frames * 0.55), 1.0),
                          (start + frames, 1.0)):
        set_bone(arm, "neck", frame, [(Z, yaw * 0.35 * factor), (X, pitch * 0.4 * factor)])
        set_bone(arm, "head", frame, [(Z, yaw * 0.65 * factor), (X, pitch * factor)])
        set_bone(arm, "eye.L", frame, [(Z, yaw * 0.25 * factor)])
        set_bone(arm, "eye.R", frame, [(Z, yaw * 0.25 * factor)])
    return {"beat": "look_at", "start": start, "frames": frames, "yaw_deg": yaw}


def beat_turn_to(arm, start, frames, degrees=90.0):
    for frame, factor in ((start, 0.0), (start + int(frames * 0.3), 0.15),
                          (start + frames, 1.0)):
        set_bone(arm, "root", frame, [(Z, degrees * factor)])
    return {"beat": "turn_to", "start": start, "frames": frames, "degrees": degrees}


def beat_pick_up(arm, start, frames, hold=6):
    down = start + int(frames * 0.45)
    up = start + frames
    for frame, squat, reach in ((start, 0.0, 0.0), (down, 42.0, 1.0),
                                (down + hold, 44.0, 1.0), (up, 0.0, 0.0)):
        set_bone(arm, "thigh.L", frame, [(X, -squat * 0.55)])
        set_bone(arm, "thigh.R", frame, [(X, -squat * 0.55)])
        set_bone(arm, "shin.L", frame, [(X, squat)])
        set_bone(arm, "shin.R", frame, [(X, squat)])
        set_bone(arm, "foot.L", frame, [(X, -squat * 0.45)])
        set_bone(arm, "foot.R", frame, [(X, -squat * 0.45)])
        set_bone(arm, "hips", frame, [], location=(0.0, 0.0, -0.06 * (squat / 44.0)))
        set_bone(arm, "spine", frame, [(X, 26.0 * (squat / 44.0))])
        set_bone(arm, "upper_arm.R", frame, [(X, -70.0 * reach)])
        set_bone(arm, "forearm.R", frame, [(X, -35.0 * reach)])
        set_bone(arm, "hand.R", frame, [(X, -20.0 * reach)])
        set_bone(arm, "head", frame, [(X, 14.0 * (squat / 44.0))])
    return {"beat": "pick_up", "start": start, "frames": frames}


def beat_talk(arm, start, frames, keys=None, syllables=6):
    per = max(3, frames // max(1, syllables))
    for index in range(syllables + 1):
        frame = start + index * per
        opening = 0.55 if index % 2 == 0 else 0.12
        set_bone(arm, "jaw", frame, [(X, 9.0 * opening)])
        key_shape(keys, "mouth_open", frame, opening)
        set_bone(arm, "head", frame, [(X, -2.0 if index % 2 == 0 else 1.5),
                                      (Z, 3.0 if index % 3 == 0 else -2.0)])
        set_bone(arm, "spine", frame, [(Z, 2.0 if index % 2 == 0 else -2.0)])
        set_bone(arm, "upper_arm.L", frame, [(Y, -8.0 * opening)])
    set_bone(arm, "jaw", start + frames, [(X, 0.0)])
    key_shape(keys, "mouth_open", start + frames, 0.0)
    return {"beat": "talk", "start": start, "frames": frames, "syllables": syllables}


BEATS = {"walk_to": beat_walk_to, "look_at": beat_look_at, "turn_to": beat_turn_to,
         "pick_up": beat_pick_up, "talk": beat_talk}


DEFAULT_BEATS = [
    {"action": "walk_to", "frames": 32, "distance": 0.45},
    {"action": "look_at", "frames": 14, "yaw": 28.0},
    {"action": "pick_up", "frames": 26},
    {"action": "turn_to", "frames": 18, "degrees": -35.0},
    {"action": "talk", "frames": 28, "syllables": 6},
]


def mouth_keys():
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.data.shape_keys:
            if "mouth_open" in obj.data.shape_keys.key_blocks:
                return obj.data.shape_keys
    return None


def main():
    opts = parse_args()
    if not opts["plan"] or not opts["out"]:
        raise SystemExit("--plan and --out are required")
    with open(opts["plan"], "r", encoding="utf-8-sig") as handle:
        plan = json.load(handle)
    contract = {}
    if opts["contract"] and os.path.isfile(opts["contract"]):
        with open(opts["contract"], "r", encoding="utf-8-sig") as handle:
            contract = json.load(handle)

    out_dir = os.path.abspath(opts["out"])
    os.makedirs(out_dir, exist_ok=True)
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm is None:
        raise RuntimeError("no armature in the scene")

    bones = set(contract.get("skeleton", {}).get("bones") or [])
    if bones:
        missing = sorted(name for name in bones if name not in arm.pose.bones)
        if missing:
            raise RuntimeError("contract bones not present: %s" % ",".join(missing[:6]))
    keys = mouth_keys()

    beats = plan.get("animation_beats") or DEFAULT_BEATS
    action_name = plan.get("action_name") or ("scene_%s" % plan.get("scene_id", "001"))
    if arm.animation_data is None:
        arm.animation_data_create()
    action = bpy.data.actions.new(action_name)
    action.use_fake_user = True
    arm.animation_data.action = action

    cursor = 1
    report = []
    for beat in beats:
        name = beat.get("action")
        if name not in BEATS:
            raise RuntimeError("unknown beat %r" % name)
        frames = int(beat.get("frames", 24))
        params = {k: v for k, v in beat.items() if k not in ("action", "frames", "start")}
        if name == "talk":
            result = BEATS[name](arm, cursor, frames, keys=keys, **params)
        else:
            result = BEATS[name](arm, cursor, frames, **params)
        result["frame_range"] = [cursor, cursor + frames - 1]
        report.append(result)
        log("%s frames %d-%d" % (name, cursor, cursor + frames - 1))
        cursor += frames

    end = max(1, cursor - 1)
    try:
        action.use_frame_range = True
        action.frame_start, action.frame_end = 1.0, float(end)
    except Exception:
        pass
    smooth(action)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, end
    bpy.context.scene.frame_set(1)

    stamp = ""
    blend_path = os.path.join(out_dir, "%s-animated.blend" % plan.get("character_id", "character"))
    glb_path = os.path.join(out_dir, "%s-animated.glb" % plan.get("character_id", "character"))
    if os.path.exists(blend_path):
        stamp = "-%d" % int(os.path.getmtime(blend_path))
        blend_path = blend_path.replace(".blend", "%s.blend" % stamp)
        glb_path = glb_path.replace(".glb", "%s.glb" % stamp)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    for obj in bpy.context.scene.objects:
        obj.select_set(obj.type in {"MESH", "ARMATURE"})
    try:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB",
                                  use_selection=True, export_animations=True,
                                  export_animation_mode="ACTIONS")
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=True)

    manifest = {
        "schema": "ahos.animation.v1",
        "character_id": plan.get("character_id"),
        "scene_id": plan.get("scene_id", "001"),
        "action": action_name,
        "frame_range": [1, end],
        "fps": plan.get("fps", 24),
        "beats": report,
        "contract_sha256": plan.get("rig_contract_sha256"),
        "bones_used": sorted({b.name for b in arm.pose.bones
                              if any(b.name in json.dumps(entry) for entry in report)}),
        "blender": bpy.app.version_string,
        "log": LOG,
    }
    with open(os.path.join(out_dir, "animation-manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    log("action %s frames 1-%d" % (action_name, end))
    log("blend: %s" % blend_path)
    print("ANIMATION_OK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("ANIMATION_FAILED", flush=True)
        sys.exit(1)


