import pytest

from ahos.kurmanji_quality import (
    KurmanjiLineReview,
    KurmanjiQualityError,
    KurmanjiQualityGate,
)


def review(**overrides):
    values = dict(
        line_id="L1", localized_text="Silav! Tu dixwazî bi min re bilîzî?",
        native_reviewer="native-reviewer-01", terminology_approved=True,
        pronunciation_approved=True, timing_approved=True,
        child_audience_approved=True,
    )
    values.update(overrides)
    return KurmanjiLineReview(**values)


def test_professional_kurmanji_review_passes_deterministically():
    first = KurmanjiQualityGate().evaluate((review(),))
    second = KurmanjiQualityGate().evaluate((review(),))
    assert first.ready is True
    assert first.regions == ("Adiyaman-Kahta", "Diyarbakir", "Sanliurfa", "Batman", "Mardin")
    assert first.report_hash == second.report_hash


@pytest.mark.parametrize(
    "field,issue",
    [
        ("native_reviewer", "native-review-required"),
        ("terminology_approved", "terminology-not-approved"),
        ("pronunciation_approved", "pronunciation-not-approved"),
        ("timing_approved", "timing-not-approved"),
        ("child_audience_approved", "child-register-not-approved"),
    ],
)
def test_missing_professional_approval_fails_closed(field, issue):
    value = "" if field == "native_reviewer" else False
    report = KurmanjiQualityGate().evaluate((review(**{field: value}),))
    assert report.ready is False
    assert f"L1:{issue}" in report.blocking_issues


def test_duplicate_or_empty_review_set_is_rejected():
    with pytest.raises(KurmanjiQualityError):
        KurmanjiQualityGate().evaluate(())
    with pytest.raises(KurmanjiQualityError):
        KurmanjiQualityGate().evaluate((review(), review()))
