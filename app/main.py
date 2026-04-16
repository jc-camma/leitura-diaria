from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.analysis import generate_academic_analysis_with_openai
from app.catalog import build_year_plan, ensure_catalog_for_year, get_entry_for_day, load_catalog
from app.config import RuntimePaths
from app.models import BookEntry, Lesson
from app.pdf_raw import generate_raw_text_pdf
from app.youtube import YoutubeVideoReference, find_most_relevant_video


@dataclass(frozen=True)
class DailyArtifacts:
    entry: BookEntry
    lesson: Lesson
    analysis_text: str
    markdown_path: Path
    text_path: Path
    pdf_path: Path
    youtube_reference: YoutubeVideoReference


def prepare_daily_artifacts(
    *,
    day: int,
    runtime: RuntimePaths,
    generation_date: date,
    catalog_year: int,
    rebuild_catalog: bool = False,
    read_confirmation_url: str | None = None,
    next_reading_url: str | None = None,
) -> DailyArtifacts:
    catalog_path = ensure_catalog_for_year(
        data_dir=runtime.data_file.parent,
        year=catalog_year,
        openai_api_key=runtime.openai_api_key,
        openai_model=runtime.openai_model,
        rebuild=rebuild_catalog,
    )
    catalog = load_catalog(catalog_path)
    plan = build_year_plan(catalog)
    entry = get_entry_for_day(plan, day)

    analysis_text = generate_academic_analysis_with_openai(
        entry,
        openai_api_key=runtime.openai_api_key,
        openai_model=runtime.openai_model,
    )
    markdown_path, text_path = save_analysis_text_files(
        out_dir=runtime.out_dir,
        generation_date=generation_date,
        entry=entry,
        analysis_text=analysis_text,
    )
    lesson = build_lesson_envelope(entry, analysis_text)
    youtube_reference = find_most_relevant_video(lesson, youtube_api_key=runtime.youtube_api_key)
    pdf_path = generate_raw_text_pdf(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        raw_text=analysis_text,
        out_dir=runtime.out_dir,
        generation_date=generation_date,
        youtube_video_url=youtube_reference.url,
        youtube_video_title=youtube_reference.title,
        read_confirmation_url=read_confirmation_url,
        next_reading_url=next_reading_url,
    )
    return DailyArtifacts(
        entry=entry,
        lesson=lesson,
        analysis_text=analysis_text,
        markdown_path=markdown_path,
        text_path=text_path,
        pdf_path=pdf_path,
        youtube_reference=youtube_reference,
    )


def build_lesson_envelope(entry: BookEntry, analysis_text: str) -> Lesson:
    concepts = [f"{idx}. {item}" for idx, item in enumerate(entry.key_ideas[:5], start=1)]
    practical = [f"{idx}. {item}" for idx, item in enumerate(entry.practical_applications[:3], start=1)]
    return Lesson(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        central_idea=analysis_text.strip(),
        concepts=concepts,
        practical_applications=practical,
        reflection_question=entry.reflection_question.strip(),
        guided_reading=[],
        summary_bullets=[],
        optional_quote=entry.optional_quote.strip() if entry.optional_quote else None,
    )


def save_analysis_text_files(
    *,
    out_dir: Path,
    generation_date: date,
    entry: BookEntry,
    analysis_text: str,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"{generation_date.isoformat()}_Dia{entry.day:03d}_{_slugify(entry.title)}"
    markdown_path = out_dir / f"{base}.md"
    text_path = out_dir / f"{base}.txt"

    md_content = (
        f"# Dia {entry.day:03d} - {entry.title}\n\n"
        f"**Autor:** {entry.author}\n\n"
        f"**Tema:** {entry.theme}\n\n"
        f"**Area:** {entry.category or '-'}\n\n"
        f"{analysis_text.strip()}\n"
    )
    txt_content = (
        f"Dia {entry.day:03d} - {entry.title}\n\n"
        f"Autor: {entry.author}\n"
        f"Tema: {entry.theme}\n"
        f"Area: {entry.category or '-'}\n\n"
        f"{analysis_text.strip()}\n"
    )
    markdown_path.write_text(md_content, encoding="utf-8")
    text_path.write_text(txt_content, encoding="utf-8")
    return markdown_path, text_path


def _slugify(value: str, limit: int = 42) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    if not slug:
        slug = "leitura"
    return slug[:limit].rstrip("_")

