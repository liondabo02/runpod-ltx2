"""AHOS Mesh Factory v0.1 — parametric, rig-ready humanoid generator.

Input : character spec (id, class, height, palette, style)
Output: .blend + .glb + manifest, with the exact part naming the Rig Factory expects.

This is a *technical* mesh generator (procedural primitives). It is NOT an identity
model: output is always TECHNICAL_ONLY / PENDING_IDENTITY_REVIEW unless a real
identity pipeline replaces it.

    blender -b --factory-startup --python mesh_factory.py -- \
        --spec specs/kaan.json --out out/kaan

Part contract (must match rig_factory.py):
  Head, Neck, Torso_Shirt, Shirt_Hem, Hips_Shorts, Shorts_Left/Right,
  Sleeve_L/R, Arm_L/R, Hand_L/R, Thigh_L/R, Shin_L/R, Shoe_Upper_L/R, Sole_L/R,
  Eye_White/Iris/Pupil/Glint_L/R, Eyelid_L/R, Brow_L/R, Mouth, Teeth, Tongue,
  Hair_Cap, Hair_Clump_1..4, Ear_L/R, Nose, Freckle_1..3, Star_Clip, Shirt_Kite_Print
"""
import hashlib
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

DEG = math.radians

# vertical proportions as fractions of total height (they overlap on purpose,
# exactly like the hand-built Aden v1 model)
PROFILES = {
    "infant":  {"head": 0.40, "neck": 0.05, "torso": 0.30, "leg": 0.27, "arm": 0.21,
                "width": 0.36, "depth": 0.28, "eye": 0.115},
    "toddler": {"head": 0.395, "neck": 0.05, "torso": 0.30, "leg": 0.31, "arm": 0.23,
                "width": 0.28, "depth": 0.22, "eye": 0.10},
    "child":   {"head": 0.26, "neck": 0.05, "torso": 0.32, "leg": 0.39, "arm": 0.27,
                "width": 0.24, "depth": 0.18, "eye": 0.085},
    "adult":   {"head": 0.19, "neck": 0.05, "torso": 0.33, "leg": 0.45, "arm": 0.32,
                "width": 0.23, "depth": 0.17, "eye": 0.075},
}

DEFAULT_PALETTE = {
    "skin": [0.86, 0.62, 0.47, 1.0],
    "skin_shadow": [0.72, 0.48, 0.36, 1.0],
    "shirt": [0.035, 0.16, 0.55, 1.0],
    "shorts": [0.035, 0.045, 0.09, 1.0],
    "shoe": [0.035, 0.16, 0.55, 1.0],
    "sole": [0.88, 0.82, 0.68, 1.0],
    "hair": [0.13, 0.065, 0.035, 1.0],
    "eye_white": [0.96, 0.96, 0.94, 1.0],
    "iris": [0.22, 0.10, 0.035, 1.0],
    "pupil": [0.01, 0.01, 0.01, 1.0],
    "mouth": [0.55, 0.16, 0.17, 1.0],
    "tongue": [0.85, 0.42, 0.45, 1.0],
    "star": [0.95, 0.68, 0.08, 1.0],
    "accent": [0.95, 0.68, 0.08, 1.0],
}


def log(msg):
    print("[MESH] %s" % (msg,), flush=True)


def parse_args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"spec": None, "out": None}
    i = 0
    while i < len(tail):
        if tail[i] in ("--spec", "--out") and i + 1 < len(tail):
            opts[tail[i].strip("-")] = tail[i + 1]
            i += 2
        else:
            i += 1
    return opts


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def material(name, rgba):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = tuple(rgba)
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = tuple(rgba)
        principled.inputs["Roughness"].default_value = 0.55
    return mat


def finish(obj, name, mat):
    obj.name = name
    obj.data.name = name + "_mesh"
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def sphere(name, center, radius, scale, mat, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings,
                                         radius=radius, location=center)
    obj = bpy.context.active_object
    obj.scale = scale
    return finish(obj, name, mat)


def cylinder(name, center, radius, depth, mat, vertices=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=depth, location=center)
    return finish(bpy.context.active_object, name, mat)


def cube(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.scale = size
    return finish(obj, name, mat)


# ---------------------------------------------------------------------------
# layout + part construction
# ---------------------------------------------------------------------------
def layout(height, profile):
    H = height
    foot = 0.035 * H
    leg = profile["leg"] * H
    shin = leg * 0.45
    thigh = leg * 0.55
    knee = foot + shin
    hip = knee + thigh
    torso = profile["torso"] * H
    torso_bottom = hip - 0.06 * H
    torso_top = torso_bottom + torso
    neck = profile["neck"] * H
    neck_bottom = torso_top - 0.03 * H
    neck_top = neck_bottom + neck
    head = profile["head"] * H
    head_bottom = neck_top - 0.04 * H
    head_top = head_bottom + head
    return {
        "H": H, "foot": foot, "leg": leg, "shin": shin, "thigh": thigh,
        "knee": knee, "hip": hip, "torso": torso, "torso_bottom": torso_bottom,
        "torso_top": torso_top, "neck": neck, "neck_bottom": neck_bottom,
        "neck_top": neck_top, "head": head, "head_bottom": head_bottom,
        "head_top": head_top, "head_c": (head_bottom + head_top) / 2.0,
        "half_w": profile["width"] * H / 2.0,
        "half_d": profile["depth"] * H / 2.0,
        "leg_x": 0.062 * H,
    }


def build_body(spec):
    p = PROFILES[spec.get("class", "toddler")]
    L = layout(float(spec["height_m"]), p)
    H = L["H"]
    pal = dict(DEFAULT_PALETTE)
    pal.update(spec.get("palette") or {})
    M = {key: material("MF_" + key, value) for key, value in pal.items()}
    parts = []

    # spine / body
    parts.append(sphere("Head", (0, 0, L["head_c"]), L["head"] * 0.5, (0.97, 0.92, 1.0), M["skin"]))
    parts.append(cylinder("Neck", (0, 0, (L["neck_bottom"] + L["neck_top"]) / 2),
                          0.055 * H, L["neck"] + 0.02 * H, M["skin"]))
    parts.append(sphere("Torso_Shirt", (0, 0, (L["torso_bottom"] + L["torso_top"]) / 2),
                        1.0, (L["half_w"], L["half_d"], L["torso"] * 0.52), M["shirt"]))
    parts.append(cylinder("Shirt_Hem", (0, 0, L["torso_bottom"] + 0.02 * H),
                          L["half_w"] * 0.95, 0.035 * H, M["shirt"]))
    parts.append(sphere("Hips_Shorts", (0, 0, L["hip"] - L["torso"] * 0.18), 1.0,
                        (L["half_w"] * 0.9, L["half_d"] * 0.9, L["torso"] * 0.30), M["shorts"]))

    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        parts.append(sphere("Shorts_" + side, (sign * L["leg_x"], 0, L["hip"] - L["torso"] * 0.28),
                            1.0, (L["half_w"] * 0.45, L["half_d"] * 0.75, L["leg"] * 0.18),
                            M["shorts"]))

    # legs + feet
    for side, sign in (("L", -1.0), ("R", 1.0)):
        x = sign * L["leg_x"]
        parts.append(sphere("Thigh_" + side, (x, 0, (L["knee"] + L["hip"]) / 2), 1.0,
                            (0.052 * H, 0.055 * H, L["thigh"] * 0.55), M["skin"]))
        parts.append(cylinder("Shin_" + side, (x, 0, (L["foot"] + L["knee"]) / 2),
                              0.036 * H, L["shin"], M["skin"]))
        parts.append(sphere("Shoe_Upper_" + side, (x, -0.018 * H, L["foot"] * 0.70), 1.0,
                            (0.055 * H, 0.085 * H, L["foot"] * 0.55), M["shoe"]))
        # the sole is a box of height 0.022*H: centre it at half its height so the
        # bottom face sits exactly on z=0 (the ground) for every character class
        parts.append(cube("Sole_" + side, (x, -0.020 * H, 0.011 * H),
                          (0.110 * H, 0.190 * H, 0.022 * H), M["sole"]))

    # arms
    arm_top = L["torso_top"] - 0.06 * H
    arm_len = p["arm"] * H
    arm_c = arm_top - arm_len / 2.0
    for side, sign in (("L", -1.0), ("R", 1.0)):
        x = sign * (L["half_w"] * 0.95)
        parts.append(cylinder("Sleeve_" + side, (x, 0, arm_top - 0.02 * H),
                              0.048 * H, 0.08 * H, M["shirt"]))
        parts.append(cylinder("Arm_" + side, (x, 0, arm_c), 0.032 * H, arm_len * 0.86, M["skin"]))
        parts.append(sphere("Hand_" + side, (x, 0, arm_top - arm_len - 0.01 * H),
                            0.048 * H, (1.0, 0.9, 1.1), M["skin"]))

    return parts, L, M


def build_face(spec, L, M):
    hd = L["head"]
    hc = L["head_c"]
    eye_scale = float(spec.get("eye_scale", 1.0))
    parts = []
    ex = 0.166 * hd
    eye_r = 0.115 * hd * eye_scale
    eye_y = -0.40 * hd
    eye_z = hc + 0.05 * hd

    for side, sign in (("L", -1.0), ("R", 1.0)):
        x = sign * ex
        parts.append(sphere("Eye_White_" + side, (x, eye_y, eye_z), eye_r,
                            (1.0, 0.55, 1.0), M["eye_white"], 16, 10))
        parts.append(sphere("Eye_Iris_" + side, (x, eye_y - 0.030 * hd, eye_z), eye_r * 0.62,
                            (1.0, 0.50, 1.0), M["iris"], 16, 10))
        parts.append(sphere("Eye_Pupil_" + side, (x, eye_y - 0.048 * hd, eye_z), eye_r * 0.34,
                            (1.0, 0.50, 1.0), M["pupil"], 14, 8))
        parts.append(sphere("Eye_Glint_" + side,
                            (x - 0.12 * eye_r, eye_y - 0.062 * hd, eye_z + 0.35 * eye_r),
                            eye_r * 0.14, (1.0, 1.0, 1.0), M["eye_white"], 10, 6))
        parts.append(sphere("Eyelid_" + side, (x, eye_y - 0.005 * hd, eye_z + 1.02 * eye_r),
                            eye_r * 1.15, (1.0, 0.30, 0.34), M["skin_shadow"], 16, 10))
        parts.append(cube("Brow_" + side, (x, eye_y + 0.02 * hd, eye_z + 1.55 * eye_r),
                          (0.16 * hd, 0.020 * hd, 0.012 * hd), M["hair"]))
        parts.append(sphere("Ear_" + side, (sign * 0.47 * hd, 0.0, hc), 0.075 * hd,
                            (0.60, 1.0, 1.0), M["skin"], 14, 8))

    mouth_z = hc - 0.16 * hd
    parts.append(sphere("Mouth", (0, -0.40 * hd, mouth_z), 0.075 * hd,
                        (1.0, 0.45, 0.55), M["mouth"], 16, 10))
    parts.append(sphere("Teeth", (0, -0.405 * hd, mouth_z + 0.018 * hd), 0.045 * hd,
                        (1.0, 0.35, 0.35), M["eye_white"], 14, 8))
    parts.append(sphere("Tongue", (0, -0.405 * hd, mouth_z - 0.014 * hd), 0.035 * hd,
                        (1.0, 0.40, 0.40), M["tongue"], 12, 8))
    parts.append(sphere("Nose", (0, -0.435 * hd, hc - 0.03 * hd), 0.045 * hd,
                        (1.0, 0.70, 0.70), M["skin"], 12, 8))

    for index, (dx, dz) in enumerate(((0.30, -0.10), (0.36, -0.14), (0.28, -0.17))):
        parts.append(sphere("Freckle_%d" % (index + 1), (dx * hd, -0.375 * hd, hc + dz * hd),
                            0.010 * hd, (1.0, 1.0, 1.0), M["hair"], 8, 5))

    parts.append(sphere("Hair_Cap", (0, 0.03 * hd, hc + 0.10 * hd), 0.50 * hd,
                        (1.03, 1.00, 0.92), M["hair"], 20, 12))
    for index, (ax, ay, az, radius) in enumerate((
            (0.00, 0.10, 0.42, 0.17), (-0.22, 0.02, 0.36, 0.15),
            (0.22, 0.02, 0.36, 0.15), (0.00, 0.24, 0.26, 0.16))):
        parts.append(sphere("Hair_Clump_%d" % (index + 1),
                            (ax * hd, ay * hd, hc + az * hd), radius * hd,
                            (1.0, 1.0, 1.0), M["hair"], 14, 8))
    parts.append(sphere("Star_Clip", (-0.40 * hd, -0.24 * hd, hc + 0.30 * hd), 0.055 * hd,
                        (1.0, 0.50, 1.0), M["star"], 10, 6))
    parts.append(cube("Shirt_Kite_Print",
                      (0, -L["half_d"] * 0.96,
                       L["torso_bottom"] + L["torso"] * 0.55),
                      (0.10 * L["H"], 0.006 * L["H"], 0.10 * L["H"]), M["accent"]))
    return parts


def main():
    opts = parse_args()
    if not opts["spec"]:
        raise SystemExit("--spec is required")
    spec_path = os.path.abspath(opts["spec"])
    with open(spec_path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    character_id = spec["character_id"]
    out_dir = os.path.abspath(opts["out"] or os.path.join("out", character_id))
    os.makedirs(out_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    body_parts, L, M = build_body(spec)
    face_parts = build_face(spec, L, M)
    parts = body_parts + face_parts
    log("%s: %d parts, height %.3f m, class=%s"
        % (character_id, len(parts), L["H"], spec.get("class")))

    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    totals = {"objects": len(meshes),
              "vertices": sum(len(o.data.vertices) for o in meshes),
              "faces": sum(len(o.data.polygons) for o in meshes)}

    stamp = time.strftime("%Y%m%d-%H%M%S")
    blend_path = os.path.join(out_dir, "%s-model.blend" % character_id)
    if os.path.exists(blend_path):
        blend_path = os.path.join(out_dir, "%s-model_%s.blend" % (character_id, stamp))
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    for obj in scene.objects:
        obj.select_set(obj.type == "MESH")
    glb_path = os.path.join(out_dir, "%s-model.glb" % character_id)
    if os.path.exists(glb_path):
        glb_path = os.path.join(out_dir, "%s-model_%s.glb" % (character_id, stamp))
    try:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB",
                                  use_selection=True, export_apply=True)
    except TypeError:
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB",
                                  use_selection=True)

    manifest = {
        "schema": "ahos.character-mesh.v1",
        "character_id": character_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "generator": "ahos-mesh-factory/mesh_factory.py v0.1",
        "blender": bpy.app.version_string,
        "spec": {"path": spec_path, "sha256": sha256(spec_path)},
        "class": spec.get("class"),
        "height_m": spec["height_m"],
        "layout": {key: (round(value, 4) if isinstance(value, float) else value)
                   for key, value in L.items()},
        "palette": {key: list(value) for key, value in (spec.get("palette") or {}).items()},
        "parts": sorted(obj.name for obj in meshes),
        "totals": totals,
        "outputs": {
            "blend": {"path": blend_path, "bytes": os.path.getsize(blend_path),
                      "sha256": sha256(blend_path)},
            "glb": {"path": glb_path, "bytes": os.path.getsize(glb_path),
                    "sha256": sha256(glb_path)},
        },
        "identity_status": "TECHNICAL_ONLY",
        "identity_note": "Procedural technical mesh for pipeline validation. "
                         "Not an owner-approved likeness; PRODUCTION_READY stays false.",
        "rig_ready": True,
        "rig_contract": "part names match ahos-rig-factory naming contract",
    }
    manifest_path = os.path.join(out_dir, "model-manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    log("blend: %s" % blend_path)
    log("glb  : %s" % glb_path)
    log("objects=%d vertices=%d faces=%d"
        % (totals["objects"], totals["vertices"], totals["faces"]))
    print("MESH_OK", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print("MESH_FAILED", flush=True)
        sys.exit(1)

