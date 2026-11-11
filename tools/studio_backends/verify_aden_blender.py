"""Reopen the saved Aden .blend in a fresh Blender process and report real mesh stats."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
blend = Path(args[args.index("--blend") + 1])
out = Path(args[args.index("--out") + 1])
bpy.ops.wm.open_mainfile(filepath=str(blend))
objects = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "QA_Floor"]
stats = {
    "opened_file": str(blend),
    "objects": len(objects),
    "vertices": sum(len(o.data.vertices) for o in objects),
    "faces": sum(len(o.data.polygons) for o in objects),
    "materials": sorted({m.name for o in objects for m in o.data.materials}),
    "object_names": sorted(o.name for o in objects),
    "dimensions_m": [round(v, 3) for v in objects[0].dimensions] if objects else None,
}
out.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("REOPEN_OK", json.dumps({k: stats[k] for k in ("objects", "vertices", "faces")}))
