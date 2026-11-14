"""AHOS Scene Factory v0.1 - environment, lights and shot cameras (bpy script).

    blender -b <animated.blend> --factory-startup --python scene_factory.py -- \
        --out <dir> [--shots wide,medium,close]

Builds a reusable set: ground, backdrop, three-point lighting and one camera per
requested shot, sized from the character's own bounding box.
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

DEG = math.radians


def parse_args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"out": None, "shots": "wide,medium,close"}
    i = 0
    while i < len(tail):
        if tail[i] == "--out" and i + 1 < len(tail):
            opts["out"] = tail[i + 1]
            i += 2
        elif tail[i] == "--shots" and i + 1 < len(tail):
            opts["shots"] = tail[i + 1]
            i += 2
        else:
            i += 1
    return opts


def character_bounds():
    low = Vector((1e9, 1e9, 1e9))
    high = Vector((-1e9, -1e9, -1e9))
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.name.startswith("RIGTEST_"):
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            for axis in range(3):
                low[axis] = min(low[axis], point[axis])
                high[axis] = max(high[axis], point[axis])
    return low, high


def material(name, rgba, roughness=0.6):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = tuple(rgba)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = tuple(rgba)
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def add_plane(name, size, location, rgba, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rotation
    obj.data.materials.clear()
    obj.data.materials.append(material(name + "_mat", rgba, 0.85))
    return obj


def add_cube(name, size, location, rgba):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.scale = size
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(material(name + "_mat", rgba, 0.7))
    return obj


def add_light(name, location, energy, size=2.0):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.size = size
    lamp = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(lamp)
    lamp.location = location
    target = Vector((0.0, 0.0, 0.6))
    lamp.rotation_euler = (target - lamp.location).to_track_quat("-Z", "Y").to_euler()
    return lamp


def add_camera(name, preset, low, high):
    height = max(0.5, high.z - low.z)
    center = (low + high) * 0.5
    table = {"wide": (height * 1.45, 0.50, 26.0), "medium": (height * 0.85, 0.62, 22.0),
             "close": (height * 0.40, 0.80, 18.0)}
    frame_height, target_z, azimuth = table.get(preset, table["wide"])
    lens, sensor = 50.0, 36.0
    half = math.tan(math.atan((sensor * 9.0 / 16.0) / 2.0 / lens))
    distance = frame_height / (2.0 * half)
    target = Vector((center.x, center.y, low.z + target_z))
    direction = Vector((math.sin(DEG(azimuth)), -math.cos(DEG(azimuth)), 0.10)).normalized()
    data = bpy.data.cameras.new("CAM_" + preset)
    data.lens = lens
    cam = bpy.data.objects.new("CAM_" + preset, data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = target + direction * distance
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam


def main():
    opts = parse_args()
    out = os.path.abspath(opts["out"] or ".")
    os.makedirs(out, exist_ok=True)
    low, high = character_bounds()

    add_plane("SCENE_Ground", 8.0, (0.0, 0.0, 0.0), (0.16, 0.18, 0.22, 1.0))
    add_plane("SCENE_Backdrop", 8.0, (0.0, 2.6, 0.0), (0.10, 0.12, 0.16, 1.0), (DEG(90), 0.0, 0.0))
    add_cube("SCENE_PropA", (0.25, 0.25, 0.35), (-0.7, 0.6, 0.175), (0.30, 0.25, 0.20, 1.0))
    add_cube("SCENE_PropB", (0.18, 0.18, 0.55), (0.8, 0.7, 0.275), (0.22, 0.28, 0.24, 1.0))

    add_light("LIGHT_Key", (1.6, -2.0, 2.2), 320.0, 2.5)
    add_light("LIGHT_Fill", (-2.0, -1.2, 1.4), 120.0, 3.0)
    add_light("LIGHT_Rim", (0.0, 2.2, 2.0), 180.0, 2.0)

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs[0].default_value = (0.045, 0.055, 0.075, 1.0)

    cameras = {}
    for preset in [p.strip() for p in opts["shots"].split(",") if p.strip()]:
        cameras[preset] = add_camera(preset, preset, low, high).name

    scene = bpy.context.scene
    scene.camera = bpy.data.objects[cameras.get("wide", "CAM_wide")]
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = 24
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True

    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "scene"
    blend_path = os.path.join(out, stem + "-scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    for obj in scene.objects:
        obj.select_set(obj.type in {"MESH", "ARMATURE", "CAMERA", "LIGHT"})
    glb_path = os.path.join(out, stem + "-scene.glb")
    try:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB",
                                  use_selection=True, export_apply=True)
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=True)

    manifest = {"schema": "ahos.scene.v1", "cameras": cameras,
                "bounds": {"low": [round(v, 4) for v in low],
                           "high": [round(v, 4) for v in high]},
                "props": ["SCENE_PropA", "SCENE_PropB"],
                "lights": ["LIGHT_Key", "LIGHT_Fill", "LIGHT_Rim"],
                "blend": blend_path, "glb": glb_path}
    with open(os.path.join(out, "scene-manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    print("SCENE_OK cameras=%s" % ",".join(sorted(cameras)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

