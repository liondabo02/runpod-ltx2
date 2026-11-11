"""Procedural Aden 3D character build for Blender 4.5 (headless).

Creates real editable mesh objects: head, face, eyes, lids, brows, hair, star
clip, torso, shirt print, arms, hands, legs, shoes. It is an original
code-built chibi model, NOT a photogrammetric likeness of the approved poster;
identity status is PENDING_IDENTITY_REVIEW.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve() if "--out" in sys.argv else ROOT / "build"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "previews").mkdir(exist_ok=True)

# ---------- scene reset ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 700
scene.render.resolution_y = 700
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.world = bpy.data.worlds.new("World")
scene.world.color = (0.82, 0.84, 0.86)

COL = bpy.data.collections.new("CHARACTER")
scene.collection.children.link(COL)


def mat(name: str, color: tuple[float, float, float], rough: float = 0.55, metal: float = 0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1.0)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
    return m


SKIN = mat("Skin_Aden", (0.86, 0.62, 0.47))
SKIN_DARK = mat("Skin_Shadow", (0.72, 0.48, 0.36))
HAIR = mat("Hair_Aden_DarkBrown", (0.13, 0.065, 0.035), 0.45)
BLUE = mat("Shirt_Aden_Cobalt", (0.035, 0.16, 0.55), 0.6)
NAVY = mat("Shorts_Aden_Navy", (0.035, 0.045, 0.09), 0.7)
YELLOW = mat("Clip_Kite_Yellow", (0.95, 0.68, 0.08), 0.35)
WHITE = mat("Eye_White", (0.96, 0.96, 0.94), 0.3)
BROWN = mat("Iris_Brown", (0.22, 0.10, 0.035), 0.35)
BLACK = mat("Pupil_Black", (0.01, 0.01, 0.01), 0.25)
RED = mat("Mouth_Rose", (0.55, 0.16, 0.17), 0.5)
CREAM = mat("Shoe_Cream", (0.88, 0.82, 0.68), 0.55)
FRECKLE = mat("Freckle_Brown", (0.40, 0.23, 0.13), 0.6)


def track(obj, material, smooth=True):
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    for c in obj.users_collection:
        c.objects.unlink(obj)
    COL.objects.link(obj)
    return obj


def sphere(name, loc, scale, material, segments=32, rings=20, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return track(obj, material)


def cube(name, loc, scale, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.modifier_add(type="BEVEL")
    obj.modifiers[-1].width = 0.012
    obj.modifiers[-1].segments = 3
    return track(obj, material)


def cylinder(name, loc, radius, depth, material, rot=(0, 0, 0), vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return track(obj, material)


# ---------- body ----------
# 3-year-old chibi proportions, ~0.98 m tall, big head.
sphere("Head", (0, 0, 0.90), (0.225, 0.205, 0.235), SKIN)
sphere("Neck", (0, 0, 0.70), (0.075, 0.07, 0.08), SKIN)
sphere("Torso_Shirt", (0, 0, 0.55), (0.165, 0.115, 0.165), BLUE)
cylinder("Shirt_Hem", (0, 0, 0.43), 0.155, 0.045, BLUE)
sphere("Hips_Shorts", (0, 0, 0.36), (0.145, 0.105, 0.10), NAVY)
sphere("Shorts_Left", (-0.075, 0, 0.33), (0.075, 0.095, 0.09), NAVY)
sphere("Shorts_Right", (0.075, 0, 0.33), (0.075, 0.095, 0.09), NAVY)
# sleeves
cylinder("Sleeve_L", (-0.155, 0, 0.60), 0.065, 0.09, BLUE, rot=(0, math.radians(20), 0))
cylinder("Sleeve_R", (0.155, 0, 0.60), 0.065, 0.09, BLUE, rot=(0, math.radians(-20), 0))
# arms (skin) and hands
cylinder("Arm_L", (-0.195, 0, 0.47), 0.045, 0.24, SKIN, rot=(0, math.radians(12), 0))
cylinder("Arm_R", (0.195, 0, 0.47), 0.045, 0.24, SKIN, rot=(0, math.radians(-12), 0))
sphere("Hand_L", (-0.218, 0, 0.34), (0.052, 0.045, 0.06), SKIN)
sphere("Hand_R", (0.218, 0, 0.34), (0.052, 0.045, 0.06), SKIN)
# legs
sphere("Thigh_L", (-0.078, 0, 0.24), (0.062, 0.062, 0.10), SKIN)
sphere("Thigh_R", (0.078, 0, 0.24), (0.062, 0.062, 0.10), SKIN)
cylinder("Shin_L", (-0.078, 0, 0.13), 0.048, 0.16, SKIN)
cylinder("Shin_R", (0.078, 0, 0.13), 0.048, 0.16, SKIN)
# shoes (cream sole, blue upper, star accent)
for side, x in (("L", -0.078), ("R", 0.078)):
    sphere(f"Shoe_Upper_{side}", (x, -0.025, 0.055), (0.062, 0.105, 0.045), BLUE)
    cube(f"Sole_{side}", (x, -0.025, 0.018), (0.115, 0.21, 0.025), CREAM)
    sphere(f"Shoe_Star_{side}", (x - 0.03 if side == "L" else x + 0.03, -0.115, 0.06),
           (0.012, 0.008, 0.012), YELLOW)

# ---------- face ----------
# eye whites / irises / pupils / catchlights
for side, x in (("L", -0.078), ("R", 0.078)):
    sphere(f"Eye_White_{side}", (x, -0.180, 0.925), (0.052, 0.030, 0.058), WHITE)
    sphere(f"Eye_Iris_{side}", (x, -0.206, 0.922), (0.034, 0.014, 0.038), BROWN)
    sphere(f"Eye_Pupil_{side}", (x, -0.217, 0.921), (0.019, 0.008, 0.022), BLACK)
    sphere(f"Eye_Glint_{side}", (x - 0.008, -0.224, 0.936), (0.007, 0.004, 0.007), WHITE)
    # upper eyelid rim, skin tone
    sphere(f"Eyelid_{side}", (x, -0.174, 0.958), (0.054, 0.020, 0.018), SKIN_DARK)
    # brow
    sphere(f"Brow_{side}", (x, -0.198, 0.995), (0.050, 0.010, 0.009), HAIR,
           rot=(0, 0, math.radians(6 if side == "L" else -6)))
# ears
sphere("Ear_L", (-0.218, 0, 0.91), (0.035, 0.025, 0.05), SKIN)
sphere("Ear_R", (0.218, 0, 0.91), (0.035, 0.025, 0.05), SKIN)
# nose
sphere("Nose", (0, -0.213, 0.875), (0.028, 0.025, 0.022), SKIN_DARK)
# mouth / smile
sphere("Mouth", (0, -0.205, 0.805), (0.062, 0.018, 0.030), RED)
sphere("Tongue", (0, -0.221, 0.798), (0.034, 0.010, 0.014), mat("Tongue", (0.85, 0.42, 0.45)))
# three freckles on HER left cheek (+X in this front-facing convention)
for i, (x, z) in enumerate(((0.118, 0.842), (0.135, 0.828), (0.112, 0.817))):
    sphere(f"Freckle_{i + 1}", (x, -0.185, z), (0.008, 0.005, 0.008), FRECKLE, segments=12, rings=8)

# ---------- hair ----------
# cap + chunky wavy bob; separate clumps keep it editable
sphere("Hair_Cap", (0, 0.018, 0.945), (0.245, 0.225, 0.250), HAIR)
for i, (x, y, z, s) in enumerate((
        (-0.225, -0.02, 0.83, 0.085), (0.225, -0.02, 0.83, 0.085),
        (-0.19, 0.05, 0.74, 0.085), (0.19, 0.05, 0.74, 0.085),
        (-0.13, -0.15, 1.03, 0.075), (-0.04, -0.15, 1.05, 0.070),
        (0.06, -0.15, 1.045, 0.072), (0.15, -0.13, 1.01, 0.070),
        (-0.20, 0.10, 0.94, 0.075), (0.20, 0.10, 0.94, 0.075),
        (0.0, 0.17, 0.85, 0.10), (-0.10, 0.16, 0.78, 0.075),
        (0.10, 0.16, 0.78, 0.075))):
    sphere(f"Hair_Clump_{i + 1}", (x, y, z), (s * 1.05, s * 0.65, s * 1.35), HAIR)

# star clip: real extruded 5-point star mesh
verts2d = []
for i in range(10):
    r = 0.055 if i % 2 == 0 else 0.023
    a = math.pi / 2 + i * math.pi / 5
    verts2d.append((r * math.cos(a), r * math.sin(a)))
verts = [(x, 0.0, z) for x, z in verts2d]
faces = []
for i in range(10):
    faces.append((i, (i + 1) % 10, 10 + (i + 1) % 10, 10 + i))
faces.append(tuple(range(10)))
faces.append(tuple(range(10, 20)))
mesh = bpy.data.meshes.new("StarClipMesh")
mesh.from_pydata(verts + [(x, 0.02, z) for x, z in verts2d], [], faces)
mesh.update()
star = bpy.data.objects.new("Star_Clip", mesh)
scene.collection.objects.link(star)
star.location = (-0.185, -0.205, 1.035)
star.rotation_euler = (0, 0, math.radians(-14))
star.scale = (1.25, 1.25, 1.25)
track(star, YELLOW)
# teeth behind the smile
sphere("Teeth", (0, -0.219, 0.812), (0.042, 0.010, 0.013), WHITE)

# kite print on shirt front
kite_v = [(0, 0, 0.045), (0.055, 0, 0), (0, 0, -0.055), (-0.055, 0, 0)]
kite_f = [(0, 1, 2, 3)]
kmesh = bpy.data.meshes.new("KitePrintMesh")
kmesh.from_pydata(kite_v, [], kite_f)
kmesh.update()
kite = bpy.data.objects.new("Shirt_Kite_Print", kmesh)
scene.collection.objects.link(kite)
kite.location = (0, -0.118, 0.56)
track(kite, YELLOW)

# ---------- UV + origin ----------
for obj in list(COL.objects):
    if obj.type == "MESH":
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
        obj.select_set(False)

# ---------- export ----------
for obj in bpy.context.selected_objects:
    obj.select_set(False)
for obj in COL.objects:
    obj.select_set(True)
blend_path = OUT / "aden-character-v1.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
glb_path = OUT / "aden-character-v1.glb"
bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB",
                          use_selection=True, export_apply=True)

# ---------- stats ----------
stats = {"objects": [], "totals": {"objects": 0, "vertices": 0, "faces": 0}}
mats = set()
for obj in COL.objects:
    if obj.type != "MESH":
        continue
    verts = len(obj.data.vertices)
    faces = len(obj.data.polygons)
    stats["objects"].append({"name": obj.name, "vertices": verts, "faces": faces,
                             "materials": [m.name for m in obj.data.materials]})
    stats["totals"]["objects"] += 1
    stats["totals"]["vertices"] += verts
    stats["totals"]["faces"] += faces
    mats.update(m.name for m in obj.data.materials)
stats["materials"] = sorted(mats)
stats["dimensions_m"] = [round(v, 3) for v in bpy.context.object.dimensions] if bpy.context.object else None
(OUT / "model-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")

# ---------- previews ----------
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
floor = bpy.context.object
floor.name = "QA_Floor"
track(floor, mat("QA_Floor", (0.78, 0.78, 0.78)), smooth=False)

cam_data = bpy.data.cameras.new("QA_Camera")
cam = bpy.data.objects.new("QA_Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.type = "ORTHO"


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


views = {
    "front": ((0, -3.0, 0.52), 1.18, (0, 0, 0.52)),
    "back": ((0, 3.0, 0.52), 1.18, (0, 0, 0.52)),
    "left": ((-3.0, 0, 0.52), 1.18, (0, 0, 0.52)),
    "right": ((3.0, 0, 0.52), 1.18, (0, 0, 0.52)),
    "threequarter": ((-2.1, -2.1, 0.75), 1.18, (0, 0, 0.52)),
    "face_close": ((0, -2.0, 0.93), 0.52, (0, 0, 0.93)),
}
scene.render.image_settings.file_format = "PNG"
for name, (loc, scale, target) in views.items():
    cam.location = loc
    cam_data.ortho_scale = scale
    look_at(cam, target)
    scene.render.filepath = str(OUT / "previews" / f"{name}.png")
    bpy.ops.render.render(write_still=True)

print("BLENDER_BUILD_OK", json.dumps({"blend": str(blend_path), "glb": str(glb_path),
                                      "objects": stats["totals"]["objects"],
                                      "vertices": stats["totals"]["vertices"],
                                      "faces": stats["totals"]["faces"]}))
