from pathlib import Path

p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\worker_mind.py")
t = p.read_text(encoding="utf-8")

old1 = "        set_goal(mind, ctx)\n        plan_steps(mind, ctx)\n        save(runtime, mind)"
new1 = (
    "        set_goal(mind, ctx)\n        plan_steps(mind, ctx)\n        calibrate(mind)\n"
    "        to_plan_queue(runtime, mind)\n        save(runtime, mind)"
)
old2 = '    with open(runtime / "minds" / "thoughts.jsonl", "a", encoding="utf-8") as fh:'
new2 = (
    "    share_department_brain(runtime, departments)\n"
    '    with open(runtime / "minds" / "thoughts.jsonl", "a", encoding="utf-8") as fh:'
)

changed = []
if old1 in t:
    t = t.replace(old1, new1, 1)
    changed.append("calibrate+plan_queue")
if old2 in t:
    t = t.replace(old2, new2, 1)
    changed.append("share_department_brain")

p.write_text(t, encoding="utf-8")
print("bağlanan:", changed or "hiçbiri")
