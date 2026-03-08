from app.formatter import lesson_from_refinement_text, lesson_to_refinement_text
from app.lesson import Lesson


def test_formatter_roundtrip_keeps_sections() -> None:
    lesson = Lesson(
        day=10,
        title="Titulo",
        author="Autor",
        theme="Tema",
        central_idea="Ideia central",
        concepts=["1. C1", "2. C2", "3. C3", "4. C4", "5. C5", "6. C6", "7. C7"],
        practical_applications=["1. A1", "2. A2", "3. A3"],
        reflection_question="Pergunta?",
        guided_reading=["Paragrafo um.", "Paragrafo dois."],
        summary_bullets=["B1", "B2", "B3"],
        optional_quote="Frase curta",
    )
    text = lesson_to_refinement_text(lesson)
    parsed = lesson_from_refinement_text(lesson, text)
    assert parsed is not None
    assert parsed.title == lesson.title
    assert len(parsed.concepts) == 7
    assert len(parsed.practical_applications) == 3
