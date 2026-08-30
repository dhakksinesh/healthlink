
import logging
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.doctor import doctor_agent
from app.agents.scheduling import scheduling_agent
from app.agents.summary import summary_agent
from app.agents.symptom import symptom_agent
from app.database import get_db_manager
from app.observability import Trace, timed
from shared.config import get_settings
from shared.schemas import (
    DoctorRecommendation,
    DoctorSummary,
    HealthAssessmentRequest,
    HealthAssessmentResponse,
    HealthSummary,
    SchedulingRecommendation,
    SymptomExtraction,
)

logger = logging.getLogger("healthlink.orchestrator")

class PipelineState(TypedDict, total=False):
    request: HealthAssessmentRequest
    user_input: str
    patient_profile: dict
    preferred_date: str | None
    preferred_location: str | None
    clarifying_answers: list
    request_id: str
    trace: Trace
    symptom_analysis: SymptomExtraction
    doctor_recommendation: DoctorRecommendation
    scheduling_recommendation: SchedulingRecommendation
    health_summary: HealthSummary
    doctor_summary: DoctorSummary

def symptom_node(state: PipelineState) -> PipelineState:
    request = state["request"]
    trace: Trace = state["trace"]
    with timed("symptom-agent", trace):
        result = symptom_agent(
            user_input=request.user_input,
            settings=get_settings(),
            use_rag=True,
            clarifying_answers=request.clarifying_answers,
        )
    return {"symptom_analysis": result}

def doctor_node(state: PipelineState) -> PipelineState:
    trace: Trace = state["trace"]
    settings = get_settings()
    with timed("doctor-agent", trace):
        db_manager = get_db_manager(settings)
        with db_manager.session_scope() as session:
            result = doctor_agent(
                symptom_analysis=state["symptom_analysis"],
                db_session=session,
                settings=settings,
                max_recommendations=3,
                preferred_location=state.get("preferred_location"),
            )
    return {"doctor_recommendation": result}

def scheduling_node(state: PipelineState) -> PipelineState:
    trace: Trace = state["trace"]
    profile = state.get("patient_profile") or {}
    with timed("scheduling-agent", trace):
        result = scheduling_agent(
            doctor_recommendation=state["doctor_recommendation"],
            urgency_level=state["symptom_analysis"].urgency_level,
            settings=get_settings(),
            preferred_date=state.get("preferred_date"),
            preferred_time_of_day=profile.get("preferred_time_of_day"),
            consultation_type=profile.get("consultation_type"),
        )
    return {"scheduling_recommendation": result}

def summary_node(state: PipelineState) -> PipelineState:
    trace: Trace = state["trace"]
    with timed("summary-agent", trace):
        patient_summary, doctor_summary = summary_agent(
            symptom_analysis=state["symptom_analysis"],
            doctor_recommendation=state["doctor_recommendation"],
            scheduling_recommendation=state["scheduling_recommendation"],
            settings=get_settings(),
        )
    return {"health_summary": patient_summary, "doctor_summary": doctor_summary}

def build_graph():

    graph = StateGraph(PipelineState)
    graph.add_node("symptom", symptom_node)
    graph.add_node("doctor", doctor_node)
    graph.add_node("scheduling", scheduling_node)
    graph.add_node("summary", summary_node)

    graph.add_edge(START, "symptom")
    graph.add_edge("symptom", "doctor")
    graph.add_edge("doctor", "scheduling")
    graph.add_edge("scheduling", "summary")
    graph.add_edge("summary", END)

    return graph.compile()

_assessment_graph = None

def run_pipeline(request: HealthAssessmentRequest) -> HealthAssessmentResponse:

    global _assessment_graph
    if _assessment_graph is None:
        _assessment_graph = build_graph()

    request_id = _new_request_id()
    trace = Trace(request_id=request_id)
    logger.info(f"[{request_id}] Starting orchestration")

    profile = request.patient_profile.model_dump() if request.patient_profile else {}

    state = _assessment_graph.invoke({
        "request": request,
        "user_input": request.user_input,
        "patient_profile": profile,
        "preferred_date": request.preferred_date,
        "preferred_location": request.preferred_location,
        "clarifying_answers": request.clarifying_answers or [],
        "request_id": request_id,
        "trace": trace,
    })

    logger.info(f"[{request_id}] Orchestration complete ({trace.summary()['total_ms']:.0f} ms)")

    return HealthAssessmentResponse(
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        symptom_analysis=state["symptom_analysis"],
        doctor_recommendations=state["doctor_recommendation"],
        scheduling_options=state["scheduling_recommendation"],
        health_summary=state["health_summary"],
        doctor_summary=state["doctor_summary"],
        metadata={
            "user_id": request.user_id,
            "preferred_location": request.preferred_location,
            "trace": trace.summary(),
        },
    )

def _new_request_id() -> str:
    import uuid
    return str(uuid.uuid4())
