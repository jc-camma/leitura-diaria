from datetime import date

from app.emailer import build_email_body
from app.lesson import Lesson


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
