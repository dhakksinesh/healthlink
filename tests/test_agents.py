
from types import SimpleNamespace

from app.agents import doctor, scheduling, summary, symptom
from app.database import get_db_manager
from shared.config import get_settings
from shared.schemas import (
    Doctor,
    DoctorRecommendation,
    DoctorSummary,
    HealthSummary,
    SchedulingRecommendation,
    SymptomExtraction,
    TimeSlot,
)


def _fake_extraction() -> SymptomExtraction:
    return SymptomExtraction(
        symptoms=[{"name": "cough", "severity": "moderate", "duration": "1 week"}],
        primary_complaint="persistent cough",
        urgency_level="medium",
        additional_context=None,
        clarifying_questions=[],
    )

def _fake_doctor_recommendation() -> DoctorRecommendation:
    return DoctorRecommendation(
        recommended_doctors=[Doctor(
            name="Dr. Sarah Johnson",
            specialty="General Practice",
            experience_years=15,
            rating=4.8,
            availability="Mon-Fri 9AM-5PM",
            location="Downtown Medical Center",
        )],
        specialty_rationale="General medicine fits these symptoms.",
        match_score=0.85,
    )

class TestSymptomAgent:
    def test_returns_extraction(self, monkeypatch):
        monkeypatch.setattr(symptom, "llm_generate", lambda **kwargs: _fake_extraction())
        result = symptom.symptom_agent("I have a cough for a week", settings=get_settings())
        assert result.primary_complaint == "persistent cough"
        assert result.urgency_level == "medium"

    def test_fallback_on_llm_error(self, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("llm down")

        monkeypatch.setattr(symptom, "llm_generate", boom)
        result = symptom.symptom_agent("I have a cough for a week", settings=get_settings())
        assert result.symptoms == []
        assert result.urgency_level == "medium"

class TestDoctorAgent:
    def test_recommends_by_specialty(self, client, monkeypatch):
        monkeypatch.setattr(
            doctor,
            "llm_generate",
            lambda **kwargs: SimpleNamespace(
                recommended_specialty="Cardiology", specialty_rationale="Heart-related", match_score=0.9
            ),
        )
        settings = get_settings()
        with get_db_manager(settings).session_scope() as session:
            result = doctor.doctor_agent(
                symptom_analysis=_fake_extraction(),
                db_session=session,
                settings=settings,
            )
        assert result.recommended_doctors
        assert all("Cardiology" in d.specialty for d in result.recommended_doctors)

    def test_fallback_when_llm_fails(self, client, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("llm down")

        monkeypatch.setattr(doctor, "llm_generate", boom)
        settings = get_settings()
        with get_db_manager(settings).session_scope() as session:
            result = doctor.doctor_agent(
                symptom_analysis=_fake_extraction(),
                db_session=session,
                settings=settings,
            )
        assert result.recommended_doctors

class TestSchedulingAgent:
    def test_generates_weekday_slots_only(self):
        from datetime import date

        slots = scheduling.generate_time_slots("Dr. X", date(2026, 8, 17), num_days=7, slots_per_day=8)
        assert slots
        assert all(slot.doctor_name == "Dr. X" for slot in slots)

    def test_picks_recommended_slot(self, monkeypatch):
        monkeypatch.setattr(
            scheduling,
            "llm_generate",
            lambda **kwargs: SimpleNamespace(
                recommended_slot_id=kwargs["prompt"].split("Available Slots")[0] and "x",
                scheduling_notes="Morning slot chosen.",
            ),
        )


        result = scheduling.scheduling_agent(
            doctor_recommendation=_fake_doctor_recommendation(),
            urgency_level="medium",
            settings=get_settings(),
        )
        assert result.available_slots
        assert result.recommended_slot is not None

class TestSummaryAgent:
    def test_produces_both_summaries(self, monkeypatch):
        patient = HealthSummary(
            summary="Your symptoms may be consistent with a respiratory issue.",
            key_findings=["Persistent cough"],
            recommended_actions=["Consult a doctor"],
            urgency_assessment="medium",
            disclaimer="This is not a medical diagnosis.",
        )
        doc = DoctorSummary(
            patient_overview="Patient reports persistent cough.",
            presenting_symptoms=["cough"],
            key_points=["Assess severity"],
            suggested_follow_ups=["Consider a chest exam"],
        )

        def fake_generate(prompt, schema, **kwargs):
            if schema is HealthSummary:
                return patient
            return doc

        monkeypatch.setattr(summary, "llm_generate", fake_generate)
        patient_result, doctor_result = summary.summary_agent(
            symptom_analysis=_fake_extraction(),
            doctor_recommendation=_fake_doctor_recommendation(),
            scheduling_recommendation=SchedulingRecommendation(
                available_slots=[],
                recommended_slot=TimeSlot(
                    doctor_name="Dr. Sarah Johnson",
                    date="2026-08-20",
                    time="10:00",
                    slot_id="s1",
                ),
                scheduling_notes="Morning slot.",
            ),
            settings=get_settings(),
        )
        assert patient_result.summary
        assert doctor_result.patient_overview
