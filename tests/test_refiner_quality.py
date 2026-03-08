from app.lesson import Lesson
from app.quality import evaluate_lesson_quality
from app.refiner import refine_lesson_local


def _sample_lesson() -> Lesson:
    return Lesson(
        day=1,
        title="Livro",
        author="Autor",
        theme="Tema",
        central_idea="No contexto de uma equipe, de forma passiva as decisoes perdem clareza.",
        concepts=[
            "1. Mapear a decisao",
            "2. Mapear a decisao",
            "3. Mapear a decisao",
            "4. Mapear a decisao",
            "5. Mapear a decisao",
            "6. Mapear a decisao",
            "7. Mapear a decisao",
        ],
        practical_applications=["1. Fazer reuniao", "2. Fazer reuniao", "3. Fazer reuniao"],
        reflection_question="Como melhorar?",
        guided_reading=[
            "O time executa sem criterio claro.",
            "O time executa sem revisar riscos.",
            "O time executa sem registrar aprendizados.",
        ],
        summary_bullets=["B1", "B2", "B3"],
    )


def test_local_refiner_preserves_core_concepts() -> None:
    lesson = refine_lesson_local(_sample_lesson())
    assert len(lesson.concepts) == 7
    assert lesson.concepts[0].startswith("1. Mapear a decisao")
    assert lesson.concepts[-1].startswith("7. Mapear a decisao")
    assert all("criterio de interpretacao" not in item.lower() for item in lesson.practical_applications)


def test_quality_detects_repetition_signals() -> None:
    report = evaluate_lesson_quality(_sample_lesson())
    codes = {issue.code for issue in report.issues}
    assert "repeated_paragraph_opening" in codes
    assert "banned_expression" in codes
    assert "similar_concept_structure" in codes
