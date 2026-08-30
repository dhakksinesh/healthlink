
import logging
import os

from shared.config import Settings

logger = logging.getLogger("healthlink.tracing")

def configure_langsmith(settings: Settings | None = None) -> bool:

    if settings is None:
        from shared.config import get_settings

        settings = get_settings()

    enabled = bool(settings.langchain_tracing_v2) and bool(settings.langchain_api_key)

    if enabled:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
        logger.info(
            f"LangSmith tracing ENABLED (project={settings.langchain_project}, "
            "llm=trace llm calls, agent=trace agent handoffs)"
        )
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        logger.info("LangSmith tracing disabled (set LANGCHAIN_TRACING_V2=true + a key to enable)")

    return enabled

def tracing_enabled() -> bool:

    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true" and bool(
        os.environ.get("LANGCHAIN_API_KEY")
    )
