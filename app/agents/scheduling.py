
import logging
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from shared.config import Settings, get_settings
from shared.llm import LLMClient, llm_generate
from shared.schemas import DoctorRecommendation, SchedulingRecommendation, TimeSlot

logger = logging.getLogger("healthlink.scheduling.agent")

def generate_time_slots(
    doctor_name: str,
    start_date: date,
    num_days: int = 14,
    slots_per_day: int = 8,
) -> list[TimeSlot]:

    slots = []
    working_hours = [9, 10, 11, 12, 14, 15, 16, 17]

    for day_offset in range(num_days):
        current_date = start_date + timedelta(days=day_offset)
        if current_date.weekday() >= 5:
            continue

        for hour in working_hours[:slots_per_day]:
            slots.append(TimeSlot(
                doctor_name=doctor_name,
                date=current_date.strftime("%Y-%m-%d"),
                time=f"{hour:02d}:00",
                duration_minutes=30,
                slot_id=f"{doctor_name.replace(' ', '_')}_{current_date.strftime('%Y%m%d')}_{hour:02d}00",
            ))

    return slots

def scheduling_agent(
    doctor_recommendation: DoctorRecommendation,
    urgency_level: str,
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
    preferred_date: str | None = None,
    preferred_time_of_day: str | None = None,
    consultation_type: str | None = None,
) -> SchedulingRecommendation:

    logger.info(f"Scheduling agent processing with urgency: {urgency_level}")

    if settings is None:
        settings = get_settings()

    start_date = datetime.now().date()
    if preferred_date:
        try:
            start_date = datetime.strptime(preferred_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid preferred date: {preferred_date}, using today")

    all_slots = []
    for doctor in doctor_recommendation.recommended_doctors:
        all_slots.extend(generate_time_slots(
            doctor_name=doctor.name,
            start_date=start_date,
            num_days=14,
            slots_per_day=8,
        ))

    if not all_slots:
        logger.warning("No available slots generated")
        return SchedulingRecommendation(
            available_slots=[],
            recommended_slot=None,
            scheduling_notes="No available appointments at this time. Please contact the clinic directly.",
        )

    class SlotSelection(BaseModel):
        recommended_slot_id: str = Field(..., description="ID of recommended slot")
        scheduling_notes: str = Field(..., description="Scheduling notes")

    try:
        slot_summary = "\n".join([
            f"- {slot.doctor_name}: {slot.date} at {slot.time}"
            for slot in all_slots[:12]
        ])

        recommendation_prompt = f"""Select the best appointment slot based on these criteria:

Urgency Level: {urgency_level}
Available Slots (showing first 12):
{slot_summary}

Preferred Date: {preferred_date or "None specified"}
Preferred Time of Day: {preferred_time_of_day or "No preference"}
Consultation Type: {consultation_type or "No preference"}

Select the most appropriate slot considering:
1. Urgency (higher urgency = sooner appointment)
2. User's preferred date if specified
3. Preferred time of day (morning/afternoon/evening) if specified
4. Convenient timing

Return the slot_id of the recommended slot and brief scheduling notes.
"""

        selection = llm_generate(
            prompt=recommendation_prompt,
            schema=SlotSelection,
            temperature=0.1,
            client=llm_client,
        )

        recommended_slot = next(
            (slot for slot in all_slots if slot.slot_id == selection.recommended_slot_id),
            all_slots[0] if all_slots else None,
        )

        logger.info(f"Generated {len(all_slots)} available slots")
        return SchedulingRecommendation(
            available_slots=all_slots[:20],
            recommended_slot=recommended_slot,
            scheduling_notes=selection.scheduling_notes,
        )

    except Exception as e:
        logger.error(f"Scheduling agent failed: {e}", exc_info=True)
        return SchedulingRecommendation(
            available_slots=all_slots[:20],
            recommended_slot=all_slots[0] if all_slots else None,
            scheduling_notes=f"First available appointment recommended. Urgency level: {urgency_level}",
        )
