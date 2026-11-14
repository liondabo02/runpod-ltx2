"""Reopen a rigged .blend and prove it really contains a usable rig.

    blender -b <rigged.blend> --factory-startup --python verify_rig.py -- <out.json>

Prints VERIFY_OK / VERIFY_FAILED so the backend can refuse a fake PASSED.
"""
import json
import os
import sys

import bpy

argv = sys.argv
out_path = argv[argv.index("--") + 1] if "--" in argv else None

arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
report = {
    "blender": bpy.app.version_string,
    "file": bpy.data.filepath,
    "armature": arm.name if arm else None,
    "bones": len(arm.data.bones) if arm else 0,
    "meshes": len(meshes),
    "vertices": sum(len(o.data.vertices) for o in meshes),
    "faces": sum(len(o.data.polygons) for o in meshes),
    "parented": sum(1 for o in meshes if arm and o.parent == arm),
    "with_armature_modifier": sum(
        1 for o in meshes if any(m.type == "ARMATURE" for m in o.modifiers)),
    "unweighted_vertices": 0,
    "shape_keys": sorted({b.name for o in meshes if o.data.shape_keys
                          for b in o.data.shape_keys.key_blocks if b.name != "Basis"}),
    "actions": sorted(a.name for a in bpy.data.actions),
    "bone_names": sorted(b.name for b in arm.data.bones) if arm else [],
}
for obj in meshes:
    index_to_name = {g.index: g.name for g in obj.vertex_groups}
    for vertex in obj.data.vertices:
        if sum(e.weight for e in vertex.groups if index_to_name.get(e.group)) <= 1e-4:
            report["unweighted_vertices"] += 1

problems = []
if not arm:
    problems.append("no armature")
if report["bones"] < 10:
    problems.append("too few bones: %d" % report["bones"])
if report["meshes"] < 5:
    problems.append("too few meshes: %d" % report["meshes"])
if report["vertices"] < 500:
    problems.append("too few vertices: %d" % report["vertices"])
if report["parented"] != report["meshes"]:
    problems.append("only %d/%d meshes parented" % (report["parented"], report["meshes"]))
if report["unweighted_vertices"] > 0:
    problems.append("%d unweighted vertices" % report["unweighted_vertices"])
if len(report["shape_keys"]) < 5:
    problems.append("shape keys: %d" % len(report["shape_keys"]))
if len(report["actions"]) < 3:
    problems.append("actions: %d" % len(report["actions"]))

report["status"] = "OK" if not problems else "FAILED"
report["problems"] = problems

if out_path:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

print("VERIFY_%s bones=%d meshes=%d verts=%d keys=%d actions=%d"
      % (report["status"], report["bones"], report["meshes"], report["vertices"],
         len(report["shape_keys"]), len(report["actions"])))
for problem in problems:
    print("  problem: %s" % problem)
sys.exit(0 if report["status"] == "OK" else 1)
