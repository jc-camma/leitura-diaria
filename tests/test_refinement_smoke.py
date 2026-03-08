from app.main import refinement_smoke_test
from app.lesson import BookEntry


def test_refinement_smoke_prints_lengths(capsys) -> None:  # noqa: ANN001
    entry = BookEntry(
        day=1,
        title="Livro de teste",
        author="Autor",
        theme="Tomada de decisao",
        key_ideas=["Ideia 1", "Ideia 2", "Ideia 3", "Ideia 4", "Ideia 5"],
        practical_applications=["Acao 1", "Acao 2", "Acao 3"],
        reflection_question="Qual decisao devo melhorar hoje?",
        optional_quote="Feito e melhor que perfeito.",
    )
    refinement_smoke_test(entry, openai_api_key=None, openai_model="gpt-4.1-mini")
    captured = capsys.readouterr()
    assert "Before length:" in captured.out
    assert "After length:" in captured.out
