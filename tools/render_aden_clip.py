"""Riglenmiş Aden'den 5 sn, 24 fps, 768×512 yerel klip kareleri üretir."""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = Path(args[args.index("--out") + 1]) if "--out" in args else Path("frames")
out.mkdir(parents=True, exist_ok=True)

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

for pose_bone in arm.pose.bones:
    pose_bone.rotation_mode = "QUATERNION"
    pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    pose_bone.location = (0.0, 0.0, 0.0)
    pose_bone.scale = (1.0, 1.0, 1.0)
arm.animation_data_create()
arm.animation_data.action = action
if hasattr(arm.animation_data, "action_slot") and action.slots:
    arm.animation_data.action_slot = action.slots[0]

for index in range(120):
    source = (index % 48) + 1
    scene.frame_set(source)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out / f"f{index:04d}.png")
    bpy.ops.render.render(write_still=True)
    if index % 20 == 0:
        print(f"FRAME_OK {index}/120 source={source}")
print("RENDER_DONE 120")
