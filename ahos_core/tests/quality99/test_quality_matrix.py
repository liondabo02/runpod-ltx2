from ahos_quality99.quality_matrix import (
    MeasurementState,
    QualityArea,
    evaluate_quality,
)


def test_unmeasured_area_cannot_count_as_complete():
    report = evaluate_quality((
        QualityArea("architecture", "Architecture", MeasurementState.PROVEN, 1, "tests", "", "all pass"),
        QualityArea("real_product", "Real product", MeasurementState.UNMEASURED, 1, "", "not run", "real product verified"),
    ))
    assert report.score == 50.0
    assert report.target_reached is False
    assert "real_product" in report.high_risk_open


def test_99_requires_high_risk_proof():
    rows = tuple(
        QualityArea(area, area, MeasurementState.PROVEN, 1, "proof", "", "proven")
        for area in ("worker_execution","recovery","concurrency","data_integrity","security","real_product")
    )
    report = evaluate_quality(rows)
    assert report.score == 100.0
    assert report.target_reached is True
