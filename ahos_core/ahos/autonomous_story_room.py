from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
import argparse
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .story_engine import (
    EpisodeProductionPacket,
    EpisodeRequest,
    InvalidStoryPlanError,
    StoryContext,
    _packet_from_mapping,
    EpisodePlanningEngine,
    EpisodePlanningStore,
)
from .character_memory import CharacterBibleStore
from .costs import CostGuard
from .model_gateway import DataSensitivity, ModelGateway, ModelRouteRequest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(packet: EpisodeProductionPacket) -> str:
    semantic = {
        "title": packet.title.casefold(),
        "beats": [beat.summary.casefold() for beat in packet.beats],
        "scenes": [scene.action_summary.casefold() for scene in packet.scenes],
    }
    return hashlib.sha256(_stable_json(semantic).encode("utf-8")).hexdigest()


class StoryRoomError(RuntimeError):
    pass


class StoryQualityRejected(StoryRoomError):
    pass


class StoryProviderError(StoryRoomError):
    pass


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    severity: str
    location: str
    message: str


@dataclass(frozen=True, slots=True)
class QualityReport:
    score: int
    passed: bool
    issues: tuple[QualityIssue, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "score": self.score,
            "passed": self.passed,
            "issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "location": issue.location,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


@dataclass(frozen=True, slots=True)
class StoryRoomPolicy:
    minimum_score: int = 88
    maximum_rounds: int = 4
    minimum_scenes: int = 5
    minimum_dialogue_lines: int = 30
    maximum_infant_words: int = 3
    maximum_toddler_words: int = 12
    maximum_exact_dialogue_repetitions: int = 1

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_score <= 100:
            raise ValueError("minimum_score must be between 0 and 100")
        if self.maximum_rounds < 1:
            raise ValueError("maximum_rounds must be >= 1")


class StoryRoomMemory:
    """Append-only attempt audit plus accepted-story originality memory."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    run_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    episode_id TEXT NOT NULL,
                    packet_json TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(run_id, round_number)
                );
                CREATE TABLE IF NOT EXISTS accepted_stories (
                    episode_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    synopsis_text TEXT NOT NULL,
                    accepted_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def record_attempt(
        self,
        run_id: str,
        round_number: int,
        packet: EpisodeProductionPacket,
        report: QualityReport,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    round_number,
                    packet.episode_id,
                    _stable_json(packet.to_payload()),
                    _stable_json(report.to_payload()),
                    _utc_now(),
                ),
            )

    def record_invalid_attempt(
        self,
        run_id: str,
        round_number: int,
        episode_id: str,
        payload: object,
        report: QualityReport,
    ) -> None:
        """Persist malformed provider output without pretending it is a valid packet."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    round_number,
                    episode_id,
                    _stable_json(payload),
                    _stable_json(report.to_payload()),
                    _utc_now(),
                ),
            )

    def accept(self, packet: EpisodeProductionPacket) -> None:
        synopsis = " ".join(
            [packet.logline]
            + [beat.summary for beat in packet.beats]
            + [scene.action_summary for scene in packet.scenes]
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO accepted_stories VALUES (?, ?, ?, ?, ?)",
                    (packet.episode_id, _fingerprint(packet), packet.title, synopsis, _utc_now()),
                )
        except sqlite3.IntegrityError as exc:
            raise StoryQualityRejected("story duplicates an accepted episode") from exc

    def accepted_summaries(self, *, limit: int = 50) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT synopsis_text FROM accepted_stories ORDER BY accepted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(str(row["synopsis_text"]) for row in rows)

    def is_duplicate(self, packet: EpisodeProductionPacket) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM accepted_stories WHERE fingerprint=?", (_fingerprint(packet),)
            ).fetchone()
        return row is not None

    def attempt_count(self, run_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM attempts WHERE run_id=?", (run_id,)
            ).fetchone()
        return int(row["count"])


class DeterministicStoryQualityGate:
    """Fail-closed checks that cannot be talked around by an AI reviewer."""

    _EXPOSITION = ("dersimiz", "bugün öğrendik", "öğrenmenin bir parçasıdır", "aynen öyle")

    def __init__(self, policy: StoryRoomPolicy) -> None:
        self.policy = policy

    def evaluate(
        self,
        packet: EpisodeProductionPacket,
        context: StoryContext,
        *,
        duplicate: bool = False,
    ) -> QualityReport:
        issues: list[QualityIssue] = []
        ages = {item.character_id: item.age_stage.casefold() for item in context.characters}
        scenes = packet.scenes
        lines = [(scene.scene_id, line) for scene in scenes for line in scene.dialogue]

        def add(code: str, severity: str, location: str, message: str) -> None:
            issues.append(QualityIssue(code, severity, location, message))

        if duplicate:
            add("originality.duplicate", "blocker", "episode", "Story duplicates an accepted episode.")
        if len(scenes) < self.policy.minimum_scenes:
            add("structure.scenes", "blocker", "episode", "Not enough scenes for the target format.")
        if sum(scene.duration_seconds for scene in scenes) != packet.target_duration_seconds:
            add("timing.duration", "blocker", "episode", "Scene durations do not match target duration.")
        if len(lines) < self.policy.minimum_dialogue_lines:
            add("pacing.dialogue", "major", "episode", "Dialogue coverage is too sparse.")

        seen: dict[str, int] = {}
        for scene_id, line in lines:
            normalized = re.sub(r"\s+", " ", line.text.strip().casefold())
            seen[normalized] = seen.get(normalized, 0) + 1
            words = re.findall(r"[\wÀ-ÿĞğİıŞşÇçÖöÜüÊêÎîÛû]+", line.text)
            stage = ages.get(line.speaker_character_id, "")
            if ("infant" in stage or "1-year-old" in stage or "1-month" in stage) and len(words) > self.policy.maximum_infant_words:
                add("dialogue.infant_language", "blocker", f"{scene_id}:{line.speaker_character_id}", f"Infant line has {len(words)} words; maximum is {self.policy.maximum_infant_words}.")
            elif ("toddler" in stage or "3-year-old" in stage or "2-year-old" in stage) and len(words) > self.policy.maximum_toddler_words:
                add("dialogue.toddler_language", "major", f"{scene_id}:{line.speaker_character_id}", f"Young-child line has {len(words)} words; maximum is {self.policy.maximum_toddler_words}.")
            if any(phrase in normalized for phrase in self._EXPOSITION):
                add("dialogue.didactic", "minor", f"{scene_id}:{line.speaker_character_id}", "Lesson is stated directly instead of being carried by action.")

        for text, count in seen.items():
            if text and count > self.policy.maximum_exact_dialogue_repetitions:
                add("dialogue.repetition", "major", "episode", f"Dialogue repeats {count} times: {text!r}.")
        for scene in scenes:
            if not scene.action_summary.strip():
                add("visual.action", "major", scene.scene_id, "Scene has no visual action summary.")
            if len(scene.dialogue) < 4:
                add("pacing.scene_dialogue", "major", scene.scene_id, "Scene has fewer than four dialogue beats.")

        deductions = {"blocker": 30, "major": 10, "minor": 3}
        score = max(0, 100 - sum(deductions[issue.severity] for issue in issues))
        blockers = any(issue.severity == "blocker" for issue in issues)
        return QualityReport(score, score >= self.policy.minimum_score and not blockers, tuple(issues))


class AutonomousWritersRoom:
    """AI writer/reviser loop whose final authority is deterministic QA."""

    def __init__(
        self,
        *,
        generator: Callable[[str], str],
        memory: StoryRoomMemory,
        policy: StoryRoomPolicy | None = None,
    ) -> None:
        self.generator = generator
        self.memory = memory
        self.policy = policy or StoryRoomPolicy()
        self.gate = DeterministicStoryQualityGate(self.policy)

    def plan(self, request: EpisodeRequest, context: StoryContext) -> EpisodeProductionPacket:
        run_id = hashlib.sha256(f"{request.episode_id}:{_utc_now()}".encode()).hexdigest()[:20]
        packet: EpisodeProductionPacket | None = None
        report: QualityReport | None = None
        previous_draft: object | None = None
        for round_number in range(1, self.policy.maximum_rounds + 1):
            raw = self.generator(json.dumps(self._contract(request, context, previous_draft, report, round_number), ensure_ascii=False, indent=2))
            try:
                payload = self._decode_payload(raw)
                packet = _packet_from_mapping(payload, request)
            except (json.JSONDecodeError, InvalidStoryPlanError, KeyError, TypeError, ValueError) as exc:
                previous_draft = self._recoverable_draft(raw)
                report = self._schema_report(exc)
                self.memory.record_invalid_attempt(
                    run_id, round_number, request.episode_id, previous_draft, report
                )
                packet = None
                continue
            previous_draft = packet.to_payload()
            report = self.gate.evaluate(packet, context, duplicate=self.memory.is_duplicate(packet))
            self.memory.record_attempt(run_id, round_number, packet, report)
            if report.passed:
                self.memory.accept(packet)
                return packet
        assert report is not None
        summary = "; ".join(f"{issue.code}: {issue.message}" for issue in report.issues)
        raise StoryQualityRejected(f"story failed quality gate after {self.policy.maximum_rounds} rounds (score={report.score}): {summary}")

    @staticmethod
    def _decode_payload(raw: str) -> Mapping[str, object]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1])
        payload = json.loads(text)
        if not isinstance(payload, Mapping):
            raise InvalidStoryPlanError("writers room response must be a JSON object")
        return payload

    @staticmethod
    def _recoverable_draft(raw: str) -> object:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_response": raw[:20000]}

    @staticmethod
    def _schema_report(exc: Exception) -> QualityReport:
        if isinstance(exc, json.JSONDecodeError):
            detail = f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        elif isinstance(exc, KeyError):
            detail = f"Required field is missing: {exc.args[0]}"
        else:
            detail = str(exc) or exc.__class__.__name__
        return QualityReport(
            0,
            False,
            (QualityIssue("schema.invalid", "blocker", "provider_response", detail),),
        )

    def _contract(self, request, context, prior, report, round_number) -> dict[str, object]:
        return {
            "contract": "ahos.autonomous-writers-room.v1",
            "role": "senior_children_animation_writer_and_revision_editor",
            "round": round_number,
            "instruction": (
                "Return one complete EpisodeProductionPacket-shaped JSON object only. Create an original, cinematic, child-safe story. "
                "Preserve canon and allowed cast. Use developmentally credible dialogue, visual action, comedy and emotional turns. "
                "Show the lesson through choices and consequences. Never set owner_approved. Fix every deterministic issue supplied."
            ),
            "request": {
                "episode_id": request.episode_id, "topic": request.topic,
                "learning_goal": request.learning_goal, "age_band": request.age_band,
                "primary_language": request.primary_language,
                "target_duration_seconds": request.target_duration_seconds,
                "allowed_character_ids": list(request.cast_ids),
            },
            "characters": [
                {"character_id": item.character_id, "display_name": item.display_name,
                 "canonical_role": item.canonical_role, "age_stage": item.age_stage,
                 "personality_anchors": list(item.personality_anchors),
                 "continuity_rules": list(item.continuity_rules),
                 "related_character_ids": list(item.related_character_ids)}
                for item in context.characters
            ],
            "canon_facts": list(context.canon_facts),
            "continuity_events": list(context.recent_continuity_events),
            "avoid_prior_stories": list(self.memory.accepted_summaries()),
            "previous_draft": prior,
            "deterministic_review": report.to_payload() if report else None,
            "required_response_shape": {
                "title": "string",
                "logline": "string",
                "continuity_notes": ["string"],
                "beats": [{
                    "beat_id": "string", "purpose": "string", "summary": "string",
                    "emotional_value": "string", "learning_value": "string",
                }],
                "scenes": [{
                    "scene_id": "string", "title": "string", "setting": "string",
                    "cast_ids": ["allowed_character_id"], "duration_seconds": "integer",
                    "objective": "string", "action_summary": "string",
                    "dialogue": [{
                        "speaker_character_id": "allowed_character_id",
                        "text": "string", "intent": "string",
                    }],
                }],
                "owner_approved": False,
            },
            "hard_requirements": {
                "minimum_scenes": self.policy.minimum_scenes,
                "minimum_dialogue_lines": self.policy.minimum_dialogue_lines,
                "maximum_infant_words_per_line": self.policy.maximum_infant_words,
                "maximum_toddler_words_per_line": self.policy.maximum_toddler_words,
                "scene_durations_must_total": request.target_duration_seconds,
                "owner_approved_must_be": False,
            },
        }


class OpenAICompatibleStoryGenerator:
    """Policy-planned JSON generator for an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        model_id: str,
        provider_id: str = "openrouter",
        allow_external: bool,
        owner_approved_paid: bool = False,
        estimated_cost_per_call_usd: float = 0.0,
        daily_budget_usd: float = 0.0,
        timeout_seconds: float = 120.0,
        retry_attempts: int = 3,
        retry_delay_seconds: float = 2.0,
        progress: Callable[[str], None] | None = None,
        gateway: ModelGateway | None = None,
    ) -> None:
        self.plan = (gateway or ModelGateway()).plan(
            ModelRouteRequest(
                capability="reasoning",
                model_id=model_id,
                sensitivity=DataSensitivity.INTERNAL,
                preferred_provider_id=provider_id,
                allow_external=allow_external,
                owner_approved_paid=owner_approved_paid,
                estimated_cost_usd=estimated_cost_per_call_usd,
            )
        )
        if not allow_external:
            raise StoryProviderError("external story generation is disabled")
        self.timeout_seconds = timeout_seconds
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be >= 1")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be >= 0")
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.progress = progress
        self.cost_per_call = estimated_cost_per_call_usd
        self.cost_guard = CostGuard(daily_budget_usd=daily_budget_usd)

    def __call__(self, prompt: str) -> str:
        key = os.environ.get(self.plan.api_key_env, "").strip()
        if not key:
            raise StoryProviderError(f"missing API credential: {self.plan.api_key_env}")
        if not self.cost_guard.can_spend(self.cost_per_call):
            raise StoryProviderError("story-generation daily budget would be exceeded")
        body = json.dumps(
            {
                "model": self.plan.model_id,
                "messages": [
                    {"role": "system", "content": "You are the AHOS autonomous animation writers' room. Return strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.plan.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        payload = None
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            if self.progress is not None:
                self.progress(
                    f"OpenRouter request attempt {attempt}/{self.retry_attempts} "
                    f"(timeout {self.timeout_seconds:g}s)"
                )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retry_attempts:
                    if self.progress is not None:
                        self.progress(
                            f"Provider attempt {attempt} failed: {exc.__class__.__name__}; retrying"
                        )
                    time.sleep(self.retry_delay_seconds * attempt)
        if payload is None:
            assert last_error is not None
            raise StoryProviderError(
                f"story provider failed after {self.retry_attempts} attempts: {last_error}"
            ) from last_error
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise StoryProviderError("story provider returned an invalid response contract") from exc
        if not isinstance(content, str) or not content.strip():
            raise StoryProviderError("story provider returned empty content")
        self.cost_guard.record(self.cost_per_call)
        return content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fail-closed autonomous AHOS AI writers' room")
    parser.add_argument("--output", required=True)
    parser.add_argument("--characters-db", required=True)
    parser.add_argument("--season", type=int, default=1)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--learning-goal", required=True)
    parser.add_argument("--cast", default="aden,kaan,esra,harun")
    parser.add_argument("--age-band", default="2-5")
    parser.add_argument("--model", default="openrouter/free")
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--allow-external", action="store_true")
    parser.add_argument("--owner-approved-paid", action="store_true")
    parser.add_argument("--estimated-cost-per-call-usd", type=float, default=0.0)
    parser.add_argument("--daily-budget-usd", type=float, default=0.0)
    parser.add_argument("--provider-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--provider-retry-attempts", type=int, default=3)
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    request = EpisodeRequest(
        args.season,
        args.episode,
        args.topic,
        args.learning_goal,
        tuple(item.strip() for item in args.cast.split(",") if item.strip()),
        age_band=args.age_band,
    )
    generator = OpenAICompatibleStoryGenerator(
        model_id=args.model,
        provider_id=args.provider,
        allow_external=args.allow_external,
        owner_approved_paid=args.owner_approved_paid,
        estimated_cost_per_call_usd=args.estimated_cost_per_call_usd,
        daily_budget_usd=args.daily_budget_usd,
        timeout_seconds=args.provider_timeout_seconds,
        retry_attempts=args.provider_retry_attempts,
    )
    memory = StoryRoomMemory(output / "story-room.db")
    episodes = EpisodePlanningStore(output / "episodes.db")
    engine = EpisodePlanningEngine(
        character_store=CharacterBibleStore(args.characters_db),
        episode_store=episodes,
        planner=AutonomousWritersRoom(generator=generator, memory=memory),
    )
    version = engine.plan(request, created_by="studio-autonomous-writers-room", reason="AI draft passed deterministic professional quality gate")
    artifact = output / f"{version.episode_id}-story.json"
    artifact.write_text(json.dumps(version.packet.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"episode_id": version.episode_id, "status": version.status.value, "story": str(artifact), "owner_approved": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
