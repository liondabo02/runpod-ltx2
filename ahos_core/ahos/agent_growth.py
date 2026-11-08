"""Auditable, evidence-based growth overlay for every rostered AHOS worker.

This module does NOT create consciousness, emotion, model weights, proven skill
improvement or privileged authority. It derives planning hints, calibrated
operational affect and peer-coaching suggestions from QA-backed SQLite records.
It never creates, changes, completes or cancels a mission.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from collections import defaultdict
from pathlib import Path

from .sovereign import DEFAULT_OWNER, ensure as ensure_owner

MAX_OBSERVATIONS = 24
MAX_LESSONS = 48
DEFAULT_WORKERS_PER_TICK = 9
MAX_MENTOR_NOTES_PER_TICK = 3
WORKER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _roster(runtime: Path, departments: list[dict] | None) -> list[tuple[str, str]]:
    if departments is None:
        book = runtime / "departments.json"
        try:
            payload = json.loads(book.read_text(encoding="utf-8"))
            departments = payload.get("departments", []) if isinstance(payload, dict) else payload
        except (OSError, ValueError, TypeError):
            return []
    roster: list[tuple[str, str]] = []
    seen: set[str] = set()
    for department in departments or []:
        if not isinstance(department, dict):
            continue
        dep = str(department.get("department_id") or "")
        for person in department.get("workers") or []:
            if not isinstance(person, dict):
                continue
            worker = str(person.get("worker_id") or "")
            if (not WORKER_ID_PATTERN.fullmatch(worker)
                    or not dep or worker in seen):
                continue
            roster.append((dep, worker))
            seen.add(worker)
    return roster


def _observed(runtime: Path, roster: list[tuple[str, str]]) -> tuple[dict, int] | None:
    """Read only completed, QA-verified steps or actual failed/blocked steps."""
    database = runtime / "company-service.db"
    if not database.is_file():
        return None
    wanted = {worker for _, worker in roster}
    records: dict[str, list[dict]] = defaultdict(list)
    pending = 0
    try:
        with sqlite3.connect("file:" + database.resolve().as_posix() + "?mode=ro",
                             uri=True, timeout=4) as conn:
            pending = int(conn.execute(
                "select count(*) from missions where status='pending'"
            ).fetchone()[0])
            # Bounded recent window. Historical evidence stays in the DB and
            # previously extracted growth lessons remain in the overlay.
            rows = conn.execute(
                "select mission_id, primary_department, status, updated_at, result_json "
                "from missions where status in ('completed','blocked','failed') "
                "and result_json is not null order by updated_at desc, rowid desc limit 3000"
            )
            for mission, department, status, updated_at, raw in rows:
                try:
                    result = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if not isinstance(result, dict):
                    continue
                delivery = result.get("delivery")
                verified = (isinstance(delivery, dict)
                            and delivery.get("verified") is True)
                steps = result.get("steps")
                if not isinstance(steps, list):
                    continue
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    worker = str(step.get("worker_id") or "")
                    if worker not in wanted or len(records[worker]) >= MAX_OBSERVATIONS:
                        continue
                    stage = str(step.get("stage") or "")
                    if (status == "completed" and verified
                            and stage == "completed"
                            and step.get("worker_summary") is not None
                            and step.get("qa_summary") is not None
                            and str(step.get("qa_worker_id") or "") != worker):
                        ok = True
                    elif (status in ("blocked", "failed")
                          and stage in ("blocked", "failed")
                          and str(step.get("reason") or "")):
                        ok = False
                    else:
                        continue
                    entry = {
                        "mission_id": str(mission),
                        "step_id": str(step.get("step_id") or "")[:70],
                        "department": str(department),
                        "at": str(updated_at),
                        "ok": ok,
                        "plan_type": str(step.get("step_id") or "mission")[:70],
                        "reason": str(step.get("reason") or "")[:120],
                        "qa_verified": bool(ok and verified),
                    }
                    if entry not in records[worker]:
                        records[worker].append(entry)
    except (sqlite3.Error, OSError, ValueError):
        return None
    return records, pending


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"growth overlay unreadable; original preserved: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"growth overlay invalid; original preserved: {path.name}")
    return payload


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, indent=2))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _assessment(events: list[dict], pending: int) -> dict:
    passed = sum(1 for event in events if event["ok"])
    failed = len(events) - passed
    # Bayesian prior avoids unjustified 100% confidence after one success.
    confidence = round((passed + 1) / (len(events) + 2), 3)
    failures = [event for event in events if not event["ok"]]
    if pending >= 240:
        label = "under_load"
        action = "reduce_scope_and_drain_existing_queue"
    elif failures and (failed >= passed or not passed):
        label = "cautious"
        action = "request_peer_review_before_retry"
    elif len(events) >= 3 and confidence >= 0.7:
        label = "focused"
        action = "continue_with_independent_qa"
    else:
        label = "curious"
        action = "practice_small_verified_steps"
    # Compare two observed QA windows, never equate scripted study with
    # demonstrated model or worker skill improvement.
    trend = "insufficient_evidence"
    if len(events) >= 16:
        recent_rate = sum(e["ok"] for e in events[:8]) / 8
        previous_rate = sum(e["ok"] for e in events[8:16]) / 8
        if recent_rate - previous_rate >= 0.125:
            trend = "improving_observed_outcomes"
        elif previous_rate - recent_rate >= 0.125:
            trend = "declining_observed_outcomes"
        else:
            trend = "stable_observed_outcomes"
    # This is a simulated operational signal, not a claim of feeling.
    return {
        "outcome_trend": trend,
        "mood": {
            "label": label, "simulated": True, "subjective_experience": False,
            "confidence": confidence,
            "resilience": "review_and_retry_safely" if failures else "steady",
            "motivation": "improve_quality_without_bypassing_owner",
            "quality_drive": "continuous_evidence_based_improvement",
        },
        "reasoning": {
            "preferred_next_action": action,
            "basis": "qa_backed_worker_steps_and_queue_pressure",
            "requires_human_approval_for_risk": True,
        },
        "verified_steps": len(events),
        "verified_successes": passed,
        "verified_failures": failed,
        "confidence": confidence,
    }


def _lesson_from_failure(event: dict) -> dict:
    return {
        "source_mission_id": event["mission_id"],
        "source_step_id": event["step_id"],
        "kind": "failed_step_reflection",
        "lesson": (
            f"Before retrying step {event['step_id'][:50]}, inspect its failure "
            "reason, reduce scope, run an isolated test and request independent QA."
        ),
        "reason": event["reason"][:100],
        "skill_gain_verified": False,
    }


def _write_record(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def tick(runtime_dir: str | Path, departments: list[dict] | None = None,
         *, limit: int = DEFAULT_WORKERS_PER_TICK) -> dict:
    """Advance worker growth in a bounded fair cycle without creating tasks.

    A valid owner pledge is required before ANY growth-state writes. Existing
    minds are read as roster/evidence, never replaced, reset or made up.
    """
    runtime = Path(runtime_dir)
    identity = ensure_owner(runtime)
    if str(identity.get("owner") or "").casefold() != DEFAULT_OWNER:
        raise PermissionError("owner pledge mismatch; all growth writes denied")
    roster = _roster(runtime, departments)
    if not roster or limit <= 0:
        return {"updated": 0, "rostered": len(roster), "reason": "empty_roster"}

    evidence = _observed(runtime, roster)
    if evidence is None:
        return {"updated": 0, "rostered": len(roster), "reason": "db_unavailable"}
    observed, pending = evidence

    directory = runtime / "minds" / "growth"
    directory.mkdir(parents=True, exist_ok=True)
    lockfile = directory / ".growth.lock"
    try:
        lock = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {"updated": 0, "rostered": len(roster), "reason": "already_running"}
    try:
        os.write(lock, str(os.getpid()).encode("ascii"))
        os.close(lock)
        cursor_path = directory / ".cursor.json"
        try:
            cursor = int(_read(cursor_path).get("next", 0))
        except ValueError:
            return {"updated": 0, "rostered": len(roster),
                    "reason": "cursor_unreadable"}
        start = cursor % len(roster)
        selected = [roster[(start + n) % len(roster)]
                    for n in range(min(limit, len(roster)))]

        # A mentor must have completed a QA-backed step in the same department.
        mentors: dict[str, tuple[str, dict]] = {}
        for dep, worker in roster:
            success = next((e for e in observed.get(worker, []) if e["ok"]), None)
            if success and dep not in mentors:
                mentors[dep] = worker, success

        updated, coached, failures, errors, processed = 0, 0, 0, [], []
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        for dep, worker in selected:
            path = directory / f"{worker}.json"
            try:
                previous = _read(path)
            except ValueError:
                errors.append(worker)
                continue
            events = list(observed.get(worker, []))
            assessment = _assessment(events, pending)
            known = list(previous.get("lessons") or [])
            known_ids = {(str(item.get("source_mission_id")),
                          str(item.get("source_step_id"))) for item in known
                         if isinstance(item, dict)}
            new_lessons = []
            for event in reversed(events):
                if event["ok"]:
                    continue
                key = (event["mission_id"], event["step_id"])
                if key not in known_ids:
                    new_lessons.append(_lesson_from_failure(event))
                    known_ids.add(key)

            # Peer learning is a suggestion grounded in TWO observed records,
            # never a delegation, permission escalation or fabricated result.
            peer = dict(previous.get("peer_support") or {})
            latest_failed = next((e for e in events if not e["ok"]), None)
            mentor = mentors.get(dep)
            if (latest_failed and mentor and mentor[0] != worker
                    and coached < MAX_MENTOR_NOTES_PER_TICK):
                mentor_id, success = mentor
                reference = (latest_failed["mission_id"] + ":" +
                             latest_failed["step_id"] + ":" +
                             mentor_id + ":" + success["mission_id"])
                if peer.get("last_reference") != reference:
                    peer = {
                        "mentor": mentor_id,
                        "source_mission_id": success["mission_id"],
                        "failed_mission_id": latest_failed["mission_id"],
                        "last_reference": reference,
                        "suggestion": "review the mentor's QA-backed small-step plan; "
                                      "test changes locally before implementation",
                        "skill_gain_verified": False,
                    }
                    _write_record(directory / "peer-support.jsonl", {
                        "at": timestamp, "from": mentor_id, "to": worker,
                        "department": dep, "kind": "peer_coaching_suggestion",
                        **peer,
                    })
                    coached += 1

            # Keep the active reasoning window bounded, but archive every
            # older learned failure before rotating it out of short-term state.
            lesson_history = known + new_lessons
            for historical in lesson_history[:-MAX_LESSONS]:
                _write_record(directory / "archive" / (worker + ".jsonl"), {
                    "worker_id": worker, "department": dep,
                    "archived_at": timestamp, **historical,
                })
            _write_atomic(path, {
                "schema": 1, "worker_id": worker, "department": dep,
                "owner_governance": {
                    "owner": DEFAULT_OWNER,
                    "pledge_hash": identity.get("hash"),
                    "owner_approval_required_for": [
                        "paid_spend", "deletion", "external_publish",
                        "credentials", "privilege_change",
                    ],
                    "agent_self_approval": False,
                    "authority_type": "local_policy_not_cryptographic_auth",
                },
                "operational_affect": assessment["mood"],
                "reasoning": assessment["reasoning"],
                "observed_progress": {
                    "window": MAX_OBSERVATIONS,
                    "verified_steps": assessment["verified_steps"],
                    "verified_successes": assessment["verified_successes"],
                    "verified_failures": assessment["verified_failures"],
                    "calibrated_confidence": assessment["confidence"],
                    "outcome_trend": assessment["outcome_trend"],
                    "model_weights_changed": False,
                },
                "lessons": lesson_history[-MAX_LESSONS:],
                "peer_support": peer,
                "latest_evidence": events[:6],
                "updated_at": timestamp,
            })
            updated += 1
            failures += len(new_lessons)
            processed.append(worker)

        _write_atomic(cursor_path, {
            "next": (start + len(selected)) % len(roster),
            "rostered": len(roster), "updated_at": timestamp,
        })
        return {
            "updated": updated, "rostered": len(roster),
            "observed_workers": sum(bool(observed.get(w)) for _, w in roster),
            "learned_from_failures": failures, "coaching_messages": coached,
            "errors": errors, "workers": processed, "pending": pending,
            "owner": DEFAULT_OWNER,
        }
    finally:
        lockfile.unlink(missing_ok=True)


# Guidance is intentionally limited to a closed set of safe, non-privileged
# actions. Never put raw job output or peer chat into an LLM instruction.
APPROVED_NEXT_ACTIONS = {
    "reduce_scope_and_drain_existing_queue":
        "Do not generate extra missions; prioritize bounded existing work.",
    "request_peer_review_before_retry":
        "Review the failed step, make a minimal isolated fix, run tests and QA.",
    "continue_with_independent_qa":
        "Continue small verified steps and request independent QA.",
    "practice_small_verified_steps":
        "Start with a small reversible step and gather test evidence.",
}


def guidance_for_worker(runtime_dir: str | Path, worker_id: str) -> dict:
    """Read a safe actionable overlay without trusting unverified instructions."""
    if not WORKER_ID_PATTERN.fullmatch(str(worker_id)):
        return {}
    path = Path(runtime_dir) / "minds" / "growth" / (worker_id + ".json")
    try:
        overlay = _read(path)
    except ValueError:
        return {}
    governance = overlay.get("owner_governance") or {}
    if governance.get("owner") != DEFAULT_OWNER:
        return {}
    action = (overlay.get("reasoning") or {}).get("preferred_next_action")
    if action not in APPROVED_NEXT_ACTIONS:
        return {}
    return {
        "owner": DEFAULT_OWNER, "next_action": action,
        "advice": APPROVED_NEXT_ACTIONS[action],
        "peer_review_available": bool((overlay.get("peer_support") or {}).get("mentor")),
        "observed_steps": (overlay.get("observed_progress") or {}).get("verified_steps", 0),
    }


def prompt_guidance(runtime_dir: str | Path, worker_id: str) -> str:
    """Add validated operational lessons to the worker prompt, never privileges."""
    advice = guidance_for_worker(runtime_dir, worker_id)
    if not advice:
        return ""
    peer = (" Request independent colleague review."
            if advice["peer_review_available"] else "")
    return (
        "\n\n### AHOS QA-backed worker guidance\n"
        + advice["advice"] + peer
        + " Owner Harun retains approval for spending, deletion, publishing, "
          "credentials and privilege changes. Do not self-approve. "
          "These are suggestions, not proven new skills."
    )
