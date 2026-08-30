
import logging

from app.guardrails import apply_guardrails
from shared.config import Settings, get_settings
from shared.llm import LLMClient, llm_generate
from shared.schemas import (
    DoctorRecommendation,
    DoctorSummary,
    HealthSummary,
    SchedulingRecommendation,
    SymptomExtraction,
)

logger = logging.getLogger("healthlink.summary.agent")

def _flatten_symptoms(symptom_analysis: SymptomExtraction) -> str:
    return ", ".join([
        f"{s.name} ({s.severity})" + (f" for {s.duration}" if s.duration else "")
        for s in symptom_analysis.symptoms
    ])

def summary_agent(
    symptom_analysis: SymptomExtraction,
    doctor_recommendation: DoctorRecommendation,
    scheduling_recommendation: SchedulingRecommendation,
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
) -> tuple[HealthSummary, DoctorSummary]:

    logger.info("Summary agent generating health summaries")

    if settings is None:
        settings = get_settings()

    symptoms_text = _flatten_symptoms(symptom_analysis)
    doctors_text = ", ".join([
        f"Dr. {d.name} ({d.specialty})" for d in doctor_recommendation.recommended_doctors
    ])

    recommended_slot = scheduling_recommendation.recommended_slot
    slot_text = (
        f"{recommended_slot.doctor_name} on {recommended_slot.date} at {recommended_slot.time}"
        if recommended_slot
        else "No specific slot recommended"
    )

    shared_context = f"""SYMPTOM ANALYSIS:
- Primary Complaint: {symptom_analysis.primary_complaint}
- Symptoms Identified: {symptoms_text}
- Urgency Level: {symptom_analysis.urgency_level}
- Additional Context: {symptom_analysis.additional_context or 'None'}

DOCTOR RECOMMENDATIONS:
- Recommended Doctors: {doctors_text}
- Specialty Rationale: {doctor_recommendation.specialty_rationale}
- Match Confidence: {doctor_recommendation.match_score}

SCHEDULING:
- Recommended Appointment: {slot_text}
- Scheduling Notes: {scheduling_recommendation.scheduling_notes or 'None'}
"""


    patient_prompt = f"""Generate a comprehensive PATIENT summary based on the following information:

{shared_context}

Include:
1. A clear, empathetic overview of the health situation (2-3 sentences)
2. Key medical findings from the symptom analysis (list format)
3. Recommended next steps including doctor consultation and appointment (list format)
4. Overall urgency assessment with explanation

IMPORTANT:
- Be professional and empathetic
- NEVER make a definitive diagnosis (say "may be consistent with", not "you have")
- Emphasize that this is guidance, not medical advice
- Use clear, patient-friendly language
- Include the mandatory disclaimer
"""

    try:
        patient_result = llm_generate(
            prompt=patient_prompt,
            schema=HealthSummary,
            temperature=0.3,
            client=llm_client,
        )
        if not patient_result.disclaimer:
            patient_result.disclaimer = (
                "This is not a medical diagnosis. Please consult with healthcare "
                "professionals for medical advice."
            )
        patient_result = apply_guardrails(patient_result)
    except Exception as e:
        logger.error(f"Patient summary generation failed: {e}", exc_info=True)
        patient_result = HealthSummary(
            summary=(
                f"Based on your reported symptoms ({symptom_analysis.primary_complaint}), "
                "we recommend consulting with a healthcare professional. The urgency "
                f"level has been assessed as {symptom_analysis.urgency_level}."
            ),
            key_findings=[
                f"Primary complaint: {symptom_analysis.primary_complaint}",
                f"Urgency level: {symptom_analysis.urgency_level}",
                "Recommended specialty: "
                + (doctor_recommendation.recommended_doctors[0].specialty
                   if doctor_recommendation.recommended_doctors else "General Practice"),
            ],
            recommended_actions=[
                "Schedule an appointment with a recommended healthcare provider",
                "Monitor your symptoms and seek immediate care if they worsen",
                "Bring any relevant medical history to your appointment",
            ],
            urgency_assessment=symptom_analysis.urgency_level,
            disclaimer=(
                "This is not a medical diagnosis. Please consult with healthcare "
                "professionals for medical advice."
            ),
        )


    doctor_prompt = f"""Generate a structured DOCTOR summary (for the consulting clinician) based on:

{shared_context}

The doctor summary must contain:
1. patient_overview: concise patient history/overview (2-3 sentences)
2. presenting_symptoms: the symptoms the patient reported
3. key_points: key points to discuss during the consultation
4. suggested_follow_ups: suggested follow-up actions or tests to consider

Keep it factual and structured. Do not make diagnoses.
"""

    try:
        doctor_result = llm_generate(
            prompt=doctor_prompt,
            schema=DoctorSummary,
            temperature=0.2,
            client=llm_client,
        )
    except Exception as e:
        logger.error(f"Doctor summary generation failed: {e}", exc_info=True)
        doctor_result = DoctorSummary(
            patient_overview=f"Patient presents with {symptom_analysis.primary_complaint}.",
            presenting_symptoms=[s.name for s in symptom_analysis.symptoms],
            key_points=[
                f"Reported urgency level: {symptom_analysis.urgency_level}",
                f"Recommended specialty: {doctor_recommendation.recommended_doctors[0].specialty if doctor_recommendation.recommended_doctors else 'General Practice'}",
            ],
            suggested_follow_ups=[
                "Confirm symptom timeline and severity during consultation",
                "Review any known conditions or medications",
            ],
        )

    logger.info("Summary generation complete")
    return patient_result, doctor_result
