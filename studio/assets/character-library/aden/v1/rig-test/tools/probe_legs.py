"""Read-only probe: does the TEST_POSE actually move the legs?"""
import math
import bpy
from mathutils import Vector, Quaternion

DEG = math.radians
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
scene = bpy.context.scene


def centres(names):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    out = {}
    for name in names:
        obj = bpy.data.objects[name].evaluated_get(dg)
        mesh = obj.to_mesh()
        mw = obj.matrix_world
        pts = [mw @ v.co for v in mesh.vertices]
        out[name] = [(sum(p[i] for p in pts) / len(pts)) for i in range(3)]
        if name.startswith("Sole"):
            out[name + "_minz"] = min(p.z for p in pts)
        obj.to_mesh_clear()
    return out


NAMES = ["Thigh_R", "Shin_R", "Sole_R", "Arm_L", "Hand_L", "Head"]
for pb in arm.pose.bones:
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
    pb.location = Vector((0, 0, 0))
bpy.context.view_layer.update()
before = centres(NAMES)


def pose(bone, axis, deg):
    pb = arm.pose.bones[bone]
    inv = pb.bone.matrix_local.to_3x3().inverted()
    pb.rotation_quaternion = Quaternion((inv @ Vector(axis)).normalized(), DEG(deg))


pose("thigh.R", (1, 0, 0), -32)
pose("shin.R", (1, 0, 0), 48)
pose("foot.R", (1, 0, 0), -12)
pose("upper_arm.L", (0, 1, 0), 62)
bpy.context.view_layer.update()
after = centres(NAMES)

for key in before:
    b = before[key]
    a = after[key]
    if isinstance(b, float):
        print("%-14s %.4f -> %.4f" % (key, b, a))
    else:
        print("%-14s (%7.4f,%7.4f,%7.4f) -> (%7.4f,%7.4f,%7.4f)  delta=%s"
              % (key, b[0], b[1], b[2], a[0], a[1], a[2],
                 [round(a[i] - b[i], 4) for i in range(3)]))
print("chain: %s" % [(b.name, b.parent.name if b.parent else None, b.use_connect)
                     for b in arm.data.bones if b.name in ("thigh.R", "shin.R", "foot.R")])
