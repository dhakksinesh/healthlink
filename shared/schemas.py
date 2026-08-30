
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:

    return datetime.now(timezone.utc)



class PatientProfile(BaseModel):

    age: int | None = Field(None, ge=0, le=130, description="Patient age")
    gender: str | None = Field(None, description="Patient gender")
    known_conditions: str | None = Field(
        None, description="Known medical conditions / history"
    )
    preferred_time_of_day: str | None = Field(
        None, description="Morning, afternoon or evening preference"
    )
    consultation_type: str | None = Field(
        None, description="In-person, Telemedicine or either"
    )

class HealthAssessmentRequest(BaseModel):

    user_input: str = Field(..., min_length=10, description="User's health concern description")
    user_id: str | None = Field(None, description="User identifier for tracking")
    patient_profile: PatientProfile | None = Field(None, description="Patient metadata")
    preferred_date: str | None = Field(None, description="Preferred appointment date")
    preferred_location: str | None = Field(None, description="Preferred doctor location")
    clarifying_answers: list[str] | None = Field(
        None, description="Answers to clarifying questions from a previous turn"
    )



class Symptom(BaseModel):

    name: str = Field(..., description="Symptom name")
    severity: str = Field(..., description="Severity level: mild, moderate, severe")
    duration: str | None = Field(None, description="How long symptom has been present")

class SymptomExtraction(BaseModel):

    symptoms: list[Symptom] = Field(..., description="Extracted symptoms")
    primary_complaint: str = Field(..., description="Main health concern")
    urgency_level: str = Field(..., description="Urgency: low, medium, high, emergency")
    additional_context: str | None = Field(None, description="Additional relevant context")
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Follow-up questions when more information is needed",
    )



class Doctor(BaseModel):

    name: str = Field(..., description="Doctor's full name")
    specialty: str = Field(..., description="Medical specialty")
    experience_years: int = Field(..., description="Years of experience")
    rating: float = Field(..., ge=0, le=5, description="Rating out of 5")
    availability: str = Field(..., description="General availability")
    location: str | None = Field(None, description="Clinic location")
    consultation_type: str | None = Field(
        None, description="In-person, Telemedicine or both"
    )

class DoctorRecommendation(BaseModel):

    recommended_doctors: list[Doctor] = Field(..., description="List of recommended doctors")
    specialty_rationale: str = Field(..., description="Why this specialty was chosen")
    match_score: float = Field(..., ge=0, le=1, description="Overall match confidence")

class DoctorDB(BaseModel):

    id: int
    name: str
    specialty: str
    experience_years: int
    rating: float
    availability: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    qualifications: str | None = None
    languages: str | None = None
    consultation_type: str | None = None



class TimeSlot(BaseModel):

    doctor_name: str = Field(..., description="Doctor's name")
    date: str = Field(..., description="Appointment date (YYYY-MM-DD)")
    time: str = Field(..., description="Appointment time (HH:MM)")
    duration_minutes: int = Field(default=30, description="Appointment duration")
    slot_id: str = Field(..., description="Unique slot identifier")

class SchedulingRecommendation(BaseModel):

    available_slots: list[TimeSlot] = Field(..., description="Available appointment slots")
    recommended_slot: TimeSlot | None = Field(None, description="Best recommended slot")
    scheduling_notes: str | None = Field(None, description="Additional scheduling information")



class DoctorSummary(BaseModel):

    patient_overview: str = Field(..., description="Concise patient history/overview")
    presenting_symptoms: list[str] = Field(..., description="Symptoms the patient reported")
    key_points: list[str] = Field(..., description="Key points to discuss during consultation")
    suggested_follow_ups: list[str] = Field(..., description="Suggested follow-up actions")

class HealthSummary(BaseModel):

    summary: str = Field(..., description="Comprehensive health summary")
    key_findings: list[str] = Field(..., description="Key medical findings")
    recommended_actions: list[str] = Field(..., description="Recommended next steps")
    urgency_assessment: str = Field(..., description="Overall urgency level")
    disclaimer: str = Field(
        default="This is not a medical diagnosis. Please consult with healthcare "
        "professionals for medical advice.",
        description="Medical disclaimer",
    )



class AppointmentBookRequest(BaseModel):

    user_id: str = Field(..., description="User identifier")
    slot_id: str = Field(..., description="Slot to book")
    notes: str | None = Field(None, description="Optional booking notes")

class Appointment(BaseModel):

    id: int = Field(..., description="Appointment id")
    user_id: str = Field(..., description="User identifier")
    doctor_name: str = Field(..., description="Doctor's name")
    specialty: str = Field(..., description="Doctor's specialty")
    appointment_date: str = Field(..., description="Appointment date (YYYY-MM-DD)")
    appointment_time: str = Field(..., description="Appointment time (HH:MM)")
    status: str = Field(..., description="scheduled, completed or cancelled")
    reminder: str | None = Field(None, description="Simulated reminder / follow-up text")
    created_at: datetime = Field(..., description="When the appointment was booked")



class HealthAssessmentResponse(BaseModel):

    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(default_factory=utcnow, description="Response timestamp")
    symptom_analysis: SymptomExtraction = Field(..., description="Symptom extraction results")
    doctor_recommendations: DoctorRecommendation = Field(..., description="Recommended doctors")
    scheduling_options: SchedulingRecommendation = Field(..., description="Scheduling information")
    health_summary: HealthSummary = Field(..., description="Patient-facing health summary")
    doctor_summary: DoctorSummary = Field(..., description="Doctor-facing structured summary")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Additional metadata")



class HealthCheckResponse(BaseModel):

    status: str = "healthy"
    timestamp: datetime = Field(default_factory=utcnow)
    version: str = "1.0.0"
    services: dict[str, str] = Field(default_factory=dict)

class ErrorResponse(BaseModel):

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=utcnow)



class Document(BaseModel):

    content: str = Field(..., description="Document content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    embedding: list[float] | None = Field(None, description="Document embedding vector")

class RetrievalResult(BaseModel):

    documents: list[Document] = Field(..., description="Retrieved documents")
    scores: list[float] = Field(..., description="Relevance scores")
    query: str = Field(..., description="Original query")
