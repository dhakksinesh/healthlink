
import logging

from app.rag import format_retrieval_context, retrieve_relevant_docs
from shared.config import Settings, get_settings
from shared.llm import LLMClient, llm_generate
from shared.schemas import SymptomExtraction

logger = logging.getLogger("healthlink.symptom.agent")

def symptom_agent(
    user_input: str,
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
    use_rag: bool = True,
    clarifying_answers: list[str] | None = None,
) -> SymptomExtraction:

    logger.info("Symptom agent processing user input")

    if settings is None:
        settings = get_settings()

    context = ""
    if use_rag:
        try:
            retrieval_result = retrieve_relevant_docs(user_input, k=settings.rag_top_k, settings=settings)
            context = format_retrieval_context(retrieval_result, max_docs=3)
            logger.debug(f"Retrieved {len(retrieval_result.documents)} relevant documents")
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}. Continuing without context.")

    answers_text = ""
    if clarifying_answers:
        logger.info(f"Clarifying answers provided: {clarifying_answers}")
        answers_text = "Patient answers to follow-up questions: " + " ".join(
            f"[{i + 1}] {answer}" for i, answer in enumerate(clarifying_answers)
        )

    prompt = f"""Analyze the following patient complaint and extract structured symptom information.

Patient Input: "{user_input}"
{answers_text}

Your task:
1. Identify all mentioned symptoms with their severity (mild, moderate, severe)
2. Note symptom duration if mentioned
3. Determine the primary health complaint
4. Assess urgency level based on symptoms:
   - emergency: Life-threatening symptoms (chest pain, difficulty breathing, severe bleeding, etc.)
   - high: Severe symptoms requiring prompt medical attention
   - medium: Moderate symptoms that should be evaluated soon
   - low: Mild symptoms for routine consultation
5. If important information is MISSING (e.g. how long symptoms have lasted, whether
   other symptoms are present, red-flag symptoms not yet asked about), generate up to
   3 clarifying questions the patient should answer. Examples:
   "Do you also have nausea or vision problems?", "How long have these symptoms lasted?",
   "Is the pain severe or getting worse?". If the input is detailed enough, return an
   empty list.

Be conservative with urgency assessment - if uncertain, err on the side of higher urgency.
"""

    try:
        result = llm_generate(
            prompt=prompt,
            schema=SymptomExtraction,
            temperature=0.2,
            context=context,
            client=llm_client,
        )


        if clarifying_answers:
            result.clarifying_questions = []

        logger.info(
            f"Symptom extraction complete: {len(result.symptoms)} symptoms, "
            f"urgency={result.urgency_level}, clarifying_questions={len(result.clarifying_questions)}"
        )
        return result

    except Exception as e:
        logger.error(f"Symptom agent failed: {e}", exc_info=True)
        return SymptomExtraction(
            symptoms=[],
            primary_complaint=user_input[:100],
            urgency_level="medium",
            additional_context="Error occurred during symptom analysis. Please consult a healthcare provider.",
            clarifying_questions=[],
        )
