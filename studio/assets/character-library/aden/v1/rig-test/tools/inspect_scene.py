"""Read-only scene inspection for the Aden rig test.

Usage:
    blender -b model.blend --factory-startup --python inspect_scene.py -- <report.json>

Writes a JSON report and prints a human readable summary. It never modifies
the .blend file and never saves.
"""
import json
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv
    if "--" in argv:
        tail = argv[argv.index("--") + 1:]
        if tail:
            return tail[0]
    return None


def world_bounds(obj):
    mw = obj.matrix_world
    pts = [mw @ Vector(corner) for corner in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    mn = [min(xs), min(ys), min(zs)]
    mx = [max(xs), max(ys), max(zs)]
    center = [(mn[i] + mx[i]) * 0.5 for i in range(3)]
    size = [mx[i] - mn[i] for i in range(3)]
    return {"min": mn, "max": mx, "center": center, "size": size}


def describe(obj):
    info = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "parent_type": obj.parent_type,
        "location": list(obj.location),
        "rotation_euler_deg": [round(v * 57.29577951308232, 4) for v in obj.rotation_euler],
        "scale": list(obj.scale),
        "dimensions": list(obj.dimensions),
        "hide_viewport": obj.hide_viewport,
        "hide_render": obj.hide_render,
        "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
        "vertex_groups": [g.name for g in obj.vertex_groups],
        "constraints": [c.type for c in obj.constraints],
    }
    if obj.type == "MESH":
        me = obj.data
        info.update({
            "data_name": me.name,
            "vertices": len(me.vertices),
            "edges": len(me.edges),
            "faces": len(me.polygons),
            "materials": [ms.material.name if ms.material else None for ms in obj.material_slots],
            "shape_keys": [k.name for k in me.shape_keys.key_blocks] if me.shape_keys else [],
            "users": me.users,
        })
        info["world"] = world_bounds(obj)
    elif obj.type == "ARMATURE":
        info["bones"] = [b.name for b in obj.data.bones]
    return info


def main():
    report_path = parse_args()

    objects = [describe(o) for o in bpy.data.objects]
    objects.sort(key=lambda d: d["name"])

    meshes = [o for o in objects if o["type"] == "MESH"]
    report = {
        "blender_version": bpy.app.version_string,
        "filepath": bpy.data.filepath,
        "scene": bpy.context.scene.name,
        "scene_objects": [o.name for o in bpy.context.scene.objects],
        "collections": [c.name for c in bpy.data.collections],
        "object_count": len(objects),
        "mesh_object_count": len(meshes),
        "totals": {
            "vertices": sum(o.get("vertices", 0) for o in meshes),
            "edges": sum(o.get("edges", 0) for o in meshes),
            "faces": sum(o.get("faces", 0) for o in meshes),
        },
        "armatures": [o["name"] for o in objects if o["type"] == "ARMATURE"],
        "actions": [a.name for a in bpy.data.actions],
        "existing_shape_key_objects": [o["name"] for o in meshes if o.get("shape_keys")],
        "materials": sorted({m.name for m in bpy.data.materials}),
        "unit_system": bpy.context.scene.unit_settings.system,
        "unit_scale": bpy.context.scene.unit_settings.scale_length,
        "render_engine": bpy.context.scene.render.engine,
        "world_objects": [o for o in objects if o["type"] == "MESH" and "world" in o],
        "objects": objects,
    }

    # overall character bounds from every mesh object
    mins = [1e9, 1e9, 1e9]
    maxs = [-1e9, -1e9, -1e9]
    for o in report["world_objects"]:
        for i in range(3):
            mins[i] = min(mins[i], o["world"]["min"][i])
            maxs[i] = max(maxs[i], o["world"]["max"][i])
    report["character_bounds"] = {
        "min": mins,
        "max": maxs,
        "size": [maxs[i] - mins[i] for i in range(3)],
        "height": maxs[2] - mins[2],
    }

    print("=" * 78)
    print("BLENDER %s | file=%s" % (bpy.app.version_string, bpy.data.filepath))
    print("objects=%d  mesh_objects=%d  verts=%d  edges=%d  faces=%d" % (
        report["object_count"], report["mesh_object_count"],
        report["totals"]["vertices"], report["totals"]["edges"], report["totals"]["faces"]))
    print("armatures=%s  actions=%s  shapekey_objects=%s" % (
        report["armatures"], report["actions"], report["existing_shape_key_objects"]))
    print("character bounds min=%s max=%s height=%.4f" % (
        [round(v, 4) for v in mins], [round(v, 4) for v in maxs],
        report["character_bounds"]["height"]))
    print("-" * 78)
    print("%-22s %6s %6s  %-22s %s" % ("OBJECT", "VERTS", "FACES", "CENTER (x,y,z)", "SIZE (x,y,z)"))
    for o in meshes:
        w = o["world"]
        print("%-22s %6d %6d  (%7.4f,%7.4f,%7.4f)  (%.4f,%.4f,%.4f)" % (
            o["name"], o["vertices"], o["faces"],
            w["center"][0], w["center"][1], w["center"][2],
            w["size"][0], w["size"][1], w["size"][2]))
    print("=" * 78)

    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
        print("REPORT_WRITTEN: %s" % report_path)


main()
