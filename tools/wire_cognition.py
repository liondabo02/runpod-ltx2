from pathlib import Path

BASE = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos")
changes = []

# 1) worker_mind: öngörü + mantık katmanı tick içinde çalışsın
wm = BASE / "worker_mind.py"
t = wm.read_text(encoding="utf-8")
if "cognition" not in t:
    t = t.replace("from . import sovereign", "from . import cognition, sovereign", 1)
    t = t.replace(
        "        sovereign.embed(mind)\n",
        "        sovereign.embed(mind)\n"
        "        forecast = cognition.predict(ctx, mind)\n"
        "        mind.self_model[\"reasoning\"] = cognition.reason(\n"
        "            str((mind.self_model or {}).get(\"goal\") or \"\"),\n"
        "            {\"blocked\": ctx.get(\"blocked\", 0), \"pending\": ctx.get(\"pending\", 0),\n"
        "             \"rate\": mind.success_rate},\n"
        "        )\n"
        "        mind.self_model[\"forecast\"] = forecast\n",
        1,
    )
    changes.append("worker_mind: cognition")

# 2) commune: konuşmadan öğrenme
cm = BASE / "commune.py"
c = cm.read_text(encoding="utf-8")
if "cognition" not in c:
    c = c.replace("from .worker_mind import load, save", "from . import cognition\nfrom .worker_mind import load, save", 1)
    c = c.replace(
        "            for mind, text, kind in ((asker_mind, question, \"ask\"), (responder_mind, answer, \"answer\")):",
        "            cognition.learn_from(runtime, responder, dep_id, cognition.extract_lesson(\n"
        "                {\"from\": asker, \"body\": question}), source=\"soru\")\n"
        "            cognition.learn_from(runtime, asker, dep_id, cognition.extract_lesson(\n"
        "                {\"from\": responder, \"body\": answer}), source=\"cevap\")\n"
        "            for mind, text, kind in ((asker_mind, question, \"ask\"), (responder_mind, answer, \"answer\")):",
        1,
    )
    changes.append("commune: learned")

wm.write_text(t, encoding="utf-8")
cm.write_text(c, encoding="utf-8")
print("değişen:", changes)
