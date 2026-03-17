"""Unit-Tests für llm/client.py."""
from unittest.mock import MagicMock, patch

import pytest
import openai

from gysi_ml.llm.client import call_llm
from gysi_ml.llm.exceptions import LLMConnectionError


def _make_fake_openai(content="test response", captured_kwargs: dict | None = None):
    """Erstellt eine Fake-OpenAI-Client-Factory mit konfigurierbarem Antwort-Content."""
    fake_message = MagicMock()
    fake_message.content = content
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_completion = MagicMock()
    fake_completion.choices = [fake_choice]

    def fake_openai_cls(**kw):
        if captured_kwargs is not None:
            captured_kwargs.update(kw)
        client = MagicMock()
        client.chat.completions.create.return_value = fake_completion
        return client

    return fake_openai_cls


def test_call_llm_returns_string(monkeypatch):
    """Mock OpenAI → gibt den Content-String zurück."""
    monkeypatch.setattr("gysi_ml.llm.client.openai.OpenAI", _make_fake_openai())
    result = call_llm(
        messages=[{"role": "user", "content": "Hallo"}],
        model="gpt-4o-mini",
        api_key="sk-test",
    )
    assert isinstance(result, str)
    assert result == "test response"


def test_call_llm_with_base_url(monkeypatch):
    """Prüft, dass base_url an den Client übergeben wird."""
    captured: dict = {}
    monkeypatch.setattr(
        "gysi_ml.llm.client.openai.OpenAI", _make_fake_openai(captured_kwargs=captured)
    )
    call_llm(
        messages=[{"role": "user", "content": "Test"}],
        model="gpt-4o-mini",
        api_key="sk-test",
        base_url="http://localhost:1234",
    )
    assert captured.get("base_url") == "http://localhost:1234"


def test_call_llm_without_base_url_does_not_set_it(monkeypatch):
    """Ohne base_url darf kein base_url an den Client übergeben werden."""
    captured: dict = {}
    monkeypatch.setattr(
        "gysi_ml.llm.client.openai.OpenAI", _make_fake_openai(captured_kwargs=captured)
    )
    call_llm(
        messages=[{"role": "user", "content": "Test"}],
        model="gpt-4o-mini",
        api_key="sk-test",
    )
    assert "base_url" not in captured


def test_call_llm_connection_error(monkeypatch):
    """Mock API-Verbindungsfehler → LLMConnectionError wird geworfen."""

    def fake_openai_cls(**kw):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIConnectionError(
            request=None
        )
        return client

    monkeypatch.setattr("gysi_ml.llm.client.openai.OpenAI", fake_openai_cls)

    with pytest.raises(LLMConnectionError):
        call_llm(
            messages=[{"role": "user", "content": "Test"}],
            model="gpt-4o-mini",
            api_key="sk-test",
        )


def test_call_llm_api_error(monkeypatch):
    """Mock generischer API-Fehler (z. B. AuthenticationError) → LLMConnectionError."""

    def fake_openai_cls(**kw):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.AuthenticationError(
            message="Incorrect API key",
            response=MagicMock(status_code=401),
            body={},
        )
        return client

    monkeypatch.setattr("gysi_ml.llm.client.openai.OpenAI", fake_openai_cls)

    with pytest.raises(LLMConnectionError):
        call_llm(
            messages=[{"role": "user", "content": "Test"}],
            model="gpt-4o-mini",
            api_key="sk-wrong",
        )

