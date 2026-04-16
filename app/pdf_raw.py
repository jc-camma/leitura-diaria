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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_pdf_filename(generation_date: date, day: int, title: str) -> str:
    short_title = _slugify_title(title)
    return f"{generation_date.isoformat()}_Dia{day:03d}_{short_title}.pdf"


def generate_raw_text_pdf(
    *,
    day: int,
    title: str,
    author: str,
    theme: str,
    raw_text: str,
    out_dir: Path,
    generation_date: date,
    youtube_video_url: str | None = None,
    youtube_video_title: str | None = None,
    read_confirmation_url: str | None = None,
    next_reading_url: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / build_pdf_filename(generation_date, day, title)

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

    story = [
        Paragraph(f"Dia {day:03d} - {title}", styles["Header"]),
        Paragraph(f"Autor: {author}", styles["Body"]),
        Paragraph(f"Tema: {theme}", styles["Body"]),
        Spacer(1, 6),
        Paragraph("Analise academica", styles["SubHeader"]),
    ]
    for block in _split_blocks(raw_text):
        story.append(Paragraph(_render_block(block), styles["Body"]))

    if youtube_video_url:
        story.extend(
            [
                Paragraph("Video recomendado", styles["SubHeader"]),
                Paragraph(_build_youtube_link_paragraph(youtube_video_url, youtube_video_title), styles["Body"]),
            ]
        )
    if read_confirmation_url:
        story.extend(
            [
                Paragraph("Confirmacao de leitura", styles["SubHeader"]),
                Paragraph(_build_confirmation_link_paragraph(read_confirmation_url), styles["Body"]),
            ]
        )
    if next_reading_url:
        story.extend(
            [
                Paragraph("Proxima leitura", styles["SubHeader"]),
                Paragraph(_build_next_reading_link_paragraph(next_reading_url), styles["Body"]),
            ]
        )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.0 * cm,
        title=f"MBA 15min - Dia {day}",
        author=author,
    )
    doc.build(
        story,
        onFirstPage=lambda canvas, _: _draw_footer(canvas, generation_date),
        onLaterPages=lambda canvas, _: _draw_footer(canvas, generation_date),
    )
    return output_path


def _slugify_title(title: str, limit: int = 42) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")
    safe = re.sub(r"_+", "_", safe)
    if not safe:
        safe = "Licao"
    return safe[:limit].rstrip("_")


def _split_blocks(raw_text: str) -> list[str]:
    text = raw_text.strip()
    if not text:
        return ["(Sem conteudo retornado pela IA)"]
    blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return blocks or [text]


def _render_block(text: str) -> str:
    escaped = escape(text, {'"': "&quot;"}).replace("\n", "<br/>")
    return escaped.replace("**", "").replace("__", "")


def _draw_footer(canvas, generation_date: date) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#4a5568"))
    canvas.drawString(2.0 * cm, 1.2 * cm, f"Gerado em {generation_date.isoformat()}  |  MBA 15min")
    canvas.restoreState()


def _build_youtube_link_paragraph(url: str, title: str | None) -> str:
    safe_url = escape(url, {'"': "&quot;"})
    label = escape(title or "Video recomendado no YouTube")
    return f'{label}<br/><link href="{safe_url}" color="blue"><u>{safe_url}</u></link>'


def _build_confirmation_link_paragraph(url: str) -> str:
    safe_url = escape(url, {'"': "&quot;"})
    return f'<link href="{safe_url}" color="blue"><u>Clique aqui para confirmar a leitura</u></link>'


def _build_next_reading_link_paragraph(url: str) -> str:
    safe_url = escape(url, {'"': "&quot;"})
    return f'<link href="{safe_url}" color="blue"><u>Clique aqui para receber a proxima leitura agora</u></link>'

