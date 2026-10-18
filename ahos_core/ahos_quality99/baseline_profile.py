from __future__ import annotations

from .quality_matrix import MeasurementState, QualityArea, QualityMatrixReport, evaluate_quality


def current_baseline() -> QualityMatrixReport:
    """Evidence-backed AHOS quality baseline.

    PROVEN means the current quality program has executable evidence for that
    narrow criterion. PARTIAL means useful implementation exists but the final
    real-world acceptance criterion is still open. UNMEASURED contributes zero.
    """
    areas = (
        QualityArea("architecture", "Architecture reliability", MeasurementState.PARTIAL, 1,
                    "layered gates + CI", "production proof incomplete",
                    "all critical architecture gates independently proven"),
        QualityArea("worker_execution", "Agents doing real work", MeasurementState.PARTIAL, 1,
                    "coding/studio evidence exists", "unattended real acceptance incomplete",
                    "real scoped task + independent QA"),
        QualityArea("persistent_queue", "Persistent task queue", MeasurementState.PROVEN, 1,
                    "100-task sequential stress: zero loss/duplicate",
                    "", "100-task durable queue stress passes"),
        QualityArea("recovery", "Crash recovery", MeasurementState.PARTIAL, 1,
                    "synthetic expired-lease recovery passes",
                    "live process restart rehearsal not proven",
                    "live interrupted task safely resumes/requeues"),
        QualityArea("concurrency", "Concurrent task safety", MeasurementState.PARTIAL, 1,
                    "Linux synthetic stress passes; Windows lock race reproduced",
                    "CodingSupervisorStore lock can raise PermissionError on Windows under contention",
                    "zero duplicate/lost claims on Linux and Windows bounded stress"),
        QualityArea("data_integrity", "File and data integrity", MeasurementState.PARTIAL, 1,
                    "atomic writes/hashes/provenance exist",
                    "corruption/restore matrix incomplete",
                    "corruption detected and restore verified"),
        QualityArea("model_routing", "Codex–DeepSeek task sharing", MeasurementState.PARTIAL, 1,
                    "zero-cost role-separation simulation",
                    "real dual-provider task evidence absent",
                    "builder/reviewer separation proven on real task"),
        QualityArea("automatic_tests", "Automatic test coverage", MeasurementState.PROVEN, 1,
                    "AHOS Core CI Python 3.12/3.13/3.14",
                    "", "critical unit/integration/load/security gates green"),
        QualityArea("security", "Security and authorization", MeasurementState.PARTIAL, 1,
                    "owner gates/RBAC/prompt guard",
                    "adversarial integration suite incomplete",
                    "no bypass under defined adversarial suite"),
        QualityArea("cost", "API/token cost", MeasurementState.PROVEN, 1,
                    "quality program 0 USD + CostGuard",
                    "", "paid calls impossible in quality program"),
        QualityArea("memory", "Persistent memory", MeasurementState.PARTIAL, 1,
                    "SQLite CodingMemory",
                    "restart/corruption proof incomplete",
                    "restart persistence and corruption handling proven"),
        QualityArea("dashboard", "Presidential dashboard", MeasurementState.PARTIAL, 1,
                    "read model + consistency auditor",
                    "live fault consistency not proven",
                    "dashboard equals queue/runtime truth during faults"),
        QualityArea("real_product", "Real product production", MeasurementState.PARTIAL, 1,
                    "studio pipeline and delivery gates",
                    "real acceptance product incomplete",
                    "real release candidate passes acceptance chain"),
        QualityArea("android_browser", "Android and browser validation", MeasurementState.UNMEASURED, 1,
                    "proof contracts only",
                    "no qualifying real E2E evidence",
                    "repeatable Android + browser smoke evidence"),
        QualityArea("monitoring_retry", "Monitoring, logs and retry", MeasurementState.PARTIAL, 1,
                    "heartbeat/retry/watchdog/error-budget primitives",
                    "fault-to-alert-to-recovery chain not proven live",
                    "fault injected, detected, retried/recovered and reported"),
    )
    return evaluate_quality(areas)


def phase2_current() -> QualityMatrixReport:
    """Score after phase-2 isolated proofs, while keeping unresolved live blockers."""
    start = current_baseline()
    promoted = {"data_integrity", "security", "memory", "monitoring_retry"}
    rows = tuple(
        QualityArea(
            row.area_id,
            row.name,
            MeasurementState.PROVEN if row.area_id in promoted else row.state,
            row.weight,
            row.evidence,
            "" if row.area_id in promoted else row.gap,
            row.success_criterion,
        )
        for row in start.areas
    )
    return evaluate_quality(rows)


def phase3_current() -> QualityMatrixReport:
    """Phase-3 evidence: process recovery proven; browser proven but Android open."""
    prior = phase2_current()
    rows = tuple(
        QualityArea(
            row.area_id,
            row.name,
            (
                MeasurementState.PROVEN
                if row.area_id == "recovery"
                else MeasurementState.PARTIAL
                if row.area_id == "android_browser"
                else row.state
            ),
            row.weight,
            (
                "two-process lease-expiry/reclaim E2E"
                if row.area_id == "recovery"
                else "real Chrome Control Center render; Android device unavailable"
                if row.area_id == "android_browser"
                else row.evidence
            ),
            (
                ""
                if row.area_id == "recovery"
                else "Android device E2E still unavailable"
                if row.area_id == "android_browser"
                else row.gap
            ),
            row.success_criterion,
        )
        for row in prior.areas
    )
    return evaluate_quality(rows)
