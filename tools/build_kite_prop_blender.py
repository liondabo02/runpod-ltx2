"""Create a reusable, original six-strip AHOS kite as REAL Blender geometry.

Usage:
  blender --background --factory-startup --python tools/build_kite_prop_blender.py -- --output-dir PATH

This generates only a *proposed* prop; it does not change or approve the cast.
The output directory must be new or empty. No downloads, paid APIs or external media.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

try:
    import bpy
    from mathutils import Vector
except ImportError as exc:
    raise RuntimeError("Run this script through Blender, not system Python") from exc


STRIPS = [
    ("red", (0.90, 0.13, 0.13)),
    ("yellow", (1.00, 0.73, 0.12)),
    ("blue", (0.18, 0.42, 0.96)),
    ("green", (0.14, 0.72, 0.43)),
    ("orange", (1.00, 0.38, 0.12)),
    ("purple", (0.53, 0.25, 0.79)),
]
DESTINATIONS = {
    "red": "piknik örtüsü", "yellow": "piknik örtüsü", "blue": "piknik örtüsü",
    "green": "papatya yanındaki çimen", "orange": "papatya yanındaki çimen",
    "purple": "alçak çalı",
}


def material(name: str, rgb: tuple[float, float, float]):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.78
    return mat


def mesh_obj(name: str, points, faces, mat):
    data = bpy.data.meshes.new(name + "_Mesh")
    data.from_pydata(points, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def rod(name: str, a, b, mat):
    pa, pb = Vector(a), Vector(b)
    direction = pb - pa
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=0.022, depth=direction.length, location=(pa + pb) / 2.0
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return obj


def make_kite():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    names = []
    vivid = [
        material("kite_blue", (0.10, 0.51, 0.87)),
        material("kite_yellow", (1.00, 0.72, 0.12)),
        material("kite_pink", (0.98, 0.32, 0.48)),
        material("kite_teal", (0.10, 0.71, 0.63)),
    ]
    points = [(0, 0, 1.42), (-0.88, 0, 0.10), (0, 0, -1.12),
              (0.88, 0, 0.10), (0, 0, 0.13)]
    faces = [(4, 0, 1), (4, 1, 2), (4, 2, 3), (4, 3, 0)]
    obj = mesh_obj("AHOS_KITE_DIAMOND", points, faces, vivid[0])
    for mat in vivid[1:]:
        obj.data.materials.append(mat)
    for i, poly in enumerate(obj.data.polygons):
        poly.material_index = i
    obj["asset_id"] = "kite-six-strip-tail"
    obj["status"] = "PROPOSED_NOT_APPROVED"
    names.append(obj.name)
    brown = material("kite_bamboo", (0.61, 0.33, 0.11))
    names.append(rod("KITE_SPINE", (0, 0.035, 1.42),
                     (0, 0.035, -1.12), brown).name)
    names.append(rod("KITE_CROSSBAR", (-0.88, 0.035, 0.10),
                     (0.88, 0.035, 0.10), brown).name)
    for i, (color, rgb) in enumerate(STRIPS):
        mat = material("tail_" + color, rgb)
        points = []
        top = -1.11 - (i * 0.39)
        for j in range(7):
            t = j / 6
            x = 0.12 * math.sin(t * math.pi * 1.7 + i * 0.47)
            y = -0.014 - 0.065 * math.sin(t * math.pi * 2 + i)
            z = top - 0.43 * t
            half = 0.085 * (1 - 0.20 * t)
            points.extend([(x - half, y, z), (x + half, y, z)])
        faces = [(2*j, 2*j+1, 2*j+3, 2*j+2) for j in range(6)]
        obj = mesh_obj(f"KITE_TAIL_{i+1:02d}_{color.upper()}", points, faces, mat)
        obj["tail_strip_index"] = i + 1
        obj["color"] = color
        obj["landing"] = DESTINATIONS[color]
        obj["separable"] = True
        obj["status"] = "PROPOSED_NOT_APPROVED"
        solid = obj.modifiers.new("fabric_thickness", "SOLIDIFY")
        solid.thickness = 0.008
        names.append(obj.name)
    assert len([x for x in bpy.data.objects if x.name.startswith("KITE_TAIL_")]) == 6
    return names


def setup_preview():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    world = bpy.data.worlds.new("AHOS_Preview_World")
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.40, 0.59, 0.73, 1)
    world.node_tree.nodes.get("Background").inputs["Strength"].default_value = 0.9
    scene.world = world

    bpy.ops.object.camera_add(location=(3.2, -7.6, 0.20))
    camera = bpy.context.object
    camera.name = "PREVIEW_CAMERA_NOT_ASSET"
    direction = Vector((0, 0, -1.15)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 6.5
    scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(1.7, -3.5, 4))
    lamp = bpy.context.object
    lamp.name = "PREVIEW_LIGHT_NOT_ASSET"
    lamp.data.energy = 550
    lamp.data.shape = "DISK"
    lamp.data.size = 5


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true",
                        help="Recover proof for existing media without overwriting or rerendering")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    blend = output / "kite-six-strip-PROPOSED.blend"
    glb = output / "kite-six-strip-PROPOSED.glb"
    png = output / "kite-six-strip-preview.png"
    proof = output / "prop-proof.json"
    if proof.exists():
        raise FileExistsError(f"Existing QA proof must never be overwritten: {proof}")

    if args.verify_existing:
        if not all(p.is_file() for p in (blend, glb, png)):
            raise FileNotFoundError("Cannot recover partial media; .blend/.glb/.png required")
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        obj_names = [
            obj.name for obj in bpy.data.objects
            if obj.type == "MESH" and
            (obj.name == "AHOS_KITE_DIAMOND" or obj.name.startswith("KITE_"))
        ]
    else:
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"Protect existing production media: {output}")
        output.mkdir(parents=True, exist_ok=True)
        obj_names = make_kite()
        setup_preview()
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB",
                                  export_apply=True, export_cameras=False, export_lights=False)
        bpy.context.scene.render.filepath = str(png)
        bpy.ops.render.render(write_still=True)

    for i, (color, _) in enumerate(STRIPS, 1):
        obj = bpy.data.objects.get(f"KITE_TAIL_{i:02d}_{color.upper()}")
        if obj is None or obj.type != "MESH" or obj.get("color") != color:
            raise RuntimeError(f"Missing actual mesh or metadata for tail: {color}")
        if obj.get("landing") != DESTINATIONS[color]:
            raise RuntimeError(f"Incorrect story-continuity landing for {color}")
    if len(obj_names) != 9:
        raise RuntimeError(f"Expected 9 real mesh objects, found {len(obj_names)}")

    # Blender 5.2 saves compressed .blend files (Zstandard) whose header
    # contains BLENDER after the zstd frame prefix. Reopening above verifies
    # scene validity independently of this signature check.
    if b"BLENDER" not in blend.open("rb").read(32):
        raise RuntimeError("Blender file signature invalid")
    if not glb.read_bytes().startswith(b"glTF"):
        raise RuntimeError("GLB signature invalid")
    if not png.read_bytes().startswith(b"\x89PNG"):
        raise RuntimeError("Preview PNG signature invalid")

    outputs = {}
    for item in (blend, glb, png):
        outputs[item.name] = {"size": item.stat().st_size, "sha256": digest(item)}
    report = {
        "schema": "ahos.studio.prop-proof.v1",
        "asset_id": "kite-six-strip-tail",
        "status": "PROPOSED_3D_PROP_QA",
        "owner_approved": False,
        "blender_version": bpy.app.version_string,
        "mesh_objects": obj_names,
        "strip_count": 6,
        "colors": [entry[0] for entry in STRIPS],
        "landing_map": DESTINATIONS,
        "outputs": outputs,
        "note": "True 3D geometry and CPU-rendered preview; this is NOT an approved character or completed animation.",
    }
    (output / "prop-proof.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("AHOS_KITE_PROP_SUCCESS", json.dumps(
        {"blender": bpy.app.version_string, "mesh_count": len(obj_names),
         "strip_count": len(STRIPS), "output": str(output)}, ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
