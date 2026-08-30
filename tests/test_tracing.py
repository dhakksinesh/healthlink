
import os
from types import SimpleNamespace

from shared.tracing import configure_langsmith, tracing_enabled


class TestConfigureLangsmith:
    def test_enabled_sets_env(self, monkeypatch):
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)

        settings = SimpleNamespace(
            langchain_tracing_v2=True,
            langchain_api_key="ls-key-123",
            langchain_project="healthlink",
        )
        assert configure_langsmith(settings) is True
        assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
        assert os.environ["LANGCHAIN_API_KEY"] == "ls-key-123"
        assert os.environ["LANGCHAIN_PROJECT"] == "healthlink"
        assert tracing_enabled() is True

    def test_disabled_when_no_key(self, monkeypatch):
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

        settings = SimpleNamespace(
            langchain_tracing_v2=True,
            langchain_api_key="",
            langchain_project="healthlink",
        )
        assert configure_langsmith(settings) is False
        assert tracing_enabled() is False

    def test_does_not_override_existing_env(self, monkeypatch):
        monkeypatch.setenv("LANGCHAIN_API_KEY", "already-set")

        settings = SimpleNamespace(
            langchain_tracing_v2=True,
            langchain_api_key="ls-key-123",
            langchain_project="healthlink",
        )
        configure_langsmith(settings)

        assert os.environ["LANGCHAIN_API_KEY"] == "already-set"
