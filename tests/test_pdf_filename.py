from datetime import date

from app.pdf_gen import build_pdf_filename


def test_pdf_filename_pattern() -> None:
    filename = build_pdf_filename(date(2026, 3, 5), 7, "A Coragem de Liderar!")
    assert filename == "2026-03-05_Dia007_A_Coragem_de_Liderar.pdf"

