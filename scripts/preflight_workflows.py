#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.request import urlopen

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8188"
WORKFLOW_ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/opt/ltx2/workflows")

with urlopen(f"{BASE_URL}/object_info", timeout=30) as r:
    object_info = json.load(r)

errors = []
checked = 0
for path in sorted(WORKFLOW_ROOT.glob("*.json")):
    try:
        workflow = json.loads(path.read_text())
    except Exception as exc:
        errors.append(f"{path.name}: invalid JSON: {exc}")
        continue

    # API-format workflows are dicts of node_id -> node definition.
    if not isinstance(workflow, dict) or not workflow:
        continue

    api_nodes = {
        node_id: node
        for node_id, node in workflow.items()
        if isinstance(node, dict) and "class_type" in node and isinstance(node.get("inputs"), dict)
    }
    if not api_nodes:
        continue

    checked += 1
    for node_id, node in api_nodes.items():
        class_type = node.get("class_type")
        inputs = node.get("inputs") or {}
        schema = object_info.get(class_type)
        if schema is None:
            errors.append(f"{path.name} node {node_id}: class_type {class_type!r} not registered")
            continue

        required = set(((schema.get("input") or {}).get("required") or {}).keys())
        missing = sorted(required - set(inputs.keys()))
        if missing:
            errors.append(
                f"{path.name} node {node_id} ({class_type}): missing required inputs {missing}"
            )

    # Critical invariant from the RunPod incident: native LTX text encoder must be wired
    # with every live required field and keep device=default unless deliberately changed.
    loaders = [n for n in api_nodes.values() if n.get("class_type") == "LTXAVTextEncoderLoader"]
    for loader in loaders:
        if (loader.get("inputs") or {}).get("device") != "default":
            errors.append(f"{path.name}: LTXAVTextEncoderLoader device must be 'default'")

if checked == 0:
    errors.append(f"No API-format workflows found under {WORKFLOW_ROOT}")

if errors:
    print("WORKFLOW PREFLIGHT FAILED")
    for err in errors:
        print(f" - {err}")
    raise SystemExit(1)

print(f"WORKFLOW PREFLIGHT PASSED: {checked} API workflow(s) validated against live ComfyUI schema")
