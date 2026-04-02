from __future__ import annotations

from datetime import date
from pathlib import Path

from app.lesson import Lesson
from app.pdf_gen import generate_lesson_pdf


def export_pdf(
    lesson: Lesson,
    out_dir: Path,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
    read_confirmation_url: str | None = None,
) -> Path:
    return generate_lesson_pdf(
        lesson,
        out_dir,
        generation_date,
        youtube_video_url=youtube_video_url,
        youtube_video_title=youtube_video_title,
        read_confirmation_url=read_confirmation_url,
    )
