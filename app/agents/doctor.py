
import logging

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import DoctorModel, get_all_doctors, get_doctors_by_specialty
from shared.config import Settings, get_settings
from shared.llm import LLMClient, llm_generate
from shared.schemas import Doctor, DoctorRecommendation, SymptomExtraction

logger = logging.getLogger("healthlink.doctor.agent")

def convert_doctor_model_to_schema(doctor_model: DoctorModel) -> Doctor:
    return Doctor(
        name=doctor_model.name,
        specialty=doctor_model.specialty,
        experience_years=doctor_model.experience_years,
        rating=doctor_model.rating,
        availability=doctor_model.availability,
        location=doctor_model.location,
        consultation_type=doctor_model.consultation_type,
    )

def doctor_agent(
    symptom_analysis: SymptomExtraction,
    db_session: Session,
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
    max_recommendations: int = 3,
    preferred_location: str | None = None,
) -> DoctorRecommendation:

    logger.info("Doctor agent processing symptom analysis")

    if settings is None:
        settings = get_settings()

    specialty_prompt = f"""Based on the following symptom analysis, determine the most appropriate medical specialty.

Primary Complaint: {symptom_analysis.primary_complaint}
Symptoms: {', '.join([f"{s.name} ({s.severity})" for s in symptom_analysis.symptoms])}
Urgency: {symptom_analysis.urgency_level}

Common specialties include:
- General Practice / Family Medicine
- Internal Medicine
- Cardiology
- Neurology
- Orthopedics
- Dermatology
- ENT (Ear, Nose, Throat)
- Gastroenterology
- Psychiatry
- Pediatrics
- Emergency Medicine

Recommend the most appropriate specialty and explain why.
"""

    class SpecialtyRecommendation(BaseModel):
        recommended_specialty: str = Field(..., description="Recommended medical specialty")
        specialty_rationale: str = Field(..., description="Why this specialty is appropriate")
        match_score: float = Field(..., ge=0, le=1, description="Confidence score")

    try:
        specialty_result = llm_generate(
            prompt=specialty_prompt,
            schema=SpecialtyRecommendation,
            temperature=0.2,
            client=llm_client,
        )

        logger.info(f"Recommended specialty: {specialty_result.recommended_specialty}")

        doctors_db = get_doctors_by_specialty(db_session, specialty_result.recommended_specialty)
        if not doctors_db:
            logger.warning(f"No doctors found for specialty: {specialty_result.recommended_specialty}")
            doctors_db = get_all_doctors(db_session)

        if preferred_location:
            located = [d for d in doctors_db if d.location and preferred_location.lower() in d.location.lower()]
            if located:
                doctors_db = located

        doctors = [convert_doctor_model_to_schema(d) for d in doctors_db]
        doctors.sort(key=lambda x: x.rating, reverse=True)

        recommended_doctors = doctors[:max_recommendations]

        if not recommended_doctors:
            logger.error("No doctors available in database")
            return DoctorRecommendation(
                recommended_doctors=[],
                specialty_rationale="No doctors currently available. Please contact our support team.",
                match_score=0.0,
            )

        logger.info(f"Recommended {len(recommended_doctors)} doctors")
        return DoctorRecommendation(
            recommended_doctors=recommended_doctors,
            specialty_rationale=specialty_result.specialty_rationale,
            match_score=specialty_result.match_score,
        )

    except Exception as e:
        logger.error(f"Doctor agent failed: {e}", exc_info=True)
        try:
            fallback_doctors = get_doctors_by_specialty(db_session, "General Practice")
            if not fallback_doctors:
                fallback_doctors = get_all_doctors(db_session)

            doctors = [convert_doctor_model_to_schema(d) for d in fallback_doctors]
            doctors.sort(key=lambda x: x.rating, reverse=True)

            return DoctorRecommendation(
                recommended_doctors=doctors[:max_recommendations],
                specialty_rationale="General practitioners recommended due to system error.",
                match_score=0.5,
            )
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
            return DoctorRecommendation(
                recommended_doctors=[],
                specialty_rationale="Unable to retrieve doctor recommendations at this time.",
                match_score=0.0,
            )
