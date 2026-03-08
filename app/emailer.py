from __future__ import annotations

import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from app.config import SmtpConfig
from app.lesson import Lesson


class EmailSendError(RuntimeError):
    """Raised when SMTP sending fails."""


def build_email_subject(lesson: Lesson) -> str:
    return f"MBA 15min - Dia {lesson.day}: {lesson.title}"


def build_email_body(
    lesson: Lesson,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
) -> str:
    concepts = "\n".join([f"- {concept}" for concept in lesson.concepts])
    video_block = ""
    if youtube_video_url:
        video_label = youtube_video_title or "Video recomendado no YouTube"
        video_block = f"\n\nVideo recomendado:\n{video_label}\n{youtube_video_url}"

    return (
        "Bom dia,\n\n"
        f"Segue a leitura do Dia {lesson.day} em anexo (PDF).\n"
        f"Tema: {lesson.theme}\n"
        f"Data de geracao: {generation_date.isoformat()}\n\n"
        "Formato desta edicao:\n"
        "- Resumo analitico do livro\n"
        "- Principais conceitos\n"
        "- Link de video complementar\n\n"
        "Principais conceitos do dia:\n"
        f"{concepts}"
        f"{video_block}\n\n"
        "Leitura estimada: 10 a 15 minutos.\n\n"
        "Bons estudos,\n"
        "MBA 15min"
    )


def send_lesson_email(
    smtp_config: SmtpConfig,
    lesson: Lesson,
    pdf_path: Path,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
) -> None:
    message = EmailMessage()
    message["Subject"] = build_email_subject(lesson)
    message["From"] = smtp_config.email_from
    message["To"] = smtp_config.email_to
    message.set_content(
        build_email_body(
            lesson,
            generation_date,
            youtube_video_url=youtube_video_url,
            youtube_video_title=youtube_video_title,
        )
    )

    with pdf_path.open("rb") as fh:
        pdf_bytes = fh.read()
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as server:
            server.starttls(context=context)
            server.login(smtp_config.user, smtp_config.password)
            server.send_message(message)
    except Exception as exc:
        raise EmailSendError(f"Falha no envio SMTP: {exc}") from exc
