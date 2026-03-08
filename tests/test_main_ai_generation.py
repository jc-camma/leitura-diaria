from app.lesson import BookEntry
from app.main import build_refined_lesson


def test_build_refined_lesson_uses_ai_summary_when_valid(monkeypatch) -> None:  # noqa: ANN001
    entry = BookEntry(
        day=1,
        title="Livro",
        author="Autor",
        theme="Tema",
        key_ideas=["I1", "I2", "I3", "I4", "I5"],
        practical_applications=["A1", "A2", "A3"],
        reflection_question="Pergunta?",
    )

    long_chunk = " ".join(["conteudo"] * 65)
    concepts_block = "\n\n".join(
        [
            f"Conceito: Conceito {idx}\nExplicacao: {long_chunk}\nExemplo: {long_chunk}"
            for idx in range(1, 6)
        ]
    )
    summary = (
        "1. Ideia central\n"
        f"{long_chunk}\n\n"
        "2. Por que este livro importa\n"
        f"{long_chunk}\n\n"
        "3. Conceitos fundamentais do livro\n"
        f"{concepts_block}\n\n"
        "4. Modelo mental ou estrutura apresentada pelo autor\n"
        f"{long_chunk}\n\n"
        "5. Exemplo ou historia marcante do livro\n"
        f"{long_chunk}\n\n"
        "6. Aplicacao pratica\n"
        "1. Acao pratica 1 com detalhe.\n"
        "2. Acao pratica 2 com detalhe.\n"
        "3. Acao pratica 3 com detalhe.\n\n"
        "7. Limitacoes ou criticas possiveis\n"
        f"{long_chunk}\n\n"
        "8. Sintese final\n"
        f"{long_chunk}\n"
    )

    monkeypatch.setattr("app.main.generate_book_summary_with_openai", lambda *args, **kwargs: summary)
    lesson = build_refined_lesson(entry, openai_api_key="key", openai_model="gpt-4.1-mini")

    assert lesson.central_idea.startswith("conteudo")
    assert lesson.concepts[0].startswith("1. Conceito 1")
    assert lesson.word_count() >= 900


def test_build_refined_lesson_with_openai_key_requires_ai_summary(monkeypatch) -> None:  # noqa: ANN001
    entry = BookEntry(
        day=1,
        title="Livro",
        author="Autor",
        theme="Tema",
        key_ideas=["I1", "I2", "I3", "I4", "I5"],
        practical_applications=["A1", "A2", "A3"],
        reflection_question="Pergunta?",
    )
    monkeypatch.setattr("app.main.generate_book_summary_with_openai", lambda *args, **kwargs: None)

    try:
        build_refined_lesson(entry, openai_api_key="key", openai_model="gpt-4.1-mini")
        assert False, "Era esperado RuntimeError quando a geracao IA falha."
    except RuntimeError as exc:
        assert "Falha ao gerar resumo com IA" in str(exc)
