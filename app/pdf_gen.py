from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from app.lesson import Lesson


def slugify_title(title: str, limit: int = 42) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")
    safe = re.sub(r"_+", "_", safe)
    if not safe:
        safe = "Licao"
    return safe[:limit].rstrip("_")


def build_pdf_filename(generation_date: date, day: int, title: str) -> str:
    short_title = slugify_title(title)
    return f"{generation_date.isoformat()}_Dia{day:03d}_{short_title}.pdf"


def generate_lesson_pdf(
    lesson: Lesson,
    out_dir: Path,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = build_pdf_filename(generation_date, lesson.day, lesson.title)
    output_path = out_dir / filename

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Header",
            parent=styles["Heading1"],
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#1c3d5a"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeader",
            parent=styles["Heading3"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#243447"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=15,
            spaceAfter=8,
        )
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.0 * cm,
        title=f"MBA 15min - Dia {lesson.day}",
        author=lesson.author,
    )

    story = [
        Paragraph(f"Dia {lesson.day:03d} - {lesson.title}", styles["Header"]),
        Paragraph(f"Autor: {lesson.author}", styles["Body"]),
        Paragraph(f"Tema: {lesson.theme}", styles["Body"]),
        Spacer(1, 6),
        Paragraph("Resumo do livro", styles["SubHeader"]),
    ]

    for paragraph in [lesson.central_idea, *lesson.guided_reading]:
        if paragraph.strip():
            story.append(Paragraph(_strip_markdown_emphasis(paragraph), styles["Body"]))

    story.extend(
        [
            Paragraph("Principais conceitos", styles["SubHeader"]),
            _bullet_list(lesson.concepts, styles["Body"]),
        ]
    )

    if youtube_video_url:
        story.extend(
            [
                Paragraph(
                    _build_youtube_link_paragraph(youtube_video_url, youtube_video_title),
                    styles["Body"],
                ),
            ]
        )

    doc.build(
        story,
        onFirstPage=lambda canvas, _: _draw_footer(canvas, generation_date),
        onLaterPages=lambda canvas, _: _draw_footer(canvas, generation_date),
    )
    return output_path


def _bullet_list(items: list[str], style: ParagraphStyle) -> ListFlowable:
    flow_items = [ListItem(Paragraph(_strip_markdown_emphasis(item), style), leftIndent=8) for item in items]
    return ListFlowable(flow_items, bulletType="bullet", leftIndent=14)


def _draw_footer(canvas, generation_date: date) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#4a5568"))
    canvas.drawString(2.0 * cm, 1.2 * cm, f"Gerado em {generation_date.isoformat()}  |  MBA 15min")
    canvas.restoreState()


def _build_youtube_link_paragraph(url: str, title: str | None) -> str:
    safe_url = escape(url, {'"': "&quot;"})
    _ = title
    return f'<link href="{safe_url}" color="blue"><u>Video recomendado no YouTube</u></link>'


def _strip_markdown_emphasis(text: str) -> str:
    return text.replace("**", "").replace("__", "")
