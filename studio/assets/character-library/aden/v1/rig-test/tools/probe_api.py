"""Environment/API probe for Blender 4.5 rig build (read-only, no saving)."""
import bpy
import sys

print("=" * 70)
print("BLENDER:", bpy.app.version_string)
print("ffmpeg build option:", getattr(bpy.app.build_options, "codec_ffmpeg", "n/a"))

act = bpy.data.actions.new("__probe__")
print("action has 'slots':", hasattr(act, "slots"))
if hasattr(act, "slots"):
    print("slots dir:", [n for n in dir(act.slots) if not n.startswith("_")])
    try:
        slot = act.slots.new(id_type="OBJECT", name="probe")
        print("slot created:", slot, "identifier:", slot.identifier)
    except Exception as exc:
        print("slot new failed:", exc)
print("action has layers:", hasattr(act, "layers"))
print("animation_data attrs:", [n for n in dir(bpy.types.AnimData) if "slot" in n.lower() or "action" in n.lower()])

try:
    print("render engines:", [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items])
except Exception as exc:
    print("engine enum failed:", exc)

print("gltf export op:", hasattr(bpy.ops.export_scene, "gltf"))
import addon_utils
print("io_scene_gltf2 enabled:", addon_utils.check("io_scene_gltf2"))

shading = bpy.context.scene.display.shading
print("workbench shading attrs:", [n for n in ("light", "color_type", "show_shadows", "show_cavity", "cavity_type", "studio_light") if hasattr(shading, n)])
try:
    print("ffmpeg formats:", [i.identifier for i in bpy.types.FFmpegSettings.bl_rna.properties["format"].enum_items])
    print("ffmpeg codecs:", [i.identifier for i in bpy.types.FFmpegSettings.bl_rna.properties["codec"].enum_items])
except Exception as exc:
    print("ffmpeg enum failed:", exc)

for name in ("Eyelid_L", "Mouth", "Teeth", "Tongue", "Head", "Brow_L", "Eye_White_L"):
    ob = bpy.data.objects.get(name)
    if ob is None:
        print("MISSING OBJECT:", name)
        continue
    mats = [ms.material.name if ms.material else None for ms in ob.material_slots]
    vg = [g.name for g in ob.vertex_groups]
    print("%-12s mats=%s groups=%s keys=%s" % (
        name, mats, vg, list(ob.data.shape_keys.key_blocks.keys()) if ob.data.shape_keys else []))

print("materials viewport colors:")
for m in bpy.data.materials:
    print("   %-22s diffuse=%s use_nodes=%s" % (m.name, tuple(round(c, 3) for c in m.diffuse_color), m.use_nodes))

scn = bpy.context.scene
print("render engine:", scn.render.engine, "fps:", scn.render.fps, "res:", scn.render.resolution_x, scn.render.resolution_y)
print("existing cameras:", [o.name for o in bpy.data.objects if o.type == "CAMERA"])
print("existing lights:", [o.name for o in bpy.data.objects if o.type == "LIGHT"])
print("scene collection children:", [c.name for c in scn.collection.children])
print("=" * 70)
