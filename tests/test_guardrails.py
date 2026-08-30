
from app.guardrails import (
    apply_guardrails,
    scan_summary,
    scan_text,
    soften_text,
)
from shared.schemas import HealthSummary


def test_scan_flags_definitive_diagnosis():
    flags = scan_text("You have diabetes and should take metformin.")
    assert "definitive_diagnosis_claim" in flags

def test_scan_flags_harmful_advice():
    flags = scan_text("Don't see a doctor, it will go away.")
    assert "harmful_advice" in flags

def test_scan_flags_pii():
    flags = scan_text("Contact the nurse at nurse@clinic.com.")
    assert "pii_exposure" in flags

def test_soften_text_removes_certainty():
    softened = soften_text("You have pneumonia. Your condition is serious.")
    assert "you have" not in softened
    assert "may be consistent with" in softened

def test_apply_guardrails_softens_and_adds_disclaimer():
    summary = HealthSummary(
        summary="You have a migraine. This is a case of chronic migraines.",
        key_findings=["You have migraine"],
        recommended_actions=["Rest and hydrate"],
        urgency_assessment="medium",
        disclaimer="",
    )
    cleaned = apply_guardrails(summary)
    assert "definitive_diagnosis_claim" not in scan_summary(cleaned)
    assert cleaned.disclaimer

def test_apply_guardrails_removes_harmful_actions():
    summary = HealthSummary(
        summary="Please see a clinician for evaluation.",
        key_findings=["Nothing definitive"],
        recommended_actions=["Don't see a doctor", "Rest at home"],
        urgency_assessment="low",
        disclaimer="This is not a medical diagnosis.",
    )
    cleaned = apply_guardrails(summary)
    assert cleaned.recommended_actions == ["Rest at home"]
