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
    read_confirmation_url: str | None = None,
) -> str:
    concepts = "\n".join([f"- {concept}" for concept in lesson.concepts])
    video_block = ""
    if youtube_video_url:
        video_label = youtube_video_title or "Video recomendado no YouTube"
        video_block = f"\n\nVideo recomendado:\n{video_label}\n{youtube_video_url}"
    confirmation_block = ""
    if read_confirmation_url:
        confirmation_block = (
            "\n\nQuando terminar a leitura, confirme aqui:\n"
            f"{read_confirmation_url}"
        )

    body = (
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
    )
    if confirmation_block:
        body += f"{confirmation_block}\n\n"
    body += "Bons estudos,\nMBA 15min"
    return body


def send_lesson_email(
    smtp_config: SmtpConfig,
    lesson: Lesson,
    pdf_path: Path,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
    read_confirmation_url: str | None = None,
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
            read_confirmation_url=read_confirmation_url,
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
        with _open_smtp_connection(smtp_config, context) as server:
            server.login(smtp_config.user, smtp_config.password)
            server.send_message(message)
    except Exception as exc:
        raise EmailSendError(f"Falha no envio SMTP: {exc}") from exc


def _open_smtp_connection(smtp_config: SmtpConfig, context: ssl.SSLContext):
    if smtp_config.port == 465:
        return smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, timeout=30, context=context)
    server = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30)
    server.starttls(context=context)
    return server
