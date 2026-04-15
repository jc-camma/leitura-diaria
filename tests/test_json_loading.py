from pathlib import Path

from app.lesson import load_books


def test_books_json_has_365_days() -> None:
    data_file = Path(__file__).resolve().parent.parent / "data" / "books_365.json"
    books = load_books(data_file)
    assert len(books) == 365
    assert books[0].day == 1
    assert books[-1].day == 365
    assert all(book.author != "Autor a definir" for book in books)
    categories = {book.category for book in books if book.category}
    assert len(categories) >= 10
    assert "Ficcao classica" in categories
    assert "Ficcao moderna e contemporanea" in categories
    assert "Filosofia" in categories
    assert "Psicologia e comportamento" in categories
    assert "Economia e negocios" in categories
    assert "Geopolitica e relacoes internacionais" in categories
