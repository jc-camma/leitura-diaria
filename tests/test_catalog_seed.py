from app.catalog_seed import build_balanced_catalog


def test_build_balanced_catalog_generates_diverse_full_year() -> None:
    payload = build_balanced_catalog()

    assert len(payload) == 365
    assert payload[0]["day"] == 1
    assert payload[-1]["day"] == 365
    assert all(item["author"] != "Autor a definir" for item in payload)

    categories = {item["category"] for item in payload}
    assert len(categories) >= 10
    assert "Ficcao classica" in categories
    assert "Ficcao moderna e contemporanea" in categories
    assert "Filosofia" in categories
    assert "Psicologia e comportamento" in categories
    assert "Economia e negocios" in categories
    assert "Geopolitica e relacoes internacionais" in categories
