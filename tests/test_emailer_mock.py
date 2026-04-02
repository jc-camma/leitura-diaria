from __future__ import annotations

from datetime import date
from pathlib import Path

from app.config import SmtpConfig
from app.emailer import send_lesson_email
from app.lesson import Lesson


class DummySMTP:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN003
        self.logged = False
        self.sent = False

    def __enter__(self) -> "DummySMTP":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def starttls(self, context=None) -> None:  # noqa: ANN001
        return None

    def login(self, user: str, password: str) -> None:
        self.logged = bool(user and password)

    def send_message(self, msg) -> None:  # noqa: ANN001
        self.sent = msg is not None


class DummySMTPSSL(DummySMTP):
    pass


def test_send_email_with_mock(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("smtplib.SMTP", DummySMTP)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%mock")

    lesson = Lesson(
        day=1,
        title="Teste",
        author="Autor",
        theme="Tema",
        central_idea="Ideia central longa.",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["Paragrafo 1", "Paragrafo 2"],
        summary_bullets=["B1", "B2", "B3"],
    )

    smtp = SmtpConfig(
        host="smtp.example.com",
        port=587,
        user="user",
        password="pass",
        email_from="from@example.com",
        email_to="to@example.com",
    )

    send_lesson_email(smtp, lesson, pdf, date(2026, 3, 5))


def test_send_email_uses_ssl_on_port_465(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("smtplib.SMTP_SSL", DummySMTPSSL)
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%mock")

    lesson = Lesson(
        day=1,
        title="Teste",
        author="Autor",
        theme="Tema",
        central_idea="Ideia central longa.",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["Paragrafo 1", "Paragrafo 2"],
        summary_bullets=["B1", "B2", "B3"],
    )

    smtp = SmtpConfig(
        host="smtp.example.com",
        port=465,
        user="user",
        password="pass",
        email_from="from@example.com",
        email_to="to@example.com",
    )

    send_lesson_email(smtp, lesson, pdf, date(2026, 3, 5))
