from __future__ import annotations

import sys
import types

from app.lesson import BookEntry
from app.openai_refiner import refine_text_with_openai
from app.openai_refiner import generate_book_summary_with_openai


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


def test_openai_refiner_success(monkeypatch) -> None:  # noqa: ANN001
    class _Completions:
        @staticmethod
        def create(**kwargs):  # noqa: ANN003
            return _FakeResponse("texto refinado")

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, api_key: str) -> None:
            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(OpenAI=_Client)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    assert refine_text_with_openai("texto base") == "texto refinado"


def test_openai_refiner_fallback_after_retries(monkeypatch) -> None:  # noqa: ANN001
    calls = {"n": 0}

    class _Completions:
        @staticmethod
        def create(**kwargs):  # noqa: ANN003
            calls["n"] += 1
            raise RuntimeError("rate limit")

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, api_key: str) -> None:
            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(OpenAI=_Client)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setattr("app.openai_refiner.time.sleep", lambda _: None)
    assert refine_text_with_openai("texto base") == "texto base"
    assert calls["n"] == 3


def test_generate_book_summary_with_openai(monkeypatch) -> None:  # noqa: ANN001
    class _Completions:
        @staticmethod
        def create(**kwargs):  # noqa: ANN003
            return _FakeResponse("1. Ideia central\nResumo")

    class _Chat:
        completions = _Completions()

    class _Client:
        def __init__(self, api_key: str) -> None:
            self.chat = _Chat()

    fake_openai = types.SimpleNamespace(OpenAI=_Client)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    entry = BookEntry(
        day=1,
        title="Livro",
        author="Autor",
        theme="Tema",
        key_ideas=["I1", "I2", "I3", "I4", "I5"],
        practical_applications=["A1", "A2", "A3"],
        reflection_question="Pergunta?",
    )
    result = generate_book_summary_with_openai(entry, openai_api_key="key", openai_model="gpt-4.1-mini")
    assert result == "1. Ideia central\nResumo"
