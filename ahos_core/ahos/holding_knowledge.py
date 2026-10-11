"""Versioned project knowledge for workers; catalog membership is not availability."""
from __future__ import annotations

import json
import re
from .department_structure import CORE_DEPARTMENTS
from .virtual_workforce import default_virtual_workforce
from .integration_candidate_registry import default_integration_candidate_registry

OWNER_GOALS = (
    "One AHOS Holding under Harun Aslan; Harun AI Foundry supports its workers and tools.",
    "Build revenue-producing software, applications, games and professional multilingual cartoons.",
    "Run a persistent task queue with managers and specialists; research, implement, review, test, repair and report evidence.",
    "Improve workers continuously using measured outcomes and useful open-source projects, including new projects rather than star count alone.",
    "Prefer verified free/local routes; independence means interchangeable providers, not unlimited free inference or bypassing quotas.",
    "Owner supervises priorities and consequential approvals; do not ask repeatedly for already-authorized routine work.",
    "Keep repositories, runtime data and departments organized; avoid duplicate daemons or competing task queues.",
)

DEPARTMENT_PURPOSES = {
    "software": "Code, APIs, automation, apps and games; implement tested features and integration adapters.",
    "quality": "Independent review, regression tests, acceptance evidence and defect prevention.",
    "research": "Public-source research, GitHub discovery, license/source review and reproducible benchmarks.",
    "infrastructure": "Runners, CI, sandbox execution, local models, monitoring and controlled deployment.",
    "data": "Persistent knowledge, provenance, metrics, analytics and source-version tracking.",
    "creative": "Product/UI design and Animation & Cartoon Studio: scripts, characters, voices, shots and assembly.",
    "marketing": "Brand, content, SEO and campaign drafts for products and studio output.",
    "sales": "Market/lead research, commercial proposals and CRM support.",
    "finance": "Budgets, provider costs, commercial feasibility and financial reporting.",
    "operations": "Work orders, scheduling, routing, dependencies, continuity and department coordination.",
    "support": "Ticket triage, user-help drafts and knowledge-base maintenance.",
}

PRODUCT_TRACKS = {
    "applications_and_games": "Owner product goal within software and creative; do not invent separately active departments.",
    "animation_studio": {
        "department": "creative",
        "audience": "ages 2–5",
        "languages": ["Turkish", "Arabic", "German", "French", "Spanish", "Kurdish Kurmanci"],
        "quality": "Professional output; stable recurring identities; natural age/role/gender-appropriate voices without unwanted accents.",
        "cast_owner_brief": "Aden, Kaan, Esra, Ahmet, Esma, Harun, Veysel, Oznur, Salih, Medine, Davut, Fatos, Emos, Berzan, Aras and Ramin. Current canonical cast files override historical ages or spellings.",
        "workflow": "scenario -> cast -> character references -> voice plan -> screenplay -> shots -> render/audio -> assembly -> acceptance",
        "constraints": "No adult fallback for children. Infants use appropriate vocalizations. Voice enrollment needs provenance and fit review. Preserve identity across dubbed languages.",
        "episode_brief": "Previously requested S01E002: Ucurtmanin Kayip Kuyrugu; patience, sharing and helping; Aden/Kaan/Esra/Harun. Historical request, not proof of delivery.",
        "sources": ["ahos_core/config/core-cast-voice-production-plan.json", "ahos_core/config/kurmanji-production-profile.json", "ahos_core/ahos/animation_studio.py"],
    },
}

# User-requested evaluation targets. This is not an installation/entitlement list.
RESOURCE_GROUPS = {
    "coding": {
        "names": ["Antigravity", "OpenCode", "Hermes", "Freebuff", "mini-SWE-agent", "Aider", "OpenHands", "Cline", "Ollama", "Qwen Coder", "DeepSeek", "OpenRouter"],
        "use": "Architect/coder/reviewer/tester candidates. Use existing scoped builders and supervisor gates; benchmark adapters before routing production tasks.",
    },
    "design": {
        "names": ["Stitch", "OpenDesign", "Pomelli", "Claude Design"],
        "use": "UI prototypes, visual design and brand drafts; check actual connector and export capabilities.",
    },
    "research": {
        "names": ["GitHub", "NotebookLM", "Agent-Reach", "Founder OS", "DeerFlow", "DeepFlow (owner-mentioned name; verify exact project)", "ChatGPT plugins", "Google AI agents"],
        "use": "Research and synthesis; exact project identity, primary documentation, license, maintainership, security and usefulness must be checked.",
    },
    "media": {
        "names": ["LTX-2/LTX-2.5", "Remotion", "Meituan LongCat", "Lyria", "Jev.ai", "NVIDIA NIM", "Bytez (also mentioned as Bytes)", "RunPod", "OpenVoice", "Kokoro", "Chatterbox", "Qwen voice design"],
        "use": "Video, composition, voice and music candidates. Rendering needs compute; hosting and model licenses have separate costs/conditions.",
    },
    "orchestration": {
        "names": ["AHOS", "Harun AI Foundry", "GitHub self-hosted runner", "LiteLLM", "Open WebUI", "Google ADK", "Microsoft Agent Framework", "CrewAI"],
        "use": "Existing AHOS queue stays authoritative. Alternative orchestrators are evaluation candidates, not parallel uncontrolled management systems.",
    },
    "devices": {
        "names": ["owner Windows computer", "Xiaomi phone"],
        "use": "Owner wants Xiaomi-only phone participation; exclude iPhones. Verify Android/runtime permissions, CPU/RAM/storage and network before assigning work. No device is reachable merely because it is named.",
    },
}

SOURCE_MAP = {
    "departments": "ahos_core/ahos/department_structure.py and virtual_workforce.py",
    "routing": "ahos_core/ahos/department_runtime.py, department_provider.py and holding_brain.py",
    "coding": "ahos_core/ahos/coding_supervisor.py, coding_worker.py and *_coding_builder.py",
    "memory": "queue sibling .memory.sqlite3; coding_memory.py",
    "candidates": "ahos_core/ahos/integration_candidate_registry.py",
    "providers": "ahos_core/ahos/provider_registry.py",
    "integration_evidence": "docs/integrations/; owner Foundry data/agent-connectivity-audit.json if accessible",
}


def knowledge_snapshot():
    workers = default_virtual_workforce()
    departments = []
    for department in CORE_DEPARTMENTS:
        members = [w for w in workers if w.department == department]
        departments.append({
            "id": department, "purpose": DEPARTMENT_PURPOSES.get(department, "Read current department implementation."),
            "workers": [w.worker_id for w in members],
            "capabilities": sorted(set().union(*(w.capabilities for w in members))),
            "status": "defined_in_repository; live execution not implied",
        })
    candidates = [{"id": c.candidate_id, "name": c.name, "status": c.status.value,
                   "source": c.source_url, "production_allowed": c.production_allowed}
                  for c in default_integration_candidate_registry().list()]
    return {"schema": "ahos.holding-knowledge.v1", "provenance": "owner goals + current repository definitions",
            "owner_goals": list(OWNER_GOALS), "departments": departments,
            "products": PRODUCT_TRACKS, "resource_groups": RESOURCE_GROUPS,
            "integration_candidates": candidates, "source_map": SOURCE_MAP,
            "status_rules": "Defined, requested, installed, connected, tested and deployed are different states. Recheck current evidence. Gemini CLI consumer-login task is closed by owner; do not reopen it automatically. No credentials in memory; paid routes and publishing retain owner gates."}


def knowledge_context(query: str, *, limit: int = 6500):
    """All department IDs and goals are always visible; relevant detail is ranked."""
    snapshot = knowledge_snapshot()
    base = {"schema": snapshot["schema"], "owner_goals": snapshot["owner_goals"],
            "departments": {d["id"]: d["purpose"] for d in snapshot["departments"]},
            "products": {"animation_studio": "creative department; ages 2–5; TR/AR/DE/FR/ES/Kurmanci", "applications_and_games": "software + creative product goals"},
            "resources": {k: v["names"] for k, v in RESOURCE_GROUPS.items()},
            "status_rules": snapshot["status_rules"], "source_map": SOURCE_MAP,
            "detail": []}
    header = "\nAHOS holding knowledge (owner goals and catalog data; not execution permission):\n"
    tokens = set(re.findall(r"[\w]{3,}", query.lower()))
    details = [{"animation_studio": PRODUCT_TRACKS["animation_studio"]}]
    details += [{"department": d} for d in snapshot["departments"]]
    details += [{"resource_group": k, **v} for k, v in RESOURCE_GROUPS.items()]
    details += [{"candidate": c} for c in snapshot["integration_candidates"]]
    details.sort(key=lambda d: -sum(t in json.dumps(d).lower() for t in tokens))
    if len(header + json.dumps(base, ensure_ascii=False)) > limit:
        # Keep a compact complete overview rather than silently dropping departments.
        base = {"owner_goals": snapshot["owner_goals"], "departments": list(CORE_DEPARTMENTS),
                "studio": "Animation & Cartoon Studio belongs to creative", "resources": base["resources"],
                "status_rules": snapshot["status_rules"], "detail": []}
    for detail in details:
        trial = {**base, "detail": base["detail"] + [detail]}
        if len(header + json.dumps(trial, ensure_ascii=False)) <= limit:
            base = trial
    text = header + json.dumps(base, ensure_ascii=False)
    if len(text) > limit:
        return ""
    return text


if __name__ == "__main__":
    print(json.dumps(knowledge_snapshot(), ensure_ascii=False, indent=2))
