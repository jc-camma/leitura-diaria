from __future__ import annotations

from pathlib import Path

from app.lesson import BookEntry, get_entry_for_day, load_books


def select_daily_entry(data_file: Path, day: int) -> BookEntry:
    books = load_books(data_file)
    return get_entry_for_day(books, day)
