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
        QualityArea("concurrency", "Concurrent task safety", MeasurementState.PROVEN, 1,
                    "100-task/4 synthetic claimer stress",
                    "", "no duplicate/lost claims under bounded stress"),
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
