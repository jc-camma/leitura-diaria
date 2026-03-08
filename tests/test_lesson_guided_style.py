from app.lesson import BookEntry, generate_first_draft


def test_guided_reading_uses_explanatory_concept_style() -> None:
    entry = BookEntry(
        day=1,
        title="Habitos Atomicos",
        author="James Clear",
        theme="Construcao de habitos consistentes",
        key_ideas=[
            "Pequenas melhorias diarias geram crescimento composto.",
            "Ambiente desenhado supera motivacao eventual.",
            "Identidade guia comportamento sustentavel.",
            "Sistemas vencem metas isoladas.",
            "Rastreamento visual reforca consistencia.",
        ],
        practical_applications=[
            "Definir um habito minimo de 2 minutos para comecar hoje.",
            "Remover um atrito fisico de uma tarefa importante.",
            "Registrar a execucao do habito por 7 dias consecutivos.",
        ],
        reflection_question="Qual identidade profissional voce quer reforcar com um habito diario simples?",
    )

    lesson = generate_first_draft(entry)
    text = " ".join(lesson.guided_reading).lower()

    assert "cumpre funcao estrutural no livro" not in text
    assert "chave de leitura mais precisa" not in text
    assert "conceito 1 de habitos atomicos" in text
    assert "1.01^365" in text
    assert "passo pratico de hoje" in text
