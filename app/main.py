
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.database import (
    create_appointment,
    get_all_doctors,
    get_appointments_for_user,
    get_db_manager,
    get_doctor_by_id,
    get_doctor_by_name,
    get_specialties,
    update_appointment_status,
)
from app.orchestrator import run_pipeline
from app.security import (
    RateLimiter,
    detect_prompt_injection,
    mask_pii,
    validate_user_input,
)
from app.seed import seed_if_needed
from shared.config import get_settings
from shared.logging import set_request_id, setup_logging
from shared.schemas import (
    Appointment,
    AppointmentBookRequest,
    DoctorDB,
    ErrorResponse,
    HealthAssessmentRequest,
    HealthAssessmentResponse,
    HealthCheckResponse,
)

settings = get_settings()
logger = setup_logging(log_level=settings.log_level, service_name="healthlink")



from shared.tracing import configure_langsmith

configure_langsmith(settings)

rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_max,
    window_seconds=settings.rate_limit_window,
)

@asynccontextmanager
async def lifespan(_: FastAPI):

    seed_if_needed(settings)
    if settings.load_kb_on_startup:
        from app.rag import load_knowledge_base

        kb_file = settings.kb_file
        if os.path.exists(kb_file):
            try:
                load_knowledge_base(kb_file, settings)
            except Exception as e:
                logger.error(f"Knowledge base load failed: {e}", exc_info=True)
    yield

app = FastAPI(
    title="HealthLink",
    description="Smart Health Management System - a monolithic multi-agent FastAPI service.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "name": "HealthLink",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "assess": "POST /api/v1/assess",
            "doctors": "GET /api/v1/doctors",
            "appointments": "POST /api/v1/appointments",
        },
    }

@app.get("/health", response_model=HealthCheckResponse)
@app.get("/api/v1/health", response_model=HealthCheckResponse)
def health():

    services = {"app": "healthy"}

    try:
        db_manager = get_db_manager(settings)
        with db_manager.session_scope() as session:
            get_all_doctors(session)
        services["database"] = "healthy"
    except Exception:
        services["database"] = "unavailable"

    services["llm"] = "healthy" if settings.openrouter_api_key else "unavailable"
    services["pinecone"] = "configured" if settings.pinecone_api_key else "unavailable"

    overall = "healthy" if services["database"] == "healthy" else "degraded"
    return HealthCheckResponse(status=overall, services=services)

@app.post("/api/v1/assess", response_model=HealthAssessmentResponse, responses={400: {"model": ErrorResponse}})
def assess(request: HealthAssessmentRequest, http_request: Request) -> HealthAssessmentResponse:

    client_id = http_request.client.host if http_request.client else "unknown"

    if not rate_limiter.allow(client_id):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")

    is_valid, error = validate_user_input(request.user_input)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    if detect_prompt_injection(request.user_input):
        logger.warning(f"Prompt-injection attempt blocked from {client_id}")
        raise HTTPException(status_code=400, detail="Input rejected by safety filter.")

    request_id = str(uuid.uuid4())
    set_request_id(request_id)
    logger.info(
        f"[{request_id}] Assessment request from {client_id}: {mask_pii(request.user_input[:120])}"
    )

    try:
        return run_pipeline(request)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"[{request_id}] Assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal pipeline error.")



def _to_doctor_db(model) -> DoctorDB:
    return DoctorDB.model_validate(model, from_attributes=True)

@app.get("/api/v1/doctors", response_model=list[DoctorDB])
def list_doctors():
    with get_db_manager(settings).session_scope() as session:
        return [_to_doctor_db(d) for d in get_all_doctors(session)]

@app.get("/api/v1/doctors/{doctor_id}", response_model=DoctorDB)
def get_doctor(doctor_id: int):
    with get_db_manager(settings).session_scope() as session:
        doctor = get_doctor_by_id(session, doctor_id)
        if doctor is None:
            raise HTTPException(status_code=404, detail=f"Doctor {doctor_id} not found")
        return _to_doctor_db(doctor)

@app.get("/api/v1/specialties", response_model=list[str])
def list_specialties():
    with get_db_manager(settings).session_scope() as session:
        return get_specialties(session)



@app.post("/api/v1/appointments", response_model=Appointment, status_code=201)
def book_appointment(request: AppointmentBookRequest, http_request: Request) -> Appointment:

    client_id = http_request.client.host if http_request.client else "unknown"
    if not rate_limiter.allow(client_id):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again shortly.")

    parts = request.slot_id.split("_")
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Invalid slot_id format.")

    doctor_name_key = "_".join(parts[:-2])
    doctor_name = doctor_name_key.replace("_", " ")
    date_str = parts[-2]
    time_str = parts[-1]

    try:
        appointment_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        appointment_time = f"{time_str[:2]}:{time_str[2:]}"
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slot date/time in slot_id.")

    reminder = (
        f"Reminder: your appointment with {doctor_name} is on {appointment_date} "
        f"at {appointment_time}. Please arrive 10 minutes early and bring any "
        "relevant medical history. Reply to reschedule."
    )

    with get_db_manager(settings).session_scope() as session:
        doctor = get_doctor_by_name(session, doctor_name)
        specialty = doctor.specialty if doctor else "General Practice"

        appointment = create_appointment(
            session=session,
            user_id=request.user_id,
            doctor_name=doctor_name,
            specialty=specialty,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reminder=reminder,
            notes=request.notes,
        )
        appointment_id = appointment.id

    return _load_appointment(appointment_id)

@app.get("/api/v1/appointments", response_model=list[Appointment])
def list_appointments(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id query parameter is required.")
    with get_db_manager(settings).session_scope() as session:
        rows = get_appointments_for_user(session, user_id)
        return [Appointment(
            id=a.id,
            user_id=a.user_id,
            doctor_name=a.doctor_name,
            specialty=a.specialty,
            appointment_date=a.appointment_date,
            appointment_time=a.appointment_time,
            status=a.status,
            reminder=a.reminder,
            created_at=a.created_at,
        ) for a in rows]

@app.patch("/api/v1/appointments/{appointment_id}", response_model=Appointment)
def cancel_appointment(appointment_id: int, status: str = "cancelled"):

    if status not in {"scheduled", "completed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid status value.")
    with get_db_manager(settings).session_scope() as session:
        appointment = update_appointment_status(session, appointment_id, status)
        if appointment is None:
            raise HTTPException(status_code=404, detail=f"Appointment {appointment_id} not found")
        appointment_id = appointment.id
    return _load_appointment(appointment_id)

def _load_appointment(appointment_id: int) -> Appointment:
    with get_db_manager(settings).session_scope() as session:
        from app.database import get_appointment_by_id

        a = get_appointment_by_id(session, appointment_id)
        if a is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return Appointment(
            id=a.id,
            user_id=a.user_id,
            doctor_name=a.doctor_name,
            specialty=a.specialty,
            appointment_date=a.appointment_date,
            appointment_time=a.appointment_time,
            status=a.status,
            reminder=a.reminder,
            created_at=a.created_at,
        )
