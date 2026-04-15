from datetime import date

from app.emailer import build_email_body
from app.lesson import Lesson
from app.pdf_gen import _build_confirmation_link_paragraph, _build_next_reading_link_paragraph


def test_email_body_matches_new_editorial_format() -> None:
    lesson = Lesson(
        day=1,
        title="Titulo",
        author="Autor",
        theme="Tema",
        central_idea="Resumo",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["P1", "P2"],
        summary_bullets=["B1", "B2", "B3"],
    )
    body = build_email_body(
        lesson,
        date(2026, 3, 7),
        youtube_video_url="https://www.youtube.com/watch?v=abc123",
        youtube_video_title="Video teste",
    )
    assert "Resumo analitico do livro" in body
    assert "Principais conceitos do dia" in body
    assert "Video recomendado" in body
    assert "https://www.youtube.com/watch?v=abc123" in body


def test_email_body_includes_read_confirmation_link_when_available() -> None:
    lesson = Lesson(
        day=2,
        title="Titulo",
        author="Autor",
        theme="Tema",
        central_idea="Resumo",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["P1", "P2"],
        summary_bullets=["B1", "B2", "B3"],
    )
    body = build_email_body(
        lesson,
        date(2026, 3, 7),
        read_confirmation_url="https://example.com/confirm-read?token=abc",
    )
    assert "Quando terminar a leitura" in body
    assert "https://example.com/confirm-read?token=abc" in body


def test_email_body_includes_next_reading_link_when_available() -> None:
    lesson = Lesson(
        day=2,
        title="Titulo",
        author="Autor",
        theme="Tema",
        central_idea="Resumo",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["P1", "P2"],
        summary_bullets=["B1", "B2", "B3"],
    )
    body = build_email_body(
        lesson,
        date(2026, 3, 7),
        next_reading_url="https://example.com/send-next-reading?token=abc",
    )
    assert "Se quiser continuar hoje" in body
    assert "https://example.com/send-next-reading?token=abc" in body


def test_pdf_confirmation_paragraph_includes_link() -> None:
    paragraph = _build_confirmation_link_paragraph("https://example.com/confirm-read?token=abc")
    assert "Clique aqui para confirmar a leitura" in paragraph
    assert "https://example.com/confirm-read?token=abc" in paragraph


def test_pdf_next_reading_paragraph_includes_link() -> None:
    paragraph = _build_next_reading_link_paragraph("https://example.com/send-next-reading?token=abc")
    assert "Clique aqui para receber a proxima leitura agora" in paragraph
    assert "https://example.com/send-next-reading?token=abc" in paragraph
