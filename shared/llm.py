
import json
import logging
import time
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.config import Settings, get_settings

logger = logging.getLogger("healthlink.llm")

T = TypeVar('T', bound=BaseModel)

class LLMClient:


    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.openrouter_model

        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            max_tokens=None if settings.llm_max_tokens <= 0 else settings.llm_max_tokens,
            max_retries=2,
        )

        logger.info(f"LLM client initialized with model: {self.model_name}")

    def _build_llm(self, temperature: float | None, max_tokens: int | None) -> ChatOpenAI:
        if temperature is None and max_tokens is None:
            return self.llm
        return ChatOpenAI(
            model=self.model_name,
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            temperature=temperature if temperature is not None else self.settings.llm_temperature,
            max_tokens=max_tokens
            if max_tokens is not None
            else (None if self.settings.llm_max_tokens <= 0 else self.settings.llm_max_tokens),
            max_retries=2,
        )

    def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_instruction: str | None = None,
    ) -> str:

        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))

        start = time.monotonic()
        response = self._build_llm(temperature, max_tokens).invoke(messages)
        elapsed = (time.monotonic() - start) * 1000
        logger.debug(f"LLM text call took {elapsed:.0f} ms")
        return response.content

    def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        system_instruction: str | None = None,
    ) -> T:

        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))

        llm = self._build_llm(temperature, None)
        start = time.monotonic()
        structured_llm = llm.with_structured_output(response_schema)
        result = structured_llm.invoke(messages)
        elapsed = (time.monotonic() - start) * 1000
        logger.debug(f"LLM structured call for {response_schema.__name__} took {elapsed:.0f} ms")
        return result

_llm_client: LLMClient | None = None

def get_llm_client(settings: Settings | None = None) -> LLMClient:

    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(settings or get_settings())
    return _llm_client

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def llm_generate(
    prompt: str,
    schema: type[T],
    temperature: float | None = None,
    context: str | None = None,
    client: LLMClient | None = None,
) -> T:

    if client is None:
        client = get_llm_client()

    full_prompt = f"TASK:\n{prompt}"
    if context:
        full_prompt += f"\n\nCONTEXT:\n{context}"

    logger.debug(f"Generating with schema: {schema.__name__}")

    try:
        result = client.generate_structured(
            prompt=full_prompt,
            response_schema=schema,
            temperature=temperature,
            system_instruction=(
                "You are a helpful medical information assistant. Provide structured, "
                "accurate responses. Never provide definitive diagnoses."
            ),
        )
        logger.info(f"Successfully generated and validated {schema.__name__}")
        return result

    except Exception as e:
        logger.warning(f"Structured generation failed, falling back to text mode: {e}")
        return generate_with_text_fallback(client, prompt, schema, temperature, context)

def generate_with_text_fallback(
    client: LLMClient,
    prompt: str,
    schema: type[T],
    temperature: float | None,
    context: str | None,
) -> T:

    schema_json = schema.model_json_schema()
    schema_description = json.dumps(schema_json, indent=2)

    enhanced_prompt = (
        "You are a medical information assistant. Respond with ONLY valid JSON "
        "matching the schema below.\n\n"
        f"SCHEMA:\n{schema_description}\n\nTASK:\n{prompt}"
    )
    if context:
        enhanced_prompt += f"\n\nCONTEXT:\n{context}"
    enhanced_prompt += "\n\nRESPONSE (JSON only, no markdown, no explanation):"

    response_text = client.generate(prompt=enhanced_prompt, temperature=temperature)

    cleaned_response = response_text.strip()
    cleaned_response = cleaned_response.removeprefix("```json")
    cleaned_response = cleaned_response.removeprefix("```")
    cleaned_response = cleaned_response.removesuffix("```")
    cleaned_response = cleaned_response.strip()

    try:
        response_dict = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}. Response: {cleaned_response}")
        raise ValueError(f"LLM returned invalid JSON: {e!s}")

    try:
        validated_output = schema(**response_dict)
        logger.info(f"Successfully generated and validated {schema.__name__} (fallback)")
        return validated_output
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        corrected_output = attempt_correction(response_dict, schema, e)
        if corrected_output:
            return corrected_output
        raise

def attempt_correction(data: dict[str, Any], schema: type[T], error: ValidationError) -> T | None:

    try:
        corrected_data = data.copy()

        for err in error.errors():
            field_path = err['loc']
            error_type = err['type']

            if error_type == 'missing':
                field_name = field_path[0] if field_path else None
                if field_name:
                    field_info = schema.model_fields.get(field_name)
                    if field_info:
                        if field_info.default is not None:
                            corrected_data[field_name] = field_info.default
                        elif field_info.annotation == str:
                            corrected_data[field_name] = ""
                        elif field_info.annotation == list:
                            corrected_data[field_name] = []
                        elif field_info.annotation == dict:
                            corrected_data[field_name] = {}

        return schema(**corrected_data)

    except Exception as e:
        logger.warning(f"Correction attempt failed: {e}")
        return None
