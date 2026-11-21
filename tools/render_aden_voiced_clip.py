"""Aden 5 sn klip: idle_wave + Rhubarb viseme ağız animasyonu."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = Path(args[args.index("--out") + 1]) if "--out" in args else Path("frames")
viseme_path = Path(args[args.index("--visemes") + 1]) if "--visemes" in args else None
out.mkdir(parents=True, exist_ok=True)
if viseme_path is None:
    raise SystemExit("MISSING --visemes")
cues = json.loads(viseme_path.read_text(encoding="utf-8"))["mouthCues"]

# Rhubarb A/B/C... -> ağız açıklığı; X sessiz.
OPEN = {"X": 0.0, "A": 0.34, "B": 0.12, "C": 0.26, "D": 0.20,
        "E": 0.16, "F": 0.18, "G": 0.10, "H": 0.22}

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 768
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True

bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
floor = bpy.context.object
floor.name = "QA_Floor"
mat = bpy.data.materials.new("QA_Floor")
mat.diffuse_color = (0.78, 0.78, 0.78, 1.0)
floor.data.materials.append(mat)

cam_data = bpy.data.cameras.new("QA_Camera")
cam = bpy.data.objects.new("QA_Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.8
cam.location = (0, -3.0, 1.0)
cam.rotation_euler = (Vector((0, 0, 1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()

arm = next((obj for obj in bpy.data.objects if obj.type == "ARMATURE"), None)
if arm is None:
    raise SystemExit("NO_ARMATURE")
action = bpy.data.actions.get("idle_wave")
if action is None:
    raise SystemExit("MISSING_ACTION idle_wave")
arm.animation_data_create()
arm.animation_data.action = action
if hasattr(arm.animation_data, "action_slot") and action.slots:
    arm.animation_data.action_slot = action.slots[0]
jaw = arm.pose.bones.get("jaw")
mouth = bpy.data.objects.get("Mouth")
mouth_key = mouth.data.shape_keys.key_blocks.get("mouth_open") if mouth and mouth.data.shape_keys else None

for index in range(120):
    source = (index % 48) + 1
    scene.frame_set(source)
    t = index / 24.0 - 0.30
    value = "X"
    for cue in cues:
        if float(cue["start"]) <= t < float(cue["end"]):
            value = str(cue["value"])
            break
    amount = OPEN.get(value, 0.12)
    if mouth_key is not None:
        mouth_key.value = amount
    if jaw is not None:
        jaw.rotation_mode = "XYZ"
        jaw.rotation_euler = (amount * 0.35, 0.0, 0.0)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out / f"f{index:04d}.png")
    bpy.ops.render.render(write_still=True)
    if index % 20 == 0:
        print(f"FRAME_OK {index}/120 viseme={value} mouth={amount:.2f}")
print("RENDER_DONE 120")
