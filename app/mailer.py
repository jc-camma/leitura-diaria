from __future__ import annotations

from datetime import date
from pathlib import Path

from app.config import SmtpConfig
from app.emailer import EmailSendError, send_lesson_email
from app.models import Lesson


def deliver_lesson_email(
    smtp_config: SmtpConfig,
    lesson: Lesson,
    pdf_path: Path,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
    read_confirmation_url: str | None = None,
    next_reading_url: str | None = None,
) -> None:
    send_lesson_email(
        smtp_config,
        lesson,
        pdf_path,
        generation_date,
        youtube_video_url=youtube_video_url,
        youtube_video_title=youtube_video_title,
        read_confirmation_url=read_confirmation_url,
        next_reading_url=next_reading_url,
    )


__all__ = ["EmailSendError", "deliver_lesson_email"]
